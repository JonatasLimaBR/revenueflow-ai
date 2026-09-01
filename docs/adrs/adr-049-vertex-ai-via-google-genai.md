# ADR-049 — Vertex AI via google-genai (vertexai=True), com retry e handoff

## Status
Accepted

## Contexto
O fluxo inbound (ADR-038, fatias `WHATSAPP_INBOUND_SLICE` e `PRICING_AND_NEGOTIATION`) roda em
`LLM_STUB=1`: classificação de intenção e geração da resposta ancorada usam um stub
determinístico por keyword. O caminho real do Gemini já existe em
`src/revenueflow/services/llm.py` (ADR-028 — simular primeiro), mas instanciava
`genai.Client()` no modo Gemini Developer (exige API key), e nunca foi ligado.

A fatia `WHATSAPP_INBOUND_VERTEX` liga o caminho real nos dois call sites (`gemini_json` para
intent, `gemini_text` para resposta). Restrições que moldam a decisão: keyless (ADR-048),
LLM não é system of record (ADR-009), prompt injection não altera regras (ADR-024, invariante),
least privilege (ADR-008), a suíte de testes roda só com `postgres:16` e sem credencial de
nuvem, e o `llm_stub` continua sendo o default de dev local.

## Decisão
O caminho real usa **Vertex AI** através do pacote **`google-genai`** em modo Vertex,
autenticando por **ADC** (a service account de runtime do Cloud Run) — sem chave.

- `genai.Client(vertexai=True, project=<settings.google_cloud_project>, location=<settings.vertex_location>)`.
- `vertex_location` tem default **`"global"`** (endpoint global do Vertex para Gemini), o que
  remove a dependência de disponibilidade regional do Gemini em `southamerica-east1`. Uma
  variável Terraform `vertex_location` permite fixar uma região (ex.: `us-central1`) se houver
  exigência de residência de dados.
- **Retry classificado por tipo de erro** (`_generate_with_retry`): `google.genai.errors.ServerError`
  (5xx), `ClientError` com código em `{429,500,502,503,504}` e `TimeoutError` → backoff
  exponencial com jitter, até `llm_max_retries` (default 2) tentativas extra. Qualquer outro
  `ClientError` (401/403/400/404) → `LLMError` imediato, sem retry.
- **Falha esgotada → handoff humano.** `classify_intent_node` e `respond_node` capturam
  `LLMError` e roteiam para um nó terminal `handoff` que registra o trace com `handoff=True`.
  A `reply` do turno vira uma frase fixa de encaminhamento — nenhuma resposta gerada pelo modelo
  é enviada nesse turno.
- **Hardening de prompt (v2).** O conteúdo do cliente vai entre `<mensagem_cliente>` e é
  descrito no system prompt como DADO, nunca instrução; o bloco `<resultados>` idem. `prompt_version`
  sobe para `v2` no tracing.
- **Testes.** O CI (`tests`) permanece sem credencial: baseline stub determinístico + testes de
  construção de prompt anti-injection + teste `LLMError → handoff`, todos offline. A avaliação
  contra o Vertex real fica num eval **live opt-in** (`@pytest.mark.live`, só com
  `RUN_LIVE_EVAL=1` + ADC), rodado por um humano antes do merge.
- A imagem de produção instala o extra `[llm]` (`google-genai`); o Cloud Run roda `LLM_STUB=0`;
  a SA de runtime recebe `roles/aiplatform.user`.

## Alternativas consideradas
- **Gemini Developer API com API key** — introduz um segredo no Secret Manager e fere o keyless
  do ADR-048.
- **Pinar `southamerica-east1`** — disponibilidade do Gemini na região não confirmada; risco de
  quebrar o deploy. `"global"` destrava sem essa dependência; a região fixa continua sendo só
  trocar a variável.
- **Fallback automático para o stub quando o Vertex falha** — produz uma resposta que parece
  real sem ser; rejeitado em favor do handoff explícito.
- **Retry em qualquer exceção** — desperdiça latência em erro de auth e mascara erro de
  configuração.
- **`interrupt()` / nó `await_approval` como destino da falha** — semântica de pausar-e-retomar
  após decisão humana, não de encerrar o turno.
- **Rodar o eval real no CI** — exigiria credencial de produção em teste (invariante), custo por
  run e flakiness.
- **Porta `LLM` formal (Protocol + StubLLM/VertexLLM)** — over-engineering para 2 call sites sem
  terceiro provider à vista; possível refactor futuro.

## Motivo
ADC + `google-genai` modo Vertex é o caminho keyless e é o mesmo pacote/API já escrito, então a
mudança é trocar o construtor do `Client` e adicionar a política de resiliência. `"global"`
elimina a única incógnita operacional (região). Retry classificado trata transitório sem
mascarar erro permanente. Handoff explícito honra "o mais real possível, sem inventar": ou
resposta real ancorada, ou um humano assume. O split de testes respeita as invariantes de
credencial sem abrir mão de um eval contra o modelo real.

## Consequências
- O texto da mensagem do cliente trafega para o endpoint `global` do Vertex. O mascaramento de
  PII (ADR-040/SPEC-031) é antes do sink de observabilidade, não antes do LLM — mandar a
  mensagem ao modelo é inerente à feature. Se LGPD exigir região fixa, `vertex_location` é a
  alavanca (sem novo ADR).
- A cobertura contra o modelo real depende de um passo manual (`RUN_LIVE_EVAL=1 pytest -m live`
  com ADC), documentado no runbook e registrado no BUILD_REPORT.
- `services/llm.py` passa a acoplar (lazy, só no caminho real) `google.genai.errors`.
- Custo por turno = 2 chamadas Gemini (`gemini-2.5-flash` — a linha 2.0 foi retirada do Vertex
  para o projeto; a validação de disponibilidade fixou `gemini-2.5-flash` no endpoint `global`).
  Sem hard cap nesta fatia — ADR-023 trata custo como KPI/observabilidade; `cost_usd` continua
  registrado por generation.
- O grafo ganha um nó `handoff` e dois campos opcionais no `TurnState` (`handoff`,
  `handoff_reason`).
- `LLM_STUB` continua sendo o default de `Settings` — dev local (`make up` sem GCP) e CI não
  mudam.

## Regra de revisão
Mudanças nesta decisão exigem novo ADR ou superseding ADR.
