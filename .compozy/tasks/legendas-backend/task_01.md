---
status: completed
title: Constantes compartilhadas e transcrição pura
type: backend
complexity: medium
---

# Task 1: Constantes compartilhadas e transcrição pura

## Overview

Cria o pacote `studio/edit/captions/` com as constantes que o backend e o `view.js` da frente C
precisam manter idênticas (`WPS`, `CAPTION_MODES`, `HI_COLORS`, `CHUNK_OPTS`, a regra do centro) e
o módulo de transcrição portado do repo irmão ContentFlow: distribuição proporcional
determinística, alinhamento do nosso texto ao tempo ouvido, provider fake e o provider real
`whisper-1` com import lazy. É a camada pura sobre a qual as tasks 2 a 4 são construídas — sem
ffmpeg, sem HTTP, sem rede.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST criar `studio/edit/captions/__init__.py` exportando exatamente os valores do contrato
  congelado: `WPS = 2.4`, `CAPTION_MODES = ("karaoke", "linha", "bloco")`,
  `HI_COLORS = ["#C8F751", "#57E2F0", "#F2B544", "#A78BFA"]`, `CHUNK_OPTS = [0, 6, 4, 2]`,
  `DEFAULT_HI = HI_COLORS[0]`. Estes valores são espelhados pela frente C em `view.js`:
  divergir quebra um critério cross-feature. Este é o ÚNICO lugar do WPS no backend.
- MUST implementar `word_in_window(word, a, b) -> bool` com a **regra do centro** do contrato:
  a palavra pertence à janela se `a <= (start_s + end_s) / 2 < b` (`a` incluso, `b` excluso).
  Deve aceitar tanto um `dict` (`{"w", "start_s", "end_s"}`) quanto um `WordTiming`.
- MUST implementar `effective_mode(mode, default="bloco") -> str`: valor fora de `CAPTION_MODES`
  (incluindo `None` e não-string) resolve para `default`.
- MUST implementar em `studio/edit/captions/transcribe.py`, conforme §5.7 do TechSpec:
  `WordTiming` (dataclass **frozen** com `text, start, end`), `ProviderError(RuntimeError)`,
  `proportional`, `align`, `fake_transcript`, `TranscribeProvider` (Protocol), `FakeTranscribe`,
  `OpenAITranscribe`, `get_transcribe()`.
- MUST portar `proportional` com peso `len(w) + 1` por palavra (NÃO peso uniforme) e tempos
  `round(..., 3)`; texto vazio ou `duration_s <= 0` devolve `[]`.
- MUST portar `align` com a política do ContentFlow: contagem igual → um-para-um com os tempos
  ouvidos; contagem diferente → `proportional` do NOSSO texto dentro de
  `[ouvidas[0].start, ouvidas[-1].end]`; `ouvidas` vazias → `proportional` sobre `duration_s`.
  O texto exibido é SEMPRE o nosso — a transcrição só fornece o tempo.
- MUST implementar a **política assimétrica de falha**: `OpenAITranscribe.words()` (temos o texto)
  captura qualquer exceção do provedor, registra `WARNING` e devolve `proportional(text, duration_s)`;
  `OpenAITranscribe.transcribe_text()` (não temos o texto) levanta `ProviderError`. Nunca o inverso.
- MUST fazer o import do SDK (`from openai import OpenAI`) **dentro dos métodos**, nunca no topo do
  módulo, e chamar `client.audio.transcriptions.create(model="whisper-1", file=fh,
  response_format="verbose_json", timestamp_granularities=["word"], language="pt")` com
  `OpenAI(api_key=..., timeout=120, max_retries=1)`.
- MUST ler a chave com `os.environ.get("OPENAI_API_KEY")` **em tempo de chamada** dentro de
  `get_transcribe()`, nunca em constante de módulo — `monkeypatch.setenv/delenv` precisa funcionar
  sem reimportar o módulo. Sem chave, devolve `FakeTranscribe()`.
- MUST garantir que a chave nunca apareça em log, exceção ou repr. Mensagens de erro do SDK são
  truncadas em 300 caracteres antes de irem para o log.
- MUST acrescentar `openai>=1.40` a `requirements.txt` (única lista de deps do projeto). NÃO tocar
  `pyproject.toml` nem `requirements-dev.txt`.
- MUST usar o logger `studio.edit.captions` (via `logging.getLogger`) — sem `print`.
- MUST NOT importar nada de `videoengine` nem do repo irmão: o porte é por cópia adaptada.
- MUST NOT criar dependência de `studio/edit/captions/__init__.py` para `transcribe.py` que force
  o import de `openai` ao importar o pacote.
</requirements>

## Subtasks

- [x] 1.1 Criar o pacote `studio/edit/captions/` com `__init__.py` contendo as constantes do
      contrato congelado, `word_in_window` e `effective_mode`, com docstring `[extensão]`
      explicando que os valores são espelhados no `view.js` da frente C.
- [x] 1.2 Criar `captions/transcribe.py` com `WordTiming`, `ProviderError` e o Protocol
      `TranscribeProvider` (assinaturas SEM `BudgetPort`/`item_id` — o studio não tem livro-caixa
      nesta entrega, ver §5.7 do TechSpec).
- [x] 1.3 Portar `proportional`, `align` e `fake_transcript` do ContentFlow, preservando os
      números e a semântica, com docstrings em português explicando o porquê de cada regra
      (peso `len+1`; "nosso texto, tempo ouvido"; 2,4 wps).
- [x] 1.4 Implementar `FakeTranscribe` (`words` = `proportional`; `transcribe_text` =
      `fake_transcript` + `proportional`).
- [x] 1.5 Implementar `OpenAITranscribe` com import lazy, `model`/`language`/`timeout_s` de
      classe, e a política assimétrica de falha.
- [x] 1.6 Implementar `get_transcribe()` lendo `OPENAI_API_KEY` em runtime.
- [x] 1.7 Acrescentar `openai>=1.40` a `requirements.txt`.
- [x] 1.8 Criar `tests/test_edit_captions.py` com os casos listados em `## Tests`, incluindo o
      SDK falso injetado em `sys.modules["openai"]`.

## Implementation Details

Arquivos a criar: `studio/edit/captions/__init__.py`, `studio/edit/captions/transcribe.py`,
`tests/test_edit_captions.py`. Arquivo a modificar: `requirements.txt` (uma linha).

Código de referência para PORTAR (repo irmão, **read-only**, não importar):
`/home/arthu/code/making-money-with-videos-social-media/videoengine/transcribe.py` e
`/home/arthu/code/making-money-with-videos-social-media/tests/test_captions.py`.
Adaptações obrigatórias em relação à origem: remover `ContextAware`/`RenderContext`/`BudgetPort`
(o studio lê a chave do ambiente e não registra custo nesta entrega — ver §10 do TechSpec) e
remover `budget.check`/`budget.record`.

O SDK falso dos testes deve expor `OpenAI(api_key=..., timeout=..., max_retries=...)` cujo
`audio.transcriptions.create(...)` devolve um objeto com `.text` e `.words` (cada palavra com
`.word`, `.start`, `.end`) — e uma variante que levanta exceção, para exercitar a política
assimétrica.

### Relevant Files

- `studio/edit/burnin.py` — helpers `_font(size, bold)` e `_hex(color, default)` que as tasks 3 e 4
  vão reutilizar; conhecer a assinatura evita duplicar código depois.
- `studio/edit/editor.py` — `_clampi`, `_num`, `safe_rel` e o vocabulário de normalização do
  domínio; as constantes novas devem conversar com `normalize_style`.
- `tests/conftest.py` — fixtures `studio_env`, `client`, `ffmpeg_or_skip` e helpers `make_audio` /
  `make_video`; `studio_env` limpa `sys.modules["studio*"]`, o que importa para o teste de
  "`openai` não é importado".
- `requirements.txt` — única lista de dependências do projeto (`pyproject.toml` não lista deps).

### Dependent Files

- `studio/edit/captions/layout.py`, `audio.py`, `service.py` (tasks 3 e 4) — consomem `WordTiming`,
  `word_in_window`, `effective_mode` e `get_transcribe`.
- `studio/edit/editor.py` (task 2) — chamará `effective_mode` na normalização do item `caption`.

### Related ADRs

- ADR-008 (testes sem rede) — cumprida por `FakeTranscribe` + import lazy + SDK falso.
- ADR-002 (ponte Higgsfield só por CLI) — restringe apenas a Higgsfield; a OpenAI é serviço novo e
  ganha a ADR-024 na task 5.
- ADR-016 (livro-caixa de créditos) — o custo do whisper **não** é registrado nesta entrega; a
  lacuna é intencional e documentada.

## Deliverables

- Pacote `studio/edit/captions/` importável com as constantes do contrato congelado.
- `transcribe.py` completo com os dois providers e a política assimétrica.
- `openai>=1.40` em `requirements.txt`.
- `tests/test_edit_captions.py` criado com os casos abaixo.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Este workflow **não tem `_tests.md`**; os casos abaixo são o contrato desta task, derivados dos
critérios 7, 8, 12 e 16a–d/16h da §9 do `_techspec.md`. Todos em `tests/test_edit_captions.py`.

- [x] `proportional("de desenvolvimento", 3.0)` devolve 2 palavras, determinístico, e a segunda
      (mais longa) tem span maior que a primeira; a soma dos spans cobre `3.0`; primeiro `start`
      é `0.0`. `proportional("", 5)` e `proportional("oi", 0)` devolvem `[]`.
- [x] `align("nosso texto aqui", ouvidas)` com 3 `ouvidas` devolve exatamente
      `["nosso", "texto", "aqui"]` com os tempos das ouvidas (contagem igual → um-para-um).
- [x] `align` com contagem DIFERENTE (ex.: 2 ouvidas em `[2.0, 4.0]` para 5 palavras nossas)
      devolve as 5 palavras nossas, com `start` da primeira `>= 2.0` e `end` da última `<= 4.0`.
- [x] `align("um dois", [], 4.0)` cai no proporcional sobre `4.0` (última palavra termina em 4.0).
- [x] `align("", ouvidas, 3.0)` devolve `[]`.
- [x] `fake_transcript("qualquer.wav", 5.0)` tem 12 palavras (`round(5.0 * 2.4)`), começa em
      `palavra1`, e o resultado NÃO muda com outro `name`.
- [x] `word_in_window`: palavra com centro exatamente em `a` pertence; centro exatamente em `b`
      NÃO pertence; aceita `dict` e `WordTiming` com o mesmo resultado.
- [x] `effective_mode("karaoke")=="karaoke"`; `effective_mode("x")=="bloco"`;
      `effective_mode(None)=="bloco"`; `effective_mode("x", "linha")=="linha"`.
- [x] `get_transcribe()` devolve `FakeTranscribe` com `monkeypatch.delenv("OPENAI_API_KEY", raising=False)`
      e `OpenAITranscribe` com `monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")` — **sem reimportar**
      o módulo entre as duas asserções (prova que a chave é lida em runtime).
- [x] Importar `studio.edit.captions` e `studio.edit.captions.transcribe` sem chave NÃO importa o
      SDK: `"openai" not in sys.modules` depois do import.
- [x] `OpenAITranscribe.transcribe_text` com SDK falso bem-sucedido mapeia `result.words` para
      `WordTiming` (texto, start, end corretos) e devolve `result.text` como primeiro elemento.
- [x] `OpenAITranscribe.transcribe_text` com SDK falso que levanta → `ProviderError`.
- [x] `OpenAITranscribe.words` com SDK falso que levanta → devolve `proportional(text, duration)`
      (NÃO levanta), e a lista tem exatamente as palavras de `text.split()`.
- [x] `OpenAITranscribe.words` com SDK falso bem-sucedido e contagem igual devolve o NOSSO texto
      com os tempos ouvidos (nunca o texto do whisper).
- [x] `FakeTranscribe.transcribe_text` devolve texto de `fake_transcript` e palavras proporcionais
      com a mesma contagem.

## Success Criteria

- Every assigned test case implemented and passing
- `make verify` VERDE (ruff + pytest); os 890 testes anteriores continuam passando
- `WPS`, `CAPTION_MODES`, `HI_COLORS`, `CHUNK_OPTS` batem byte a byte com o contrato congelado
  citado no `_prd.md`
- Nenhum teste faz rede; `openai` nunca é importado de verdade pela suíte
- `grep -rn "videoengine" studio/` não retorna nada
