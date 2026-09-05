# ADR-073 — Portal operacional: Google Sign-In + wrapper sobre rotas internas + painel ao vivo via Postgres LISTEN/NOTIFY

## Status
Accepted

## Contexto
Toda a infraestrutura de dados operacionais (audit trail turno a turno, analytics, dashboard do
Cloud Monitoring, aprovações/handoffs) já existe e está no ar, mas não há nenhuma aplicação web
própria — só páginas do Console GCP gateadas por IAM de projeto. O usuário pediu explicitamente uma
página própria: transações, observabilidade, e o trabalho de cada agente turno a turno, incluindo
o momento real em que cada agente está executando, com ação (aprovar/resolver) direto da tela, para
ele e sua equipe.

## Decisão

- **Novo serviço Cloud Run `revenueflow-api-portal`** (FastAPI + Jinja2 server-rendered, sem
  SPA/bundler JS), mesma imagem da API, `command` diferente — mesmo padrão de
  `revenueflow-api-mcp-readonly` (ADR-067).
- **Leitura**: direto de `repositories.analytics`/`repositories.audit`/`repositories.portal` (mesma
  pool de conexão da API) — nenhuma lógica de negócio nova.
- **Ação (aprovar/rejeitar/resolver)**: via `httpx` contra as MESMAS rotas
  `/internal/approvals`/`/internal/handoffs` que o MCP pessoal já usa (ADR-064) — o portal
  **nunca** escreve direto nas tabelas de estado (`approval`/`handoff`/`quote`/etc.), reforçando o
  invariante do ADR-037 (nenhuma segunda aplicação escreve direto).
- **Autenticação**: Google Sign-In client-side (token JWT, sem client secret, sem fluxo OAuth
  redirect completo) verificado server-side (`google-auth`, import lazy) contra
  `PORTAL_VIEWER_EMAILS` — que **reaproveita** `var.dashboard_viewer_emails` (ADR-065, mesma lista,
  não duplicada) — mais um cookie de sessão assinado HMAC (stdlib, TTL de 12h).
- **Painel de agentes ao vivo**: `AuditTracer.span()` (`observability/tracer.py`) — o único ponto
  que já intercepta toda chamada `span("node.*")` de qualquer nó do grafo, sem tocar os 9 arquivos
  de agente — ganha um `NOTIFY` Postgres best-effort (`observability/live.py`,
  `pg_notify(channel, payload)`, fire-and-forget via `asyncio.create_task`, nunca propaga exceção
  pro turno real). O portal expõe `GET /portal/live/stream` (Server-Sent Events, `EventSource`
  nativo do browser) que faz `LISTEN` na mesma pool e transmite cada evento.
- **`min_instance_count = 1`** (não 0, diferente de todo outro serviço deste projeto) — o painel ao
  vivo perderia eventos enquanto o Cloud Run dorme (scale-to-zero fecharia a conexão `LISTEN`).

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- **Identity-Aware Proxy (IAP)** — exigiria criar um "IAP brand" no projeto, um recurso
  irreversível do GCP; risco desnecessário depois de 4 rodadas de bugs de infra nesta mesma sessão
  (ADR-069→072, todos nos alertas do Cloud Monitoring). Google Sign-In client-side dá o mesmo
  resultado (login por conta Google, allowlist por e-mail) sem esse risco.
- **WebSocket completo** — SSE (unidirecional, servidor→browser) cobre o caso; o portal nunca
  precisa mandar dado de volta pelo mesmo canal.
- **RBAC/permissões granulares** — a allowlist é binária: quem está em
  `dashboard_viewer_emails` vê e age em tudo; sem papéis/escopos por usuário na V1.
- **Broker de mensagens novo** (Redis/Pub-Sub dedicado) — Postgres `LISTEN`/`NOTIFY` já é
  suficiente pro volume desta V1 e não introduz infraestrutura nova.
- **Exportar dado em massa** além do JSON de auditoria de uma conversa por vez.

## Alternativas consideradas

- **Portal com lógica própria, escrevendo direto no Postgres** (em vez de chamar as rotas
  internas) — rejeitada: duplicaria a máquina de estados de aprovação/handoff já testada e
  violaria o padrão ADR-037 que toda superfície de ação deste projeto já segue.
- **Instrumentar o painel ao vivo em cada `*_node`** (9 arquivos) em vez de em
  `AuditTracer.span()` — rejeitada: tocaria a lógica de decisão dos agentes por uma preocupação de
  observabilidade, e exigiria 9 pontos de mudança em vez de 1.

## Motivo
O portal reaproveita 100% do que já existe (dados, rotas de ação, allowlist do dashboard) — a única
peça genuinamente nova é o transporte em tempo real entre os dois processos Cloud Run (worker da
API e o portal), e Postgres `LISTEN`/`NOTIFY` resolve isso sem infraestrutura adicional, com o
menor número de arquivos tocados no caminho crítico do grafo (zero — só o wrapper do tracer).

## Consequências
- `min_instance_count=1` no `revenueflow-api-portal` — custo pequeno mas real, aceito
  explicitamente pelo usuário como trade-off do painel ao vivo.
- `AuditTracer.span()` ganha uma dependência leve em `observability/live.py`; o `NOTIFY` é
  disparado de dentro de um context manager síncrono via `asyncio.create_task` — só é seguro porque
  toda chamada a `span()` já acontece dentro de uma função `async def` de nó (loop sempre presente).
- Uma conexão do pool fica presa por navegador conectado ao painel ao vivo (LISTEN) enquanto a aba
  está aberta — aceitável pro público pequeno desta V1 (equipe), documentado como limitação.
- `PORTAL_GOOGLE_CLIENT_ID` fica pendente de criação manual no Google Cloud Console (tipo "Web
  application", origem JavaScript autorizada = URL do portal) — mesmo padrão dos secrets manuais do
  WhatsApp.

## Regra de revisão
Mudanças nesta decisão — em especial trocar Google Sign-In por IAP, permitir que o portal escreva
direto numa tabela de estado, ou remover o `min_instance_count=1` sem substituir o painel ao vivo
por outro mecanismo — exigem novo ADR ou superseding ADR.
