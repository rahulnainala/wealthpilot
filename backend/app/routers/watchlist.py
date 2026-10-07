"""Phase 50 — watchlist (live quotes) + a gap-based screener."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete as sql_delete
from sqlalchemy import select

from app.dependencies import DbSession
from app.models.watchlist import WatchlistItem
from app.services.market import build_market_data_provider

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class SymbolIn(BaseModel):
    symbol: str


class WatchRead(BaseModel):
    id: int
    symbol: str
    last_price: float | None = None
    change_pct: float | None = None


@router.get("", response_model=list[WatchRead])
async def list_watch(db: DbSession) -> list[WatchRead]:
    items = (await db.execute(select(WatchlistItem).order_by(WatchlistItem.id))).scalars().all()
    symbols = [i.symbol for i in items]
    quotes: dict[str, object] = {}
    if symbols:
        provider = build_market_data_provider()
        try:
            for q in await provider.get_quotes(symbols):
                quotes[q.symbol] = q
        finally:
            await provider.close()
    return [
        WatchRead(
            id=i.id,
            symbol=i.symbol,
            last_price=getattr(quotes.get(i.symbol), "last_price", None),
            change_pct=getattr(quotes.get(i.symbol), "change_pct", None),
        )
        for i in items
    ]


@router.get("/screener")
async def screener(db: DbSession) -> dict:
    """Gap-based ideas from the portfolio's own imbalances (no external universe)."""
    from app.services.ai.xray import portfolio_xray

    x = await portfolio_xray(db)
    ideas: list[str] = []
    if x and x["classes"]:
        by_weight = sorted(x["classes"], key=lambda c: c["weight"])
        low = by_weight[0]
        ideas.append(
            f"Thin on {low['asset_class']} — only {low['weight'] * 100:.0f}% of the book; "
            f"a candidate to add on the next SIP."
        )
        top = by_weight[-1]
        if top["weight"] > 0.4:
            ideas.append(
                f"{top['asset_class']} is {top['weight'] * 100:.0f}% — screen for names in "
                f"under-represented classes to rebalance into."
            )
    return {"ideas": ideas or ["Add holdings to get gap-based ideas."]}


@router.post("", response_model=WatchRead)
async def add_watch(payload: SymbolIn, db: DbSession) -> WatchRead:
    sym = payload.symbol.strip().upper()[:64]
    existing = (
        await db.execute(select(WatchlistItem).where(WatchlistItem.symbol == sym))
    ).scalar_one_or_none()
    if existing is None:
        existing = WatchlistItem(symbol=sym)
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
    return WatchRead(id=existing.id, symbol=existing.symbol)


@router.delete("/{item_id}")
async def delete_watch(item_id: int, db: DbSession) -> dict[str, str]:
    res = await db.execute(sql_delete(WatchlistItem).where(WatchlistItem.id == item_id))
    await db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="not_found")
    return {"status": "deleted"}
