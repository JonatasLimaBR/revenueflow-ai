FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
# [events] pulls google-cloud-pubsub for the in-process pull consumer
# (RUN_CONSUMER=1, ADR-047); [llm] pulls google-genai for the real Vertex path
# (LLM_STUB=0, ADR-049). Without them run_subscriber() / the model calls die.
RUN pip install --upgrade pip && pip install -e ".[events,llm]"

COPY migrations ./migrations
COPY seeds ./seeds
COPY scripts ./scripts

EXPOSE 8000

# Honor $PORT (Cloud Run injects it); fall back to 8000 for local runs.
CMD ["sh", "-c", "exec uvicorn revenueflow.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
