"""Guia da etapa 5 — Ângulos por cena (aula 011) + cena do produto (aula 013).

Leitura pura dos artefatos do projeto: texto e checklist da auditoria §5.4, validações de §5.5
(V5.2–V5.8). Nada aqui grava, chama o CLI ou baixa nada — o guia só olha o disco (ADR-003).

Desvio consciente da §5.4 (auto-aceite desta frente): `mood/palette.json` é listado lá como
entrada necessária, mas entra aqui como **validação** (atenção), não como entrada bloqueante —
a paleta é `[extensão]` do Studio (OS-014) e não pode travar uma etapa que a aula libera.
"""
from __future__ import annotations

from pathlib import Path

from ...common.guide import Guide, exists, read_json
from ...refs.service import project_dir
from ...shots.service import PRODUCT_NOTE
from . import META

WHAT = (
    "Para cada cena do storyboard, primeiro acerte a imagem base da cena: realismo cinematográfico "
    "(câmera, lente, abertura, estilo), rosto oculto se for o caso, sem elementos que não pertencem "
    "à cena e com sensação de movimento — peça as modificações numeradas em uma rodada. Acerte "
    "cores e luz antes do Multishot, porque toda variação herda a base. Então suba a base no "
    "Multishot, gere o grid, escolha os melhores takes, faça upscale e baixe. Organize por pasta "
    "de cena e ordene os frames como a cena progride. Repita para todas as cenas."
)

CHECKLIST = [
    "Base da cena sem \"cheiro de plástico\": linguagem de cinema.",
    "Cores e iluminação padronizadas antes do Multishot.",
    "Vários enquadramentos por cena: close no rosto, plano aberto, foco nos pés/mãos, ritmo variado.",
    "Só os melhores takes; cada um upscalado antes de baixar.",
    "Uma pasta por cena; frames em ordem de progressão narrativa.",
    "Storyboard atualizado com os prints, na ordem.",
    PRODUCT_NOTE,
]

_IMG = {".png", ".jpg", ".jpeg", ".webp"}


def _mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


def _oldest_candidate(cdir: Path) -> float:
    """Data do candidato mais antigo da cena (0.0 sem candidatos)."""
    files = [f for f in cdir.iterdir() if f.is_file() and f.suffix.lower() in _IMG] if cdir.is_dir() else []
    return min((f.stat().st_mtime for f in files), default=0.0)


def _numero(scenes: list, sid) -> str:
    """"cena01" → "1" (o protótipo escreve "cena 1", sem zero à esquerda)."""
    s = next((x for x in scenes if x.get("id") == sid), None)
    n = (s or {}).get("n")
    return str(n) if n else str(sid)


def _next_action(scenes: list, escritas: list, sem_base: list, sem_shot: list,
                 sem_up: list, produto) -> str | None:
    """Próxima ação no estilo do protótipo (wave 4): imperativo curto, sem "Produza o artefato…".

    `None` devolve o texto padrão do shell (etapa concluída → "siga para a etapa 6").
    """
    if not escritas:
        return "Escrever as cenas da história na etapa 4"
    if sem_base:
        return f"Acertar cores e luz na base da cena {_numero(scenes, sem_base[0])} antes do multishot"
    if sem_shot:
        return f"Escolher e ordenar os frames da cena {_numero(scenes, sem_shot[0])}"
    if sem_up:
        return "Fazer upscale dos frames escolhidos e salvar a ordem de novo"
    if not produto:
        return "Montar a cena do produto (aula 013)"
    return None


def guide(pid: str) -> dict:
    root = project_dir(pid)
    g = Guide(META).text(WHAT, CHECKLIST)

    scenes = (read_json(pid, "storyboard/scenes.json", default={}) or {}).get("scenes") or []
    escritas = [s for s in scenes if (s.get("text") or "").strip()]

    # ---------- entradas ----------
    g.input("scenes", "storyboard/scenes.json com cenas escritas (etapa 4)", bool(escritas),
            detail=f"{len(escritas)} de {len(scenes)} cenas escritas" if scenes else "sem storyboard ainda",
            fix="Volte à etapa 4 e escreva as ~5 cenas da história", step="storyboard")
    g.input("base_final", "base/base_final.png (etapa 3)", exists(pid, "base/base_final.png"),
            detail="é a base de fallback de uma cena sem imagem própria",
            fix="Volte à etapa 3 e escolha a imagem base", step="base")

    # ---------- estado das cenas no disco ----------
    board = read_json(pid, "shots/storyboard.json", default=None)
    by_id = {s.get("id"): s for s in ((board or {}).get("scenes") or [])}
    ids = [s.get("id") for s in scenes]
    com_base = [i for i in ids if (root / "shots" / str(i) / "base.png").exists()]
    shots_por_cena = {i: ((by_id.get(i) or {}).get("shots") or []) for i in ids}
    com_shot = [i for i in ids if shots_por_cena[i]]
    todos_shots = [sh for i in ids for sh in shots_por_cena[i]]

    # ---------- saídas ----------
    g.output("bases", "shots/cenaNN/base.png em todas as cenas",
             bool(ids) and len(com_base) == len(ids),
             detail=f"{len(com_base)}/{len(ids)} cenas com base")
    g.output("storyboard", "shots/storyboard.json (toda cena com ≥ 1 frame)",
             bool(ids) and len(com_shot) == len(ids),
             detail=f"{len(com_shot)}/{len(ids)} cenas com frames · {len(todos_shots)} frames no total")
    g.output("storyboard_md", "shots/storyboard.md", exists(pid, "shots/storyboard.md"),
             detail="o documento de storyboard da aula, com a base e os frames na ordem")

    # ---------- validações (nunca bloqueiam) ----------
    sem_shot = [i for i in ids if not shots_por_cena[i]]
    g.check("v52_cena_com_shot", "Toda cena tem ≥ 1 frame antes da etapa 6",
            "ok" if ids and not sem_shot else ("todo" if not com_shot else "warn"),
            detail="todas as cenas têm frame" if ids and not sem_shot
                   else f"sem frame: {', '.join(str(i) for i in sem_shot)}",
            fix=None if not sem_shot else "Abra a cena, importe os resultados e salve a ordem")

    sem_up = [sh.get("id") for i in ids for sh in shots_por_cena[i] if not sh.get("upscaled")]
    g.check("v53_upscale", "Todo frame escolhido está upscalado (aula 011)",
            "ok" if todos_shots and not sem_up else ("todo" if not todos_shots else "warn"),
            detail=f"{len(todos_shots) - len(sem_up)}/{len(todos_shots)} frames upscalados",
            fix=None if not sem_up else "Faça o upscale 2x (na UI ou pelo CLI) e salve a ordem de novo")

    ordem_ruim = []
    for i in ids:
        shots = shots_por_cena[i]
        if [sh.get("order") for sh in shots] != list(range(1, len(shots) + 1)):
            ordem_ruim.append(f"{i}: ordem")
        ordem_ruim += [f"{i}: {sh.get('id')} ausente" for sh in shots
                       if not (root / (sh.get("file") or "__sem_arquivo__")).exists()]
    g.check("v54_ordem_e_arquivos", "Ordem contígua e arquivo de cada frame no disco",
            "ok" if todos_shots and not ordem_ruim else ("todo" if not todos_shots else "fail"),
            detail="; ".join(ordem_ruim) if ordem_ruim else "frames em ordem, arquivos presentes",
            fix=None if not ordem_ruim else "Salve a ordem da cena de novo para reconstruir os frames")

    um_so = [i for i in com_shot if len(shots_por_cena[i]) < 2]
    g.check("v55_variacoes", "Pelo menos 2 enquadramentos por cena (grid do Multishot)",
            "ok" if com_shot and not um_so else ("todo" if not com_shot else "warn"),
            detail=f"cenas com 1 frame só: {', '.join(str(i) for i in um_so)}" if um_so
                   else "toda cena com frames tem variação",
            fix=None if not um_so else "Gere mais ângulos da cena (close, aberto, pés, mãos) e escolha 2+")

    velhos = [i for i in ids
              if 0 < _oldest_candidate(root / "shots" / str(i) / "candidates")
              < _mtime(root / "shots" / str(i) / "base.png")]
    g.check("v56_candidatos_antigos", "Candidatos gerados depois da base atual (cores e luz)",
            "ok" if ids and not velhos else "warn" if velhos else "todo",
            detail=f"a base mudou depois de importar em: {', '.join(str(i) for i in velhos)}" if velhos
                   else "nenhum candidato anterior à base atual",
            fix=None if not velhos else "Regere os ângulos: as variações antigas herdaram a base anterior")

    tem_formula = any("another point of view" in (sh.get("prompt") or "").lower() for sh in todos_shots)
    g.check("v57_formula_do_angulo", "Prompt de ângulo na fórmula da aula (\"another point of view\")",
            "ok" if tem_formula else ("todo" if not todos_shots else "warn"),
            detail="a aula pede outro ponto de vista da MESMA imagem, com o foco explícito",
            fix=None if tem_formula else "Use o prompt \"Outro ponto de vista\" do painel da cena")

    produto = (board or {}).get("product_scene")
    g.check("v58_cena_do_produto", "Cena do produto (aula 013) antes da etapa 8",
            "ok" if produto else "todo", detail=PRODUCT_NOTE)

    palette = read_json(pid, "mood/palette.json", default=None)
    cores = (palette or {}).get("colors") or []
    g.check("palette", "Paleta do mood board (etapa 2) [extensão]", "ok" if cores else "warn",
            detail=f"{len(cores)} cores" if cores else "sem mood/palette.json: confira cores e luz no olho",
            fix=None if cores else "Volte à etapa 2 e salve a seleção do mood board")

    sem_base = [i for i in ids if i not in com_base]
    return g.build(next_action=_next_action(scenes, escritas, sem_base, sem_shot, sem_up, produto))
