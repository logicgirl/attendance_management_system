# AttendEase — Student Attendance Management System

AttendEase replaces paper attendance registers with a secure, central digital record.
Lecturers take a class register for each course in a few clicks. Administrators manage
students, courses, staff accounts and academic terms. Students can check their own attendance
history. Reports can be viewed on screen or exported to Excel.

The system has two parts:

- **Desktop client** (`attendease_client.py`, `client/`): a Windows app built with Tkinter,
  with a custom dark theme (rounded components drawn at start-up), sidebar navigation,
  a dashboard with an attendance chart, pop-up date pickers and toast notifications.
- **REST API** (`backend/`): FastAPI and PostgreSQL. It holds all data and enforces every rule.

![Dashboard](docs/screenshots/dashboard.png)

## Features

- **Secure sign-in:** JWT authentication, bcrypt password hashing, and an account lockout after
  5 failed attempts. Users can change their own password.
- **Role-based access:**

  | | Admin | Lecturer | Student |
  |---|:-:|:-:|:-:|
  | Manage users, courses and terms; view the audit log | ✓ | | |
  | Register and edit students | ✓ | ✓ | |
  | Enroll students in courses | ✓ | own courses | |
  | Take registers, correct records | ✓ | own courses | |
  | Reports and Excel export | ✓ | own courses | |
  | Delete records, deactivate students | ✓ | | |
  | View own attendance | | | ✓ |

- **Automatic student IDs:** each new student gets an ID made from their department, the
  year and a number, such as `CS-26-0001`.
- **Class registers:** attendance is taken per course, per day. Mark students Present, Late or
  Absent, one at a time or in bulk (keys P, L, A), then save the whole register at once.
- **Data integrity:** a student can only be marked once per course per day, only when enrolled,
  and never for a future date. The database enforces this as well as the API.
- **Academic terms:** records are tagged automatically with the term their date falls in.
- **Dashboard:** today's attendance, registers still to take, a 14-day attendance-rate chart,
  and the students who need attention.
- **Reports:** attendance rate per student (below 75% is highlighted), filtered record
  history, and export to a formatted Excel workbook (records plus a per-student summary).
- **Audit log:** every change records who made it, what changed and when.
- **History is preserved:** students and courses are deactivated rather than deleted.

## Technology

**Frontend:** Python Tkinter (ttk), httpx, PyInstaller, Inno Setup

**Backend:** Python 3.12, FastAPI, Uvicorn, Gunicorn, SQLAlchemy 2.0 (async), asyncpg, Alembic,
Pydantic v2, pydantic-settings, PyJWT, passlib[bcrypt], openpyxl (Excel reports), OpenAPI/Swagger UI

**Database:** PostgreSQL 16+

**Quality and deployment:** pytest (tests run on SQLite and on PostgreSQL), Ruff, GitHub
Actions, Docker, Render

## Architecture

```mermaid
flowchart LR
    subgraph PC["Staff and student PCs"]
        C["AttendEase.exe<br/>(Tkinter)"]
    end
    subgraph Cloud["Cloud host (Render)"]
        A["FastAPI app<br/>Gunicorn + Uvicorn"]
        D[("PostgreSQL")]
    end
    C -- "HTTPS + JSON<br/>JWT bearer token" --> A
    A -- "SQLAlchemy async<br/>(asyncpg)" --> D
```

## Database design

```mermaid
erDiagram
    USERS ||--o{ COURSES : teaches
    USERS |o--o| STUDENTS : "student login"
    USERS ||--o{ ATTENDANCE : "recorded by"
    USERS ||--o{ AUDIT_LOGS : "made change"
    STUDENTS ||--o{ ENROLLMENTS : ""
    COURSES ||--o{ ENROLLMENTS : ""
    STUDENTS ||--o{ ATTENDANCE : ""
    COURSES ||--o{ ATTENDANCE : ""

    USERS {
        int id PK
        string full_name
        string email UK
        string hashed_password
        string role "admin | lecturer | student"
        bool is_active
        string student_id FK "nullable, unique"
        int failed_login_attempts
        timestamp locked_until
    }
    STUDENTS {
        string student_id PK
        string name
        string department
        bool is_active
    }
    COURSES {
        int id PK
        string code UK
        string title
        string department
        int lecturer_id FK
        bool is_active
    }
    ENROLLMENTS {
        int course_id PK, FK
        string student_id PK, FK
    }
    ATTENDANCE {
        int id PK
        string student_id FK
        int course_id FK
        date date
        time time
        string status "Present | Late | Absent"
        string term
        int recorded_by FK
    }
    TERMS {
        int id PK
        string name UK
        date start_date
        date end_date
    }
    AUDIT_LOGS {
        int id PK
        int user_id FK
        string action
        string entity_type
        string entity_id
        json details
        timestamp created_at
    }
```

`ATTENDANCE` has a unique constraint on `(student_id, course_id, date)`.

## How to run the app

AttendEase has two parts that run at the same time: the **server** (backend) and the
**desktop app**. You use two terminal windows, one for each.

### What you need

- Windows 10 or 11
- [Python 3.12](https://www.python.org/downloads/) (tick "Add Python to PATH" when installing)
- [PostgreSQL 16 or newer](https://www.postgresql.org/download/windows/) (remember the password
  you set for the `postgres` user, and the port, which is usually `5432`)

### First-time setup (once)

Open a terminal in the project folder, then go into `backend`:

```bash
cd backend
```

1. **Install the server's dependencies:**
   ```bash
   python -m venv .venv
   ```
   ```bash
   .venv\Scripts\python -m pip install -r requirements-dev.txt
   ```

2. **Create the database.** It asks for your PostgreSQL password. Use your own port if it
   isn't 5432.
   ```bash
   createdb -h localhost -p 5432 -U postgres attendease
   ```
   If Windows says `createdb` is not recognised, use the full path, e.g.
   `"C:\Program Files\PostgreSQL\16\bin\createdb.exe"`.

3. **Create your settings file.** Copy `backend/.env.example` to `backend/.env` and open it:
   - `DATABASE_URL`: put your PostgreSQL password in place of `CHANGE_ME`, and fix the port
     if needed.
   - `SECRET_KEY`: paste a random value. You can generate one with:
     ```bash
     .venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"
     ```
   - `TIMEZONE`: a region name such as `Africa/Lagos` or `Europe/London` (not `UTC+1`).
   - `FIRST_ADMIN_EMAIL` and `FIRST_ADMIN_PASSWORD`: the admin account to create (password at
     least 8 characters).

4. **Create the tables:**
   ```bash
   .venv\Scripts\alembic upgrade head
   ```

5. **Create the admin account:**
   ```bash
   .venv\Scripts\python -m app.initial_data
   ```

6. **Install the desktop app's dependencies.** Open a second terminal in the main project
   folder (not `backend`):
   ```bash
   python -m venv .venv
   ```
   ```bash
   .venv\Scripts\python -m pip install -r requirements.txt
   ```

### Every time you use it

**Terminal 1: start the server** (in the `backend` folder)

```bash
.venv\Scripts\uvicorn app.main:app --reload
```

Wait for `Application startup complete`, and leave this window open. The server is now at
http://127.0.0.1:8000. Its interactive API documentation is at http://127.0.0.1:8000/docs.

**Terminal 2: start the desktop app** (in the main project folder)

```bash
.venv\Scripts\python attendease_client.py
```

Or double-click `dist\AttendEase.exe` if you have built it (see below).

To stop, close the app window, then press `Ctrl+C` in the server's terminal.

### Your first session

1. **Sign in** with the admin email and password from `backend/.env`.
2. **Users:** create a lecturer account.
3. **Students:** register some students (only name and department are needed; IDs are generated).
4. **Courses:** create a course, assign the lecturer, then **Enroll students**.
5. **Academic Terms:** add the current term's dates.
6. Sign out and sign in as the lecturer. **Take Attendance:** pick the course, mark each student
   (keys P, L, A, or the buttons), and click **Save register** (or press Ctrl+S).
7. Explore **Dashboard**, **Records & Reports** (filters, Student report, Export to Excel), and as
   admin, **Audit Log**.

The app connects to `http://127.0.0.1:8000` by default. To use a server elsewhere (for example
the deployed one), click **Server settings** on the sign-in screen. The address is remembered.

### If something goes wrong

| What you see | What to do |
|---|---|
| "Cannot reach the server" in the app | The server (Terminal 1) isn't running, or the address in Server settings is wrong. |
| `password authentication failed` | The password in `DATABASE_URL` in `backend/.env` is wrong. |
| `database "attendease" does not exist` | Run the `createdb` step. |
| An error mentioning `TIMEZONE` | Use a region name such as `Africa/Lagos`, not `UTC+1`. |
| `SECRET_KEY` field required | Run server commands from inside the `backend` folder, where `.env` is. |
| "Too many failed attempts" | The account is locked for 15 minutes. An admin can reset its password to unlock it. |
| `'python' is not recognized` | Reinstall Python with "Add Python to PATH" ticked. |
| Scripts are blocked in PowerShell | Use the commands exactly as shown (`.venv\Scripts\...`); activating the venv isn't needed. |

### Build the Windows program and installer

```bash
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\pyinstaller --noconfirm attendease_client.spec
```

This produces `dist\AttendEase.exe`. To make an installer, copy `config.json.example` to
`config.json`, set your server's address, and compile `installer.iss` with
[Inno Setup 6](https://jrsoftware.org/isinfo.php).

### Deploy the backend online

The repository includes a Render Blueprint (`render.yaml`). In the Render dashboard choose
**New → Blueprint** and select this repository. Render creates the database and the API, and
asks for `TIMEZONE` (for example `Africa/Lagos`), `FIRST_ADMIN_EMAIL` and
`FIRST_ADMIN_PASSWORD`. On start-up the server applies migrations and creates that admin account.
Put the resulting `https://….onrender.com` address in `config.json` before building the installer.

### Moving data from the old version

The first version stored data in a local SQLite file. To copy it into PostgreSQL:

```bash
cd backend
.venv\Scripts\python -m app.import_sqlite ..\attendance_system.db
```

The old version had no courses, so its records go into a course called `GENERAL`.

## Tests

```bash
cd backend
.venv\Scripts\python -m pytest
```

GitHub Actions (`.github/workflows/backend.yml`) runs lint, a migration round-trip check, and the
full test suite against PostgreSQL on every push.

## Screenshots

| | |
|---|---|
| ![Sign in](docs/screenshots/login.png) | ![Taking a class register](docs/screenshots/register.png) |
| ![Records and reports](docs/screenshots/records.png) | ![Attendance by student](docs/screenshots/student_report.png) |
| ![Courses and enrolment](docs/screenshots/courses.png) | ![Audit log](docs/screenshots/audit.png) |
| ![A student's own view](docs/screenshots/student.png) | |
