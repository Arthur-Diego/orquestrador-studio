"""Smoke visual da feature base-prompt-provenance (ADH-OS-20260827-08) — fora do CI.

Sobe o Studio num diretório isolado, popula uma campanha (referência da etapa 1 + mood da etapa 2),
gera o prompt da base (modo template, instantâneo) e injeta uma resposta do bot no formato de 5
linhas para provar a visão anotada. Abre a etapa 3 no Playwright (dark + light) e comprova que:

- o cabeçalho de junção aparece (thumb da referência + thumbs do mood + paleta + o texto da junção);
- a visão anotada mostra as 5 linhas com chip de proveniência (referência / mood / técnico) e o
  parágrafo rotulado "junção";
- o textarea copiável continua com o prompt COMPLETO;
- 0 erro de console/JS.

Uso:  . .venv/bin/activate && python scripts/smoke_base_provenance.py <pasta-de-saida>
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

# Um prompt no padrão do bot da aula (parágrafo + 5 linhas) — é o que o Claude devolveria; aqui é
# injetado direto no prompts.json para o smoke ser instantâneo e determinístico.
BOT_PROMPT = (
    "Ultra-realistic commercial product photography of the energy drink can in the exact same "
    "snowy-forest situation as the reference, in the campaign mood: icy neon light and cold blues.\n\n"
    "Camera: RED Komodo 6K, 50mm lens, T2.8, shallow depth of field, tack-sharp focus.\n"
    "Lighting: diffused cold key light, neon rim lights on both sides, subtle backlight.\n"
    "Composition: clean, minimal, premium, centered hero shot.\n"
    "Color grading: icy blues, teal shadows, neon cyan and pink highlights, cinematic contrast.\n"
    "Style: futuristic winter commercial, ultra-photorealistic, high resolution, no illustration."
)


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


def populate(base: str, projects_dir: Path) -> str:
    c = httpx.Client(base_url=base, timeout=30)
    resp = c.post("/api/projects", json={"name": "Gelo Zero (smoke)", "product": "energético Gelo Zero",
                                         "vibe": ""})
    if resp.status_code not in (200, 201) or "id" not in resp.json():
        raise RuntimeError(f"POST /api/projects → {resp.status_code}: {resp.text[:300]}")
    pid = resp.json()["id"]
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
           files=[("files", ("m1.png", png((15, 35, 80)), "image/png")),
                  ("files", ("m2.png", png((25, 45, 95)), "image/png"))],
           data={"prompt": "vibe gelo neon ciano"})
    mc = c.get(f"/api/projects/{pid}/mood/candidates").json()
    mids = [x["id"] for x in (mc if isinstance(mc, list) else mc.get("candidates", []))]
    c.post(f"/api/projects/{pid}/mood/select", json={"ids": mids, "note": "gelo neon ciano"})
    # Etapa 3 — gera o prompt (template) e injeta a resposta do bot (5 linhas) no histórico
    c.post(f"/api/projects/{pid}/base/prompts/generate", json={"mode": "template"})
    r = c.get(f"/api/projects/{pid}/base/prompts").json()
    ref = r["refs"][0]
    hist_path = projects_dir / pid / "base" / "prompts.json"
    hist = json.loads(hist_path.read_text()) if hist_path.exists() else []
    hist.insert(0, {"ref_id": ref["ref_id"], "ref_file": ref["file"], "mode": "images",
                    "source": "claude", "prompt": BOT_PROMPT, "created": "2026-08-27T00:00:00"})
    hist_path.write_text(json.dumps(hist, ensure_ascii=False, indent=1))
    # confere que o backend já expõe a proveniência com partes rotuladas
    prov = c.get(f"/api/projects/{pid}/base/prompts").json()["refs"][0]["provenance"]
    froms = {p["from"] for p in prov["parts"]}
    assert froms == {"reference", "mood", "technical"}, froms
    c.close()
    return pid


def shoot(base: str, pid: str, out: Path) -> int:
    from playwright.sync_api import sync_playwright

    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    proofs: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("dark", "light"):
            ctx = browser.new_context(viewport={"width": 1440, "height": 1400}, color_scheme=scheme)
            page = ctx.new_page()
            page.on("pageerror", lambda e, s=scheme: errors.append(f"[{s}] pageerror: {e}"))
            page.on("console", lambda m, s=scheme: errors.append(f"[{s}] console.{m.type}: {m.text}")
                    if m.type in ("error", "warning") else None)
            page.goto(f"{base}/#/{pid}/base")
            page.wait_for_selector("#baseJunction .thumbs img", timeout=15000)
            page.wait_for_timeout(800)
            junction = page.query_selector("#baseJunction")
            prov = page.query_selector("#baseProvenance")
            chips = page.query_selector_all("#baseProvenance .bs-chip")
            chip_kinds = sorted({c.get_attribute("class").split("from-")[1].split()[0]
                                 for c in chips if "from-" in (c.get_attribute("class") or "")})
            textarea = page.query_selector("#basePrompts textarea")
            ta_val = textarea.input_value() if textarea else ""
            proofs[scheme] = {
                "junction_visible": bool(junction and junction.is_visible()),
                "junction_has_ref_thumb": bool(page.query_selector('#baseJunction img[alt^="referência"]')),
                "junction_mood_thumbs": len(page.query_selector_all('#baseJunction img[alt="imagem do mood"]')),
                "junction_swatches": len(page.query_selector_all("#baseJunction .sw")),
                "provenance_visible": bool(prov and prov.is_visible()),
                "chip_kinds": chip_kinds,
                "chip_count": len(chips),
                "ext_marker": bool(page.query_selector("#baseProvenance .ext")),
                "textarea_has_full_prompt": ("Camera:" in ta_val and "Composition:" in ta_val),
            }
            page.screenshot(path=str(out / f"base-provenance-{scheme}.png"), full_page=True)
            # crop do painel 01 para a prova ficar legível
            panel = page.query_selector("#baseJunction")
            if panel:
                box = page.evaluate(
                    "() => { const s = document.querySelectorAll('section.panel')[1].getBoundingClientRect();"
                    " return {x:s.x, y:s.y, width:s.width, height:s.height}; }")
                page.screenshot(path=str(out / f"panel01-{scheme}.png"),
                                clip={"x": box["x"], "y": box["y"],
                                      "width": box["width"], "height": min(box["height"], 1200)})
            ctx.close()
        browser.close()
    (out / "proofs.json").write_text(json.dumps({"proofs": proofs, "errors": errors}, indent=2))
    print(json.dumps(proofs, indent=2))
    print("errors:", errors)
    ok = (not errors
          and all(v["junction_visible"] and v["junction_has_ref_thumb"] and v["junction_mood_thumbs"] >= 1
                  and v["junction_swatches"] >= 1 and v["provenance_visible"]
                  and v["chip_kinds"] == ["join", "mood", "reference", "technical"]
                  and v["ext_marker"] and v["textarea_has_full_prompt"]
                  for v in proofs.values()))
    print("SMOKE", "OK" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "../_provenance-prints").resolve()
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
        pid = populate(base, projects_dir)
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
