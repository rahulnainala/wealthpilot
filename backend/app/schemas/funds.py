"""Response models for the per-fund views."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GoalRef(BaseModel):
    key: str
    name: str
    target_value: float | None = None


class FundRead(BaseModel):
    isin: str
    name: str
    category: str
    asset_class: str
    recommendation: str
    goal_tag: str | None = None
    units: float
    avg_nav: float
    nav: float
    invested: float
    value: float
    pnl: float
    assigned_goals: list[GoalRef] = []


class MFOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    isin: str
    fund: str
    transaction_type: str
    status: str
    quantity: float
    amount: float
    average_price: float
    order_timestamp: str | None = None
