import asyncio
from collections.abc import Iterator

import pytest
from asgi_lifespan import LifespanManager

from revenueflow.config import get_settings
from revenueflow.main import app


@pytest.fixture
def consumer(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[list[int], asyncio.Event]]:
    calls: list[int] = []
    started = asyncio.Event()

    async def _stub() -> None:
        calls.append(1)
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr("revenueflow.main.run_subscriber", _stub)
    get_settings.cache_clear()
    yield calls, started
    get_settings.cache_clear()


async def test_consumer_stays_off_when_flag_false(
    db: None,
    consumer: tuple[list[int], asyncio.Event],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUN_CONSUMER", "0")
    calls, _ = consumer
    async with LifespanManager(app):
        await asyncio.sleep(0)
    assert calls == []


async def test_consumer_runs_and_cancels_when_flag_true(
    db: None,
    consumer: tuple[list[int], asyncio.Event],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUN_CONSUMER", "1")
    calls, started = consumer
    async with LifespanManager(app):
        await asyncio.wait_for(started.wait(), timeout=2)
        assert calls == [1]
    assert calls == [1]
