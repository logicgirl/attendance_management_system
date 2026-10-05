import pytest

pytestmark = pytest.mark.anyio


async def test_terms_crud_and_overlap(client, admin_headers, lecturer_headers):
    res = await client.post(
        "/api/v1/terms",
        headers=admin_headers,
        json={"name": "2026-T1", "start_date": "2026-01-10", "end_date": "2026-04-10"},
    )
    assert res.status_code == 201
    term_id = res.json()["id"]

    overlap = await client.post(
        "/api/v1/terms",
        headers=admin_headers,
        json={"name": "2026-T2", "start_date": "2026-04-01", "end_date": "2026-07-01"},
    )
    assert overlap.status_code == 409

    backwards = await client.post(
        "/api/v1/terms",
        headers=admin_headers,
        json={"name": "Bad", "start_date": "2026-05-01", "end_date": "2026-04-01"},
    )
    assert backwards.status_code == 422

    denied = await client.post(
        "/api/v1/terms",
        headers=lecturer_headers,
        json={"name": "X", "start_date": "2027-01-01", "end_date": "2027-02-01"},
    )
    assert denied.status_code == 403

    renamed = await client.patch(
        f"/api/v1/terms/{term_id}", headers=admin_headers, json={"name": "Spring"}
    )
    assert renamed.json()["name"] == "Spring"
    listed = await client.get("/api/v1/terms", headers=lecturer_headers)
    assert [t["name"] for t in listed.json()] == ["Spring"]

    assert (
        await client.delete(f"/api/v1/terms/{term_id}", headers=admin_headers)
    ).status_code == 204


async def test_changes_are_audited(client, admin, admin_headers, lecturer_headers):
    await client.post(
        "/api/v1/students",
        headers=lecturer_headers,
        json={"student_id": "S1", "name": "ada", "department": "science"},
    )
    await client.delete("/api/v1/students/S1", headers=admin_headers)

    logs = (await client.get("/api/v1/audit-logs", headers=admin_headers)).json()
    assert [(log["action"], log["entity_id"]) for log in logs[:2]] == [
        ("student.deactivate", "S1"),
        ("student.create", "S1"),
    ]
    assert logs[0]["user_email"] == admin.email
    assert logs[1]["user_email"] == "lecturer@example.com"
    assert logs[1]["details"]["name"] == "Ada"

    filtered = await client.get(
        "/api/v1/audit-logs?entity_type=student&entity_id=S1", headers=admin_headers
    )
    assert len(filtered.json()) == 2
    assert (await client.get("/api/v1/audit-logs", headers=lecturer_headers)).status_code == 403
