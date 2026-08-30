# FDD: edit · Legendas no servidor `[extensão]` (frente B · legendas-backend, Wave 8)

Versão: 1.0 · Data: 2026-08-29 · Task-Id `ADH-OS-20260829-39` · Card <https://trello.com/c/bzh7UKVT> · Responsável: fluxo `/dd-parallel` (W3, modo batch; revisão humana em lote)

Fontes: `.claude/plans/2026-08-29-studio-de-video-estavel.md` (item 9, parte servidor), `docs/domains/studio/recon-wave-8.md`, `docs/domains/studio/waves/wave-8.md` (contrato HTTP CONGELADO e decisões da W2), `docs/domains/studio/diagrams/mermaid/wave-8-dependencias.md`, `docs/domains/edit/features/editor-video-completo-fdd.md`, código de referência do repo irmão `making-money-with-videos-social-media` (`videoengine/transcribe.py`, `videoengine/captions.py`, `videoengine/shots.py`, `videoengine/slideshow.py`, `app/services/speech_map.py`, `app/services/storyboard_v2.py`, `tests/test_captions.py`).

> **Gate de fidelidade (CLAUDE.md, regras 2 e 4).** A aula 014 monta no CapCut sem legendas. Tudo aqui é `[extensão]` aprovada pelo dono do produto no plano de 2026-08-29. O backbone do ffmpeg (clipes V1, pretos, música, SFX, fade) não muda. A transcrição usa um serviço externo novo (OpenAI `whisper-1`), o que exige a **ADR-024**; a ADR-002 cobre só a Higgsfield e a ADR-008 (testes sem rede) é respeitada com provider fake.

> **Modo batch.** Nenhuma pergunta foi feita ao usuário. Toda decisão tomada pelo agente está rotulada `[auto-aceito: ...]` no ponto em que aparece. Nenhuma divergência com o contrato congelado do `wave-8.md` foi auto-aceita: o que não cabe no contrato está em "Pendências" na §10.

---

## 1. Contexto e motivação técnica

O editor completo da etapa 7 (ADR-030, FDD `editor-video-completo-fdd.md`) já tem a faixa `t_cap` de legendas, mas o botão "Gerar" só mostra um toast (`view.js:553`) e o FDD anterior deixou "geração de legenda automática" como pendência por falta de transcrição. Esta frente entrega a **parte servidor** dessa pendência: um pacote `studio/edit/captions/` que produz itens de legenda prontos para `t_cap` a partir de um roteiro colado (timing proporcional) ou de um arquivo de áudio/vídeo (timing real por palavra via `whisper-1`, ou fake sem chave), a normalização dos campos aditivos `words/mode/hi/chunk` no `PUT /timeline`, o upload de narração e o burn-in karaokê (um PNG por palavra) no `master.mp4`.

Encaixe no HLD do `studio`: plugin de duas peças; a frente B só toca `router.py` (rotas aditivas) e serviços em `studio/edit/`. Nada de núcleo (`app.py`, `steps.py`, `web/*`). O estado continua em arquivo (ADR-003): `edit/narration/` para uploads, `edit/timeline.json` para as legendas (via o `PUT` que já existe). O servidor **não persiste** o resultado do `generate`; o front (frente C) insere via `commit()` e o `PUT /timeline` salva.

Porte fiel do repo irmão (ContentFlow): a lógica de `transcribe.py` (proportional, align, política assimétrica) e de `captions.py` (janelas de uma linha pela largura real, estados por palavra) é copiada/adaptada, trocando `videoengine/canvas` por `burnin._font/_hex`, o `RenderContext`/`BudgetPort` por leitura direta de `OPENAI_API_KEY` e o canvas 1080×1920 (Reels) por 1920×1080 (master do studio).

**Atores:** usuário (via modal da frente C ou Postman); serviço externo OpenAI (`whisper-1`, HTTP via SDK); ffmpeg/ffprobe local (extração de áudio e burn-in); frente C (consome o contrato); frente A (sem `consumes`; interseção só em `editor.py::normalize_item`, ramos diferentes).

**Provides** (contrato congelado do `wave-8.md`, normativo): `POST /captions/generate`, `POST /captions/narration/upload`, `GET /captions/narration`; item de `caption` com `words/mode/hi/chunk` sobrevivendo ao `PUT /timeline`; PNG por palavra no `master.mp4`; constantes compartilhadas `WPS = 2.4`, `CAPTION_MODES`, `HI_COLORS`, `CHUNK_OPTS` e a regra do centro em `studio/edit/captions/__init__.py` (a frente C espelha em `view.js`).

**Consumes:** `PUT /timeline` e `POST /render` existentes (`router.py`, `service.validate_timeline`, `editor.normalize_editor`, `render.build_filtergraph`, `burnin.render_layer_pngs`); `common/ffmpeg.py` (`available`, `run`, `probe`); `editor.safe_rel`; arquivos do projeto (`videos/<cena>/<shot>_take1.mp4`, `audio/music.*`, `edit/candidates/*`, `edit/narration/*`).

**Suposições e restrições**
- `[auto-aceito: a geração é síncrona (sem JobRegistry). O whisper recebe no máximo 25 MB de wav 16 kHz mono (~13 min), o que cabe numa chamada HTTP normal; ADR-006 fica como plano B se medições mostrarem chamadas acima de 30 s.]`
- `[auto-aceito: a chave é lida por `os.environ.get("OPENAI_API_KEY")` em tempo de chamada, nunca na importação, para `monkeypatch.setenv/delenv` funcionar sem reimport (recon §CONFIG). `settings.py` não é tocado, apesar de citado na regra de arquivos da wave: ele é o livro-caixa da ADR-016 e a decisão da W2 manda a chave ficar em `captions/`.]`
- `[auto-aceito: não há custo/crédito registrado no livro-caixa da ADR-016 para o whisper nesta entrega; o log registra `provider` e duração para auditoria futura.]`
- Sem edição de `view.js`/`view.html` (frente C) e de `steps.py`/`__init__.py` do plugin (frente A).

---

## 2. Objetivos técnicos

1. **Contrato congelado byte a byte:** as três rotas novas e os dois contratos existentes estendidos respondem exatamente o shape da §5 (que copia o `wave-8.md`); a coleção Postman valida cada status.
2. **Nosso texto, tempo ouvido:** com `source=audio` e `text`, o texto exibido é sempre o colado pelo usuário; a transcrição só fornece o tempo (regressão do "gaélico" do ContentFlow). Invariante: `[w.w for w in words] == text.split()`.
3. **Determinismo sem rede:** sem `OPENAI_API_KEY`, `generate` responde `source:"estimate"` com `proportional` (peso `len(w)+1`) e `fake_transcript` a 2,4 wps; a suíte roda sem `openai` importado (ADR-008).
4. **Política assimétrica de falha:** `words()` (temos o texto) cai em `proportional` com `warning`; `transcribe_text()` (não temos texto) levanta `ProviderError` → 502. Nunca `estimate` silencioso quando `source=audio` sem `text`.
5. **Janelas corretas:** toda palavra pertence a exatamente uma janela; janelas de um mesmo `generate` cobrem `[start, start+total_s)` sem sobreposição; a palavra pertence à janela se `a <= (start_s+end_s)/2 < b`; nenhuma janela mistura palavras de duas fontes/itens.
6. **Retrocompat total:** `PUT /timeline` sem os campos novos produz saída byte-idêntica à atual; `render` de timeline sem `words` gera os mesmos PNGs de hoje.
7. **Burn-in real:** legenda `karaoke` com N palavras gera N PNGs e N `overlay … enable='between(t,…)'` no filtergraph (critério cross-feature "B → render"); acima de 200 inputs `-i` o render cai para faixa + `ffconcat` sem mudar o resultado visual.

---

## 3. Escopo e exclusões

**Incluído**

Pacote novo `studio/edit/captions/` (tudo `[extensão]`):

| Módulo | Conteúdo |
| --- | --- |
| `__init__.py` | `WPS = 2.4`; `CAPTION_MODES = ("karaoke", "linha", "bloco")`; `HI_COLORS = ["#C8F751", "#57E2F0", "#F2B544", "#A78BFA"]`; `CHUNK_OPTS = [0, 6, 4, 2]`; `DEFAULT_HI = HI_COLORS[0]`; `word_in_window(word, a, b) -> bool` (regra do centro); `effective_mode(mode, default="bloco") -> str` (porte de `effective_karaoke`: valor fora de `CAPTION_MODES` cai no default). Único lugar do WPS no backend. |
| `transcribe.py` | `WordTiming` (frozen dataclass `text, start, end`), `ProviderError(RuntimeError)`, `proportional(text, duration_s)`, `align(text, ouvidas, duration_s)`, `fake_transcript(name, duration_s)`, `TranscribeProvider` (Protocol), `FakeTranscribe`, `OpenAITranscribe` (`model="whisper-1"`, `language="pt"`, import lazy de `openai` dentro dos métodos), `get_transcribe() -> TranscribeProvider` (fake quando não há `OPENAI_API_KEY`). |
| `audio.py` | `duration_of(path) -> float` (via `ff.probe`, exige `has_audio`); `extract_wav(src, out, duration=None) -> Path` (ffmpeg `-vn -ac 1 -ar 16000`, opcional `-t`); `WHISPER_MAX_BYTES = 25 * 1024 * 1024`; context manager `extracted(src, duration) -> Path` em `tempfile.TemporaryDirectory`. |
| `layout.py` | `LayoutOpts` (dataclass: `W, H, style, chunk, hi, mode, position, start, max_width_ratio=0.84`); `layout_windows(words, opts) -> list[list[WordTiming]]` (janela fecha por `chunk` palavras ou por largura real da linha medida com `burnin._font`, mínimo `KARAOKE_MIN_WORDS = 2`, e por pausa `GAP_S = 1.0`); `build_items(words, opts) -> list[dict]` (itens no shape do contrato); `karaoke_states(item, W, H, out_dir, n0) -> list[dict]` (um PNG por palavra usando `burnin._font/_hex`, specs `{path, start, end}`); `karaoke_strip_states(item, W, H, out_dir, n0) -> tuple[Path, int, int]` (faixa + lista `ffconcat`, para o fallback). |
| `service.py` | `generate(root, req: dict) -> dict` orquestrando `script|audio`; `import_narration(root, files) -> dict`; `list_narration(root) -> list[dict]`; constantes `NARRATION_DIR = "edit/narration"`, `MAX_SCRIPT_CHARS = 20_000`. |

Mais:
- `studio/etapas/edit/router.py`: modelos `CaptionStyleReq`, `CaptionsGenerateReq`; rotas `POST .../captions/generate`, `POST .../captions/narration/upload`, `GET .../captions/narration` (aditivas).
- `studio/edit/editor.py`: `normalize_caption_extra(raw) -> dict` chamado no ramo `caption` de `normalize_item` (decisão da W2; a frente A acrescenta `effects/filters/presetCss` no mesmo ramo, linhas distintas).
- `studio/edit/burnin.py`: `render_layer_pngs` delega para `captions.layout.karaoke_states` quando o item de `caption` tem `words` e `mode == "karaoke"`; `linha`/`bloco` seguem um PNG por item (`_text_png`). Fallback de faixa + `ffconcat` acima de `MAX_OVERLAY_INPUTS = 200`.
- `studio/edit/render.py`: `build_filtergraph` aceita spec de overlay com `kind:"concat"` (input `-f concat -safe 0 -i lista.txt`, `overlay=0:{y}:eof_action=pass:shortest=0`). `[auto-aceito: render.py não está na regra de arquivos da frente B no wave-8.md, mas a frente A não o toca e o plano (item 9) prevê "burnin.py + render.py"; a mudança é aditiva e fica marcada no PR.]`
- `requirements.txt`: `openai>=1.40` (única lista de deps; `pyproject.toml` não lista deps).
- ADR-024 + `docs/adrs/mapping.md` (indexar ADR-024 e retro-indexar ADR-030) + coleção Postman + nota neste domínio.
- Testes: `tests/test_edit_captions.py` (novo), `tests/test_edit_api.py`, `tests/test_edit_editor.py`, `tests/test_edit_service.py` (burn-in).

**Excluído**
- Toda a UI (modal "Gerar legendas", spans de karaokê, `paintKaraoke`, propriedades): frente C.
- Roteiro por LLM, TTS/síntese de voz, tradução, diarização.
- Persistir o resultado do `generate` no servidor (o `PUT /timeline` já faz isso).
- Registrar custo do whisper no livro-caixa (ADR-016) e job assíncrono para transcrição (ver §10).
- MP4 na VÍDEO 2 e efeitos em texto no `master.mp4` (continuam preview-only, ADR-030).

---

## 4. Fluxos detalhados e diagramas

Sequência completa em `docs/domains/studio/diagrams/mermaid/wave-8-dependencias.md` §2.

**Fluxo principal: `source=script` (proportional)**
1. `router.generate` valida `CaptionsGenerateReq` (Pydantic) e chama `captions.service.generate(root, req.model_dump())`.
2. `service`: `text` vazio após `split()` → `ValueError` → 422; `len(text) > MAX_SCRIPT_CHARS` → 422. `[auto-aceito: teto de 20 000 caracteres para o roteiro; o contrato só fixa 422 para texto vazio e o teto reutiliza o mesmo status.]`
3. `duration = req.duration or len(text.split()) / WPS`; `words = proportional(text, duration)` (tempos relativos, `round(3)`).
4. `words` viram absolutos somando `start`; `layout.build_items(words_abs, opts)` monta as janelas.
5. Resposta `{source:"estimate", word_count, total_s: round(duration,3), items}`.

**Fluxo: `source=audio` sem `text` (transcribe_text)**
1. `file` obrigatório; `editor.safe_rel(root, file, "captions.file")` (path traversal → `ValueError` → 422); `root/file` inexistente → `FileNotFoundError` → 404.
2. `ff.available()` falso → 409 `NO_FFMPEG` (mesma constante do `router.py:15`).
3. `audio.duration_of(path)`: `probe` sem `has_audio` → 422 "arquivo sem trilha de áudio". `duration = req.duration or file_duration`.
4. `with audio.extracted(path, duration) as wav:` extrai para tempfile (`-vn -ac 1 -ar 16000`, `-t duration` quando informado). `[auto-aceito: `duration` recorta o áudio na extração em vez de escalar os tempos como `speech_map` faz; escalar tempos reais do whisper desalinharia a fala.]` Wav acima de `WHISPER_MAX_BYTES` → 422 "áudio acima do limite do whisper (25 MB): informe `duration` menor".
5. `provider = get_transcribe()`; `texto, ouvidas = provider.transcribe_text(wav, duration)`. Erro do provedor → `ProviderError` → 502 (nunca `estimate`). Fake: `fake_transcript` + `proportional`.
6. `ouvidas` vazias com provedor real → 422 "nenhuma palavra reconhecida no áudio". `[auto-aceito: whisper sem palavras num áudio válido é resultado, não falha do provedor; 422 é o status do contrato para entrada inutilizável.]`
7. `words_abs = start + w`; `build_items`; `source = "whisper"` (real) ou `"estimate"` (fake).

**Fluxo: `source=audio` com `text` (align)**
1-4. Idênticos ao anterior.
5. `words = provider.words(wav, text, duration)`: `OpenAITranscribe.words` chama o whisper, monta `ouvidas` e devolve `align(text, ouvidas, duration)`; em qualquer exceção do provedor devolve `proportional(text, duration)` e registra `warning`. `FakeTranscribe.words` = `proportional`.
6. Resposta: `source:"whisper"` quando o alinhamento usou tempos reais; `source:"estimate"` + `warning:"transcrição indisponível: tempos estimados"` quando caiu no `proportional`. `[auto-aceito: `warning` é campo opcional da resposta, presente só no fallback, como o contrato descreve em prosa.]`
7. `align`: contagem igual → um para um; diferente → `proportional` do nosso texto dentro de `[ouvidas[0].start, ouvidas[-1].end]`; `ouvidas` vazias → `proportional` sobre `duration`.

**Fluxo: upload de narração**
1. `POST /captions/narration/upload` multipart `files[]`; cada arquivo > `MAX_MEDIA_BYTES` (200 MB) → 413. `[auto-aceito: limite de 200 MB porque o contrato aceita `.mp4/.mov/.webm`; o limite de 25 MB do whisper vale para o wav extraído, não para o upload.]`
2. Extensão fora de `MEDIA_EXT["audio"] ∪ MEDIA_EXT["video"]` → `ValueError` → 422.
3. `service.import_narration(root, files)`: grava em `edit/narration/<sha1[:12]><ext>` (dedupe por conteúdo, como `ingest_bytes`), `ff.probe` para `duration` (sem `has_audio` → arquivo removido e ignorado), sidecar `edit/narration/index.json` com `[{file, name, duration, imported}]`. `[auto-aceito: `ingest.import_upload` grava sempre em `<step>/candidates/`; para cumprir o `edit/narration/` do contrato o serviço escreve direto na pasta, copiando dedupe e probe do `ingest`.]`
4. Resposta `{added, files:[{file:"edit/narration/<x>.wav", duration}]}`.
5. `GET /captions/narration` lê `index.json` e devolve `[{file, name, duration}]` (lista vazia quando a pasta não existe).

**Fluxo: `PUT /timeline` com `words` (normalização)**
1. `editor.normalize_item("caption", raw, root)` chama `normalize_caption_extra(raw)` e faz `item.update(...)`.
2. `normalize_caption_extra` só emite chaves presentes em `raw`: `mode` → `effective_mode(raw["mode"], "bloco")`; `hi` → mantido se casa `^#[0-9A-Fa-f]{6}$` (normalizado em maiúsculas), senão omitido; `chunk` → `_clampi(raw["chunk"], 0, 20, 6)`; `words` → lista saneada como `_layout_speech`: descarta não-dict, `w` vazio, tempos não numéricos ou não finitos; `start_s = max(0, start)`, `end_s = max(start, end)`, `round(3)`; palavras válidas mantêm a ordem; lista vazia após saneamento → `words: []`. Nunca `ValueError` por palavra.
3. Item sem os campos → dict idêntico ao atual (retrocompat byte a byte).

**Fluxo: render karaokê (burn-in)**
1. `render.start_render` → `burnin.render_layer_pngs(root, editor, 1920, 1080, root/"edit"/"_overlays")`.
2. Para item de `caption` com `words` não vazias e `mode == "karaoke"`: `layout.karaoke_states(item, W, H, out_dir, n)` gera um PNG full-frame por palavra (linha inteira do item, palavra corrente em `hi`, demais em `style.color`, fundo `style.bg`, sombra como `_text_png`), spec `{path, start: w.start_s, end: próxima.start_s ou item.end}`, `end - start >= 1/30`. `[auto-aceito: a janela de cada palavra vai até o início da próxima (ou o fim do item) em vez de `end_s`, para a linha não piscar em pausas do whisper e as janelas serem contíguas por construção.]` Palavras fora de `[item.start, item.end)` pelo centro são ignoradas.
3. `linha` e `bloco`: um PNG por item via `_text_png` (como hoje).
4. Após montar os specs, se `len(specs) + inputs do backbone > MAX_OVERLAY_INPUTS (200)`: os specs de karaokê são refeitos como **faixa**: `karaoke_strip_states` gera PNGs `W × altura_da_linha` e uma lista `ffconcat version 1.0` (`file`/`duration` por estado, `vazio.png` nos intervalos, última entrada repetida, como `slideshow._subtitle_input`), devolvendo um único spec `{kind:"concat", path: lista, y: topo, start: 0, end: duração}`. `build_filtergraph` acrescenta `-f concat -safe 0 -i lista` e `overlay=0:{y}:eof_action=pass:shortest=0`. Os demais overlays seguem o caminho normal.
5. `_overlays` é apagada no fim do render como hoje.

**Fluxos alternativos e exceções**
- `generate` com `mode`/`hi`/`position`/`source` fora do domínio → 422 pelo Pydantic (`Literal`/regex), antes do serviço.
- `source=script` com `file` → `file` ignorado. `source=audio` com `duration <= 0` → 422.
- Falha do ffmpeg na extração (`RuntimeError`) → 422 "não foi possível extrair o áudio". `[auto-aceito: erro do ffmpeg local é problema de entrada/ambiente, não do provedor; 502 fica reservado ao whisper como diz o contrato.]`
- `render`: falha ao gerar PNGs de legenda vira aviso no job e não derruba o render (comportamento atual de `render.py:391-393`).

---

## 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Prefixo `/api/projects/{pid}/edit`. Os itens 1 a 4 copiam o **contrato congelado** do `wave-8.md` (normativo; qualquer divergência vira pendência, nunca auto-aceite).

### 5.1 Modelos Pydantic (`router.py`)

```python
class CaptionStyleReq(BaseModel):
    model_config = ConfigDict(extra="allow")   # presets do editor podem trazer font/shadow etc.
    size: int = 34
    weight: int = 700
    align: str = "center"
    color: str = "#FFFFFF"
    bg: str = "transparent"


class CaptionsGenerateReq(BaseModel):
    source: Literal["script", "audio"]
    text: str | None = None
    file: str | None = None
    start: float = 0.0
    duration: float | None = None
    mode: Literal["karaoke", "linha", "bloco"] = "karaoke"
    chunk: int = Field(6, ge=0, le=20)
    hi: str = Field("#C8F751", pattern=r"^#[0-9A-Fa-f]{6}$")
    position: Literal["top", "middle", "bottom"] = "bottom"
    style: CaptionStyleReq = CaptionStyleReq()
```

`[auto-aceito: `CaptionStyleReq` com `extra="allow"` para o preset do editor atravessar intacto; o `PUT /timeline` já normaliza `style` por `normalize_style`.]`

### 5.2 `POST /captions/generate`

- Tipo: endpoint · Método: POST · Síncrono · Timeout do whisper: 120 s.
- Defaults: `start=0`, `duration` = duração do arquivo (`audio`) ou `len(words)/2.4` (`script`), `mode="karaoke"`, `chunk=6` (0 = uma janela por linha de largura), `hi="#C8F751"`, `position="bottom"`, `style` = preset de legenda do editor.
- Semântica de status:
  - `200`: itens prontos para `editor.tracks[t_cap].items[]`; o servidor não persiste.
  - `422`: `text` vazio em `script`; `file` ausente/inválido (path traversal); `mode` fora de `karaoke|linha|bloco`; `hi` não `#RRGGBB`; arquivo sem áudio; wav acima de 25 MB; falha de extração.
  - `404`: arquivo não existe.
  - `409`: ffmpeg indisponível (`NO_FFMPEG`) com `source=audio`.
  - `502`: `ProviderError` do whisper (`source=audio` sem `text`). Com `text`, cai em `proportional` e responde `200` com `source:"estimate"` + `warning`.

Exemplo de requisição (`script`):
```json
{
  "source": "script",
  "text": "Você já parou pra pensar no que sustenta tudo isso?",
  "start": 0.0,
  "mode": "karaoke",
  "chunk": 6,
  "hi": "#C8F751",
  "position": "bottom",
  "style": { "size": 34, "weight": 700, "align": "center", "color": "#FFFFFF", "bg": "transparent" }
}
```

Exemplo de requisição (`audio` alinhando o roteiro):
```json
{
  "source": "audio",
  "file": "edit/narration/3f9a1c2b7d4e.wav",
  "text": "Você já parou pra pensar no que sustenta tudo isso?",
  "start": 2.0,
  "duration": 12.5,
  "mode": "karaoke",
  "chunk": 0,
  "hi": "#57E2F0",
  "position": "bottom"
}
```

Exemplo de resposta `200`:
```json
{
  "source": "estimate",
  "word_count": 10,
  "total_s": 4.167,
  "items": [
    { "id": "cap_a1b2c3", "start": 0.0, "end": 2.31, "text": "Você já parou pra pensar no",
      "mode": "karaoke", "hi": "#C8F751", "chunk": 6,
      "words": [ { "w": "Você", "start_s": 0.0, "end_s": 0.394 }, { "w": "já", "start_s": 0.394, "end_s": 0.63 } ],
      "style": { "size": 34, "weight": 700, "align": "center", "color": "#FFFFFF", "bg": "transparent" },
      "transform": { "x": 0.5, "y": 0.82, "scaleX": 1, "scaleY": 1, "rotation": 0, "opacity": 1 },
      "anim": { "in": "fade", "out": "fade" } }
  ],
  "warning": "transcrição indisponível: tempos estimados"
}
```
`warning` só aparece no fallback do fluxo `audio` com `text`. `words[].start_s/end_s` são segundos absolutos da timeline (`start` somado). `transform.y` por `position`: `top=0.12`, `middle=0.5`, `bottom=0.82` `[auto-aceito: 0.82 é o y que `addText` já usa para legenda em `view.js:933`]`. `id` = `cap_` + 6 hex.

### 5.3 `POST /captions/narration/upload`

- Tipo: endpoint · Método: POST · multipart `files[]` (`.wav .mp3 .m4a .ogg .mp4 .mov .webm`), limite 200 MB por arquivo.
- Status: `200` `{added, files:[{file, duration}]}`; `413` arquivo acima do limite; `422` extensão não aceita; `404` projeto inexistente.
- Grava em `edit/narration/` (mesmo padrão de `sfx/upload`: dedupe por conteúdo, probe de duração).

Resposta:
```json
{ "added": 1, "files": [ { "file": "edit/narration/3f9a1c2b7d4e.wav", "duration": 12.48 } ] }
```

### 5.4 `GET /captions/narration`

- Método: GET · `200` lista `[{file, name, duration}]` (vazia sem uploads) · `404` projeto inexistente.

```json
[ { "file": "edit/narration/3f9a1c2b7d4e.wav", "name": "narracao-take1.wav", "duration": 12.48 } ]
```

### 5.5 `PUT /timeline` (existente, aditivo)

Item de `caption` aceita `mode`, `hi`, `chunk`, `words`; itens sem eles continuam byte-idênticos. `words` inválidas são descartadas (nunca 422); `mode` inválido vira `bloco`; `hi` inválido é omitido; `chunk` clampado em `[0, 20]`.

```json
{ "id": "cap_a1b2c3", "start": 0.0, "end": 2.31, "text": "Você já parou",
  "mode": "karaoke", "hi": "#C8F751", "chunk": 6,
  "words": [ { "w": "Você", "start_s": 0.0, "end_s": 0.394 }, { "w": "", "start_s": 9, "end_s": 1 } ] }
```
→ round-trip com `words` de 1 elemento (a segunda é descartada).

### 5.6 `POST /render` (existente, aditivo)

Legenda `karaoke` gera um PNG por palavra (spec por palavra, `enable='between(t,start,end)'`); `linha` um PNG por item; `bloco` como hoje. Acima de 200 inputs, faixa + `ffconcat` (mesmo resultado visual). Status inalterados (409 sem ffmpeg/`NO_MUSIC`/já rodando, 404, 422 sem clipes).

### 5.7 Assinaturas Python (contratos internos)

```python
# studio/edit/captions/__init__.py
WPS: float = 2.4
CAPTION_MODES: tuple[str, ...] = ("karaoke", "linha", "bloco")
HI_COLORS: list[str] = ["#C8F751", "#57E2F0", "#F2B544", "#A78BFA"]
CHUNK_OPTS: list[int] = [0, 6, 4, 2]
def word_in_window(word: dict | WordTiming, a: float, b: float) -> bool
def effective_mode(mode: str | None, default: str = "bloco") -> str

# studio/edit/captions/transcribe.py
@dataclass(frozen=True)
class WordTiming: text: str; start: float; end: float
class ProviderError(RuntimeError): ...
class TranscribeProvider(Protocol):
    def words(self, audio: Path, text: str, duration_s: float) -> list[WordTiming]: ...
    def transcribe_text(self, audio: Path, duration_s: float) -> tuple[str, list[WordTiming]]: ...
def proportional(text: str, duration_s: float) -> list[WordTiming]
def align(text: str, ouvidas: list[WordTiming], duration_s: float) -> list[WordTiming]
def fake_transcript(name: str, duration_s: float) -> str
class FakeTranscribe: ...
class OpenAITranscribe:
    model = "whisper-1"; language = "pt"; timeout_s = 120
    def __init__(self, api_key: str) -> None
def get_transcribe() -> TranscribeProvider          # lê OPENAI_API_KEY em runtime

# studio/edit/captions/audio.py
WHISPER_MAX_BYTES = 25 * 1024 * 1024
def duration_of(path: Path) -> float                 # RuntimeError sem ffprobe; ValueError sem áudio
def extract_wav(src: Path, out: Path, duration: float | None = None) -> Path
@contextmanager
def extracted(src: Path, duration: float | None = None) -> Iterator[Path]

# studio/edit/captions/layout.py
KARAOKE_MIN_WORDS = 2; GAP_S = 1.0; MAX_WIDTH_RATIO = 0.84
@dataclass
class LayoutOpts: W: int = 1920; H: int = 1080; style: dict; chunk: int = 6; hi: str; mode: str; position: str; start: float = 0.0
def layout_windows(words: list[WordTiming], opts: LayoutOpts) -> list[list[WordTiming]]
def build_items(words: list[WordTiming], opts: LayoutOpts) -> list[dict]
def karaoke_states(item: dict, W: int, H: int, out_dir: Path, n0: int) -> list[dict]
def karaoke_strip_states(item: dict, W: int, H: int, out_dir: Path, n0: int) -> tuple[Path, int, float]

# studio/edit/captions/service.py
def generate(root: Path, req: dict) -> dict          # ValueError→422, FileNotFoundError→404, ProviderError→502
def import_narration(root: Path, files: list[tuple[str, bytes]]) -> dict
def list_narration(root: Path) -> list[dict]

# studio/edit/editor.py
def normalize_caption_extra(raw: dict) -> dict

# studio/edit/burnin.py
MAX_OVERLAY_INPUTS = 200
def render_layer_pngs(root, editor, W, H, out_dir) -> list[dict]   # specs {path,start,end} ou {kind:"concat",path,y,start,end}
```

`OpenAITranscribe.words/transcribe_text` chamam `client.audio.transcriptions.create(model="whisper-1", file=fh, response_format="verbose_json", timestamp_granularities=["word"], language="pt")` com `OpenAI(api_key=..., timeout=120, max_retries=1)` importado dentro do método. `[auto-aceito: `max_retries=1` (o SDK usa 2 por default) para a chamada síncrona não passar de ~4 min no pior caso.]`

---

## 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Status | Tratamento |
| --- | --- | --- |
| `source=script` com `text` vazio/só espaços | 422 | `ValueError` no serviço |
| `text` acima de 20 000 caracteres | 422 | `ValueError` |
| `source=audio` sem `file` | 422 | `ValueError` |
| `file` com path traversal | 422 | `editor.safe_rel` |
| `file` não existe | 404 | `FileNotFoundError` |
| `source`, `mode`, `position` fora do domínio; `hi` não `#RRGGBB`; `chunk` fora de 0..20 | 422 | Pydantic |
| `source=audio` sem ffmpeg | 409 | `NO_FFMPEG` (mesma constante do router) |
| arquivo sem trilha de áudio (`probe.has_audio=False`) | 422 | `ValueError` |
| falha do ffmpeg na extração | 422 | `RuntimeError` → `ValueError` "não foi possível extrair o áudio" |
| wav extraído > 25 MB | 422 | `ValueError` pedindo `duration` menor |
| whisper falha e não há `text` (`transcribe_text`) | 502 | `ProviderError`; nunca `estimate` |
| whisper falha e há `text` (`words`) | 200 | `proportional` + `source:"estimate"` + `warning` + log `warning` |
| whisper devolve zero palavras sem `text` | 422 | `ValueError` "nenhuma palavra reconhecida" |
| `OPENAI_API_KEY` ausente | 200 | `FakeTranscribe`; `source:"estimate"` |
| upload acima de 200 MB | 413 | `HTTPException` no router |
| upload com extensão não aceita | 422 | `ValueError` |
| upload sem áudio (probe) | 200 | arquivo descartado; não conta em `added` |
| `PUT` com `words` inválidas | 200 | descartadas uma a uma; nunca 422 |
| `PUT` com `mode` inválido / `hi` inválido / `chunk` fora | 200 | `bloco` / omitido / clamp |
| burn-in: falha ao rasterizar uma legenda | render segue | aviso no job (`render.py:391-393`) |
| render com > 200 inputs | render segue | fallback faixa + `ffconcat` |

**Política assimétrica (porte fiel do ContentFlow):** `words()` (texto conhecido) nunca levanta; cai em `proportional` porque legenda é enfeite e o texto já é nosso. `transcribe_text()` (texto desconhecido) levanta `ProviderError` porque sem transcrição não há o que legendar. O router traduz: `ProviderError` → 502, `ValueError` → 422, `FileNotFoundError` → 404.

**Resiliência:** timeout 120 s e `max_retries=1` no SDK; sem backoff próprio nem circuit breaker (app local single-user). Tempfile sempre removido (`TemporaryDirectory`). Sem retries na extração.

**Invariantes**
- `[w.w for w in words] == text.split()` sempre que `text` foi enviado.
- Toda palavra pertence a exatamente um item; itens de um `generate` são ordenados, não se sobrepõem e cobrem `[start, start + total_s)`.
- `item.start == words[0].start_s` e `item.end == words[-1].end_s` (`round(3)`).
- `PUT /timeline` sem os campos novos = saída byte-idêntica; `words` nunca produzem 422.
- O backbone (`clips/blacks/music/sfx/fade_out/loudnorm`) e `timeline.json` não são alterados por `generate` nem por `render`.
- A chave da OpenAI nunca aparece em log, resposta ou arquivo.

---

## 7. Observabilidade

**Métricas** (derivadas dos logs; sem sistema de métricas no app local): contagem de `generate` por `source` e `provider`; duração da chamada ao whisper; contagem de fallback (`warning`); número de PNGs por render e uso do fallback `concat`.

**Logs** (logger `studio.edit.captions`, formato do app):
- `INFO captions.generate pid=<pid> source=<script|audio> provider=<fake|openai> result=<estimate|whisper> word_count=<n> items=<n> total_s=<f> file=<rel|-> elapsed_ms=<n>`
- `WARNING captions.fallback pid=<pid> reason=<str>` quando `words()` caiu em `proportional`.
- `ERROR captions.provider pid=<pid> error=<str>` antes do 502 (mensagem do SDK truncada em 300 caracteres).
- `INFO captions.narration pid=<pid> added=<n> skipped=<n>`.
- `INFO burnin.captions pid=<pid> karaoke_items=<n> pngs=<n> mode=<overlay|concat>` (logger `studio.edit`, já existente).
- Nunca gravar `OPENAI_API_KEY`, o texto do roteiro inteiro nem o áudio; `text` aparece só como `word_count`.

**Tracing:** não há; `elapsed_ms` no log de `generate` cobre a necessidade.

**Dashboards e alertas:** nenhum (app local). O job de render (`jobs/edit_render_<stamp>.json`) registra o aviso de burn-in como hoje.

---

## 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| `openai` (SDK Python) | `>=1.40` | Só em `requirements.txt` (única lista de deps; `pyproject.toml` não lista). Import lazy dentro de `OpenAITranscribe`; a suíte nunca o importa (ADR-008). `[auto-aceito: sem teto de versão; o uso é uma chamada estável (`audio.transcriptions.create`).]` |
| ffmpeg/ffprobe | build estática atual (7.x em `~/.local/bin`) | Extração `-vn -ac 1 -ar 16000` e `-f concat`; `available()` guarda o 409 |
| Pillow | atual do projeto | `burnin._font/_hex` reutilizados; fontes Liberation/DejaVu (largura medida com a fonte do Pillow, não a do preview) |
| Python | 3.12 | `dataclass(frozen=True)`, `Literal` |
| `OPENAI_API_KEY` | env | Lida em runtime em `captions.transcribe.get_transcribe`; ausente = fake |

**ADRs:** **ADR-024** (nova): transcrição de legendas via OpenAI `whisper-1` com fake sem chave; é o primeiro serviço externo HTTP do studio. Explicita que ADR-002 proíbe só a API da Higgsfield (a ponte continua CLI) e que ADR-008 é cumprida por `FakeTranscribe` + import lazy. Relaciona ADR-003 (arquivos), ADR-004 (fidelidade, `[extensão]`), ADR-006 (síncrono; job é plano B), ADR-016 (custo não registrado nesta entrega) e ADR-030 (bloco `editor` aditivo). `mapping.md` ganha a ADR-024 e retro-indexa a ADR-030 (decisão da W2).

**Garantias de compatibilidade**
- `PUT/GET /timeline` sem `mode/hi/chunk/words`: saída byte-idêntica (teste de regressão compara o dict antes/depois da mudança).
- `MAX_ITEMS = 4000` continua valendo: `words` ficam dentro do item e não contam como itens; `generate` nunca devolve mais itens do que palavras.
- `render` de timeline sem `words`: mesmos PNGs e mesmo filtergraph de hoje.
- Rotas existentes inalteradas; `export` (etapa 8) continua consumindo `edit/master.mp4`.
- Frente C consome só o contrato da §5 e as constantes de `captions/__init__.py`.

---

## 9. Critérios de aceite técnicos

**Funcionais (pytest, sem rede, sem navegador)**
1. `POST /captions/generate` `{source:"script", text:<10 palavras>}` sem chave → `200`, `source=="estimate"`, `word_count==10`, `total_s == round(10/2.4, 3)`, itens ordenados, `items[i].end == items[i+1].start`, `items[0].start == 0`, `items[-1].end == total_s`, cada item no shape (`id/start/end/text/mode/hi/chunk/words/style/transform/anim`), `transform.y == 0.82`.
2. `generate` com `start=3.0` desloca todas as `words` e itens em 3 s.
3. `generate` `script` com `chunk=2` → nenhum item com mais de 2 palavras; `chunk=0` → janelas só pela largura (item com texto longo quebra em mais de uma janela).
4. `generate` `audio` sem chave (fixture `make_audio`, `ffmpeg_or_skip`) → `200`, `source=="estimate"`, `word_count == max(1, round(dur*2.4))`, palavras `palavra1..N`.
5. `generate` `audio` com `text` sem chave → `200`, `[w.w] == text.split()`.
6. `generate`: `text` vazio → 422; `file:"../x.wav"` → 422; `file` inexistente → 404; `mode:"x"` → 422; `hi:"verde"` → 422; `source=audio` sem `file` → 422; `source=audio` sem ffmpeg (`monkeypatch ff.FFMPEG=None`) → 409.
7. `OpenAITranscribe` com `sys.modules["openai"]` fake: `transcribe_text` mapeia `result.words` para `WordTiming`; cliente que levanta → `ProviderError` em `transcribe_text` e `proportional` em `words`; `generate` `audio` sem `text` com chave fake e cliente que falha → 502; com `text` → 200 + `source:"estimate"` + `warning`.
8. `get_transcribe()` devolve `FakeTranscribe` sem `OPENAI_API_KEY` e `OpenAITranscribe` com a chave (`monkeypatch.setenv`, sem reimport); `import studio.edit.captions` não importa `openai` (`"openai" not in sys.modules` após importar o pacote com a chave ausente).
9. Upload de narração (`.wav` do `make_audio`) → `200`, `added==1`, `files[0].file` começa com `edit/narration/`, `duration > 0`; reenvio do mesmo conteúdo → `added==0`; `.txt` → 422; `GET /captions/narration` lista o arquivo com `name` e `duration`.
10. `PUT /timeline` com item de `caption` com `words/mode/hi/chunk` → `GET` devolve os quatro campos iguais (round-trip); palavras com `w` vazio, `start_s` não numérico, `end_s < start_s` (corrigido para `start_s`) são tratadas sem 422; `mode:"x"` → `"bloco"`; `hi:"x"` ausente; `chunk: 99` → 20.
11. `PUT /timeline` com item de `caption` **sem** os campos → dict de saída idêntico ao de antes da mudança (fixture congelada).
12. `normalize_caption_extra({})` == `{}`; idempotente (normalizar duas vezes = mesma saída).
13. Burn-in: `render_layer_pngs` com uma legenda `karaoke` de N palavras gera N PNGs `{path,start,end}` contíguos (`spec[i].end == spec[i+1].start`), `end - start >= 1/30`, primeiro `start == item.start`, último `end == item.end`; PNG da palavra i tem pixels na cor `hi` e as demais palavras em `style.color`; `linha`/`bloco` → 1 PNG.
14. `build_filtergraph` com esses specs contém N ocorrências de `overlay=0:0:enable='between(t,` (critério **B → render**).
15. Com mais de 200 inputs (mock de `MAX_OVERLAY_INPUTS=5` + 6 palavras) o spec vira `{kind:"concat"}`, a lista `ffconcat` tem N entradas `file` + `duration` e a última repetida, e o filtergraph contém `-f concat` e `overlay=0:<y>:eof_action=pass:shortest=0`.
16. Porte do ContentFlow em `test_edit_captions.py`: (a) `align` devolve nosso texto com os tempos ouvidos (contagem igual); (b) contagem diferente usa o intervalo real `[2.0, 4.0]`; (c) `ouvidas=[]` cai no proporcional até `duration`; (d) `proportional` é determinístico e pesa `len+1` (`"de desenvolvimento"` → segunda palavra mais longa); (e) janelas cobrem a fala inteira e não se sobrepõem; (f) janela nunca junta palavras de duas fontes (dois `generate` com `start` distintos, ou pausa > `GAP_S`, nunca compartilham item); (g) narração longa encolhe a fonte: `karaoke_states` com janela cujo texto não cabe em `0.84*W` reduz o corpo até caber ou até `MIN_FONT_PX=18` `[auto-aceito: escada de corpos por fator 0.9 a partir de `style.size`, como `draw_caption` faz com 52→36]`; (h) `fake_transcript(name, 5.0)` tem 12 palavras e não depende de `name`.
17. `ruff check` e `pytest` verdes (`make verify`); nenhum teste faz rede.

**Cross-feature (cobrados na W5)**
- `[cross-feature C ← B]` Os itens de `generate` inseridos em `t_cap` sobrevivem ao `PUT /timeline` + `GET` (`words/mode/hi/chunk` presentes). Evidência: request "generate → PUT → GET" na coleção Postman de B + teste de API de C.
- `[cross-feature C ← B]` Constantes `WPS`, `CAPTION_MODES`, `HI_COLORS`, `CHUNK_OPTS` e `word_in_window` em `captions/__init__.py` têm o mesmo valor que `view.js` da frente C (teste de contrato de C lê o arquivo).
- `[cross-feature B → render]` `POST /render` com legenda karaokê de N palavras gera N PNGs e N `overlay … enable=between` (critérios 13 e 14).

**Testes por arquivo**
- `tests/test_edit_captions.py` (novo): critérios 7, 8, 12, 16 (a–h); `layout_windows` com `chunk` e largura; `word_in_window` nos limites (`a` incluso, `b` excluso); `effective_mode`; `audio.extract_wav` produz wav 16 kHz mono (`ffmpeg_or_skip`); `duration_of` sem áudio → `ValueError`.
- `tests/test_edit_api.py`: critérios 1 a 6, 9 (generate script/audio fake, 422/404/409, upload/list narração, 502 com cliente fake).
- `tests/test_edit_editor.py`: critérios 10, 11 (round-trip `words/mode/hi/chunk`, inválidos descartados, retrocompat byte a byte).
- `tests/test_edit_service.py` (burn-in): critérios 13, 14, 15.

---

## 10. Riscos e mitigação

### Whisper devolve palavras em outro idioma ou contagem diferente do roteiro
- **Probabilidade:** média
- **Impacto:** legenda ilegível (regressão do "gaélico") ou dessincronizada
- **Mitigação:**
    - `language="pt"` fixo; com `text`, o texto exibido é sempre o nosso (`align`), a transcrição só dá o tempo
    - contagem diferente → distribuição proporcional dentro do intervalo real da fala
- **Plano de contingência:** o usuário regera com `source=script` (`estimate`) ou edita as `words` no front (frente C)

### Áudio dos takes não tem fala (o método gera vídeo sem som)
- **Probabilidade:** alta
- **Impacto:** `generate` por `audio` sobre take devolve zero palavras (422) e o usuário estranha
- **Mitigação:**
    - 422 com mensagem clara "nenhuma palavra reconhecida"; a UI (C) rotula que a fonte "áudio" na prática é o upload de narração
    - `probe.has_audio` barra arquivos mudos antes da chamada paga
- **Plano de contingência:** fonte `script`

### Render com centenas de inputs `-i` (60 s de karaokê ≈ 145 PNGs)
- **Probabilidade:** média
- **Impacto:** linha de comando enorme, memória do ffmpeg, render lento
- **Mitigação:**
    - PNG full-frame só até 200 inputs; acima, faixa de altura da linha + `ffconcat` (um único input), como `slideshow._subtitle_input`
    - PNGs gerados em `_overlays` e apagados no fim
- **Plano de contingência:** baixar o limiar (`MAX_OVERLAY_INPUTS`) após medição real

### Divergência de largura entre preview (fonte do browser) e burn-in (Liberation/DejaVu)
- **Probabilidade:** alta
- **Impacto:** quebra de janela diferente entre o palco e o mp4 em linhas longas
- **Mitigação:**
    - as janelas são decididas no servidor (`build_items`) e viajam nos itens; o front só re-fatia por `chunk` com `chunkOf`, não por largura
    - `chunk=6` default limita a linha por contagem, onde as fontes divergem pouco
- **Plano de contingência:** `chunk` menor; a ADR-030 já aceita pequena divergência preview × mp4

### Chamada síncrona longa ao whisper
- **Probabilidade:** baixa (≤ 25 MB, ≈ 13 min de áudio)
- **Impacto:** requisição HTTP presa até 120 s; UI sem progresso
- **Mitigação:**
    - timeout 120 s, `max_retries=1`; `duration` recorta o áudio
    - `elapsed_ms` no log para medir
- **Plano de contingência:** mover para `JobRegistry` (ADR-006) com polling, sem mudar o shape da resposta final

### Custo da OpenAI fora do livro-caixa (ADR-016)
- **Probabilidade:** média
- **Impacto:** gasto não contabilizado no painel de créditos
- **Mitigação:** log por chamada com duração; ADR-024 registra a lacuna
- **Plano de contingência:** registrar `record_generation("edit.captions")` numa rodada seguinte

**Pendências (não auto-aceitas; subir para a revisão em lote)**
1. **Custo do whisper no livro-caixa da ADR-016:** o contrato congelado não fala em créditos; a frente B não registra custo. Decidir se entra nesta wave ou numa rodada seguinte.
2. **`render.py` fora da regra de arquivos da frente B** (wave-8.md lista só `burnin.py`): o fallback `ffconcat` exige uma mudança aditiva em `build_filtergraph`. Sem ela, o fallback não existe e o limiar de 200 vira só um aviso no log. Confirmar no lote.
3. **Status 422 para "wav acima de 25 MB" e "zero palavras reconhecidas":** o contrato lista 422 apenas para `text` vazio, `file` inválido, `mode` e `hi`. As duas condições novas reutilizam o 422 (não criam status novo), mas ampliam a prosa do contrato. Confirmar ou trocar por 413/502.
4. **Campo `warning` na resposta:** o contrato o cita em prosa ("responde `source:"estimate"` + `warning`") mas não no JSON de exemplo. Este FDD o trata como campo opcional, só no fallback. Confirmar.
5. **Job assíncrono para transcrição:** fora desta entrega; decidir gatilho (tamanho do áudio ou tempo medido).

---

## 11. Sequenciamento de implementação (Build Order)

**Caminho: SDD (Compozy).** Regra do `dd-parallel-feature`: direta só se ≤ 3 contratos **e** 1 fluxo principal **e** ≤ 8 arquivos. Aqui são 5 contratos (§5.2 a §5.6), 3 fluxos principais (script, audio sem text, audio com text) mais upload e render, e 16 arquivos (5 do pacote + `router.py`, `editor.py`, `burnin.py`, `render.py`, `requirements.txt`, 4 de teste, ADR, `mapping.md`, Postman). Logo **SDD**: `cy-create-tasks` a partir deste FDD, `compozy tasks run` na worktree `feature/adh-os-20260829-39-legendas-backend` (porta 8767), reconciliação e revalidação no estado integrado antes do PR (rebase sobre A por causa de `editor.py`/`test_edit_editor.py`).

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (§9) |
| --- | --- | --- | --- | --- |
| 1 | Constantes e transcrição pura | - | `studio/edit/captions/__init__.py`, `captions/transcribe.py`, `requirements.txt` (`openai>=1.40`), `tests/test_edit_captions.py` | 7, 8, 16a–d, 16h |
| 2 | Normalização aditiva do item `caption` | - | `studio/edit/editor.py` (`normalize_caption_extra` no ramo `caption`), `tests/test_edit_editor.py` | 10, 11, 12 |
| 3 | Layout de janelas e itens | 1 | `captions/layout.py` (`layout_windows`, `build_items`, `word_in_window`), `tests/test_edit_captions.py` | 3, 16e–f |
| 4 | Extração de áudio e serviço | 1, 3 | `captions/audio.py`, `captions/service.py` (`generate`, `import_narration`, `list_narration`) | 2, 4, 5 (nível serviço) |
| 5 | Rotas e modelos | 4 | `studio/etapas/edit/router.py` (`CaptionStyleReq`, `CaptionsGenerateReq`, 3 rotas, tradução de erros), `tests/test_edit_api.py` | 1–6, 9 |
| 6 | Burn-in karaokê | 2, 3 | `captions/layout.py` (`karaoke_states`, `karaoke_strip_states`), `studio/edit/burnin.py`, `studio/edit/render.py` (spec `concat`), `tests/test_edit_service.py` | 13, 14, 15, 16g, B → render |
| 7 | Observabilidade | 4, 6 | logs em `captions/service.py`, `burnin.py` | §7 |
| 8 | ADR e documentação | 1–6 | `docs/adrs/generated/STUDIO/ADR-024-transcricao-de-legendas-via-openai-whisper-1-com-fake-sem-chave.md`; `docs/adrs/mapping.md` (seção "Atualização 2026-08-29 (wave 8, frente ADH-OS-20260829-39)": indexar ADR-024 e retro-indexar ADR-030); `docs/adrs/README.md` (linha da ADR-024); nota `[extensão]` em `editor-video-completo-fdd.md` apontando para este FDD | §8 |
| 9 | Coleção Postman | 5 | `docs/domains/edit/postman/edit.postman_collection.json` (pasta "captions [extensão]": generate script 200, generate audio fake 200, generate text vazio 422, generate file inválido 422, generate file inexistente 404, narration/upload (multipart), GET narration, PUT timeline com words → GET round-trip) + `README.md` | C ← B (Postman), 17 (`make qa-api`) |
| 10 | `make verify` + revalidação integrada + PR | 1–9 | worktree, rebase sobre A, gate `ft-pr` | 17 |

**ADR-024, título sugerido:** "Transcrição de legendas via OpenAI whisper-1 com fake sem chave". Conteúdo mínimo: contexto (legendas `[extensão]`, primeiro serviço externo HTTP do studio), decisão (SDK `openai` com import lazy, `whisper-1` `verbose_json` por palavra, `language=pt`, chave `OPENAI_API_KEY` em runtime, `FakeTranscribe` sem chave com `source:"estimate"`, política assimétrica `words()`/`transcribe_text()`, nosso texto nunca o ouvido), alternativas (whisper local: peso do modelo e CPU; transcrição no browser: quebra ADR-008 e fidelidade), consequências (dependência de rede opcional, custo não contabilizado, testes 100% fake), relações (ADR-002 restringe só a Higgsfield; ADR-003, ADR-004, ADR-006, ADR-008, ADR-016, ADR-030).
