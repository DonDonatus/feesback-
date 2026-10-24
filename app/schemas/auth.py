from typing import Literal
from pydantic import BaseModel, ConfigDict


UserRole = Literal["admin", "bursar", "clerk"]


class UserResponse(BaseModel):
    id: str
    name: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class UserListItem(BaseModel):
    id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    user_id: str
    pin: str


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
