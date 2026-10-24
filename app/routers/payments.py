from datetime import date
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from app.database import get_db
from app.models.payment import PaymentModel
from app.models.school import StudentModel, ClassModel
from app.models.user import UserModel
from app.schemas.payment import (
    PaymentCreate,
    PaymentResponse,
    PaymentReverseRequest,
    RecordPaymentResponse,
    PaymentAuditItem,
    PaymentsListResponse,
    HubtelInitiateRequest,
    HubtelInitiateResponse,
    HubtelCallbackPayload
)
from app.services.payment_service import create_payment, reverse_payment
from app.services.auth_service import get_current_user_optional
from app.services.hubtel_service import (
    initiate_hubtel_payment,
    process_hubtel_callback,
    check_hubtel_transaction_status
)

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", response_model=RecordPaymentResponse, status_code=status.HTTP_201_CREATED)
def record_payment_endpoint(
    payment_in: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_current_user_optional)
):
    """
    Record a cash, bank, or manual offline payment.
    Append-only: never edits or deletes existing payments.
    """
    received_by = current_user.name if current_user else "Bursar"
    payment = create_payment(db, payment_in, received_by_name=received_by)
    return RecordPaymentResponse(
        id=payment.id,
        receipt_no=payment.receipt_no or f"REC-{payment.id[:8]}",
        received_by_name=payment.received_by_name or received_by,
        balance_after=float(getattr(payment, "balance_after", Decimal("0.00")))
    )


@router.post("/{payment_id}/reverse", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def reverse_payment_endpoint(
    payment_id: str,
    reverse_in: Optional[PaymentReverseRequest] = None,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_current_user_optional)
):
    """
    Creates an append-only reversal entry for an erroneous payment.
    Mistakes get a reversing row referencing reverses_id.
    """
    reason = reverse_in.reason if reverse_in else "Manual correction"
    reversed_by = current_user.name if current_user else "Bursar"
    return reverse_payment(db, payment_id, reason=reason, reversed_by_name=reversed_by)


@router.get("", response_model=PaymentsListResponse)
def list_payments(
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    term: Optional[str] = Query(None, description="Filter by term"),
    date_from: Optional[date] = Query(None, description="Filter payments from date"),
    date_to: Optional[date] = Query(None, description="Filter payments to date"),
    method: Optional[str] = Query(None, description="Filter by payment method"),
    received_by: Optional[str] = Query(None, description="Filter by cashier name"),
    status: Optional[str] = Query(None, description="Filter by status (active or reversed)"),
    q: Optional[str] = Query(None, description="Search term across student, admission no, receipt, reference"),
    sort: Optional[str] = Query("paid_at:desc", description="Sort field and direction"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Page size"),
    db: Session = Depends(get_db)
):
    """
    Audit log list of payments with joined student and class details, search, and pagination.
    """
    # 1. Base query joining student and class
    query = (
        select(PaymentModel, StudentModel, ClassModel)
        .outerjoin(StudentModel, PaymentModel.student_id == StudentModel.id)
        .outerjoin(ClassModel, StudentModel.class_id == ClassModel.id)
    )

    if student_id:
        query = query.where(PaymentModel.student_id == student_id)
    if term and term != "all":
        query = query.where(PaymentModel.term == term)

    results = db.execute(query.order_by(PaymentModel.paid_at.desc())).all()

    # Collect all reversed_ids
    all_reversals = {r[0].reverses_id for r in results if r[0].reverses_id}

    items: List[PaymentAuditItem] = []
    for row in results:
        p: PaymentModel = row[0]
        s: Optional[StudentModel] = row[1]
        c: Optional[ClassModel] = row[2]

        if p.reverses_id is not None:
            rec_status = "reversal"
        elif p.id in all_reversals:
            rec_status = "reversed"
        else:
            rec_status = "active"

        # Apply status filter
        if status and status != "all":
            if rec_status != status:
                continue

        # Apply method filter
        if method and method != "all":
            if method.lower() not in p.method.lower():
                continue

        # Apply cashier filter
        if received_by and received_by != "all":
            p_cashier = p.received_by_name or ("Momo" if p.method in ("hubtel", "momo") else "Bursar")
            if received_by == "Momo":
                if "momo" not in p_cashier.lower() and "hubtel" not in p.method.lower():
                    continue
            elif received_by != p_cashier:
                continue

        # Apply date filters
        p_date = p.paid_at.date()
        if date_from and p_date < date_from:
            continue
        if date_to and p_date > date_to:
            continue

        # Apply search q
        student_name = s.name if s else "Unknown"
        admission_no = s.admission_no if s else "N/A"
        class_name = c.name if c else "Unknown"
        receipt_no = p.receipt_no or f"REC-{p.id[:8]}"

        if q and q.strip():
            query_str = q.strip().lower()
            match = (
                query_str in student_name.lower() or
                query_str in admission_no.lower() or
                query_str in receipt_no.lower() or
                query_str in p.reference.lower()
            )
            if not match:
                continue

        item = PaymentAuditItem(
            id=p.id,
            receipt_no=receipt_no,
            paid_at=p.paid_at,
            student_id=p.student_id,
            student_name=student_name,
            admission_no=admission_no,
            class_name=class_name,
            amount=float(p.amount),
            method=p.method,
            reference=p.reference,
            received_by_name=p.received_by_name or "Bursar",
            status=rec_status,
            reversal_reason=p.reversal_reason,
            reversed_by_name=p.reversed_by_name,
            pending_sync=False
        )
        items.append(item)

    # Sorting
    if sort:
        parts = sort.split(":")
        field = parts[0]
        direction = parts[1] if len(parts) > 1 else "desc"
        is_rev = direction.lower() == "desc"

        if field == "paid_at":
            items.sort(key=lambda x: x.paid_at, reverse=is_rev)
        elif field == "amount":
            items.sort(key=lambda x: x.amount, reverse=is_rev)
        elif field == "student_name":
            items.sort(key=lambda x: x.student_name.lower(), reverse=is_rev)
        elif field == "admission_no":
            items.sort(key=lambda x: x.admission_no.lower(), reverse=is_rev)

    total_count = len(items)
    total_amount = float(sum((Decimal(str(item.amount)) for item in items if item.status == "active"), Decimal("0.00")))

    # Paginate
    start_idx = (page - 1) * page_size
    paginated_items = items[start_idx : start_idx + page_size]

    return PaymentsListResponse(
        items=paginated_items,
        total=total_count,
        total_amount=total_amount
    )


@router.post("/hubtel/initiate", response_model=HubtelInitiateResponse)
def initiate_hubtel(
    request: HubtelInitiateRequest,
    db: Session = Depends(get_db)
):
    """
    Initiates a Hubtel payment request. Prompts parent's phone for mobile money authorization.
    Requires internet connection.
    """
    return initiate_hubtel_payment(db, request)


@router.post("/hubtel/callback")
def hubtel_callback(
    payload: HubtelCallbackPayload,
    db: Session = Depends(get_db)
):
    """
    Cloud-only callback endpoint.
    Hubtel posts transaction results here; the cloud records a payments row using
    the client reference for idempotency.
    """
    return process_hubtel_callback(db, payload)


@router.get("/hubtel/status/{client_reference}")
def get_hubtel_status(
    client_reference: str,
    db: Session = Depends(get_db)
):
    """
    Checks the status of a transaction using Hubtel's Transaction Status Check API.
    Mandatory fallback if a callback is delayed or missed.
    """
    return check_hubtel_transaction_status(db, client_reference)
