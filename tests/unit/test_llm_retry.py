from typing import Any

import pytest

from revenueflow.domain.errors import LLMError
from revenueflow.services import llm

genai_errors = pytest.importorskip("google.genai.errors")


@pytest.fixture(autouse=True)
def _no_sleep_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(_delay: float) -> None:
        return None

    monkeypatch.setattr(llm.asyncio, "sleep", _instant)
    monkeypatch.setattr(llm, "_vertex_client", lambda: object())


def _server_error() -> genai_errors.ServerError:
    return genai_errors.ServerError(503, {"error": {"message": "unavailable"}})


def _client_error(code: int) -> genai_errors.ClientError:
    return genai_errors.ClientError(code, {"error": {"message": "nope"}})


async def test_retries_transient_then_succeeds() -> None:
    calls = {"n": 0}

    async def call(_client: Any) -> str:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _server_error()
        return "ok"

    assert await llm._generate_with_retry(call) == "ok"
    assert calls["n"] == 3


async def test_transient_exhausted_raises_llmerror() -> None:
    async def call(_client: Any) -> str:
        raise _server_error()

    with pytest.raises(LLMError):
        await llm._generate_with_retry(call)


async def test_non_retryable_client_error_raises_immediately() -> None:
    calls = {"n": 0}

    async def call(_client: Any) -> str:
        calls["n"] += 1
        raise _client_error(401)

    with pytest.raises(LLMError):
        await llm._generate_with_retry(call)
    assert calls["n"] == 1


async def test_rate_limit_is_retried() -> None:
    calls = {"n": 0}

    async def call(_client: Any) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _client_error(429)
        return "ok"

    assert await llm._generate_with_retry(call) == "ok"
    assert calls["n"] == 2
