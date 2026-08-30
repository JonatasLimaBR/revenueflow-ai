# Infra stub for the RevenueFlow inbound slice. Reviewed with `terraform fmt`,
# `terraform validate` and `terraform plan` only; `apply` / `destroy` require
# explicit human approval (ADR-043) and are never run from an agent harness.

resource "google_service_account" "api" {
  account_id   = "${var.service_name}-sa"
  display_name = "RevenueFlow API runtime identity"
}

resource "google_pubsub_topic" "messages" {
  name = "revenueflow-messages"
}

resource "google_pubsub_subscription" "messages_worker" {
  name  = "revenueflow-messages-worker"
  topic = google_pubsub_topic.messages.id

  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "300s"
  }
}

resource "google_sql_database_instance" "oltp" {
  name             = "${var.service_name}-oltp"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier              = var.db_tier
    availability_type = "ZONAL"

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = true
}

resource "google_sql_database" "app" {
  name     = "revenueflow"
  instance = google_sql_database_instance.oltp.name
}

resource "google_secret_manager_secret" "whatsapp_app_secret" {
  secret_id = "revenueflow-whatsapp-app-secret"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "whatsapp_access_token" {
  secret_id = "revenueflow-whatsapp-access-token"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "api_reads_app_secret" {
  secret_id = google_secret_manager_secret.whatsapp_app_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_reads_access_token" {
  secret_id = google_secret_manager_secret.whatsapp_access_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name     = var.service_name
  location = var.region

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/revenueflow/api:latest"

      env {
        name  = "PUBSUB_PROJECT_ID"
        value = var.project_id
      }
    }
  }
}
