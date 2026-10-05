from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import Token
from app.schemas.user import PasswordChange, UserRead
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def as_utc(value: datetime) -> datetime:
    # SQLite drops the timezone; stored values are always UTC
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@router.post("/login", response_model=Token)
async def login(db: SessionDep, form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Log in with email (sent as `username`) and password."""
    now = datetime.now(UTC)
    user = await db.scalar(select(User).where(User.email == form.username.strip().lower()))
    password_ok = verify_password(form.password, user.hashed_password if user else DUMMY_HASH)

    if user is not None and user.locked_until and as_utc(user.locked_until) > now:
        minutes = int((as_utc(user.locked_until) - now).total_seconds() // 60) + 1
        raise HTTPException(
            status.HTTP_423_LOCKED,
            f"Too many failed attempts. Try again in {minutes} minute(s).",
        )
    if user is None or not password_ok:
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
                audit(db, None, "user.locked", "user", user.id)
            await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated")

    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.commit()
    return Token(access_token=create_access_token(user.id, user.role), user=user)


@router.get("/me", response_model=UserRead)
async def read_me(user: CurrentUser):
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(db: SessionDep, user: CurrentUser, payload: PasswordChange):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "New password must be different from the current one"
        )
    user.hashed_password = hash_password(payload.new_password)
    audit(db, user, "user.change_password", "user", user.id)
    await db.commit()
