---
status: completed
title: Layout de janelas, extração de áudio, serviço e rotas de `captions`
type: backend
complexity: high
---

# Task 3: Layout de janelas, extração de áudio, serviço e rotas de `captions`

## Overview

Entrega a fatia vertical do contrato HTTP: fatiar palavras cronometradas em janelas de uma linha
(por contagem `chunk`, por largura real medida com a fonte do Pillow e por pausa), montar os itens
no shape de `editor.tracks[t_cap].items[]`, extrair o wav 16 kHz mono de um arquivo do projeto e
expor as três rotas novas (`generate`, `narration/upload`, `narration`) com a tradução exata de
erros para `422/404/409/502`.

É a task que a frente C consome. O contrato HTTP é **congelado**: o shape da resposta, os status e
o formato do `detail` do 422 não são negociáveis.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>

### `captions/layout.py` (parte de janelas; o burn-in é da task 4)

- MUST implementar `LayoutOpts` (dataclass), `layout_windows(words, opts) -> list[list[WordTiming]]`
  e `build_items(words, opts) -> list[dict]`, mais as constantes `KARAOKE_MIN_WORDS = 2`,
  `GAP_S = 1.0`, `MAX_WIDTH_RATIO = 0.84`.
- MUST fechar uma janela por três motivos, portados de `layout_karaoke` do ContentFlow:
  (a) atingiu `chunk` palavras (quando `chunk > 0`); (b) a largura REAL da linha, medida com
  `burnin._font(size, bold)` e `ImageDraw.textlength`, passaria de `MAX_WIDTH_RATIO * W` **e** a
  janela já tem pelo menos `KARAOKE_MIN_WORDS` palavras (janela de 1 palavra pisca);
  (c) o intervalo entre o fim da palavra anterior e o início da próxima passa de `GAP_S`.
- MUST garantir os invariantes da §6 do TechSpec: **toda palavra pertence a exatamente uma janela**;
  as janelas de um mesmo `generate` são ordenadas, não se sobrepõem e cobrem
  `[start, start + total_s)`; `items[i].end == items[i+1].start`; `items[0].start == start`;
  `items[-1].end == start + total_s`. Nenhuma janela mistura palavras de fontes/itens diferentes.
- MUST montar cada item de `build_items` com **exatamente** estas chaves:
  `id` (`"cap_" + 6 hex`), `start`, `end`, `text`, `mode`, `hi`, `chunk`, `words`, `style`,
  `transform`, `anim` — no shape do exemplo da §5.2 do `_techspec.md`.
- MUST usar `transform.y` conforme `position`: `top=0.12`, `middle=0.5`, `bottom=0.82`; e
  `transform` completo `{x: 0.5, y: <pos>, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1}`;
  `anim` = `{"in": "fade", "out": "fade"}`.
- MUST emitir `words[].start_s/end_s` em segundos **ABSOLUTOS** da timeline (com `start` somado),
  `round(..., 3)`; `item.start == words[0].start_s` e `item.end == words[-1].end_s`.
- MUST usar `word_in_window` (task 1) como a regra de pertencimento — não reimplementar o centro.
- MUST degradar sem Pillow: se a medição de largura falhar, a janela fecha só por `chunk`/`GAP_S`
  (nunca levantar).

### `captions/audio.py`

- MUST implementar `WHISPER_MAX_BYTES = 25 * 1024 * 1024`, `duration_of(path) -> float`,
  `extract_wav(src, out, duration=None) -> Path` e o context manager `extracted(src, duration=None)`.
- MUST usar `studio.common.ffmpeg` (`ff.probe`, `ff.run`) — nunca `subprocess` direto.
- MUST fazer `duration_of` levantar `ValueError` quando `probe` devolver `has_audio` falso
  (mensagem começando por `"file: "`, ver formato do `detail` abaixo).
- MUST extrair com `-vn -ac 1 -ar 16000` e, quando `duration` for informado, `-t <duration>`
  (RECORTAR o áudio, nunca escalar os tempos).
- MUST usar `tempfile.TemporaryDirectory` em `extracted` e garantir a remoção do wav mesmo em erro.

### `captions/service.py`

- MUST implementar `generate(root, req) -> dict`, `import_narration(root, files) -> dict`,
  `list_narration(root) -> list[dict]` e as constantes `NARRATION_DIR = "edit/narration"`,
  `MAX_SCRIPT_CHARS = 20_000`.
- MUST implementar os três fluxos da §4 do `_techspec.md` (script, audio sem `text`, audio com
  `text`) exatamente como especificados, inclusive a ordem das validações.
- MUST responder `{source, word_count, total_s, items}` e acrescentar `warning` **apenas** no
  fallback do fluxo `audio` com `text` (campo opcional; ausente quando não há aviso).
- MUST usar `source = "whisper"` só quando o alinhamento usou tempos reais do provedor real;
  `"estimate"` no fake e no fallback proporcional.
- MUST aplicar a política assimétrica: `audio` **sem** `text` cujo provedor falha → `ProviderError`
  → `502`, nunca `estimate` silencioso. `audio` **com** `text` → `200` + `estimate` + `warning`.
- MUST gravar a narração em `edit/narration/<sha1[:12]><ext>` com dedupe por conteúdo (padrão de
  `common/ingest.ingest_bytes`) e um sidecar `edit/narration/index.json` com
  `[{file, name, duration, imported}]`; arquivo sem trilha de áudio no probe é REMOVIDO e ignorado
  (não conta em `added`). `list_narration` devolve `[]` quando a pasta não existe.
- MUST usar `editor.safe_rel(root, file, "captions.file")` para barrar path traversal.
- MUST registrar os logs da §7 do `_techspec.md` no logger `studio.edit.captions`
  (`captions.generate` INFO com `elapsed_ms`, `captions.fallback` WARNING, `captions.provider`
  ERROR truncado em 300 chars, `captions.narration` INFO). NUNCA logar a chave, o roteiro inteiro
  nem o áudio — `text` aparece só como `word_count`.

### `studio/etapas/edit/router.py`

- MUST acrescentar `CaptionStyleReq` (com `model_config = ConfigDict(extra="allow")`) e
  `CaptionsGenerateReq` exatamente como a §5.1 do `_techspec.md` (incluindo os `Literal`, o
  `Field(6, ge=0, le=20)` de `chunk` e o `pattern=r"^#[0-9A-Fa-f]{6}$"` de `hi`).
- MUST acrescentar as três rotas **aditivas** sob `/api/projects/{pid}/edit`:
  `POST /captions/generate`, `POST /captions/narration/upload` (multipart `files[]`),
  `GET /captions/narration`. Nenhuma rota existente pode mudar.
- MUST traduzir: `ValueError` → `422`, `FileNotFoundError` → `404`, `ProviderError` → `502`,
  ffmpeg indisponível com `source="audio"` → `409` com a constante `NO_FFMPEG` já existente,
  upload acima de `MAX_MEDIA_BYTES` (200 MB) → `413`.
- MUST fazer o `detail` de todo `422` do serviço ser uma **string iniciada pelo nome do campo**,
  como manda o contrato congelado: `"text: obrigatório em script"`, `"file: …"`, `"hi: …"`,
  `"mode: …"`. (Os 422 do próprio Pydantic mantêm o formato padrão do FastAPI.)
- MUST validar a existência do projeto com `refs.project_dir(pid)` como as demais rotas fazem.

### Transversal

- MUST NOT persistir o resultado do `generate` — o servidor só devolve os itens.
- MUST NOT alterar o backbone (`clips/blacks/music/sfx/fade_out/loudnorm`) nem `edit/timeline.json`.
- MUST NOT fazer rede em teste algum; sem `OPENAI_API_KEY` o caminho é sempre o `FakeTranscribe`.
- Os testes novos em `tests/test_edit_api.py` MUST usar o prefixo `test_captions_` no nome.
</requirements>

## Subtasks

- [x] 3.1 Implementar `captions/layout.py` com `LayoutOpts`, `layout_windows` e `build_items`
      (a parte de burn-in fica para a task 4, no mesmo arquivo).
- [x] 3.2 Implementar `captions/audio.py` (`duration_of`, `extract_wav`, `extracted`,
      `WHISPER_MAX_BYTES`).
- [x] 3.3 Implementar `captions/service.py::generate` cobrindo os três fluxos e a matriz de erros
      da §6 do `_techspec.md`.
- [x] 3.4 Implementar `import_narration` / `list_narration` com dedupe, probe e sidecar.
- [x] 3.5 Acrescentar os logs da §7 (incluindo `elapsed_ms` da chamada ao provedor).
- [x] 3.6 Acrescentar os modelos Pydantic e as três rotas em `studio/etapas/edit/router.py`.
- [x] 3.7 Escrever os testes de layout/serviço em `tests/test_edit_captions.py`.
- [x] 3.8 Escrever os testes de API em `tests/test_edit_api.py` (prefixo `test_captions_`).

## Implementation Details

Arquivos a criar: `studio/edit/captions/layout.py`, `studio/edit/captions/audio.py`,
`studio/edit/captions/service.py`. Arquivos a modificar: `studio/etapas/edit/router.py`
(aditivo), `tests/test_edit_captions.py` (acrescentar), `tests/test_edit_api.py` (funções novas).

Padrões do repositório a seguir (ler antes de escrever):

- Rotas: `studio/etapas/edit/router.py` já traz `_translate(e)` (404 para `FileNotFoundError`,
  422 no resto), a constante `NO_FFMPEG` (linha 15), `MAX_MEDIA_BYTES` (200 MB, linha 14) e o
  padrão de upload multipart de `upload_sfx`/`upload_media` (`await f.read()`, checagem de
  tamanho, `payload.append((f.filename or ..., data))`). Reusar tudo isso.
- Dedupe e probe: `studio/common/ingest.py::ingest_bytes` grava em `<step>/candidates/<sha12><ext>`
  com `hashlib.sha1(data).hexdigest()[:12]` e `MEDIA_EXT`. Aqui o destino é `edit/narration/`,
  então o serviço replica o dedupe/probe em vez de chamar `import_upload` — as extensões aceitas
  são `MEDIA_EXT["audio"] ∪ MEDIA_EXT["video"]`.
- ffmpeg: `studio/common/ffmpeg.py` expõe `available()`, `run(args)` (levanta `RuntimeError`),
  `probe(path)` (`{duration, width, height, fps, has_audio}`).
- Medição de largura: `studio/edit/burnin.py::_font(size, bold)` devolve uma fonte do Pillow
  (Liberation/DejaVu) e `_hex(color, default)` converte `#RRGGBB` em tupla RGB. Importar esses
  dois helpers de `burnin`, não duplicar.
- `studio/edit/editor.py::safe_rel(root, rel, label)` levanta `EditorError` (subclasse de
  `ValueError`) para caminho fora do projeto.
- Fixtures de teste: `tests/conftest.py` traz `studio_env`, `client`, `ffmpeg_or_skip` e
  `make_audio(path, seconds)` (wav sintético via lavfi). Testes que dependem de ffmpeg usam
  `ffmpeg_or_skip`. Para o 409 sem ffmpeg, o padrão é `monkeypatch.setattr(ff, "FFMPEG", None)`.

Nota de fidelidade: tudo aqui é `[extensão]` (a aula 014 monta sem legendas) e deve ser marcado
como tal nas docstrings, conforme CLAUDE.md regra 2.

### Relevant Files

- `studio/etapas/edit/router.py` — `_translate`, `NO_FFMPEG`, `MAX_MEDIA_BYTES`, `upload_sfx`,
  `upload_media`; molde exato para as três rotas novas.
- `studio/common/ffmpeg.py` — `available`, `run`, `probe`; toda a extração passa por aqui.
- `studio/common/ingest.py` — `MEDIA_EXT`, `ingest_bytes`; padrão de dedupe por sha1 e probe.
- `studio/edit/burnin.py` — `_font` e `_hex` para medir a largura da linha com a fonte real do
  burn-in (a divergência com a fonte do browser é risco conhecido da §10 do TechSpec).
- `studio/edit/editor.py` — `safe_rel`, `EditorError`; validação de caminho.
- `studio/edit/service.py` — `WIDTH`/`HEIGHT`/`FPS` (canvas 1920×1080/30) e o padrão de acesso a
  `project_dir`; **não modificar este arquivo**.
- `tests/conftest.py` — `studio_env`, `client`, `ffmpeg_or_skip`, `make_audio`.
- `studio/edit/captions/__init__.py` e `transcribe.py` (task 1) — constantes e providers.

### Dependent Files

- `studio/edit/captions/layout.py` — a task 4 acrescenta `karaoke_states` e
  `karaoke_strip_states` NESTE mesmo arquivo; deixar o módulo organizado para essa extensão.
- `docs/domains/edit/postman/` (task 5) — a coleção exercita exatamente estas rotas.
- `studio/etapas/edit/view.js` (frente C, outra worktree) — consome este contrato; **não tocar**.

### Related ADRs

- ADR-024 (criada na task 5) — transcrição via OpenAI `whisper-1` com fake sem chave.
- ADR-003 (estado em arquivo) — `edit/narration/` e `index.json` em disco, sem banco.
- ADR-006 (jobs assíncronos) — o `generate` é SÍNCRONO nesta entrega; job é plano B declarado.
- ADR-008 (testes sem rede) — todo teste desta task roda no `FakeTranscribe` ou com SDK falso.

## Deliverables

- `captions/layout.py` (janelas e itens), `captions/audio.py`, `captions/service.py`.
- Três rotas novas e dois modelos Pydantic em `studio/etapas/edit/router.py`, sem alterar as
  rotas existentes.
- Logs da §7 do `_techspec.md` emitidos no logger `studio.edit.captions`.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Este workflow **não tem `_tests.md`**; os casos abaixo derivam dos critérios 1–6, 9 e 16e–f da
§9 do `_techspec.md`. Layout/serviço em `tests/test_edit_captions.py`; API em
`tests/test_edit_api.py` com prefixo `test_captions_`.

### Layout (`tests/test_edit_captions.py`)

- [x] `build_items` com 10 palavras e `chunk=6` → nenhum item com mais de 6 palavras; a união das
      `words` dos itens é exatamente as 10 originais, na ordem, sem duplicata nem perda.
- [x] `chunk=2` → nenhum item com mais de 2 palavras.
- [x] `chunk=0` com um texto longo → mais de uma janela (a largura decide), e nenhuma janela com
      menos de `KARAOKE_MIN_WORDS` palavras, exceto possivelmente a última.
- [x] Cobertura contígua: `items[0].start == start`, `items[i].end == items[i+1].start` para todo
      `i`, `items[-1].end == round(start + total_s, 3)`.
- [x] Pausa maior que `GAP_S` entre duas palavras força janelas diferentes (as duas palavras nunca
      caem no mesmo item), mesmo com `chunk` grande o bastante para caberem juntas.
- [x] Dois `generate` com `start` distintos nunca compartilham item (as janelas de cada chamada
      cobrem só o próprio intervalo).
- [x] Cada item tem exatamente o conjunto de chaves
      `{id, start, end, text, mode, hi, chunk, words, style, transform, anim}`; `id` casa
      `^cap_[0-9a-f]{6}$`; `transform.y` é `0.82` para `bottom`, `0.12` para `top`, `0.5` para
      `middle`.
- [x] `item.text` é a junção das palavras da janela por espaço simples.

### Áudio (`tests/test_edit_captions.py`, com `ffmpeg_or_skip`)

- [x] `extract_wav` sobre um wav do `make_audio` produz um arquivo cujo `ff.probe` acusa
      `has_audio` verdadeiro; com `duration=1.0` a duração resultante fica ≈ 1 s (tolerância 0.2).
- [x] `duration_of` de um wav do `make_audio(seconds=3)` devolve ≈ 3.0 (tolerância 0.3).
- [x] `duration_of` de um arquivo SEM trilha de áudio (PNG ou vídeo mudo) levanta `ValueError`.
- [x] `extracted(...)` remove o diretório temporário ao sair do `with`, inclusive quando o corpo
      levanta exceção.

### API (`tests/test_edit_api.py`, prefixo `test_captions_`)

- [x] `POST .../captions/generate` `{source:"script", text:<10 palavras>}` sem chave → `200`;
      `source == "estimate"`; `word_count == 10`; `total_s == round(10 / 2.4, 3)`; `"warning"`
      AUSENTE da resposta.
- [x] Mesmo `generate` com `start=3.0` → toda `words[].start_s` e todo `item.start` deslocados em
      3 s (`items[0].start == 3.0`).
- [x] `generate` `audio` sem `text`, sem chave (wav do `make_audio`, `ffmpeg_or_skip`) → `200`,
      `source == "estimate"`, `word_count == max(1, round(dur * 2.4))`, palavras `palavra1..N`.
- [x] `generate` `audio` COM `text`, sem chave → `200` e `[w["w"] for w in todas as words] ==
      text.split()` (o texto exibido é sempre o nosso).
- [x] `generate` `{source:"script", text:"   "}` → `422` e o `detail` (string) começa com `"text:"`.
- [x] `generate` `{source:"audio", file:"../x.wav"}` → `422` com `detail` começando por `"file:"`.
- [x] `generate` `{source:"audio", file:"edit/narration/nao-existe.wav"}` → `404`.
- [x] `generate` `{source:"audio"}` sem `file` → `422` com `detail` começando por `"file:"`.
- [x] `generate` com `mode:"x"` → `422`; com `hi:"verde"` → `422`; com `chunk: 99` → `422`
      (validação do Pydantic).
- [x] `generate` `source="audio"` com `monkeypatch.setattr(ff, "FFMPEG", None)` → `409` com a
      mensagem `NO_FFMPEG`.
- [x] Com `OPENAI_API_KEY` falsa e SDK falso que levanta: `generate` `audio` **sem** `text` →
      `502`; `generate` `audio` **com** `text` → `200`, `source == "estimate"` e `warning`
      presente na resposta.
- [x] `POST .../captions/narration/upload` com um `.wav` do `make_audio` → `200`, `added == 1`,
      `files[0]["file"]` começa com `edit/narration/`, `files[0]["duration"] > 0`.
- [x] Reenviar o MESMO conteúdo → `added == 0` (dedupe).
- [x] Upload de um `.txt` → `422`.
- [x] `GET .../captions/narration` depois do upload lista o arquivo com `file`, `name` e
      `duration`; num projeto sem uploads devolve `[]`.
- [x] Cross-feature C ← B: o resultado de um `generate` inserido numa track `caption` e enviado no
      `PUT /timeline` volta no `GET /timeline` com `words/mode/hi/chunk` preservados.

## Success Criteria

- Every assigned test case implemented and passing
- `make verify` VERDE; os 890 testes anteriores continuam passando
- As três rotas aparecem no OpenAPI do app e nenhuma rota existente mudou de shape
- Todo `422` originado no serviço tem `detail` string iniciada pelo nome do campo
- Nenhum teste faz rede; sem `OPENAI_API_KEY` o caminho é sempre `FakeTranscribe`
- `edit/timeline.json` não é escrito por nenhuma das três rotas novas
