locals {
  # env var name (config.py) => Secret Manager secret id. The values for these
  # are added by the human (runbook Fase 3) with `gcloud secrets versions add`
  # BEFORE the first Cloud Run revision can go healthy.
  manual_secrets = {
    WHATSAPP_APP_SECRET      = "revenueflow-whatsapp-app-secret"
    WHATSAPP_ACCESS_TOKEN    = "revenueflow-whatsapp-access-token"
    WHATSAPP_VERIFY_TOKEN    = "revenueflow-whatsapp-verify-token"
    WHATSAPP_PHONE_NUMBER_ID = "revenueflow-whatsapp-phone-number-id"
    LANGFUSE_PUBLIC_KEY      = "revenueflow-langfuse-public-key"
    LANGFUSE_SECRET_KEY      = "revenueflow-langfuse-secret-key"
    APPROVAL_API_TOKEN       = "revenueflow-approval-api-token"
    HANDOFF_API_TOKEN        = "revenueflow-handoff-api-token"
  }
}

resource "google_secret_manager_secret" "manual" {
  for_each  = local.manual_secrets
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.this]
}

# Created and versioned by Terraform. Used by the human migration step (Fase 6);
# the runtime service reads DATABASE_URL, not this.
resource "google_secret_manager_secret" "db_password" {
  secret_id = "revenueflow-db-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.this]
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db.result
}

resource "google_secret_manager_secret" "db_url" {
  secret_id = "revenueflow-database-url"

  replication {
    auto {}
  }

  depends_on = [google_project_service.this]
}

resource "google_secret_manager_secret_version" "db_url" {
  secret      = google_secret_manager_secret.db_url.id
  secret_data = "postgresql://${google_sql_user.app.name}:${random_password.db.result}@/${google_sql_database.app.name}?host=/cloudsql/${google_sql_database_instance.oltp.connection_name}"
}

# The approval-route bearer token (ADR-050). Terraform generates the first value
# so the deploy is not gated on a manual `gcloud secrets versions add`; rotate
# later by adding a new version. Read the current one with:
#   gcloud secrets versions access latest --secret=revenueflow-approval-api-token
resource "random_password" "approval_token" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret_version" "approval_api_token" {
  secret      = google_secret_manager_secret.manual["APPROVAL_API_TOKEN"].id
  secret_data = random_password.approval_token.result
}

# The handoff-route bearer token (ADR-054). Same Terraform-generated pattern as
# the approval token so the deploy is not gated on a manual add; a separate
# secret keeps the internal scopes isolated. Read the current one with:
#   gcloud secrets versions access latest --secret=revenueflow-handoff-api-token
resource "random_password" "handoff_token" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret_version" "handoff_api_token" {
  secret      = google_secret_manager_secret.manual["HANDOFF_API_TOKEN"].id
  secret_data = random_password.handoff_token.result
}

resource "google_secret_manager_secret_iam_member" "api_manual" {
  for_each  = google_secret_manager_secret.manual
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_db_url" {
  secret_id = google_secret_manager_secret.db_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}
