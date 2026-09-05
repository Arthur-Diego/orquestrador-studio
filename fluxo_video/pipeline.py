"""[extensão] Orquestração local do fluxo: roteiro → imagens (engine local) → vídeo (ffmpeg).

Independente: não fala com ContentFlow nem com nenhum serviço externo. Só usa o local_ai_engine
(no lugar) para as imagens e o ffmpeg para o vídeo. As dependências de geração são injetáveis,
para testar a orquestração sem GPU nem ffmpeg.
"""

from __future__ import annotations

from pathlib import Path

from . import engine_local, render, render_i2v
from .projeto import Projeto
from .schema import Plano, Roteiro


def _prompt_movimento(p: Plano) -> str:
    """Prompt descritivo (longo) para o i2v — o LTX degrada com prompt curto."""
    vp = p.video_prompt
    return (f"{p.image_prompt}. {vp.subject_movement}. Camera: {vp.camera}. "
            f"{vp.lighting}. {vp.atmosphere}.")


def _prompt_ancora(roteiro: Roteiro) -> str:
    """Prompt do retrato-âncora (character sheet) a partir da identidade visual."""
    iv = roteiro.identidade_visual
    return (f"{iv.estilo}, {iv.personagem.descriptor}, character reference portrait, "
            f"upper body, front view, neutral expression, clean simple background, no text")


def gerar_ancora_personagem(roteiro: Roteiro, projeto: Projeto, *, motor: str = "anime",
                            model: str = "flux-schnell", gerar=engine_local.gerar_imagem) -> Path:
    """Gera UMA vez o retrato-âncora fixo do personagem (item 2: character sheet)."""
    projeto.preparar()
    gerar(_prompt_ancora(roteiro), projeto.personagem, motor=motor, model=model, ref=None)
    return projeto.personagem


def gerar_imagens(roteiro: Roteiro, projeto: Projeto, *, motor: str = "anime",
                  model: str = "flux-schnell", seguir_identidade: bool = True,
                  gerar=engine_local.gerar_imagem) -> list[Path]:
    """Gera a imagem de cada plano.

    Com `seguir_identidade`, fixa um retrato-âncora do personagem (character sheet) e o aplica
    como referência (IPAdapter) SÓ nos planos marcados `personagem=True` — cenas de cenário puro
    (`personagem=False`) saem sem âncora, evitando injetar um rosto onde não deve haver.
    """
    projeto.preparar()
    ancora: Path | None = None
    if seguir_identidade:
        ancora = gerar_ancora_personagem(roteiro, projeto, motor=motor, model=model, gerar=gerar)
    caminhos: list[Path] = []
    for p in roteiro.planos:
        out = projeto.imagem(p.n)
        ref = ancora if (ancora is not None and p.personagem) else None
        gerar(p.image_prompt, out, motor=motor, model=model, ref=ref)
        caminhos.append(out)
    return caminhos


def montar_video(roteiro: Roteiro, projeto: Projeto, *, motion: str = "kenburns",
                 render_clip=render.render_kenburns, concat=render.concat,
                 animar=render_i2v.animar_i2v, normalizar=render.normalizar_clip) -> Path:
    """Cada imagem → clipe (Ken Burns ou i2v LTX) na duração do plano; concatena no final.

    `motion`: 'kenburns' (movimento de câmera sobre a imagem parada) ou 'i2v' (a cena ganha
    vida via LTX-Video no ComfyUI).
    """
    clips: list[Path] = []
    for p in roteiro.planos:
        img = projeto.imagem(p.n)
        if not img.exists():
            raise FileNotFoundError(f"imagem do plano {p.n} não encontrada: {img} (rode 'imagens' antes)")
        clip = projeto.clip(p.n)
        if motion == "i2v":
            raw = projeto.clips / f"plano{p.n:02d}_raw.mp4"
            animar(img, _prompt_movimento(p), raw, seed=p.n)
            normalizar(raw, clip)
        else:
            render_clip(img, clip, dur_s=p.duration_s)
        clips.append(clip)
    return concat(clips, projeto.final)
