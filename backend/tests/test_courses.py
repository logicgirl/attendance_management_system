import pytest

from app.models import Role
from tests.conftest import login

pytestmark = pytest.mark.anyio

URL = "/api/v1/courses"


async def test_admin_creates_course_and_assigns_lecturer(
    client, admin_headers, lecturer, lecturer_headers
):
    res = await client.post(
        URL,
        headers=admin_headers,
        json={
            "code": "cs 101",
            "title": "intro to computing",
            "department": "science",
            "lecturer_id": lecturer.id,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert (body["code"], body["title"]) == ("CS 101", "Intro To Computing")
    assert body["lecturer_name"] == "Lecturer"

    dup = await client.post(
        URL, headers=admin_headers, json={"code": "CS 101", "title": "X", "department": "Y"}
    )
    assert dup.status_code == 409

    mine = await client.get(URL, headers=lecturer_headers)
    assert [c["code"] for c in mine.json()] == ["CS 101"]


async def test_lecturer_cannot_create_courses(client, lecturer_headers):
    res = await client.post(
        URL, headers=lecturer_headers, json={"code": "CS101", "title": "X", "department": "Y"}
    )
    assert res.status_code == 403


async def test_student_cannot_be_lecturer(client, admin_headers, make_student, make_user):
    await make_student("S1")
    student = await make_user("s@example.com", Role.STUDENT, student_id="S1")
    res = await client.post(
        URL,
        headers=admin_headers,
        json={"code": "CS101", "title": "X", "department": "Y", "lecturer_id": student.id},
    )
    assert res.status_code == 404


async def test_lecturer_only_sees_own_courses(client, lecturer, lecturer_headers, make_course):
    await make_course("MINE", lecturer.id)
    other = await make_course("THEIRS")
    assert [c["code"] for c in (await client.get(URL, headers=lecturer_headers)).json()] == ["MINE"]
    assert (await client.get(f"{URL}/{other}", headers=lecturer_headers)).status_code == 403


async def test_enroll_and_unenroll(client, lecturer, lecturer_headers, make_course, make_student):
    await make_student("S1", name="Ada")
    await make_student("S2", name="Bob")
    course_id = await make_course("CS101", lecturer.id)

    res = await client.post(
        f"{URL}/{course_id}/students", headers=lecturer_headers, json={"student_ids": ["S1", "S2"]}
    )
    assert [s["student_id"] for s in res.json()] == ["S1", "S2"]

    again = await client.post(
        f"{URL}/{course_id}/students", headers=lecturer_headers, json={"student_ids": ["S1"]}
    )
    assert len(again.json()) == 2

    unknown = await client.post(
        f"{URL}/{course_id}/students", headers=lecturer_headers, json={"student_ids": ["NOPE"]}
    )
    assert unknown.status_code == 404

    removed = await client.delete(f"{URL}/{course_id}/students/S1", headers=lecturer_headers)
    assert removed.status_code == 204
    left = await client.get(f"{URL}/{course_id}/students", headers=lecturer_headers)
    assert [s["student_id"] for s in left.json()] == ["S2"]


async def test_update_and_deactivate_course(client, admin_headers, lecturer, make_course):
    course_id = await make_course("CS101")
    res = await client.patch(
        f"{URL}/{course_id}", headers=admin_headers, json={"lecturer_id": lecturer.id}
    )
    assert res.json()["lecturer_name"] == "Lecturer"
    unassigned = await client.patch(
        f"{URL}/{course_id}", headers=admin_headers, json={"lecturer_id": None}
    )
    assert unassigned.json()["lecturer_id"] is None

    assert (await client.delete(f"{URL}/{course_id}", headers=admin_headers)).status_code == 204
    assert (await client.get(URL, headers=admin_headers)).json() == []
    everything = await client.get(f"{URL}?include_inactive=true", headers=admin_headers)
    assert everything.json()[0]["is_active"] is False


async def test_register_rejects_other_lecturers(client, make_user, make_course):
    await make_user("a@example.com", Role.LECTURER)
    course_id = await make_course("CS101")
    headers = await login(client, "a@example.com")
    res = await client.get(f"{URL}/{course_id}/register", headers=headers)
    assert res.status_code == 403
