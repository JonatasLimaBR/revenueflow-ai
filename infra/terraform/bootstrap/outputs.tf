# Set these as GitHub repository Variables (Settings -> Secrets and variables ->
# Actions -> Variables). They are not secret.

output "wif_provider" {
  description = "GitHub repo variable WIF_PROVIDER"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_sa" {
  description = "GitHub repo variable DEPLOY_SA"
  value       = google_service_account.deployer.email
}

output "tf_state_bucket" {
  description = "GitHub repo variable TF_STATE_BUCKET"
  value       = google_storage_bucket.tfstate.name
}

output "gcp_project_id" {
  value = var.project_id
}

output "gcp_region" {
  value = var.region
}
