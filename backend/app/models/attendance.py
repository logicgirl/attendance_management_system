import datetime as dt
import enum

from sqlalchemy import Date, DateTime, ForeignKey, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, str_enum
from app.models.course import Course
from app.models.student import Student


class AttendanceStatus(enum.StrEnum):
    PRESENT = "Present"
    ABSENT = "Absent"
    LATE = "Late"


class Attendance(Base):
    __tablename__ = "attendance"
    # One record per student, per course, per day
    __table_args__ = (UniqueConstraint("student_id", "course_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id", ondelete="RESTRICT"))
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), index=True
    )
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    time: Mapped[dt.time] = mapped_column(Time)
    status: Mapped[AttendanceStatus] = mapped_column(str_enum(AttendanceStatus, "status"))
    term: Mapped[str] = mapped_column(String(20), index=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    student: Mapped[Student] = relationship(lazy="joined", innerjoin=True)
    course: Mapped[Course] = relationship(lazy="joined", innerjoin=True)

    @property
    def student_name(self) -> str:
        return self.student.name

    @property
    def course_code(self) -> str:
        return self.course.code

    @property
    def day(self) -> str:
        return self.date.strftime("%A")
