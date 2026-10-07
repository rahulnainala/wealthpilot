"""gRPC client wrapping the C++ risk engine (SimulateGoalProbability, etc.)."""

from __future__ import annotations

import grpc

from app.risk.proto import risk_pb2, risk_pb2_grpc
from app.services.risk.base import (
    BaseRiskClient,
    BucketRisk,
    CorrelatedPair,
    DiversificationAsset,
    DiversificationOutcome,
    GoalSimInputs,
    GoalSimOutcome,
    PortfolioRiskOutcome,
    ProjectionPoint,
    RetirementPlanInputs,
    RetirementPlanOutcome,
    RiskContribution,
    RiskEngineError,
    Sleeve,
)


# Per-RPC deadlines: without them, an unreachable engine hangs the API request
# path for gRPC's full connect-backoff (observed ~10s) before failing.
_HEALTH_TIMEOUT_S = 2.0
_COMPUTE_TIMEOUT_S = 8.0     # historical VaR / diversification — pure math, fast
_SIMULATION_TIMEOUT_S = 30.0  # Monte Carlo paths — generous headroom


class GrpcRiskEngineClient(BaseRiskClient):
    """Async gRPC client to the internal risk-engine service."""

    def __init__(self, host: str, port: int) -> None:
        self._target = f"{host}:{port}"
        self._channel: grpc.aio.Channel | None = None
        self._stub: risk_pb2_grpc.RiskEngineStub | None = None

    def _get_stub(self) -> risk_pb2_grpc.RiskEngineStub:
        if self._channel is None:
            self._channel = grpc.aio.insecure_channel(self._target)
            self._stub = risk_pb2_grpc.RiskEngineStub(self._channel)
        assert self._stub is not None
        return self._stub

    async def health(self) -> bool:
        try:
            response = await self._get_stub().Health(
                risk_pb2.HealthRequest(), timeout=_HEALTH_TIMEOUT_S
            )
        except grpc.aio.AioRpcError:
            return False
        return bool(response.status == "ok")

    async def simulate_goal(self, inputs: GoalSimInputs) -> GoalSimOutcome:
        request = risk_pb2.GoalSimRequest(
            sleeves=[
                risk_pb2.GoalSleeve(
                    bucket=s.bucket,
                    value=s.value,
                    annual_return_mean=s.annual_return_mean,
                    annual_return_volatility=s.annual_return_volatility,
                )
                for s in inputs.sleeves
            ],
            monthly_contribution=inputs.monthly_contribution,
            months_remaining=inputs.months_remaining,
            target_value=inputs.target_value,
            num_paths=inputs.num_paths,
            seed=inputs.seed,
            initial_shock=inputs.initial_shock,
        )
        try:
            response = await self._get_stub().SimulateGoalProbability(
                request, timeout=_SIMULATION_TIMEOUT_S
            )
        except grpc.aio.AioRpcError as exc:
            raise RiskEngineError(f"risk engine unavailable: {exc}") from exc
        return GoalSimOutcome(
            probability_of_success=response.probability_of_success,
            median_ending_value=response.median_ending_value,
            p10_value=response.p10_value,
            p90_value=response.p90_value,
        )

    async def compute_portfolio_risk(
        self, buckets: list[BucketRisk], confidence: float = 0.95
    ) -> PortfolioRiskOutcome:
        request = risk_pb2.PortfolioRiskRequest(
            buckets=[
                risk_pb2.BucketRisk(bucket=b.bucket, value=b.value, returns=b.returns)
                for b in buckets
            ],
            confidence=confidence,
            periods_per_year=252.0,  # bucket series are daily returns
        )
        try:
            response = await self._get_stub().ComputePortfolioRisk(
                request, timeout=_COMPUTE_TIMEOUT_S
            )
        except grpc.aio.AioRpcError as exc:
            raise RiskEngineError(f"risk engine unavailable: {exc}") from exc
        return PortfolioRiskOutcome(
            var=response.var,
            cvar=response.cvar,
            annual_volatility=response.annual_volatility,
            max_drawdown=response.max_drawdown,
            contributions=[
                RiskContribution(bucket=c.bucket, contribution=c.contribution)
                for c in response.contributions
            ],
        )

    async def simulate_portfolio_projection(
        self,
        sleeves: list[Sleeve],
        monthly_contribution: float,
        months: int,
        num_paths: int = 10_000,
        seed: int = 0,
    ) -> list[ProjectionPoint]:
        request = risk_pb2.PortfolioProjectionRequest(
            sleeves=[
                risk_pb2.GoalSleeve(
                    bucket=s.bucket,
                    value=s.value,
                    annual_return_mean=s.annual_return_mean,
                    annual_return_volatility=s.annual_return_volatility,
                )
                for s in sleeves
            ],
            monthly_contribution=monthly_contribution,
            months=months,
            num_paths=num_paths,
            seed=seed,
        )
        try:
            response = await self._get_stub().SimulatePortfolioProjection(
                request, timeout=_SIMULATION_TIMEOUT_S
            )
        except grpc.aio.AioRpcError as exc:
            raise RiskEngineError(f"risk engine unavailable: {exc}") from exc
        return [
            ProjectionPoint(
                month=p.month, p10=p.p10, median=p.median, p90=p.p90
            )
            for p in response.points
        ]

    async def compute_diversification(
        self, assets: list[DiversificationAsset]
    ) -> DiversificationOutcome:
        request = risk_pb2.DiversificationRequest(
            assets=[
                risk_pb2.DiversificationAsset(
                    label=a.label, weight=a.weight, returns=a.returns
                )
                for a in assets
            ]
        )
        try:
            response = await self._get_stub().ComputeDiversification(
                request, timeout=_COMPUTE_TIMEOUT_S
            )
        except grpc.aio.AioRpcError as exc:
            raise RiskEngineError(f"risk engine unavailable: {exc}") from exc
        return DiversificationOutcome(
            average_correlation=response.average_correlation,
            diversification_ratio=response.diversification_ratio,
            effective_holdings=response.effective_holdings,
            holdings=response.holdings,
            top_pairs=[
                CorrelatedPair(
                    label_a=p.label_a, label_b=p.label_b, correlation=p.correlation
                )
                for p in response.top_pairs
            ],
        )

    async def simulate_retirement_plan(
        self, inputs: RetirementPlanInputs
    ) -> RetirementPlanOutcome:
        request = risk_pb2.RetirementPlanRequest(
            sleeves=[
                risk_pb2.GoalSleeve(
                    bucket=s.bucket,
                    value=s.value,
                    annual_return_mean=s.annual_return_mean,
                    annual_return_volatility=s.annual_return_volatility,
                )
                for s in inputs.sleeves
            ],
            contribution_schedule=inputs.contribution_schedule,
            monthly_contribution=inputs.monthly_contribution,
            accumulation_months=inputs.accumulation_months,
            target_value=inputs.target_value,
            withdrawal_schedule=inputs.withdrawal_schedule,
            drawdown_months=inputs.drawdown_months,
            num_paths=inputs.num_paths,
            seed=inputs.seed,
        )
        try:
            response = await self._get_stub().SimulateRetirementPlan(
                request, timeout=_SIMULATION_TIMEOUT_S
            )
        except grpc.aio.AioRpcError as exc:
            raise RiskEngineError(f"risk engine unavailable: {exc}") from exc
        return RetirementPlanOutcome(
            probability_of_success=response.probability_of_success,
            median_corpus=response.median_corpus,
            p10_corpus=response.p10_corpus,
            p90_corpus=response.p90_corpus,
            depletion_probability=response.depletion_probability,
            median_depletion_month=response.median_depletion_month,
            median_terminal_value=response.median_terminal_value,
            bands=[
                ProjectionPoint(month=b.month, p10=b.p10, median=b.median, p90=b.p90)
                for b in response.bands
            ],
        )

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None
