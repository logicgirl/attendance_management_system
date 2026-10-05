import csv
import datetime as dt
import io

import pytest

from app.services.attendance import now_local

pytestmark = pytest.mark.anyio


@pytest.fixture
async def course_id(make_student, make_course, lecturer):
    ids = tuple(f"CS-00{i}" for i in range(1, 5))
    for i, student_id in enumerate(ids):
        await make_student(student_id, name=f"Student {'ABCD'[i]}")
    return await make_course("CS101", lecturer.id, ids)


async def register(client, headers, course_id, statuses: dict[str, str]):
    res = await client.post(
        "/api/v1/attendance/register",
        headers=headers,
        json={
            "course_id": course_id,
            "records": [{"student_id": s, "status": v} for s, v in statuses.items()],
        },
    )
    assert res.status_code == 200, res.text


async def test_summary(client, lecturer_headers, course_id):
    await register(
        client,
        lecturer_headers,
        course_id,
        {"CS-001": "Present", "CS-002": "Present", "CS-003": "Late"},
    )
    res = await client.get(
        f"/api/v1/reports/summary?course_id={course_id}", headers=lecturer_headers
    )
    body = res.json()
    assert body["active_students"] == 4
    assert body["total_records"] == 3
    assert (body["present"], body["late"], body["absent"]) == (2, 1, 0)
    assert body["present_rate"] == 66.7


async def test_lecturer_summary_only_counts_own_students(
    client, lecturer_headers, course_id, make_student
):
    await make_student("OUTSIDER")
    body = (await client.get("/api/v1/reports/summary", headers=lecturer_headers)).json()
    assert body["active_students"] == 4
    assert body["total_records"] == 0
    assert body["present_rate"] == 0.0


async def test_student_stats(client, lecturer_headers, course_id):
    await register(client, lecturer_headers, course_id, {"CS-001": "Late", "CS-002": "Absent"})
    res = await client.get(
        f"/api/v1/reports/students?course_id={course_id}", headers=lecturer_headers
    )
    stats = {s["student_id"]: s for s in res.json()}
    assert stats["CS-001"]["attendance_rate"] == 100.0
    assert stats["CS-002"]["attendance_rate"] == 0.0
    assert stats["CS-002"]["absent"] == 1


async def test_csv_export(client, lecturer_headers, course_id):
    await register(client, lecturer_headers, course_id, {"CS-001": "Present"})

    res = await client.get("/api/v1/reports/attendance.csv", headers=lecturer_headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(res.text)))
    assert rows[0][:4] == ["Record ID", "Student ID", "Full Name", "Course"]
    assert rows[1][1:4] == ["CS-001", "Student A", "CS101"]
    assert rows[1][7] == "Present"


async def test_daily_counts(client, lecturer_headers, course_id):
    today = now_local().date()
    yesterday = (today - dt.timedelta(days=1)).isoformat()
    res = await client.post(
        "/api/v1/attendance/register",
        headers=lecturer_headers,
        json={
            "course_id": course_id,
            "date": yesterday,
            "records": [
                {"student_id": "CS-001", "status": "Present"},
                {"student_id": "CS-002", "status": "Absent"},
            ],
        },
    )
    assert res.status_code == 200
    await register(client, lecturer_headers, course_id, {"CS-001": "Late"})

    days = (await client.get("/api/v1/reports/daily?days=3", headers=lecturer_headers)).json()
    assert [d["date"] for d in days][-1] == today.isoformat()
    assert len(days) == 3
    assert days[0]["total"] == 0 and days[0]["attendance_rate"] is None
    assert (days[1]["present"], days[1]["absent"], days[1]["attendance_rate"]) == (1, 1, 50.0)
    assert (days[2]["late"], days[2]["attendance_rate"]) == (1, 100.0)


async def test_course_overview(client, lecturer_headers, course_id, make_course):
    await make_course("OTHER")  # not taught by this lecturer
    await register(client, lecturer_headers, course_id, {"CS-001": "Present", "CS-002": "Late"})

    overview = (await client.get("/api/v1/reports/courses", headers=lecturer_headers)).json()
    assert len(overview) == 1
    row = overview[0]
    assert (row["code"], row["enrolled"], row["marked"]) == ("CS101", 4, 2)
    assert (row["present"], row["late"], row["absent"]) == (1, 1, 0)
    assert row["lecturer_name"] == "Lecturer"
