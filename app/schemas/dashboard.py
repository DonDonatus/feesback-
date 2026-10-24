from decimal import Decimal
from datetime import datetime
from typing import Optional, Literal, List, Any
from pydantic import BaseModel, ConfigDict, model_validator


PaymentStatusType = Literal["paid", "partial", "unpaid"]
FrontendPaymentStatus = Literal["paid", "part", "owing"]


# --- Legacy Schemas for Backward Compatibility ---
class StudentDashboardRow(BaseModel):
    student_id: str
    admission_no: str
    name: str
    guardian_phone: str
    class_id: str
    class_name: str
    term: str
    fee_amount: Decimal
    total_paid: Decimal
    balance: Decimal
    status: PaymentStatusType


class DashboardSummary(BaseModel):
    total_students: int
    total_fees_expected: Decimal
    total_fees_collected: Decimal
    total_outstanding_balance: Decimal
    paid_count: int
    partial_count: int
    unpaid_count: int
    # Frontend aliases
    expected: Optional[float] = None
    collected: Optional[float] = None
    outstanding: Optional[float] = None
    collection_rate: Optional[int] = None
    part_count: Optional[int] = None
    owing_count: Optional[int] = None


class DashboardResponse(BaseModel):
    term: Optional[str]
    summary: DashboardSummary
    students: List[StudentDashboardRow]


# --- Frontend Aligned Schemas ---
class FrontendDashboardSummary(BaseModel):
    expected: float
    collected: float
    outstanding: float
    collection_rate: int
    paid_count: int
    part_count: int
    owing_count: int
    pending_sync_count: int
    last_synced_at: str
    online: bool = True


class PaymentByMethod(BaseModel):
    method: str
    amount: float
    count: int


class PaymentByCashier(BaseModel):
    user_id: str
    name: str
    amount: float
    count: int


class DashboardToday(BaseModel):
    collected_today: float
    payment_count: int
    by_method: List[PaymentByMethod]
    by_cashier: List[PaymentByCashier]


class StudentListItem(BaseModel):
    id: str
    student_id: Optional[str] = None
    admission_no: str
    name: str
    guardian_phone: str
    class_id: Optional[str] = None
    class_name: str
    fee: float
    fee_amount: Optional[Decimal] = None
    paid: float
    total_paid: Optional[Decimal] = None
    balance: float
    status: str
    last_payment_at: Optional[str] = None
    last_received_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class StudentListResponse(BaseModel):
    items: List[StudentListItem]
    students: Optional[List[StudentListItem]] = None
    total: int
    filtered_outstanding: float
    term: Optional[str] = None
    summary: Optional[DashboardSummary] = None

    @model_validator(mode="before")
    @classmethod
    def populate_students_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "items" in data and "students" not in data:
                data["students"] = data["items"]
            elif "students" in data and "items" not in data:
                data["items"] = data["students"]
        return data
