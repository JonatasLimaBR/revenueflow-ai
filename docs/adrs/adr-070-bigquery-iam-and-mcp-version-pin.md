# ADR-070 — Segunda rodada de correções do deploy: IAM do BigQuery + pin da versão do `mcp`

## Status
Accepted

## Contexto
ADR-069 corrigiu o `apply` faltando `logging.admin`/`monitoring.admin`/`compute.admin` na service
account de deploy. Antes desse fix ser aplicado no bootstrap (ainda pendente — bootstrap é manual,
ADR-048), uma nova tentativa de deploy rodou e revelou **dois problemas adicionais** que só
apareceriam depois que os primeiros três fossem resolvidos:

1. `google_bigquery_dataset.analytics` (ADR-061) falhou com `403: bigquery.datasets.create` — a
   service account de deploy também nunca teve papel de BigQuery.
2. `google_cloud_run_v2_service.mcp_readonly` (ADR-067) falhou o health check de startup — os
   logs do Cloud Run mostraram o motivo real: `ModuleNotFoundError: No module named
   'mcp.server.fastmcp'`. O pacote `mcp` lançou uma versão 2.x que renomeia `FastMCP` para
   `MCPServer` e muda a API; `pyproject.toml` pedia só `mcp>=1.9` (sem teto), então o `pip install`
   em produção pegou a 2.x mais recente, que quebra `from mcp.server.fastmcp import FastMCP`
   (usado em `mcp/server.py` e `mcp/http_server.py`, ADR-064/067).

## Decisão

- **`+roles/bigquery.admin`** em `local.deployer_roles` (bootstrap) — mesmo padrão `*.admin` já
  usado pra todo outro serviço nessa lista.
- **`mcp>=1.9,<2`** em `pyproject.toml` — trava a versão pra manter a API v1 (`FastMCP`) que todo o
  código já escrito (`mcp/server.py`, `mcp/http_server.py`) usa. Migrar pra `MCPServer` da v2 é um
  follow-up deliberado, não parte desta correção — a v1 continua sendo uma escolha válida e
  suportada (o próprio erro do pacote sugere `mcp<2` como caminho pra manter o código v1
  funcionando).

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Migrar `mcp/server.py`/`mcp/http_server.py` pra API `MCPServer` da v2 — mudança de API maior,
  melhor feita como sua própria fatia depois que o v1 pinado estiver funcionando em produção.
- Testar o pacote `mcp` localmente antes de mudanças futuras — continua não instalado no ambiente
  de dev desta sessão (Windows, sem esse extra); a auditoria/produção é que revelou o problema real,
  reforçando o risco residual já documentado nos BUILD_REPORTs de ADR-064/067.

## Alternativas consideradas

- **Migrar pra `MCPServer` (v2) agora, em vez de pinar `<2`** — mais correto a longo prazo, mas
  arriscado fazer sem conseguir testar a API nova localmente; travar a versão é a correção mínima
  que desbloqueia o deploy sem reescrever código não verificado sob pressão de produção quebrada.
- **`roles/bigquery.dataOwner` em vez de `roles/bigquery.admin`** — `dataOwner` é escopado a
  datasets específicos (precisaria existir o dataset primeiro, problema de ordem circular pra
  criação); `admin` de projeto é consistente com o padrão já estabelecido pra essa SA.

## Motivo
Essas duas falhas só ficaram visíveis depois que o ADR-069 corrigiu os três primeiros gaps de IAM
e um `apply` real chegou mais longe — cada camada de erro só aparece depois que a anterior é
resolvida, típico de infraestrutura que nunca tinha rodado de ponta a ponta.

## Consequências
- +1 role em `infra/terraform/bootstrap/main.tf::local.deployer_roles`; +1 teto de versão em
  `pyproject.toml`; +ADR-070. Mesma pendência do ADR-069: exige `terraform apply` manual do
  bootstrap antes de ter efeito real.
- Depois deste fix, o próximo deploy real do CI (ou o `apply` manual da pasta raiz, se for o caso)
  deve chegar mais longe — mas pode revelar mais gaps ainda não vistos, já que esta é a primeira
  vez que o `apply` completo roda desde antes de metade das fatias entregues nesta sessão.

## Regra de revisão
Mudanças nesta decisão — em especial migrar pra `mcp>=2` sem antes reescrever `mcp/server.py`/
`mcp/http_server.py` pra API `MCPServer`, ou remover o teto de versão — exigem novo ADR ou
superseding ADR.
