resource "google_sql_database_instance" "oltp" {
  name             = "${var.service_name}-oltp"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    # Pin Enterprise: the API now defaults new instances to ENTERPRISE_PLUS, which
    # rejects shared-core / db-custom-* tiers (only db-perf-optimized-N-* are valid
    # there). var.db_tier (db-custom-1-3840) is an Enterprise tier and keeps V1 cost down.
    edition           = "ENTERPRISE"
    tier              = var.db_tier
    availability_type = "ZONAL"

    backup_configuration {
      enabled = true
    }

    ip_configuration {
      ipv4_enabled    = true
      ssl_mode        = "ENCRYPTED_ONLY"
      private_network = data.google_compute_network.default.id
    }

    deletion_protection_enabled = true
  }

  deletion_protection = true

  # private_network needs the VPC peering (langfuse_network.tf) to exist
  # first, or the instance update is rejected.
  depends_on = [
    google_project_service.this,
    google_service_networking_connection.private_service_access,
  ]
}

resource "google_sql_database" "app" {
  name     = "revenueflow"
  instance = google_sql_database_instance.oltp.name
}

resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "_-"
}

resource "google_sql_user" "app" {
  name     = "revenueflow"
  instance = google_sql_database_instance.oltp.name
  password = random_password.db.result
}

# Langfuse (self-hosted, ADR-045/056 amendment) gets its own database + user
# on the same instance rather than a second Cloud SQL instance — same
# reuse-the-instance pattern as the app's own database, keeps V1 cost down.
resource "google_sql_database" "langfuse" {
  name     = "langfuse"
  instance = google_sql_database_instance.oltp.name
}

resource "random_password" "langfuse_db" {
  length           = 32
  special          = true
  override_special = "_-"
}

resource "google_sql_user" "langfuse" {
  name     = "langfuse"
  instance = google_sql_database_instance.oltp.name
  password = random_password.langfuse_db.result
}
