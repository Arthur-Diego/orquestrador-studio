"""Descoberta de plugins de etapa.

Cada etapa implementada vive em `studio/etapas/<id>/` com:
- `__init__.py` exportando `META` (id, n, title, aula, desc);
- `router.py` exportando `router` (fastapi.APIRouter) — as rotas da etapa;
- `view.html` (fragmento inserido em <main>) e `view.js` (registra `Studio.register("<id>", {...})`).

Etapas ainda não implementadas ficam apenas no catálogo `studio.steps.SOON`. Assim, uma
frente de trabalho nova cria só a sua pasta e nunca edita `app.py`, `index.html` ou `app.js`.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

ETAPAS_DIR = Path(__file__).resolve().parent


def discover() -> dict[str, dict]:
    """{id: {"meta": META, "router": APIRouter|None, "dir": Path}} em ordem de META['n']."""
    found: dict[str, dict] = {}
    for mod in pkgutil.iter_modules([str(ETAPAS_DIR)]):
        if not mod.ispkg:
            continue
        pkg = importlib.import_module(f"{__name__}.{mod.name}")
        meta = getattr(pkg, "META", None)
        if not meta or meta.get("id") != mod.name:
            raise RuntimeError(f"etapa '{mod.name}' precisa exportar META com id == nome da pasta")
        router = None
        try:
            router = importlib.import_module(f"{__name__}.{mod.name}.router").router
        except ModuleNotFoundError as e:
            if not e.name.endswith(".router"):
                raise
        found[mod.name] = {"meta": {**meta, "status": "ready"}, "router": router, "dir": ETAPAS_DIR / mod.name}
    return dict(sorted(found.items(), key=lambda kv: kv[1]["meta"]["n"]))
