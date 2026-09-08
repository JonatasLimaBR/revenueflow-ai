"""Regression: the main API service must not silently fall back to Cloud
Run's bare-default resources (512Mi/1 CPU) — that default never actually
matched the real workload (LangGraph, 2 psycopg pools, the Vertex AI
client, and concurrent turns during a Pub/Sub redelivery storm). Found
live: an instance restart pattern ("Starting new instance" then "Shutting
down" ~10s apart, mid-turn, no clean ack/nack logged) consistent with an
OOM kill."""

from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform" / "cloud_run.tf"


def _api_service_block() -> str:
    body = _TF.read_text()
    return body.split('resource "google_cloud_run_v2_service" "api"', 1)[1].split(
        '\nresource "google_cloud_run_v2_service"', 1
    )[0]


def test_api_service_sets_explicit_memory_limit() -> None:
    block = _api_service_block()
    assert "resources" in block
    assert 'memory = "2Gi"' in block
