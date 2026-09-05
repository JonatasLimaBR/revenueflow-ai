from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform"


def test_portal_service_declared() -> None:
    body = (_TF / "portal_service.tf").read_text()
    assert 'resource "google_cloud_run_v2_service" "portal"' in body
    assert 'name     = "${var.service_name}-portal"' in body
    assert 'command = ["python", "scripts/portal_server.py"]' in body


def test_portal_does_not_scale_to_zero() -> None:
    body = (_TF / "portal_service.tf").read_text()
    block = body.split('resource "google_cloud_run_v2_service" "portal"', 1)[1]
    assert "min_instance_count = 1" in block
    assert "min_instance_count = 0" not in block


def test_portal_invoker_is_public_app_level_auth() -> None:
    body = (_TF / "portal_service.tf").read_text()
    assert 'resource "google_cloud_run_v2_service_iam_member" "portal_public_invoker"' in body
    block = body.split(
        'resource "google_cloud_run_v2_service_iam_member" "portal_public_invoker"', 1
    )[1]
    assert 'role     = "roles/run.invoker"' in block
    assert 'member   = "allUsers"' in block


def test_portal_reuses_dashboard_viewer_emails() -> None:
    body = (_TF / "portal_service.tf").read_text()
    assert 'join(",", var.dashboard_viewer_emails)' in body


def test_portal_secrets_declared() -> None:
    body = (_TF / "secrets.tf").read_text()
    assert "PORTAL_GOOGLE_CLIENT_ID" in body
    assert "PORTAL_SESSION_SECRET" in body
    assert 'resource "random_password" "portal_session_secret"' in body


def test_portal_url_output_declared() -> None:
    body = (_TF / "outputs.tf").read_text()
    assert 'output "portal_url"' in body
    assert "google_cloud_run_v2_service.portal.uri" in body
