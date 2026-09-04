# ADR-058 — HARDENING_SECURITY_PII: security-by-architecture + `mask()` += CPF + suíte `tests/security/`

## Status
Accepted

## Contexto
As SPEC-030 (Security), SPEC-031 (PII) e SPEC-032 (Prompt Injection) são de **controles mínimos**,
e a arquitetura do RevenueFlow já respeita a maior parte:

- policies decidem, não o LLM (ADR-009); tools isoladas por registry (ADR-037); `mask()` na borda
  do tracer; secrets Terraform-generated, fora do repo; gitleaks no pre-commit e no CI.

Mas há **lacunas concretas** e **falta de evidência**:

- `observability/masking.py::mask()` cobre só `email` + `phone` (+ `extra_terms`). A SPEC-031
  lista `phone, email, address, CPF, name` — **CPF não tem regex próprio**.
- `main.py` não emite **nenhum** header de segurança (`FastAPI(...)` sem middleware).
- `tests/security/` tem só `test_tool_permissions.py` (a fronteira ADR-037). Não há prova de que
  uma injeção **não** muda alçada/preço/tools, de que um turno real **não** deixa PII crua no
  log/`audit_event`, nem de que **toda** rota `/internal/*` recusa sem Bearer.

Restrições: ADR-032 escolhe **minimizar** PII, não cifrar; o `phone` é PII **necessária**
(identidade via índice único + outbound); a suíte roda só com `postgres:16` sem credencial de
nuvem; sem dependência nova.

## Decisão

- **`mask()` += `_CPF` (DA1).** `_CPF = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")`, aplicado em
  `_mask_text` na ordem `_EMAIL → _CPF → _PHONE → extra_terms` (mais específico primeiro; o
  `_PHONE` largo comeria dígitos do CPF). `name`/`address` continuam cobertos **só** via
  `extra_terms` — quem chama `mask()` passa os termos conhecidos. Regex de nome redige palavra
  comum ("Silva", "Bomba") — falso-positivo pior que o gap. **`pii_terms_from` (previsto no
  DEFINE) não entra**: auditados os call sites, nenhum valor de `name` atravessa a borda do
  tracer/LLM hoje (o `Customer360View` não tem `name`; o `handoff.context` tem `name` **de
  propósito** para o atendente e é Bearer-gated). Helper sem consumidor = código morto.
- **Headers de segurança via `@app.middleware("http")` (DA2).** `_SECURITY_HEADERS` =
  `{X-Content-Type-Options: nosniff, X-Frame-Options: DENY, Referrer-Policy: no-referrer,
  Strict-Transport-Security: max-age=31536000; includeSubDomains}`, aplicados com `setdefault`
  (não sobrescreve um header que uma rota tenha setado — nenhuma seta hoje) a **toda** resposta,
  incl. erros e 404. Sem dependência (rejeita a lib `secure`). Sem `Content-Security-Policy` (a
  API não serve HTML; CSP entra com a LANDING_PAGE).
- **A suíte `tests/security/` é a evidência executável (DA4).** 4 arquivos novos:
  - `test_pii_masking.py` — `mask()` redige phone/email/CPF em str/dict/list; `extra_terms` redige
    nome; um `process_event` real → `audit_event.events` (jsonb) e `caplog` **não** contêm o
    telefone cru do envelope.
  - `test_injection_resistance.py` — os 3 registries (`RECOMMENDATION`/`NEGOTIATION`/`CHECKOUT`)
    são **disjuntos** e `graph_tool_names(build_graph(...))` == a união dos 3 (a fronteira é
    estática — um turno não a expande); `pricing_policy.evaluate` é **pura** (só `Decimal`) — um
    "conceda 50%" da injeção ainda dá `requires_approval`; um turno adversário com desconto pedido
    `> pricing_max_discount_pct` → `snapshot.next` contém `await_approval` (o `interrupt`
    disparou); `is_explicit_confirmation` de um texto com injeção retorna `True` **mas é seguro**
    (`quote_from_state` lê `state["checkout_discount"]` resolvido antes, não o texto).
  - `test_internal_routes_auth.py` — parametrizado sobre as 5 rotas `/internal/*`: sem `Bearer` →
    `401`, errado → `401`, sem o secret configurado → `503`.
  - `test_security_headers.py` — `GET /healthz` traz os 4 headers com os valores exatos.
- **Ordem dos regex (DA5).** `_EMAIL → _CPF → _PHONE` — mais específico primeiro para o `_PHONE`
  largo não redigir parte do CPF e apagar a intenção.

## Fora de escopo (decisões explícitas de **não** fazer na V1 — DA3)

- **Cifra a nível de campo / tokenização** do `phone`/`name` no OLTP — quebra o índice único
  `lead(phone)`/`customer(phone)` (identidade), o join de `customer_360` e o `ChannelOutbound.send`.
  ADR-032 = **minimizar**; o controle de PII em repouso na V1 é o **RBAC do Cloud SQL** + o
  `mask()` na borda de logs/traces.
- **Sweep de retenção / TTL de PII** (`lead`/`conversation_session` antigos) — fatia de dados
  futura, junto do TTL-sweep de `Approval`/`Quote`/`Handoff` já recomendado.
- **Regex de `name`/`address`** no `mask()` — falso-positivo; via `extra_terms`.
- **Rate limiting / WAF** — território do Cloud Run / Load Balancer; V1 confia no HMAC do webhook
  + Bearer das rotas internas.
- **Google DLP API** — custo + latência + dep; o `mask()` determinístico basta para o contrato da
  SPEC-031.
- **Tamper-evidence / hash-chain do `audit_event`** — já decidido fora na AUDIT_TRAIL.
- **mTLS API↔consumer** — mesmo processo (ADR-047); não há tráfego entre serviços.
- **Rotação automática dos `*_API_TOKEN`** — Terraform gera; rotação é `terraform apply` manual
  na V1.
- **`Permissions-Policy` / `Content-Security-Policy`** — entram com a LANDING_PAGE (GCS).
- **Split public-webhook / private-admin service** — follow-up de infra conhecido.

## Alternativas consideradas
- **Regex de `name`/`address` no `mask()`** — redige palavra comum; nomes brasileiros são
  palavras comuns.
- **`pii_terms_from` não-usado como "defesa futura"** — código morto; entra quando houver call
  site.
- **lib `secure` / `starlette-secure-headers`** — dependência nova para ~10 linhas.
- **`BaseHTTPMiddleware` (classe)** — mais verboso que a function.
- **`response.headers[k] = v` (sobrescreve)** — perde um header intencional de uma rota.
- **Diff de `graph_tool_names` antes/depois de um turno adversário** — `graph_tool_names` é
  **estático por construção** hoje (a união dos registries); o diff seria sempre vazio → teste sem
  valor. Asserimos a pureza das policies + o `interrupt` + a disjunção dos registries.
- **Cifrar `phone` com `pgcrypto` + coluna `phone_hash` para o índice** — muita máquina; ADR-032
  não pede.

## Motivo
As três SPECs são de controles mínimos e a arquitetura já os respeita — o que falta é fechar 2
lacunas baratas (CPF, headers) e transformar "a arquitetura garante" em **teste que falha se
alguém quebrar**. ~15 linhas de código + 4 arquivos de teste, sem dependência, sem infra, sem
migração. O que **não** fazer (cifra de campo, retention, rate-limiting) fica registrado aqui para
não ser re-litigado.

## Consequências
- +`_CPF` em `masking.py` (~3 linhas); +`_SECURITY_HEADERS` + 1 middleware em `main.py` (~15
  linhas); +4 arquivos em `tests/security/`; +ADR-058.
- Uma regressão que exponha a alçada à injeção, torne `pricing_policy.evaluate` impura, tire o
  Bearer de uma rota, ou pare de mascarar PII → **CI vermelho**.
- Um id de 11 dígitos num log pode virar `***` (falso-positivo do `_CPF`) — aceitável (log/trace,
  não regra de negócio).
- `phone`/`name` ficam em claro no OLTP (protegidos por RBAC) — dívida conhecida, registrada.
- `name` num `attrs` de span **futuro** passa cru até o call site passar `extra_terms=[name]` —
  mitigado pelo teste do padrão `extra_terms` + este ADR.

## Regra de revisão
Mudanças nesta decisão — em especial adicionar regex de nome ao `mask()`, remover um header de
segurança, ou reverter a decisão de **não** cifrar/expirar PII na V1 sem um controle equivalente —
exigem novo ADR ou superseding ADR.
