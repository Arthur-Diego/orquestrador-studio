"""Etapa 6 — Animação (aula 012), em "modo UI" com geração paga opcional pelo CLI:

1. lê `shots/storyboard.json` (etapa 5) e monta o plano de takes, mesclando com o que já existe;
2. sugere o prompt de movimento do take (simples, elaborado ou start/end frame) — o usuário edita;
3. o usuário gera na interface da Higgsfield (áudio OFF, 2 takes) e importa o mp4 (upload,
   pasta Downloads ou histórico do CLI) — ou gera via CLI, pagando créditos;
4. atribui o candidato ao shot como take K, dá "like" no usável e o Studio grava `_final.mp4`;
5. após 3 falhas no shot, o serviço SUGERE o próximo modelo da ordem (nunca troca sozinho:
   gasta créditos); esgotada a ordem, sugere `fallback_black` (corte para preto na montagem).

Saída para a etapa 8 (montagem): `animate/takes.json` + `videos/cenaNN/shotMM_takeK.mp4`.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path

from .. import higgsfield as hf
from ..common import ingest
from ..common.jobs import JobRegistry
from ..refs.service import project_dir

log = logging.getLogger("studio.animate")

STEP = "animate"
MODEL_ORDER = ["kling3_0", "seedance_2_0", "veo3_1_lite"]   # ordem de troca da aula 012 (Kling → Seedance)
FAIL_THRESHOLD = 3          # a aula fala em "3 a 4 falhas"; 3 é o conservador em créditos
DURATIONS = (5, 10)         # 5 s padrão, 10 s para mudanças lentas (aula 012)
DEFAULT_TAKES = 2           # "gere 2 e escolha o usável"
GENERATE_TIMEOUT_S = 900    # vídeo em série é lento; acima dos 600 s padrão do CLI
MODES = ("simple", "elaborate", "start_end")
VIDEO_EXT = ingest.MEDIA_EXT["video"]
DOWNLOADS_DEFAULT = ingest.DOWNLOADS_DEFAULT

_UNSET = object()           # distingue "não informado" de "limpar" em update_shot(start_end=None)
_registry = JobRegistry()


def model_order() -> list[str]:
    """Ordem viva de modelos (ADR-002: ids não ficam presos no código). Override: STUDIO_ANIMATE_MODELS."""
    models = [m.strip() for m in os.environ.get("STUDIO_ANIMATE_MODELS", "").split(",") if m.strip()]
    return models or list(MODEL_ORDER)


# ---------- storyboard (etapa 5) ----------
def _storyboard_file(root: Path) -> Path:
    return root / "shots" / "storyboard.json"


def _read_storyboard(root: Path) -> tuple[list[dict], list[str]]:
    """Lê o storyboard de forma defensiva: [{scene, shot, order, image, scene_prompt}] + avisos."""
    f = _storyboard_file(root)
    if not f.exists():
        return [], []
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        return [], [f"shots/storyboard.json inválido: {e}"]
    if not isinstance(data, dict):
        return [], ["shots/storyboard.json não é um objeto JSON"]
    scenes = [s for s in (data.get("scenes") or []) if isinstance(s, dict)]
    product = data.get("product_scene")
    if isinstance(product, dict) and (product.get("shots") or []):
        scenes.append(product)   # aula 013: a cena do produto é a última cena do plano
    entries: list[dict] = []
    warnings: list[str] = []
    for si, scene in enumerate(scenes, start=1):
        sid = scene.get("id") or f"cena{si:02d}"
        raw = [s for s in (scene.get("shots") or []) if isinstance(s, dict)]
        ordered = sorted(enumerate(raw, start=1),
                         key=lambda kv: (kv[1]["order"] if isinstance(kv[1].get("order"), int) else kv[0], kv[0]))
        for pos, (idx, sh) in enumerate(ordered, start=1):
            shot_id = sh.get("id") or f"shot{idx:02d}"
            image = sh.get("file")
            if not image or not (root / image).exists():
                warnings.append(f"{sid}/{shot_id}: frame ausente ({image or 'shot sem file'})")
                image = None
            entries.append({"scene": sid, "shot": shot_id, "order": sh.get("order") or pos,
                            "image": image, "scene_prompt": sh.get("prompt") or ""})
    return entries, warnings


# ---------- takes.json ----------
def _takes_file(root: Path) -> Path:
    return root / STEP / "takes.json"


def _load_data(root: Path) -> dict:
    f = _takes_file(root)
    if not f.exists():
        return {"shots": []}
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError:
        return {"shots": []}
    if not isinstance(data, dict) or not isinstance(data.get("shots"), list):
        return {"shots": []}
    data["shots"] = [s for s in data["shots"] if isinstance(s, dict) and s.get("scene") and s.get("shot")]
    return data


def _save_data(root: Path, data: dict) -> None:
    """Gravação atômica: nenhum leitor (etapa 8) vê `takes.json` pela metade."""
    d = root / STEP
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / ".takes.json.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    os.replace(tmp, _takes_file(root))


def _blank(scene: str, shot: str, order: int = 999, image: str | None = None, scene_prompt: str = "") -> dict:
    return {"scene": scene, "shot": shot, "order": order, "image": image, "scene_prompt": scene_prompt,
            "prompt": "", "mode": "simple", "duration": DURATIONS[0], "start_end": None,
            "fallback_black": False, "cli_failures": 0, "orphan": False, "takes": []}


def _merge(root: Path) -> tuple[dict, list[str]]:
    """Plano = storyboard (ordem e frames) mesclado com o que já está em takes.json.
    Nunca perde takes: shot que saiu do storyboard permanece com `orphan: true`."""
    entries, warnings = _read_storyboard(root)
    data = _load_data(root)
    stored = {(s["scene"], s["shot"]): s for s in data["shots"]}
    merged: list[dict] = []
    for e in entries:
        cur = stored.pop((e["scene"], e["shot"]), None)
        base = _blank(e["scene"], e["shot"], e["order"], e["image"], e["scene_prompt"])
        if cur is None:
            merged.append(base)
        else:
            merged.append({**base, **cur, "order": e["order"], "image": e["image"],
                           "scene_prompt": e["scene_prompt"], "orphan": False})
    for (scene, shot), cur in stored.items():
        merged.append({**_blank(scene, shot), **cur, "image": None, "orphan": True})
    data["shots"] = merged
    return data, warnings


def _find(data: dict, scene: str, shot: str) -> dict:
    for s in data["shots"]:
        if s["scene"] == scene and s["shot"] == shot:
            return s
    raise FileNotFoundError(f"shot não encontrado no plano: {scene}/{shot}")


def _next_in_scene(data: dict, scene: str, shot: str) -> str | None:
    seq = [s for s in data["shots"] if s["scene"] == scene and not s.get("orphan")]
    for i, s in enumerate(seq):
        if s["shot"] == shot:
            return seq[i + 1]["shot"] if i + 1 < len(seq) else None
    return None


# ---------- estado derivado ----------
def failures_of(shot: dict) -> int:
    """Falhas do shot: takes rejeitados pelo usuário + erros do CLI (aula 012: contar para trocar de modelo)."""
    return int(shot.get("cli_failures") or 0) + sum(1 for t in shot.get("takes", []) if t.get("liked") is False)


def suggested_model(failures: int) -> str | None:
    """A cada FAIL_THRESHOLD falhas, sugere o próximo modelo. Esgotada a ordem: None (corte para preto)."""
    order = model_order()
    idx = failures // FAIL_THRESHOLD
    return order[idx] if idx < len(order) else None


def _is_ready(shot: dict) -> bool:
    return bool(shot.get("fallback_black")) or any(t.get("liked") is True for t in shot.get("takes", []))


def _public(data: dict, shot: dict) -> dict:
    fails = failures_of(shot)
    model = suggested_model(fails)
    return {**{k: shot.get(k) for k in ("scene", "shot", "order", "image", "scene_prompt", "prompt", "mode",
                                        "duration", "start_end", "fallback_black", "orphan")},
            "next_in_scene": _next_in_scene(data, shot["scene"], shot["shot"]),
            "failures": fails, "suggested_model": model, "suggest_fallback_black": model is None,
            "ready": _is_ready(shot), "takes": shot.get("takes", [])}


# ---------- plano ----------
def load_plan(pid: str) -> dict:
    """Plano de takes na ordem do storyboard. Cria/atualiza `animate/takes.json`."""
    root = project_dir(pid)
    if not _storyboard_file(root).exists():
        raise FileNotFoundError("Etapa 5 ainda não produziu shots/storyboard.json")
    data, warnings = _merge(root)
    _save_data(root, data)
    shots = [_public(data, s) for s in data["shots"]]
    return {"shots": shots, "ready": sum(1 for s in shots if s["ready"]), "total": len(shots),
            "model_order": model_order(), "warnings": warnings}


def update_shot(pid: str, scene: str, shot: str, *, prompt: str | None = None, mode: str | None = None,
                duration: int | None = None, start_end=_UNSET, fallback_black: bool | None = None) -> dict:
    root = project_dir(pid)
    data, _ = _merge(root)
    entry = _find(data, scene, shot)
    if prompt is not None:
        entry["prompt"] = prompt.strip()
    if mode is not None:
        if mode not in MODES:
            raise ValueError(f"modo inválido: {mode} (use {', '.join(MODES)})")
        entry["mode"] = mode
    if duration is not None:
        if duration not in DURATIONS:
            raise ValueError(f"duração inválida: {duration} (a aula 012 usa {DURATIONS[0]} s ou {DURATIONS[1]} s)")
        entry["duration"] = duration
    if start_end is not _UNSET:
        entry["start_end"] = _validate_start_end(root, entry, start_end)
    if fallback_black is not None:
        entry["fallback_black"] = bool(fallback_black)
    _save_data(root, data)
    return _public(data, entry)


def _validate_start_end(root: Path, entry: dict, value) -> dict | None:
    if value in (None, {}):
        return None
    if not isinstance(value, dict):
        raise ValueError("start_end precisa ser um objeto {start, end}")
    end = (value.get("end") or "").strip()
    start = (value.get("start") or entry.get("image") or "").strip()
    if not end:
        raise ValueError("start_end exige o frame final (end)")
    if not (root / end).exists():
        raise ValueError(f"end frame inexistente: {end}")
    if not start:
        raise ValueError("start_end exige o frame inicial (start)")
    return {"start": start, "end": end}


# ---------- sugestão de prompt (aula 012) ----------
_UI_HINT = ("Na Higgsfield: Image to Video, Kling 3.0 (ou 2.6), start frame = este shot, "
            "áudio do modelo OFF, gerar 2, like no usável, download.")
_UI_HINT_SE = ("Na Higgsfield: Image to Video com start frame = este shot e end frame = o próximo, "
               "áudio do modelo OFF, gerar 2, like no usável, download.")
_EXAMPLE_PT = {
    "simple": "Quero que ele esteja caminhando para frente em meio à nevasca. "
              "Ele está com muita dificuldade de se locomover.",
    "elaborate": "Dolly dramático focando no reflexo de seu capacete.",
    "start_end": "Esta é uma cena start frame e end frame. O clima rapidamente se modifica. "
                 "A movimentação de câmera deve ser lenta e dramática.",
}


def suggest_prompt(pid: str, scene: str, shot: str, mode: str = "simple", camera: str = "",
                   action: str = "", slow: bool = False) -> dict:
    """Texto do prompt de movimento pelo template da aula (em inglês). Determinístico."""
    if mode not in MODES:
        raise ValueError(f"modo inválido: {mode} (use {', '.join(MODES)})")
    root = project_dir(pid)
    data, _ = _merge(root)
    entry = _find(data, scene, shot)
    scene_prompt = (entry.get("scene_prompt") or "").strip().rstrip(".")
    act = (action or "").strip().rstrip(".") or scene_prompt
    cam = (camera or "").strip().rstrip(".")
    if mode == "simple":
        text = f"{act or 'The scene comes to life'}, realistic, natural motion"
    elif mode == "elaborate":
        text = (f"{cam or 'Slow dramatic'} camera movement, "
                f"{act or 'the scene comes to life'}. Realistic, cinematic")
    else:
        nxt = _next_in_scene(data, scene, shot)
        if not nxt and not (entry.get("start_end") or {}).get("end"):
            raise ValueError("modo start/end exige um próximo shot na mesma cena ou um end frame informado "
                             "(ex.: edit/last_frames/<shot>_last.png)")
        text = (f"This is a start frame and end frame scene. {act or 'The scene changes between the two frames'}. "
                "The camera movement must be slow and dramatic.")
    return {"prompt": text, "mode": mode, "duration": DURATIONS[1] if slow else DURATIONS[0],
            "ui_hint": _UI_HINT_SE if mode == "start_end" else _UI_HINT, "example_pt": _EXAMPLE_PT[mode]}


# ---------- importação (delegada a studio/common/ingest.py) ----------
def list_candidates(pid: str) -> list[dict]:
    return ingest.load_candidates(project_dir(pid), STEP)


def import_upload(pid: str, files: list[tuple[str, bytes]], prompt: str = "") -> dict:
    return ingest.import_upload(project_dir(pid), STEP, files, prompt, kind="video")


def import_downloads(pid: str, folder: str | None = None, since_minutes: int = 120, limit: int = 40) -> dict:
    return ingest.import_downloads(project_dir(pid), STEP, folder, since_minutes, limit, kind="video")


def import_history(pid: str, size: int = 50, prompt_filter: str | None = None) -> dict:
    return ingest.import_history(project_dir(pid), STEP, "video", size, prompt_filter)


# ---------- takes ----------
def _take_number(take_id: str) -> int:
    digits = "".join(c for c in take_id if c.isdigit())
    return int(digits) if digits else 0


def _video_rel(scene: str, shot: str, suffix: str, ext: str = ".mp4") -> str:
    return f"videos/{scene}/{shot}_{suffix}{ext}"


def attach_take(pid: str, scene: str, shot: str, candidate_id: str, model: str | None = None,
                prompt: str | None = None) -> dict:
    """Copia o candidato para `videos/cenaNN/shotMM_takeK.mp4` e registra o take (liked: null)."""
    root = project_dir(pid)
    data, _ = _merge(root)
    entry = _find(data, scene, shot)
    cands = ingest.load_candidates(root, STEP)
    cand = next((c for c in cands if c["id"] == candidate_id), None)
    if cand is None:
        raise FileNotFoundError(f"candidato não encontrado: {candidate_id}")
    if any(t.get("candidate_id") == candidate_id for t in entry["takes"]):
        raise RuntimeError("Este vídeo já é um take deste shot.")
    order = model_order()
    model = model or suggested_model(failures_of(entry)) or order[0]
    if model not in order:
        raise ValueError(f"modelo fora da ordem configurada: {model} ({', '.join(order)})")
    src = root / STEP / "candidates" / cand["file"]
    if not src.exists():
        raise FileNotFoundError(f"arquivo do candidato ausente: {cand['file']}")
    # A convenção da wave é .mp4; se o usuário importou .mov/.webm, manter o container real
    ext = Path(cand["file"]).suffix.lower()
    ext = ext if ext in VIDEO_EXT else ".mp4"
    k = max((_take_number(t["id"]) for t in entry["takes"]), default=0) + 1
    rel = _video_rel(scene, shot, f"take{k}", ext)
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    take = {"id": f"take{k}", "file": rel, "liked": None, "model": model,
            "prompt": (prompt if prompt is not None else entry.get("prompt")) or "",
            "duration": entry.get("duration") or DURATIONS[0], "start_end": entry.get("start_end"),
            "source": cand.get("source"), "thumb": cand.get("thumb"), "candidate_id": candidate_id}
    entry["takes"].append(take)
    _save_data(root, data)
    for c in cands:
        if c["id"] == candidate_id:
            c["selected"] = True
    ingest.save_candidates(root, STEP, cands)
    log.info("animate: take %s de %s/%s a partir do candidato %s", take["id"], scene, shot, candidate_id)
    return {"take": take, "shot": _public(data, entry)}


def set_like(pid: str, scene: str, shot: str, take_id: str, liked: bool | None = True) -> dict:
    """Like = o take usável da aula 012: vira `shotMM_final.mp4`. Rejeitar conta como falha."""
    root = project_dir(pid)
    data, _ = _merge(root)
    entry = _find(data, scene, shot)
    take = next((t for t in entry["takes"] if t["id"] == take_id), None)
    if take is None:
        raise FileNotFoundError(f"take não encontrado: {scene}/{shot}/{take_id}")
    if liked is True:
        for t in entry["takes"]:
            if t is not take and t.get("liked") is True:
                t["liked"] = None       # no máximo um like por shot; rejeições (False) são preservadas
    take["liked"] = liked
    _sync_final(root, entry)
    _save_data(root, data)
    log.info("animate: like=%s em %s/%s/%s", liked, scene, shot, take_id)
    return _public(data, entry)


def _sync_final(root: Path, entry: dict) -> None:
    """`shotMM_final.mp4` existe se e somente se há take com like (cópia byte a byte)."""
    liked = next((t for t in entry["takes"] if t.get("liked") is True), None)
    for ext in VIDEO_EXT:
        old = root / _video_rel(entry["scene"], entry["shot"], "final", ext)
        if old.exists():
            old.unlink()
    if liked:
        src = root / liked["file"]
        dest = root / _video_rel(entry["scene"], entry["shot"], "final", Path(liked["file"]).suffix.lower())
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dest)


# ---------- geração paga pelo CLI ----------
def build_params(shot_entry: dict, model: str, prompt: str | None = None, duration: int | None = None,
                 root: Path | None = None) -> dict:
    """Params do `generate create`. Áudio do modelo SEMPRE OFF (aula 012)."""
    def _p(rel: str | None) -> str | None:
        if not rel:
            return None
        return str((root / rel).resolve()) if root else rel

    se = shot_entry.get("start_end") or None
    dur = duration or shot_entry.get("duration") or DURATIONS[0]
    params = {"prompt": (prompt if prompt is not None else shot_entry.get("prompt")) or "",
              "start_image": _p((se or {}).get("start") or shot_entry.get("image")),
              "duration": dur, "aspect_ratio": "16:9", "mode": "pro", "sound": False}
    if se:
        params["end_image"] = _p(se.get("end"))
        if model == "veo3_1_lite":
            params["duration"] = 8      # ressalva do CLI: veo3_1_lite com start+end exige 8 s
    return params


def _validated(pid: str, scene: str, shot: str, model: str, count: int) -> tuple[Path, dict, dict]:
    root = project_dir(pid)
    data, _ = _merge(root)
    entry = _find(data, scene, shot)
    order = model_order()
    if model not in order:
        raise ValueError(f"modelo fora da ordem configurada: {model} ({', '.join(order)})")
    if not 1 <= count <= 4:
        raise ValueError("gere de 1 a 4 takes por vez (a aula 012 usa 2)")
    return root, data, entry


def cost(pid: str, scene: str, shot: str, model: str, count: int = DEFAULT_TAKES) -> dict:
    root, _, entry = _validated(pid, scene, shot, model, count)
    res = hf.cost(model, build_params(entry, model, root=root))
    credits = res.get("credits")
    known = isinstance(credits, (int, float))
    return {"per_take": credits if known else None, "total": credits * count if known else None,
            "credits_unknown": not known, "model": model, "count": count, "error": res.get("error")}


def start_generate(pid: str, scene: str, shot: str, model: str, count: int = DEFAULT_TAKES,
                   prompt: str | None = None, duration: int | None = None) -> dict:
    root, _, entry = _validated(pid, scene, shot, model, count)
    text = (prompt if prompt is not None else entry.get("prompt")) or ""
    if not text.strip():
        raise ValueError("escreva (ou peça a sugestão de) o prompt do shot antes de gerar")
    if duration is not None and duration not in DURATIONS:
        raise ValueError(f"duração inválida: {duration} (a aula 012 usa {DURATIONS[0]} s ou {DURATIONS[1]} s)")
    params = build_params(entry, model, text, duration, root=root)

    def run(job: dict) -> None:
        for k in range(count):
            label = f"take{k + 1}"
            t0 = time.time()
            job["log"].append(f"{label}: started model={model}")
            if params.get("duration") == 8:
                job["log"].append(f"{label}: duration forced to 8 (veo3_1_lite start+end)")
            try:
                res = hf.generate(model, params, timeout_s=GENERATE_TIMEOUT_S)
                jid = res.get("id") or f"{int(t0)}_{k}"
                (root / "jobs").mkdir(parents=True, exist_ok=True)
                (root / "jobs" / f"animate_{jid}.json").write_text(
                    json.dumps(res.get("raw"), ensure_ascii=False, indent=1))
                urls = [u for u in res.get("urls") or [] if Path(u.split("?")[0]).suffix.lower() in VIDEO_EXT]
                if not urls:
                    raise RuntimeError("o CLI não devolveu URL de vídeo (JSON bruto em jobs/)")
                url = urls[0]
                tmp = root / STEP / "tmp" / f"{jid}_{k}{Path(url.split('?')[0]).suffix.lower()}"
                hf.download(url, tmp)
                cand = ingest.ingest_bytes(root, STEP, tmp.read_bytes(), "cli", tmp.name, text,
                                           {"job_id": jid, "model": model}, kind="video")
                tmp.unlink(missing_ok=True)
                if cand is None:
                    job["log"].append(f"{label}: skipped (vídeo repetido ou ilegível)")
                else:
                    attach_take(pid, scene, shot, cand["id"], model, text)
                    job["added"] += 1
                    job["log"].append(f"{label}: ok url={url.split('?')[0][-60:]} · {int(time.time() - t0)} s")
            except (RuntimeError, OSError) as e:     # falha de um take não derruba o job (aula 012: paciência)
                job["log"].append(f"{label}: failed {str(e)[:200]}")
                _bump_failure(root, scene, shot)
            job["done"] += 1

    try:
        return _registry.start(pid, count, run, scene=scene, shot=shot, model=model)
    except RuntimeError as e:
        raise RuntimeError("Já existe uma geração em andamento para este projeto.") from e


def _bump_failure(root: Path, scene: str, shot: str) -> None:
    data, _ = _merge(root)
    try:
        entry = _find(data, scene, shot)
    except FileNotFoundError:
        return
    entry["cli_failures"] = int(entry.get("cli_failures") or 0) + 1
    _save_data(root, data)


def job_status(pid: str) -> dict:
    return _registry.status(pid)
