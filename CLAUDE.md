# CLAUDE.md — RevenueFlow AI

## Papel do Claude Code

Claude Code é um harness suportado deste repositório. O contrato de engenharia compartilhado continua em [`AGENTS.md`](AGENTS.md). Este arquivo adiciona as regras específicas de Claude Code, MCP, skills, hooks e agentes auxiliares.

## Ordem obrigatória de leitura

1. `CLAUDE.md`
2. `AGENTS.md`
3. PRD relacionado
4. SPEC relacionada
5. ADRs aplicáveis
6. testes existentes
7. código

## Estado da implementação

Fatias entregues, arquivadas em `.claude/sdd/archive/`:

- **WHATSAPP_INBOUND_SLICE** (2026-08-31, PRs #3–#10, modo `LLM_STUB`) — webhook → grafo →
  resposta ancorada.
- **PRICING_AND_NEGOTIATION** (2026-08-31, PRs #12–#13, modo `LLM_STUB`) — Pricing Service
  determinístico + Negotiation Agent + `interrupt()` que pausa o grafo e cria `Approval(PENDING)`
  quando o desconto está fora da alçada (fire-and-stop; a retomada é a fatia `APPROVAL_RESUME`).
- **WHATSAPP_INBOUND_VERTEX** (2026-09-01, PRs #29–#30, ADR-049) — os 2 call sites de intent e
  resposta ancorada passam a chamar o Vertex AI / Gemini real (`gemini-2.5-flash`, endpoint
  `global`), keyless via ADC. Retry com backoff em erro transitório; na exaustão, `LLMError` →
  nó terminal `handoff` (resposta fixa de encaminhamento, nada gerado). Prompts `v2` com moldura
  anti-injection. Eval contra o modelo real em `tests/ai_eval/test_vertex_eval.py` (marker
  `live`, fora do CI). **Produção roda `LLM_STUB=0`; dev local e CI mantêm o stub como default.**
- **APPROVAL_RESUME** (2026-09-02, PR #32, ADR-050) — fecha o fire-and-stop: `POST /internal/approvals/{id}`
  (Bearer `APPROVAL_API_TOKEN`) transiciona o `Approval` e publica `approval_decided`; o consumer
  pega `pg_advisory_xact_lock(conversation_id)` e retoma o grafo com `Command(resume=…)`. Novo nó
  `apply_decision_node` determinístico (approve / approve_with_override / reject / expired). `0004`
  adiciona `expires_at`/`approved_discount`/`decided_at`. Mensagem nova durante o `interrupt` →
  "sua solicitação ainda está em análise".
- **CHECKOUT** (2026-09-02, PR #35, ADR-051) — fecha a venda: `ORDER_REQUEST` → `checkout_node`
  determinístico gera `Quote(SENT)` a partir do preço resolvido e pede "sim, pode fechar"; a
  próxima mensagem cai no gate (`get_open_quote` no `supervisor` + `is_explicit_confirmation`
  pura, SPEC-014) → cria `sales_order` idempotente por `quote_id`, revalida estoque, roda
  `create_payment_sandbox` (fake `APPROVED`, sem dado de cartão). `CHECKOUT_TOOLS` isolado
  (nenhum outro agente vê `create_*`). `0005` adiciona `quote`/`sales_order`/`payment` + índice
  único parcial. `apply_decision` ganha aresta `→ {checkout, END}` para o pós-aprovação.
- **CUSTOMER_360** (2026-09-03, PR #37, ADR-052) — reconhece o cliente recorrente pelo telefone e
  carrega uma visão comercial limitada. `identity.resolve` consulta `customer` (telefone exato)
  antes do lead; conhecido → `customer_id` real + `conversation_session.customer_id` gravado no
  `process_event` (via `session_repo.set_customer`). `repositories.customer.customer_360` agrega
  determinístico, sem LLM (janela de 365d, `sim_customer_order` ∪ `sales_order`;
  `preferred_products` de `sim_customer_sales`; `open_quotes` de `quote`). Tool estreita
  `get_customer_360` **só** em `RECOMMENDATION_TOOLS` (ADR-033); `recommendation_node` a chama no
  ramo `if customer_id:` (substitui `get_customer_sales_context`); falha →
  `{"error": "unavailable"}` + log com `trace_id`. `0006` cria `customer` + `sim_customer_order`.
- **OPPORTUNITY_ENGINE** (2026-09-03, PR #39, ADR-053) — detecção de oportunidade por **regra
  determinística**, em batch, **fora do grafo** (ADR-019). `services.opportunity.scan()` puxa
  candidatos (recompra atrasada: `days_since_last_purchase > average_purchase_interval * threshold`;
  quote parada: `SENT` sem `sales_order` além do limite), roda `policies.opportunity_policy`
  (funções puras, `now` injetável, sem LLM/agents/adapters) e faz `upsert_open` idempotente
  (índice único parcial `opportunity (customer_id, opportunity_type, product) WHERE status='OPEN'`).
  Cada `opportunity` guarda `reason` + `evidence` jsonb (SPEC-021). **Gera opportunity, não
  mensagem** (SPEC-022 — outreach é a fatia OUTBOUND). `probability` fixo por tipo (placeholder,
  ADR-018). Roda pelo Cloud Run Job `revenueflow-opportunity-scan` on-demand (`scripts/detect_opportunities.py`);
  Cloud Scheduler diário é follow-up. `0007` cria `opportunity`.
- **HUMAN_HANDOFF** (2026-09-03, PR #41, ADR-054) — transfere a conversa para um humano em 3
  gatilhos determinísticos: pedido explícito (`Intent.HUMAN_SUPPORT`, que antes caía em
  `respond`), `low_confidence` da classificação, `high_value_order` (`customer_price * qty` acima
  do teto, checado no `negotiation_node` antes do checkout). O check de `low_confidence` /
  `explicit_request` roda no `supervisor_node`, **depois** do gate de quote aberto.
  `policies.handoff_policy.should_handoff` é pura (precedência fixa, sem LLM). `agents/handoff.py`
  (módulo próprio — quebra o ciclo `graph ↔ negotiation`): `handoff_node` monta
  `services.handoff.build_context` (8 chaves da SPEC-027, determinístico; `next_best_action`
  reusa a `opportunity` OPEN), persiste um `Handoff` idempotente (índice único parcial
  `handoff (conversation_id) WHERE status='PENDING'`) e marca a sessão `HUMAN_HANDOFF`. Handoff
  de falha de LLM também persiste. Rota `GET/POST /internal/handoffs` (Bearer `HANDOFF_API_TOKEN`,
  secret Terraform-generated). Guard no `process_event`: sessão em `HUMAN_HANDOFF` → frase fixa,
  sem grafo. `0008` cria `handoff`.
- **AUDIT_TRAIL** (2026-09-03, PR #43, ADR-055) — trilho de auditoria persistido no OLTP
  (SPEC-028, fecha o V1 core do PRD-016). `AuditTracer` **envolve** o sink de `tracer_sink`
  (`noop`/`langfuse`/`otel`): encaminha `span`/`generation`/`event`/`end` para ele **e** acumula
  um buffer; `new_tracer` devolve o `AuditTracer` quando `audit_enabled` (default `True`,
  ortogonal ao sink). Nova op `async flush()` na porta `Tracer` (no-op nos 3 sinks) grava **uma**
  linha `audit_event` por turno
  (`agent`/`model`/`prompt_version`/`tools`/`token_usage`/`cost_usd`/`latency_ms`/`outcome` +
  `events jsonb` p/ reconstrução) via `services.audit.persist` (falha isolada + log `trace_id`).
  Chamado no `finally` de `process_event`/`process_approval_decided`/`scan`, depois do
  `_send_once` (fora do P95). `0009` cria `audit_event` + views `v_ai_cost_per_conversation` /
  `v_ai_cost_per_outcome`. Rota `GET /internal/audit/{conversation_id}` (Bearer reusa
  `HANDOFF_API_TOKEN`). Sem infra nova.
- **OBSERVABILITY_OPS** (2026-09-03, PR #45, ADR-056) — fecha a SPEC-034. `AuditTracer.flush()` passa a
  emitir **uma** linha JSON `audit.turn` por turno (`conversation_id`/`outcome`/`agent`/`model`/
  `cost_usd`/`token_usage`/`latency_ms`/`handoff`/`tool_failures`) ao lado do `persist` —
  `observability/logging_setup.py` traz um `JsonFormatter` stdlib (sem dep) + `configure_logging()`
  idempotente no `lifespan`/`run_subscriber`. `observability/otel_setup.py::configure_otel()`
  configura um `TracerProvider` global + `CloudTraceSpanExporter` (import lazy, idempotente),
  chamado no `lifespan` **só** se `tracer_sink == "otel"` — produção passa a `TRACER_SINK=otel`
  (ADR-056 emenda o ADR-045; `LangfuseTracer` fica atrás da porta). `infra/terraform/monitoring.tf`
  (novo): 5 `google_logging_metric` sobre a linha `audit.turn`, `google_monitoring_dashboard`
  (`dashboards/revenueflow_ops.json`) + métricas nativas do Cloud Run, 5 `google_monitoring_alert_policy`
  (5xx, p95, tool failures, custo/h, ausência de turno) + canal de email opcional (`var.alert_email`).
  `cost.py::MODEL_PRICES` com preços publicados do Vertex + proveniência. `0010` cria
  `v_ai_cost_per_revenue` (`audit_event` ⟕ `quote` ⟕ `sales_order` PAID). `apis.tf` +=
  `cloudtrace`/`logging`/`monitoring`; `iam.tf` += `roles/cloudtrace.agent`; `Dockerfile` instala
  `.[events,llm,observability]`.
- **HARDENING_PERFORMANCE** (2026-09-04, PR #47, ADR-057) — fecha a SPEC-035: impõe um orçamento de
  latência. `asyncio.wait_for` em 3 lugares — cada tentativa da chamada Vertex em
  `_generate_with_retry` (`llm_call_timeout_s=6`; `TimeoutError` é transitório → retry → exaustão
  → `LLMError` → handoff), o `graph.ainvoke` nos 2 consumidores (`turn_budget_s=15` — teto de
  turno **preso**; `except TimeoutError` → `_SLOW_REPLY` fixo + `end(outcome="timeout")` + ack,
  porque o `processed_event.claim` já foi committado), e `statement_timeout=3000ms` no
  `AsyncConnectionPool` da app (via `kwargs={"options": ...}`). O alvo de P95<5s continua
  **medido** (métrica/alerta da OBSERVABILITY_OPS), não imposto. `0011` cria 4 índices
  (`opportunity`/`handoff`/`approval` por `(status, created_at)`, `quote (customer_ref) WHERE
  status='SENT'`). Sem dep nova, sem infra nova.
- **HARDENING_SECURITY_PII** (2026-09-04, PR #49, ADR-058) — passada dedicada de SPEC-030/031/032.
  Fecha 2 lacunas concretas e **prova** as invariantes que a arquitetura já garante: `mask()` ganha
  um regex de **CPF** (`_EMAIL → _CPF → _PHONE`; nome/endereço seguem via `extra_terms`); `main.py`
  ganha um `@app.middleware("http")` que adiciona `X-Content-Type-Options`/`X-Frame-Options`/
  `Referrer-Policy`/`Strict-Transport-Security` a toda resposta (via `setdefault`). Suíte nova
  `tests/security/`: `test_pii_masking` (mask cobre phone/email/CPF; turno real → `audit_event.events`
  + `caplog` sem telefone cru), `test_injection_resistance` (registries disjuntos + `graph_tool_names`
  == união; `pricing_policy.evaluate` puro sob `Decimal` adversário; desconto > alçada →
  `snapshot.next` tem `await_approval`; `is_explicit_confirmation` não carrega desconto do texto),
  `test_internal_routes_auth` (varredura `401`/`503` das 5 rotas `/internal/*`), `test_security_headers`.
  **Sem** cifra a nível de campo / retention sweep / rate-limiting na V1 (ADR-032 = minimizar; RBAC
  do Cloud SQL é o controle). Sem dep, sem infra, sem migração. **Fecha o V1 core do PRD-016.**
- **ACTIVE_SALES** (2026-09-04, PR #51, ADR-059) — fecha o PRD-011: `services.campaign.run()`
  (batch, fora do grafo, ADR-019/020) consome `opportunity(OPEN)`, roda o Policy Gate determinístico
  (`policies.outbound_policy.evaluate` — opt-out > sem opt-in > frequência > permitido; `Customer`
  ganha `consent_opt_in_at`/`consent_opt_out_at`) e envia uma mensagem template (sem LLM) via
  `ChannelOutbound.send`, idempotente por dia (`dispatch_key=campaign:{opportunity_id}:{date}`),
  registrando cada tentativa (`SENT`/`SKIPPED`/`FAILED`) em `outbound_contact` (log append-only,
  sem PII de conteúdo). Guard de opt-out em `worker.consume.process_event` (antes do grafo, keyword
  exata, sem `SessionStatus` novo) fecha o loop de opt-out do PRD-011. `0012` adiciona as 2 colunas
  em `customer` + `outbound_contact`. Cloud Run Job `revenueflow-campaign-run` (espelha
  `revenueflow-opportunity-scan`; Cloud Scheduler é follow-up). **Sem** WhatsApp Message
  Templates (HSM) reais, opt-in inbound, ou personalização por LLM na V1 (ADR-059).
- **LANDING_PAGE** (2026-09-04, PR #53, ADR-060) — primeira fatia sem PRD/SPEC dedicado: um site estático
  (`site/index.html` + `site/assets/styles.css`, sem framework/build step) detalhando as fatias
  entregues (agrupadas em 6 fases) + arquitetura + roadmap, hospedado em GCS atrás de um Load
  Balancer HTTP global com Cloud CDN (`infra/terraform/landing_page.tf`, 7 recursos) — domínio
  próprio/HTTPS vieram depois, aditivamente (ADR-068). Deploy do conteúdo via `gsutil rsync` no job `deploy` de
  `terraform.yml` (depois do `terraform apply`, com invalidação de cache CDN), não via
  `google_storage_bucket_object` — editar copy é um commit normal, sem `plan`/`apply`. CSP via
  `<meta http-equiv>` (cumpre a nota do ADR-058, já que GCS não roda servidor de app próprio).
  Zero código Python tocado; zero coleta de dado (sem formulário/analytics).
- **ANALYTICS** (2026-09-04, PR #55, ADR-061) — fecha o domínio Revenue + Custo de IA do PRD-015 (dos 5
  domínios, só este entra nesta fatia). Nova view `v_conversation_revenue` (`0013`, ao lado das 3
  views de custo/receita já existentes — nenhuma delas é tocada) calcula, por conversa, `margin_usd`
  (receita menos custo dos itens via `sim_product.unit_cost`) e `recovered_revenue_usd` (pedidos
  cujo `quote_id` bate com uma `opportunity(QUOTE_RECOVERY)`). `services.analytics_sync.run()`
  (batch, fora do grafo) lê essa view + `v_ai_cost_per_outcome` e recarrega 2 tabelas no BigQuery
  (`WRITE_TRUNCATE` — snapshot idempotente, resiliente por tabela) + 1 view `v_revenue_summary`
  (receita/receita recuperada/margem/ticket médio/receita por custo de IA num único SELECT).
  Cloud Run Job `revenueflow-analytics-sync` (espelha os 2 Jobs batch anteriores). IAM do BigQuery
  escopado ao dataset (`google_bigquery_dataset_iam_member`, não a nível de projeto). Extra
  opcional `analytics` (`google-cloud-bigquery`, import lazy). **Sem** os outros 4 domínios do
  PRD-015, sem sync incremental/CDC, sem dashboard, sem Cloud Scheduler na V1 (ADR-061).
- **LEAD_LIFECYCLE** (2026-09-05, ADR-062) — fecha uma lacuna achada ao escopar o Lead 360 do
  PRD-015: `LeadStatus` nunca transicionava além de `NEW`, e nenhum lead virava `Customer` real
  após comprar. `policies.lead_policy.evaluate` (pura, monotônica) avança
  `NEW→QUALIFYING→QUALIFIED→PROPOSAL→WON` por sinal de intent/`final_outcome`, chamada a cada
  turno em `worker.consume.process_event`; `WON` promove um `Customer` real (telefone do lead,
  idempotente). `services.lead_lifecycle.sweep_stale()` (batch, Cloud Run Job
  `revenueflow-lead-sweep`) move leads sem atividade recente para `LOST` (reusa
  `conversation_session.last_interaction` via join — sem migração nova). Sem LLM, sem UI de CRM,
  sem Cloud Scheduler na V1 (ADR-062).
- **ANALYTICS_360** (2026-09-05, ADR-063) — fecha os 4 domínios restantes do PRD-015 (Customer 360,
  Lead 360, Opportunity 360, Conversation Analytics), pedidos explicitamente pelo usuário como
  fatia nova sobre o corte do ADR-061. 4 views novas no Postgres (`0014`, ao lado das existentes):
  `v_customer_360_all` (1 linha por cliente, incl. sem pedido; `preferred_product` via
  `preferred_agg`→`preferred` — `row_number()` sobre agregação já feita, não sobre `sum()` direto);
  `v_lead_funnel` (sem telefone); `v_opportunity_summary` (sem `reason`/`evidence`);
  `v_handoff_rate` (turnos com `handoff=true` / total, de `audit_event`). `services.analytics_sync.run()`
  generaliza de 2 para 6 cargas via uma lista `_SOURCES` — cada fetch é resolvido por
  `getattr(analytics_repo, fn_name)` a cada chamada (não uma referência de função vinculada no
  import), pra continuar compatível com o `monkeypatch.setattr(analytics_repo, ...)` da suíte de
  testes; `SyncResult` muda de campos fixos pra `rows_loaded: dict[str, int]`. `infra/terraform/analytics.tf`
  += 4 tabelas de fato + 3 views (`v_lead_conversion`/`v_opportunity_pipeline`/`v_opportunity_conversion`),
  mesmo dataset e IAM já escopados — nenhum recurso de IAM novo. **Sem** dashboard/Looker Studio,
  sem histórico de tendência, sem Cloud Scheduler (ADR-063).
- **DASHBOARD_ACCESS** (2026-09-05, ADR-065) — acesso de leitura ao dashboard do Cloud Monitoring
  (ADR-056) para outras pessoas via conta Google. Cloud Monitoring não tem IAM por dashboard
  individual — `google_project_iam_member` com `for_each` sobre `var.dashboard_viewer_emails`
  (`list(string)`, default `[]`) concede `roles/monitoring.viewer` de projeto (o papel de leitura
  mais estreito disponível: dashboards/métricas/alertas, nada além disso) por e-mail. Lista vazia
  por padrão — infraestrutura pronta, ninguém novo ganha acesso até o `tfvars` ser preenchido com
  e-mails reais. **Sem** grupo do Workspace, sem papel mais amplo que `monitoring.viewer` (ADR-065).
- **MCP_SERVER** (2026-09-05, ADR-064) — servidor MCP pessoal (`src/revenueflow/mcp/`, extra
  `mcp`, stdio) pro usuário acessar o sistema via Claude Desktop/Claude Code. 6 tools de leitura
  chamam `repositories.analytics` direto (mesmo padrão dos batch jobs); 5 tools de ação chamam as
  rotas HTTP internas já deployadas (`/internal/approvals`/`/internal/handoffs`/`/internal/audit`,
  mesmo Bearer). `mcp/tools.py` isola a lógica de negócio do pacote `mcp` — testável sem o extra
  instalado (`httpx.MockTransport` pras tools de ação). **Sem** servidor hospedado/multi-tenant,
  sem tool de escrita nova além das rotas já existentes (ADR-064).
- **WHATSAPP_CTA** (2026-09-05, ADR-066) — CTA de WhatsApp na landing page (ADR-060), pedido
  explicitamente pelo usuário. Deep link `https://wa.me/<E.164>?text=...` em 3 pontos (topnav, hero,
  rodapé) leva o visitante direto pro fluxo já em produção (`WHATSAPP_INBOUND_SLICE`) — sem
  formulário, sem backend novo, sem analytics de clique. Número fixo no HTML, editado como copy
  estática (mesmo fluxo de deploy do ADR-060). Zero código Python/Terraform tocado.
- **MCP_READONLY_PUBLIC** (2026-09-05, ADR-067) — MCP público de leitura, pedido explicitamente
  pelo usuário ("online, só visualização, pra outras pessoas") — emenda o "fora de escopo" do
  ADR-064 só pra essa capacidade. Novo Cloud Run service `revenueflow-mcp-readonly` (mesma imagem
  da API, `command` diferente, mesmo padrão dos Jobs batch), Streamable HTTP em vez de stdio,
  escala a zero. `mcp/server.py` dividido em `register_read_tools`/`register_action_tools` —
  `http_server.py` só registra as 6 tools de leitura, nunca as 5 de ação. Mesmo modelo de confiança
  das rotas `/internal/*`: `allUsers` invoker + bearer compartilhado (`MCP_API_TOKEN`,
  Terraform-generated). `mcp/auth.py` (o `bearer_gate` ASGI) não depende do pacote `mcp` — testável
  sem o extra instalado. `Dockerfile` ganha o extra `mcp` (deixa de ser só do ambiente pessoal).
  **Sem** identidade por pessoa (OAuth/IAM), sem tool de ação no servidor público (ADR-067).
- **LANDING_PAGE_DOMAIN** (2026-09-05, ADR-068) — domínio próprio `mastavista.com.br` pra landing
  page, fornecido e pedido explicitamente pelo usuário — extensão aditiva do ADR-060 (nenhum
  recurso recriado). `google_compute_managed_ssl_certificate` escopado só ao domínio (sem `www`);
  novo `google_compute_target_https_proxy` na porta 443, mesmo IP estático de sempre; o proxy HTTP
  existente passa a redirecionar pra HTTPS (`google_compute_url_map` novo, `https_redirect =
  true`) em vez de servir o bucket direto. Tudo condicionado a `var.landing_domain != ""`
  (default = o domínio real; vazio desliga tudo e mantém o comportamento HTTP-only do ADR-060).
  DNS fica fora do Terraform — apontar o registro A pro `landing_page_ip` é passo manual do
  usuário no provedor de DNS; o cert fica `PROVISIONING` até isso resolver.
- **PORTAL** (2026-09-05, ADR-073) — portal operacional web pedido explicitamente pelo usuário
  (nenhuma aplicação própria existia — só páginas do Console GCP gateadas por IAM). Novo Cloud Run
  service `revenueflow-api-portal` (`scripts/portal_server.py`, mesma imagem da API, mesmo padrão
  do MCP público). Leitura direto de `repositories.analytics`/`audit`/`portal` (`quote`/
  `sales_order`/`payment`/`conversation_session`, sem migração nova); ação (aprovar/rejeitar/
  resolver) via `httpx` contra as MESMAS rotas `/internal/approvals`/`/internal/handoffs` do MCP
  pessoal (ADR-064) — o portal nunca escreve direto em tabela de estado (ADR-037). Autenticação:
  Google Sign-In client-side (`google-auth`, sem client secret) + allowlist reaproveitando
  `var.dashboard_viewer_emails` (ADR-065, mesma lista) + cookie de sessão HMAC (TTL 12h). Painel de
  agentes ao vivo: `AuditTracer.span()` ganha um `NOTIFY` Postgres best-effort
  (`observability/live.py`, fire-and-forget, nunca propaga erro pro turno); `GET
  /portal/live/stream` (SSE) faz `LISTEN` e destaca o nó ativo do grafo em tempo real —
  `min_instance_count=1` no serviço do portal (único do projeto que não escala a zero) pra não
  perder eventos. IAP considerado e rejeitado (exigiria criar um "IAP brand" irreversível no
  projeto). Extra opcional `portal` (`google-auth`, `jinja2`). Pendente: criar o OAuth Client ID
  "Web application" no Google Cloud Console (origem JavaScript = URL do portal) e preencher
  `PORTAL_GOOGLE_CLIENT_ID` via `gcloud secrets versions add` — mesmo padrão dos secrets manuais do
  WhatsApp.
- **SUBDOMAINS** (2026-09-06, ADR-074) — `mcp.mastavista.com.br`/`portal.mastavista.com.br`
  pedidos explicitamente pelo usuário, extensão aditiva do ADR-068 (mesmo IP/Load Balancer/
  certificado, nenhum recurso recriado além do certificado em si). `infra/terraform/subdomains.tf`
  (novo): 1 `google_compute_region_network_endpoint_group` (`SERVERLESS`) + 1
  `google_compute_backend_service` por serviço (`mcp_readonly`, `portal`) — padrão oficial do GCP
  pra Cloud Run atrás de um HTTP(S) Load Balancer. `landing_page.tf`: `host_rule`/`path_matcher`
  novos no `google_compute_url_map.landing` já existente (`default_service` — a landing page —
  inalterado); `domains` do certificado gerenciado ganha os 2 subdomínios (campo imutável,
  certificado recriado — usuário confirmou aceitar a janela de reprovisionamento antes da
  implementação). `outputs.tf` += `mcp_domain_url`/`portal_domain_url`. Pendência operacional
  nova: 2 registros DNS A (`mcp`/`portal`) → mesmo `landing_page_ip`. **Correção pós-merge**: o
  primeiro `apply` real falhou (`resourceInUseByAnotherResource` — Terraform tentou destruir o
  certificado antigo antes de criar o novo); corrigido com `lifecycle { create_before_destroy =
  true }` + nome do certificado derivado de um hash dos domínios (senão colidiria com o nome fixo
  do antigo durante a transição).
- **LANGFUSE_SELF_HOSTED** (2026-09-08, ADR-075) — fecha a lacuna achada ao investigar por que o
  portal não mostrava nada de observabilidade: `TRACER_SINK` real em produção nunca saiu de `noop`
  (ADR-056 documentou a troca pra `otel`, mas o `terraform.tfvars` real nunca foi atualizado).
  Usuário pediu explicitamente pra resolver e escolheu self-hosted completo (controle total) em vez
  de Langfuse Cloud SaaS. Novo Cloud Run service `revenueflow-api-langfuse`
  (`infra/terraform/langfuse_service.tf`), mesma imagem pública `langfuse/langfuse:2` do
  `docker-compose.yml` local — sem build próprio. Banco próprio (`google_sql_database`/
  `google_sql_user` `langfuse`) na MESMA instância Cloud SQL já existente (`cloud_sql.tf`), DSN via
  IP privado + `sslmode=require` (não o socket unix `/cloudsql/...` que os pools `psycopg` da app
  usam — o cliente Prisma/Node do Langfuse não fala essa convenção; **correção pós-merge**: o 1º
  `apply` real usou o IP PÚBLICO da instância e quebrou — `ipv4_enabled=true` sem
  `authorized_networks` bloqueia por padrão qualquer IP externo, não abre a instância; corrigido com
  Serverless VPC Access connector + IP privado, `infra/terraform/langfuse_network.tf`, em vez de
  abrir `authorized_networks` pra `0.0.0.0/0` — que seria uma regressão de segurança real). Subdomínio fixo
  `langfuse.mastavista.com.br` (mesmo padrão Serverless NEG + backend service do ADR-074) em vez da
  URL `*.run.app` do Cloud Run — resolve de saída o ovo-e-galinha do `NEXTAUTH_URL` (precisa ser
  conhecido antes do 1º boot; a URL do Cloud Run só existe depois do serviço criado). Certificado
  gerenciado ganha esse 4º domínio (mesma janela de reprovisionamento já aceita no ADR-074). 3
  secrets novos Terraform-gerados (`secrets.tf`, mesmo padrão dos tokens approval/handoff/mcp —
  não travam o deploy num passo manual): `revenueflow-langfuse-database-url`,
  `revenueflow-langfuse-nextauth-secret`, `revenueflow-langfuse-salt`. `LANGFUSE_PUBLIC_KEY`/
  `LANGFUSE_SECRET_KEY` continuam manuais (só existem depois do 1º login gerar o par de API keys na
  própria UI). `var.tracer_sink` continua `noop` nesta fatia — vira `langfuse` numa troca de
  `tfvars` separada, só depois do passo manual. `AUTH_DISABLE_SIGNUP` controlado por
  `var.langfuse_disable_signup` (default `false`, signup aberto até a 1ª conta admin existir).
  **Sem** automatizar a conta admin/API keys via Terraform, sem instância Cloud SQL dedicada
  (ADR-075). **Mais 3 correções pós-merge até o deploy real ter sucesso**: nome do VPC connector
  excedia o limite de 25 caracteres do GCP (`lf` no lugar de `langfuse`); a API do GCP rejeita
  criar o connector sem `max_instances`/`max_throughput` explícito (`min_instances=2`/
  `max_instances=3`); e um connector ficou órfão em estado `ERROR` depois de uma tentativa que
  falhou a meio caminho — `terraform apply` não registrou o ID no state, então a tentativa seguinte
  colidiu com `409 already exists`; resolvido deletando o recurso quebrado manualmente
  (`gcloud compute networks vpc-access connectors delete`) antes de reaplicar. **Incidente
  paralelo**: adicionar o 4º domínio (`langfuse.mastavista.com.br`) ao certificado gerenciado o
  recriou (campo imutável) e tirou `mastavista.com.br`/`mcp.`/`portal.` do ar por ~40 min — o
  certificado só fica `ACTIVE` (e só então o Load Balancer o usa) quando **todos** os domínios
  validam, não domínio a domínio; o novo precisava de um registro DNS A que ainda não existia.
  Lição: ao adicionar um domínio a um certificado gerenciado multi-domínio já em uso, confirmar o
  DNS do domínio novo **antes** do apply, não depois — o ADR-074 já documentava aceitar a janela de
  reprovisionamento, mas presumia que todo domínio já tinha DNS pronto.
- **CLOUD_SCHEDULER_JOBS** (2026-09-08, ADR-076) — fecha o follow-up documentado desde
  OPPORTUNITY_ENGINE/ACTIVE_SALES/ANALYTICS/LEAD_LIFECYCLE (cada um mencionava Cloud Scheduler como
  pendência, nunca implementado). `infra/terraform/scheduler.tf` (novo): 4 `google_cloud_scheduler_job`
  (padrão oficial GCP pra Cloud Run Job — `http_target` na API v1 de Jobs + `oauth_token`), 1 por
  `opportunity_scan`/`campaign_run`/`lead_sweep`/`analytics_sync`, com uma service account dedicada
  (`revenueflow-api-scheduler`, ADR-008 least privilege — só `roles/run.invoker` nos 4 Jobs, nunca a
  SA de runtime da própria API). Horários encadeados: `opportunity_scan` 09:00 UTC, `lead_sweep`
  09:15 UTC, `campaign_run` 09:30 UTC (30 min de folga pra consumir as oportunidades que o scan
  acabou de gerar — Cloud Scheduler não tem "rodar depois que X terminar" nativo),
  `analytics_sync` 22:00 UTC. **Sem** orquestração explícita de dependência (Cloud Workflows) —
  a folga de horário é suficiente pro volume atual.
- **EXPIRATION_TTL_SWEEP** (2026-09-09, ADR-077) — achado ao vivo enquanto o usuário testava o
  fluxo end-to-end de novo: uma `Approval` que ninguém decidiu deixou o checkpoint do LangGraph
  pausado em `await_approval` **para sempre** — toda mensagem seguinte da mesma conversa caía na
  resposta fixa "sua solicitação ainda está em análise", sem nunca progredir (`Approval` já tinha
  `expires_at` desde o ADR-050, mas nada verificava isso proativamente). Destravado manualmente
  primeiro (conectando direto no Cloud SQL via Cloud SQL Python Connector — `psql`/`cloud-sql-proxy`
  não estavam disponíveis localmente — e limpando o checkpoint dessa conversa: 402 linhas de
  `checkpoint_writes`, 55 de `checkpoint_blobs`, 137 de `checkpoints`), depois corrigido de vez.
  `services/expiration.py::sweep()` (batch, fora do grafo, ADR-019/020, Cloud Scheduler de hora em
  hora — não diário como os outros 4 Jobs, `infra/terraform/expiration_sweep_job.tf`): Approval
  `PENDING` vencida publica `approval_decided` (mesmo evento da rota humana —
  `apply_decision_node` já se auto-detecta expirado a partir de `expires_at`, só faltava alguém
  disparar o resume); Quote `SENT` vencida vira `EXPIRED` (para de aparecer em `get_open_quote`);
  Handoff `PENDING` mais velho que `handoff_stale_hours` (novo, default 24h) é auto-resolvido e a
  sessão volta pra `OPEN`. **Segundo bug achado na mesma investigação, mesmo PR**: resolver um
  Handoff (`POST /internal/handoffs/{id}`) nunca revertia `conversation_session.status` — a sessão
  ficava presa em `HUMAN_HANDOFF` mesmo depois do atendente marcar como resolvido; corrigido em
  `services/handoff.py::resolve` (agora sempre reabre a sessão, não só no caminho de expiração
  automática). `0015` cria índices parciais em `approval`/`quote` pro sweep horário. **Sem**
  notificação quando um Handoff expira sem resolução humana, sem TTL configurável por
  conversa/cliente (ADR-077).
- **WHATSAPP_OPT_IN** (2026-09-09, ADR-078) — fecha o follow-up documentado desde ACTIVE_SALES
  (ADR-059): `consent_opt_in_at` nunca era populado por ninguém, então `campaign.run()` nunca de
  fato contatava um cliente real. `policies/outbound_policy.py::is_opt_in` — mesmo padrão exato de
  `is_opt_out` (match exato, não substring). Frase escolhida pelo usuário: **"ACEITO RECEBER
  OFERTAS"** — deliberadamente específica; uma palavra curta como "aceito" sozinha colidiria com
  aceitar uma proposta de negociação/preço (testado explicitamente: `test_is_opt_in_rejects_...`).
  Guard simétrico em `worker/consume.py::process_event`, logo depois do guard de opt-out — grava
  `consent_opt_in_at` (só quando `customer_id` já existe) e responde fixo, sem passar pelo grafo.
  **Sem** pergunta proativa de opt-in em algum ponto do fluxo — a frase precisa ser comunicada ao
  cliente por fora (campanha, landing page) pra virar utilizável na prática (ADR-078).
- **OPPORTUNITY_ENGINE_REMAINING_TYPES** (2026-09-09, ADR-079) — fecha a lacuna do PRD-010: só 2
  dos 8 tipos de oportunidade listados (REPLENISHMENT, QUOTE_RECOVERY) tinham regra implementada.
  Usuário autorizou explicitamente implementar os 6 restantes de uma vez, decisão de negócio por
  minha conta, documentada no ADR-079. CHURN/REACTIVATION reusam o sinal do REPLENISHMENT
  (`ReplenishmentSignal`) em multiplicadores mais altos (`churn_threshold=3.0`,
  `reactivation_threshold=6.0`), `product=None` (sinal de relacionamento, não de produto) — **não**
  são mutuamente exclusivas com REPLENISHMENT (índice único é por tipo, não por cliente).
  ORDER_RECOVERY = `sales_order(FAILED)` sem retentativa `PAID`/`CONFIRMED` depois, com piso de
  idade (`order_recovery_hours=24`). CROSS_SELL sempre oferece o acessório mais barato do catálogo
  (heurística — sem mapa de compatibilidade produto↔acessório). UPSELL recomenda o próximo produto
  mais caro da mesma categoria pra quem recomprou (`upsell_min_repeat_purchases=2`).
  INVENTORY_TO_CASH inverte a direção do sinal (parte do produto parado em estoque, não do
  cliente). `services/opportunity.py::scan()` generaliza de 2 para 8 chamadas via um helper privado
  `_apply()` (contagem + `try/except` isolado por candidato, mesmo padrão de antes). Sem migração
  nova (o índice único parcial de `0007` já cobre qualquer `opportunity_type`).

**Incidente 2026-09-09**: usuário reportou "Langfuse ainda sem dados" (de novo, apesar do pin
`langfuse<3` do PR #104) e, em paralelo, a mesma conversa de teste caindo em handoff humano em
mensagens triviais de produto. Investigados juntos:
1. **Langfuse**: `revenueflow-api-langfuse` tinha `min_instance_count=0` — todo flush de trace
   sofria cold start (~18s medido direto) que estourava o timeout do cliente HTTP do SDK antes da
   requisição sequer chegar no serviço (zero hits em `/api/public/ingestion` nos logs, apesar de
   turnos reais rodando). Corrigido com `min_instance_count=1` (mesmo ajuste do portal, mesma
   classe de motivo — dependência chamada por turno não tolera cold start).
2. **Handoff em mensagem trivial**: não era bug de código — `classify_intent_node` isola
   `LLMError` corretamente (confirmado: nenhuma exceção não-tratada, `handoff_reason` real era
   `explicit_request`, não `intent`). O Gemini genuinamente classificou mensagens como "Bomba
   d'água centrífuga 1.5CV 220V" como `human_support` algumas vezes — reprodução local do mesmo
   texto retornou a classificação correta. O prompt v2 (`services/prompts.py`) não dava nenhum
   critério de precisão pra `human_support`, só listava o enum; `_INTENT_SYSTEM` v3 adiciona uma
   cláusula explícita ("APENAS quando o cliente pedir explicitamente para falar com uma pessoa,
   atendente ou humano") e `classify_intent_node` ganhou um log em INFO sempre que classificar
   `human_support`, pra confirmar se o v3 reduz a taxa ou se acontecer de novo com evidência
   melhor. Sem certeza absoluta de causa raiz (ruído de LLM não é 100% eliminável), mas o prompt
   mais preciso e o logging novo são a mitigação disponível nesta fatia.

Deploy: **auditoria em 2026-09-05 (ADR-069 a 072) achou que nenhum deploy real tinha rodado desde
CUSTOMER_360 (2026-09-03)** — o ambiente GitHub `production` tem um gate de aprovação manual
(`required_reviewers`) que ficou parado por 17 deploys seguidos sem ninguém aprovar. Quando
finalmente aprovado, o `apply` revelou, em camadas sucessivas (cada uma só aparecia depois da
anterior ser corrigida): `deployer_roles` sem `logging.admin`/`monitoring.admin`/`compute.admin`/
`bigquery.admin` (ADR-069/070, corrigido e **já reaplicado manualmente no bootstrap**, confirmado
via `gcloud`); o pacote `mcp` v2.x quebrando `revenueflow-mcp-readonly` por renomear
`FastMCP`→`MCPServer` (ADR-070, `pyproject.toml` fixado em `mcp>=1.9,<2`, **já confirmado
funcionando em produção**); e `ALIGN_SUM` não escalariza métrica `DISTRIBUTION` nos 2 alertas de
custo/falha de ferramenta — tentativa 1 (ADR-071, métrica gêmea sem `bucket_options`) também falhou
porque `value_extractor` só é legal em métrica `DISTRIBUTION`; corrigido de vez no ADR-072
(`ALIGN_PERCENTILE_99` nas métricas originais, mudando a semântica do alerta pra "pico por turno"
em vez de "total na hora", documentado nos próprios alertas). Um `apply` real já criou a maior
parte da infraestrutura (Load Balancer da landing page, BigQuery, Cloud Run
`revenueflow-mcp-readonly` rodando com sucesso) — só os 2 alertas de custo/falha de ferramenta
ficaram pendentes de confirmação depois do fix do ADR-072 — **confirmado**: os 5 alertas do
Monitoring estão ativos em produção (`gcloud alpha monitoring policies list`). DNS de
`mastavista.com.br` também **já resolve certo** (`34.49.128.234`) e o certificado gerenciado está
`ACTIVE` — HTTPS da landing page está de fato no ar.

**Incidente 2026-09-06** (achado e corrigido na sessão seguinte): o merge do PORTAL (ADR-073)
adicionou `PORTAL_GOOGLE_CLIENT_ID` a `manual_secrets`, que o `cloud_run.tf` monta em TODO serviço
(inclusive a API principal, que não usa esse secret) via `local.runtime_secret_env` — sem
`gcloud secrets versions add` prévio (a etapa manual que o comentário de `secrets.tf` já exige
antes do 1º deploy saudável), isso quebrou o deploy da API principal por ~15h (produção continuou
servindo a revisão anterior o tempo todo — nunca caiu, só os deploys novos ficaram bloqueados).
Corrigido com um valor placeholder no secret; o `revenueflow-api-portal` também subiu com sucesso
pela primeira vez no mesmo deploy. **Risco latente não corrigido**: qualquer secret manual novo
adicionado por uma fatia futura vai repetir esse mesmo bloqueio se ninguém popular o valor antes do
próximo deploy — vale considerar, como follow-up, escopar `runtime_secret_env` só aos secrets que a
API principal realmente usa, em vez do mapa inteiro de `manual_secrets`.

**Incidente 2026-09-06 (nº2)**: a primeira execução real de qualquer um dos 4 jobs batch
(`opportunity-scan`/`campaign-run`/`lead-sweep`/`analytics-sync` — nenhum tinha rodado em produção
antes de hoje) revelou que os 4 scripts (`scripts/detect_opportunities.py` e companhia) nunca
chamavam `open_pool()` antes de usar o pool de conexões — `psycopg_pool.PoolClosed` em toda
tentativa. Corrigido nos 4 (`open_pool()`/`close_pool()` ao redor da chamada do serviço, mesmo
padrão da fixture `db` dos testes); verificado rodando de verdade contra Postgres real localmente
(3 dos 4 — `sync_analytics.py` só confirmado até a abertura do pool, pra não gravar dado de teste
no BigQuery real). Risco latente: nenhum desses 4 scripts tinha teste próprio, só os `services.*`
subjacentes — o bug só apareceu rodando de verdade.

**Incidente 2026-09-06 (nº3)**: o fix acima (PR #74) mergeou em `main` mas **nunca chegou a
produção sozinho** — o `path` do trigger `push` do `.github/workflows/terraform.yml` (que builda e
sobe a imagem Docker nova a cada push) cobria `src/**`/`Dockerfile`/`pyproject.toml`, mas não
`scripts/**`/`migrations/**`/`seeds/**`, apesar dos 3 serem `COPY`ados pro container (`Dockerfile`).
Um PR que só toca `scripts/` passa no CI e mergeia, mas a imagem em produção nunca é reconstruída —
só um push futuro que toque `src/**` "carregaria" o fix, por acidente. Corrigido adicionando os 3
diretórios ao filtro; teste novo (`test_ci_workflow.py`) trava os dois lados um contra o outro
(todo `COPY` do Dockerfile precisa estar no filtro do trigger) pra não regredir de novo.

**Incidente 2026-09-07**: teste end-to-end real do CTA de WhatsApp da landing page revelou uma
cadeia de 4 problemas independentes, cada um mascarando o próximo — nenhuma mensagem real de
cliente jamais tinha percorrido o fluxo completo em produção até este dia:
1. **Número errado no CTA** (`5519982499116`, nunca confirmado — o próprio ADR-066 já registrava
   isso). Corrigido pro número real (`+1 555-202-7113`, número de teste do Meta, confirmado via
   Graph API `display_phone_number`); mensagem pré-preenchida passou a citar um produto real do
   catálogo. Addendum no ADR-066.
2. **Access token do WhatsApp expirado** (token temporário do painel de teste, ~24h de validade).
   Substituído por um token de usuário de sistema sem expiração (Business Settings → Usuários do
   sistema), gravado em `revenueflow-whatsapp-access-token` + force-redeploy do Cloud Run pra
   pegar o valor novo (mesma pegadinha do `version="latest"` de sempre).
3. **A WABA nunca esteve inscrita no app da aplicação** (`POST /{waba-id}/subscribed_apps`) — só
   estava inscrita no app interno de teste do Meta (`WA DevX Webhook Events 1P App`). Mesmo com
   webhook verificado e campo `messages` assinado, nenhuma chamada chegava. Corrigido chamando a
   mesma rota com o token do usuário de sistema (idempotente, sem infra/deploy).
4. **Bug real de código, achado só depois de instrumentar o webhook com um log de diagnóstico
   (PR #79, sem PII — só a forma do payload)**: `events/publisher.py::_default_publisher()` tinha
   os dois ramos do `if/else` retornando `InMemoryPublisher()` — o ramo que deveria escolher
   `PubSubPublisher()` pra projetos GCP reais nunca foi escrito, apesar do docstring do módulo já
   sinalizar isso como pendente ("for now"). **Toda mensagem inbound, em produção, desde que a
   fatia `WHATSAPP_INBOUND_SLICE` foi construída (ADR-044), era publicada numa lista em memória
   descartada no fim da requisição** — o tópico real do Pub/Sub nunca recebia nada, o subscriber
   (que corretamente usa `pubsub_v1.SubscriberClient` contra o tópico real) nunca tinha o que
   processar, e nenhuma resposta jamais foi enviada. Corrigido (PR #80) + 2 testes de regressão
   travando a seleção do publisher por `pubsub_project_id`.

Depois do fix #4, o teste end-to-end **funcionou de ponta a ponta pela primeira vez**: webhook →
Pub/Sub real → subscriber → grafo (Gemini real, `LLM_STUB=0` confirmado) → `ChannelOutbound.send`
→ mensagem entregue no WhatsApp do usuário. Achado colateral: o primeiro turno real levou ~4min
entre o webhook aceitar e o subscriber processar, e o processamento em si estourou o
`turn_budget_s=15` (ADR-057) — usuário recebeu o `_SLOW_REPLY` fixo em vez da recomendação real.
Não investigado a fundo ainda (hipótese: warm-up de cliente Vertex/pool de conexão no primeiro
turno real da instância) — acompanhar se turnos seguintes normalizam.

**Achado à parte, não relacionado ao WhatsApp (2026-09-07, resolvido 2026-09-09)**: `TRACER_SINK`
em produção estava `noop`, não `otel` como o bullet OBSERVABILITY_OPS abaixo afirma — o `ADR-056`
nunca chegou a ser de fato aplicado. Usuário queria **Langfuse** em produção (não OTel/Cloud
Trace) — resolvido pela fatia LANGFUSE_SELF_HOSTED (ADR-075): `var.tracer_sink` default virou
`"langfuse"` depois do onboarding manual (1ª conta admin, org/project, par de API keys, secrets
populados) confirmado em 2026-09-09 — `AuditTracer` agora envia de verdade pro Langfuse
self-hosted em `langfuse.mastavista.com.br`. Ver bullet OBSERVABILITY_OPS — a frase "produção
passa a `TRACER_SINK=otel`" ali continua desatualizada/nunca foi verdade na prática (produção usa
`langfuse`, não `otel`); não corrigida no bullet original, só registrada aqui.

**Incidente 2026-09-08 — cadeia de 6 fixes até o WhatsApp end-to-end funcionar de verdade**: o
teste real do CTA (ADR-066) revelou que "webhook aceita e Pub/Sub publica" nunca foi o mesmo que
"o cliente recebe a recomendação real" — 6 achados reais em produção, cada um mascarando o
seguinte:
1. **Cliente Vertex reconstruído a cada chamada** (`services/llm.py::_vertex_client()`) —
   resolução de credenciais ADC síncrona no event loop em toda chamada de LLM, fora do
   `asyncio.wait_for`. Um turno chegou a 239s. Fix: client cacheado por processo.
2. **`AsyncConnectionPool` da app fixo em 4 conexões** (default do psycopg_pool nunca
   configurado) — `error connecting in 'pool-1': connection timeout expired` sob carga real.
   Fix: `min_size=2, max_size=10`.
3. **Checkpointer do LangGraph com uma conexão bare só, pra vida toda do processo**
   (`AsyncPostgresSaver.from_conn_string`), atrás do próprio `asyncio.Lock()` da lib, compartilhada
   por todo turno concorrente. Fix: `AsyncPostgresSaver(AsyncConnectionPool(...))` — a lib aceita
   pool nativamente.
4. **`turn_budget_s=15` e `ack_deadline_seconds=60` apertados demais** pra 2 chamadas Gemini
   reais sequenciais + overhead de DB — um turno legítimo sem bug nenhum levava ~30s. Pior: o
   Pub/Sub redeliverava a mensagem **enquanto ela ainda estava sendo processada**, gerando
   processamento concorrente duplicado da mesma mensagem (confirmado ao vivo: a mesma mensagem
   processada 3x em paralelo). Fix: `turn_budget_s=25`, `ack_deadline_seconds=120`.
5. **`revenueflow-api` rodando no default bruto do Cloud Run (512Mi/1 CPU)**, nunca configurado
   explicitamente — não sustentava LangGraph + 2 pools de até 10 conexões + cliente Vertex sob
   reentrega concorrente. Bate com o padrão "Starting new instance" → "Shutting down" ~10s
   depois, no meio do processamento, sem log de ack/nack — consistente com OOM kill. Fix:
   `memory=2Gi`.
6. **Negociação perdia o produto em qualquer follow-up sem repetir o nome dele**
   (`recommendation_node` refazia a busca por produto todo turno e sobrescrevia `tool_results` com
   resultado vazio quando a mensagem não citava produto — ex.: "pode fazer por 700?"). Fix: se a
   busca do turno não acha nada e já havia produto estabelecido, retorna `{}` (preserva o estado
   do checkpointer em vez de apagar).

Depois do fix #5, turnos novos passaram a processar em segundos (2.5s–12.9s), sem redelivery, com
resposta real do Gemini entregue via WhatsApp — confirmado com uma sequência de negociação real
(quoted → proposed → clarify). Catálogo simulado também expandido nesse mesmo dia: 6→24 produtos,
3→15 clientes (`seeds/*.json`), já carregado em produção via `revenueflow-api-migrate`. Landing
page ganhou uma seção "Simular" com 5 cenários de teste (preço/estoque/desconto/pedido/handoff) +
tabela do catálogo com preço real.

Pendências operacionais: valores reais dos secrets do WhatsApp (✅ preenchidos e token permanente
gerado 2026-09-07), registro do webhook no Meta (✅ confirmado, incl. inscrição da WABA no app —
2026-09-07), migração do banco (✅ `0006`–`0014` aplicadas em 2026-09-06), DNS + certificado dos
subdomínios do ADR-074 (✅ `mastavista.com.br`/`mcp`/`portal` — certificado `ACTIVE` nos 3
domínios, confirmado 2026-09-08), os 4 jobs batch (✅ `opportunity-scan`/`lead-sweep`/
`analytics-sync`/`campaign-run` — todos já rodaram com sucesso em 2026-09-06), `ALERT_EMAIL` nas
GitHub Actions repo variables (✅ `jonalic@gmail.com`, `DASHBOARD_VIEWER_EMAILS` ✅ preenchida),
token do MCP público (✅ distribuído — usuário configurou o conector no claude.ai com
`mcp.mastavista.com.br`), OAuth Client ID do portal (✅ configurado, login real confirmado
funcionando com 3 contas), latência do primeiro turno (✅ investigada e corrigida — ver cadeia de
6 fixes acima), negociação perdendo contexto de desconto/quantidade em follow-up (✅ corrigido —
`negotiation_node` reaplica o desconto/quantidade já estabelecidos quando o turno atual não os
repete, PR #94). Langfuse em produção (✅ concluído 2026-09-09 — DNS/certificado/1ª conta
admin/API keys/`var.tracer_sink="langfuse"`, todos os passos manuais do ADR-075 fechados; ver
correção pós-merge do ADR-075 e o ADR-076 pro incidente de outage de ~40min do certificado durante
esse processo), os 4 jobs batch agora rodam sozinhos via Cloud Scheduler (✅ ADR-076, 2026-09-09 —
não mais só sob demanda). **Resta**: popular `consent_opt_in_at` de clientes reais (deferido
deliberadamente — só quando o cliente responder no WhatsApp, per decisão do usuário).

O código de aplicação **existe** e não é mais scaffolding.

Fluxo que roda: `POST /webhook/whatsapp` (HMAC) → Pub/Sub `message_received` → `process_event`
idempotente → sessão + lead provisório → grafo LangGraph `classify_intent → supervisor →
{handoff | recommendation → {respond | negotiation → [await_approval → apply_decision] → [checkout]}}`
(checkpointer PostgreSQL) → resposta ancorada / proposta de desconto / "encaminhado para
aprovação" / proposta versionada + "sim, pode fechar" / pedido + pagamento sandbox / transferência
para atendente humano (pedido explícito, baixa confiança, alto valor ou falha de LLM) →
`ChannelOutbound.send`. A retomada da aprovação chega por
`POST /internal/approvals/{id}` → evento `approval_decided` → consumer com advisory lock. O gate
de checkout: `supervisor` lê `get_open_quote`; enquanto há `Quote(SENT)`, o turno é do
`checkout_node`. O `supervisor` também transfere (`handoff`) em pedido explícito ou baixa
confiança quando **não** há quote aberto; sessão em `HUMAN_HANDOFF` não roda o grafo.

Mapa de `src/revenueflow/`:

| Pacote | Papel |
|---|---|
| `config` | `Settings` tipado (pydantic-settings) + flags `CHANNEL_OUTBOUND`/`TRACER_SINK`/`LLM_STUB`; `google_cloud_project`/`vertex_location`/`llm_max_retries`; `log_level`/`otel_service_name`; `llm_call_timeout_s`/`db_statement_timeout_ms`/`turn_budget_s`; `bigquery_dataset`; `lead_stale_days`; `revenueflow_api_base_url`; `mcp_api_token`;
`portal_viewer_emails`/`portal_google_client_id`/`portal_session_secret` |
| `domain` | erros tipados; enums `SessionStatus` (+`HUMAN_HANDOFF`)/`LeadStatus`/`Intent`/`ApprovalStatus`/`QuoteStatus`/`OrderStatus`/`PaymentStatus`/`OpportunityType`/`OpportunityStatus`/`HandoffReason`/`HandoffStatus`; dataclasses de entidade (`Quote`/`Order`/`Payment`/`Customer`/`Opportunity`/`Handoff` incl.) |
| `observability` | `mask()` de PII (email/CPF/phone + `extra_terms`, ADR-058); porta `Tracer` (`noop`/`langfuse`/`otel` + `AuditTracer` que envolve o sink, grava `audit_event` e emite a linha `audit.turn` por turno via `flush()`; `span()` também dispara `live.notify_agent_start`/`_end`, ADR-073); `live.py` (`NOTIFY`/`LISTEN` best-effort do painel de agentes ao vivo do portal); `cost_usd()` (`MODEL_PRICES` do Vertex); `logging_setup` (`JsonFormatter` stdlib + `configure_logging`); `otel_setup` (`configure_otel` — `TracerProvider` + Cloud Trace exporter, ADR-056) |
| `events` | `EventEnvelope`; porta `EventPublisher` (`in_memory`/`pubsub`) |
| `adapters` | portas de canal; `verify_signature` + `parse_inbound`; `WhatsAppOutbound` + `FakeOutbound` |
| `repositories` | pool async psycopg; `processed_event`/`dispatch` (idempotência); `session` (+`set_customer`)/`lead` (`get_by_phone`/`get_by_id`/`set_status`/`stale_candidates`)/`customer` (`get_by_phone`/`customer_360`/`set_consent_opt_in`/`set_consent_opt_out`); `sim_*`; `sim_pricing`; `approval`; `checkout` (quote/order/payment); `opportunity` (`upsert_open`/`list_by_status`/`set_status` + queries de candidatos); `handoff` (`create` idempotente/`list_by_status`/`resolve`); `audit` (`record` `ON CONFLICT`/`by_conversation`); `outbound_contact` (`last_contact_at`/`record`); `analytics` (`conversation_revenue`/`cost_per_outcome`/`customer_360_all`/`lead_funnel`/`opportunity_summary`/`handoff_rate`, JSON-safe pra BigQuery) |
| `policies` | `pricing_policy.evaluate()` (alçada/margem) + `opportunity_policy` (`replenishment`/`churn`/`reactivation`/`quote_recovery`/`order_recovery`/`cross_sell`/`upsell`/`inventory_to_cash`, ADR-053/079) + `handoff_policy.should_handoff` (3 gatilhos) + `outbound_policy` (`evaluate` — Policy Gate de contato ativo; `is_opt_out`/`is_opt_in` — guards inbound) + `lead_policy.advance` (transição de status, monotônica) — regras puras, sem I/O nem LLM |
| `services` | `ingest`, `session` (+`phone_for`), `identity` (`customer` antes do `lead`), `prompts` (v2), `llm` (stub + Vertex real), `intent`, `respond`, `pricing`, `negotiation`, `approval`, `checkout` (`is_explicit_confirmation` + `quote_from_state` + `confirm`), `opportunity` (`scan()` — batch, fora do grafo, 8 tipos via helper `_apply()`, ADR-079), `handoff` (`build_context` SPEC-027 + `create`/`list_pending`/`resolve`), `audit` (`persist` falha-isolada + `reconstruct`), `campaign` (`run()` — batch, Policy Gate + envio, fora do grafo), `analytics_sync` (`run()` — batch, 6 cargas via `_SOURCES`, sync BigQuery `WRITE_TRUNCATE`, fora do grafo), `lead_lifecycle` (`advance_from_turn` — síncrono, promove a Customer em `WON`; `sweep_stale()` — batch, `LOST`) |
| `tools` | `RECOMMENDATION_TOOLS` (5 read-only, incl. `get_customer_360`) + `NEGOTIATION_TOOLS` (3 de pricing) + `CHECKOUT_TOOLS` (`create_quote`/`create_order`/`create_payment_sandbox`, determinísticas, registry isolado) + `registry` (fronteira — nenhum `set_discount`) |
| `agents` | `TurnState`; `recommendation_node` (anexa `get_customer_360` p/ cliente conhecido); `negotiation_node` (+check `high_value_order`) + `await_approval_node` + `apply_decision_node` (ADR-050); `checkout_node` (quote/confirmação/order/payment, ADR-051); `handoff.py` (`to_handoff` + `handoff_node` que persiste + marca `HUMAN_HANDOFF`, ADR-054); `build_graph` |
| `mcp` | `tools.py` (leitura via `repositories.analytics` + ação via `httpx` nas rotas `/internal/*`, sem depender do pacote `mcp`) + `auth.py` (`bearer_gate` ASGI, também sem depender do pacote `mcp`) + `server.py` (`register_read_tools`/`register_action_tools`; servidor pessoal stdio, ADR-064, os dois) + `http_server.py` (servidor público Streamable HTTP, ADR-067, só `register_read_tools`) |
| `api` | `webhook` (GET verify + POST 202), `health` (`/healthz`), `approvals` (`/internal/approvals`, Bearer), `handoffs` (`/internal/handoffs`, Bearer), `audit` (`/internal/audit/{conversation_id}`, Bearer). `main.py` tem um `@app.middleware("http")` de headers de segurança (ADR-058) |
| `portal` | `auth.py` (Google Sign-In + allowlist + cookie de sessão, sem depender de banco/rede) + `views.py` (rotas de leitura via `repositories.*` + ação via `httpx` nas rotas `/internal/*`, nunca escreve direto) + `server.py` (app FastAPI própria, mesmo middleware de segurança do `main.py`) + `templates/` (Jinja2, sem SPA); painel ao vivo via `observability/live.py` (ADR-073) |
| `worker` | `process_event` (+ guard de opt-out inbound antes do grafo; + `lead_lifecycle.advance_from_turn` depois do `ainvoke`) + `process_approval_decided` (consumidores idempotentes), `subscriber` (loop Pub/Sub, roteia por `event_type`) |

Portas com impl `noop`/`in_memory`/`fake` por default: a suíte roda só com `postgres:16`. Os
caminhos reais (`google-genai`, `google-cloud-pubsub`, `httpx` para a Graph API, `langfuse`) são
imports lazy atrás de flags/extras opcionais.

Modo `LLM_STUB`: `llm_stub=True` continua sendo o default de `Settings` (dev local com `make up`
sem GCP, e CI — que roda sem credencial de nuvem). Em produção o Cloud Run roda `LLM_STUB=0` e
intent/resposta chamam o Vertex AI real (ADR-049, fatia `WHATSAPP_INBOUND_VERTEX`).

### Como rodar

```bash
make up          # sobe app + postgres + emulador Pub/Sub + Langfuse (docker-compose)
make run         # roda a API local com autoreload (precisa de postgres)
make migrate     # aplica migrations + setup do checkpointer LangGraph
make seed        # popula o catálogo/estoque simulado
make check       # lint + typecheck + testes + validate_docs (tudo que o CI roda)
```

`make test` sobe `postgres` via compose e roda `pytest -q` (~150 testes: unit + integration +
security + ai_eval; os testes marcados `live` só rodam com `RUN_LIVE_EVAL=1` + ADC).

## Invariantes

- LLM não é fonte de verdade para preço, estoque, margem, identidade, pedido ou pagamento.
- LLM interpreta; Policy Engine decide; API executa.
- Tool ausente é controle de segurança; não registrar tools proibidas.
- Ações irreversíveis exigem checkpoint/approval quando definido.
- Nunca executar pagamento real na V1.
- Nunca emitir documento fiscal real.
- Nunca remover guardrail para fazer CI passar.
- Nunca inserir segredo no repositório.
- Nunca usar credenciais de produção em teste.
- Nunca executar `terraform apply`, `terraform destroy`, exclusão de projeto, remoção de banco ou IAM destrutivo sem aprovação humana explícita no terminal.

## GCP

Plataforma principal:
- Cloud Run
- Cloud SQL PostgreSQL
- BigQuery
- Pub/Sub
- Vertex AI / Gemini
- Secret Manager
- Cloud Storage
- Artifact Registry
- IAM
- Terraform

## MCP

O MCP oficial principal deste kit é o **Google Cloud CLI remote MCP**.

Configuração de projeto:
- `.mcp.json`

Endpoint:
- `https://cloudcli.googleapis.com/mcp`

O MCP deve operar com a identidade autenticada do usuário e nunca contornar IAM.

### Servidor MCP pessoal do RevenueFlow (ADR-064)

`src/revenueflow/mcp/` (extra opcional `mcp`, `pip install -e ".[mcp]"`) expõe o próprio sistema
via stdio para o usuário (Claude Desktop/Claude Code), não para uso de terceiros. Tools de leitura
(`get_revenue_summary`/`list_customer_360`/`get_customer_360`/`list_lead_funnel`/
`list_opportunities`/`get_handoff_rate`) leem `repositories.analytics` direto do Postgres, mesmo
padrão dos batch jobs. Tools de ação (`list_pending_approvals`/`decide_approval`/
`list_pending_handoffs`/`resolve_handoff`/`get_audit_trail`) chamam as rotas HTTP internas já
deployadas (Bearer `APPROVAL_API_TOKEN`/`HANDOFF_API_TOKEN`) — nenhuma lógica de negócio nova.
Entrypoint: `scripts/mcp_server.py` (registrar no `claude_desktop_config.json` apontando pro
Python do venv com o extra `mcp` instalado; precisa de `DATABASE_URL` e
`REVENUEFLOW_API_BASE_URL` configurados no ambiente). `mcp/tools.py` não depende do pacote `mcp` —
testável na suíte padrão sem o extra instalado.

## Skills

Skills ficam em `.claude/skills/<skill>/SKILL.md`.

Use a skill quando a tarefa corresponder ao domínio.

## Agentes auxiliares

- `gcp-architect`
- `data-engineer`
- `ai-engineer`
- `terraform-reviewer`
- `security-reviewer`
- `finops-reviewer`
- `spec-reviewer`

O `spec-reviewer` revisa e NÃO corrige código na mesma sessão.

## Hooks

Hooks em `.claude/hooks/` bloqueiam comandos destrutivos ou de alto risco.

Se um hook bloquear uma ação, não tente contorná-lo.
Explique a necessidade e peça aprovação humana.

## Rituais

- `/gcp-check`
- `/gcp-login`
- `/verify-spec`
- `/verify-risk`
- `/terraform-plan`
- `/cloud-run-check`
- `/bigquery-check`
- `/cost-check`

## Processo de feature

```text
PRD
 ↓
SPEC
 ↓
ADRs
 ↓
Implementação
 ↓
testes
 ↓
/verify-spec
 ↓
/verify-risk (quando necessário)
 ↓
PR
```

## Fluxo de contribuição / CI

- A `main` é protegida (`enforce_admins`): **sem push direto**, inclusive para admins.
- Toda tarefa de desenvolvimento cria uma branch nova (`feat/…`, `fix/…`, `chore/…`) e entra por **PR**. Merge é **squash-only**; o título do PR vira a mensagem do commit e precisa seguir Conventional Commits (`feat|fix|test|docs|refactor|chore|ci`).
- 7 checks obrigatórios e "strict" (branch atualizada): `docs`, `lint`, `typecheck`, `tests`, `security`, `pre-commit`, `pr-title`. 0 aprovações humanas exigidas — o portão é o CI.
- Portão local: `pre-commit install --install-hooks` ativa ruff, ruff-format, gitleaks, higiene de arquivos e `scripts/check_commit_msg.py` (Conventional Commits). O job `pre-commit` do CI roda os mesmos hooks.
- Comandos equivalentes ao CI: `python scripts/validate_docs.py`, `ruff check .`, `ruff format --check .`, `mypy src`, `pytest -q`, `pre-commit run --all-files`.
- Dev harness (em construção — fatia WhatsApp inbound): **Docker Compose + Makefile** (`make up/down/migrate/seed/lint/test/run`); o CI usa os mesmos comandos por trás dos alvos.
- Artefatos do fluxo SDD (`/brainstorm`, `/define`, `/design`, `/build`) ficam em `.claude/sdd/` e **não são versionados** (git-ignored).

## Catálogo documental obrigatório

Claude deve localizar e ler os documentos relacionados antes de implementar.

### PRDs
- [PRD-001 — Visão e Objetivos do Produto](docs/prd/prd-001-vis-o-e-objetivos-do-produto.md)
- [PRD-002 — Novo Cliente via WhatsApp](docs/prd/prd-002-novo-cliente-via-whatsapp.md)
- [PRD-003 — Cliente Existente e Customer 360](docs/prd/prd-003-cliente-existente-e-customer-360.md)
- [PRD-004 — Catálogo e Recomendação de Produtos](docs/prd/prd-004-cat-logo-e-recomenda-o-de-produtos.md)
- [PRD-005 — Preço, Margem e Negociação](docs/prd/prd-005-pre-o-margem-e-negocia-o.md)
- [PRD-006 — Estoque e Prazo](docs/prd/prd-006-estoque-e-prazo.md)
- [PRD-007 — Propostas Comerciais](docs/prd/prd-007-propostas-comerciais.md)
- [PRD-008 — Pedidos e Confirmação](docs/prd/prd-008-pedidos-e-confirma-o.md)
- [PRD-009 — Human-in-the-Loop](docs/prd/prd-009-human-in-the-loop.md)
- [PRD-010 — Opportunity Engine](docs/prd/prd-010-opportunity-engine.md)
- [PRD-011 — Venda Ativa via WhatsApp](docs/prd/prd-011-venda-ativa-via-whatsapp.md)
- [PRD-012 — Arquitetura Multiagente](docs/prd/prd-012-arquitetura-multiagente.md)
- [PRD-013 — Observabilidade, Auditoria e Custos de IA](docs/prd/prd-013-observabilidade-auditoria-e-custos-de-ia.md)
- [PRD-014 — Segurança e Privacidade](docs/prd/prd-014-seguran-a-e-privacidade.md)
- [PRD-015 — Analytics e Revenue Intelligence](docs/prd/prd-015-analytics-e-revenue-intelligence.md)
- [PRD-016 — Escopo e Critérios da V1](docs/prd/prd-016-escopo-e-crit-rios-da-v1.md)

### SPECs
- [SPEC-001 — WhatsApp Webhook](docs/specs/spec-001-whatsapp-webhook.md)
- [SPEC-002 — Conversation Session](docs/specs/spec-002-conversation-session.md)
- [SPEC-003 — Identificação do Cliente](docs/specs/spec-003-identifica-o-do-cliente.md)
- [SPEC-004 — Lead Creation](docs/specs/spec-004-lead-creation.md)
- [SPEC-005 — Intent Classification](docs/specs/spec-005-intent-classification.md)
- [SPEC-006 — Product Search](docs/specs/spec-006-product-search.md)
- [SPEC-007 — Product Recommendation](docs/specs/spec-007-product-recommendation.md)
- [SPEC-008 — Inventory Service](docs/specs/spec-008-inventory-service.md)
- [SPEC-009 — Pricing Service](docs/specs/spec-009-pricing-service.md)
- [SPEC-010 — Pricing Guardrail](docs/specs/spec-010-pricing-guardrail.md)
- [SPEC-011 — Negotiation Agent](docs/specs/spec-011-negotiation-agent.md)
- [SPEC-012 — Human Approval](docs/specs/spec-012-human-approval.md)
- [SPEC-013 — Quote](docs/specs/spec-013-quote.md)
- [SPEC-014 — Confirmation](docs/specs/spec-014-confirmation.md)
- [SPEC-015 — Order](docs/specs/spec-015-order.md)
- [SPEC-016 — Payment Sandbox](docs/specs/spec-016-payment-sandbox.md)
- [SPEC-017 — Customer 360](docs/specs/spec-017-customer-360.md)
- [SPEC-018 — Opportunity Engine](docs/specs/spec-018-opportunity-engine.md)
- [SPEC-019 — Replenishment Rule](docs/specs/spec-019-replenishment-rule.md)
- [SPEC-020 — Quote Recovery](docs/specs/spec-020-quote-recovery.md)
- [SPEC-021 — Opportunity Entity](docs/specs/spec-021-opportunity-entity.md)
- [SPEC-022 — Outbound Contact](docs/specs/spec-022-outbound-contact.md)
- [SPEC-023 — Agent Supervisor](docs/specs/spec-023-agent-supervisor.md)
- [SPEC-024 — Allowed Agents](docs/specs/spec-024-allowed-agents.md)
- [SPEC-025 — Tool Permissions](docs/specs/spec-025-tool-permissions.md)
- [SPEC-026 — Human Handoff](docs/specs/spec-026-human-handoff.md)
- [SPEC-027 — Handoff Context](docs/specs/spec-027-handoff-context.md)
- [SPEC-028 — Audit Trail](docs/specs/spec-028-audit-trail.md)
- [SPEC-029 — Grounding](docs/specs/spec-029-grounding.md)
- [SPEC-030 — Security](docs/specs/spec-030-security.md)
- [SPEC-031 — PII](docs/specs/spec-031-pii.md)
- [SPEC-032 — Prompt Injection](docs/specs/spec-032-prompt-injection.md)
- [SPEC-033 — Idempotency](docs/specs/spec-033-idempotency.md)
- [SPEC-034 — Observability](docs/specs/spec-034-observability.md)
- [SPEC-035 — Performance](docs/specs/spec-035-performance.md)
- [SPEC-036 — Testing](docs/specs/spec-036-testing.md)
- [SPEC-037 — Technology Stack](docs/specs/spec-037-technology-stack.md)

### ADRs
- [ADR-001 — GCP como cloud principal](docs/adrs/adr-001-gcp-como-cloud-principal.md)
- [ADR-002 — Cloud Run como runtime](docs/adrs/adr-002-cloud-run-como-runtime.md)
- [ADR-003 — Monólito modular na V1](docs/adrs/adr-003-mon-lito-modular-na-v1.md)
- [ADR-004 — PostgreSQL como OLTP](docs/adrs/adr-004-postgresql-como-oltp.md)
- [ADR-005 — BigQuery como analytics](docs/adrs/adr-005-bigquery-como-analytics.md)
- [ADR-006 — Pub/Sub como event backbone](docs/adrs/adr-006-pub-sub-como-event-backbone.md)
- [ADR-007 — Arquitetura multiagente](docs/adrs/adr-007-arquitetura-multiagente.md)
- [ADR-008 — Least privilege para agentes](docs/adrs/adr-008-least-privilege-para-agentes.md)
- [ADR-009 — LLM não é System of Record](docs/adrs/adr-009-llm-n-o-system-of-record.md)
- [ADR-010 — RAG apenas para conteúdo não estruturado](docs/adrs/adr-010-rag-apenas-para-conte-do-n-o-estruturado.md)
- [ADR-011 — Pricing determinístico](docs/adrs/adr-011-pricing-determin-stico.md)
- [ADR-012 — Negotiation Agent limitado](docs/adrs/adr-012-negotiation-agent-limitado.md)
- [ADR-013 — Human-in-the-Loop](docs/adrs/adr-013-human-in-the-loop.md)
- [ADR-014 — Separar AI Decision de Business Decision](docs/adrs/adr-014-separar-ai-decision-de-business-decision.md)
- [ADR-015 — WhatsApp como primeiro canal](docs/adrs/adr-015-whatsapp-como-primeiro-canal.md)
- [ADR-016 — Core independente do WhatsApp](docs/adrs/adr-016-core-independente-do-whatsapp.md)
- [ADR-017 — Lead scoring por regras](docs/adrs/adr-017-lead-scoring-por-regras.md)
- [ADR-018 — ML após histórico suficiente](docs/adrs/adr-018-ml-ap-s-hist-rico-suficiente.md)
- [ADR-019 — Opportunity Engine separado do Sales Agent](docs/adrs/adr-019-opportunity-engine-separado-do-sales-agent.md)
- [ADR-020 — Outbound exige Policy Gate](docs/adrs/adr-020-outbound-exige-policy-gate.md)
- [ADR-021 — Idempotência obrigatória](docs/adrs/adr-021-idempot-ncia-obrigat-ria.md)
- [ADR-022 — Observabilidade completa dos agentes](docs/adrs/adr-022-observabilidade-completa-dos-agentes.md)
- [ADR-023 — AI Cost como KPI de negócio](docs/adrs/adr-023-ai-cost-como-kpi-de-neg-cio.md)
- [ADR-024 — Prompt injection não altera regras](docs/adrs/adr-024-prompt-injection-n-o-altera-regras.md)
- [ADR-025 — Tools financeiras determinísticas](docs/adrs/adr-025-tools-financeiras-determin-sticas.md)
- [ADR-026 — Databricks Free fora do caminho crítico](docs/adrs/adr-026-databricks-free-fora-do-caminho-cr-tico.md)
- [ADR-027 — GCP como System of Record](docs/adrs/adr-027-gcp-como-system-of-record.md)
- [ADR-028 — Dados simulados primeiro](docs/adrs/adr-028-dados-simulados-primeiro.md)
- [ADR-029 — Pagamento somente sandbox](docs/adrs/adr-029-pagamento-somente-sandbox.md)
- [ADR-030 — Documento comercial simulado](docs/adrs/adr-030-documento-comercial-simulado.md)
- [ADR-031 — Security by Design](docs/adrs/adr-031-security-by-design.md)
- [ADR-032 — PII minimization](docs/adrs/adr-032-pii-minimization.md)
- [ADR-033 — Customer 360 não vai inteiro ao LLM](docs/adrs/adr-033-customer-360-n-o-vai-inteiro-ao-llm.md)
- [ADR-034 — Explicabilidade comercial](docs/adrs/adr-034-explicabilidade-comercial.md)
- [ADR-035 — Receita como principal métrica](docs/adrs/adr-035-receita-como-principal-m-trica.md)
- [ADR-036 — Autonomia proporcional ao risco](docs/adrs/adr-036-autonomia-proporcional-ao-risco.md)
- [ADR-037 — Security by Architecture for Tool Permissions](docs/adrs/adr-037-security-by-architecture-for-tool-permissions.md)
- [ADR-038 — LangGraph for Stateful Agent Orchestration](docs/adrs/adr-038-langgraph-for-stateful-agent-orchestration.md)
- [ADR-039 — Persistent Interrupt Before Irreversible Actions](docs/adrs/adr-039-persistent-interrupt-before-irreversible-actions.md)
- [ADR-040 — Observability From First Functional Slice](docs/adrs/adr-040-observability-from-first-functional-slice.md)
- [ADR-041 — Independent Spec Verification Ritual](docs/adrs/adr-041-independent-spec-verification-ritual.md)
- [ADR-042 — Google Cloud CLI Remote MCP for Developer Harness](docs/adrs/adr-042-google-cloud-cli-remote-mcp-for-developer-harness.md)
- [ADR-043 — Claude Code Hooks Block Destructive GCP Actions](docs/adrs/adr-043-claude-code-hooks-block-destructive-gcp-actions.md)
- [ADR-044 — Pub/Sub para processamento assíncrono do webhook, atrás de uma porta EventPublisher](docs/adrs/adr-044-pub-sub-async-webhook-with-publisher-port.md)
- [ADR-045 — Langfuse self-hosted atrás de uma porta Tracer](docs/adrs/adr-045-langfuse-self-hosted-behind-tracer-port.md)
- [ADR-046 — Docker Compose e Makefile como harness de desenvolvimento](docs/adrs/adr-046-docker-compose-and-makefile-dev-harness.md)
- [ADR-047 — Cloud Run consome o Pub/Sub por pull, com min_instances >= 1 na V1](docs/adrs/adr-047-cloud-run-consumes-pub-sub-by-pull-with-min-instance.md)
- [ADR-048 — CD via GitHub Actions + Workload Identity Federation, sem chave](docs/adrs/adr-048-github-actions-wif-keyless-cd.md)
- [ADR-049 — Vertex AI via google-genai (vertexai=True), com retry e handoff](docs/adrs/adr-049-vertex-ai-via-google-genai.md)
- [ADR-050 — Retomada da aprovação: rota interna + evento Pub/Sub + Command(resume)](docs/adrs/adr-050-approval-resume-via-internal-route-and-event.md)
- [ADR-051 — Checkout Agent determinístico + CHECKOUT_TOOLS; confirmação determinística](docs/adrs/adr-051-checkout-agent-deterministic.md)
- [ADR-052 — Customer 360: identidade determinística por telefone + visão comercial limitada tool-gated](docs/adrs/adr-052-customer-360-identity-and-bounded-view.md)
- [ADR-053 — Opportunity Engine determinístico: scan em batch + regras puras + entidade](docs/adrs/adr-053-opportunity-engine-deterministic-batch.md)
- [ADR-054 — Human Handoff: gatilhos determinísticos + entidade + contexto estruturado](docs/adrs/adr-054-human-handoff-deterministic-triggers-and-context.md)
- [ADR-055 — Audit Trail: AuditTracer envolve o sink + uma linha por turno via flush()](docs/adrs/adr-055-audit-trail-tracer-sink-wrapper.md)
- [ADR-056 — OBSERVABILITY_OPS: OTel → Cloud Trace de produção + métricas via log-based metrics](docs/adrs/adr-056-observability-ops-otel-cloud-trace-and-log-metrics.md)
- [ADR-057 — Orçamento de latência: timeout por dependência + teto duro no turno](docs/adrs/adr-057-latency-budget-per-dependency-timeout-and-turn-cap.md)
- [ADR-058 — HARDENING_SECURITY_PII: security-by-architecture + mask() += CPF + suíte tests/security/](docs/adrs/adr-058-security-pii-hardening-pass.md)
- [ADR-059 — ACTIVE_SALES: Policy Gate de contato ativo + job batch + guard de opt-out](docs/adrs/adr-059-active-sales-outbound-policy-gate.md)
- [ADR-060 — LANDING_PAGE: hosting estático GCS + Cloud CDN, sem domínio/HTTPS na V1](docs/adrs/adr-060-landing-page-gcs-cdn.md)
- [ADR-061 — ANALYTICS: sync batch Postgres → BigQuery, domínio Revenue + Custo de IA](docs/adrs/adr-061-analytics-bigquery-revenue-cost.md)
- [ADR-062 — LEAD_LIFECYCLE: transições determinísticas de status + promoção lead→customer](docs/adrs/adr-062-lead-lifecycle-deterministic-transitions.md)
- [ADR-063 — ANALYTICS_360: os 4 domínios restantes do PRD-015](docs/adrs/adr-063-analytics-360-remaining-prd015-domains.md)
- [ADR-064 — Servidor MCP pessoal: leitura + operações internas já existentes, stdio](docs/adrs/adr-064-personal-mcp-server-read-and-internal-ops.md)
- [ADR-065 — Acesso de leitura ao dashboard: roles/monitoring.viewer por e-mail](docs/adrs/adr-065-dashboard-viewer-access-monitoring-viewer.md)
- [ADR-066 — CTA de WhatsApp na landing page: deep link wa.me, sem backend novo](docs/adrs/adr-066-whatsapp-cta-landing-page.md)
- [ADR-067 — MCP público de leitura: novo Cloud Run service, Streamable HTTP, bearer compartilhado](docs/adrs/adr-067-public-readonly-mcp-server.md)
- [ADR-068 — Domínio próprio da landing page: mastavista.com.br, cert gerenciado, redirect HTTP→HTTPS](docs/adrs/adr-068-custom-domain-landing-page.md)
- [ADR-069 — Bootstrap: deployer_roles estava sem Logging/Monitoring/Compute admin](docs/adrs/adr-069-bootstrap-deployer-missing-iam-roles.md)
- [ADR-070 — Segunda rodada de correções do deploy: IAM do BigQuery + pin da versão do mcp](docs/adrs/adr-070-bigquery-iam-and-mcp-version-pin.md)
- [ADR-071 — ALIGN_SUM não escalariza métrica DISTRIBUTION: métricas gêmeas pra alerta](docs/adrs/adr-071-distribution-metric-alert-sum-fix.md)
- [ADR-072 — Correção do ADR-071: value_extractor só existe pra métrica DISTRIBUTION](docs/adrs/adr-072-value-extractor-requires-distribution.md)
- [ADR-073 — Portal operacional: Google Sign-In + wrapper sobre rotas internas + painel ao vivo via Postgres LISTEN/NOTIFY](docs/adrs/adr-073-operational-portal.md)
- [ADR-074 — Subdomínios mcp./portal. via Serverless NEG no mesmo Load Balancer (ADR-068 estendido)](docs/adrs/adr-074-mcp-and-portal-subdomains.md)
- [ADR-075 — Langfuse self-hosted em produção (ADR-045 emendado)](docs/adrs/adr-075-langfuse-self-hosted-production.md)
- [ADR-076 — Cloud Scheduler encadeando os 4 jobs batch](docs/adrs/adr-076-cloud-scheduler-batch-jobs.md)
- [ADR-077 — TTL de aprovações, propostas e handoffs pendentes](docs/adrs/adr-077-expiration-ttl-sweep.md)
- [ADR-078 — Fluxo de opt-in via WhatsApp, simétrico ao guard de opt-out](docs/adrs/adr-078-whatsapp-opt-in-flow.md)
- [ADR-079 — Opportunity Engine: os 6 tipos restantes (CHURN, REACTIVATION, ORDER_RECOVERY, CROSS_SELL, UPSELL, INVENTORY_TO_CASH)](docs/adrs/adr-079-opportunity-engine-remaining-six-types.md)
