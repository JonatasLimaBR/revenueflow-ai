# Marks stale, non-terminal leads LOST as a Cloud Run Job on the same image, so
# the lead lifecycle (ADR-062) has a batch backstop for the one transition a
# single turn can't decide: absence of activity over time. Run it with:
#   gcloud run jobs execute revenueflow-lead-sweep --region <region> --wait
resource "google_cloud_run_v2_job" "lead_sweep" {
  name                = "${var.service_name}-lead-sweep"
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
        command = ["python", "scripts/sweep_leads.py"]

        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
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
  ]
}
