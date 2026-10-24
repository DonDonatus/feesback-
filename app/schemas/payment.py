from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import BaseModel, ConfigDict, Field


PaymentMethodType = Literal["cash", "hubtel", "bank", "momo"]
PaymentRecordStatus = Literal["active", "reversed", "reversal"]


class PaymentCreate(BaseModel):
    id: Optional[str] = None
    student_id: str
    term: str = Field(..., min_length=1, max_length=50)
    amount: Decimal = Field(..., gt=0)
    method: PaymentMethodType = "cash"
    reference: Optional[str] = None
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None
    client_id: Optional[str] = None


class PaymentReverseRequest(BaseModel):
    reason: Optional[str] = "Manual correction"


class RecordPaymentResponse(BaseModel):
    id: str
    receipt_no: str
    received_by_name: str
    balance_after: float

    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    id: str
    student_id: str
    term: str
    amount: Decimal
    method: str
    reference: str
    paid_at: datetime
    reverses_id: Optional[str] = None
    receipt_no: Optional[str] = None
    received_by_name: Optional[str] = None
    reversed_by_name: Optional[str] = None
    reversal_reason: Optional[str] = None
    notes: Optional[str] = None
    client_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StudentPaymentRecord(BaseModel):
    id: str
    receipt_no: str
    paid_at: datetime
    amount: float
    method: str
    reference: str
    received_by_name: Optional[str] = None
    status: PaymentRecordStatus
    reversal_reason: Optional[str] = None
    reversed_by_name: Optional[str] = None
    pending_sync: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)


class PaymentAuditItem(BaseModel):
    id: str
    receipt_no: str
    paid_at: datetime
    student_id: Optional[str] = None
    student_name: str
    admission_no: str
    class_name: str
    amount: float
    method: str
    reference: str
    received_by_name: Optional[str] = None
    status: PaymentRecordStatus
    reversal_reason: Optional[str] = None
    reversed_by_name: Optional[str] = None
    pending_sync: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)


class PaymentsListResponse(BaseModel):
    items: List[PaymentAuditItem]
    total: int
    total_amount: float


class HubtelInitiateRequest(BaseModel):
    student_id: str
    term: str
    amount: Decimal = Field(..., gt=0)
    customer_phone: str
    description: Optional[str] = "School Fees Payment"


class HubtelInitiateResponse(BaseModel):
    status: str
    checkout_url: Optional[str] = None
    checkout_direct_url: Optional[str] = None
    checkout_id: Optional[str] = None
    client_reference: str
    message: str


class HubtelCallbackPayload(BaseModel):
    ResponseCode: Optional[str] = None
    Status: Optional[str] = "Success"
    Data: Optional[dict] = None
    ClientReference: Optional[str] = None
    Amount: Optional[Decimal] = None
    TransactionId: Optional[str] = None
    ExternalTransactionId: Optional[str] = None
