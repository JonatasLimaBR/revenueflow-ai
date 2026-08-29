Validate the GCP developer environment without changing infrastructure.

Check:
- `gcloud --version`
- active account
- configured project
- ADC availability if needed
- enabled project context
- Cloud Run API visibility
- BigQuery visibility
- Vertex AI visibility
- Pub/Sub visibility
- Cloud SQL visibility
- MCP configuration presence

Report PASS/WARN/FAIL per item.
Do not enable APIs automatically unless explicitly requested.
