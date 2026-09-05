# ADR-064 — Servidor MCP pessoal: leitura + operações internas já existentes, stdio

## Status
Accepted

## Contexto
O usuário pediu explicitamente um servidor MCP para dar acesso ao sistema. Via discovery, confirmou
o escopo (**leitura + as operações internas já existentes** — não novas capacidades de escrita) e o
consumidor (**ele mesmo, via Claude Desktop/Claude Code** — uso pessoal, não um servidor hospedado
multi-tenant). O sistema já expõe 3 rotas internas protegidas por Bearer
(`/internal/approvals`, `/internal/handoffs`, `/internal/audit/{conversation_id}`, ADR-050/054/055)
e 6 funções de leitura JSON-safe em `repositories.analytics` (ADR-061/063), mas nenhuma delas é
alcançável de um cliente MCP hoje.

## Decisão

- **Dois tipos de tool, dois transportes de dado — deliberadamente não um único caminho.** Tools de
  leitura (`get_revenue_summary`, `list_customer_360`, `get_customer_360`, `list_lead_funnel`,
  `list_opportunities`, `get_handoff_rate`) chamam `repositories.analytics` diretamente sobre uma
  conexão Postgres — mesmo padrão dos batch jobs já existentes (`opportunity.scan`,
  `analytics_sync.run`, ADR-004: Postgres é a fonte da verdade). Tools de ação
  (`list_pending_approvals`, `decide_approval`, `list_pending_handoffs`, `resolve_handoff`,
  `get_audit_trail`) chamam as rotas HTTP internas **já deployadas**, com o mesmo Bearer token que
  elas já exigem — nenhuma lógica de negócio nova, nenhum caminho de escrita privilegiado que
  contorne a API.
- **`mcp/tools.py` sem dependência do pacote `mcp`** — só `repositories.analytics` (interno) e
  `httpx` (dependência core já existente). Isso deixa toda a lógica de negócio testável pela suíte
  padrão sem o extra `mcp` instalado (mesmo shape de teste do `test_analytics_sync.py`: repositório
  mockado via `monkeypatch.setattr`; para as tools de ação, `httpx.MockTransport` — sem rede real).
  `mcp/server.py` é só o encaixe fino: decorators `@mcp.tool()` chamando `tools.py`.
- **Extra opcional `mcp`** (`pip install -e ".[mcp]"`), import lazy — nada no app principal importa
  `revenueflow.mcp.server`; só `scripts/mcp_server.py` (o entrypoint) o faz. CI nunca instala o
  extra `mcp` (mesma decisão dos extras `analytics`/`observability`/`events`) — o arquivo não é
  exercitado por testes, só por `mypy` com `ignore_missing_imports` no módulo `mcp`.
- **Transporte stdio, não HTTP/SSE.** O consumidor confirmado é o próprio usuário local (Claude
  Desktop/Claude Code) — stdio é o transporte padrão do MCP para esse caso, sem porta exposta, sem
  autenticação de transporte a desenhar.
- **Sem tool de escrita nova.** `decide_approval`/`resolve_handoff` só encaminham para as rotas
  `POST /internal/approvals/{id}` e `POST /internal/handoffs/{id}` — a mesma validação
  (`Decision` pydantic, `_auth` bearer) que já roda hoje continua sendo a única porta de entrada.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Servidor MCP hospedado/multi-tenant, transporte HTTP/SSE, ou qualquer autenticação de usuário
  externo — o usuário confirmou uso pessoal.
- Novas capacidades de escrita além do que `/internal/approvals` e `/internal/handoffs` já fazem
  (ex.: criar `Opportunity`, editar `Customer`, disparar campanha via MCP).
- Cache/rate limiting no servidor MCP — uso pessoal e local, volume irrelevante.
- Deploy do servidor MCP no Cloud Run — roda localmente, no ambiente do usuário.

## Alternativas consideradas

- **Ler diretamente as rotas `/internal/approvals`/`/internal/handoffs`/`/internal/audit` só via
  HTTP para tudo** (inclusive as leituras de analytics) — exigiria criar 6 rotas HTTP novas
  (revenue summary, customer 360, lead funnel, etc.) só para o MCP consumir, superfície de API
  pública nova sem necessidade; ler direto do Postgres (mesmo padrão dos batch jobs) é mais simples
  e não adiciona rota alguma.
- **`server.py` chamando `analytics_repo`/httpx diretamente, sem o módulo `tools.py`** — misturaria
  a dependência do pacote `mcp` com a lógica de negócio testável, forçando os testes a também
  dependerem do extra `mcp` instalado (que a CI não instala). Separar em `tools.py` mantém a lógica
  100% testável sem essa dependência.
- **`customer_repo.customer_360` para `get_customer_360`** — retorna `Decimal` (não é JSON-safe
  direto); `analytics_repo.customer_360_all` filtrado por `customer_id` já é JSON-safe (a mesma
  função que a fatia ANALYTICS_360 testou) — reaproveitar evita reimplementar serialização.

## Motivo
O usuário já confirmou escopo e consumidor via discovery; o desenho só precisava decidir *como*
alcançar leitura + as 3 operações internas já existentes sem duplicar lógica de negócio ou abrir uma
superfície de API nova. Reaproveitar as rotas HTTP já autenticadas para ação, e o padrão de conexão
direta dos batch jobs para leitura, cumpre isso com zero rota nova e zero regra de negócio
duplicada.

## Consequências
- +1 pacote `src/revenueflow/mcp/` (`tools.py` testável sem o extra; `server.py` só com ele);
  +1 script `scripts/mcp_server.py`; +1 extra opcional `mcp` em `pyproject.toml`; +1 override de
  mypy (`disallow_untyped_decorators = false` só em `revenueflow.mcp.server`, porque `mcp.tool()`
  resolve pra `Any` sem stubs); +1 setting `revenueflow_api_base_url`; +ADR-064.
- O usuário precisa configurar `DATABASE_URL` (Postgres do Cloud SQL, via proxy ou IP) e
  `REVENUEFLOW_API_BASE_URL`/`APPROVAL_API_TOKEN`/`HANDOFF_API_TOKEN` no ambiente onde roda
  `scripts/mcp_server.py` — detalhe operacional, fora do código.
- Uma regressão que faça uma tool de ação reimplementar a lógica de decisão/resolução localmente
  (em vez de chamar a rota HTTP existente) reintroduziria um caminho de escrita privilegiado
  duplicado — pegar isso em revisão de código.

## Regra de revisão
Mudanças nesta decisão — em especial adicionar uma tool de escrita nova sem rota HTTP equivalente,
mudar o transporte para HTTP/SSE, ou hospedar o servidor fora do ambiente pessoal do usuário —
exigem novo ADR ou superseding ADR.
