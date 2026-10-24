from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class SyncLogItem(BaseModel):
    seq: int
    table: str
    row_id: str
    action: str  # INSERT, UPDATE
    payload: Dict[str, Any]
    created_at: datetime


class SyncPushRequest(BaseModel):
    items: List[SyncLogItem]


class SyncPushResponse(BaseModel):
    synced_seqs: List[int]
    processed_count: int
    message: str


class SyncPullResponse(BaseModel):
    classes: List[Dict[str, Any]]
    students: List[Dict[str, Any]]
    fees: List[Dict[str, Any]]
    payments: List[Dict[str, Any]]
    synced_at: datetime
