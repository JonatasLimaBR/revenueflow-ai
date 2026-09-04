output "service_url" {
  description = "Public Cloud Run URL; WhatsApp webhook = <url>/webhook/whatsapp"
  value       = google_cloud_run_v2_service.api.uri
}

output "db_connection_name" {
  description = "Cloud SQL connection name for the Auth Proxy / connector"
  value       = google_sql_database_instance.oltp.connection_name
}

output "topic_id" {
  value = google_pubsub_topic.messages.id
}

output "subscription_id" {
  value = google_pubsub_subscription.messages.id
}

output "runtime_service_account" {
  value = google_service_account.api.email
}

output "migrate_job" {
  description = "gcloud run jobs execute <this> --region <region> --wait"
  value       = google_cloud_run_v2_job.migrate.name
}

# The "revenueflow" repo is created by infra/terraform/bootstrap (it has to exist
# before the CD pipeline pushes the image, ahead of this config's apply).
output "artifact_registry_repo" {
  description = "docker push target prefix"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/revenueflow"
}

output "landing_page_ip" {
  description = "Static IP for the landing page (no domain yet: http://<this>/)"
  value       = google_compute_global_address.landing.address
}

output "landing_page_bucket" {
  description = "GCS bucket name for `gsutil rsync` in CD"
  value       = google_storage_bucket.landing.name
}

output "landing_page_url_map" {
  description = "URL map name for `gcloud compute url-maps invalidate-cdn-cache` in CD"
  value       = google_compute_url_map.landing.name
}
