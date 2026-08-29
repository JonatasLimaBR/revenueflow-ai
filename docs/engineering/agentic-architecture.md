# Arquitetura Agentic — RevenueFlow AI

## Princípio central

O RevenueFlow AI aplica **segurança por arquitetura**, e não apenas por prompt.

A regra não é:

> "o agente não deve usar uma ferramenta"

A regra é:

> "o agente não possui essa ferramenta registrada".

Isso reduz a superfície de erro, prompt injection e privilege escalation.

## Topologia de agentes

```text
Cliente
  │
  ▼
WhatsApp Adapter
  │
  ▼
Sales Supervisor
  │
  ├──────── Recommendation Agent
  │           tools read-only
  │           ├─ search_products
  │           ├─ get_product_details
  │           ├─ get_inventory
  │           └─ get_customer_sales_context
  │
  ├──────── Negotiation Agent
  │           tools restritas
  │           ├─ get_price
  │           ├─ calculate_margin
  │           └─ propose_allowed_discount
  │
  └──────── Checkout Agent
              tools de escrita
              ├─ create_quote
              ├─ create_order
              └─ create_payment_sandbox
                       │
                       ▼
                Human Interrupt
                       │
                       ▼
                 Approval Queue
```

## Read-only vs write tools

### Recommendation Agent
Não possui qualquer ferramenta de escrita.

Ele pode:
- pesquisar;
- consultar;
- recomendar;
- explicar.

Ele não pode:
- alterar cadastro;
- criar proposta;
- criar pedido;
- criar pagamento;
- alterar preço.

### Negotiation Agent
Não possui liberdade para inventar condições.

Ele pode:
- consultar pricing;
- consultar margem;
- sugerir condição dentro da política.

Se a condição ultrapassa a política, o grafo entra em `interrupt`.

### Checkout Agent
É o único agente com ferramentas de escrita comercial.

Ainda assim, ações irreversíveis passam por pré-condições determinísticas e, quando aplicável, aprovação humana.

## Orquestração

A V1 utilizará **LangGraph** para fluxos agentic.

Motivos:
- grafo explícito;
- estado persistente;
- `interrupt`;
- retomada do fluxo após aprovação;
- separação entre passos;
- testabilidade do workflow.

## Persistência de estado

O estado do workflow será persistido em PostgreSQL.

Estados relevantes:

- conversation_state;
- current_agent;
- pending_tool_call;
- approval_id;
- quote_id;
- order_id;
- workflow_checkpoint.

Nenhuma ação de checkout depende apenas de memória de conversa do modelo.

## Interrupt como primitivo de segurança

Antes de uma ação irreversível, o grafo deve poder parar.

Exemplos:

```text
discount_out_of_policy
high_value_order
margin_below_minimum
special_payment_condition
customer_requests_human
```

Fluxo:

```text
Agent
  ↓
Policy Check
  ↓
interrupt
  ↓
Postgres checkpoint
  ↓
Operator Queue
  ↓
approve / reject
  ↓
Resume graph
```

Sem `APPROVED`, não existe transição válida para execução.

## Observabilidade desde o início

A observabilidade não entra no fim do projeto.

Ela entra na primeira fatia funcional.

A solução deverá registrar:

- trace_id;
- conversation_id;
- agent;
- node;
- tool;
- tool input sanitizado;
- tool result sanitizado;
- model;
- prompt version;
- latency;
- token usage;
- cost;
- policy decision;
- approval;
- final outcome.

## Langfuse

A arquitetura adota **Langfuse** como camada de tracing de LLM/agents.

Na V1 pode ser:
- self-hosted;
- ou substituída por tracing compatível se necessário.

PII deve ser mascarada antes de chegar à plataforma de observabilidade.

## Regra de preço

Preço nunca sai do modelo.

O agente chama:

```text
get_price(customer_id, product_id, quantity)
```

Fonte:

PostgreSQL / Pricing Service.

## Regra de estoque

Estoque nunca sai do modelo.

O agente chama:

```text
get_inventory(product_id, quantity)
```

## Regra de desconto

Não existe tool genérica:

```text
set_discount(percent)
```

O agente só dispõe de:

```text
propose_allowed_discount(...)
```

Essa tool aplica a política e retorna:
- allowed;
- max_allowed;
- resulting_margin;
- requires_approval.

A arquitetura impede desconto livre.

## Decisão de segurança

Prompt é orientação.

Permissão de tool é controle.

Policy Engine é autoridade.

Human approval é barreira final.
