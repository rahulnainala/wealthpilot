"""Build goal simulation inputs, run the risk engine, and cache the result.

The ``goal_simulation`` table is a cache keyed by ``input_hash`` so the risk
engine is not re-run on every page load — only on demand (Recalculate) or by the
daily scheduler.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.mf_audit import AssetClass, mf_asset_class
from app.analytics.models import HoldingView
from app.domain.enums import Bucket, HoldingType
from app.models.goal import Goal, GoalSimulation
from app.services.risk import BaseRiskClient, GoalSimInputs, Sleeve

# Per-sleeve-class annual (mean, volatility) assumptions — editable defaults.
RETURN_ASSUMPTIONS: dict[str, tuple[float, float]] = {
    "equity": (0.12, 0.18),
    "dividend": (0.10, 0.14),
    "debt": (0.065, 0.03),
    "gold": (0.07, 0.13),
}
_DEFAULT_ASSUMPTION = (0.11, 0.15)


@dataclass(frozen=True)
class SimulationOverrides:
    target_value: float | None = None
    monthly_contribution: float | None = None
    num_paths: int | None = None
    seed: int | None = None


def _months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


def _sleeve_class(holding: HoldingView) -> str:
    if holding.type == HoldingType.MF:
        asset_class = mf_asset_class(holding.symbol)
        return asset_class.value if asset_class else AssetClass.EQUITY.value
    if holding.bucket == Bucket.GROWTH:
        return "equity"
    if holding.bucket == Bucket.DIVIDEND:
        return "dividend"
    if holding.bucket == Bucket.OTHER:
        return "gold"
    return "equity"


def _assigned(goal: Goal, holdings: list[HoldingView]) -> list[HoldingView]:
    isins = set(goal.assigned_isins)
    buckets = set(goal.assigned_buckets)
    return [h for h in holdings if h.symbol in isins or h.bucket.value in buckets]


def build_goal_sim_inputs(
    goal: Goal,
    holdings: list[HoldingView],
    today: date,
    default_paths: int,
    overrides: SimulationOverrides | None = None,
) -> GoalSimInputs | None:
    """Assemble simulation inputs for a goal, or None if it has no target."""
    overrides = overrides or SimulationOverrides()
    target = overrides.target_value if overrides.target_value is not None else goal.target_value
    if target is None or goal.target_date is None:
        return None

    # Group assigned money into sleeves by asset class.
    sleeve_values: dict[str, float] = {}
    for holding in _assigned(goal, holdings):
        cls = _sleeve_class(holding)
        sleeve_values[cls] = sleeve_values.get(cls, 0.0) + holding.value

    sleeves = [
        Sleeve(
            bucket=cls,
            value=round(value, 2),
            annual_return_mean=RETURN_ASSUMPTIONS.get(cls, _DEFAULT_ASSUMPTION)[0],
            annual_return_volatility=RETURN_ASSUMPTIONS.get(cls, _DEFAULT_ASSUMPTION)[1],
        )
        for cls, value in sorted(sleeve_values.items())
    ]

    contribution = (
        overrides.monthly_contribution
        if overrides.monthly_contribution is not None
        else goal.monthly_contribution
    )
    return GoalSimInputs(
        sleeves=sleeves,
        monthly_contribution=contribution,
        months_remaining=_months_between(today, goal.target_date),
        target_value=target,
        num_paths=overrides.num_paths or default_paths,
        # Stable per-goal seed keeps repeated runs (and their hash) reproducible.
        seed=overrides.seed if overrides.seed is not None else goal.id,
    )


def input_hash(inputs: GoalSimInputs) -> str:
    parts = [
        *(f"{s.bucket}:{s.value:.2f}:{s.annual_return_mean}:{s.annual_return_volatility}"
          for s in inputs.sleeves),
        f"c={inputs.monthly_contribution:.2f}",
        f"m={inputs.months_remaining}",
        f"t={inputs.target_value:.2f}",
        f"p={inputs.num_paths}",
        f"s={inputs.seed}",
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


async def simulate_goal_and_cache(
    db: AsyncSession,
    goal: Goal,
    holdings: list[HoldingView],
    risk_client: BaseRiskClient,
    today: date,
    default_paths: int,
    overrides: SimulationOverrides | None = None,
) -> GoalSimulation | None:
    """Run the risk engine for a goal and persist a cached simulation row."""
    inputs = build_goal_sim_inputs(goal, holdings, today, default_paths, overrides)
    if inputs is None:
        return None

    outcome = await risk_client.simulate_goal(inputs)
    row = GoalSimulation(
        goal_id=goal.id,
        input_hash=input_hash(inputs),
        probability_of_success=outcome.probability_of_success,
        median_ending_value=outcome.median_ending_value,
        p10_value=outcome.p10_value,
        p90_value=outcome.p90_value,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@dataclass(frozen=True)
class RequiredContribution:
    required_monthly_contribution: float
    probability_of_success: float
    target_probability: float
    reachable: bool


@dataclass(frozen=True)
class StressScenario:
    label: str
    shock: float  # e.g. -0.30 for a 30% equity crash at t=0
    probability_of_success: float
    median_ending_value: float
    p10_value: float


@dataclass(frozen=True)
class StressTest:
    baseline_probability: float
    scenarios: list[StressScenario]


# Default shock ladder: baseline + progressively deeper one-time crashes at t=0.
_STRESS_SHOCKS: list[tuple[str, float]] = [
    ("Baseline", 0.0),
    ("Mild correction (−10%)", -0.10),
    ("Bear market (−20%)", -0.20),
    ("Severe crash (−30%)", -0.30),
    ("2008-style (−40%)", -0.40),
]


async def stress_test_goal(
    goal: Goal,
    holdings: list[HoldingView],
    risk_client: BaseRiskClient,
    today: date,
    default_paths: int,
) -> StressTest | None:
    """Re-run a goal's Monte Carlo under a ladder of one-time market shocks.

    Shows how each goal's success probability holds up if markets fall right now —
    the shock is beta-scaled by sleeve volatility, so liquid/debt sleeves (e.g. the
    Travel fund) barely move while equity sleeves take the full hit.
    """
    base = build_goal_sim_inputs(goal, holdings, today, default_paths)
    if base is None:
        return None

    scenarios: list[StressScenario] = []
    baseline_probability = 0.0
    for label, shock in _STRESS_SHOCKS:
        outcome = await risk_client.simulate_goal(replace(base, initial_shock=shock))
        if shock == 0.0:
            baseline_probability = outcome.probability_of_success
        scenarios.append(
            StressScenario(
                label=label,
                shock=shock,
                probability_of_success=outcome.probability_of_success,
                median_ending_value=outcome.median_ending_value,
                p10_value=outcome.p10_value,
            )
        )
    return StressTest(baseline_probability=baseline_probability, scenarios=scenarios)


async def solve_required_contribution(
    goal: Goal,
    holdings: list[HoldingView],
    risk_client: BaseRiskClient,
    today: date,
    default_paths: int,
    target_probability: float = 0.75,
    max_monthly: float = 500_000.0,
    iterations: int = 16,
) -> RequiredContribution | None:
    """Binary-search the monthly contribution needed to hit a success probability.

    Probability is monotonic in contribution, so a bisection converges quickly.
    Returns None if the goal has no target to solve for.
    """
    base = build_goal_sim_inputs(goal, holdings, today, default_paths)
    if base is None:
        return None

    async def prob_at(contribution: float) -> float:
        inputs = replace(base, monthly_contribution=contribution)
        outcome = await risk_client.simulate_goal(inputs)
        return outcome.probability_of_success

    # Already achievable with no extra contributions?
    if await prob_at(0.0) >= target_probability:
        return RequiredContribution(0.0, await prob_at(0.0), target_probability, True)

    # Unreachable even at the ceiling.
    prob_ceiling = await prob_at(max_monthly)
    if prob_ceiling < target_probability:
        return RequiredContribution(
            max_monthly, prob_ceiling, target_probability, reachable=False
        )

    lo, hi = 0.0, max_monthly
    for _ in range(iterations):
        mid = (lo + hi) / 2
        if await prob_at(mid) >= target_probability:
            hi = mid
        else:
            lo = mid

    return RequiredContribution(
        round(hi, 0), await prob_at(hi), target_probability, reachable=True
    )


@dataclass(frozen=True)
class GoalAllocation:
    goal_id: int
    goal_key: str
    goal_name: str
    allocated_monthly: float
    baseline_probability: float
    optimized_probability: float


@dataclass(frozen=True)
class JointOptimization:
    total_budget: float
    step: float
    allocations: list[GoalAllocation]
    expected_goals_before: float
    expected_goals_after: float
    on_track_after: int
    goal_count: int
    unallocated: float


async def optimize_across_goals(
    goals: list[Goal],
    holdings: list[HoldingView],
    risk_client: BaseRiskClient,
    today: date,
    default_paths: int,
    total_budget: float,
    max_steps: int = 16,
) -> JointOptimization | None:
    """Split one fixed monthly budget across all goals for the most probability per rupee.

    The goals compete for a single pool of money. Each ``step`` of budget is handed
    to whichever goal it lifts the *most* — i.e. the largest marginal jump in success
    probability — which maximises the expected number of goals achieved for the
    budget. (A pure max-min "lift the weakest" rule is degenerate here: one huge,
    under-resourced goal would otherwise soak the whole budget for little gain.) It
    leans only on the existing Monte Carlo primitive — no new engine work — by pricing
    a per-goal probability curve over a contribution grid, then allocating greedily on
    the cached curves. Returns None if no goal is simulatable or the budget is zero.
    """
    # Cap paths so the O(goals x grid) sim sweep stays interactive.
    paths = min(default_paths, 2000)

    candidates: list[tuple[Goal, GoalSimInputs]] = []
    for goal in goals:
        base = build_goal_sim_inputs(goal, holdings, today, paths)
        if base is not None:
            candidates.append((goal, base))
    if not candidates or total_budget <= 0:
        return None

    step = total_budget / max_steps
    grid = [i * step for i in range(max_steps + 1)]

    # Probability as a function of this goal's own monthly contribution.
    curves: dict[int, list[float]] = {}
    for goal, base in candidates:
        probs: list[float] = []
        for contribution in grid:
            outcome = await risk_client.simulate_goal(
                replace(base, monthly_contribution=contribution, num_paths=paths)
            )
            probs.append(outcome.probability_of_success)
        curves[goal.id] = probs

    levels: dict[int, int] = {goal.id: 0 for goal, _ in candidates}
    for _ in range(max_steps):
        best_id: int | None = None
        best_gain = 1e-6  # require a real, positive marginal to spend the step
        for goal, _ in candidates:
            gid = goal.id
            cur = levels[gid]
            if cur >= max_steps:
                continue
            gain = curves[gid][cur + 1] - curves[gid][cur]
            if gain > best_gain:
                best_gain = gain
                best_id = gid
        if best_id is None:
            break
        levels[best_id] += 1

    on_track = 0.75
    allocations = [
        GoalAllocation(
            goal_id=goal.id,
            goal_key=goal.key,
            goal_name=goal.name,
            allocated_monthly=round(levels[goal.id] * step, 0),
            baseline_probability=curves[goal.id][0],
            optimized_probability=curves[goal.id][levels[goal.id]],
        )
        for goal, _ in candidates
    ]
    allocated_total = sum(a.allocated_monthly for a in allocations)
    return JointOptimization(
        total_budget=round(total_budget, 0),
        step=round(step, 0),
        expected_goals_before=round(sum(a.baseline_probability for a in allocations), 2),
        expected_goals_after=round(sum(a.optimized_probability for a in allocations), 2),
        on_track_after=sum(1 for a in allocations if a.optimized_probability >= on_track),
        goal_count=len(allocations),
        unallocated=round(total_budget - allocated_total, 0),
        allocations=allocations,
    )
