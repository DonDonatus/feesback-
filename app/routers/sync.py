from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, update
import httpx
from app.config import settings
from app.database import get_db
from app.models.sync import SyncLogModel
from app.schemas.sync import (
    SyncPushRequest, SyncPushResponse, SyncPullResponse, SyncLogItem
)
from app.services.sync_service import (
    process_cloud_push, process_cloud_pull, apply_pull_to_local
)

router = APIRouter(prefix="/sync", tags=["Sync"])


@router.post("/push", response_model=SyncPushResponse)
def sync_push(
    request: SyncPushRequest,
    db: Session = Depends(get_db)
):
    """
    Cloud Node handler for receiving pushed sync_log entries.
    Payments are append-only. Classes, students, and fees use Last-Write-Wins.
    """
    return process_cloud_push(db, request.items)


@router.get("/pull", response_model=SyncPullResponse)
def sync_pull(
    since: Optional[datetime] = Query(None, description="ISO timestamp to fetch records modified after"),
    db: Session = Depends(get_db)
):
    """
    Cloud Node handler to return all records modified or created since the last pull.
    """
    return process_cloud_pull(db, since)


@router.post("/trigger")
def trigger_sync_from_local(
    db: Session = Depends(get_db)
):
    """
    Local Node action:
    1. Reads unsynced records from sync_log.
    2. Pushes them to Cloud Node (/sync/push). Marks acknowledged records as synced=True.
    3. Pulls new records from Cloud Node (/sync/pull) and applies them locally.
    """
    if settings.NODE_TYPE != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trigger sync is intended for local nodes"
        )

    # 1. Gather unsynced entries
    unsynced_entries = db.execute(
        select(SyncLogModel).where(SyncLogModel.synced == False).order_by(SyncLogModel.seq)
    ).scalars().all()

    pushed_count = 0
    pulled_count = 0

    try:
        with httpx.Client(base_url=settings.SYNC_REMOTE_URL, timeout=15.0) as client:
            # 2. PUSH
            if unsynced_entries:
                items = [
                    SyncLogItem(
                        seq=e.seq,
                        table=e.table,
                        row_id=e.row_id,
                        action=e.action,
                        payload=e.payload,
                        created_at=e.created_at
                    )
                    for e in unsynced_entries
                ]
                push_res = client.post("/sync/push", json={"items": [i.model_dump(mode="json") for i in items]})
                if push_res.status_code == 200:
                    resp_data = push_res.json()
                    synced_seqs = resp_data.get("synced_seqs", [])
                    if synced_seqs:
                        db.execute(
                            update(SyncLogModel)
                            .where(SyncLogModel.seq.in_(synced_seqs))
                            .values(synced=True)
                        )
                        db.commit()
                        pushed_count = len(synced_seqs)

            # 3. PULL
            pull_res = client.get("/sync/pull")
            if pull_res.status_code == 200:
                pull_data = SyncPullResponse(**pull_res.json())
                apply_pull_to_local(db, pull_data)
                pulled_count = (
                    len(pull_data.classes) + len(pull_data.students) +
                    len(pull_data.fees) + len(pull_data.payments)
                )

    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to reach cloud node at '{settings.SYNC_REMOTE_URL}'. Are you connected to the internet?"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync error: {str(exc)}"
        )

    return {
        "status": "success",
        "pushed": pushed_count,
        "pulled": pulled_count,
        "pushed_records": pushed_count,
        "pulled_records": pulled_count,
        "synced_at": datetime.now(timezone.utc).isoformat()
    }
