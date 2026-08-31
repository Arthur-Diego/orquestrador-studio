"""Pré-roteiro e prompt realista via Claude (aulas 010/011) — `[extensão]` (ADR-018).

Dois usos do Claude CLI (assinatura do usuário, sem chave de API), ambos GRÁTIS:

1. `generate_prescript`: olha a imagem-base + as fotos-semente do 1º multishot e propõe a lista
   ORDENADA de cenas em texto, no arco começo → descoberta → ação → desfecho (editável).
2. `realistic_prompt`: para uma cena + a foto-semente escolhida, gera o prompt fotorrealista
   chamando a skill `/generate_realistic_prompt_images` em modo headless, com as escolhas fixadas
   (modelo = Nano Banana Pro, rig = Auto, aspect = do projeto) para não travar. Parseia a saída;
   se o Claude falhar, cai no método embutido (`common/prompter.from_images`).

Fallbacks determinísticos garantem que a etapa funciona mesmo sem o Claude CLI no PATH.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from . import prompter

#: Reusa o binário e o modelo do bot de prompts (Opus 4.8 por default; STUDIO_PROMPTER_MODEL).
BIN = prompter.BIN
MODEL = prompter.MODEL
TIMEOUT_S = 240
MAX_SEED_IMAGES = 4

#: Arco narrativo das aulas 010/011: começo → descoberta → ação → desfecho.
ARC = [
    {"id": "comeco", "label": "Começo"},
    {"id": "descoberta", "label": "Descoberta"},
    {"id": "acao", "label": "Ação"},
    {"id": "desfecho", "label": "Desfecho"},
]
MIN_SCENES, MAX_SCENES, DEFAULT_SCENES = 3, 10, 4


def available() -> bool:
    return BIN is not None


def arc_for(n: int, total: int) -> dict:
    """A fase do arco da cena `n` (1-based) numa sequência de `total` cenas."""
    if total <= 0:
        return ARC[0]
    idx = min(len(ARC) - 1, int((n - 1) * len(ARC) / total))
    return ARC[idx]


def _run(args: list[str], timeout: int) -> str:
    if not BIN:
        raise RuntimeError("Claude CLI não encontrado no PATH")
    p = subprocess.run([BIN, *args], capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"Claude falhou: {(p.stderr or p.stdout).strip()[-400:]}")
    return p.stdout


# ---------- pré-roteiro ----------
def _fallback_prescript(product: str, vibe: str, n: int) -> dict:
    """Pré-roteiro determinístico (sem Claude): uma cena por fase do arco, em pt-BR."""
    n = max(MIN_SCENES, min(MAX_SCENES, n or DEFAULT_SCENES))
    prod = product or "o produto"
    templates = [
        ("Abertura", f"Plano de abertura que apresenta o mundo da campanha e a vibe ({vibe or 'cinematográfica'}), ainda sem revelar {prod}."),
        ("Descoberta", f"{prod} aparece em cena e desperta o interesse; a atenção do público se volta para ele."),
        ("Ação", f"{prod} em uso/movimento no auge da energia da campanha — o momento mais marcante."),
        ("Desfecho", f"Plano final de marca: {prod} em destaque, fechando com a assinatura visual da vibe."),
    ]
    scenes = []
    for i in range(1, n + 1):
        arc = arc_for(i, n)
        base = templates[min(len(templates) - 1, [a["id"] for a in ARC].index(arc["id"]))]
        scenes.append({"title": base[0], "text": base[1], "arc": arc["id"]})
    return {"scenes": scenes, "source": "template"}


def generate_prescript(base_path: Path, seed_paths: list[Path], product: str = "", vibe: str = "",
                       n_scenes: int = DEFAULT_SCENES, aspect_ratio: str = "16:9") -> dict:
    """Propõe a lista ordenada de cenas a partir da base + fotos-semente. `{scenes:[{title,text,arc}], source}`.

    `source ∈ {"claude","template"}`. Nunca levanta: sem Claude/parse, cai no template.
    """
    n = max(MIN_SCENES, min(MAX_SCENES, n_scenes or DEFAULT_SCENES))
    imgs = [Path(p) for p in ([base_path] + list(seed_paths)) if p and Path(p).exists()][:MAX_SEED_IMAGES]
    if not available() or not imgs:
        return _fallback_prescript(product, vibe, n)
    paths = "\n".join(f"- {p}" for p in imgs)
    arc_ids = " → ".join(a["label"] for a in ARC)
    prompt = (
        "You are a creative director writing the shot list (pré-roteiro) of a short AI video ad. "
        f"First, read these reference images with the Read tool (the base image and seed frames):\n{paths}\n\n"
        f"Propose EXACTLY {n} scenes, in order, following the narrative arc: {arc_ids} "
        "(começo → descoberta → ação → desfecho). Each scene is one shot described in Brazilian "
        f"Portuguese. Product: {product or '—'}. Vibe: {vibe or '—'}. Aspect: {aspect_ratio}. "
        "Keep the same visual identity as the images. "
        'Return ONLY a JSON object inside a ```json fence: '
        '{"scenes":[{"title":"<curto, pt-BR>","text":"<1-2 frases descrevendo o plano, pt-BR>",'
        '"arc":"comeco|descoberta|acao|desfecho"}]}. No prose outside the fence.'
    )
    try:
        out = _run(["-p", prompt, "--model", MODEL, "--output-format", "text",
                    "--allowedTools", "Read", "--max-turns", "6"], TIMEOUT_S)
        data = _parse_json(out)
        scenes = data.get("scenes") if isinstance(data, dict) else None
        if not isinstance(scenes, list) or not scenes:
            return _fallback_prescript(product, vibe, n)
        clean = []
        for i, s in enumerate(scenes[:MAX_SCENES], 1):
            if not isinstance(s, dict):
                continue
            arc = s.get("arc") if s.get("arc") in {a["id"] for a in ARC} else arc_for(i, len(scenes))["id"]
            clean.append({"title": str(s.get("title") or f"Cena {i}").strip()[:80],
                          "text": str(s.get("text") or "").strip()[:500], "arc": arc})
        return {"scenes": clean or _fallback_prescript(product, vibe, n)["scenes"], "source": "claude"}
    except Exception:  # noqa: BLE001 — qualquer falha cai no template
        return _fallback_prescript(product, vibe, n)


# ---------- prompt realista via skill ----------
def realistic_prompt(scene_text: str, photo_path: Path, aspect_ratio: str = "16:9",
                     product: str = "") -> dict:
    """Prompt fotorrealista da cena via skill `/generate_realistic_prompt_images` (Opção A).

    Escolhas fixadas (modelo=Nano Banana Pro, rig=Auto, aspect=projeto) e "não pergunte nada" para
    rodar headless. Parseia o prompt em prosa + negativos; se o Claude falhar, cai no método
    embutido (`prompter.from_images("base", ...)`). `{prompt, negative, source, seconds}`;
    `source ∈ {"skill","fallback","template"}`.
    """
    photo_path = Path(photo_path)
    scene_text = (scene_text or "").strip() or "the product in the campaign scene"
    if available() and photo_path.exists():
        instr = (
            f"/generate_realistic_prompt_images {scene_text}. Use the photo at {photo_path} as the "
            f"exact reference (keep the subject and identity from that photo). Fixed choices — do NOT "
            f"ask any questions, use these: modelo=Nano Banana Pro, rig=Auto, aspect={aspect_ratio}"
            + (f", product={product}" if product else "") + ". Read the photo, then output the final "
            "English prompt (prose) and its JSON version."
        )
        try:
            t0 = time.time()
            out = _run(["-p", instr, "--model", MODEL, "--output-format", "text",
                        "--allowedTools", "Read", "--max-turns", "8"], TIMEOUT_S)
            prose, negative = _parse_skill(out)
            if prose and len(prose.split()) >= 20:
                return {"prompt": prose, "negative": negative, "source": "skill",
                        "seconds": round(time.time() - t0, 1)}
        except Exception:  # noqa: BLE001 — cai no método embutido
            pass
    # Fallback embutido: o próprio bot de prompts da base, olhando a foto.
    try:
        res = prompter.from_images("base", [photo_path], scene_text)
        return {"prompt": res.get("prompt", ""), "negative": res.get("negative", ""),
                "source": "fallback", "seconds": res.get("seconds", 0.0)}
    except Exception:  # noqa: BLE001 — sem Claude nenhum: template determinístico
        res = prompter.fallback_template("base", {"product": product, "vibe": ""})
        return {"prompt": res.get("prompt", ""), "negative": res.get("negative", ""),
                "source": "template", "seconds": 0.0}


# ---------- parsers ----------
def _parse_json(text: str):
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _parse_skill(text: str) -> tuple[str, str]:
    """Extrai (prompt em prosa, negativos) da saída da skill. Prosa = 1º bloco cercado não-JSON;
    negativos = campo `negative` do bloco ```json, se houver."""
    blocks = re.findall(r"```(\w*)\s*\n(.*?)```", text, re.S)
    prose, negative = None, ""
    for lang, body in blocks:
        if lang.lower() == "json":
            try:
                data = json.loads(body)
                neg = data.get("negative")
                if isinstance(neg, list):
                    negative = ", ".join(str(x) for x in neg)
                elif isinstance(neg, str):
                    negative = neg
                if prose is None and isinstance(data.get("prompt"), str):
                    prose = data["prompt"].strip()
            except json.JSONDecodeError:
                pass
        elif prose is None and body.strip():
            prose = body.strip()
    if not prose:
        # sem blocos cercados: usa o texto inteiro, sem cabeçalhos markdown
        prose = "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("#")).strip()
    return prose, negative
