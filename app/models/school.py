import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ClassModel(Base):
    __tablename__ = "classes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    students = relationship("StudentModel", back_populates="school_class", cascade="all, delete-orphan")
    fees = relationship("FeeModel", back_populates="school_class", cascade="all, delete-orphan")


class StudentModel(Base):
    __tablename__ = "students"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admission_no = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(150), nullable=False, index=True)
    guardian_phone = Column(String(30), nullable=False)
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False, index=True)
    status = Column(String(30), default="active", nullable=False)  # active, withdrawn, graduated
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    school_class = relationship("ClassModel", back_populates="students")
    payments = relationship("PaymentModel", back_populates="student", cascade="all, delete-orphan")


class FeeModel(Base):
    __tablename__ = "fees"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    class_id = Column(String(36), ForeignKey("classes.id"), nullable=False, index=True)
    term = Column(String(50), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    school_class = relationship("ClassModel", back_populates="fees")
