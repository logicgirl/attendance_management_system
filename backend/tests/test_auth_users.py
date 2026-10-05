import pytest

from app.models import Role
from tests.conftest import PASSWORD, login

pytestmark = pytest.mark.anyio


async def test_login_and_me(client, make_user):
    await make_user("admin@example.com", Role.ADMIN)
    res = await client.post(
        "/api/v1/auth/login", data={"username": "ADMIN@example.com", "password": PASSWORD}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "admin"

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.json()["email"] == "admin@example.com"


async def test_login_rejects_bad_password(client, make_user):
    await make_user("admin@example.com", Role.ADMIN)
    res = await client.post(
        "/api/v1/auth/login", data={"username": "admin@example.com", "password": "wrong-pass"}
    )
    assert res.status_code == 401


async def test_requests_without_token_are_rejected(client):
    assert (await client.get("/api/v1/students")).status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert (await client.get("/api/v1/students", headers=bad)).status_code == 401


async def test_admin_creates_users(client, admin_headers, make_student):
    res = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "full_name": "Grace Hopper",
            "email": "Grace@Example.com",
            "password": "lecturer-pass",
            "role": "lecturer",
        },
    )
    assert res.status_code == 201
    assert res.json()["email"] == "grace@example.com"

    dup = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "full_name": "X",
            "email": "grace@example.com",
            "password": "12345678",
            "role": "admin",
        },
    )
    assert dup.status_code == 409

    no_link = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "full_name": "S",
            "email": "s@example.com",
            "password": "12345678",
            "role": "student",
        },
    )
    assert no_link.status_code == 422

    await make_student("STU-1")
    student = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "full_name": "S",
            "email": "s@example.com",
            "password": "12345678",
            "role": "student",
            "student_id": "STU-1",
        },
    )
    assert student.status_code == 201


async def test_lecturer_cannot_manage_users(client, lecturer_headers):
    res = await client.get("/api/v1/users", headers=lecturer_headers)
    assert res.status_code == 403


async def test_deactivated_user_loses_access(client, admin_headers, make_user):
    lecturer = await make_user("lecturer@example.com", Role.LECTURER)
    headers = await login(client, "lecturer@example.com")

    res = await client.patch(
        f"/api/v1/users/{lecturer.id}", headers=admin_headers, json={"is_active": False}
    )
    assert res.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401


async def test_admin_cannot_demote_self(client, admin_headers):
    me = (await client.get("/api/v1/auth/me", headers=admin_headers)).json()
    res = await client.patch(
        f"/api/v1/users/{me['id']}", headers=admin_headers, json={"role": "lecturer"}
    )
    assert res.status_code == 400


async def test_account_locks_after_repeated_failures(client, make_user, admin_headers):
    user = await make_user("lecturer@example.com", Role.LECTURER)
    for _ in range(5):
        res = await client.post(
            "/api/v1/auth/login", data={"username": user.email, "password": "wrong-pass"}
        )
        assert res.status_code == 401

    locked = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": PASSWORD}
    )
    assert locked.status_code == 423
    assert "Try again" in locked.json()["detail"]

    # An admin password reset unlocks the account
    await client.patch(
        f"/api/v1/users/{user.id}", headers=admin_headers, json={"password": "fresh-pass-1"}
    )
    assert (await login(client, user.email, "fresh-pass-1"))["Authorization"]


async def test_successful_login_resets_failure_count(client, make_user):
    user = await make_user("lecturer@example.com", Role.LECTURER)
    for _ in range(4):
        await client.post(
            "/api/v1/auth/login", data={"username": user.email, "password": "wrong-pass"}
        )
    await login(client, user.email)
    await client.post("/api/v1/auth/login", data={"username": user.email, "password": "nope"})
    assert await login(client, user.email)


async def test_change_own_password(client, lecturer_headers):
    url = "/api/v1/auth/change-password"
    wrong = await client.post(
        url,
        headers=lecturer_headers,
        json={"current_password": "not-it", "new_password": "brand-new-pass"},
    )
    assert wrong.status_code == 400

    ok = await client.post(
        url,
        headers=lecturer_headers,
        json={"current_password": PASSWORD, "new_password": "brand-new-pass"},
    )
    assert ok.status_code == 204
    assert await login(client, "lecturer@example.com", "brand-new-pass")
