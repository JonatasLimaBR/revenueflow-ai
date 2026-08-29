# Terraform GCP Skill

## Use when
Changing GCP infrastructure.

## Allowed automatically
- `terraform fmt`
- `terraform validate`
- `terraform plan`
- static/security review

## Never automatic
- `terraform apply`
- `terraform destroy`

Those require explicit human approval.

## Rules
- no secrets in tfvars committed to Git;
- use variables and Secret Manager references;
- least privilege IAM;
- separate environments/state;
- review plan before any apply.
