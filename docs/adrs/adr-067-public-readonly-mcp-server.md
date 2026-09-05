# ADR-067 — MCP público de leitura: novo Cloud Run service, Streamable HTTP, bearer compartilhado

## Status
Accepted

## Contexto
ADR-064 decidiu explicitamente **não** ter "servidor MCP hospedado/multi-tenant". O usuário pediu
essa capacidade agora — outras pessoas precisam acessar o sistema **só para visualização**, sem
instalar nada localmente. Isso emenda o "fora de escopo" do ADR-064 apenas para o caso de leitura;
as 5 tools de ação (`decide_approval`/`resolve_handoff`/etc.) continuam só no servidor pessoal
stdio, sem exceção.

## Decisão

- **Novo serviço Cloud Run** (`revenueflow-mcp-readonly`), não uma rota dentro da API principal.
  Reaproveita a mesma imagem de container (`var.image`) com `command` diferente — mesmo padrão já
  usado pelos Jobs batch (`analytics-sync`, `campaign-run`, etc.), sem build de imagem nova.
- **Transporte Streamable HTTP** (`mcp.server.fastmcp.FastMCP.streamable_http_app()`), não stdio.
  É o transporte remoto padrão do protocolo MCP hoje; extra `mcp` sobe de `>=1.2` pra `>=1.9`
  (versão mínima com esse método).
- **Só as 6 tools de leitura.** `src/revenueflow/mcp/server.py` foi dividido em
  `register_read_tools`/`register_action_tools` — o servidor pessoal (stdio) chama os dois; o
  servidor público (`http_server.py`) chama só `register_read_tools`. Nenhuma tool de ação
  (aprovar desconto, resolver handoff) existe nesse processo.
- **Mesmo modelo de confiança das rotas `/internal/*` já em produção**: serviço com ingress público
  (`allUsers` invoker no Cloud Run), gate real é um bearer token compartilhado
  (`MCP_API_TOKEN`, Terraform-generated, mesmo padrão de `APPROVAL_API_TOKEN`/`HANDOFF_API_TOKEN`).
  Não há identidade por pessoa — quem tem o token vê os dados; aceitável porque o escopo é só
  leitura (revenue, customer 360, lead funnel, opportunities, handoff rate), não uma ação que move
  dinheiro.
- **`mcp/auth.py` — o bearer check é ASGI puro, sem depender do pacote `mcp`.** `bearer_gate(app,
  token)` envolve o app do FastMCP; passa `lifespan` (start/stop do gerenciador de sessão do MCP)
  sempre adiante, sem checar — só requisições `http` reais são barradas. Isso deixa a lógica de
  autenticação testável na suíte padrão, sem o extra `mcp` instalado (mesma decisão do ADR-064 pra
  `mcp/tools.py`).
- **Escala a zero** (`min_instance_count = 0`) — ferramenta de baixo tráfego, sem o requisito de
  `min_instances >= 1` do ADR-047 (esse requisito é específico do consumer Pub/Sub da API
  principal; este serviço não consome fila nenhuma).
- **Reaproveita a service account de runtime** (`google_service_account.api`) — já tem acesso a
  `DATABASE_URL` e (via `for_each` sobre `manual_secrets`) automaticamente ganha acesso a
  `MCP_API_TOKEN` assim que o secret é adicionado ao mapa, sem binding de IAM novo.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Autenticação por pessoa (OAuth, IAM do Google) — avaliada e descartada nesta rodada porque o
  cliente MCP do usuário final (Claude Desktop, etc.) não tem suporte maduro/uniforme pra token
  assinado do Google por requisição; bearer compartilhado é o padrão que a própria API já usa.
- Qualquer tool de ação no servidor público — `register_action_tools` nunca é chamado em
  `http_server.py`; se isso mudar, é uma decisão que precisa de um novo ADR.
- Rate limiting / cache no servidor público — mesmo argumento do ADR-064 (uso de baixo volume),
  reavaliar se o tráfego justificar.
- Rotação automática do `MCP_API_TOKEN` — mesmo modelo manual dos tokens de approval/handoff já em
  produção (`gcloud secrets versions add`).

## Alternativas consideradas

- **Montar o endpoint MCP dentro do serviço `revenueflow-api` existente** (rota `/mcp` no mesmo
  FastAPI) — misturaria o roteamento ASGI do MCP com o app voltado ao cliente final, e exigiria
  `mcp` como dependência inevitável do processo principal mesmo pra quem nunca usa a feature;
  separar em serviço próprio isola o blast radius (um bug no wiring do MCP não pode derrubar o
  webhook do WhatsApp) e reflete o padrão já usado pra Jobs batch.
- **IAM do Google por e-mail (mesmo padrão do ADR-065/DASHBOARD_ACCESS)** — dá identidade real por
  pessoa, mas exige que cada cliente MCP saiba enviar um token de identidade assinado pelo Google a
  cada requisição; fricção de configuração maior pra "outras pessoas" que só querem visualizar.
- **SSE (transporte MCP mais antigo)** em vez de Streamable HTTP — Streamable HTTP é o transporte
  remoto atual recomendado pelo protocolo; não há razão pra adotar o mais antigo numa fatia nova.

## Motivo
O usuário confirmou explicitamente: acesso online, só visualização, pra outras pessoas. O padrão
`allUsers` + bearer compartilhado já é o modelo de confiança comprovado em produção pras 3 rotas
`/internal/*` — reaproveitar isso é a menor mudança que entrega o pedido, sem inventar um esquema
de autenticação novo nem abrir uma tool de escrita pra fora do ambiente pessoal do usuário.

## Consequências
- +1 serviço Cloud Run (`mcp_service.tf`, 2 recursos); +1 secret Terraform-generated
  (`MCP_API_TOKEN`); +1 output (`mcp_readonly_url`); `Dockerfile` ganha o extra `mcp` (deixa de ser
  só do ambiente pessoal do usuário — agora é dependência de produção); +2 módulos
  (`mcp/auth.py` testável, `mcp/http_server.py` não-testável — mesmo padrão de `server.py`);
  `mcp/server.py` refatorado em `register_read_tools`/`register_action_tools` (comportamento do
  servidor stdio pessoal não muda, só a estrutura interna); +ADR-067.
- Qualquer pessoa com o `MCP_API_TOKEN` vê revenue, customer 360, lead funnel e opportunities de
  todos os clientes — é dado comercial sensível, não PII de cliente final (sem telefone/nome nas
  respostas dessas 6 tools, mesma garantia do ADR-061/063), mas ainda assim informação de negócio;
  o token deve ser tratado como segredo (nunca commitado, rotação manual se vazar).
- Uma regressão que registre uma tool de ação em `http_server.py`, ou que troque o `allUsers`
  invoker por algo mais permissivo sem token, deveria ser pega em revisão de código.

## Regra de revisão
Mudanças nesta decisão — em especial adicionar uma tool de ação ao servidor público, trocar o
bearer compartilhado por identidade por pessoa, ou remover o gate de autenticação — exigem novo
ADR ou superseding ADR.
