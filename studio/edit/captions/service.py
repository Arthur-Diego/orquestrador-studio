"""Geração de legendas e biblioteca de narração da etapa 7. `[extensão]`

Três caminhos chegam aqui, e o que os separa é de onde vem o TEMPO:

- `script` — o usuário colou o roteiro e não há áudio: os tempos são estimados por
  `proportional` a 2,4 palavras por segundo. Resposta `source:"estimate"`;
- `audio` sem `text` — o áudio É o roteiro: o provedor devolve texto e tempos. Se ele falhar,
  a requisição falha (502): inventar uma legenda estimada aqui seria pôr na tela um texto que
  ninguém escreveu;
- `audio` com `text` — o texto é nosso, o tempo é ouvido: `align` casa um com o outro. Se o
  provedor falhar, cai no `proportional` e responde 200 com `warning` — a legenda continua
  certa, só dessincronizada.

Essa assimetria é o coração do módulo e vem do porte do repo irmão ContentFlow. O servidor
**não persiste** nada do `generate`: os itens voltam na resposta e quem salva é o
`PUT /timeline` que já existe (ADR-003).

A biblioteca de narração (`edit/narration/`) segue o padrão de `common/ingest`: nome pelo sha1
do conteúdo (dedupe de graça), `ffprobe` para a duração e um catálogo ao lado. Ela é separada
de `edit/candidates/` porque narração não é SFX nem mídia do palco — é a fonte da legenda.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import datetime
from pathlib import Path

from studio.common import ffmpeg as ff
from studio.common.ingest import MEDIA_EXT
from studio.edit import editor
from studio.edit.captions import DEFAULT_HI, WPS
from studio.edit.captions.audio import WHISPER_MAX_BYTES, duration_of, extracted
from studio.edit.captions.layout import LayoutOpts, build_items
from studio.edit.captions.transcribe import (
    MAX_ERROR_CHARS,
    FakeTranscribe,
    ProviderError,
    get_transcribe,
    proportional,
)

log = logging.getLogger("studio.edit.captions")

#: Onde as narrações do usuário ficam, relativo à raiz do projeto.
NARRATION_DIR = "edit/narration"

#: Teto do roteiro colado. Acima disso não é roteiro de vídeo curto — é engano ou colagem torta.
MAX_SCRIPT_CHARS = 20_000

#: Catálogo da biblioteca de narração (o `candidates.json` desta pasta).
_INDEX = "index.json"

#: Extensões aceitas no upload de narração: áudio e vídeo (o vídeo entra pela trilha).
NARRATION_EXT = MEDIA_EXT["audio"] | MEDIA_EXT["video"]

#: Aviso devolvido quando o tempo saiu de estimativa, e não do áudio.
FALLBACK_WARNING = "transcrição indisponível: tempos estimados"

__all__ = [
    "MAX_SCRIPT_CHARS",
    "NARRATION_DIR",
    "generate",
    "import_narration",
    "list_narration",
]


# ---------- geração ----------
def generate(root: Path, req: dict) -> dict:
    """Itens de legenda prontos para a faixa `t_cap`, a partir de roteiro ou de áudio.

    Devolve `{source, word_count, total_s, items}` — e `warning` só quando o tempo é estimado
    apesar de haver áudio. Nada é gravado no projeto.
    """
    began = time.perf_counter()
    source = str(req.get("source") or "")
    words, duration, provider, warning, rel = (
        _from_audio(root, req) if source == "audio" else _from_script(req))
    if duration <= 0:
        raise ValueError("duration: deve ser maior que zero")
    real = provider is not None and not isinstance(provider, FakeTranscribe)
    result = "whisper" if (real and not warning) else "estimate"
    items = build_items(words, _opts(req))
    log.info(
        "captions.generate pid=%s source=%s provider=%s result=%s word_count=%d items=%d "
        "total_s=%s file=%s elapsed_ms=%d",
        root.name, source or "script", "-" if provider is None else ("openai" if real else "fake"),
        result, len(words), len(items), round(duration, 3), rel or "-",
        int((time.perf_counter() - began) * 1000),
    )
    out = {"source": result, "word_count": len(words), "total_s": round(duration, 3), "items": items}
    if warning:
        out["warning"] = warning
    return out


def _from_script(req: dict) -> tuple[list, float, None, str, str]:
    """Roteiro colado: sem áudio, o tempo é sempre estimativa determinística."""
    text = str(req.get("text") or "")
    if not text.split():
        raise ValueError("text: obrigatório em script")
    if len(text) > MAX_SCRIPT_CHARS:
        raise ValueError(f"text: acima de {MAX_SCRIPT_CHARS} caracteres")
    duration = float(req.get("duration") or 0) or len(text.split()) / WPS
    return proportional(text, duration), duration, None, "", ""


def _from_audio(root: Path, req: dict) -> tuple[list, float, object, str, str]:
    """Áudio do projeto: extrai o wav, chama o provedor e devolve as palavras com tempo real."""
    rel = _audio_rel(root, req)
    path = root / rel
    if not path.exists():
        raise FileNotFoundError(f"file: arquivo não encontrado: {rel}")
    file_duration = duration_of(path)
    asked = req.get("duration")
    if asked is not None and float(asked) <= 0:
        raise ValueError("duration: deve ser maior que zero")
    duration = float(asked) if asked else file_duration
    text = str(req.get("text") or "").strip()
    if len(text) > MAX_SCRIPT_CHARS:
        raise ValueError(f"text: acima de {MAX_SCRIPT_CHARS} caracteres")
    provider = get_transcribe()
    with _wav(path, duration) as wav:
        if text:
            words = provider.words(wav, text, duration)
            warning = _warning_if_estimated(root, words, text, duration, provider)
            return words, duration, provider, warning, rel
        _, words = _transcribe(root, provider, wav, duration)
    if not words:
        raise ValueError("file: nenhuma palavra reconhecida no áudio")
    return words, duration, provider, "", rel


def _audio_rel(root: Path, req: dict) -> str:
    """Caminho do arquivo dentro do projeto, barrado contra `../`.

    O label do `safe_rel` é o do domínio (`captions.file`), mas o erro que sai daqui começa por
    `file:` porque o contrato congelado manda o `detail` de todo 422 começar pelo nome do campo
    do pedido — é por ele que o front destaca o campo errado no modal.
    """
    raw = str(req.get("file") or "").strip()
    if not raw:
        raise ValueError("file: obrigatório em audio")
    try:
        return editor.safe_rel(root, raw, "captions.file")
    except editor.EditorError as exc:
        raise ValueError(f"file: caminho fora do projeto: {raw}") from exc


@contextmanager
def _wav(path: Path, duration: float) -> Iterator[Path]:
    """`extracted` com os erros do ffmpeg LOCAL traduzidos para 422, e o teto do whisper aferido.

    Só a extração é traduzida: erro do binário local é problema de entrada/ambiente. O 502 fica
    reservado ao provedor — e `ProviderError` também é `RuntimeError`, então envolver o corpo
    inteiro transformaria a falha do whisper num 422 mentiroso.
    """
    with ExitStack() as stack:
        try:
            wav = stack.enter_context(extracted(path, duration))
        except RuntimeError as exc:
            raise ValueError(f"file: não foi possível extrair o áudio: {str(exc)[:MAX_ERROR_CHARS]}") from exc
        if wav.stat().st_size > WHISPER_MAX_BYTES:
            raise ValueError("file: áudio acima do limite do whisper (25 MB): informe `duration` menor")
        yield wav


def _transcribe(root: Path, provider, wav: Path, duration: float) -> tuple[str, list]:
    """Sem texto nosso, falha do provedor é 502 — nunca uma legenda estimada em silêncio."""
    try:
        return provider.transcribe_text(wav, duration)
    except ProviderError as exc:
        log.error("captions.provider pid=%s error=%s", root.name, str(exc)[:MAX_ERROR_CHARS])
        raise


def _warning_if_estimated(root: Path, words: list, text: str, duration: float, provider) -> str:
    """O provedor real caiu no proporcional? Então o tempo não veio do áudio, e o usuário precisa saber.

    `words()` engole a falha por dentro (legenda é enfeite: não derruba a geração), então o que
    resta para descobrir se o tempo é ouvido ou estimado é comparar com a própria estimativa —
    que é determinística. O fake não gera aviso: ali a estimativa é o contrato, não uma queda.
    """
    if isinstance(provider, FakeTranscribe) or words != proportional(text, duration):
        return ""
    log.warning("captions.fallback pid=%s reason=%s", root.name, "provedor indisponível")
    return FALLBACK_WARNING


def _opts(req: dict) -> LayoutOpts:
    return LayoutOpts(
        style=dict(req.get("style") or {}),
        chunk=int(req.get("chunk") or 0),
        hi=str(req.get("hi") or DEFAULT_HI).upper(),   # forma canônica: é como o `PUT /timeline` guarda
        mode=str(req.get("mode") or "karaoke"),
        position=str(req.get("position") or "bottom"),
        start=float(req.get("start") or 0.0),
    )


# ---------- biblioteca de narração ----------
def _index_file(root: Path) -> Path:
    return root / NARRATION_DIR / _INDEX


def _load_index(root: Path) -> list[dict]:
    f = _index_file(root)
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text())
    except (OSError, ValueError):        # catálogo corrompido não pode derrubar a etapa
        return []
    return data if isinstance(data, list) else []


def import_narration(root: Path, files: list[tuple[str, bytes]]) -> dict:
    """Grava as narrações em `edit/narration/`, com dedupe por conteúdo e duração pelo probe.

    O nome no disco é o sha1 do conteúdo: reenviar o mesmo arquivo (com outro nome, inclusive)
    não duplica nada. Arquivo que o `ffprobe` acusa sem trilha de áudio é APAGADO e não conta
    em `added` — narração muda não legenda coisa alguma, e deixá-la na lista só faria o usuário
    escolhê-la para tomar 422 depois.
    """
    for name, _ in files:
        if Path(name or "").suffix.lower() not in NARRATION_EXT:
            raise ValueError(f"files: {name}: extensão fora de {sorted(NARRATION_EXT)}")
    index = _load_index(root)
    # o dedupe é por CONTEÚDO, como em `ingest_bytes`: o id é o sha, não o caminho — o mesmo
    # áudio reenviado com outro nome (ou outra extensão) não entra duas vezes na biblioteca
    known = {Path(e.get("file") or "").stem for e in index}
    added: list[dict] = []
    skipped = 0
    for name, data in files:
        cid = hashlib.sha1(data).hexdigest()[:12]
        if cid in known:
            skipped += 1
            continue
        entry = _store(root, f"{NARRATION_DIR}/{cid}{Path(name).suffix.lower()}", name, data)
        if entry is None:
            skipped += 1
            continue
        known.add(cid)
        index.append(entry)
        added.append(entry)
    if added:
        _index_file(root).write_text(json.dumps(index, ensure_ascii=False, indent=1))
    log.info("captions.narration pid=%s added=%d skipped=%d", root.name, len(added), skipped)
    return {"added": len(added), "files": [{"file": e["file"], "duration": e["duration"]} for e in added]}


def _store(root: Path, rel: str, name: str, data: bytes) -> dict | None:
    """Grava um arquivo e devolve a entrada do catálogo, ou `None` se ele não serve."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    try:
        info = ff.probe(path)
        if not info.get("has_audio"):
            raise ValueError("arquivo sem trilha de áudio")
        duration = round(float(info.get("duration") or 0.0), 3)
    except Exception:
        path.unlink(missing_ok=True)
        return None
    return {"file": rel, "name": name, "duration": duration,
            "imported": datetime.now().isoformat(timespec="seconds")}


def list_narration(root: Path) -> list[dict]:
    """A biblioteca de narração do projeto. Lista vazia quando ainda não há upload."""
    return [{"file": e.get("file", ""), "name": e.get("name", ""), "duration": e.get("duration", 0.0)}
            for e in _load_index(root)]
