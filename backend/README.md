# AttendEase API

REST backend for the AttendEase attendance management system.
Built with FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic and JWT authentication.

## Roles

| Action | Admin | Lecturer | Student |
|---|:-:|:-:|:-:|
| Manage user accounts, courses and terms | ✓ | | |
| View the audit log | ✓ | | |
| View / add / edit students | ✓ | ✓ | |
| Enroll students in a course | ✓ | own courses | |
| Mark / edit attendance | ✓ | own courses | |
| View reports, export to Excel | ✓ | own courses | |
| Deactivate students, delete attendance records | ✓ | | |
| View own attendance | | | ✓ |

## Local setup (Windows)

Run these from the `backend` folder.

1. Create the virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements-dev.txt
   ```
2. Create the database (enter your PostgreSQL password when asked):
   ```bash
   createdb -h localhost -p 5433 -U postgres attendease
   ```
3. Copy `.env.example` to `.env` and set `DATABASE_URL` (your PostgreSQL password), `SECRET_KEY`
   and `TIMEZONE`.
4. Create the tables:
   ```bash
   .venv\Scripts\alembic upgrade head
   ```
5. Create the first admin account (it asks for an email and password unless they are in `.env`):
   ```bash
   .venv\Scripts\python -m app.initial_data
   ```
6. (Optional) Import students and attendance from the old desktop app. Old records go into a
   course called `GENERAL`, and every imported student is enrolled in it:
   ```bash
   .venv\Scripts\python -m app.import_sqlite ..\attendance_system.db
   ```
7. Start the server:
   ```bash
   .venv\Scripts\uvicorn app.main:app --reload
   ```
   Interactive API docs: http://127.0.0.1:8000/docs. Click **Authorize** and log in with your
   admin email and password.

## Tests

```bash
.venv\Scripts\python -m pytest
```

By default the tests use a temporary SQLite database, so PostgreSQL does not need to be running.
To run them against PostgreSQL, point `TEST_DATABASE_URL` at an empty database. Its tables are
dropped and recreated for every test.

```bash
set TEST_DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@localhost:5433/attendease_test
.venv\Scripts\python -m pytest
```

## Main endpoints (prefix `/api/v1`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login` | Log in (form fields `username` = email, `password`); returns a JWT |
| GET | `/auth/me` | Current user |
| POST | `/auth/change-password` | Change your own password |
| GET, POST | `/users` | List / create users (admin) |
| PATCH | `/users/{id}` | Update role, active flag, or reset a password; a reset also unlocks the account (admin) |
| GET, POST | `/students` | List (with `search`, `department`) / register students (leave out `student_id` to have one generated, e.g. `CS-26-0001`) |
| GET, PATCH, DELETE | `/students/{student_id}` | View / edit / deactivate a student |
| GET, POST | `/courses` | List (lecturers see their own) / create courses (admin) |
| GET, PATCH, DELETE | `/courses/{id}` | View / edit / deactivate a course |
| GET, POST | `/courses/{id}/students` | List / enroll students |
| DELETE | `/courses/{id}/students/{student_id}` | Remove a student from a course |
| GET | `/courses/{id}/register?date=` | Enrolled students with their status for the day |
| POST | `/attendance/register` | Save a whole class register (creates or updates) |
| GET, POST | `/attendance` | List (filters: `search`, `student_id`, `course_id`, `status`, `term`, `date_from`, `date_to`) / mark one student |
| PATCH | `/attendance/{id}` | Change a record's status |
| DELETE | `/attendance?ids=1&ids=2` | Delete records (admin) |
| GET | `/attendance/me` | A student's own attendance |
| GET, POST | `/terms` | List / create academic terms (admin creates) |
| GET | `/terms/current` | The term covering today |
| PATCH, DELETE | `/terms/{id}` | Edit / delete a term (admin) |
| GET | `/reports/summary?course_id=` | Roster size and the day's attendance counts |
| GET | `/reports/students` | Attendance totals and rate per student (same filters as the list) |
| GET | `/reports/attendance.xlsx` | Excel workbook: matching records and a per-student summary (same filters as the list) |
| GET | `/audit-logs` | Who changed what, newest first (admin) |
| GET | `/health` | Health check (no prefix) |

## Rules the API enforces

- One record per student, per course, per day, backed by a database unique constraint.
- Student IDs are generated as department code, year and number (`CS-26-0001`): initials for
  multi-word departments, the first three letters otherwise, numbered per department and year.
- Students must be enrolled and active to be marked. Dates in the future are rejected.
- Lecturers only see and change data for the courses they teach.
- Five wrong passwords lock an account for 15 minutes (`MAX_FAILED_LOGINS`, `LOCKOUT_MINUTES`).
- Attendance is tagged with the term whose dates cover it; `CURRENT_TERM` is the fallback.
- Every change is written to the audit log in the same transaction as the change itself.

## Database migrations

After changing a model in `app/models`, generate and apply a migration:

```bash
.venv\Scripts\alembic revision --autogenerate -m "describe the change"
.venv\Scripts\alembic upgrade head
```

Migration `0002` moves attendance recorded before courses existed into a `GENERAL` course.

## Deployment

The `Dockerfile` applies migrations, creates the first admin if `FIRST_ADMIN_EMAIL` and
`FIRST_ADMIN_PASSWORD` are set, and then serves the app with Gunicorn and Uvicorn workers.
The `render.yaml` Blueprint in the repository root sets this up on Render. On other hosts, create
a PostgreSQL database and a web service from this folder, then set `DATABASE_URL`, `SECRET_KEY`
and `TIMEZONE` as environment variables. `postgres://` URLs from the host are converted to the
async driver automatically.
