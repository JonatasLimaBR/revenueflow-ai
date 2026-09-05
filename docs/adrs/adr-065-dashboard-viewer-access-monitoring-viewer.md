# ADR-065 — Acesso de leitura ao dashboard: `roles/monitoring.viewer` por e-mail, lista vazia por padrão

## Status
Accepted

## Contexto
O usuário pediu para configurar acesso ao dashboard de observabilidade (ADR-056) para outras
pessoas via conta Google, mas ainda não sabe os e-mails concretos — só quer a infraestrutura
preparada. Cloud Monitoring **não tem IAM por dashboard individual**: o menor escopo de leitura
disponível é o papel predefinido de projeto `roles/monitoring.viewer`.

## Decisão

- **`roles/monitoring.viewer` a nível de projeto**, não um papel mais amplo (`viewer`/`editor`).
  É o papel de leitura mais estreito que o Cloud Monitoring oferece — dá acesso a dashboards,
  métricas e políticas de alerta, e nada além disso (sem Cloud SQL, sem Pub/Sub, sem código-fonte,
  sem Secret Manager).
- **`var.dashboard_viewer_emails` (`list(string)`, default `[]`)** + `for_each = toset(...)` sobre
  `google_project_iam_member` — uma associação por e-mail, todas idempotentes e aditivas (não
  removem nenhum binding de IAM existente, ADR-008). Lista vazia por padrão: a infraestrutura fica
  pronta, mas ninguém novo ganha acesso até o usuário preencher o `tfvars` com e-mails reais.
- **Sem grupo do Google Workspace / Identity Group** — o usuário não mencionou ter um grupo
  configurado; e-mails individuais é o caminho mais direto para o número pequeno de pessoas
  envolvido agora. Migrar pra um grupo é aditivo se o número crescer.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Papel mais amplo que `monitoring.viewer` (ex.: `roles/viewer` de projeto) — daria acesso de
  leitura a todo o projeto GCP, muito além do dashboard pedido.
- Autenticação/dashboard fora do Cloud Monitoring (ex.: Looker Studio, Grafana) — fora do que foi
  pedido.
- Preencher `dashboard_viewer_emails` com e-mails reais — o usuário ainda não os forneceu; a lista
  fica vazia até ele decidir e rodar `terraform apply` com o `tfvars` atualizado.

## Alternativas consideradas

- **`roles/viewer` (Viewer básico de projeto)** — muito mais amplo que o necessário; violaria
  least privilege (ADR-008) só pra dar acesso a um dashboard.
- **IAM Condition restringindo `monitoring.viewer` a um recurso específico** — Cloud Monitoring
  dashboards não são um tipo de recurso individualmente endereçável em condições de IAM hoje;
  não há como restringir mais que "todo o Monitoring do projeto".
- **Google Group em vez de e-mails individuais** — mais escalável, mas exige que o usuário já
  tenha (ou crie) um grupo no Workspace; e-mails individuais é suficiente e mais simples para o
  número atual de pessoas.

## Motivo
`monitoring.viewer` de projeto é o papel de menor escopo que o GCP oferece pra esse caso de uso —
não existe IAM por dashboard. Uma lista vazia por padrão, preenchida via `tfvars`, dá ao usuário
controle total sobre quem entra, sem exigir uma decisão de nome/e-mail agora.

## Consequências
- +1 `variable` (`dashboard_viewer_emails`) + +1 `google_project_iam_member` com `for_each` em
  `infra/terraform/monitoring.tf`; +ADR-065.
- Qualquer e-mail listado em `dashboard_viewer_emails` precisa ser uma conta Google válida (pessoal
  ou Workspace) — o `terraform apply` falha se o e-mail não corresponder a uma identidade real.
- Uma regressão que amplie o papel além de `monitoring.viewer`, ou que remova o `toset()`/`for_each`
  em favor de um binding manual fora do Terraform, deveria ser pega em revisão de código.

## Regra de revisão
Mudanças nesta decisão — em especial trocar o papel por algo mais amplo que `monitoring.viewer`,
ou mover o acesso pra fora do Terraform — exigem novo ADR ou superseding ADR.
