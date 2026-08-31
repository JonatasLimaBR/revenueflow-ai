# ADR-047 — Cloud Run consome o Pub/Sub por pull, com min_instances >= 1 na V1

## Status
Accepted

## Contexto
O ADR-006 e o ADR-044 fixam o Pub/Sub como event backbone e o processamento assíncrono do
webhook atrás da porta `EventPublisher`, mas não definem **como** um serviço Cloud Run consome
a subscription. O `worker/subscriber.py` já implementado é um pull loop
(`SubscriberClient().subscribe(callback=...)`). Cloud Run só executa código enquanto atende
requisição, então um pull loop exige uma instância sempre viva. É uma escolha arquitetural com
impacto em custo, superfície de segurança e estrutura de deploy (AGENTS.md invariante 9).

## Decisão
Na V1, o mesmo serviço Cloud Run que serve o webhook também roda o consumidor: `main.lifespan`
inicia `worker.subscriber.run_subscriber()` como task de background, e o serviço é implantado
com `min_instance_count >= 1`. A subscription é **pull**.

O tópico e a subscription do Pub/Sub se chamam `revenueflow.messages` (com ponto) — os nomes que
o código já usa (`services/ingest.py`, `worker/subscriber.py`); não há env var para sobrescrever.

## Alternativas consideradas
- **Push subscription → endpoint `/internal/consume`** autenticado por OIDC de uma service
  account dedicada + `roles/run.invoker`, com rotas pública/privada separadas.
- **Worker separado** — um segundo serviço Cloud Run (ou Cloud Run Job) rodando só o subscriber,
  deixando a API com scale-to-zero.

## Motivo
Pull + `min_instances >= 1` ship agora com o mínimo de código novo (só a task no lifespan) e
reusa o `subscriber.py` que já existe e é testado. Push exige um endpoint HTTP novo, tratamento
de auth de request e mais IAM; o worker separado adiciona um deployable. Para a V1 em
`LLM_STUB=1`, o custo de uma instância parada é aceitável frente à complexidade evitada.

## Consequências
- Uma instância Cloud Run sempre ligada (custo fixo ~USD 10–20/mês além do Cloud SQL).
- Ingestão e consumo acoplados no mesmo serviço; um deploy reinicia os dois.
- Quando o `WHATSAPP_INBOUND_VERTEX` entrar (turnos mais longos, `ack_deadline` maior, carga
  variável), reavaliar para push ou worker separado — esta decisão pode ser substituída por um
  ADR posterior.
- O `ack_deadline_seconds = 60` da subscription é suficiente em `LLM_STUB`; revisar com o Vertex.

## Regra de revisão
Mudanças nesta decisão exigem novo ADR ou superseding ADR.
