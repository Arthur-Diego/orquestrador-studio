---
status: completed
title: Rotas novas — diagnóstico do CLI, papel `keyframe` e `POST /image-prompt`
type: backend
complexity: high
---

# Task 2: Rotas novas — diagnóstico do CLI, papel `keyframe` e `POST /image-prompt`

## Overview

Expõe pela API o que a task_01 construiu e fecha o lado servidor do card #99: nasce
`GET .../storyboard/script/cli?refresh=`, nasce o papel `[extensão]` `keyframe` no prompter com a
função `prompter.keyframe(...)`, e nasce `POST .../storyboard/image-prompt`, que devolve UM prompt
de imagem por foto com fallback determinístico quando o Claude CLI falta. Acrescenta também
`local_kind` ao `_idea_row`, o dado de que a galeria da task_05 precisa para o badge de origem.
É a task 3, 6, 7 e a metade backend da 10 da Build Order (§11).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- `GET /api/projects/{pid}/storyboard/script/cli` MUST aceitar a query `refresh` (booleano,
  default `false`) e devolver o objeto de `_techspec.md` §5.1. Com `refresh=true` MUST re-resolver
  o PATH via `prompter.cli_status(refresh=True)`.
- Essa rota MUST devolver `200` sempre que o projeto existe e `404` para projeto inexistente.
  **NUNCA 409**: a ausência do CLI é dado, não erro.
- MUST nascer `ROLES["keyframe"]` e `prompter.keyframe(images, brief, preset=None,
  model_target="nano_banana_2")` conforme §5.12, devolvendo
  `{prompt, negative, source, seconds, preset}`.
- `keyframe` MUST reusar a ordem de briefing e o hint de modelo do papel `script` **por meio de
  constantes compartilhadas** (extrair as constantes, não duplicar o texto), e MUST reusar
  `script_preset_block` para o rig e o `_parse` de prompt único para a resposta (§10, Risco 5).
  Com preset, o rig MUST aparecer literalmente no prompt devolvido.
- `POST /api/projects/{pid}/storyboard/image-prompt` MUST aceitar `ImagePromptReq` com `scene_id`
  (obrigatório, `cenaNN`), `photo` (obrigatório, relativo sob `storyboard/ideas/`), `description`
  (opcional, teto 500) e `preset` (opcional, **três estados**, mesmo `field_validator` de
  `VideoPromptReq`, com o mesmo helper `preset_arg()`).
- Status dessa rota: `200` prompt pronto; `404` projeto inexistente; `422` para `scene_id`,
  `photo`, `description` ou `preset` inválidos (inclusive foto fora de `storyboard/ideas/`, por
  `_check_image`). **NÃO existe 409** — sem CLI cai no template determinístico e devolve
  `source: "template"` (§12 auto-aceito 3; o 409 do ADR-025 é do ROTEIRO, que escreve arquivo).
- A rota MUST resolver o preset por `settings.resolve_preset(KEYFRAME_ACTION, pid, preset_arg)` e
  devolver o preset resolvido no corpo da resposta.
- A rota **NÃO persiste nada**: quem grava é o cliente, pelo `PUT /scenes` (mesma política de
  `/video-prompt`).
- Falha ou timeout do Claude MUST cair no template com `log.warning`, igual a `video_prompt`.
- MUST logar `log.info("cli_probe %s", {...})` e `log.info("image_prompt %s", {...})` conforme §7.
  **Nunca logar o texto do prompt inteiro** — apenas o tamanho em caracteres.
- `_idea_row` MUST ganhar `local_kind` (string ou `null`), lido do `meta` do candidato.
  `source`, `file`, `thumb`, `prompt`, `selected` e `imported` MUST seguir intocados (§5.6).
- Os acréscimos em `studio/etapas/storyboard/router.py` e `studio/storyboard/service.py` MUST
  ficar em **blocos próprios e no fim do bloco correspondente** (roteiro, ideação, prompt por
  foto), nunca no meio do bloco de ângulos — para que o rebase com F07 seja trivial (§8).
- `studio/storyboard/angles.py`, `studio/storyboard/local.py` e
  `studio/etapas/storyboard/ui/Angles.tsx` MUST permanecer **intocados**.
- Todo teste MUST mockar o binário `claude`.
</requirements>

## Subtasks

- [x] 2.1 Acrescentar a rota `GET .../storyboard/script/cli` no bloco `script` do router,
      delegando a `prompter.cli_status`.
- [x] 2.2 Extrair para constantes compartilhadas a ordem de briefing e o hint de modelo hoje
      embutidos no papel `script`.
- [x] 2.3 Criar `ROLES["keyframe"]` e a output spec própria de UM prompt.
- [x] 2.4 Implementar `prompter.keyframe(...)` reusando `script_preset_block` e `_parse`.
- [x] 2.5 Criar `ImagePromptReq` em `router.py` com o `field_validator` de preset e o teto de
      `description`.
- [x] 2.6 Implementar `service.image_prompt(...)` com validação de `scene_id`/`photo`, resolução
      de preset, chamada ao prompter e fallback de template determinístico.
- [x] 2.7 Acrescentar a rota `POST .../storyboard/image-prompt` no fim do bloco de prompt por foto.
- [x] 2.8 Acrescentar `local_kind` ao `_idea_row`.
- [x] 2.9 Acrescentar os logs estruturados `cli_probe` e `image_prompt`.
- [x] 2.10 Escrever os testes inline listados em `## Tests`.
- [x] 2.11 Rodar `make frontend-schema` (rotas e modelo Pydantic novos) e **commitar**
      `frontend/src/api/schema.ts` e `frontend/openapi.json`.

## Implementation Details

Arquivos a modificar: `studio/common/prompter.py`, `studio/etapas/storyboard/router.py`,
`studio/storyboard/service.py`, `tests/test_prompter.py`, `tests/test_storyboard_api.py`,
`tests/test_storyboard_service.py`, `frontend/src/api/schema.ts` (gerado),
`frontend/openapi.json` (gerado).

Contratos exatos em `_techspec.md` §5.1 (rota do CLI), §5.4 (`/image-prompt`, com exemplos de
requisição e resposta), §5.6 (`local_kind`) e §5.12 (`prompter.keyframe`). Matriz de erros em §6.
Observabilidade em §7.

O template determinístico do prompt de imagem deve seguir a mesma forma do `VIDEO_TEMPLATE` já
existente para `/video-prompt`: prompt não vazio, útil, sem Claude, com `source: "template"`.

`make frontend-schema` roda `python scripts/gen_openapi.py` + `npm run schema:gen`; a guarda de
drift do CI reprova se o `schema.ts` versionado divergir.

Pontos exatos do código (levantados nesta worktree):

- `studio/common/prompter.py`: **`ROLES` :117-163 é um `dict[str, str]` PLANO** — a chave é o id do
  papel e o valor é uma string longa em inglês; a entrada `"script"` está em :142-152. `keyframe`
  é mais uma chave de string, não uma estrutura aninhada. `OUTPUT_SPEC` (prompt único) :165-170 ·
  `preset_block` :239-252 · `_role_text` :266-270 · `_with_preset` :273-287 · `_run` :294-309
  (levanta `RuntimeError` sem `BIN`, em timeout e em returncode ≠ 0) · **`_parse` :311-322** (o
  parser de prompt ÚNICO, que `keyframe` reusa; devolve `{prompt, negative, camera, notes_pt}`) ·
  `_brief_text` :325-332 (lista FIXA de chaves em :326-329) · `SCRIPT_TIMEOUT_S = 300` :481 ·
  **`SCRIPT_OUTPUT_SPEC` :491-504** · **`SCRIPT_MODEL_HINTS` :508-515** (única chave
  `"nano_banana_2"`) e `_SCRIPT_MODEL_HINT_FALLBACK` :516-519 · **`script_preset_block`
  :522-542** (é ele que emite o `MANDATORY RIG, IDENTICAL IN EVERY SCENE: …`) ·
  **`script(...)` :608-646**, cuja ordem de montagem em :630-641 é exatamente a "ordem de briefing"
  a extrair para constante compartilhada.
- `studio/storyboard/service.py`: **`video_prompt` :905-942** é o gêmeo direto de
  `image_prompt` — `resolve_preset("motion", …)` :917, validações :918-925
  (`MAX_VIDEO_DESC = 500` :800), montagem da instrução :926, `kw = {"preset": preset} if preset
  else {}` :930, caminho Claude :931-938 com **`except` logado em :938 que cai no template**, e o
  fallback `{"prompt", "source": "template", "seconds", "preset"}` :939-942. `VIDEO_TEMPLATE`
  :808-820. `_SCENE_ID_RE = re.compile(r"^cena\d{2,}$")` :803. `_idea_row` :402-408 (hoje
  `{id, file, thumb, prompt, selected, source, imported}` — `local_kind` entra aqui);
  `list_ideas` :411-414; `_visible` :179-181. `script_generate` :1336-1399, com a **ordem** de
  guardas: `project_dir` :1351 → `resolve_preset` :1352 → validações :1353-1356 → `_require_base`
  :1357 → **409 de job concorrente :1360** → **409 de CLI ausente :1362** (a precedência que os
  testes verificam).
- `studio/etapas/storyboard/router.py`: **`VideoPromptReq` :88-105** é o molde de
  `ImagePromptReq` — tem o `@field_validator("preset")` chamando `prompter.valid_preset` :96-99 e
  o **`preset_arg()` :101-105** que devolve `settings.PRESET_UNSET` quando o campo não está em
  `model_fields_set` (é isso que preserva "ausente ≠ null"). `_guard` :148-155 traduz
  `Invalid`→422 e `Precondition`→409. Rotas do bloco: `GET .../script/job` :327,
  `GET .../script` :333, `POST .../video-prompt` :339-342, `GET .../video/job` :357-359.
  **Melhor ponto de inserção das rotas novas: logo após a linha 361**, antes do banner `# ===` do
  bloco de Ângulos em :363 — é o que mantém o rebase com F07 trivial. A rota do CLI pode ficar
  logo após :335 (fim do bloco `script`).
- Padrão de 404: `refs.project_dir(pid)` chamado **sem atribuição e sem try/except** levanta o 404
  sozinho (ex.: :166, :178, :270, :304, :329, :359). Rotas que delegam a um serviço que já chama
  `project_dir` omitem a linha.
- `studio/storyboard/local.py` (**somente leitura, não editar**): grava `local_kind` no `meta` do
  candidato (`"keyframe_local"` para o motor local e o do inpaint).

### Relevant Files

- `studio/common/prompter.py` — `ROLES`, `SCRIPT_OUTPUT_SPEC`, `SCRIPT_MODEL_HINTS`,
  `script_preset_block`, `_run`, `_parse`, `TIMEOUT_S`, `script()`: o papel `keyframe` espelha
  essa estrutura.
- `studio/storyboard/service.py` — `video_prompt(...)` é o gêmeo direto de `image_prompt(...)`,
  incluindo o fallback de template e o formato do log; `_idea_row`, `_visible` e `list_ideas`
  para o `local_kind`; `_check_image` e o validador de `cenaNN`.
- `studio/etapas/storyboard/router.py` — `VideoPromptReq` (com o `field_validator` de preset de
  três estados) é o molde de `ImagePromptReq`; o padrão de 404 por `refs.project_dir`.
- `studio/common/settings.py` — **somente leitura**: `resolve_preset` de três estados.
- `studio/storyboard/local.py` — **somente leitura**: grava `local_kind` no `meta` do candidato
  (motor local e inpaint). **Não editar** (é de F07).

### Dependent Files

- `frontend/src/api/schema.ts`, `frontend/openapi.json` — regenerados pelas rotas novas.
- `studio/etapas/storyboard/ui/Ideation.tsx` — as tasks 05 e 06 consomem `/image-prompt`,
  `/script/cli` e `local_kind`.
- `studio/mcp/actions.py` — a task_03 chama `/image-prompt` a partir de
  `storyboard_keyframe_prompt`.

### Related ADRs

- ADR-025 — o 409 sem CLI vale **só para o roteiro**; `/image-prompt` cai no template.
- ADR-028 — os `shot_prompts` continuam morando só em `script.json`.
- ADR-035 — "preset" aqui é exclusivamente o preset de REALISMO; não reintroduzir o combo de
  fórmulas da aula.
- ADR-042 (a criar na task_07) — item 2 da Decisão (papel `keyframe` e `/image-prompt`).

## Deliverables

- `GET /api/projects/{pid}/storyboard/script/cli?refresh=` funcionando.
- `ROLES["keyframe"]` + `prompter.keyframe(...)` com rig do preset.
- `POST /api/projects/{pid}/storyboard/image-prompt` com fallback de template.
- `local_kind` em `GET .../storyboard/candidates`.
- `frontend/src/api/schema.ts` e `frontend/openapi.json` regenerados e commitados.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Não há `_tests.md` — os casos abaixo são as definições completas.

- [x] `GET .../storyboard/script/cli` com `prompter.BIN = None` responde 200 com
      `available: false`, `path: null` e `searched_path` igual ao `PATH` do processo (critério A1).
- [x] `GET .../storyboard/script/cli?refresh=true`, com `clibin.which` monkeypatchado para
      encontrar o binário depois de o app subir, responde `available: true` **e** um
      `POST /script/generate` subsequente inicia o job, sem reiniciar o processo (critério A2).
- [x] `GET .../storyboard/script/cli` em projeto inexistente responde 404.
- [x] `prompter.keyframe(...)` com `_run` fingido devolve `{prompt, negative, source, seconds,
      preset}`; com `preset="documentary-street"`, o rig do preset aparece **literalmente** no
      prompt (Risco 5).
- [x] `prompter.keyframe(...)` sem CLI (`_run` levanta `RuntimeError`) propaga o erro para quem
      chama — o fallback é responsabilidade do serviço, não do prompter.
- [x] `POST .../storyboard/image-prompt` com o `claude` fingido devolve `source: "claude"` e
      prompt não vazio (critério D1).
- [x] `POST .../storyboard/image-prompt` **sem** CLI devolve **200** com `source: "template"` e
      prompt não vazio — nunca 409 (critério D1 e §6).
- [x] `POST .../storyboard/image-prompt` com Claude que estoura timeout devolve 200 com
      `source: "template"` e registra `log.warning`.
- [x] `POST .../storyboard/image-prompt` com `scene_id="lixo"` devolve 422.
- [x] `POST .../storyboard/image-prompt` com `photo` fora de `storyboard/ideas/` (inclusive
      tentativa de path traversal `../../etc/passwd`) devolve 422.
- [x] `POST .../storyboard/image-prompt` com `description` de 501 caracteres devolve 422.
- [x] `POST .../storyboard/image-prompt` com `preset: "nao-existe"` devolve 422 **antes** de
      qualquer chamada ao CLI (o fake do `_run` não é invocado).
- [x] `POST .../storyboard/image-prompt` **sem** a chave `preset`, com
      `storyboard.keyframe` configurado no projeto, devolve na resposta o preset da campanha;
      com `preset: null` devolve `preset: null`.
- [x] `POST .../storyboard/image-prompt` em projeto inexistente devolve 404.
- [x] A rota **não** escreve em `scenes.json`: o arquivo continua idêntico depois da chamada.
- [x] `GET .../storyboard/candidates` devolve `local_kind` por ideia (`"keyframe_local"` para a
      gerada pelo motor local, o do inpaint para a de inpaint, `null` para as demais) e mantém
      `source`, `file`, `thumb`, `prompt`, `selected` e `imported` inalterados.
- [x] `POST /script/generate` sem CLI continua respondendo 409 com a mensagem atual (ADR-025,
      inalterado), e o 409 de job concorrente continua tendo precedência sobre o de CLI.

## Success Criteria

- Every assigned test case implemented and passing.
- `make verify` verde (menos as 2 falhas pré-existentes de `tests/test_edit_captions.py`).
- `make frontend-schema` roda e o `schema.ts`/`openapi.json` commitados contêm as duas rotas
  novas; `make frontend-schema-check` não acusa drift.
- `git diff --name-only` **não** contém `studio/storyboard/angles.py`,
  `studio/storyboard/local.py`, `studio/etapas/storyboard/ui/Angles.tsx` nem
  `studio/common/settings.py`.
- Nenhum teste existente foi editado para passar.
