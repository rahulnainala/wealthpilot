"""Phase 35 — decision journal + episodic memory.

Records why the owner acted (sold X because…, paused a SIP…) and also ingests
each entry into the RAG corpus (`portfolio/decisions/*`) so chat/brief can
reference past choices — advice that remembers your reasoning over time.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision import Decision
from app.models.knowledge import KnowledgeChunk


async def add_decision(
    db: AsyncSession, action: str, symbol: str | None, note: str
) -> Decision:
    row = Decision(action=action.strip()[:64], symbol=(symbol or None), note=note.strip())
    db.add(row)
    await db.commit()
    await db.refresh(row)

    # Mirror into RAG so it's retrievable by chat/brief.
    tag = f"{action} {symbol or ''}".strip()
    content = f"Decision on {date.today().isoformat()}: {tag} — {note.strip()}"
    db.add(
        KnowledgeChunk(
            source=f"portfolio/decisions/{row.id}",
            title=f"Decision: {tag}",
            chunk_index=0,
            content=content,
        )
    )
    await db.commit()

    from app.services.ai.rag import embed_pending

    await embed_pending(db, batch=8)
    return row


async def list_decisions(db: AsyncSession, limit: int = 50) -> list[Decision]:
    rows = (
        await db.execute(select(Decision).order_by(Decision.id.desc()).limit(limit))
    ).scalars()
    return list(rows)
