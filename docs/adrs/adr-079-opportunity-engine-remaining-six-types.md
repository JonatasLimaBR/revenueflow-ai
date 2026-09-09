# ADR-079 — Opportunity Engine: os 6 tipos restantes (CHURN, REACTIVATION, ORDER_RECOVERY, CROSS_SELL, UPSELL, INVENTORY_TO_CASH)

## Status
Accepted

## Contexto
PRD-010 lista 8 tipos de oportunidade. O ADR-053 (OPPORTUNITY_ENGINE) só entregou 2
(REPLENISHMENT, QUOTE_RECOVERY) — os outros 6 ficaram como lacuna, descoberta ao auditar o escopo
real do PRD-010 contra o `OpportunityType` do domínio. O usuário autorizou explicitamente
implementar os 6 de uma vez, decidindo sozinho as regras de negócio onde o PRD não especifica o
critério exato, e documentando as decisões aqui para revisão posterior.

Restrições herdadas do ADR-053 (inalteradas): regra pura em `policies/opportunity_policy.py`
(`now` injetado, sem I/O), candidatos vindos de query em `repositories/opportunity.py`, `scan()`
continua em batch fora do grafo (ADR-019), `probability` é placeholder documentado (ADR-018), o
índice único parcial `opportunity (customer_id, opportunity_type, product) WHERE status='OPEN'`
(`0007`) já suporta qualquer valor novo de `opportunity_type` sem migração.

## Decisão

- **CHURN e REACTIVATION reusam o sinal do REPLENISHMENT, em camadas de severidade (DA1).** As
  três regras (`replenishment`, `churn`, `reactivation`) recebem o mesmo `ReplenishmentSignal`
  (dias desde a última compra ÷ intervalo médio), cada uma com seu próprio multiplicador de
  `Settings`: `replenishment_threshold=1.5`, `churn_threshold=3.0`, `reactivation_threshold=6.0`.
  **Não são mutuamente exclusivas** — um cliente muito atrasado pode abrir as três
  simultaneamente, já que o índice único é por `(customer_id, opportunity_type, product)`, não por
  cliente. Aceito deliberadamente: cada tipo carrega uma ação diferente
  (`offer_replenishment` / `reengagement_outreach` / `win_back_campaign`) e cabe ao time comercial
  (ou à fatia ACTIVE_SALES) escolher qual disparar; a alternativa — bandas mutuamente exclusivas —
  exigiria threading de estado entre as três chamadas dentro do mesmo `scan()`.
- **`product=None` em CHURN/REACTIVATION (DA1).** Ao contrário de REPLENISHMENT (que recomenda o
  produto habitual do cliente), CHURN/REACTIVATION são sinais de **relacionamento**, não de
  produto — a oportunidade é "reengajar o cliente", não "vender X de novo". Isso também evita que
  CHURN/REACTIVATION colidam com a chave única do REPLENISHMENT (que já usa o produto habitual).
- **ORDER_RECOVERY = `sales_order(FAILED)` sem retentativa paga (DA2).**
  `order_recovery_candidates` seleciona pedidos `FAILED` onde não existe, para o mesmo
  `customer_ref`, um pedido `CONFIRMED`/`PAID` **posterior**. A regra pura só aplica um piso de
  idade (`order_recovery_hours=24`, `Settings`) para não disparar imediatamente após a falha —
  o cliente pode estar refazendo o pagamento na hora.
- **CROSS_SELL recomenda o acessório mais barato do catálogo, universalmente (DA3).** O catálogo
  simulado tem só 3 produtos `categoria='acessório'` (capacitor, chave-bóia, mangueira) sem mapa de
  compatibilidade por bomba. Em vez de modelar compatibilidade (fora de escopo, exigiria dado que
  não existe), `cross_sell_candidates` sempre oferece o acessório de menor preço
  (`ACC-CAP-250`, hoje) a qualquer cliente que já comprou de qualquer categoria não-acessório e
  nunca comprou acessório nenhum. Simples e determinístico; superestima em alguns casos (o
  capacitor não serve toda bomba), mas é uma sugestão inicial de contato, não um pedido automático.
- **UPSELL recomenda o próximo produto mais caro da mesma categoria (DA4).** `upsell_candidates`
  conta recompras (`≥ upsell_min_repeat_purchases=2`, `Settings`) do mesmo `product_id` e junta
  lateralmente o produto de menor preço **acima** do preço atual, na mesma `category`, que o
  cliente ainda não comprou. Heurística de catálogo (mais caro ⇒ "nível acima"), não olha
  atributos técnicos (HP, vazão) — aceitável no catálogo atual, onde preço e capacidade sobem
  juntos dentro de cada categoria (ex.: bomba periférica 1/3CV → 1/2CV → 3/4CV).
- **INVENTORY_TO_CASH inverte a direção do sinal (DA5).** As outras 7 regras partem do cliente
  (sinal → cliente → produto); esta parte do **produto** (estoque alto e parado, via
  `sim_inventory.available` + tempo desde a última venda, incl. produto nunca vendido) e junta com
  clientes que já compraram da mesma categoria. Dois pisos configuráveis
  (`inventory_to_cash_stock_threshold=10`, `inventory_to_cash_stale_days=60`, `Settings`), ambos
  aplicados na regra pura, não na query.
- **`probability` por tipo, todos placeholders (DA6, ADR-018).** CHURN=0.25, REACTIVATION=0.15,
  ORDER_RECOVERY=0.40, CROSS_SELL=0.20, UPSELL=0.20, INVENTORY_TO_CASH=0.15 — decrescente com a
  distância do sinal em relação a uma compra real (recuperar um pagamento que já quase aconteceu é
  mais provável que reengajar um cliente dormente).
- **`services/opportunity.py::scan()` generaliza para 8 chamadas via um helper `_apply` (DA7).**
  Em vez de repetir o bloco `for signal in candidates: try/except` 8 vezes (2 existentes + 6
  novas), um helper privado `_apply(conn, result, counter=, candidates=, rule=, key=, **kwargs)`
  encapsula o padrão comum (contagem, `try/except` isolado por candidato, evento de tracer no
  erro). `ScanResult` ganha 6 campos de contagem novos; `created`/`errors` continuam agregados.

## Alternativas consideradas
- **Bandas mutuamente exclusivas para REPLENISHMENT/CHURN/REACTIVATION** — exigiria que
  `replenishment()` soubesse do threshold de `churn()` (acoplamento entre regras "independentes").
  Rejeitado por YAGNI: o time comercial revisando a lista de oportunidades resolve a redundância
  manualmente; três sinais abertos para o mesmo cliente não é um bug, é mais contexto.
- **Compatibilidade produto↔acessório modelada em `sim_product.attrs`** — exigiria estender o
  schema simulado e o seed de 24 produtos com um mapa de compatibilidade que não existe hoje. Fora
  de escopo desta fatia; a heurística "acessório mais barato" é suficiente para uma sugestão de
  contato inicial.
- **UPSELL por atributo técnico (HP/vazão) em vez de preço** — mais preciso, mas o catálogo não
  tem uma dimensão de "capacidade" normalizada entre categorias; preço já é um proxy direto e
  monotônico dentro de cada categoria simulada.
- **INVENTORY_TO_CASH global (sem exigir compra prévia na categoria)** — ofereceria estoque
  parado a qualquer cliente, sem sinal de interesse; a versão implementada pelo menos direciona a
  um cliente que já demonstrou comprar daquela categoria.
- **8 blocos de scan repetidos manualmente (sem helper)** — mantém o estilo original do ADR-053,
  mas 8 cópias do mesmo `try/except`/contador é exatamente o tipo de duplicação que motivaria um
  helper; adicionado porque o número de tipos triplicou nesta fatia.

## Motivo
O padrão já estabelecido pelo ADR-053 (regra pura + query de candidatos + `probability` placeholder
+ scan fora do grafo) generaliza limpo para os 6 tipos restantes sem precisar de nenhuma mudança de
arquitetura — só volume. Onde o PRD-010 não especifica o critério de negócio exato (limite de
severidade, escolha de acessório, definição de "próximo nível"), a decisão priorizou o que é
computável a partir do catálogo simulado existente (ADR-028: dados simulados primeiro) sobre
modelagem nova.

## Consequências
- +6 valores de `OpportunityType`, +6 regras puras, +4 queries de candidatos novas (CHURN/
  REACTIVATION reusam a query de REPLENISHMENT), +6 campos de config em `Settings`, +6 contadores
  em `ScanResult`.
- Sem migração nova — o índice único parcial de `0007` já cobre qualquer `opportunity_type`.
- CROSS_SELL pode sugerir um acessório tecnicamente incompatível com a bomba do cliente; aceito
  como heurística inicial, revisar se virar reclamação recorrente.
- UPSELL e INVENTORY_TO_CASH's `stale_days`/`repeat_count` dependem de `sim_customer_order` +
  `sales_order` terem histórico suficiente — em catálogo/base de teste pequenos, os candidatos
  podem ser poucos ou nenhum; comportamento esperado, não é bug.
- Mesmo risco do ADR-053 herdado 6x: `probability` são todos placeholders até haver dado real para
  calibrar.

## Regra de revisão
Mudanças que tornem REPLENISHMENT/CHURN/REACTIVATION mutuamente exclusivas, que modelem
compatibilidade de produto para CROSS_SELL, ou que movam qualquer uma dessas regras para dentro do
grafo (LLM decidindo o gatilho) exigem novo ADR ou superseding ADR.
