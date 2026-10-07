"""Phase 13 — data freshness / confidence signal.

Pilot should not sound equally sure when the numbers are stale. This computes a
cheap, honest freshness read — how old the latest snapshot is and whether RAG
embedding is behind — so chat and the brief can show a staleness banner and
temper confidence. All read-only; degrades to "unknown" rather than failing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import SnapshotStatus
from app.models.knowledge import KnowledgeChunk
from app.models.snapshot import Snapshot

_STALE_HOURS = 30.0  # a weekday snapshot older than this reads as stale


@dataclass(frozen=True)
class DataHealth:
    stale: bool
    snapshot_age_hours: float | None
    confidence: str  # "high" | "medium" | "low"
    reasons: list[str] = field(default_factory=list)


async def data_health(db: AsyncSession) -> DataHealth:
    created = (
        await db.execute(
            select(Snapshot.created_at)
            .where(Snapshot.status == SnapshotStatus.OK.value)
            .order_by(Snapshot.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    reasons: list[str] = []
    age_h: float | None = None
    if created is None:
        reasons.append("No portfolio snapshot yet.")
    else:
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        age_h = round((datetime.now(UTC) - created).total_seconds() / 3600, 1)
        if age_h > _STALE_HOURS:
            reasons.append(
                f"Latest snapshot is {age_h:.0f}h old — the Kite session may have expired."
            )

    total = (await db.execute(select(func.count(KnowledgeChunk.id)))).scalar_one()
    pending = (
        await db.execute(
            select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.embedding.is_(None))
        )
    ).scalar_one()
    if total and pending:
        reasons.append(f"{pending} knowledge chunks await embedding (3070 offline?).")

    stale = age_h is None or age_h > _STALE_HOURS
    confidence = "low" if (age_h is None or age_h > 72) else "medium" if reasons else "high"
    return DataHealth(
        stale=stale, snapshot_age_hours=age_h, confidence=confidence, reasons=reasons
    )
