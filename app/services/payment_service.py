import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.payment import PaymentModel
from app.models.school import StudentModel
from app.schemas.payment import PaymentCreate
from app.services.audit import log_sync_event
from app.services.balance_service import calculate_student_balance


def generate_receipt_no(db: Session) -> str:
    count = db.query(PaymentModel).count() + 1001
    return f"REC-2026-{count:04d}"


def create_payment(
    db: Session,
    payment_in: PaymentCreate,
    received_by_name: Optional[str] = None
) -> PaymentModel:
    """
    Creates an append-only payment record.
    Supports idempotency via client_id.
    Logs the mutation in sync_log on the local node.
    """
    # 1. Idempotency guard: return existing payment if client_id already processed
    if payment_in.client_id:
        existing = db.execute(
            select(PaymentModel).where(PaymentModel.client_id == payment_in.client_id)
        ).scalar_one_or_none()
        if existing:
            student = existing.student or db.get(StudentModel, existing.student_id)
            bal_info = calculate_student_balance(db, student, existing.term) if student else {"balance": Decimal("0.00")}
            setattr(existing, "balance_after", bal_info["balance"])
            return existing

    # 2. Verify student exists
    student = db.get(StudentModel, payment_in.student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID '{payment_in.student_id}' does not exist"
        )

    payment_id = payment_in.id or str(uuid.uuid4())
    paid_at = payment_in.paid_at or datetime.now(timezone.utc)
    reference = payment_in.reference or f"{payment_in.method.upper()}-{uuid.uuid4().hex[:8].upper()}"
    receipt_no = generate_receipt_no(db)
    cashier = received_by_name or "Bursar"

    payment = PaymentModel(
        id=payment_id,
        student_id=payment_in.student_id,
        term=payment_in.term,
        amount=payment_in.amount,
        method=payment_in.method,
        reference=reference,
        paid_at=paid_at,
        reverses_id=None,
        receipt_no=receipt_no,
        received_by_name=cashier,
        notes=payment_in.notes,
        client_id=payment_in.client_id,
        created_at=datetime.now(timezone.utc)
    )

    db.add(payment)
    db.flush()

    # Log to local sync_log
    log_sync_event(
        db=db,
        table_name="payments",
        row_id=payment.id,
        action="INSERT",
        payload={
            "id": payment.id,
            "student_id": payment.student_id,
            "term": payment.term,
            "amount": payment.amount,
            "method": payment.method,
            "reference": payment.reference,
            "receipt_no": payment.receipt_no,
            "received_by_name": payment.received_by_name,
            "notes": payment.notes,
            "client_id": payment.client_id,
            "paid_at": payment.paid_at,
            "reverses_id": None,
            "created_at": payment.created_at
        }
    )

    db.commit()
    db.refresh(payment)

    # Compute balance after this payment
    bal_info = calculate_student_balance(db, student, payment.term)
    setattr(payment, "balance_after", bal_info["balance"])

    return payment


def reverse_payment(
    db: Session,
    payment_id: str,
    reason: Optional[str] = None,
    reversed_by_name: Optional[str] = None
) -> PaymentModel:
    """
    Creates an append-only reversal entry.
    Payments are never edited; mistakes get a reversing row.
    """
    target = db.get(PaymentModel, payment_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID '{payment_id}' not found"
        )

    if target.reverses_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reverse a payment that is already a reversal record"
        )

    # Check if target is already reversed
    existing_reversal = db.execute(
        select(PaymentModel).where(PaymentModel.reverses_id == payment_id)
    ).scalar_one_or_none()

    if existing_reversal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment '{payment_id}' has already been reversed by record '{existing_reversal.id}'"
        )

    reversal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    reversal_reference = f"REV-{target.reference}"
    reversal_receipt = f"REV-{target.receipt_no}" if target.receipt_no else f"REV-{reversal_id[:8]}"
    rev_reason = reason or "Manual correction"
    rev_user = reversed_by_name or "Bursar"

    # Annotate target with reversal info
    target.reversal_reason = rev_reason
    target.reversed_by_name = rev_user

    reversal = PaymentModel(
        id=reversal_id,
        student_id=target.student_id,
        term=target.term,
        amount=target.amount,
        method=target.method,
        reference=reversal_reference,
        receipt_no=reversal_receipt,
        received_by_name=target.received_by_name,
        reversed_by_name=rev_user,
        reversal_reason=rev_reason,
        paid_at=now,
        reverses_id=target.id,
        created_at=now
    )

    db.add(reversal)
    db.flush()

    # Log to local sync_log
    log_sync_event(
        db=db,
        table_name="payments",
        row_id=reversal.id,
        action="INSERT",
        payload={
            "id": reversal.id,
            "student_id": reversal.student_id,
            "term": reversal.term,
            "amount": reversal.amount,
            "method": reversal.method,
            "reference": reversal.reference,
            "receipt_no": reversal.receipt_no,
            "received_by_name": reversal.received_by_name,
            "reversed_by_name": reversal.reversed_by_name,
            "reversal_reason": reversal.reversal_reason,
            "paid_at": reversal.paid_at,
            "reverses_id": reversal.reverses_id,
            "created_at": reversal.created_at
        }
    )

    db.commit()
    db.refresh(reversal)
    return reversal
