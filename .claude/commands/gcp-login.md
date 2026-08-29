Authenticate the local developer environment with Google Cloud.

Run/guide:
1. `gcloud auth login`
2. `gcloud auth application-default login` when local SDK ADC is required
3. ask for/confirm the intended project ID
4. `gcloud config set project <PROJECT_ID>`
5. run `/gcp-check`

Never print access tokens or create service-account keys automatically.
