"""Etapa 6 — Trilha (aula 013): assistir a história inteira e só então escolher a música.

A aula começa ANTES da trilha: "colocar todas as cenas em ordem na timeline, sem cortar nada…
o objetivo não é editar, é enxergar a história como um todo" e decidir se a história fecha ou se
falta uma cena (um encerramento mais forte ou mais comercial). Isso é o passo 0 desta etapa:
`audio/rough_sequence.mp4` (concat dos takes com like, na ordem do storyboard, sem música) e a
decisão gravada em `audio/story_check.json`.

Só depois vem a trilha — "não para editar ainda, mas para sentir a energia". O curso manda ouvir
várias músicas na biblioteca (YouTube Audio Library, Artlist, Epidemic; a aula não fixa número),
escolher "sentindo" e usar as batidas fortes como marcação de onde algo acontece. Aqui isso vira:
reunir candidatas (upload / Downloads / histórico do CLI / geração paga por `sonilo_music`
`[extensão]`) →
ouvir na UI → escolher UMA → detectar batidas e impactos em `audio/beats.json`, que a etapa 7
consome. A origem/licença da faixa é um campo opcional `[extensão]` — a aula não fala em licença.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .. import higgsfield as hf
from ..common import ffmpeg as ff
from ..common import ingest, settings
from ..common.jobs import JobRegistry
from ..refs.service import project_dir
from . import beats as beats_mod

log = logging.getLogger("studio.music")

STEP = "audio"                     # a pasta do projeto é `audio/` (PROJECT_LAYOUT), o id da etapa é `music`
KIND = "audio"
MODEL = "sonilo_music"             # `[extensão]`: gerar trilha por IA NÃO é passo do curso — a
                                   # aula 013 ensina SELECIONAR de bibliotecas (YouTube Audio Library,
                                   # Artlist, Epidemic). Gerar é acréscimo do Studio (ADR-004). Id do
                                   # plano Higgsfield, não confirmado no catálogo vivo (wave, decisão 13).
DEFAULT_DURATION = 35
DEFAULT_COUNT = 3
DOWNLOADS_DEFAULT = ingest.DOWNLOADS_DEFAULT
AUDIO_EXT = ingest.MEDIA_EXT[KIND]
AUDIO_URL_RE = re.compile(r"https?://[^\s\"']+\.(?:wav|mp3|m4a|ogg)(?:\?[^\s\"']*)?", re.I)
GENERATE_TIMEOUT = 600
INSTRUCTIONS = (
    "Baixe várias músicas na biblioteca (YouTube Audio Library, Artlist, Epidemic) e importe aqui — "
    "a aula não fixa número. Ouça cada uma inteira antes de decidir: a trilha é escolhida no sentimento, "
    "e é ela que dita o ritmo da montagem. Em cada batida forte tem que acontecer alguma coisa no vídeo. "
    "Você não deve editar antes de escolher a trilha."
)

# Passo 0 da aula 013 (assistir a história inteira, sem cortar nada).
STORY_VIDEO = "rough_sequence.mp4"          # em audio/ — a sequência bruta, sem música
STORY_CHECK = "story_check.json"            # {closed, note, decided}
STORY_TIMEOUT = 1800                        # concat de todos os takes em 1080p é lento
STORY_QUESTION = ("A história fecha? Assista a sequência inteira e diga se falta cena — em especial "
                  "um encerramento mais forte ou mais comercial, com o produto em evidência.")


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
def _track_bpm(path: Path) -> int | None:
    """bpm inteiro da faixa, ou None (arquivo curto, sem periodicidade ou análise que falhou)."""
    if not path.exists():
        return None
    try:
        bpm = beats_mod.estimate_bpm(beats_mod.onset_envelope(beats_mod.decode_pcm(path)))
    except Exception as e:  # noqa: BLE001  (uma candidata sem bpm não pode derrubar a listagem)
        log.warning("bpm failed file=%s reason=%s", path.name, e)
        return None
    return round(bpm) if bpm else None


def _annotate_bpm(root: Path) -> list[dict]:
    """Anota `bpm` em cada candidata que ainda não tem a chave e persiste (wave 4, regra 5).

    A tela mostra "0:34 · 128 bpm" em TODA faixa, não só na escolhida — é o mesmo cálculo do
    `beats.py` (ADR-009), ~40 ms por faixa, feito uma vez por candidata. Sem ffmpeg nada é
    gravado (a próxima leitura tenta de novo) e a resposta sai com `bpm: null`.
    """
    cands = ingest.load_candidates(root, STEP)
    pendentes = [c for c in cands if "bpm" not in c]
    if not pendentes:
        return cands
    if ff.available():
        for c in pendentes:
            c["bpm"] = _track_bpm(root / STEP / "candidates" / c["file"])
        ingest.save_candidates(root, STEP, cands)
        return cands
    for c in pendentes:
        c["bpm"] = None
    return cands


def list_candidates(pid: str) -> list[dict]:
    """Backfill preguiçoso do `bpm`: as candidatas antigas ganham a chave na primeira leitura."""
    return _annotate_bpm(project_dir(pid))


def import_upload(pid: str, files: list[tuple[str, bytes]]) -> dict:
    root = project_dir(pid)
    r = ingest.import_upload(root, STEP, files, kind=KIND)
    _annotate_bpm(root)
    log.info("import ok pid=%s source=upload added=%s", pid, r["added"])
    return r


def import_downloads(pid: str, folder: str | None = None, since_minutes: int = 120, limit: int = 40) -> dict:
    root = project_dir(pid)
    r = ingest.import_downloads(root, STEP, folder, since_minutes, limit, kind=KIND)
    _annotate_bpm(root)
    log.info("import ok pid=%s source=downloads added=%s", pid, r["added"])
    return r


def import_history(pid: str, size: int = 50) -> dict:
    root = project_dir(pid)
    r = ingest.import_history(root, STEP, KIND, size)
    _annotate_bpm(root)
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
    # `error` explícito: sem ele, um CLI que falhou vira um 200 com tudo nulo e o usuário não
    # sabe se a faixa é grátis ou se a estimativa não foi feita.
    return {"per_track": per, "total": total, "raw": c.get("raw"), "error": c.get("error")}


def _audio_urls(res: dict) -> list[str]:
    urls = [u for u in (res.get("urls") or []) if Path(u.split("?")[0]).suffix.lower() in AUDIO_EXT]
    if urls:
        return urls
    raw = json.dumps(res.get("raw"), ensure_ascii=False, default=str)
    return sorted(set(AUDIO_URL_RE.findall(raw)))


def _elapsed(started: float) -> str:
    """Tempo da faixa no log do job — a seção 7 do FDD pede tempo por faixa."""
    return f"{time.perf_counter() - started:.1f}s"


def start_generate(pid: str, prompt: str, duration: int = DEFAULT_DURATION, count: int = DEFAULT_COUNT) -> dict:
    """`[extensão]` Gera `count` faixas com `sonilo_music` e importa cada uma como candidata.

    Gerar trilha por IA é acréscimo do Studio (ADR-004): a aula 013 ensina selecionar de
    bibliotecas. O caminho fiel ao curso é importar (upload/Downloads/histórico); a geração é
    uma opção paga. Um job por projeto."""
    root = project_dir(pid)
    log.info("generate start pid=%s count=%s duration=%s", pid, count, duration)

    def run(job: dict):
        last_error = None
        for i in range(count):
            started = time.perf_counter()
            try:
                res = hf.generate(MODEL, {"prompt": prompt, "duration": duration}, timeout_s=GENERATE_TIMEOUT)
            except Exception as e:  # noqa: BLE001  (uma faixa que falha não derruba as outras)
                last_error = f"{type(e).__name__}: {e}"
                job["log"].append(f"faixa {i + 1}/{count}: geração falhou em {_elapsed(started)}: {e}")
                job["done"] = i + 1
                continue
            # `[extensão]` livro-caixa de créditos (ADR-016): custo por faixa gerada.
            settings.record_generation(action="music.track", model=MODEL, params={"duration": duration},
                                       count=1, pid=pid, step="music", job_id=res.get("id"))
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
            job["log"].append(f"faixa {i + 1}/{count}: {len(urls)} áudio(s) em {_elapsed(started)}")
            job["done"] = i + 1
        if job["added"]:
            _annotate_bpm(root)
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


def select(pid: str, cand_id: str, license: str = "") -> dict:
    """Escolhe UMA candidata: copia para audio/music.<ext>, detecta as batidas e, se o usuário
    tiver declarado a origem, grava `audio/license.txt`.

    A origem/licença é **opcional** `[extensão]`: nenhuma transcrição da aula 013 fala em licença
    (auditoria 7.4). Declarar continua sendo recomendado — é o que permite recuperar depois de onde
    veio a faixa —, mas não bloqueia a escolha da trilha.
    """
    declared = (license or "").strip()
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
    lic = root / STEP / "license.txt"
    if declared:
        lic.write_text(
            f"Arquivo: {STEP}/music{ext}\n"
            f"Candidata: {chosen['id']} ({chosen.get('name') or chosen['file']}, origem: {chosen.get('source', '?')})\n"
            f"Origem/licença declarada: {declared}\n"
            f"Declarado em: {datetime.now().isoformat(timespec='seconds')}\n")
    else:
        # Sem declaração, o arquivo da trilha anterior não pode sobrar dizendo outra origem.
        lic.unlink(missing_ok=True)
    log.info("select pid=%s id=%s ext=%s license_len=%s", pid, cand_id, ext, len(declared))

    # Invariante da seção 6 do FDD: `beats.json`, quando existe, é SEMPRE o da trilha atual.
    # Por isso o arquivo antigo cai antes da detecção, e não só no caminho sem ffmpeg — se a
    # análise falhar no meio, é melhor ficar sem batidas do que com as batidas da trilha anterior.
    _beats_file(root).unlink(missing_ok=True)
    beats, warning = None, None
    if not ff.available():
        warning = "ffmpeg indisponível: batidas não detectadas"
        log.info("beats skipped reason=ffmpeg_unavailable pid=%s", pid)
    else:
        try:
            beats = _write_beats(root, beats_mod.analyze(dst))
            log.info("beats pid=%s bpm=%s beats=%d impacts=%d ms=%s", pid, beats["bpm"],
                     len(beats["beats"]), len(beats["impacts"]), beats.get("analysis_ms"))
        except Exception as e:  # noqa: BLE001  (a escolha da trilha não pode cair junto com a análise)
            _beats_file(root).unlink(missing_ok=True)
            warning = f"não foi possível detectar as batidas: {e}"
            log.warning("beats failed pid=%s reason=%s", pid, e)
    return {"selected": chosen, "music": f"{STEP}/music{ext}", "beats": beats, "warning": warning,
            "license": declared}


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


# ---------- passo 0: assistir a história inteira (aula 013) ----------
_story_registry = JobRegistry()


def _story_video(root: Path) -> Path:
    return root / STEP / STORY_VIDEO


def _story_check_file(root: Path) -> Path:
    return root / STEP / STORY_CHECK


def read_story_check(pid: str) -> dict | None:
    """A decisão gravada: `{closed, note, decided}` — `None` enquanto o usuário não decidiu."""
    f = _story_check_file(project_dir(pid))
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        return None


def set_story_check(pid: str, closed: bool, note: str = "") -> dict:
    """Grava a resposta da aula: a história fecha, ou falta um encerramento mais forte/comercial?"""
    root = project_dir(pid)
    data = {"closed": bool(closed), "note": (note or "").strip(),
            "decided": datetime.now().isoformat(timespec="seconds")}
    _story_check_file(root).write_text(json.dumps(data, ensure_ascii=False, indent=1))
    log.info("story_check pid=%s closed=%s note_len=%s", pid, data["closed"], len(data["note"]))
    return data


def _product_scene(root: Path) -> dict | None:
    """A cena extra do produto vive na etapa 4 (ADR-011); aqui só se mostra se ela existe."""
    f = root / "storyboard" / "storyboard.json"
    if not f.exists():
        return None
    try:
        extra = (json.loads(f.read_text()) or {}).get("product_scene")
    except json.JSONDecodeError:
        return None
    return extra if isinstance(extra, dict) and extra.get("id") else None


def _story_timeline(pid: str) -> dict:
    """Sequência bruta: os takes com like na ordem do storyboard, sem música, sem corte nenhum.

    Reaproveita a etapa 7 (`edit.initial_timeline`) em modo leitura — nada é gravado em
    `edit/timeline.json`: a aula 013 é explícita em que aqui ainda não se edita.
    """
    from ..edit import service as edit_svc
    root = project_dir(pid)
    base = edit_svc.initial_timeline(pid)
    return edit_svc.validate_timeline(root, {**base, "blacks": [], "sfx": [],
                                             "music": {"file": None, "offset": 0.0}, "fade_out": 0.0})


def story_status(pid: str) -> dict:
    """Estado do passo 0 para a tela: vídeo, decisão, cena do produto e quantas cenas entram."""
    root = project_dir(pid)
    video = _story_video(root)
    out: dict = {"video": f"{STEP}/{STORY_VIDEO}" if video.exists() else None,
                 "check": read_story_check(pid), "question": STORY_QUESTION,
                 "product_scene": _product_scene(root) is not None,
                 "ffmpeg": ff.available(), "clips": 0, "duration": 0.0, "warning": None}
    try:
        timeline = _story_timeline(pid)
    except (FileNotFoundError, ValueError) as e:
        out["warning"] = str(e)
        return out
    from ..edit import service as edit_svc
    out["clips"] = len(timeline["clips"])
    out["duration"] = edit_svc.timeline_duration(timeline)
    return out


def start_story_render(pid: str) -> dict:
    """Renderiza `audio/rough_sequence.mp4` num job em thread (ADR-006): concat puro, sem música."""
    root = project_dir(pid)
    if not ff.available():
        raise RuntimeError("ffmpeg indisponível: não dá para montar a sequência bruta")
    from ..edit import render as edit_render
    timeline = _story_timeline(pid)
    final = _story_video(root)
    part = Path(f"{final}.part")
    args, duration = edit_render.build_filtergraph(root, timeline, "rough", out=final)
    n = len(timeline["clips"])

    def run(job: dict) -> None:
        job["log"].append(f"{n} cena(s) na ordem do storyboard, sem música — {duration:.2f}s previstos")
        job["done"] += 1
        try:
            ff.run(args, timeout=STORY_TIMEOUT)
            part.replace(final)
        except Exception:
            part.unlink(missing_ok=True)
            raise
        job["log"].append(f"ok {STEP}/{STORY_VIDEO} — assista inteiro antes de escolher a trilha")
        job["added"] = 1
        job["done"] += 1

    log.info("story render start pid=%s clips=%s duration=%.2f", pid, n, duration)
    return _story_registry.start(pid, 2, run, output=f"{STEP}/{STORY_VIDEO}", duration=duration)


def story_job(pid: str) -> dict:
    return _story_registry.status(pid)
