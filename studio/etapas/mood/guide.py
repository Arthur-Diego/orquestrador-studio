"""Guia da etapa 2 — Mood board (aula 009). Leitura pura dos artefatos do projeto.

**A criação de mood boards migrou para a biblioteca global** (ADR-014, que estende a ADR-013/
ADR-007). A etapa 2 agora só ESCOLHE um board da biblioteca e o aplica à campanha (`pull_board`).
O texto de aula (achar a vibe pelo sentimento, grid de 4, teto de 8) continua aqui como CONTEXTO,
mas a ação desta etapa é escolher da biblioteca — por isso saíram as checagens de "gerar prompt/
importar grid". `done` = há mood aplicado (`mood/selected` não vazio).
"""
from __future__ import annotations

from ...common.guide import Guide, count_files, read_json
from . import META

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
#: ADR-007: uma vibe só, teto de 8 imagens no mood.
MAX_SELECTED = 8
#: Distância RGB média acima da qual as escolhidas "parecem moods diferentes" (aviso).
_MOOD_DISTANCE = 130.0


def _hex_rgb(value: str) -> tuple[int, int, int] | None:
    v = str(value or "").lstrip("#")
    if len(v) != 6:
        return None
    try:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    except ValueError:
        return None


def _mood_distance(by_file: dict) -> float | None:
    """Distância média entre os tons dominantes das imagens aplicadas (None se não dá para saber)."""
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
    n_selected = count_files(pid, "mood/selected", IMG_EXT)
    palette = read_json(pid, "mood/palette.json", default={}) or {}
    refs = read_json(pid, "refs/candidates/candidates.json", default=[]) or []
    n_refs = sum(1 for c in refs if isinstance(c, dict) and c.get("selected"))

    # Wave 4/etapa2-pick: a tela não cria mood — escolhe da biblioteca. O texto de aula que a etapa
    # exibia nos painéis de criação vive aqui como contexto (ADR-004: o conhecimento não se perde).
    g = Guide(META).text(
        "A etapa 2 agora só ESCOLHE um mood board pronto da biblioteca global e o aplica a esta "
        "campanha — a criação e a curadoria de moods migraram para a tela \"Mood boards\". Escolha "
        "o board cuja vibe você quer para a campanha inteira e clique em \"Aplicar a esta "
        "campanha\": as imagens dele são copiadas para o mood da campanha (mood/selected) e viram "
        "o filtro de tudo o que você gerar daqui em diante. Continua valendo o modelo da aula 009: "
        "uma vibe só por campanha (ADR-007) — o board é a semente e não some da biblioteca ao ser "
        "aplicado (a cópia é independente). Ainda não tem nenhum board? Crie um na biblioteca: a "
        "vibe é encontrada numa imagem cujo sentimento você gosta (não descrita do zero), você "
        "importa um grid e escolhe as imagens no mesmo mood — depois volte aqui para aplicá-lo. "
        "Produto, texto e logo não são proibidos no mood (o mood da aula tem a lata); a única "
        "restrição que a aula enuncia é \"sem pessoas\", e é opcional.",
        ["Escolhi um mood board da biblioteca e apliquei à campanha",
         "A vibe do board é a que eu quero para a campanha inteira (uma vibe só)",
         "As imagens aplicadas estão em mood/selected — o filtro das próximas etapas",
         "Sem board ainda? Crie e cure na biblioteca global e volte para aplicar",
         "(Contexto da aula: a vibe é encontrada pelo sentimento, não descrita do zero)"],
    )

    # Entrada: o produto da campanha (a etapa 3 precisa dele). Referências da etapa 1 NÃO bloqueiam.
    g.input("product", "Produto do projeto (project.json)", bool(product),
            detail=product or "sem produto — defina o produto da campanha",
            fix="Preencha o produto do projeto na barra lateral")

    g.output("selected", f"mood/selected/ com 1 a {MAX_SELECTED} imagens (aplicadas de um board)",
             n_selected > 0, detail=f"{n_selected} imagens aplicadas")

    # Validações (atenção, nunca bloqueio).
    if not n_selected:
        g.check("selected_range", f"Um mood board aplicado (1 a {MAX_SELECTED} imagens)", "todo",
                detail="nenhum mood aplicado — escolha um board da biblioteca")
    else:
        g.check("selected_range", f"Um mood board aplicado (1 a {MAX_SELECTED} imagens)",
                "ok" if n_selected <= MAX_SELECTED else "warn", detail=f"{n_selected} imagens")

    dist = _mood_distance(palette.get("by_file") or {})
    if not n_selected or dist is None:
        g.check("same_mood", "As imagens aplicadas parecem do mesmo mood", "todo",
                detail=None if n_selected else "nada aplicado ainda")
    else:
        g.check("same_mood", "As imagens aplicadas parecem do mesmo mood",
                "ok" if dist <= _MOOD_DISTANCE else "warn",
                detail=f"distância média entre os tons dominantes: {dist:.0f}")

    g.check("refs_from_step1", "Referências da etapa 1 disponíveis (contexto para a etapa 3)",
            "ok" if n_refs else "todo", detail=f"{n_refs} escolhidas na etapa 1",
            fix=None if n_refs else "Opcional aqui — a vibe vem do mood board")

    g.check("project_vibe", "Vibe da campanha gravada no projeto (aplicar um board com vibe grava)",
            "ok" if (meta.get("vibe") or "").strip() else "todo",
            detail=meta.get("vibe") or "aplique um board com vibe para gravar a vibe da campanha")

    # `next_action` no estilo imperativo curto do protótipo.
    if not product:
        proxima = None                                   # blocked: o texto padrão explica o que falta
    elif not n_selected:
        proxima = "Escolha um mood board da biblioteca e aplique à campanha"
    else:
        proxima = "montar a imagem base do produto"
    # Sem `summary`: a faixa compacta do protótipo desta tela não tem chip extra.
    return g.build(next_action=proxima)
