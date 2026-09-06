"""Catálogo de modelos da Higgsfield e tabela de custo em créditos `[extensão]`.

A aula 008 coloca o **custo** como critério principal de cada geração ("olha o preço antes de
gerar"). O curso não mantém uma tabela de preços — isto é uma extensão do Studio (ADR-016): um
catálogo único dos modelos que o Studio aciona pelo CLI, com o custo **medido** por
resolução/duração, para (a) mostrar a estimativa antes de gastar e (b) alimentar a tela
"Créditos & Custos".

Duas fontes de custo convivem, nunca se contradizem por design:
- **medida** (esta tabela): valor observado nas gerações reais, usado como referência offline e
  quando o CLI está indisponível/deslogado. Consultar a tabela **não** gasta crédito;
- **ao vivo** (`higgsfield generate cost`, em `studio.higgsfield.cost`): estimativa do próprio CLI
  no momento da geração. `generate cost` é grátis — só `generate create` cobra.

Este módulo é puro (sem rede, sem subprocess): só conhece os números. Quem chama o CLI é a ponte
`studio.higgsfield`; quem resolve o modelo default de cada ação é `studio.common.settings`.
"""
from __future__ import annotations

#: Custo medido por chave de variação (resolução de imagem ou duração de vídeo/clip). A chave
#: `"*"` é o custo fixo do modelo (upscale, música, modelos sem variação medida). Valores em
#: CRÉDITOS Higgsfield, medidos em gerações reais (pedido do dono do produto, 2026-08-27).
CATALOG: dict[str, dict] = {
    "nano_banana_2": {
        "label": "Nano Banana Pro",
        "kind": "image",
        "variants": {"1k": 2, "2k": 2, "4k": 4},
        "variant_key": "resolution",
        "variant_options": ["1k", "2k", "4k"],
        "default_variant": "2k",
        "note": "Imagem fotorrealista (Gemini 3 Pro Image). Padrão das etapas de imagem.",
    },
    "gpt_image_2": {
        "label": "GPT Image 2",
        "kind": "image",
        "variants": {"*": 8.5},
        "note": "Imagem alternativa; mais cara que a Nano Banana Pro.",
    },
    "bytedance_image_upscale": {
        "label": "Bytedance Upscale",
        "kind": "upscale",
        "variants": {"*": 2},
        "note": "Upscale 2x da imagem base (aula 009).",
    },
    "kling3_0": {
        "label": "Kling 3.0",
        "kind": "video",
        "variants": {"5s": 10, "10s": 20},
        "variant_key": "duration",
        "variant_options": ["5s", "10s"],
        "default_variant": "5s",
        "note": "Image-to-video (aula 012); transição start/end (ADR-023: é a Kling que aceita end frame). "
                "Custo por duração do clipe.",
    },
    # `[extensão]` wave 7 (ADR-021): vídeo por cena no storyboard + revert do desvio do animate.
    # Kling 2.6 = modelo das CENAS (o desvio "CLI só tem 3.0" caiu: 2.6 existe no CLI). Custo
    # medido no CLI (`higgsfield generate cost kling2_6`): 5s=10, 10s=20 créditos.
    "kling2_6": {
        "label": "Kling 2.6",
        "kind": "video",
        "variants": {"5s": 10, "10s": 20},
        "variant_key": "duration",
        "variant_options": ["5s", "10s"],
        "default_variant": "5s",
        "note": "Image-to-video (Kling 2.6). Cena do storyboard/animação; custo medido no CLI (wave 7).",
    },
    # `[extensão]` wave 7 (ADR-021): Kling 3.0 Turbo era o modelo das TRANSIÇÕES (modo start/end).
    # A ADR-023 tirou esse papel dele (o `model get` do CLI não declara `end_image` nem `mode`), mas
    # o modelo CONTINUA na tabela: é ofertável e é o que takes antigos registram. Custo medido: 5s=7,5, 10s=15.
    "kling3_0_turbo": {
        "label": "Kling 3.0 Turbo",
        "kind": "video",
        "variants": {"5s": 7.5, "10s": 15},
        "variant_key": "duration",
        "variant_options": ["5s", "10s"],
        "default_variant": "5s",
        "note": "Image-to-video rápido (transição start/end). Custo medido no CLI (wave 7).",
    },
    "seedance_2_0": {
        "label": "Seedance 2.0",
        "kind": "video",
        "variants": {"*": 22.5},
        "note": "Image-to-video alternativo; clipe mais caro.",
    },
    "veo3_1_lite": {
        "label": "Veo 3.1 Lite",
        "kind": "video",
        "variants": {"8s": 8},
        "variant_key": "duration",
        "variant_options": ["8s"],
        "default_variant": "8s",
        "note": "Image-to-video econômico, clipe de 8 s.",
    },
    "sonilo_music": {
        "label": "Sonilo Music",
        "kind": "audio",
        "variants": {"*": 0.94},
        "note": "Trilha (aula 013); custo aproximado por faixa.",
    },
    # `[extensão]` wave 11 (card #92): o reframe pago da etapa 8 (ADR-028) já grava no livro-caixa,
    # mas o modelo não existia aqui — logo a ação `export.reframe` não podia ser catalogada
    # (`settings._valid` exige `pricing.known(model)`). Família PRÓPRIA de propósito: com `kind`
    # de vídeo, `reframe` viraria opção selecionável para `animate.video` e para as duas ações de
    # vídeo do storyboard (o `<select>` do painel filtra por `kind`), permitindo config inválida.
    # `variants: {"*": None}` = modelo real do CLI SEM custo medido: os números desta tabela são
    # medições do dono do produto e não há medição de reframe (não se inventa número).
    "reframe": {
        "label": "Reframe (CLI)",
        "kind": "reframe",
        "variants": {"*": None},
        "note": "Reenquadra o master exportado (etapa 8). Sem custo medido offline: o valor vem do "
                "`generate cost` ao vivo do CLI.",
    },
}

#: Ordem das famílias na tela de custos.
KIND_ORDER = ("image", "upscale", "video", "audio", "reframe")
KIND_LABEL = {"image": "Imagem", "upscale": "Upscale", "video": "Vídeo", "audio": "Áudio",
              "reframe": "Reenquadramento"}


def known(model: str) -> bool:
    return model in CATALOG


def _norm_variant(model: str, params: dict | None) -> str | None:
    """Deriva a chave de variação (resolução/duração) a partir dos params da geração.

    Aceita `resolution`/`size` (imagem) e `duration`/`duration_seconds`/`seconds` (vídeo), com ou
    sem sufixo (`"5"`, `5`, `"5s"`). Devolve a chave existente em `variants` ou `None`.
    """
    spec = CATALOG.get(model)
    if not spec:
        return None
    variants = spec["variants"]
    if list(variants) == ["*"]:
        return "*"
    params = params or {}
    raw = None
    if spec.get("variant_key") == "resolution":
        raw = params.get("resolution") or params.get("size") or params.get("quality")
    elif spec.get("variant_key") == "duration":
        raw = params.get("duration") or params.get("duration_seconds") or params.get("seconds")
    if raw is None:
        return spec.get("default_variant")
    key = str(raw).strip().lower()
    if key in variants:
        return key
    if spec.get("variant_key") == "duration":
        digits = "".join(ch for ch in key if ch.isdigit())
        if digits and f"{digits}s" in variants:
            return f"{digits}s"
    if spec.get("variant_key") == "resolution":
        if key in ("hd", "1080", "1080p", "1k"):
            return "1k" if "1k" in variants else spec.get("default_variant")
        if key in ("2048", "2k"):
            return "2k" if "2k" in variants else spec.get("default_variant")
        if key in ("4096", "4k", "uhd"):
            return "4k" if "4k" in variants else spec.get("default_variant")
    return spec.get("default_variant")


def estimate(model: str, params: dict | None = None) -> dict:
    """Custo medido de uma geração: `{model, label, kind, variant, credits, source}`.

    `source ∈ {"measured", "unknown"}`. `credits`/`variant` = `None` quando o modelo é
    desconhecido. Não consulta o CLI (barato, offline) — é o piso mostrado quando o
    `generate cost` ao vivo não responde.
    """
    spec = CATALOG.get(model)
    if not spec:
        return {"model": model, "label": model, "kind": None, "variant": None,
                "credits": None, "source": "unknown"}
    variant = _norm_variant(model, params)
    credits = spec["variants"].get(variant) if variant else None
    return {"model": model, "label": spec["label"], "kind": spec["kind"],
            "variant": None if variant == "*" else variant, "credits": credits, "source": "measured"}


def public_model(model: str) -> dict:
    """Ficha pública de um modelo para a UI (catálogo + linhas de custo por variação)."""
    spec = CATALOG[model]
    rows = [{"variant": None if k == "*" else k, "credits": v} for k, v in spec["variants"].items()]
    return {"id": model, "label": spec["label"], "kind": spec["kind"], "note": spec.get("note", ""),
            "variant_key": spec.get("variant_key"), "variant_options": spec.get("variant_options"),
            "default_variant": None if spec.get("default_variant") in (None, "*") else spec.get("default_variant"),
            "rows": rows}


def list_models(kind: str | None = None) -> list[dict]:
    """Catálogo público, ordenado por família (imagem, upscale, vídeo, áudio) e rótulo."""
    order = {k: i for i, k in enumerate(KIND_ORDER)}
    models = [public_model(m) for m in CATALOG if kind is None or CATALOG[m]["kind"] == kind]
    return sorted(models, key=lambda m: (order.get(m["kind"], 99), m["label"]))
