---
status: pending
title: Contratos puros do frontend — decisão de navegação, áreas globais no router e barramento de intenção
type: frontend
complexity: medium
---

# Task 2: Contratos puros do frontend — decisão de navegação, áreas globais no router e barramento de intenção

## Overview

Esta task entrega os três contratos que o dock vai consumir, todos como código puro e testável sem
React de componente: a função de decisão "navego ou recuso, e com que texto", o `navigate` do shell
passando a montar as áreas globais (contrato **consumido pela frente F12**) e o barramento sticky
de intenção de abertura (`emitNavIntent`/`useNavIntent`). Isolar essa lógica é a mitigação do risco
R3 do `_techspec.md`: o `ChatDock.tsx` é o arquivo mais disputado da wave, e quanto menos lógica
morar nele, menor o conflito de rebase.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- A decisão de navegação MUST viver em `frontend/src/areas/chat/navigate.ts` (arquivo novo) como
  função(ões) **pura(s)**: sem React, sem rede, sem `location`, sem `localStorage`. Entrada: alvo,
  `pid`, catálogo de etapas (`Step[]`) e agregado do guia (`GuideAll | null`). Saída: uma decisão
  discriminada (navegar × recusar) com o texto de recusa pronto.
- A decisão MUST separar **navegável** (etapa no catálogo `/api/steps` com `status === "ready"`) de
  **liberada** (guia daquela etapa com `status !== "blocked"`), com textos de recusa DISTINTOS —
  mitigação do risco R5.
- A decisão MUST NOT derivar prontidão: só compara campos que o backend mandou (ADR-010 item a).
- Áreas globais aceitas MUST ser exatamente `MB_ROUTE` (`moodboards`), `CHAR_ROUTE` (`characters`) e
  `CR_ROUTE` (`creditos`), lidas de `frontend/src/shell/constants.ts` — nunca strings literais
  duplicadas. Área global MUST navegar sem consultar o guia e MUST funcionar sem `pid`.
- `target` vazio, não string, ou com `/` fora das áreas globais MUST ser recusado.
- Guia indisponível (`GuideAll` nulo) com etapa navegável MUST resultar em navegar, sem recusa
  (E8: o guia é informativo).
- `navigate` de `frontend/src/shell/router.ts` MUST passar a montar `#/moodboards[/<sub>]`,
  `#/characters[/<sub>]` e `#/creditos` (sub-rota de `creditos` ignorada), mantendo a **assinatura
  inalterada** `(target: string, opts?: { pid?: string; replace?: boolean }) => void`.
- A gramática do hash MUST NOT mudar: nada de query string, nada de segmento novo. Toda chamada
  existente MUST continuar produzindo exatamente o mesmo hash de hoje.
- `navigate` para área global MUST funcionar mesmo com `pidRef` nulo (a guarda `if (!p)` de hoje
  passa a valer só para alvo de campanha) e MUST respeitar `opts.replace`.
- O barramento MUST ser acrescentado a `frontend/src/shell/events.ts` (arquivo da F03), exportando
  `NavIntent`, `emitNavIntent(intent)` e `useNavIntent(target, cb)` conforme o Contrato 6 da §5 do
  `_techspec.md`. A intenção é **sticky de um disparo**: consumir limpa; publicar duas vezes antes
  do consumo mantém só a última; um consumidor com `target` diferente não consome.
- O código existente de `events.ts` (`emitStudioChange`/`useStudioChange`, F03) MUST NOT mudar de
  comportamento; o arquivo só cresce.
- A task MUST NOT tocar `ChatDock.tsx` (é a task 3) nem regenerar `schema.ts`/`openapi.json`.
</requirements>

## Subtasks

- [ ] 2.1 Ler `frontend/src/api/types.ts` (`Step`, `Guide`, `GuideAll`, `StepStatus`) e
      `frontend/src/shell/constants.ts` para fixar o vocabulário exato.
- [ ] 2.2 Criar `frontend/src/areas/chat/navigate.ts` com o tipo de decisão e a função pura,
      cobrindo os casos A2–A6 e E4–E10 da §4/§6 do `_techspec.md`, com os textos de recusa
      literais que o `_tests.md` especifica.
- [ ] 2.3 Criar `frontend/src/areas/chat/navigate.test.ts` com os casos UT-10..UT-20.
- [ ] 2.4 Estender `navigate` em `frontend/src/shell/router.ts` para as áreas globais, sem tocar a
      resolução de rota (o efeito que lê o hash já entende essas rotas hoje).
- [ ] 2.5 Acrescentar os casos UT-21..UT-27 a `frontend/src/shell/router.test.ts`, reusando as
      fixtures `PROJECTS`/`STEPS` de `frontend/src/shell/test-utils.tsx` e o padrão
      `renderHook` + `history.replaceState` que o arquivo já usa.
- [ ] 2.6 Acrescentar `NavIntent`/`emitNavIntent`/`useNavIntent` a `frontend/src/shell/events.ts`,
      documentando por que a intenção é sticky (a corrida entre navegar e montar a tela).
- [ ] 2.7 Acrescentar os casos UT-28..UT-32 a `frontend/src/shell/events.test.ts`, mantendo o
      padrão de `vi.useFakeTimers()` do arquivo e sem quebrar nenhum teste existente.
- [ ] 2.8 Rodar `make frontend-verify` (typecheck + lint + vitest, sem `--watch`) e registrar o
      output real.

## Implementation Details

Arquivos a criar: `frontend/src/areas/chat/navigate.ts`, `frontend/src/areas/chat/navigate.test.ts`.
Arquivos a modificar: `frontend/src/shell/router.ts`, `frontend/src/shell/router.test.ts`,
`frontend/src/shell/events.ts`, `frontend/src/shell/events.test.ts`.

**`router.ts` hoje.** `navigate` (linhas ~60-80) faz `const p = opts?.pid ?? pidRef.current; if (!p)
{ forcar(); return; }` e monta `#/${encodeURIComponent(p)}/${encodeURIComponent(target)}`. As áreas
globais precisam de um ramo ANTES dessa guarda, montando `#/<prefixo>[/<sub>]` com o mesmo cuidado
de `encodeURIComponent` por segmento, e preservando o resto do corpo (comparação com
`location.hash`, `history.replaceState` no modo `replace`, `location.hash = h` caso contrário,
`forcar()` quando o hash já é o alvo). `pidRef` **não** é limpo ao entrar numa área global — o
efeito de resolução já preserva o `pid` corrente (`setRota({..., pid: pidRef.current, ...})`).

**Vocabulário do guia.** `Guide.status` é `StepStatus` (`todo | in_progress | done | blocked |
unknown`, `frontend/src/api/types.ts`), e o agregado `GuideAll` traz `steps: Guide[]`. O catálogo
`Step.status` é só `"ready" | "soon"`. São duas fontes distintas, e é isso que a decisão precisa
manter separado.

**Testes.** `frontend/src/shell/router.test.ts` já usa `renderHook`/`waitFor` de
`@testing-library/react`, as fixtures `PROJECTS`/`STEPS` de `./test-utils` e
`history.replaceState(null, "", "#…")` em `beforeEach`/`afterEach`. `frontend/src/shell/events.test.ts`
usa `vi.useFakeTimers()` em todos os testes. O setup global (`frontend/src/setupTests.ts`) só
instala os matchers do jest-dom: qualquer stub é local ao teste (ADR-008).

### Relevant Files

- `frontend/src/shell/router.ts` — `navigate` e a resolução de rota que já entende as áreas globais.
- `frontend/src/shell/router.test.ts` — padrão de teste do roteador e fixtures a reusar.
- `frontend/src/shell/test-utils.tsx` — fixtures `PROJECTS` e `STEPS` (`refs`/`mood`/`base` `ready`,
  `prospect` `soon`), exatamente o que os casos de decisão precisam.
- `frontend/src/shell/constants.ts` — `MB_ROUTE`, `CHAR_ROUTE`, `CR_ROUTE` e o tipo `Area`.
- `frontend/src/shell/events.ts` — arquivo da F03 que recebe o barramento de intenção.
- `frontend/src/shell/events.test.ts` — padrão de teste do barramento (fake timers).
- `frontend/src/api/types.ts` — `Step`, `Guide`, `GuideAll`, `StepStatus`.
- `frontend/src/setupTests.ts` — o que o setup global instala (só jest-dom).

### Dependent Files

- `frontend/src/areas/chat/ChatDock.tsx` — consumidor dos três contratos (task 3).
- `frontend/src/shell/Shell.tsx` — passa `rota.navigate` ao contexto (`shellApi.navigate`); nenhuma
  mudança é necessária ali, mas o comportamento novo chega ao dock por esse caminho.
- Frente F12 (`chat-moodboards`) — consome o `navigate` com áreas globais; a assinatura e a tabela
  de alvos da §5 (Contrato 5) do `_techspec.md` são normativas para ela.

### Related ADRs

- ADR-010 item a — prontidão de etapa vem sempre do guia do backend.
- ADR-013 / ADR-016 / ADR-039 — as três áreas globais e seus prefixos reservados de rota.
- ADR-031 / ADR-032 — o núcleo do frontend e o bundle versionado.

## Deliverables

- `frontend/src/areas/chat/navigate.ts` com a decisão pura e os textos de recusa.
- `navigate` do shell montando `#/moodboards[/<mbid>]`, `#/characters[/<cid>]` e `#/creditos`, com
  assinatura e comportamento de campanha inalterados.
- `NavIntent`, `emitNavIntent` e `useNavIntent` em `frontend/src/shell/events.ts`.
- `make frontend-verify` verde, com os 411 testes atuais preservados.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Cases assigned from `_tests.md`, the test contract — read each ID's full definition there before
writing tests.

- [ ] UT-10, UT-11, UT-12, UT-13, UT-14, UT-15, UT-16, UT-17, UT-18, UT-19, UT-20 — decisão pura de
      navegação: navegável × liberada, áreas globais, alvos inválidos, sem campanha, guia ausente.
- [ ] UT-21, UT-22, UT-23, UT-24, UT-25, UT-26, UT-27 — `navigate` do shell com áreas globais e a
      não-regressão dos alvos de campanha.
- [ ] UT-28, UT-29, UT-30, UT-31, UT-32 — barramento de intenção sticky e a não-regressão do
      barramento de mudanças da F03.

## Success Criteria

- Every assigned test case implemented and passing.
- `make frontend-verify` verde (typecheck + lint + vitest), com contagem de testes ≥ 411 + os novos.
- `git status --porcelain -- frontend/src/api/schema.ts frontend/openapi.json` vazio.
- `frontend/src/areas/chat/ChatDock.tsx` intocado por esta task.
- Nenhum cenário de `scripts/qa/cenarios/` editado.
