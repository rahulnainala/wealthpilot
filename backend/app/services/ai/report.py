"""Phase 22 — monthly PDF report.

A shareable keepsake statement built from structured numbers (value, P&L, risk,
goals, benchmark, tax, active alerts) via fpdf2 — pure-Python, no system deps,
no 3070 call in the download path. Currency is written as "Rs" to stay within
fpdf2's Latin-1 core fonts. Generated on demand from the AI tab.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import latest_holding_views, load_goal_views
from app.services.market import build_market_data_provider
from app.services.portfolio_risk_service import portfolio_risk
from app.services.risk import BaseRiskClient


def _rs(x: float) -> str:
    return f"Rs {x:,.0f}"


def _safe(s: str) -> str:
    """Coerce text to fpdf2's Latin-1 core-font range."""
    return (
        s.replace("₹", "Rs ")
        .replace("—", "-")
        .replace("–", "-")
        .replace("→", "->")
        .replace("•", "-")
        .replace("’", "'")
        .replace("‘", "'")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


async def monthly_report_pdf(db: AsyncSession, risk_client: BaseRiskClient) -> bytes | None:
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, cash = data
    total = sum(h.value for h in holdings) + cash
    pnl = sum(h.pnl for h in holdings)

    provider = build_market_data_provider()
    try:
        risk = await portfolio_risk(db, provider, risk_client)
    finally:
        await provider.close()

    from app.models.goal import GoalSimulation

    sims = {
        r.goal_id: r
        for r in (
            await db.execute(select(GoalSimulation).order_by(GoalSimulation.id.desc()))
        ).scalars()
    }
    goals = await load_goal_views(db)

    from app.services.ai.benchmark import benchmark_vs_nifty
    from app.services.ai.tax import tax_summary
    from app.services.ai.watch import evaluate_watch

    bench = await benchmark_vs_nifty(db)
    tax = await tax_summary(db)
    alerts = await evaluate_watch(db, risk_client)

    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "WealthPilot - Monthly Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, date.today().strftime("%B %Y"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    def heading(txt: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.ln(2)
        pdf.cell(0, 8, _safe(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 11)

    def line(txt: str) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 6, _safe(txt))

    heading("Portfolio")
    line(f"Total value: {_rs(total)}   Cash: {_rs(cash)}   Unrealized P&L: {_rs(pnl)}")

    if risk:
        heading("Risk")
        line(
            f"1-day VaR(95%): {_rs(risk.var)}   CVaR: {_rs(risk.cvar)}   "
            f"Annualized vol: {risk.annual_volatility * 100:.1f}%   "
            f"3-mo max drawdown: {risk.max_drawdown * 100:.1f}%"
        )

    if bench:
        heading("Vs NIFTY 50")
        line(
            f"Last {bench.days} trading days: portfolio {bench.portfolio_return_pct:+.1f}% "
            f"vs NIFTY {bench.nifty_return_pct:+.1f}% (alpha {bench.alpha_pct:+.1f} pts)."
        )

    heading("Goals")
    for g in goals:
        sim = sims.get(g.id)
        prob = f"{sim.probability_of_success * 100:.0f}% success" if sim else "not simulated"
        line(f"- {g.name}: {prob}")

    if tax:
        heading("Tax (if gains realized this FY)")
        line(
            f"Unrealized stock gains {_rs(tax.total_unrealized_gain)}; est. LTCG "
            f"{_rs(tax.est_ltcg_tax)} (STCG {_rs(tax.est_stcg_tax)}). "
            f"Harvest candidates: {len(tax.harvest_candidates)}."
        )

    heading("Active alerts")
    if alerts:
        for a in alerts:
            line(f"[{a.severity}] {a.text}")
    else:
        line("None.")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    line("Informational analysis, not licensed financial advice. Figures from your latest snapshot.")

    return bytes(pdf.output())
