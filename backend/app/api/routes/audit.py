from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import AdminUser, SessionDep
from app.models import AuditLog
from app.schemas.audit import AuditLogRead

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(
    db: SessionDep,
    _: AdminUser,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: int | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
):
    """Most recent changes first."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    return (await db.scalars(stmt.offset(offset).limit(limit))).all()
