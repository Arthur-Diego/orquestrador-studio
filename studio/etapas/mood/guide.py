"""Guia da etapa 2 — Mood board (aula 009). Leitura pura dos artefatos do projeto.

Textos de `what`/`checklist` conforme a auditoria de fidelidade da wave 2 (§2.4) e validações
conforme §2.5. Nada aqui força "sem produto": o mood board da aula **tem** o produto — a única
restrição que o instrutor enuncia é "não tenho nenhum interesse em pessoas", e é opcional.
"""
from __future__ import annotations

from ...common.guide import Guide, count_files, exists, read_json
from . import META

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
#: ADR-007: uma vibe só, teto de 8 imagens no mood.
MAX_SELECTED = 8
#: Stopwords de português que denunciam prompt fora do inglês (aula 007: prompt em inglês).
_PT_STOPWORDS = (" com ", " para ", " uma ", " que ", " dos ", " das ", " não ", " sem ")
#: Distância RGB média acima da qual as escolhidas "parecem moods diferentes" (aviso).
_MOOD_DISTANCE = 130.0


def _is_english(text: str) -> bool:
    """Heurística da auditoria: ≥ 90 % ASCII e sem stopwords de português."""
    if not text:
        return False
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text)
    low = f" {text.lower()} "
    return ascii_ratio >= 0.9 and not any(w in low for w in _PT_STOPWORDS)


def _hex_rgb(value: str) -> tuple[int, int, int] | None:
    v = str(value or "").lstrip("#")
    if len(v) != 6:
        return None
    try:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    except ValueError:
        return None


def _mood_distance(by_file: dict) -> float | None:
    """Distância média entre os tons dominantes das imagens escolhidas (None se não dá para saber)."""
    tones = []
    for colors in by_file.values():
        rgb = _hex_rgb((colors or [None])[0]) if isinstance(colors, list) else None
        if rgb:
            tones.append(rgb)
    if len(tones) < 2:
        return None
    pairs = [(a, b) for i, a in enumerate(tones) for b in tones[i + 1:]]
    dists = [sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) ** 0.5 for a, b in pairs]
    return sum(dists) / len(dists)


def guide(pid: str) -> dict:
    meta = read_json(pid, "project.json", default={}) or {}
    product = (meta.get("product") or "").strip()
    n_vibe = count_files(pid, "mood/vibe/candidates", IMG_EXT)
    n_selected = count_files(pid, "mood/selected", IMG_EXT)
    has_md = exists(pid, "mood/mood.md")
    palette = read_json(pid, "mood/palette.json", default={}) or {}
    history = read_json(pid, "mood/prompts.json", default=[]) or []
    last = history[0] if isinstance(history, list) and history and isinstance(history[0], dict) else {}
    refs = read_json(pid, "refs/candidates/candidates.json", default=[]) or []
    n_refs = sum(1 for c in refs if isinstance(c, dict) and c.get("selected"))

    # Wave 4: o protótipo não desenha `details.lesson` nesta tela — o texto de aula que a etapa 2
    # exibia nos três painéis vive aqui (ADR-004: o texto não se perde; a tela é que não o mostra).
    g = Guide(META).text(
        "Referências soltas geram uma campanha incoerente; ela precisa de um mood. Ache uma imagem "
        "cujo sentimento você gosta — não precisa ter a ver com o produto (a aula usou \"snow neon "
        "commercial\" no Explore do Midjourney, porque lá vem o prompt junto). A aula começa "
        "\"copiar o prompt dessa pessoa e criar ali pra mim\": se você tem esse prompt, cole-o no "
        "campo do Explore — ele vira a base e o Studio só acrescenta a estilização. Sem ele, peça "
        "ao bot um prompt com essa vibe (anexe a imagem de vibe e, se quiser, uma referência que "
        "você gostou; a aula pediu \"sem pessoas\" porque o foco é o produto — o produto em si pode "
        "aparecer, e Produto, texto e logo não são proibidos aqui: o mood da aula tem a lata). Gere "
        "um grid de 4; se saírem parecidas demais, aumente a estilização (no meio-termo: extremos "
        "alucinam); se não pegou a vibe, pegue a melhor imagem do grid como referência de estilo e "
        "gere mais 4 com o mesmo prompt. Salve as que estão no mesmo mood: esse conjunto vira o "
        "filtro de tudo o que você gerar daqui em diante. 2K e 16:9 são sugestão do Studio, não "
        "regra da aula.",
        ["Escolhi a vibe pelo sentimento, não pelo assunto",
         "Um único prompt de vibe (variações só de estilização)",
         "Evitei imagens focadas em rosto/pessoas — o produto é o foco",
         "O grid \"pegou a vibe\"? Se não, referência de estilo + mesmo prompt de novo",
         "Todas as imagens salvas estão no mesmo mood",
         "(Opcional, aula 004/009) mood board de filme para ganhar realismo"],
    )

    # Entradas. A aula encontra a vibe no Explore — referências da etapa 1 NÃO bloqueiam esta etapa.
    g.input("product", "Produto do projeto (project.json)", bool(product),
            detail=product or "sem produto — o prompt de vibe não se escreve sozinho",
            fix="Preencha o produto do projeto na barra lateral")

    g.output("selected", f"mood/selected/ com 1 a {MAX_SELECTED} imagens no mesmo mood", n_selected > 0,
             detail=f"{n_selected} imagens escolhidas")
    g.output("mood_md", "mood/mood.md com o prompt de vibe", has_md)

    # Validações (auditoria §2.5): atenção, nunca bloqueio.
    g.check("vibe_images", "Imagem de vibe importada (a vibe é encontrada, não descrita)",
            "ok" if n_vibe else "todo", detail=f"{n_vibe} em mood/vibe/",
            fix=None if n_vibe else "Traga 1 a 4 imagens do Explore/Pinterest/frame de filme")

    if not n_selected:
        g.check("selected_range", f"Entre 1 e {MAX_SELECTED} imagens escolhidas (uma vibe só)", "todo")
    else:
        g.check("selected_range", f"Entre 1 e {MAX_SELECTED} imagens escolhidas (uma vibe só)",
                "ok" if n_selected <= MAX_SELECTED else "warn", detail=f"{n_selected} imagens")

    prompts_in_md = _count_prompts(pid)
    if not has_md or not prompts_in_md:
        g.check("single_vibe", "Um único prompt de vibe no mood.md (variações só de estilização)", "todo",
                detail="mood.md ainda não existe" if not has_md
                else "nenhum prompt de origem registrado (as imagens entraram sem prompt)")
    else:
        # Original + variação de estilização contam como a MESMA vibe (aula 009); mais que isso é
        # sinal de mood board misturado.
        g.check("single_vibe", "Um único prompt de vibe no mood.md (variações só de estilização)",
                "ok" if prompts_in_md <= 2 else "warn", detail=f"{prompts_in_md} prompts registrados")

    prompt_text = str(last.get("prompt") or "")
    g.check("prompt_en", "Prompt de vibe em inglês (aula 007)",
            "todo" if not prompt_text else ("ok" if _is_english(prompt_text) else "warn"),
            detail=None if not prompt_text else prompt_text[:80])

    if last.get("mode") == "images":
        g.check("images_mode_ref", "Modo \"com imagens\": havia imagem de vibe anexada",
                "ok" if last.get("images") else "warn",
                detail=f"{len(last.get('images') or [])} anexadas")
    else:
        g.check("images_mode_ref", "Modo \"com imagens\": havia imagem de vibe anexada", "todo",
                detail="último prompt não usou imagens de vibe")

    forced = [t for t in ("no product", "no logos") if t in prompt_text.lower()]
    g.check("no_forced_negatives", "Prompt sem negativos que a aula não pede (produto/logo)",
            "todo" if not prompt_text else ("ok" if not forced else "warn"),
            detail=None if not forced else f"contém: {', '.join(forced)} — o mood da aula tem o produto")

    dist = _mood_distance(palette.get("by_file") or {})
    if not n_selected or dist is None:
        g.check("same_mood", "As escolhidas parecem do mesmo mood", "todo",
                detail=None if n_selected else "nada escolhido ainda")
    else:
        g.check("same_mood", "As escolhidas parecem do mesmo mood",
                "ok" if dist <= _MOOD_DISTANCE else "warn",
                detail=f"distância média entre os tons dominantes: {dist:.0f}")

    g.check("refs_from_step1", "Referências da etapa 1 disponíveis (contexto para a etapa 3)",
            "ok" if n_refs else "todo", detail=f"{n_refs} escolhidas na etapa 1",
            fix=None if n_refs else "Opcional aqui — a vibe pode vir do Explore")

    g.check("project_vibe", "Vibe da campanha gravada no projeto (a etapa 2 grava ao salvar)",
            "ok" if (meta.get("vibe") or "").strip() else "todo",
            detail=meta.get("vibe") or "escreva a vibe em 3 palavras ao salvar o mood")

    # `next_action` no estilo imperativo curto do protótipo (a faixa compacta desenha
    # "→ Importar o grid gerado na UI da Higgsfield e escolher até 8 no mesmo mood").
    if not product:
        proxima = None                                   # blocked: o texto padrão explica o que falta
    elif not n_selected:
        proxima = "Importar o grid gerado na UI da Higgsfield e escolher até 8 no mesmo mood"
    elif not has_md:
        proxima = "registrar o prompt de vibe no mood.md"
    else:
        proxima = "montar a imagem base do produto"
    # Sem `summary`: a faixa compacta do protótipo desta tela não tem chip extra.
    return g.build(next_action=proxima)


def _count_prompts(pid: str) -> int:
    """Quantos prompts distintos o `mood.md` registra (a aula fecha com um, no máximo dois)."""
    from ...refs.service import project_dir
    p = project_dir(pid) / "mood" / "mood.md"
    if not p.is_file():
        return 0
    try:
        text = p.read_text()
    except OSError:
        return 0
    return len({line.split("prompt:", 1)[1].strip()[:120] for line in text.splitlines() if "prompt:" in line})
