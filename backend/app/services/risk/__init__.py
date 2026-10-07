"""Risk-engine client layer (mock + gRPC behind one interface)."""

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
    RiskEngineError,
    Sleeve,
)
from app.services.risk.factory import build_risk_client, get_risk_client

__all__ = [
    "BaseRiskClient",
    "BucketRisk",
    "CorrelatedPair",
    "DiversificationAsset",
    "DiversificationOutcome",
    "GoalSimInputs",
    "GoalSimOutcome",
    "PortfolioRiskOutcome",
    "ProjectionPoint",
    "RetirementPlanInputs",
    "RetirementPlanOutcome",
    "RiskEngineError",
    "Sleeve",
    "build_risk_client",
    "get_risk_client",
]
