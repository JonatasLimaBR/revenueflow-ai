# Schema migrations + seed as a Cloud Run Job on the same image, so the runbook
# Fase 6 step runs in-cluster (runtime SA + Cloud SQL socket) instead of needing
# a local Auth Proxy. Run it after each deploy with:
#   gcloud run jobs execute revenueflow-api-migrate --region <region> --wait
resource "google_cloud_run_v2_job" "migrate" {
  name                = "${var.service_name}-migrate"
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
        command = ["sh", "-c"]
        args    = ["python scripts/migrate.py && python scripts/seed.py"]

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
