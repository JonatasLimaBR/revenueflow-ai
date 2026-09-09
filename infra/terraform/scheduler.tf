# Cloud Scheduler encadeando os jobs batch (follow-up documentado desde
# OPPORTUNITY_ENGINE/ACTIVE_SALES — os Jobs só rodavam sob demanda via
# `gcloud run jobs execute` até aqui). Horários em sequência: opportunity_scan
# primeiro (gera as oportunidades), campaign_run 30 min depois (consome as
# oportunidades recém-detectadas, ADR-020 Policy Gate), lead_sweep e
# analytics_sync em horários independentes. expiration_sweep (ADR-077) roda
# de hora em hora, não diariamente como os outros.
#
# SA dedicada com escopo mínimo (ADR-008): só roles/run.invoker nos Jobs
# específicos via IAM member por-job, nunca no service_account.api da app
# (que roda o próprio processo, não deveria também poder disparar jobs).
resource "google_service_account" "scheduler" {
  account_id   = "${var.service_name}-scheduler"
  display_name = "RevenueFlow Cloud Scheduler -> Cloud Run Jobs invoker"
}

locals {
  scheduled_jobs = {
    opportunity_scan = {
      job_name = google_cloud_run_v2_job.opportunity_scan.name
      schedule = "0 9 * * *"
    }
    campaign_run = {
      job_name = google_cloud_run_v2_job.campaign_run.name
      schedule = "30 9 * * *"
    }
    lead_sweep = {
      job_name = google_cloud_run_v2_job.lead_sweep.name
      schedule = "15 9 * * *"
    }
    analytics_sync = {
      job_name = google_cloud_run_v2_job.analytics_sync.name
      schedule = "0 22 * * *"
    }
    # Hourly, not daily like the others above: a stale Approval/Quote/Handoff
    # leaves a customer conversation stuck until this runs (ADR-077) -- an
    # hour of delay is a much smaller cost than a day.
    expiration_sweep = {
      job_name = google_cloud_run_v2_job.expiration_sweep.name
      schedule = "0 * * * *"
    }
  }
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  for_each = local.scheduled_jobs

  name     = each.value.job_name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "this" {
  for_each = local.scheduled_jobs

  name      = "${var.service_name}-${replace(each.key, "_", "-")}-schedule"
  region    = var.region
  schedule  = each.value.schedule
  time_zone = "Etc/UTC"

  # Official pattern for Cloud Scheduler -> Cloud Run Job (v1 Jobs API "run"
  # action, invoked with an OIDC token from a scoped SA) -- google_cloud_run_v2_job
  # itself has no invoke-via-scheduler shortcut in this provider.
  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${each.value.job_name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [
    google_project_service.this,
    google_cloud_run_v2_job_iam_member.scheduler_invoker,
  ]
}
