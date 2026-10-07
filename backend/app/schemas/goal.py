"""Request/response models for goals CRUD."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class GoalBase(BaseModel):
    name: str
    start_date: date | None = None
    target_date: date | None = None
    checkpoint_date: date | None = None
    target_value: float | None = None
    monthly_contribution: float = 0.0
    assigned_isins: list[str] = Field(default_factory=list)
    assigned_buckets: list[str] = Field(default_factory=list)
    notes: str | None = None


class GoalCreate(GoalBase):
    key: str


class GoalUpdate(BaseModel):
    """Partial update — only provided fields are applied."""

    name: str | None = None
    start_date: date | None = None
    target_date: date | None = None
    checkpoint_date: date | None = None
    target_value: float | None = None
    monthly_contribution: float | None = None
    assigned_isins: list[str] | None = None
    assigned_buckets: list[str] | None = None
    notes: str | None = None


class GoalRead(GoalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
