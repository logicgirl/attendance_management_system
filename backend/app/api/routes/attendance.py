import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.api.access import get_course_for_user, lecturer_scope
from app.api.deps import AdminUser, SessionDep, StaffUser, StudentUser
from app.models import Attendance, Course, Enrollment, Student
from app.schemas.attendance import (
    AttendanceCreate,
    AttendanceRead,
    AttendanceUpdate,
    DeleteResult,
    RegisterSubmit,
)
from app.services.attendance import AttendanceFilters, filtered_attendance_query, now_local
from app.services.audit import audit
from app.services.terms import term_for_date

router = APIRouter(prefix="/attendance", tags=["attendance"])

FiltersDep = Annotated[AttendanceFilters, Depends()]


def resolve_date(requested: dt.date | None) -> tuple[dt.date, dt.time]:
    now = now_local()
    day = requested or now.date()
    if day > now.date():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot mark attendance for a future date"
        )
    return day, now.time().replace(microsecond=0)


async def check_enrolled(db: SessionDep, course: Course, student_ids: set[str]) -> None:
    enrolled = set(
        (
            await db.scalars(
                select(Enrollment.student_id)
                .join(Student, Student.student_id == Enrollment.student_id)
                .where(
                    Enrollment.course_id == course.id,
                    Enrollment.student_id.in_(student_ids),
                    Student.is_active,
                )
            )
        ).all()
    )
    if missing := sorted(student_ids - enrolled):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Not enrolled in {course.code} (or inactive): {', '.join(missing)}",
        )


async def get_record_for_user(db: SessionDep, user, record_id: int) -> Attendance:
    record = await db.get(Attendance, record_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attendance record not found")
    await get_course_for_user(db, user, record.course_id)
    return record


async def reload(db: SessionDep, ids: list[int]) -> list[Attendance]:
    stmt = filtered_attendance_query(AttendanceFilters()).where(Attendance.id.in_(ids))
    return list((await db.scalars(stmt.execution_options(populate_existing=True))).all())


@router.get("", response_model=list[AttendanceRead])
async def list_attendance(
    db: SessionDep,
    user: StaffUser,
    filters: FiltersDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=5000),
):
    stmt = filtered_attendance_query(filters, lecturer_scope(user)).offset(offset).limit(limit)
    return (await db.scalars(stmt)).all()


@router.post("", response_model=AttendanceRead, status_code=status.HTTP_201_CREATED)
async def mark_attendance(db: SessionDep, user: StaffUser, payload: AttendanceCreate):
    """Mark one student. Use POST /attendance/register to save a whole class at once."""
    day, time = resolve_date(payload.date)
    course = await get_course_for_user(db, user, payload.course_id)
    await check_enrolled(db, course, {payload.student_id})

    duplicate = HTTPException(
        status.HTTP_409_CONFLICT,
        f"Attendance for {payload.student_id} in {course.code} on {day.isoformat()} "
        "has already been recorded",
    )
    existing = await db.scalar(
        select(Attendance.id).where(
            Attendance.student_id == payload.student_id,
            Attendance.course_id == course.id,
            Attendance.date == day,
        )
    )
    if existing is not None:
        raise duplicate

    record = Attendance(
        student_id=payload.student_id,
        course_id=course.id,
        date=day,
        time=time,
        status=payload.status,
        term=await term_for_date(db, day),
        recorded_by=user.id,
    )
    db.add(record)
    try:
        await db.flush()
        audit(db, user, "attendance.create", "attendance", record.id, **payload.model_dump())
        await db.commit()
    except IntegrityError:
        # Another request recorded the same student/course/day in the meantime
        await db.rollback()
        raise duplicate from None
    return (await reload(db, [record.id]))[0]


@router.post("/register", response_model=list[AttendanceRead])
async def save_register(db: SessionDep, user: StaffUser, payload: RegisterSubmit):
    """Save a class register: creates new records and updates ones already marked that day."""
    day, time = resolve_date(payload.date)
    course = await get_course_for_user(db, user, payload.course_id)
    statuses = {entry.student_id: entry.status for entry in payload.records}
    await check_enrolled(db, course, set(statuses))

    existing = {
        a.student_id: a
        for a in (
            await db.scalars(
                select(Attendance).where(
                    Attendance.course_id == course.id,
                    Attendance.date == day,
                    Attendance.student_id.in_(statuses),
                )
            )
        ).all()
    }
    term = await term_for_date(db, day)
    records = []
    for student_id, new_status in statuses.items():
        record = existing.get(student_id)
        if record is None:
            record = Attendance(
                student_id=student_id,
                course_id=course.id,
                date=day,
                time=time,
                status=new_status,
                term=term,
                recorded_by=user.id,
            )
            db.add(record)
        else:
            record.status = new_status
        records.append(record)

    await db.flush()
    audit(
        db,
        user,
        "attendance.register",
        "course",
        course.id,
        date=day,
        created=len(statuses) - len(existing),
        updated=len(existing),
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The register was changed by someone else; please reload"
        ) from None
    return await reload(db, [r.id for r in records])


@router.get("/me", response_model=list[AttendanceRead])
async def my_attendance(db: SessionDep, user: StudentUser, filters: FiltersDep):
    """A student's own attendance history."""
    if not user.student_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No student record is linked to your account"
        )
    filters.student_id = user.student_id
    return (await db.scalars(filtered_attendance_query(filters))).all()


@router.patch("/{record_id}", response_model=AttendanceRead)
async def update_attendance(
    db: SessionDep, user: StaffUser, record_id: int, payload: AttendanceUpdate
):
    record = await get_record_for_user(db, user, record_id)
    audit(
        db,
        user,
        "attendance.update",
        "attendance",
        record.id,
        old_status=record.status,
        new_status=payload.status,
    )
    record.status = payload.status
    await db.commit()
    return record


@router.delete("", response_model=DeleteResult)
async def delete_attendance(
    db: SessionDep, admin: AdminUser, ids: Annotated[list[int], Query(min_length=1)]
):
    """Delete one or more records, e.g. `DELETE /attendance?ids=4&ids=7`."""
    doomed = (await db.scalars(select(Attendance).where(Attendance.id.in_(ids)))).all()
    for record in doomed:
        audit(
            db,
            admin,
            "attendance.delete",
            "attendance",
            record.id,
            student_id=record.student_id,
            course=record.course_code,
            date=record.date,
            status=record.status,
        )
    await db.execute(delete(Attendance).where(Attendance.id.in_([r.id for r in doomed])))
    await db.commit()
    return DeleteResult(deleted=len(doomed))
