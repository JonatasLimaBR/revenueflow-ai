# ADR-046 — Docker Compose e Makefile como harness de desenvolvimento

## Status
Accepted

## Contexto
A fatia WHATSAPP_INBOUND_SLICE depende de PostgreSQL, do emulador do Pub/Sub e do Langfuse para rodar ponta a ponta. Sem um ambiente local padronizado, cada contribuidor (humano ou agente) monta o seu, e o CI diverge do que roda na máquina. O repositório também impõe que todo desenvolvimento entre por Pull Request na `main` protegida.

## Decisão
O ambiente local é um `docker-compose.yml` com os serviços `app`, `postgres`, `pubsub-emulator`, `langfuse` e `langfuse-db`. Os comandos comuns ficam num `Makefile` (`make up/down/logs/migrate/seed/lint/format/typecheck/test/run/shell`), e cada alvo chama exatamente os mesmos comandos que o CI executa — sem lógica própria. Cada tarefa de desenvolvimento cria uma branch nova (`feat/…`, `fix/…`, `chore/…`) e entra por PR com os checks obrigatórios verdes; a `main` não recebe push direto, inclusive de administradores.

## Alternativas consideradas
- Scripts soltos em `scripts/`: dispersam o conhecimento e divergem do CI com o tempo.
- Rodar tudo no host sem contêiner: divergência de ambiente e necessidade de PostgreSQL, Pub/Sub e Langfuse instalados localmente.
- Trabalhar direto na `main`: incompatível com desenvolvimento paralelo por múltiplos agentes e com a branch protection já configurada.

## Motivo
Um único ponto de entrada para desenvolvimento e CI reduz o "na minha máquina funciona". O fluxo de branch por tarefa e PR é o que torna seguro múltiplos agentes desenvolverem em paralelo, com escopos de arquivo disjuntos e revisão automatizada pelo CI.

## Consequências
Contribuidores precisam de Docker. O `Makefile` vira o contrato de comandos e é a fonte de verdade que o CI espelha. O número de Pull Requests cresce, mas cada um fica pequeno e revisável de forma independente.

## Regra de revisão
Alterações relevantes nesta decisão exigem novo ADR ou substituição formal deste documento.
