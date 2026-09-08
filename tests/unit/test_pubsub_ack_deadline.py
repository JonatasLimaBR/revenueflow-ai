"""Regression: the subscription's ack_deadline_seconds must stay comfortably
above turn_budget_s, or a legitimately-slow-but-successful turn gets
redelivered mid-flight — found live: the same WhatsApp message processed
concurrently 3 times, competing for the same DB/checkpointer resources and
compounding the very slowness that triggered the redelivery."""

from pathlib import Path

from revenueflow.config import get_settings

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform" / "pubsub.tf"


def test_ack_deadline_exceeds_turn_budget_with_margin() -> None:
    body = _TF.read_text()
    block = body.split('resource "google_pubsub_subscription" "messages"', 1)[1].split(
        "\nresource ", 1
    )[0]
    line = next(
        line for line in block.splitlines() if "ack_deadline_seconds" in line and "=" in line
    )
    ack_deadline = int(line.split("=")[1].strip())

    get_settings.cache_clear()
    try:
        turn_budget_s = get_settings().turn_budget_s
    finally:
        get_settings.cache_clear()

    assert ack_deadline >= turn_budget_s * 2
