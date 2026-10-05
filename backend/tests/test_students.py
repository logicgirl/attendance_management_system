import pytest

from app.services.attendance import now_local
from app.services.student_ids import department_code

pytestmark = pytest.mark.anyio


async def test_create_and_list_students(client, lecturer_headers):
    res = await client.post(
        "/api/v1/students",
        headers=lecturer_headers,
        json={"student_id": "CS-001", "name": "  ada lovelace ", "department": "computer science"},
    )
    assert res.status_code == 201
    assert res.json()["name"] == "Ada Lovelace"
    assert res.json()["department"] == "Computer Science"

    listed = await client.get("/api/v1/students?search=ada", headers=lecturer_headers)
    assert [s["student_id"] for s in listed.json()] == ["CS-001"]


async def test_student_id_format_is_validated(client, lecturer_headers):
    res = await client.post(
        "/api/v1/students",
        headers=lecturer_headers,
        json={"student_id": "bad id!", "name": "X", "department": "Y"},
    )
    assert res.status_code == 422


async def test_duplicate_active_student_conflicts(client, lecturer_headers, make_student):
    await make_student("CS-001")
    res = await client.post(
        "/api/v1/students",
        headers=lecturer_headers,
        json={"student_id": "CS-001", "name": "Someone", "department": "Arts"},
    )
    assert res.status_code == 409


async def test_deactivate_hides_student_and_reregister_reactivates(
    client, admin_headers, make_student
):
    await make_student("CS-001")
    assert (
        await client.delete("/api/v1/students/CS-001", headers=admin_headers)
    ).status_code == 204

    active = await client.get("/api/v1/students", headers=admin_headers)
    assert active.json() == []
    everyone = await client.get("/api/v1/students?include_inactive=true", headers=admin_headers)
    assert everyone.json()[0]["is_active"] is False

    res = await client.post(
        "/api/v1/students",
        headers=admin_headers,
        json={"student_id": "CS-001", "name": "Ada Byron", "department": "Maths"},
    )
    assert res.status_code == 201
    assert res.json() | {"created_at": None} == {
        "student_id": "CS-001",
        "name": "Ada Byron",
        "department": "Maths",
        "is_active": True,
        "created_at": None,
    }


async def test_lecturer_cannot_deactivate(client, lecturer_headers, make_student):
    await make_student("CS-001")
    res = await client.delete("/api/v1/students/CS-001", headers=lecturer_headers)
    assert res.status_code == 403


async def test_update_student(client, lecturer_headers, make_student):
    await make_student("CS-001")
    res = await client.patch(
        "/api/v1/students/CS-001", headers=lecturer_headers, json={"department": "physics"}
    )
    assert res.json()["department"] == "Physics"
    assert res.json()["name"] == "Ada Lovelace"


async def test_student_id_is_generated_when_left_out(client, lecturer_headers):
    yy = f"{now_local().year % 100:02d}"
    ids = []
    for name, department in (
        ("Ada Lovelace", "computer science"),
        ("Alan Turing", "Computer Science"),
        ("Emmy Noether", "Mathematics"),
    ):
        res = await client.post(
            "/api/v1/students",
            headers=lecturer_headers,
            json={"name": name, "department": department},
        )
        assert res.status_code == 201, res.text
        ids.append(res.json()["student_id"])
    assert ids == [f"CS-{yy}-0001", f"CS-{yy}-0002", f"MAT-{yy}-0001"]

    logs = await client.get("/api/v1/students?search=CS-", headers=lecturer_headers)
    assert len(logs.json()) == 2


async def test_generated_ids_continue_after_the_highest(client, lecturer_headers, make_student):
    yy = f"{now_local().year % 100:02d}"
    await make_student(f"CS-{yy}-0007", department="Computer Science")
    res = await client.post(
        "/api/v1/students",
        headers=lecturer_headers,
        json={"name": "New Student", "department": "Computer Science"},
    )
    assert res.json()["student_id"] == f"CS-{yy}-0008"


def test_department_codes():
    assert department_code("Computer Science") == "CS"
    assert department_code("Mathematics") == "MAT"
    assert department_code("Business Administration / B") == "BAB"
    assert department_code("123") == "STU"
