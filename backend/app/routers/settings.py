"""Settings key/value endpoints (editable assumptions, expense ratios)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DbSession
from app.models.settings import Setting
from app.schemas.settings import SettingRead, SettingWrite

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=list[SettingRead])
async def list_settings(db: DbSession) -> list[Setting]:
    result = await db.execute(select(Setting).order_by(Setting.key))
    return list(result.scalars().all())


@router.get("/{key}", response_model=SettingRead)
async def get_setting(key: str, db: DbSession) -> Setting:
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found.")
    return setting


@router.put("/{key}", response_model=SettingRead)
async def put_setting(key: str, payload: SettingWrite, db: DbSession) -> Setting:
    """Create or replace a setting value."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = Setting(key=key, value=payload.value)
        db.add(setting)
    else:
        setting.value = payload.value
    await db.commit()
    await db.refresh(setting)
    return setting
