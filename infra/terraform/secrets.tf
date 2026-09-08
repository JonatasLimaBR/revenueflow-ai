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
    MCP_API_TOKEN            = "revenueflow-mcp-api-token"
    PORTAL_GOOGLE_CLIENT_ID  = "revenueflow-portal-google-client-id"
    PORTAL_SESSION_SECRET    = "revenueflow-portal-session-secret"
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

# The public read-only MCP server's bearer token (ADR-067) — same
# Terraform-generated pattern as the approval/handoff tokens, same isolated-scope
# rationale (a separate secret per route family). Read the current one with:
#   gcloud secrets versions access latest --secret=revenueflow-mcp-api-token
resource "random_password" "mcp_token" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret_version" "mcp_api_token" {
  secret      = google_secret_manager_secret.manual["MCP_API_TOKEN"].id
  secret_data = random_password.mcp_token.result
}

# The portal's session-cookie signing secret (ADR-073) — same
# Terraform-generated pattern as the approval/handoff/mcp tokens (not a
# manual gcloud step). PORTAL_GOOGLE_CLIENT_ID stays a manual secret (it's a
# public OAuth Client ID, not a real secret, but follows the same
# manual-config pattern as the WhatsApp secrets until the user creates it in
# the Google Cloud Console). Read the current session secret with:
#   gcloud secrets versions access latest --secret=revenueflow-portal-session-secret
resource "random_password" "portal_session_secret" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret_version" "portal_session_secret" {
  secret      = google_secret_manager_secret.manual["PORTAL_SESSION_SECRET"].id
  secret_data = random_password.portal_session_secret.result
}

# Langfuse's own Postgres DSN (its Prisma/Node client, unlike the app's
# psycopg pools, doesn't speak the /cloudsql unix-socket DSN convention — a
# plain host:port DSN, same ssl_mode=ENCRYPTED_ONLY the instance already
# enforces). Fix pós-merge (2026-09-08): the first deploy used the
# instance's PUBLIC IP and failed (`P1001: Can't reach database server`) —
# ipv4_enabled=true without authorized_networks blocks every external IP by
# default, it does not open the instance up. The private IP (reachable only
# via the VPC connector, langfuse_network.tf/langfuse_service.tf) is the
# fix, not opening authorized_networks to the internet.
resource "google_secret_manager_secret" "langfuse_db_url" {
  secret_id = "revenueflow-langfuse-database-url"

  replication {
    auto {}
  }

  depends_on = [google_project_service.this]
}

resource "google_secret_manager_secret_version" "langfuse_db_url" {
  secret      = google_secret_manager_secret.langfuse_db_url.id
  secret_data = "postgresql://${google_sql_user.langfuse.name}:${random_password.langfuse_db.result}@${google_sql_database_instance.oltp.private_ip_address}:5432/${google_sql_database.langfuse.name}?sslmode=require"
}

# Langfuse's NextAuth cookie-signing secret and password-hashing salt —
# Terraform-generated, same not-gated-on-a-manual-step pattern as the
# approval/handoff/mcp/portal_session tokens above. Read either with:
#   gcloud secrets versions access latest --secret=revenueflow-langfuse-nextauth-secret
#   gcloud secrets versions access latest --secret=revenueflow-langfuse-salt
resource "google_secret_manager_secret" "langfuse_nextauth_secret" {
  secret_id = "revenueflow-langfuse-nextauth-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.this]
}

resource "random_password" "langfuse_nextauth_secret" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret_version" "langfuse_nextauth_secret" {
  secret      = google_secret_manager_secret.langfuse_nextauth_secret.id
  secret_data = random_password.langfuse_nextauth_secret.result
}

resource "google_secret_manager_secret" "langfuse_salt" {
  secret_id = "revenueflow-langfuse-salt"

  replication {
    auto {}
  }

  depends_on = [google_project_service.this]
}

resource "random_password" "langfuse_salt" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret_version" "langfuse_salt" {
  secret      = google_secret_manager_secret.langfuse_salt.id
  secret_data = random_password.langfuse_salt.result
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

# Langfuse's own secrets (langfuse_service.tf) — the api service account is
# reused for this Cloud Run service too, same as portal/mcp_readonly.
resource "google_secret_manager_secret_iam_member" "langfuse_db_url" {
  secret_id = google_secret_manager_secret.langfuse_db_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "langfuse_nextauth_secret" {
  secret_id = google_secret_manager_secret.langfuse_nextauth_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "langfuse_salt" {
  secret_id = google_secret_manager_secret.langfuse_salt.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}
