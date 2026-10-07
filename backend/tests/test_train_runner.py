"""Tests for the training-generator background-task singleton (train_runner).

The real generator (train_generator.run_generation) hits the DB and Ollama —
these tests monkeypatch it with a stand-in so they exercise only the
start/stop/is_running orchestration, not the generation logic itself.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.ai import train_runner


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    train_runner.stop()
    await asyncio.sleep(0)  # let any cancellation settle before the next test


async def test_not_running_initially() -> None:
    assert train_runner.is_running() is False


async def test_start_runs_in_background_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()

    async def fake_run(target: int, concurrency: int, model: str | None) -> None:
        started.set()
        await asyncio.sleep(10)

    monkeypatch.setattr(train_runner, "run_generation", fake_run)

    assert train_runner.start() is True
    assert train_runner.is_running() is True
    # Calling start again while already running is a no-op.
    assert train_runner.start() is False

    await started.wait()  # confirms the background task actually executed


async def test_stop_cancels_the_running_task(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(target: int, concurrency: int, model: str | None) -> None:
        await asyncio.sleep(10)

    monkeypatch.setattr(train_runner, "run_generation", fake_run)

    train_runner.start()
    assert train_runner.is_running() is True

    assert train_runner.stop() is True
    await asyncio.sleep(0)
    assert train_runner.is_running() is False


async def test_stop_when_nothing_running_is_a_noop() -> None:
    assert train_runner.stop() is False
