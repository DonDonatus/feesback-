from decimal import Decimal
from typing import Dict, Any, List, Set, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.school import StudentModel, FeeModel
from app.models.payment import PaymentModel
from app.schemas.dashboard import StudentDashboardRow, PaymentStatusType


def calculate_student_balance(
    db: Session,
    student: StudentModel,
    term: str
) -> Dict[str, Any]:
    """
    Computes dynamic balance and payment status for a student in a specific term.
    Balance = Fee for student's class and term - sum of active payments.
    Nothing is stored or edited.
    """
    # 1. Fetch class fee for this term
    fee_query = select(FeeModel).where(
        FeeModel.class_id == student.class_id,
        FeeModel.term == term
    )
    fee = db.execute(fee_query).scalar_one_or_none()
    fee_amount = Decimal(str(fee.amount)) if fee else Decimal("0.00")

    # 2. Fetch all payments for this student and term
    payments_query = select(PaymentModel).where(
        PaymentModel.student_id == student.id,
        PaymentModel.term == term
    )
    payments = db.execute(payments_query).scalars().all()

    # 3. Resolve active payments (accounting for append-only reversals)
    reversed_ids: Set[str] = {p.reverses_id for p in payments if p.reverses_id}
    
    active_payments = [
        p for p in payments
        if p.reverses_id is None and p.id not in reversed_ids
    ]

    total_paid = sum((Decimal(str(p.amount)) for p in active_payments), Decimal("0.00"))
    balance = fee_amount - total_paid

    # 4. Determine status
    if fee_amount == Decimal("0.00"):
        status: PaymentStatusType = "paid" if total_paid >= Decimal("0.00") else "unpaid"
    elif balance <= Decimal("0.00"):
        status = "paid"
    elif total_paid == Decimal("0.00"):
        status = "unpaid"
    else:
        status = "partial"

    class_name = student.school_class.name if student.school_class else "Unknown"

    return {
        "student_id": student.id,
        "admission_no": student.admission_no,
        "name": student.name,
        "guardian_phone": student.guardian_phone,
        "class_id": student.class_id,
        "class_name": class_name,
        "term": term,
        "fee_amount": fee_amount,
        "total_paid": total_paid,
        "balance": balance,
        "status": status,
        "active_payments_count": len(active_payments),
        "total_payments_count": len(payments),
    }
