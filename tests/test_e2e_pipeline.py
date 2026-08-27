"""Teste fino que roda o E2E mockado (scripts/e2e_pipeline.py) num projeto isolado.

Cobre 1→11 + reset ponta a ponta pela API, sem rede. Exige ffmpeg (etapas 6–11); sem ele o
teste é ignorado (ADR-008: geração de mídia real fica fora do CI puro). Reusa as fixtures
isoladas do conftest (`client`/`studio_env`), então não toca no `projects/` do repo.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.e2e_pipeline import run
from studio.common import ffmpeg as ff

pytestmark = pytest.mark.skipif(not ff.available(), reason="ffmpeg ausente: E2E de mídia não roda")


def test_e2e_pipeline_full(client, studio_env):
    projects_dir = Path(studio_env["tmp"]) / "projects"
    ok, fail = run(client, projects_dir, do_reset=True)
    assert not fail, "checks E2E falharam:\n  " + "\n  ".join(fail)
    # 1→11 + reset devem somar a bateria completa (âncora contra regressão silenciosa de cobertura)
    assert len(ok) >= 30, f"esperava >=30 checks, veio {len(ok)}"
