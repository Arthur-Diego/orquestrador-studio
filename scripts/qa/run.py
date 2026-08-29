"""Runner do QA E2E de frontend (skill qa-studio) — fora do CI (ADR-008).

    . .venv/bin/activate
    python scripts/qa/run.py --run <run-id> [--telas refs mood ...] [--casos C-REFS-03 ...]
                             [--temas light,dark] [--viewports 1440x900,1024x768]
                             [--so-auditoria] [--sem-timers] [--headed]

Para cada tela pedida (padrão: todas as `ready` de /api/steps + shell/overview/moodboards/creditos):
1. auditoria automática por tema × viewport: navega, espera, `auditar_visual`, print full-page,
   console/pageerror/HTTP≥400 (harness.Sonda);
2. casos funcionais do módulo `scripts/qa/cenarios/<tela>.py` (uma vez, no 1º tema × viewport);
3. timer órfão (sai da tela e conta requests da tela anterior por 6 s).

Saída: `.qa/runs/<run-id>/resultados.json` (+ prints em `evidencias/`) e um sumário no stdout.
Exit 1 se houver FALHA ou auditoria com problema; 2 se argumento inválido.
Revalidação incremental: use `--casos` (ids exatos) e/ou `--telas` para reexecutar só o que
falhou ou o que o raio de impacto da correção alcança.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.qa import harness as H  # noqa: E402

ORDEM_GLOBAIS = ["shell", "overview", "moodboards", "creditos"]


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True, help="run-id (pasta em .qa/runs/)")
    p.add_argument("--repo", default=str(REPO))
    p.add_argument("--telas", nargs="*", default=None, help="ids de tela (refs, 4, moodboards…); vazio = todas")
    p.add_argument("--casos", nargs="*", default=None, help="ids exatos de casos a executar (revalidação)")
    p.add_argument("--temas", default="light,dark")
    p.add_argument("--viewports", default="1440x900,1024x768")
    p.add_argument("--so-auditoria", action="store_true", help="pula os casos funcionais")
    p.add_argument("--sem-timers", action="store_true")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--saida", default=None, help="caminho do JSON (padrão: .qa/runs/<run>/resultados.json)")
    return p.parse_args(argv)


def resolver_telas(pedidas: list[str] | None, steps: list[dict]) -> tuple[list[str], list[str]]:
    """Devolve (telas válidas na ordem canônica, telas pedidas mas `soon`/inválidas)."""
    ready = [s["id"] for s in steps if s["status"] == "ready"]
    por_n = {str(s["n"]): s["id"] for s in steps}
    todas = ORDEM_GLOBAIS[:2] + ready + ORDEM_GLOBAIS[2:]
    if not pedidas:
        return todas, []
    ok, ruins = [], []
    for t in pedidas:
        t = por_n.get(t, t)
        if t in todas:
            ok.append(t)
        else:
            ruins.append(t)
    return [t for t in todas if t in ok], ruins


def carregar_casos(tela: str) -> list[H.Caso]:
    try:
        mod = importlib.import_module(f"scripts.qa.cenarios.{tela}")
    except ModuleNotFoundError:
        return []
    return list(getattr(mod, "CASOS", []))


def main(argv: list[str]) -> int:
    a = parse_args(argv)
    run_dir = Path(a.repo) / ".qa" / "runs" / a.run
    if not (run_dir / "seed.json").exists():
        print(f"seed.json ausente em {run_dir} — rode stack-up.sh e seed.sh", file=sys.stderr)
        return 2
    ctx = H.Ctx.da_rodada(run_dir)
    temas = [t.strip() for t in a.temas.split(",") if t.strip()]
    viewports = [tuple(int(x) for x in v.split("x")) for v in a.viewports.split(",") if v.strip()]

    nav = H.Navegador(ctx, headless=not a.headed)
    page, sonda = nav.nova_pagina(temas[0], viewports[0])
    ctx.steps = page.request.get(f"{ctx.base}/api/steps").json()
    telas, ruins = resolver_telas(a.telas, ctx.steps)
    if ruins:
        validas = ORDEM_GLOBAIS + [s["id"] for s in ctx.steps]
        print(f"telas inválidas ou ainda não implementadas: {ruins} — válidas: {validas}", file=sys.stderr)
        if not telas:
            nav.fechar()
            return 2

    resultado = {"run": a.run, "base": ctx.base, "modo": ctx.modo, "inicio": datetime.now(timezone.utc).isoformat(),
                 "telas": telas, "temas": temas, "viewports": [f"{w}x{h}" for w, h in viewports],
                 "auditorias": [], "casos": [], "timers": {}}
    filtro = set(a.casos) if a.casos else None

    # ---- 1) auditorias por tema × viewport ----
    for tema in temas:
        for vp in viewports:
            ctx.tema, ctx.viewport = tema, vp
            page, sonda = nav.nova_pagina(tema, vp)
            page.goto(f"{ctx.base}/")
            H.esperar_tela(page)
            for tela in telas:
                if filtro and not any(c.startswith(f"C-{tela.upper()}") for c in filtro) and tela != "shell":
                    continue
                if a.casos and tela == "shell":
                    continue
                sonda.zerar()
                t0 = time.time()
                try:
                    H.abrir_tela(page, ctx, tela)
                    aud = H.auditar_visual(page)
                    print_path = H.evidencia(page, ctx, f"{tela}")
                    problemas = H.problemas_visuais(aud)
                    snap = sonda.snapshot()
                    resultado["auditorias"].append({
                        "tela": tela, "tema": tema, "viewport": f"{vp[0]}x{vp[1]}", "print": print_path,
                        "visual": aud, "problemas": problemas, **snap,
                        "ok": not problemas and not snap["pageerrors"] and not snap["console"] and not snap["http_erros"],
                        "segundos": round(time.time() - t0, 1)})
                except Exception as e:  # noqa: BLE001
                    resultado["auditorias"].append({"tela": tela, "tema": tema, "viewport": f"{vp[0]}x{vp[1]}",
                                                    "ok": False, "erro": f"{type(e).__name__}: {e}", **sonda.snapshot()})

    # ---- 2) casos funcionais (1º tema × viewport) ----
    if not a.so_auditoria:
        ctx.tema, ctx.viewport = temas[0], viewports[0]
        for tela in telas:
            casos = [c for c in carregar_casos(tela) if not filtro or c.id in filtro]
            if not casos:
                continue
            page, sonda = nav.nova_pagina(ctx.tema, ctx.viewport)
            page.goto(f"{ctx.base}/")
            H.esperar_tela(page)
            for caso in casos:
                sonda.zerar()
                t0 = time.time()
                pid = None if tela in ("moodboards", "creditos") else {"cheio": ctx.pid_cheio, "vazio": ctx.pid_vazio}.get(caso.pid or "")
                try:
                    H.abrir_tela(page, ctx, tela, pid)
                    res = caso.fn(page, ctx)
                except Exception as e:  # noqa: BLE001
                    ev = []
                    try:
                        ev.append(H.evidencia(page, ctx, f"{caso.id}-excecao"))
                    except Exception:  # noqa: BLE001
                        pass
                    res = H.Resultado.falha(f"exceção no caso: {type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}", *ev)
                    # recomeça o navegador para o próximo caso não herdar estado quebrado
                    page, sonda = nav.nova_pagina(ctx.tema, ctx.viewport)
                    page.goto(f"{ctx.base}/")
                    H.esperar_tela(page)
                snap = sonda.snapshot()
                if res.http_esperados:   # caminho triste provocado pelo caso: não é erro da sonda
                    snap["http_erros"] = [h for h in snap["http_erros"] if h["status"] not in res.http_esperados]
                    snap["console"] = [c for c in snap["console"]
                                       if not any(f"status of {st}" in c for st in res.http_esperados)]
                    snap["http_esperados"] = list(res.http_esperados)
                resultado["casos"].append({"id": caso.id, "tela": tela, "titulo": caso.titulo, "pid": pid,
                                           "status": res.status, "detalhe": res.detalhe, "evidencias": res.evidencias,
                                           **snap, "segundos": round(time.time() - t0, 1)})
                print(f"{'✓' if res.status == H.PASSA else '✗' if res.status == H.FALHA else '⊘'} {caso.id} {caso.titulo}"
                      + (f"  — {res.detalhe[:140]}" if res.status != H.PASSA else ""))
                try:
                    H.fechar_modal(page)
                except Exception:  # noqa: BLE001
                    pass

    # ---- 3) timers órfãos ----
    if not a.sem_timers and not a.casos:
        page, sonda = nav.nova_pagina(temas[0], viewports[0])
        page.goto(f"{ctx.base}/")
        H.esperar_tela(page)
        etapas = [t for t in telas if t not in ORDEM_GLOBAIS]
        for i, tela in enumerate(etapas):
            prox = etapas[(i + 1) % len(etapas)] if len(etapas) > 1 else "overview"
            try:
                resultado["timers"][tela] = H.timer_orfao(page, ctx, tela, prox)
            except Exception as e:  # noqa: BLE001
                resultado["timers"][tela] = [f"erro: {e}"]

    nav.fechar()
    resultado["fim"] = datetime.now(timezone.utc).isoformat()
    saida = Path(a.saida) if a.saida else run_dir / "resultados.json"
    parcial = bool(a.casos or a.telas or a.so_auditoria)
    if parcial and saida.exists():   # execução parcial: mescla em cima do resultado anterior da rodada
        antigo = json.loads(saida.read_text())
        ids = {c["id"] for c in resultado["casos"]}
        antigo["casos"] = [c for c in antigo.get("casos", []) if c["id"] not in ids] + resultado["casos"]
        chaves = {(x["tela"], x["tema"], x["viewport"]) for x in resultado["auditorias"]}
        antigo["auditorias"] = [x for x in antigo.get("auditorias", [])
                                if (x["tela"], x["tema"], x["viewport"]) not in chaves] + resultado["auditorias"]
        antigo["revalidacoes"] = antigo.get("revalidacoes", []) + [{"quando": resultado["fim"], "casos": sorted(ids), "telas": telas}]
        resultado = antigo
    saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1))

    # ---- sumário ----
    casos = resultado["casos"]
    n_pass = sum(1 for c in casos if c["status"] == H.PASSA)
    n_fail = sum(1 for c in casos if c["status"] == H.FALHA)
    n_blq = sum(1 for c in casos if c["status"] == H.BLOQUEADO)
    aud_ruins = [x for x in resultado["auditorias"] if not x.get("ok")]
    timers_ruins = {k: v for k, v in resultado["timers"].items() if v}
    print(f"\ncasos: {n_pass} PASSA, {n_fail} FALHA, {n_blq} BLOQUEADO de {len(casos)}")
    print(f"auditorias com problema: {len(aud_ruins)} de {len(resultado['auditorias'])}")
    for x in aud_ruins:
        print(f"  - {x['tela']} [{x['tema']} {x['viewport']}]: " + "; ".join(
            x.get("problemas", []) + [f"pageerror: {e}" for e in x.get("pageerrors", [])]
            + [f"console {c}" for c in x.get("console", [])]
            + [f"HTTP {h['status']} {h['method']} {h['url']}" for h in x.get("http_erros", [])]
            + ([x["erro"]] if x.get("erro") else [])))
    if timers_ruins:
        print(f"timers órfãos: {timers_ruins}")
    print(f"resultados: {saida}")
    return 1 if (n_fail or aud_ruins or timers_ruins) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
