# ADR-041 — Independent Spec Verification Ritual

## Status
Accepted

## Contexto
O mesmo agente que implementa tende a validar seu próprio raciocínio e pode deixar passar desvios da SPEC.

## Decisão
A verificação de SPEC deve ser executada em sessão independente, com contexto da documentação e do diff, mas sem permissão para corrigir o código.

## Alternativas consideradas
- Autor revisar a própria implementação.
- Revisor automático que também modifica o código.

## Motivo
Separar autoria e verificação reduz confirmação de viés e mantém o veredito independente.

## Consequências
O fluxo de desenvolvimento terá uma etapa explícita de verificação antes do merge.

## Regra de revisão
Mudanças nesta decisão exigem novo ADR ou superseding ADR.
