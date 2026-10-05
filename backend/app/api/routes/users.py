from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminUser, SessionDep
from app.core.security import hash_password
from app.models import Role, Student, User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.audit import audit

router = APIRouter(prefix="/users", tags=["users"])


async def ensure_student_link_valid(db: SessionDep, student_id: str, user_id: int | None = None):
    if await db.get(Student, student_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Student '{student_id}' not found")
    owner = await db.scalar(select(User).where(User.student_id == student_id))
    if owner is not None and owner.id != user_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Student '{student_id}' is already linked to another account"
        )


@router.get("", response_model=list[UserRead])
async def list_users(db: SessionDep, _: AdminUser, role: Role | None = None):
    stmt = select(User).order_by(User.full_name)
    if role:
        stmt = stmt.where(User.role == role)
    return (await db.scalars(stmt)).all()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(db: SessionDep, admin: AdminUser, payload: UserCreate):
    if await db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    if payload.role == Role.STUDENT and not payload.student_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "student_id is required for student accounts"
        )
    if payload.student_id:
        await ensure_student_link_valid(db, payload.student_id)

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        student_id=payload.student_id,
    )
    db.add(user)
    await db.flush()
    audit(
        db,
        admin,
        "user.create",
        "user",
        user.id,
        **payload.model_dump(exclude={"password"}),
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(db: SessionDep, admin: AdminUser, user_id: int, payload: UserUpdate):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    changes = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and (
        changes.get("is_active") is False or (changes.get("role") or Role.ADMIN) != Role.ADMIN
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "You cannot deactivate or demote your own account"
        )
    new_role = changes.get("role") or user.role
    new_student_id = changes["student_id"] if "student_id" in changes else user.student_id
    if new_role == Role.STUDENT and not new_student_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "student_id is required for student accounts"
        )
    if changes.get("student_id"):
        await ensure_student_link_valid(db, changes["student_id"], user.id)

    for field in ("full_name", "role", "is_active"):
        if changes.get(field) is not None:
            setattr(user, field, changes[field])
    if "student_id" in changes:
        user.student_id = changes["student_id"]
    if changes.get("password"):
        user.hashed_password = hash_password(changes["password"])
        # An admin password reset also unlocks the account
        user.failed_login_attempts = 0
        user.locked_until = None

    logged = {k: v for k, v in changes.items() if k != "password"}
    audit(db, admin, "user.update", "user", user.id, password_reset="password" in changes, **logged)

    await db.commit()
    await db.refresh(user)
    return user
