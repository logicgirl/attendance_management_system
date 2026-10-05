import datetime as dt

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, or_, select

from app.api.access import get_course_for_user, lecturer_scope
from app.api.deps import AdminUser, SessionDep, StaffUser
from app.models import Attendance, Course, Enrollment, Role, Student, User
from app.schemas.attendance import RegisterRow
from app.schemas.course import CourseCreate, CourseRead, CourseUpdate, EnrollRequest
from app.schemas.student import StudentRead
from app.services.attendance import now_local
from app.services.audit import audit

router = APIRouter(prefix="/courses", tags=["courses"])


async def ensure_can_teach(db: SessionDep, lecturer_id: int) -> None:
    lecturer = await db.get(User, lecturer_id)
    if lecturer is None or lecturer.role not in (Role.LECTURER, Role.ADMIN):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No lecturer with ID {lecturer_id}")


async def enrolled_students(db: SessionDep, course_id: int) -> list[Student]:
    stmt = (
        select(Student)
        .join(Enrollment, Enrollment.student_id == Student.student_id)
        .where(Enrollment.course_id == course_id, Student.is_active)
        .order_by(Student.name)
    )
    return list((await db.scalars(stmt)).all())


@router.get("", response_model=list[CourseRead])
async def list_courses(
    db: SessionDep,
    user: StaffUser,
    search: str | None = None,
    include_inactive: bool = False,
):
    """Admins see every course; lecturers see the courses they teach."""
    stmt = select(Course).order_by(Course.code)
    if (lecturer_id := lecturer_scope(user)) is not None:
        stmt = stmt.where(Course.lecturer_id == lecturer_id)
    if not include_inactive:
        stmt = stmt.where(Course.is_active)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Course.code.ilike(pattern), Course.title.ilike(pattern)))
    return (await db.scalars(stmt)).all()


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
async def create_course(db: SessionDep, admin: AdminUser, payload: CourseCreate):
    if await db.scalar(select(Course.id).where(Course.code == payload.code)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Course code '{payload.code}' already exists"
        )
    if payload.lecturer_id is not None:
        await ensure_can_teach(db, payload.lecturer_id)

    course = Course(**payload.model_dump())
    db.add(course)
    await db.flush()
    audit(db, admin, "course.create", "course", course.id, **payload.model_dump())
    await db.commit()
    return await db.get(Course, course.id, populate_existing=True)


@router.get("/{course_id}", response_model=CourseRead)
async def read_course(db: SessionDep, user: StaffUser, course_id: int):
    return await get_course_for_user(db, user, course_id)


@router.patch("/{course_id}", response_model=CourseRead)
async def update_course(db: SessionDep, admin: AdminUser, course_id: int, payload: CourseUpdate):
    course = await get_course_for_user(db, admin, course_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("lecturer_id") is not None:
        await ensure_can_teach(db, changes["lecturer_id"])

    for field, value in changes.items():
        if value is not None or field == "lecturer_id":
            setattr(course, field, value)
    audit(db, admin, "course.update", "course", course.id, **changes)
    await db.commit()
    return await db.get(Course, course.id, populate_existing=True)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_course(db: SessionDep, admin: AdminUser, course_id: int):
    course = await get_course_for_user(db, admin, course_id)
    course.is_active = False
    audit(db, admin, "course.deactivate", "course", course.id)
    await db.commit()


@router.get("/{course_id}/students", response_model=list[StudentRead])
async def list_enrolled(db: SessionDep, user: StaffUser, course_id: int):
    await get_course_for_user(db, user, course_id)
    return await enrolled_students(db, course_id)


@router.post("/{course_id}/students", response_model=list[StudentRead])
async def enroll_students(db: SessionDep, user: StaffUser, course_id: int, payload: EnrollRequest):
    """Enroll students in a course. Students already enrolled are left as they are."""
    await get_course_for_user(db, user, course_id)
    wanted = set(payload.student_ids)
    found = set(
        (
            await db.scalars(
                select(Student.student_id).where(Student.student_id.in_(wanted), Student.is_active)
            )
        ).all()
    )
    if missing := sorted(wanted - found):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No active student with ID: {', '.join(missing)}"
        )

    already = set(
        (
            await db.scalars(
                select(Enrollment.student_id).where(
                    Enrollment.course_id == course_id, Enrollment.student_id.in_(wanted)
                )
            )
        ).all()
    )
    new_ids = sorted(wanted - already)
    db.add_all(Enrollment(course_id=course_id, student_id=sid) for sid in new_ids)
    if new_ids:
        audit(db, user, "course.enroll", "course", course_id, student_ids=new_ids)
    await db.commit()
    return await enrolled_students(db, course_id)


@router.delete("/{course_id}/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unenroll_student(db: SessionDep, user: StaffUser, course_id: int, student_id: str):
    """Remove a student from a course. Their past attendance is kept."""
    await get_course_for_user(db, user, course_id)
    result = await db.execute(
        delete(Enrollment).where(
            Enrollment.course_id == course_id, Enrollment.student_id == student_id
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student is not enrolled in this course")
    audit(db, user, "course.unenroll", "course", course_id, student_id=student_id)
    await db.commit()


@router.get("/{course_id}/register", response_model=list[RegisterRow])
async def class_register(
    db: SessionDep,
    user: StaffUser,
    course_id: int,
    date: dt.date | None = Query(None, description="Defaults to today"),
):
    """Enrolled students with their status for the day (null if not yet marked)."""
    await get_course_for_user(db, user, course_id)
    day = date or now_local().date()
    marked = {
        a.student_id: a
        for a in (
            await db.scalars(
                select(Attendance).where(Attendance.course_id == course_id, Attendance.date == day)
            )
        ).all()
    }
    return [
        RegisterRow(
            student_id=s.student_id,
            name=s.name,
            department=s.department,
            attendance_id=marked[s.student_id].id if s.student_id in marked else None,
            status=marked[s.student_id].status if s.student_id in marked else None,
        )
        for s in await enrolled_students(db, course_id)
    ]
