# ADR-060 — LANDING_PAGE: hosting estático GCS + Cloud CDN, sem domínio/HTTPS na V1

## Status
Accepted

## Contexto
Não existia nenhuma página pública explicando o RevenueFlow AI — nenhuma infra de hosting
estático, nenhum conteúdo de marketing/showcase no repo, nenhum PRD/SPEC dedicado (esta é a
primeira fatia do projeto sem grounding formal em PRD/SPEC; o único precedente é uma nota lateral
no ADR-058: "CSP entra com a LANDING_PAGE (GCS)"). O usuário pediu um site detalhado, cobrindo as
13 fatias entregues e o roadmap, com produção visual de alto padrão, hospedado em GCS + Cloud CDN
— sem domínio próprio disponível ainda.

## Decisão

- **GCS + Cloud CDN atrás de um Load Balancer HTTP global, sem domínio/HTTPS nesta fatia (DA1).**
  `google_storage_bucket` público (`uniform_bucket_level_access`, `website{}`) atrás de um
  `google_compute_backend_bucket` (`enable_cdn = true`), servido por um LB HTTP global (IP
  estático reservado via `google_compute_global_address`). Um certificado gerenciado do Google
  exige domínio validado — inexistente hoje. A URL pública é `http://<IP estático>/`. Quando um
  domínio existir, o upgrade é aditivo (cert + proxy HTTPS apontando pro mesmo backend) — nada do
  criado agora precisa ser recriado.
- **Deploy de conteúdo via `gsutil rsync` no CD existente, não via `google_storage_bucket_object`
  (DA2).** `landing_page.tf` cria só a infraestrutura; `site/**` é sincronizado por
  `gsutil -m rsync -r -d` num passo do job `deploy` de `terraform.yml`, depois do
  `terraform apply`, com invalidação de cache CDN em seguida. Editar HTML/CSS é um commit normal,
  sem `plan`/`apply` de infraestrutura.
- **1 página com navegação por âncora; as 13 fatias agrupadas em 6 fases coerentes (DA3).**
  `site/index.html` — hero, 6 seções de fase (Atendimento & IA; Negociação & Aprovação; Pedido &
  Pagamento; Inteligência de Cliente; Governança & Operação; Venda Ativa), arquitetura em alto
  nível, roadmap. Sem multi-página, sem framework, sem build step — HTML/CSS puro.
- **CSP via `<meta http-equiv>`, não via servidor (DA4).** GCS + backend bucket não roda um app
  server próprio; a fatia cumpre a intenção do ADR-058 com uma meta tag CSP
  (`default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none';
  frame-ancestors 'none'`), sem script algum no site.

## Fora de escopo (decisões explícitas de **não** fazer na V1)

- **Domínio custom + certificado HTTPS gerenciado** — sem domínio disponível; follow-up aditivo
  quando o usuário tiver um (a arquitetura de LB já deixa o caminho pronto).
- **Formulário de contato / captura de lead com backend** — sem e-mail de destino/domínio
  definido; um formulário sem processamento real seria fachada.
- **Analytics / tracking (GA, Plausible, etc.)** — sem domínio, sem política de cookie definida;
  não pedido pelo usuário.
- **Multi-página / roteamento** — 1 página com âncoras cobre o pedido de "máximo de detalhe" sem
  complexidade de roteamento.
- **Build step (React/Vite/Next/qualquer bundler)** — o monorepo é Python; HTML/CSS puro evita
  Node como dependência nova do CI.
- **CMS / conteúdo editável sem novo deploy** — o site versionado no repo é a fonte de verdade;
  editar é um commit, como o resto do projeto.
- **i18n (PT/EN)** — o resto do repo (docs, ADRs, mensagens do produto) é PT-BR.
- **Testemunhais / cases de cliente reais** — não há cliente real ainda (ADR-028, dados
  simulados).
- **Página de preço / self-serve signup** — não é um SaaS com onboarding próprio; é um showcase
  de engenharia/produto.

## Alternativas consideradas

- **Bucket público direto, sem LB/CDN** — menos recursos Terraform, mas sem cache de borda e sem
  caminho reaproveitável para domínio custom depois (o LB teria que ser criado do zero).
- **`google_storage_bucket_object` por arquivo** — acoplaria conteúdo a infraestrutura; qualquer
  edição de copy viraria uma mudança de `plan`/`apply` de Terraform, com ruído desnecessário.
- **Cloud Run/Cloud Function só para injetar headers HTTP customizados** — reintroduz um servidor
  de aplicação para uma página 100% estática; contradiz o motivo de usar GCS+CDN.
- **Publicar como Artifact (claude.ai) em vez de infra própria** — não atende ao pedido explícito
  de GCS+CDN; não aparece no repo/domínio do próprio projeto.
- **Esperar o domínio existir para fazer a fatia inteira** — o usuário pediu para seguir agora.

## Motivo
O usuário quer um showcase técnico-comercial detalhado das 13 fatias entregues, hospedado em
infraestrutura própria (GCS+CDN), sem esperar por um domínio que ainda não existe. A arquitetura
escolhida entrega performance e uma URL estável hoje, sem fechar a porta para domínio+HTTPS
depois — e mantém o site 100% desacoplado do monólito Python (ADR-003), sem dependência nova de
runtime nem impacto em `pytest`/`mypy`.

## Consequências
- +7 recursos Terraform (`landing_page.tf`); +1 API habilitada (`storage.googleapis.com`); +3
  outputs; +1 passo no job `deploy` do CD; +`site/**` nos path filters do workflow; +ADR-060.
- Navegador mostra "não seguro" (HTTP puro, sem HTTPS) — aceito porque o site não coleta nenhum
  dado (sem formulário, sem cookie, sem analytics).
- `<meta http-equiv="Content-Security-Policy">` não cobre todas as diretivas que um header HTTP
  real cobriria (`frame-ancestors` é ignorado via meta por alguns navegadores) — limitação
  conhecida de site 100% estático sem servidor de aplicação, aceita nesta V1.
- Custo marginal baixo: Storage + egress de um bucket pequeno + Cloud CDN sob tráfego incerto;
  sem chamada LLM, sem Cloud SQL/Pub/Sub envolvidos.
- Uma regressão que reintroduza `google_storage_bucket_object` por arquivo, ou que remova a meta
  tag CSP, deveria ser pega em revisão manual (sem teste automatizado de conteúdo nesta V1).

## Regra de revisão
Mudanças nesta decisão — em especial adicionar domínio/HTTPS, um formulário com coleta de dado,
ou trocar o mecanismo de deploy de conteúdo — exigem novo ADR ou superseding ADR.
