# ADR-068 — Domínio próprio da landing page: mastavista.com.br, cert gerenciado, redirect HTTP→HTTPS

## Status
Accepted

## Contexto
ADR-060 hospedou a landing page atrás de um Load Balancer HTTP global (GCS + Cloud CDN), sem
domínio próprio nem HTTPS, deixando explícito que "adicionar depois é aditivo (um cert gerenciado +
um proxy HTTPS apontando pro mesmo backend), nada aqui precisa ser recriado". O usuário forneceu o
domínio `mastavista.com.br` e pediu pra configurá-lo.

## Decisão

- **`google_compute_managed_ssl_certificate`** escopado só a `mastavista.com.br` (sem `www.` —
  pedido literal do usuário foi só o domínio único; adicionar `www` depois é aditivo, mas exigiria
  um segundo registro DNS que ninguém confirmou ainda).
- **Novo `google_compute_target_https_proxy`** usando esse cert, mesmo `url_map` de conteúdo
  (`google_compute_url_map.landing`, o mesmo backend bucket + CDN do ADR-060) — nenhum recurso do
  ADR-060 foi recriado, exatamente como aquele ADR previu.
- **Novo `google_compute_global_forwarding_rule` na porta 443**, mesmo IP estático já existente
  (`google_compute_global_address.landing`) — o domínio aponta pro mesmo IP de sempre, só ganha uma
  porta nova.
- **HTTP passa a redirecionar pra HTTPS** — um `google_compute_url_map` novo
  (`landing_redirect`, só `default_url_redirect { https_redirect = true }`) e o
  `google_compute_target_http_proxy` existente passa a apontar pra ele em vez do mapa de conteúdo,
  condicionado a `var.landing_domain != ""`. Sem domínio configurado, o comportamento HTTP-only do
  ADR-060 continua idêntico.
- **`var.landing_domain` (default `"mastavista.com.br"`), vazio desliga tudo.** Todo recurso novo
  usa `count = var.landing_domain != "" ? 1 : 0` — outro clone deste repo, ou um ambiente de teste,
  não herda o domínio de produção sem decidir isso explicitamente (o default aqui é o valor real
  porque o usuário forneceu; um fork trocaria isso no próprio `tfvars`).
- **DNS fica fora do Terraform.** O domínio `.com.br` não está gerenciado por Cloud DNS neste
  projeto — apontar o registro A pra `output landing_page_ip` é um passo manual no provedor de DNS
  do usuário (Registro.br ou onde o domínio estiver registrado), mesmo padrão de outros passos
  operacionais já documentados (secrets do WhatsApp, `dashboard_viewer_emails`). O cert gerenciado
  fica em `PROVISIONING` até esse DNS resolver — `terraform apply` não falha por causa disso.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- `www.mastavista.com.br` — não foi pedido; adicionar é uma linha a mais em `domains = [...]` no
  cert gerenciado, quando/se o usuário quiser.
- Cloud DNS gerenciando o domínio — o registro em si (Registro.br ou outro provedor) continua sendo
  a fonte de verdade do DNS; migrar pra Cloud DNS é uma decisão separada, não pedida.
- HSTS / `Strict-Transport-Security` na landing page — a página já não tem servidor de app próprio
  (ADR-060); esse header viria do Load Balancer (`google_compute_url_map` header policy), fora do
  escopo desta fatia específica de domínio.

## Alternativas consideradas

- **Recriar o Load Balancer do zero com HTTPS desde o início** — desnecessário; ADR-060 já deixou
  o design pronto pra extensão aditiva, e é exatamente isso que esta fatia faz.
- **Cloud DNS gerenciando o domínio** — exigiria migrar os nameservers do domínio no registrador
  (Registro.br), um passo que ninguém pediu; apontar só o registro A no provedor atual é
  suficiente e reversível.
- **HTTP continuar servindo o conteúdo direto (sem redirect)** — deixaria a página acessível sem
  TLS mesmo com o domínio configurado; redirecionar é o padrão esperado quando um cert existe.

## Motivo
O usuário forneceu o domínio e pediu a configuração — o caminho aditivo já estava desenhado desde
o ADR-060. A única decisão real aqui foi documentar precisamente o escopo (só o domínio pedido,
sem `www`) e deixar o DNS como passo manual, coerente com todo outro dado externo (WhatsApp,
e-mails de viewer) que este projeto já trata como pendência operacional, não como algo pra
Terraform inventar.

## Consequências
- +4 recursos condicionais em `landing_page.tf` (cert, proxy HTTPS, forwarding rule HTTPS, url_map
  de redirect) + 1 modificação (o proxy HTTP existente aponta condicionalmente pro redirect);
  +1 variável (`landing_domain`); +3 outputs (`landing_page_domain`, `landing_page_cert_check`,
  descrição atualizada de `landing_page_ip`); +ADR-068.
- Pendência operacional nova: apontar o registro A de `mastavista.com.br` pro IP de
  `landing_page_ip` no provedor de DNS do usuário, e confirmar `ACTIVE` via
  `landing_page_cert_check` antes de anunciar o domínio publicamente.
- Uma regressão que remova a condicional `var.landing_domain != ""` forçaria o domínio em qualquer
  ambiente que reusar este Terraform — pegar isso em revisão de código.

## Regra de revisão
Mudanças nesta decisão — em especial trocar o domínio, migrar pra Cloud DNS, ou remover a
condicional que permite desligar tudo com `landing_domain = ""` — exigem novo ADR ou superseding
ADR.
