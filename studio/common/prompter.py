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

#: Nome de cada seção sem os dois-pontos (chave do `split_sections`).
SECTION_NAMES = tuple(s.rstrip(":") for s in PROMPT_SECTIONS)

#: Mapa de proveniência determinístico (base-prompt-provenance, FDD §1): fiel ao papel do bot da
#: base ("place the product in EXACTLY the same situation/composition as the reference image,
#: keeping the campaign mood"). Composição vem da REFERÊNCIA; luz/cor/estilo vêm do MOOD; câmera é
#: técnica. O parágrafo é a JUNÇÃO (produto da referência na vibe do mood). Não depende de o modelo
#: "explicar" nada: mapeia as linhas do formato garantido (`PROMPT_SECTIONS`).
PROVENANCE_MAP = {
    "Camera": "technical",
    "Lighting": "mood",
    "Composition": "reference",
    "Color grading": "mood",
    "Style": "mood",
}


def split_sections(prompt: str) -> dict:
    """Quebra o prompt do padrão do bot em `{"paragraph": str, "sections": {<nome>: <texto>}}`.

    O padrão é um parágrafo denso + as cinco linhas nomeadas (`Camera:`, `Lighting:`, ...). O parser
    é robusto: linha nomeada que falte simplesmente não entra em `sections`; texto solto antes da
    primeira linha nomeada é o parágrafo; continuação de uma linha nomeada gruda na última seção.
    """
    text = (prompt or "").strip()
    sections: dict[str, str] = {}
    paragraph_lines: list[str] = []
    seen_section = False
    for line in text.split("\n"):
        stripped = line.strip()
        matched = next((n for n in SECTION_NAMES if stripped.lower().startswith(n.lower() + ":")), None)
        if matched:
            seen_section = True
            sections[matched] = stripped[len(matched) + 1:].strip()
        elif not seen_section:
            paragraph_lines.append(line)
        elif sections and stripped:
            last = next(reversed(sections))
            sections[last] = (sections[last] + " " + stripped).strip()
    return {"paragraph": "\n".join(paragraph_lines).strip(), "sections": sections}


def provenance(prompt: str) -> dict:
    """Proveniência do prompt da base: `{"paragraph": str, "parts": [{label, text, from}]}`.

    `from ∈ {reference, mood, technical}` conforme `PROVENANCE_MAP`; as partes seguem a ordem em que
    as linhas aparecem no prompt (`PROMPT_SECTIONS`). Degradação graciosa: linha ausente não vira
    parte — a UI mostra o prompt inteiro + a legenda geral.
    """
    parsed = split_sections(prompt)
    parts = [
        {"label": name, "text": parsed["sections"][name], "from": PROVENANCE_MAP[name]}
        for name in SECTION_NAMES
        if name in parsed["sections"]
    ]
    return {"paragraph": parsed["paragraph"], "parts": parts}

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
    # `[extensão]` (ADR-004 / ADR-025): NENHUMA aula ensina roteiro por LLM — a aula 010 manda o
    # ALUNO escrever as ~5 cenas. Este papel é extensão opt-in aprovada no gate W3 da Wave 9: o
    # texto gerado é SUGESTÃO editável e o caminho padrão da etapa continua sendo o manual.
    "script": (
        "You are a commercial film director and screenwriter. Task: write a complete N-scene advertising video "
        "script from the given brand images (base image first, then mood frames), following the course arc "
        "(opening → discovery → action → payoff) that is given to you per scene. For each scene return: a short "
        "scene description in Brazilian Portuguese (\"text\", max 500 chars) and ONE photorealistic image prompt in "
        "English (\"image_prompt\") written as a director-of-photography briefing, in this order: subject → action → "
        "environment → camera/lens/aperture from the given rig → lighting with ONE dominant source → textures and "
        "real imperfections → color/film grade → composition + aspect ratio → fidelity block → negatives. Use "
        "EXACTLY the camera rig given below in EVERY scene (same body, same lens, same format — a commercial is shot "
        "with one rig). No contradictions between scenes: same product, same palette, same world."
    ),
    # `[extensão]` (ADR-039): biblioteca de personagem. NENHUMA aula ensina character sheet — é
    # extensão. Este papel escreve o DESCRITOR CANÔNICO de identidade: os traços que NÃO podem
    # mudar entre cenas (rosto, cabelo, roupa-assinatura, paleta), para reancorar o personagem.
    "character": (
        "You are a character designer writing a CANONICAL identity descriptor for a recurring character in an ad "
        "campaign. From the given reference image(s), write ONE dense English paragraph describing ONLY what must "
        "stay identical across every scene: face shape and features, skin tone, hair (color, length, style), eye "
        "color, signature outfit and materials, distinctive marks, and the character's color palette. Be concrete "
        "and reusable as a prompt prefix — no scene, no background, no action, no camera. 60–120 words."
    ),
}

OUTPUT_SPEC = (
    'Return ONLY a JSON object inside a ```json fence with keys: "prompt" (the final prompt, English), '
    '"negative" (comma-separated things to avoid, English), "camera" (camera/lens/aperture summary), '
    '"notes_pt" (2 short lines in Brazilian Portuguese explaining the choices). Inside "prompt", keep real line '
    'breaks (\\n) between the paragraph and the technical lines.'
)


#: Vocabulário de fidelidade comum a todo preset (TEMPLATE UNIVERSAL da skill de origem): o que
#: separa "foto" de "render". Vai para o parágrafo e para a linha `Style:` do prompt final.
PRESET_FIDELITY = (
    "hyper-detailed natural skin with visible pores, subtle imperfections and asymmetry, "
    "physically accurate light behavior, imperfect real-world details, must look like an "
    "unedited photograph, not an AI render"
)

#: Lista base de negativos anti-IA (REGRAS DE OURO da skill de origem). Cada preset recebe a
#: própria cópia — o `negative` de um preset nunca compartilha a lista com outro.
PRESET_NEGATIVE_BASE = ["plastic skin", "airbrushed look", "oversaturation", "HDR glow",
                        "extra fingers", "deformed anatomy", "CGI look", "perfect symmetry"]


def _preset(pid: str, name: str, desc_pt: str, camera: str, lens: str, fmt: str, focal: str,
            aperture: str, light: str, grade: str, *, default: bool = False) -> dict:
    entry = {"id": pid, "name": name, "desc_pt": desc_pt,
             "rig": {"camera": camera, "lens": lens, "format": fmt, "focal": focal, "aperture": aperture},
             "light": light, "grade": grade, "fidelity": PRESET_FIDELITY,
             "negative": list(PRESET_NEGATIVE_BASE)}
    if default:
        entry["default"] = True
    return entry


#: `[extensão]` — catálogo de presets de realismo cinematográfico. NENHUMA aula do curso ensina
#: presets: a feature inteira é extensão (ADR-004, gate 2 do CLAUDE.md) e é estritamente OPT-IN —
#: sem `preset` explícito nada é injetado e o texto enviado ao CLI é o mesmo de sempre.
#:
#: Os valores são a TRANSCRIÇÃO da tabela de rig presets da skill `generate_realistic_prompt_images`
#: (câmera+lente+formato+abertura, luz dominante, color grade). A skill é fonte de DESIGN-TIME: ela
#: nunca é lida em runtime nem referenciada por path — este dict é a única fonte do servidor.
REALISM_PRESETS: dict[str, dict] = {
    "documentary-street": _preset(
        "documentary-street", "Documentary Street Realism",
        "Documentário autêntico: cru, granulado, câmera na mão, contexto amplo de rua.",
        "Blackmagic Pocket 6K Pro", "Cooke S4", "Super 35", "24-35mm", "T2.8",
        "soft overcast diffused daylight, handheld feel",
        "raw, grainy, muted documentary grade, real film grain", default=True),
    "arri-natural-narrative": _preset(
        "arri-natural-narrative", "ARRI Natural Narrative",
        "Narrativa cinematográfica orgânica: pele quente e contraste suave; default seguro com pessoa.",
        "ARRI Alexa Mini LF", "Cooke S4", "Large Format", "40-50mm", "T2.0",
        "one dominant soft key, gentle fill, 1:2-1:3 ratio",
        'warm skin tones, soft contrast, gentle highlight roll-off ("Cooke look")'),
    "red-commercial-precision": _preset(
        "red-commercial-precision", "RED Commercial Precision",
        "Precisão comercial: nitidez cristalina para produto, moda e tech.",
        "RED V-Raptor", "Zeiss Supreme Prime", "Large Format", "35-50mm", "T4.0",
        "clean controlled key, crisp speculars",
        "precise color, high micro-contrast, clean punchy look"),
    "sony-venice-night": _preset(
        "sony-venice-night", "Sony Venice Night",
        "Noturno limpo: neon e interiores escuros sem ruído.",
        "Sony Venice 2", "Zeiss Supreme Prime", "Full Frame", "35mm", "T2.0",
        "practical lights only (neon, lamps), low-light dual-base ISO",
        "clean shadows, high latitude night grade"),
    "anamorphic-film-look": _preset(
        "anamorphic-film-look", "Anamorphic Film Look",
        "Widescreen épico: flares horizontais e bokeh oval (indicado p/ 2.39:1).",
        "ARRI Alexa Mini LF", "Hawk V-Lite Anamorphic", "Large Format", "40mm", "T2.2",
        "key with horizontal blue flares allowed",
        "filmic grade, oval bokeh, edge distortion"),
}


def preset_block(preset_id: str) -> str:
    """Instrução em inglês (< 80 palavras) que amarra o preset às linhas técnicas já existentes.

    Uma única linha, de propósito: o bloco manda PREENCHER `Camera:`/`Lighting:`/`Color grading:`/
    `Style:` do padrão do bot, nunca criar seção nova — `split_sections`/`provenance` continuam
    vendo as mesmas cinco linhas. `KeyError` para id desconhecido (os routers convertem em 422).
    """
    p = REALISM_PRESETS[preset_id]
    r = p["rig"]
    return (
        f"REALISM PRESET (mandatory): Camera: line = {r['camera']}, {r['lens']}, {r['format']}, "
        f"{r['focal']}, {r['aperture']}. Lighting: line = {p['light']} as dominant source. "
        f"Color grading: line = {p['grade']}. Paragraph and Style: line must carry: {p['fidelity']}."
    )


def valid_preset(preset: str | None) -> str | None:
    """Valida um id de preset vindo do cliente. `None` = "sem preset" (sempre aceito).

    Fonte única de verdade é `REALISM_PRESETS`: nenhum router ou serviço mantém uma segunda lista
    de ids à mão. O `ValueError` vira 422 nos bodies de geração — antes de qualquer chamada ao CLI.
    """
    if preset is not None and preset not in REALISM_PRESETS:
        raise ValueError(f"preset desconhecido: {preset} — válidos: {', '.join(REALISM_PRESETS)}")
    return preset


def _role_text(kind: str, preset: str | None) -> str:
    """Papel do bot + bloco do preset. Sem preset, devolve o papel intocado (invariante do gate W3:
    o texto enviado ao CLI fica byte-idêntico ao de antes desta extensão)."""
    role = ROLES[kind]
    return f"{role}\n\n{preset_block(preset)}" if preset else role


def _with_preset(result: dict, preset: str | None) -> dict:
    """Acrescenta `"preset"` ao retorno e mescla os negativos do preset no campo `negative`.

    Sem preset, `negative` sai exatamente como o CLI devolveu. Com preset, os termos do catálogo
    entram no fim, sem duplicar o que o Claude já pediu para evitar (comparação case-insensitive).
    """
    if preset:
        items = [t.strip() for t in (result.get("negative") or "").split(",") if t.strip()]
        seen = {t.lower() for t in items}
        for term in REALISM_PRESETS[preset]["negative"]:
            if term.lower() not in seen:
                items.append(term)
                seen.add(term.lower())
        result["negative"] = ", ".join(items)
    return {**result, "preset": preset}


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


def from_brief(kind: str, brief: dict, preset: str | None = None) -> dict:
    """Modo 'simplificado/guiado' do bot (aula 007): só texto.

    `preset` (`[extensão]`, opt-in) injeta o bloco de realismo logo depois do papel; com `None` o
    prompt enviado ao CLI é byte-idêntico ao de antes da extensão.
    """
    role = _role_text(kind, preset)
    text, secs = _run(f"{role}\n\nBrief:\n{_brief_text(brief)}\n\n{OUTPUT_SPEC}")
    return _with_preset({**_parse(text), "source": "claude", "seconds": secs}, preset)


def from_images(kind: str, images: list[Path], instruction: str = "", brief: dict | None = None,
                preset: str | None = None) -> dict:
    """Modo com imagem (aula 009): o bot olha a(s) imagem(ns) e escreve o prompt fiel a elas."""
    images = [Path(p) for p in images][:MAX_IMAGES]
    if not images:
        raise ValueError("informe ao menos uma imagem")
    for p in images:
        if not p.exists():
            raise FileNotFoundError(str(p))
    role = _role_text(kind, preset)
    paths = "\n".join(f"- {p}" for p in images)
    prompt = (
        f"{role}\n\nFirst, read these image files with the Read tool and study their light, palette, atmosphere and "
        f"composition:\n{paths}\n\nThe prompt must be FAITHFUL to what these images look like (their vibe), not to "
        f"their subject.\n" + (f"User instruction (must be obeyed): {instruction}\n" if instruction else "")
        + (f"Brief:\n{_brief_text(brief)}\n" if brief else "") + f"\n{OUTPUT_SPEC}"
    )
    text, secs = _run(prompt, images)
    return _with_preset({**_parse(text), "source": "claude", "seconds": secs,
                         "images": [str(p) for p in images]}, preset)


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


def _sections(vibe: str, composition: str, no_people: bool, preset: str | None = None) -> str:
    """As cinco linhas técnicas do padrão do bot (`EXAMPLE_PROMPT`), para o template sem Claude.

    Com `preset` (`[extensão]`), o rig/luz/grade do catálogo substituem as strings fixas; sem
    preset, o texto é o mesmo desde sempre (os testes do template fixam essas strings).
    """
    style = "ultra-photorealistic, high resolution, sharp details, no illustration, no CGI look"
    if no_people:
        style += ", no people"
    camera = "RED Komodo 6K, 50mm lens, T2.8, shallow depth of field, tack-sharp focus"
    lighting = "diffused key light, rim lights on both sides, subtle backlight for separation"
    grading = f"{vibe} palette, cinematic contrast"
    if preset:
        p = REALISM_PRESETS[preset]
        r = p["rig"]
        camera = (f"{r['camera']}, {r['lens']}, {r['format']}, {r['focal']}, {r['aperture']}, "
                  "shallow depth of field, tack-sharp focus")
        lighting = p["light"]
        grading = f"{p['grade']}, {vibe} palette"
    return (f"\n\nCamera: {camera}.\n"
            f"Lighting: {lighting}.\n"
            f"Composition: {composition}.\n"
            f"Color grading: {grading}.\n"
            f"Style: {style}.")


def fallback_template(kind: str, brief: dict, variation: int = 0, no_people: bool = True,
                      preset: str | None = None) -> dict:
    """Template determinístico (sem Claude) — o que a etapa 2 usava antes desta feature.

    `no_people` reproduz a única restrição que a aula 009 enuncia ("não tenho nenhum interesse em
    pessoas") e é escolha do usuário: desmarcado, o prompt não pede nada disso. Produto, texto e
    logo **não** são proibidos — o mood board da aula tem a lata.

    `preset` (`[extensão]`) só é aplicado quando pedido explicitamente: preenche as linhas
    `Camera:`/`Lighting:`/`Color grading:` com o rig do catálogo. Com `None`, o template é o do
    curso, sem uma vírgula de diferença. Em `motion` não há linhas técnicas — preset não se aplica.
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
        prompt += _sections(vibe, "wide, empty, atmosphere-first establishing shot", no_people, preset)
    elif kind == "base":
        prompt = (f"Ultra-realistic commercial product photography of the {product} placed in exactly the same "
                  f"situation and composition as the reference image, with the campaign mood ({vibe}): same light, "
                  "palette and atmosphere. Shot as high-end advertising photography, sharp focus, hyper-detailed "
                  "textures, realistic reflections. No text.")
        prompt += _sections(vibe, "clean, minimal, premium, centered hero shot", no_people, preset)
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


# --------------------------------------------------------------------------------------------
# Roteiro de storyboard por LLM `[extensão]` — ADR-025 (aprovada no gate W3 da Wave 9), ADR-004.
#
# Caminho INDEPENDENTE do prompt único: papel próprio (`ROLES["script"]`), output spec próprio
# (`SCRIPT_OUTPUT_SPEC`), parser próprio (`_parse_script`) e timeout próprio. Nada aqui toca
# `_parse`/`PROMPT_FORMAT`/`split_sections`/`provenance` — o formato de 5 linhas do prompt único
# (base-prompt-provenance) continua exatamente como estava.
# --------------------------------------------------------------------------------------------

#: Um roteiro de até 10 cenas com imagens demora mais que um prompt só: teto próprio, entre o do
#: prompter (`TIMEOUT_S` = 180, inalterado) e o dos jobs pagos (600).
SCRIPT_TIMEOUT_S = 300

#: `[extensão]` roteiro-por-cena (ADR-028) — quantas fotos uma cena pede é INFERIDO pelo modelo a
#: partir da descrição da cena, entre estes limites. Uma cena simples (um plano, um gesto) pede o
#: piso; uma cena densa (várias ações/beats) pede mais. O modelo devolve `shots` (o número que ele
#: sugere) e `shot_prompts` (um `image_prompt` por foto, coeso DENTRO da cena). O servidor apenas
#: normaliza para esta faixa — não escolhe o número.
SHOTS_MIN = 3
SHOTS_MAX = 6

SCRIPT_OUTPUT_SPEC = (
    'Return ONLY a JSON object inside a ```json fence, with exactly these keys: "scenes" (array, one entry per '
    'scene, in order) and "notes_pt" (2 short lines in Brazilian Portuguese about the narrative choices). Each '
    'entry of "scenes" is an object with: "n" (scene number, integer), "arc" (the arc id given for that scene), '
    '"text" (the scene description in Brazilian Portuguese, max 500 chars), '
    f'"shots" (an integer between {SHOTS_MIN} and {SHOTS_MAX}: how many photos THIS scene needs to be told well '
    '— judge it from the scene description, a simple single-action scene needs fewer, a scene with several beats '
    'or camera moves needs more), "shot_prompts" (array of EXACTLY "shots" full director-of-photography briefings, '
    'English, one single paragraph each; they must be VISUALLY COHERENT with one another — same location, product, '
    'palette, light and world within the scene, differing only in the moment, framing or camera angle so the '
    'photos read as one continuous scene), "image_prompt" (the first entry of "shot_prompts", kept for '
    'compatibility) and "negative" (comma-separated things to avoid, English). No prose outside the fence, no '
    'extra keys, no missing scene.'
)

#: Ajuste de formato por modelo alvo (R10): o id NÃO é validado aqui — quem tem o catálogo
#: (`SCRIPT_MODELS`) é o serviço da etapa 4, que devolve 422 antes de chamar o CLI.
SCRIPT_MODEL_HINTS = {
    "nano_banana_2": (
        "Target image model: Nano Banana Pro (Gemini 3 Pro Image). It follows long technical descriptions "
        "literally, so write each \"image_prompt\" as a LONG, densely specified paragraph (about 90–150 words) in "
        "natural English prose — explicit camera body, lens, aperture, light direction and quality, surface "
        "textures, grade and composition. Never use tags, weights or parameter syntax."
    ),
}
_SCRIPT_MODEL_HINT_FALLBACK = (
    "Target image model: unknown. Write each \"image_prompt\" as a self-contained paragraph of natural English "
    "prose, technical but readable, with no tags, weights or parameter syntax."
)


def script_preset_block(preset_id: str) -> str:
    """Bloco de rig do ROTEIRO: o `preset_block` da provedora + o que o formato por cena exige.

    `preset_block` fala das cinco linhas técnicas do prompt único (`Camera:`, `Lighting:`, ...), que
    o roteiro não usa — daí a ressalva explícita aqui. O resto é o mesmo catálogo: corpo, lente,
    formato, focal/abertura, luz dominante, grade, fidelidade e negativos. A provedora fica intocada
    (`KeyError` para id desconhecido continua vindo dela).
    """
    p = REALISM_PRESETS[preset_id]
    r = p["rig"]
    return (
        f"{preset_block(preset_id)}\n"
        "SCRIPT FORMAT NOTE: the script has no named technical lines — fold the values above into the prose of "
        "every scene's \"image_prompt\", in the briefing order.\n"
        f"MANDATORY RIG, IDENTICAL IN EVERY SCENE: camera body {r['camera']}, lens {r['lens']}, "
        f"format {r['format']}, focal length {r['focal']}, aperture {r['aperture']} — write these words "
        f"literally in the camera part of each \"image_prompt\".\n"
        f"Dominant light: {p['light']}. Color grade: {p['grade']}.\n"
        f"Fidelity block (every scene): {p['fidelity']}.\n"
        f"Negatives (end of every \"image_prompt\" and in the \"negative\" field): {', '.join(p['negative'])}."
    )


def _normalize_shots(item: dict, image_prompt: str, scene_no: int) -> tuple[int, list[str]]:
    """`[extensão]` roteiro-por-cena (ADR-028): normaliza `shots`/`shot_prompts` de uma cena.

    O modelo INFERE quantas fotos a cena pede; o servidor só ajusta à faixa `SHOTS_MIN..SHOTS_MAX`
    e garante coerência entre `shots` e o número de prompts, SEM inventar conteúdo:

    - `shot_prompts` presente e não vazio → é a fonte da verdade; `shots` passa a ser o tamanho da
      lista (limitado ao teto), e um `shots` do modelo em desacordo é ignorado.
    - `shot_prompts` ausente → a cena vira uma foto só, o `image_prompt` já validado (compat: o
      caminho antigo, uma foto por cena, continua idêntico).

    O piso NÃO cria fotos que o modelo não escreveu (isso seria inventar, proibido pela §6 do FDD):
    um `shots` sugerido acima do que veio em `shot_prompts` é reduzido ao que existe. Prompts vazios
    na lista são descartados; se sobrar nada, cai no `image_prompt`.
    """
    raw = item.get("shot_prompts")
    prompts = [str(p).strip() for p in raw if str(p).strip()] if isinstance(raw, list) else []
    if not prompts:
        return 1, [image_prompt]
    prompts = prompts[:SHOTS_MAX]
    return len(prompts), prompts


def _parse_script(text: str, count: int, arcs: list[str] | None = None) -> dict:
    """Parser do roteiro: JSON da fence → `{"scenes": [...], "notes_pt": str}` validado e normalizado.

    Nunca completa o que falta (decisão da seção 6 do FDD: sem fonte não se inventa) — resposta
    incompleta ou malformada vira `RuntimeError`, que o job da etapa traduz em `state: "error"`.
    Cenas a MAIS são cortadas em `count`; `n` é renumerado 1..count na ordem recebida e `arc` vem
    da lista do servidor (`scene_arc`), nunca da escolha do modelo. `shots`/`shot_prompts` são
    normalizados por `_normalize_shots` (ADR-028); `image_prompt` continua sendo a primeira foto.
    """
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise RuntimeError("Claude não devolveu JSON do roteiro: " + text.strip()[:300])
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise RuntimeError("JSON inválido do Claude (roteiro): " + text.strip()[:300]) from e
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
        raise RuntimeError("JSON do roteiro sem a lista 'scenes'")
    raw = data["scenes"]
    if len(raw) < count:
        raise RuntimeError(f"roteiro incompleto: {count} cenas pedidas, {len(raw)} recebidas")
    arcs = list(arcs or [])
    scenes = []
    for i, item in enumerate(raw[:count]):
        if not isinstance(item, dict):
            raise RuntimeError(f"cena {i + 1} do roteiro não é um objeto JSON")
        scene_text = str(item.get("text") or "").strip()
        image_prompt = str(item.get("image_prompt") or "").strip()
        if not scene_text:
            raise RuntimeError(f"cena {i + 1} do roteiro sem 'text'")
        if not image_prompt:
            raise RuntimeError(f"cena {i + 1} do roteiro sem 'image_prompt'")
        arc = arcs[i] if i < len(arcs) else str(item.get("arc") or "").strip()
        shots, shot_prompts = _normalize_shots(item, image_prompt, i + 1)
        scenes.append({"n": i + 1, "arc": arc, "text": scene_text,
                       "image_prompt": shot_prompts[0], "shots": shots, "shot_prompts": shot_prompts,
                       "negative": str(item.get("negative") or "").strip()})
    return {"scenes": scenes, "notes_pt": str(data.get("notes_pt") or "").strip()}


def script(images: list[Path], brief: dict, preset: str | None = None, count: int = 5,
           arcs: list[str] | None = None, model_target: str = "nano_banana_2") -> dict:
    """Roteiro completo de `count` cenas pelo Claude CLI (`[extensão]`, ADR-025 + ADR-028).

    Cada cena volta com `text` em pt-BR, um número `shots` de fotos INFERIDO pelo modelo a partir da
    descrição (faixa `SHOTS_MIN..SHOTS_MAX`, ADR-028) e uma lista `shot_prompts` coesa dentro da cena
    (inglês, formato briefing de diretor de fotografia). `image_prompt` continua sendo a primeira
    foto, para o caminho de uma foto por cena não mudar. Com `preset`, o rig do catálogo (corpo +
    lente + formato) é obrigatório em TODAS as cenas e fotos — é o que o critério `[cross-feature]`
    da wave cobra. Com `preset=None`, nenhum bloco de rig entra no prompt.

    `arcs` é o arco de cada cena calculado pelo SERVIDOR (`scene_arc`), não pelo modelo.
    `model_target` só ajusta o formato pedido; a validação do id é do serviço da etapa 4
    (`SCRIPT_MODELS`). Sem CLI, `_run` levanta `RuntimeError` (o job traduz em 409/erro).
    """
    images = [Path(p) for p in images][:MAX_IMAGES]
    for p in images:
        if not p.exists():
            raise FileNotFoundError(str(p))
    arcs = list(arcs or [])
    plan = "\n".join(f"- scene {i + 1}: arc = {arcs[i]}" if i < len(arcs) else f"- scene {i + 1}"
                     for i in range(count))
    parts = [ROLES["script"]]
    if preset:
        parts.append(script_preset_block(preset))
    if images:
        paths = "\n".join(f"- {p}" for p in images)
        parts.append("First, read these brand reference image files with the Read tool (the base image comes first, "
                     "then any chosen storyboard shots, then mood frames) and keep the product, palette, light and "
                     f"atmosphere of the script faithful to them:\n{paths}")
    parts.append(f"Write EXACTLY {count} scenes. Arc of each scene (decided by the server, keep it as given):\n{plan}")
    parts.append(f"Brief:\n{_brief_text(brief)}")
    parts.append(SCRIPT_MODEL_HINTS.get(model_target, _SCRIPT_MODEL_HINT_FALLBACK))
    parts.append(SCRIPT_OUTPUT_SPEC)
    text, secs = _run("\n\n".join(parts), images, timeout=SCRIPT_TIMEOUT_S)
    parsed = _parse_script(text, count, arcs)
    return {**parsed, "source": "claude", "seconds": secs, "preset": preset,
            "model_target": model_target, "count": len(parsed["scenes"]),
            "images": [str(p) for p in images]}
