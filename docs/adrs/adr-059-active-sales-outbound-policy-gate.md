# ADR-059 — ACTIVE_SALES: Policy Gate de contato ativo + job batch + guard de opt-out

## Status
Accepted

## Contexto
O Opportunity Engine (ADR-053) detecta e persiste `opportunity(OPEN)`, mas nada as consome — o
RevenueFlow não tem nenhum contato de iniciativa própria. PRD-011 pede o fluxo
`Opportunity → Policy Gate → Consent Check → Frequency Cap → Campaign Candidate → WhatsApp`
(SPEC-022), e ADR-020 exige que contato ativo passe por consentimento, frequência e política.

Não existia nenhum conceito de consentimento no domínio: `Customer` não tinha campo de
opt-in/opt-out. Implementar contato ativo sem isso, mesmo "temporariamente", seria um Policy Gate
placeholder — o risco que o próprio ADR-020 existe para evitar.

## Decisão

- **Consentimento é opt-in explícito, opt-out sempre vence (DA1).** `Customer` ganha
  `consent_opt_in_at`/`consent_opt_out_at` (carimbos, não booleanos — auditáveis). Sem
  `consent_opt_in_at`, o cliente é bloqueado por padrão, mesmo com histórico de compra.
  `policies/outbound_policy.py::evaluate(*, has_opt_in, has_opt_out, last_contact_at, now,
  frequency_cap_days) -> CampaignDecision` é pura, com precedência fixa: opt-out > sem opt-in >
  frequência > permitido.
- **`outbound_contact` é log append-only; a idempotência do envio vem do `dispatch` existente,
  não de um índice na tabela (DA2).** Cada `record()` insere uma linha (inclusive `SKIPPED`
  repetido no mesmo dia — é medição, não efeito colateral). O que **não pode** repetir é o envio
  real: `dispatch_key = f"campaign:{opportunity_id}:{date}"` via `repositories.dispatch` (mesmo
  contrato do `_send_once` do inbound) — se já reservado hoje, o candidato é pulado sem gravar
  nada novo.
- **Nenhuma transação cobre a chamada `ChannelOutbound.send` (DA3).** `services/campaign.py::run()`
  faz até 1 chamada HTTP por candidato permitido; cada operação de banco (`get_by_id`,
  `last_contact_at`, `dispatch.reserve`, `record`) abre sua própria `unit_of_work` curta, molde de
  `worker.consume._send_once` — nenhuma conexão do pool fica presa durante retry/backoff de rede.
- **Guard de opt-out puro, keyword em `policies/`, sem `SessionStatus` novo (DA4).**
  `policies/outbound_policy.py::is_opt_out(text)` — `_normalize` (NFKD casefold, mesmo padrão de
  `services.checkout._normalize`) + igualdade **exata** (não substring) contra
  `{"parar", "sair", "cancelar", "descadastrar"}`. Roda em `worker/consume.py::process_event`,
  depois de `resolve(phone)` (precisa de `customer_id`), antes do `graph.ainvoke`. Sem
  `customer_id` resolvido → responde fixo, nada a persistir. Opt-out é atributo do `Customer`, não
  estado de sessão — sem `SessionStatus` novo, ao contrário do guard `HUMAN_HANDOFF`.
- **Mensagem de 1º contato é template determinístico por `OpportunityType`, sem LLM (DA5).** Não
  há texto do cliente para ancorar (é o próprio disparo) e nenhum guardrail de
  `tests/security/` foi provado para "gerar contato não solicitado" — consistente com
  `checkout_node`/`handoff_node` (determinismo onde não há grounding em texto do cliente).
- **Só Cloud Run Job `revenueflow-campaign-run`, sem Cloud Scheduler (DA6).** Espelha
  `opportunity_job.tf`; roda on-demand via `gcloud run jobs execute`, depois do
  `opportunity-scan`. Cron encadeado é follow-up (mesma decisão da OPPORTUNITY_ENGINE).

## Fora de escopo (decisões explícitas de **não** fazer na V1)

- **Fluxo de opt-in por palavra-chave inbound** (simétrico ao guard de opt-out) — PRD-011 não
  define UX de opt-in; V1 usa `set_consent_opt_in` só via seed/manual. Extensão barata (mesmo
  molde do `is_opt_out`) se o PRD pedir depois.
- **WhatsApp Message Templates (HSM) aprovados pela Meta** — fora do código: registro/aprovação é
  trabalho no Meta Business Manager. Esta fatia usa `ChannelOutbound.send` (texto livre) como o
  resto do sistema; em produção real, mensagem de iniciativa da empresa fora da janela de 24h pode
  exigir template aprovado pela política do WhatsApp Business — limitação operacional conhecida,
  não uma decisão de arquitetura.
- **Mensagem gerada por LLM / personalização por histórico** — custo + superfície de risco de
  "gerar contato não solicitado" sem grounding em texto do cliente; follow-up aditivo depois que o
  Policy Gate determinístico estiver provado em produção.
- **Cloud Scheduler** — segue a decisão da OPPORTUNITY_ENGINE; on-demand primeiro.
- **Novo `OpportunityStatus`** (ex.: `CONTACTED`) — o frequency cap via `outbound_contact` já
  impede recontato indevido; `Opportunity.status` não muda nesta fatia.
- **Métricas de taxa de resposta / conversão / dashboard** (PRD-015) — esta fatia só grava o dado
  bruto; cálculo/dashboard é fatia de analytics futura.
- **Aprovação humana antes do disparo** (`interrupt()`) — ADR-020 pede Policy Gate determinístico,
  não aprovação; o Opportunity Engine também não pediu aprovação para persistir.
- **Rastreio da janela de 24h do WhatsApp Business em código** — regra operacional da Meta.
- **Cifra/retention de `outbound_contact`** — mesma postura do ADR-058; a tabela não guarda o
  corpo da mensagem, reduzindo a superfície de PII em repouso desde já.

## Alternativas consideradas

- **Opt-out implícito** ("todo cliente pode ser contatado até recusar") — inverte o ônus; WhatsApp
  Business Messaging Policy e LGPD Art. 8 pedem consentimento específico para o canal.
- **Outbound síncrono dentro do próprio `opportunity.scan()`** — reacopla "quem abordar" e "como
  abordar", violando ADR-019 na prática, mesmo sem nó de grafo.
- **Índice único em `outbound_contact` para dedup** — duplicaria a responsabilidade do `dispatch`
  já existente; perderia granularidade de `SKIPPED` para as métricas futuras.
- **Uma `unit_of_work` só para o `run()` inteiro** (como `opportunity.scan()`) — prenderia a
  conexão do pool durante N chamadas HTTP sequenciais; aceitável no `scan()` (zero I/O externo),
  não aqui.
- **Substring match para opt-out** (`keyword in texto`) — falso-positivo em frases longas que só
  mencionem a palavra sem intenção de opt-out.
- **`SessionStatus` novo para opt-out** (espelhando `HUMAN_HANDOFF`) — over-engineering; opt-out
  não muda o que a conversa faz depois.

## Motivo
ADR-020 exige Policy Gate real para contato ativo — não uma frase de ADR sem implementação. Esta
fatia constrói o consentimento (que não existia), a frequência (que não existia), e o job que os
usa, sem tocar o Opportunity Engine (ADR-019) nem introduzir LLM onde não há texto do cliente para
ancorar (ADR-009). O que fica fora (HSM, opt-in inbound, Scheduler, personalização) é registrado
aqui para não ser re-litigado a cada fatia futura.

## Consequências
- +2 colunas em `customer`; +1 tabela `outbound_contact`; +1 policy pura; +2 repositórios/funções;
  +1 serviço batch; +1 guard em `worker/consume.py`; +1 Cloud Run Job; +ADR-059.
- Nenhum cliente tem opt-in por padrão — o Job roda e não envia nada até seed/operação popular
  `consent_opt_in_at`. É o comportamento correto do opt-in explícito, não um bug.
- `outbound_contact` cresce a cada execução do Job (inclusive `SKIPPED` repetido) — sem problema
  de volume na V1; índice/partição por data é follow-up se necessário.
- Uma regressão que remova o check de opt-out, inverta a precedência da policy, ou envie sem
  `dispatch.reserve` → deveria falhar CI (a suíte de testes desta fatia cobre os 4 branches da
  policy + o guard + a idempotência do envio).

## Regra de revisão
Mudanças nesta decisão — em especial inverter a precedência opt-out/opt-in, trocar o template por
geração via LLM, ou remover o guard de opt-out — exigem novo ADR ou superseding ADR.
