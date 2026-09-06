# ADR-038: Protocolo humano-no-laço do chat (`ui.ask` / `confirm_cost` / `open`)

**Status:** Aceito
**Data:** 2026-09-05
**Task-Id:** ADH-OS-20260905-04
**ADRs relacionados:** [ADR-004 (fidelidade ao curso)](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-016 (gate de custo)](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-036](./ADR-036-runtime-de-chat-via-claude-cli-em-processo-terceiro-modo.md), [ADR-037](./ADR-037-servidor-mcp-do-studio-como-cliente-http-da-propria-api.md)

## Contexto e Problema

O assistente conduz a criação, mas duas classes de decisão **não podem ser dele**: a **escolha
visual** (qual foto, qual take, qual ordem) e o **gasto** (toda geração paga). Se o agente
escolhesse a imagem ou disparasse geração paga sozinho, violaria o princípio do produto (o usuário
decide o que é bom) e o gate de custo (ADR-016). Ao mesmo tempo, reescrever a máscara de inpaint ou
a timeline dentro do chat duplicaria telas que já existem e são melhores para edição fina.

## Decisão

**Um protocolo humano-no-laço em que o agente pergunta e o browser responde**, mediado por HTTP +
WebSocket, sem o agente nunca decidir escolha visual nem gasto.

1. **A tool `ui.*` pausa o turno.** Rodando no subprocess do MCP (ADR-037), a tool faz
   `POST /api/chats/{id}/ask {payload}`. O router cria um `ask` (`uibridge.bridge`), empurra o
   pedido pelo WebSocket ao browser e **aguarda** a `asyncio.Future`. O browser mostra o widget,
   o usuário responde (`POST .../answer` ou pelo WS), a Future resolve e a tool devolve a escolha
   ao agente.
2. **Tipos de pergunta (payload `kind`).** `choose_images` (grade com seleção/ordenação),
   `choose_one`, `form`, `confirm_cost` (custo/saldo/modelo, dados da rota `cost`), `open`
   (navega para uma tela/modal existente e espera `ui.done`), `show`/`notify`. Onda A entrega a
   **ponte** (bridge + endpoints + fallback no dock); os widgets ricos e as tools `ui.*` entram na
   Onda B; `open`/`done` na Onda C.
3. **Gasto é sempre confirmado.** Nenhuma tool paga executa sem um `confirm_token` emitido por
   `ui.confirm_cost` (que chamou a rota `cost`). Sem browser (terminal), `ui.*` degrada para
   "pergunte em texto" — o `ask` só é acionado quando há `STUDIO_CHAT_ID` e WS conectado.
4. **Timeout, não trava.** `ui.ask` tem timeout longo (default 30 min); ao expirar devolve
   `{answered: false}` e o agente re-pergunta em texto. A aba mostra "aguardando você".

## Consequências

**Positivas**
- A decisão visual e o gasto ficam com o usuário, por construção — o agente não tem como pular.
- Edição fina reusa as telas existentes (via `open`), sem duplicação (respeita ADR-010).
- O mesmo mecanismo serve qualquer pergunta futura do agente.

**Negativas / custos**
- Uma tool paga bloqueia até o usuário responder — é o comportamento desejado, mas prende um
  turno; o timeout e o cancelamento (`/stop`) são a válvula.
- O contrato `open → done` exige que a tela alvo aceite parâmetros de abertura e publique conclusão
  (opt-in por tela, Onda C); telas que não implementarem apenas abrem e o agente pede aviso manual.

## Adendo (Wave 11 · F10) — o `confirm_token` do item 3 passou a existir

Card #91 / `ADH-OS-20260906-12`. FDD: `docs/domains/creditos/features/creditos-chat-fdd.md`.

O item 3 da Decisão diz que "nenhuma tool paga executa sem um `confirm_token` emitido por
`ui.confirm_cost`". Até esta wave isso era **letra morta**: `actions._paid` chamava
`ui.confirm_cost` e, vendo `ans["confirmed"]`, fazia direto o `POST` de geração. Não havia token
nenhum. Agora há.

- **Emissão.** `ui.issue_confirm_token(action, model)` gera um token opaco
  (`secrets.token_urlsafe(16)`) e só é chamado por `confirm_cost`, **apenas quando o usuário
  aprova** — logo é impossível haver aprovação sem token, e impossível haver token sem aprovação.
- **Escopo e validade.** `(action, model, chat_id)`, TTL de 900 s, **uso único**, no máximo um vivo
  por par por aba (uma emissão nova invalida a anterior). O escopo deliberadamente NÃO inclui
  `count` nem `pid`, que podem variar legitimamente entre a estimativa e a geração.
- **Consumo.** `_paid` chama `ui.consume_confirm_token(...)` antes do `POST` do `gen_path`. Token
  ausente, expirado, já usado, de outra ação, de outro modelo ou de outra aba bloqueia a geração
  com uma mensagem que ensina a saída (chamar a tool de novo).
- **Sigilo.** O token é estado **efêmero de processo** (um dict de módulo, como o registro de jobs
  em memória do ADR-006 — a ADR-003 não se aplica). Nunca vai a disco, nunca ao WebSocket, nunca ao
  modelo. Há teste afirmando que o valor não aparece no payload do `ask` nem no texto devolvido à
  tool, e nenhum log o registra.
- **Caminho terminal inalterado.** Sem `STUDIO_CHAT_ID` o gate continua sendo `confirm=true`
  explícito na chamada da tool, e nenhum token é exigido nem emitido.
- **Escape hatch.** A flag de módulo `ui.CONFIRM_TOKEN_REQUIRED` desliga a exigência sem reverter
  commit, caindo no comportamento anterior (só `confirmed: true`), caso o token venha a travar
  geração legítima.

O widget `confirm_cost` do item 2 também deixa de ser um cartão de duas linhas: `ui.confirm_cost`
ganha o parâmetro keyword-only `breakdown` com o `CostPreview` inteiro, e o dock renderiza as mesmas
linhas do `CostSheet` das telas pela mesma função pura (`frontend/src/ui/costRows.ts`). O parâmetro
é opcional e os campos antigos seguem no payload, então um dock antigo continua funcionando.

Coerente com esta ADR, o alerta de **saldo insuficiente** apenas avisa: o botão de aprovar continua
habilitado, porque quem decide gastar é o usuário.

## Adendo (Wave 11) — o agente pode mover a tela; escolher e gastar continuam sendo do usuário

Card #88 · `ADH-OS-20260906-10` · FDD `docs/domains/chat/features/chat-navigate-fdd.md`.

A decisão original deixou duas lacunas que a Wave 11 fecha. A primeira: sem uma tool de navegação,
o agente terminava uma etapa e o usuário ficava com a tela parada na etapa anterior, tendo de achar
a próxima no menu — o método do curso é uma sequência, e a ferramenta não a acompanhava. A segunda
está registrada acima como custo: "telas que não implementarem [conclusão] apenas abrem e o agente
pede aviso manual". Nenhuma tela publica conclusão, então todo `open` esperava um clique só para
dizer "terminei" algo que o guia do backend já sabia.

Fica registrado, **sem revogar nada da decisão acima**:

1. **Navegação automática pelo chat é permitida.** A tool `ui_navigate(target, reason)` emite um
   evento `{"kind": "navigate", "target", "reason"}` pela ponte e **não bloqueia** — não é um `ask`,
   não cria Future, não espera resposta. O agente pede; quem decide se a tela troca é o dock. O uso
   canônico é depois de uma `*_pick` bem-sucedida, com o `next_step` que ela devolveu no sufixo JSON.
2. **Escolha visual e confirmação de gasto continuam exigindo gesto humano, sem exceção.** Este
   adendo move a tela; ele não escolhe imagem, não ordena frames e não dispara geração paga. Os
   itens 1 e 3 da decisão seguem valendo na íntegra: `choose_images`/`choose_one`/`form` continuam
   pausando o turno, e nenhuma tool paga executa sem `confirm_token` de `ui.confirm_cost` (ADR-016).
   Navegar não é uma decisão do usuário sendo tomada pelo agente — é a mesma decisão, mostrada na
   tela certa.
3. **"Concluir" um `open` pode ser derivado do guia**, em vez de exigir um `ui.done` publicado pela
   tela, sob três limites cumulativos: só na **transição** para `done` (um `open` cuja etapa já
   estava `done` quando o cartão nasceu nunca é auto-respondido — o agente pediu edição fina de algo
   completo, e essa decisão continua do usuário); só nas telas **opt-in** `refs`, `mood` e `base`;
   e sempre pelo guia do backend, nunca por prontidão calculada no cliente (ADR-010 a). A resposta
   automática viaja marcada (`{done: true, auto: true}`) e o cartão diz que foi automática.
4. **O usuário mantém veto.** O toggle "seguir o assistente" no dock (ligado por padrão, persistido
   em `localStorage`) desliga a navegação automática a qualquer momento; desligado, nenhum evento do
   chat altera a rota e o cartão vira um botão "Ir agora". Etapa bloqueada nunca abre, mesmo com o
   toggle ligado: o dock recusa em voz alta e explica o que falta.

**Pendências levadas ao gate em lote da Wave 11 (card #88) e aceitas ali** — registro para
auditoria, conforme o gate 4 do `CLAUDE.md`:

- **P1 — flexibilização deste ADR.** O `done` automático faz um `ask` ser respondido **sem gesto
  humano**, o que contraria a leitura literal do item 2 da decisão (`open` "navega e espera
  `ui.done`"). Aceita nos limites do ponto 3 acima. Escolha visual e gasto seguem exigindo clique,
  sem exceção.
- **P2 — default do toggle.** "Seguir o assistente" nasce **ligado**: a tela pode trocar sozinha na
  primeira vez que o usuário usar o chat, antes de ele saber que o toggle existe. Aceita como está;
  inverter o default é trocar uma constante no dock, não um novo ADR.

**Fidelidade ao curso.** Navegar é mecânica da ferramenta, não etapa do método: nenhuma aula muda de
comportamento, nenhuma etapa nova nasce daqui. Tudo neste adendo é `[extensão]` (ADR-004), e o
prompt do sistema (`studio/chat/prompts/sistema.md`) descreve a regra nesses termos.
