---
status: pending
title: "`costRows.ts` — fonte única das linhas de custo, extraída do `CostSheet`"
type: frontend
complexity: high
---

# Task 4: `costRows.ts` — fonte única das linhas de custo, extraída do `CostSheet`

## Overview

Extrai a lógica de montagem das linhas de custo, hoje presa dentro de `CostSheet.tsx` na função
privada `corpoRico`, para um módulo puro novo `frontend/src/ui/costRows.ts`. É uma refatoração de
**risco zero de comportamento**: o `CostSheet` passa a importar do novo módulo e o DOM que ele
gera fica byte a byte igual. O widget do chat (task_05) vai importar do mesmo lugar, e é isso que
impede a divergência entre tela e chat de voltar a aparecer.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (invariante suprema).** O DOM renderizado pelo `CostSheet` MUST ficar **idêntico** ao de
  hoje: `.cost-sheet`, `.cost-row`, `.cost-row.total`, `.cost-line`, `.cost-warn`, `.cost-note`,
  mesma ordem, mesmos textos. `frontend/src/ui/CostSheet.test.tsx` MUST passar **sem uma linha de
  alteração** — se precisou mudar o teste, o comportamento mudou e a task está errada.
- **R2.** `frontend/src/ui/costRows.ts` MUST ser `.ts` **puro, sem JSX** (decisão 5 da seção 12 do
  `_techspec.md`). Consequência aceita: os dois avisos de CLI continuam como JSX em quem
  renderiza, com o **texto** vindo de constantes exportadas por `costRows.ts` para não duplicar
  redação.
- **R3 (exports exatos, C7 do `_techspec.md`).** MUST exportar: `NOTA_PADRAO`, a interface
  `CostRow`, a interface `CostInfoLike`, `costRows(info, count)`, `costWarn(info)` e
  `saldoInsuficiente(info, count)`.
- **R4 (regras preservadas verbatim de `corpoRico`, `CostSheet.tsx:94-140`).**
  - `n = Math.max(1, Number(count) || 1)`;
  - unitário = `unit_credits ?? credits` (hoje é só `credits`; o `??` é a extensão que aceita o
    `CostPreview`), lido com `Number(...)` e só quando `!= null`;
  - `total = Math.round(unit * n * 100) / 100`;
  - linha **"Modelo"** só quando há `model`; valor `` `${label || model}${variant ? ` · ${variant}` : ""}` ``;
  - linha **"Custo por geração"** só quando o unitário existe; valor `` `${unit} créditos${suf}` ``
    com `suf` = `" (CLI)"` para `source === "cli"`, `" (medido)"` para `"measured"`, `""` senão;
  - linha **"Quantidade"** só quando `n > 1`, valor `` `${n}×` ``;
  - linha **"Total estimado"** **sempre**, com `total: true`, valor `` `${total} créditos` `` ou
    `"indisponível"`;
  - linhas **"Saldo atual"** e **"Saldo depois"** só quando `balance.credits != null`; a segunda
    só quando o total existe, valor `` `${Math.round((saldo - total) * 100) / 100} créditos` ``.
- **R5.** `costWarn(info)` MUST devolver `"not_installed"` quando `balance.installed` é falso,
  `"logged_out"` quando instalado mas `logged_in` falso, e `null` quando instalado e logado —
  exatamente a precedência de hoje (`notInstalled` antes de `loggedOut`), inclusive o fato de que
  sem `balance` nenhum aviso sai.
- **R6.** `saldoInsuficiente(info, count)` MUST devolver `true` **somente** quando o saldo é
  conhecido (`balance.credits != null`) **e** o total é conhecido **e** `saldo < total`.
- **R7.** `CostInfoLike` MUST ser o superconjunto das duas fontes: o `CostPreview` do backend
  (task_01) e a resposta de `GET /api/…/creditos/cost` que o modo rico já consome. Campos:
  `model`, `label`, `variant`, `kind`, `credits`, `unit_credits`, `count`, `total`, `source`,
  `balance` e `balance_after`, todos opcionais.
- **R8 (compatibilidade de import).** `CostRow` MUST continuar sendo reexportado por
  `frontend/src/ui/CostSheet.tsx` e por `frontend/src/ui/index.ts` — nenhum import existente pode
  quebrar. `frontend/src/ui/index.ts` **só ganha** exports; nada é removido nem renomeado
  (`surface.test.ts` checa presença dos 28 membros).
- **R9.** `NOTA_PADRAO` hoje é uma **const de módulo não exportada** em `CostSheet.tsx:18`. Ela
  MUST passar a viver em `costRows.ts` e ser importada por `CostSheet.tsx`, com o texto
  byte-idêntico: `"Isso gasta créditos — o ilimitado do plano vale só na UI da Higgsfield."`
- **R10 (textos dos avisos).** Os dois avisos de CLI MUST ter o texto exportado de `costRows.ts`
  como constantes, para o widget do chat (task_05) reusar a mesma redação sem copiar. O **JSX**
  (com `<b>` e `<code>`) continua em `CostSheet.tsx`, byte a byte como hoje.
- **R11.** TypeScript estrito: nenhum `any`, nenhum `@ts-ignore`. `make frontend-verify` roda
  typecheck + lint + vitest.
- **R12.** Esta task MUST NOT rodar `make frontend-build` nem tocar `studio/web/dist/` — o bundle
  é regenerado uma vez só, no fim, pela task_07.

## Subtasks
- [ ] 4.1 Criar `frontend/src/ui/costRows.ts` com `NOTA_PADRAO`, os textos dos avisos, `CostRow`,
      `CostInfoLike`, `costRows`, `costWarn` e `saldoInsuficiente`, com um comentário no topo
      dizendo que este módulo é a **fonte única** das linhas de custo (mitigação do risco 3).
- [ ] 4.2 Escrever `frontend/src/ui/costRows.test.ts` cobrindo cada regra de R4, R5 e R6.
- [ ] 4.3 Reescrever `corpoRico` em `CostSheet.tsx` para delegar a `costRows` + `costWarn`,
      mantendo o mapeamento `"not_installed"`/`"logged_out"` → o JSX de hoje.
- [ ] 4.4 Importar `NOTA_PADRAO` de `costRows.ts` em `CostSheet.tsx` e apagar a const local.
- [ ] 4.5 Acrescentar os exports novos a `frontend/src/ui/index.ts`, sem remover nenhum.
- [ ] 4.6 Rodar `frontend/src/ui/CostSheet.test.tsx` **sem alterá-lo** e ver passar.
- [ ] 4.7 Rodar `make frontend-verify` inteiro.

## Implementation Details

Estado de hoje (231 linhas em `CostSheet.tsx`):
- `:18` — `const NOTA_PADRAO = "Isso gasta créditos — o ilimitado do plano vale só na UI da Higgsfield.";`
  (não exportada).
- `:20-25` — `export interface CostRow { label; value: ReactNode; total?: boolean }`.
- `:60-67` — `interface CostInfo` privada, com `credits`, `model`, `label`, `variant`, `source`,
  `balance?: { installed?; logged_in?; credits? }`. Note que ela **não** tem `plan`,
  `unit_credits`, `count`, `total` nem `balance_after` — `CostInfoLike` é o superconjunto.
- `:91` — `const NUM = (x: unknown) => (x == null ? null : Number(x));`
- `:94-140` — `function corpoRico(info, count): { rows: CostRow[]; warn: ReactNode }`, a lógica a
  extrair. O JSX dos dois avisos está em `:124-138`.
- `:194-208` — o modo rico do `useCostConfirm`, que chama `corpoRico(info as CostInfo, count)` nos
  dois ramos (sucesso e falha do fetch). Note que **falha do fetch chama `corpoRico(null, …)`** —
  `costRows(null, n)` MUST portanto devolver só a linha "Total estimado: indisponível", como hoje.

`frontend/src/ui/index.ts:54-55` hoje exporta `{ CostSheet, useCostConfirm }` e os tipos
`{ CostRow, CostSheetProps, RichCostOpts, SimpleCostOpts }` — acrescentar os novos ao lado.

`frontend/src/ui/surface.test.ts:27-28` lista `confirmCost: ui.useCostConfirm` e
`CostSheet: ui.CostSheet` entre os 28 membros, e só checa que não são `undefined`/`null`.
Um segundo `describe` lê `src/styles/style.css` e `src/styles/ui.css` do disco e afirma com
`toContain` que `.cost-sheet`, `.cost-row` etc. existem — **nenhuma folha de estilo é tocada por
esta task**, então esse bloco continua passando sozinho.

### Relevant Files
- `frontend/src/ui/CostSheet.tsx` — origem de `corpoRico` e `NOTA_PADRAO`.
- `frontend/src/ui/index.ts` — barrel de exports do design system.
- `frontend/src/ui/CostSheet.test.tsx` (126 linhas) — o oráculo desta task; **não editar**.
- `frontend/src/ui/surface.test.ts` — contrato dos 28 membros.

### Dependent Files
- `frontend/src/areas/chat/ChatDock.tsx` — passará a importar `costRows` (task_05).
- Qualquer tela que importe `CostRow` de `ui` — segue funcionando por R8.

### Related ADRs
- **ADR-016** — o gate de custo cujas linhas este módulo produz.
- **ADR-031 / ADR-032** — design system em `frontend/src/ui/`, ids/classes como contrato de QA.

## Deliverables
- `frontend/src/ui/costRows.ts` (novo, puro, sem JSX) e `frontend/src/ui/costRows.test.ts` (novo).
- `frontend/src/ui/CostSheet.tsx` delegando ao novo módulo, com DOM inalterado.
- `frontend/src/ui/index.ts` com os exports novos.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`. Casos inline, derivados dos critérios 7 e 8 da seção 9 do `_techspec.md`.

- [ ] **Snapshot de regressão (critério 7).** Para um `CostInfoLike` de referência
      (`{model:"nano_banana_2", label:"Nano Banana Pro", variant:"2k", credits:4, source:"cli",
      balance:{installed:true, logged_in:true, credits:118}}`) com `count = 3`, `costRows` devolve
      exatamente: Modelo `"Nano Banana Pro · 2k"`; Custo por geração `"4 créditos (CLI)"`;
      Quantidade `"3×"`; Total estimado `"12 créditos"` com `total: true`; Saldo atual
      `"118 créditos"`; Saldo depois `"106 créditos"` — nessa ordem.
- [ ] **`info` nulo.** `costRows(null, 1)` devolve **uma** linha: Total estimado `"indisponível"`,
      `total: true` (é o ramo de falha de fetch do `useCostConfirm`).
- [ ] **Sem modelo.** Sem `model`, a linha "Modelo" não aparece.
- [ ] **Sufixo da fonte.** `source:"cli"` ⇒ `" (CLI)"`; `"measured"` ⇒ `" (medido)"`;
      `"unknown"`/ausente ⇒ sem sufixo.
- [ ] **Quantidade só acima de 1.** `count = 1` ⇒ nenhuma linha "Quantidade"; `count = 2` ⇒ `"2×"`.
- [ ] **`count` inválido.** `count = 0`, `NaN` e negativo caem todos em `n = 1`.
- [ ] **`unit_credits` vence `credits`.** Com os dois presentes e diferentes, o unitário usado é
      `unit_credits`; só com `credits`, usa `credits` (compatibilidade com a rota antiga).
- [ ] **Total indisponível.** Unitário nulo ⇒ Total estimado `"indisponível"`, e **nenhuma** linha
      "Saldo depois", ainda que o saldo seja conhecido.
- [ ] **Saldo desconhecido.** `balance.credits` nulo ⇒ nem "Saldo atual" nem "Saldo depois".
- [ ] **Arredondamento.** Unitário `0.94` com `count = 3` ⇒ `"2.82 créditos"` (duas casas).
- [ ] **`costWarn` (R5).** `{installed:false}` ⇒ `"not_installed"`;
      `{installed:true, logged_in:false}` ⇒ `"logged_out"`;
      `{installed:true, logged_in:true}` ⇒ `null`; `balance` ausente ⇒ `null`.
- [ ] **`saldoInsuficiente` (R6).** saldo 10 e total 12 ⇒ `true`; saldo 20 e total 12 ⇒ `false`;
      saldo nulo ⇒ `false`; total nulo ⇒ `false`.
- [ ] **DOM do `CostSheet` intacto (critério 8).** `frontend/src/ui/CostSheet.test.tsx` passa sem
      nenhuma alteração no arquivo (verificar com `git diff --exit-code` nesse caminho).

## Success Criteria
- Every assigned test case implemented and passing
- `git diff --exit-code frontend/src/ui/CostSheet.test.tsx` sai limpo (o teste não foi tocado).
- `frontend/src/ui/costRows.ts` não contém JSX nem importa React em runtime (só `import type`).
- `make frontend-verify` verde (typecheck estrito, lint, vitest).
- `frontend/src/ui/index.ts` só ganhou linhas; `surface.test.ts` continua passando.
- `studio/web/dist/` **não** foi tocado por esta task.
