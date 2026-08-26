"""O "bot" de prompts do curso (Abrahub Creative Engine, aulas 007/009/012), reproduzido com o
Claude CLI local (`claude -p`, assinatura do usuário, sem chave de API).

Dois modos, como o bot do instrutor:
- `from_brief`: descrição/brief → prompt profissional em inglês (câmera, lente, luz, estilo);
- `from_images`: 1–4 imagens + instrução do usuário → prompt fiel às imagens.
Fallback determinístico (`fallback_template`) quando o CLI não existe ou falha.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

BIN = shutil.which("claude")
#: Modelo usado pelo bot (pedido do dono do produto: Opus 4.8). Sobrescreva com STUDIO_PROMPTER_MODEL.
MODEL = os.environ.get("STUDIO_PROMPTER_MODEL", "claude-opus-4-8")
TIMEOUT_S = 180
MAX_IMAGES = 4

#: Padrão de prompt do bot do instrutor, extraído do vídeo da aula 009: um parágrafo denso de
#: fotografia publicitária + cinco linhas técnicas. O bot deve seguir ESTA estrutura (não copiar o
#: conteúdo). Mantido literal como exemplar para o modelo.
EXAMPLE_PROMPT = (
    "Ultra-realistic commercial product photography of an energy drink can partially embedded in fresh snow, "
    "no people, no human elements. The can is centered and upright, covered with fine ice crystals, frost, and "
    "condensation droplets, emphasizing extreme cold. Surrounding environment is a snowy forest at dusk or blue "
    "hour, softly blurred in the background for depth. Strong neon lighting accents in cyan and magenta wrap "
    "around the scene and subtly reflect on the aluminum surface, creating a futuristic winter-neon aesthetic. "
    "Cinematic contrast with cool blue ambient light and vibrant neon rim lights outlining the can. Shot as "
    "high-end advertising photography, sharp focus, hyper-detailed textures, visible aluminum grain, crisp "
    "typography, realistic reflections.\n\n"
    "Camera: Canon EOS R5, 85mm lens, f/2.8, shallow depth of field, tack-sharp product focus.\n"
    "Lighting: diffused cold key light from above, neon rim lights on both sides, subtle backlight for separation.\n"
    "Composition: clean, minimal, premium, centered hero shot.\n"
    "Color grading: icy blues, teal shadows, neon cyan and pink highlights, cinematic contrast.\n"
    "Style: futuristic winter commercial, neon snow aesthetic, ultra-photorealistic, high resolution, sharp "
    "details, no illustration, no CGI look, no people."
)

#: Rótulos das linhas técnicas do padrão (na ordem).
PROMPT_SECTIONS = ("Camera:", "Lighting:", "Composition:", "Color grading:", "Style:")

PROMPT_FORMAT = (
    "FORMAT (mandatory, this is the instructor's bot pattern): the \"prompt\" value is ONE dense paragraph of "
    "high-end advertising photography (subject and its state, environment and depth, lighting accents and how they "
    "reflect on materials, cinematic contrast, 'shot as high-end advertising photography, sharp focus, "
    "hyper-detailed textures, realistic reflections'), then a blank line, then exactly these five lines in this "
    "order: 'Camera: <body, lens mm, aperture, depth of field, focus>', 'Lighting: <key, rim, back light>', "
    "'Composition: <framing>', 'Color grading: <palette, shadows, highlights, contrast>', 'Style: <look, "
    "photorealism, resolution, exclusions>'. 120–220 words in total, English. Example of the pattern (copy the "
    "STRUCTURE and level of detail, never the content):\n---\n" + EXAMPLE_PROMPT + "\n---"
)

# Papel do bot por tipo de prompt — o que a aula manda em cada caso.
ROLES = {
    # Aula 009: o mood é a VIBE (luz, cor, atmosfera). O instrutor NÃO proíbe o produto — o mood
    # board dele tem a lata ("ele já me deu inclusive o Red Bull […] Essa é a vibe"). A única
    # restrição que ele enuncia é "não tenho nenhum interesse em pessoas", e para aquela campanha:
    # por isso "no people" é opção do usuário (`no_people`), não regra do papel.
    "mood": (
        "You are a cinematic art director writing image-generation prompts (Midjourney/Higgsfield style). "
        "Task: write ONE prompt for a MOOD FRAME — the visual identity of an ad campaign: light, color palette, "
        "atmosphere, materials, textures, time of day, weather. Rules from the course: one single vibe, chosen by "
        "FEELING (it does not have to be about the product); photorealistic cinematic still. " + PROMPT_FORMAT
    ),
    "base": (
        "You are a cinematic art director writing image-generation prompts. Task: write ONE prompt that places the "
        "product in EXACTLY the same situation/composition as the reference image, keeping the campaign mood "
        "(light, palette, atmosphere). Ultra-photorealistic commercial product photography. " + PROMPT_FORMAT
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
    '"notes_pt" (2 short lines in Brazilian Portuguese explaining the choices). Inside "prompt", keep real line '
    'breaks (\\n) between the paragraph and the technical lines.'
)


def available() -> bool:
    return BIN is not None


def _run(prompt: str, images: list[Path] | None = None, timeout: int = TIMEOUT_S) -> tuple[str, float]:
    """Chama `claude -p`. Com imagens, libera só a tool Read (o Claude lê os arquivos). Devolve (texto, segundos)."""
    if not BIN:
        raise RuntimeError("Claude CLI não encontrado no PATH (instale o Claude Code ou use o modo template)")
    args = [BIN, "-p", prompt, "--model", MODEL, "--output-format", "text", "--max-turns", "6"]
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
            ("reference", "Aesthetic reference"), ("instruction", "Extra instruction from the user"),
            ("explore_prompt", "Base prompt copied by the user (preserve its subject, light and palette)"),
            ("no_people", "Hard constraint")]
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


#: Variações de "estilização" do prompt de vibe — equivalem a mexer no Stylization/Weirdness do
#: Midjourney entre um grid e outro (aula 007/009): a MESMA vibe, outro tratamento. Fonte única —
#: `studio/mood/service.py` importa daqui (antes havia uma cópia lá).
STYLE_VARIANTS = [
    "atmosphere and light define the mood; balanced stylization",
    "stronger stylization: bolder color contrast, more dramatic light, same palette",
    "more literal and restrained: natural light, subtle color, documentary feel",
    "wider, emptier composition; the environment breathes; same palette and light",
]
_STYLE_VARIANTS = STYLE_VARIANTS   # alias histórico


def _sections(vibe: str, composition: str, no_people: bool) -> str:
    """As cinco linhas técnicas do padrão do bot (`EXAMPLE_PROMPT`), para o template sem Claude."""
    style = "ultra-photorealistic, high resolution, sharp details, no illustration, no CGI look"
    if no_people:
        style += ", no people"
    return ("\n\nCamera: RED Komodo 6K, 50mm lens, T2.8, shallow depth of field, tack-sharp focus.\n"
            "Lighting: diffused key light, rim lights on both sides, subtle backlight for separation.\n"
            f"Composition: {composition}.\n"
            f"Color grading: {vibe} palette, cinematic contrast.\n"
            f"Style: {style}.")


def fallback_template(kind: str, brief: dict, variation: int = 0, no_people: bool = True) -> dict:
    """Template determinístico (sem Claude) — o que a etapa 2 usava antes desta feature.

    `no_people` reproduz a única restrição que a aula 009 enuncia ("não tenho nenhum interesse em
    pessoas") e é escolha do usuário: desmarcado, o prompt não pede nada disso. Produto, texto e
    logo **não** são proibidos — o mood board da aula tem a lata.
    """
    product = brief.get("product") or "the product"
    vibe = brief.get("vibe") or "cinematic"
    hint = brief.get("hints") or ""
    style = STYLE_VARIANTS[variation % len(STYLE_VARIANTS)]
    if kind == "mood":
        base = (brief.get("explore_prompt") or "").strip()
        if base:
            # Aula 009: "copiar o prompt dessa pessoa" (Explore) é o ponto de partida do 1º grid.
            prompt = f"{base.rstrip('. ')}. Same vibe — {style}."
        else:
            prompt = (f"Mood frame (vibe reference) for a {product} campaign. Vibe: {vibe}. "
                      + (f"Inspired by real campaign references: {hint}. " if hint else "")
                      + f"Wide establishing shot that carries the mood — {style}. "
                      "Photorealistic cinematic still, shot on RED Komodo, film grain.")
        if no_people:
            prompt += " No people."
        prompt += _sections(vibe, "wide, empty, atmosphere-first establishing shot", no_people)
    elif kind == "base":
        prompt = (f"Ultra-realistic commercial product photography of the {product} placed in exactly the same "
                  f"situation and composition as the reference image, with the campaign mood ({vibe}): same light, "
                  "palette and atmosphere. Shot as high-end advertising photography, sharp focus, hyper-detailed "
                  "textures, realistic reflections. No text.")
        prompt += _sections(vibe, "clean, minimal, premium, centered hero shot", no_people)
    else:
        prompt = ("Subject performs one clear action; slow cinematic camera move; keep lighting, colors and character "
                  "identical to the input frame; realistic physics; no text.")
    return {"prompt": prompt, "negative": "text, logos, watermark, extra fingers, plastic skin, oversaturated",
            "camera": "RED Komodo, film grain", "notes_pt": "Template fixo (sem Claude): ajuste à mão se precisar.",
            "source": "template", "seconds": 0.0}


#: O ÚNICO negativo que a aula 009 enuncia — e ainda assim como escolha da campanha ("não tenho
#: nenhum interesse em pessoas"). "no product/no text/no logos" foi removido: o mood board da aula
#: mostra o produto ("Gostei muito da noite, a lata aqui"). Nunca injete regra que a aula não ensina.
MOOD_GUARDS = ("no people",)


def enforce_mood_rules(result: dict, no_people: bool = True) -> dict:
    """Acrescenta "No people." quando o usuário pediu isso e o prompt esqueceu.

    Com `no_people=False` o prompt volta intocado: nenhuma regra entra no prompt do usuário sem
    ele ter marcado (auditoria da wave 2, item M1).
    """
    if not no_people:
        return result
    p = result.get("prompt", "")
    low = p.lower()
    missing = [g for g in MOOD_GUARDS if g not in low]
    if missing:
        result["prompt"] = p.rstrip(". ") + ". " + ", ".join(m.capitalize() for m in missing) + "."
    return result
