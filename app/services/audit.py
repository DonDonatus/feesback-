import json
from contextvars import ContextVar
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict
from sqlalchemy.orm import Session
from app.config import settings
from app.models.sync import SyncLogModel

# Context variable to suppress sync logging during sync pull operations
_suppress_sync = ContextVar("suppress_sync", default=False)


class SuppressSyncLogging:
    """Context manager to suppress writing to sync_log (used when applying cloud pulls)."""
    def __enter__(self):
        self.token = _suppress_sync.set(True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _suppress_sync.reset(self.token)


def is_sync_suppressed() -> bool:
    return _suppress_sync.get()


def serialize_for_sync(obj_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Serializes date/decimal fields into JSON-serializable primitives."""
    result = {}
    for k, v in obj_dict.items():
        if isinstance(v, (datetime,)):
            result[k] = v.isoformat()
        elif isinstance(v, Decimal):
            result[k] = str(v)
        else:
            result[k] = v
    return result


def log_sync_event(
    db: Session,
    table_name: str,
    row_id: str,
    action: str,
    payload: Dict[str, Any]
) -> None:
    """
    Records an insert/update action into local sync_log if running as local node
    and sync logging is not suppressed.
    """
    if is_sync_suppressed():
        return

    # In local mode, write to sync_log
    if settings.NODE_TYPE == "local":
        clean_payload = serialize_for_sync(payload)
        sync_entry = SyncLogModel(
            table=table_name,
            row_id=row_id,
            action=action.upper(),
            payload=clean_payload,
            synced=False,
            created_at=datetime.now(timezone.utc)
        )
        db.add(sync_entry)
        db.flush()
