---
status: completed
title: "`MediaCard` com ações e lightbox no dock do chat"
type: frontend
complexity: medium
---

# Task 5: `MediaCard` com ações e lightbox no dock do chat

## Overview
O dock do chat passa a renderizar o `ask` de `choose_images` com `actions`: cada imagem vira um
`MediaCard` com o botão da ação (clique responde o `ask` com o `value` exato), e clicar na imagem abre um
lightbox reusando `frontend/src/ui/Modal.tsx`, sem responder nada. `MediaCard` sai de dentro de
`ChatDock.tsx` para `frontend/src/areas/chat/MediaCard.tsx` (decisão auto-aceita 9), mantendo o ramo
`show` idêntico. É o Build Order **passo 5** e o consumidor do Contrato 4. O caminho sem `actions`
("Confirmar seleção (N)") continua intacto para os quatro `*_pick`.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST extrair `MediaCard` de `ChatDock.tsx` (L383-400) para `frontend/src/areas/chat/MediaCard.tsx`
  (export nomeado), preservando o DOM atual do ramo `show` (`.chat-msg.assistant > .chat-bubble.chat-media
  > .chat-media-title? + .chat-grid > img.chat-thumb | video.chat-thumb`).
- MUST dar ao `MediaCard` suporte a `actions` opcionais (`{label, value, for?}`) e a um lightbox: clique
  na imagem abre `Modal` (de `frontend/src/ui`) com a imagem em tamanho maior e **não** chama `onAnswer`;
  o botão de ação chama `onAnswer(askId, action.value)`.
- MUST fazer o ramo `choose_images` do `AskCard` (`ChatDock.tsx:438-464`) renderizar, quando
  `ev.actions` está presente e não vazio, um `MediaCard` por imagem com o botão cuja `for === im.id`
  (ou com par before/after de `ev.media` filtrado por `pair === im.id`, quando existir), mais os botões
  globais (sem `for`) abaixo da grade; manter "Confirmar seleção (N)" **apenas** quando `actions` está
  ausente.
- MUST respeitar `done` ("Respondido.") também no caminho com `actions`.
- MUST tipar os campos novos em `frontend/src/areas/chat/types.ts` (`AskAction`, `AskMediaItem` com
  `role`/`pair`, ou equivalentes) sem remover a index signature aberta de `ChatEvent`.
- MUST acrescentar CSS em `frontend/src/areas/chat/chat.css` **só por adição** (nenhuma classe renomeada
  ou removida; contrato com os cenários de QA).
- MUST NOT criar overlay/modal próprio (decisão auto-aceita 8) nem adicionar dependência npm.
- MUST **estender** `frontend/src/areas/chat/ChatDock.test.tsx` (F01 já o criou) — não recriar; manter
  os 6 `it` existentes verdes.
- MUST manter o recorte mínimo em `ChatDock.tsx` (Risco 3): só o ramo `choose_images`, o import do
  `MediaCard` e o `case "show"`; nada no composer, abas, socket ou ponte `state_changed`.
- MUST NOT registrar titularidade em `tests/test_adr010_fronteira_nucleo.py` nesta task (é da task_07,
  Build Order passo 8) e MUST NOT rodar `make frontend-build` aqui (o `dist/` é regenerado na task_07).
  A guarda ADR-010 fica vermelha entre esta task e a task_07 por desenho do Build Order — registrar,
  não "corrigir".
- Commits MUST usar `feat(base): … [extensão]` com trailer `Task-Id: ADH-OS-20260906-13`.
</requirements>

## Subtasks
- [x] 5.1 Criar `frontend/src/areas/chat/MediaCard.tsx` com o componente extraído, props para `actions`/`onAnswer`/`askId` opcionais e o lightbox com `Modal`.
- [x] 5.2 Trocar o `case "show"` do `Message` para importar o `MediaCard` extraído, sem mudar o DOM.
- [x] 5.3 Reescrever o ramo `choose_images` do `AskCard` com o caminho `actions` (cards + botões globais) e o caminho antigo intacto.
- [x] 5.4 Declarar os tipos novos em `types.ts` e acrescentar as classes CSS (ações do card, par antes/depois, imagem do lightbox) em `chat.css`.
- [x] 5.5 Estender `ChatDock.test.tsx` com os casos dos critérios 10 e 11 (instrumentar `FakeWS.send` para capturar o `answer`).
- [x] 5.6 Rodar `cd frontend && npm run typecheck && npm run lint && npx vitest run src/areas/chat` e depois `make frontend-verify`.
- [x] 5.7 Rodar `pytest tests/test_mcp_ui.py -q` (nada de Python muda; conferência) e registrar no commit/nota que `tests/test_adr010_fronteira_nucleo.py` só volta a passar na task_07.

## Implementation Details
- `frontend/src/areas/chat/ChatDock.tsx`: `MediaCard` local (L383-400, não exportado); `MediaItem`
  (L377-381); `AskImage`/`AskOption`/`AskField` (L402-416); `AskCard` (L419-569) com `askId` (L430),
  `done` early-return (L435), ramo `choose_images` (L438-464) que hoje responde sempre `{selected}`;
  `case "show"` (L368-369). `onAnswer` chega de `Conversation.respond` (L226-232) → `useChatSocket.answer`
  → `ws.send({type:"answer", ask_id, answer})` (`useChatSocket.ts:76-78`).
- `frontend/src/ui/Modal.tsx`: `Modal({title, subtitle?, actions?, onClose, children})`, controlado,
  `createPortal` em `document.body`, `role="dialog"`, `aria-label={title}`, Esc/backdrop fecham.
- `frontend/src/areas/chat/types.ts`: `ChatEvent` com `media?: unknown`, `images?: unknown` e index
  signature `[k: string]: unknown` (L56) — `ev.actions`/`ev.max` compilam, mas devem ganhar tipo.
- `frontend/src/areas/chat/chat.css`: `.chat-grid` (L232), `.chat-thumb` (L233, `aspect-ratio: 1/1` +
  `object-fit: cover`), `.chat-pick` (L234-235), `.chat-media`/`.chat-media-title` (L242-243),
  `.chat-send` (L201-212). Não há classe de lightbox — acrescentar.
- `frontend/src/areas/chat/ChatDock.test.tsx`: `FakeWS` (L37-51, `send()` no-op — instrumentar com
  `static sent: string[]`), `replay` (L54), `montarDock()` (L84-98), `chegaPeloSocket(ev)` (L101-103),
  `vi.mock("../../shell/events")` só para `emitStudioChange`. Um `ask` chega por `chegaPeloSocket` com
  `kind:"ask"`, `ask_id`, `widget:"choose_images"`, `images`, `media`, `actions`.
- Exemplo do evento `ask` estendido: `_techspec.md` §5 Contrato 4.

### Relevant Files
- `frontend/src/areas/chat/ChatDock.tsx` — `AskCard`, `Message`, `MediaCard` a extrair.
- `frontend/src/areas/chat/MediaCard.tsx` — NOVO; componente extraído com `actions` e lightbox.
- `frontend/src/areas/chat/types.ts` — tipos do evento `ask` estendido.
- `frontend/src/areas/chat/chat.css` — classes novas (só adição).
- `frontend/src/areas/chat/ChatDock.test.tsx` — ESTENDER (F01).
- `frontend/src/ui/Modal.tsx` — lightbox.
- `frontend/src/areas/chat/useChatSocket.ts` — `answer()` envia `{type:"answer", ask_id, answer}`.
- `.compozy/tasks/base-upscale-chat/_techspec.md` — §4 passos 9-10, §5 Contrato 4, §10 Risco 3 e 5, §12 decisões 5, 8, 9.

### Dependent Files
- `frontend/src/areas/chat/MessageMarkdown.tsx` / `.test.tsx` — F01; não tocar, mas o `Message` exportado continua sendo usado pelo teste de markdown.
- `studio/web/dist/` — bundle versionado; regenerado na task_07 (não aqui).
- `tests/test_adr010_fronteira_nucleo.py` — passa a acusar `frontend/` até a task_07 registrar a titularidade.
- `scripts/qa/cenarios/` — oráculo; nenhuma classe/ID do chat pode ser renomeado.

### Related ADRs
- ADR-038 — a escolha é do usuário; `actions` viajam no `ask` com `ask_id`.
- ADR-031/ADR-032 — núcleo do frontend e bundle versionado (titularidade e build na task_07).
- ADR-004 — `[extensão]`.

## Deliverables
- `frontend/src/areas/chat/MediaCard.tsx` com `actions` + lightbox (`Modal`); `ChatDock.tsx` consumindo-o no `show` e no `choose_images` com `actions`.
- Tipos em `types.ts`; CSS aditivo em `chat.css`.
- `ChatDock.test.tsx` estendido.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`: os casos abaixo são os critérios 10 e 11 da seção 9 do `_techspec.md`, escritos como
casos concretos em `frontend/src/areas/chat/ChatDock.test.tsx` (vitest + jsdom, `FakeWS`).

- [x] **Critério 10 (botão por ação)** — `ask` de `choose_images` com 1 imagem, `media` (before/after) e `actions` = ["Usar como imagem base" `for:"n1"`, "Manter a atual" global] renderiza exatamente 2 botões com esses rótulos, e **não** renderiza "Confirmar seleção".
- [x] **Critério 10 (clique responde com o value exato)** — clicar em "Usar como imagem base" faz `FakeWS.sent` conter `{type:"answer", ask_id:"<ask_id>", answer:{selected:["n1"]}}`; clicar em "Manter a atual" envia `answer:{selected:[], keep:true}`; após responder, o card mostra "Respondido.".
- [x] **Critério 10 (lightbox)** — clicar na imagem do card abre um `role="dialog"` (Modal) contendo um `img` com a `url` da imagem; `FakeWS.sent` continua vazio; Esc fecha o dialog.
- [x] **Critério 10 (par antes/depois)** — com `media` contendo `role:"before"` e `role:"after"` para `pair:"n1"`, o card de `n1` mostra as duas imagens com os rótulos "antes…"/"depois…"; sem `media` mostra só a imagem nova.
- [x] **Critério 11 (regressão dos `*_pick`)** — `ask` de `choose_images` **sem** `actions` (2 imagens, `max:null`) renderiza "Confirmar seleção (0)" desabilitado; clicar em 2 thumbs habilita "Confirmar seleção (2)"; clicar envia `answer:{selected:["a","b"]}`; nenhum `role="dialog"` é aberto ao clicar no thumb.
- [x] **`show` intacto** — evento `kind:"show"` com `media` de 2 imagens renderiza `.chat-media` com 2 `img.chat-thumb` e sem botão de ação.

## Success Criteria
- Every assigned test case implemented and passing
- `make frontend-verify` verde (typecheck + eslint + vitest, incluindo os 6 `it` pré-existentes de `ChatDock.test.tsx` e os de `MessageMarkdown.test.tsx`).
- `git diff --stat` limitado a `frontend/src/areas/chat/{ChatDock.tsx,MediaCard.tsx,types.ts,chat.css,ChatDock.test.tsx}`; `grep -c "className=\"chat-" chat.css` só cresce; nenhuma classe removida.
- Nenhum novo `import` de `frontend/src/shell/**` nem de `frontend/src/api/**` além dos já existentes no `ChatDock.tsx`.
- Commits com `feat(base): … [extensão]` e trailer `Task-Id: ADH-OS-20260906-13`, com nota de que a guarda ADR-010 fecha na task_07.
