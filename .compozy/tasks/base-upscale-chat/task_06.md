---
status: completed
title: "Tela Base: cobertura da recarga por evento e antes/depois por `source_id`"
type: frontend
complexity: low
---

# Task 6: Tela Base: cobertura da recarga por evento e antes/depois por `source_id`

## Overview
Fecha o Build Order **passo 6**, que está **parcialmente pronto**: a tela Base já assina
`useStudioChange("base", () => void load().catch(...), { pid })` (`studio/etapas/base/ui/index.tsx:614-627`,
F03 integrada) com debounce por par `(pid, step)` vindo de `frontend/src/shell/events.ts`. O que falta é
(a) provar o critério 12 em `studio/etapas/base/ui/index.test.tsx` — hoje **não há nenhum** teste de
recarga por evento, filtro de `pid` ou colapso de rajada para a etapa `base` — e (b) fazer o bloco
"Modificação, antes → depois" (`#baseGenResult`) ler `source_id` da candidata (task_01) em vez de
inferir a origem pela cadeia selecionada no cliente, mantendo a heurística atual só quando `source_id`
é `null` (critério 13).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST NOT acrescentar segunda assinatura de `useStudioChange`, NÃO reimplementar debounce e NÃO mexer no
  bloco `index.tsx:614-627` nem em `frontend/src/shell/events.ts` (F03). O critério 12 é coberto por
  **testes**, não por código de produção.
- MUST acrescentar `source_id?: string | null` ao tipo `Candidate` da tela e fazer a origem do par
  antes/depois ser resolvida **por candidata do resultado**: se `c.source_id` existe e aponta para uma
  candidata carregada, o "antes" é essa candidata (URL `ctx.files(file)`, rótulo `KINDS[kind]`);
  se `source_id` é `null`/ausente ou a origem sumiu, cai na heurística atual de `originFor(kind)`.
- MUST manter o DOM do bloco (`#baseGenResult`, `.bs-result`, `.pair`, `.ba`, `figure`/`figcaption`,
  `.arrow`, `.link.dl`) e os textos "antes · …"/"depois · …" (cenários de QA são oráculo).
- MUST preservar `finalV` (cache-bust em `load()`, L414) e o `useEffect([pid])` (L598-612) intactos.
- MUST cobrir no `index.test.tsx` da etapa: recarga com evento `{pid:P, step:"base", scope:"candidates"}`,
  ignorar `{pid:Q}`, e **uma única** recarga para uma rajada de 3 eventos em < 400 ms (padrão de
  `studio/etapas/refs/ui/index.test.tsx:172-205`, contando chamadas de `api`/`fetch` a `/base/candidates`).
- MUST NOT tocar `frontend/**` nem `studio/web/**` (esta task fica fora do núcleo; `studio/etapas/base/`
  não está em `NUCLEO_PREFIXOS`); o bundle é regenerado na task_07.
- Commits MUST usar `feat(base): … [extensão]` com trailer `Task-Id: ADH-OS-20260906-13`.
</requirements>

## Subtasks
- [x] 6.1 Acrescentar `source_id` ao tipo `Candidate` da tela e resolver a origem do antes/depois por candidata (`source_id` → fallback `originFor`).
- [x] 6.2 Conferir que `load()` continua reconstruindo `chain`/`finalV` e que o bloco `#baseGenResult` sobrevive à recarga por evento (`resultIds` não é limpo por `load()`).
- [x] 6.3 Escrever em `studio/etapas/base/ui/index.test.tsx` os testes do critério 12 (recarga no pid certo, ignora outro pid, rajada → 1 recarga) usando `emitStudioChange` real e `DEBOUNCE_GUIA_MS`.
- [x] 6.4 Escrever os testes do critério 13 (antes/depois por `source_id`; fallback quando `null`).
- [x] 6.5 Registrar no corpo do commit a evidência do critério 12: a assinatura já existia (F03, `index.tsx:614-627`) e a cobertura foi acrescentada aqui.
- [x] 6.6 Rodar `cd frontend && npx vitest run ../studio/etapas/base/ui` (ou `npm test -- base`), depois `make frontend-verify`.

## Implementation Details
- `studio/etapas/base/ui/index.tsx`:
  - `useStudioChange` importado em L27 de `../../../../frontend/src/shell/events`; assinatura em
    L614-627 — **não mexer**.
  - `load()` L404-430 (GET `/api/projects/<pid>/base/candidates`, bump de `finalV` em L414, reconstrói
    `chain`, não toca `resultIds`).
  - `originFor(kind)` L475-490 — heurística atual (`label → clean → situation` a partir de `st.chain`);
    `results`/`origin`/`depoisLbl` calculados em L639-646; JSX de `#baseGenResult` em L1176-1210
    (`origin` hoje é único para todos os resultados — passa a ser por candidata).
  - Tipo `Candidate` (~L95-104: `id, kind, selected, file, thumb, source, ref_id?, prompt?, name?, job_id?`).
  - `showResult(newIds, kind)` L492-502 é quem preenche `resultIds`/`resultKind` (chamado por
    `afterImport` L444 e `gerarViaCli` L591).
- `studio/etapas/base/ui/index.test.tsx`: mocks `vi.mock` do módulo de API (`api`, `apiUpload`),
  `respostasBase` por chave `"GET /api/projects/camp-a/base/..."`, `PID = "camp-a"`, `StudioProvider` +
  `ShellProvider` + `mockShellApi`. Não importa `emitStudioChange` hoje.
- Modelo do teste de barramento em tela: `studio/etapas/refs/ui/index.test.tsx:172-205`
  (`describe("refs — barramento de mudanças do chat")`: `act(() => emitStudioChange({...}))`, espera
  `DEBOUNCE_GUIA_MS + 200` com timers reais, conta chamadas ao endpoint de candidatas). Unitários do
  debounce por par em `frontend/src/shell/events.test.ts:73-105` e `:186-247` (UT-11, UT-20).
- `DEBOUNCE_GUIA_MS = 400` em `frontend/src/api/guide-sync.ts:50`.

### Relevant Files
- `studio/etapas/base/ui/index.tsx` — tipo `Candidate`, `originFor`, bloco `#baseGenResult`.
- `studio/etapas/base/ui/index.test.tsx` — testes novos dos critérios 12 e 13.
- `studio/etapas/refs/ui/index.test.tsx` — padrão de teste de recarga por evento em tela.
- `frontend/src/shell/events.ts` — `emitStudioChange`/`useStudioChange` (só leitura; F03).
- `frontend/src/api/guide-sync.ts` — `DEBOUNCE_GUIA_MS`.
- `.compozy/tasks/base-upscale-chat/_techspec.md` — §4 passos 13-14, §6 (eventos de outro pid, rajada, falha de `load`), §10 Risco 6, §12 decisão 10.
- `.compozy/tasks/base-upscale-chat/_prd.md` — "Preflight já verificado": passo 6 parcialmente pronto.

### Dependent Files
- `studio/base/service.py` — expõe `source_id` em `GET /base/candidates` (task_01).
- `scripts/qa/cenarios/base.py` — oráculo dos ids/textos do bloco antes/depois; não editar.
- `studio/web/dist/` — rebuild na task_07.

### Related ADRs
- ADR-006 (polling continua) — a assinatura é canal aditivo; `useEffect([pid])` e `progressJob` ficam.
- ADR-010 (a) — prontidão vem do guia do backend; a tela só recarrega candidatas.
- ADR-004 — `[extensão]`.

## Deliverables
- Antes/depois da tela Base lendo `source_id` com fallback para a heurística atual.
- Cobertura do critério 12 em `index.test.tsx` sem alteração do bloco de assinatura.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`: os casos abaixo são os critérios 12 e 13 da seção 9 do `_techspec.md`, escritos como
casos concretos em `studio/etapas/base/ui/index.test.tsx` (vitest + jsdom; API mockada).

- [x] **Critério 12 (recarga no pid certo)** — tela montada com `pid="camp-a"`; após a carga inicial, `act(() => emitStudioChange({pid:"camp-a", step:"base", scope:"candidates"}))` e espera de `DEBOUNCE_GUIA_MS + 200` → o mock de `api` recebeu **+1** chamada `GET /api/projects/camp-a/base/candidates` e a grade reflete a resposta nova (por exemplo, uma candidata a mais).
- [x] **Critério 12 (ignora outro pid)** — `emitStudioChange({pid:"camp-b", step:"base", scope:"candidates"})` → nenhuma chamada extra a `/base/candidates` após a espera.
- [x] **Critério 12 (rajada colapsa)** — 3 `emitStudioChange` do mesmo `(pid:"camp-a", step:"base")` em sequência síncrona → exatamente **+1** chamada a `/base/candidates` após a espera.
- [x] **Critério 12 (final troca com cache-bust)** — evento cuja resposta muda `final` faz `#baseFinalCard img[src]` conter um `?v=` diferente do anterior.
- [x] **Critério 13 (usa `source_id`)** — candidatas `s1` (situation, selected) e `u1` (upscale, `source_id:"s1"`); após `showResult(["u1"], "upscale")` (via fluxo de import/CLI mockado), `#baseGenResult` mostra a figura "antes · situação" com `src` de `s1.file` e "depois · upscale 2x" com `u1.file`.
- [x] **Critério 13 (`source_id` aponta para outra que não a heurística)** — cadeia com `label` selecionada `l1`, mas `u1.source_id = "s1"` → o "antes" é `s1` (não `l1`).
- [x] **Critério 13 (fallback quando `null`)** — `u1.source_id = null` com `label` selecionada `l1` → o "antes" é `l1` (comportamento atual preservado); `source_id` apontando para id inexistente → mesmo fallback.

## Success Criteria
- Every assigned test case implemented and passing
- `make frontend-verify` verde; os 22 `it` pré-existentes de `studio/etapas/base/ui/index.test.tsx` continuam verdes.
- `git diff studio/etapas/base/ui/index.tsx` não toca as linhas do bloco `useStudioChange` (L614-627) nem `frontend/`.
- Commits com `feat(base): … [extensão]` e trailer `Task-Id: ADH-OS-20260906-13`, com a evidência do critério 12 no corpo.
