import os

# Must be set before the app is imported
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["TIMEZONE"] = "UTC"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Course, Enrollment, Role, Student, User  # noqa: E402

PASSWORD = "password123"

# Set TEST_DATABASE_URL (postgresql+asyncpg://...) to run the suite against PostgreSQL.
# The database's tables are dropped and recreated for every test.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def sessionmaker(tmp_path):
    url = TEST_DATABASE_URL or f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(sessionmaker):
    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(sessionmaker):
    async def _make(email: str, role: Role, student_id: str | None = None) -> User:
        async with sessionmaker() as db:
            user = User(
                full_name=email.split("@")[0].title(),
                email=email,
                hashed_password=hash_password(PASSWORD),
                role=role,
                student_id=student_id,
            )
            db.add(user)
            await db.commit()
            return user

    return _make


@pytest.fixture
def make_student(sessionmaker):
    async def _make(student_id: str, name: str = "Ada Lovelace", department: str = "Science"):
        async with sessionmaker() as db:
            db.add(Student(student_id=student_id, name=name, department=department))
            await db.commit()

    return _make


@pytest.fixture
def make_course(sessionmaker):
    async def _make(
        code: str, lecturer_id: int | None = None, student_ids: tuple[str, ...] = ()
    ) -> int:
        async with sessionmaker() as db:
            course = Course(code=code, title=f"{code} Course", department="Science")
            course.lecturer_id = lecturer_id
            db.add(course)
            await db.flush()
            db.add_all(Enrollment(course_id=course.id, student_id=s) for s in student_ids)
            await db.commit()
            return course.id

    return _make


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    res = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
async def admin(make_user):
    return await make_user("admin@example.com", Role.ADMIN)


@pytest.fixture
async def lecturer(make_user):
    return await make_user("lecturer@example.com", Role.LECTURER)


@pytest.fixture
async def admin_headers(client, admin):
    return await login(client, admin.email)


@pytest.fixture
async def lecturer_headers(client, lecturer):
    return await login(client, lecturer.email)
