"""`[extensão]` Reset de etapa (em cascata) e da campanha inteira — ADH-OS-20260827-01.

Reset **não é passo do curso** (ADR-004): é uma extensão do Studio para desfazer o trabalho já
feito e refazer com outra decisão. Duas operações, ambas mantendo sempre o `project.json`
(nome, produto, vibe e formato da campanha):

- `reset_step(pid, step)` — CASCATA: apaga as saídas de `step` **e de todas as etapas seguintes**
  (ordem canônica em `studio/steps.py`), remove os `jobs/<prefixo>_*.json` e o estado em memória
  dessas etapas e recria as pastas vazias do `PROJECT_LAYOUT` que sumiram.
- `reset_campaign(pid)` — apaga TODAS as saídas + a infra compartilhada (`jobs/`, `assets/`,
  `images/`, `videos/`, `audio/`, `edit/`, `export/`), recria o `PROJECT_LAYOUT`.

O MAPA `STEP_OUTPUTS` abaixo foi conferido lendo o `service.py` de cada etapa: é a lista das
pastas/arquivos que cada etapa escreve em `projects/<pid>/`. Um caminho errado apagaria de menos
ou de mais — por isso o reset só usa caminhos deste mapa (nunca um valor cru) e nunca escreve nem
apaga fora de `projects/<pid>/`.
"""
from __future__ import annotations

import importlib
import shutil
from pathlib import Path

from ..config import PROJECT_LAYOUT
from ..refs.service import project_dir
from ..steps import SOON

#: Ordem canônica das etapas — `studio/steps.py` é a única fonte da ordem (o `n` de cada etapa).
STEP_ORDER: list[str] = [s["id"] for s in sorted(SOON, key=lambda s: s["n"])]

#: MAPA etapa_id → saídas (pastas/arquivos) que a etapa escreve em `projects/<pid>/`.
#: Conferido no `service.py` de cada etapa:
#:   refs       → tudo em `refs/` (candidates/, thumbs, brainstorming/, README.md, last_job.json)
#:   mood       → tudo em `mood/` (vibe/, candidates/, selected/, prompts.json, palette.json, mood.md)
#:   base       → tudo em `base/` (brand.json, prompts.json, candidates/, base.md, base_final.png)
#:   storyboard → tudo em `storyboard/` (candidates/, ideas/, scenes.json, storyboard.md/.json)
#:   shots      → tudo em `shots/` (cenaNN/, product/, storyboard.json/.md)
#:   animate    → `animate/` (takes.json, candidates/, tmp/) **e** `videos/` (os vídeos gerados)
#:   music      → `audio/` (o id da etapa é `music`, mas a pasta do projeto é `audio/`:
#:                candidates/, music.*, beats.json, license.txt, rough_sequence.mp4, story_check.json)
#:   edit       → `edit/` (timeline.json, master.mp4, rough_cut.mp4, last_frames/, candidates/)
#:   export     → `export/` ({fmt}.mp4, thumb.jpg, qa_report.md, previews/, .state.json)
#:   publish    → `publish/` (log.json, portfolio.md, community.json)
#:   prospect   → `prospect/` (leads.json, teasers/, pitch.json, pitch.md)
STEP_OUTPUTS: dict[str, list[str]] = {
    "refs": ["refs"],
    "mood": ["mood"],
    "base": ["base"],
    "storyboard": ["storyboard"],
    "shots": ["shots"],
    "animate": ["animate", "videos"],
    "music": ["audio"],
    "edit": ["edit"],
    "export": ["export"],
    "publish": ["publish"],
    "prospect": ["prospect"],
}

#: Prefixo dos arquivos `jobs/<prefixo>_*.json` por etapa (ausente = a etapa não persiste em `jobs/`).
#: refs usa `refs/last_job.json` (dentro de `refs/`, some junto); edit/publish/prospect não escrevem
#: nada em `jobs/`.
JOB_PREFIX: dict[str, str] = {
    "mood": "mood",
    "base": "base",
    "storyboard": "storyboard",
    "shots": "shots",
    "animate": "animate",
    "music": "music",
    "export": "export",
}


class ResetBlocked(RuntimeError):
    """`[extensão]` Uma etapa afetada tem job em andamento — reset recusado (vira 409 na rota).

    A thread daemon de um job não pode ser morta (ADR-006); apagar as saídas com um job escrevendo
    corromperia o estado. Por isso o reset só é aceito quando nenhuma etapa afetada está 'running'.
    """

    def __init__(self, steps: list[str]) -> None:
        self.steps = steps
        super().__init__("etapa com trabalho em andamento (aguarde ou cancele): " + ", ".join(steps))


def _safe_path(root: Path, rel: str) -> Path:
    """Resolve `rel` dentro de `root` e recusa qualquer caminho que escape de `projects/<pid>/`."""
    root_r = root.resolve()
    p = (root / rel).resolve()
    if p != root_r and root_r not in p.parents:
        raise ValueError(f"caminho fora do projeto: {rel!r}")
    return p


def _registries(step: str) -> list:
    """Registros de jobs em memória da etapa (`_registry`, `registry`, `_story_registry`)."""
    if step == "refs":
        return []  # refs usa um dict próprio por pid — tratado em `_clear_memory`/`_running_steps`
    mod = importlib.import_module(f"studio.{step}.service")
    out = []
    for attr in ("_registry", "registry", "_story_registry"):
        reg = getattr(mod, attr, None)
        if reg is not None:
            out.append(reg)
    return out


def _running_steps(pid: str, steps: list[str]) -> list[str]:
    """Subconjunto de `steps` com algum job 'running' agora (para recusar o reset)."""
    busy: list[str] = []
    for step in steps:
        if step == "refs":
            from ..refs import service as refs_service
            with refs_service._lock:
                if refs_service._jobs.get(pid, {}).get("state") == "running":
                    busy.append(step)
            continue
        if any(reg.is_running(pid) for reg in _registries(step)):
            busy.append(step)
    return busy


def _clear_memory(pid: str, step: str) -> None:
    """Esquece o estado em memória dos jobs da etapa (volta o polling para 'idle')."""
    if step == "refs":
        from ..refs import service as refs_service
        with refs_service._lock:
            refs_service._jobs.pop(pid, None)
        return
    for reg in _registries(step):
        reg.clear(pid)


def _wipe_step(root: Path, pid: str, step: str) -> list[str]:
    """Apaga as saídas em disco de UMA etapa, os `jobs/<prefixo>_*.json` e o estado em memória.

    Devolve a lista de caminhos relativos efetivamente removidos.
    """
    cleared: list[str] = []
    for rel in STEP_OUTPUTS[step]:
        target = _safe_path(root, rel)
        if target.is_dir():
            shutil.rmtree(target)
            cleared.append(rel)
        elif target.exists():
            target.unlink()
            cleared.append(rel)
    prefix = JOB_PREFIX.get(step)
    if prefix:
        jobs_dir = root / "jobs"
        if jobs_dir.is_dir():
            for f in sorted(jobs_dir.glob(f"{prefix}_*.json")):
                f.unlink()
                cleared.append(f"jobs/{f.name}")
    _clear_memory(pid, step)
    return cleared


def _recreate_layout(root: Path) -> None:
    """Recria as pastas do `PROJECT_LAYOUT` que sumiram (idempotente; nunca toca em `project.json`)."""
    for sub in PROJECT_LAYOUT:
        (root / sub).mkdir(parents=True, exist_ok=True)


def reset_step(pid: str, step: str) -> dict:
    """Reset em cascata: apaga `step` e todas as etapas seguintes; mantém `project.json`.

    `KeyError` para pid inválido/inexistente (via `project_dir`) **ou** etapa desconhecida — ambos
    viram 404 na rota. `ResetBlocked` quando alguma etapa afetada tem job em andamento (409).
    """
    root = project_dir(pid)                 # KeyError → 404
    if step not in STEP_OUTPUTS:
        raise KeyError(step)                # etapa desconhecida → 404
    affected = STEP_ORDER[STEP_ORDER.index(step):]
    busy = _running_steps(pid, affected)
    if busy:
        raise ResetBlocked(busy)
    cleared: list[str] = []
    for st in affected:
        cleared += _wipe_step(root, pid, st)
    _recreate_layout(root)
    return {"cleared": sorted(set(cleared)), "kept": "project.json"}


def reset_campaign(pid: str) -> dict:
    """Apaga tudo em `projects/<pid>/` menos o `project.json` e recria o `PROJECT_LAYOUT`.

    Cobre as saídas das 11 etapas + a infra compartilhada (`jobs/`, `assets/`, `images/`, ...).
    `KeyError` → 404; `ResetBlocked` (409) se qualquer etapa tiver job em andamento.
    """
    root = project_dir(pid)                 # KeyError → 404
    busy = _running_steps(pid, STEP_ORDER)
    if busy:
        raise ResetBlocked(busy)
    cleared: list[str] = []
    for child in sorted(root.iterdir()):
        if child.name == "project.json":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        cleared.append(child.name)
    for step in STEP_ORDER:
        _clear_memory(pid, step)
    _recreate_layout(root)
    return {"cleared": sorted(cleared), "kept": "project.json"}
