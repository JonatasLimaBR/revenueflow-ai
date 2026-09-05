# ADR-066 — CTA de WhatsApp na landing page: deep link `wa.me`, sem backend novo

## Status
Accepted

## Contexto
ADR-060 (LANDING_PAGE) publicou um site estático explicando as fatias entregues, mas sem nenhum
caminho de conversão real — um visitante não tinha como acionar os agentes a partir da página. O
usuário pediu explicitamente um CTA de WhatsApp na landing page "para acionar os agentes" e forneceu
o número de telefone comercial (`19982499116`, DDD + número, assumido `+55` pelo contexto do
projeto — confirmar com o usuário se o número final publicado precisar mudar).

## Decisão

- **Deep link `https://wa.me/<E.164>?text=<mensagem pré-preenchida>`, sem integração de backend
  nova.** O clique abre o WhatsApp do visitante (app ou Web) já com uma mensagem inicial —
  `"Olá! Vim pela landing page da RevenueFlow AI e quero saber mais sobre o produto."` — que, ao
  ser enviada, entra no fluxo real já em produção (`POST /webhook/whatsapp` → grafo LangGraph →
  `WHATSAPP_INBOUND_SLICE`/`WHATSAPP_INBOUND_VERTEX`). Não existe "acionar os agentes" fora desse
  caminho — o CTA só leva o visitante até a porta de entrada que já funciona.
- **Número fixo no HTML** (`5519982499116`), não uma variável de Terraform/config. O número do
  WhatsApp Business já é a fonte de verdade operacional em `WHATSAPP_PHONE_NUMBER_ID` (Secret
  Manager, ADR-015); o link do `wa.me` é conteúdo de site estático, editado como qualquer outra
  copy da página (ADR-060 já estabeleceu isso — "editar copy é um commit normal, sem plan/apply").
- **Três pontos de entrada**, mesma URL: `topnav__cta` (sempre visível, substitui o antigo "Ver no
  GitHub" — a ação comercial é a prioridade agora), o primeiro botão do hero (`btn--whatsapp`, cor
  dourada nova — diferencia da ação "Explorar o código" em teal), e um link no rodapé. O link pro
  GitHub continua acessível no hero e no rodapé — não foi removido, só deixou de ser a ação
  primária do topo.
- **Sem CSP nova.** A CSP existente (`default-src 'self'`) não restringe navegação de `<a href>`
  para um domínio externo — só recursos carregados pela própria página (script/style/img/connect).
  Um clique em `wa.me` é navegação de topo, não uma requisição da página.

## Fora de escopo (decisões explícitas de **não** fazer nesta fatia)

- WhatsApp Business API/Message Templates para a mensagem inicial — o deep link `wa.me` já cobre o
  caso de uso (visitante inicia a conversa), sem precisar de HSM aprovado pela Meta.
- Analytics de clique/conversão no CTA — a landing page continua com **zero coleta de dado**
  (ADR-060), sem exceção pra esse botão.
- Atualizar as demais estatísticas da landing page (contagem de "fatias entregues", "ADRs") — a
  página já estava desatualizada antes desta fatia; corrigir os números é um follow-up de conteúdo
  separado, fora do escopo do CTA em si (só o texto "13 fatias" que citava um número específico foi
  removido do botão, pra não publicar um dado errado).

## Alternativas consideradas

- **Formulário de contato na própria página** (nome/telefone/mensagem, com um backend novo pra
  processar) — exigiria uma rota HTTP nova, armazenamento de lead pré-WhatsApp, e um caminho de
  conversão paralelo ao WhatsApp já existente; o deep link é zero infraestrutura nova e leva direto
  pro fluxo que já funciona em produção.
- **Botão flutuante fixo (sticky) no canto da tela** — mais comum em sites comerciais, mas
  competiria visualmente com o CSP restritivo e o design já estabelecido do ADR-060; três pontos de
  entrada (topo, hero, rodapé) já cobrem a página inteira sem precisar de posição fixa.
- **Número como variável de Terraform** (`var.whatsapp_business_display_number`) — a copy do site
  já é editada como conteúdo estático (ADR-060); criar uma variável de infraestrutura só pra um
  número de telefone exibido em HTML adiciona indireção sem necessidade.

## Motivo
O usuário pediu um caminho real de conversão na landing page. `wa.me` é o mecanismo padrão do
próprio WhatsApp pra isso — sem exigir nenhuma peça de infraestrutura nova, sem duplicar lógica de
negócio, e entregando o visitante exatamente no fluxo (`WHATSAPP_INBOUND_SLICE`) que já está em
produção.

## Consequências
- 3 CTAs novos em `site/index.html` (topnav, hero, rodapé) + `.btn--whatsapp`/`--gold-strong` em
  `site/assets/styles.css`; +ADR-066. Nenhuma mudança em Python, Terraform ou infraestrutura.
- O número de telefone fica hardcoded na página publicada — se o WhatsApp Business trocar de
  número, é um commit de conteúdo (mesmo fluxo de deploy do ADR-060: `gsutil rsync` + invalidação
  de CDN no job `deploy`), sem exigir `plan`/`apply`.
- O país do número (`+55`) foi assumido pelo contexto do projeto (documentação em pt-BR, região
  `southamerica-east1`) — se estiver incorreto, corrigir é uma troca de string, sem impacto em
  nenhuma outra parte do sistema.

## Regra de revisão
Mudanças nesta decisão — em especial adicionar coleta de dado/analytics ao clique, trocar o deep
link por um formulário com backend próprio, ou mover o número pra uma variável de infraestrutura —
exigem novo ADR ou superseding ADR.
