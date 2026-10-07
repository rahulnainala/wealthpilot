"""Tests for the training-generator log broadcaster (train_log).

Black-box: drives the real "traingen" logger and checks what comes out of
history()/subscribe(), rather than reaching into the handler internals.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from app.services.ai import train_log

_logger = logging.getLogger("traingen")


@pytest.fixture(autouse=True)
def _isolate():
    train_log.reset()
    train_log._subscribers.clear()
    yield
    train_log.reset()
    train_log._subscribers.clear()


def test_logged_lines_land_in_history() -> None:
    train_log.attach()
    _logger.info("bank=10 unasked=10 target=1000")

    lines = train_log.history()
    assert len(lines) == 1
    assert "bank=10 unasked=10 target=1000" in lines[0]


def test_attach_is_idempotent() -> None:
    train_log.attach()
    train_log.attach()
    train_log.attach()
    _logger.info("only once")

    # A duplicated handler would append this line more than once.
    assert train_log.history() == [line for line in train_log.history() if "only once" in line]
    assert len(train_log.history()) == 1


def test_history_is_bounded_and_drops_the_oldest() -> None:
    train_log.attach()
    for i in range(train_log._BUFFER_SIZE + 5):
        _logger.info("line %d", i)

    lines = train_log.history()
    assert len(lines) == train_log._BUFFER_SIZE
    assert lines[0].endswith("line 5")  # lines 0-4 dropped — outside the window
    assert lines[-1].endswith(f"line {train_log._BUFFER_SIZE + 4}")


def test_reset_clears_history() -> None:
    train_log.attach()
    _logger.info("something")
    assert train_log.history() != []

    train_log.reset()
    assert train_log.history() == []


async def test_subscriber_receives_new_lines() -> None:
    train_log.attach()
    q = train_log.subscribe()
    try:
        _logger.info("hello subscriber")
        line = await asyncio.wait_for(q.get(), timeout=1.0)
        assert "hello subscriber" in line
    finally:
        train_log.unsubscribe(q)


async def test_unsubscribe_stops_delivery() -> None:
    train_log.attach()
    q = train_log.subscribe()
    train_log.unsubscribe(q)

    _logger.info("should not arrive")
    assert q.empty()
