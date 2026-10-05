import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Student


def department_code(department: str) -> str:
    """Initials for multi-word departments (Computer Science -> CS), otherwise the first
    three letters (Mathematics -> MAT)."""
    words = re.findall(r"[A-Za-z]+", department)
    if not words:
        return "STU"
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(w[0] for w in words[:4]).upper()


async def next_student_id(db: AsyncSession, department: str, year: int) -> str:
    """The next free ID for this department and year, e.g. CS-26-0001."""
    prefix = f"{department_code(department)}-{year % 100:02d}-"
    existing = (
        await db.scalars(select(Student.student_id).where(Student.student_id.like(f"{prefix}%")))
    ).all()
    numbers = [int(sid[len(prefix) :]) for sid in existing if sid[len(prefix) :].isdigit()]
    return f"{prefix}{max(numbers, default=0) + 1:04d}"
