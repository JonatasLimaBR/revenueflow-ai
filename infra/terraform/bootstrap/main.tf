locals {
  state_bucket = var.state_bucket_name != "" ? var.state_bucket_name : "${var.project_id}-tfstate"

  bootstrap_services = toset([
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
  ])

  deployer_roles = toset([
    "roles/run.admin",
    "roles/cloudsql.admin",
    "roles/pubsub.admin",
    "roles/secretmanager.admin",
    "roles/artifactregistry.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/storage.admin",
  ])
}

resource "google_project_service" "bootstrap" {
  for_each = local.bootstrap_services

  service            = each.value
  disable_on_destroy = false
}

# The CD pipeline (.github/workflows/terraform.yml) pushes the image BEFORE it runs
# `terraform apply`, so the registry has to exist ahead of the main config — same
# chicken-and-egg as the state bucket. It lives here, not in ../artifact_registry.tf.
resource "google_artifact_registry_repository" "api" {
  repository_id = "revenueflow"
  location      = var.region
  format        = "DOCKER"
  description   = "RevenueFlow container images"

  depends_on = [google_project_service.bootstrap]
}

resource "google_storage_bucket" "tfstate" {
  name                        = local.state_bucket
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.bootstrap]
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  description               = "OIDC identities from GitHub Actions"

  depends_on = [google_project_service.bootstrap]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Only this repository may mint tokens against this provider.
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  account_id   = "revenueflow-deployer"
  display_name = "RevenueFlow Terraform deployer (GitHub Actions via WIF)"
}

resource "google_project_iam_member" "deployer" {
  for_each = local.deployer_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "deployer_wif" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}
