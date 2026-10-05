import datetime as dt
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


def _jsonable(value: Any) -> Any:
    if isinstance(value, dt.date | dt.time | dt.datetime):
        return value.isoformat()
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def audit(
    db: AsyncSession,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: object = None,
    **details: Any,
) -> None:
    """Add an audit entry to the session; it is saved with the caller's commit."""
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=None if entity_id is None else str(entity_id),
            details=_jsonable(details) or None,
        )
    )
