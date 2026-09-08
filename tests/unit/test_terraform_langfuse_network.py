from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform"


def test_private_service_access_peering_declared() -> None:
    body = (_TF / "langfuse_network.tf").read_text()
    assert 'resource "google_compute_global_address" "private_service_access"' in body
    assert 'purpose       = "VPC_PEERING"' in body
    assert 'resource "google_service_networking_connection" "private_service_access"' in body


def test_vpc_connector_declared_for_langfuse() -> None:
    body = (_TF / "langfuse_network.tf").read_text()
    assert 'resource "google_vpc_access_connector" "langfuse"' in body


def test_vpc_connector_name_fits_the_gcp_25_char_limit() -> None:
    # Regression: "${var.service_name}-langfuse-vpc" (28 chars with the
    # default service_name) exceeded GCP's connector ID limit
    # (^[a-z][-a-z0-9]{0,23}[a-z0-9]$, max 25) and the apply failed with a
    # 400. "lf" instead of "langfuse" fits (22 chars with the default).
    body = (_TF / "langfuse_network.tf").read_text()
    block = body.split('resource "google_vpc_access_connector" "langfuse"', 1)[1].split(
        "\nresource ", 1
    )[0]
    default_service_name = "revenueflow-api"
    name_expr = block.split('name          = "', 1)[1].split('"', 1)[0]
    rendered = name_expr.replace("${var.service_name}", default_service_name)
    assert len(rendered) <= 25, f"connector name '{rendered}' ({len(rendered)} chars) exceeds 25"


def test_vpc_connector_specifies_max_instances() -> None:
    # Regression: the GCP API rejects a connector create call unless
    # max_throughput or max_instances is explicit -- left implicit, the
    # apply failed with "must specify either max_throughput or max_instances".
    body = (_TF / "langfuse_network.tf").read_text()
    block = body.split('resource "google_vpc_access_connector" "langfuse"', 1)[1].split(
        "\nresource ", 1
    )[0]
    assert "max_instances" in block


def test_cloud_sql_instance_gets_a_private_network() -> None:
    # Regression: the first apply used the instance's PUBLIC IP for the
    # Langfuse DSN and failed (`P1001: Can't reach database server`) —
    # ipv4_enabled=true without authorized_networks blocks every external
    # IP by default, it does not open the instance up. A private IP
    # reachable only via the VPC connector is the fix.
    body = (_TF / "cloud_sql.tf").read_text()
    block = body.split('resource "google_sql_database_instance" "oltp"', 1)[1].split(
        "\nresource ", 1
    )[0]
    assert "private_network = data.google_compute_network.default.id" in block
    assert "google_service_networking_connection.private_service_access" in block


def test_langfuse_db_url_uses_the_private_ip_not_public() -> None:
    body = (_TF / "secrets.tf").read_text()
    block = body.split('resource "google_secret_manager_secret_version" "langfuse_db_url"', 1)[1]
    assert "google_sql_database_instance.oltp.private_ip_address" in block
    assert "public_ip_address" not in block


def test_langfuse_service_uses_the_vpc_connector() -> None:
    body = (_TF / "langfuse_service.tf").read_text()
    block = body.split('resource "google_cloud_run_v2_service" "langfuse"', 1)[1]
    assert "vpc_access" in block
    assert "google_vpc_access_connector.langfuse.id" in block
    assert 'egress    = "PRIVATE_RANGES_ONLY"' in block


def test_networking_apis_enabled() -> None:
    body = (_TF / "apis.tf").read_text()
    assert "servicenetworking.googleapis.com" in body
    assert "vpcaccess.googleapis.com" in body


def test_no_authorized_networks_opened_to_the_internet() -> None:
    # The fix must never be "allow 0.0.0.0/0" -- that would trade one
    # outage for a real security regression (ADR-031).
    body = (_TF / "cloud_sql.tf").read_text()
    assert "authorized_networks" not in body
    assert "0.0.0.0/0" not in body
