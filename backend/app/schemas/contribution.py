"""Request/response models for contributions CRUD."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class ContributionCreate(BaseModel):
    bucket: str
    month: date
    amount: float


class ContributionRead(ContributionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
