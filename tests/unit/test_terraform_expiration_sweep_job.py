from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform"


def test_expiration_sweep_job_declared() -> None:
    body = (_TF / "expiration_sweep_job.tf").read_text()
    assert 'resource "google_cloud_run_v2_job" "expiration_sweep"' in body
    assert 'command = ["python", "scripts/sweep_expirations.py"]' in body


def test_expiration_sweep_job_sets_pubsub_project_id() -> None:
    # Regression: unlike the other batch jobs, this one publishes
    # approval_decided (services/expiration.py) -- without PUBSUB_PROJECT_ID
    # set, _default_publisher() falls back to the in-memory publisher and
    # the expired approval's resume never reaches the paused turn.
    body = (_TF / "expiration_sweep_job.tf").read_text()
    block = body.split('resource "google_cloud_run_v2_job" "expiration_sweep"', 1)[1]
    assert 'name  = "PUBSUB_PROJECT_ID"' in block
    assert "google_pubsub_topic_iam_member.api_publisher" in block
