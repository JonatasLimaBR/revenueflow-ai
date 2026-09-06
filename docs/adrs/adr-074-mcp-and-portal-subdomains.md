# ADR-074 — Subdomínios `mcp.`/`portal.` via Serverless NEG no mesmo Load Balancer (ADR-068 estendido)

## Status
Accepted

## Contexto
ADR-068 deu domínio próprio + HTTPS pra landing page (`mastavista.com.br`). Os outros 2 serviços
públicos (`revenueflow-api-mcp-readonly`, ADR-067; `revenueflow-api-portal`, ADR-073) só respondem
em URLs `*.run.app`. Usuário pediu explicitamente `mcp.mastavista.com.br` e
`portal.mastavista.com.br`.

## Decisão

- **Reaproveitar o Load Balancer/IP/certificado já existentes** (ADR-068) via roteamento por
  hostname, em vez de um LB/IP/cert dedicado por serviço:
  - Um `google_compute_region_network_endpoint_group` (`SERVERLESS`, `cloud_run.service` = o
    serviço alvo) + `google_compute_backend_service` por serviço (`mcp_readonly`, `portal`) —
    padrão oficial do GCP pra expor Cloud Run atrás de um HTTP(S) Load Balancer.
  - `host_rule`/`path_matcher` novos no `google_compute_url_map.landing` já existente —
    `default_service` (o bucket da landing page) fica inalterado pro domínio raiz.
  - `google_compute_managed_ssl_certificate.landing.domains` ganha os 2 subdomínios
    (`compact([var.landing_domain, local.mcp_subdomain, local.portal_subdomain])`) — mesmo
    certificado, mais domínios, não um novo por subdomínio.
- **Certificado é recriado** — `domains` é campo imutável no GCP; usuário confirmou explicitamente
  aceitar a janela de reprovisionamento (o domínio raiz nem tinha HTTPS ativo ainda quando isso foi
  decidido, então o momento de menor risco).
- **Tudo condicionado a `var.landing_domain != ""`** — mesmo guard do ADR-068; nenhum recurso novo
  se o domínio não estiver configurado.
- **DNS fica fora do Terraform** — 2 registros A novos (mesmo IP de `landing_page_ip`), passo
  manual do usuário, mesmo padrão do domínio raiz.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Load Balancer/IP dedicado por serviço — custo e complexidade maiores sem benefício sobre
  host-based routing num LB só.
- Certificado separado por subdomínio — um único gerenciado, multi-domínio, é suficiente e mais
  simples de operar.
- Cloud Run "domain mapping" nativo — não compõe com o Load Balancer/Cloud CDN já existente.

## Alternativas consideradas

- **`gcloud run domain-mappings create`** — mecanismo nativo do Cloud Run pra domínio custom, mas
  não gerenciável de forma limpa via Terraform neste provider, e cria um caminho de tráfego
  paralelo ao Load Balancer já existente (perderia Cloud CDN/host-based routing unificado).
- **Um Load Balancer por serviço** — rejeitada sem análise formal: seria 2 IPs globais + 2
  certificados novos, custo fixo de LB duplicado, sem nenhum ganho sobre roteamento por hostname.

## Motivo
Host-based routing num Load Balancer que já existe é o padrão de menor custo/complexidade quando
múltiplos serviços precisam de domínio próprio sob o mesmo domínio raiz — reaproveita 100% da
infra do ADR-068 (IP, LB, certificado) em vez de duplicá-la.

## Consequências
- +1 arquivo (`subdomains.tf`: 2 NEGs + 2 backend services); `landing_page.tf` modificado (4
  `dynamic` blocks no url_map + `domains` do cert); `outputs.tf` += `mcp_domain_url`/
  `portal_domain_url`; +ADR-074.
- Certificado gerenciado recriado no próximo `apply` — janela de `PROVISIONING` até reemitir,
  confirmada e aceita pelo usuário antes da implementação.
- Pendência operacional nova: 2 registros DNS A (`mcp.mastavista.com.br`,
  `portal.mastavista.com.br`) → mesmo IP de `landing_page_ip`.
- Um teste pré-existente (`test_managed_cert_scoped_to_landing_domain_only`) foi atualizado pra
  refletir que o certificado agora cobre 3 domínios, não 1 — mudança de comportamento esperada,
  não regressão.

## Regra de revisão
Mudanças nesta decisão — em especial criar um Load Balancer/IP dedicado por serviço, ou remover a
condicional que permite desligar tudo com `landing_domain = ""` — exigem novo ADR ou superseding
ADR.
