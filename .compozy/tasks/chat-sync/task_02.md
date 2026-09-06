---
status: completed
title: Barramento de mudanças do shell (`emitStudioChange` + `useStudioChange`)
type: frontend
complexity: medium
---

# Task 2: Barramento de mudanças do shell (`emitStudioChange` + `useStudioChange`)

## Overview

Cria `frontend/src/shell/events.ts`, o barramento em memória pelo qual o `ChatDock` avisa as telas
de etapa que algo mudou. É a peça que evita migrar sete telas para TanStack Query: quem já sabe
recarregar (`load()`) apenas passa a ser notificado. Módulo isolado, sem rede e sem `window`, com o
filtro por `step`/`pid` e o debounce de 400 ms que fecham as condições de corrida.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1.** `frontend/src/shell/events.ts` MUST exportar exatamente o Contrato 4 da seção 5 do
  `_techspec.md`: o tipo `EscopoDaMudanca`, a interface `MudancaDoStudio`, a interface
  `OpcoesDeAssinatura`, a função `emitStudioChange(m)` e o hook
  `useStudioChange(step, cb, opts?)`. Nomes e formas MUST bater letra por letra com o contrato —
  três outras frentes da wave (F06, F08, F11) consomem esta assinatura.
- **R2.** A implementação MUST usar um `Map<string, Set<...>>` de módulo. MUST NOT usar `window`,
  `CustomEvent`, `EventTarget` global, `localStorage` nem qualquer global do browser — o módulo tem
  de ser testável em jsdom sem instalar globais (ADR-008).
- **R3.** O filtro MUST ser: entrega só a assinantes do MESMO `step`; entre esses, ignora o evento
  quando `ev.pid` é não-nulo e diferente do `opts.pid` declarado. `ev.pid === null` MUST chegar a
  todos os assinantes do step, inclusive os que declararam um pid. `opts.pid` `undefined` MUST
  aceitar qualquer pid.
- **R4.** O debounce MUST ser por par `(pid, step)` do assinante, com janela default
  `DEBOUNCE_GUIA_MS` importada de `frontend/src/api/guide-sync.ts` (hoje 400), sobrescrevível por
  `opts.debounceMs`. Semântica: **o último evento da janela vence** e `cb` roda no máximo uma vez
  por janela. MUST NOT reusar a **classe** `AgendadorDeRefresh` — ela termina obrigatoriamente em
  `invalidateQueries(chaves.guia)` e não executa callback arbitrário; reuse apenas a constante.
- **R5.** `useStudioChange` MUST guardar `cb` em `useRef` para não reassinar a cada render, e o
  cleanup do `useEffect` MUST cancelar o timer pendente — desmontar antes do fim da janela não pode
  chamar `cb` nem causar `setState` após unmount.
- **R6.** `emitStudioChange` MUST ser síncrono e MUST isolar assinante que lança: o `throw` de um
  assinante não pode impedir os demais de receberem. MUST NOT engolir o erro silenciosamente sem
  deixar rastro no console de desenvolvimento.
- **R7.** MUST NOT alterar `frontend/src/api/guide-sync.ts`, `frontend/src/api/queries.ts` nem
  qualquer outro arquivo do shell nesta task. O único arquivo de produção criado é `events.ts`.
- **R8.** `frontend/src/shell/events.test.ts` MUST usar temporizadores falsos do vitest para
  UT-11/UT-13 e MUST NOT depender de `setTimeout` real (nada de `await sleep(500)`).
- **R9.** TypeScript estrito: MUST NOT usar `any`, `@ts-ignore` nem `eslint-disable` novo.
  `make frontend-verify` roda typecheck + lint + vitest.
</requirements>

## Subtasks
- [x] 2.1 Ler o Contrato 4 da seção 5 do `_techspec.md` e os fluxos alternativos da seção 4 que o
      barramento tem de satisfazer (outra campanha, rajada, dock fechado, unmount).
- [x] 2.2 Ler `frontend/src/api/guide-sync.ts` para importar `DEBOUNCE_GUIA_MS` e entender por que
      a classe `AgendadorDeRefresh` **não** serve aqui.
- [x] 2.3 Escrever `frontend/src/shell/events.ts`.
- [x] 2.4 Escrever `frontend/src/shell/events.test.ts` cobrindo UT-10…UT-14 com fake timers.
- [x] 2.5 Conferir o padrão dos testes vizinhos do shell (`estado.test.ts`, `toast.test.ts`,
      `host.test.tsx`) e seguir a mesma convenção de nomes em pt-BR.
- [x] 2.6 Rodar `make frontend-verify` (sem `--watch`) e colar o output real.

## Implementation Details

Contrato completo, incluindo os comentários de doc que cada símbolo deve carregar: seção 5,
Contrato 4 do `_techspec.md`. Justificativa das duas decisões auto-aceitas (constante em vez de
classe; terceiro parâmetro `opts`): mesma seção.

O barramento é do **shell** (`frontend/src/shell/`), não da área de chat e não da camada de API:
ele é consumido tanto por telas de plugin (que têm `pid`) quanto pela área global de personagens
(que não tem). Ele **não** conhece TanStack Query e **não** invalida nada — quem invalida o guia é
o dock, na task_03.

### Relevant Files
- `frontend/src/api/guide-sync.ts` — `DEBOUNCE_GUIA_MS` (linha 50) e a classe
  `AgendadorDeRefresh` (linha 109), que serve de referência de semântica mas **não** é reusada.
- `frontend/src/shell/toast.ts` e `frontend/src/shell/estado.ts` — módulos de shell pequenos com
  estado de módulo; seguir o mesmo estilo.
- `frontend/src/shell/toast.test.ts`, `frontend/src/shell/estado.test.ts` — padrão de teste.
- `frontend/src/shell/context.ts` — `useShell`, para entender o que o shell já expõe às telas.

### Dependent Files
- `frontend/src/areas/chat/ChatDock.tsx` — passa a publicar aqui (task_03).
- `studio/etapas/{refs,base,mood,storyboard,animate}/ui/*` e
  `frontend/src/areas/characters/CharactersArea.tsx` — passam a assinar aqui (task_04).

### Related ADRs
- **ADR-008** — testes sem navegador de verdade; o módulo evita globais por isso.
- **ADR-010 item a** — o barramento transporta um aviso, nunca estado de domínio nem prontidão.
- **ADR-031 / ADR-032** — `frontend/` é núcleo; a titularidade já foi declarada na task_01.

## Deliverables
- `frontend/src/shell/events.ts` (novo).
- `frontend/src/shell/events.test.ts` (novo).
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Definições completas em `_tests.md`.

- **UT-10** filtro por step e por pid.
- **UT-11** três eventos em 400 ms → uma chamada, com o último evento (fake timers).
- **UT-12** `pid: null` chega a assinante com pid declarado.
- **UT-13** unmount antes do fim do debounce não chama `cb`.
- **UT-14** assinante que lança não impede os demais.

## Success Criteria
- Every assigned test case implemented and passing.
- `make frontend-verify` verde (typecheck + lint + vitest), com output real citado.
- Nenhum arquivo de produção alterado além de `frontend/src/shell/events.ts`.
- Nenhuma referência a `window`, `document`, `CustomEvent` ou `EventTarget` em `events.ts`.
- Nenhum arquivo Python alterado.
