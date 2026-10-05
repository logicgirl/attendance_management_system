import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.access import get_course_for_user, lecturer_scope
from app.api.deps import SessionDep, StaffUser
from app.schemas.attendance import (
    AttendanceSummary,
    CourseOverview,
    DailyCounts,
    StudentAttendanceStats,
)
from app.services.attendance import (
    AttendanceFilters,
    attendance_to_csv,
    filtered_attendance_query,
    get_course_overview,
    get_daily_counts,
    get_student_stats,
    get_summary,
    now_local,
)

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


@router.get("/attendance.csv", response_class=Response)
async def export_attendance_csv(db: SessionDep, user: StaffUser, filters: FiltersDep):
    records = (await db.scalars(filtered_attendance_query(filters, lecturer_scope(user)))).all()
    filename = f"attendance_report_{now_local().date().isoformat()}.csv"
    return Response(
        content=attendance_to_csv(records),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
