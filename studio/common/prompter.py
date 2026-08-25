"""O "bot" de prompts do curso (Abrahub Creative Engine, aulas 007/009/012), reproduzido com o
Claude CLI local (`claude -p`, assinatura do usuário, sem chave de API).

Dois modos, como o bot do instrutor:
- `from_brief`: descrição/brief → prompt profissional em inglês (câmera, lente, luz, estilo);
- `from_images`: 1–4 imagens + instrução do usuário → prompt fiel às imagens.
Fallback determinístico (`fallback_template`) quando o CLI não existe ou falha.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

BIN = shutil.which("claude")
TIMEOUT_S = 180
MAX_IMAGES = 4

# Papel do bot por tipo de prompt — o que a aula manda em cada caso.
ROLES = {
    "mood": (
        "You are a cinematic art director writing image-generation prompts (Midjourney/Higgsfield style). "
        "Task: write ONE prompt for a MOOD FRAME — the visual identity of an ad campaign: light, color palette, "
        "atmosphere, materials, textures, time of day, weather. Rules from the course: environment only — "
        "NO product, NO people, NO text, NO logos; one single vibe; photorealistic cinematic still; include camera "
        "body, lens (mm), aperture, film stock/grain and lighting setup. 60–120 words, English."
    ),
    "base": (
        "You are a cinematic art director writing image-generation prompts. Task: write ONE prompt that places the "
        "product in EXACTLY the same situation/composition as the reference image, keeping the campaign mood "
        "(light, palette, atmosphere). No people unless the reference has them. Photorealistic, camera body, lens, "
        "aperture, lighting. 60–120 words, English."
    ),
    "motion": (
        "You are a film director writing image-to-video motion prompts (Kling/Seedance style). Task: describe the "
        "subject action and the camera movement for a 5–10 s clip from the given frame: one clear action, one camera "
        "move (dolly, push-in, tracking, tilt), physics, what the last frame shows. Keep lighting and character "
        "identical to the frame. 40–90 words, English. No text, no audio."
    ),
}

OUTPUT_SPEC = (
    'Return ONLY a JSON object inside a ```json fence with keys: "prompt" (the final prompt, English), '
    '"negative" (comma-separated things to avoid, English), "camera" (camera/lens/aperture summary), '
    '"notes_pt" (2 short lines in Brazilian Portuguese explaining the choices).'
)


def available() -> bool:
    return BIN is not None


def _run(prompt: str, images: list[Path] | None = None, timeout: int = TIMEOUT_S) -> tuple[str, float]:
    """Chama `claude -p`. Com imagens, libera só a tool Read (o Claude lê os arquivos). Devolve (texto, segundos)."""
    if not BIN:
        raise RuntimeError("Claude CLI não encontrado no PATH (instale o Claude Code ou use o modo template)")
    args = [BIN, "-p", prompt, "--output-format", "text", "--max-turns", "6"]
    if images:
        args += ["--allowedTools", "Read"]
    t0 = time.time()
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Claude demorou mais de {timeout}s") from e
    if p.returncode != 0:
        raise RuntimeError(f"Claude falhou: {(p.stderr or p.stdout).strip()[-400:]}")
    return p.stdout, round(time.time() - t0, 1)


def _parse(text: str) -> dict:
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise RuntimeError("Claude não devolveu JSON: " + text.strip()[:300])
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise RuntimeError("JSON inválido do Claude: " + text.strip()[:300]) from e
    if not isinstance(data, dict) or not data.get("prompt"):
        raise RuntimeError("JSON do Claude sem 'prompt'")
    return {"prompt": str(data.get("prompt", "")).strip(), "negative": str(data.get("negative", "")).strip(),
            "camera": str(data.get("camera", "")).strip(), "notes_pt": str(data.get("notes_pt", "")).strip()}


def _brief_text(brief: dict) -> str:
    keys = [("product", "Product"), ("vibe", "Vibe"), ("purpose", "Purpose"), ("tone", "Emotional tone"),
            ("reference", "Aesthetic reference"), ("instruction", "Extra instruction from the user")]
    lines = [f"- {label}: {brief[k]}" for k, label in keys if brief.get(k)]
    return "\n".join(lines) if lines else "- (no brief given; choose a strong cinematic vibe)"


def from_brief(kind: str, brief: dict) -> dict:
    """Modo 'simplificado/guiado' do bot (aula 007): só texto."""
    role = ROLES[kind]
    text, secs = _run(f"{role}\n\nBrief:\n{_brief_text(brief)}\n\n{OUTPUT_SPEC}")
    return {**_parse(text), "source": "claude", "seconds": secs}


def from_images(kind: str, images: list[Path], instruction: str = "", brief: dict | None = None) -> dict:
    """Modo com imagem (aula 009): o bot olha a(s) imagem(ns) e escreve o prompt fiel a elas."""
    images = [Path(p) for p in images][:MAX_IMAGES]
    if not images:
        raise ValueError("informe ao menos uma imagem")
    for p in images:
        if not p.exists():
            raise FileNotFoundError(str(p))
    role = ROLES[kind]
    paths = "\n".join(f"- {p}" for p in images)
    prompt = (
        f"{role}\n\nFirst, read these image files with the Read tool and study their light, palette, atmosphere and "
        f"composition:\n{paths}\n\nThe prompt must be FAITHFUL to what these images look like (their vibe), not to "
        f"their subject.\n" + (f"User instruction (must be obeyed): {instruction}\n" if instruction else "")
        + (f"Brief:\n{_brief_text(brief)}\n" if brief else "") + f"\n{OUTPUT_SPEC}"
    )
    text, secs = _run(prompt, images)
    return {**_parse(text), "source": "claude", "seconds": secs, "images": [str(p) for p in images]}


_STYLE_VARIANTS = [
    "atmosphere and light define the mood; balanced stylization",
    "stronger stylization: bolder color contrast, more dramatic light, same palette",
    "more literal and restrained: natural light, subtle color, documentary feel",
    "wider, emptier composition; the environment breathes; same palette and light",
]


def fallback_template(kind: str, brief: dict, variation: int = 0) -> dict:
    """Template determinístico (sem Claude) — o que a etapa 2 usava antes desta feature."""
    product = brief.get("product") or "the product"
    vibe = brief.get("vibe") or "cinematic"
    hint = brief.get("hints") or ""
    style = _STYLE_VARIANTS[variation % len(_STYLE_VARIANTS)]
    if kind == "mood":
        prompt = (f"Mood frame (vibe reference) for a {product} campaign. Vibe: {vibe}. "
                  + (f"Inspired by real campaign references: {hint}. " if hint else "")
                  + f"Wide establishing shot of the environment only — {style}. "
                  "Photorealistic cinematic still, shot on RED Komodo, film grain. No product, no people, no text, no logos.")
    elif kind == "base":
        prompt = (f"The {product} placed in exactly the same situation and composition as the reference image, with the "
                  f"campaign mood ({vibe}): same light, palette and atmosphere. Photorealistic, shot on RED Komodo, "
                  "50mm, T2.8. No people unless the reference has them. No text.")
    else:
        prompt = ("Subject performs one clear action; slow cinematic camera move; keep lighting, colors and character "
                  "identical to the input frame; realistic physics; no text.")
    return {"prompt": prompt, "negative": "text, logos, watermark, extra fingers, plastic skin, oversaturated",
            "camera": "RED Komodo, film grain", "notes_pt": "Template fixo (sem Claude): ajuste à mão se precisar.",
            "source": "template", "seconds": 0.0}


MOOD_GUARDS = ("no product", "no people", "no text")


def enforce_mood_rules(result: dict) -> dict:
    """Aula 009: mood é ambiente/luz/cor. Garante os negativos mesmo se o Claude esquecer."""
    p = result.get("prompt", "")
    low = p.lower()
    missing = [g for g in MOOD_GUARDS if g not in low]
    if missing:
        result["prompt"] = p.rstrip(". ") + ". " + ", ".join(m.capitalize() for m in missing) + "."
    return result
