import datetime as dt
from dataclasses import dataclass

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.core.config import settings
from app.models import Attendance, AttendanceStatus, Course, Enrollment, Student


def now_local() -> dt.datetime:
    return dt.datetime.now(settings.tz)


@dataclass
class AttendanceFilters:
    """Query parameters shared by the attendance list, reports and the CSV export."""

    search: str | None = None
    student_id: str | None = None
    course_id: int | None = None
    status: AttendanceStatus | None = None
    term: str | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None


def _scope(stmt: Select, filters: AttendanceFilters, lecturer_id: int | None) -> Select:
    if lecturer_id is not None:
        stmt = stmt.where(
            Attendance.course_id.in_(select(Course.id).where(Course.lecturer_id == lecturer_id))
        )
    if filters.search:
        pattern = f"%{filters.search.strip()}%"
        stmt = stmt.where(or_(Student.name.ilike(pattern), Attendance.student_id.ilike(pattern)))
    if filters.student_id:
        stmt = stmt.where(Attendance.student_id == filters.student_id)
    if filters.course_id:
        stmt = stmt.where(Attendance.course_id == filters.course_id)
    if filters.status:
        stmt = stmt.where(Attendance.status == filters.status)
    if filters.term:
        stmt = stmt.where(Attendance.term == filters.term)
    if filters.date_from:
        stmt = stmt.where(Attendance.date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Attendance.date <= filters.date_to)
    return stmt


def filtered_attendance_query(
    filters: AttendanceFilters, lecturer_id: int | None = None
) -> Select[tuple[Attendance]]:
    stmt = select(Attendance).join(Attendance.student).options(contains_eager(Attendance.student))
    stmt = _scope(stmt, filters, lecturer_id)
    return stmt.order_by(Attendance.date, Attendance.time, Attendance.id)


async def get_summary(
    db: AsyncSession, day: dt.date, course_id: int | None, lecturer_id: int | None
) -> dict:
    roster = select(func.count(func.distinct(Student.student_id))).where(Student.is_active)
    if course_id is not None or lecturer_id is not None:
        roster = roster.join(Enrollment, Enrollment.student_id == Student.student_id).join(
            Course, Course.id == Enrollment.course_id
        )
        if course_id is not None:
            roster = roster.where(Course.id == course_id)
        if lecturer_id is not None:
            roster = roster.where(Course.lecturer_id == lecturer_id)
    active_students = await db.scalar(roster)

    counts_stmt = (
        select(Attendance.status, func.count()).join(Attendance.student).group_by(Attendance.status)
    )
    counts_stmt = _scope(
        counts_stmt,
        AttendanceFilters(course_id=course_id, date_from=day, date_to=day),
        lecturer_id,
    )
    counts = {status: 0 for status in AttendanceStatus}
    counts.update({status: n for status, n in (await db.execute(counts_stmt)).all()})
    total = sum(counts.values())
    present = counts[AttendanceStatus.PRESENT]
    return {
        "date": day,
        "active_students": active_students or 0,
        "total_records": total,
        "present": present,
        "late": counts[AttendanceStatus.LATE],
        "absent": counts[AttendanceStatus.ABSENT],
        "present_rate": round(present / total * 100, 1) if total else 0.0,
    }


async def get_student_stats(
    db: AsyncSession, filters: AttendanceFilters, lecturer_id: int | None
) -> list[dict]:
    def count_of(status: AttendanceStatus):
        return func.sum(case((Attendance.status == status, 1), else_=0))

    stmt = (
        select(
            Student.student_id,
            Student.name,
            func.count(Attendance.id),
            count_of(AttendanceStatus.PRESENT),
            count_of(AttendanceStatus.LATE),
            count_of(AttendanceStatus.ABSENT),
        )
        .select_from(Attendance)
        .join(Attendance.student)
        .group_by(Student.student_id, Student.name)
        .order_by(Student.name)
    )
    stmt = _scope(stmt, filters, lecturer_id)
    stats = []
    for student_id, name, total, present, late, absent in (await db.execute(stmt)).all():
        stats.append(
            {
                "student_id": student_id,
                "name": name,
                "total": total,
                "present": present,
                "late": late,
                "absent": absent,
                "attendance_rate": round((present + late) / total * 100, 1) if total else 0.0,
            }
        )
    return stats


async def get_daily_counts(
    db: AsyncSession,
    start: dt.date,
    end: dt.date,
    course_id: int | None,
    lecturer_id: int | None,
) -> list[dict]:
    """Status counts for every day from start to end, including days with no records."""
    stmt = (
        select(Attendance.date, Attendance.status, func.count())
        .join(Attendance.student)
        .group_by(Attendance.date, Attendance.status)
    )
    stmt = _scope(
        stmt, AttendanceFilters(course_id=course_id, date_from=start, date_to=end), lecturer_id
    )
    counts: dict[dt.date, dict[AttendanceStatus, int]] = {}
    for day, status, n in (await db.execute(stmt)).all():
        counts.setdefault(day, {})[status] = n

    days = []
    day = start
    while day <= end:
        c = counts.get(day, {})
        present = c.get(AttendanceStatus.PRESENT, 0)
        late = c.get(AttendanceStatus.LATE, 0)
        absent = c.get(AttendanceStatus.ABSENT, 0)
        total = present + late + absent
        days.append(
            {
                "date": day,
                "present": present,
                "late": late,
                "absent": absent,
                "total": total,
                "attendance_rate": round((present + late) / total * 100, 1) if total else None,
            }
        )
        day += dt.timedelta(days=1)
    return days


async def get_course_overview(
    db: AsyncSession, day: dt.date, lecturer_id: int | None
) -> list[dict]:
    """Each active course with its class size and how much of the day's register is done."""
    courses_stmt = select(Course).where(Course.is_active).order_by(Course.code)
    if lecturer_id is not None:
        courses_stmt = courses_stmt.where(Course.lecturer_id == lecturer_id)
    courses = (await db.scalars(courses_stmt)).all()
    ids = [c.id for c in courses]
    if not ids:
        return []

    enrolled = dict(
        (
            await db.execute(
                select(Enrollment.course_id, func.count())
                .join(Student, Student.student_id == Enrollment.student_id)
                .where(Enrollment.course_id.in_(ids), Student.is_active)
                .group_by(Enrollment.course_id)
            )
        ).all()
    )
    marked: dict[int, dict[AttendanceStatus, int]] = {}
    for course_id, status, n in (
        await db.execute(
            select(Attendance.course_id, Attendance.status, func.count())
            .where(Attendance.course_id.in_(ids), Attendance.date == day)
            .group_by(Attendance.course_id, Attendance.status)
        )
    ).all():
        marked.setdefault(course_id, {})[status] = n

    overview = []
    for course in courses:
        c = marked.get(course.id, {})
        overview.append(
            {
                "course_id": course.id,
                "code": course.code,
                "title": course.title,
                "lecturer_name": course.lecturer_name,
                "enrolled": enrolled.get(course.id, 0),
                "marked": sum(c.values()),
                "present": c.get(AttendanceStatus.PRESENT, 0),
                "late": c.get(AttendanceStatus.LATE, 0),
                "absent": c.get(AttendanceStatus.ABSENT, 0),
            }
        )
    return overview
