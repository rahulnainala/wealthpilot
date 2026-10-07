"""Risk-engine client interface and its plain-data DTOs.

Both the gRPC client (talks to the C++ engine) and the in-process mock conform
to this, so the rest of the backend is agnostic to which is wired in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Sleeve:
    """One allocation sleeve: money in a class with its return assumptions."""

    bucket: str
    value: float
    annual_return_mean: float
    annual_return_volatility: float


@dataclass(frozen=True)
class GoalSimInputs:
    sleeves: list[Sleeve]
    monthly_contribution: float
    months_remaining: int
    target_value: float
    num_paths: int = 10_000
    seed: int = 0
    initial_shock: float = 0.0  # <= 0: one-time market shock at t=0 (beta-scaled)


@dataclass(frozen=True)
class GoalSimOutcome:
    probability_of_success: float
    median_ending_value: float
    p10_value: float
    p90_value: float


@dataclass(frozen=True)
class BucketRisk:
    bucket: str
    value: float
    returns: list[float]


@dataclass(frozen=True)
class RiskContribution:
    bucket: str
    contribution: float


@dataclass(frozen=True)
class PortfolioRiskOutcome:
    var: float
    cvar: float
    annual_volatility: float = 0.0
    max_drawdown: float = 0.0
    contributions: list[RiskContribution] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectionPoint:
    month: int
    p10: float
    median: float
    p90: float


@dataclass(frozen=True)
class RetirementPlanInputs:
    sleeves: list[Sleeve]
    # Per-month contribution during accumulation. Empty -> monthly_contribution
    # every month; shorter than the phase -> the last value extends (a step-up
    # schedule only needs the months up to the step).
    contribution_schedule: list[float]
    monthly_contribution: float
    accumulation_months: int
    target_value: float  # nominal corpus wanted at retirement
    # Per-month withdrawal during drawdown, nominal (caller bakes in inflation).
    # Same empty/short semantics as the contribution schedule.
    withdrawal_schedule: list[float]
    drawdown_months: int
    num_paths: int = 0  # <= 0 -> engine default
    seed: int = 0  # 0 -> nondeterministic


@dataclass(frozen=True)
class RetirementPlanOutcome:
    # At the retirement boundary.
    probability_of_success: float
    median_corpus: float
    p10_corpus: float
    p90_corpus: float
    # Through the drawdown phase.
    depletion_probability: float
    median_depletion_month: float  # among depleting paths; -1 if none
    median_terminal_value: float  # corpus left at the end of drawdown
    # p10/median/p90 sampled yearly across BOTH phases (month 0 included).
    bands: list[ProjectionPoint]


@dataclass(frozen=True)
class DiversificationAsset:
    label: str
    weight: float
    returns: list[float]


@dataclass(frozen=True)
class CorrelatedPair:
    label_a: str
    label_b: str
    correlation: float


@dataclass(frozen=True)
class DiversificationOutcome:
    average_correlation: float
    diversification_ratio: float
    effective_holdings: float
    holdings: int
    top_pairs: list[CorrelatedPair]


class RiskEngineError(RuntimeError):
    """Raised when the risk engine is unreachable or returns an error."""


class BaseRiskClient(ABC):
    @abstractmethod
    async def health(self) -> bool:
        """Return True if the risk engine is reachable."""

    @abstractmethod
    async def simulate_goal(self, inputs: GoalSimInputs) -> GoalSimOutcome:
        """Monte Carlo probability that a goal reaches its target."""

    @abstractmethod
    async def compute_portfolio_risk(
        self, buckets: list[BucketRisk], confidence: float = 0.95
    ) -> PortfolioRiskOutcome:
        """Historical VaR/CVaR and per-bucket risk contributions."""

    @abstractmethod
    async def simulate_portfolio_projection(
        self,
        sleeves: list[Sleeve],
        monthly_contribution: float,
        months: int,
        num_paths: int = 10_000,
        seed: int = 0,
    ) -> list[ProjectionPoint]:
        """Monte Carlo the portfolio value forward: p10/median/p90 per month."""

    @abstractmethod
    async def compute_diversification(
        self, assets: list[DiversificationAsset]
    ) -> DiversificationOutcome:
        """Correlation-based diversification & concentration analysis."""

    @abstractmethod
    async def simulate_retirement_plan(
        self, inputs: RetirementPlanInputs
    ) -> RetirementPlanOutcome:
        """Accumulation + drawdown simulated on one continuous path.

        Carries sequence-of-returns risk across the retirement boundary, and
        reports whether/when the corpus runs dry during drawdown.
        """

    async def close(self) -> None:
        """Release any resources (no-op by default)."""
        return None
