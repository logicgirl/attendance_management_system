import datetime as dt
from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.access import get_course_for_user, lecturer_scope
from app.api.deps import SessionDep, StaffUser
from app.models import Course
from app.schemas.attendance import (
    AttendanceSummary,
    CourseOverview,
    DailyCounts,
    StudentAttendanceStats,
)
from app.services.attendance import (
    AttendanceFilters,
    filtered_attendance_query,
    get_course_overview,
    get_daily_counts,
    get_student_stats,
    get_summary,
    now_local,
)
from app.services.excel import attendance_workbook

router = APIRouter(prefix="/reports", tags=["reports"])

FiltersDep = Annotated[AttendanceFilters, Depends()]


@router.get("/summary", response_model=AttendanceSummary)
async def attendance_summary(
    db: SessionDep, user: StaffUser, date: dt.date | None = None, course_id: int | None = None
):
    """Roster size and attendance counts for a day (today by default)."""
    if course_id is not None:
        await get_course_for_user(db, user, course_id)
    return await get_summary(db, date or now_local().date(), course_id, lecturer_scope(user))


@router.get("/daily", response_model=list[DailyCounts])
async def daily_counts(
    db: SessionDep,
    user: StaffUser,
    days: int = Query(14, ge=1, le=120),
    course_id: int | None = None,
):
    """Attendance counts for each of the last `days` days, ending today."""
    if course_id is not None:
        await get_course_for_user(db, user, course_id)
    end = now_local().date()
    start = end - dt.timedelta(days=days - 1)
    return await get_daily_counts(db, start, end, course_id, lecturer_scope(user))


@router.get("/courses", response_model=list[CourseOverview])
async def course_overview(db: SessionDep, user: StaffUser, date: dt.date | None = None):
    """Active courses (a lecturer's own) with class size and the day's register progress."""
    return await get_course_overview(db, date or now_local().date(), lecturer_scope(user))


@router.get("/students", response_model=list[StudentAttendanceStats])
async def student_stats(db: SessionDep, user: StaffUser, filters: FiltersDep):
    """Attendance totals and rate per student, e.g. for one course over a term."""
    if filters.course_id is not None:
        await get_course_for_user(db, user, filters.course_id)
    return await get_student_stats(db, filters, lecturer_scope(user))


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def describe_filters(db: SessionDep, filters: AttendanceFilters) -> str:
    parts = []
    if filters.course_id is not None:
        course = await db.get(Course, filters.course_id)
        parts.append(f"Course {course.code if course else filters.course_id}")
    if filters.date_from or filters.date_to:
        start = filters.date_from.isoformat() if filters.date_from else "the start"
        end = filters.date_to.isoformat() if filters.date_to else "today"
        parts.append(f"{start} to {end}")
    if filters.status:
        parts.append(f"{filters.status.value} only")
    if filters.term:
        parts.append(f"Term {filters.term}")
    if filters.student_id:
        parts.append(f"Student {filters.student_id}")
    if filters.search:
        parts.append(f"Matching “{filters.search}”")
    return " · ".join(parts) if parts else "All records"


@router.get("/attendance.xlsx", response_class=Response)
async def export_attendance_excel(db: SessionDep, user: StaffUser, filters: FiltersDep):
    """Excel workbook: the matching records, and attendance per student."""
    if filters.course_id is not None:
        await get_course_for_user(db, user, filters.course_id)
    scope = lecturer_scope(user)
    records = (await db.scalars(filtered_attendance_query(filters, scope))).all()
    # Rates need every status, so the per-student sheet ignores a status filter
    stats = await get_student_stats(db, replace(filters, status=None), scope)
    now = now_local()
    content = attendance_workbook(records, stats, await describe_filters(db, filters), now)
    filename = f"attendance_report_{now.date().isoformat()}.xlsx"
    return Response(
        content=content,
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
