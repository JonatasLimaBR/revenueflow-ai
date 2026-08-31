# Partial backend config. Initialize with:
#   terraform init \
#     -backend-config="bucket=<PROJECT_ID>-tfstate" \
#     -backend-config="prefix=prod"
# The state bucket is created by the human bootstrap step (runbook Fase 1), not by
# this config, so its IAM / versioning / uniform-bucket-level-access must be
# verified manually.

terraform {
  backend "gcs" {}
}
