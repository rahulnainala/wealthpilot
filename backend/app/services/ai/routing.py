"""Phase 45 — multi-model routing.

Picks which local model answers a chat turn: the fast fine-tune (`OLLAMA_MODEL`,
usually wealthpilot) for everyday questions, and an optional bigger model
(`OLLAMA_HEAVY_MODEL`) for complex/agentic ones. Opt-in: if no heavy model is
configured, everything stays on the primary — no behaviour change.
"""

from __future__ import annotations

from app.config import get_settings

_HEAVY_TRIGGERS = (
    "rebalance", "optimize", "compare", "backtest", "should i", "across all",
    "multi-goal", "every goal", "factor", "scenario", "strategy", "trade-off",
    "tradeoff", "step by step", "plan for",
)


def pick_model(message: str) -> str:
    settings = get_settings()
    heavy = settings.ollama_heavy_model
    if not heavy:
        return settings.ollama_model
    m = (message or "").lower()
    if len(message) > 200 or any(t in m for t in _HEAVY_TRIGGERS):
        return heavy
    return settings.ollama_model
