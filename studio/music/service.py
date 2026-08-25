"""Etapa 7 — Trilha (aula 013): a música vem ANTES da montagem.

O curso manda baixar de 3 a 5 candidatas na biblioteca (YouTube Audio Library, Artlist,
Epidemic), ouvir até "sentir" a certa e usar as batidas fortes como marcação de onde algo
acontece. Aqui isso vira: reunir candidatas (upload / Downloads / histórico do CLI / geração
paga por `sonilo_music`) → ouvir na UI → escolher UMA, declarando a origem/licença → detectar
batidas e impactos em `audio/beats.json`, que a etapa 8 consome.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from .. import higgsfield as hf
from ..common import ffmpeg as ff
from ..common import ingest
from ..common.jobs import JobRegistry
from ..refs.service import project_dir
from . import beats as beats_mod

log = logging.getLogger("studio.music")

STEP = "audio"                     # a pasta do projeto é `audio/` (PROJECT_LAYOUT), o id da etapa é `music`
KIND = "audio"
MODEL = "sonilo_music"             # id do plano Higgsfield; não confirmado no catálogo vivo (wave, decisão 13)
DEFAULT_DURATION = 35
DEFAULT_COUNT = 3
DOWNLOADS_DEFAULT = ingest.DOWNLOADS_DEFAULT
AUDIO_EXT = ingest.MEDIA_EXT[KIND]
AUDIO_URL_RE = re.compile(r"https?://[^\s\"']+\.(?:wav|mp3|m4a|ogg)(?:\?[^\s\"']*)?", re.I)
GENERATE_TIMEOUT = 600
INSTRUCTIONS = (
    "Baixe de 3 a 5 músicas na biblioteca (YouTube Audio Library, Artlist, Epidemic) e importe aqui. "
    "Ouça cada uma inteira antes de decidir: a trilha é escolhida no sentimento, e é ela que dita o ritmo "
    "da montagem. Em cada batida forte tem que acontecer alguma coisa no vídeo — por isso a trilha vem "
    "antes do corte, nunca depois."
)


# ---------- prompt derivado do mood ----------
def _mood_vibe(root: Path) -> str:
    """A vibe em palavras que o usuário escreveu ao salvar o mood board (etapa 2)."""
    md = root / "mood" / "mood.md"
    if not md.exists():
        return ""
    for line in md.read_text().splitlines():
        if line.lower().startswith("**vibe em palavras:**"):
            return line.split(":**", 1)[1].strip()
    return ""


def mood_prompt(pid: str) -> dict:
    """Prompt em inglês para `sonilo_music`, montado com a vibe do mood board + o produto do projeto."""
    root = project_dir(pid)
    meta = json.loads((root / "project.json").read_text()) if (root / "project.json").exists() else {}
    vibe = _mood_vibe(root) or (meta.get("vibe") or "")
    core = " ".join(x for x in (vibe.strip(), (meta.get("product") or "").strip()) if x)
    prompt = f"{core}, cinematic, strong beats, no vocals" if core else "cinematic, strong beats, no vocals"
    return {"prompt": prompt, "duration": DEFAULT_DURATION, "model": MODEL, "instructions": INSTRUCTIONS}


# ---------- candidatas (importação delegada a studio/common/ingest.py) ----------
def list_candidates(pid: str) -> list[dict]:
    return ingest.load_candidates(project_dir(pid), STEP)


def import_upload(pid: str, files: list[tuple[str, bytes]]) -> dict:
    r = ingest.import_upload(project_dir(pid), STEP, files, kind=KIND)
    log.info("import ok pid=%s source=upload added=%s", pid, r["added"])
    return r


def import_downloads(pid: str, folder: str | None = None, since_minutes: int = 120, limit: int = 40) -> dict:
    r = ingest.import_downloads(project_dir(pid), STEP, folder, since_minutes, limit, kind=KIND)
    log.info("import ok pid=%s source=downloads added=%s", pid, r["added"])
    return r


def import_history(pid: str, size: int = 50) -> dict:
    r = ingest.import_history(project_dir(pid), STEP, KIND, size)
    log.info("import ok pid=%s source=higgsfield added=%s", pid, r["added"])
    return r


# ---------- geração via CLI (paga créditos) ----------
_registry = JobRegistry()


def generate_cost(pid: str, prompt: str, duration: int = DEFAULT_DURATION, count: int = DEFAULT_COUNT) -> dict:
    """Estimativa de créditos SEM gerar (a aula insiste em conferir o custo antes)."""
    project_dir(pid)
    c = hf.cost(MODEL, {"prompt": prompt, "duration": duration})
    per = c.get("credits")
    total = per * count if isinstance(per, (int, float)) else None
    return {"per_track": per, "total": total, "raw": c.get("raw") or c.get("error")}


def _audio_urls(res: dict) -> list[str]:
    urls = [u for u in (res.get("urls") or []) if Path(u.split("?")[0]).suffix.lower() in AUDIO_EXT]
    if urls:
        return urls
    raw = json.dumps(res.get("raw"), ensure_ascii=False, default=str)
    return sorted(set(AUDIO_URL_RE.findall(raw)))


def start_generate(pid: str, prompt: str, duration: int = DEFAULT_DURATION, count: int = DEFAULT_COUNT) -> dict:
    """Gera `count` faixas com `sonilo_music` e importa cada uma como candidata. Um job por projeto."""
    root = project_dir(pid)
    log.info("generate start pid=%s count=%s duration=%s", pid, count, duration)

    def run(job: dict):
        last_error = None
        for i in range(count):
            try:
                res = hf.generate(MODEL, {"prompt": prompt, "duration": duration}, timeout_s=GENERATE_TIMEOUT)
            except Exception as e:  # noqa: BLE001  (uma faixa que falha não derruba as outras)
                last_error = f"{type(e).__name__}: {e}"
                job["log"].append(f"faixa {i + 1}/{count}: geração falhou: {e}")
                job["done"] = i + 1
                continue
            urls = _audio_urls(res)
            log.info("generate track %s/%s job_id=%s urls=%s", i + 1, count, res.get("id"), len(urls))
            if not urls:
                job["log"].append(f"faixa {i + 1}/{count}: nenhuma URL de áudio no resultado do CLI")
            for url in urls:
                try:
                    with tempfile.TemporaryDirectory() as td:
                        name = url.split("?")[0].rsplit("/", 1)[-1] or "track.wav"
                        data = hf.download(url, Path(td) / name).read_bytes()
                    if ingest.ingest_bytes(root, STEP, data, "cli", name, prompt,
                                           {"job_id": res.get("id"), "model": MODEL}, kind=KIND):
                        job["added"] += 1
                except Exception as e:  # noqa: BLE001
                    job["log"].append(f"faixa {i + 1}/{count}: download falhou: {e}")
            (root / "jobs").mkdir(parents=True, exist_ok=True)
            (root / "jobs" / f"music_{res.get('id') or i}.json").write_text(
                json.dumps(res.get("raw"), ensure_ascii=False, indent=1, default=str))
            job["done"] = i + 1
        if job["added"] == 0 and last_error:
            raise RuntimeError(last_error)

    try:
        return _registry.start(pid, count, run)
    except RuntimeError as e:
        raise RuntimeError("Já existe uma geração de trilha em andamento para este projeto.") from e


def job_status(pid: str) -> dict:
    return _registry.status(pid)


# ---------- escolha, licença e batidas ----------
def _music_path(root: Path) -> Path | None:
    found = sorted(p for p in (root / STEP).glob("music.*") if p.suffix.lower() in AUDIO_EXT)
    return found[0] if found else None


def _beats_file(root: Path) -> Path:
    return root / STEP / "beats.json"


def _write_beats(root: Path, data: dict) -> dict:
    _beats_file(root).write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return data


def select(pid: str, cand_id: str, license: str) -> dict:
    """Escolhe UMA candidata: copia para audio/music.<ext>, grava a licença declarada e detecta as batidas."""
    declared = (license or "").strip()
    if not declared:
        raise ValueError("Declare a origem/licença da trilha (a aula 013 exige saber de onde veio a música).")
    root = project_dir(pid)
    cands = ingest.load_candidates(root, STEP)
    chosen = next((c for c in cands if c["id"] == cand_id), None)
    if chosen is None:
        raise FileNotFoundError(f"candidata não encontrada: {cand_id}")
    src = root / STEP / "candidates" / chosen["file"]
    if not src.exists():
        raise FileNotFoundError(f"arquivo da candidata não encontrado: {chosen['file']}")

    for c in cands:
        c["selected"] = c["id"] == cand_id
    ingest.save_candidates(root, STEP, cands)

    ext = Path(chosen["file"]).suffix.lower()
    for old in (root / STEP).glob("music.*"):
        old.unlink()
    dst = root / STEP / f"music{ext}"
    shutil.copy2(src, dst)
    (root / STEP / "license.txt").write_text(
        f"Arquivo: {STEP}/music{ext}\n"
        f"Candidata: {chosen['id']} ({chosen.get('name') or chosen['file']}, origem: {chosen.get('source', '?')})\n"
        f"Origem/licença declarada: {declared}\n"
        f"Declarado em: {datetime.now().isoformat(timespec='seconds')}\n")
    log.info("select pid=%s id=%s ext=%s license_len=%s", pid, cand_id, ext, len(declared))

    beats, warning = None, None
    if ff.available():
        beats = _write_beats(root, beats_mod.analyze(dst))
    else:
        _beats_file(root).unlink(missing_ok=True)   # beats.json nunca pode sobrar de outra trilha
        warning = "ffmpeg indisponível: batidas não detectadas"
        log.info("beats skipped reason=ffmpeg_unavailable pid=%s", pid)
    return {"selected": chosen, "music": f"{STEP}/music{ext}", "beats": beats, "warning": warning}


def recompute_beats(pid: str, k: float = beats_mod.K) -> dict:
    """Redetecta as batidas da trilha escolhida (mesmo contrato de `beats.json`)."""
    root = project_dir(pid)
    music = _music_path(root)
    if music is None:
        raise FileNotFoundError("nenhuma trilha escolhida ainda")
    if not ff.available():
        raise RuntimeError("ffmpeg indisponível: não dá para detectar as batidas")
    return _write_beats(root, beats_mod.analyze(music, k=k))


def read_beats(pid: str) -> dict:
    f = _beats_file(project_dir(pid))
    if not f.exists():
        raise FileNotFoundError("beats.json ainda não existe (escolha uma trilha primeiro)")
    return json.loads(f.read_text())
