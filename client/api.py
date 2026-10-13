"""Thin wrapper around the AttendEase REST API."""

import httpx

API_PREFIX = "/api/v1"


class ApiError(Exception):
    """A request failed; the message is safe to show to the user."""


class SessionExpired(ApiError):
    pass


def _clean(params: dict) -> dict:
    return {k: v for k, v in params.items() if v not in (None, "")}


def _error_message(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        # FastAPI validation errors: [{"loc": [...], "msg": "..."}]
        parts = []
        for err in detail:
            field = err.get("loc", [])[-1] if err.get("loc") else ""
            parts.append(f"{field}: {err.get('msg', '')}".strip(": "))
        return "\n".join(parts)
    return f"Server error ({response.status_code})"


class ApiClient:
    # Generous, because free hosting plans put an idle server to sleep and the first
    # request after that can take about a minute while it wakes up
    def __init__(self, base_url: str, timeout: float = 90.0):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url + API_PREFIX, timeout=timeout)
        self.user: dict | None = None

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.TimeoutException:
            raise ApiError(
                "The server took too long to respond. If it was asleep it should be awake "
                "now, so please try again."
            ) from None
        except httpx.HTTPError:
            raise ApiError(
                f"Cannot reach the server at {self.base_url}.\n"
                "Check your internet connection and the server address."
            ) from None
        if response.status_code == 401 and self.user is not None:
            raise SessionExpired("Your session has expired. Please log in again.")
        if response.is_error:
            raise ApiError(_error_message(response))
        return response

    def _get(self, path: str, **params):
        return self._request("GET", path, params=_clean(params)).json()

    def _post(self, path: str, payload: dict | None = None):
        response = self._request("POST", path, json=payload)
        return response.json() if response.content else None

    def _patch(self, path: str, payload: dict):
        return self._request("PATCH", path, json=payload).json()

    def _delete(self, path: str, **params):
        response = self._request("DELETE", path, params=params)
        return response.json() if response.content else None

    # Auth
    def login(self, email: str, password: str) -> dict:
        response = self._request(
            "POST", "/auth/login", data={"username": email, "password": password}
        )
        body = response.json()
        self._http.headers["Authorization"] = f"Bearer {body['access_token']}"
        self.user = body["user"]
        return self.user

    def change_password(self, current: str, new: str) -> None:
        self._post("/auth/change-password", {"current_password": current, "new_password": new})

    # Students
    def students(self, search: str = "", include_inactive: bool = False) -> list[dict]:
        return self._get(
            "/students", search=search, include_inactive=include_inactive or None, limit=1000
        )

    def create_student(self, name: str, department: str, student_id: str | None = None) -> dict:
        """Leave student_id out to have the server generate one."""
        payload = {"name": name, "department": department}
        if student_id:
            payload["student_id"] = student_id
        return self._post("/students", payload)

    def update_student(self, student_id: str, **changes) -> dict:
        return self._patch(f"/students/{student_id}", changes)

    def deactivate_student(self, student_id: str) -> None:
        self._delete(f"/students/{student_id}")

    # Courses
    def courses(self, include_inactive: bool = False) -> list[dict]:
        return self._get("/courses", include_inactive=include_inactive or None)

    def create_course(self, **fields) -> dict:
        return self._post("/courses", fields)

    def update_course(self, course_id: int, **changes) -> dict:
        return self._patch(f"/courses/{course_id}", changes)

    def deactivate_course(self, course_id: int) -> None:
        self._delete(f"/courses/{course_id}")

    def course_students(self, course_id: int) -> list[dict]:
        return self._get(f"/courses/{course_id}/students")

    def enroll(self, course_id: int, student_ids: list[str]) -> list[dict]:
        return self._post(f"/courses/{course_id}/students", {"student_ids": student_ids})

    def unenroll(self, course_id: int, student_id: str) -> None:
        self._delete(f"/courses/{course_id}/students/{student_id}")

    def register(self, course_id: int, date: str) -> list[dict]:
        return self._get(f"/courses/{course_id}/register", date=date)

    # Attendance
    def save_register(self, course_id: int, date: str, statuses: dict[str, str]) -> list[dict]:
        records = [{"student_id": s, "status": v} for s, v in statuses.items()]
        return self._post(
            "/attendance/register", {"course_id": course_id, "date": date, "records": records}
        )

    def attendance(self, **filters) -> list[dict]:
        return self._get("/attendance", limit=5000, **filters)

    def my_attendance(self, **filters) -> list[dict]:
        return self._get("/attendance/me", **filters)

    def update_attendance(self, record_id: int, status: str) -> dict:
        return self._patch(f"/attendance/{record_id}", {"status": status})

    def delete_attendance(self, ids: list[int]) -> int:
        return self._delete("/attendance", ids=ids)["deleted"]

    # Reports
    def summary(self, course_id: int | None = None) -> dict:
        return self._get("/reports/summary", course_id=course_id)

    def daily_counts(self, days: int = 14) -> list[dict]:
        return self._get("/reports/daily", days=days)

    def course_overview(self) -> list[dict]:
        return self._get("/reports/courses")

    def student_stats(self, **filters) -> list[dict]:
        return self._get("/reports/students", **filters)

    def export_excel(self, **filters) -> bytes:
        """The report as an .xlsx workbook."""
        return self._request("GET", "/reports/attendance.xlsx", params=_clean(filters)).content

    # Users
    def users(self) -> list[dict]:
        return self._get("/users")

    def create_user(self, **fields) -> dict:
        return self._post("/users", fields)

    def update_user(self, user_id: int, **changes) -> dict:
        return self._patch(f"/users/{user_id}", changes)

    # Terms
    def terms(self) -> list[dict]:
        return self._get("/terms")

    def create_term(self, name: str, start_date: str, end_date: str) -> dict:
        return self._post("/terms", {"name": name, "start_date": start_date, "end_date": end_date})

    def update_term(self, term_id: int, **changes) -> dict:
        return self._patch(f"/terms/{term_id}", changes)

    def delete_term(self, term_id: int) -> None:
        self._delete(f"/terms/{term_id}")

    # Audit
    def audit_logs(self, entity_type: str = "") -> list[dict]:
        return self._get("/audit-logs", entity_type=entity_type, limit=500)
