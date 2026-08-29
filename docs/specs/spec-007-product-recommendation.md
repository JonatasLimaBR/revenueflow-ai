# SPEC-007 — Product Recommendation

## Objetivo
Gerar recomendação com motivo, fonte e confiança.

## Contrato / Dados
recommended_product, reason, source, confidence, required_confirmation

## Regra de implementação
Abaixo do threshold, fazer perguntas adicionais.

## Critérios de aceite
- O comportamento deve ser determinístico quando envolver regra de negócio.
- Falhas devem gerar log estruturado e trace_id.
- O componente deve possuir testes automatizados compatíveis com seu risco.
