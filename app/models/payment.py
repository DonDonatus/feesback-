import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class PaymentModel(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    term = Column(String(50), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    method = Column(String(20), nullable=False)  # cash, hubtel, bank
    reference = Column(String(100), unique=False, index=True, nullable=False)  # Receipt no or Hubtel ref
    paid_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    reverses_id = Column(String(36), ForeignKey("payments.id"), nullable=True, index=True)
    receipt_no = Column(String(50), nullable=True, index=True)
    received_by_name = Column(String(100), nullable=True)
    reversed_by_name = Column(String(100), nullable=True)
    reversal_reason = Column(String(255), nullable=True)
    notes = Column(String(255), nullable=True)
    client_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    student = relationship("StudentModel", back_populates="payments")
    reversed_payment = relationship("PaymentModel", remote_side=[id], backref="reversal_entries")
