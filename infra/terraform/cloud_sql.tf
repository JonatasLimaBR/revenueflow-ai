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
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    deletion_protection_enabled = true
  }

  deletion_protection = true

  depends_on = [google_project_service.this]
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
