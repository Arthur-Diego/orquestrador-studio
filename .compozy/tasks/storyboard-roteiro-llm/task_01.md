---
status: completed
title: Papel `script` e `prompter.script()` no prompter
type: backend
complexity: high
---

# Task 1: Papel `script` e `prompter.script()` no prompter

## Overview

Entrega a fundação da feature: um papel novo `script` em `prompter.ROLES` e a função pública
`prompter.script(...)`, que pede ao Claude CLI um roteiro completo de N cenas (texto pt-BR +
prompt de imagem em inglês no formato "briefing de diretor de fotografia") aplicando o rig do
preset de realismo escolhido. É o contrato interno que a task_02 chama de dentro do job da
etapa 4 — nenhuma rota HTTP nasce aqui.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **R1 (invariante suprema desta task).** Tudo é ADITIVO. `ROLES["mood"]`, `ROLES["base"]`,
  `ROLES["motion"]`, `PROMPT_FORMAT`, `EXAMPLE_PROMPT`, `OUTPUT_SPEC`, `_parse`, `split_sections`,
  `provenance`, `from_brief`, `from_images`, `fallback_template`, `_role_text`, `_with_preset`,
  `preset_block`, `valid_preset` e `REALISM_PRESETS` MUST permanecer byte-idênticos. A feature
  `base-prompt-provenance` depende do formato de 5 linhas de `_parse` — não encoste nele.
- **R2.** MUST existir a chave nova `ROLES["script"]`, em inglês, instruindo: papel de diretor de
  cinema publicitário e roteirista; escrever um roteiro de N cenas a partir das imagens da marca
  (imagem base primeiro, depois frames de mood); seguir o arco do curso (começo → descoberta →
  ação → desfecho) recebido por cena; e devolver, POR CENA, um `text` curto em português do
  Brasil e UM `image_prompt` em inglês escrito como briefing de diretor de fotografia na ordem
  sujeito → ação → ambiente → câmera/lente/abertura do rig dado → luz com uma fonte dominante →
  texturas e imperfeições reais → color grade → composição + aspect ratio → bloco de fidelidade →
  negativos. O texto do papel MUST mandar usar EXATAMENTE o rig fornecido em TODAS as cenas.
- **R3 (o que sustenta o critério `[cross-feature]` da wave).** Quando `preset` é um id de
  `REALISM_PRESETS`, o prompt enviado ao CLI MUST conter, literalmente, `rig["camera"]`,
  `rig["lens"]` e `rig["format"]` desse preset, além de `light`, `grade`, `fidelity` e a lista
  `negative`. Reuse `preset_block(preset_id)` como base e complemente com o que o roteiro exige
  (o `preset_block` da provedora fala das cinco linhas técnicas do prompt único; o roteiro tem
  formato próprio) — mas **sem alterar `preset_block`**. Com `preset=None`, nenhum bloco de rig
  entra no prompt e o pedido segue sem rig fixo.
- **R4.** MUST existir um output spec PRÓPRIO (constante nova, ex.: `SCRIPT_OUTPUT_SPEC`) pedindo
  APENAS um objeto JSON dentro de uma fence ```json com a forma
  `{"scenes": [{"n", "arc", "text", "image_prompt", "negative"}], "notes_pt"}`, e um parser
  PRÓPRIO (ex.: `_parse_script`). O parser MUST ser usado só pelo roteiro.
- **R5.** MUST existir `SCRIPT_TIMEOUT_S = 300` (constante nova; `TIMEOUT_S` continua 180) e a
  chamada ao CLI MUST usar esse timeout via o parâmetro `timeout` de `_run`.
- **R6 (nunca inventar).** O parser MUST levantar erro claro quando: a resposta não tem JSON
  parseável; `scenes` não é lista; vierem MENOS cenas que `count`; alguma cena não tem `text` ou
  `image_prompt` não vazios. Vindo MAIS cenas que `count`, MUST cortar em `count`. **É proibido
  completar o roteiro com conteúdo gerado deterministicamente** — não existe `fallback_template`
  para roteiro.
- **R7.** `script(...)` MUST respeitar `MAX_IMAGES` (corta a lista em 4), MUST validar que cada
  caminho existe (`FileNotFoundError`) e MUST liberar a tool `Read` do CLI passando as imagens a
  `_run` (mesmo caminho de `from_images`). Lista vazia de imagens é aceitável apenas se a
  task_02 assim decidir; a assinatura MUST aceitar `list[Path]`.
- **R8.** Os campos `n` e `arc` devolvidos MUST ser normalizados pelo parser: `n` renumerado
  1..count na ordem recebida e `arc` preenchido a partir da lista `arcs` recebida como parâmetro
  (o servidor manda o arco correto de cada cena; o LLM não decide isso).
- **R9.** O retorno MUST ser um dict com, no mínimo, `scenes` (lista normalizada), `notes_pt`,
  `source` (sempre `"claude"`), `seconds` (float do `_run`), `preset` e `model_target`.
- **R10.** `model_target` MUST ajustar o prompt: para `nano_banana_2` (Nano Banana Pro, único
  alvo da v1 pelo gate W3 P3), prompt técnico longo. A função MUST aceitar o parâmetro sem
  validar o catálogo (a validação de id é da task_02, contra `SCRIPT_MODELS`).
- **R11.** Testes MUST usar o fake do Claude CLI já estabelecido em `tests/test_prompter.py`
  (monkeypatch de `prompter.BIN` e de `subprocess.run`). Sem rede, sem processo real (ADR-008).
</requirements>

## Subtasks

- [x] 1.1 Ler `_techspec.md` inteiro, com atenção à **seção 0 (amendas)**, à seção 5.5 (contrato
      de `prompter.script`), à seção 5.3 (schema do `script.json`, que fixa os campos por cena) e
      à seção 6 (por que não há fallback determinístico).
- [x] 1.2 Ler `studio/common/prompter.py` inteiro antes de editar, mapeando o que é intocável
      (R1) e onde o código novo entra sem se misturar ao caminho do prompt único.
- [x] 1.3 Acrescentar `ROLES["script"]` (R2), sem tocar nas outras chaves.
- [x] 1.4 Acrescentar `SCRIPT_OUTPUT_SPEC` (R4) e `SCRIPT_TIMEOUT_S` (R5).
- [x] 1.5 Escrever o bloco de rig do roteiro a partir de `preset_block` + rig/luz/grade/
      fidelidade/negativos do catálogo (R3), sem alterar a função da provedora.
- [x] 1.6 Escrever `_parse_script` com todas as validações e normalizações de R6 e R8.
- [x] 1.7 Escrever `script(...)` montando papel + rig + brief + arcos por cena + caminhos das
      imagens + output spec, chamando `_run` com as imagens e `SCRIPT_TIMEOUT_S` (R7, R9, R10).
- [x] 1.8 Escrever os testes da seção `## Tests` em `tests/test_prompter.py`, com o fake do CLI.
- [x] 1.9 Rodar `make verify` e conferir que os 1092 testes da baseline continuam passando.

## Implementation Details

Arquivo a modificar: `studio/common/prompter.py` (único arquivo de produção desta task).
Arquivo de testes: `tests/test_prompter.py` (acrescentar casos; não alterar os existentes).

Padrões a seguir, todos já no arquivo:

- `_run(prompt, images, timeout)` é o único ponto de contato com o CLI e já devolve
  `(texto, segundos)`; ele levanta `RuntimeError` quando `BIN` é `None`.
- `from_images` é o modelo de como montar um prompt com imagens: papel, depois a instrução de ler
  os arquivos com a tool `Read` listando os caminhos, depois o brief, depois o output spec.
- `_brief_text(brief)` já formata o brief em linhas `- Label: valor` e ignora chaves vazias —
  reuse em vez de reimplementar.
- `_parse` mostra como extrair JSON de uma fence ```json com tolerância a texto ao redor; o
  `_parse_script` segue a mesma tolerância, mas com validação própria (R6).
- `REALISM_PRESETS[id]` tem exatamente `{id, name, desc_pt, rig{camera,lens,format,focal,aperture},
  light, grade, fidelity, negative[], default?}`.

Não crie módulo novo, não mova código existente, não renomeie nada.

### Relevant Files

- `studio/common/prompter.py` — onde tudo desta task acontece: `ROLES` (~:117), `OUTPUT_SPEC`,
  `REALISM_PRESETS` (~:181), `preset_block` (~:215), `_run` (~:270), `_brief_text`, `from_images`
  (~:324), `MAX_IMAGES`/`TIMEOUT_S` (~:22).
- `tests/test_prompter.py` — padrão do fake do CLI (monkeypatch de `BIN` + `subprocess.run`), a
  ser reusado nos casos novos.
- `_techspec.md` §0 (amendas A1/A3/A6/A9), §5.3, §5.5, §6 — contrato normativo.

### Dependent Files

- `studio/storyboard/service.py` — a task_02 chama `prompter.script(...)` de dentro do job; a
  assinatura definida aqui é o contrato dela.
- `tests/test_prompter_api.py`, `tests/test_mood_service.py`, `tests/test_base_service.py`,
  `tests/test_storyboard_service.py` — travam o comportamento atual do prompter; devem continuar
  passando sem edição (prova de R1).

### Related ADRs

- ADR-004 (fidelidade ao curso) — o papel `script` é `[extensão]`; comentar isso no código.
- ADR-008 (testes sem rede/navegador) — o CLI é sempre fake nos testes.
- ADR-025 (roteiro por LLM como extensão opt-in) — aprovada no gate W3, formalizada no
  fechamento da frente; citar como referência no comentário do papel novo.

## Deliverables

- `ROLES["script"]`, `SCRIPT_OUTPUT_SPEC`, `SCRIPT_TIMEOUT_S`, o bloco de rig do roteiro,
  `_parse_script` e `script(...)` em `studio/common/prompter.py`, todos marcados `[extensão]`
  em comentário.
- Casos novos em `tests/test_prompter.py` cobrindo os cenários abaixo.
- `make verify` verde, com os testes existentes do prompter intactos.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md` neste workflow. Casos concretos, todos com o Claude CLI fake:

- [x] **T1.1 — roteiro feliz com preset.** Fake devolve fence ```json com 5 cenas válidas;
      chamar `script(images=[base], brief={...}, preset="documentary-street", count=5,
      arcs=["comeco","descoberta","acao","acao","desfecho"], model_target="nano_banana_2")`.
      Esperado: retorno com 5 cenas, `source == "claude"`, `seconds` numérico,
      `preset == "documentary-street"`, e `scenes[i]["n"] == i+1`.
- [x] **T1.2 — rig no prompt enviado ao CLI (`[cross-feature]`, metade de baixo).** Capturar o
      `prompt` que o fake recebeu; esperado: contém literalmente
      `REALISM_PRESETS["documentary-street"]["rig"]["camera"]` (`Blackmagic Pocket 6K Pro`),
      `["lens"]` (`Cooke S4`) e `["format"]` (`Super 35`), mais `light` e `grade` do preset.
- [x] **T1.3 — sem preset.** Com `preset=None`, o prompt enviado NÃO contém
      `"Blackmagic Pocket 6K Pro"` nem a string `REALISM PRESET`; a chamada mesmo assim devolve
      as cenas do fake.
- [x] **T1.4 — arcos vêm do servidor.** Fake devolve cenas com `arc` errado (ex.: todas
      `"acao"`); esperado: o retorno traz exatamente os `arcs` passados como parâmetro, na ordem.
- [x] **T1.5 — cenas de menos = erro.** `count=5` e fake devolve 3 cenas; esperado: exceção com
      mensagem citando o número esperado e o recebido; NENHUM preenchimento automático.
- [x] **T1.6 — JSON inválido = erro.** Fake devolve texto livre sem fence; esperado: exceção
      clara (não `KeyError`/`IndexError` cru).
- [x] **T1.7 — cena sem `image_prompt` = erro.** Fake devolve 5 cenas, uma com `image_prompt`
      vazio; esperado: exceção citando a cena.
- [x] **T1.8 — cenas a mais são cortadas.** `count=3` e fake devolve 5 cenas; esperado: 3 cenas,
      `n` 1..3.
- [x] **T1.9 — teto de imagens.** Passar 6 caminhos existentes; esperado: no máximo 4 caminhos
      citados no prompt e passados a `_run` (`MAX_IMAGES`).
- [x] **T1.10 — imagem inexistente.** Um caminho que não existe → `FileNotFoundError`.
- [x] **T1.11 — timeout próprio.** Capturar o `timeout` recebido por `subprocess.run`; esperado:
      `300` (`SCRIPT_TIMEOUT_S`), não `180`.
- [x] **T1.12 — sem CLI.** Com `prompter.BIN = None`, `script(...)` levanta `RuntimeError`
      (a tradução para 409 é da task_02).
- [x] **T1.13 — regressão de R1.** `ROLES` continua tendo `mood`/`base`/`motion` com o texto de
      antes, e `from_brief`/`from_images` sem preset continuam produzindo o prompt de sempre
      (os testes existentes do arquivo já cobrem isso e devem passar sem edição).

## Success Criteria

- Every assigned test case implemented and passing.
- `make verify` verde (ruff + pytest), sem alterar nenhum teste pré-existente.
- `git diff` desta task toca exatamente dois arquivos: `studio/common/prompter.py` e
  `tests/test_prompter.py`.
- Uma busca por `preset_block(`, `_parse(`, `PROMPT_FORMAT`, `split_sections` e `provenance` no
  diff mostra que nenhuma dessas definições foi modificada.
