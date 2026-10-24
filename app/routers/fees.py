import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.school import FeeModel, ClassModel
from app.schemas.school import FeeCreate, FeeResponse
from app.services.audit import log_sync_event

router = APIRouter(prefix="/fees", tags=["Fees"])


@router.post("", response_model=FeeResponse, status_code=status.HTTP_201_CREATED)
def create_fee(fee_in: FeeCreate, db: Session = Depends(get_db)):
    # Verify class exists
    school_class = db.get(ClassModel, fee_in.class_id)
    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class '{fee_in.class_id}' does not exist"
        )

    fee_id = fee_in.id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    fee = FeeModel(
        id=fee_id,
        class_id=fee_in.class_id,
        term=fee_in.term,
        amount=fee_in.amount,
        created_at=now,
        updated_at=now
    )
    db.add(fee)
    db.flush()

    # Log to sync_log
    log_sync_event(
        db=db,
        table_name="fees",
        row_id=fee.id,
        action="INSERT",
        payload={
            "id": fee.id,
            "class_id": fee.class_id,
            "term": fee.term,
            "amount": fee.amount,
            "created_at": fee.created_at,
            "updated_at": fee.updated_at
        }
    )

    db.commit()
    db.refresh(fee)
    return fee


@router.get("", response_model=List[FeeResponse])
def list_fees(
    class_id: Optional[str] = Query(None, description="Filter by class ID"),
    term: Optional[str] = Query(None, description="Filter by academic term"),
    db: Session = Depends(get_db)
):
    query = select(FeeModel)
    if class_id:
        query = query.where(FeeModel.class_id == class_id)
    if term:
        query = query.where(FeeModel.term == term)

    fees = db.execute(query).scalars().all()
    return fees
