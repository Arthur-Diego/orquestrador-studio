---
status: completed
title: Interface do dock — digitando, status, chips, Parar, badge e CSS
type: frontend
complexity: high
---

# Task 5: Interface do dock — digitando, status, chips, Parar, badge e CSS

## Overview

Esta é a task que o usuário vê: a bolha "digitando", a linha de status `aria-live` que diz o que a
IA está fazendo agora, os chips de tool com spinner/✓/✗ e duração, o resultado de sucesso colapsado,
o botão Parar e o badge "●" no título da aba do navegador — mais o bloco de CSS com
`prefers-reduced-motion`. Ela consome o estado vivo da task 4 e os rótulos da task 3, e só renderiza.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- A bolha "digitando" (três pontos) MUST aparecer com o `turn_started` e sumir no primeiro texto do
  assistente.
- A linha de status MUST ter `role="status"` e `aria-live="polite"`, e MUST mostrar: "Pensando…" sem
  tool pendente; o rótulo humano de `toolLabels.ts` enquanto a tool está pendente; e
  "Aguardando geração (NN %)…" durante `job_wait` com `total` conhecido. Sem `pct`, o percentual é
  **omitido** e o `label` do servidor vira o detalhe (`_techspec.md` §4 fluxo B passo 4).
- O texto da linha de status MUST mudar no máximo a cada 2 s (a cadência do `tool_progress`), para
  não inundar o leitor de tela (critério 9).
- Cada `tool_call` MUST virar um chip com três estados: spinner enquanto pendente, ✓ quando o
  `tool_result` de mesmo `id` chega sem erro, ✗ quando chega com erro; o chip MUST mostrar a duração
  em segundos, calculada pelos `ts` dos eventos persistidos (`_techspec.md` §12 decisão 9).
- O conteúdo de `tool_result` de **sucesso** MUST ficar colapsado atrás do chip, expansível (hoje é
  simplesmente descartado); o de **erro** MUST continuar visível como hoje.
- `tool_result` sem `tool_call` correspondente: o chip órfão MUST NÃO ser renderizado, e o
  `tool_result` de erro continua aparecendo como hoje.
- Progresso órfão: ao receber `turn_ended`, chip ainda pendente MUST ser marcado como concluído, sem
  ✓ nem ✗.
- O botão Parar MUST aparecer **somente** entre `turn_started` e `turn_ended`, MUST chamar o `stop()`
  já exposto pelo hook, e MUST sumir ao chegar o `turn_ended`.
- O título do documento MUST ganhar o prefixo "● " enquanto houver turno em andamento e MUST voltar
  ao original quando todos terminarem — implementado **dentro** do `ChatDock`, sem arquivo novo, para
  limitar a superfície de conflito de rebase (`_techspec.md` §12 decisão 12).
- Evento desconhecido MUST continuar caindo no `default: return null` do `Message`, sem quebrar a
  renderização (compatibilidade aditiva).
- **NÃO** renomear nada existente: só acrescentar casos ao `switch` de `Message` e blocos novos no
  final dos componentes. O CSS novo MUST ficar num bloco **no fim** de `chat.css`, sem alterar
  nenhuma regra existente (`_techspec.md` §10 risco 5 — mitigação do conflito com F01/F03).
- Com `prefers-reduced-motion: reduce`, a bolha "digitando" e o spinner do chip MUST parar de animar
  e passar a um estado estático legível, seguindo o precedente já existente no fim de `chat.css`
  (o `@media` do `.chat-tab-dot.st-running`).
- `shortTool` MUST ser substituído por `toolLabel` no chip e na linha de status, mantendo o mesmo
  texto de fallback para tool desconhecida.
- Nenhuma dependência npm nova.
</requirements>

## Subtasks

- [x] 5.1 Consumir `turn` e `busy` do `useChatSocket` em `Conversation` (o `stop` já vem do hook e
      hoje é descartado no destructuring).
- [x] 5.2 Renderizar a bolha viva de delta como componente isolado, para não re-renderizar o log
      inteiro a cada flush.
- [x] 5.3 Renderizar a linha de status com `role="status"` e `aria-live="polite"`, derivando o texto
      do estado vivo (pensando × tool pendente × progresso com/sem percentual).
- [x] 5.4 Correlacionar `tool_call` ↔ `tool_result` por `id` e renderizar o chip com estado,
      duração e rótulo humano.
- [x] 5.5 Colapsar o conteúdo de `tool_result` de sucesso atrás do chip (expansível); manter o de
      erro visível.
- [x] 5.6 Acrescentar o botão Parar, visível apenas durante o turno.
- [x] 5.7 Acrescentar o badge "● " no `document.title` durante o turno, restaurando o título original
      no fim e no unmount.
- [x] 5.8 Trocar `shortTool` por `toolLabel` no chip e na linha de status.
- [x] 5.9 Acrescentar o bloco de CSS novo **no fim** de `chat.css`, com o `@media
      (prefers-reduced-motion: reduce)` correspondente.
- [x] 5.10 Criar `frontend/src/areas/chat/ChatDock.test.tsx` com os casos atribuídos.

## Implementation Details

Modificar `frontend/src/areas/chat/ChatDock.tsx` e `frontend/src/areas/chat/chat.css`; criar
`frontend/src/areas/chat/ChatDock.test.tsx`.

**Atenção ao conflito de rebase previsto** (`_techspec.md` §10 risco 5): a frente F01
(chat-markdown) mexe no **corpo da bolha** do `Message` (renderização via `MessageMarkdown`) e a
frente F03 (chat-sync) mexe no **handler do socket**. Esta task mexe nos **chips e no status**.
Manter as três regiões separadas e não renomear nada é o que torna o rebase uma inserção. Se, no
rebase, a bolha viva de delta puder renderizar via `MessageMarkdown` (F01 já integrada), preservar as
duas intenções.

O `busy` já existente em `Conversation` (o `useMemo` com a heurística) passa a vir do hook; a
fórmula heurística migrou para a task 4 e **não** deve ficar duplicada aqui.

Consultar `_techspec.md`: §4 fluxos A, B e C, §5 contrato 7, §6 (matriz de erros: `tool_result`
órfão, progresso órfão), §9 critérios 1, 2, 5, 6, 7, 9, 10 e 17, §11 ordens 7 e 8.

### Relevant Files

- `frontend/src/areas/chat/ChatDock.tsx` — `Conversation` (composer, quick, log), `Message`
  (`switch` por `kind`), `shortTool` no fim do arquivo.
- `frontend/src/areas/chat/chat.css` — 211 linhas; o precedente de `prefers-reduced-motion` está no
  fim, no `@media` do `.chat-tab-dot.st-running`.
- `frontend/src/areas/chat/useChatSocket.ts` — o estado vivo `turn`, `busy` e `stop` (task 4).
- `frontend/src/areas/chat/toolLabels.ts` — `toolLabel` (task 3).
- `frontend/src/ui/` — design system: componentes e convenções de id/classe/ARIA a reaproveitar.
- `frontend/src/shell/host.test.tsx` — padrão de teste de componente React desta base.

### Dependent Files

- `studio/web/dist/` — o bundle precisa ser reconstruído (task 6).
- Frente F01 (chat-markdown) — toca `Message` na região da bolha; conflito de rebase previsto.
- Frente F09 (chat-audio) — toca o mesmo trecho de composer.

### Related ADRs

- ADR-038 (humano no laço) — o botão Parar é ação humana; nenhum elemento novo decide nada sozinho.
- ADR-031/032 — o bundle é versionado; a UI de área vive em `frontend/src/areas/`.
- ADR-010 — titularidade de núcleo (`frontend/`) declarada na task 1.
- ADR-004 — fidelidade ao curso: a mudança é de feedback, não de método.

## Deliverables

- Bolha "digitando", linha de status `aria-live`, chips com estado e duração, resultado de sucesso
  colapsado, botão Parar e badge "●" no título.
- Bloco de CSS novo no fim de `chat.css`, com `prefers-reduced-motion`.
- `frontend/src/areas/chat/ChatDock.test.tsx` novo.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [x] T-DK-01 — bolha "digitando" aparece e some na hora certa.
- [x] T-DK-02, T-DK-03, T-DK-04 — a linha de status em cada estado (pensando, tool pendente,
      progresso com e sem percentual).
- [x] T-DK-05 — `role="status"` e `aria-live="polite"`.
- [x] T-DK-06, T-DK-07 — chip com três estados e duração; sucesso colapsado, erro visível.
- [x] T-DK-08 — botão Parar: ausência fora do turno, presença durante, chamada de `stop`, sumiço no
      `turn_ended`.
- [x] T-DK-09 — badge "● " no título do documento.
- [x] T-DK-10 — evento desconhecido cai no `default` sem quebrar.
- [x] T-CSS-01, T-CSS-02 — `prefers-reduced-motion` desliga as animações mantendo a informação; o
      bloco novo fica no fim do arquivo, sem alterar regra existente.
      **Implementados em `tests/test_chat_css_feedback.py` (pytest), não no `ChatDock.test.tsx`**:
      são asserções sobre o ARQUIVO, e o Vitest não o lê — roda com `css: false` (o import da folha
      vira módulo vazio, `?raw` inclusive) e o projeto npm não tem `@types/node`, sendo que a task
      proíbe dependência npm nova. Mesmo precedente de `tests/test_chat_tool_labels.py` (task 3),
      que também vigia um arquivo do frontend a partir do pytest. A guarda fixa o sha256 das 211
      linhas originais de `chat.css`, o que prova "sem alterar nenhuma regra existente".

## Success Criteria

- Every assigned test case implemented and passing.
- `make frontend-verify` verde (typecheck estrito + lint + vitest).
- `git diff` de `chat.css` mostra **apenas** acréscimo no fim do arquivo.
- `git diff` de `ChatDock.tsx` não contém renomeação de símbolo existente.
- Nenhum `console.error` durante os testes do dock.
