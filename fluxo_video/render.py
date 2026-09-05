"""[extensão] Montagem de vídeo com ffmpeg — 100% local, sem serviço externo.

Cada plano vira um clipe com movimento Ken Burns (zoom lento) a partir da sua imagem, na
duração do plano; depois os clipes são concatenados no vídeo final 9:16. É o baseline local e
grátis (equivalente ao slideshow), com ponto de extensão claro para i2v depois.

`args_kenburns` e `args_concat` são puros (montam a linha do ffmpeg) e testáveis; os `render_*`
executam, com runner injetável.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

LARGURA = 1080
ALTURA = 1920
FPS = 30


class RenderError(RuntimeError):
    pass


def _vf_kenburns(dur_s: float, w: int = LARGURA, h: int = ALTURA, fps: int = FPS,
                 zoom_max: float = 1.15) -> str:
    frames = max(1, round(dur_s * fps))
    # enquadra em 9:16 (cobre e corta) e aplica um zoom-in suave ao longo do plano.
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},"
        f"zoompan=z='min(zoom+0.0008,{zoom_max})':d={frames}:s={w}x{h}:fps={fps}"
    )


def args_kenburns(imagem: Path | str, saida: Path | str, *, dur_s: float,
                  w: int = LARGURA, h: int = ALTURA, fps: int = FPS) -> list[str]:
    """Args do ffmpeg (sem o 'ffmpeg' inicial) para 1 imagem → 1 clipe Ken Burns."""
    return [
        "-y", "-loop", "1", "-i", str(imagem), "-t", f"{dur_s:.3f}", "-r", str(fps),
        "-vf", _vf_kenburns(dur_s, w, h, fps),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(saida),
    ]


def args_concat(lista_txt: Path | str, saida: Path | str) -> list[str]:
    """Args do ffmpeg para concatenar clipes uniformes (concat demuxer, copy)."""
    return ["-y", "-f", "concat", "-safe", "0", "-i", str(lista_txt), "-c", "copy", str(saida)]


def args_normalizar(entrada: Path | str, saida: Path | str, *,
                    w: int = LARGURA, h: int = ALTURA, fps: int = FPS) -> list[str]:
    """Args do ffmpeg para padronizar um clipe (ex.: o cru 512x768 do LTX) em 9:16 uniforme."""
    return [
        "-y", "-i", str(entrada),
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(saida),
    ]


def _run(args: list[str], runner) -> None:
    try:
        proc = runner(["ffmpeg", *args], capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RenderError(f"falha ao executar ffmpeg: {exc}") from exc
    if proc.returncode != 0:
        raise RenderError(f"ffmpeg retornou {proc.returncode}: {(proc.stderr or '').strip()[-300:]}")


def render_kenburns(imagem: Path, saida: Path, *, dur_s: float, runner=subprocess.run) -> Path:
    saida.parent.mkdir(parents=True, exist_ok=True)
    _run(args_kenburns(imagem, saida, dur_s=dur_s), runner)
    return saida


def normalizar_clip(entrada: Path, saida: Path, *, runner=subprocess.run) -> Path:
    """Padroniza um clipe (i2v cru) para o formato final 9:16 uniforme."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    _run(args_normalizar(entrada, saida), runner)
    return saida


def concat(clips: list[Path], saida: Path, *, runner=subprocess.run) -> Path:
    if not clips:
        raise RenderError("nada para concatenar (lista de clipes vazia)")
    saida.parent.mkdir(parents=True, exist_ok=True)
    lista = saida.parent / "concat.txt"
    lista.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    _run(args_concat(lista, saida), runner)
    return saida
