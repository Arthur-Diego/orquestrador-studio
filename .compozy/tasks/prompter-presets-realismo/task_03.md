---
status: pending
title: Campo `preset` aditivo nos 3 endpoints de geração de prompt
type: backend
complexity: medium
---

# Task 3: Campo `preset` aditivo nos 3 endpoints de geração de prompt

## Overview

Liga o catálogo da task_01 aos três endpoints que hoje geram prompt com o Claude: mood, base e o
`video-prompt` do storyboard. O campo `preset` entra no body de forma estritamente aditiva, com
três estados semânticos (ausente = resolver default; `null` = sem preset; `"<id>"` = usar esse), é
validado no router antes de qualquer chamada ao CLI, e volta na resposta para que a UI e os testes
saibam qual preset foi de fato aplicado.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (invariante suprema).** Um body **sem** o campo `preset`, com `PRESET_ACTIONS` no estado
  opt-in de fábrica, MUST produzir exatamente o mesmo comportamento observável de
  `develop@7162c41`: mesmo texto enviado ao CLI, mesmas chaves na resposta além de `"preset"`,
  mesmos registros de histórico. Nenhum teste existente de `tests/test_mood_api.py`,
  `tests/test_base_api.py`, `tests/test_storyboard_api.py` ou `tests/test_storyboard_service.py`
  MUST ser alterado.
- **R2 (três estados).** Campo **ausente** → o serviço resolve `settings.preset_default_for(kind,
  pid)`; campo `null` → nenhum preset, mesmo que haja override configurado; campo `"<id>"` →
  esse preset. A distinção ausente × `null` MUST ser real no modelo pydantic (não colapsar os
  dois em `None`) — use um sentinela ou `model_fields_set`.
- **R3.** Os três endpoints MUST ganhar `"preset": <id | None>` na resposta.
- **R4 (validação antes do CLI).** `preset` desconhecido MUST devolver **422** com mensagem que
  liste os ids válidos, **antes** de qualquer chamada ao Claude CLI (o teste prova que o fake do
  subprocess não foi chamado).
- **R5 (mood).** `POST /api/projects/{pid}/mood/prompts/generate`
  (`studio/etapas/mood/router.py:106`) e `studio/mood/service.py:generate_prompt` (:128) MUST
  aceitar e repassar `preset` a `from_brief`/`from_images`, e o registro inserido em
  `mood/prompts.json` (:163-168) MUST ganhar o campo `preset`. **Não** mexer na tela da etapa 2
  (ver amenda A4 do `_techspec.md`): este endpoint hoje não tem chamador na UI, e o campo entra só
  para deixar o contrato pronto.
- **R6 (base).** `POST /api/projects/{pid}/base/prompts/generate`
  (`studio/etapas/base/router.py:83`) e `studio/base/service.py:generate_prompt` (:289) MUST
  aceitar e repassar `preset` nos três caminhos (`mode="brief"` :315, `no_bias=True` :317,
  padrão :320) e gravar `preset` no registro de `base/prompts.json` (:324-337), **sem** alterar
  os campos `provenance`, `mood_refs` e `palette` já gravados. No caminho `mode="template"`, o
  preset explícito MUST chegar a `fallback_template`; o preset apenas resolvido por default
  MUST NOT alterar o template (regra de determinismo do `_techspec.md` §4).
- **R7 (storyboard).** `POST /api/projects/{pid}/storyboard/video-prompt`
  (`studio/etapas/storyboard/router.py:211`) e `studio/storyboard/service.py:video_prompt` (:736)
  MUST aceitar e repassar `preset` para `from_images("motion", ...)` / `from_brief("motion", ...)`
  e devolvê-lo na resposta. Conforme a **amenda A5** do `_techspec.md`, esta task MUST NOT
  alterar o schema de `scenes.json` (ADR-018/022) — não há `prompts.json` no storyboard.
- **R8 (matriz de erro preservada).** Cada router MUST manter o próprio padrão de conversão de
  exceção, sem uniformizá-los: mood decide 409×502 pelo texto da mensagem
  (`studio/etapas/mood/router.py:108-114`); base decide pela causa real, via
  `prompter.available()` (`studio/etapas/base/router.py:86-96`); storyboard usa o helper `_guard`
  com o vocabulário próprio `sb.Invalid` / `sb.Precondition` (:108-115). O 422 do preset entra
  como validação nova, sem tocar nos ramos existentes.
- **R9.** A validação MUST reusar a regra que já vive em `settings`/`prompter` (catálogo como
  fonte única) — MUST NOT haver uma segunda lista de ids válidos escrita à mão em router ou
  service.
</requirements>

## Subtasks

- [ ] 3.1 Acrescentar o campo `preset` (nullable, distinguindo ausente de `null`) aos modelos
      `PromptGenReq` de mood e base e ao `VideoPromptReq` do storyboard.
- [ ] 3.2 Implementar a validação de id desconhecido → 422 nos três routers, antes da chamada ao
      serviço, com mensagem citando os ids válidos.
- [ ] 3.3 Propagar `preset` por `studio/mood/service.py:generate_prompt`, incluindo a resolução
      do default por `settings.preset_default_for("mood", pid)` quando o campo vier ausente.
- [ ] 3.4 Idem em `studio/base/service.py:generate_prompt`, cobrindo os três caminhos de chamada
      ao prompter e o caminho `template`.
- [ ] 3.5 Idem em `studio/storyboard/service.py:video_prompt` (ação `motion`).
- [ ] 3.6 Gravar `preset` nos registros de `mood/prompts.json` e `base/prompts.json`.
- [ ] 3.7 Escrever os testes da seção `## Tests`.
- [ ] 3.8 Rodar ruff + suíte completa e confirmar zero regressão nas três etapas.

## Implementation Details

Modificar seis arquivos de produção: `studio/etapas/{mood,base,storyboard}/router.py` e
`studio/{mood,base,storyboard}/service.py`. Testes em `tests/test_mood_api.py`,
`tests/test_base_api.py` e `tests/test_storyboard_service.py` (+ `tests/test_storyboard_api.py`
se for testar a rota por HTTP).

Detalhes já verificados no código (usar como mapa, conferir antes de editar):

- **mood**: `PromptGenReq` em `studio/etapas/mood/router.py:65-78` (campos `mode`, `instruction`,
  `image_ids`, `purpose`, `tone`, `reference`, `model`, `variation`, `no_people`,
  `explore_prompt`); rota :106-114 chama `mood.generate_prompt(...)` posicionalmente — ao
  acrescentar parâmetro, preferir keyword para não depender da ordem.
  `studio/mood/service.py:generate_prompt` :128-169; histórico gravado em :163-168.
- **base**: `PromptGenReq` em `studio/etapas/base/router.py:58-67`; rota :83-96.
  `studio/base/service.py:generate_prompt` :289-340; três chamadas ao prompter em :315, :317,
  :320; histórico em :324-337 (entry já carrega `provenance`, `mood_refs`, `palette`).
- **storyboard**: `VideoPromptReq` em `studio/etapas/storyboard/router.py:80-83`; rota :211-213
  via `_guard`. `studio/storyboard/service.py:video_prompt` :736-764; chamadas em :757/:758;
  atenção ao `except Exception` de :761-762, que engole falha do Claude e cai no template — o
  `preset` da resposta precisa continuar coerente nesse caminho de fallback.
- **Cuidado com o mock nos testes do storyboard**: `tests/test_storyboard_service.py` faz
  `monkeypatch.setattr(sb.prompter, ...)` — mocka o prompter **através do módulo do serviço**.
  Testes novos devem seguir o mesmo estilo, senão o mock não pega.

## Relevant Files

- `studio/etapas/mood/router.py`, `studio/mood/service.py` — endpoint e serviço de mood.
- `studio/etapas/base/router.py`, `studio/base/service.py` — endpoint e serviço de base.
- `studio/etapas/storyboard/router.py`, `studio/storyboard/service.py` — `video-prompt`.
- `studio/common/prompter.py`, `studio/common/settings.py` — catálogo e resolução (task_01).
- `tests/conftest.py` — fixtures `studio_env` (isola `STATE_DIR`/`projects/` por env var) e
  `client`; não há fixture central de fake do Claude — cada teste monkeypatcha `prompter.BIN` e
  `prompter.subprocess.run`.
- `tests/test_base_api.py` — já tem o padrão completo de teste de `prompts/generate` com Claude
  fakeado e a matriz 200/409/422/502; é o modelo a seguir.

## Dependent Files

- `studio/etapas/{base,storyboard}/view.js` — task_04 passará a enviar o campo.
- `tests/test_mood_view.py` — **não pode** passar a citar `mood/prompts/generate`; a tela da
  etapa 2 fica fora (amenda A4).

### Related ADRs

- ADR-014 — tirou a criação de prompt de vibe da etapa 2; é a razão de o endpoint de mood estar
  sem chamador e de a UI de mood ficar fora do escopo.
- ADR-018 / ADR-022 — schema de `scenes.json`; por isso o storyboard não persiste `preset`.
- ADR-016 — resolução de default por ação.

## Deliverables

- Campo `preset` aceito e devolvido pelos três endpoints, com os três estados semânticos.
- 422 para id desconhecido, antes de qualquer chamada ao CLI.
- `preset` gravado no histórico de mood e de base.
- Testes cobrindo retrocompatibilidade, os três estados, o 422 e o histórico.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md` neste workflow: casos concretos inline. Claude fakeado pelo padrão de
`tests/test_base_api.py` (monkeypatch de `prompter.BIN` + `prompter.subprocess.run`).

- [ ] **T3.1 — body antigo continua 200 (base).** `POST .../base/prompts/generate` com
      `{"mode": "images"}` (sem `preset`) → 200, resposta com as mesmas chaves de hoje mais
      `"preset": None`, e o prompt capturado no fake **não** contém nenhum nome de câmera do
      catálogo.
- [ ] **T3.2 — preset explícito chega ao CLI (base).** Mesmo endpoint com
      `{"mode": "images", "preset": "arri-natural-narrative"}` → 200 com
      `"preset": "arri-natural-narrative"`, e o prompt capturado contém "ARRI Alexa Mini LF".
- [ ] **T3.3 — `null` explícito desliga (base).** Com um override global gravado
      (`set_global_preset("base", "documentary-street")`), um body `{"mode": "images",
      "preset": None}` → 200 com `"preset": None` e prompt sem termos de rig; enquanto o mesmo
      body **sem** o campo → 200 com `"preset": "documentary-street"` e prompt com "Blackmagic
      Pocket 6K Pro". Este é o caso que prova a distinção ausente × `null`.
- [ ] **T3.4 — 422 antes do CLI (base).** Body `{"mode": "images", "preset": "nao-existe"}` →
      422; a mensagem cita ao menos um id válido; e o fake de `subprocess.run` registra
      **zero** chamadas.
- [ ] **T3.5 — histórico da base grava o preset.** Após um generate com
      `preset="red-commercial-precision"`, `GET` do histórico (ou leitura direta de
      `projects/<pid>/base/prompts.json`) traz o campo `preset` com esse id no registro mais
      recente, e os campos `provenance`/`mood_refs`/`palette` continuam presentes.
- [ ] **T3.6 — matriz de erro da base intacta.** Repetir as asserções já existentes: 409 com
      `prompter.BIN = None`, 200 com `mode="template"`, 422 com `mode="magico"`, 502 quando
      `subprocess.run` levanta — todas continuam valendo com o campo `preset` presente no body.
- [ ] **T3.7 — `template` só usa preset explícito.** `{"mode": "template", "preset":
      "red-commercial-precision"}` → o prompt devolvido tem `Camera:` com "RED V-Raptor";
      `{"mode": "template"}` com override global configurado → template byte-idêntico ao atual
      (contém "RED Komodo 6K, 50mm lens, T2.8").
- [ ] **T3.8 — mood: body antigo e preset explícito.** `POST .../mood/prompts/generate` com
      `{"mode": "brief"}` → 200 com `"preset": None`; com `{"mode": "brief", "preset":
      "sony-venice-night"}` → 200 com esse preset e prompt contendo "Sony Venice 2".
- [ ] **T3.9 — mood: 422 e histórico.** `preset` desconhecido → 422 sem chamar o CLI; após um
      generate com preset, o registro no topo de `projects/<pid>/mood/prompts.json` tem o campo
      `preset`.
- [ ] **T3.10 — storyboard: preset no `video_prompt`.** No nível de serviço (estilo
      `tests/test_storyboard_service.py`, com `monkeypatch.setattr(sb.prompter, ...)`):
      `sb.video_prompt(pid, "cena01", "an astronaut walking", {"mode": "single"})` sem preset
      devolve `preset: None` e chama o prompter com `preset=None`; com
      `preset="anamorphic-film-look"` devolve esse id e repassa ao prompter.
- [ ] **T3.11 — storyboard: 422 por HTTP.** `POST .../storyboard/video-prompt` com
      `{"scene_id": "cena01", "description": "x", "preset": "nao-existe"}` → 422.
- [ ] **T3.12 — storyboard: fallback do Claude preserva coerência.** Quando o prompter levanta
      (caminho do `except Exception` de `video_prompt`), a resposta ainda traz a chave `preset`
      com o id pedido, sem 500.
- [ ] **T3.13 — `scenes.json` intocado.** Após um `video-prompt` com preset, o arquivo
      `projects/<pid>/storyboard/scenes.json` tem exatamente as mesmas chaves de antes
      (nenhum campo novo) — prova da amenda A5.
- [ ] **T3.14 — a tela da etapa 2 continua sem geração.** `tests/test_mood_view.py` segue verde
      sem edição: `"mood/prompts/generate"` continua ausente de `studio/etapas/mood/view.js`.

## Success Criteria

- Every assigned test case implemented and passing.
- Critérios 8 e 9 da seção 9 do `_techspec.md` fechados.
- Nenhum teste pré-existente das três etapas alterado (verificável no diff: só adições).
- Nenhuma edição em `studio/app.py`, `studio/steps.py`, `studio/web/*` ou `studio/moodboards/*`.
- `.venv/bin/ruff check studio tests scripts` limpo e `.venv/bin/pytest -q` verde.
