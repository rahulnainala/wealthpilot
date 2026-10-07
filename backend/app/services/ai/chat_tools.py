"""Tool handlers for Ask WealthPilot (Phase 2): one function per named tool,
dispatched from chat_service.chat via `run_tool`. Split out of chat_service.py
so that file stays under the cohesion guideline — this module is the tool
surface, chat_service.py is the conversation loop.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.issues import detect_issues
from app.services.ai.rag import hybrid_retrieve, retrieve_daily_notes
from app.services.analytics_service import latest_holding_views
from app.services.diversification_service import portfolio_diversification
from app.services.market import build_market_data_provider
from app.services.portfolio_risk_service import portfolio_risk
from app.services.risk import BaseRiskClient


async def _tool_get_portfolio(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    data = await latest_holding_views(db)
    if data is None:
        return "No snapshot yet."
    holdings, cash = data
    rows = [
        f"{h.symbol} ({h.type.value}, {h.bucket.value}): value ₹{h.value:,.0f}, P&L ₹{h.pnl:,.0f}"
        for h in holdings
    ]
    total = sum(h.value for h in holdings) + cash
    return f"Total ₹{total:,.0f}; cash ₹{cash:,.0f}\n" + "\n".join(rows)


async def _tool_get_risk(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    provider = build_market_data_provider()
    try:
        r = await portfolio_risk(db, provider, risk_client)
        if r is None:
            return "No snapshot yet."
        contribs = "; ".join(
            f"{c.bucket} ₹{c.contribution:,.0f}" for c in r.contributions
        )
        return (
            f"1-day VaR(95%) ₹{r.var:,.0f}; CVaR ₹{r.cvar:,.0f}; annualized vol "
            f"{r.annual_volatility * 100:.1f}%; max drawdown {r.max_drawdown * 100:.1f}%; "
            f"contributions: {contribs}"
        )
    finally:
        await provider.close()


async def _tool_get_diversification(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    provider = build_market_data_provider()
    try:
        d = await portfolio_diversification(db, provider, risk_client)
        if d is None:
            return "Need at least 2 holdings."
        pairs = "; ".join(
            f"{p.label_a}~{p.label_b} {p.correlation:.2f}" for p in d.top_pairs
        )
        return (
            f"Effective holdings {d.effective_holdings:.1f}/{d.holdings}; ratio "
            f"{d.diversification_ratio:.2f}; avg corr {d.average_correlation:.2f}; top pairs: {pairs}"
        )
    finally:
        await provider.close()


async def _tool_get_issues(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    data = await latest_holding_views(db)
    if data is None:
        return "No snapshot yet."
    holdings, cash = data
    return (
        "\n".join(
            f"[{i.severity.value}] {i.title}: {i.message}"
            for i in detect_issues(holdings, cash)[:8]
        )
        or "No issues."
    )


async def _tool_list_goals(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.analytics_service import load_goal_views

    goals = await load_goal_views(db)
    return "\n".join(
        f"{g.key} — {g.name}: target ₹{g.target_value:,.0f} by {g.target_date}, SIP ₹{g.monthly_contribution:,.0f}/mo"
        for g in goals
        if g.target_value is not None
    ) or "No goals defined."


async def _tool_simulate_goal(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from dataclasses import replace as dc_replace

    from app.services.analytics_service import load_goal_views, today_ist
    from app.services.goal_simulation import SimulationOverrides, build_goal_sim_inputs

    data = await latest_holding_views(db)
    if data is None:
        return "No snapshot yet."
    holdings, _cash = data
    wanted = str(args.get("goal", "")).strip().lower()
    goals = await load_goal_views(db)
    goal = next(
        (g for g in goals if g.key.lower() == wanted or wanted in g.name.lower()),
        None,
    )
    if goal is None:
        return f"Unknown goal '{wanted}'. Known: {', '.join(g.key for g in goals)}"
    overrides = SimulationOverrides(
        monthly_contribution=args.get("monthly_contribution"),
        target_value=args.get("target_value"),
        num_paths=5000,
    )
    inputs = build_goal_sim_inputs(goal, holdings, today_ist(), 5000, overrides)
    if inputs is None:
        return "Goal has no target/date to simulate."
    shock = args.get("shock_pct")
    if shock:
        inputs = dc_replace(inputs, initial_shock=-abs(float(shock)) / 100.0)
    out = await risk_client.simulate_goal(inputs)
    return (
        f"{goal.name}: P(success) {out.probability_of_success * 100:.0f}%; median ending "
        f"₹{out.median_ending_value:,.0f}; p10 ₹{out.p10_value:,.0f}; p90 ₹{out.p90_value:,.0f} "
        f"(months={inputs.months_remaining}, SIP ₹{inputs.monthly_contribution:,.0f}/mo"
        + (f", shock -{abs(float(shock)):.0f}%" if shock else "")
        + ")"
    )


async def _tool_required_sip(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.analytics_service import load_goal_views, today_ist
    from app.services.goal_simulation import solve_required_contribution

    data = await latest_holding_views(db)
    if data is None:
        return "No snapshot yet."
    holdings, _cash = data
    wanted = str(args.get("goal", "")).strip().lower()
    goals = await load_goal_views(db)
    goal = next(
        (g for g in goals if g.key.lower() == wanted or wanted in g.name.lower()), None
    )
    if goal is None:
        return f"Unknown goal '{wanted}'. Known: {', '.join(g.key for g in goals)}"
    target = float(args.get("target_probability") or 0.75)
    res = await solve_required_contribution(
        goal, holdings, risk_client, today_ist(), 5000, target_probability=target
    )
    if res is None:
        return "Goal has no target/date to solve."
    if not res.reachable:
        return (
            f"{goal.name}: even ₹{res.required_monthly_contribution:,.0f}/mo only reaches "
            f"{res.probability_of_success * 100:.0f}% (< {target * 100:.0f}% target) — "
            f"the target/date may be unrealistic."
        )
    return (
        f"{goal.name}: ₹{res.required_monthly_contribution:,.0f}/mo reaches the "
        f"{target * 100:.0f}% success target."
    )


async def _tool_search_knowledge(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    hits = await hybrid_retrieve(db, str(args.get("query", "")), k=3)
    if not hits:
        return "No knowledge matches found."
    return "\n---\n".join(f"[{h.source} — {h.title}] {h.content[:800]}" for h in hits)


async def _tool_find_similar_days(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    q = str(args.get("query") or "").strip() or "current portfolio risk and allocation"
    hits = await retrieve_daily_notes(db, q, k=3)
    if not hits:
        return "No dated portfolio history yet — daily notes accumulate via the nightly learning run."
    return "\n---\n".join(
        f"[{h.source.removeprefix('portfolio/')}] {h.content[:600]}" for h in hits
    )


async def _tool_get_news(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.news import get_headlines
    from app.services.ai.sentiment import mood

    heads = await get_headlines(str(args.get("query", "")), k=5)
    if not heads:
        return "No recent headlines found (or the news feed is unreachable)."
    label, avg = mood([h.sentiment for h in heads])
    lines = "\n".join(f"- {h.title} ({h.source}, {h.published})" for h in heads)
    return f"Overall news mood: {label} ({avg:+.2f}).\n{lines}"


async def _tool_optimize_portfolio(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.optimize import optimize_portfolio

    r = await optimize_portfolio(db)
    if r is None:
        return "Need at least two asset classes to optimize."
    moves = "; ".join(
        f"{x['asset_class']} {x['delta_weight'] * 100:+.0f}% (₹{x['delta_amount']:,.0f})"
        for x in r.rebalance
    )
    return (
        f"Risk-parity ({r.method}) target vs current — estimated volatility "
        f"{r.current_vol_est}% → {r.target_vol_est}%. Rebalance: {moves}."
    )


async def _tool_draft_sell_order(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.order_draft import draft_sell_order

    d = await draft_sell_order(db, str(args.get("symbol", "")))
    if d is None:
        return "That stock isn't in the latest snapshot, so there's nothing to draft."
    routes = "; ".join(f"{r['label']} ₹{r['amount']:,.0f}" for r in d.routing)
    return (
        f"DRAFT (review & place yourself): {d.side} {d.quantity:g} {d.symbol} "
        f"@ trigger ₹{d.trigger_price:,.2f}; est. proceeds ₹{d.est_proceeds:,.0f} "
        f"(gain ₹{d.gain:,.0f}, est. LTCG tax ₹{d.est_ltcg_tax:,.0f}) → {routes}. {d.note}"
    )


async def _tool_earnings_calendar(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.earnings import earnings_calendar

    rows = await earnings_calendar(db)
    if not rows:
        return "No upcoming earnings dates found (feed unavailable)."
    return "Upcoming earnings: " + "; ".join(f"{r['symbol']} {r['earnings_date']}" for r in rows)


async def _tool_hedge(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.options import hedge_analysis

    h = await hedge_analysis(db)
    if h is None:
        return "No snapshot yet."
    return h.get("note", "No equity-like exposure to hedge.")


async def _tool_forecast(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.forecast import forecast_signals

    f = await forecast_signals(db)
    if f is None:
        return "Not enough history to forecast yet."
    return (
        f"Forecast (EWMA) volatility ~{f.forecast_vol_annual_pct}% annualized; "
        f"10-day momentum {f.momentum_10d_pct:+.1f}% ({f.trend}). A volatility "
        f"estimate over {f.days} days, not a price call."
    )


async def _tool_macro(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.macro import macro_dashboard

    m = await macro_dashboard(db)
    if not m["indicators"]:
        return "Macro feed unreachable right now."
    line = "; ".join(f"{i['name']} {i['price']:,.2f} ({i['change_pct']:+.1f}%)" for i in m["indicators"])
    return f"{line}. {m['note']}"


async def _tool_recall_decisions(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.decisions import list_decisions

    rows = await list_decisions(db, limit=8)
    if not rows:
        return "No decisions logged yet."
    return "\n".join(
        f"{d.created_at.date()}: {d.action} {d.symbol or ''} — {d.note}".strip() for d in rows
    )


async def _tool_dividend_forecast(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.dividends import dividend_forecast

    r = await dividend_forecast(db)
    if r is None:
        return "No snapshot yet."
    top = "; ".join(f"{h['symbol']} ₹{h['annual']:,.0f}/yr" for h in r["holdings"][:5])
    return (
        f"Estimated dividend income ₹{r['annual_income']:,.0f}/yr "
        f"(~₹{r['monthly_avg']:,.0f}/mo) at an assumed {r['assumed_yield_pct']}% yield. "
        f"Top: {top}."
    )


async def _tool_portfolio_xray(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.xray import portfolio_xray

    r = await portfolio_xray(db)
    if r is None:
        return "No snapshot yet."
    rows = "; ".join(
        f"{c['asset_class']} {c['weight'] * 100:.0f}% (direct ₹{c['direct']:,.0f} + funds ₹{c['fund']:,.0f})"
        for c in r["classes"]
    )
    return f"True exposure: {rows}."


async def _tool_stress_scenario(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.stress import run_stress

    r = await run_stress(db, str(args.get("scenario") or "market"))
    if r is None:
        return "No snapshot yet."
    hits = "; ".join(f"{h['symbol']} {h['change']:,.0f}" for h in r["top_hits"][:4])
    return (
        f"{r['label']}: portfolio ₹{r['total_before']:,.0f} → ₹{r['total_after']:,.0f} "
        f"({r['change_pct']:+.1f}%). Hardest hit: {hits}."
    )


async def _tool_fi_projection(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.fi import fi_projection

    r = await fi_projection(
        db,
        risk_client,
        int(args.get("years") or 15),
        float(args.get("target_corpus") or 30_000_000),
        float(args.get("monthly_contribution") or 20_000),
        float(args.get("swr") or 0.035),
        float(args.get("inflation") or 0.06),
        bool(args.get("post_selloff") or False),
    )
    if r is None:
        return "No snapshot yet."
    shortfall = (
        f" To hit {r.target_probability * 100:.0f}% odds you'd need about "
        f"₹{r.required_monthly_contribution:,.0f}/mo."
        if r.required_reachable
        else f" Even ₹{r.required_monthly_contribution:,.0f}/mo wouldn't reach it."
    )
    return (
        f"FI in {r.years}y at ₹{r.monthly_contribution:,.0f}/mo toward "
        f"₹{r.target_today:,.0f} in today's money (= ₹{r.target_nominal:,.0f} nominal "
        f"after {r.inflation * 100:.0f}% inflation): P(success) "
        f"{r.probability_of_success * 100:.0f}%; median corpus ₹{r.median_corpus:,.0f} "
        f"nominal = ₹{r.median_corpus_today:,.0f} in today's money (p10 "
        f"₹{r.p10_corpus_today:,.0f} today's). At {r.swr * 100:.1f}% SWR that's "
        f"₹{r.sustainable_monthly_income_today:,.0f}/mo in today's purchasing power."
        + shortfall
    )


async def _tool_make_chart(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.chart_spec import build_chart

    kind = str(args.get("kind") or "allocation").lower()
    spec = await build_chart(db, kind)
    if spec is None:
        return "No snapshot to chart yet."
    top = "; ".join(f"{s['label']} {s['value']:,.0f}" for s in spec["series"][:6])
    return f"[[chart:{kind}]] {spec['title']}: {top}."


async def _tool_benchmark(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.benchmark import benchmark_vs_nifty

    b = await benchmark_vs_nifty(db)
    if b is None:
        return "Not enough history or NIFTY data to benchmark yet."
    verdict = "ahead of" if b.alpha_pct >= 0 else "behind"
    return (
        f"Last {b.days} trading days: portfolio {b.portfolio_return_pct:+.1f}% vs "
        f"NIFTY {b.nifty_return_pct:+.1f}% — {verdict} the index by "
        f"{abs(b.alpha_pct):.1f} pts. {b.note}"
    )


async def _tool_tax_impact(args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    from app.services.ai.tax import tax_summary

    t = await tax_summary(db)
    if t is None:
        return "No snapshot yet."
    harvest = (
        "; ".join(f"{h['symbol']} (₹{h['loss']:,.0f})" for h in t.harvest_candidates)
        or "none"
    )
    return (
        f"Unrealized stock gains ₹{t.total_unrealized_gain:,.0f}. If realized this FY: "
        f"est. LTCG tax ₹{t.est_ltcg_tax:,.0f} (or STCG ₹{t.est_stcg_tax:,.0f}). "
        f"Tax-loss-harvest candidates: {harvest}. {t.note}"
    )


_TOOL_HANDLERS: dict[str, Callable[[dict, AsyncSession, BaseRiskClient], Awaitable[str]]] = {
    "get_portfolio": _tool_get_portfolio,
    "get_risk": _tool_get_risk,
    "get_diversification": _tool_get_diversification,
    "get_issues": _tool_get_issues,
    "list_goals": _tool_list_goals,
    "simulate_goal": _tool_simulate_goal,
    "required_sip": _tool_required_sip,
    "search_knowledge": _tool_search_knowledge,
    "find_similar_days": _tool_find_similar_days,
    "get_news": _tool_get_news,
    "optimize_portfolio": _tool_optimize_portfolio,
    "draft_sell_order": _tool_draft_sell_order,
    "earnings_calendar": _tool_earnings_calendar,
    "hedge": _tool_hedge,
    "forecast": _tool_forecast,
    "macro": _tool_macro,
    "recall_decisions": _tool_recall_decisions,
    "dividend_forecast": _tool_dividend_forecast,
    "portfolio_xray": _tool_portfolio_xray,
    "stress_scenario": _tool_stress_scenario,
    "fi_projection": _tool_fi_projection,
    "make_chart": _tool_make_chart,
    "benchmark": _tool_benchmark,
    "tax_impact": _tool_tax_impact,
}


async def run_tool(name: str, args: dict, db: AsyncSession, risk_client: BaseRiskClient) -> str:
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool {name}"
    return await handler(args, db, risk_client)
