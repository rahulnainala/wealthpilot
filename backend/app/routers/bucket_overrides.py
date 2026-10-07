"""Bucket-override CRUD endpoints (force a symbol into a bucket)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DbSession
from app.models.bucket_override import InstrumentBucketOverride
from app.schemas.bucket_override import BucketOverrideCreate, BucketOverrideRead

router = APIRouter(prefix="/api/bucket-overrides", tags=["bucket-overrides"])


@router.get("", response_model=list[BucketOverrideRead])
async def list_overrides(db: DbSession) -> list[InstrumentBucketOverride]:
    result = await db.execute(
        select(InstrumentBucketOverride).order_by(InstrumentBucketOverride.symbol)
    )
    return list(result.scalars().all())


@router.post("", response_model=BucketOverrideRead, status_code=201)
async def upsert_override(
    payload: BucketOverrideCreate, db: DbSession
) -> InstrumentBucketOverride:
    """Create or update the bucket override for a symbol (normalized upper-case)."""
    symbol = payload.symbol.strip().upper()
    existing = await db.execute(
        select(InstrumentBucketOverride).where(
            InstrumentBucketOverride.symbol == symbol
        )
    )
    override = existing.scalar_one_or_none()
    if override is None:
        override = InstrumentBucketOverride(symbol=symbol, bucket=payload.bucket.value)
        db.add(override)
    else:
        override.bucket = payload.bucket.value
    await db.commit()
    await db.refresh(override)
    return override


@router.delete("/{override_id}", status_code=204)
async def delete_override(override_id: int, db: DbSession) -> None:
    override = await db.get(InstrumentBucketOverride, override_id)
    if override is None:
        raise HTTPException(status_code=404, detail="Override not found.")
    await db.delete(override)
    await db.commit()
