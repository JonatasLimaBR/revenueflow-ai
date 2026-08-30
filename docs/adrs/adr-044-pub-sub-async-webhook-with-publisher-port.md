# ADR-044 — Pub/Sub para processamento assíncrono do webhook, atrás de uma porta EventPublisher

## Status
Accepted

## Contexto
O webhook do WhatsApp precisa responder em poucos segundos (SC1 da fatia WHATSAPP_INBOUND_SLICE), mas o processamento de um turno (classificação de intenção, execução de tools, geração de resposta, envio) leva mais tempo. É preciso desacoplar a recepção do processamento sem contrariar o ADR-006 (Pub/Sub como event backbone).

## Decisão
O serviço de ingestão publica um evento `message_received` num tópico Pub/Sub e devolve `202 Accepted`. Um consumidor processa o evento de forma idempotente. O acesso ao Pub/Sub passa por uma porta `EventPublisher` com duas implementações: `PubSubPublisher` (produção e desenvolvimento) e `InMemoryPublisher` (testes). No ambiente local o Pub/Sub roda como emulador dentro do `docker-compose`.

## Alternativas consideradas
- `fastapi.BackgroundTasks` in-process: acopla o webhook ao processamento, perde a semântica de retry/idempotência de fila e diverge do ADR-006.
- Fila caseira numa tabela PostgreSQL (`SELECT ... FOR UPDATE SKIP LOCKED`): reimplementa o que o Pub/Sub já entrega; o ADR-006 já decidiu o backbone.

## Motivo
A costura de eventos é exercitada desde a primeira fatia, com o envelope padrão (`event_id`, `event_type`, `occurred_at`, `trace_id`, `schema_version`). O emulador remove a dependência de rede e credencial no desenvolvimento e no CI. A porta permite testes determinísticos sem infraestrutura.

## Consequências
Dependência de `google-cloud-pubsub` (extra opcional) e do emulador no `docker-compose`. O consumidor precisa ser idempotente por `event_id`. Em troca, o webhook fica trivialmente rápido e a arquitetura de eventos fica provada desde o início.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
