"""Phase 8 — lightweight news/earnings context (no API key).

Pulls recent headlines from Google News' free RSS endpoint for a holding, so
Pilot can add "here's whether to pull the trigger now" context when a stock
nears the +10% sell threshold. Cached (PgTTLCache) to avoid hammering the feed;
degrades to an empty list when the feed is unreachable — never blocks a reply.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import httpx

from app.services.cache import get_shared_cache

logger = logging.getLogger("wealthpilot.ai")

_RSS = "https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
_TTL_S = 6 * 3600
_TIMEOUT_S = 8.0


@dataclass(frozen=True)
class Headline:
    title: str
    source: str
    published: str
    sentiment: float = 0.0


async def _fetch(query: str, k: int) -> list[dict[str, Any]]:
    url = _RSS.format(q=quote_plus(f"{query} stock India"))
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "WealthPilot/1.0"})
            resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except (httpx.HTTPError, ET.ParseError) as exc:
        logger.info("news fetch skipped (%s)", exc)
        return []
    out: list[dict[str, Any]] = []
    for item in list(root.iterfind(".//item"))[:k]:
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        published = (item.findtext("pubDate") or "").strip()[:16]
        if title:
            out.append({"title": title, "source": source, "published": published})
    return out


async def get_headlines(query: str, k: int = 5) -> list[Headline]:
    """Cached recent headlines for a holding; empty when the feed is down."""
    query = query.strip()
    if not query:
        return []
    key = f"ai:news:{query.lower()}:{k}"

    async def _factory() -> list[dict[str, Any]]:
        return await _fetch(query, k)

    rows = await get_shared_cache().get_or_set(key, float(_TTL_S), _factory)
    from app.services.ai.sentiment import score

    return [Headline(sentiment=score(r["title"]), **r) for r in rows]
