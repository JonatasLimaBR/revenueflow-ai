import importlib.util
import sys

import pytest

from revenueflow.observability import otel_setup


def test_module_imports_without_the_extra() -> None:
    assert hasattr(otel_setup, "configure_otel")


def test_configure_otel_without_opentelemetry_is_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    for name in list(sys.modules):
        if name == "opentelemetry" or name.startswith("opentelemetry."):
            monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setitem(sys.modules, "opentelemetry", None)

    with caplog.at_level("WARNING", logger="revenueflow.observability.otel_setup"):
        otel_setup.configure_otel()

    assert "opentelemetry not installed" in caplog.text


def _has_otel() -> bool:
    return (
        importlib.util.find_spec("opentelemetry.sdk.trace") is not None
        and importlib.util.find_spec("opentelemetry.exporter.cloud_trace") is not None
    )


@pytest.mark.skipif(not _has_otel(), reason="observability extra not installed")
def test_configure_otel_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    monkeypatch.setattr(trace, "_TRACER_PROVIDER", None, raising=False)

    otel_setup.configure_otel()
    first = trace.get_tracer_provider()
    otel_setup.configure_otel()
    second = trace.get_tracer_provider()

    assert isinstance(first, TracerProvider)
    assert first is second
