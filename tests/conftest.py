"""Fixtures compartilhadas: projetos isolados em diretório temporário e cliente HTTP."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture()
def studio_env(tmp_path, monkeypatch):
    """Isola PROJECTS_DIR e STATE_DIR e recarrega os módulos para que leiam o novo ambiente."""
    monkeypatch.setenv("STUDIO_PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setenv("STUDIO_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("STUDIO_DOWNLOADS", str(tmp_path / "downloads"))
    (tmp_path / "downloads").mkdir()
    for name in [m for m in list(sys.modules) if m == "studio" or m.startswith("studio.")]:
        del sys.modules[name]
    import studio.config  # noqa: F401  (re-executa com as variáveis novas)
    from studio import app as app_module
    from studio.mood import service as mood_service
    from studio.refs import service as refs_service
    return {"tmp": tmp_path, "app": app_module.app, "refs": refs_service, "mood": mood_service}


@pytest.fixture()
def client(studio_env):
    from fastapi.testclient import TestClient
    return TestClient(studio_env["app"])


def make_image(path: Path, color=(30, 120, 200), size=(64, 96)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "JPEG")
    return path


def image_bytes(color=(200, 40, 40), size=(48, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()
