FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
# [events] pulls google-cloud-pubsub for the in-process pull consumer
# (RUN_CONSUMER=1, ADR-047); [llm] pulls google-genai for the real Vertex path
# (LLM_STUB=0, ADR-049); [observability] pulls the OTel Cloud Trace exporter
# (TRACER_SINK=otel, ADR-056); [analytics] pulls google-cloud-bigquery for the
# revenue/cost sync batch job (revenueflow-analytics-sync, ADR-061). Without
# them run_subscriber() / model calls / span export / scripts/sync_analytics.py
# die.
RUN pip install --upgrade pip && pip install -e ".[events,llm,observability,analytics]"

COPY migrations ./migrations
COPY seeds ./seeds
COPY scripts ./scripts

EXPOSE 8000

# Honor $PORT (Cloud Run injects it); fall back to 8000 for local runs.
CMD ["sh", "-c", "exec uvicorn revenueflow.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
