# Revisão de Código Gerado por Agentes

Código gerado por agente é não revisado até passar por validações automáticas e humanas.

## 1. Automática
lint, format, types, testes, docs, secrets.

## 2. Arquitetural
aderência aos ADRs e boundaries.

## 3. Negócio
obrigatória para pricing, margem, inventory, order, payment, outbound e PII.

## 4. Segurança
prompt injection, tool escalation, data leakage, logging de PII e secrets.

## Checklist do reviewer
- Implementa SPEC ou inventa comportamento?
- Agente ganhou nova tool?
- LLM está calculando algo determinístico?
- Existe bypass de aprovação?
- Pode haver mistura de contexto entre clientes?
- Falha de forma segura?
- Há testes negativos?
- A decisão é auditável?

“Foi gerado pelo Codex” não é evidência de correção.
