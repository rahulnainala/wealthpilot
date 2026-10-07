"""Construct the appropriate Kite service for the current configuration."""

from __future__ import annotations

from app.config import get_settings
from app.services.cache import CacheBackend, get_shared_cache
from app.services.kite.base import BaseKiteService
from app.services.kite.cached import CachedKiteService
from app.services.kite.mock import MockKiteService
from app.services.kite.real import KiteService

# Process-wide cache shared across all requests (survives per-request service
# construction), so the TTL genuinely rate-limits upstream Kite calls. Redis
# when configured (shared, restart-surviving); in-process otherwise.
def _get_cache() -> CacheBackend:
    return get_shared_cache()


def build_kite_service(access_token: str | None = None) -> BaseKiteService:
    """Return a cache-wrapped Kite service (mock or real per ``USE_MOCK_KITE``).

    ``access_token`` is the decrypted token for the active session; it is
    ignored in mock mode and for unauthenticated auth calls (login URL).
    """
    settings = get_settings()
    inner: BaseKiteService
    if settings.use_mock_kite:
        inner = MockKiteService()
    else:
        inner = KiteService(
            api_key=settings.kite_api_key,
            api_secret=settings.kite_api_secret,
            access_token=access_token,
        )
    return CachedKiteService(inner, _get_cache(), settings.kite_cache_ttl_seconds)


def reset_kite_cache() -> None:
    """Clear the shared cache (used by tests and on reconnect)."""
    _get_cache().invalidate()
