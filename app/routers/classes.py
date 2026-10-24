import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.school import ClassModel
from app.schemas.school import ClassCreate, ClassResponse
from app.services.audit import log_sync_event

router = APIRouter(prefix="/classes", tags=["Classes"])


@router.post("", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
def create_class(class_in: ClassCreate, db: Session = Depends(get_db)):
    class_id = class_in.id or str(uuid.uuid4())
    existing = db.get(ClassModel, class_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Class with ID '{class_id}' already exists"
        )

    now = datetime.now(timezone.utc)
    school_class = ClassModel(
        id=class_id,
        name=class_in.name,
        created_at=now,
        updated_at=now
    )
    db.add(school_class)
    db.flush()

    # Log to sync_log
    log_sync_event(
        db=db,
        table_name="classes",
        row_id=school_class.id,
        action="INSERT",
        payload={
            "id": school_class.id,
            "name": school_class.name,
            "created_at": school_class.created_at,
            "updated_at": school_class.updated_at
        }
    )

    db.commit()
    db.refresh(school_class)
    return school_class


@router.get("", response_model=List[ClassResponse])
def list_classes(db: Session = Depends(get_db)):
    classes = db.execute(select(ClassModel).order_by(ClassModel.name)).scalars().all()
    return classes
