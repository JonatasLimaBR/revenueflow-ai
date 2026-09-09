# Self-hosted Langfuse (ADR-045 amendment): the tracer sink production has
# never actually pointed at (TRACER_SINK stayed "noop" in the real
# terraform.tfvars despite ADR-056 documenting a switch to "otel" — Cloud
# Trace confirmed empty via the API). The user chose self-hosted over
# Langfuse Cloud SaaS for full control. Same public-image container as
# docker-compose.yml's local `langfuse` service (langfuse/langfuse:2), same
# env shape, but backed by its own Postgres database on the existing Cloud
# SQL instance (cloud_sql.tf) instead of a second local container, and a
# fixed subdomain (subdomains.tf/landing_page.tf) instead of localhost so
# NEXTAUTH_URL is known before the service is ever created.
#
# Bootstrapping is still a one-time manual step, same pattern as the
# portal's OAuth Client ID: this Terraform only gets Langfuse itself
# running. The first person to open https://langfuse.<domain> creates the
# first admin account (signup is open by default — var.langfuse_disable_signup
# flips AUTH_DISABLE_SIGNUP once that account exists), then creates an
# organization/project and an API key pair in the Langfuse UI. Only then do
# LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY (already reserved in
# local.manual_secrets) get real values via `gcloud secrets versions add`,
# and only then does var.tracer_sink flip from "noop" to "langfuse" to wire
# revenueflow-api's AuditTracer at it.
resource "google_cloud_run_v2_service" "langfuse" {
  name     = "${var.service_name}-langfuse"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  deletion_protection = false

  template {
    service_account = google_service_account.api.email

    # Found live (2026-09-09): scale-to-zero here silently drops every
    # trace. The AuditTracer's LangfuseTracer flushes span/generation/event
    # calls fire-and-forget through the SDK's own HTTP client, which times
    # out well before a cold Next.js start (~18s measured) finishes — the
    # ingestion request never reaches this service at all (zero
    # /api/public/ingestion hits in its logs despite real turns running),
    # and the client just logs "Unexpected error occurred" and moves on.
    # min_instance_count=1 keeps it warm (~150ms once warm), same fix as
    # the portal service and for the same class of reason: a dependency
    # the app calls synchronously-ish per turn can't tolerate a cold start.
    scaling {
      min_instance_count = 1
      max_instance_count = 2
    }

    # Only private-range traffic (the Cloud SQL private IP) goes through the
    # connector — Vertex AI/Gemini and anything else still egresses direct.
    vpc_access {
      connector = google_vpc_access_connector.langfuse.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "langfuse/langfuse:2"

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      ports {
        container_port = 3000
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.langfuse_db_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "NEXTAUTH_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.langfuse_nextauth_secret.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "SALT"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.langfuse_salt.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "NEXTAUTH_URL"
        value = "https://${local.langfuse_subdomain}"
      }

      env {
        name  = "TELEMETRY_ENABLED"
        value = "false"
      }

      env {
        name  = "AUTH_DISABLE_SIGNUP"
        value = tostring(var.langfuse_disable_signup)
      }
    }
  }

  depends_on = [
    google_project_service.this,
    google_secret_manager_secret_iam_member.langfuse_db_url,
    google_secret_manager_secret_iam_member.langfuse_nextauth_secret,
    google_secret_manager_secret_iam_member.langfuse_salt,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "langfuse_public_invoker" {
  name     = google_cloud_run_v2_service.langfuse.name
  location = google_cloud_run_v2_service.langfuse.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
