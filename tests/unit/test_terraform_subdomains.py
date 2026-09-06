from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform"


def test_negs_declared_for_both_services() -> None:
    body = (_TF / "subdomains.tf").read_text()
    assert 'resource "google_compute_region_network_endpoint_group" "mcp_readonly"' in body
    assert 'resource "google_compute_region_network_endpoint_group" "portal"' in body
    assert body.count('network_endpoint_type = "SERVERLESS"') == 2


def test_neg_services_point_at_the_right_cloud_run_service() -> None:
    body = (_TF / "subdomains.tf").read_text()
    mcp_block = body.split(
        'resource "google_compute_region_network_endpoint_group" "mcp_readonly"', 1
    )[1].split("\nresource ", 1)[0]
    assert "google_cloud_run_v2_service.mcp_readonly.name" in mcp_block

    portal_block = body.split(
        'resource "google_compute_region_network_endpoint_group" "portal"', 1
    )[1].split("\nresource ", 1)[0]
    assert "google_cloud_run_v2_service.portal.name" in portal_block


def test_backend_services_declared() -> None:
    body = (_TF / "subdomains.tf").read_text()
    assert 'resource "google_compute_backend_service" "mcp_readonly"' in body
    assert 'resource "google_compute_backend_service" "portal"' in body


def test_url_map_has_host_rules_for_both_subdomains() -> None:
    body = (_TF / "landing_page.tf").read_text()
    assert "local.mcp_subdomain" in body
    assert "local.portal_subdomain" in body
    assert body.count('dynamic "host_rule"') == 2
    assert body.count('dynamic "path_matcher"') == 2
    # the bare domain must keep hitting the bucket, unconditionally
    assert "default_service = google_compute_backend_bucket.landing.id" in body


def test_managed_cert_lists_both_subdomains() -> None:
    body = (_TF / "landing_page.tf").read_text()
    cert_block = body.split('resource "google_compute_managed_ssl_certificate" "landing"', 1)[
        1
    ].split("\nresource ", 1)[0]
    assert "local.mcp_subdomain" in cert_block
    assert "local.portal_subdomain" in cert_block
    assert "var.landing_domain" in cert_block


def test_domain_outputs_declared() -> None:
    body = (_TF / "outputs.tf").read_text()
    assert 'output "mcp_domain_url"' in body
    assert 'output "portal_domain_url"' in body
