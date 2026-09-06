---
status: pending
title: "Dock do chat — widget `confirm_cost` rico, `CreditsChip` e refresh por tool paga"
type: frontend
complexity: high
---

# Task 5: Dock do chat — widget `confirm_cost` rico, `CreditsChip` e refresh por tool paga

## Overview

É a fatia que o usuário vê. Substitui o cartão de duas linhas do `confirm_cost` no `ChatDock` por
um cartão com as MESMAS linhas do `CostSheet` das telas (via `costRows`, da task_04), acrescenta o
aviso de CLI, o alerta de saldo insuficiente e a nota da aula 008; põe o `CreditsChip` no
cabeçalho do dock; e faz o saldo se refrescar sozinho depois de cada tool paga.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (fonte única, mitigação do risco 3).** O widget MUST importar `costRows`, `costWarn`,
  `saldoInsuficiente` e `NOTA_PADRAO` de `frontend/src/ui` (task_04). MUST NOT reimplementar
  nenhuma regra de linha de custo. Copiar a lógica é o defeito que a feature existe para corrigir.
- **R2 (compatibilidade para trás).** Um `ask` com `widget: "confirm_cost"` **sem** `breakdown`
  MUST renderizar o cartão antigo, de duas linhas (`Custo estimado` + `Modelo`), exatamente como
  hoje. A heurística `inferWidget` (`ChatDock.tsx:519-528`) MUST continuar funcionando: ela decide
  por `raw["credits"] !== undefined || raw["action"] !== undefined`, e esses campos seguem no
  payload.
- **R3.** Com `breakdown`, MUST renderizar as linhas Modelo, Custo por geração, Quantidade (só
  quando maior que 1), Total estimado, Saldo atual e Saldo depois, mais a nota da aula 008.
- **R4.** Quando `costWarn(breakdown)` não é `null`, MUST mostrar o aviso de CLI correspondente
  (não instalado / sem login), com a MESMA redação do `CostSheet` — texto vindo das constantes de
  `costRows.ts`, nunca redigido de novo.
- **R5 (critério 10).** Quando `saldoInsuficiente(breakdown, count)` é verdadeiro, MUST mostrar
  uma linha de alerta em `.chat-cost-warn` e o botão "Aprovar e gerar" MUST continuar
  **habilitado** — o alerta avisa, não bloqueia (ADR-038, decisão 13 da seção 12).
- **R6.** Os dois botões MUST continuar respondendo `onAnswer(askId, { confirmed: true })` e
  `{ confirmed: false }`, com os mesmos rótulos "Aprovar e gerar" e "Cancelar".
- **R7 (`CreditsChip`, critério 11).** MUST aparecer no cabeçalho do dock (`.chat-head`), mostrar
  saldo e plano no `title` e, ao clique, navegar para `#/creditos`. Usar o `CreditsChip` de
  `frontend/src/ui` — **não** criar um chip novo. Ele já expõe `refreshKey` para forçar releitura.
- **R8 (refresh, critério 12).** Ao chegar um `tool_result` de uma tool da lista de tools pagas,
  o dock MUST incrementar o `refreshKey` do chip **exatamente uma vez**, o que dispara
  `refreshCredits(true)` → `GET /api/creditos/balance?refresh=1`. Para `tool_result` de tool
  **não** paga, **nenhuma** releitura.
- **R9 (debounce, decisão 12 / risco 6).** O incremento MUST ter debounce de **1500 ms**, para dois
  `tool_result` pagos seguidos não empilharem dois subprocessos de 30 s.
- **R10 (isolamento de conflito, risco 4).** O mapa de tools pagas MUST viver em um módulo próprio
  `frontend/src/areas/chat/toolCredits.ts`, e o widget rico MUST ser um componente próprio dentro
  do `ChatDock.tsx`. Cinco frentes da wave tocam esse arquivo; a superfície de conflito tem de
  ficar mínima.
- **R11 (conteúdo do mapa).** As tools pagas são as que passam por `actions._paid`:
  `mcp__studio__mood_generate`, `mcp__studio__base_generate`,
  `mcp__studio__storyboard_scene_generate`, `mcp__studio__animate_generate` e
  `mcp__studio__music_generate`. O mapa MUST casar tanto o nome completo quanto a forma curta
  (`shortTool` em `ChatDock.tsx:530-533` troca o prefixo `mcp__studio__` por `studio.`).
- **R12 (CSS).** As classes novas MUST ser acrescentadas a
  `frontend/src/areas/chat/chat.css` (que hoje tem só `.chat-cost`, `.chat-cost-body`,
  `.chat-cost-row`, em `:236-238`). MUST NOT tocar `frontend/src/styles/style.css` nem
  `frontend/src/styles/ui.css` — são cópias byte-a-byte do vanilla e contrato de QA.
- **R13 (tipos).** `frontend/src/areas/chat/types.ts` MUST declarar o `breakdown` no `ChatEvent`.
  Os campos existentes (inclusive `cost?: number | null`, hoje sem consumidor) MUST NOT ser
  removidos. TypeScript estrito: nenhum `any`.
- **R14.** Esta task MUST NOT rodar `make frontend-build` nem tocar `studio/web/dist/`.
- **R15.** Os cenários de `scripts/qa/cenarios/` MUST NOT ser editados (só acrescentados, se for
  o caso).

## Subtasks
- [ ] 5.1 Criar `frontend/src/areas/chat/toolCredits.ts` com o conjunto de tools pagas e um
      predicado `isToolPaga(name)` que aceita as duas formas do nome.
- [ ] 5.2 Declarar o `breakdown` em `frontend/src/areas/chat/types.ts`.
- [ ] 5.3 Extrair o `confirm_cost` de `AskCard` (`ChatDock.tsx:429-457`) para um componente
      próprio, com o ramo rico (com `breakdown`) e o ramo legado (sem).
- [ ] 5.4 Renderizar as linhas de `costRows`, o aviso de `costWarn`, o alerta de
      `saldoInsuficiente` e a `NOTA_PADRAO`.
- [ ] 5.5 Acrescentar as classes novas a `frontend/src/areas/chat/chat.css`.
- [ ] 5.6 Pôr o `CreditsChip` no `.chat-head`, com o clique navegando para `#/creditos`.
- [ ] 5.7 Ligar o incremento debounced do `refreshKey` ao `tool_result` de tool paga.
- [ ] 5.8 Escrever `frontend/src/areas/chat/ChatDock.test.tsx` (novo) com os casos abaixo.
- [ ] 5.9 Rodar `make frontend-verify`.

## Implementation Details

Estado de hoje (`ChatDock.tsx`, 533 linhas):
- `:107-115` — o `.chat-head`, com `.chat-title` e dois `.chat-iconbtn` (novo chat, fechar). O
  chip entra aqui.
- `:287-323` — `Message()`, o switch por `ev.kind`. `tool_result` (`:306-311`) hoje renderiza
  `null` quando não é erro — é o ponto onde o gatilho do refresh se liga, **sem** mudar o que
  é renderizado.
- `:318-319` — `case "ask": return <AskCard .../>`.
- `:429-457` — o bloco `if (widget === "confirm_cost")` a substituir. Hoje é markup ad-hoc
  (`chat-ask chat-cost`, `chat-cost-body`, `chat-cost-row`) com apenas Custo estimado e Modelo,
  lendo `ev.credits`, `ev.model`, `ev.action` e `ev.detail`.
- `:519-528` — `inferWidget`. `:530-533` — `shortTool`.
- Os eventos chegam por `frontend/src/areas/chat/useChatSocket.ts:38-46`, cujo `onmessage` empurra
  qualquer `ChatEvent` para o array `events` sem tratar `kind` — a dispatch é toda em `Message()`.

`frontend/src/ui/credits.tsx` (101 linhas) já dá tudo o que o chip precisa:
`CreditsChip({id, className, refreshKey, onClick})` (`:76-101`) relê na montagem e a cada mudança
de `refreshKey`, chamando `refreshCredits(refreshKey > 0)` (`:81`); `creditsView` (`:53-65`) já
monta o `title` com plano e créditos. `refreshCredits(true)` (`:17-23`) bate em
`/api/creditos/balance?refresh=1` e devolve `{installed:false, logged_in:false}` em falha.

Atenção: `refreshCredits(refreshKey > 0)` significa que a **primeira** montagem (`refreshKey = 0`)
faz `?refresh=0` e só as releituras forçam `?refresh=1` — que é exatamente o que o critério 12
pede. Não mexer nesse arquivo.

### Relevant Files
- `frontend/src/areas/chat/ChatDock.tsx` — cabeçalho, `Message`, `AskCard`, `inferWidget`.
- `frontend/src/areas/chat/types.ts` (37 linhas) — `ChatEvent`.
- `frontend/src/areas/chat/chat.css` — `.chat-head` (`:50-83`), `.chat-cost*` (`:236-238`).
- `frontend/src/areas/chat/useChatSocket.ts` — origem dos eventos; **não** alterado.
- `frontend/src/ui/credits.tsx` — `CreditsChip`, `refreshCredits`, `creditsView`; **não** alterado.
- `frontend/src/ui/costRows.ts` — a fonte única (task_04).

### Dependent Files
- `frontend/src/ui/index.ts` — de onde os imports saem.
- `studio/mcp/ui.py` — produz o `breakdown` que este widget renderiza (task_02).

### Related ADRs
- **ADR-036** — o dock do assistente.
- **ADR-038** — escolha visual e gasto são do usuário; por isso o alerta de saldo não bloqueia.
- **ADR-016** §4 — o chip global de créditos; esta task acrescenta um **segundo** gatilho de
  refresh (o `tool_result` de tool paga), além do funil `progressJob` que a ADR descreve.
  Isso vira nota de adendo na ADR (fechamento de ciclo, fora desta task).

## Deliverables
- `frontend/src/areas/chat/toolCredits.ts` (novo).
- `ChatDock.tsx` com o widget rico, o chip no cabeçalho e o refresh debounced.
- Classes novas em `chat.css`; `breakdown` tipado em `types.ts`.
- `frontend/src/areas/chat/ChatDock.test.tsx` (novo).
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`. Casos inline, derivados dos critérios 9, 10, 11 e 12 da seção 9 do `_techspec.md`.
Vitest + Testing Library, `fetch` mockado, timers falsos para o debounce.

- [ ] **Cartão rico (critério 9).** Um `ask` com `widget:"confirm_cost"` e um `breakdown` completo
      (`count: 3`, saldo 118, total 12) renderiza, nesta ordem: Modelo, Custo por geração,
      Quantidade, Total estimado, Saldo atual, Saldo depois — e a nota da aula 008.
- [ ] **Quantidade omitida.** `breakdown.count = 1` ⇒ nenhuma linha "Quantidade".
- [ ] **Cartão legado (critério 9).** Um `ask` **sem** `breakdown` renderiza só as duas linhas de
      hoje (Custo estimado e Modelo) — regressão de compatibilidade.
- [ ] **Mesmas linhas que o `CostSheet` (mitigação do risco 3).** Para um mesmo `CostInfoLike`,
      a sequência de rótulos renderizada pelo widget do dock é igual à renderizada pelo
      `CostSheet` — um teste que roda os dois e compara.
- [ ] **Aviso de CLI (R4).** `balance:{installed:true, logged_in:false}` ⇒ o aviso de login
      aparece e as linhas Saldo atual / Saldo depois **não** aparecem.
- [ ] **Saldo insuficiente (critério 10).** `balance.credits = 5` e `total = 12` ⇒ o alerta
      aparece em `.chat-cost-warn` **e** o botão "Aprovar e gerar" continua habilitado
      (`expect(botao).not.toBeDisabled()`).
- [ ] **Total indisponível.** `total: null`, `source: "unknown"` ⇒ linha Total estimado mostra
      "indisponível" e o botão de aprovar continua ativo.
- [ ] **Aprovar e cancelar (R6).** Clicar "Aprovar e gerar" chama `onAnswer` com
      `{confirmed: true}`; "Cancelar" com `{confirmed: false}`.
- [ ] **Chip no cabeçalho (critério 11).** O `.chat-head` contém um `[data-credits-chip]`; o
      `title` traz plano e créditos; o clique leva a `#/creditos`.
- [ ] **Refresh por tool paga (critério 12).** Um `tool_result` de
      `mcp__studio__base_generate` dispara **exatamente uma** chamada a
      `/api/creditos/balance?refresh=1`.
- [ ] **Tool não paga não refresca (critério 12).** Um `tool_result` de `mcp__studio__guide`
      dispara **zero** chamadas de refresh.
- [ ] **Nome curto também casa (R11).** `tool_result` com o nome já encurtado
      (`studio.base_generate`) também dispara o refresh.
- [ ] **Debounce (R9).** Dois `tool_result` pagos dentro de 1500 ms disparam **uma** releitura, não
      duas (timers falsos).
- [ ] **`tool_result` de erro continua renderizando o erro.** O gatilho de refresh não muda o que
      `Message()` renderiza para `is_error: true`.

## Success Criteria
- Every assigned test case implemented and passing
- O mapa de tools pagas está em `toolCredits.ts`, não inline no `ChatDock.tsx`.
- Nenhuma regra de linha de custo foi reescrita: `ChatDock.tsx` importa `costRows`/`costWarn`/
  `saldoInsuficiente`/`NOTA_PADRAO` e não recalcula total, sufixo de fonte nem saldo depois.
- `git diff --exit-code frontend/src/styles/` sai limpo (folhas do vanilla intocadas).
- `git diff --exit-code scripts/qa/cenarios/` sai limpo.
- `make frontend-verify` verde.
- `studio/web/dist/` **não** foi tocado por esta task.
