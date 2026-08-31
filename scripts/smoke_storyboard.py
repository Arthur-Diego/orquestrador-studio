"""Smoke visual do storyboard guiado por pré-roteiro `[extensão]` (ADR-018), fora do CI (ADR-008).

Popula um projeto NO DISCO (base, fotos-semente, pré-roteiro, e a cena 1 com semente/prompt/foto/
frames ordenados) SEM gerar nada de verdade (nada de CLI/Claude/crédito) e prova que a tela:
- mostra o fluxo (sementes + pré-roteiro, cenas em cards);
- abre a cena e renderiza os passos c→g sem erro de JS/console.

Uso (o servidor precisa usar os MESMOS STUDIO_PROJECTS/STATE/MOODBOARDS deste processo):

    . .venv/bin/activate
    STUDIO_PROJECTS=/tmp/sb/projects STUDIO_STATE=/tmp/sb/state STUDIO_MOODBOARDS=/tmp/sb/mb \\
      python scripts/smoke_storyboard.py http://127.0.0.1:8766 <pasta-de-saida> [dark]

Sai com código 1 se houver erro de JS/console ou se a tela não montar os blocos esperados.
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

from playwright.async_api import async_playwright


def _png(color=(40, 90, 160)) -> bytes:
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(b, "PNG")
    return b.getvalue()


def populate(base_url: str) -> str:
    """Cria e popula um projeto no disco, devolvendo o pid. Usa os módulos do Studio + a API."""
    import httpx

    from studio.common import ingest
    from studio.refs.service import project_dir

    r = httpx.post(f"{base_url}/api/projects", json={"name": "Storyboard Smoke", "product": "energy drink"})
    pid = r.json()["id"]
    root = project_dir(pid)
    (root / "base").mkdir(parents=True, exist_ok=True)
    (root / "base" / "base_final.png").write_bytes(_png((30, 120, 200)))

    # fotos-semente (multishot da base) — ingeridas direto, sem CLI
    for i in range(3):
        ingest.ingest_bytes(root, "storyboard/seeds", _png((60 + i * 40, 80, 140)), "cli",
                            f"seed{i}.png", "another point of view", {"role": "multishot", "parent": "base"})
    seeds = ingest.load_candidates(root, "storyboard/seeds")
    seed_id = seeds[0]["id"]

    # pré-roteiro (via API de edição — sem Claude)
    scenes = [{"title": "Abertura", "text": "Plano de abertura na nevasca", "arc": "comeco"},
              {"title": "Descoberta", "text": "A lata aparece", "arc": "descoberta"},
              {"title": "Ação", "text": "A ação no auge", "arc": "acao"}]
    httpx.put(f"{base_url}/api/projects/{pid}/storyboard/prescript", json={"scenes": scenes})

    # cena 1: semente + prompt + foto + 2 frames ordenados
    httpx.post(f"{base_url}/api/projects/{pid}/storyboard/scenes/cena01/seed", json={"seed_id": seed_id})
    httpx.put(f"{base_url}/api/projects/{pid}/storyboard/scenes/cena01/prompt",
              json={"prompt": "ultra realistic cinematic photograph of the can in fresh snow, natural "
                              "light, film grain, sharp focus, hyper detailed textures, photorealistic"})
    (root / "storyboard" / "cena01").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "cena01" / "base.png").write_bytes(_png((90, 110, 160)))
    for i in range(2):
        ingest.ingest_bytes(root, "storyboard/cena01", _png((120, 60 + i * 40, 90)), "cli",
                            f"frame{i}.png", "another point of view", {"role": "multishot", "parent": "cena01:photo"})
    frames = ingest.load_candidates(root, "storyboard/cena01")
    httpx.post(f"{base_url}/api/projects/{pid}/storyboard/scenes/cena01/order",
               json={"shots": [{"id": frames[0]["id"], "upscaled": True}, {"id": frames[1]["id"], "upscaled": True}]})
    return pid


async def shoot(base_url: str, pid: str, out: Path, dark: bool) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 1200},
                                        color_scheme="dark" if dark else "light")
        page = await ctx.new_page()
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                if m.type in ("error", "warning") else None)

        await page.goto(f"{base_url}/#/{pid}/storyboard")
        await page.wait_for_timeout(1600)
        for sel, nome in [("#sbSeeds", "sementes"), ("#sbPrescript", "pré-roteiro"), ("#sbScenes", "cenas")]:
            if await page.query_selector(sel) is None:
                errors.append(f"storyboard sem bloco: {nome} ({sel})")
        await page.screenshot(path=str(out / "storyboard.png"), full_page=True)

        # abre a cena 1 e confere os passos c→g
        head = await page.query_selector('[data-toggle="cena01"]')
        if head is None:
            errors.append("card da cena 1 ([data-toggle=cena01]) ausente")
        else:
            await head.click()
            await page.wait_for_timeout(1000)
            for sel, nome in [("[data-seed]", "escolher semente"), ("[data-prompt]", "prompt"),
                              ("[data-photo]", "foto"), ("[data-frames]", "frames")]:
                if await page.query_selector(sel) is None:
                    errors.append(f"cena 1 sem controle: {nome} ({sel})")
            await page.screenshot(path=str(out / "storyboard-cena.png"), full_page=True)

        await browser.close()
    (out / "errors.txt").write_text("\n".join(errors))
    return errors


def main() -> int:
    args = sys.argv[1:]
    base_url = args[0] if args else "http://127.0.0.1:8766"
    rest = args[1:]
    dark = "dark" in rest
    rest = [a for a in rest if a != "dark"]
    out = Path(rest[0]) if rest else Path("scripts/_smoke_storyboard")
    pid = populate(base_url)
    errors = asyncio.run(shoot(base_url, pid, out, dark))
    if errors:
        print("SMOKE FALHOU:")
        for e in errors:
            print(" -", e)
        return 1
    print(f"Smoke OK ({pid}) — prints em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
