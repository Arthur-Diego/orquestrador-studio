# Wave 1 — API transversal disponível para as frentes

Implementada pelo orquestrador ANTES das frentes (PR de preparo), para que nenhuma frente
edite arquivos únicos. Frentes devem **usar** estes módulos, nunca copiá-los nem alterá-los.

## `studio/common/ingest.py` — importação de mídia por etapa
```python
MEDIA_EXT = {"image": {".png", ".jpg", ".jpeg", ".webp"}, "video": {".mp4", ".mov", ".webm"}, "audio": {".wav", ".mp3", ".m4a", ".ogg"}}
DOWNLOADS_DEFAULT: Path                       # pasta Downloads do usuário (override STUDIO_DOWNLOADS)
ingest_bytes(root, step, data, source, name, prompt="", meta=None, kind="image") -> dict | None
    # grava root/<step>/candidates/<sha12>.<ext> (+ thumbs/<sha12>.jpg para imagem e vídeo),
    # registra em root/<step>/candidates.json {id, kind, source, name, prompt, file, thumb, width, height, duration, selected, imported, **meta}
    # devolve None se duplicado (mesmo conteúdo) ou inválido
load_candidates(root, step) -> list[dict]; save_candidates(root, step, cands) -> None
import_upload(root, step, files: list[tuple[str, bytes]], prompt="", kind="image") -> {"added": n}
import_downloads(root, step, folder=None, since_minutes=120, limit=40, kind="image") -> {"added", "scanned", "folder"}
import_history(root, step, kind="image", size=50, prompt_filter=None) -> {"added", "jobs"}   # via hf.history_media
```
`root` é sempre `refs.service.project_dir(pid)`. `step` é o id da etapa (pasta).

## `studio/common/jobs.py` — jobs em thread com lock (padrão ADR-006)
```python
registry = JobRegistry()                       # um por módulo de serviço: registry = JobRegistry()
registry.start(key, total, fn) -> dict         # fn(job) roda em thread daemon; RuntimeError se já houver job "running" para key
registry.status(key) -> dict                   # {"state": idle|running|done|error, "done", "total", "added", "error", "log": [], **extras}
```
Dentro de `fn(job)`: atualize `job["done"]`, `job["added"]`, `job["log"].append(...)`; exceção vira `state=error`.

## `studio/common/ffmpeg.py` — ffmpeg/ffprobe (estático em ~/.local/bin)
```python
FFMPEG, FFPROBE: str | None; available() -> bool
run(args: list[str], timeout=600) -> subprocess.CompletedProcess   # levanta RuntimeError com stderr
probe(path) -> {"duration": s, "width", "height", "fps", "has_audio": bool}
last_frame(video, out_png, offset=0.05) -> Path
video_thumb(video, out_jpg, t=0.5) -> Path
```

## `studio/higgsfield.py` (estendido)
```python
MEDIA_URL_RE                                  # png|jpe?g|webp|mp4|mov|webm|wav|mp3
history_media(kind="image"|"video"|"audio", size=50) -> [{id, prompt, model, created, urls[]}]
generate(model, params, timeout_s=600) -> {"raw", "urls" (todas as mídias), "id"}
download(url, dest: Path) -> Path
```

## `tests/conftest.py` (estendido)
```python
studio_env["svc"]("base")  -> studio.base.service (import após a fixture)
make_image(path), image_bytes(), make_video(path, seconds=2, size="320x240"), make_audio(path, seconds=3)
```
`make_video`/`make_audio` usam ffmpeg (lavfi); testes que dependem deles devem `pytest.skip` se `ffmpeg.available()` for False (o CI instala ffmpeg via apt).

## `tests/test_steps_and_config.py`
Passa a validar dinamicamente: toda etapa em `discover()` tem `META.n` igual ao catálogo e serve
`view.html`/`view.js`. Frentes **não** editam esse arquivo.
