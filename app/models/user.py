import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)  # admin, bursar, clerk
    pin = Column(String(10), nullable=False)   # 4-digit numeric PIN
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
