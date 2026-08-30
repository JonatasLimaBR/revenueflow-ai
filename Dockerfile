FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e .

COPY migrations ./migrations
COPY seeds ./seeds
COPY scripts ./scripts

EXPOSE 8000

CMD ["uvicorn", "revenueflow.main:app", "--host", "0.0.0.0", "--port", "8000"]
