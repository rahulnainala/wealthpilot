"""Phase 11 — A/B eval: score wealthpilot vs a base model on fixed questions.

Runs the SAME grounded chat path for each model (temporary per-run override of
settings.ollama_model, exactly like generate_training) and scores each answer
with cheap, objective heuristics — grounding (cites a number), clean FOLLOW-UPS
trailer, plausible length. Prints a side-by-side so you can see the fine-tune
actually earns its keep before committing a retrain.

    docker compose exec backend python scripts/eval_models.py --base qwen2.5:7b
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys

sys.path.insert(0, "/app")

QUESTIONS = [
    "What is my single biggest risk right now?",
    "Which holding is closest to the +10% sell threshold?",
    "Am I on track for my goals?",
    "How diversified is my portfolio, really?",
    "Explain my VaR in one line.",
    "What should I do this week?",
]
_SCAFFOLD = re.compile(r"q1\s*\|\s*q2|three short question|naturally ask", re.IGNORECASE)


def _score(reply: str) -> tuple[int, dict]:
    grounded = bool(re.search(r"[₹\d]", reply))
    clean = not _SCAFFOLD.search(reply)
    has_followups = "FOLLOW-UPS:" in reply
    length_ok = 40 <= len(reply) <= 1200
    checks = {"grounded": grounded, "clean": clean, "followups": has_followups, "length": length_ok}
    return sum(checks.values()), checks


async def _run(model: str, db, risk) -> tuple[int, int]:
    from app.config import get_settings
    from app.services.ai.chat_service import chat

    get_settings().ollama_model = model
    total = 0
    for q in QUESTIONS:
        res = await chat(q, [], db, risk)
        reply = (res.reply or "") if res.status == "ok" else ""
        s, checks = _score(reply)
        total += s
        flags = "".join(k[0].upper() if v else "·" for k, v in checks.items())
        print(f"  [{model}] {s}/4 {flags}  {q[:44]}")
    return total, len(QUESTIONS) * 4


async def main(candidate: str, base: str) -> None:
    from app.db import get_sessionmaker
    from app.services.risk import build_risk_client

    risk = build_risk_client()
    try:
        async with get_sessionmaker()() as db:
            print(f"=== {candidate} ===")
            c_score, c_max = await _run(candidate, db, risk)
            print(f"=== {base} ===")
            b_score, b_max = await _run(base, db, risk)
    finally:
        await risk.close()

    print("\n--- RESULT ---")
    print(f"{candidate}: {c_score}/{c_max}")
    print(f"{base}: {b_score}/{b_max}")
    verdict = (
        f"{candidate} wins" if c_score > b_score
        else f"{base} wins" if b_score > c_score
        else "tie"
    )
    print(f"verdict: {verdict}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default="wealthpilot")
    ap.add_argument("--base", default="qwen2.5:7b")
    args = ap.parse_args()
    asyncio.run(main(args.candidate, args.base))
