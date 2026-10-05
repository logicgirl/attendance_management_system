"""Create the first admin account.

Usage: python -m app.initial_data
Reads FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD from .env, or prompts for them.
With --if-configured it does nothing unless both are set (used when the server starts).
"""

import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models import Role, User


async def create_first_admin(email: str, password: str, full_name: str) -> None:
    try:
        async with SessionLocal() as db:
            if await db.scalar(select(User).where(User.role == Role.ADMIN)):
                print("An admin account already exists; nothing to do.")
                return
            db.add(
                User(
                    full_name=full_name,
                    email=email.strip().lower(),
                    hashed_password=hash_password(password),
                    role=Role.ADMIN,
                )
            )
            await db.commit()
            print(f"Created admin account {email}")
    finally:
        await engine.dispose()


def main() -> None:
    # Servers run this on every start; without the settings there is nobody to ask
    if "--if-configured" in sys.argv and not (
        settings.FIRST_ADMIN_EMAIL and settings.FIRST_ADMIN_PASSWORD
    ):
        return
    email = settings.FIRST_ADMIN_EMAIL or input("Admin email: ")
    password = settings.FIRST_ADMIN_PASSWORD or getpass.getpass("Admin password (min 8 chars): ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")
    asyncio.run(create_first_admin(email, password, settings.FIRST_ADMIN_NAME))


if __name__ == "__main__":
    main()
