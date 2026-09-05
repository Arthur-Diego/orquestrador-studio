"""[extensão] Ponte fina para o `local_ai_engine` — aciona o motor ONDE ELE ESTÁ.

Não duplica nem move o local_ai_engine: só chama o binário dele (`engine`/`anime`, na venv
dele) por subprocess para gerar a imagem de cada plano via ComfyUI local. O caminho do binário
é configurável por env (`FLUXO_ENGINE_BIN`); o default aponta para a venv do repositório vizinho.

`build_args_*` são puros (montam a linha de comando) e testáveis. `gerar_imagem` executa — com
o runner injetável para testar sem GPU.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

DEFAULT_ENGINE_DIR = "~/local_ai_engine/.venv/bin"  # diretório com os binários engine/anime


class EngineError(RuntimeError):
    """Falha ao acionar o local_ai_engine (mensagem curta, sem stacktrace cru)."""


def resolve_bin(nome: str = "engine") -> str:
    """Resolve o binário do local_ai_engine (`engine` ou `anime`).

    Env `FLUXO_ENGINE_DIR` (diretório dos binários) vence; senão a venv default; senão o PATH.
    """
    base = os.environ.get("FLUXO_ENGINE_DIR", DEFAULT_ENGINE_DIR)
    candidato = Path(base).expanduser() / nome
    if candidato.exists():
        return str(candidato)
    achado = shutil.which(nome)
    if achado:
        return achado
    raise EngineError(
        f"não encontrei o binário '{nome}' do local_ai_engine. "
        f"Ajuste FLUXO_ENGINE_DIR ou instale o motor em {DEFAULT_ENGINE_DIR}.")


def build_args_image(prompt: str, *, preset: str, model: str,
                     seed: int | None = None, steps: int | None = None) -> list[str]:
    args = ["image", prompt, "--preset", preset, "--model", model]
    if seed is not None:
        args += ["--seed", str(seed)]
    if steps:
        args += ["--steps", str(steps)]
    return args


def build_args_mood(prompt: str, ref: Path | str, *, preset: str, model: str,
                    strength: float = 0.1) -> list[str]:
    """Modo mood/referência: propaga a vibe/identidade da 1ª imagem (âncora) para os demais planos."""
    return [
        "mood", prompt, "--ref", str(ref), "--mode", "mood",
        "--strength", str(strength), "--preset", preset, "--model", model,
    ]


def build_args_anime(prompt: str, *, preset: str, ref: Path | str | None = None,
                     seed: int | None = None) -> list[str]:
    """Motor anime (Illustrious XL / SDXL). Com `ref`, usa o IPAdapter de rosto (personagem consistente)."""
    args = ["gerar", prompt, "--preset", preset]
    if ref is not None:
        args += ["--ref", str(ref), "--face"]
    if seed is not None:
        args += ["--seed", str(seed)]
    return args


#: preset default por motor (o motor anime não tem 9:16 nativo; `retrato` 2:3 é o mais vertical,
#: e o render corta para 9:16). O motor engine (Flux) tem `story` = 9:16.
PRESET_DEFAULT = {"anime": "retrato", "engine": "story"}


def _ultima_linha(texto: str) -> str:
    linhas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    return linhas[-1] if linhas else ""


def gerar_imagem(prompt: str, out_path: Path, *, motor: str = "anime",
                 preset: str | None = None, model: str = "flux-schnell",
                 seed: int | None = None, ref: Path | str | None = None,
                 bin: str | None = None, timeout: float = 600.0,
                 runner=subprocess.run) -> Path:
    """Gera a imagem de um plano chamando o local_ai_engine; copia a saída para `out_path`.

    `motor`: 'anime' (Illustrious XL/SDXL, default) ou 'engine' (Flux). `ref` (âncora de
    identidade) ativa o IPAdapter de rosto no anime, ou o modo mood no engine.
    """
    if preset is None:
        preset = PRESET_DEFAULT.get(motor, "retrato")
    if motor == "anime":
        exe = bin or resolve_bin("anime")
        args = build_args_anime(prompt, preset=preset, ref=ref, seed=seed)
    else:
        exe = bin or resolve_bin("engine")
        if ref is not None:
            args = build_args_mood(prompt, ref, preset=preset, model="flux-dev")
        else:
            args = build_args_image(prompt, preset=preset, model=model, seed=seed)
    try:
        proc = runner([exe, *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise EngineError(f"falha ao executar o engine: {exc}") from exc
    if proc.returncode != 0:
        raise EngineError(f"engine retornou {proc.returncode}: {(proc.stderr or '').strip()[:300]}")
    produzido = _ultima_linha(proc.stdout or "")
    if not produzido or not Path(produzido).exists():
        raise EngineError(f"engine não devolveu um caminho de imagem válido: {produzido!r}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(produzido, out_path)
    return out_path
