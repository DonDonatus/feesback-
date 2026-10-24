from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class SyncLogModel(Base):
    __tablename__ = "sync_log"

    seq = Column(Integer, primary_key=True, autoincrement=True)
    table = Column(String(50), nullable=False, index=True)
    row_id = Column(String(36), nullable=False, index=True)
    action = Column(String(20), nullable=False)  # INSERT, UPDATE
    payload = Column(JSON, nullable=False)
    synced = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
