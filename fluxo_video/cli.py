"""[extensão] CLI `fluxo_video` — fluxo LOCAL e independente (roteiro→imagens→vídeo).

Autossuficiente: usa o local_ai_engine (no lugar, via binário dele) para as imagens e o ffmpeg
para o vídeo. Não depende de ContentFlow nem de nenhum serviço externo. A REDAÇÃO do roteiro é
dos subagents; aqui ficam as etapas mecânicas.

  python -m fluxo_video validar roteiro.json
  python -m fluxo_video imagens roteiro.json [--projeto DIR] [--model flux-dev]
  python -m fluxo_video video   roteiro.json [--projeto DIR]
  python -m fluxo_video tudo    roteiro.json [--projeto DIR]   # imagens + vídeo
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import pipeline
from .engine_local import EngineError
from .projeto import Projeto, projeto_para
from .render import RenderError
from .schema import Roteiro, RoteiroInvalido, carregar_roteiro
from .validador import validar_congruencia


def _erro(msg: str) -> int:
    print(f"falha: {msg}", file=sys.stderr)
    return 1


def _carregar_valido(caminho: str) -> Roteiro:
    """Carrega e exige congruência (gate). Levanta RoteiroInvalido se qualquer coisa falhar."""
    roteiro = carregar_roteiro(caminho)
    rel = validar_congruencia(roteiro)
    if not rel.ok:
        raise RoteiroInvalido("roteiro incongruente — rode `validar` e corrija:\n" + rel.resumo())
    return roteiro


def _projeto(args, roteiro: Roteiro) -> Projeto:
    proj = Projeto(Path(args.projeto).expanduser()) if args.projeto else projeto_para(roteiro.meta.titulo)
    proj.preparar()
    shutil.copyfile(args.roteiro, proj.roteiro_path)  # guarda o roteiro no projeto
    return proj


def cmd_validar(args) -> int:
    try:
        roteiro = carregar_roteiro(args.roteiro)
    except RoteiroInvalido as exc:
        return _erro(str(exc))
    rel = validar_congruencia(roteiro)
    print(rel.resumo())
    return 0 if rel.ok else 2


def cmd_imagens(args) -> int:
    try:
        roteiro = _carregar_valido(args.roteiro)
        proj = _projeto(args, roteiro)
        print(f"projeto: {proj.raiz}")
        caminhos = pipeline.gerar_imagens(
            roteiro, proj, motor=args.motor, model=args.model,
            seguir_identidade=not args.sem_identidade)
    except (RoteiroInvalido, EngineError, OSError) as exc:
        return _erro(str(exc))
    for p in caminhos:
        print(str(p.resolve()))
    return 0


def cmd_video(args) -> int:
    try:
        roteiro = _carregar_valido(args.roteiro)
        proj = _projeto(args, roteiro)
        print(f"projeto: {proj.raiz}")
        final = pipeline.montar_video(roteiro, proj, motion=args.motion)
    except (RoteiroInvalido, RenderError, FileNotFoundError, RuntimeError) as exc:
        return _erro(str(exc))
    print(str(final.resolve()))
    return 0


def cmd_tudo(args) -> int:
    try:
        roteiro = _carregar_valido(args.roteiro)
        proj = _projeto(args, roteiro)
        print(f"projeto: {proj.raiz}")
        pipeline.gerar_imagens(roteiro, proj, motor=args.motor, model=args.model,
                               seguir_identidade=not args.sem_identidade)
        final = pipeline.montar_video(roteiro, proj, motion=args.motion)
    except (RoteiroInvalido, EngineError, RenderError, FileNotFoundError, OSError, RuntimeError) as exc:
        return _erro(str(exc))
    print(str(final.resolve()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fluxo_video",
        description="Fluxo LOCAL de criação de vídeo (roteiro→cenas→planos→imagens→vídeo).")
    sub = p.add_subparsers(dest="cmd", required=True)

    def _add_gen(nome, func, ajuda):
        sp = sub.add_parser(nome, help=ajuda)
        sp.add_argument("roteiro")
        sp.add_argument("--projeto", help="Pasta de saída (default: projects/<slug-do-titulo>).")
        sp.add_argument("--motor", default="anime", choices=["anime", "engine"],
                        help="anime (Illustrious/SDXL, default) | engine (Flux).")
        sp.add_argument("--model", default="flux-schnell", help="Modelo do engine Flux (flux-schnell|flux-dev).")
        sp.add_argument("--motion", default="kenburns", choices=["kenburns", "i2v"],
                        help="kenburns (câmera sobre imagem parada) | i2v (LTX-Video, a cena se move).")
        sp.add_argument("--sem-identidade", action="store_true", help="Não usa a 1ª imagem como âncora.")
        sp.set_defaults(func=func)
        return sp

    v = sub.add_parser("validar", help="Valida a congruência de um roteiro rico (gate).")
    v.add_argument("roteiro")
    v.set_defaults(func=cmd_validar)

    _add_gen("imagens", cmd_imagens, "Gera a imagem de cada plano (local_ai_engine → ComfyUI).")
    vp = _add_gen("video", cmd_video, "Monta o vídeo a partir das imagens (ffmpeg Ken Burns).")
    # 'video' não usa model/identidade, mas herdar as flags simplifica; ignoradas se passadas.
    del vp
    _add_gen("tudo", cmd_tudo, "Ponta a ponta: imagens + vídeo.")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
