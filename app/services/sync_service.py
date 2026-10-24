from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.school import ClassModel, StudentModel, FeeModel
from app.models.payment import PaymentModel
from app.schemas.sync import SyncLogItem, SyncPushResponse, SyncPullResponse
from app.services.audit import SuppressSyncLogging, serialize_for_sync


def parse_datetime(val: Any) -> Optional[datetime]:
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        return datetime.fromisoformat(val)
    return None


def process_cloud_push(db: Session, items: List[SyncLogItem]) -> SyncPushResponse:
    """
    Executed on Cloud Node when Local pushes a batch of sync_log rows.
    - Payments: Append-only (insert if not present, never mutate).
    - Students / Classes / Fees: Last-Write-Wins based on updated_at.
    """
    synced_seqs: List[int] = []

    for item in items:
        table = item.table.lower()
        payload = item.payload
        row_id = item.row_id

        if table == "payments":
            existing = db.get(PaymentModel, row_id)
            if not existing:
                payment = PaymentModel(
                    id=row_id,
                    student_id=payload["student_id"],
                    term=payload["term"],
                    amount=Decimal(str(payload["amount"])),
                    method=payload["method"],
                    reference=payload["reference"],
                    paid_at=parse_datetime(payload.get("paid_at")) or datetime.now(timezone.utc),
                    reverses_id=payload.get("reverses_id"),
                    created_at=parse_datetime(payload.get("created_at")) or datetime.now(timezone.utc)
                )
                db.add(payment)

        elif table == "classes":
            existing = db.get(ClassModel, row_id)
            incoming_updated_at = parse_datetime(payload.get("updated_at")) or datetime.now(timezone.utc)
            if not existing:
                school_class = ClassModel(
                    id=row_id,
                    name=payload["name"],
                    created_at=parse_datetime(payload.get("created_at")) or datetime.now(timezone.utc),
                    updated_at=incoming_updated_at
                )
                db.add(school_class)
            else:
                # Last-write-wins
                if existing.updated_at is None or incoming_updated_at >= existing.updated_at:
                    existing.name = payload["name"]
                    existing.updated_at = incoming_updated_at

        elif table == "students":
            existing = db.get(StudentModel, row_id)
            incoming_updated_at = parse_datetime(payload.get("updated_at")) or datetime.now(timezone.utc)
            if not existing:
                student = StudentModel(
                    id=row_id,
                    admission_no=payload["admission_no"],
                    name=payload["name"],
                    guardian_phone=payload["guardian_phone"],
                    class_id=payload["class_id"],
                    status=payload.get("status", "active"),
                    created_at=parse_datetime(payload.get("created_at")) or datetime.now(timezone.utc),
                    updated_at=incoming_updated_at
                )
                db.add(student)
            else:
                # Last-write-wins
                if existing.updated_at is None or incoming_updated_at >= existing.updated_at:
                    existing.admission_no = payload["admission_no"]
                    existing.name = payload["name"]
                    existing.guardian_phone = payload["guardian_phone"]
                    existing.class_id = payload["class_id"]
                    existing.status = payload.get("status", existing.status)
                    existing.updated_at = incoming_updated_at

        elif table == "fees":
            existing = db.get(FeeModel, row_id)
            incoming_updated_at = parse_datetime(payload.get("updated_at")) or datetime.now(timezone.utc)
            if not existing:
                fee = FeeModel(
                    id=row_id,
                    class_id=payload["class_id"],
                    term=payload["term"],
                    amount=Decimal(str(payload["amount"])),
                    created_at=parse_datetime(payload.get("created_at")) or datetime.now(timezone.utc),
                    updated_at=incoming_updated_at
                )
                db.add(fee)
            else:
                # Last-write-wins
                if existing.updated_at is None or incoming_updated_at >= existing.updated_at:
                    existing.class_id = payload["class_id"]
                    existing.term = payload["term"]
                    existing.amount = Decimal(str(payload["amount"]))
                    existing.updated_at = incoming_updated_at

        synced_seqs.append(item.seq)

    db.commit()
    return SyncPushResponse(
        synced_seqs=synced_seqs,
        processed_count=len(synced_seqs),
        message="Sync push processed successfully"
    )


def process_cloud_pull(db: Session, since: Optional[datetime]) -> SyncPullResponse:
    """
    Executed on Cloud Node when Local requests changes since a given timestamp.
    """
    now = datetime.now(timezone.utc)

    # Classes
    class_q = select(ClassModel)
    if since:
        class_q = class_q.where(ClassModel.updated_at >= since)
    classes = [
        serialize_for_sync({
            "id": c.id, "name": c.name,
            "created_at": c.created_at, "updated_at": c.updated_at
        })
        for c in db.execute(class_q).scalars().all()
    ]

    # Students
    stud_q = select(StudentModel)
    if since:
        stud_q = stud_q.where(StudentModel.updated_at >= since)
    students = [
        serialize_for_sync({
            "id": s.id, "admission_no": s.admission_no, "name": s.name,
            "guardian_phone": s.guardian_phone, "class_id": s.class_id,
            "status": s.status, "created_at": s.created_at, "updated_at": s.updated_at
        })
        for s in db.execute(stud_q).scalars().all()
    ]

    # Fees
    fee_q = select(FeeModel)
    if since:
        fee_q = fee_q.where(FeeModel.updated_at >= since)
    fees = [
        serialize_for_sync({
            "id": f.id, "class_id": f.class_id, "term": f.term,
            "amount": f.amount, "created_at": f.created_at, "updated_at": f.updated_at
        })
        for f in db.execute(fee_q).scalars().all()
    ]

    # Payments (append-only)
    pay_q = select(PaymentModel)
    if since:
        pay_q = pay_q.where(PaymentModel.created_at >= since)
    payments = [
        serialize_for_sync({
            "id": p.id, "student_id": p.student_id, "term": p.term,
            "amount": p.amount, "method": p.method, "reference": p.reference,
            "paid_at": p.paid_at, "reverses_id": p.reverses_id, "created_at": p.created_at
        })
        for p in db.execute(pay_q).scalars().all()
    ]

    return SyncPullResponse(
        classes=classes,
        students=students,
        fees=fees,
        payments=payments,
        synced_at=now
    )


def apply_pull_to_local(db: Session, pull_data: SyncPullResponse) -> None:
    """
    Applies cloud updates down to local SQLite database with sync logging suppressed.
    """
    with SuppressSyncLogging():
        # Apply classes
        for c_dict in pull_data.classes:
            existing = db.get(ClassModel, c_dict["id"])
            up_at = parse_datetime(c_dict["updated_at"])
            if not existing:
                db.add(ClassModel(
                    id=c_dict["id"],
                    name=c_dict["name"],
                    created_at=parse_datetime(c_dict["created_at"]),
                    updated_at=up_at
                ))
            elif existing.updated_at is None or up_at >= existing.updated_at:
                existing.name = c_dict["name"]
                existing.updated_at = up_at

        # Apply fees (must be before students if referenced, or class)
        for f_dict in pull_data.fees:
            existing = db.get(FeeModel, f_dict["id"])
            up_at = parse_datetime(f_dict["updated_at"])
            if not existing:
                db.add(FeeModel(
                    id=f_dict["id"],
                    class_id=f_dict["class_id"],
                    term=f_dict["term"],
                    amount=Decimal(str(f_dict["amount"])),
                    created_at=parse_datetime(f_dict["created_at"]),
                    updated_at=up_at
                ))
            elif existing.updated_at is None or up_at >= existing.updated_at:
                existing.class_id = f_dict["class_id"]
                existing.term = f_dict["term"]
                existing.amount = Decimal(str(f_dict["amount"]))
                existing.updated_at = up_at

        # Apply students
        for s_dict in pull_data.students:
            existing = db.get(StudentModel, s_dict["id"])
            up_at = parse_datetime(s_dict["updated_at"])
            if not existing:
                db.add(StudentModel(
                    id=s_dict["id"],
                    admission_no=s_dict["admission_no"],
                    name=s_dict["name"],
                    guardian_phone=s_dict["guardian_phone"],
                    class_id=s_dict["class_id"],
                    status=s_dict.get("status", "active"),
                    created_at=parse_datetime(s_dict["created_at"]),
                    updated_at=up_at
                ))
            elif existing.updated_at is None or up_at >= existing.updated_at:
                existing.admission_no = s_dict["admission_no"]
                existing.name = s_dict["name"]
                existing.guardian_phone = s_dict["guardian_phone"]
                existing.class_id = s_dict["class_id"]
                existing.status = s_dict.get("status", existing.status)
                existing.updated_at = up_at

        # Apply payments
        for p_dict in pull_data.payments:
            existing = db.get(PaymentModel, p_dict["id"])
            if not existing:
                db.add(PaymentModel(
                    id=p_dict["id"],
                    student_id=p_dict["student_id"],
                    term=p_dict["term"],
                    amount=Decimal(str(p_dict["amount"])),
                    method=p_dict["method"],
                    reference=p_dict["reference"],
                    paid_at=parse_datetime(p_dict["paid_at"]),
                    reverses_id=p_dict.get("reverses_id"),
                    created_at=parse_datetime(p_dict["created_at"])
                ))

        db.commit()
