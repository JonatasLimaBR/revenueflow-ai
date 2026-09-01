locals {
  # LANGFUSE_* secrets are only mounted when the sink is langfuse; Cloud Run v2
  # requires every referenced secret version to exist at deploy time.
  runtime_secret_env = {
    for env_name, sid in local.manual_secrets : env_name => sid
    if !startswith(env_name, "LANGFUSE_") || var.tracer_sink == "langfuse"
  }
}

resource "google_cloud_run_v2_service" "api" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.oltp.connection_name]
      }
    }

    containers {
      image = var.image

      # Cloud Run defaults to 8080 and probes that port; the app listens on 8000.
      ports {
        container_port = 8000
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name  = "PUBSUB_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "TRACER_SINK"
        value = var.tracer_sink
      }
      env {
        name  = "CHANNEL_OUTBOUND"
        value = "real"
      }
      env {
        name  = "LLM_STUB"
        value = "1"
      }
      env {
        name  = "RUN_CONSUMER"
        value = "1"
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "VERTEX_AI_LOCATION"
        value = var.region
      }
      env {
        name  = "LANGFUSE_HOST"
        value = var.langfuse_host
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_url.secret_id
            version = "latest"
          }
        }
      }

      dynamic "env" {
        for_each = local.runtime_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.this,
    google_secret_manager_secret_iam_member.api_manual,
    google_secret_manager_secret_iam_member.api_db_url,
  ]
}

# The webhook route is public; the HMAC signature check in
# adapters/whatsapp_inbound.verify_signature is the control (ADR-016, ADR-031).
# DECISION PENDING: if ADR-047 is superseded by a push subscription, split this
# into a public webhook route and a private /internal/consume invoker.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
