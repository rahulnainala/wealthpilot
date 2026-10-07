"""A small process-local async TTL cache.

Kite Connect enforces per-endpoint rate limits, and the portfolio only needs
near-real-time freshness for reads. A 60s TTL cache keyed by logical resource
name both rate-limits our calls and de-duplicates concurrent requests via a
per-key lock (single-flight), so a burst of dashboard requests triggers at most
one upstream Kite call per resource per TTL window.
"""

from __future__ import annotations

import asyncio
import pickle
import time
from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar

T = TypeVar("T")


class CacheBackend(Protocol):
    """TTL cache contract shared by the in-process and Redis backends."""

    async def get_or_set(
        self, key: str, ttl: float, factory: Callable[[], Awaitable[T]]
    ) -> T: ...

    def invalidate(self, key: str | None = None) -> None: ...


class AsyncTTLCache:
    """Coalescing time-to-live cache for async factory functions."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, object]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())

    async def get_or_set(
        self, key: str, ttl: float, factory: Callable[[], Awaitable[T]]
    ) -> T:
        """Return a cached value for ``key`` or compute and store it.

        Concurrent callers for the same missing key await a single ``factory``
        invocation rather than each hitting the upstream service.
        """
        cached = self._store.get(key)
        if cached is not None and cached[0] > time.monotonic():
            return cached[1]  # type: ignore[return-value]

        async with self._lock_for(key):
            # Re-check: another coroutine may have populated it while we waited.
            cached = self._store.get(key)
            if cached is not None and cached[0] > time.monotonic():
                return cached[1]  # type: ignore[return-value]

            value = await factory()
            self._store[key] = (time.monotonic() + ttl, value)
            return value

    def invalidate(self, key: str | None = None) -> None:
        """Drop a single key, or the entire cache when ``key`` is None."""
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)


class RedisTTLCache:
    """Redis-backed TTL cache: survives backend restarts and is shared across
    workers. Values are pickled — acceptable because only this backend writes
    to its dedicated Redis database. Per-key locks still give per-process
    single-flight coalescing; Redis's PX expiry owns the TTL.
    """

    _PREFIX = "wp:cache:"

    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(url)
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())

    async def get_or_set(
        self, key: str, ttl: float, factory: Callable[[], Awaitable[T]]
    ) -> T:
        rkey = self._PREFIX + key
        raw = await self._redis.get(rkey)
        if raw is not None:
            return pickle.loads(raw)  # noqa: S301 — self-written cache data

        async with self._lock_for(key):
            raw = await self._redis.get(rkey)
            if raw is not None:
                return pickle.loads(raw)  # noqa: S301
            value = await factory()
            await self._redis.set(rkey, pickle.dumps(value), px=int(ttl * 1000))
            return value

    def invalidate(self, key: str | None = None) -> None:
        """Fire-and-forget delete (callers are sync; Redis I/O is async)."""

        async def _run() -> None:
            if key is None:
                keys = [k async for k in self._redis.scan_iter(f"{self._PREFIX}*")]
                if keys:
                    await self._redis.delete(*keys)
            else:
                await self._redis.delete(self._PREFIX + key)

        try:
            asyncio.get_running_loop().create_task(_run())
        except RuntimeError:  # no running loop (e.g. sync teardown)
            asyncio.run(_run())


_shared: CacheBackend | None = None


def get_shared_cache() -> CacheBackend:
    """Process-wide cache: Redis when REDIS_URL is set, in-process otherwise."""
    global _shared
    if _shared is None:
        from app.config import get_settings

        settings = get_settings()
        if settings.cache_backend == "postgres":
            _shared = PgTTLCache()
        elif settings.cache_backend == "redis" or settings.redis_url:
            _shared = RedisTTLCache(settings.redis_url or "redis://localhost:6379/0")
        else:
            _shared = AsyncTTLCache()
    return _shared


class PgTTLCache:
    """Postgres-backed TTL cache: one fewer service for the local stack, and
    long-TTL entries (the AI brief) survive backend restarts. Values are
    pickled like the Redis backend; per-key locks keep single-flight.
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())

    async def _get_raw(self, key: str):
        from sqlalchemy import text

        from app.db import get_sessionmaker

        async with get_sessionmaker()() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT value FROM cache_entries "
                        "WHERE key = :k AND expires_at > now()"
                    ),
                    {"k": key},
                )
            ).first()
            return row[0] if row else None

    async def get_or_set(
        self, key: str, ttl: float, factory: Callable[[], Awaitable[T]]
    ) -> T:
        raw = await self._get_raw(key)
        if raw is not None:
            return pickle.loads(raw)  # noqa: S301 — self-written cache data

        async with self._lock_for(key):
            raw = await self._get_raw(key)
            if raw is not None:
                return pickle.loads(raw)  # noqa: S301
            value = await factory()
            from sqlalchemy import text

            from app.db import get_sessionmaker

            async with get_sessionmaker()() as db:
                await db.execute(
                    text(
                        "INSERT INTO cache_entries (key, value, expires_at) "
                        "VALUES (:k, :v, now() + make_interval(secs => :ttl)) "
                        "ON CONFLICT (key) DO UPDATE SET value = :v, "
                        "expires_at = now() + make_interval(secs => :ttl)"
                    ),
                    {"k": key, "v": pickle.dumps(value), "ttl": ttl},
                )
                await db.commit()
            return value

    def invalidate(self, key: str | None = None) -> None:
        async def _run() -> None:
            from sqlalchemy import text

            from app.db import get_sessionmaker

            async with get_sessionmaker()() as db:
                if key is None:
                    await db.execute(text("DELETE FROM cache_entries"))
                else:
                    await db.execute(
                        text("DELETE FROM cache_entries WHERE key = :k"), {"k": key}
                    )
                await db.commit()

        try:
            asyncio.get_running_loop().create_task(_run())
        except RuntimeError:
            asyncio.run(_run())
