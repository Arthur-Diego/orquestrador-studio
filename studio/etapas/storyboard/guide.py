"""Guia da etapa 4 — Storyboard (aulas 010 + 011, ADR-015). Leitura pura dos artefatos do projeto.

Cobre as duas metades da etapa fundida:
- ideação + cenas em texto (aula 010): auditoria de fidelidade §4.4/§4.5 (V4.1–V4.6);
- ângulos por cena + cena do produto (aula 011 + 013): auditoria §5.4/§5.5 (V5.2–V5.8).

Nada aqui cria, regrava ou toca no CLI: o guia é derivado do que já está no disco (ADR-003). Os
artefatos dos ângulos, que antes moravam em `shots/`, agora vivem em `storyboard/` (ADR-015):
`storyboard/cenaNN/base.png`, `storyboard/storyboard.json`, `storyboard/frames.md`.
"""
from __future__ import annotations

import re
from pathlib import Path

from ...common.guide import Guide, count_files, exists, read_json
from ...refs.service import project_dir
from ...storyboard.angles import PRODUCT_NOTE
from ...storyboard.service import COUNTS, DEFAULT_SCENES, UPSCALE_NOTE
from . import META

#: Mesma heurística do serviço: uma instrução importada com lista numerada de 2+ itens é sinal de
#: que o usuário pediu várias edições de uma vez (aula 010 manda uma por vez).
_NUMBERED = re.compile(r"\b\d+[.)]\s")
_IMG = {".png", ".jpg", ".jpeg", ".webp"}


def _has_image(s: dict) -> bool:
    """Cena "com imagem" = tem ≥ 1 keyframe (`[extensão]` cena-multi-keyframe, ADR-018).

    Lê o formato novo (`images`/`primary`) e, por retrocompat, o `image` singular antigo."""
    imgs = s.get("images")
    if isinstance(imgs, list):
        return bool(imgs)
    return bool(s.get("primary") or s.get("image"))

WHAT = (
    "Pegue a imagem base da campanha (etapa 3) e use-a para ter ideias de cena na Higgsfield "
    "(Draw to Edit, edições uma instrução por vez, Multi Shot); importe o que gostou e escreva a "
    "história em ~5 cenas, com começo, descoberta, ação e desfecho. Depois, para cada cena, acerte "
    "a base da cena (cores e luz antes do Multishot), gere vários ângulos (\"outro ponto de vista\"), "
    "escolha os melhores, faça upscale e ordene os frames como a cena progride. Por fim, monte a cena "
    "do produto (aula 013). É este storyboard (storyboard/storyboard.json) que a etapa 5 (animate) lê."
)

CHECKLIST = [
    "Cada instrução pede uma coisa; a próxima parte do resultado anterior.",
    "4 imagens quando incerto, 1 quando é tweak.",
    "~5 cenas em texto, em ordem: começo → descoberta → ação → desfecho.",
    "Base de cada cena sem \"cheiro de plástico\"; cores e luz padronizadas antes do Multishot.",
    "Vários enquadramentos por cena: close no rosto, plano aberto, foco nos pés/mãos.",
    "Só os melhores takes; cada um upscalado antes de virar vídeo (etapa 5).",
    "Frames em ordem de progressão narrativa; storyboard atualizado com os prints.",
    PRODUCT_NOTE,
]


def _mtime(pid: str, rel: str) -> float:
    """Data de modificação de um artefato (0.0 se não existe) — só leitura de metadado."""
    p = project_dir(pid) / rel
    return p.stat().st_mtime if p.exists() else 0.0


def _oldest_candidate(cdir: Path) -> float:
    """Data do candidato mais antigo de uma cena (0.0 sem candidatos)."""
    files = [f for f in cdir.iterdir() if f.is_file() and f.suffix.lower() in _IMG] if cdir.is_dir() else []
    return min((f.stat().st_mtime for f in files), default=0.0)


def _numero(scenes: list, sid) -> str:
    """"cena01" → "1" (o protótipo escreve "cena 1", sem zero à esquerda)."""
    s = next((x for x in scenes if x.get("id") == sid), None)
    n = (s or {}).get("n")
    return str(n) if n else str(sid)


def _next_action(has_base, chosen, scenes, escritas_ok, md_ok,
                 sem_base, sem_shot, sem_up, produto) -> str | None:
    """Próxima ação no estilo do protótipo (wave 4): imperativo curto.

    `None` devolve o texto padrão do shell (etapa concluída → "siga para a etapa 5").
    """
    if not has_base:
        return "Escolher a imagem base da campanha na etapa 3"
    if not chosen or not escritas_ok:
        return f"Gerar ideias a partir da imagem base e escrever as {DEFAULT_SCENES} cenas"
    if any(not _has_image(s) for s in scenes):
        return "Anexar uma ideia a cada cena"
    if not md_ok:
        return "Gerar o storyboard.md com as cenas escritas"
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

    # ---------- entradas ----------
    g.input("base_final", "base/base_final.png (etapa 3)", exists(pid, "base/base_final.png"),
            detail="a aula 010 parte da imagem base da campanha",
            fix="Volte à etapa 3 e escolha a imagem base", step="base")

    # ---------- ideação (aula 010) ----------
    cands = read_json(pid, "storyboard/candidates.json", default=[]) or []
    cands = cands if isinstance(cands, list) else []
    chosen = [c for c in cands if c.get("selected")]
    scenes = (read_json(pid, "storyboard/scenes.json", default={}) or {}).get("scenes") or []
    written = [s for s in scenes if (s.get("text") or "").strip()]
    with_image = [s for s in scenes if _has_image(s)]
    alvo = min(DEFAULT_SCENES, len(scenes)) if scenes else DEFAULT_SCENES
    escritas_ok = bool(scenes) and len(written) >= alvo

    g.output("ideas", "storyboard/ideas/ (ideias escolhidas)", bool(chosen),
             detail=f"{len(chosen)} de {len(cands)} ideias escolhidas"
                    f" · {count_files(pid, 'storyboard/ideas', _IMG)} arquivos")
    g.output("scenes", "storyboard/scenes.json (~5 cenas com texto e imagem)",
             escritas_ok and bool(scenes) and len(with_image) == len(scenes),
             detail=f"{len(written)}/{len(scenes)} cenas escritas · {len(with_image)} com imagem")
    g.output("storyboard_md", "storyboard/storyboard.md", exists(pid, "storyboard/storyboard.md"))

    # ---------- ângulos por cena (aula 011) ----------
    board = read_json(pid, "storyboard/storyboard.json", default=None)
    by_id = {s.get("id"): s for s in ((board or {}).get("scenes") or [])}
    ids = [s.get("id") for s in scenes]
    com_base = [i for i in ids if (root / "storyboard" / str(i) / "base.png").exists()]
    shots_por_cena = {i: ((by_id.get(i) or {}).get("shots") or []) for i in ids}
    com_shot = [i for i in ids if shots_por_cena[i]]
    todos_shots = [sh for i in ids for sh in shots_por_cena[i]]

    g.output("bases", "storyboard/cenaNN/base.png em todas as cenas",
             bool(ids) and len(com_base) == len(ids),
             detail=f"{len(com_base)}/{len(ids)} cenas com base")
    g.output("storyboard_json", "storyboard/storyboard.json (toda cena com ≥ 1 frame)",
             bool(ids) and len(com_shot) == len(ids),
             detail=f"{len(com_shot)}/{len(ids)} cenas com frames · {len(todos_shots)} frames no total")
    g.output("frames_md", "storyboard/frames.md", exists(pid, "storyboard/frames.md"),
             detail="o documento de grade dos ângulos, com a base e os frames na ordem")

    # ---------- validações da ideação (nunca bloqueiam) ----------
    g.check("v41_cinco_cenas", f"~{DEFAULT_SCENES} cenas escritas (aula 010)",
            "ok" if escritas_ok else ("todo" if not written else "warn"),
            detail=f"{len(written)} de {len(scenes) or DEFAULT_SCENES} cenas com texto",
            fix=None if escritas_ok else "Escreva o texto das cenas no painel 03")

    sem_img = [s.get("id") for s in scenes if not _has_image(s)]
    g.check("v42_cena_com_imagem", "Toda cena aponta para uma ideia de storyboard/ideas/",
            "ok" if scenes and not sem_img else ("todo" if not with_image else "warn"),
            detail="todas as cenas têm imagem" if scenes and not sem_img
                   else f"sem imagem: {', '.join(sem_img)}" if sem_img else "nenhuma cena ainda",
            fix=None if not sem_img else "Escolha a ideia de cada cena no painel 03")

    ordem_ok = [s.get("n") for s in scenes] == list(range(1, len(scenes) + 1))
    g.check("v43_ordem", "Cenas em ordem contígua (1..N)", "ok" if ordem_ok else "fail",
            detail="a numeração é recalculada a cada gravação" if ordem_ok else "renumere salvando as cenas")

    numeradas = [c for c in cands if len(_NUMBERED.findall(c.get("prompt") or "")) >= 2]
    g.check("v44_instrucao_unica", "Uma instrução por vez nas ideias importadas (aula 010)",
            "ok" if not numeradas else "warn",
            detail=f"{len(numeradas)} ideia(s) importada(s) com lista numerada"
                   if numeradas else "nenhuma instrução com lista numerada",
            fix=None if not numeradas else "Refaça a edição pedindo uma coisa de cada vez")

    g.check("v45_count", f"Geração em {COUNTS['uncertain']} (incerto) ou {COUNTS['tweak']} (tweak)", "ok",
            detail="a API só aceita 4 ou 1 — garantido pelo contrato da etapa")

    md_ok = _mtime(pid, "storyboard/storyboard.md") >= _mtime(pid, "storyboard/scenes.json") > 0
    g.check("v46_md_atualizado", "storyboard.md mais novo que scenes.json",
            "ok" if md_ok else ("todo" if not exists(pid, "storyboard/storyboard.md") else "warn"),
            detail="documento em dia com as cenas" if md_ok else "o documento está atrás das cenas",
            fix=None if md_ok else "Clique em \"Gerar storyboard.md\" no painel 03")

    # ---------- validações dos ângulos (nunca bloqueiam) ----------
    sem_shot = [i for i in ids if not shots_por_cena[i]]
    g.check("v52_cena_com_shot", "Toda cena tem ≥ 1 frame antes da etapa 5",
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
              if 0 < _oldest_candidate(root / "storyboard" / str(i) / "candidates")
              < _mtime(pid, f"storyboard/{i}/base.png")]
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
    g.check("v58_cena_do_produto", "Cena do produto (aula 013) antes da etapa 7",
            "ok" if produto else "todo", detail=PRODUCT_NOTE)

    palette = read_json(pid, "mood/palette.json", default=None)
    cores = (palette or {}).get("colors") or []
    g.check("palette", "Paleta do mood board (etapa 2) [extensão]", "ok" if cores else "warn",
            detail=f"{len(cores)} cores" if cores else "sem mood/palette.json: confira cores e luz no olho",
            fix=None if cores else "Volte à etapa 2 e salve a seleção do mood board")

    g.check("v47_upscale_note", "Upscale dos frames (aula 011)", "ok", detail=UPSCALE_NOTE)

    sem_base = [i for i in ids if i not in com_base]
    return g.build(
        summary=f"{len(com_shot)}/{len(ids)} cenas com frames" if ids else None,
        next_action=_next_action(
            exists(pid, "base/base_final.png"), chosen, scenes, escritas_ok, md_ok,
            sem_base, sem_shot, sem_up, produto))
