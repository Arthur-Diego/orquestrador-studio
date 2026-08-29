"""Casos da visão geral da campanha (`renderOverview` em `studio/web/app.js`)."""
from __future__ import annotations

from scripts.qa import harness as H

TELA = "overview"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)


@caso("C-OVERVIEW-01", "um card por etapa, com status igual ao do guia")
def cards(page, ctx):
    guide = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/guide").json()
    cards = page.locator("#main .ovgrid [data-go], #main .ovgrid .card, #main .ovgrid article")
    n_cards = page.locator("#main .ovgrid > *").count()
    ev = H.evidencia(page, ctx, "overview-cards")
    return H.verifica(n_cards == len(guide["steps"]), f"{n_cards} cards",
                      f"{n_cards} cards para {len(guide['steps'])} etapas (botões data-go={cards.count()})", ev)


@caso("C-OVERVIEW-02", "botão do card abre a etapa correspondente")
def card_abre(page, ctx):
    btn = page.locator("#main .ovgrid [data-go]:not([disabled])").first
    alvo = btn.get_attribute("data-go")
    btn.click()
    H.esperar_tela(page)
    return H.verifica(page.url.endswith(f"/{alvo}"), f"abriu {alvo}", f"url={page.url} esperado …/{alvo}")


@caso("C-OVERVIEW-03", "resumo de status (chips) soma o total de etapas")
def resumo(page, ctx):
    chips = page.locator("#main .ov-summary .chip").all_text_contents()
    import re
    soma = sum(int(m.group(1)) for c in chips if (m := re.match(r"\s*(\d+)", c)))
    return H.verifica(soma == len(ctx.steps), f"chips={chips}", f"chips={chips} somam {soma}, etapas={len(ctx.steps)}")


@caso("C-OVERVIEW-04", "campanha vazia: 'Você está na etapa 1' e todas as etapas 'a fazer'", pid="vazio")
def vazia(page, ctx):
    texto = page.locator("#main").inner_text()
    guide = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_vazio}/guide").json()
    ev = H.evidencia(page, ctx, "overview-vazia")
    return H.verifica("etapa 1" in texto.lower() and guide["current"] == ctx.steps[0]["id"],
                      "etapa 1 apontada", f"current={guide['current']} texto contém 'etapa 1'? {'etapa 1' in texto.lower()}", ev)


@caso("C-OVERVIEW-05", "trocar campanha no select recarrega o overview da outra campanha")
def troca_campanha(page, ctx):
    page.locator("#projSel").select_option(ctx.pid_vazio)
    H.esperar_tela(page)
    nome = (page.locator("#tbName").text_content() or "").strip()
    meta = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_vazio}").json()
    return H.verifica(page.url.endswith(f"#/{ctx.pid_vazio}/overview") and meta["name"] in nome,
                      f"topbar='{nome}'", f"url={page.url} topbar='{nome}' esperado '{meta['name']}'")
