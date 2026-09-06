---
status: pending
title: Fundação — schema de foto, probe do CLI, chaves de preset e PATH do `run.sh`
type: backend
complexity: high
---

# Task 1: Fundação — schema de foto, probe do CLI, chaves de preset e PATH do `run.sh`

## Overview

Entrega os quatro contratos-base de que todas as outras tasks dependem, sem criar nenhuma rota
HTTP nova: (a) o schema por foto de `scenes.json` cresce com `image_prompt`, `preset` de três
estados e `origin`; (b) nasce `studio/common/clibin.py` e `prompter.cli_status(refresh=)`, que
tornam o binário `claude` diagnosticável e re-resolvível **sem reiniciar o servidor**; (c) as duas
chaves novas de `PRESET_ACTIONS` são registradas por `setdefault` em import time; (d) o `run.sh`
passa a acrescentar os diretórios de binário do usuário ao PATH herdado. É a task 1, 2, 4 e 5 da
Build Order (§11 do `_techspec.md`).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `_scene_photos`/`save_scenes`/`_blank_scenes` em `studio/storyboard/service.py` MUST preservar,
  por foto: `image_prompt` (string, default `""`), `video_prompt` e `video_desc` (já existentes),
  `videos` (já existente), `preset` (**opcional, três estados**) e `origin` (mapa opcional).
  Contrato exato em `_techspec.md` §5.5.
- Os três estados de `preset` MUST ser preservados literalmente: **chave ausente ≠ `null` ≠ id**.
  Ausente herda o default da ação; `null` desliga; `"<id>"` usa esse id. Um round-trip
  `PUT /scenes` → `GET /scenes` MUST devolver o mesmo dos três estados (critério C4 da §9).
- `preset` com id fora do catálogo (`prompter.valid_preset`) MUST devolver 422.
- `image_prompt` e `video_prompt` MUST ter teto `MAX_PHOTO_PROMPT = 4000`; acima disso, 422
  **citando a cena e a foto** (critério D10).
- `origin` MUST ser leniente: `{campo: {source, preset, at}}` com `campo ∈ {image_prompt,
  video_prompt}`, `source ∈ {ia, manual, template}`; valores fora do enum são **descartados
  silenciosamente**, nunca derrubam o save (mesma leniência dos `videos`).
- A poda existente MUST ser mantida: `photos` só contém chaves que estão em `images`
  (invariante 5); `primary` continua sendo item de `images` ou `null` (invariante 2).
- `scenes.json` de campanhas antigas (sem `image_prompt`/`preset`/`origin`) MUST carregar sem
  migração — todo campo novo é opcional e aditivo.
- MUST nascer `studio/common/clibin.py` com `which(name="claude")` e `describe(name, path, hint)`
  exatamente como a assinatura de `_techspec.md` §5.9. `describe` MUST devolver as seis chaves
  `{name, available, path, searched_path, checked_at, hint}`, com `searched_path` =
  `os.environ.get("PATH", "")` e `hint` preenchida só quando `path` é `None`.
- MUST nascer `prompter.cli_status(refresh: bool = False) -> dict` (§5.10). Com `refresh=True`,
  MUST re-resolver `shutil.which` **e reatribuir o módulo-global `prompter.BIN`** — é isso que faz
  o botão "Verificar de novo" funcionar sem reiniciar o processo. Com `refresh=False`, MUST apenas
  descrever o `BIN` atual, para que `monkeypatch.setattr(prompter, "BIN", …)` continue funcionando
  como jeito de fingir o CLI nos testes (ADR-008).
- `prompter.available()` MUST continuar sendo `BIN is not None` e continuar patchável. Nenhuma
  chamada existente pode mudar de comportamento.
- `status()` de `studio/storyboard/service.py` MUST ganhar a chave aditiva `script_cli_diag`
  (o mesmo objeto, **sem** re-resolver o PATH — leitura barata). `script_cli` (booleano) MUST
  permanecer com a semântica atual.
- MUST registrar, em `studio/storyboard/service.py` e ao lado do registro já existente de
  `SCRIPT_ACTION`: `ANGLES_ACTION = "storyboard.angles"` e `KEYFRAME_ACTION =
  "storyboard.keyframe"`, ambas por `settings.PRESET_ACTIONS.setdefault(<chave>, None)`.
  **`studio/common/settings.py` NÃO pode ser editado** (é território de F05) e
  **`studio/storyboard/angles.py` NÃO pode ser editado** (é território de F07). O `setdefault`
  é o que torna o registro idempotente e o rebase com F07 trivial.
- `run.sh` MUST acrescentar `$HOME/.local/bin` (e os demais diretórios de binário do usuário)
  **DEPOIS do PATH herdado, nunca antes** — para não trocar silenciosamente um binário que o
  usuário já tem — com um comentário explicando a causa (§10, Risco 6).
- O log `scenes_saved` MUST ganhar os campos `with_image_prompt` e `with_photo_preset` (§7).
- Todo teste MUST mockar o binário `claude`; nenhum teste pode tocar rede nem subprocess real.
</requirements>

## Subtasks

- [ ] 1.1 Criar `studio/common/clibin.py` com `which` e `describe`, puros e testáveis sem rede.
- [ ] 1.2 Acrescentar `prompter.cli_status(refresh=False)` reusando `clibin`, reatribuindo `BIN`
      quando `refresh=True`; manter `available()` intacto e patchável.
- [ ] 1.3 Acrescentar `script_cli_diag` ao `status()` da etapa 4, sem re-resolver o PATH.
- [ ] 1.4 Introduzir `MAX_PHOTO_PROMPT = 4000` e estender a normalização/poda de `_scene_photos`,
      `save_scenes` e `_blank_scenes` com `image_prompt`, `preset` (três estados) e `origin`.
- [ ] 1.5 Validar `preset` por foto contra o catálogo (422 em id desconhecido) e os tetos de
      `image_prompt`/`video_prompt` (422 citando cena e foto).
- [ ] 1.6 Tornar `origin` leniente: descartar chaves/valores fora do enum sem derrubar o save.
- [ ] 1.7 Registrar `ANGLES_ACTION` e `KEYFRAME_ACTION` em `settings.PRESET_ACTIONS` por
      `setdefault`, dentro de `studio/storyboard/service.py`.
- [ ] 1.8 Estender o log `scenes_saved` com `with_image_prompt` e `with_photo_preset`.
- [ ] 1.9 Corrigir o PATH em `run.sh` (append, nunca prepend), com comentário da causa.
- [ ] 1.10 Escrever os testes inline listados em `## Tests`.

## Implementation Details

Arquivos a criar: `studio/common/clibin.py`.
Arquivos a modificar: `studio/common/prompter.py`, `studio/storyboard/service.py`, `run.sh`,
`tests/test_prompter.py`, `tests/test_storyboard_api.py`, `tests/test_storyboard_service.py`.

O contrato exato de cada estrutura está em `_techspec.md` §5.5 (schema por foto), §5.9 (`clibin`),
§5.10 (`cli_status`), §5.11 (`PRESET_ACTIONS`) e §5.2 (`script_cli_diag`). A matriz de erros que
esta task fecha está em §6. **Nenhuma rota HTTP nasce aqui** — a rota `GET .../script/cli` e a
`POST .../image-prompt` são da task_02.

Ponto de atenção do repositório: `studio/etapas/storyboard/router.py` declara `SceneIn.photos`
como `dict` livre (`:50-59`), então **nenhum modelo Pydantic muda nesta task** — o que muda é a
normalização no serviço. Isso mantém o schema OpenAPI estável até a task_02, que é quem obriga
`make frontend-schema`.

Pontos exatos do código (levantados nesta worktree):

- `studio/common/prompter.py`: `BIN = shutil.which("claude")` :19 · `available()` :290
  (`return BIN is not None`) · `TIMEOUT_S = 180` :22 · `valid_preset` :255-263 ·
  `REALISM_PRESETS` :205-236 (ids `documentary-street`, `arri-natural-narrative`,
  `red-commercial-precision`, `sony-venice-night`, `anamorphic-film-look`).
- `studio/storyboard/service.py`: `_blank_scenes` :473-477 · `_scene_images` :480-499 ·
  `_scene_videos` :502-508 · **`_scene_photos` :511-531** (hoje só `{video_desc, video_prompt,
  videos}`; migra o par legado por cena para a `primary`) · `_normalize` :534-547 ·
  `_write_scenes` :556-559 · `load_scenes` :562-568 · `_check_image` :571-579 ·
  **`save_scenes` :582-627** (guarda de `MAX_SCENES` :585, `MAX_SCENE_TEXT` :589, `_check_image`
  :594, correção da `primary` :599, `_check_video` :603, poda de `photos` :610-623) ·
  **o log `scenes_saved` :626** (hoje `{"pid", "scenes", "with_image"}`) ·
  `MAX_VIDEO_DESC = 500` :800 · `status(pid)` :197-219 (`script_preset_default` :216,
  `script_cli = prompter.available()` :218) · **`SCRIPT_ACTION = "storyboard.script"` :1149 e o
  precedente `settings.PRESET_ACTIONS.setdefault(SCRIPT_ACTION, SCRIPT_PRESET_DEFAULT)` :1166** —
  é ao lado desta linha que `ANGLES_ACTION` e `KEYFRAME_ACTION` entram.
- `studio/common/settings.py` (**somente leitura**): `PRESET_ACTIONS` :103 (mapa ABERTO,
  `{mood: None, base: None, motion: None}`) · `PresetUnset` :106-118 e `PRESET_UNSET` :121 ·
  `PresetArg = str | None | PresetUnset` :123 · `preset_default_for` :241-265 (cadeia projeto →
  global → código; `null` gravado **termina** a cadeia :261, chave ausente cai para o próximo
  :257-258, id que saiu do catálogo é ignorado :262) · `resolve_preset` :268-280 (devolve
  `(resolvido, explícito)`).
- Convenção de teste: `tests/test_storyboard_service.py` alcança o serviço pela fixture
  `sb = studio_env["svc"]("storyboard")` e faz `monkeypatch.setattr(sb.prompter, …)`;
  `tests/test_storyboard_api.py` tem a fixture `claude` :602-609 que faz
  `monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")` mais um fake de
  `prompter.subprocess.run`.

### Relevant Files

- `studio/common/prompter.py` — `BIN` resolvido em import time é a causa-raiz do defeito 1 do PRD;
  ganha `cli_status`.
- `studio/storyboard/service.py` — `_blank_scenes`, `_normalize`, `_scene_photos`, `save_scenes`,
  `_check_image`, `status()` e o registro de `SCRIPT_ACTION` (o precedente de `setdefault`).
- `studio/common/settings.py` — **somente leitura**: `PRESET_ACTIONS`, `preset_default_for`,
  `resolve_preset` definem a semântica de três estados que esta task precisa preservar.
- `run.sh` — três linhas; ativa o venv e executa o uvicorn sem normalizar o PATH.
- `tests/test_storyboard_service.py`, `tests/test_storyboard_api.py`, `tests/test_prompter.py` —
  convenções de fixture de projeto e de `monkeypatch` do `prompter`.

### Dependent Files

- `studio/etapas/storyboard/router.py` — a task_02 acrescenta rotas que consomem `cli_status` e
  o serviço de prompt por foto.
- `studio/etapas/storyboard/ui/Ideation.tsx` — as tasks 04–06 consomem `script_cli_diag` e o
  schema por foto.
- `studio/mcp/actions.py` — a task_03 grava `origin` pelo `PUT /scenes`.
- `studio/storyboard/angles.py` — **não editar**; apenas se beneficia da chave
  `storyboard.angles` registrada aqui (contrato consumido por F07).

### Related ADRs

- ADR-042 (a criar na task_07) — schema de foto e papel `keyframe`; esta task implementa os
  itens 1 e 4 da Decisão.
- ADR-018 / ADR-022 — cena = `images[]` + `primary`; bloco de vídeo por foto. O acréscimo é
  aditivo e retrocompatível.
- ADR-025 — o servidor nunca escreve `scenes.json` a partir do roteiro; nada aqui viola isso.
- ADR-008 — testes sem rede/navegador; o `claude` é sempre fake.

## Deliverables

- `studio/common/clibin.py` novo, com `which` e `describe`.
- `prompter.cli_status(refresh)` funcionando, com `BIN` reatribuível em runtime.
- `script_cli_diag` no `status()` da etapa 4.
- Schema por foto com `image_prompt`, `preset` (3 estados) e `origin`, validado e podado.
- `storyboard.angles` e `storyboard.keyframe` em `PRESET_ACTIONS` por `setdefault`.
- `run.sh` com PATH determinístico (append).
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Não há `_tests.md` neste workflow — os casos abaixo são as definições completas. Cada um nomeia
entrada, condição e resultado esperado.

- [ ] `clibin.describe` com `path=None` devolve as seis chaves, `available=False` e `hint` não
      vazia; com `path="/x/claude"` devolve `available=True` e `hint == ""`.
- [ ] `clibin.describe` põe em `searched_path` exatamente `os.environ["PATH"]` do processo
      (monkeypatch de `os.environ`).
- [ ] `prompter.cli_status()` com `monkeypatch.setattr(prompter, "BIN", None)` devolve
      `available=False`; com `BIN="/x/claude"` devolve `available=True, path="/x/claude"`.
- [ ] `prompter.cli_status(refresh=True)` com `clibin.which` monkeypatchado para devolver
      `"/novo/claude"` **reatribui `prompter.BIN`** e devolve `available=True` — provando que
      não é preciso reiniciar o processo (critério A2).
- [ ] `prompter.available()` continua devolvendo `BIN is not None` depois de `cli_status`.
- [ ] `GET /api/projects/{pid}/storyboard` devolve `script_cli` booleano **e** `script_cli_diag`
      com as seis chaves (critério A3); projeto inexistente continua 404.
- [ ] `PUT /scenes` com `photos[img]` sem a chave `preset` → `GET /scenes` devolve o objeto
      **sem** a chave `preset` (herda). Com `preset: null` → devolve `null`. Com
      `preset: "documentary-street"` → devolve o id. (critério C4, três estados)
- [ ] `PUT /scenes` com `photos[img].preset = "nao-existe"` devolve 422.
- [ ] `PUT /scenes` com `image_prompt` de 4001 caracteres devolve 422 e a mensagem cita a cena e a
      foto (critério D10). Com 4000 caracteres, salva.
- [ ] `PUT /scenes` com `origin` malformado (`source: "extraterrestre"`, campo desconhecido)
      salva com sucesso e descarta o que é inválido, sem 422.
- [ ] `PUT /scenes` → `GET /scenes` preserva `image_prompt` e `origin` bem formado.
- [ ] `scenes.json` legado (só `video_desc`/`video_prompt`/`videos` por foto) carrega sem erro e
      sem inventar chaves.
- [ ] `photos` continua podado às chaves presentes em `images` depois de remover uma imagem.
- [ ] `settings.PRESET_ACTIONS` contém `storyboard.angles` e `storyboard.keyframe` com valor
      `None`, e um `setdefault` repetido da mesma chave **não** altera um valor já registrado
      (critério C5 da §9).
- [ ] `run.sh`: inspeção do script (sem subir servidor) prova que o PATH do usuário aparece
      **antes** dos diretórios acrescentados e que `$HOME/.local/bin` é acrescentado
      (critério A4).

## Success Criteria

- Every assigned test case implemented and passing.
- `make verify` verde na worktree (exceto as 2 falhas pré-existentes de
  `tests/test_edit_captions.py`, que **não** são desta frente e não devem ser corrigidas aqui).
- `studio/common/settings.py` e `studio/storyboard/angles.py` **intocados** (`git diff` vazio para
  os dois).
- Nenhuma rota nova e nenhum modelo Pydantic alterado — `make frontend-schema` ainda não é
  necessário nesta task.
- Commit com `Task-Id: ADH-OS-20260906-08` e mensagem `feat(storyboard): … [extensão]`.
