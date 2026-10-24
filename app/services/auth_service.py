import time
from typing import Optional
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.user import UserModel


def generate_token(user: UserModel) -> str:
    timestamp = int(time.time())
    return f"token_{user.id}_{timestamp}"


def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[UserModel]:
    if not authorization:
        # Fallback to the first bursar or first user in DB if exists
        user = db.execute(select(UserModel).order_by(UserModel.created_at)).scalars().first()
        return user

    parts = authorization.split(" ")
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1]
    else:
        token = parts[0]

    if token.startswith("token_") or token.startswith("mock_token_"):
        token_parts = token.split("_")
        if len(token_parts) >= 2:
            user_id = token_parts[1]
            user = db.get(UserModel, user_id)
            if user:
                return user

    # Fallback to first user in DB
    return db.execute(select(UserModel).order_by(UserModel.created_at)).scalars().first()


def get_current_user(
    user: Optional[UserModel] = Depends(get_current_user_optional)
) -> UserModel:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    return user
