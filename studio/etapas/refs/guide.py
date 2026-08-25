"""Guia da etapa 1 — Referências (aula 009). Leitura pura dos artefatos do projeto.

Os textos de `what`/`checklist` vêm da auditoria de fidelidade da wave 2 (§1.4), que por sua vez
cita a transcrição da aula 009. Nada aqui inventa regra que o instrutor não ensina; o que é
escolha do Studio aparece marcado `[extensão]`.
"""
from __future__ import annotations

from ...common.guide import Guide, count_files, exists, read_json
from . import META

#: Vocabulário genérico de anúncio — um termo feito só disso não tem "marca validada" dentro.
_GENERIC_WORDS = {
    "ad", "ads", "advert", "advertising", "advertisement", "campaign", "commercial", "creative",
    "photography", "photo", "photoshoot", "product", "shot", "shots", "cinematic", "giant", "poster",
    "billboard", "brand", "branding", "design", "upload", "explore", "midjourney", "pinterest",
    "de", "da", "do", "the", "a", "of", "and",
}
#: Lixo de DOM do Pinterest que às vezes vem no `alt` (a auditoria pede aviso quando sobra).
_ALT_JUNK = ("salvar pin", "save pin", "pinterest")
#: A aula fica com ~6 referências; abaixo disso é aviso, nunca bloqueio.
MIN_REFS = 3


def _looks_like_brand(term: str, own_words: set[str]) -> bool:
    """O termo tem alguma palavra que não é vocabulário genérico nem o próprio produto/vibe?

    A aula 009 manda buscar por uma marca já validada ("Red Bull", depois "Red Bull snow ads").
    Heurística deliberadamente frouxa — o resultado é um **aviso**, nunca um bloqueio.
    """
    for token in term.replace("-", " ").split():
        word = token.strip(".,:;!?\"'").lower()
        if not word or word in _GENERIC_WORDS or word in own_words:
            continue
        return True
    return False


def guide(pid: str) -> dict:
    meta = read_json(pid, "project.json", default={}) or {}
    cands = read_json(pid, "refs/candidates/candidates.json", default=[]) or []
    if not isinstance(cands, list):
        cands = []
    selected = [c for c in cands if isinstance(c, dict) and c.get("selected")]
    n_brain = count_files(pid, "refs/brainstorming", {".jpg", ".jpeg", ".png", ".webp"})
    has_readme = exists(pid, "refs/README.md")

    g = Guide(META).text(
        "Comece sem ideia nenhuma. Pesquise no Pinterest uma marca já validada do seu segmento "
        '(ex.: "Red Bull", depois "Red Bull snow ads") e role o "buraco de minhoca" que o Pinterest '
        "abre. Marque só o que você gosta e o que foge do clichê — nada de \"lata com fundo preto\". "
        "Se quiser, traga também imagens salvas do Explore do Midjourney (botão \"adicionar por "
        "upload\"). Ao salvar, as escolhidas vão para refs/brainstorming/; depois de ver tudo, volte "
        "e desmarque o que já não te agrada.",
        ["Busquei por uma marca validada, não só pela categoria do produto",
         "Salvei o que gosto, sem me prender ao produto (\"não tem nada a ver com Red Bull, mas gostei do conceito\")",
         "Fugi do padrão que \"todo mundo já viu\"",
         "Revisei e apaguei o que deixou de me agradar",
         "Ainda não tentei decidir a campanha — isso vem depois do mood"],
    )

    # Entradas: a etapa 1 é a primeira do curso — nada vem de outra etapa, então nada bloqueia.
    g.input("project", "Projeto criado (nome + produto)", True,
            detail=(meta.get("name") or pid) + (f" · produto: {meta['product']}" if meta.get("product") else ""))

    # Saídas desta etapa.
    g.output("selected", "≥ 1 referência escolhida em refs/brainstorming/", bool(selected) and n_brain > 0,
             detail=f"{len(selected)} escolhidas · {n_brain} arquivos em brainstorming")
    g.output("readme", "refs/README.md com a origem de cada referência", has_readme)

    # Validações (auditoria §1.5): qualidade, nunca bloqueio.
    g.check("candidates", "Busca rodada (há candidatas baixadas)", "ok" if cands else "todo",
            detail=f"{len(cands)} candidatas", fix=None if cands else "Rode uma busca ou traga imagens por upload")
    if not selected:
        g.check("min_refs", f"{MIN_REFS} ou mais referências escolhidas", "todo",
                detail="a aula fica com ~6 imagens")
    else:
        g.check("min_refs", f"{MIN_REFS} ou mais referências escolhidas",
                "ok" if len(selected) >= MIN_REFS else "warn",
                detail=f"{len(selected)} escolhidas (a aula fica com ~6)")

    orphans = [c for c in selected if not c.get("file")]
    g.check("brainstorming_sync", "Cada escolhida tem cópia em refs/brainstorming/",
            "ok" if (len(selected) == n_brain and not orphans) else ("fail" if selected or n_brain else "todo"),
            detail=f"{len(selected)} selecionadas × {n_brain} arquivos",
            fix="Salve a seleção de novo para regravar refs/brainstorming/"
            if len(selected) != n_brain else None)

    own = _own_words(meta)
    terms = sorted({str(c.get("term") or "") for c in cands if c.get("term")})
    brand_terms = [t for t in terms if _looks_like_brand(t, own)]
    g.check("brand_term", "Algum termo de busca aponta uma marca validada (aula 009)",
            "ok" if brand_terms else ("warn" if terms else "todo"),
            detail=", ".join(brand_terms[:3]) if brand_terms else "só termos genéricos de anúncio",
            fix=None if brand_terms else "Informe a marca validada e clique em \"Sugerir termos\"")

    junk = [c for c in selected if any(j in str(c.get("alt") or "").lower() for j in _ALT_JUNK)]
    g.check("alt_junk", "Nenhuma escolhida com descrição de lixo do Pinterest",
            "ok" if not junk else "warn", detail=f"{len(junk)} com \"salvar pin\"/\"pinterest\" na descrição")

    g.check("product", "Produto do projeto preenchido (alimenta as etapas 2 e 3)",
            "ok" if meta.get("product") else "warn",
            detail=meta.get("product") or "sem produto no project.json",
            fix=None if meta.get("product") else "Preencha o produto na barra lateral do projeto")

    return g.build()


def _own_words(meta: dict) -> set[str]:
    """Palavras do próprio produto/vibe — não contam como 'marca validada'."""
    text = f"{meta.get('product') or ''} {meta.get('vibe') or ''}".lower()
    return {w.strip(".,:;!?\"'") for w in text.replace("-", " ").split() if w}
