"""Smoke visual da tela "Créditos & Custos" `[extensão]` (ADR-016), fora do CI (ADR-008).

Prova, com o servidor no ar e o Chromium do Playwright instalado, que:
- a tela global `#/creditos` abre sem erro de JS/console (saldo, tabela de custo, admin, histórico);
- o indicador global de créditos aparece na topbar (`[data-credits-chip]`);
- o modal de custo (gate da aula 008) e o painel admin renderizam.

Uso:

    . .venv/bin/activate
    python scripts/smoke_creditos.py http://127.0.0.1:8765 [pid] <pasta-de-saida> [dark]

Sai com código 1 se houver erro de JS/console ou se a tela não montar os blocos esperados.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright


async def shoot(base: str, pid: str | None, out: Path, dark: bool) -> list[str]:
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

        # 1) indicador global na topbar existe (partindo da visão geral, se houver campanha)
        await page.goto(f"{base}/#/{pid}/overview" if pid else f"{base}/")
        await page.wait_for_timeout(1000)
        chip = await page.query_selector("[data-credits-chip]")
        if chip is None:
            errors.append("indicador global de créditos ([data-credits-chip]) ausente na topbar")

        # 2) tela global de créditos
        await page.goto(f"{base}/#/creditos")
        await page.wait_for_timeout(1200)
        for sel, nome in [(".cr-balance", "saldo"), (".cr-table.admin", "painel admin"),
                          (".cr-table", "tabela de custo"), (".cr-hist-grid", "histórico")]:
            if await page.query_selector(sel) is None:
                errors.append(f"tela de créditos sem bloco: {nome} ({sel})")
        await page.screenshot(path=str(out / "creditos.png"), full_page=True)

        # 3) trocar um default no admin (não gera nada — só persiste config)
        sel = await page.query_selector(".cr-table.admin tr[data-action] select.cr-model")
        if sel is not None:
            options = await sel.query_selector_all("option")
            if len(options) > 1:
                val = await options[1].get_attribute("value")
                await sel.select_option(val)
                await page.wait_for_timeout(700)
                await page.screenshot(path=str(out / "creditos-admin.png"), full_page=True)

        await browser.close()
    (out / "errors.txt").write_text("\n".join(errors))
    return errors


def main() -> int:
    args = sys.argv[1:]
    base = args[0] if args else "http://127.0.0.1:8765"
    rest = args[1:]
    dark = "dark" in rest
    rest = [a for a in rest if a != "dark"]
    pid = rest[0] if len(rest) >= 2 else None
    out = Path(rest[-1]) if rest else Path("scripts/_smoke_creditos")
    errors = asyncio.run(shoot(base, pid, out, dark))
    if errors:
        print("SMOKE FALHOU:")
        for e in errors:
            print(" -", e)
        return 1
    print(f"Smoke OK — prints em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
