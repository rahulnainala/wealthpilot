"""Chat + RAG endpoints, split out of ai.py (Phase 2/25). See docs/AI_ROADMAP.md."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import DbSession, RiskDep

router = APIRouter(prefix="/api/ai", tags=["ai"])


class IngestResult(BaseModel):
    files: int
    chunks_added: int
    embedded: int


@router.post("/ingest", response_model=IngestResult)
async def ai_ingest(db: DbSession) -> IngestResult:
    """Sync the knowledge folder into the RAG store, then embed what we can."""
    from app.services.ai.rag import embed_pending, ingest_knowledge_dir

    stats = await ingest_knowledge_dir(db)
    embedded = await embed_pending(db)
    return IngestResult(files=stats["files"], chunks_added=stats["chunks_added"], embedded=embedded)


class SearchHit(BaseModel):
    source: str
    title: str
    content: str


@router.get("/search", response_model=list[SearchHit])
async def ai_search(db: DbSession, q: str) -> list[SearchHit]:
    """Hybrid RAG retrieval (vector + keyword; works even when the 3070 is off)."""
    from app.services.ai.rag import hybrid_retrieve

    hits = await hybrid_retrieve(db, q)
    return [SearchHit(source=h.source, title=h.title, content=h.content[:600]) for h in hits]


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = []
    screen: str | None = None


class ChatResponse(BaseModel):
    status: str
    reply: str | None = None
    tools_used: list[str] = []


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(req: ChatRequest, db: DbSession, risk: RiskDep) -> ChatResponse:
    """Ask WealthPilot: tool-use chat grounded in engine-computed numbers."""
    from app.services.ai.chat_service import chat

    result = await chat(
        req.message,
        [t.model_dump() for t in req.history[-10:]],
        db,
        risk,
        screen=req.screen,
    )
    if result.status == "ok" and result.reply:
        from app.config import get_settings
        from app.models.chat_log import ChatExchange

        settings = get_settings()
        db.add(
            ChatExchange(
                question=req.message,
                reply=result.reply,
                provider="anthropic" if settings.anthropic_api_key else "ollama",
                tools_used=",".join(result.tools_used)[:512],
            )
        )
        await db.commit()
    return ChatResponse(status=result.status, reply=result.reply, tools_used=result.tools_used)


@router.get("/training-data")
async def training_data(db: DbSession, grounded: bool = True) -> list[dict]:
    """Accumulated Q&A pairs in chat-tuning shape (LoRA input).

    Phase 25: with grounded=true (default) each example is prefixed with the
    grounding system prompt, so the next fine-tune explicitly learns to answer
    from provided numbers, cite sources, and keep a clean FOLLOW-UPS trailer —
    a RAG-grounded model rather than a free-associating one.

    Export with: curl '.../api/ai/training-data' | jq -c '.[]' > train.jsonl
    """
    from sqlalchemy import select

    from app.models.chat_log import ChatExchange
    from app.services.ai.chat_service import _SYSTEM

    rows = (await db.execute(select(ChatExchange).order_by(ChatExchange.id))).scalars()
    out: list[dict] = []
    for r in rows:
        messages = [{"role": "user", "content": r.question}, {"role": "assistant", "content": r.reply}]
        if grounded:
            messages.insert(0, {"role": "system", "content": _SYSTEM})
        out.append(
            {
                "messages": messages,
                "meta": {"provider": r.provider, "tools": r.tools_used, "ts": str(r.created_at)},
            }
        )
    return out


@router.post("/chat/stream")
async def ai_chat_stream(req: ChatRequest, db: DbSession, risk: RiskDep):
    """SSE token stream (Ollama only). Events: phase, token, final, done, error."""
    from fastapi.responses import StreamingResponse

    from app.config import get_settings
    from app.services.ai.chat_service import stream_chat_ollama
    from app.services.ai.providers import _ollama_reachable

    settings = get_settings()

    async def gen():
        if not settings.ollama_url or not await _ollama_reachable(settings.ollama_url):
            yield "event: error\ndata: unconfigured\n\n"
            return
        try:
            async for kind, payload in stream_chat_ollama(
                req.message, [t.model_dump() for t in req.history[-10:]], db, risk, screen=req.screen
            ):
                data = payload.replace("\n", "\\n")
                yield f"event: {kind}\ndata: {data}\n\n"
            yield "event: done\ndata: ok\n\n"
        except Exception:  # noqa: BLE001
            yield "event: error\ndata: stream-failed\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/history", response_model=list[ChatTurn])
async def chat_history(db: DbSession, limit: int = 10) -> list[ChatTurn]:
    """Recent exchanges, oldest first, as chat turns (Pilot remembers)."""
    from sqlalchemy import select

    from app.models.chat_log import ChatExchange

    rows = (
        (
            await db.execute(
                select(ChatExchange).order_by(ChatExchange.id.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    turns: list[ChatTurn] = []
    for r in reversed(rows):
        turns.append(ChatTurn(role="user", content=r.question))
        turns.append(ChatTurn(role="assistant", content=r.reply))
    return turns
