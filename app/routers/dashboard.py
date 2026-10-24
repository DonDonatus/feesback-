from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func
from app.database import get_db
from app.models.school import StudentModel, FeeModel
from app.models.payment import PaymentModel
from app.models.sync import SyncLogModel
from app.schemas.dashboard import (
    FrontendDashboardSummary,
    DashboardToday,
    PaymentByMethod,
    PaymentByCashier,
    StudentListItem,
    StudentListResponse,
    DashboardSummary
)
from app.services.balance_service import calculate_student_balance

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=FrontendDashboardSummary)
def get_dashboard_summary(
    term: Optional[str] = Query(None, description="Academic term (defaults to latest available)"),
    db: Session = Depends(get_db)
):
    """
    Returns high-level metric cards for Expected, Collected, Outstanding, and Collection Rate.
    """
    if not term:
        latest_fee = db.execute(select(FeeModel).order_by(FeeModel.created_at.desc())).scalars().first()
        term = latest_fee.term if latest_fee else "Term-1"

    students = db.execute(select(StudentModel)).scalars().all()

    total_expected = Decimal("0.00")
    total_collected = Decimal("0.00")
    paid_count = 0
    part_count = 0
    owing_count = 0

    for s in students:
        bal_info = calculate_student_balance(db, s, term)
        total_expected += bal_info["fee_amount"]
        total_collected += bal_info["total_paid"]
        st = bal_info["status"]
        if st == "paid":
            paid_count += 1
        elif st == "partial":
            part_count += 1
        else:
            owing_count += 1

    outstanding = max(Decimal("0.00"), total_expected - total_collected)
    collection_rate = (
        int(round((total_collected / total_expected) * 100))
        if total_expected > Decimal("0.00")
        else 0
    )

    pending_sync_count = db.query(SyncLogModel).filter(SyncLogModel.synced == False).count()
    last_synced = (
        db.query(SyncLogModel)
        .filter(SyncLogModel.synced == True)
        .order_by(SyncLogModel.created_at.desc())
        .first()
    )
    last_synced_at = (
        last_synced.created_at.isoformat()
        if last_synced
        else datetime.now(timezone.utc).isoformat()
    )

    return FrontendDashboardSummary(
        expected=float(total_expected),
        collected=float(total_collected),
        outstanding=float(outstanding),
        collection_rate=collection_rate,
        paid_count=paid_count,
        part_count=part_count,
        owing_count=owing_count,
        pending_sync_count=pending_sync_count,
        last_synced_at=last_synced_at,
        online=True
    )


@router.get("/today", response_model=DashboardToday)
def get_dashboard_today(
    term: Optional[str] = Query(None, description="Academic term"),
    db: Session = Depends(get_db)
):
    """
    Returns today's collections broken down by payment method and cashier.
    """
    today_utc = datetime.now(timezone.utc).date()

    payments_query = select(PaymentModel)
    if term:
        payments_query = payments_query.where(PaymentModel.term == term)

    all_payments = db.execute(payments_query).scalars().all()
    reversed_ids = {p.reverses_id for p in all_payments if p.reverses_id}

    # Filter to active payments made today
    todays_active = [
        p for p in all_payments
        if p.reverses_id is None
        and p.id not in reversed_ids
        and p.paid_at.date() == today_utc
    ]

    collected_today = sum((p.amount for p in todays_active), Decimal("0.00"))

    # Breakdown by method
    method_data: Dict[str, Dict[str, Any]] = {
        "Cash": {"amount": Decimal("0.00"), "count": 0},
        "Bank": {"amount": Decimal("0.00"), "count": 0},
        "Mobile Money": {"amount": Decimal("0.00"), "count": 0},
    }

    for p in todays_active:
        m = p.method.lower()
        if "cash" in m:
            key = "Cash"
        elif "bank" in m:
            key = "Bank"
        else:
            key = "Mobile Money"

        method_data[key]["amount"] += p.amount
        method_data[key]["count"] += 1

    by_method = [
        PaymentByMethod(method=k, amount=float(v["amount"]), count=v["count"])
        for k, v in method_data.items()
    ]

    # Breakdown by cashier
    cashier_data: Dict[str, Dict[str, Any]] = {}
    for p in todays_active:
        c_name = p.received_by_name or ("Momo (online)" if p.method in ("hubtel", "momo") else "Bursar")
        if c_name not in cashier_data:
            cashier_data[c_name] = {"user_id": c_name, "name": c_name, "amount": Decimal("0.00"), "count": 0}
        cashier_data[c_name]["amount"] += p.amount
        cashier_data[c_name]["count"] += 1

    by_cashier = [
        PaymentByCashier(
            user_id=v["user_id"],
            name=v["name"],
            amount=float(v["amount"]),
            count=v["count"]
        )
        for v in cashier_data.values()
    ]

    return DashboardToday(
        collected_today=float(collected_today),
        payment_count=len(todays_active),
        by_method=by_method,
        by_cashier=by_cashier
    )


@router.get("/students", response_model=StudentListResponse)
def get_students_dashboard(
    class_id: Optional[str] = Query(None, description="Filter by class ID"),
    term: Optional[str] = Query(None, description="Academic term"),
    status: Optional[str] = Query(None, description="Filter by payment status (paid, part/partial, owing/unpaid)"),
    sort: Optional[str] = Query("balance:desc", description="Sort order"),
    q: Optional[str] = Query(None, description="Search by student name or admission number"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Page size"),
    db: Session = Depends(get_db)
):
    """
    Returns student list with dynamic balance calculation, search, filters, and pagination.
    """
    if not term:
        latest_fee = db.execute(select(FeeModel).order_by(FeeModel.created_at.desc())).scalars().first()
        term = latest_fee.term if latest_fee else "Term-1"

    query = select(StudentModel)
    if class_id and class_id != "all":
        query = query.where(StudentModel.class_id == class_id)
    if q and q.strip():
        search_term = q.strip()
        query = query.where(
            or_(
                StudentModel.name.ilike(f"%{search_term}%"),
                StudentModel.admission_no.ilike(f"%{search_term}%"),
                StudentModel.guardian_phone.ilike(f"%{search_term}%")
            )
        )

    students = db.execute(query).scalars().all()

    # Pre-fetch payments for these students to resolve last_payment_at and last_received_by
    student_ids = [s.id for s in students]
    payments_map: Dict[str, List[PaymentModel]] = {sid: [] for sid in student_ids}
    if student_ids:
        all_p = db.execute(
            select(PaymentModel).where(PaymentModel.student_id.in_(student_ids)).order_by(PaymentModel.paid_at.desc())
        ).scalars().all()
        for p in all_p:
            payments_map[p.student_id].append(p)

    rows: List[StudentListItem] = []
    total_fees_expected = Decimal("0.00")
    total_fees_collected = Decimal("0.00")
    total_outstanding_balance = Decimal("0.00")
    paid_count = 0
    part_count = 0
    owing_count = 0

    for s in students:
        bal_info = calculate_student_balance(db, s, term)
        fee_amt = bal_info["fee_amount"]
        tot_paid = bal_info["total_paid"]
        bal = bal_info["balance"]
        internal_status = bal_info["status"]

        # Map status to frontend vocabulary
        if internal_status == "paid":
            fe_status = "paid"
            paid_count += 1
        elif internal_status == "partial":
            fe_status = "part"
            part_count += 1
        else:
            fe_status = "owing"
            owing_count += 1

        total_fees_expected += fee_amt
        total_fees_collected += tot_paid
        total_outstanding_balance += max(bal, Decimal("0.00"))

        # Check status filter
        if status and status != "all":
            st_req = status.lower()
            if st_req in ("paid",) and fe_status != "paid":
                continue
            elif st_req in ("part", "partial") and fe_status != "part":
                continue
            elif st_req in ("owing", "unpaid") and fe_status != "owing":
                continue

        # Resolve latest active payment
        s_payments = payments_map.get(s.id, [])
        rev_ids = {p.reverses_id for p in s_payments if p.reverses_id}
        active_p = [p for p in s_payments if p.reverses_id is None and p.id not in rev_ids]
        latest_p = active_p[0] if active_p else None

        last_payment_at = latest_p.paid_at.isoformat() if latest_p else None
        last_received_by = None
        if latest_p and latest_p.received_by_name:
            names = latest_p.received_by_name.split()
            last_received_by = f"{names[0]} {names[1][0]}." if len(names) > 1 else names[0]

        row = StudentListItem(
            id=s.id,
            student_id=s.id,
            admission_no=s.admission_no,
            name=s.name,
            guardian_phone=s.guardian_phone,
            class_id=s.class_id,
            class_name=bal_info["class_name"],
            fee=float(fee_amt),
            fee_amount=fee_amt,
            paid=float(tot_paid),
            total_paid=tot_paid,
            balance=float(bal),
            status=fe_status,
            last_payment_at=last_payment_at,
            last_received_by=last_received_by
        )
        rows.append(row)

    # Sorting
    if sort:
        parts = sort.split(":")
        field = parts[0]
        direction = parts[1] if len(parts) > 1 else "desc"
        is_rev = direction.lower() == "desc"

        if field == "balance":
            rows.sort(key=lambda x: x.balance, reverse=is_rev)
        elif field == "name":
            rows.sort(key=lambda x: x.name.lower(), reverse=is_rev)
        elif field == "admission_no":
            rows.sort(key=lambda x: x.admission_no.lower(), reverse=is_rev)
        elif field in ("fee", "fee_amount"):
            rows.sort(key=lambda x: x.fee, reverse=is_rev)
        elif field in ("paid", "total_paid"):
            rows.sort(key=lambda x: x.paid, reverse=is_rev)

    total_filtered = len(rows)
    filtered_outstanding = float(sum(max(Decimal(str(r.balance)), Decimal("0.00")) for r in rows))

    # Paginate
    start_idx = (page - 1) * page_size
    paginated_items = rows[start_idx : start_idx + page_size]

    summary_legacy = DashboardSummary(
        total_students=len(students),
        total_fees_expected=total_fees_expected,
        total_fees_collected=total_fees_collected,
        total_outstanding_balance=total_outstanding_balance,
        paid_count=paid_count,
        partial_count=part_count,
        unpaid_count=owing_count,
        expected=float(total_fees_expected),
        collected=float(total_fees_collected),
        outstanding=float(total_outstanding_balance),
        collection_rate=int(round((total_fees_collected / total_fees_expected) * 100)) if total_fees_expected > Decimal("0.00") else 0,
        part_count=part_count,
        owing_count=owing_count
    )

    return StudentListResponse(
        items=paginated_items,
        students=paginated_items,
        total=total_filtered,
        filtered_outstanding=filtered_outstanding,
        term=term,
        summary=summary_legacy
    )
