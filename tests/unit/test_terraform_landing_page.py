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


def test_managed_cert_covers_root_domain_and_subdomains() -> None:
    # Extended (SUBDOMAINS) to also cover mcp./portal. — still just the
    # domains this deploy actually configures, via compact(), never a
    # hardcoded or unrelated domain.
    body = (_TF / "landing_page.tf").read_text()
    block = body.split('resource "google_compute_managed_ssl_certificate" "landing"', 1)[1]
    assert (
        "domains = compact([var.landing_domain, local.mcp_subdomain, local.portal_subdomain])"
        in block
    )


def test_managed_cert_uses_create_before_destroy_with_a_dynamic_name() -> None:
    # Real production failure (2026-09-06): `domains` forces replacement, and
    # without create_before_destroy Terraform destroys the old cert first —
    # GCP rejects that with resourceInUseByAnotherResource because the HTTPS
    # proxy still references it. create_before_destroy alone isn't enough
    # either: the name must also change whenever domains changes, or the new
    # cert collides with the old one's still-live name. Both together are the
    # fix — regression-test each half.
    body = (_TF / "landing_page.tf").read_text()
    block = body.split('resource "google_compute_managed_ssl_certificate" "landing"', 1)[1].split(
        "\nresource ", 1
    )[0]
    assert "create_before_destroy = true" in block
    assert "sha1(join(" in block
    assert 'name = "${var.service_name}-landing-cert"' not in block
