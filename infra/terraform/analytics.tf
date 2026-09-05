# Revenue + AI-cost analytics: a small BigQuery dataset fed by a batch Cloud Run
# Job (WRITE_TRUNCATE — a full snapshot each run, not an event log). Postgres
# stays the source of truth for the business logic (ADR-004); this dataset only
# receives the already-computed rows (ADR-061, closes the Revenue slice of
# PRD-015 via ADR-005). Run it after a deploy or on a schedule with:
#   gcloud run jobs execute revenueflow-analytics-sync --region <region> --wait
resource "google_bigquery_dataset" "analytics" {
  dataset_id = "revenueflow_analytics"
  location   = var.region

  depends_on = [google_project_service.this]
}

resource "google_bigquery_table" "conversation_revenue" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "conversation_revenue"
  deletion_protection = false

  schema = jsonencode([
    { name = "conversation_id", type = "STRING", mode = "REQUIRED" },
    { name = "ai_cost_usd", type = "FLOAT64", mode = "NULLABLE" },
    { name = "turns", type = "INT64", mode = "NULLABLE" },
    { name = "last_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "orders", type = "INT64", mode = "NULLABLE" },
    { name = "revenue", type = "FLOAT64", mode = "NULLABLE" },
    { name = "margin_usd", type = "FLOAT64", mode = "NULLABLE" },
    { name = "recovered_revenue_usd", type = "FLOAT64", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "cost_per_outcome" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "cost_per_outcome"
  deletion_protection = false

  schema = jsonencode([
    { name = "outcome", type = "STRING", mode = "REQUIRED" },
    { name = "turns", type = "INT64", mode = "NULLABLE" },
    { name = "cost_usd", type = "FLOAT64", mode = "NULLABLE" },
    { name = "avg_latency_ms", type = "FLOAT64", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "customer_360" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "customer_360"
  deletion_protection = false

  schema = jsonencode([
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "orders_12m", type = "INT64", mode = "NULLABLE" },
    { name = "revenue_12m", type = "FLOAT64", mode = "NULLABLE" },
    { name = "last_purchase", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "purchase_interval_days", type = "FLOAT64", mode = "NULLABLE" },
    { name = "preferred_product", type = "STRING", mode = "NULLABLE" },
    { name = "open_quotes", type = "INT64", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "lead_funnel" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "lead_funnel"
  deletion_protection = false

  schema = jsonencode([
    { name = "lead_id", type = "STRING", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "opportunity_summary" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "opportunity_summary"
  deletion_protection = false

  schema = jsonencode([
    { name = "opportunity_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "opportunity_type", type = "STRING", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "estimated_revenue", type = "FLOAT64", mode = "NULLABLE" },
    { name = "probability", type = "FLOAT64", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "handoff_rate" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "handoff_rate"
  deletion_protection = false

  schema = jsonencode([
    { name = "total_turns", type = "INT64", mode = "NULLABLE" },
    { name = "handoff_turns", type = "INT64", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "v_lead_conversion" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "v_lead_conversion"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT status, COUNT(*) AS leads
      FROM `${var.project_id}.${google_bigquery_dataset.analytics.dataset_id}.lead_funnel`
      GROUP BY status
    SQL
  }

  depends_on = [google_bigquery_table.lead_funnel]
}

resource "google_bigquery_table" "v_opportunity_pipeline" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "v_opportunity_pipeline"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT opportunity_type, SUM(estimated_revenue) AS pipeline_usd
      FROM `${var.project_id}.${google_bigquery_dataset.analytics.dataset_id}.opportunity_summary`
      WHERE status = 'OPEN'
      GROUP BY opportunity_type
    SQL
  }

  depends_on = [google_bigquery_table.opportunity_summary]
}

resource "google_bigquery_table" "v_opportunity_conversion" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "v_opportunity_conversion"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT
        opportunity_type,
        SAFE_DIVIDE(COUNTIF(status = 'CONVERTED'), COUNT(*)) AS conversion_rate
      FROM `${var.project_id}.${google_bigquery_dataset.analytics.dataset_id}.opportunity_summary`
      GROUP BY opportunity_type
    SQL
  }

  depends_on = [google_bigquery_table.opportunity_summary]
}

resource "google_bigquery_table" "v_revenue_summary" {
  dataset_id          = google_bigquery_dataset.analytics.dataset_id
  table_id            = "v_revenue_summary"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT
        SUM(revenue) AS total_revenue,
        SUM(recovered_revenue_usd) AS total_recovered_revenue,
        SUM(margin_usd) AS total_margin,
        SAFE_DIVIDE(SUM(revenue), SUM(orders)) AS average_ticket,
        SUM(ai_cost_usd) AS total_ai_cost,
        SAFE_DIVIDE(SUM(revenue), SUM(ai_cost_usd)) AS revenue_per_ai_cost_usd
      FROM `${var.project_id}.${google_bigquery_dataset.analytics.dataset_id}.conversation_revenue`
    SQL
  }

  depends_on = [google_bigquery_table.conversation_revenue]
}

resource "google_bigquery_dataset_iam_member" "analytics_editor" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.api.email}"
}

resource "google_cloud_run_v2_job" "analytics_sync" {
  name                = "${var.service_name}-analytics-sync"
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
        command = ["python", "scripts/sync_analytics.py"]

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

        env {
          name  = "BIGQUERY_DATASET"
          value = google_bigquery_dataset.analytics.dataset_id
        }
      }
    }
  }

  depends_on = [
    google_project_service.this,
    google_secret_manager_secret_iam_member.api_db_url,
    google_sql_database.app,
    google_sql_user.app,
    google_bigquery_dataset_iam_member.analytics_editor,
  ]
}
