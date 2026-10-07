"""Response models for the curated market overview (indices & sectors)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class IndexQuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    instrument_token: int
    last_price: float
    change_pct: float


class MarketOverview(BaseModel):
    # True when served from the mock fixture (not real market quotes).
    is_fixture: bool
    indices: list[IndexQuoteRead]
