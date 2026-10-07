"""AI endpoints — data health, news, orders/decisions, journal, market
context, chart data, backtest, vision/statement ingest, training/status and
knowledge notes. See docs/AI_ROADMAP.md.

Push subscriptions, chat/RAG, model evals and portfolio-insight endpoints
(brief/hedge/forecast/factors/dividends/xray/stress/fi/tax-summary/optimize/
benchmark/weekly-review/monthly-report) live in routers/push.py, chat.py,
evals.py and insights.py respectively.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from app.dependencies import DbSession, RiskDep

router = APIRouter(prefix="/api/ai", tags=["ai"])


class DataHealthRead(BaseModel):
    stale: bool
    snapshot_age_hours: float | None
    confidence: str
    reasons: list[str]


@router.get("/data-health", response_model=DataHealthRead)
async def ai_data_health(db: DbSession) -> DataHealthRead:
    """Phase 13: freshness/confidence signal for chat & brief staleness banners."""
    from app.services.ai.data_health import data_health

    h = await data_health(db)
    return DataHealthRead(
        stale=h.stale,
        snapshot_age_hours=h.snapshot_age_hours,
        confidence=h.confidence,
        reasons=h.reasons,
    )


class HeadlineRead(BaseModel):
    title: str
    source: str
    published: str
    sentiment: float = 0.0


@router.get("/news", response_model=list[HeadlineRead])
async def ai_news(query: str, k: int = 5) -> list[HeadlineRead]:
    """Phase 8/17: recent headlines for a holding with per-headline sentiment."""
    from app.services.ai.news import get_headlines

    return [
        HeadlineRead(
            title=h.title, source=h.source, published=h.published, sentiment=h.sentiment
        )
        for h in await get_headlines(query, k=k)
    ]


class OrderDraftRead(BaseModel):
    symbol: str
    side: str
    quantity: float
    trigger_price: float
    est_proceeds: float
    threshold_met: bool
    gain: float
    est_ltcg_tax: float
    routing: list[dict]
    note: str


@router.get("/order-draft", response_model=OrderDraftRead | None)
async def ai_order_draft(symbol: str, db: DbSession) -> OrderDraftRead | None:
    """Phase 12/20: draft (never place) a tax-aware GTT sell. Human-in-loop."""
    from app.services.ai.order_draft import draft_sell_order

    d = await draft_sell_order(db, symbol)
    if d is None:
        return None
    return OrderDraftRead(
        symbol=d.symbol, side=d.side, quantity=d.quantity, trigger_price=d.trigger_price,
        est_proceeds=d.est_proceeds, threshold_met=d.threshold_met, gain=d.gain,
        est_ltcg_tax=d.est_ltcg_tax, routing=d.routing, note=d.note,
    )


@router.post("/critique")
async def ai_critique(db: DbSession, risk: RiskDep) -> dict[str, str | None]:
    """Phase 29: a risk-skeptic's counterpoints to the current action plan."""
    from app.services.ai.critique import critique_plan

    return {"critique": await critique_plan(db, risk)}


@router.get("/daily-plan")
async def ai_daily_plan(db: DbSession) -> dict:
    """Phase 28: the ranked 'do this today' plan (built by the nightly agent)."""
    from app.services.ai.action_agent import get_stored_plan

    return await get_stored_plan(db)


@router.post("/daily-plan/refresh")
async def ai_daily_plan_refresh(db: DbSession, risk: RiskDep) -> dict:
    """Rebuild the action plan on demand."""
    from app.services.ai.action_agent import build_and_store_plan

    return {"items": await build_and_store_plan(db, risk)}


@router.get("/earnings")
async def ai_earnings(db: DbSession) -> list[dict]:
    """Phase 38: upcoming earnings dates per stock holding (best-effort)."""
    from app.services.ai.earnings import earnings_calendar

    return await earnings_calendar(db)


@router.get("/timetravel/dates")
async def ai_timetravel_dates(db: DbSession) -> list[str]:
    """Phase 37: snapshot dates available to time-travel to."""
    from app.services.ai.timetravel import available_dates

    return await available_dates(db)


@router.get("/timetravel")
async def ai_timetravel(db: DbSession, date: str) -> dict | None:
    """The portfolio as of the latest snapshot on/before `date`."""
    from app.services.ai.timetravel import snapshot_as_of

    return await snapshot_as_of(db, date)


@router.get("/macro")
async def ai_macro(db: DbSession) -> dict:
    """Phase 36: macro indicators (rupee, crude, NIFTY, VIX) vs energy exposure."""
    from app.services.ai.macro import macro_dashboard

    return await macro_dashboard(db)


class DecisionCreate(BaseModel):
    action: str
    symbol: str | None = None
    note: str


class DecisionRead(BaseModel):
    id: int
    action: str
    symbol: str | None
    note: str
    at: str


@router.get("/decisions", response_model=list[DecisionRead])
async def ai_decisions(db: DbSession) -> list[DecisionRead]:
    """Phase 35: the decision journal (newest first)."""
    from app.services.ai.decisions import list_decisions

    return [
        DecisionRead(id=d.id, action=d.action, symbol=d.symbol, note=d.note, at=d.created_at.isoformat())
        for d in await list_decisions(db)
    ]


@router.post("/decisions", response_model=DecisionRead)
async def ai_add_decision(payload: DecisionCreate, db: DbSession) -> DecisionRead:
    """Log a decision (also ingested into RAG memory)."""
    from app.services.ai.decisions import add_decision

    d = await add_decision(db, payload.action, payload.symbol, payload.note)
    return DecisionRead(id=d.id, action=d.action, symbol=d.symbol, note=d.note, at=d.created_at.isoformat())


@router.get("/backtest")
async def ai_backtest(db: DbSession, threshold_pct: float = 10.0, window: str = "2y") -> dict:
    """Phase 54: backtest the +10% take-profit sell rule vs buy-and-hold."""
    from app.services.ai.backtest import backtest_sell_rule

    return await backtest_sell_rule(db, threshold_pct=threshold_pct, window=window)


@router.get("/chart")
async def ai_chart(db: DbSession, kind: str = "allocation") -> dict | None:
    """Phase 27: chart spec ({type,title,series}) for the chat to render inline."""
    from app.services.ai.chart_spec import build_chart

    return await build_chart(db, kind)


@router.post("/vision")
async def ai_vision(
    db: DbSession,
    file: UploadFile = File(...),
    prompt: str | None = Form(default=None),
) -> dict[str, str | None]:
    """Phase 48: read an uploaded chart/screenshot with the local vision model."""
    from app.services.ai.vision import analyze_image

    data = await file.read()
    result = await analyze_image(db, data, prompt)
    return {
        "result": result
        or "Vision unavailable — start the 3070 and `ollama pull llava`."
    }


@router.post("/upload-statement")
async def ai_upload_statement(
    db: DbSession,
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
) -> dict:
    """Phase 23: ingest a broker/CAS PDF's text into RAG (Pilot can then cite it)."""
    from app.services.ai.statement_ingest import ingest_statement

    data = await file.read()
    return await ingest_statement(db, file.filename or "statement.pdf", data, password)


class LoadedModel(BaseModel):
    name: str
    vram_gb: float


class AiStatus(BaseModel):
    model: str
    ollama_reachable: bool
    custom_model_present: bool = False
    loaded: list[LoadedModel] = []
    chunks_total: int
    chunks_embedded: int
    training_pairs: int
    pairs_since_train: int = 0
    retrain_recommended: bool = False
    last_memory_date: str | None = None
    training_generator_running: bool = False


@router.get("/status", response_model=AiStatus)
async def ai_status(db: DbSession) -> AiStatus:
    """Observability for the AI loops (RAG, memory, LoRA progress)."""
    from sqlalchemy import func, select

    from app.config import get_settings
    from app.models.chat_log import ChatExchange
    from app.models.knowledge import KnowledgeChunk
    from app.services.ai.providers import _ollama_reachable

    settings = get_settings()
    total = (await db.execute(select(func.count(KnowledgeChunk.id)))).scalar_one()
    embedded = (
        await db.execute(
            select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.embedding.is_not(None))
        )
    ).scalar_one()
    pairs = (await db.execute(select(func.count(ChatExchange.id)))).scalar_one()
    last_mem = (
        await db.execute(
            select(func.max(KnowledgeChunk.source)).where(
                KnowledgeChunk.source.like("portfolio/daily-%")
            )
        )
    ).scalar_one()
    from app.services.ai import train_runner
    from app.services.ai.training_state import get_baseline, retrain_recommended

    baseline = await get_baseline(db)
    pairs_since = max(0, pairs - baseline)

    reachable = bool(settings.ollama_url) and await _ollama_reachable(settings.ollama_url)
    custom = False
    loaded: list[LoadedModel] = []
    if reachable:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                base = settings.ollama_url.rstrip("/")
                resp = await client.get(f"{base}/api/tags")
                custom = any(
                    m.get("name", "").startswith("wealthpilot")
                    for m in resp.json().get("models", [])
                )
                ps = await client.get(f"{base}/api/ps")
                loaded = [
                    LoadedModel(
                        name=m.get("name", "?"),
                        vram_gb=round(m.get("size_vram", 0) / 1e9, 1),
                    )
                    for m in ps.json().get("models", [])
                ]
        except httpx.HTTPError:
            pass
    return AiStatus(
        custom_model_present=custom,
        loaded=loaded,
        model=settings.ollama_model if settings.ollama_url else (settings.ai_chat_model if settings.anthropic_api_key else "unconfigured"),
        ollama_reachable=reachable,
        chunks_total=total,
        chunks_embedded=embedded,
        training_pairs=pairs,
        pairs_since_train=pairs_since,
        retrain_recommended=retrain_recommended(pairs, baseline),
        last_memory_date=last_mem.removeprefix("portfolio/daily-") if last_mem else None,
        training_generator_running=train_runner.is_running(),
    )


class TrainRunRead(BaseModel):
    running: bool


@router.post("/train/start", response_model=TrainRunRead)
async def ai_train_start(
    target: int = 1000, concurrency: int = 4, model: str | None = None
) -> TrainRunRead:
    """Push work to the 3070: start the training-pair generator in the
    background. Each question is a real grounded chat call, so it's Ollama on
    the 3070 doing the inference. Safe to call again while already running —
    no-op, one run at a time."""
    from app.services.ai import train_runner

    train_runner.start(target=target, concurrency=concurrency, model=model)
    return TrainRunRead(running=True)


@router.post("/train/stop", response_model=TrainRunRead)
async def ai_train_stop() -> TrainRunRead:
    """Cancel the background training-pair generator, if one is running."""
    from app.services.ai import train_runner

    train_runner.stop()
    return TrainRunRead(running=False)


@router.get("/train/logs/stream")
async def ai_train_logs_stream():
    """SSE tail of the training generator's log output — the live terminal
    view on the AI panel. Replays recent history immediately on connect, then
    streams new lines as they're emitted; heartbeats keep the connection open
    through idle periods until the client disconnects."""
    from fastapi.responses import StreamingResponse

    from app.services.ai import train_log

    async def gen():
        for line in train_log.history():
            yield f"data: {line}\n\n"
        q = train_log.subscribe()
        try:
            while True:
                try:
                    line = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {line}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            train_log.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/mark-trained")
async def ai_mark_trained(db: DbSession) -> dict[str, int]:
    """Record the current pair count as the retrain baseline (call after a train)."""
    from sqlalchemy import func, select

    from app.models.chat_log import ChatExchange
    from app.services.ai.training_state import set_baseline

    pairs = (await db.execute(select(func.count(ChatExchange.id)))).scalar_one()
    return {"baseline_pairs": await set_baseline(db, pairs)}


class LearnResult(BaseModel):
    distilled: bool
    files: int
    chunks_added: int
    embedded: int


@router.post("/learn", response_model=LearnResult)
async def ai_learn(db: DbSession, risk: RiskDep) -> LearnResult:
    """Run the full learning loop on demand: distill today's portfolio into
    memory, sync the knowledge folder, embed everything the 3070 can."""
    from app.services.ai.distill import distill_daily
    from app.services.ai.rag import embed_pending, ingest_knowledge_dir

    from app.services.ai.insights import generate_insights

    distilled = await distill_daily(db, risk)
    stats = await ingest_knowledge_dir(db)
    embedded = await embed_pending(db, batch=256)
    await generate_insights(db, risk)
    return LearnResult(
        distilled=distilled,
        files=stats["files"],
        chunks_added=stats["chunks_added"],
        embedded=embedded,
    )


class InsightRead(BaseModel):
    id: int
    text: str
    severity: str = "info"
    source: str = "model"


@router.get("/insights", response_model=list[InsightRead])
async def ai_insights(db: DbSession) -> list[InsightRead]:
    from app.services.ai.insights import current_insights

    return [
        InsightRead(id=i.id, text=i.text, severity=i.severity, source=i.source)
        for i in await current_insights(db)
    ]


@router.post("/insights/{insight_id}/dismiss")
async def dismiss_insight(insight_id: int, db: DbSession) -> dict[str, str]:
    from sqlalchemy import update

    from app.models.ai_insight import AiInsight

    await db.execute(
        update(AiInsight).where(AiInsight.id == insight_id).values(dismissed=True)
    )
    await db.commit()
    return {"status": "ok"}


class KnowledgeNote(BaseModel):
    title: str
    content: str


@router.post("/knowledge")
async def save_knowledge(note: KnowledgeNote, db: DbSession) -> dict[str, str]:
    """User-approved note into the knowledge base (embeds when the 3070 can)."""
    import re

    from app.models.knowledge import KnowledgeChunk
    from app.services.ai.rag import embed_pending

    slug = re.sub(r"[^a-z0-9]+", "-", note.title.lower()).strip("-")[:60] or "note"
    db.add(
        KnowledgeChunk(
            source=f"user-notes/{slug}",
            title=note.title[:256],
            chunk_index=0,
            content=note.content[:4000],
        )
    )
    await db.commit()
    await embed_pending(db, batch=8)
    return {"status": "ok", "source": f"user-notes/{slug}"}
