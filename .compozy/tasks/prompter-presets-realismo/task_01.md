---
status: completed
title: Catálogo de presets no prompter + resolução por ação em settings
type: backend
complexity: high
---

# Task 1: Catálogo de presets no prompter + resolução por ação em settings

## Overview

Entrega a fundação de dados da feature: o dict `REALISM_PRESETS` em `studio/common/prompter.py`
(transcrição, para dentro do repositório, dos 5 rig presets da skill externa
`generate_realistic_prompt_images`), o helper `preset_block()` que vira instrução em inglês no
prompt do papel, o parâmetro opcional `preset` nas três funções públicas do prompter, e a
resolução de preset default **por ação** em `studio/common/settings.py` no padrão ADR-016
(projeto → global → código). Todas as demais tasks da feature consomem o que sai daqui, e a
feature `storyboard-roteiro-llm` (sub-wave 2) consome isto como contrato congelado.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (invariante suprema).** Com `preset=None`, `from_brief`, `from_images` e
  `fallback_template` MUST produzir string de prompt e dict de retorno **byte-idênticos** aos de
  `develop@7162c41`. Os testes existentes de `tests/test_prompter.py` MUST passar sem qualquer
  alteração no arquivo. Esta é a fidelidade à aula exigida pelo gate W3 (P1) e pelo ADR-004.
- **R2.** `REALISM_PRESETS` MUST conter exatamente os 5 ids da seção 5 do `_techspec.md`
  (`documentary-street`, `arri-natural-narrative`, `red-commercial-precision`,
  `sony-venice-night`, `anamorphic-film-look`), cada um com as chaves `id`, `name`, `desc_pt`,
  `rig` (com `camera`, `lens`, `format`, `focal`, `aperture`), `light`, `grade`, `fidelity` e
  `negative` (lista). Exatamente `documentary-street` MUST ter `default: true`.
- **R3.** Os valores de rig/luz/grade MUST ser a transcrição fiel da tabela 4.5 da skill externa
  reproduzida na seção 5 do `_techspec.md`; `fidelity` e a lista base de `negative` vêm do
  TEMPLATE UNIVERSAL e das REGRAS DE OURO, também já literais no `_techspec.md`. A skill em
  `~/.claude/skills/` MUST NOT ser lida em runtime nem referenciada por path no código — o dict
  é a única fonte de runtime.
- **R4.** `preset_block(preset_id)` MUST devolver instrução em inglês com menos de 80 palavras,
  mandando usar o corpo/lente/formato/abertura exatos na linha `Camera:`, a luz do preset como
  fonte dominante em `Lighting:`, a grade em `Color grading:` e o vocabulário de fidelidade no
  parágrafo/`Style:`. MUST levantar `KeyError` para id desconhecido. MUST NOT instruir a criar
  seção nova nem alterar o limite de 120–220 palavras do `PROMPT_FORMAT`.
- **R5.** `from_brief(kind, brief, preset=None)` e
  `from_images(kind, images, instruction="", brief=None, preset=None)` MUST aceitar o parâmetro
  como keyword opcional em última posição, preservando as assinaturas atuais para os chamadores
  existentes. Com preset, o bloco entra logo após o texto do papel; a resposta MUST ganhar a
  chave `"preset"` com o id, e `"preset": None` quando não houver preset.
- **R6.** Com preset, os itens de `negative` do preset MUST ser mesclados ao campo `negative` da
  resposta (string separada por vírgula), sem duplicar termos já presentes e sem descartar o que
  o Claude devolveu. Sem preset, o campo MUST sair exatamente como o CLI devolveu.
- **R7.** `fallback_template(kind, brief, variation=0, no_people=True, preset=None)` com preset
  explícito MUST preencher as linhas `Camera:`, `Lighting:` e `Color grading:` com o rig, a luz e
  a grade do preset; sem preset, MUST devolver o template atual sem uma vírgula de diferença.
- **R8.** `settings.PRESET_ACTIONS` MUST ser um dict `{ação: preset default de código | None}`
  inicializado com `{"mood": None, "base": None, "motion": None}`, **extensível por outros
  módulos em import time** — a feature consumidora registra `"storyboard.script"` sem editar
  esta frente. `settings.PROMPTER_KINDS` MUST permanecer a tupla `("mood", "base", "motion")`,
  usada pelos routers de etapa, mas MUST NOT ser o universo de validação da configuração.
- **R9.** `settings.preset_default_for(kind, pid=None)` MUST devolver
  `{"kind", "preset", "source"}` com `source ∈ {"project", "global", "code"}`, resolvendo na
  ordem projeto → global → código, e MUST aceitar qualquer chave registrada em `PRESET_ACTIONS`,
  inclusive chaves pontuadas no padrão de `settings.ACTIONS` (ex.: `"storyboard.script"`).
  Chave não registrada MUST levantar `ValueError`.
- **R10 (semântica de `null` × ausente).** Override persistido com valor `null` significa "sem
  preset, escolhido de propósito": **encerra a cadeia** e devolve `preset: None` com o `source`
  daquele nível. Chave **ausente** cai para o próximo nível. Override apontando para id que não
  existe em `REALISM_PRESETS` MUST ser ignorado e cair para o próximo nível (mesma semântica de
  `default_for` para modelos).
- **R11.** `set_global_preset(kind, preset)`, `set_project_preset(pid, kind, preset)` e
  `clear_project_preset(pid, kind)` MUST persistir sob a chave nova `prompter_presets` do
  `config.json` (global e de projeto), via `common.atomic.write_json_atomic`, **sem tocar** a
  chave `defaults` existente, e MUST devolver o `preset_default_for` resultante. Valor inválido
  (kind não registrado ou preset fora de `REALISM_PRESETS` e diferente de `None`) MUST levantar
  `ValueError`.
- **R12.** `config.json` já existentes (sem a chave `prompter_presets`) MUST continuar válidos
  sem migração, e nenhuma chave, rota ou string de teste existente MUST ser renomeada.
</requirements>

## Subtasks

- [x] 1.1 Transcrever a tabela de rig presets do `_techspec.md` §5 para o dict `REALISM_PRESETS`
      em `studio/common/prompter.py`, com docstring explicando que é `[extensão]` (nenhuma aula
      ensina presets) e que a skill externa é fonte de design-time, nunca de runtime.
- [x] 1.2 Implementar `preset_block(preset_id)` — instrução curta em inglês derivada do preset.
- [x] 1.3 Adicionar o parâmetro `preset` a `from_brief` e `from_images`, injetando o bloco no
      prompt do papel só quando não for `None`, e acrescentando `"preset"` ao retorno.
- [x] 1.4 Implementar a mesclagem dos negativos do preset no campo `negative` da resposta.
- [x] 1.5 Adicionar o parâmetro `preset` a `fallback_template` (e ao helper interno `_sections`),
      preenchendo as linhas técnicas com o rig quando houver preset.
- [x] 1.6 Criar `PRESET_ACTIONS`, `PROMPTER_KINDS` e a chave de persistência `prompter_presets`
      em `studio/common/settings.py`.
- [x] 1.7 Implementar `preset_default_for` com a cadeia projeto → global → código, a semântica de
      `null` × ausente × id morto, e suporte a chave de ação arbitrária.
- [x] 1.8 Implementar `set_global_preset`, `set_project_preset` e `clear_project_preset`.
- [x] 1.9 Escrever os testes da seção `## Tests` em `tests/test_prompter.py` (acrescentando ao
      arquivo, sem editar os testes já existentes) e em `tests/test_settings.py`.
- [x] 1.10 Rodar `.venv/bin/ruff check studio tests scripts` e a suíte completa
      (`.venv/bin/pytest -q`) e confirmar que nada regrediu.

## Implementation Details

Modificar `studio/common/prompter.py` e `studio/common/settings.py`; acrescentar testes em
`tests/test_prompter.py` e `tests/test_settings.py`. Nenhum arquivo novo é necessário.

Pontos de encaixe já verificados no código:

- `prompter.ROLES` (`studio/common/prompter.py:117`) e `PROMPT_FORMAT` (:105) definem o texto do
  papel; `from_brief` (:193) monta `f"{role}\n\nBrief:\n{...}\n\n{OUTPUT_SPEC}"` e `from_images`
  (:200) monta o prompt com a lista de paths. O bloco de preset entra **depois do papel**,
  antes do restante — e só quando `preset` não é `None`, para não deslocar um único byte no
  caminho sem preset.
- `_parse` (:170) devolve `{prompt, negative, camera, notes_pt}`; `from_brief`/`from_images`
  acrescentam `source`/`seconds` (e `images`). A chave `"preset"` entra nesse mesmo ponto.
- `_sections` (:232) monta as cinco linhas técnicas do `fallback_template` (:244) — é onde o rig
  do preset substitui as strings fixas `RED Komodo 6K, 50mm lens, T2.8...`. Para `kind="motion"`
  o template não tem seções técnicas; manter esse caminho intocado.
- `split_sections` (:65) e `provenance` (:90) dependem de `PROMPT_SECTIONS` (:46) — não tocar em
  nenhum dos três; o preset nunca cria seção nova (critério 10 da seção 9 do `_techspec.md`).
- Em `settings.py`, o par a espelhar é `DEFAULTS` (:61) + `default_for` (:143): mesma ideia de
  cadeia e de "override inválido cai para o próximo nível". Reusar `_read` (:79), `_write_atomic`
  (:87) e `_project_config_path` (:93) — **não** duplicar leitura/escrita de config.
- `settings.py` pode importar o catálogo com `from . import prompter` (mesmo pacote
  `studio/common/`; `prompter` não importa `settings`, então não há ciclo).

## Relevant Files

- `studio/common/prompter.py` — recebe o catálogo, o `preset_block` e o parâmetro `preset`.
- `studio/common/settings.py` — recebe `PRESET_ACTIONS` e a resolução por ação.
- `studio/common/atomic.py` — `write_json_atomic`, usado pela persistência (via `_write_atomic`).
- `tests/test_prompter.py` — testes existentes com fake de `BIN`/`subprocess.run`; a
  retrocompatibilidade byte-idêntica é medida contra eles.
- `tests/test_settings.py` — padrão de teste da cadeia projeto → global → código.
- `docs/domains/mood/features/prompter-fdd.md` e
  `docs/domains/studio/features/base-prompt-provenance-fdd.md` — contratos publicados do prompter
  que esta task não pode quebrar.

## Dependent Files

- `studio/creditos/router.py` — task_02 exporá `REALISM_PRESETS` e `preset_default_for` por HTTP.
- `studio/etapas/{mood,base,storyboard}/router.py` e `studio/{mood,base,storyboard}/service.py` —
  task_03 passará `preset` adiante.
- `studio/mood/service.py` — já importa `STYLE_VARIANTS` do prompter; sensível a mudança de módulo.

### Related ADRs

- ADR-016 (modelo default por ação via settings) — o padrão de resolução que esta task estende
  para presets; a decisão é "config é dado, não regra espalhada".
- ADR-004 + gates de fidelidade do `CLAUDE.md` — presets são `[extensão]`; daí a invariante R1.
- ADR-003 (estado só em arquivo) — persistência em `config.json`, escrita atômica.

## Deliverables

- `REALISM_PRESETS` com os 5 presets e `preset_block()` em `studio/common/prompter.py`.
- Parâmetro `preset` em `from_brief`, `from_images` e `fallback_template`, com `"preset"` no
  retorno das duas primeiras.
- `PRESET_ACTIONS`, `PROMPTER_KINDS`, `preset_default_for`, `set_global_preset`,
  `set_project_preset` e `clear_project_preset` em `studio/common/settings.py`.
- Testes novos em `tests/test_prompter.py` e `tests/test_settings.py`, sem editar os existentes.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md` neste workflow: casos concretos inline. Fake do Claude CLI pelo padrão já usado
em `tests/test_prompter.py` (monkeypatch de `prompter.BIN` e `subprocess.run`).

- [x] **T1.1 — estrutura do catálogo.** `REALISM_PRESETS` tem exatamente as 5 chaves esperadas;
      cada preset tem `id`, `name`, `desc_pt`, `rig{camera,lens,format,focal,aperture}`, `light`,
      `grade`, `fidelity` e `negative` (lista não vazia); `id` do valor bate com a chave do dict;
      exatamente um preset tem `default: true` e é `documentary-street`.
- [x] **T1.2 — rig fiel à transcrição.** `REALISM_PRESETS["arri-natural-narrative"]["rig"]` tem
      `camera == "ARRI Alexa Mini LF"`, `lens == "Cooke S4"` e `format == "Large Format"`;
      `REALISM_PRESETS["documentary-street"]["rig"]["camera"] == "Blackmagic Pocket 6K Pro"`.
- [x] **T1.3 — `preset_block` conteúdo e limite.** `preset_block("red-commercial-precision")`
      contém "RED V-Raptor" e "Zeiss Supreme Prime", tem menos de 80 palavras, e não contém
      nenhum dos rótulos de `PROMPT_SECTIONS` como início de linha nova (não cria seção).
- [x] **T1.4 — `preset_block` id desconhecido.** `preset_block("nao-existe")` levanta `KeyError`.
- [x] **T1.5 — retrocompat byte-idêntica de `from_brief`.** Com CLI fakeado que captura o prompt
      recebido, `from_brief("mood", brief)` e `from_brief("mood", brief, preset=None)` produzem
      exatamente a MESMA string de prompt, e essa string não contém nenhum nome de câmera do
      catálogo. O retorno traz `"preset": None`.
- [x] **T1.6 — `from_brief` com preset.** `from_brief("mood", brief,
      preset="arri-natural-narrative")` envia prompt contendo "ARRI Alexa Mini LF", "Cooke S4" e
      "Large Format"; o retorno traz `"preset": "arri-natural-narrative"`.
- [x] **T1.7 — `from_images` com e sem preset.** Com 1 imagem temporária real e CLI fakeado:
      sem preset o prompt não contém termos do rig e o retorno traz `"preset": None`; com
      `preset="sony-venice-night"` o prompt contém "Sony Venice 2". Em ambos os casos o limite de
      4 imagens e o uso de `--allowedTools Read` permanecem (assertar nos args capturados).
- [x] **T1.8 — mesclagem de negativos.** Com CLI fakeado devolvendo `"negative": "text, plastic
      skin"` e `preset="documentary-street"`, o campo `negative` do retorno contém "text",
      contém "CGI look" (vindo do preset) e **não** repete "plastic skin". Sem preset, o campo
      sai exatamente `"text, plastic skin"`.
- [x] **T1.9 — `fallback_template` com preset.** `fallback_template("base", brief,
      preset="red-commercial-precision")["prompt"]` tem uma linha começando por `Camera:` que
      contém "RED V-Raptor"; a linha `Color grading:` contém termo da grade do preset.
- [x] **T1.10 — `fallback_template` sem preset.** `fallback_template("mood", brief)` devolve dict
      idêntico ao de `fallback_template("mood", brief, preset=None)` e o `prompt` contém a string
      atual "RED Komodo 6K, 50mm lens, T2.8" — prova de que o template do curso não mudou.
- [x] **T1.11 — `provenance` intacto com preset.** Um prompt no formato padrão gerado com preset
      passa por `split_sections` devolvendo as 5 seções, e `provenance` devolve 5 partes com os
      mesmos rótulos e valores de `from` de hoje.
- [x] **T1.12 — default de código é opt-in.** `settings.preset_default_for("mood")`,
      `("base")` e `("motion")`, sem nenhum override, devolvem
      `{"kind": <ação>, "preset": None, "source": "code"}`.
- [x] **T1.13 — resolução genérica por ação (contrato do handoff).** Registrando
      `settings.PRESET_ACTIONS["storyboard.script"] = "documentary-street"` no teste,
      `preset_default_for("storyboard.script")` devolve
      `{"preset": "documentary-street", "source": "code"}`. Chave não registrada
      (`preset_default_for("nao.existe")`) levanta `ValueError`.
- [x] **T1.14 — override de projeto vence o global.** Com `set_global_preset("base",
      "arri-natural-narrative")` e `set_project_preset(pid, "base", "sony-venice-night")`,
      `preset_default_for("base", pid)` devolve `sony-venice-night` com `source: "project"`, e
      `preset_default_for("base")` (sem pid) devolve `arri-natural-narrative` com
      `source: "global"`.
- [x] **T1.15 — `null` persistido encerra a cadeia.** Com global setado em
      `"documentary-street"` e projeto setado em `None`, `preset_default_for("base", pid)`
      devolve `{"preset": None, "source": "project"}` — e **não** cai para o global.
- [x] **T1.16 — `clear_project_preset` volta a cair para o global.** Após
      `clear_project_preset(pid, "base")` no cenário de T1.15, `preset_default_for("base", pid)`
      devolve `documentary-street` com `source: "global"`.
- [x] **T1.17 — override apontando para id morto é ignorado.** Escrevendo à mão
      `{"prompter_presets": {"base": "preset-que-nao-existe"}}` no `config.json` do projeto,
      `preset_default_for("base", pid)` cai para o próximo nível (global, ou código com
      `preset: None`), sem levantar.
- [x] **T1.18 — validação dos setters.** `set_global_preset("nao-existe", "documentary-street")`
      e `set_global_preset("base", "preset-que-nao-existe")` levantam `ValueError`;
      `set_global_preset("base", None)` é aceito e persiste `null`.
- [x] **T1.19 — persistência não toca `defaults`.** Com um `config.json` que já tem
      `{"defaults": {"base.image": {...}}}`, chamar `set_global_preset("base",
      "documentary-street")` mantém a chave `defaults` intacta e acrescenta `prompter_presets`;
      `settings.default_for("base.image")` continua devolvendo o mesmo resultado de antes.
- [x] **T1.20 — config antigo sem a chave nova.** Um `config.json` sem `prompter_presets` não
      quebra `preset_default_for` (devolve o default de código) nem `global_config()`.

## Success Criteria

- Every assigned test case implemented and passing.
- `tests/test_prompter.py` e `tests/test_settings.py` **não têm nenhuma linha pré-existente
  alterada** — só linhas acrescentadas (verificável no diff).
- `.venv/bin/ruff check studio tests scripts` limpo e `.venv/bin/pytest -q` verde na suíte
  completa (nenhum teste de outra etapa regride).
- Critérios 1, 2, 3, 4, 5 e 10 da seção 9 do `_techspec.md` fechados.
- Nenhuma edição em `studio/app.py`, `studio/steps.py` ou `studio/web/*`.
