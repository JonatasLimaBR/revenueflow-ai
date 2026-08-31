# Bootstrap state is LOCAL and git-ignored. This runs once, from a human admin
# terminal, before anything else exists (chicken-and-egg with the state bucket).

terraform {
  required_version = ">= 1.7"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "this" {}
