# Decisões do GCP Claude Code Dev Kit

## Cloud CLI MCP remoto

Adotado como MCP GCP principal de desenvolvimento.

Motivo:
- endpoint remoto gerenciado pelo Google;
- integração com serviços Google via comandos Cloud CLI;
- autenticação baseada em identidade Google/IAM.

Não é dependência de runtime do RevenueFlow.

## GKE MCP

Mantido apenas como opção futura.

A V1 usa Cloud Run, portanto instalar GKE MCP agora aumentaria privilégios e superfície operacional sem necessidade.

## Skills próprias

Skills são versionadas junto do repositório porque o conhecimento importante é específico do RevenueFlow:
- boundaries;
- segurança;
- policy engine;
- dados;
- GCP;
- FinOps.

## Hooks

Hooks funcionam como barreira adicional para ações destrutivas.

Ainda assim, IAM e revisão humana continuam sendo os controles de segurança principais.

## Revisão independente

`spec-reviewer` e `security-reviewer` são deliberadamente read-only.
O revisor não deve virar autor na mesma sessão.
