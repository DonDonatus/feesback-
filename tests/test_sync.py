import uuid
from datetime import datetime, timezone
from decimal import Decimal
from app.schemas.sync import SyncPushRequest, SyncLogItem


def test_sync_push_and_pull(client):
    # 1. Simulate Local Node pushing a class and student
    class_id = str(uuid.uuid4())
    student_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    items = [
        SyncLogItem(
            seq=1,
            table="classes",
            row_id=class_id,
            action="INSERT",
            payload={
                "id": class_id,
                "name": "Class from Local",
                "created_at": now_iso,
                "updated_at": now_iso
            },
            created_at=datetime.now(timezone.utc)
        ),
        SyncLogItem(
            seq=2,
            table="students",
            row_id=student_id,
            action="INSERT",
            payload={
                "id": student_id,
                "admission_no": "LOC-101",
                "name": "Local Student",
                "guardian_phone": "0240000000",
                "class_id": class_id,
                "status": "active",
                "created_at": now_iso,
                "updated_at": now_iso
            },
            created_at=datetime.now(timezone.utc)
        )
    ]

    push_res = client.post("/sync/push", json={"items": [i.model_dump(mode="json") for i in items]})
    assert push_res.status_code == 200
    push_data = push_res.json()
    assert push_data["synced_seqs"] == [1, 2]
    assert push_data["processed_count"] == 2

    # Verify the records now exist in the database
    c_res = client.get("/classes")
    assert any(c["id"] == class_id for c in c_res.json())

    s_res = client.get(f"/students/{student_id}")
    assert s_res.status_code == 200
    assert s_res.json()["name"] == "Local Student"

    # 2. Test Pull
    pull_res = client.get("/sync/pull")
    assert pull_res.status_code == 200
    pull_data = pull_res.json()
    assert any(c["id"] == class_id for c in pull_data["classes"])
    assert any(s["id"] == student_id for s in pull_data["students"])
