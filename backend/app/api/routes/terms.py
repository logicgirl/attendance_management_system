from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.models import Term
from app.schemas.term import TermCreate, TermRead, TermUpdate
from app.services.attendance import now_local
from app.services.audit import audit

router = APIRouter(prefix="/terms", tags=["terms"])


async def check_no_clash(db: SessionDep, term: Term) -> None:
    if term.end_date < term.start_date:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "end_date must be on or after start_date"
        )
    clash = await db.scalar(
        select(Term).where(
            Term.id != term.id,
            (Term.name == term.name)
            | ((Term.start_date <= term.end_date) & (Term.end_date >= term.start_date)),
        )
    )
    if clash is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Clashes with term '{clash.name}' (same name or dates)"
        )


@router.get("", response_model=list[TermRead])
async def list_terms(db: SessionDep, _: CurrentUser):
    return (await db.scalars(select(Term).order_by(Term.start_date))).all()


@router.get("/current", response_model=TermRead | None)
async def current_term(db: SessionDep, _: CurrentUser):
    today = now_local().date()
    return await db.scalar(select(Term).where(Term.start_date <= today, Term.end_date >= today))


@router.post("", response_model=TermRead, status_code=status.HTTP_201_CREATED)
async def create_term(db: SessionDep, admin: AdminUser, payload: TermCreate):
    term = Term(**payload.model_dump())
    await check_no_clash(db, term)
    db.add(term)
    await db.flush()
    audit(db, admin, "term.create", "term", term.id, **payload.model_dump())
    await db.commit()
    return term


@router.patch("/{term_id}", response_model=TermRead)
async def update_term(db: SessionDep, admin: AdminUser, term_id: int, payload: TermUpdate):
    term = await db.get(Term, term_id)
    if term is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Term not found")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(term, field, value)
    # Keep the proposed values out of the database until they are validated
    with db.no_autoflush:
        await check_no_clash(db, term)
    audit(db, admin, "term.update", "term", term.id, **changes)
    await db.commit()
    return term


@router.delete("/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_term(db: SessionDep, admin: AdminUser, term_id: int):
    """Existing attendance keeps the term name it was recorded with."""
    term = await db.get(Term, term_id)
    if term is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Term not found")
    audit(db, admin, "term.delete", "term", term.id, name=term.name)
    await db.delete(term)
    await db.commit()
