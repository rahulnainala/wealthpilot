"""Response models for the target-allocation basket (SIP-routing model)."""

from __future__ import annotations

from pydantic import BaseModel


class BasketPosition(BaseModel):
    label: str
    symbol: str | None = None
    current_value: float
    sip_pct: float  # share of the bucket's monthly SIP routed here
    sip_monthly: float  # ₹/mo routed here
    mode: str  # core | planned | hold | bonus
    note: str


class BasketSleeve(BaseModel):
    goal_key: str
    goal_name: str
    role: str
    target_value: float | None
    current_value: float
    monthly_contribution: float
    portfolio_pct: float
    positions: list[BasketPosition]


class MonthlySplit(BaseModel):
    goal_name: str
    monthly: float
    pct: float


class LegacyHolding(BaseModel):
    symbol: str
    name: str
    current_value: float
    note: str


class BasketRead(BaseModel):
    total_value: float
    monthly_total: float
    monthly_split: list[MonthlySplit]
    sleeves: list[BasketSleeve]
    legacy: list[LegacyHolding]
