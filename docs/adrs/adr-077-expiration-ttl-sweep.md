# ADR-077 — TTL de aprovações, propostas e handoffs pendentes

## Status
Accepted

## Contexto
`Approval` já tem `expires_at` desde o ADR-050, mas nada o verificava proativamente — só era
checado quando alguém finalmente decidia. Achado ao vivo em produção (2026-09-09): uma `Approval`
que ninguém decidiu deixou o checkpoint do LangGraph pausado em `await_approval` **para sempre**
— toda mensagem seguinte da mesma conversa caía na resposta fixa "sua solicitação ainda está em
análise", sem nunca progredir (destravado manualmente conectando direto no Cloud SQL e limpando o
checkpoint dessa conversa). No mesmo dia, achado um segundo bug relacionado: resolver um
`Handoff` (`POST /internal/handoffs/{id}`) nunca revertia `conversation_session.status` de volta
— a sessão ficava presa em `HUMAN_HANDOFF` mesmo depois do atendente marcar o handoff como
resolvido.

## Decisão

- **`services/expiration.py::sweep()`** — job batch, fora do grafo (mesmo padrão de
  `services.opportunity.scan`/`services.lead_lifecycle.sweep_stale`, ADR-019/020). Três
  responsabilidades independentes, cada uma reaproveitando um fallback determinístico que **já
  existia**, não uma decisão de UX nova:
  - **Approval**: busca `PENDING` com `expires_at` vencido, chama `services.approval.decide(id,
    "expire", None)` — o MESMO evento `approval_decided` que a rota humana publica.
    `apply_decision_node` (agents/apply_decision.py) já se auto-detecta expirado a partir de
    `approval.expires_at`, ignorando o `decision` do payload — então só faltava alguém disparar
    esse resume. `_DECISION_STATUS` em `services/approval.py` ganha `"expire" →
    ApprovalStatus.EXPIRED` (era só `approve`/`approve_with_override`/`reject`).
  - **Quote**: `UPDATE quote SET status='EXPIRED' WHERE status='SENT' AND expiration < now()`.
    `get_open_quote` já filtra por `status='SENT'` — uma vez expirada, o próximo turno do cliente
    simplesmente não acha mais quote aberta, em vez de repetir "responda 'sim, pode fechar'"
    contra um preço vencido.
  - **Handoff**: `PENDING` mais velho que `handoff_stale_hours` (novo, default 24h) é
    auto-resolvido e a sessão volta pra `OPEN` — a mesma chamada de "não deixar o cliente preso
    pra sempre" já feita pra Approval/Quote acima, só que por ausência total de ação humana em vez
    de um prazo formal.
- **Fix separado, mesmo PR**: `services/handoff.py::resolve()` agora sempre reverte a sessão pra
  `OPEN` quando o handoff transiciona com sucesso — não só no caminho de expiração automática. Bug
  real, não parte do TTL em si; corrigido junto porque o mesmo código (`handoff_repo.resolve`)
  precisava mudar de assinatura (`int` → `str | None`, devolvendo o `conversation_id` via
  `RETURNING`) pros dois caminhos.
- **Cloud Scheduler de hora em hora** (`scheduler.tf`), não diário como os outros 4 Jobs — um
  cliente preso custa muito mais numa espera de 1h do que de 24h.
- **`0015_expiration_indexes.sql`**: índices parciais `approval (status, expires_at) WHERE
  status='PENDING'` e `quote (status, expiration) WHERE status='SENT'` — o sweep roda de hora em
  hora, então o `WHERE` do índice importa.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Notificar alguém quando um Handoff expira sem resolução humana — hoje só devolve a conversa pro
  agente automático, silenciosamente. Um alerta seria um follow-up razoável, mas é uma decisão de
  operação separada.
- TTL configurável por conversa/cliente — um valor global (`approval_ttl_hours`,
  `handoff_stale_hours`) é suficiente pro volume atual.
- Orquestração explícita de dependência entre o sweep e os outros jobs — não há nenhuma: o sweep
  não lê nem escreve nada que os outros 4 jobs também tocam.

## Alternativas consideradas

- **Verificar expiração dentro do próprio guard `_HELD_FOR_APPROVAL`** (`worker/consume.py`), sob
  demanda, na próxima mensagem do cliente — rejeitada: exigiria o cliente mandar uma nova
  mensagem pra "descobrir" que expirou, e ainda não resolveria o caso em que ninguém nunca manda
  outra mensagem (a conversa fica presa silenciosamente pro lado do negócio, mesmo sem o cliente
  notar).
- **TTL como coluna em `Handoff`** (como `Approval` já tem `expires_at`) em vez de um threshold
  fixo em `config.py` — rejeitada por simplicidade: nenhum caso de uso pedia TTL por-handoff, e
  isso evita uma migração extra.

## Motivo
Approval/Quote já tinham o fallback determinístico certo (`expires_at`/`expiration`) — faltava só
alguém disparar isso proativamente. Handoff nunca teve fallback nenhum. Os três fecham a mesma
lacuna: nada, hoje, garante que uma conversa travada esperando decisão humana eventualmente
continua sozinha.

## Consequências
- +1 arquivo (`services/expiration.py`); `services/approval.py` += entrada `"expire"`;
  `repositories/approval.py` += `list_expired_pending`; `repositories/checkout.py` +=
  `expire_stale_quotes`; `repositories/handoff.py` += `list_stale_pending`, `resolve` muda de
  assinatura; `services/handoff.py::resolve` reabre a sessão; `config.py` +=
  `handoff_stale_hours`; `scripts/sweep_expirations.py` (novo); `infra/terraform/expiration_sweep_job.tf`
  (novo) + `scheduler.tf` (+1 job, horário); `migrations/0015_expiration_indexes.sql`; +ADR-077.
- `expiration_sweep_job.tf` é o primeiro Job batch que publica um evento Pub/Sub — precisa de
  `PUBSUB_PROJECT_ID`, diferente dos outros 4 (documentado no próprio arquivo, travado por teste).
- Sem migração de dado existente — Approvals/Quotes/Handoffs já presos em produção continuam
  presos até o primeiro `sweep()` rodar (ou até serem destravados manualmente, como já foi feito
  pela conversa achada ao vivo nesta mesma investigação).

## Regra de revisão
Mudanças nesta decisão — em especial expirar uma Approval sem publicar `approval_decided` (deixaria
o checkpoint preso de novo), ou resolver um Handoff sem reverter a sessão — exigem novo ADR ou
superseding ADR.
