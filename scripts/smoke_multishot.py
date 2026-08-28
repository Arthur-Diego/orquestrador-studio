"""Smoke visual do componente de multishot `[extensão]` (ADR-017), fora do CI (ADR-008).

Prova, com o servidor no ar e o Chromium do Playwright instalado, que:
- o editor de um mood board mostra a ação "▨ ângulos" nas imagens candidatas;
- clicar nela abre o modal do componente `Studio.multishot` (origem, controle de ângulos, galeria);
- nada disso gera nada de verdade (o smoke NÃO clica em "Gerar" — não gasta crédito).

Uso (o board precisa ter ao menos uma imagem importada):

    . .venv/bin/activate
    python scripts/smoke_multishot.py http://127.0.0.1:8765 <mbid> <pasta-de-saida> [dark]

Sai com código 1 se houver erro de JS/console ou se o modal não montar.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright


async def shoot(base: str, mbid: str, out: Path, dark: bool) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 1000},
                                        color_scheme="dark" if dark else "light")
        page = await ctx.new_page()
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                if m.type in ("error", "warning") else None)

        await page.goto(f"{base}/#/moodboards/{mbid}")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(out / "board.png"), full_page=True)

        btn = await page.query_selector(".ms-btn")
        if btn is None:
            errors.append("ação '▨ ângulos' ([.ms-btn]) ausente nas imagens do board")
        else:
            # hover força a opacidade; clicar abre o modal do componente
            card = await page.query_selector(".gallery .card")
            if card:
                await card.hover()
            await btn.click()
            await page.wait_for_timeout(800)
            if await page.query_selector(".ms-wrap") is None:
                errors.append("modal do componente de multishot (.ms-wrap) não montou")
            if await page.query_selector("#msGen") is None:
                errors.append("botão 'Gerar ângulos via CLI' (#msGen) ausente no modal")
            await page.screenshot(path=str(out / "multishot-modal.png"), full_page=True)

        await browser.close()
    (out / "errors.txt").write_text("\n".join(errors))
    return errors


def main() -> int:
    args = sys.argv[1:]
    base = args[0] if args else "http://127.0.0.1:8765"
    rest = args[1:]
    dark = "dark" in rest
    rest = [a for a in rest if a != "dark"]
    if len(rest) < 2:
        print("uso: smoke_multishot.py <base> <mbid> <out> [dark]")
        return 2
    mbid, out = rest[0], Path(rest[1])
    errors = asyncio.run(shoot(base, mbid, out, dark))
    if errors:
        print("SMOKE FALHOU:")
        for e in errors:
            print(" -", e)
        return 1
    print(f"Smoke OK — prints em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
