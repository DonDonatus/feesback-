from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.user import UserModel
from app.schemas.auth import LoginRequest, LoginResponse, UserResponse, UserListItem
from app.services.auth_service import generate_token, get_current_user

router = APIRouter(tags=["Auth"])


@router.post("/auth/login", response_model=LoginResponse)
def login(login_req: LoginRequest, db: Session = Depends(get_db)):
    user = db.get(UserModel, login_req.user_id)
    if not user or user.pin != login_req.pin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PIN. Please check and try again."
        )

    token = generate_token(user)
    return LoginResponse(
        token=token,
        user=UserResponse.model_validate(user)
    )


@router.get("/auth/me", response_model=UserResponse)
def get_me(user: UserModel = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.get("/users", response_model=List[UserListItem])
def list_users(db: Session = Depends(get_db)):
    users = db.execute(select(UserModel).order_by(UserModel.name)).scalars().all()
    return [UserListItem.model_validate(u) for u in users]
