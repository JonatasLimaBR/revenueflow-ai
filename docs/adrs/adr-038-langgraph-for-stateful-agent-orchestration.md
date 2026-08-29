# ADR-038 — LangGraph for Stateful Agent Orchestration

## Status
Accepted

## Contexto
O fluxo possui pausas, aprovação humana, retomada e múltiplos agentes.

## Decisão
Utilizar LangGraph para orquestração agentic com estado persistido.

## Alternativas consideradas
- Orquestração ad hoc em FastAPI.
- Loop manual de tool calling.
- Agente único sem grafo.

## Motivo
O grafo torna transições, interrupções e checkpoints explícitos e testáveis.

## Consequências
A aplicação ganha dependência de LangGraph, mas reduz lógica implícita de workflow.

## Regra de revisão
Mudanças nesta decisão exigem novo ADR ou superseding ADR.
