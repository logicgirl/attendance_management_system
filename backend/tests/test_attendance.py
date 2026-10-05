import datetime as dt

import pytest

from app.models import Role
from app.services.attendance import now_local
from tests.conftest import login

pytestmark = pytest.mark.anyio

URL = "/api/v1/attendance"


@pytest.fixture
async def course_id(make_student, make_course, lecturer):
    await make_student("CS-001", name="Ada Lovelace")
    await make_student("CS-002", name="Alan Turing")
    return await make_course("CS101", lecturer.id, ("CS-001", "CS-002"))


async def test_mark_attendance_today(client, lecturer_headers, course_id):
    res = await client.post(
        URL,
        headers=lecturer_headers,
        json={"course_id": course_id, "student_id": "CS-001", "status": "Late"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    today = now_local().date()
    assert body["date"] == today.isoformat()
    assert body["day"] == today.strftime("%A")
    assert body["student_name"] == "Ada Lovelace"
    assert body["course_code"] == "CS101"
    assert body["status"] == "Late"
    assert body["term"] == "2026-Term1"
    assert body["recorded_by"] is not None


async def test_same_day_in_two_courses_is_allowed(
    client, lecturer, lecturer_headers, course_id, make_course
):
    other = await make_course("CS102", lecturer.id, ("CS-001",))
    for cid in (course_id, other):
        res = await client.post(
            URL, headers=lecturer_headers, json={"course_id": cid, "student_id": "CS-001"}
        )
        assert res.status_code == 201

    again = await client.post(
        URL, headers=lecturer_headers, json={"course_id": course_id, "student_id": "CS-001"}
    )
    assert again.status_code == 409
    assert "already been recorded" in again.json()["detail"]


async def test_rejects_future_dates_and_students_not_enrolled(
    client, lecturer_headers, course_id, make_student
):
    tomorrow = (now_local().date() + dt.timedelta(days=1)).isoformat()
    future = await client.post(
        URL,
        headers=lecturer_headers,
        json={"course_id": course_id, "student_id": "CS-001", "date": tomorrow},
    )
    assert future.status_code == 422

    await make_student("CS-999")
    outsider = await client.post(
        URL, headers=lecturer_headers, json={"course_id": course_id, "student_id": "CS-999"}
    )
    assert outsider.status_code == 422
    assert "Not enrolled" in outsider.json()["detail"]


async def test_lecturer_limited_to_own_courses(
    client, lecturer_headers, course_id, make_user, make_course
):
    other_lecturer = await make_user("other@example.com", Role.LECTURER)
    foreign = await make_course("MA101", other_lecturer.id, ("CS-001",))

    res = await client.post(
        URL, headers=lecturer_headers, json={"course_id": foreign, "student_id": "CS-001"}
    )
    assert res.status_code == 403

    other_headers = await login(client, "other@example.com")
    await client.post(
        URL, headers=other_headers, json={"course_id": foreign, "student_id": "CS-001"}
    )
    mine = await client.get(URL, headers=lecturer_headers)
    assert mine.json() == []
    record_id = (await client.get(URL, headers=other_headers)).json()[0]["id"]
    patch = await client.patch(
        f"{URL}/{record_id}", headers=lecturer_headers, json={"status": "Absent"}
    )
    assert patch.status_code == 403


async def test_save_register_creates_then_updates(client, lecturer_headers, course_id):
    payload = {
        "course_id": course_id,
        "records": [
            {"student_id": "CS-001", "status": "Present"},
            {"student_id": "CS-002", "status": "Absent"},
        ],
    }
    first = await client.post(f"{URL}/register", headers=lecturer_headers, json=payload)
    assert first.status_code == 200, first.text
    assert {r["student_id"]: r["status"] for r in first.json()} == {
        "CS-001": "Present",
        "CS-002": "Absent",
    }

    payload["records"][1]["status"] = "Late"
    second = await client.post(f"{URL}/register", headers=lecturer_headers, json=payload)
    assert {r["status"] for r in second.json()} == {"Present", "Late"}
    assert {r["id"] for r in second.json()} == {r["id"] for r in first.json()}

    register = await client.get(f"/api/v1/courses/{course_id}/register", headers=lecturer_headers)
    assert [(r["name"], r["status"]) for r in register.json()] == [
        ("Ada Lovelace", "Present"),
        ("Alan Turing", "Late"),
    ]


async def test_list_filter_update_and_delete(client, admin_headers, course_id):
    today = now_local().date()
    yesterday = today - dt.timedelta(days=1)
    for student_id, day in [("CS-001", yesterday), ("CS-001", today), ("CS-002", today)]:
        res = await client.post(
            URL,
            headers=admin_headers,
            json={"course_id": course_id, "student_id": student_id, "date": day.isoformat()},
        )
        assert res.status_code == 201

    everything = (await client.get(URL, headers=admin_headers)).json()
    assert everything[0]["date"] == yesterday.isoformat()

    turing = await client.get(f"{URL}?search=turing", headers=admin_headers)
    assert [r["student_id"] for r in turing.json()] == ["CS-002"]
    by_date = await client.get(f"{URL}?date_from={today}&date_to={today}", headers=admin_headers)
    assert len(by_date.json()) == 2
    by_course = await client.get(f"{URL}?course_id={course_id}", headers=admin_headers)
    assert len(by_course.json()) == 3

    record_id = everything[0]["id"]
    patched = await client.patch(
        f"{URL}/{record_id}", headers=admin_headers, json={"status": "Absent"}
    )
    assert patched.json()["status"] == "Absent"

    ids = [r["id"] for r in everything[:2]]
    deleted = await client.delete(f"{URL}?ids={ids[0]}&ids={ids[1]}", headers=admin_headers)
    assert deleted.json() == {"deleted": 2}
    assert len((await client.get(URL, headers=admin_headers)).json()) == 1


async def test_lecturer_cannot_delete_records(client, lecturer_headers):
    res = await client.delete(f"{URL}?ids=1", headers=lecturer_headers)
    assert res.status_code == 403


async def test_term_comes_from_terms_table(client, admin_headers, course_id):
    today = now_local().date()
    await client.post(
        "/api/v1/terms",
        headers=admin_headers,
        json={
            "name": "Autumn",
            "start_date": (today - dt.timedelta(days=30)).isoformat(),
            "end_date": (today + dt.timedelta(days=30)).isoformat(),
        },
    )
    res = await client.post(
        URL, headers=admin_headers, json={"course_id": course_id, "student_id": "CS-001"}
    )
    assert res.json()["term"] == "Autumn"


async def test_student_sees_only_own_attendance(client, lecturer_headers, course_id, make_user):
    for student_id in ("CS-001", "CS-002"):
        await client.post(
            URL, headers=lecturer_headers, json={"course_id": course_id, "student_id": student_id}
        )

    await make_user("ada@example.com", Role.STUDENT, student_id="CS-001")
    headers = await login(client, "ada@example.com")

    mine = await client.get(f"{URL}/me", headers=headers)
    assert [r["student_id"] for r in mine.json()] == ["CS-001"]
    assert (await client.get(URL, headers=headers)).status_code == 403
    denied = await client.post(
        URL, headers=headers, json={"course_id": course_id, "student_id": "CS-001"}
    )
    assert denied.status_code == 403
