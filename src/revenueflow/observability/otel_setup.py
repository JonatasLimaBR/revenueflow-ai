"""Global OpenTelemetry TracerProvider wired to Cloud Trace (ADR-056).

Called from the app lifespan only when ``settings.tracer_sink == "otel"``. The
SDK and the GCP exporter are imported lazily so this module stays importable
without the ``observability`` extra; a missing dependency downgrades to a
warning instead of raising. Idempotent: a second call is a no-op.
"""

from __future__ import annotations

import logging

from revenueflow.config import get_settings

_LOGGER = logging.getLogger(__name__)


def configure_otel() -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        _LOGGER.warning("opentelemetry not installed; install .[observability] for otel sink")
        return

    try:
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
    except ImportError:
        _LOGGER.warning("cloud-trace exporter not installed; install .[observability]")
        return

    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return

    settings = get_settings()
    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name})
    )
    provider.add_span_processor(
        BatchSpanProcessor(CloudTraceSpanExporter(project_id=settings.google_cloud_project))
    )
    trace.set_tracer_provider(provider)
    _LOGGER.info("otel.configured", extra={"exporter": "cloud_trace"})
