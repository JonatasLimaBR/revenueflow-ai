# ADR-050 — Retomada da aprovação: rota interna + evento Pub/Sub + `Command(resume)`

## Status
Accepted

## Contexto
A fatia `PRICING_AND_NEGOTIATION` entregou o fire-and-stop (ADR-039): desconto fora da alçada
→ `Approval(PENDING)` + `interrupt()` no `await_approval_node` → grafo pausa com checkpoint no
Postgres. Não havia par: nada seta `APPROVED/REJECTED/EXPIRED`, não há rota para o operador
decidir, o thread do LangGraph fica interrompido pra sempre e o cliente nunca recebe a resposta
final.

Restrições que moldam a decisão: preço/margem nunca saem do LLM (ADR-009/011/025); idempotência
obrigatória (ADR-021); a API publica evento e não processa no request (ADR-047); a suíte roda
só com `postgres:16`, sem credencial de nuvem; autonomia proporcional ao risco (ADR-036).

## Decisão

**Registrar a decisão numa rota interna, transformá-la num evento, e retomar o grafo no consumer
pull com `Command(resume=...)`.**

- **Rota** `api/approvals.py` no mesmo serviço Cloud Run (público, `allUsers`):
  - `GET /internal/approvals?status=PENDING` — lista o que o operador pode decidir.
  - `POST /internal/approvals/{approval_id}` — body `{decision: approve|approve_with_override|reject, discount_pct?}`.
  - Ambas atrás de `Authorization: Bearer <APPROVAL_API_TOKEN>` (`secrets.compare_digest`;
    token vazio → `503`, nunca "aberto"). É o mesmo nível de controle do HMAC do webhook
    (ADR-016/031): controle de aplicação, trade-off V1 documentado.
- **Serviço** `services/approval.decide()`: transição **condicional**
  `UPDATE approval SET status=…, approved_discount=…, decided_at=now() WHERE approval_id=%s AND status='PENDING'`.
  `rowcount == 1` → publica **um** `EventEnvelope(event_type="approval_decided", …)` no mesmo
  tópico `revenueflow.messages`. `rowcount == 0` (já decidido) → `200` no-op. `approval_id`
  inexistente → `404`.
- **Consumer** `worker/consume.process_approval_decided()`: `processed_event.claim(kind="resume")`
  → `pg_advisory_xact_lock(hashtext(conversation_id))` numa transação →
  `graph.ainvoke(Command(resume={decision, discount_pct}), config={thread_id: conversation_id})`
  → envio idempotente pelo `dispatch.reserve` + `ChannelOutbound.send`. O `subscriber._handle`
  roteia por `event_type`.
- **Grafo**: `await_approval_node` passa a `decision = interrupt({...})` e a devolver
  `{"approval_decision": decision}`. Nova aresta `await_approval → apply_decision → END`.
  `apply_decision_node` é **determinístico** — lê o `Approval`, o `price_quote` **congelado** no
  state do checkpoint pelo `negotiation_node`, aplica o desconto efetivo clampado ao pedido, e
  monta a `reply` por template. Nenhum `import` de `services.llm`. Quatro desfechos:
  `approved`, `overridden`, `rejected`, `expired`.
- **TTL**: `migrations/0004_approval_resume.sql` adiciona `expires_at`, `approved_discount`,
  `decided_at` (nullable). O `negotiation_node` grava `expires_at = now + approval_ttl_hours` na
  criação. O `apply_decision_node` compara `now` com `approval.expires_at` (nunca recalcula
  tempo — o nó re-executa top-down na retomada). "Ninguém decide nunca" (sem retomada
  disparada) fica pra uma fatia futura de TTL-sweep.
- **Concorrência**: se o cliente manda mensagem nova enquanto o thread está interrompido, o
  `process_event` consulta `aget_state()`; se `next` inclui `await_approval`, responde "sua
  solicitacao anterior ainda esta em analise" e não roda turno novo.

## Alternativas consideradas
- **Retomar sincronamente no request HTTP** — fere o ADR-047 (a API publica, o consumer
  processa) e prende a latência da retomada no request do operador.
- **Reusar `negotiation_node` com flag** — sobrecarrega um nó com dois trabalhos; testes e
  wiring piores.
- **Resolver tudo fora do grafo, no consumer** — o checkpoint nunca resolve; qualquer mensagem
  futura no thread trava. Contraria o ADR-039.
- **Segundo tópico Pub/Sub `revenueflow.approvals`** — mais IaC (tópico + subscription + IAM)
  sem ganho no volume V1; ack/nack e DLQ são por mensagem, não por tipo.
- **Recalcular o preço na data da aprovação** (re-`get_price`) — o cliente foi cotado num
  preço; aprovar não deve re-precificar. `price_quote` congelado no checkpoint.
- **Job agendado de TTL-sweep nesta fatia** — infra à parte; o `expires_at` já cobre "decisão
  chegou tarde".
- **Rota interna privada por rede/IAM** — exigiria split do serviço ou VPC; fora do escopo V1.

## Motivo
O `interrupt()` do ADR-039 foi feito pra ser retomado com `Command(resume=...)` — usar o
mecanismo canônico mantém o ciclo de checkpoint limpo e "um nó, um trabalho". Evento no mesmo
tópico reusa toda a máquina de idempotência/DLQ já existente. `apply_decision` determinístico
honra ADR-009/011/025. O advisory lock transacional é a trava mais leve pra serializar por
`conversation_id` sem tabela nova. Bearer + secret é proporcional ao risco (ADR-036) e
consistente com o webhook.

## Consequências
- `config.py` ganha `approval_api_token` e `approval_ttl_hours`; `secrets.tf` ganha o container
  `revenueflow-approval-api-token` — alguém precisa `gcloud secrets versions add` antes da
  revisão nova ficar healthy (mesmo padrão dos secrets do WhatsApp).
- `negotiation_node` passa a persistir `price_quote`/`requested_quantity`/`requested_discount`
  no state do checkpoint (mudança pequena e local).
- `apply_decision_node` mantém um `unit_of_work` aberto durante o `ainvoke` da retomada (o
  advisory lock). Aceitável no volume de aprovações da V1.
- Colisão de `hashtext` (rara) serializa dois `conversation_id` distintos — perda de
  throughput, não de correção.
- A rota fica no serviço público; o token é o único gate. Anotado como trade-off V1; um split
  webhook-público / admin-privado é fatia futura (já há um `DECISION PENDING` no `cloud_run.tf`).
- "Cliente insiste durante a análise" só recebe um aviso; enfileirar a mensagem para depois da
  aprovação é melhoria futura.

## Regra de revisão
Mudanças nesta decisão exigem novo ADR ou superseding ADR.
