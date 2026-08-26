"""Guia da etapa 6 — Animação (aula 012), por leitura pura dos artefatos do projeto.

Nada aqui grava: `animate.load_plan()` cria/atualiza `animate/takes.json` e por isso está
proibido no guia (contrato em `studio/common/guide.py`). Lemos `shots/storyboard.json` e
`animate/takes.json` direto, pelos leitores puros do serviço.

Textos de `what`/`checklist` são os da aula 012 (ADR-004) — auditoria de fidelidade
`docs/domains/studio/waves/wave-2-auditoria-etapas-4-6.md` §6.4. Validações: §6.5 (V6.1–V6.10).
"""
from __future__ import annotations

import re

from ...animate import service as animate
from ...common.guide import Guide, exists
from . import META

#: A aula 012 pede 2 takes por shot antes de escolher (mesmo valor da tela).
TAKES_DA_AULA = 2

#: `videos/cenaNN/shotMM_takeK.ext` — a nomenclatura que a aula pede ("nomear e organizar").
TAKE_NAME = re.compile(r"^videos/[^/]+/[^/]+_take\d+\.[A-Za-z0-9]+$")

#: Radicais de movimento/câmera (en da aula 007 + pt) — heurística de aviso, nunca bloqueio.
MOTION_STEMS = (
    "walk", "run", "move", "motion", "camera", "dolly", "pan ", "zoom", "tilt", "push", "pull",
    "orbit", "track", "crane", "handheld", "drift", "rise", "fall", "turn", "spin", "approach",
    "reveal", "fly", "glide", "shake", "sweep", "step", "lift", "enter", "exit", "comes to life",
    "changes", "slowly", "câmera", "camera", "movimento", "caminh", "gira", "aproxima", "afasta",
    "anda", "sobe", "desce",
)

WHAT = (
    "Anime cada frame do storyboard como um take de vídeo. Descreva o movimento com clareza: "
    "prompt simples para cena simples; movimento de câmera + ação (ou o Abrahub Creative Engine) "
    "quando a cena pede mais; quanto mais claro, menos a IA alucina. Use Kling para cenas simples, "
    "start frame + end frame (dois frames seguidos da mesma cena) para transições, Seedance para "
    "movimentos complexos; 10 s quando a mudança é lenta; áudio do modelo desligado. Gere 2 "
    "variações, dê like na usável, baixe e nomeie por cena e take. Depois de 3–4 tentativas ruins, "
    "troque o modelo ou adapte a ideia; o que não sair, resolve-se na montagem com cortes. "
    "Enquanto um take gera, dispare outros em paralelo."
)

CHECKLIST = [
    "Movimento pedido presente e coerente.",
    "Continuidade com a cena anterior/seguinte; variação de ângulo (wide, POV, close).",
    "Start/end frame quando dois frames se seguem na mesma cena.",
    "Áudio do modelo OFF; 5 s (10 s se a mudança for lenta).",
    "Pelo menos 2 takes por shot, 1 usável.",
    "Após 3–4 falhas: outro modelo, prompt reescrito ou corte para preto.",
    "Takes nomeados por cena (videos/cenaNN/).",
]


def _has_motion(prompt: str) -> bool:
    text = (prompt or "").lower()
    return any(stem in text for stem in MOTION_STEMS)


def _safe_exists(pid: str, rel: str) -> bool:
    """`exists` que nunca explode: `takes.json` editado à mão pode ter caminho fora do projeto."""
    try:
        return bool(rel) and exists(pid, rel)
    except ValueError:
        return False


def _shots(pid: str) -> tuple[list[dict], list[dict]]:
    """Shots do storyboard mesclados com o que está gravado em `takes.json` (sem gravar nada).

    Devolve também os shots do `takes.json` cru: o plano só existe depois que a etapa foi aberta.
    """
    entries, _ = animate.storyboard_entries(pid)
    gravados = animate.stored_takes(pid)["shots"]
    stored = {(s["scene"], s["shot"]): s for s in gravados}
    # storyboard manda em ordem/frame (como `_merge` do serviço); takes.json manda no resto.
    merged = [{**stored.get((e["scene"], e["shot"]), {}), **e} for e in entries]
    return merged, gravados


def _product_shots(pid: str) -> list[tuple[str, str]]:
    """Shots da cena do produto (aula 013), se o storyboard trouxer `product_scene`."""
    from ...common.guide import read_json
    board = read_json(pid, "shots/storyboard.json", default={}) or {}
    scene = board.get("product_scene") if isinstance(board, dict) else None
    if not isinstance(scene, dict):
        return []
    sid = scene.get("id") or "cena_produto"
    return [(sid, sh.get("id") or "") for sh in (scene.get("shots") or []) if isinstance(sh, dict)]


def _ready(shot: dict) -> bool:
    return bool(shot.get("fallback_black")) or any(t.get("liked") is True for t in shot.get("takes") or [])


def guide(pid: str) -> dict:
    g = Guide(META).text(WHAT, CHECKLIST)
    shots, gravados = _shots(pid)
    total = len(shots)

    # ---------- entradas ----------
    g.input("storyboard", "shots/storyboard.json com os frames finais (etapa 5)", total > 0,
            detail=f"{total} shot(s) no plano" if total else "nenhum shot para animar",
            fix="Volte à etapa 5, gere os frames de cada cena e salve o storyboard", step="shots")

    # ---------- saídas ----------
    with_prompt = [s for s in shots if (s.get("prompt") or "").strip() or s.get("fallback_black")]
    ready = [s for s in shots if _ready(s)]
    finals = [s for s in ready if not s.get("fallback_black")]
    g.output("takes_json", "animate/takes.json com o plano dos takes", bool(gravados),
             detail=f"{len(gravados)} shot(s) gravados" if gravados else "abra a etapa para criar o plano")
    g.output("prompts", "Prompt de movimento em todo shot", bool(shots) and len(with_prompt) == total,
             detail=f"{len(with_prompt)}/{total} com prompt")
    g.output("finals", "videos/cenaNN/shotMM_final.mp4 (ou corte para preto) em todo shot",
             bool(shots) and len(ready) == total,
             detail=f"{len(ready)}/{total} prontos · {len(finals)} com take usável")

    # ---------- validações (auditoria §6.5) ----------
    _checks(g, pid, shots, total, ready)
    # Wave 4: a faixa compacta do guia mostra "N/M shots prontos" (o chip que saiu do painel 01)
    # e uma próxima ação imperativa no estilo do protótipo.
    return g.build(summary=f"{len(ready)}/{total} shots prontos" if total else None,
                   next_action=_next_action(shots))


def _next_action(shots: list[dict]) -> str | None:
    """Imperativo curto do protótipo: "Gerar 2 takes do shot02 e dar like no usável"."""
    pendentes = [s for s in shots if not _ready(s)]
    if not shots or not pendentes:
        return None
    alvo = pendentes[0]
    faltam = max(TAKES_DA_AULA - len(alvo.get("takes") or []), 1)
    return (f"Gerar {faltam} {'takes' if faltam > 1 else 'take'} do {alvo.get('shot') or 'shot'} "
            "e dar like no usável")


def _checks(g: Guide, pid: str, shots: list[dict], total: int, ready: list[dict]) -> None:
    # V6.1 — image-to-video: sem frame não há o que animar.
    sem_frame = [s for s in shots if not s.get("image")]
    g.check("v6_1_frames", "Todo shot tem frame da etapa 5", _status(not shots, not sem_frame, "fail"),
            detail=(f"{len(sem_frame)} shot(s) sem frame: "
                    + ", ".join(f"{s['scene']}/{s['shot']}" for s in sem_frame[:4]) if sem_frame
                    else f"{total} frame(s) no lugar"),
            fix="Gere o frame que falta na etapa 5" if sem_frame else None)

    # V6.2 — "selecionar o que é utilizável": a etapa 8 só monta com take usável (ou preto).
    g.check("v6_2_ready", "Todo shot com take usável ou corte para preto (antes da etapa 8)",
            _status(not shots, len(ready) == total, "todo"),
            detail=f"{len(ready)}/{total} shot(s) prontos",
            fix="Dê like no take usável de cada shot ou marque corte para preto"
                if shots and len(ready) != total else None)

    # V6.3 — "gerar múltiplas variações" (o plano fala em 2 antes de escolher).
    poucos = [s for s in shots if any(t.get("liked") is True for t in s.get("takes") or [])
              and len(s.get("takes") or []) < 2]
    g.check("v6_3_two_takes", "Pelo menos 2 takes antes do like (aula 012)",
            _status(not shots, not poucos, "warn"),
            detail=(", ".join(f"{s['scene']}/{s['shot']}" for s in poucos[:4]) + " com 1 take só"
                    if poucos else "nenhum like com take único"),
            fix="Gere uma segunda variação e compare antes de escolher" if poucos else None)

    # V6.4 — Kling 2.5 Turbo: start/end só existe de verdade com o `end` gravado.
    se_shots = [s for s in shots if s.get("mode") == "start_end"]
    sem_par = [s for s in se_shots if not _safe_exists(pid, ((s.get("start_end") or {}).get("end") or ""))]
    g.check("v6_4_start_end", "Modo start/end com end frame gravado e existente",
            _status(not se_shots, not sem_par, "fail"),
            detail=(", ".join(f"{s['scene']}/{s['shot']}" for s in sem_par[:4]) + " sem end frame"
                    if sem_par else f"{len(se_shots)} shot(s) em start/end com par completo"),
            fix="Escolha o end frame do shot (próximo frame da cena ou um edit/last_frames/*.png)"
                if sem_par else None)

    # V6.5 — áudio do modelo OFF: o Studio manda `sound: false` em toda chamada ao CLI.
    g.check("v6_5_sound_off", "Áudio do modelo sempre OFF na geração pelo CLI", "ok",
            detail="build_params envia sound: false em todo take (aula 012)")

    # V6.6 — 5 s padrão, 10 s só quando a mudança é lenta.
    fora = [s for s in shots if s.get("duration") not in animate.DURATIONS]
    longos = [s for s in shots if s.get("duration") == animate.DURATIONS[1]]
    g.check("v6_6_duration", "Duração 5 s (10 s só para mudanças lentas)",
            _status(not shots, not fora, "warn"),
            detail=(f"{len(fora)} shot(s) fora de 5/10 s" if fora
                    else f"{len(longos)} shot(s) em 10 s — confira se a mudança é mesmo lenta"))

    # V6.7 — "trocar modelos": 3 falhas no mesmo shot pedem o próximo da ordem.
    travados = [s for s in shots if animate.failures_of(s) >= animate.FAIL_THRESHOLD and not _ready(s)]
    adaptar = [s for s in travados if animate.failures_of(s) >= animate.ADAPT_THRESHOLD]
    g.check("v6_7_model_switch", "Shot com 3+ falhas: trocar de modelo",
            _status(not shots, not travados, "warn"),
            detail=(", ".join(f"{s['scene']}/{s['shot']} ({animate.failures_of(s)} falhas)"
                              for s in travados[:4]) if travados else "nenhum shot travado"),
            fix=("Adapte a ideia: gere um novo frame na etapa 5 ou aceite o corte para preto"
                 if adaptar else "Gere o próximo modelo sugerido para o shot" if travados else None))

    # V6.8 — "nomear e organizar cenas e takes".
    takes = [(s, t) for s in shots for t in (s.get("takes") or [])]
    fora_padrao = [t for _s, t in takes if not TAKE_NAME.match(t.get("file") or "")]
    g.check("v6_8_naming", "Takes em videos/cenaNN/shotMM_takeK.mp4",
            _status(not takes, not fora_padrao, "warn"),
            detail=(f"{len(fora_padrao)} take(s) fora do padrão" if fora_padrao
                    else f"{len(takes)} take(s) nomeados pela convenção"))

    # V6.9 — "descrever claramente o movimento".
    escritos = [s for s in shots if (s.get("prompt") or "").strip()]
    sem_verbo = [s for s in escritos if not _has_motion(s["prompt"])]
    g.check("v6_9_motion_verb", "Prompt descreve movimento ou câmera",
            _status(not escritos, not sem_verbo, "warn"),
            detail=(", ".join(f"{s['scene']}/{s['shot']}" for s in sem_verbo[:4])
                    + " sem verbo de movimento" if sem_verbo else f"{len(escritos)} prompt(s) com movimento"),
            fix="Diga o que se move e como a câmera se move (a aula: quanto mais claro, melhor)"
                if sem_verbo else None)

    # V6.10 — a cena do produto também é animada (aula 013).
    produto = _product_shots(pid)
    prontos = [s for s in shots if _ready(s) and (s["scene"], s["shot"]) in produto]
    g.check("v6_10_product", "Cena do produto animada (aula 013)",
            _status(not produto, len(prontos) == len(produto), "warn"),
            detail=(f"{len(prontos)}/{len(produto)} shot(s) da cena do produto prontos" if produto
                    else "storyboard sem cena do produto"),
            fix="Anime também a cena do produto — ela fecha o anúncio"
                if produto and len(prontos) != len(produto) else None)


def _status(vazio: bool, ok: bool, ruim: str) -> str:
    """`todo` quando não há o que avaliar, `ok` quando passa, `ruim` (warn|fail) quando não."""
    if vazio:
        return "todo"
    return "ok" if ok else ruim
