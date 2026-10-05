from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import StudentId, TitleCaseStr


class StudentCreate(BaseModel):
    # Left out, the ID is generated from the department and year, e.g. CS-26-0001
    student_id: StudentId | None = None
    name: TitleCaseStr
    department: TitleCaseStr


class StudentUpdate(BaseModel):
    name: TitleCaseStr | None = None
    department: TitleCaseStr | None = None
    is_active: bool | None = None


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    name: str
    department: str
    is_active: bool
    created_at: datetime
