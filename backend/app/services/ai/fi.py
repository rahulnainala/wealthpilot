"""Phase 31 — Financial-Independence projection + SWR planner.

Runs a whole-portfolio Monte Carlo (reusing the C++ goal engine over every
holding as a sleeve) to a retirement corpus, then converts the projected corpus
into a safe-withdrawal monthly income. Answers "can I retire, and how much can I
draw?" — engine-cited, an estimate not a guarantee.

Two things this models that a plain nominal projection hides:

**Inflation.** The target the investor sets is read as *today's purchasing power*
— that's how people actually think about money ("I want ₹1.5Cr"). What has to
be accumulated by the target date is that figure compounded at the inflation
rate, so a ₹1.5Cr goal 13 years out at 6% really means ~₹3.2Cr nominal. The
engine still runs in nominal rupees; outputs are deflated back to today's money
so both framings are visible side by side. 6% is the default floor
(long-run Indian CPI has run ~5-6%; healthcare and education run hotter).

**Post-sell-off allocation.** The legacy PSU/energy/REIT basket is on a
+10%-profit exit with a hard mid-2027 deadline (app.domain.exit_plan is
authoritative), with proceeds routed 50/30/20
into equity mutual funds. ``post_selloff=True`` reclassifies that dividend
sleeve as equity so the projection reflects the portfolio the plan is actually
heading toward, not the one being wound down.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import latest_holding_views
from app.services.goal_simulation import (
    _DEFAULT_ASSUMPTION,
    RETURN_ASSUMPTIONS,
    _sleeve_class,
)
from app.services.risk import (
    BaseRiskClient,
    GoalSimInputs,
    RetirementPlanInputs,
    Sleeve,
)

# The owner's floor for planning (2026-07-20): never project below 6%.
DEFAULT_INFLATION = 0.06
MIN_INFLATION = 0.06

# The required-SIP bisection re-runs the engine per step, so it uses a lighter
# path count than the headline projection — it only needs the crossing point,
# not a precise distribution.
_SOLVE_PATHS = 2000
_SOLVE_ITERATIONS = 12
_SOLVE_CEILING = 500_000.0
_SOLVE_TARGET_PROBABILITY = 0.75

# The plan's SIP amounts (the demo investor's): once Travel/Vehicle complete,
# their SIP is freed and rolls into FI rather than the plan ending at a flat
# SIP forever. Used by the retirement-plan step-up schedule; fallback dates
# below only apply when the caller doesn't pass the real goal dates.
_TRAVEL_SIP_STEP = 10_000.0
_VEHICLE_SIP_STEP = 6_000.0
_TRAVEL_FALLBACK_DATE = date(2030, 2, 1)
_VEHICLE_FALLBACK_DATE = date(2031, 5, 1)

_PLAN_SOLVE_PATHS = 4000


@dataclass(frozen=True)
class FiProjection:
    years: int
    swr: float
    inflation: float
    post_selloff: bool
    monthly_contribution: float
    # Targets: what the owner set (today's money) vs what must actually be
    # accumulated by the date (future rupees).
    target_today: float
    target_nominal: float
    # Engine output, nominal (future rupees).
    probability_of_success: float
    median_corpus: float
    p10_corpus: float
    p90_corpus: float
    sustainable_monthly_income: float
    # Same figures deflated to today's purchasing power.
    median_corpus_today: float
    p10_corpus_today: float
    p90_corpus_today: float
    sustainable_monthly_income_today: float
    # What it would actually take to reach _SOLVE_TARGET_PROBABILITY.
    required_monthly_contribution: float
    required_reachable: bool
    target_probability: float
    # Allocation context for the UI.
    equity_pct: float


@dataclass(frozen=True)
class PlanBand:
    month: int  # months from today; the retirement boundary is at `years * 12`
    p10: float
    median: float
    p90: float
    # Same three, deflated to today's purchasing power.
    p10_today: float
    median_today: float
    p90_today: float


@dataclass(frozen=True)
class RetirementPlanResult:
    """One continuous accumulation + drawdown simulation.

    Unlike :class:`FiProjection` (a single snapshot at the retirement date),
    this carries sequence-of-returns risk across the retirement boundary and
    answers the question the snapshot can't: does the corpus outlive the
    drawdown horizon, and if not, roughly when does it run out.
    """

    years: int
    retirement_years: int
    swr: float
    inflation: float
    post_selloff: bool
    step_up: bool
    monthly_contribution: float
    target_today: float
    target_nominal: float
    # At the retirement boundary.
    probability_of_success: float
    median_corpus: float
    p10_corpus: float
    p90_corpus: float
    # Through the drawdown phase.
    depletion_probability: float
    median_depletion_year: int | None  # None if the median path never depletes
    median_terminal_value: float
    median_terminal_value_today: float
    # Allocation context + the full yearly fan, both phases.
    equity_pct: float
    bands: list[PlanBand]


def _months_until(target: date, today: date | None = None) -> int:
    today = today or date.today()
    return max(1, (target.year - today.year) * 12 + (target.month - today.month))


def _build_sleeves(
    holdings: list, cash: float, post_selloff: bool
) -> list[Sleeve] | None:
    """Aggregate holdings into return-assumption sleeves.

    When ``post_selloff`` is set, the dividend sleeve is folded into equity —
    the legacy basket is being sold and its proceeds routed into equity funds,
    so that is the allocation the plan ends up with.
    """
    values: dict[str, float] = {}
    for h in holdings:
        cls = _sleeve_class(h)
        if post_selloff and cls == "dividend":
            cls = "equity"
        values[cls] = values.get(cls, 0.0) + h.value
    if cash:
        values["debt"] = values.get("debt", 0.0) + cash  # cash ~ liquid/debt
    if not values:
        return None

    return [
        Sleeve(
            bucket=cls,
            value=round(v, 2),
            annual_return_mean=RETURN_ASSUMPTIONS.get(cls, _DEFAULT_ASSUMPTION)[0],
            annual_return_volatility=RETURN_ASSUMPTIONS.get(cls, _DEFAULT_ASSUMPTION)[1],
        )
        for cls, v in sorted(values.items())
    ]


async def _solve_required_contribution(
    risk_client: BaseRiskClient, base: GoalSimInputs
) -> tuple[float, bool]:
    """Bisect the monthly SIP needed to clear the target probability.

    Success probability is monotonic in contribution, so bisection converges
    fast. Returns ``(monthly, reachable)`` — when unreachable even at the
    ceiling, the ceiling is returned so the UI can say "more than ₹X/mo".
    """
    light = replace(base, num_paths=_SOLVE_PATHS)

    async def prob_at(monthly: float) -> float:
        out = await risk_client.simulate_goal(replace(light, monthly_contribution=monthly))
        return out.probability_of_success

    if await prob_at(0.0) >= _SOLVE_TARGET_PROBABILITY:
        return 0.0, True
    if await prob_at(_SOLVE_CEILING) < _SOLVE_TARGET_PROBABILITY:
        return _SOLVE_CEILING, False

    lo, hi = 0.0, _SOLVE_CEILING
    for _ in range(_SOLVE_ITERATIONS):
        mid = (lo + hi) / 2
        if await prob_at(mid) >= _SOLVE_TARGET_PROBABILITY:
            hi = mid
        else:
            lo = mid
    return round(hi, -2), True  # nearest ₹100 — false precision helps nobody


async def fi_projection(
    db: AsyncSession,
    risk_client: BaseRiskClient,
    years: int = 15,
    target: float = 30_000_000.0,
    monthly_contribution: float = 20_000.0,
    swr: float = 0.035,
    inflation: float = DEFAULT_INFLATION,
    post_selloff: bool = False,
    solve_required: bool = True,
) -> FiProjection | None:
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, cash = data

    sleeves = _build_sleeves(holdings, cash, post_selloff)
    if sleeves is None:
        return None

    inflation = max(MIN_INFLATION, inflation)
    years = max(1, years)
    # `target` is today's purchasing power; grow it to the nominal figure that
    # must actually sit in the account on the target date.
    divisor = (1.0 + inflation) ** years
    target_nominal = target * divisor

    inputs = GoalSimInputs(
        sleeves=sleeves,
        monthly_contribution=monthly_contribution,
        months_remaining=years * 12,
        target_value=target_nominal,
        num_paths=5000,
        seed=42,
    )
    out = await risk_client.simulate_goal(inputs)

    required, reachable = (
        await _solve_required_contribution(risk_client, inputs)
        if solve_required
        else (0.0, True)
    )

    equity_value = sum(s.value for s in sleeves if s.bucket == "equity")
    total_value = sum(s.value for s in sleeves) or 1.0
    nominal_income = out.median_ending_value * swr / 12

    return FiProjection(
        years=years,
        swr=swr,
        inflation=inflation,
        post_selloff=post_selloff,
        monthly_contribution=monthly_contribution,
        target_today=round(target, 2),
        target_nominal=round(target_nominal, 2),
        probability_of_success=out.probability_of_success,
        median_corpus=round(out.median_ending_value, 2),
        p10_corpus=round(out.p10_value, 2),
        p90_corpus=round(out.p90_value, 2),
        sustainable_monthly_income=round(nominal_income, 2),
        median_corpus_today=round(out.median_ending_value / divisor, 2),
        p10_corpus_today=round(out.p10_value / divisor, 2),
        p90_corpus_today=round(out.p90_value / divisor, 2),
        sustainable_monthly_income_today=round(nominal_income / divisor, 2),
        required_monthly_contribution=required,
        required_reachable=reachable,
        target_probability=_SOLVE_TARGET_PROBABILITY,
        equity_pct=round(equity_value / total_value * 100, 1),
    )


async def retirement_plan_projection(
    db: AsyncSession,
    risk_client: BaseRiskClient,
    years: int = 15,
    target: float = 30_000_000.0,
    monthly_contribution: float = 20_000.0,
    swr: float = 0.035,
    inflation: float = DEFAULT_INFLATION,
    post_selloff: bool = False,
    retirement_years: int = 25,
    step_up: bool = True,
    travel_months: int | None = None,
    vehicle_months: int | None = None,
) -> RetirementPlanResult | None:
    """One continuous accumulation-then-drawdown simulation for the plan.

    ``step_up`` models FI's SIP growing as Travel/Vehicle complete and free
    their share of the SIP (+₹10k when Travel completes, +₹6k when Vehicle
    does) rather than staying flat forever — ``travel_months`` /
    ``vehicle_months`` are months-from-today until each completes (the
    caller reads this off the real goal dates; falls back to the seeded
    goal dates if not supplied). The withdrawal side escalates the nominal draw at
    ``inflation`` through drawdown so purchasing power holds steady.
    """
    data = await latest_holding_views(db)
    if data is None:
        return None
    holdings, cash = data

    sleeves = _build_sleeves(holdings, cash, post_selloff)
    if sleeves is None:
        return None

    inflation = max(MIN_INFLATION, inflation)
    years = max(1, years)
    retirement_years = max(1, retirement_years)
    accumulation_months = years * 12
    drawdown_months = retirement_years * 12

    divisor = (1.0 + inflation) ** years
    target_nominal = target * divisor

    contribution_schedule: list[float] = []
    if step_up:
        jm = travel_months if travel_months is not None else _months_until(_TRAVEL_FALLBACK_DATE)
        om = vehicle_months if vehicle_months is not None else _months_until(_VEHICLE_FALLBACK_DATE)
        contribution_schedule = [
            monthly_contribution
            + (_TRAVEL_SIP_STEP if m >= jm else 0.0)
            + (_VEHICLE_SIP_STEP if m >= om else 0.0)
            for m in range(accumulation_months)
        ]

    # Nominal monthly draw starts at the SWR figure and escalates at the
    # inflation rate so the real (today's-money) income stays flat through
    # drawdown — matching the assumption already used for the target itself.
    initial_withdrawal = target_nominal * swr / 12.0
    monthly_inflation = (1.0 + inflation) ** (1.0 / 12.0) - 1.0
    withdrawal_schedule = [
        initial_withdrawal * (1.0 + monthly_inflation) ** m for m in range(drawdown_months)
    ]

    inputs = RetirementPlanInputs(
        sleeves=sleeves,
        contribution_schedule=contribution_schedule,
        monthly_contribution=monthly_contribution,
        accumulation_months=accumulation_months,
        target_value=target_nominal,
        withdrawal_schedule=withdrawal_schedule,
        drawdown_months=drawdown_months,
        num_paths=_PLAN_SOLVE_PATHS,
        seed=42,
    )
    out = await risk_client.simulate_retirement_plan(inputs)

    equity_value = sum(s.value for s in sleeves if s.bucket == "equity")
    total_value = sum(s.value for s in sleeves) or 1.0

    median_depletion_year = None
    if out.median_depletion_month >= 0:
        median_depletion_year = (
            date.today().year + years + int(out.median_depletion_month // 12)
        )

    full_divisor = (1.0 + inflation) ** (years + retirement_years)

    bands = [
        PlanBand(
            month=b.month,
            p10=round(b.p10, 2),
            median=round(b.median, 2),
            p90=round(b.p90, 2),
            p10_today=round(b.p10 / (1.0 + inflation) ** (b.month / 12.0), 2),
            median_today=round(b.median / (1.0 + inflation) ** (b.month / 12.0), 2),
            p90_today=round(b.p90 / (1.0 + inflation) ** (b.month / 12.0), 2),
        )
        for b in out.bands
    ]

    return RetirementPlanResult(
        years=years,
        retirement_years=retirement_years,
        swr=swr,
        inflation=inflation,
        post_selloff=post_selloff,
        step_up=step_up,
        monthly_contribution=monthly_contribution,
        target_today=round(target, 2),
        target_nominal=round(target_nominal, 2),
        probability_of_success=out.probability_of_success,
        median_corpus=round(out.median_corpus, 2),
        p10_corpus=round(out.p10_corpus, 2),
        p90_corpus=round(out.p90_corpus, 2),
        depletion_probability=out.depletion_probability,
        median_depletion_year=median_depletion_year,
        median_terminal_value=round(out.median_terminal_value, 2),
        median_terminal_value_today=round(out.median_terminal_value / full_divisor, 2),
        equity_pct=round(equity_value / total_value * 100, 1),
        bands=bands,
    )
