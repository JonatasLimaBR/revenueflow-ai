from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform"


_SERVICES = ("mcp_readonly", "portal", "langfuse")


def test_negs_declared_for_all_services() -> None:
    body = (_TF / "subdomains.tf").read_text()
    for service in _SERVICES:
        assert f'resource "google_compute_region_network_endpoint_group" "{service}"' in body
    assert body.count('network_endpoint_type = "SERVERLESS"') == len(_SERVICES)


def test_neg_services_point_at_the_right_cloud_run_service() -> None:
    body = (_TF / "subdomains.tf").read_text()
    for service in _SERVICES:
        block = body.split(
            f'resource "google_compute_region_network_endpoint_group" "{service}"', 1
        )[1].split("\nresource ", 1)[0]
        assert f"google_cloud_run_v2_service.{service}.name" in block


def test_backend_services_declared() -> None:
    body = (_TF / "subdomains.tf").read_text()
    for service in _SERVICES:
        assert f'resource "google_compute_backend_service" "{service}"' in body


def test_url_map_has_host_rules_for_all_subdomains() -> None:
    body = (_TF / "landing_page.tf").read_text()
    assert "local.mcp_subdomain" in body
    assert "local.portal_subdomain" in body
    assert "local.langfuse_subdomain" in body
    assert body.count('dynamic "host_rule"') == len(_SERVICES)
    assert body.count('dynamic "path_matcher"') == len(_SERVICES)
    # the bare domain must keep hitting the bucket, unconditionally
    assert "default_service = google_compute_backend_bucket.landing.id" in body


def test_managed_cert_lists_all_subdomains() -> None:
    body = (_TF / "landing_page.tf").read_text()
    cert_block = body.split('resource "google_compute_managed_ssl_certificate" "landing"', 1)[
        1
    ].split("\nresource ", 1)[0]
    assert "local.mcp_subdomain" in cert_block
    assert "local.portal_subdomain" in cert_block
    assert "local.langfuse_subdomain" in cert_block
    assert "var.landing_domain" in cert_block


def test_domain_outputs_declared() -> None:
    body = (_TF / "outputs.tf").read_text()
    assert 'output "mcp_domain_url"' in body
    assert 'output "portal_domain_url"' in body
    assert 'output "langfuse_domain_url"' in body
