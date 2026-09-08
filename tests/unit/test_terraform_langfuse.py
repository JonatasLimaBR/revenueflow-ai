from pathlib import Path

_TF = Path(__file__).resolve().parents[2] / "infra" / "terraform"


def test_langfuse_service_declared() -> None:
    body = (_TF / "langfuse_service.tf").read_text()
    assert 'resource "google_cloud_run_v2_service" "langfuse"' in body
    assert 'name     = "${var.service_name}-langfuse"' in body
    assert 'image = "langfuse/langfuse:2"' in body
    assert "container_port = 3000" in body


def test_langfuse_scales_to_zero() -> None:
    body = (_TF / "langfuse_service.tf").read_text()
    block = body.split('resource "google_cloud_run_v2_service" "langfuse"', 1)[1]
    assert "min_instance_count = 0" in block


def test_langfuse_invoker_is_public_app_level_auth() -> None:
    body = (_TF / "langfuse_service.tf").read_text()
    assert 'resource "google_cloud_run_v2_service_iam_member" "langfuse_public_invoker"' in body
    block = body.split(
        'resource "google_cloud_run_v2_service_iam_member" "langfuse_public_invoker"', 1
    )[1]
    assert 'role     = "roles/run.invoker"' in block
    assert 'member   = "allUsers"' in block


def test_langfuse_secrets_are_never_plain_env_values() -> None:
    # DATABASE_URL/NEXTAUTH_SECRET/SALT all carry real credentials -- they
    # must come from Secret Manager (value_source), never a bare `value`.
    body = (_TF / "langfuse_service.tf").read_text()
    block = body.split('resource "google_cloud_run_v2_service" "langfuse"', 1)[1]
    for secret_ref in (
        "google_secret_manager_secret.langfuse_db_url.secret_id",
        "google_secret_manager_secret.langfuse_nextauth_secret.secret_id",
        "google_secret_manager_secret.langfuse_salt.secret_id",
    ):
        assert secret_ref in block


def test_langfuse_nextauth_url_uses_the_fixed_subdomain_not_localhost() -> None:
    # Cloud Run's own generated URL isn't known before the service exists;
    # a custom subdomain (known at plan time) sidesteps that entirely.
    body = (_TF / "langfuse_service.tf").read_text()
    block = body.split('resource "google_cloud_run_v2_service" "langfuse"', 1)[1]
    assert 'value = "https://${local.langfuse_subdomain}"' in block
    assert "localhost" not in block


def test_langfuse_gets_its_own_database_separate_from_the_app() -> None:
    body = (_TF / "cloud_sql.tf").read_text()
    assert 'resource "google_sql_database" "langfuse"' in body
    assert 'name     = "langfuse"' in body
    assert 'resource "google_sql_user" "langfuse"' in body
    # same instance as the app database, not a second Cloud SQL instance
    assert body.count("google_sql_database_instance.oltp.name") >= 3


def test_langfuse_secrets_declared_and_iam_granted() -> None:
    body = (_TF / "secrets.tf").read_text()
    assert 'resource "google_secret_manager_secret" "langfuse_db_url"' in body
    assert 'resource "google_secret_manager_secret" "langfuse_nextauth_secret"' in body
    assert 'resource "google_secret_manager_secret" "langfuse_salt"' in body
    for secret in ("langfuse_db_url", "langfuse_nextauth_secret", "langfuse_salt"):
        assert f'resource "google_secret_manager_secret_iam_member" "{secret}"' in body


def test_langfuse_db_url_is_a_plain_tcp_dsn_not_a_unix_socket() -> None:
    # Langfuse's Prisma/Node client doesn't speak the /cloudsql unix-socket
    # DSN convention the app's own psycopg pools use. Private IP, not
    # public — see test_terraform_langfuse_network.py for the regression
    # this was found and fixed for (P1001, public IP unreachable by default).
    body = (_TF / "secrets.tf").read_text()
    block = body.split('resource "google_secret_manager_secret_version" "langfuse_db_url"', 1)[1]
    assert "google_sql_database_instance.oltp.private_ip_address" in block
    assert "sslmode=require" in block
    assert "/cloudsql/" not in block


def test_langfuse_domain_url_output_declared() -> None:
    body = (_TF / "outputs.tf").read_text()
    assert 'output "langfuse_domain_url"' in body
    assert "local.langfuse_subdomain" in body


def test_langfuse_host_default_matches_the_service_subdomain() -> None:
    body = (_TF / "variables.tf").read_text()
    block = body.split('variable "langfuse_host"', 1)[1].split("variable ", 1)[0]
    assert 'default     = "https://langfuse.mastavista.com.br"' in block
