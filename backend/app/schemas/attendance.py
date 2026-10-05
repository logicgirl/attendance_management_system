import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.models import AttendanceStatus
from app.schemas.common import StudentId


class AttendanceCreate(BaseModel):
    course_id: int
    student_id: StudentId
    status: AttendanceStatus = AttendanceStatus.PRESENT
    # Defaults to today; past dates are allowed for corrections
    date: dt.date | None = None


class RegisterEntry(BaseModel):
    student_id: StudentId
    status: AttendanceStatus


class RegisterSubmit(BaseModel):
    """A whole class register for one course and day."""

    course_id: int
    date: dt.date | None = None
    records: list[RegisterEntry] = Field(min_length=1)


class RegisterRow(BaseModel):
    student_id: str
    name: str
    department: str
    attendance_id: int | None
    status: AttendanceStatus | None


class AttendanceUpdate(BaseModel):
    status: AttendanceStatus


class AttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    student_name: str
    course_id: int
    course_code: str
    day: str
    date: dt.date
    time: dt.time
    status: AttendanceStatus
    term: str
    recorded_by: int | None


class DeleteResult(BaseModel):
    deleted: int


class AttendanceSummary(BaseModel):
    date: dt.date
    active_students: int
    total_records: int
    present: int
    late: int
    absent: int
    present_rate: float


class StudentAttendanceStats(BaseModel):
    student_id: str
    name: str
    total: int
    present: int
    late: int
    absent: int
    # Late counts as attended
    attendance_rate: float


class DailyCounts(BaseModel):
    date: dt.date
    present: int
    late: int
    absent: int
    total: int
    # Late counts as attended; null on days with no records
    attendance_rate: float | None


class CourseOverview(BaseModel):
    course_id: int
    code: str
    title: str
    lecturer_name: str | None
    enrolled: int
    marked: int
    present: int
    late: int
    absent: int
