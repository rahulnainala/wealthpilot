"""Phase 7 — proactive watch & alert engine.

Rule-based conditions evaluated over fully-computed portfolio state (holdings,
risk, diversification, cached goal sims). Emits typed Alerts that the learning
run stores as AiInsights so Pilot flags a crossing *before* the owner asks —
the core one being a legacy stock passing the +10% sell threshold (the
legacy exit plan — see app.domain.exit_plan). Every number comes from the
engine/DB; nothing is invented.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal import Goal, GoalSimulation
from app.services.analytics_service import latest_holding_views, load_goal_views
from app.services.diversification_service import portfolio_diversification
from app.services.market import build_market_data_provider
from app.services.portfolio_risk_service import portfolio_risk
from app.services.risk import BaseRiskClient

logger = logging.getLogger("wealthpilot.ai")

# Thresholds (single source of truth for the rules below).
SELL_THRESHOLD_PCT = 10.0      # the legacy sell plan's +10% trigger
NEAR_SELL_PCT = 8.0            # "approaching" band
CONCENTRATION_WEIGHT = 0.12    # single holding share that reads as concentrated
CORRELATION_LIMIT = 0.60       # correlated-pair ceiling
DRAWDOWN_LIMIT = -0.15         # 3-month max drawdown comfort band
GOAL_PROB_FLOOR = 0.50         # success odds below this = off track
_SEVERITY_RANK = {"action": 0, "watch": 1, "info": 2}
_MAX_ALERTS = 6


@dataclass(frozen=True)
class Alert:
    key: str       # stable identity, e.g. "sell:NMDC" — powers dismiss-until-cleared
    severity: str  # "action" | "watch" | "info"
    text: str      # one line, engine-cited numbers


async def _latest_goal_sims(db: AsyncSession) -> dict[int, GoalSimulation]:
    """Most recent cached simulation per goal (by row id)."""
    rows = (
        (await db.execute(select(GoalSimulation).order_by(GoalSimulation.id.desc())))
        .scalars()
        .all()
    )
    latest: dict[int, GoalSimulation] = {}
    for row in rows:
        latest.setdefault(row.goal_id, row)
    return latest


async def evaluate_watch(db: AsyncSession, risk_client: BaseRiskClient) -> list[Alert]:
    """Evaluate all watch rules; returns alerts sorted most-urgent first."""
    data = await latest_holding_views(db)
    if data is None:
        return []
    holdings, cash = data
    total = sum(h.value for h in holdings) + cash
    alerts: list[Alert] = []

    # 1) Sell-threshold crossings (the core plan signal) — stocks only.
    for h in holdings:
        if getattr(h.type, "value", h.type) != "stock":
            continue
        if h.pnl_pct >= SELL_THRESHOLD_PCT:
            alerts.append(Alert(
                f"sell:{h.symbol}", "action",
                f"{h.symbol} is +{h.pnl_pct:.1f}% — past the +10% sell threshold; "
                f"legacy sell-plan candidate.",
            ))
        elif h.pnl_pct >= NEAR_SELL_PCT:
            alerts.append(Alert(
                f"near:{h.symbol}", "watch",
                f"{h.symbol} is +{h.pnl_pct:.1f}%, approaching the +10% sell threshold.",
            ))

    # 2) Single-holding concentration (top offender only).
    if total > 0:
        heavy = max(holdings, key=lambda h: h.value, default=None)
        if heavy is not None and heavy.value / total >= CONCENTRATION_WEIGHT:
            # Tickers read fine for stocks; funds carry an ISIN symbol, so use the name.
            label = heavy.symbol if getattr(heavy.type, "value", heavy.type) == "stock" else (heavy.name or heavy.symbol)
            alerts.append(Alert(
                f"conc:{heavy.symbol}", "watch",
                f"{label[:32]} is {heavy.value / total * 100:.1f}% of the portfolio "
                f"— concentrated in one name.",
            ))

    # 3) Risk & diversification (market-data dependent).
    provider = build_market_data_provider()
    try:
        risk = await portfolio_risk(db, provider, risk_client)
        if risk and risk.max_drawdown <= DRAWDOWN_LIMIT:
            alerts.append(Alert(
                "drawdown", "watch",
                f"3-month max drawdown is {risk.max_drawdown * 100:.1f}% — beyond the "
                f"15% comfort band.",
            ))
        div = await portfolio_diversification(db, provider, risk_client)
        if div and div.top_pairs:
            top = div.top_pairs[0]
            if top.correlation >= CORRELATION_LIMIT:
                alerts.append(Alert(
                    f"corr:{top.label_a}~{top.label_b}", "watch",
                    f"{top.label_a} and {top.label_b} move together at "
                    f"{top.correlation:.2f} — less real diversification than it looks.",
                ))
    except Exception:  # noqa: BLE001 — market feed down shouldn't kill the run
        logger.info("watch: risk/diversification skipped (provider error)")
    finally:
        await provider.close()

    # 4) Goal off-track (worst single goal below the floor).
    sims = await _latest_goal_sims(db)
    if sims:
        goals: dict[int, Goal] = {g.id: g for g in await load_goal_views(db)}
        worst = min(sims.values(), key=lambda s: s.probability_of_success)
        if worst.probability_of_success < GOAL_PROB_FLOOR and worst.goal_id in goals:
            g = goals[worst.goal_id]
            alerts.append(Alert(
                f"goal:{g.id}", "action",
                f"{g.name} goal is at {worst.probability_of_success * 100:.0f}% success "
                f"odds on the current SIP — off track.",
            ))

    # 5) Statistical anomaly (unusual daily move vs this portfolio's own history).
    from app.services.ai.anomaly import detect_value_anomaly

    anomaly = await detect_value_anomaly(db)
    if anomaly:
        alerts.append(Alert("anomaly:value", "watch", anomaly))

    alerts.sort(key=lambda a: _SEVERITY_RANK.get(a.severity, 9))
    return alerts[:_MAX_ALERTS]
