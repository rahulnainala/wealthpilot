"""Contributions CRUD endpoints (manual monthly entries per bucket)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DbSession
from app.models.contribution import Contribution
from app.schemas.contribution import ContributionCreate, ContributionRead

router = APIRouter(prefix="/api/contributions", tags=["contributions"])


@router.get("", response_model=list[ContributionRead])
async def list_contributions(db: DbSession) -> list[Contribution]:
    result = await db.execute(
        select(Contribution).order_by(Contribution.month, Contribution.bucket)
    )
    return list(result.scalars().all())


@router.post("", response_model=ContributionRead, status_code=201)
async def upsert_contribution(
    payload: ContributionCreate, db: DbSession
) -> Contribution:
    """Create or update the amount for a (bucket, month) pair."""
    month = payload.month.replace(day=1)  # normalize to first of month
    existing = await db.execute(
        select(Contribution).where(
            Contribution.bucket == payload.bucket, Contribution.month == month
        )
    )
    contribution = existing.scalar_one_or_none()
    if contribution is None:
        contribution = Contribution(
            bucket=payload.bucket, month=month, amount=payload.amount
        )
        db.add(contribution)
    else:
        contribution.amount = payload.amount
    await db.commit()
    await db.refresh(contribution)
    return contribution


@router.delete("/{contribution_id}", status_code=204)
async def delete_contribution(contribution_id: int, db: DbSession) -> None:
    contribution = await db.get(Contribution, contribution_id)
    if contribution is None:
        raise HTTPException(status_code=404, detail="Contribution not found.")
    await db.delete(contribution)
    await db.commit()
