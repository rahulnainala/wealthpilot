"""In-process singleton owning the training-generator's background task.

Runs ``train_generator.run_generation`` as an ``asyncio.Task`` inside the
backend's own event loop rather than a separate container — each question it
asks is a real chat call, which is what actually sends work to the 3070
(Ollama inference over the LAN). One run at a time; starting while already
running is a no-op, and the task survives across requests since it's kept on
this module rather than tied to any single request's lifecycle.

Trade-off, accepted deliberately: a backend redeploy kills the run silently,
same as the previous `traingen` container would lose its work on a restart —
resumable either way since already-asked questions are skipped on the next
start.
"""

from __future__ import annotations

import asyncio
import logging

from app.services.ai import train_log
from app.services.ai.train_generator import run_generation

# Same logger train_generator uses — so stop/crash lines land in the same
# broadcast stream as the generation progress lines (the live terminal view).
log = logging.getLogger("traingen")

_task: asyncio.Task[None] | None = None


def is_running() -> bool:
    return _task is not None and not _task.done()


def start(target: int = 1000, concurrency: int = 4, model: str | None = None) -> bool:
    """Start the generator in the background. Returns False if already running."""
    global _task
    if is_running():
        return False

    train_log.attach()
    train_log.reset()

    async def _run() -> None:
        try:
            await run_generation(target, concurrency, model)
        except asyncio.CancelledError:
            log.info("training generator stopped")
            raise
        except Exception:
            log.exception("training generator crashed")

    _task = asyncio.create_task(_run())
    return True


def stop() -> bool:
    """Cancel the running generator. Returns False if nothing was running."""
    if not is_running():
        return False
    assert _task is not None
    _task.cancel()
    return True
