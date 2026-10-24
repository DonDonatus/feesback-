from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ClassCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=100)


class ClassResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StudentCreate(BaseModel):
    id: Optional[str] = None
    admission_no: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    guardian_phone: str = Field(..., min_length=3, max_length=30)
    class_id: str
    status: str = "active"


class StudentResponse(BaseModel):
    id: str
    admission_no: str
    name: str
    guardian_phone: str
    class_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeeCreate(BaseModel):
    id: Optional[str] = None
    class_id: str
    term: str = Field(..., min_length=1, max_length=50)
    amount: Decimal = Field(..., gt=0)


class FeeResponse(BaseModel):
    id: str
    class_id: str
    term: str
    amount: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
