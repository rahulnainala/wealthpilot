"""Self-generate LoRA training pairs through the real grounded pipeline.

Builds a large bank of varied, realistic questions from the live portfolio
(symbols, goals) and the finance corpus topics, then asks Pilot each one via
the normal chat path — answers are grounded in real data + RAG and logged to
chat_exchanges automatically. Resumable: already-asked questions are skipped,
and the run stops cleanly when Ollama is unreachable.

Lives in ``app.services`` (rather than only as a script) so it can be started
from a FastAPI route as a background task — see ``train_runner.py`` for the
in-process singleton that owns the asyncio.Task, and the ``/api/ai/train/*``
endpoints. ``scripts/generate_training.py`` is a thin CLI wrapper around
:func:`run_generation` for the original detached-container workflow.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import random

log = logging.getLogger("traingen")

SYMBOL_TEMPLATES = [
    "Should I sell {s} now or wait for the +10% threshold?",
    "How risky is my {s} position right now?",
    "What does {s} contribute to my concentration risk?",
    "If {s} drops 15% tomorrow, what happens to my portfolio?",
    "Explain my P&L on {s} and what would make you change view on it.",
    "How correlated is {s} with the rest of my holdings?",
]
GOAL_TEMPLATES = [
    "Am I on track for the {g} goal?",
    "Simulate the {g} goal with a 30 percent crash at the start.",
    "What monthly SIP would get {g} to 90% success odds?",
    "What happens to {g} if I pause SIPs for six months?",
    "When should I start de-risking the {g} goal and into what?",
]
PORTFOLIO_QUESTIONS = [
    "What is my biggest risk right now?",
    "Summarize my portfolio in three sentences.",
    "Why is my VaR at its current level and what drives it?",
    "Is my diversification actually good, or just many tickers?",
    "What changed in my portfolio since yesterday?",
    "What is the single most useful action I can take this week?",
    "How exposed am I to a PSU-energy sector shock?",
    "Explain my max drawdown and whether it should worry me.",
    "How does my cash position affect my risk?",
    "If markets fall 20% next month, walk me through the damage.",
    "Which holding deserves to be sold first and why?",
    "How is my allocation versus the one-third target split?",
]
KNOWLEDGE_QUESTIONS = [
    "How are REIT distributions taxed in India?",
    "Why do we use arbitrage funds for de-risking goals?",
    "Explain LTCG rules on equity for this financial year.",
    "What is CVaR and why does it matter more than VaR?",
    "Why prefer direct plans over regular mutual fund plans?",
    "What is the difference between XIRR and CAGR?",
    "When should ELSS get new money and when not?",
    "How do GTT orders help execute a sell plan?",
    "What did the 2008 crash do to Indian markets and how long was recovery?",
    "Why does the plan gate investing behind Phase 0?",
    "How much health insurance cover should I hold?",
    "What is sequence-of-returns risk and how do we defend against it?",
    "Why does SIP discipline beat market timing?",
    "What is the effective holdings number and why is mine what it is?",
    "How should proceeds from legacy stock sales be routed?",
    "What is a diversification ratio and what is a healthy value?",
    "Explain the difference between duration risk and credit risk.",
    "Are SGBs better than gold ETFs? Why?",
    "What behavioral bias is most dangerous for my sell plan?",
    "How big should my emergency fund be and where should it live?",
]
STYLES = [
    "",
    " Keep it to two sentences.",
    " Explain like I'm new to investing.",
    " Be specific with numbers.",
    " What would you do in my position?",
    " Give me the risks first, then the upside.",
    " Answer as a checklist I can act on.",
    " Compare it against the plan's rules.",
]


async def run_generation(target: int, concurrency: int, model: str | None) -> None:
    from sqlalchemy import func, select

    from app.config import get_settings
    from app.db import get_sessionmaker
    from app.models.chat_log import ChatExchange
    from app.services.ai.chat_service import chat
    from app.services.ai.providers import _ollama_reachable
    from app.services.analytics_service import latest_holding_views, load_goal_views
    from app.services.risk import build_risk_client

    settings = get_settings()
    if model:
        # Generator-only override (this process only; the API keeps its model).
        settings.ollama_model = model
        log.info("generator model override: %s", model)
    risk = build_risk_client()
    sm = get_sessionmaker()
    gate = asyncio.Semaphore(concurrency)

    async with sm() as db:
        data = await latest_holding_views(db)
        symbols = [h.symbol for h in (data[0] if data else []) if h.type.value == "stock"]
        goals = [g.name for g in await load_goal_views(db)]
        asked = set((await db.execute(select(ChatExchange.question))).scalars().all())

    bank: list[str] = []
    for t, s in itertools.product(SYMBOL_TEMPLATES, symbols):
        bank.append(t.format(s=s))
    for t, g in itertools.product(GOAL_TEMPLATES, goals):
        bank.append(t.format(g=g))
    bank.extend(PORTFOLIO_QUESTIONS)
    bank.extend(KNOWLEDGE_QUESTIONS)
    # Style variants multiply coverage with natural phrasing differences.
    styled = [q + st for q in bank for st in STYLES]
    rng = random.Random(42)
    rng.shuffle(styled)
    queue = [q for q in styled if q not in asked]
    log.info("bank=%d unasked=%d target=%d", len(styled), len(queue), target)

    done = 0
    stop = asyncio.Event()

    async def current_count() -> int:
        async with sm() as db:
            return (await db.execute(select(func.count(ChatExchange.id)))).scalar_one()

    async def worker(q: str) -> None:
        nonlocal done
        async with gate:
            if stop.is_set():
                return
            n = await current_count()
            if n >= target:
                if not stop.is_set():
                    stop.set()
                    log.info("target reached: %d pairs", n)
                    from app.models.ai_insight import AiInsight

                    async with sm() as db:
                        exists = (
                            await db.execute(
                                select(AiInsight).where(
                                    AiInsight.text.like("Training dataset complete%")
                                )
                            )
                        ).first()
                        if exists:
                            return
                        db.add(
                            AiInsight(
                                text=(
                                    f"Training dataset complete: {n} pairs collected. "
                                    "Run auto_train.py on the 3070 "
                                    "(or ai-training/README.md) to build wealthpilot."
                                )
                            )
                        )
                        await db.commit()
                return
            # PC asleep? Wait patiently and resume — never die.
            while not (settings.ollama_url and await _ollama_reachable(settings.ollama_url)):
                log.info("ollama unreachable — waiting (PC asleep?) …")
                await asyncio.sleep(120)
            try:
                async with sm() as db:
                    result = await chat(q, [], db, risk)
                    if result.status == "ok" and result.reply:
                        db.add(
                            ChatExchange(
                                question=q,
                                reply=result.reply,
                                provider="ollama",
                                tools_used=",".join(result.tools_used)[:512] or "context-injected",
                            )
                        )
                        await db.commit()
                done += 1
                log.info("[+%d] %s -> %d chars", done, q[:60], len(result.reply or ""))
            except Exception as exc:  # noqa: BLE001 — log and continue
                log.warning("failed %r: %s", q[:60], exc)
                await asyncio.sleep(5)

    try:
        # Launch in waves of `concurrency` so parallel sequences batch on the GPU.
        for i in range(0, len(queue), concurrency):
            if stop.is_set():
                break
            await asyncio.gather(*(worker(q) for q in queue[i : i + concurrency]))
    finally:
        await risk.close()
        log.info("run finished (%d generated this session)", done)
