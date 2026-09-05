---
status: completed
title: Serviço e rotas `mood-run`
type: backend
complexity: high
---

# Task 2: Serviço e rotas `mood-run`

## Overview

Entrega o miolo da feature: `studio/moodboards/mood_run.py` (validação contra o manifesto,
montagem do comando, job com `JobRegistry`, leitura do resultado) e
`studio/moodboards/mood_run_router.py` com as cinco rotas da seção 5 do `_techspec.md`, incluído
em `studio/moodboards/router.py` por um bloco de **duas linhas** no fim do arquivo. É aqui que a
estimativa obrigatória de downloads, o 409 de concorrência e a matriz de erros inteira ganham
comportamento e teste.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1.** As rotas MUST viver em `studio/moodboards/mood_run_router.py` (módulo próprio) e o
  `studio/moodboards/router.py` MUST receber exatamente **duas linhas** (import + `include_router`)
  num bloco delimitado por comentário no fim do arquivo, no mesmo padrão dos blocos já existentes
  das frentes 03 e 04. Este é o risco 3 do `recon-wave-10.md` e a pegada não pode crescer.
- **R2.** A lógica MUST viver em `studio/moodboards/mood_run.py` (módulo próprio da frente).
  `studio/moodboards/service.py` MUST NOT ser alterado — dele só se **importa** `board_dir`.
  (Divergência deliberada em relação ao §5 do plano, registrado na seção 11 do `_techspec.md`.)
- **R3.** Nenhum objetivo, fundo, default ou piso MUST ser escrito à mão. Todos vêm de
  `skills_params.skill("mood_orquestrador")` — camada declarada para opções/defaults, camada
  `apresentacao` para os pisos de UI. Um teste MUST comparar a resposta de `/options` com o
  manifesto, não com literais.
- **R4.** A fórmula MUST ser exatamente `consultas = board - 1` e
  `downloads = len(objetivos) * consultas * n`. `todos --board 8 --n 3` (4 objetivos) MUST dar
  **84**.
- **R5.** `gate` MUST ser sempre `"auto"` e MUST NOT ser aceito no body (D3: em `claude -p` não
  existe `AskUserQuestion`). `saida` MUST ser imposto pelo servidor como
  `MOODBOARDS_DIR/<mbid>/mood_run` e MUST NOT ser aceito no body — é o que confina a escrita ao
  board (D1, ADR-013).
- **R6.** `foto` MUST ser validada por **contenção do caminho resolvido** dentro de
  `vibes.chosen_dir()`, não por prefixo textual, e MUST existir como arquivo de imagem. O valor
  vira argumento de linha de comando: aceitar caminho arbitrário entregaria leitura de qualquer
  arquivo do disco à corrida.
- **R7.** O job MUST usar um `JobRegistry` de módulo com chave `f"mood_run:{mbid}"`; segundo
  disparo MUST devolver **409**. O método de esquecer estado é `clear`, **não `forget`** — o §7 do
  plano erra e `studio/common/jobs.py` é a fonte.
- **R8.** `board_dir(mbid)` MUST ser chamado **antes** de qualquer verificação de CLI em toda rota
  que receba `mbid`, para que 404 sempre preceda 409 — mesma ordem já usada pelo bloco de
  multishot em `router.py`.
- **R9.** `params.json` MUST ser gravado com `common.atomic.write_json_atomic`, nunca
  `.write_text()` cru (risco 8 do recon).
- **R10.** Cada linha da matriz de erros da seção 6 do `_techspec.md` (E1…E16) MUST ter teste.
- **R11.** O módulo MUST NOT importar `studio.higgsfield`, MUST NOT chamar `require_cli()` e
  MUST NOT registrar `spend_action`/`record_generation` (ADR-002, ADR-016).
- **R12.** O `job["log"]` MUST receber as linhas de fase da seção 7 do `_techspec.md`, e
  `job["total"]` MUST ser o número de objetivos. MUST NOT haver progresso intermediário simulado:
  um `subprocess.run` bloqueante não tem como reportá-lo.
- **R13.** Todo o código novo MUST ser anotado e passar `ruff check` com `line-length=120`.
</requirements>

## Subtasks
- [ ] 2.1 Criar `studio/moodboards/mood_run.py` com o registry de módulo, os caminhos derivados
      (`run_dir(mbid)`) e os validadores (`_validar_objetivos`, `_validar_foto`, `_validar_numeros`).
- [ ] 2.2 Implementar `options(mbid)` lendo o manifesto e a peneira.
- [ ] 2.3 Implementar `estimate(objetivos, board, n)` — função pura, sem I/O.
- [ ] 2.4 Implementar `start_run(...)`: validação, gravação atômica do `params.json`, montagem do
      prompt via `skill_runner.build_prompt` e `registry.start` com a função de corrida.
- [ ] 2.5 Implementar `job(mbid)` e `read_result(mbid)` (com as `*_url` só quando o arquivo existe).
- [ ] 2.6 Criar `studio/moodboards/mood_run_router.py` com as cinco rotas e a tradução de exceção
      para status code conforme a matriz de erros.
- [ ] 2.7 Acrescentar o bloco de duas linhas no fim de `studio/moodboards/router.py`.
- [ ] 2.8 Escrever `tests/test_mood_run_api.py` com o fake do CLI que escreve `_run.json` e as
      pranchas, e o polling do job no padrão de `tests/test_multishot.py`.
- [ ] 2.9 Escrever a guarda de `git check-ignore` sobre `moodboards/<mbid>/mood_run/` e a guarda de
      "nenhum gasto/Higgsfield" nos módulos novos.
- [ ] 2.10 Rodar `ruff check` e a suíte.

## Implementation Details

Contratos literais na seção **5** do `_techspec.md`; matriz de erros na **6**; observabilidade na
**7**; layout no disco na **5.0**.

Peças a reusar sem duplicar: `service.board_dir` (validação de `mbid` + 404 pelo handler global de
`KeyError`), `vibes.chosen_dir()`/`vibes.list_chosen()` (a peneira), `skills_params.skill()`
(o manifesto), `jobs.JobRegistry`, `atomic.write_json_atomic`, `config.MOODBOARDS_DIR`.

A fixture `studio_env` de `tests/conftest.py` apaga e reimporta todos os módulos `studio.*` por
teste, então o `JobRegistry` de módulo nasce limpo a cada caso — não é preciso resetá-lo à mão.

### Relevant Files
- `studio/moodboards/router.py` — recebe o bloco de duas linhas; o padrão a copiar está no bloco
  `# ---------- multishot …` e nos dois blocos das frentes 03 e 04, no fim do arquivo.
- `studio/moodboards/skills_params.py` — `skill()`, `Param`, `Apresentacao`; **leitura apenas**.
- `studio/moodboards/vibes.py` — `chosen_dir()`, `list_chosen()`; **leitura apenas**.
- `studio/moodboards/service.py` — `board_dir()`, `MBID_RE`; **leitura apenas, não editar**.
- `studio/common/jobs.py` — `JobRegistry.start/status/clear`.
- `studio/common/atomic.py` — `write_json_atomic`.
- `studio/common/skill_runner.py` — entregue pela task_01.
- `tests/conftest.py` — fixtures `studio_env`, `client`, `make_image`.
- `tests/test_multishot.py` — padrão de polling de job assíncrono em teste (linhas 70-75).
- `tests/test_moodboards_api.py` — padrão de teste de contrato HTTP do domínio.

### Dependent Files
- `docs/domains/mood/postman/` (task_04) — a coleção é gerada da seção 5.
- `pendencias/mood-run-front.patch` (task_03) — o painel consome estas cinco rotas.

### Related ADRs
- **ADR-006** — um job por chave, thread daemon, polling; segundo disparo é 409.
- **ADR-013** — escrita confinada a `MOODBOARDS_DIR/<mbid>/`, rotas sem `pid`, imagens por `/mbfiles`.
- **ADR-014** — nenhum controle novo pode voltar para `studio/etapas/mood/view.*`.
- **ADR-016 / ADR-002** — cadeia gratuita: nada de `spend_action` nem de gate Higgsfield.
- **ADR-003** — estado em arquivo, sem banco.

## Deliverables
- `studio/moodboards/mood_run.py` e `studio/moodboards/mood_run_router.py`, anotados.
- Bloco de duas linhas em `studio/moodboards/router.py`.
- `tests/test_mood_run_api.py` verde.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Casos inline (não há `_tests.md` neste fluxo — ver `_tasks.md`).

**`/options`**
- [ ] **IT-01** `GET /api/moodboards/{mbid}/mood-run/options` devolve `objetivos`, `agregador`,
      `fundos` e `defaults` **iguais** aos derivados de `skills_params.skill("mood_orquestrador")`
      (o teste compara com o manifesto, não com literais).
- [ ] **IT-02** `mbid` inexistente → **404** (E7). `mbid` com `../` → **404**.
- [ ] **IT-03** `skill_runner.BIN = None` → `available_claude: false` (A1/E1).
- [ ] **IT-04** com 2 fotos na peneira, `escolhidas.total == 2` e `escolhidas.pasta` é
      `vibes.chosen_dir()`.

**`/estimate`**
- [ ] **IT-05** `{"objetivos": ["todos"], "board": 8, "n": 3}` → `downloads == 84` e
      `consultas == 7` (A2).
- [ ] **IT-06** `{"objetivos": ["ambiente","produto"], "board": 8, "n": 3}` → `downloads == 42`.
- [ ] **IT-07** objetivo `"paisagem"` → **422**, e a mensagem lista os quatro aceitos (E9).
- [ ] **IT-08** `objetivos: []` → **422**.
- [ ] **IT-09** `board: 3` → **422** citando o piso 4; `n: 0` → **422** citando o piso 1 (E11).

**`/mood-run`**
- [ ] **IT-10** `skill_runner.BIN = None` → **409** (E1).
- [ ] **IT-11** peneira vazia → **422** com a mensagem que ensina a rodar `/mood_vibe_scout` (E8).
- [ ] **IT-12** `foto` apontando para fora de `_escolhidas/` (ex.: `/etc/hosts`) → **422** (E10).
- [ ] **IT-13** `foto` dentro de `_escolhidas/` mas inexistente → **422** (E10).
- [ ] **IT-14** `mbid` inexistente **com** `BIN = None` → **404**, não 409 (ordem do E7).
- [ ] **IT-15** caminho feliz com fake do CLI: **200** com job `running`; polling até `done`;
      `params.json` existe no `mood_run/` do board e contém os parâmetros pedidos (A3).
- [ ] **IT-16** segundo `POST` com job `running` → **409** (E6/A6).
- [ ] **IT-17** o body MUST NOT aceitar `gate` nem `saida`: enviá-los não muda o comando montado
      (o `saida` usado é sempre `MOODBOARDS_DIR/<mbid>/mood_run` e o `gate`, `auto`).

**`/job`**
- [ ] **IT-18** sem corrida → `{"state": "idle"}` com as chaves-base `done/total/added/error/log`.
- [ ] **IT-19** fake com `returncode=1` → após o polling, `state == "error"` e `error` contém a
      cauda do stderr (E3).

**`/result`**
- [ ] **IT-20** sem corrida anterior → **404** (E13).
- [ ] **IT-21** caminho feliz → `boards[0].prancha_url == "/mbfiles/<mbid>/mood_run/<pasta>/_moodboard.jpg"`
      e as `leitura_url`/`curadoria_url` presentes quando os arquivos existem (A3/A5).
- [ ] **IT-22** fake escrevendo 4 boards → `len(boards) == 4`, cada pasta com seu `dna.json` (A4).
- [ ] **IT-23** `_run.json` com texto corrompido → **502** (E14).
- [ ] **IT-24** board declarado no `_run.json` cuja prancha não existe em disco → o board aparece
      **sem** `prancha_url`, sem exceção (E15).

**Guardas**
- [ ] **IT-25** `git check-ignore` reprova `moodboards/<qualquer>/mood_run/x.jpg` a partir da raiz
      do repositório — as imagens de terceiros não podem entrar no git (A10). `pytest.skip` só se
      `git` não existir no ambiente.
- [ ] **IT-26** o texto de `studio/moodboards/mood_run.py`, `mood_run_router.py` e
      `studio/common/skill_runner.py` não contém `higgsfield`, `require_cli`, `spend_action` nem
      `record_generation` (A11).

## Success Criteria
- Every assigned test case implemented and passing.
- `studio/moodboards/router.py` com exatamente **duas linhas** de diff (mais o comentário do bloco).
- `studio/moodboards/service.py` com **zero** linhas de diff.
- Nenhum literal de objetivo/fundo/default fora de `skills_params.py`.
- `ruff check studio tests scripts` sem erro novo; nenhuma regressão além das 3 falhas de baseline
  listadas na seção 9 do `_techspec.md`.
- O diff da task não contém nenhum caminho sob `studio/web/`.
