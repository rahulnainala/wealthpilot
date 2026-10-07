"""APScheduler wiring for the weekday auto-snapshot job.

Runs at 09:45 IST Mon-Fri: the market opens at 09:15, and the requirement is a
snapshot "fresh by 10:00 IST". A stale/expired token is recorded as a FAILED
snapshot rather than crashing the job. The same tick is where the daily goal
simulation is triggered (wired in Phase 4B).
"""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.config import get_settings
from app.db import get_sessionmaker
from app.domain.enums import SnapshotStatus
from app.models.snapshot import Snapshot
from app.security.crypto import decrypt
from app.services.analytics_service import (
    ist_date,
    latest_holding_views,
    load_goal_views,
    today_ist,
)
from app.services.goal_simulation import simulate_goal_and_cache
from app.services.kite import BaseKiteService, KiteTokenExpired, build_kite_service
from app.services.kite_sessions import get_active_session
from app.services.risk import RiskEngineError, build_risk_client
from app.services.snapshot_service import record_failed_snapshot, refresh_snapshot

logger = logging.getLogger("wealthpilot.scheduler")
IST = ZoneInfo("Asia/Kolkata")

_scheduler: AsyncIOScheduler | None = None


async def _resolve_kite_or_fail(db: AsyncSession) -> BaseKiteService | None:
    """Return a Kite service for the job, or None (recording a failure)."""
    settings = get_settings()
    if settings.use_mock_kite:
        return build_kite_service()

    session = await get_active_session(db)
    if session is None:
        await record_failed_snapshot(
            db, "No active Zerodha session for scheduled snapshot."
        )
        return None
    return build_kite_service(decrypt(session.access_token_encrypted))


async def run_daily_snapshot() -> None:
    """Scheduled job: refresh the portfolio snapshot (and, in 4B, simulations)."""
    async with get_sessionmaker()() as db:
        kite = await _resolve_kite_or_fail(db)
        if kite is None:
            return
        try:
            snapshot = await refresh_snapshot(db, kite)
        except KiteTokenExpired:
            # refresh_snapshot already recorded a FAILED snapshot + marked stale.
            logger.warning("Scheduled snapshot skipped: Kite token expired.")
            return
        logger.info(
            "Scheduled snapshot %s created (total=%.2f).",
            snapshot.id,
            snapshot.total_value,
        )
        # Trigger fresh goal simulations using the day's snapshot as the
        # starting value, caching each result.
        await _run_goal_simulations(db)


async def _run_goal_simulations(db: AsyncSession) -> None:
    """Recompute and cache Monte Carlo simulations for every goal."""
    data = await latest_holding_views(db)
    holdings = data[0] if data is not None else []
    goals = await load_goal_views(db)
    settings = get_settings()
    risk = build_risk_client()
    try:
        for goal in goals:
            await simulate_goal_and_cache(
                db, goal, holdings, risk, today_ist(), settings.simulation_paths
            )
    except RiskEngineError as exc:
        logger.warning("Goal simulations skipped: %s", exc)
    finally:
        await risk.close()


async def run_nightly_learning() -> None:
    """Nightly RAG loop: sync the knowledge folder, embed what the 3070 can.

    Resumable by design — if the GPU box is off, chunks wait; the next run
    (or a manual POST /api/ai/ingest) catches up. This is how the app's AI
    keeps learning as knowledge and history accumulate.
    """
    from app.db import get_sessionmaker
    from app.services.ai.distill import distill_daily
    from app.services.ai.rag import embed_pending, ingest_knowledge_dir

    risk = build_risk_client()
    try:
        async with get_sessionmaker()() as db:
            await distill_daily(db, risk)
            stats = await ingest_knowledge_dir(db)
            embedded = await embed_pending(db, batch=256)
            from app.services.ai.insights import generate_insights

            await generate_insights(db, risk)
            from app.services.ai.action_agent import build_and_store_plan
            from app.services.ai.push import notify_new_action_alerts

            plan = await build_and_store_plan(db, risk)
            # Phase 44: opt-in autonomous +10% placement — routed through the
            # execution guard, so it only fires in secured mode (never dev).
            try:
                from app.services.execution import run_auto_execute

                kite = await _resolve_kite_or_fail(db)
                if kite is not None:
                    auto = await run_auto_execute(db, kite)
                    if auto.get("placed"):
                        logger.info("auto-execute placed: %s", auto["placed"])
            except Exception:  # noqa: BLE001 — never let execution kill the loop
                logger.exception("auto-execute run failed")
            # Pre-warm tomorrow's brief while the GPU box is known to be up.
            # The 3070 isn't always on, and the brief is the one AI surface
            # that had no stored fallback — insights and the daily plan are
            # already persisted above, so they survive a sleeping GPU while
            # the brief would render "unconfigured". Writing it here means the
            # morning read is served from the Postgres cache either way.
            try:
                from app.services.ai.brief_service import generate_brief

                await generate_brief(db, risk, refresh=True)
            except Exception:  # noqa: BLE001 — a missing brief must not kill the loop
                logger.exception("brief pre-generation failed")

            pushed = await notify_new_action_alerts(db)
            if plan:
                from app.services.ai.push import send_push

                await send_push(db, "Today's plan", plan[0]["title"], url="/")
            logger.info(
                "nightly learning: %d files, %d new chunks, %d embedded, %d plan, %d pushed",
                stats["files"], stats["chunks_added"], embedded, len(plan), pushed,
            )
    except Exception:  # noqa: BLE001 — never let the loop kill the scheduler
        logger.exception("nightly learning run failed")
    finally:
        await risk.close()


async def run_startup_catchup() -> None:
    """On boot, backfill today's snapshot if the 09:45 IST cron tick was missed.

    The stack runs on a laptop that sleeps overnight, so APScheduler regularly
    finds the daily_snapshot trigger hours past due and — because the miss
    exceeds ``misfire_grace_time`` — drops it entirely rather than running it
    late (observed gaps: 2026-07-09, 07-15, 07-16 had no snapshot at all).
    Widening the grace window only helps for short naps; a host asleep past it
    (seen up to 17h) still needs this explicit "do we have today's data yet"
    check on wake instead of waiting for tomorrow's tick.
    """
    async with get_sessionmaker()() as db:
        latest_ok_ts = (
            await db.execute(
                select(Snapshot.ts)
                .where(Snapshot.status == SnapshotStatus.OK.value)
                .order_by(Snapshot.ts.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if latest_ok_ts is not None and ist_date(latest_ok_ts) == today_ist():
        return
    logger.info("Startup catch-up: no OK snapshot yet today, running one now.")
    await run_daily_snapshot()


async def run_kite_staleness_check() -> None:
    """Phase 39: proactively mark overnight-expired Kite sessions stale."""
    from app.db import get_sessionmaker
    from app.services.kite_sessions import mark_expired_sessions_stale

    try:
        async with get_sessionmaker()() as db:
            n = await mark_expired_sessions_stale(db)
            if n:
                logger.info("kite staleness: marked %d expired session(s)", n)
    except Exception:  # noqa: BLE001 — never let the loop kill the scheduler
        logger.exception("kite staleness check failed")


async def run_weekly_review() -> None:
    """Pre-warm the weekly review so Sunday morning it's already written."""
    from app.db import get_sessionmaker
    from app.services.ai.weekly_review import generate_weekly_review

    risk = build_risk_client()
    try:
        async with get_sessionmaker()() as db:
            await generate_weekly_review(db, risk, refresh=True)
            logger.info("weekly review pre-generated")
    except Exception:  # noqa: BLE001 — never let the loop kill the scheduler
        logger.exception("weekly review run failed")
    finally:
        await risk.close()


def start_scheduler() -> None:
    """Start the background scheduler if enabled."""
    global _scheduler
    settings = get_settings()
    if not settings.enable_scheduler or _scheduler is not None:
        return
    scheduler = AsyncIOScheduler(timezone=IST)
    scheduler.add_job(
        run_daily_snapshot,
        CronTrigger(
            day_of_week="mon-fri",
            hour=settings.snapshot_cron_hour,
            minute=settings.snapshot_cron_minute,
            timezone=IST,
        ),
        id="daily_snapshot",
        replace_existing=True,
        misfire_grace_time=4 * 3600,
    )
    scheduler.add_job(
        run_nightly_learning,
        CronTrigger(hour=20, minute=30, timezone=IST),
        id="nightly_learning",
        replace_existing=True,
        misfire_grace_time=6 * 3600,
    )
    scheduler.add_job(
        run_weekly_review,
        CronTrigger(day_of_week="sun", hour=7, minute=30, timezone=IST),
        id="weekly_review",
        replace_existing=True,
        misfire_grace_time=6 * 3600,
    )
    scheduler.add_job(
        run_kite_staleness_check,
        CronTrigger(hour=6, minute=30, timezone=IST),
        id="kite_staleness",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started: daily snapshot at %02d:%02d IST (Mon-Fri).",
        settings.snapshot_cron_hour,
        settings.snapshot_cron_minute,
    )


def stop_scheduler() -> None:
    """Shut the scheduler down (called on app shutdown)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
