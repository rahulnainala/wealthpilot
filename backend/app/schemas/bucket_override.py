"""Request/response models for per-symbol bucket overrides CRUD."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domain.enums import Bucket


class BucketOverrideCreate(BaseModel):
    symbol: str
    bucket: Bucket  # validated against the Bucket enum


class BucketOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    bucket: str
