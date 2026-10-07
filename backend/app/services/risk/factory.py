"""Select and cache the risk-engine client (mock vs gRPC)."""

from __future__ import annotations

from app.config import get_settings
from app.services.risk.base import BaseRiskClient
from app.services.risk.mock import MockRiskEngineClient

_client: BaseRiskClient | None = None


def build_risk_client() -> BaseRiskClient:
    """Construct a risk client per ``USE_MOCK_RISK_ENGINE``."""
    settings = get_settings()
    if settings.use_mock_risk_engine:
        return MockRiskEngineClient()
    # Imported lazily so the mock path never requires grpc/generated stubs.
    from app.services.risk.grpc_client import GrpcRiskEngineClient

    return GrpcRiskEngineClient(settings.risk_engine_host, settings.risk_engine_port)


def get_risk_client() -> BaseRiskClient:
    """Return the process-wide risk client (FastAPI dependency)."""
    global _client
    if _client is None:
        _client = build_risk_client()
    return _client
