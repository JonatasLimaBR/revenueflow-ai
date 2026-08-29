# SPEC-037 — Technology Stack

## Objetivo
Fixar stack da V1.

## Contrato / Dados
Next.js, FastAPI, Cloud Run, Cloud SQL PostgreSQL, BigQuery, Pub/Sub, Vertex AI/Gemini, Secret Manager, Cloud Storage, Terraform, GitHub Actions/Cloud Build

## Regra de implementação
Mudanças relevantes exigem ADR.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
