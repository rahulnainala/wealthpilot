"""Phase 17 — lightweight financial news sentiment.

A compact bull/bear lexicon scores each headline in [-1, +1] and aggregates to a
per-holding mood. Deliberately heuristic (not an LLM call per headline): instant,
deterministic, and works with the 3070 off — the right trade-off for scoring many
headlines to sharpen sell timing. Mood is a signal, not advice.
"""

from __future__ import annotations

import re

_BULL = {
    "surge", "surges", "jump", "jumps", "jumped", "gain", "gains", "rise", "rises",
    "rose", "beat", "beats", "record", "high", "growth", "profit", "profits",
    "approve", "approves", "approved", "win", "wins", "upgrade", "upgraded",
    "outperform", "rally", "rallies", "strong", "boost", "expansion", "dividend",
    "buyback", "order", "orders", "deal", "positive", "soar", "soars", "top", "tops",
}
_BEAR = {
    "fall", "falls", "fell", "drop", "drops", "dropped", "plunge", "plunges",
    "slump", "slumps", "loss", "losses", "miss", "misses", "weak", "cut", "cuts",
    "downgrade", "downgraded", "decline", "declines", "probe", "fraud", "ban",
    "penalty", "warning", "concern", "concerns", "risk", "risks", "debt", "default",
    "layoff", "layoffs", "negative", "crash", "selloff", "sink", "sinks", "worry",
}


def score(text: str) -> float:
    """Signed sentiment of one headline in [-1, +1]; 0 when neutral/unknown."""
    words = re.findall(r"[a-z']+", text.lower())
    bull = sum(w in _BULL for w in words)
    bear = sum(w in _BEAR for w in words)
    if bull + bear == 0:
        return 0.0
    return round((bull - bear) / (bull + bear), 2)


def mood(scores: list[float]) -> tuple[str, float]:
    """Aggregate label + mean score for a set of headline sentiments."""
    if not scores:
        return ("neutral", 0.0)
    avg = round(sum(scores) / len(scores), 2)
    label = "positive" if avg > 0.15 else "negative" if avg < -0.15 else "neutral"
    return (label, avg)
