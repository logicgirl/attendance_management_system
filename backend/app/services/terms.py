import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Term


async def term_for_date(db: AsyncSession, day: dt.date) -> str:
    name = await db.scalar(
        select(Term.name).where(Term.start_date <= day, Term.end_date >= day).limit(1)
    )
    return name or settings.CURRENT_TERM
