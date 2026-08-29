"""Observability tracer port and sink implementations.

The default sink is ``noop`` and runs on the standard library alone. The
Langfuse and OpenTelemetry implementations import their client libraries lazily
inside ``__init__`` so importing this module never requires the optional
``observability`` extra.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from revenueflow.config import get_settings
from revenueflow.observability.masking import mask

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Usage:
    """Token counts reported by a model generation."""

    input_tokens: int = 0
    output_tokens: int = 0


class Generation(Protocol):
    """A single model call recorded inside a trace."""

    def update(
        self,
        *,
        output: Any = None,
        usage: Usage | None = None,
        cost_usd: float | None = None,
    ) -> None: ...

    def end(self) -> None: ...


class Span(Protocol):
    """A unit of work (node or tool call) recorded inside a trace."""

    def end(self) -> None: ...


@runtime_checkable
class Tracer(Protocol):
    """Port every graph node uses to record what happened in a turn."""

    trace_id: str

    def span(
        self, name: str, *, attrs: Mapping[str, Any] | None = None
    ) -> AbstractContextManager[Span]: ...

    def generation(
        self,
        name: str,
        *,
        model: str,
        prompt_version: str,
        input: Any = None,
    ) -> AbstractContextManager[Generation]: ...

    def event(self, name: str, *, attrs: Mapping[str, Any] | None = None) -> None: ...

    def end(self, *, outcome: str, policy_decision: str = "n/a", handoff: bool = False) -> None: ...


class _NoopSpan:
    def end(self) -> None:
        return None


class _NoopGeneration:
    def update(
        self,
        *,
        output: Any = None,
        usage: Usage | None = None,
        cost_usd: float | None = None,
    ) -> None:
        return None

    def end(self) -> None:
        return None


class NoopTracer:
    """Fully working tracer that records nothing."""

    def __init__(self, *, turn_id: str | None = None) -> None:
        self.trace_id = turn_id or uuid4().hex

    @contextmanager
    def span(self, name: str, *, attrs: Mapping[str, Any] | None = None) -> Iterator[Span]:
        yield _NoopSpan()

    @contextmanager
    def generation(
        self,
        name: str,
        *,
        model: str,
        prompt_version: str,
        input: Any = None,
    ) -> Iterator[Generation]:
        yield _NoopGeneration()

    def event(self, name: str, *, attrs: Mapping[str, Any] | None = None) -> None:
        return None

    def end(self, *, outcome: str, policy_decision: str = "n/a", handoff: bool = False) -> None:
        return None


def _masked_mapping(attrs: Mapping[str, Any] | None) -> Any:
    if attrs is None:
        return None
    return mask(dict(attrs))


def _masked_items(attrs: Mapping[str, Any] | None) -> Iterator[tuple[str, Any]]:
    if not attrs:
        return
    masked = mask(dict(attrs))
    if isinstance(masked, Mapping):
        for key, value in masked.items():
            yield str(key), value


def _attr_value(value: Any) -> str | bool | int | float:
    if isinstance(value, str | bool | int | float):
        return value
    return repr(value)


class _LangfuseSpan:
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def end(self) -> None:
        if self._raw is None:
            return
        try:
            self._raw.end()
        except Exception:
            _LOGGER.warning("langfuse span end failed", exc_info=True)


class _LangfuseGeneration:
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def update(
        self,
        *,
        output: Any = None,
        usage: Usage | None = None,
        cost_usd: float | None = None,
    ) -> None:
        if self._raw is None:
            return
        payload: dict[str, Any] = {}
        if output is not None:
            payload["output"] = mask(output)
        details: dict[str, float] = {}
        if usage is not None:
            details["input"] = usage.input_tokens
            details["output"] = usage.output_tokens
        if cost_usd is not None:
            details["total_cost"] = cost_usd
        if details:
            payload["usage"] = details
        if not payload:
            return
        try:
            self._raw.update(**payload)
        except Exception:
            _LOGGER.warning("langfuse generation update failed", exc_info=True)

    def end(self) -> None:
        if self._raw is None:
            return
        try:
            self._raw.end()
        except Exception:
            _LOGGER.warning("langfuse generation end failed", exc_info=True)


class LangfuseTracer:
    """Sink that writes traces to a self-hosted Langfuse instance."""

    def __init__(self, *, conversation_id: str, turn_id: str) -> None:
        from langfuse import Langfuse

        settings = get_settings()
        self._client: Any = Langfuse(
            host=settings.langfuse_host,
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
        )
        self.trace_id = turn_id
        self._trace: Any = self._client.trace(id=turn_id, session_id=conversation_id)

    @contextmanager
    def span(self, name: str, *, attrs: Mapping[str, Any] | None = None) -> Iterator[Span]:
        raw: Any = None
        try:
            raw = self._trace.span(name=name, metadata=_masked_mapping(attrs))
        except Exception:
            _LOGGER.warning("langfuse span start failed", exc_info=True)
        wrapper = _LangfuseSpan(raw)
        try:
            yield wrapper
        finally:
            wrapper.end()

    @contextmanager
    def generation(
        self,
        name: str,
        *,
        model: str,
        prompt_version: str,
        input: Any = None,
    ) -> Iterator[Generation]:
        raw: Any = None
        try:
            raw = self._trace.generation(
                name=name,
                model=model,
                input=mask(input) if input is not None else None,
                metadata={"prompt_version": prompt_version},
            )
        except Exception:
            _LOGGER.warning("langfuse generation start failed", exc_info=True)
        wrapper = _LangfuseGeneration(raw)
        try:
            yield wrapper
        finally:
            wrapper.end()

    def event(self, name: str, *, attrs: Mapping[str, Any] | None = None) -> None:
        try:
            self._trace.event(name=name, metadata=_masked_mapping(attrs))
        except Exception:
            _LOGGER.warning("langfuse event failed", exc_info=True)

    def end(self, *, outcome: str, policy_decision: str = "n/a", handoff: bool = False) -> None:
        try:
            self._trace.update(
                output={"outcome": outcome},
                metadata={
                    "outcome": outcome,
                    "policy_decision": policy_decision,
                    "handoff": handoff,
                },
            )
        except Exception:
            _LOGGER.warning("langfuse trace end failed", exc_info=True)


class _OTelSpan:
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def end(self) -> None:
        if self._raw is None:
            return
        try:
            self._raw.end()
        except Exception:
            _LOGGER.warning("otel span end failed", exc_info=True)


class _OTelGeneration:
    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def update(
        self,
        *,
        output: Any = None,
        usage: Usage | None = None,
        cost_usd: float | None = None,
    ) -> None:
        if self._raw is None:
            return
        try:
            if output is not None:
                self._raw.set_attribute("revenueflow.output", _attr_value(mask(output)))
            if usage is not None:
                self._raw.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
                self._raw.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
            if cost_usd is not None:
                self._raw.set_attribute("revenueflow.cost_usd", cost_usd)
        except Exception:
            _LOGGER.warning("otel generation update failed", exc_info=True)

    def end(self) -> None:
        if self._raw is None:
            return
        try:
            self._raw.end()
        except Exception:
            _LOGGER.warning("otel generation end failed", exc_info=True)


class OTelTracer:
    """Sink that maps traces onto OpenTelemetry spans."""

    def __init__(self, *, conversation_id: str, turn_id: str) -> None:
        from opentelemetry import trace

        self._otel: Any = trace.get_tracer("revenueflow.observability")
        self.trace_id = turn_id
        self._root: Any = self._otel.start_span("turn")
        try:
            self._root.set_attribute("revenueflow.conversation_id", conversation_id)
            self._root.set_attribute("revenueflow.turn_id", turn_id)
        except Exception:
            _LOGGER.warning("otel root span setup failed", exc_info=True)

    @contextmanager
    def span(self, name: str, *, attrs: Mapping[str, Any] | None = None) -> Iterator[Span]:
        raw: Any = None
        try:
            raw = self._otel.start_span(name)
            for key, value in _masked_items(attrs):
                raw.set_attribute(key, _attr_value(value))
        except Exception:
            _LOGGER.warning("otel span start failed", exc_info=True)
        wrapper = _OTelSpan(raw)
        try:
            yield wrapper
        finally:
            wrapper.end()

    @contextmanager
    def generation(
        self,
        name: str,
        *,
        model: str,
        prompt_version: str,
        input: Any = None,
    ) -> Iterator[Generation]:
        raw: Any = None
        try:
            raw = self._otel.start_span(name)
            raw.set_attribute("gen_ai.request.model", model)
            raw.set_attribute("revenueflow.prompt_version", prompt_version)
            if input is not None:
                raw.set_attribute("revenueflow.input", _attr_value(mask(input)))
        except Exception:
            _LOGGER.warning("otel generation start failed", exc_info=True)
        wrapper = _OTelGeneration(raw)
        try:
            yield wrapper
        finally:
            wrapper.end()

    def event(self, name: str, *, attrs: Mapping[str, Any] | None = None) -> None:
        try:
            self._root.add_event(
                name, {key: _attr_value(value) for key, value in _masked_items(attrs)}
            )
        except Exception:
            _LOGGER.warning("otel event failed", exc_info=True)

    def end(self, *, outcome: str, policy_decision: str = "n/a", handoff: bool = False) -> None:
        try:
            self._root.set_attribute("revenueflow.outcome", outcome)
            self._root.set_attribute("revenueflow.policy_decision", policy_decision)
            self._root.set_attribute("revenueflow.handoff", handoff)
            self._root.end()
        except Exception:
            _LOGGER.warning("otel trace end failed", exc_info=True)


def new_tracer(*, conversation_id: str, turn_id: str) -> Tracer:
    sink = get_settings().tracer_sink
    if sink == "langfuse":
        try:
            return LangfuseTracer(conversation_id=conversation_id, turn_id=turn_id)
        except Exception:
            _LOGGER.warning("langfuse tracer unavailable; using noop", exc_info=True)
            return NoopTracer(turn_id=turn_id)
    if sink == "otel":
        try:
            return OTelTracer(conversation_id=conversation_id, turn_id=turn_id)
        except Exception:
            _LOGGER.warning("otel tracer unavailable; using noop", exc_info=True)
            return NoopTracer(turn_id=turn_id)
    return NoopTracer(turn_id=turn_id)


_DEFAULT: Tracer = NoopTracer()
_current: ContextVar[Tracer] = ContextVar("revenueflow_tracer")


def get_tracer() -> Tracer:
    return _current.get(_DEFAULT)


def set_tracer(tracer: Tracer) -> Token[Tracer]:
    return _current.set(tracer)


def reset_tracer(token: Token[Tracer]) -> None:
    _current.reset(token)
