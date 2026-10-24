import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from app.database import get_db
from app.models.school import StudentModel, ClassModel
from app.models.payment import PaymentModel
from app.schemas.school import StudentCreate, StudentResponse
from app.schemas.payment import StudentPaymentRecord
from app.services.audit import log_sync_event

router = APIRouter(prefix="/students", tags=["Students"])


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(student_in: StudentCreate, db: Session = Depends(get_db)):
    # Verify class exists
    school_class = db.get(ClassModel, student_in.class_id)
    if not school_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class with ID '{student_in.class_id}' does not exist"
        )

    # Check unique admission number
    existing_adm = db.execute(
        select(StudentModel).where(StudentModel.admission_no == student_in.admission_no)
    ).scalar_one_or_none()
    if existing_adm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student with admission number '{student_in.admission_no}' already exists"
        )

    student_id = student_in.id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    student = StudentModel(
        id=student_id,
        admission_no=student_in.admission_no,
        name=student_in.name,
        guardian_phone=student_in.guardian_phone,
        class_id=student_in.class_id,
        status=student_in.status,
        created_at=now,
        updated_at=now
    )
    db.add(student)
    db.flush()

    # Log to sync_log
    log_sync_event(
        db=db,
        table_name="students",
        row_id=student.id,
        action="INSERT",
        payload={
            "id": student.id,
            "admission_no": student.admission_no,
            "name": student.name,
            "guardian_phone": student.guardian_phone,
            "class_id": student.class_id,
            "status": student.status,
            "created_at": student.created_at,
            "updated_at": student.updated_at
        }
    )

    db.commit()
    db.refresh(student)
    return student


@router.get("", response_model=List[StudentResponse])
def list_students(
    class_id: Optional[str] = Query(None, description="Filter by class ID"),
    q: Optional[str] = Query(None, description="Search by name or admission number"),
    db: Session = Depends(get_db)
):
    query = select(StudentModel)
    if class_id:
        query = query.where(StudentModel.class_id == class_id)
    if q:
        query = query.where(
            or_(
                StudentModel.name.ilike(f"%{q}%"),
                StudentModel.admission_no.ilike(f"%{q}%")
            )
        )
    students = db.execute(query.order_by(StudentModel.name)).scalars().all()
    return students


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student_id: str, db: Session = Depends(get_db)):
    student = db.get(StudentModel, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{student_id}' not found"
        )
    return student


@router.get("/{student_id}/payments", response_model=List[StudentPaymentRecord])
def get_student_payments(student_id: str, db: Session = Depends(get_db)):
    student = db.get(StudentModel, student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{student_id}' not found"
        )

    payments = db.execute(
        select(PaymentModel).where(PaymentModel.student_id == student_id).order_by(PaymentModel.paid_at.desc())
    ).scalars().all()

    reversed_ids = {p.reverses_id for p in payments if p.reverses_id}

    records = []
    for p in payments:
        if p.reverses_id is not None:
            rec_status = "reversal"
        elif p.id in reversed_ids:
            rec_status = "reversed"
        else:
            rec_status = "active"

        records.append(
            StudentPaymentRecord(
                id=p.id,
                receipt_no=p.receipt_no or f"REC-{p.id[:8]}",
                paid_at=p.paid_at,
                amount=p.amount,
                method=p.method,
                reference=p.reference,
                received_by_name=p.received_by_name or "Bursar",
                status=rec_status,
                reversal_reason=p.reversal_reason,
                reversed_by_name=p.reversed_by_name,
                pending_sync=False
            )
        )
    return records
