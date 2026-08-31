# infra/terraform/bootstrap

Run **once**, from a human terminal with project-admin rights (Project IAM Admin +
Storage Admin on the project). Creates what the CI pipeline needs to run keyless
(ADR-048): the Terraform state bucket, the GitHub Workload Identity pool/provider,
and the `revenueflow-deployer` service account with its roles.

State for this module is **local** and git-ignored (chicken-and-egg: it creates
the bucket the main config uses).

## Run

```bash
cd infra/terraform/bootstrap
terraform init
terraform apply \
  -var project_id=<PROJECT_ID> \
  -var region=southamerica-east1
```

`github_repository` defaults to `JonatasLimaBR/revenueflow-ai` — override with
`-var github_repository=owner/repo` if the repo moves.

## After apply

1. Copy the outputs into the repo's **Actions Variables**
   (Settings -> Secrets and variables -> Actions -> Variables):

   | Variable | From output |
   |---|---|
   | `WIF_PROVIDER` | `wif_provider` |
   | `DEPLOY_SA` | `deploy_sa` |
   | `TF_STATE_BUCKET` | `tf_state_bucket` |
   | `GCP_PROJECT_ID` | `gcp_project_id` |
   | `GCP_REGION` | `gcp_region` |

2. Create a GitHub **Environment** named `production` (Settings -> Environments)
   with yourself as a **required reviewer**. That approval is the ADR-043 gate on
   `terraform apply`.

From here on, `infra/terraform/**` changes go through `.github/workflows/terraform.yml`:
`plan` on the PR, `apply` on merge to `main` after the Environment approval. No
service-account keys anywhere.

## Not covered here

- `gcloud projects create` + linking billing (needs a billing-admin human).
- The `google_billing_budget` in the main config needs a billing-account-level
  binding for the deployer SA, or stays a manual step.
