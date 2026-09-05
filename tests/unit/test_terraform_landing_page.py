from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform"


def test_landing_domain_variable_defaults_to_mastavista() -> None:
    body = (_TF / "variables.tf").read_text()
    assert 'variable "landing_domain"' in body
    block = body.split('variable "landing_domain"', 1)[1].split("variable ", 1)[0]
    assert 'default     = "mastavista.com.br"' in block


def test_https_resources_are_conditional_on_landing_domain() -> None:
    body = (_TF / "landing_page.tf").read_text()
    for resource in (
        'resource "google_compute_managed_ssl_certificate" "landing"',
        'resource "google_compute_target_https_proxy" "landing"',
        'resource "google_compute_global_forwarding_rule" "landing_https"',
        'resource "google_compute_url_map" "landing_redirect"',
    ):
        assert resource in body
        block = body.split(resource, 1)[1].split("\nresource ", 1)[0]
        assert 'count = var.landing_domain != "" ? 1 : 0' in block


def test_http_proxy_redirects_to_https_when_domain_set() -> None:
    body = (_TF / "landing_page.tf").read_text()
    block = body.split('resource "google_compute_target_http_proxy" "landing"', 1)[1]
    assert "google_compute_url_map.landing_redirect[0].id" in block
    assert "google_compute_url_map.landing.id" in block


def test_managed_cert_scoped_to_landing_domain_only() -> None:
    body = (_TF / "landing_page.tf").read_text()
    block = body.split('resource "google_compute_managed_ssl_certificate" "landing"', 1)[1]
    assert "domains = [var.landing_domain]" in block
