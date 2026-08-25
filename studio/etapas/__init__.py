"""Descoberta de plugins de etapa.

Cada etapa implementada vive em `studio/etapas/<id>/` com:
- `__init__.py` exportando `META` (id, n, title, aula, desc);
- `router.py` exportando `router` (fastapi.APIRouter) — as rotas da etapa;
- `view.html` (fragmento inserido em <main>) e `view.js` (registra `Studio.register("<id>", {...})`);
- `guide.py` (opcional) exportando `guide(pid) -> dict` — o guia da etapa, por leitura pura dos
  artefatos do projeto (contrato em `studio/common/guide.py`). Sem `guide.py`, o núcleo devolve
  um guia genérico com `status: "unknown"`.

Etapas ainda não implementadas ficam apenas no catálogo `studio.steps.SOON`. Assim, uma
frente de trabalho nova cria só a sua pasta e nunca edita `app.py`, `index.html` ou `app.js`.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

ETAPAS_DIR = Path(__file__).resolve().parent


def discover() -> dict[str, dict]:
    """{id: {"meta": META, "router": APIRouter|None, "guide": callable|None, "dir": Path}}.

    Ordenado por `META['n']`. `router` e `guide` são opcionais: a ausência do módulo não é erro
    (um `ModuleNotFoundError` de outra dependência, sim — esse propaga).
    """
    found: dict[str, dict] = {}
    for mod in pkgutil.iter_modules([str(ETAPAS_DIR)]):
        if not mod.ispkg:
            continue
        pkg = importlib.import_module(f"{__name__}.{mod.name}")
        meta = getattr(pkg, "META", None)
        if not meta or meta.get("id") != mod.name:
            raise RuntimeError(f"etapa '{mod.name}' precisa exportar META com id == nome da pasta")
        router = _optional(mod.name, "router", "router")
        guide = _optional(mod.name, "guide", "guide")
        found[mod.name] = {"meta": {**meta, "status": "ready"}, "router": router,
                           "guide": guide, "dir": ETAPAS_DIR / mod.name}
    return dict(sorted(found.items(), key=lambda kv: kv[1]["meta"]["n"]))


def _optional(step: str, module: str, attr: str):
    """`studio.etapas.<step>.<module>.<attr>` ou None se o módulo não existir na pasta."""
    name = f"{__name__}.{step}.{module}"
    try:
        return getattr(importlib.import_module(name), attr)
    except ModuleNotFoundError as e:
        if e.name != name:   # o módulo existe, mas uma dependência dele não: é erro de verdade
            raise
        return None
