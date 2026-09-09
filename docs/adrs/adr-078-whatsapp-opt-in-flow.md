# ADR-078 — Fluxo de opt-in via WhatsApp, simétrico ao guard de opt-out

## Status
Accepted

## Contexto
O ADR-059 (ACTIVE_SALES) já implementou o guard de opt-out inbound (`outbound_policy.is_opt_out`)
e o Policy Gate exige `consent_opt_in_at` antes de qualquer contato ativo — mas nada no sistema
nunca populava esse campo. `consent_opt_in_at` ficou deliberadamente vazio pra clientes reais até
agora (decisão registrada em CLAUDE.md), esperando o cliente responder no WhatsApp. Usuário pediu
explicitamente pra fechar essa lacuna.

## Decisão

- **`policies/outbound_policy.py::is_opt_in(text)`** — mesmo padrão exato de `is_opt_out`: match
  exato (não substring) contra uma frase fixa, não uma palavra solta. **Frase escolhida pelo
  usuário: "ACEITO RECEBER OFERTAS"** — deliberadamente específica. Uma palavra curta como "aceito"
  sozinha colidiria com aceitar uma proposta de negociação/preço no meio de uma conversa de venda
  (`negotiation_node`/`checkout_node` já usam linguagem parecida) — um falso positivo ali daria
  consentimento de marketing sem o cliente ter pedido isso.
- **Guard simétrico em `worker/consume.py::process_event`**, logo depois do guard de opt-out
  existente: se `is_opt_in`, grava `customer_repo.set_consent_opt_in` (só quando `customer_id` já
  existe — um lead nunca convertido não tem onde gravar `consent_opt_in_at`, mesma assimetria já
  aceita no guard de opt-out) e responde com uma frase fixa de confirmação, **sem passar pelo
  grafo** — mesmo motivo do opt-out: não é uma decisão que o LLM deveria interpretar.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- Perguntar proativamente por opt-in em algum ponto do fluxo (ex: depois do primeiro pedido
  fechado) — isso é uma decisão de UX/negócio maior, sobre quando e como pedir consentimento, não
  parte do guard inbound em si.
- Múltiplas frases de opt-in ou reconhecimento mais flexível — a mesma frase única, exata, que já
  seria comunicada ao cliente (ex: numa campanha ou na landing page) é suficiente; frouxidão aqui é
  risco de LGPD, não conveniência.

## Alternativas consideradas

- **"aceito"/"sim"/"quero receber" como keywords isoladas** — rejeitada: alto risco de falso
  positivo contra "aceito o desconto"/"aceito a proposta", que já são frases plausíveis dentro de
  uma negociação real (confirmado com um teste de regressão dedicado:
  `test_is_opt_in_rejects_substring_and_unrelated_text`).
- **Perguntar por opt-in dentro do próprio grafo (via LLM)** — rejeitada pelo mesmo motivo do
  opt-out original: consentimento de contato ativo é um controle de compliance, não uma
  interpretação de linguagem natural.

## Motivo
Fecha a lacuna documentada desde ACTIVE_SALES (ADR-059) com o mesmo padrão determinístico já
validado pro opt-out — sem introduzir ambiguidade nova nem depender do LLM pra uma decisão de
consentimento.

## Consequências
- `outbound_policy.py` += `is_opt_in` + `OPT_IN_KEYWORDS`; `worker/consume.py` += guard +
  `_OPT_IN_CONFIRMED`; +ADR-078.
- Sem migração — `customer.consent_opt_in_at` já existe desde o `0012` (ACTIVE_SALES).
- `campaign.run()` (ADR-059) passa a poder de fato contatar clientes que respondam essa frase — até
  agora nunca tinha `has_opt_in=True` pra ninguém real.
- A frase exata precisa ser comunicada ao cliente em algum canal (campanha, landing page, etc.)
  pra virar utilizável na prática — isso é responsabilidade de quem escreve a copy desses canais,
  não deste ADR.

## Regra de revisão
Mudanças nesta decisão — em especial trocar o match exato por substring, ou aceitar múltiplas
frases curtas e genéricas — exigem novo ADR ou superseding ADR.
