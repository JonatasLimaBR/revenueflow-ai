# infra/terraform

Infrastructure stubs for the RevenueFlow inbound slice. Not wired into CI.

Allowed from an agent harness (skill `terraform-gcp`, ADR-043):

```bash
terraform fmt
terraform validate
terraform plan
```

Never automatic — require explicit human approval:

```bash
terraform apply
terraform destroy
```

Rules: no secrets in committed `.tfvars`; use variables and Secret Manager
references; least-privilege IAM; separate state per environment.
