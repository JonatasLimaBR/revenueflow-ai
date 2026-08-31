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

output "artifact_registry_repo" {
  description = "docker push target prefix"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.api.repository_id}"
}
