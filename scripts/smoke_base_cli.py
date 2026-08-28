"""Smoke visual da feature base-cli-generation (ADH-OS-20260827-09) — fora do CI.

Sobe o Studio isolado, popula uma campanha (referência da etapa 1 + mood da etapa 2) e já importa
+ escolhe uma candidata de SITUAÇÃO via API (a "antes" da cadeia). Abre a etapa 3 no Playwright
(dark + light) e comprova, sem CLI da Higgsfield instalado (o caminho pago exige login do usuário):

- o botão "Gerar via CLI [extensão]" aparece no passo 03 e o rótulo muda por passo (o passo ativo
  default vira "rótulo", já que a situação foi escolhida) — prova dos 3 passos;
- a linha "Você também pode fazer no Higgsfield (UI ilimitada)" aparece;
- clicar "Gerar via CLI" deslogado mostra aviso claro (toast) e NÃO gera erro de console/JS;
- ao IMPORTAR um resultado no passo "rótulo" (via #baseUpload), aparecem o DOWNLOAD (`<a download>`)
  e o ANTES→DEPOIS (situação escolhida → rótulo importado).

Uso:  . .venv/bin/activate && python scripts/smoke_base_cli.py <pasta-de-saida>
"""
from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from PIL import Image


def png(color=(30, 120, 200), size=(640, 360)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def populate(base: str) -> str:
    c = httpx.Client(base_url=base, timeout=30)
    pid = c.post("/api/projects", json={"name": "Gelo Zero (smoke-cli)",
                                        "product": "energético Gelo Zero", "vibe": ""}).json()["id"]
    # Etapa 1 — referências
    c.post(f"/api/projects/{pid}/refs/import/upload",
           files=[("files", ("ref1.png", png((40, 90, 200)), "image/png")),
                  ("files", ("ref2.png", png((60, 200, 120)), "image/png"))])
    ref_ids = [x["id"] for x in c.get(f"/api/projects/{pid}/refs/candidates").json()]
    c.post(f"/api/projects/{pid}/refs/select", json={"ids": ref_ids, "notes": {}})
    # Etapa 2 — mood + paleta
    c.post(f"/api/projects/{pid}/mood/vibe/import/upload",
           files=[("files", ("vibe1.png", png((20, 40, 90)), "image/png"))])
    c.post(f"/api/projects/{pid}/mood/prompts/generate",
           json={"mode": "template", "purpose": "campanha", "tone": "gelo neon"})
    c.post(f"/api/projects/{pid}/mood/import/upload",
           files=[("files", ("m1.png", png((15, 35, 80)), "image/png"))],
           data={"prompt": "vibe gelo neon ciano"})
    mc = c.get(f"/api/projects/{pid}/mood/candidates").json()
    mids = [x["id"] for x in (mc if isinstance(mc, list) else mc.get("candidates", []))]
    c.post(f"/api/projects/{pid}/mood/select", json={"ids": mids, "note": "gelo neon ciano"})
    # Etapa 3 — importa e escolhe uma SITUAÇÃO (a "antes" da cadeia p/ o antes→depois do rótulo)
    c.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "template"})
    c.post(f"/api/projects/{pid}/base/import/upload",
           files=[("files", ("sit.png", png((80, 120, 210)), "image/png"))],
           data={"kind": "situation", "ref_id": ref_ids[0]})
    cid = c.get(f"/api/projects/{pid}/base/candidates").json()["candidates"][0]["id"]
    c.post(f"/api/projects/{pid}/base/brand", json={"name": "Gelo Zero", "description": "raio neon"})
    c.post(f"/api/projects/{pid}/base/select", json={"id": cid})
    c.close()
    return pid


def shoot(base: str, pid: str, out: Path) -> int:
    from playwright.sync_api import sync_playwright

    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    proofs: dict = {}
    # Uma imagem DISTINTA por esquema: o ingest deduplica por conteúdo, então reusar o mesmo PNG
    # importaria 0 na segunda passada (e o antes→depois não teria resultado novo).
    label_pngs = {"dark": out / "_label_dark.png", "light": out / "_label_light.png"}
    label_pngs["dark"].write_bytes(png((230, 80, 60)))
    label_pngs["light"].write_bytes(png((70, 200, 130)))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("dark", "light"):
            label_png = label_pngs[scheme]
            ctx = browser.new_context(viewport={"width": 1440, "height": 1500}, color_scheme=scheme)
            page = ctx.new_page()
            page.on("pageerror", lambda e, s=scheme: errors.append(f"[{s}] pageerror: {e}"))
            page.on("console", lambda m, s=scheme: errors.append(f"[{s}] console.{m.type}: {m.text}")
                    if m.type in ("error", "warning") else None)
            page.goto(f"{base}/#/{pid}/base")
            page.wait_for_selector("#btnBaseCli", timeout=15000)
            page.wait_for_timeout(600)
            # passo ativo default é "rótulo" (situação já escolhida) → prova o rótulo por passo
            cli_label_rotulo = page.inner_text("#btnBaseCli")
            hf_line = page.query_selector(".bs-hf")
            hf_txt = hf_line.inner_text() if hf_line else ""
            # clicar "Gerar via CLI" deslogado → aviso claro, sem gerar/500 (o CLI não está instalado)
            page.click("#btnBaseCli")
            page.wait_for_timeout(700)
            toast_txt = page.inner_text("#toast")
            # o rótulo por passo: volta pro passo "situação" e confirma que o texto muda
            page.click('#baseChain [data-step="situation"]')
            page.wait_for_timeout(200)
            cli_label_situacao = page.inner_text("#btnBaseCli")
            page.click('#baseChain [data-step="upscale"]')
            page.wait_for_timeout(200)
            cli_label_upscale = page.inner_text("#btnBaseCli")
            # volta pro rótulo e IMPORTA um resultado → download + antes→depois
            page.click('#baseChain [data-step="label"]')
            page.wait_for_timeout(200)
            page.set_input_files("#baseUpload", str(label_png))
            try:
                page.wait_for_selector("#baseGenResult .pair", timeout=8000)
            except Exception:
                print(f"[{scheme}] DEBUG toast:", page.inner_text("#toast"))
                print(f"[{scheme}] DEBUG genResult:", page.inner_html("#baseGenResult")[:200])
                print(f"[{scheme}] DEBUG active step:",
                      page.get_attribute('#baseChain .st.on', 'data-step'))
                raise
            page.wait_for_timeout(400)
            dl = page.query_selector("#baseGenResult a.dl[download]")
            figs = page.query_selector_all("#baseGenResult figcaption")
            fig_txt = [f.inner_text() for f in figs]
            proofs[scheme] = {
                "cli_button_visible": page.is_visible("#btnBaseCli"),
                "cli_label_rotulo": cli_label_rotulo,
                "cli_label_situacao": cli_label_situacao,
                "cli_label_upscale": cli_label_upscale,
                "ext_marker": bool(page.query_selector(".bs-cli .ext")),
                "hf_unlimited_line": ("Higgsfield (UI ilimitada)" in hf_txt),
                "logged_out_warning": ("higgsfield" in toast_txt.lower() and "login" in toast_txt.lower()),
                "download_present": bool(dl),
                "download_href_files": bool(dl and "/files/" in (dl.get_attribute("href") or "")),
                "before_after": any("antes" in t for t in fig_txt) and any("depois" in t for t in fig_txt),
                "arrow_present": bool(page.query_selector("#baseGenResult .arrow")),
            }
            page.screenshot(path=str(out / f"base-cli-{scheme}.png"), full_page=True)
            box = page.evaluate(
                "() => { const s = document.querySelectorAll('section.panel')[3].getBoundingClientRect();"
                " return {x:s.x, y:s.y, width:s.width, height:s.height}; }")
            page.screenshot(path=str(out / f"panel03-{scheme}.png"),
                            clip={"x": box["x"], "y": box["y"],
                                  "width": box["width"], "height": min(box["height"], 1200)})
            ctx.close()
        browser.close()
    (out / "proofs.json").write_text(json.dumps({"proofs": proofs, "errors": errors}, indent=2))
    print(json.dumps(proofs, indent=2))
    print("errors:", errors)
    ok = (not errors and all(
        v["cli_button_visible"] and v["ext_marker"] and v["hf_unlimited_line"]
        and v["cli_label_rotulo"] == "Gerar rótulo via CLI"
        and v["cli_label_situacao"] == "Gerar situação via CLI"
        and v["cli_label_upscale"] == "Gerar upscale via CLI"
        and v["logged_out_warning"] and v["download_present"] and v["download_href_files"]
        and v["before_after"] and v["arrow_present"]
        for v in proofs.values()))
    print("SMOKE", "OK" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "../_base-cli-prints").resolve()
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    root = Path(__file__).resolve().parent.parent
    projects_dir = out / "_projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "STUDIO_PROJECTS": str(projects_dir),
           "STUDIO_MOODBOARDS": str(out / "_moodboards"),
           "STUDIO_STATE": str(out / "_state"),
           "STUDIO_DOWNLOADS": str(out / "_downloads"), "PORT": str(port)}
    (out / "_downloads").mkdir(parents=True, exist_ok=True)
    srv = subprocess.Popen(["uvicorn", "studio.app:app", "--host", "127.0.0.1", "--port", str(port)],
                           cwd=str(root), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{base}/api/steps", timeout=2).status_code == 200:
                    break
            except Exception:
                time.sleep(0.5)
        else:
            print("servidor não subiu")
            return 2
        pid = populate(base)
        print("pid:", pid)
        return shoot(base, pid, out)
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except Exception:
            srv.kill()


if __name__ == "__main__":
    raise SystemExit(main())
