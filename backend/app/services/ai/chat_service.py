"""Ask WealthPilot (Phase 2): tool-use chat over the portfolio.

Claude drives read-only tools backed by the same services the UI uses — the
model narrates and reasons, the engine/DB supply every number. Tool use needs
the Anthropic API; a reachable Ollama alone gets a plain RAG-grounded answer
(local 8B models are not reliable tool callers).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.ai.chat_tools import run_tool as _run_tool
from app.services.ai.providers import _ollama_reachable, normalize_followups, strip_reasoning
from app.services.ai.rag import hybrid_retrieve
from app.services.ai.routing import pick_model
from app.services.risk import BaseRiskClient

logger = logging.getLogger("wealthpilot.ai")

_SYSTEM = (
    "You are Pilot, the owner's portfolio copilot. Speak in first person, "
    "calm and specific. Answer using ONLY numbers from your tools/context — "
    "never invent figures. Amounts are INR. Cite what supports each claim. "
    "For compound questions (e.g. rebalancing across goals, 'get everything to "
    "75%'), plan the steps, call the tools you need one at a time, use each "
    "result to decide the next, then synthesize one clear recommendation. "
    "Informational analysis, not licensed financial advice. When you use a "
    "knowledge result, cite the bracketed [source] you drew from. End every reply "
    "with exactly one line: FOLLOW-UPS: q1 | q2 | q3 — three short questions "
    "the owner would naturally ask next."
)


def _system_with_screen(screen: str | None) -> str:
    if not screen:
        return _SYSTEM
    return _SYSTEM + f"\nThe owner is currently viewing the {screen} page."

_TOOLS = [
    {
        "name": "get_portfolio",
        "description": "Current holdings, cash, totals and per-holding P&L.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_risk",
        "description": "Historical VaR/CVaR, annualized volatility, max drawdown, per-bucket risk contributions.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_diversification",
        "description": "Effective holdings, diversification ratio, most-correlated pairs.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_issues",
        "description": "Detected portfolio issues (concentration, allocation drift, etc.).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_goals",
        "description": "The user's goals: targets, deadlines, SIPs, latest success probability.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "simulate_goal",
        "description": "Run a Monte Carlo what-if for a goal. Optional overrides: monthly_contribution (INR/mo), target_value (INR), shock_pct (one-time market crash at t=0, e.g. 30 for -30%).",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Goal name or key, e.g. 'travel'"},
                "monthly_contribution": {"type": "number"},
                "target_value": {"type": "number"},
                "shock_pct": {"type": "number"},
            },
            "required": ["goal"],
        },
    },
    {
        "name": "required_sip",
        "description": "Solve the monthly SIP needed for a goal to reach a target success probability (default 0.75). Use for 'what SIP gets X to 75%' and multi-goal rebalancing plans.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "target_probability": {"type": "number", "description": "0-1, default 0.75"},
            },
            "required": ["goal"],
        },
    },
    {
        "name": "search_knowledge",
        "description": "Search the finance/portfolio knowledge base (tax rules, risk concepts, plan principles).",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "find_similar_days",
        "description": "Find past days when this portfolio looked similar (risk/allocation/mood) to compare with now. Use for 'has this happened before', 'how did we recover', historical-analogue questions.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "situation to match, e.g. 'high VaR, energy heavy'"}},
        },
    },
    {
        "name": "get_news",
        "description": "Recent news headlines for a holding (free feed). Use when deciding whether to sell now / 'what's happening with X'. Context only — headlines are not advice.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "company or ticker, e.g. 'NMDC' or 'ONGC'"}},
            "required": ["query"],
        },
    },
    {
        "name": "optimize_portfolio",
        "description": "Suggest a risk-balanced (inverse-volatility) target allocation across asset classes and the rebalance to reach it. Use for 'how should I rebalance', 'reduce my risk', 'optimal allocation'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "draft_sell_order",
        "description": "Draft (never place) the GTT sell-order params for a held stock: quantity, +10% trigger price, estimated proceeds, gain, LTCG tax, and 65/25/10 routing. Use for 'how would I sell X' / 'set up the order'. The owner reviews and places it themselves.",
        "input_schema": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "stock ticker, e.g. 'NMDC'"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "tax_impact",
        "description": "Estimate the tax on realizing stock gains (LTCG vs STCG, ₹1.25L exemption) and list tax-loss-harvest candidates. Use for 'what's my tax if I sell', 'tax on the sell plan'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "benchmark",
        "description": "Compare the portfolio's recent return against NIFTY 50 (alpha). Use for 'am I beating the index', 'how vs NIFTY'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "earnings_calendar",
        "description": "Upcoming earnings dates for your stock holdings. Use for 'when do my stocks report', 'earnings coming up'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "macro",
        "description": "Macro indicators (rupee, crude, NIFTY, India VIX) and how they relate to your energy exposure. Use for 'what's crude doing', 'macro picture'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "forecast",
        "description": "Near-term volatility forecast (EWMA) + recent momentum for the portfolio. NOT a price prediction. Use for 'how volatile', 'what's the trend'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "hedge",
        "description": "Protective-put hedge sizing (NIFTY put lots + estimated premium) for the equity exposure. Use for 'how do I hedge', 'protect my downside'. Heuristic, not a live quote.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "recall_decisions",
        "description": "Recall the owner's past decisions and their reasoning (sold X because…, paused a SIP…). Use for 'why did I sell', 'what have I decided before'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "dividend_forecast",
        "description": "Estimated annual + monthly dividend income from dividend-bucket holdings (assumed yield). Use for 'how much dividend income', 'passive income'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "portfolio_xray",
        "description": "True asset-class exposure across everything (direct stocks vs via-funds). Use for 'real equity exposure', 'what's inside my funds'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "stress_scenario",
        "description": "Sector-aware stress test. scenario: 'energy' (crude shock), 'market' (broad crash), 'rates', 'gold'. Use for 'what if oil crashes', 'stress my portfolio'.",
        "input_schema": {
            "type": "object",
            "properties": {"scenario": {"type": "string", "enum": ["energy", "market", "rates", "gold"]}},
        },
    },
    {
        "name": "fi_projection",
        "description": "Whole-portfolio retirement (FI) Monte Carlo + safe-withdrawal income, inflation-adjusted. target_corpus is in TODAY'S purchasing power. Optional: years, target_corpus (INR), monthly_contribution, swr (e.g. 0.035), inflation (default 0.06, floored at 0.06), post_selloff (true = model the legacy dividend basket already sold and reinvested as equity). Use for 'can I retire', 'how much can I withdraw', 'what's it worth in today's money'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "years": {"type": "number"},
                "target_corpus": {"type": "number"},
                "monthly_contribution": {"type": "number"},
                "swr": {"type": "number"},
                "inflation": {"type": "number"},
                "post_selloff": {"type": "boolean"},
            },
        },
    },
    {
        "name": "make_chart",
        "description": "Render a chart of the portfolio. kind: 'allocation' (donut by asset class), 'holdings' (top by value), 'pnl' (gains/losses). Use for 'show/chart/visualize'. Include the returned [[chart:KIND]] marker in your reply so the UI draws it.",
        "input_schema": {
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": ["allocation", "holdings", "pnl"]}},
        },
    },
]

_MAX_TOOL_ROUNDS = 8  # deeper chains for multi-step agentic planning (Phase 18)


@dataclass
class ChatResult:
    status: str  # "ok" | "unconfigured"
    reply: str | None = None
    tools_used: list[str] = field(default_factory=list)


async def chat(
    message: str,
    history: list[dict],
    db: AsyncSession,
    risk_client: BaseRiskClient,
    screen: str | None = None,
) -> ChatResult:
    settings = get_settings()

    if not settings.anthropic_api_key:
        # No API key (Claude Pro has no API access): run the SAME tool loop
        # through Ollama's native tool-calling (llama3.1 / qwen2.5 support it).
        if settings.ollama_url and await _ollama_reachable(settings.ollama_url):
            return await _chat_via_ollama(message, history, db, risk_client, screen)
        return ChatResult(status="unconfigured")

    messages = [*history, {"role": "user", "content": message}]
    tools_used: list[str] = []

    async with httpx.AsyncClient(
        base_url="https://api.anthropic.com",
        timeout=120.0,
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    ) as client:
        for _ in range(_MAX_TOOL_ROUNDS + 1):
            resp = await client.post(
                "/v1/messages",
                json={
                    "model": settings.ai_chat_model,
                    "max_tokens": 1500,
                    "system": _system_with_screen(screen),
                    "tools": _TOOLS,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", [])
            if data.get("stop_reason") != "tool_use":
                text = "".join(
                    b.get("text", "") for b in content if b.get("type") == "text"
                )
                return ChatResult(status="ok", reply=text.strip(), tools_used=tools_used)

            messages.append({"role": "assistant", "content": content})
            results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                tools_used.append(block["name"])
                try:
                    out = await _run_tool(
                        block["name"], block.get("input", {}), db, risk_client
                    )
                except Exception as exc:  # noqa: BLE001 — surface to the model
                    out = f"Tool error: {exc}"
                    logger.exception("chat tool %s failed", block["name"])
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": json.dumps(out) if not isinstance(out, str) else out,
                    }
                )
            messages.append({"role": "user", "content": results})

    return ChatResult(
        status="ok",
        reply="I hit the tool-call limit before finishing — try a narrower question.",
        tools_used=tools_used,
    )


def _openai_tools() -> list[dict]:
    """Ollama consumes OpenAI-style tool schemas; convert from Anthropic's."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in _TOOLS
    ]


async def _gather_context(
    message: str, db: AsyncSession, risk_client: BaseRiskClient
) -> str:
    """Precompute the numbers a local model needs — it must never invent them."""
    parts = []
    for tool in ("get_portfolio", "get_risk", "get_diversification", "get_issues"):
        try:
            parts.append(f"[{tool}]\n" + await _run_tool(tool, {}, db, risk_client))
        except Exception:  # noqa: BLE001
            logger.exception("context tool %s failed", tool)
    hits = await hybrid_retrieve(db, message, k=3)
    if hits:
        parts.append("[knowledge]\n" + "\n---\n".join(h.content[:600] for h in hits))
    return "\n\n".join(parts)


async def _chat_via_ollama(
    message: str,
    history: list[dict],
    db: AsyncSession,
    risk_client: BaseRiskClient,
    screen: str | None = None,
) -> ChatResult:
    settings = get_settings()
    # Local models (even ones declaring tool support, like deepseek-r1) can
    # ignore tools and hallucinate — so the real numbers ride in the system
    # prompt, and tools remain available for what-ifs (simulate_goal).
    context = await _gather_context(message, db, risk_client)
    system = (
        _system_with_screen(screen)
        + "\nCurrent portfolio data (authoritative — use these numbers):\n"
        + context
        + "\nIf the data above lacks the answer, say so instead of guessing."
    )
    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": message},
    ]
    tools_used: list[str] = []

    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=180.0) as client:
        for _ in range(_MAX_TOOL_ROUNDS + 1):
            resp = await client.post(
                "/api/chat",
                json={
                    "model": pick_model(message),
                    "messages": messages,
                    "tools": _openai_tools(),
                    "stream": False,
                    "keep_alive": -1,
                    "options": {"num_ctx": 8192},
                },
            )
            if resp.status_code == 400:
                # Model without tool support (e.g. deepseek-r1): answer with
                # portfolio + RAG context injected instead of tool calls.
                return await _ollama_plain(client, message, db, risk_client)
            resp.raise_for_status()
            msg = resp.json().get("message", {})
            calls = msg.get("tool_calls") or []
            if not calls:
                return ChatResult(
                    status="ok",
                    reply=normalize_followups(strip_reasoning(str(msg.get("content", "")))),
                    tools_used=tools_used,
                )
            messages.append(msg)
            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                tools_used.append(name)
                raw_args = fn.get("arguments") or {}
                if isinstance(raw_args, str):
                    try:
                        raw_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        raw_args = {}
                try:
                    out = await _run_tool(name, raw_args, db, risk_client)
                except Exception as exc:  # noqa: BLE001 — surface to the model
                    out = f"Tool error: {exc}"
                    logger.exception("ollama chat tool %s failed", name)
                messages.append({"role": "tool", "content": out})

    return ChatResult(
        status="ok",
        reply="I hit the tool-call limit — try a narrower question.",
        tools_used=tools_used,
    )


async def _ollama_plain(
    client: httpx.AsyncClient,
    message: str,
    db: AsyncSession,
    risk_client: BaseRiskClient,
) -> ChatResult:
    """Tools-free path: ground the local model with precomputed context."""
    parts = []
    for tool in ("get_portfolio", "get_risk", "get_diversification"):
        try:
            parts.append(f"[{tool}]\n" + await _run_tool(tool, {}, db, risk_client))
        except Exception:  # noqa: BLE001
            logger.exception("context tool %s failed", tool)
    hits = await hybrid_retrieve(db, message, k=3)
    if hits:
        parts.append("[knowledge]\n" + "\n---\n".join(h.content[:600] for h in hits))
    settings = get_settings()
    resp = await client.post(
        "/api/chat",
        json={
            "keep_alive": -1,
            "options": {"num_ctx": 8192},
            "model": pick_model(message),
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": "Context:\n" + "\n\n".join(parts) + f"\n\nQuestion: {message}",
                },
            ],
            "stream": False,
        },
    )
    resp.raise_for_status()
    reply = normalize_followups(strip_reasoning(str(resp.json().get("message", {}).get("content", ""))))
    return ChatResult(status="ok", reply=reply, tools_used=["context-injected"])


async def stream_chat_ollama(
    message: str,
    history: list[dict],
    db: AsyncSession,
    risk_client: BaseRiskClient,
    screen: str | None = None,
):
    """SSE generator: grounded Ollama chat with think-phase tracking.

    Yields ("phase", "thinking"|"answering") and ("token", text) tuples; the
    caller formats SSE. R1 wraps reasoning in <think>…</think> — we track the
    boundary, suppress think content, and only stream the real answer.
    """
    settings = get_settings()
    context = await _gather_context(message, db, risk_client)
    system = (
        _system_with_screen(screen)
        + "\nCurrent portfolio data (authoritative — use these numbers):\n"
        + context
        + "\nIf the data above lacks the answer, say so instead of guessing."
    )
    messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": message}]

    reply_parts: list[str] = []
    in_think = False
    started = False
    buffer = ""
    yield ("phase", "thinking")

    async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=300.0) as client:
        async with client.stream(
            "POST",
            "/api/chat",
            json={"model": pick_model(message), "messages": messages, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                piece = chunk.get("message", {}).get("content", "")
                if not piece:
                    continue
                buffer += piece
                # Strip <think> blocks on the fly.
                while buffer:
                    if in_think:
                        end = buffer.find("</think>")
                        if end == -1:
                            buffer = buffer[-8:]  # keep tail in case tag splits
                            break
                        buffer = buffer[end + 8 :]
                        in_think = False
                    else:
                        start = buffer.find("<think>")
                        if start == -1:
                            emit = buffer
                            buffer = ""
                        else:
                            emit = buffer[:start]
                            buffer = buffer[start + 7 :]
                            in_think = True
                        if emit:
                            if not started and emit.strip():
                                started = True
                                yield ("phase", "answering")
                            if started:
                                reply_parts.append(emit)
                                yield ("token", emit)

    reply = normalize_followups("".join(reply_parts).strip())
    # Send the cleaned reply so the client can replace the raw stream (drops any
    # literal FOLLOW-UPS placeholder the fine-tuned model emitted mid-stream).
    yield ("final", reply)
    if reply:
        from app.models.chat_log import ChatExchange

        db.add(
            ChatExchange(
                question=message, reply=reply, provider="ollama", tools_used="context-injected"
            )
        )
        await db.commit()
