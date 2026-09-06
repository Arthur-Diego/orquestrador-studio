---
status: completed
title: Telas de etapa e área de personagens assinando o barramento
type: frontend
complexity: medium
---

# Task 4: Telas de etapa e área de personagens assinando o barramento

## Overview

A fatia que o usuário enxerga: sete telas passam a assinar `useStudioChange` e a recarregar
sozinhas quando o chat mexe na etapa que elas mostram. É repetitivo por desenho — o mesmo padrão de
três linhas por tela — e é onde a regressão mora, porque cada tela tem o seu próprio `load()`, o
seu próprio `startPoll()` e, em alguns casos, buffers editáveis que **não** podem ser
sobrescritos.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1.** As sete telas MUST assinar o barramento com o seu próprio step:
  `studio/etapas/refs/ui/index.tsx` (`refs`), `studio/etapas/base/ui/index.tsx` (`base`),
  `studio/etapas/mood/ui/index.tsx` (`mood`), `studio/etapas/storyboard/ui/Ideation.tsx`
  (`storyboard`), `studio/etapas/storyboard/ui/Angles.tsx` (`storyboard`),
  `studio/etapas/animate/ui/index.tsx` (`animate`) e
  `frontend/src/areas/characters/CharactersArea.tsx` (`characters`).
- **R2.** Cada tela de plugin MUST passar o seu pid via `opts` — `{ pid: ctx.pid() }` ou o
  equivalente que a tela já usa para saber a campanha. `CharactersArea` **não** tem pid e MUST
  assinar sem `opts.pid` (aceita qualquer pid, incluindo `null`).
- **R3.** O callback de cada tela MUST reusar o `load()` (ou equivalente) que a tela **já tem**.
  MUST NOT criar uma segunda função de carga, MUST NOT duplicar chamadas de API e MUST NOT
  reimplementar polling: quando o `load()` detectar job `running`, o `startPoll()` existente da
  tela é que assume.
- **R4.** **Nenhum buffer editável pode ser sobrescrito.** Onde a tela tem `load(keepSel = true)`
  (refs, ~linha 134), o callback MUST usar a variante que preserva a seleção. Em
  `Ideation.tsx` o callback MUST recarregar apenas as listas de leitura (status, ideias,
  candidatas) e MUST NOT recarregar `scenes`, que é o buffer de texto editável do usuário. Nenhuma
  tela pode ganhar recarga automática de campo de texto em edição.
- **R5.** MUST NOT alterar classes CSS, ids de elemento, textos visíveis nem atributos ARIA de
  nenhuma tela. Os cenários de `scripts/qa/cenarios/` são o oráculo e o diff de `textContent`
  contra o baseline vigente tem de continuar vazio (ADR-004). MUST NOT editar nada sob
  `scripts/qa/cenarios/`.
- **R6.** MUST NOT migrar nenhuma tela para TanStack Query, MUST NOT introduzir `queryKey` novo e
  MUST NOT alterar a estrutura de estado existente das telas. A mudança é aditiva: um hook a mais.
- **R7.** MUST NOT alterar `frontend/src/shell/events.ts`, `frontend/src/areas/chat/**`,
  `frontend/src/api/**` nem qualquer arquivo Python.
- **R8.** `studio/etapas/refs/ui/index.test.tsx` MUST cobrir UT-19 sem rede: publicar no barramento
  e afirmar que a tela refez `GET /api/projects/p1/refs/candidates` para o pid certo e **não** o
  refez para outro pid. Se o arquivo de teste não existir, criá-lo seguindo o padrão dos testes de
  tela vizinhos.
- **R9.** TypeScript estrito: sem `any`, sem `@ts-ignore`, sem `eslint-disable` novo. Nenhuma
  dependência npm nova.
</requirements>

## Subtasks
- [x] 4.1 Ler a seção 3 (escopo), a seção 4 (fluxos alternativos) e o Risco 5 da seção 10 do
      `_techspec.md` — é o Risco 5 que dita a regra do buffer editável.
- [x] 4.2 Mapear, tela por tela, qual é a função de recarga existente e qual variante preserva
      seleção/edição.
- [x] 4.3 Ligar o hook nas cinco telas de etapa (`refs`, `base`, `mood`, `animate`) e nas duas do
      storyboard (`Ideation`, `Angles`).
- [x] 4.4 Ligar o hook em `frontend/src/areas/characters/CharactersArea.tsx`, sem filtro de pid.
- [x] 4.5 Escrever/estender `studio/etapas/refs/ui/index.test.tsx` para UT-19.
- [x] 4.6 Conferir com `git diff` que nenhuma classe, id, texto visível ou atributo ARIA mudou em
      nenhuma das sete telas.
- [x] 4.7 Rodar `make frontend-verify` e colar o output real.

## Implementation Details

O contrato do hook está na task_02 e no Contrato 4 da seção 5 do `_techspec.md`. O passo 8-9 do
fluxo principal (seção 4) descreve exatamente o que a tela de refs deve fazer, incluindo a entrada
no `startPoll` quando o job vier `running`.

Fatos do código atual, confirmados:

- `studio/etapas/refs/ui/index.tsx` — candidatas em `useState` (~62), `load()` com
  `keepSel` (~134-149), `startPoll()` (~151-171), `useEffect([pid])` (~174-210).
- `studio/etapas/base/ui/index.tsx` — mesmo padrão (~403-429 e ~611).
- `studio/etapas/storyboard/ui/Ideation.tsx` é o maior arquivo (2162 linhas) e o que tem o buffer
  editável `scenes` — é aqui que a regra R4 morde.
- `frontend/src/areas/characters/CharactersArea.tsx` — área global, sem `pid`.

O `StudioCtx` dos plugins expõe `pid()`; confira em `frontend/src/shell/plugin.ts` /
`frontend/src/shell/context.ts` o nome exato antes de usar.

### Relevant Files
- `studio/etapas/refs/ui/index.tsx` — a tela do sintoma do card; também a que ganha o teste.
- `studio/etapas/base/ui/index.tsx` — mesmo padrão de estado local.
- `studio/etapas/mood/ui/index.tsx`, `studio/etapas/animate/ui/index.tsx` — telas menores.
- `studio/etapas/storyboard/ui/Ideation.tsx`, `studio/etapas/storyboard/ui/Angles.tsx` — as duas
  telas do step `storyboard`; `Ideation` tem o buffer editável.
- `frontend/src/areas/characters/CharactersArea.tsx` — área global sem pid.
- `frontend/src/shell/events.ts` — o hook a assinar (task_02).
- `frontend/src/shell/plugin.ts`, `frontend/src/shell/context.ts` — o `ctx` dos plugins.

### Dependent Files
- `scripts/qa/cenarios/**` — oráculo; **não editar**, apenas não quebrar.
- `studio/web/dist/` — rebuild fora do runner.

### Related ADRs
- **ADR-004** — cenários de QA e baseline de `textContent` são o oráculo; nada de texto novo.
- **ADR-006** — o `startPoll` das telas permanece exatamente como está.
- **ADR-010 item a** — a tela recarrega dos seus próprios endpoints; prontidão continua vindo do
  guia do backend.
- **ADR-031 / ADR-032** — plugins de etapa e o núcleo do frontend.

## Deliverables
- As sete telas assinando `useStudioChange` com o step e o filtro de pid corretos.
- `studio/etapas/refs/ui/index.test.tsx` cobrindo UT-19.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Definição completa em `_tests.md`.

- **UT-19** a tela de refs recarrega ao receber o evento do seu step e do seu pid, e ignora evento
  de outro pid.

## Success Criteria
- Every assigned test case implemented and passing.
- `make frontend-verify` verde, com output real citado.
- Nenhuma classe, id, texto visível ou atributo ARIA alterado nas sete telas.
- Nenhum arquivo sob `scripts/qa/cenarios/`, `frontend/src/api/`, `frontend/src/areas/chat/` ou
  `studio/**/*.py` alterado.
- `Ideation.tsx` não recarrega `scenes` no callback.
