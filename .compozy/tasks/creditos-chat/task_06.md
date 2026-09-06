---
status: pending
title: "`BalanceCard` — gasto hoje/projeto/total e a reconciliação explicada"
type: frontend
complexity: medium
---

# Task 6: `BalanceCard` — gasto hoje/projeto/total e a reconciliação explicada

## Overview

A área Créditos mostra hoje o saldo do CLI e o histórico local em cartões separados, sem dizer em
lugar nenhum que um não deriva do outro. Esta task põe, ao lado do saldo, os três números do
livro-caixa (hoje, neste projeto, total) e o parágrafo que explica por que os dois números não
batem — e por que essa reconciliação é impossível por construção.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (critério 19).** O `BalanceCard` MUST mostrar três números do livro-caixa: **hoje**,
  **neste projeto** (só quando há `pid`) e **total**; e o parágrafo que explica saldo Higgsfield
  versus histórico local.
- **R2 (fonte dos números).** Vêm do payload que a área já busca (`GET /api/creditos` ou
  `GET /api/projects/{pid}/creditos`): `summary.today_credits` / `summary.today_count` e
  `summary_global` (task_01). MUST NOT criar rota nova nem uma segunda chamada HTTP.
- **R3 (semântica do escopo).** Com `pid`, `summary` é o do projeto e `summary_global` é o geral —
  logo "neste projeto" sai de `summary.total_credits` e "total" de `summary_global.total_credits`.
  Sem `pid`, `summary` já é o global e a linha "neste projeto" **não** aparece.
- **R4 (texto da reconciliação, P6 do `_techspec.md`).** O parágrafo MUST dizer, em substância,
  que o saldo vem do CLI da Higgsfield e o gasto vem do livro-caixa local, que só registra o que o
  Studio gerou pelo CLI; geração feita na UI da Higgsfield consome plano e **não** aparece aqui.
  MUST NOT prometer nem insinuar reconciliação automática — inferir gasto pela variação do saldo
  seria invenção de método e violaria a ADR-004.
- **R5 (degradação).** Com o CLI ausente ou deslogado, os três números do ledger MUST continuar
  aparecendo (eles não dependem do CLI). Com o ledger vazio, MUST mostrar zero — nunca "—" nem
  vazio, nunca levantar.
- **R6 (não regredir o cartão).** As três mensagens de estado de hoje (não instalado, sem login,
  logado), o chip, o `.cr-saldo` e o botão `#crRefresh` ("Atualizar saldo") MUST continuar
  presentes com os mesmos ids/classes — são contrato dos cenários de QA.
- **R7.** As classes novas MUST seguir o prefixo `cr-` já usado na área. MUST NOT tocar
  `frontend/src/styles/style.css` nem `frontend/src/styles/ui.css`.
- **R8.** TypeScript estrito, nenhum `any`. Os tipos do payload da área MUST ser estendidos, não
  afrouxados.
- **R9.** Esta task MUST NOT rodar `make frontend-build` nem tocar `studio/web/dist/`.
- **R10.** Os cenários de `scripts/qa/cenarios/` MUST NOT ser editados.

## Subtasks
- [ ] 6.1 Estender o tipo do payload da área com `today_credits`/`today_count` em `summary` e com
      `summary_global`.
- [ ] 6.2 Acrescentar ao `BalanceCard` o bloco dos três números, respeitando a regra de escopo (R3).
- [ ] 6.3 Acrescentar o parágrafo de reconciliação.
- [ ] 6.4 Acrescentar as classes `cr-` novas ao CSS da área.
- [ ] 6.5 Estender `frontend/src/areas/creditos/CreditosArea.test.tsx` com o caso logado e o
      deslogado, sem quebrar os 6 testes que já existem.
- [ ] 6.6 Rodar `make frontend-verify`.

## Implementation Details

Estado de hoje (`frontend/src/areas/creditos/CreditosArea.tsx`, 616 linhas):
- `:138-149` — o `useQuery` que busca `/api/projects/{pid}/creditos` ou `/api/creditos` via
  `api(url)`, tipado como `Dashboard`.
- `:153-164` — `refreshSaldo`, que faz `GET /api/creditos/balance?refresh=1` e depois chama
  `window.Studio?.ui?.refreshCredits?.(false)` (escape hatch imperativo do shell). **Não mexer**
  nesse comportamento.
- `:236-295` — `BalanceCard({balance, refreshing, onRefresh})`. Monta `chip` e `msgTxt` pelos três
  estados (`!installed`, `!logged_in`, logado), depois
  `saldo = balance.logged_in ? (balance.credits ?? "?") : "—"`, e renderiza
  `section.cr-card.cr-balance` com `.cr-balance-main` (`.eyebrow`, `.cr-saldo`, chip),
  `p.cr-balance-msg` e o `button#crRefresh.ghost`.

O componente hoje recebe **só** `balance`. Ele vai precisar receber também os agregados — passar
por props novas a partir do `data` do `useQuery`, mantendo `BalanceCard` uma função pura de props
(é o que torna o teste barato).

`frontend/src/areas/creditos/CreditosArea.test.tsx` (174 linhas) já tem 6 testes em dois
`describe` (saldo/admin/custo/histórico, toggle de escopo, deep link sem campanha; e rótulo
"Biblioteca · <board>", rótulo "Biblioteca" sem nome, modelo sem custo medido). Estender, não
reescrever.

### Relevant Files
- `frontend/src/areas/creditos/CreditosArea.tsx` — `BalanceCard` (`:236-295`), `useQuery`
  (`:138-149`), tipo `Dashboard`.
- `frontend/src/areas/creditos/CreditosArea.test.tsx` (174 linhas) — os 6 testes existentes.
- O CSS da área (classes `cr-*`).

### Dependent Files
- `studio/creditos/service.py` — produz `summary_global` (task_01).
- `studio/common/settings.py` — produz `today_credits`/`today_count` (task_01).

### Related ADRs
- **ADR-016** — a tela de créditos e o livro-caixa.
- **ADR-004** — fidelidade ao curso: por isso a reconciliação é **explicada**, nunca inferida.

## Deliverables
- `BalanceCard` com os três números e o parágrafo de reconciliação.
- Tipos do payload estendidos; classes `cr-` novas.
- `CreditosArea.test.tsx` com os casos logado e deslogado.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`. Casos inline, derivados do critério 19 da seção 9 do `_techspec.md`.

- [ ] **Caso logado, com `pid` (critério 19).** Payload com `balance` logado (plano `creator`,
      118 créditos), `summary.today_credits = 18`, `summary.total_credits = 46` e
      `summary_global.total_credits = 312` ⇒ a tela mostra 118 no saldo, 18 em "hoje", 46 em
      "neste projeto" e 312 em "total", mais o parágrafo de reconciliação.
- [ ] **Caso global, sem `pid` (R3).** Sem `pid`, a linha "neste projeto" **não** aparece, e
      "total" sai de `summary.total_credits`.
- [ ] **Caso deslogado (critério 19).** `balance:{installed:true, logged_in:false}` ⇒ o saldo
      mostra `"—"` e o chip "sem login" como hoje, **e** os três números do ledger continuam
      visíveis com os seus valores.
- [ ] **CLI não instalado.** `balance:{installed:false}` ⇒ a mensagem de hoje continua, e os
      números do ledger aparecem.
- [ ] **Ledger vazio (R5).** `today_credits = 0` e `total_credits = 0` ⇒ mostra `0`, não `"—"`
      nem string vazia; nada levanta.
- [ ] **Parágrafo de reconciliação (R4).** O texto renderizado menciona o CLI da Higgsfield como
      origem do saldo e o livro-caixa local como origem do gasto, e diz que geração feita na UI da
      Higgsfield não aparece ali.
- [ ] **Não regrediu (R6).** `#crRefresh` continua presente e clicável, e as três mensagens de
      estado continuam saindo nos mesmos casos — os 6 testes existentes passam sem alteração.

## Success Criteria
- Every assigned test case implemented and passing
- Os 6 testes que já existiam em `CreditosArea.test.tsx` continuam passando sem edição.
- Nenhuma chamada HTTP nova: o `git diff` não acrescenta `api(` nem `useQuery` na área.
- `git diff --exit-code frontend/src/styles/` e `scripts/qa/cenarios/` saem limpos.
- `make frontend-verify` verde.
- `studio/web/dist/` **não** foi tocado por esta task.
