"""In-process broadcaster for the training generator's log output.

Attaches a logging.Handler to the "traingen" logger so every log.info() call
inside train_generator.run_generation is captured — this is what powers the
live terminal view on the AI panel (``/api/ai/train/logs/stream``). A bounded
ring buffer replays recent history to a client that just connected; an
asyncio.Queue per subscriber pushes new lines as they happen.

In-memory only, deliberately — same trade-off as train_runner's task itself
(a backend redeploy loses it), and not worth persisting for a live tail.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque

_BUFFER_SIZE = 300

_buffer: deque[str] = deque(maxlen=_BUFFER_SIZE)
_subscribers: set[asyncio.Queue[str]] = set()


class _BroadcastHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        _buffer.append(line)
        for q in list(_subscribers):
            q.put_nowait(line)


_handler = _BroadcastHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
_attached = False


def attach() -> None:
    """Idempotently wire the broadcast handler onto the traingen logger."""
    global _attached
    if _attached:
        return
    logger = logging.getLogger("traingen")
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    _attached = True


def reset() -> None:
    """Clear history — called when a fresh run starts, so the terminal
    doesn't mix lines from a previous session."""
    _buffer.clear()


def history() -> list[str]:
    return list(_buffer)


def subscribe() -> asyncio.Queue[str]:
    q: asyncio.Queue[str] = asyncio.Queue()
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue[str]) -> None:
    _subscribers.discard(q)
