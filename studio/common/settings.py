"""Config de modelos default por ação + livro-caixa de gasto em créditos `[extensão]` (ADR-016).

As telas do Studio deixam de trazer o modelo default fixo no código: cada **ação** que gera
(imagem base, multishot, cena, animação, trilha…) tem um modelo default resolvido nesta ordem:

    override do projeto  →  override global  →  default de código (`DEFAULTS`)

O override global vive em `STATE_DIR/config.json`; o do projeto em `projects/<pid>/config.json`.
A tela "Créditos & Custos" é o painel administrativo que edita esses defaults (por isso a
resolução é dado, não regra espalhada). Consultar custo **não** gasta crédito; só a geração real
gasta — e cada geração real é registrada no livro-caixa (`STATE_DIR/spend-ledger.jsonl`) para o
histórico por etapa/projeto.

Módulo puro de estado em arquivo (ADR-003): sem rede, sem subprocess. `pricing` conhece os
números; este módulo conhece as escolhas e o histórico.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import STATE_DIR
from . import atomic, pricing

CONFIG_PATH = STATE_DIR / "config.json"
LEDGER_PATH = STATE_DIR / "spend-ledger.jsonl"

#: Registro das ações que geram no Studio — dirige o painel admin da tela de custos. `screen` é o
#: rótulo da tela/etapa; `kind` casa com `pricing.CATALOG`. Fonte única: telas leem o default
#: daqui (`default_for`), nunca fixam o modelo no código.
ACTIONS: list[dict] = [
    {"key": "base.image", "screen": "Etapa 3 — Imagem base", "kind": "image",
     "label": "Gerar a imagem base"},
    {"key": "base.upscale", "screen": "Etapa 3 — Imagem base", "kind": "upscale",
     "label": "Upscale 2x da base"},
    {"key": "mood.grid", "screen": "Etapa 2 — Mood board", "kind": "image",
     "label": "Gerar o grid de vibe"},
    {"key": "mood.multishot", "screen": "Etapa 2 — Mood board", "kind": "image",
     "label": "Multishot da imagem de vibe"},
    {"key": "storyboard.scene", "screen": "Etapa 4 — Storyboard", "kind": "image",
     "label": "Gerar a foto da cena (prompt realista)"},
    {"key": "storyboard.multishot", "screen": "Etapa 4 — Storyboard", "kind": "image",
     "label": "Multishot (fotos-semente e frames da cena)"},
    # `[extensão]` wave 7 (ADR-021): vídeo por cena no storyboard. Cena → Kling 2.6; transição
    # (start/end) → Kling 3.0 (ADR-023 substitui a 3.0 Turbo, que não declara `end_image` no CLI).
    # O modelo é resolvido no servidor por `default_for` conforme o modo.
    {"key": "storyboard.video.scene", "screen": "Etapa 4 — Storyboard", "kind": "video",
     "label": "Gerar o vídeo da cena (image-to-video) [extensão]"},
    {"key": "storyboard.video.transition", "screen": "Etapa 4 — Storyboard", "kind": "video",
     "label": "Gerar a transição start/end (image-to-video) [extensão]"},
    {"key": "animate.video", "screen": "Etapa 5 — Animação", "kind": "video",
     "label": "Animar (image-to-video)"},
    {"key": "music.track", "screen": "Etapa 6 — Trilha", "kind": "audio",
     "label": "Gerar a trilha"},
]
ACTION_KEYS = {a["key"] for a in ACTIONS}

#: Default de código de cada ação: `{action: {"model": id, "variant": chave|None}}`. É o piso
#: usado quando não há override de projeto nem global.
DEFAULTS: dict[str, dict] = {
    "base.image": {"model": "nano_banana_2", "variant": "2k"},
    "base.upscale": {"model": "bytedance_image_upscale", "variant": None},
    "mood.grid": {"model": "nano_banana_2", "variant": "2k"},
    "mood.multishot": {"model": "nano_banana_2", "variant": "2k"},
    "storyboard.scene": {"model": "nano_banana_2", "variant": "2k"},
    "storyboard.multishot": {"model": "nano_banana_2", "variant": "2k"},
    # `[extensão]` wave 7 (ADR-021): cena → Kling 2.6. A transição (start/end) passou a Kling 3.0
    # pela ADR-023: só a `kling3_0` declara `end_image` no catálogo do CLI (a 3.0 Turbo não).
    # `animate.video` reverte o desvio (era `kling3_0`): a cena da animação também passa a 2.6.
    "storyboard.video.scene": {"model": "kling2_6", "variant": "5s"},
    "storyboard.video.transition": {"model": "kling3_0", "variant": "5s"},
    "animate.video": {"model": "kling2_6", "variant": "5s"},
    "music.track": {"model": "sonilo_music", "variant": None},
}


# ---------- leitura/escrita de config ----------
def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_atomic(path: Path, data: dict) -> None:
    """Temporário ÚNICO (`common.atomic`): `config.json` é global e escrito de dentro das threads
    de job, então duas gravações simultâneas disputavam o mesmo `config.json.tmp`."""
    atomic.write_json_atomic(path, data, ensure_ascii=False, indent=1)


def _project_config_path(pid: str) -> Path:
    from ..refs.service import project_dir
    return project_dir(pid) / "config.json"


def global_config() -> dict:
    """`{"defaults": {action: {model, variant}}}` global (vazio se nunca configurado)."""
    cfg = _read(CONFIG_PATH)
    return {"defaults": cfg.get("defaults", {}) if isinstance(cfg.get("defaults"), dict) else {}}


def project_config(pid: str) -> dict:
    """Override do projeto (vazio se o projeto nunca sobrescreveu nada)."""
    cfg = _read(_project_config_path(pid))
    return {"defaults": cfg.get("defaults", {}) if isinstance(cfg.get("defaults"), dict) else {}}


def _valid(action: str, model: str) -> None:
    if action not in ACTION_KEYS:
        raise ValueError(f"ação desconhecida: {action}")
    if not pricing.known(model):
        raise ValueError(f"modelo desconhecido: {model}")


def set_global_default(action: str, model: str, variant: str | None = None) -> dict:
    _valid(action, model)
    cfg = _read(CONFIG_PATH)
    cfg.setdefault("defaults", {})[action] = {"model": model, "variant": variant}
    _write_atomic(CONFIG_PATH, cfg)
    return default_for(action)


def set_project_default(pid: str, action: str, model: str, variant: str | None = None) -> dict:
    _valid(action, model)
    path = _project_config_path(pid)
    cfg = _read(path)
    cfg.setdefault("defaults", {})[action] = {"model": model, "variant": variant}
    _write_atomic(path, cfg)
    return default_for(action, pid)


def clear_project_default(pid: str, action: str) -> dict:
    path = _project_config_path(pid)
    cfg = _read(path)
    if isinstance(cfg.get("defaults"), dict):
        cfg["defaults"].pop(action, None)
        _write_atomic(path, cfg)
    return default_for(action, pid)


def default_for(action: str, pid: str | None = None) -> dict:
    """Modelo default resolvido de `action`: `{action, model, variant, source}`.

    `source ∈ {"project", "global", "code"}`. Um override que aponte para modelo/variação que
    saiu do catálogo é ignorado (cai para o próximo nível) — a UI nunca fica presa a um id morto.
    """
    if action not in ACTION_KEYS:
        raise ValueError(f"ação desconhecida: {action}")
    chain: list[tuple[str, dict]] = []
    if pid is not None:
        chain.append(("project", project_config(pid)["defaults"].get(action) or {}))
    chain.append(("global", global_config()["defaults"].get(action) or {}))
    chain.append(("code", DEFAULTS[action]))
    for source, choice in chain:
        model = choice.get("model")
        if model and pricing.known(model):
            variant = choice.get("variant")
            spec = pricing.CATALOG[model]
            # variação inexistente no modelo escolhido cai para a default do modelo
            if variant is not None and variant not in spec["variants"]:
                variant = None if spec.get("default_variant") in (None, "*") else spec.get("default_variant")
            if variant is None:
                variant = None if spec.get("default_variant") in (None, "*") else spec.get("default_variant")
            return {"action": action, "model": model, "variant": variant, "source": source}
    # inalcançável (DEFAULTS sempre válido), mas defensivo:
    return {"action": action, "model": None, "variant": None, "source": "code"}


def _variant_params(model: str, variant: str | None) -> dict:
    """Monta os params de `pricing.estimate` a partir da variação resolvida (resolução/duração)."""
    spec = pricing.CATALOG.get(model) or {}
    key = spec.get("variant_key")
    return {key: variant} if key and variant else {}


def all_defaults(pid: str | None = None) -> list[dict]:
    """Default resolvido de todas as ações, com a ficha da ação e o custo medido — dirige o admin."""
    out = []
    for a in ACTIONS:
        d = default_for(a["key"], pid)
        est = pricing.estimate(d["model"], _variant_params(d["model"], d["variant"])) if d["model"] else {}
        out.append({**a, **d, "credits": est.get("credits")})
    return out


# ---------- livro-caixa de gasto ----------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_spend(*, action: str, model: str, credits, pid: str | None = None,
                 step: str | None = None, variant: str | None = None,
                 job_id: str | None = None, project_name: str | None = None) -> dict:
    """Anexa uma linha ao livro-caixa APÓS uma geração real (a única que cobra créditos).

    Nunca levanta: registrar o gasto não pode derrubar a geração que já aconteceu.
    """
    entry = {"at": _now_iso(), "pid": pid, "project_name": project_name,
             "step": step, "action": action, "model": model, "variant": variant,
             "credits": credits, "job_id": job_id}
    try:
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return entry


def record_generation(*, action: str, model: str, params: dict | None = None, count: int = 1,
                       pid: str | None = None, step: str | None = None, job_id: str | None = None,
                       project_name: str | None = None) -> dict:
    """Estima o custo medido de UMA chamada real de geração (`count` imagens/clipes) e registra.

    Atalho para os serviços: eles conhecem `model`/`params`/`count`, não a tabela de preços.
    Chamar só APÓS a geração ter dado certo. Nunca levanta.
    """
    est = pricing.estimate(model, params)
    per = est.get("credits")
    total = round(per * max(1, count), 2) if per is not None else None
    return record_spend(action=action, model=model, credits=total, pid=pid, step=step,
                        variant=est.get("variant"), job_id=job_id, project_name=project_name)


def _read_ledger() -> list[dict]:
    if not LEDGER_PATH.is_file():
        return []
    out = []
    for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def history(pid: str | None = None, limit: int = 200) -> list[dict]:
    """Últimas `limit` linhas do livro-caixa (mais recentes primeiro), opcionalmente por projeto."""
    rows = _read_ledger()
    if pid is not None:
        rows = [r for r in rows if r.get("pid") == pid]
    rows.reverse()
    return rows[:max(0, limit)]


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def summary(pid: str | None = None) -> dict:
    """Agrega o gasto do livro-caixa: total e quebras por etapa e por projeto.

    `{total_credits, count, by_step: [{step, credits, count}], by_project: [{pid, name, credits, count}]}`.
    Com `pid`, restringe ao projeto (e `by_project` fica com uma linha só).
    """
    rows = _read_ledger()
    if pid is not None:
        rows = [r for r in rows if r.get("pid") == pid]
    by_step: dict[str, dict] = {}
    by_proj: dict[str, dict] = {}
    total = 0.0
    for r in rows:
        c = _num(r.get("credits"))
        total += c
        s = r.get("step") or r.get("action") or "—"
        st = by_step.setdefault(s, {"step": s, "credits": 0.0, "count": 0})
        st["credits"] += c
        st["count"] += 1
        p = r.get("pid") or "—"
        pr = by_proj.setdefault(p, {"pid": r.get("pid"), "name": r.get("project_name"), "credits": 0.0, "count": 0})
        pr["credits"] += c
        pr["count"] += 1
        if r.get("project_name"):
            pr["name"] = r.get("project_name")
    def rnd(v):
        return round(v, 2)
    return {
        "total_credits": rnd(total),
        "count": len(rows),
        "by_step": sorted(({**v, "credits": rnd(v["credits"])} for v in by_step.values()),
                          key=lambda x: x["credits"], reverse=True),
        "by_project": sorted(({**v, "credits": rnd(v["credits"])} for v in by_proj.values()),
                             key=lambda x: x["credits"], reverse=True),
    }
