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
    monkeypatch.setenv("STUDIO_MOODBOARDS", str(tmp_path / "moodboards"))
    monkeypatch.setenv("STUDIO_CHARACTERS", str(tmp_path / "characters"))
    monkeypatch.setenv("STUDIO_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("STUDIO_DOWNLOADS", str(tmp_path / "downloads"))
    (tmp_path / "downloads").mkdir()
    for name in [m for m in list(sys.modules) if m == "studio" or m.startswith("studio.")]:
        del sys.modules[name]
    import studio.config  # noqa: F401  (re-executa com as variáveis novas)
    from studio import app as app_module
    from studio.mood import service as mood_service
    from studio.moodboards import service as moodboards_service
    from studio.refs import service as refs_service
    def svc(name: str):
        return importlib.import_module(f"studio.{name}.service")

    return {"tmp": tmp_path, "app": app_module.app, "refs": refs_service, "mood": mood_service,
            "moodboards": moodboards_service, "svc": svc}


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


# ---------- fixtures de reset (`[extensão]`) ----------
#: Um artefato-fake para CADA etapa, cobrindo as pastas/arquivos que a etapa escreve de verdade
#: (conferido no `service.py` de cada uma). Usado pelos testes de reset para provar a cascata.
RESET_FAKES: dict[str, list[str]] = {
    "refs": ["refs/candidates/c.jpg", "refs/candidates/thumbs/c.jpg",
             "refs/brainstorming/c.jpg", "refs/README.md", "refs/last_job.json"],
    "mood": ["mood/mood.md", "mood/palette.json", "mood/selected/s.jpg",
             "mood/candidates/m.jpg", "mood/vibe/candidates/v.jpg", "mood/prompts.json"],
    "base": ["base/base_final.png", "base/brand.json", "base/base.md", "base/candidates/b.png"],
    "storyboard": ["storyboard/scenes.json", "storyboard/storyboard.md", "storyboard/storyboard.json",
                   "storyboard/frames.md", "storyboard/ideas/i.jpg", "storyboard/candidates/c.jpg",
                   "storyboard/cena01/base.png", "storyboard/cena01/selection.json",
                   "storyboard/product/ref.png"],
    "animate": ["animate/takes.json", "animate/candidates/a.mp4", "videos/cena01/shot01_final.mp4"],
    "music": ["audio/music.mp3", "audio/beats.json", "audio/license.txt",
              "audio/rough_sequence.mp4", "audio/candidates/x.mp3"],
    "edit": ["edit/timeline.json", "edit/master.mp4", "edit/rough_cut.mp4",
             "edit/last_frames/f.png", "edit/candidates/s.wav"],
    "export": ["export/9x16.mp4", "export/thumb.jpg", "export/qa_report.md",
               "export/.state.json", "export/previews/9x16.jpg"],
    "publish": ["publish/log.json", "publish/portfolio.md", "publish/community.json"],
    "prospect": ["prospect/leads.json", "prospect/pitch.json", "prospect/pitch.md",
                 "prospect/teasers/1.mp4"],
}
#: `jobs/<prefixo>_*.json` que as etapas com job persistido deixam no disco.
RESET_JOB_FILES: list[str] = [
    "jobs/mood_1.json", "jobs/base_1.json", "jobs/storyboard_1.json",
    "jobs/animate_1.json", "jobs/music_1.json", "jobs/export_1.json",
]
#: Infra compartilhada que nenhuma etapa escreve hoje, mas que o reset da campanha inteira limpa.
RESET_SHARED: list[str] = ["assets/a.bin", "images/i.png"]


def seed_all_steps(root: Path) -> None:
    """Escreve um artefato-fake em TODAS as etapas + jobs/ + infra compartilhada de `root`."""
    for rel in [r for rels in RESET_FAKES.values() for r in rels] + RESET_JOB_FILES + RESET_SHARED:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")


def files_under(root: Path, rel: str) -> list[str]:
    """Arquivos (não pastas) sob `root/rel`, em caminhos relativos a `root`."""
    base = root / rel
    if not base.exists():
        return []
    return sorted(str(p.relative_to(root)) for p in base.rglob("*") if p.is_file())
