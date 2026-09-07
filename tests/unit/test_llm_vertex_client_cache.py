"""Regression: ``_vertex_client()`` must build the ``genai.Client`` once and
reuse it, not construct a fresh client per call.

A fresh client per call resolves ADC credentials synchronously on the event
loop on every single LLM call — both retry attempts and every graph node —
outside the ``llm_call_timeout_s``/``asyncio.wait_for`` wrapper around the
actual request. Found live: a turn recorded a 239s ``classify_intent``
latency; the client build, not the model call, was the thing hanging.

Kept out of ``test_llm_retry.py`` because that file's autouse fixture
monkeypatches ``llm._vertex_client`` itself (to isolate the retry loop from
any real client), which would defeat a test of ``_vertex_client`` proper.
"""

from typing import Any

import pytest

genai = pytest.importorskip("google.genai")

from revenueflow.services import llm  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_cached_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "_client", None)


def test_vertex_client_is_built_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    build_calls = {"n": 0}
    sentinel = object()

    def _fake_client(**_kwargs: Any) -> Any:
        build_calls["n"] += 1
        return sentinel

    monkeypatch.setattr(genai, "Client", _fake_client)

    first = llm._vertex_client()
    second = llm._vertex_client()

    assert first is sentinel
    assert second is sentinel
    assert build_calls["n"] == 1
