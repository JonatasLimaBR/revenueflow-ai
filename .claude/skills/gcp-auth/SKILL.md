# GCP Authentication Skill

## Use when
Authentication, project selection, ADC, IAM identity or credential troubleshooting is involved.

## Safe workflow

1. Verify binaries:
   - `gcloud --version`
   - `claude --version`

2. Interactive user login:
   - `gcloud auth login`

3. Application Default Credentials when local SDKs need them:
   - `gcloud auth application-default login`

4. Select project:
   - `gcloud config set project <PROJECT_ID>`

5. Verify:
   - `gcloud auth list`
   - `gcloud config get-value project`
   - `gcloud config get-value account`

## Rules
- Never print access tokens.
- Never commit ADC files.
- Never create service-account keys unless a documented requirement explicitly requires one.
- Prefer Workload Identity / attached service accounts for deployed workloads.
