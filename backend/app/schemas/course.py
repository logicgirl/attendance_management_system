from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import StudentId, TitleCaseStr

CourseCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9 _-]+$"
    ),
    AfterValidator(str.upper),
]


class CourseCreate(BaseModel):
    code: CourseCode
    title: TitleCaseStr
    department: TitleCaseStr
    lecturer_id: int | None = None


class CourseUpdate(BaseModel):
    title: TitleCaseStr | None = None
    department: TitleCaseStr | None = None
    # Send null to unassign the lecturer
    lecturer_id: int | None = None
    is_active: bool | None = None


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    department: str
    lecturer_id: int | None
    lecturer_name: str | None
    is_active: bool
    created_at: datetime


class EnrollRequest(BaseModel):
    student_ids: list[StudentId] = Field(min_length=1)
