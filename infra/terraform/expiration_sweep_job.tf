# Expires stale Approvals/Quotes/Handoffs as a Cloud Run Job on the same
# image (services/expiration.py). Unlike the other batch jobs, this one
# publishes approval_decided (same event the human-decision API route
# publishes) for each expired Approval -- it needs PUBSUB_PROJECT_ID set,
# or _default_publisher() falls back to the in-memory publisher and the
# resume never reaches the paused turn. Run it with:
#   gcloud run jobs execute revenueflow-expiration-sweep --region <region> --wait
resource "google_cloud_run_v2_job" "expiration_sweep" {
  name                = "${var.service_name}-expiration-sweep"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.api.email
      max_retries     = 1
      timeout         = "600s"

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.oltp.connection_name]
        }
      }

      containers {
        image   = var.image
        command = ["python", "scripts/sweep_expirations.py"]

        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }

        env {
          name  = "PUBSUB_PROJECT_ID"
          value = var.project_id
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
      }
    }
  }

  depends_on = [
    google_project_service.this,
    google_secret_manager_secret_iam_member.api_db_url,
    google_sql_database.app,
    google_sql_user.app,
    google_pubsub_topic_iam_member.api_publisher,
  ]
}
