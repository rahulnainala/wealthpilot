"""Tests for the async TTL cache (coalescing + expiry)."""

from __future__ import annotations

import asyncio

from app.services.cache import AsyncTTLCache


async def test_caches_within_ttl() -> None:
    cache = AsyncTTLCache()
    calls = 0

    async def factory() -> int:
        nonlocal calls
        calls += 1
        return calls

    first = await cache.get_or_set("k", 100, factory)
    second = await cache.get_or_set("k", 100, factory)
    assert first == second == 1  # factory ran once


async def test_coalesces_concurrent_callers() -> None:
    cache = AsyncTTLCache()
    calls = 0

    async def slow_factory() -> str:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return "value"

    results = await asyncio.gather(
        *(cache.get_or_set("k", 100, slow_factory) for _ in range(5))
    )
    assert results == ["value"] * 5
    assert calls == 1  # single-flight


async def test_recomputes_after_expiry() -> None:
    cache = AsyncTTLCache()
    calls = 0

    async def factory() -> int:
        nonlocal calls
        calls += 1
        return calls

    await cache.get_or_set("k", -1, factory)  # already expired on store
    await cache.get_or_set("k", -1, factory)
    assert calls == 2


async def test_invalidate() -> None:
    cache = AsyncTTLCache()
    calls = 0

    async def factory() -> int:
        nonlocal calls
        calls += 1
        return calls

    await cache.get_or_set("k", 100, factory)
    cache.invalidate("k")
    await cache.get_or_set("k", 100, factory)
    assert calls == 2
