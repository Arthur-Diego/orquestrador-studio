---
status: pending
title: Shape comum de custo (`CostPreview`) nas 7 rotas + agregados do ledger
type: backend
complexity: high
---

# Task 1: Shape comum de custo (`CostPreview`) nas 7 rotas + agregados do ledger

## Overview

Entrega a fundação da feature: um modelo `CostPreview` e um construtor puro `cost_preview()` em
`studio/common/pricing.py`, adotados de forma **estritamente aditiva** pelas 7 rotas `cost` em
escopo, mais os agregados novos do livro-caixa (`today_credits`/`today_count` em
`settings.summary`, `summary_global` no `dashboard(pid)`). Todo o resto da feature — o breakdown
do gate no chat, o widget do dock, o `credits_status` e o `BalanceCard` — lê o que esta task
produz.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (invariante suprema desta task).** A adoção é **ADITIVA**. Para cada uma das 7 rotas,
  TODAS as chaves que ela devolve hoje MUST continuar presentes, com o mesmo nome e o mesmo
  tipo. Nenhuma remoção, nenhuma renomeação. Em colisão de chave entre o `CostPreview` e o
  dicionário legado, **o valor LEGADO vence** (`_techspec.md` C1 e seção 12, decisão 3).
- **R2.** MUST existir `class CostPreview(BaseModel)` em `studio/common/pricing.py` com
  `model_config = ConfigDict(extra="allow")` e exatamente os campos da assinatura em
  `_techspec.md` C1: `action`, `model`, `label`, `variant`, `kind`, `unit_credits`, `count`,
  `total`, `source`, `balance`, `note`.
- **R3.** MUST existir `cost_preview(*, action, model, count=1, unit_credits=None,
  source="unknown", variant=None, balance=None, legacy=None) -> dict`, **pura** (sem I/O, sem
  subprocess, sem leitura de disco), devolvendo um `dict` já mesclado com `legacy`.
  `total = unit_credits * count` quando o unitário existe; `None` caso contrário.
- **R4.** NENHUMA rota MUST declarar `response_model=CostPreview` (`_techspec.md` seção 12,
  decisão 2). O modelo documenta o shape; o construtor é o único produtor. Consequência
  desejada: `frontend/src/api/schema.ts` não muda por causa desta task.
- **R5.** Os números de preço são intocáveis: `CATALOG`, `estimate()` e `KIND_ORDER` de
  `pricing.py` MUST permanecer byte-idênticos. Esta task não altera preço nenhum.
- **R6 (CORREÇÃO do `_techspec.md`, ler com atenção).** As chaves `action` usadas MUST já existir
  em `settings.ACTIONS` — a feature NÃO inventa chave de ação. A observação da seção 5 do
  `_techspec.md` cita três chaves que **NÃO existem** no catálogo real (auditado no código desta
  worktree, com F05 já integrada): `storyboard.frames`, `animate.take` e `storyboard.video`.
  O catálogo real (`studio/common/settings.py::ACTIONS`, 15 chaves) é:
  `base.image`, `base.upscale`, `base.clean`, `mood.grid`, `mood.multishot`, `storyboard.scene`,
  `storyboard.multishot`, `storyboard.inpaint`, `storyboard.video.scene`,
  `storyboard.video.transition`, `storyboard.angles`, `storyboard.upscale`, `animate.video`,
  `music.track`, `export.reframe`.
  **Mapeamento normativo desta task** (vence a tabela da seção 5 do `_techspec.md`):
  | Rota | `action` a usar |
  |---|---|
  | `mood/cost` | `"mood.grid"` |
  | `base/cost` | `KIND_ACTION.get(kind, ACTION_DEFAULT)` — `base.upscale`, `base.clean` ou `base.image` |
  | `animate/cost` | `"animate.video"` (NÃO `animate.take`) |
  | `music/generate/cost` | `"music.track"` |
  | `storyboard/cost` | `"storyboard.scene"` (NÃO `storyboard.frames`) |
  | `storyboard/video/cost` | `sb.video_action(mode)` — `storyboard.video.transition` no modo `start_end`, senão `storyboard.video.scene` (NÃO `storyboard.video`) |
  | `moodboards/{mbid}/multishot/cost` | `"mood.multishot"` |
  Toda chave produzida MUST estar em `settings.ACTION_KEYS`; escrever um teste que afirma isso
  para as 7 rotas de uma vez.
- **R7.** `settings.summary()` MUST ganhar `today_credits` e `today_count` sem alterar
  `total_credits`, `count`, `by_step` e `by_project`. "Hoje" é calculado em **UTC**, coerente
  com o `at` gravado por `_now_iso` (`_techspec.md` seção 12, decisão 10).
- **R8.** `dashboard(pid)` MUST ganhar `summary_global` sem alterar a chave `summary` existente.
- **R9.** As rotas MUST manter exatamente os status de hoje (200, 404, 409 de CLI ausente, 422).
  Nenhum status novo, nenhuma exceção nova escapando.
- **R10.** As rotas de ângulos (`storyboard/angles/scenes/{scene}/cost`,
  `storyboard/angles/product/cost`) e `export/reframe/cost` estão **FORA DE ESCOPO** e MUST NOT
  ser tocadas — são fronteira de F07.
- **R11.** Os testes de contrato (subtask 1.1) MUST ser escritos e passar **ANTES** de qualquer
  mudança nas rotas, para provarem que travam o contrato atual.
- **R12 (colisão de nome já existente no código).** `studio/creditos/service.py:52` JÁ tem uma
  função pública chamada `cost_preview(action, pid, model, variant)` — a que serve
  `GET /api/…/creditos/cost` e devolve `{action, model, label, variant, kind, measured, live,
  credits, source, balance}`. A função NOVA desta task mora em `studio/common/pricing.py` e tem
  assinatura keyword-only totalmente diferente. As duas MUST coexistir sem que nenhuma seja
  renomeada ou reescrita: sempre qualificar (`pricing.cost_preview` versus
  `service.cost_preview`), nunca `from ... import cost_preview`. `creditos.service.cost_preview`
  é contrato de tela em uso e MUST NOT mudar de assinatura nem de retorno.
- **R13.** O `balance` do `CostPreview` MUST vir de `creditos.service.balance()`, que já devolve
  `{installed, logged_in, plan, credits, error?}` e nunca levanta. NÃO chamar `hf.status` direto,
  e NÃO introduzir subprocess novo em rota que hoje não o faça — `balance()` usa o cache de 60 s
  de `hf.status` sem `refresh`.

## Subtasks
- [ ] 1.1 Escrever `tests/test_cost_preview.py` com um teste de contrato por rota afirmando as
      chaves de HOJE (nome e tipo) das 7 rotas em escopo. Rodar e ver passar contra o código
      atual, antes de mudar qualquer rota.
- [ ] 1.2 Implementar `CostPreview` e `cost_preview()` em `studio/common/pricing.py`, marcados
      `[extensão]`, com os testes unitários do construtor puro.
- [ ] 1.3 Adotar o construtor na rota `POST /api/projects/{pid}/mood/cost`, preservando
      `per_prompt` (lista de dicts do CLI) e `total`.
- [ ] 1.4 Adotar na rota `POST /api/projects/{pid}/base/cost`, preservando `per_item`, `count`,
      `total`, `raw`; a `action` sai da `KIND_ACTION` existente.
- [ ] 1.5 Adotar na rota `POST /api/projects/{pid}/animate/cost`, preservando `per_take`,
      `total`, `credits_unknown`, `model`, `count`, `error`.
- [ ] 1.6 Adotar na rota `POST /api/projects/{pid}/music/generate/cost`, preservando `per_track`,
      `total`, `raw`, `error`.
- [ ] 1.7 Adotar nas rotas `POST /api/projects/{pid}/storyboard/cost` (`per_image`, `total`) e
      `POST /api/projects/{pid}/storyboard/video/cost` (`model`, `per_item`, `total`).
- [ ] 1.8 Adotar na rota `POST /api/moodboards/{mbid}/multishot/cost`, preservando `model`,
      `count`, `per_image`, `total`, `source` (a chave `source` já existe com a mesma semântica).
- [ ] 1.9 Acrescentar `today_credits`/`today_count` a `settings.summary()` e `summary_global` a
      `creditos.service.dashboard(pid)`, com os testes em `tests/test_creditos_api.py`.
- [ ] 1.10 Rodar a suíte inteira e conferir que nenhum teste existente de custo quebrou.

## Implementation Details

O ponto de mudança é único por rota: onde hoje há `return <dict atual>`, passa a haver
`return pricing.cost_preview(..., legacy=<dict atual>)`. Reverter é desfazer essa linha — nenhum
serviço muda de forma. A tabela da seção 5 do `_techspec.md` lista, por rota, o arquivo e a
linha do retorno de hoje, as chaves preservadas e as chaves somadas; **usar essa tabela como
checklist**.

O `balance` vem do mesmo lugar que `creditos.service` já usa para montar
`{installed, logged_in, plan, credits}`. Nenhuma chamada nova de subprocess é introduzida em
caminho que hoje não a faça — se a rota já não consulta o CLI, o `balance` vai `None`, e o
widget degrada como a seção 6 do `_techspec.md` descreve.

### Relevant Files
- `studio/common/pricing.py` — onde `CostPreview` e `cost_preview()` nascem; `CATALOG`,
  `estimate` e `KIND_ORDER` ficam intocados.
- `studio/common/settings.py` — `ACTIONS`, `record_generation`, `history`, `summary`,
  `_read_ledger`, `_now_iso`; ganha os agregados de hoje.
- `studio/creditos/service.py` — `balance`, `cost`, `dashboard`, `history`; ganha `summary_global`.
- `studio/etapas/mood/router.py` — rota `mood/cost` (retorno em ~`:189-190`).
- `studio/base/service.py` — função de custo (~`:779`) e o dict `KIND_ACTION` (~`:62`).
- `studio/etapas/base/router.py` — rota `base/cost`.
- `studio/animate/service.py` — função de custo (~`:630-631`).
- `studio/etapas/animate/router.py` — rota `animate/cost`.
- `studio/music/service.py` — função de custo (~`:161`).
- `studio/etapas/music/router.py` — rota `music/generate/cost`.
- `studio/storyboard/service.py` — custo de frames (~`:732`) e custo de vídeo (~`:1019`).
- `studio/etapas/storyboard/router.py` — rotas `storyboard/cost` e `storyboard/video/cost`.
- `studio/common/multishot.py` — `cost()` em `:60-82`; já devolve `source` com a mesma semântica.
- `studio/moodboards/service.py` — `multishot_cost()` em `:350-356`, que embrulha `multishot.cost`.
- `studio/moodboards/router.py` — rota `POST /api/moodboards/{mbid}/multishot/cost` em `:169-177`.

**Localizações auditadas nesta worktree (usar, não redescobrir):**
- `studio/etapas/mood/router.py:178-190` — `mood_cost`; 409 se `not hf.available()`.
- `studio/base/service.py:759-779` — `estimate_cost`; `KIND_ACTION` + `ACTION_DEFAULT` em `:62`.
- `studio/etapas/base/router.py:184-197` — `base_cost`.
- `studio/animate/service.py:625-631` — `cost`; `studio/etapas/animate/router.py:159-162`.
- `studio/music/service.py:153-161` — `generate_cost`; `studio/etapas/music/router.py:103-107`.
- `studio/storyboard/service.py:725-732` — `cost` (frames); `:1020-1028` — `video_cost`;
  `video_action(mode)` em `:958-965`. Router: `:257-259` e `:356-358`.
- `studio/common/settings.py`: `ACTIONS` `:35-77`, `record_generation` `:374-386`,
  `_read_ledger` `:389-401`, `history` `:404-410`, `summary` `:420-454`, `_now_iso` `:346-347`.
- `studio/creditos/service.py:27-38` — `dashboard`; `:52-90` — `cost_preview` (NOME JÁ OCUPADO,
  ver R12).

### Dependent Files
- `studio/mcp/actions.py` — `_paid` passará a montar o breakdown a partir deste shape (task_02).
- `frontend/src/ui/costRows.ts` — `CostInfoLike` é o superconjunto deste shape (task_04).
- `frontend/src/areas/creditos/CreditosArea.tsx` — consome `summary_global` (task_06).
- `tests/test_creditos_api.py` — cobre `summary` e `dashboard`.

### Related ADRs
- **ADR-016** (gate de custo: custo antes de gerar, livro-caixa depois, modelo default por ação)
  — esta task é a implementação do "custo antes de gerar" com shape uniforme.
- **ADR-004** (fidelidade ao curso) — a feature inteira é `[extensão]` e fica marcada como tal.

## Deliverables
- `studio/common/pricing.py` com `CostPreview` e `cost_preview()`, marcados `[extensão]`.
- As 7 rotas `cost` devolvendo os campos do `CostPreview` além dos campos atuais.
- `settings.summary()` com `today_credits`/`today_count`; `dashboard(pid)` com `summary_global`.
- `tests/test_cost_preview.py` (novo) e as adições em `tests/test_creditos_api.py`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md` neste workflow. Casos inline, derivados dos critérios 1, 2 e 18 da seção 9 do
`_techspec.md`:

- [ ] **Contrato por rota (7 casos, critério 1).** Para cada uma das 7 rotas, um teste que
      chama a rota com um payload válido e afirma: (a) cada chave de hoje está presente; (b) o
      tipo de cada uma é o mesmo de hoje; (c) as chaves do `CostPreview` foram somadas. Ex.:
      `POST /api/projects/<pid>/base/cost` com `{"kind":"upscale","model":"bytedance_image_upscale","count":1}`
      devolve 200 com `per_item`, `count`, `total`, `raw` **e** `action == "base.upscale"`,
      `model`, `label`, `variant`, `kind`, `unit_credits`, `source`, `balance`, `note`.
- [ ] **`cost_preview` colisão de chave (critério 2).** `cost_preview(action="a", model="m",
      total=…, legacy={"total": 99})` devolve `total == 99` — o valor legado vence.
- [ ] **`cost_preview` total derivado (critério 2).** `unit_credits=4, count=3` ⇒ `total == 12`;
      `unit_credits=None, count=3` ⇒ `total is None`.
- [ ] **`cost_preview` precedência de `source` (critério 2).** `"cli"` acima de `"measured"`
      acima de `"unknown"`; o default sem informação é `"unknown"`.
- [ ] **`cost_preview` é pura (critério 2).** Chamada duas vezes com a mesma entrada devolve
      dicionários iguais e não toca disco nem subprocess.
- [ ] **`summary` aditivo (critério 18).** Com um ledger de fixture contendo linhas de hoje e de
      ontem, `summary()` devolve `today_credits`/`today_count` só com as de hoje (UTC), e
      `total_credits`, `count`, `by_step`, `by_project` continuam com os valores de antes.
- [ ] **`dashboard` aditivo (critério 18).** `dashboard(pid)` devolve `summary_global` e mantém
      `summary` com o mesmo conteúdo de hoje.
- [ ] **Ledger ausente.** Sem o arquivo `spend-ledger.jsonl`, `summary()` devolve zeros em
      `today_credits`/`today_count` e nada levanta.

## Success Criteria
- Every assigned test case implemented and passing
- `tests/test_cost_preview.py` passa **antes** da mudança das rotas (travando o contrato atual) e
  continua passando **depois** (com as asserções das chaves novas acrescentadas).
- `make verify` verde, ressalvadas as duas falhas pré-existentes de `tests/test_edit_captions.py`
  listadas no `_prd.md`.
- `git diff` em `studio/common/pricing.py` não toca `CATALOG`, `estimate` nem `KIND_ORDER`.
- Nenhuma rota ganhou `response_model`; `frontend/src/api/schema.ts` não muda por esta task.
