"""Phase 48 — chart/screenshot vision (llava on the 3070).

Ollama serves multimodal models, so an uploaded chart is read by a local vision
model (default `llava`) against a short portfolio context — no new infra beyond
`ollama pull llava`. Degrades cleanly when the 3070 or the model is unavailable.
"""

from __future__ import annotations

import base64
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger("wealthpilot.ai")

_TIMEOUT_S = 120.0


async def analyze_image(db: AsyncSession, image_bytes: bytes, prompt: str | None) -> str | None:
    settings = get_settings()
    if not settings.ollama_url:
        return None

    # A little portfolio context so it reads the chart "for you".
    context = ""
    try:
        from app.services.analytics_service import latest_holding_views

        data = await latest_holding_views(db)
        if data is not None:
            holdings, cash = data
            total = sum(h.value for h in holdings) + cash
            context = f" The viewer's portfolio is ~₹{total:,.0f}, PSU-energy heavy."
    except Exception:  # noqa: BLE001
        pass

    full_prompt = (
        (prompt or "Describe this chart and what it means for an investor.")
        + context
        + " Be concise and specific."
    )
    b64 = base64.b64encode(image_bytes).decode()
    try:
        async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=_TIMEOUT_S) as client:
            resp = await client.post(
                "/api/generate",
                json={
                    "model": settings.vision_model,
                    "prompt": full_prompt,
                    "images": [b64],
                    "stream": False,
                    "keep_alive": -1,
                },
            )
            resp.raise_for_status()
            return str(resp.json().get("response", "")).strip() or None
    except httpx.HTTPError as exc:
        logger.info("vision skipped (%s)", exc)
        return None
