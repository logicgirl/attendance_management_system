from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, Role, User


def lecturer_scope(user: User) -> int | None:
    """Lecturers only see their own courses; admins see everything."""
    return user.id if user.role == Role.LECTURER else None


async def get_course_for_user(db: AsyncSession, user: User, course_id: int) -> Course:
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    if user.role == Role.LECTURER and course.lecturer_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not teach this course")
    return course
