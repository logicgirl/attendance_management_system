from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import Role
from app.schemas.common import Email, FullName, Password, StudentId


class UserCreate(BaseModel):
    full_name: FullName
    email: Email
    password: Password
    role: Role
    student_id: StudentId | None = None


class UserUpdate(BaseModel):
    full_name: FullName | None = None
    password: Password | None = None
    role: Role | None = None
    is_active: bool | None = None
    # Send null to unlink the student record
    student_id: StudentId | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: Role
    is_active: bool
    student_id: str | None
    created_at: datetime
    locked_until: datetime | None


class PasswordChange(BaseModel):
    current_password: str
    new_password: Password
