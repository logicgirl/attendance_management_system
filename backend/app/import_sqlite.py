"""Copy students and attendance from the old desktop app's SQLite database.

Usage: python -m app.import_sqlite ..\\attendance_system.db
The old app had no courses, so its records go into a "GENERAL" course, and every
imported student is enrolled in it. Safe to run more than once.
"""

import argparse
import asyncio
import datetime as dt
import sqlite3
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models import Attendance, AttendanceStatus, Course, Enrollment, Student

LEGACY_COURSE = {"code": "GENERAL", "title": "General Attendance", "department": "General"}


def parse_time(value: str) -> dt.time:
    for fmt in ("%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            return dt.datetime.strptime(value.strip(), fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised time {value!r}")


async def import_db(path: Path) -> None:
    src = sqlite3.connect(path)
    students = src.execute(
        "SELECT student_id, name, department, is_active FROM students"
    ).fetchall()
    records = src.execute(
        "SELECT student_id, date, time, status, term FROM attendance ORDER BY id"
    ).fetchall()
    src.close()

    added_students = added_records = already = skipped = 0
    async with SessionLocal() as db:
        course = await db.scalar(select(Course).where(Course.code == LEGACY_COURSE["code"]))
        if course is None:
            course = Course(**LEGACY_COURSE)
            db.add(course)
            await db.flush()

        known_ids = set((await db.scalars(select(Student.student_id))).all())
        for student_id, name, department, is_active in students:
            if student_id in known_ids:
                continue
            db.add(
                Student(
                    student_id=student_id,
                    name=name,
                    department=department,
                    is_active=bool(is_active),
                )
            )
            known_ids.add(student_id)
            added_students += 1
        await db.flush()

        enrolled = set(
            (
                await db.scalars(
                    select(Enrollment.student_id).where(Enrollment.course_id == course.id)
                )
            ).all()
        )
        for student_id, *_ in students:
            if student_id not in enrolled:
                db.add(Enrollment(course_id=course.id, student_id=student_id))
                enrolled.add(student_id)

        existing = set(
            (
                await db.execute(
                    select(Attendance.student_id, Attendance.date).where(
                        Attendance.course_id == course.id
                    )
                )
            ).all()
        )
        for student_id, date_str, time_str, status, term in records:
            try:
                day = dt.date.fromisoformat(date_str)
                if (student_id, day) in existing:
                    already += 1
                    continue
                if student_id not in known_ids:
                    raise ValueError("unknown student")
                db.add(
                    Attendance(
                        student_id=student_id,
                        course_id=course.id,
                        date=day,
                        time=parse_time(time_str),
                        status=AttendanceStatus(status),
                        term=term or settings.CURRENT_TERM,
                    )
                )
                existing.add((student_id, day))
                added_records += 1
            except ValueError as exc:
                skipped += 1
                print(f"Skipped attendance row {student_id} {date_str}: {exc}")

        await db.commit()
    await engine.dispose()
    print(
        f"Imported {added_students} students and {added_records} attendance records "
        f"({already} already imported, {skipped} skipped)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_path", type=Path)
    args = parser.parse_args()
    if not args.sqlite_path.exists():
        raise SystemExit(f"File not found: {args.sqlite_path}")
    asyncio.run(import_db(args.sqlite_path))


if __name__ == "__main__":
    main()
