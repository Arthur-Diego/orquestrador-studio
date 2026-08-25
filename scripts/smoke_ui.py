"""Smoke visual do Studio (fora do CI — ADR-008): prints das 11 etapas + prova de que nenhum
timer sobrevive à troca de tela (critério cross-feature 3 da wave 2).

Uso (com o servidor no ar e o Chromium do Playwright instalado):

    . .venv/bin/activate
    python scripts/smoke_ui.py http://127.0.0.1:8765 <pid> <pasta-de-saida> [dark] [--timers]

Sai com código 1 se houver erro de JS/console em alguma tela ou se alguma etapa continuar
fazendo requisições 8 s depois de o usuário ter navegado para outra.
"""
from __future__ import annotations

import asyncio
import collections
import sys
from pathlib import Path

from playwright.async_api import async_playwright


async def shoot(base: str, pid: str, out: Path, dark: bool) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900},
                                        color_scheme="dark" if dark else "light")
        page = await ctx.new_page()
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                if m.type in ("error", "warning") else None)
        await page.goto(f"{base}/#/{pid}/overview")
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(out / "00-overview.png"), full_page=True)
        steps = await (await page.request.get(f"{base}/api/steps")).json()
        for s in steps:
            if s["status"] != "ready":
                continue
            await page.goto(f"{base}/#/{pid}/{s['id']}")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=str(out / f"{s['n']:02d}-{s['id']}.png"), full_page=True)
        await browser.close()
    (out / "errors.txt").write_text("\n".join(errors))
    return errors


async def timers(base: str, pid: str) -> dict[str, dict]:
    """Para cada etapa: abre, navega para a seguinte e conta requisições da anterior em 8 s."""
    leaks: dict[str, dict] = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        reqs: collections.Counter = collections.Counter()
        page.on("request", lambda r: reqs.update([r.url.replace(base, "")]))
        steps = [s["id"] for s in await (await page.request.get(f"{base}/api/steps")).json()
                 if s["status"] == "ready"]
        for i, s in enumerate(steps):
            nxt = steps[(i + 1) % len(steps)]
            await page.goto(f"{base}/#/{pid}/{s}")
            await page.wait_for_timeout(2500)
            await page.goto(f"{base}/#/{pid}/{nxt}")
            await page.wait_for_timeout(1500)
            reqs.clear()
            await page.wait_for_timeout(8000)
            leaks[s] = {u: n for u, n in reqs.items() if f"/{s}/" in u and f"/{nxt}/" not in u}
        await browser.close()
    return leaks


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    base, pid, out = sys.argv[1].rstrip("/"), sys.argv[2], Path(sys.argv[3])
    dark = "dark" in sys.argv[4:]
    errors = asyncio.run(shoot(base, pid, out, dark))
    print(f"prints em {out} ({'escuro' if dark else 'claro'}) — erros de JS: {len(errors)}")
    for e in errors:
        print("  ", e)
    rc = 1 if errors else 0
    if "--timers" in sys.argv:
        leaks = asyncio.run(timers(base, pid))
        for s, bad in leaks.items():
            print(f"{s:<11} {'OK' if not bad else 'TIMER ÓRFÃO ' + str(bad)}")
        rc = rc or (1 if any(leaks.values()) else 0)
    return rc


if __name__ == "__main__":
    sys.exit(main())
