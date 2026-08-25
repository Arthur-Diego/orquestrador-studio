"""Acesso ao ffmpeg/ffprobe (build estática em ~/.local/bin ou o que estiver no PATH)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def _find(name: str) -> str | None:
    local = Path.home() / ".local" / "bin" / name
    return shutil.which(name) or (str(local) if local.exists() else None)


FFMPEG = _find("ffmpeg")
FFPROBE = _find("ffprobe")


def available() -> bool:
    return bool(FFMPEG and FFPROBE)


def run(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Roda `ffmpeg <args>` (sem o binário). Levanta RuntimeError com o fim do stderr em caso de erro."""
    if not FFMPEG:
        raise RuntimeError("ffmpeg não encontrado (instale em ~/.local/bin ou no PATH)")
    p = subprocess.run([FFMPEG, "-hide_banner", "-y", *args], capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {p.stderr.strip()[-600:]}")
    return p


def probe(path: str | Path) -> dict:
    """{'duration', 'width', 'height', 'fps', 'has_audio'} via ffprobe (zeros se ausente)."""
    if not FFPROBE:
        raise RuntimeError("ffprobe não encontrado")
    p = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe falhou: {p.stderr.strip()[-300:]}")
    data = json.loads(p.stdout or "{}")
    out = {"duration": float(data.get("format", {}).get("duration") or 0), "width": 0, "height": 0, "fps": 0.0, "has_audio": False}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not out["width"]:
            out["width"], out["height"] = int(s.get("width") or 0), int(s.get("height") or 0)
            num, _, den = (s.get("avg_frame_rate") or "0/1").partition("/")
            out["fps"] = round(float(num) / float(den), 3) if den and float(den) else 0.0
        if s.get("codec_type") == "audio":
            out["has_audio"] = True
    return out


def last_frame(video: str | Path, out_png: str | Path, offset: float = 0.05) -> Path:
    """Último frame do vídeo (aula 014: vira start frame da transição colada)."""
    run(["-sseof", f"-{offset}", "-i", str(video), "-frames:v", "1", str(out_png)])
    return Path(out_png)


def video_thumb(video: str | Path, out_jpg: str | Path, t: float = 0.5) -> Path:
    run(["-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf", "scale=520:-2", str(out_jpg)])
    return Path(out_jpg)
