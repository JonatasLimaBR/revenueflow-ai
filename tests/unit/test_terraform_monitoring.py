import json
from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform"

_LOG_METRICS = {
    "revenueflow_turn_cost_usd",
    "revenueflow_turn_latency_ms",
    "revenueflow_turns",
    "revenueflow_handoffs",
    "revenueflow_tool_failures",
}


def test_monitoring_tf_declares_all_log_metrics() -> None:
    body = (_TF / "monitoring.tf").read_text()
    for name in _LOG_METRICS:
        assert f'"{name}"' in body
    assert body.count('resource "google_monitoring_alert_policy"') == 5
    assert 'resource "google_monitoring_dashboard" "revenueflow_ops"' in body
    assert "condition_absent" in body


def test_distribution_alerts_use_percentile_not_sum() -> None:
    # ADR-072 (corrects ADR-071): ALIGN_SUM never scalarizes a DISTRIBUTION
    # log metric, and value_extractor is only legal on DISTRIBUTION metrics —
    # so a plain-numeric sibling metric isn't buildable either. The
    # tool_failures/ai_cost_per_hour alerts stay on the original histogram
    # metrics (the dashboard needs them) but must use a percentile aligner,
    # never ALIGN_SUM, to produce a comparable scalar.
    body = (_TF / "monitoring.tf").read_text()
    tool_failures_block = body.split(
        'resource "google_monitoring_alert_policy" "tool_failures"', 1
    )[1].split("\nresource ", 1)[0]
    assert 'per_series_aligner = "ALIGN_PERCENTILE_99"' in tool_failures_block
    assert 'per_series_aligner = "ALIGN_SUM"' not in tool_failures_block

    cost_block = body.split('resource "google_monitoring_alert_policy" "ai_cost_per_hour"', 1)[
        1
    ].split("\nresource ", 1)[0]
    assert 'per_series_aligner = "ALIGN_PERCENTILE_99"' in cost_block
    assert 'per_series_aligner = "ALIGN_SUM"' not in cost_block


def test_alert_email_variable_has_a_default() -> None:
    body = (_TF / "variables.tf").read_text()
    assert 'variable "alert_email"' in body
    block = body.split('variable "alert_email"', 1)[1].split("variable ", 1)[0]
    assert "default" in block


def test_cloudtrace_api_and_role_are_wired() -> None:
    assert "cloudtrace.googleapis.com" in (_TF / "apis.tf").read_text()
    assert "roles/cloudtrace.agent" in (_TF / "iam.tf").read_text()


def test_dashboard_json_is_valid_and_references_expected_metrics() -> None:
    payload = json.loads((_TF / "dashboards" / "revenueflow_ops.json").read_text())
    tiles = payload["mosaicLayout"]["tiles"]
    assert len(tiles) >= 4
    blob = json.dumps(payload)
    assert "run.googleapis.com/request_" in blob
    assert "logging.googleapis.com/user/revenueflow_" in blob


def test_dashboard_viewer_emails_variable_defaults_to_empty_list() -> None:
    body = (_TF / "variables.tf").read_text()
    assert 'variable "dashboard_viewer_emails"' in body
    block = body.split('variable "dashboard_viewer_emails"', 1)[1].split("variable ", 1)[0]
    assert "default     = []" in block


def test_dashboard_viewer_iam_is_monitoring_viewer_only() -> None:
    body = (_TF / "monitoring.tf").read_text()
    assert 'resource "google_project_iam_member" "dashboard_viewer"' in body
    block = body.split('resource "google_project_iam_member" "dashboard_viewer"', 1)[1]
    assert "for_each" in block
    assert "roles/monitoring.viewer" in block
    assert "roles/viewer" not in block
