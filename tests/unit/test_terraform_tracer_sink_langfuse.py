from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform"


def test_tracer_sink_defaults_to_langfuse() -> None:
    # ADR-045/075: production points at self-hosted Langfuse once the
    # manual bootstrap (admin account, org/project, API key pair, secrets
    # populated) is done -- confirmed 2026-09-09. The workflow never passes
    # -var tracer_sink=..., so this default is what actually deploys.
    body = (_TF / "variables.tf").read_text()
    block = body.split('variable "tracer_sink"', 1)[1].split("variable ", 1)[0]
    assert 'default = "langfuse"' in block


def test_langfuse_signup_locked_down_by_default() -> None:
    body = (_TF / "variables.tf").read_text()
    block = body.split('variable "langfuse_disable_signup"', 1)[1].split("variable ", 1)[0]
    assert "default = true" in block
