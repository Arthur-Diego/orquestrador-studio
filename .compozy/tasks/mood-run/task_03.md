---
status: completed
title: Painel `05 · Gerar mood com as skills` — entregue como **patch**
type: frontend
complexity: medium
---

# Task 3: Painel `05 · Gerar mood com as skills` — entregue como **patch**

## Overview

Entrega o painel da tela que dispara a corrida: seleção da foto-semente entre as escolhidas,
objetivos, `board`/`n`/`fundo`, **a conta de downloads antes de confirmar**, progresso por polling
e galeria de pranchas com `leitura.md`/`curadoria.md`. O código é escrito e revisado nesta task,
mas **não é aplicado ao repositório**: `studio/web/*` é núcleo sob a ADR-010 e só a frente de
preparo/shell da wave pode editá-lo. O entregável é um patch e o arquivo de testes de tela que o
acompanha.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (a mais importante desta task).** `studio/web/moodboards.js` — e qualquer caminho sob
  `studio/web/` — MUST NOT aparecer no diff da branch, nem commitado nem no working tree. A
  guarda `tests/test_prompter_presets_view.py::test_diff_da_feature_nao_toca_o_nucleo` é
  executável e MUST NOT ser afrouxada, editada ou receber carve-out sob nenhuma justificativa.
  A frente 03 tentou, citando o parágrafo de *Contexto* da ADR-010 como se fosse a *Decisão*;
  foi revertido no commit `8bd8b7b`. Quem achar que a guarda precisa mudar **para e reporta**.
- **R2.** O entregável MUST ser `docs/domains/mood/features/pendencias/mood-run-front.patch`, um
  diff unificado no formato `git diff` contra `studio/web/moodboards.js`, no mesmo formato dos dois
  patches já presentes na pasta (`painel-vibes-front.patch`, `manifesto-skills-mood-front.patch`).
- **R3.** Os testes de tela MUST ir para
  `docs/domains/mood/features/pendencias/mood-run-front-tests.py.txt`, com um docstring de
  cabeçalho explicando para qual arquivo de teste eles voltam quando o patch for aplicado — no
  mesmo formato de `painel-vibes-front-tests.py.txt`.
- **R4.** O patch MUST ter hunks pequenos e delimitados por comentário. Os três patches da wave
  tocam as mesmas regiões do arquivo; quanto menor a pegada, mais fácil a integração produzir uma
  versão única (risco R7 do `_techspec.md`).
- **R5.** Nenhum objetivo, fundo ou default MUST ser escrito à mão no JS. Tudo vem de
  `GET /api/moodboards/{mbid}/mood-run/options`.
- **R6.** O botão de disparo MUST estar desabilitado quando `available_claude === false` **ou**
  quando o contador de fotos escolhidas for `0`. O contador MUST vir de
  `Studio.vibes.refreshCount()` quando disponível, com `GET /api/escolhidas?per_page=1` como
  fonte autoritativa de fallback, e MUST se atualizar por `Studio.vibes.onChange` /
  o evento `studio:escolhidas` (contrato da seção 12 do `painel-vibes-fdd.md`).
- **R7.** `POST …/mood-run/estimate` MUST ser chamado e o número MUST ser mostrado num diálogo de
  confirmação **antes** do `POST …/mood-run`. Não pode haver caminho de código que dispare a
  corrida sem passar por ele.
- **R8.** O progresso MUST usar `ui.progressJob` sobre `GET …/mood-run/job`. MUST NOT chamar
  `ui.confirmCost` nem `ui.refreshCredits` como gate de gasto: a cadeia é gratuita (ADR-016).
- **R9.** Todo o CSS novo MUST ser um `<style>` inline escopado no prefixo `.mrn-` (ADR-019).
  `ui.css` e `style.css` MUST NOT ser tocados.
- **R10.** O painel MUST viver em `studio/web/moodboards.js` (área global da biblioteca) e MUST
  NOT ser adicionado a `studio/etapas/mood/view.*` (ADR-014).
- **R11.** O patch MUST aplicar limpo (`git apply --check`) sobre a versão de
  `studio/web/moodboards.js` presente em `develop`, e o arquivo resultante MUST passar
  `node --check`.
</requirements>

## Subtasks
- [ ] 3.1 Copiar `studio/web/moodboards.js` para um arquivo de trabalho **fora** da árvore do
      repositório (o diretório de scratchpad da sessão) e escrever o painel lá.
- [ ] 3.2 Implementar `renderMoodRunPanel(st)`: `GET /options`, seletor de foto-semente a partir de
      `GET /api/escolhidas`, checkboxes de objetivo, campos numéricos e o `<style>` `.mrn-`.
- [ ] 3.3 Implementar o gate do botão (claude ausente · nenhuma escolhida) com `Studio.vibes` e o
      evento `studio:escolhidas`.
- [ ] 3.4 Implementar a confirmação com a estimativa e o disparo com `ui.progressJob`.
- [ ] 3.5 Implementar a galeria de pranchas de `GET /result`, com links para `leitura.md` e
      `curadoria.md`.
- [ ] 3.6 Gerar o patch com `git diff --no-index` (ou equivalente) e conferir o cabeçalho
      `diff --git a/studio/web/moodboards.js b/studio/web/moodboards.js`.
- [ ] 3.7 Escrever `mood-run-front-tests.py.txt`.
- [ ] 3.8 Verificar `git apply --check` e `node --check` sobre o resultado, e confirmar que
      `git status --porcelain` **não** lista nada sob `studio/web/`.

## Implementation Details

O arquivo de trabalho **nunca** pode ser `studio/web/moodboards.js` dentro da worktree, nem
temporariamente: a guarda lê o working tree além dos commits. Trabalhe numa cópia fora da árvore e
gere o diff entre a cópia original e a modificada.

Contratos consumidos: seção 5 do `_techspec.md` (as cinco rotas) e seção 12 do
`painel-vibes-fdd.md` (`Studio.vibes` e o evento `studio:escolhidas`).

Helpers do shell disponíveis (`window.Studio.ui`): `esc`, `chip`, `modal`, `confirm`, `progressJob`,
`poll`, `tile`, `moodMosaic`. O contrato de erro do `api()` do shell é lançar `Error` com
`detail` do corpo — todo caminho novo termina em `catch (err) { toast(err.message) }`.

### Relevant Files
- `studio/web/moodboards.js` — base do patch. **Leitura apenas; nunca editar na worktree.**
- `docs/domains/mood/features/pendencias/painel-vibes-front.patch` — modelo de formato.
- `docs/domains/mood/features/pendencias/manifesto-skills-mood-front.patch` — modelo de formato.
- `docs/domains/mood/features/pendencias/painel-vibes-front-tests.py.txt` — modelo do arquivo de testes.
- `studio/web/ui.js` — `progressJob` (linha 471), `modal` (297), `confirm` (214); leitura apenas.
- `docs/domains/mood/features/painel-vibes-fdd.md` §12 — o contrato do contador.

### Dependent Files
- A frente de preparo/shell da wave 10 — é quem aplica os três patches.

### Related ADRs
- **ADR-010** — `studio/web/*` é núcleo; a frente de etapa para e pede à frente de shell.
- **ADR-013 / ADR-014** — a UI nova mora na biblioteca global, nunca na etapa 2.
- **ADR-019** — CSS novo é `<style>` inline escopado; `ui.css`/`style.css` intocados.
- **ADR-016** — nada de gate de custo: a cadeia é gratuita.

## Deliverables
- `docs/domains/mood/features/pendencias/mood-run-front.patch`.
- `docs/domains/mood/features/pendencias/mood-run-front-tests.py.txt`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Casos inline (não há `_tests.md` neste fluxo — ver `_tasks.md`). FT-01 e FT-02 são testes
**pytest de verdade**, e moram em `tests/test_mood_run_api.py` (não tocam `studio/web/`); FT-03 a
FT-05 são as asserções que ficam no `.py.txt` para a integração colar de volta.

- [ ] **FT-01** `git apply --check` do patch sobre a árvore atual sai com código 0 — a pendência
      não apodrece em silêncio. `pytest.skip` só se `git` não existir.
- [ ] **FT-02** o arquivo resultante da aplicação do patch passa `node --check`. `pytest.skip` se
      `node` não existir (mesmo padrão de `test_base_view_js_node_check`).
- [ ] **FT-03** *(no `.py.txt`)* `GET /static/moodboards.js` contém `Studio.moodRun`,
      `renderMoodRunPanel`, `/mood-run/options`, `/mood-run/estimate`, `/mood-run/job`,
      `/mood-run/result`, `studio:escolhidas` e `mrn-`.
- [ ] **FT-04** *(no `.py.txt`)* `.mrn-` aparece em `moodboards.js` e **não** aparece em
      `/static/ui.css` nem em `/static/style.css` (ADR-019).
- [ ] **FT-05** *(no `.py.txt`)* o JS não contém `confirmCost` nem `record_generation` no painel
      novo, e contém a palavra `downloads` na confirmação — a barreira é a conta, não o custo.

## Success Criteria
- Every assigned test case implemented and passing.
- `git status --porcelain` e o diff da branch **não** listam nenhum caminho sob `studio/web/`.
- `test_diff_da_feature_nao_toca_o_nucleo` passa **sem nenhuma alteração no próprio teste**.
- O patch aplica limpo e o resultado passa `node --check`.
