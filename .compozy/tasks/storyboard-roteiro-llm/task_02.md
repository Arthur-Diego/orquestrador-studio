---
status: pending
title: Job de roteiro, `script.json` e rotas da etapa 4
type: backend
complexity: high
---

# Task 2: Job de roteiro, `script.json` e rotas da etapa 4

## Overview

Entrega o servidor da feature: um job assíncrono que monta o brief, resolve o preset e as
imagens de contexto, chama `prompter.script(...)` (task_01), valida a resposta e grava
`storyboard/script.json` de forma atômica — mais as três rotas aditivas da etapa 4, os campos
aditivos no status e o registro da ação `storyboard.script` no catálogo de presets. É a fatia
que carrega quase todos os critérios de aceite, inclusive a metade servidor do critério
`[cross-feature]` da wave.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (invariante suprema da feature).** NENHUM caminho de código desta task pode escrever em
  `storyboard/scenes.json`, chamar `save_scenes`, `_write_scenes`, `_normalize` ou `render`. O
  roteiro é sugestão: vive só em `storyboard/script.json`. Um teste MUST provar que, depois de um
  job completo, o `scenes.json` do projeto continua byte a byte idêntico.
- **R2 (zero crédito).** Nenhuma chamada a `hf.*`, nenhum `settings.record_generation`, nenhuma
  rota de `cost`. O Claude CLI é assinatura local. Um teste MUST provar que o livro-caixa não
  ganhou registro depois de um job completo.
- **R3 — registro da ação (amenda A2).** O módulo MUST registrar, em import time,
  `settings.PRESET_ACTIONS.setdefault("storyboard.script", "documentary-street")`.
  **É PROIBIDO editar `studio/common/settings.py`** — o dict é aberto de propósito e a docstring
  dele já cita esta feature. Depois do registro, `GET /api/prompter/presets` MUST passar a exibir
  a chave `storyboard.script` no mapa `defaults` sozinho (teste obrigatório: é o handoff da wave).
- **R4 — três estados do campo `preset` (amenda A3).** O body MUST distinguir campo AUSENTE
  (resolve o default por `settings.resolve_preset("storyboard.script", pid, PRESET_UNSET)`),
  `null` (sem preset) e `"<id>"` (usa esse). Reuse a sentinela `settings.PRESET_UNSET` /
  `settings.PresetArg` da provedora, no mesmo padrão do `video_prompt` já existente no serviço.
  Id fora de `prompter.REALISM_PRESETS` → **422 antes de qualquer chamada ao CLI**.
- **R5 — job (ADR-006) e o NOME do registry.** MUST existir um `JobRegistry` PRÓPRIO do roteiro no
  módulo, e ele MUST se chamar **`_story_registry`**. Motivo (terreno verificado, sobrepõe o nome
  `_script_registry` sugerido na §5 do `_techspec.md`): `studio/common/reset.py::_registries`
  descobre os registros da etapa por uma lista FECHADA de nomes de atributo —
  `("_registry", "registry", "_story_registry")` — e `_story_registry` é o único slot livre no
  módulo (`_registry` é da ideação, `registry` é o dos ângulos reexportado). Um nome fora dessa
  tripla (inclusive `_script_registry`) simplesmente NÃO é descoberto pelo reset. A troca é de
  identificador, sem efeito em contrato público.
  **Não edite `studio/common/reset.py`.** Observação registrada e fora de escopo: o
  `_video_registry` (:777) já hoje não é descoberto pelo reset — gap PRÉ-EXISTENTE, não corrija
  aqui. Um job de roteiro por projeto; job já em andamento → 409 com a mensagem da matriz da §6.
- **R6 — validações e matriz de erros da seção 6 do `_techspec.md`**, todas ANTES de iniciar a
  thread: projeto inexistente → 404 (via `project_dir`); `base/base_final.png` ausente → 409 com
  a mensagem de precondição já usada pela etapa; `prompter.available()` falso → 409 com a
  mensagem "Claude CLI não encontrado no PATH: escreva as cenas manualmente (aula 010) ou instale
  o Claude Code"; `count` fora de 1..`MAX_SCENES` → 422; `preset` desconhecido → 422 listando os
  ids válidos; `model_target` fora de `SCRIPT_MODELS` → 422; `instruction` acima de `MAX_TEXT`
  (300) → 422. Com qualquer 409/422, **nenhum arquivo é criado**.
- **R7 — modelo alvo (gate W3 P3, amenda A6).** MUST existir a constante nova `SCRIPT_MODELS` no
  serviço, contendo SOMENTE `nano_banana_2` (Nano Banana Pro) como fonte única dos ids aceitos e
  do default. `MODELS` (que tem `gpt_image_2`) continua intocado e serve só ao caminho pago de
  ideação.
- **R8 — imagens de contexto.** O job MUST montar a lista com `base/base_final.png` primeiro e
  até 3 imagens do mood selecionado do projeto, em ordem de arquivo, respeitando o teto
  `prompter.MAX_IMAGES` (4). Sem mood selecionado, segue só com a base. As imagens MUST existir
  em disco antes de ir para o prompter. **Fonte obrigatória do mood (terreno verificado):**
  a pasta é `mood/selected/` e quem já a lê é `studio/mood/service.py::current(pid)` (leitura
  pura, ordenada por nome de arquivo) — reuse essa função em vez de varrer o diretório à mão ou
  inventar convenção de nome. Se o import de módulo criar ciclo, faça o import DENTRO da função
  (padrão já usado no repositório). Se a pasta não existir, a lista fica só com a base.
- **R9 — aspect ratio.** MUST vir de `_aspect_ratio(root)` (projeto → `16:9` quando ausente ou
  inválido) e **não** do body. MUST ir para o brief do prompter e ser persistido em `script.json`.
- **R10 — arcos.** O job MUST calcular o arco de cada cena com `scene_arc(n, count)` já existente
  e passar a lista de ids ao `prompter.script(...)`; o LLM não decide arco (task_01 R8).
- **R11 — persistência.** `storyboard/script.json` MUST ser gravado com
  `common.atomic.write_json_atomic`, e SOMENTE quando o job termina com resposta válida. Job em
  erro MUST deixar o `script.json` anterior intacto. O schema é o da seção 5.3 do `_techspec.md`
  (`generated_at`, `preset`, `model_target`, `aspect_ratio`, `count`, `source`, `seconds`,
  `notes_pt`, `scenes[]`), com `text` truncado em `MAX_SCENE_TEXT` (500) pelo SERVIÇO, registrando
  nota no `log` do job quando truncar.
- **R12 — rotas aditivas** em `studio/etapas/storyboard/router.py`, todas passando pelo `_guard`
  existente (que já traduz `Invalid`→422 e `Precondition`→409):
  `POST /api/projects/{pid}/storyboard/script/generate`,
  `GET /api/projects/{pid}/storyboard/script/job`,
  `GET /api/projects/{pid}/storyboard/script`. Nenhuma rota existente muda de assinatura,
  resposta ou mensagem.
- **R13 — status aditivo (§5.4).** `GET /api/projects/{pid}/storyboard` MUST ganhar
  `script: {exists, generated_at}` e `script_preset_default`, sem alterar nenhum campo existente.
  MUST também expor o que a tela precisa para não adivinhar: os ids/labels de `SCRIPT_MODELS` e a
  disponibilidade do Claude CLI (para a tela desabilitar o botão) — nomes livres, aditivos.
- **R14 — `GET /script` sem geração** → 200 `{"script": null}`, nunca 404.
- **R15 — observabilidade (§7).** Log `script_generate` no início do job com
  `{pid, preset, count, model_target, aspect_ratio, images}` e `script_job` no fim com
  `{pid, state, scenes, seconds, source}`, no logger `studio.storyboard` já existente, no formato
  `evento %s` + dict usado pelo módulo. O roteiro completo NUNCA vai para o log.
- **R16 — docstring (amenda A7).** A docstring do módulo (`studio/storyboard/service.py`, o
  trecho "nada de roteiro por LLM") MUST receber ressalva **aditiva** `[extensão]` citando a
  ADR-025 — o texto original permanece legível, como registro do que a aula ensina. Não reescreva
  a docstring.
- **R17.** Testes sem rede e sem processo real: o Claude CLI é sempre fake (monkeypatch de
  `prompter.BIN`/`subprocess.run`, ou monkeypatch de `prompter.script`), ADR-008. O padrão de
  espera do job já usado na etapa é o loop de polling limitado (`for _ in range(100)` sobre a
  rota `job`, sem `sleep`), como em `tests/test_storyboard_api.py::test_cli_generate_and_job_polling`.
- **R18 — fora de escopo, não invente.** O guia da etapa
  (`studio/etapas/storyboard/guide.py`: `WHAT`, `CHECKLIST`, `guide(pid)`) **não** faz parte
  desta feature: a seção 4 do `_techspec.md` não o inclui. Não acrescente item de checklist nem
  `check`/`output` novo lá. Não toque `studio/etapas/storyboard/angles.py` nem
  `studio/storyboard/angles.py`.
</requirements>

## Subtasks

- [ ] 2.1 Ler `_techspec.md` inteiro (seção 0 amendas, 5.1–5.4, 6, 7, 9) e o `task_01.md` para
      conhecer a assinatura de `prompter.script(...)`.
- [ ] 2.2 Ler `studio/storyboard/service.py` e `studio/etapas/storyboard/router.py` inteiros,
      mapeando os padrões já usados: `_registry`/`_video_registry`, `job_status`, `Invalid`/
      `Precondition`, `_guard`, `_aspect_ratio`, `scene_arc`, `base_rel`.
- [ ] 2.3 Registrar a ação `storyboard.script` em `settings.PRESET_ACTIONS` (R3), sem editar
      `settings.py`.
- [ ] 2.4 Acrescentar `SCRIPT_MODELS`, `SCRIPT_FILE` e as demais constantes do roteiro (R7, R11).
- [ ] 2.5 Implementar as validações de pré-requisito e de parâmetros (R6), com as mensagens
      exatas da matriz da seção 6.
- [ ] 2.6 Implementar `script_generate` (job em thread com `_script_registry`), incluindo brief,
      imagens de contexto (R8), aspect ratio (R9), arcos (R10) e chamada ao prompter.
- [ ] 2.7 Implementar a validação/normalização da resposta, o truncamento de `text` em 500 e a
      gravação atômica de `script.json` (R11).
- [ ] 2.8 Implementar `script_status` e `load_script` (R14).
- [ ] 2.9 Acrescentar os campos aditivos ao `status` da etapa (R13).
- [ ] 2.10 Acrescentar as três rotas ao router (R12).
- [ ] 2.11 Acrescentar a ressalva `[extensão]` + ADR-025 na docstring do módulo (R16).
- [ ] 2.12 Escrever os testes da seção `## Tests` em `tests/test_storyboard_service.py` e
      `tests/test_storyboard_api.py`.
- [ ] 2.13 Rodar `make verify` e conferir a baseline de 1092 testes.

## Implementation Details

Arquivos de produção a modificar: `studio/storyboard/service.py` e
`studio/etapas/storyboard/router.py`. **Nenhum outro** — em especial, `studio/common/settings.py`
é proibido (R3) e `studio/common/prompter.py` é da task_01.

Padrões já no código a reusar sem reinventar:

- `JobRegistry` (`studio/common/jobs.py`): `start(key, total, fn, **extras)` levanta
  `RuntimeError` quando já há job `running` para a chave; `status(key)` devolve `{"state":"idle"}`
  quando nunca rodou. O `job_status` da ideação mostra o formato de resposta a espelhar
  (`{"done":0,"total":0,...,**registry.status(pid)}`).
- Exceções do domínio: `Invalid` → 422 e `Precondition` → 409, traduzidas pelo `_guard` do router.
  Rotas que só leem chamam `refs.project_dir(pid)` para o 404.
- `_aspect_ratio(root)`, `scene_arc(n, total)`, `SCENE_ARC`, `DEFAULT_SCENES`, `MAX_SCENES`,
  `MAX_TEXT`, `MAX_SCENE_TEXT`, `BASE_IMAGE`, `base_rel(root)` — todos já existem no serviço.
- `settings.resolve_preset(kind, pid, preset)` devolve `(resolvido, explícito)`; o `video_prompt`
  do mesmo arquivo é o exemplo vivo de como o padrão atravessa router → serviço com
  `settings.PresetArg` / `settings.PRESET_UNSET`.
- `common.atomic.write_json_atomic(path, obj, **json_kw)` para o `script.json`.

Sobre as imagens do mood: descubra em código onde o mood selecionado do projeto é persistido e
use essa fonte — **não invente caminho nem crie uma segunda convenção**. Se a pasta não existir no
projeto, o job segue só com a base (R8).

### Relevant Files

- `studio/storyboard/service.py` — módulo da etapa: docstring (:1-14), constantes (:47-50),
  `SCENE_ARC` (:78), `_registry` (:117), `status` (:182), `scene_arc` (:201), `save_scenes` (:550,
  **proibido tocar**), `_video_registry` (:777), `_aspect_ratio` (:798), `video_prompt` (:857 —
  molde do padrão de preset).
- `studio/etapas/storyboard/router.py` — `_guard` (~:76), rotas de status/scenes/job existentes
  (~:88-200), padrão de `BaseModel` por request.
- `studio/common/jobs.py` — `JobRegistry` completo.
- `studio/common/settings.py` — **leitura apenas**: `PRESET_ACTIONS` (:98), `PresetUnset`/
  `PRESET_UNSET`, `preset_default_for` (:236), `resolve_preset` (:263).
- `studio/common/atomic.py:88` — `write_json_atomic`.
- `studio/creditos/router.py:154` — `GET /api/prompter/presets`, o endpoint cujo mapa `defaults`
  deve passar a exibir `storyboard.script` (teste de R3).
- `tests/test_storyboard_service.py`, `tests/test_storyboard_api.py` — onde os casos entram.
- `tests/test_prompter.py` — padrão do fake do Claude CLI.

### Dependent Files

- `studio/common/prompter.py` — consumido (task_01); não editar aqui.
- `studio/etapas/storyboard/view.js` / `view.html` — a task_03 consome as rotas e os campos de
  status definidos aqui.
- `tests/test_api.py`, `tests/test_reset_api.py`, `tests/test_creditos_api.py` — travam rotas e
  reset da etapa; devem continuar passando sem edição (prova de que tudo foi aditivo).
- `studio/common/reset.py` — descobre os registries da etapa pelo nome; por isso o registry novo
  termina em `_registry` (R5).

### Related ADRs

- ADR-006 — jobs em thread + polling; sem estado fora de arquivo.
- ADR-016 — preset default por ação via settings (projeto → global → código); livro-caixa é só
  de créditos Higgsfield, e o roteiro não entra nele (R2).
- ADR-018 / ADR-022 — schema de `scenes.json` preservado (R1).
- ADR-010 — núcleo intocado.
- ADR-025 — roteiro por LLM como extensão opt-in (aprovada no gate W3; citada na docstring, R16).

## Deliverables

- Job, validações, persistência atômica, status aditivo e três rotas novas, funcionando de ponta
  a ponta com o Claude CLI fake.
- Ação `storyboard.script` visível no mapa `defaults` de `GET /api/prompter/presets`, com
  `preset: "documentary-street"` e `source: "code"`.
- Ressalva `[extensão]` + ADR-025 na docstring do módulo.
- Casos novos em `tests/test_storyboard_service.py` e `tests/test_storyboard_api.py`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md` neste workflow. Casos concretos, todos com o Claude CLI fake:

- [ ] **T2.1 — caminho feliz (critério 1).** Projeto com `base/base_final.png`; `POST
      script/generate` com `{"count": 5}`; esperado: 200 com estado inicial do job; depois de o
      job terminar, `GET script/job` devolve `state == "done"` e `storyboard/script.json` existe
      com 5 cenas, cada uma com `text` não vazio (≤ 500) e `image_prompt` não vazio.
- [ ] **T2.2 — arco (critério 2).** Com `count=5`: `scenes[0].arc == "comeco"`,
      `scenes[1].arc == "descoberta"`, `scenes[2].arc == "acao"`, `scenes[3].arc == "acao"`,
      `scenes[4].arc == "desfecho"`.
- [ ] **T2.3 — `[cross-feature]` (critério 3a).** Gerar com `preset="documentary-street"`;
      esperado: para CADA cena de `script.json`, o `image_prompt` contém literalmente
      `REALISM_PRESETS["documentary-street"]["rig"]["camera"]`, `["lens"]` e `["format"]`.
      O teste MUST ler os valores do catálogo, nunca strings hardcoded.
- [ ] **T2.4 — `[cross-feature]` (handoff da chave, R3).** `GET /api/prompter/presets` devolve
      `defaults["storyboard.script"] == {"kind": "storyboard.script",
      "preset": "documentary-street", "source": "code"}`. E `GET /api/prompter/presets?pid=<pid>`
      idem.
- [ ] **T2.5 — preset default (critério 4).** `POST script/generate` SEM o campo `preset`;
      esperado: `script.json["preset"] == "documentary-street"` e o rig desse preset no
      `image_prompt` das cenas.
- [ ] **T2.6 — preset `null`.** Body com `"preset": null`; esperado: `script.json["preset"]` é
      `null` e o prompt enviado ao CLI não traz rig fixo.
- [ ] **T2.7 — override de projeto.** Gravar override de projeto para `storyboard.script` com
      `arri-natural-narrative` (via `PUT /api/projects/{pid}/prompter/preset-config`, rota da
      provedora); gerar sem `preset`; esperado: `script.json["preset"] == "arri-natural-narrative"`.
- [ ] **T2.8 — preset desconhecido = 422 antes do CLI.** Body `{"preset": "nao-existe"}`;
      esperado: 422 citando os ids válidos, `subprocess.run` NUNCA chamado, nenhum arquivo criado.
- [ ] **T2.9 — aspect ratio (critério 5).** Projeto com `aspect_ratio: "9:16"`; esperado:
      `script.json["aspect_ratio"] == "9:16"` e `"9:16"` aparece no prompt enviado ao CLI. Projeto
      sem `aspect_ratio` → `"16:9"`.
- [ ] **T2.10 — Claude ausente = 409 (critério 8).** `prompter.BIN = None`; esperado: 409 com a
      mensagem da matriz, e `storyboard/script.json` NÃO é criado.
- [ ] **T2.11 — base ausente = 409.** Projeto sem `base/base_final.png`; esperado: 409 com a
      mensagem de precondição da etapa; nenhum arquivo criado.
- [ ] **T2.12 — job concorrente = 409.** Segundo `POST script/generate` enquanto o primeiro está
      `running`; esperado: 409.
- [ ] **T2.13 — `count` inválido = 422.** `count=0` e `count=11`; esperado: 422 nos dois.
- [ ] **T2.14 — `model_target` inválido = 422 (gate W3 P3).** `model_target="gpt_image_2"`;
      esperado: 422 (v1 aceita só `nano_banana_2`). `model_target="nano_banana_2"` passa.
- [ ] **T2.15 — `instruction` longa = 422.** 301 caracteres; esperado: 422.
- [ ] **T2.16 — resposta inválida = job em erro (critério 9).** Fake devolve 3 cenas com
      `count=5`; esperado: `GET script/job` com `state == "error"` e `error` preenchido; se já
      existia um `script.json` de um job anterior, ele permanece byte a byte idêntico.
- [ ] **T2.17 — `GET /script` sem geração (critério 10).** Projeto novo; esperado: 200 com
      `{"script": null}` (não 404). Depois de gerar: 200 com o schema da §5.3.
- [ ] **T2.18 — texto longo é truncado.** Fake devolve uma cena com `text` de 700 caracteres;
      esperado: `script.json` guarda 500 e o `log` do job registra o truncamento.
- [ ] **T2.19 — `scenes.json` intocado (critério 1 / R1).** Escrever textos nas cenas 1 e 3,
      capturar os bytes de `storyboard/scenes.json`, rodar um job completo; esperado: os bytes do
      arquivo são idênticos depois do job.
- [ ] **T2.20 — zero crédito (critério 11 / R2).** Depois de um job completo, o livro-caixa do
      projeto não ganhou registro e nenhum atributo de `hf` foi chamado (monkeypatch que falha se
      `hf.generate` for tocado).
- [ ] **T2.21 — status aditivo (§5.4).** `GET /api/projects/{pid}/storyboard` antes da geração:
      `script.exists is False` e `script_preset_default == "documentary-street"`; depois:
      `script.exists is True` com `generated_at` preenchido. Todos os campos anteriores do status
      continuam presentes e com o mesmo valor.
- [ ] **T2.22 — imagens de contexto (R8).** Projeto com base + 5 imagens no mood selecionado;
      esperado: no máximo 4 caminhos chegam ao prompter, com a base em primeiro lugar. Projeto
      sem mood selecionado: só a base, e o job termina `done`.
- [ ] **T2.23 — reset da etapa descobre o registry novo (R5).** `studio.common.reset._registries`
      (ou o caminho HTTP do reset da etapa) devolve o `_story_registry` do roteiro junto dos
      outros; enquanto um job de roteiro está `running`, o reset da etapa recusa com 409. Um
      assert direto sobre o nome do atributo (`hasattr(service, "_story_registry")`) trava a
      escolha de R5 contra regressão de renomeação.

## Success Criteria

- Every assigned test case implemented and passing.
- `make verify` verde, sem editar nenhum teste pré-existente.
- `git diff` desta task toca apenas `studio/storyboard/service.py`,
  `studio/etapas/storyboard/router.py` e os dois arquivos de teste citados.
- `git diff` NÃO contém `studio/common/settings.py`, `studio/common/prompter.py`, `app.py`,
  `steps.py` nem `studio/web/`.
- Uma busca por `save_scenes`, `_write_scenes`, `record_generation` e `hf.` no diff de produção
  não retorna nenhuma chamada nova.
