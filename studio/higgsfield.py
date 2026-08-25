"""Ponte fina com o CLI oficial da Higgsfield (`higgsfield`), sempre via subprocess + --json.

Regra da doc oficial: nunca chamar api.higgsfield.ai direto; o CLI cuida de auth, upload e polling.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any

BIN = shutil.which("higgsfield") or shutil.which("hf")
IMG_URL_RE = re.compile(r"https?://[^\s\"']+\.(?:png|jpe?g|webp)(?:\?[^\s\"']*)?", re.I)


def available() -> bool:
    return BIN is not None


def _run(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    if not BIN:
        return 127, "", "higgsfield CLI não encontrado (npm i -g @higgsfield/cli)"
    try:
        p = subprocess.run([BIN, *args, "--json"], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", f"higgsfield {' '.join(args[:2])}: tempo esgotado após {timeout}s"
    except (FileNotFoundError, PermissionError) as e:
        return 127, "", f"higgsfield CLI indisponível: {e}"
    return p.returncode, p.stdout, p.stderr


def _json(out: str) -> Any:
    out = out.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        # alguns comandos imprimem várias linhas JSON
        items = []
        for line in out.splitlines():
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return items or out


def status() -> dict:
    """{'installed', 'logged_in', 'plan', 'credits', 'email', 'raw'|'error'}"""
    if not BIN:
        return {"installed": False, "logged_in": False}
    code, out, err = _run(["account", "status"], timeout=30)
    if code != 0:
        return {"installed": True, "logged_in": False, "error": (err or out).strip()[:300]}
    data = _json(out) or {}
    flat = _flatten(data)
    return {
        "installed": True, "logged_in": True,
        "email": _pick(flat, "email"), "plan": _pick(flat, "plan", "subscription", "tier"),
        "credits": _pick(flat, "credits", "balance", "available_credits"),
        "raw": data,
    }


def history_images(size: int = 50) -> list[dict]:
    """Jobs de imagem recentes (inclui o que foi gerado na UI, se o backend listar tudo).
    Retorna [{id, prompt, model, created, urls[]}] — formato defensivo: procura URLs de imagem em qualquer campo."""
    code, out, err = _run(["generate", "list", "--image", "--size", str(size)], timeout=60)
    if code != 0:
        raise RuntimeError((err or out).strip()[:300])
    data = _json(out)
    jobs = data.get("items") or data.get("jobs") or data.get("data") if isinstance(data, dict) else data
    result = []
    for j in jobs or []:
        if not isinstance(j, dict):
            continue
        flat = _flatten(j)
        urls = sorted({u for v in flat.values() if isinstance(v, str) for u in IMG_URL_RE.findall(v)})
        if not urls:
            continue
        result.append({
            "id": _pick(flat, "id", "job_id"), "prompt": _pick(flat, "prompt") or "",
            "model": _pick(flat, "job_type", "model", "type") or "", "created": _pick(flat, "created_at", "created") or "",
            "urls": urls,
        })
    return result


def cost(model: str, params: dict) -> dict:
    """Estimativa de créditos SEM criar job (`generate cost`). Devolve {'credits': n|None, 'raw'|'error'}."""
    code, out, err = _run(["generate", "cost", model, *_params(params)], timeout=60)
    if code != 0:
        return {"credits": None, "error": (err or out).strip()[:300]}
    data = _json(out)
    flat = _flatten(data if isinstance(data, dict) else {"d": data})
    credits = _pick(flat, "credits", "cost", "estimated_credits", "total_credits")
    return {"credits": credits, "raw": data}


def generate(model: str, params: dict, timeout_s: int = 600) -> dict:
    """Cria um job e espera. Cobra créditos. Devolve o JSON do job (com URLs) ou levanta RuntimeError."""
    code, out, err = _run(["generate", "create", model, *_params(params), "--wait", "--wait-timeout", f"{timeout_s}s"], timeout=timeout_s + 30)
    if code != 0:
        raise RuntimeError((err or out).strip()[:400])
    data = _json(out)
    flat = _flatten(data if isinstance(data, dict) else {"d": data})
    urls = sorted({u for v in flat.values() if isinstance(v, str) for u in IMG_URL_RE.findall(v)})
    return {"raw": data, "urls": urls, "id": _pick(flat, "id", "job_id")}


# ---------- utilidades ----------
def _params(params: dict) -> list[str]:
    args: list[str] = []
    for k, v in params.items():
        flag = f"--{k.replace('_', '-')}" if k in ("image_references", "start_image", "end_image", "aspect_ratio") else f"--{k}"
        if isinstance(v, (list, tuple)):
            for item in v:
                args += [flag, str(item)]
        elif isinstance(v, bool):
            args += [flag, "true" if v else "false"]
        elif v is not None and v != "":
            args += [flag, str(v)]
    return args


def _flatten(obj: Any, prefix: str = "", out: dict | None = None) -> dict:
    out = {} if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(v, f"{prefix}{k}.", out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _flatten(v, f"{prefix}{i}.", out)
    else:
        out[prefix.rstrip(".")] = obj
    return out


def _pick(flat: dict, *names: str):
    for n in names:
        for k, v in flat.items():
            if k.split(".")[-1] == n and v not in (None, ""):
                return v
    return None
