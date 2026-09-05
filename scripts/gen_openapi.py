"""Despeja o `/openapi.json` do app em disco — insumo do `schema.ts` do frontend (Wave 10, E1).

O FastAPI já publica `/openapi.json` em runtime; este script pega o MESMO documento sem subir
servidor (`app.openapi()`), para que a geração de tipos e o teste de drift no CI não dependam de
`uvicorn`, de porta livre nem de ordem de boot.

Uso:
    python scripts/gen_openapi.py [destino]      # default: frontend/openapi.json

O destino é gitignorado de propósito: o artefato versionado é o `frontend/src/api/schema.ts`
(ADR-031), e ter duas cópias geradas do mesmo contrato no git seria duas coisas para dessincronizar.
Este arquivo existe só como entrada do `openapi-typescript`.

Determinismo (o teste de drift depende dele): a ordem das rotas vem de `discover()`, que ordena os
plugins por `META['n']`, e o JSON é escrito com `indent=2` e `ensure_ascii=False` — sem `sort_keys`,
para preservar a ordem do documento como o FastAPI o publica.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "frontend" / "openapi.json"


def main(argv: list[str]) -> int:
    sys.path.insert(0, str(ROOT))
    from studio.app import app  # noqa: PLC0415 — import tardio: precisa da raiz no sys.path

    out = Path(argv[1]).resolve() if len(argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"openapi.json escrito em {out} ({len(app.openapi()['paths'])} rotas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
