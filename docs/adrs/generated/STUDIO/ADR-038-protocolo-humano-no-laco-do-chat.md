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
