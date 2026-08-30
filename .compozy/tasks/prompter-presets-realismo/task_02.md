---
status: completed
title: Rotas de catálogo e de configuração de preset
type: backend
complexity: medium
---

# Task 2: Rotas de catálogo e de configuração de preset

## Overview

Expõe por HTTP o catálogo e a resolução de default entregues pela task_01: o endpoint de leitura
`GET /api/prompter/presets` — que a UI das etapas 2/3/4 e a feature consumidora
`storyboard-roteiro-llm` usam para montar seletores — e as rotas de configuração do preset default
por ação (global e por projeto), fechando o padrão ADR-016 no lado da API. As rotas nascem em
`studio/creditos/router.py`, a única área campanha-independente editável sem tocar o núcleo
(ADR-010) e já a casa do padrão de config de defaults.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (contrato congelado do handoff).** `GET /api/prompter/presets` MUST responder no shape
  literal da seção 5 do `_techspec.md`: `{"presets": [...], "defaults": {...}}`. Cada item de
  `presets` MUST trazer `id`, `name`, `default` (bool), `desc_pt`, `rig` (com `camera`, `lens`,
  `format`, `focal`, `aperture`), `light`, `grade` e `negative`. Esses nomes de campo são
  consumidos pela sub-wave 2 e MUST NOT ser renomeados nem aninhados de outra forma.
- **R2.** O bloco `defaults` MUST ser montado **iterando `settings.PRESET_ACTIONS`** (amenda A1 do
  gate W3), um par `{"preset", "source"}` por ação registrada — nunca com as três chaves
  `mood`/`base`/`motion` fixas no código. Assim a ação `storyboard.script`, quando registrada
  pela feature consumidora, aparece sozinha na resposta, sem mudança de contrato.
- **R3.** A query opcional `?pid=` MUST resolver os defaults com o override do projeto. `pid`
  inexistente MUST devolver 404 pelo mesmo caminho já usado nas rotas por projeto do módulo
  (`project_dir(pid)` + handler do núcleo).
- **R4.** `GET /api/prompter/presets` MUST responder 200 sempre que o pid for válido ou ausente
  (o catálogo é dict em memória, sem I/O de rede) e MUST NOT chamar o Claude CLI.
- **R5.** `GET /api/prompter/preset-config` MUST devolver os defaults globais resolvidos de todas
  as ações de `PRESET_ACTIONS`, no mesmo shape do bloco `defaults` do endpoint de catálogo.
- **R6.** `PUT /api/prompter/preset-config` MUST aceitar body `{"kind": <ação>, "preset": <id> |
  null}` e devolver o `preset_default_for(kind)` resultante. `PUT
  /api/projects/{pid}/prompter/preset-config` MUST ter a mesma semântica com override de projeto,
  e `DELETE /api/projects/{pid}/prompter/preset-config/{kind}` MUST remover o override do projeto
  e devolver a resolução resultante.
- **R7.** `kind` não registrado em `PRESET_ACTIONS` ou `preset` fora de `REALISM_PRESETS` (e
  diferente de `null`) MUST devolver **422**, convertendo o `ValueError` de settings em
  `HTTPException`, exatamente como as rotas de modelo já fazem no módulo.
- **R8.** `preset: null` no body MUST ser aceito como escolha válida ("sem preset") e persistido,
  distinto de não configurar — MUST NOT ser tratado como campo faltando.
- **R9 (aditivo).** Nenhuma rota, modelo de request ou resposta já existente em
  `studio/creditos/router.py` MUST ser alterada; nenhuma string fixada em
  `tests/test_creditos_api.py` MUST mudar. As rotas novas MUST NOT exigir auth (app local, padrão
  do projeto) e MUST NOT tocar `studio/app.py` (o router já é incluído lá).
</requirements>

## Subtasks

- [x] 2.1 Declarar o modelo pydantic do body de configuração de preset (`kind` + `preset`
      opcional/nullable), separado do `DefaultReq` de modelos.
- [x] 2.2 Implementar `GET /api/prompter/presets`, serializando o catálogo no shape da seção 5 e
      montando `defaults` por iteração de `PRESET_ACTIONS`.
- [x] 2.3 Tratar a query `pid` (opcional) com validação de projeto existente.
- [x] 2.4 Implementar `GET` e `PUT /api/prompter/preset-config` (global).
- [x] 2.5 Implementar `PUT` e `DELETE` das rotas por projeto.
- [x] 2.6 Converter `ValueError` de settings em 422 com mensagem que cite os ids válidos.
- [x] 2.7 Escrever os testes da seção `## Tests`, acrescentando a `tests/test_creditos_api.py`
      (ou a um `tests/test_prompter_api.py` novo, seguindo as fixtures do `conftest.py`).
- [x] 2.8 Rodar ruff + suíte completa e confirmar que as rotas antigas de créditos não regridem.

## Implementation Details

Modificar `studio/creditos/router.py`; acrescentar testes. Nada em `studio/app.py` — o router de
créditos já é registrado lá, então as rotas novas sobem automaticamente.

Pontos de encaixe já verificados no código:

- O módulo já tem as duas famílias que esta task espelha: globais sem pid
  (`get_config` em `studio/creditos/router.py:54`, `put_config` :59) e por projeto
  (`put_project_config` :102, `delete_project_config` :110).
- O padrão de 404 para projeto inexistente é `from ..refs.service import project_dir` +
  `project_dir(pid)` antes do trabalho (:88-92, :95-99) — `project_dir` levanta `KeyError` e o
  handler do núcleo converte em 404. Reusar exatamente esse padrão, não inventar outro.
- O padrão de 422 é `try/except ValueError` → `raise HTTPException(422, str(e)) from e` (:59-65)
  ou checagem direta contra o conjunto de chaves válidas (:80-81). Ambos aceitáveis; preferir o
  `try/except` para não duplicar a regra de validação que vive em settings.
- A serialização do catálogo deve devolver **cópias**, não o dict de módulo, para que um cliente
  não consiga mutar `REALISM_PRESETS` em memória.

## Relevant Files

- `studio/creditos/router.py` — recebe as 5 rotas novas.
- `studio/common/settings.py` — `PRESET_ACTIONS`, `preset_default_for` e os setters (task_01).
- `studio/common/prompter.py` — `REALISM_PRESETS` (task_01).
- `studio/refs/service.py` — `project_dir`, usado para o 404 de projeto inexistente.
- `tests/test_creditos_api.py` — padrão de teste das rotas do módulo.
- `tests/conftest.py` — fixtures de client e de isolamento de `STATE_DIR`/`projects/`.

## Dependent Files

- `studio/etapas/{mood,base,storyboard}/view.js` — task_04 consome `GET /api/prompter/presets`.
- `docs/domains/studio/postman/` — a coleção Postman da feature é gerada a partir destas rotas.

### Related ADRs

- ADR-016 — config de default por ação; estas rotas são a face HTTP do padrão para presets.
- ADR-010 — por isso as rotas moram em `studio/creditos/router.py` e não no núcleo.

## Deliverables

- `GET /api/prompter/presets` (com `?pid=` opcional) em `studio/creditos/router.py`.
- `GET` e `PUT /api/prompter/preset-config` (global).
- `PUT /api/projects/{pid}/prompter/preset-config` e
  `DELETE /api/projects/{pid}/prompter/preset-config/{kind}`.
- Testes de API cobrindo shape, defaults, 422 e 404.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md` neste workflow: casos concretos inline, com o client FastAPI e as fixtures de
isolamento já usadas em `tests/test_creditos_api.py`.

- [x] **T2.1 — shape do catálogo.** `GET /api/prompter/presets` → 200; `len(body["presets"]) == 5`;
      o conjunto de `id` é exatamente os 5 ids do `_techspec.md`; cada item tem as chaves `id`,
      `name`, `default`, `desc_pt`, `rig`, `light`, `grade`, `negative`; `rig` tem `camera`,
      `lens`, `format`, `focal`, `aperture`; exatamente um item tem `default is True` e seu `id`
      é `documentary-street`.
- [x] **T2.2 — defaults opt-in por ação.** No mesmo body, `body["defaults"]` tem as chaves
      `mood`, `base` e `motion`, cada uma valendo `{"preset": None, "source": "code"}`.
- [x] **T2.3 — defaults iteram o registro (contrato do handoff).** Registrando no teste
      `settings.PRESET_ACTIONS["storyboard.script"] = "documentary-street"`, uma nova chamada a
      `GET /api/prompter/presets` traz `body["defaults"]["storyboard.script"] ==
      {"preset": "documentary-street", "source": "code"}` — sem nenhuma alteração de código de
      rota. (Restaurar o registro ao fim do teste.)
- [x] **T2.4 — `?pid=` reflete o override do projeto.** Com um projeto criado pela fixture e
      `PUT /api/projects/{pid}/prompter/preset-config` `{"kind": "base", "preset":
      "sony-venice-night"}`, `GET /api/prompter/presets?pid=<pid>` traz
      `defaults["base"] == {"preset": "sony-venice-night", "source": "project"}`, enquanto
      `GET /api/prompter/presets` (sem pid) segue com `{"preset": None, "source": "code"}`.
- [x] **T2.5 — `?pid=` inexistente.** `GET /api/prompter/presets?pid=nao-existe` → 404.
- [x] **T2.6 — PUT global persiste.** `PUT /api/prompter/preset-config` com
      `{"kind": "mood", "preset": "arri-natural-narrative"}` → 200 com
      `{"kind": "mood", "preset": "arri-natural-narrative", "source": "global"}`; e o
      `config.json` global no `STATE_DIR` da fixture passa a ter
      `prompter_presets.mood == "arri-natural-narrative"`.
- [x] **T2.7 — PUT global não toca `defaults`.** Depois de gravar um default de modelo por
      `PUT /api/creditos/config`, um `PUT /api/prompter/preset-config` mantém
      `GET /api/creditos/config` devolvendo o mesmo default de modelo de antes.
- [x] **T2.8 — `preset: null` é escolha válida.** `PUT /api/prompter/preset-config` com
      `{"kind": "base", "preset": None}` → 200 com `preset` `None` e `source` `"global"`
      (não `"code"`).
- [x] **T2.9 — 422 por kind inválido.** `PUT /api/prompter/preset-config` com
      `{"kind": "nao-existe", "preset": "documentary-street"}` → 422.
- [x] **T2.10 — 422 por preset inválido.** `PUT /api/prompter/preset-config` com
      `{"kind": "base", "preset": "preset-que-nao-existe"}` → 422, e a mensagem cita ao menos um
      id válido do catálogo.
- [x] **T2.11 — DELETE por projeto limpa o override.** Após `PUT` de projeto com
      `sony-venice-night` e `DELETE /api/projects/{pid}/prompter/preset-config/base` → 200 com o
      default resolvido sem o override do projeto (`source` diferente de `"project"`).
- [x] **T2.12 — 404 nas rotas por projeto.** `PUT /api/projects/nao-existe/prompter/preset-config`
      e `DELETE /api/projects/nao-existe/prompter/preset-config/base` → 404.
- [x] **T2.13 — `GET /api/prompter/preset-config`.** Devolve o bloco de defaults globais com uma
      entrada por chave de `PRESET_ACTIONS`.
- [x] **T2.14 — catálogo imutável pela API.** Mutar o dict devolvido pelo endpoint (no teste, via
      o objeto JSON parseado) não altera `prompter.REALISM_PRESETS` — a rota devolve cópia.
- [x] **T2.15 — rotas antigas intactas.** `GET /api/creditos/config`, `GET /api/creditos/models` e
      `GET /api/creditos` continuam 200 com o mesmo shape (regressão do módulo).

## Success Criteria

- Every assigned test case implemented and passing.
- Critérios 6 e 7 da seção 9 do `_techspec.md` fechados.
- Nenhuma rota ou modelo pré-existente de `studio/creditos/router.py` alterado (verificável no
  diff: só adições).
- Nenhuma edição em `studio/app.py`, `studio/steps.py` ou `studio/web/*`.
- `.venv/bin/ruff check studio tests scripts` limpo e `.venv/bin/pytest -q` verde.
