"""WealthPilot FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.models import Base
from app.routers import (
    ai,
    analytics,
    assets,
    auth,
    basket,
    bucket_overrides,
    chat,
    contributions,
    evals,
    execution,
    funds,
    goals,
    insights,
    market,
    push,
    snapshots,
    watchlist,
    ws,
)
from app.routers import settings as settings_router
from app.scheduler import run_startup_catchup, start_scheduler, stop_scheduler
from app.services.kite import KiteError, KiteNotConnected, KiteTokenExpired, build_kite_service
from app.services.risk import RiskEngineError
from app.services.seed import seed_goals

logger = logging.getLogger("wealthpilot.startup")


async def _run_startup_catchup_safely() -> None:
    try:
        await run_startup_catchup()
    except Exception:  # noqa: BLE001 — never let a boot-time catch-up crash the app
        logger.exception("startup snapshot catch-up failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = get_engine()
    # Local/dev convenience. In Docker/production this is disabled and Alembic
    # migrations own schema evolution (`alembic upgrade head` on startup).
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                from sqlalchemy import text

                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
    async with get_sessionmaker()() as db:
        await seed_goals(db)
    start_scheduler()
    if settings.enable_scheduler:
        asyncio.create_task(_run_startup_catchup_safely())
    yield
    stop_scheduler()
    await engine.dispose()


app = FastAPI(title="WealthPilot API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_AUTH_OPEN_PREFIXES = ("/api/auth/", "/healthz", "/docs", "/openapi.json", "/redoc")


@app.middleware("http")
async def _auth_gate(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Phase 40: when APP_PASSWORD is set, require a valid session token for every
    request except auth/health. Open (no-op) when auth is disabled (local/mock)."""
    from app.security.app_auth import auth_enabled, verify_session_token

    if auth_enabled() and request.method != "OPTIONS":
        path = request.url.path
        if not any(path.startswith(p) for p in _AUTH_OPEN_PREFIXES):
            token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
            if not token or not verify_session_token(token):
                return JSONResponse(status_code=401, content={"error": "auth_required"})
    return await call_next(request)

# Public-demo allowlist: POSTs that only run a calculation. Everything else that
# writes (goals, uploads, chat, push, orders, AI training) is refused.
_DEMO_COMPUTE_POSTS = re.compile(
    r"^/api/goals/(optimize|\d+/(simulate|stress|required-contribution))$"
)


@app.middleware("http")
async def _demo_read_only(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if (
        get_settings().demo_mode
        and request.method not in ("GET", "HEAD", "OPTIONS")
        and not (request.method == "POST" and _DEMO_COMPUTE_POSTS.match(request.url.path))
    ):
        return JSONResponse(status_code=403, content={"error": "read_only_demo"})
    return await call_next(request)


app.include_router(auth.router)
app.include_router(auth.app_auth_router)
app.include_router(execution.router)
app.include_router(assets.router)
app.include_router(watchlist.router)
app.include_router(ai.router)
app.include_router(push.router)
app.include_router(chat.router)
app.include_router(evals.router)
app.include_router(insights.router)
app.include_router(snapshots.router)
app.include_router(goals.router)
app.include_router(contributions.router)
app.include_router(bucket_overrides.router)
app.include_router(settings_router.router)
app.include_router(analytics.router)
app.include_router(market.router)
app.include_router(funds.router)
app.include_router(basket.router)
app.include_router(ws.router)


def _reconnect_payload(code: str, message: str) -> dict[str, str]:
    """Machine-readable body telling the frontend to show a reconnect prompt."""
    return {
        "error": code,
        "message": message,
        "login_url": build_kite_service().get_login_url(),
    }


@app.exception_handler(KiteTokenExpired)
async def _token_expired_handler(
    request: Request, exc: KiteTokenExpired
) -> JSONResponse:
    # Mark the session stale so subsequent calls short-circuit to the reconnect
    # prompt instead of repeatedly hitting Kite with a dead token.
    try:
        from app.db import get_sessionmaker
        from app.services.kite_sessions import get_active_session, mark_session_stale

        async with get_sessionmaker()() as db:
            session = await get_active_session(db)
            if session is not None:
                await mark_session_stale(db, session)
    except Exception:  # noqa: BLE001 — never let cleanup mask the reconnect response
        pass
    return JSONResponse(
        status_code=401,
        content=_reconnect_payload(
            "kite_token_expired",
            "Your Zerodha session has expired. Please reconnect.",
        ),
    )


@app.exception_handler(KiteNotConnected)
async def _not_connected_handler(
    request: Request, exc: KiteNotConnected
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=_reconnect_payload(
            "kite_not_connected",
            "No active Zerodha session. Please connect your account.",
        ),
    )


@app.exception_handler(KiteError)
async def _kite_error_handler(request: Request, exc: KiteError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"error": "kite_upstream_error", "message": str(exc)},
    )


@app.exception_handler(RiskEngineError)
async def _risk_engine_error_handler(
    request: Request, exc: RiskEngineError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": "risk_engine_unavailable",
            "detail": "Risk engine is unavailable — analytics are paused until it recovers.",
        },
    )


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "backend"}
