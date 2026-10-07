"""Daily AI brief: narrate the portfolio's current state (Phase 1).

Compiles fully computed numbers (snapshot, VaR/vol/drawdown, diversification,
issues) into a context block and asks the provider for a short plain-language
brief. Cached in Postgres (PgTTLCache) for a day, keyed by a stable sha256 of
the context, so it costs at most one model call per refresh.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.issues import detect_issues
from app.config import get_settings
from app.services.ai.providers import build_ai_provider
from app.services.analytics_service import latest_holding_views
from app.services.cache import get_shared_cache
from app.services.diversification_service import portfolio_diversification
from app.services.market import build_market_data_provider
from app.services.portfolio_risk_service import portfolio_risk
from app.services.risk import BaseRiskClient

logger = logging.getLogger("wealthpilot.ai")

_SYSTEM = (
    "You are Pilot, the owner's portfolio copilot. In first person, write a 4-6 sentence morning brief for the "
    "portfolio owner. When a Yesterday block is provided, LEAD with what changed "
    "since yesterday. Use ONLY the numbers provided — never invent figures. "
    "Plain language, specific, calm; mention the single most actionable item "
    "last. Amounts are INR. No headings, no bullet points, no disclaimers."
)


@dataclass(frozen=True)
class Brief:
    status: str  # "ok" | "unconfigured" | "empty"
    brief: str | None = None
    provider: str | None = None


async def _compile_context(db: AsyncSession, risk_client: BaseRiskClient) -> str | None:
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, cash = data
    total = sum(h.value for h in holdings) + cash
    pnl = sum(h.pnl for h in holdings)

    lines = [f"Total value ₹{total:,.0f}; cash ₹{cash:,.0f}; unrealized P&L ₹{pnl:,.0f}."]

    provider = build_market_data_provider()
    try:
        risk = await portfolio_risk(db, provider, risk_client)
        if risk:
            lines.append(
                f"1-day VaR(95%) ₹{risk.var:,.0f}; CVaR ₹{risk.cvar:,.0f}; "
                f"annualized vol {risk.annual_volatility * 100:.1f}%; "
                f"3-month max drawdown {risk.max_drawdown * 100:.1f}%."
            )
        div = await portfolio_diversification(db, provider, risk_client)
        if div:
            top = div.top_pairs[0] if div.top_pairs else None
            lines.append(
                f"Effective holdings {div.effective_holdings:.1f} of {div.holdings}; "
                f"diversification ratio {div.diversification_ratio:.2f}"
                + (
                    f"; most correlated pair {top.label_a}~{top.label_b} at {top.correlation:.2f}."
                    if top
                    else "."
                )
            )
    finally:
        await provider.close()

    # Yesterday's distilled note (if the learning loop has run) enables deltas.
    from datetime import timedelta

    from sqlalchemy import select

    from app.models.knowledge import KnowledgeChunk
    from app.services.analytics_service import today_ist

    ysrc = f"portfolio/daily-{(today_ist() - timedelta(days=1)).isoformat()}"
    yrow = (
        await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.source == ysrc))
    ).scalar_one_or_none()
    if yrow is not None:
        lines.append("Yesterday:\n" + yrow.content[:900])

    issues = detect_issues(holdings, cash)[:4]
    if issues:
        lines.append("Open issues: " + "; ".join(i.title for i in issues) + ".")
    return "\n".join(lines)


async def generate_brief(
    db: AsyncSession, risk_client: BaseRiskClient, refresh: bool = False
) -> Brief:
    context = await _compile_context(db, risk_client)
    if context is None:
        return Brief(status="empty")

    # Lead with Phase-7 watch alerts so the brief opens on what needs action.
    # (Also folds alert state into the cache key, so a new crossing refreshes it.)
    from app.services.ai.watch import evaluate_watch

    alerts = await evaluate_watch(db, risk_client)
    if alerts:
        context = (
            "Active alerts (open the brief on the action items, cite the numbers):\n"
            + "\n".join(f"- [{a.severity}] {a.text}" for a in alerts)
            + "\n\n"
            + context
        )

    provider = await build_ai_provider()
    if provider is None:
        return Brief(status="unconfigured")

    settings = get_settings()

    async def _factory() -> dict[str, str]:
        text = await provider.complete(_SYSTEM, context)
        return {"brief": text.strip(), "provider": provider.name}

    try:
        # Key on the context itself (stable hash — Python's hash() is
        # per-process randomized and silently missed across restarts).
        import hashlib

        key = f"ai:brief:{hashlib.sha256(context.encode()).hexdigest()[:16]}"
        if refresh:
            get_shared_cache().invalidate(key)
        cached = await get_shared_cache().get_or_set(
            key, float(settings.ai_brief_ttl_seconds), _factory
        )
        return Brief(status="ok", brief=cached["brief"], provider=cached["provider"])
    finally:
        close = getattr(provider, "close", None)
        if close is not None:
            await close()
