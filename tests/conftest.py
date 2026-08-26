"""Fixtures compartilhadas: projetos isolados em diretório temporário e cliente HTTP."""
from __future__ import annotations

import importlib
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
    def svc(name: str):
        return importlib.import_module(f"studio.{name}.service")

    return {"tmp": tmp_path, "app": app_module.app, "refs": refs_service, "mood": mood_service, "svc": svc}


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


def make_video(path: Path, seconds: float = 2, size: str = "320x240") -> Path:
    """Vídeo sintético (testsrc + tom) via ffmpeg — para fixtures de animate/edit/export."""
    from studio.common import ffmpeg as ff
    path.parent.mkdir(parents=True, exist_ok=True)
    ff.run(["-f", "lavfi", "-i", f"testsrc=size={size}:rate=30", "-f", "lavfi", "-i", "sine=frequency=440",
            "-t", str(seconds), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)])
    return path


def make_audio(path: Path, seconds: float = 3, bpm: int = 120) -> Path:
    """Áudio sintético com batidas (tom pulsado) via ffmpeg — para fixtures de music/edit."""
    from studio.common import ffmpeg as ff
    path.parent.mkdir(parents=True, exist_ok=True)
    period = 60 / bpm
    ff.run(["-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
            "-af", f"volume='if(lt(mod(t,{period}),0.08),1,0.05)':eval=frame", str(path)])
    return path


@pytest.fixture()
def ffmpeg_or_skip(studio_env):
    """Pula o teste quando não há ffmpeg (fixtures de áudio/vídeo dependem do lavfi)."""
    from studio.common import ffmpeg as ff
    if not ff.available():
        pytest.skip("ffmpeg indisponível")
    return ff
