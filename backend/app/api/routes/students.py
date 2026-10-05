from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminUser, SessionDep, StaffUser
from app.models import Student
from app.schemas.student import StudentCreate, StudentRead, StudentUpdate
from app.services.attendance import now_local
from app.services.audit import audit
from app.services.student_ids import next_student_id

router = APIRouter(prefix="/students", tags=["students"])


async def get_student_or_404(db: SessionDep, student_id: str) -> Student:
    student = await db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Student '{student_id}' not found")
    return student


@router.get("", response_model=list[StudentRead])
async def list_students(
    db: SessionDep,
    _: StaffUser,
    search: str | None = Query(None, description="Matches student ID, name or department"),
    department: str | None = None,
    include_inactive: bool = False,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
):
    stmt = select(Student)
    if not include_inactive:
        stmt = stmt.where(Student.is_active)
    if department:
        stmt = stmt.where(Student.department.ilike(department.strip()))
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Student.student_id.ilike(pattern),
                Student.name.ilike(pattern),
                Student.department.ilike(pattern),
            )
        )
    stmt = stmt.order_by(Student.name).offset(offset).limit(limit)
    return (await db.scalars(stmt)).all()


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
async def create_student(db: SessionDep, user: StaffUser, payload: StudentCreate):
    """Register a student. Without a student_id one is generated (e.g. CS-26-0001).
    Re-registering a deactivated student ID reactivates it."""
    if payload.student_id is None:
        return await _create_with_generated_id(db, user, payload)

    student = await db.get(Student, payload.student_id)
    if student is not None and student.is_active:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Student ID '{payload.student_id}' already exists"
        )
    if student is None:
        student = Student(**payload.model_dump())
        db.add(student)
    else:
        student.name = payload.name
        student.department = payload.department
        student.is_active = True

    audit(db, user, "student.create", "student", payload.student_id, **payload.model_dump())
    await db.commit()
    await db.refresh(student)
    return student


async def _create_with_generated_id(db: SessionDep, user, payload: StudentCreate) -> Student:
    year = now_local().year
    # Two people registering at the same moment can pick the same number; retry if so
    for _ in range(5):
        student_id = await next_student_id(db, payload.department, year)
        student = Student(student_id=student_id, name=payload.name, department=payload.department)
        db.add(student)
        audit(
            db,
            user,
            "student.create",
            "student",
            student_id,
            **payload.model_dump(exclude={"student_id"}),
            generated_id=True,
        )
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue
        await db.refresh(student)
        return student
    raise HTTPException(
        status.HTTP_409_CONFLICT, "Could not generate a unique student ID; please try again"
    )


@router.get("/{student_id}", response_model=StudentRead)
async def read_student(db: SessionDep, _: StaffUser, student_id: str):
    return await get_student_or_404(db, student_id)


@router.patch("/{student_id}", response_model=StudentRead)
async def update_student(db: SessionDep, user: StaffUser, student_id: str, payload: StudentUpdate):
    student = await get_student_or_404(db, student_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(student, field, value)
    audit(db, user, "student.update", "student", student_id, **changes)
    await db.commit()
    await db.refresh(student)
    return student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_student(db: SessionDep, admin: AdminUser, student_id: str):
    """Remove a student from the roster. Their attendance history is kept."""
    student = await get_student_or_404(db, student_id)
    student.is_active = False
    audit(db, admin, "student.deactivate", "student", student_id)
    await db.commit()
