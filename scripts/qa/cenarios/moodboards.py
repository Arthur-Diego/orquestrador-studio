"""Casos da área global "Mood boards" `[extensão]` (`studio/web/moodboards.js` + `studio/moodboards/`).

Duas telas na mesma rota reservada: a BIBLIOTECA (`#/moodboards`) e o EDITOR de um board
(`#/moodboards/<mbid>`). Como `ctx.rota("moodboards")` devolve sempre a lista, cada caso que
precisa do editor chama `_editor(page, ctx, mbid)`.

Todos os casos são registrados com `pid=None`: a área é campanha-independente e `H.abrir_tela`
levanta RuntimeError se receber um pid que a rota não carrega.

Regras de higiene: o board do seed (`ctx.mbid`, 3 candidatas) é compartilhado — todo caso que o
altera desfaz a alteração no fim. Casos destrutivos usam boards descartáveis criados pela API.
NUNCA clicar `#btnMbOpenFolder` (abre o explorador do SO).
"""
from __future__ import annotations

import json
import random
import re

from scripts.qa import harness as H

TELA = "moodboards"
CASOS: list[H.Caso] = []
_reg = H.registrador(TELA, CASOS)
JSON = {"content-type": "application/json"}


def caso(id: str, titulo: str):
    """Registra um caso da área global (sempre `pid=None` — a rota não tem campanha)."""
    return _reg(id, titulo, pid=None)


# ---------- helpers locais ----------
def _slug(nome: str) -> str:
    """Mesmo `slugify` do serviço (`studio/moodboards/service.py`) — o mbid é o slug do nome."""
    return re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-") or "moodboard"


def _lista(page, ctx) -> None:
    """Deixa a biblioteca (lista) renderizada e fresca, venha de onde vier."""
    if page.url.endswith("#/moodboards"):
        page.evaluate("() => window.Studio.moodboards.open(null)")
    else:
        H.ir(page, ctx, "#/moodboards", espera_ms=200)
    page.wait_for_selector("#main .stephead, #main .empty-state", timeout=H.TIMEOUT_MS)
    page.wait_for_timeout(200)


def _editor(page, ctx, mbid: str | None = None) -> str:
    """Abre o editor do board e espera os três painéis montarem."""
    mbid = mbid or ctx.mbid
    alvo = f"#/moodboards/{mbid}"
    if page.url.endswith(alvo):
        page.evaluate("id => window.Studio.moodboards.open(id)", mbid)
    else:
        H.ir(page, ctx, alvo, espera_ms=200)
    page.wait_for_selector("#mbGallery", timeout=H.TIMEOUT_MS)
    page.wait_for_timeout(200)
    return mbid


def _cands(page, ctx, mbid: str | None = None) -> list[dict]:
    return H.api(page, ctx, "get", f"/api/moodboards/{mbid or ctx.mbid}/candidates").json()


def _ids(cands: list[dict]) -> set[str]:
    return {c["id"] for c in cands}


def _apagar_cands(page, ctx, mbid: str, ids) -> None:
    for cid in ids:
        H.api(page, ctx, "delete", f"/api/moodboards/{mbid}/candidates/{cid}")


def _selecionar(page, ctx, mbid: str, ids: list[str]) -> None:
    H.api(page, ctx, "post", f"/api/moodboards/{mbid}/select",
          data=json.dumps({"ids": ids}), headers=JSON)


def _board_temp(page, ctx, nome: str) -> str:
    """Cria (ou recria) um board descartável e devolve o mbid — para os casos destrutivos."""
    mbid = _slug(nome)
    H.api(page, ctx, "delete", f"/api/moodboards/{mbid}")
    r = H.api(page, ctx, "post", "/api/moodboards",
              data=json.dumps({"name": nome, "note": "descartável do QA"}), headers=JSON)
    if not r.ok:
        raise RuntimeError(f"não criou o board temporário {mbid}: HTTP {r.status} {r.text()[:120]}")
    return r.json()["id"]


def _apagar_board(page, ctx, mbid: str) -> None:
    H.api(page, ctx, "delete", f"/api/moodboards/{mbid}")


def _png(ctx, nome: str, dest=None):
    """PNG de conteúdo ÚNICO por chamada (o ingest deduplica por sha1 do conteúdo)."""
    from PIL import Image
    d = dest or (ctx.run_dir / "fixtures")
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{nome}.png"
    cor = (random.randrange(30, 250), random.randrange(30, 250), random.randrange(30, 250))
    Image.new("RGB", (640, 400), cor).save(p, "PNG")
    return p


def _espiar_progresso(page) -> None:
    """Arma um MutationObserver para saber se o modal de progresso chegou a existir (ele some
    sozinho ~900 ms depois de terminar — esperar por ele com `wait_for_selector` é corrida)."""
    page.evaluate("""() => {
      window.__qaProg = 0;
      if (window.__qaObs) window.__qaObs.disconnect();
      window.__qaObs = new MutationObserver(() => {
        if (document.querySelector('.progress-modal')) window.__qaProg++;
      });
      window.__qaObs.observe(document.body, { childList: true });
    }""")


def _progresso_visto(page) -> int:
    return page.evaluate("() => { if (window.__qaObs) window.__qaObs.disconnect(); return window.__qaProg || 0; }")


# ---------- biblioteca ----------
@caso("C-MOODBOARDS-01", "biblioteca lista um card por board de /api/moodboards, com contagem e mosaico")
def lista(page, ctx):
    _lista(page, ctx)
    boards = H.api(page, ctx, "get", "/api/moodboards").json()
    cards = page.locator("#main .mb-grid .mb-card")
    ids = cards.evaluate_all("els => els.map(e => e.dataset.mb)")
    seed = next((b for b in boards if b["id"] == ctx.mbid), None)
    card = page.locator(f"#main .mb-card[data-mb='{ctx.mbid}']")
    txt = (card.text_content() or "") if card.count() else ""
    ev = H.evidencia(page, ctx, "mb-lista")
    return H.verifica(ids == [b["id"] for b in boards] and seed is not None
                      and f"{seed['count']} imagem(ns)" in txt and seed["name"] in txt,
                      f"{len(ids)} boards; card do seed com '{seed['count']} imagem(ns)'" if seed else "",
                      f"cards={ids} api={[b['id'] for b in boards]} card='{txt[:120]}'", ev)


@caso("C-MOODBOARDS-02", "clique no card abre o editor #/moodboards/<mbid>")
def abre_editor(page, ctx):
    _lista(page, ctx)
    page.locator(f"#main .mb-card[data-mb='{ctx.mbid}']").click()
    page.wait_for_selector("#mbGallery", timeout=H.TIMEOUT_MS)
    nome = (page.locator("#mbTitle").text_content() or "").strip()
    meta = H.api(page, ctx, "get", f"/api/moodboards/{ctx.mbid}").json()
    return H.verifica(page.url.endswith(f"#/moodboards/{ctx.mbid}") and nome == meta["name"],
                      f"editor de '{nome}'", f"url={page.url} título='{nome}' esperado '{meta['name']}'")


@caso("C-MOODBOARDS-03", "Enter no card focado abre o editor (acessibilidade por teclado)")
def abre_editor_teclado(page, ctx):
    _lista(page, ctx)
    card = page.locator(f"#main .mb-card[data-mb='{ctx.mbid}']")
    card.focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(600)
    ok = page.url.endswith(f"#/moodboards/{ctx.mbid}")
    return H.verifica(ok, "Enter abriu o editor",
                      f"url={page.url} (tabindex={card.get_attribute('tabindex') if card.count() else '?'})")


@caso("C-MOODBOARDS-04", "'Novo mood board' abre modal com nome e nota")
def modal_novo(page, ctx):
    _lista(page, ctx)
    page.locator("#btnNewBoard").click()
    m = H.modal(page)
    m.wait_for()
    campos = (m.locator("#mbName").count(), m.locator("#mbNote").count(),
              m.locator("#mbName").get_attribute("required"))
    ev = H.evidencia(page, ctx, "mb-modal-novo", full_page=False)
    H.fechar_modal(page)
    sumiu = not H.modal(page).count() or not H.modal(page).is_visible()
    return H.verifica(campos[0] == 1 and campos[1] == 1 and campos[2] is not None and sumiu,
                      "modal com #mbName (required) e #mbNote, fecha no ✕",
                      f"mbName={campos[0]} mbNote={campos[1]} required={campos[2]} fechou={sumiu}", ev)


@caso("C-MOODBOARDS-05", "nome vazio bloqueia a criação com toast e mantém o modal aberto")
def nome_obrigatorio(page, ctx):
    _lista(page, ctx)
    antes = len(H.api(page, ctx, "get", "/api/moodboards").json())
    page.locator("#btnNewBoard").click()
    m = H.modal(page)
    m.wait_for()
    m.locator("#mbName").fill("   ")
    m.locator("button[type=submit]").click()
    t = H.esperar_toast(page, "nome")
    aberto = m.is_visible()
    depois = len(H.api(page, ctx, "get", "/api/moodboards").json())
    ev = H.evidencia(page, ctx, "mb-nome-vazio", full_page=False)
    H.fechar_modal(page)
    return H.verifica(bool(t) and aberto and depois == antes, f"toast='{t}', nada criado",
                      f"toast='{t}' modal aberto={aberto} boards {antes}→{depois}", ev)


@caso("C-MOODBOARDS-06", "nome duplicado devolve 409 com mensagem amigável no toast")
def nome_duplicado(page, ctx):
    _lista(page, ctx)
    nome = H.api(page, ctx, "get", f"/api/moodboards/{ctx.mbid}").json()["name"]
    antes = len(H.api(page, ctx, "get", "/api/moodboards").json())
    page.locator("#btnNewBoard").click()
    m = H.modal(page)
    m.wait_for()
    m.locator("#mbName").fill(nome)
    m.locator("button[type=submit]").click()
    t = H.esperar_toast(page, "já existe")
    depois = len(H.api(page, ctx, "get", "/api/moodboards").json())
    ev = H.evidencia(page, ctx, "mb-nome-duplicado", full_page=False)
    H.fechar_modal(page)
    return H.verifica(bool(t) and depois == antes and "Error" not in t,
                      f"toast='{t}', nenhum board criado",
                      f"toast='{t}' boards {antes}→{depois} (esperado 409 amigável)", ev)


@caso("C-MOODBOARDS-07", "criar board pelo modal grava no disco e abre o editor do board novo")
def cria_board(page, ctx):
    nome = "QA Board Novo"
    mbid = _slug(nome)
    _apagar_board(page, ctx, mbid)
    _lista(page, ctx)
    try:
        page.locator("#btnNewBoard").click()
        m = H.modal(page)
        m.wait_for()
        m.locator("#mbName").fill(nome)
        m.locator("#mbNote").fill("nota do QA")
        m.locator("button[type=submit]").click()
        t = H.esperar_toast(page, "criado")
        page.wait_for_selector("#mbGallery", timeout=H.TIMEOUT_MS)
        meta_disco = ctx.moodboards_dir / mbid / "moodboard.json"
        no_disco = meta_disco.exists() and json.loads(meta_disco.read_text()).get("note") == "nota do QA"
        ev = H.evidencia(page, ctx, "mb-board-criado")
        return H.verifica(bool(t) and page.url.endswith(f"#/moodboards/{mbid}") and no_disco,
                          f"{mbid} criado e editor aberto",
                          f"toast='{t}' url={page.url} moodboard.json ok={no_disco}", ev)
    finally:
        _apagar_board(page, ctx, mbid)


# ---------- editor: cabeçalho e navegação ----------
@caso("C-MOODBOARDS-08", "editor mostra nome, pasta real do board e os três painéis")
def editor_cabecalho(page, ctx):
    _editor(page, ctx)
    data = H.api(page, ctx, "get", f"/api/moodboards/{ctx.mbid}").json()
    pasta = (page.locator("#mbFolder").text_content() or "").strip()
    paineis = page.locator("#main section.panel").count()
    esperado = str(ctx.moodboards_dir / ctx.mbid)
    ev = H.evidencia(page, ctx, "mb-editor")
    return H.verifica(pasta == data["folder"] == esperado and paineis == 3,
                      f"pasta={pasta}, {paineis} painéis",
                      f"pasta UI='{pasta}' api='{data['folder']}' esperado='{esperado}' painéis={paineis}", ev)


@caso("C-MOODBOARDS-09", "'← Biblioteca' volta para a lista")
def voltar(page, ctx):
    _editor(page, ctx)
    page.locator("#mbBack").click()
    page.wait_for_selector("#main .mb-grid, #main .empty-state", timeout=H.TIMEOUT_MS)
    return H.verifica(page.url.endswith("#/moodboards") and page.locator("#btnNewBoard").count() == 1,
                      "voltou para a biblioteca",
                      f"url={page.url} btnNewBoard={page.locator('#btnNewBoard').count()}")


@caso("C-MOODBOARDS-10", "renomear altera nome e vibe (PATCH) e reflete no título")
def renomear(page, ctx):
    _editor(page, ctx)
    original = H.api(page, ctx, "get", f"/api/moodboards/{ctx.mbid}").json()
    try:
        page.locator("#btnMbRename").click()
        m = H.modal(page)
        m.wait_for()
        m.locator("input[name=name]").fill(original["name"] + " ✎")
        m.locator("input[name=vibe]").fill("neon e neve")
        m.locator("button[type=submit]").click()
        t = H.esperar_toast(page, "atualizado")
        page.wait_for_timeout(400)
        titulo = (page.locator("#mbTitle").text_content() or "").strip()
        depois = H.api(page, ctx, "get", f"/api/moodboards/{ctx.mbid}").json()
        ev = H.evidencia(page, ctx, "mb-renomear", full_page=False)
        return H.verifica(titulo.endswith("✎") and depois["vibe"] == "neon e neve" and depois["id"] == original["id"],
                          f"título='{titulo}', vibe salva, id estável",
                          f"toast='{t}' título='{titulo}' vibe='{depois['vibe']}' id={depois['id']}", ev)
    finally:
        H.api(page, ctx, "patch", f"/api/moodboards/{ctx.mbid}",
              data=json.dumps({"name": original["name"], "vibe": original["vibe"]}), headers=JSON)


# ---------- importação ----------
@caso("C-MOODBOARDS-11", "upload de imagem importa a candidata (toast, painel 01 e candidates/ no disco)")
def upload(page, ctx):
    _editor(page, ctx)
    antes = _ids(_cands(page, ctx))
    novos: set[str] = set()
    try:
        H.upload(page, "#mbUpload", _png(ctx, "mb-upload"))
        t = H.esperar_toast(page, "importada")
        page.wait_for_timeout(600)
        depois = _cands(page, ctx)
        novos = _ids(depois) - antes
        cards = page.locator("#mbImported .msc-card").count()
        arqs = H.arquivos(ctx.moodboards_dir / ctx.mbid, "candidates/*")
        no_disco = any(cid in a for cid in novos for a in arqs)
        ev = H.evidencia(page, ctx, "mb-upload")
        return H.verifica(len(novos) == 1 and no_disco and cards == len(depois),
                          f"1 candidata nova ({list(novos)[0][:8]}…), {cards} cards no painel 01",
                          f"toast='{t}' novos={novos} cards={cards} de {len(depois)} candidatas; arquivos={arqs[:4]}", ev)
    finally:
        _apagar_cands(page, ctx, ctx.mbid, novos)


@caso("C-MOODBOARDS-12", "'Importar da pasta Downloads' traz o PNG recente de STUDIO_DOWNLOADS")
def importar_downloads(page, ctx):
    dl = ctx.run_dir / "downloads"
    arquivo = _png(ctx, "qa-downloads-mb", dest=dl)
    _editor(page, ctx)
    antes = _ids(_cands(page, ctx))
    novos: set[str] = set()
    try:
        page.locator("#btnMbDownloads").click()
        t = H.esperar_toast(page, "novas de")
        page.wait_for_timeout(600)
        novos = _ids(_cands(page, ctx)) - antes
        cards = page.locator("#mbImported .msc-card").count()
        ev = H.evidencia(page, ctx, "mb-downloads")
        return H.verifica(len(novos) >= 1 and cards >= len(antes) + 1,
                          f"toast='{t}', {len(novos)} candidata(s) nova(s)",
                          f"toast='{t}' novos={novos} cards={cards} (pasta={dl})", ev)
    finally:
        _apagar_cands(page, ctx, ctx.mbid, novos)
        arquivo.unlink(missing_ok=True)


@caso("C-MOODBOARDS-13", "'Importar do histórico Higgsfield' traz as 3 imagens do CLI")
def importar_historico(page, ctx):
    _editor(page, ctx)
    antes = _ids(_cands(page, ctx))
    novos: set[str] = set()
    try:
        page.locator("#btnMbHistory").click()
        t = H.esperar_toast(page, "jobs")
        page.wait_for_timeout(800)
        novos = _ids(_cands(page, ctx)) - antes
        chamou = "generate list --image" in ctx.fakes_log()
        ev = H.evidencia(page, ctx, "mb-historico")
        return H.verifica(len(novos) == 3 and chamou,
                          f"toast='{t}', 3 candidatas do histórico",
                          f"toast='{t}' novos={len(novos)} ({novos}) fake chamado={chamou}", ev)
    finally:
        _apagar_cands(page, ctx, ctx.mbid, novos)


# ---------- curadoria ----------
@caso("C-MOODBOARDS-14", "'usar no board' move a candidata do painel 01 para o 02 e atualiza as contagens")
def usar_no_board(page, ctx):
    _selecionar(page, ctx, ctx.mbid, [])
    _editor(page, ctx)
    total = len(_cands(page, ctx))
    page.locator("#mbImported .use-btn").first.click()
    page.wait_for_timeout(300)
    imp = page.locator("#mbImported .msc-card").count()
    gal = page.locator("#mbGallery .msc-card").count()
    counts = (page.locator("#mbCounts").text_content() or "").strip()
    aguardando = (page.locator("#mbImpCount").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "mb-usar-no-board")
    ok = gal == 1 and imp == total - 1 and f"{total} candidatas · 1 escolhidas" in counts and aguardando == f"{total - 1} aguardando"
    _selecionar(page, ctx, ctx.mbid, [])
    return H.verifica(ok, f"1 no board, {imp} aguardando · '{counts}'",
                      f"painel01={imp} painel02={gal} counts='{counts}' impCount='{aguardando}' total={total}", ev)


@caso("C-MOODBOARDS-15", "'Salvar seleção' copia para images/, deriva a paleta e pinta os swatches")
def salvar_selecao(page, ctx):
    _selecionar(page, ctx, ctx.mbid, [])
    _editor(page, ctx)
    try:
        page.locator("#mbImported .use-btn").first.click()
        page.wait_for_timeout(200)
        page.locator("#btnMbSave").click()
        t = H.esperar_toast(page, "no board")
        page.wait_for_timeout(700)
        raiz = ctx.moodboards_dir / ctx.mbid
        imgs = H.arquivos(raiz, "images/*")
        paleta = json.loads((raiz / "palette.json").read_text()) if (raiz / "palette.json").exists() else {}
        swatches = page.locator("#mbPalette span[title]").count()
        detalhe = H.api(page, ctx, "get", f"/api/moodboards/{ctx.mbid}").json()
        ev = H.evidencia(page, ctx, "mb-salvar-selecao")
        return H.verifica(len(imgs) == 1 and len(paleta.get("colors", [])) > 0 and swatches > 0
                          and detalhe["count"] == 1,
                          f"toast='{t}', images/={imgs}, {swatches} swatches",
                          f"toast='{t}' images={imgs} palette={paleta.get('colors')} swatches={swatches} count={detalhe['count']}", ev)
    finally:
        _selecionar(page, ctx, ctx.mbid, [])


@caso("C-MOODBOARDS-16", "clicar na imagem do painel 02 tira do board e salvar remove de images/")
def tirar_do_board(page, ctx):
    cands = _cands(page, ctx)
    _selecionar(page, ctx, ctx.mbid, [cands[0]["id"]])
    _editor(page, ctx)
    try:
        antes = page.locator("#mbGallery .msc-card").count()
        page.locator("#mbGallery .msc-card").first.click()
        page.wait_for_timeout(300)
        depois = page.locator("#mbGallery .msc-card").count()
        page.locator("#btnMbSave").click()
        H.esperar_toast(page, "no board")
        page.wait_for_timeout(700)
        imgs = H.arquivos(ctx.moodboards_dir / ctx.mbid, "images/*")
        vazio = page.locator("#mbGallery .empty").count() == 1
        ev = H.evidencia(page, ctx, "mb-tirar-do-board")
        return H.verifica(antes == 1 and depois == 0 and imgs == [] and vazio,
                          "imagem saiu do board e de images/",
                          f"painel02 {antes}→{depois} images={imgs} empty={vazio}", ev)
    finally:
        _selecionar(page, ctx, ctx.mbid, [])


@caso("C-MOODBOARDS-17", "teto de 8 imagens: salvar 9 escolhidas devolve erro amigável (ADR-007)")
def teto_de_oito(page, ctx):
    mbid = _board_temp(page, ctx, "QA Board Teto")
    try:
        _editor(page, ctx, mbid)
        H.upload(page, "#mbUpload", *[_png(ctx, f"mb-teto-{i}") for i in range(9)])
        H.esperar_toast(page, "importada")
        page.wait_for_timeout(1200)
        page.wait_for_selector("#mbImported .use-btn", timeout=H.TIMEOUT_MS)
        botoes = page.locator("#mbImported .use-btn")
        for _ in range(botoes.count()):
            page.locator("#mbImported .use-btn").first.click()
            page.wait_for_timeout(80)
        escolhidas = page.locator("#mbGallery .msc-card").count()
        page.locator("#btnMbSave").click()
        t = H.esperar_toast(page, "vibe só")
        page.wait_for_timeout(500)
        imgs = H.arquivos(ctx.moodboards_dir / mbid, "images/*")
        ev = H.evidencia(page, ctx, "mb-teto-8")
        return H.verifica(escolhidas == 9 and bool(t) and imgs == [],
                          f"9 escolhidas → toast='{t}', nada copiado para images/",
                          f"escolhidas={escolhidas} toast='{t}' images={imgs}", ev)
    finally:
        _apagar_board(page, ctx, mbid)


# ---------- multishot [extensão] ----------
@caso("C-MOODBOARDS-18", "'▨ ângulos' abre o modal de multishot com a imagem de origem")
def multishot_abre(page, ctx):
    _editor(page, ctx)
    page.locator("#mbImported .ms-btn").first.click()
    m = H.modal(page)
    m.wait_for()
    src = m.locator(".ms-source img")
    count = m.locator("#msCount")
    ev = H.evidencia(page, ctx, "mb-multishot-modal", full_page=False)
    ok = src.count() == 1 and "/mbfiles/" in (src.get_attribute("src") or "") and count.input_value() == "4" \
        and m.locator("#msGen").count() == 1
    H.fechar_modal(page)
    return H.verifica(ok, "modal com origem, contador (4) e botão de gerar",
                      f"src='{src.get_attribute('src') if src.count() else None}' "
                      f"count={count.input_value() if count.count() else None} gen={m.locator('#msGen').count()}", ev)


@caso("C-MOODBOARDS-19", "multishot: 'Gerar' abre o modal de custo e cancelar não gera nada")
def multishot_custo_cancela(page, ctx):
    _editor(page, ctx)
    antes = len(_cands(page, ctx))
    page.locator("#mbImported .ms-btn").first.click()
    H.modal(page).wait_for()
    page.locator("#msGen").click()
    page.wait_for_selector(".modal[role=dialog] .cost-sheet", timeout=H.TIMEOUT_MS)   # o modal de custo empilha
    custo = H.modal(page)
    texto = custo.text_content() or ""
    api_custo = H.api(page, ctx, "get", "/api/creditos/cost?action=mood.multishot").json()
    ev = H.evidencia(page, ctx, "mb-multishot-custo", full_page=False)
    custo.locator(".modal-actions [data-act='0']").click()   # Cancelar
    page.wait_for_timeout(400)
    depois = len(_cands(page, ctx))
    H.fechar_modal(page)
    ok = "Total estimado" in texto and "Saldo atual" in texto and str(api_custo["credits"]) in texto and depois == antes
    return H.verifica(ok, f"custo unitário {api_custo['credits']} cr, cancelou sem gerar",
                      f"modal='{texto[:200]}' custo_api={api_custo['credits']} candidatas {antes}→{depois}", ev)


@caso("C-MOODBOARDS-20", "multishot: confirmar gera o ângulo (fake), mostra o carrossel e 'remover' apaga")
def multishot_gera(page, ctx):
    _editor(page, ctx)
    antes = _ids(_cands(page, ctx))
    novos: set[str] = set()
    try:
        page.locator("#mbImported .ms-btn").first.click()
        H.modal(page).wait_for()
        page.locator("#msCount").fill("1")
        _espiar_progresso(page)
        page.locator("#msGen").click()
        page.wait_for_selector(".modal[role=dialog] .cost-sheet", timeout=H.TIMEOUT_MS)
        H.modal(page).locator(".modal-actions [data-act='1']").click()   # confirmar o custo
        page.wait_for_function("() => !document.querySelector('.progress-modal')", timeout=90_000)
        page.wait_for_timeout(600)
        prog = _progresso_visto(page)
        cands = _cands(page, ctx)
        novos = _ids(cands) - antes
        ms = [c for c in cands if c.get("role") == "multishot" and c["id"] in novos]
        contador = (page.locator(".msc-count").text_content() or "").strip()
        ev = H.evidencia(page, ctx, "mb-multishot-gerado", full_page=False)
        if not (prog and len(ms) == 1 and "1/1" in contador):
            return H.Resultado.falha(f"progresso visto={prog} novas={novos} multishot={len(ms)} carrossel='{contador}'", ev)
        page.locator(".msc-remove").click()
        t = H.esperar_toast(page, "removido")
        page.wait_for_timeout(600)
        restou = _ids(_cands(page, ctx)) & novos
        novos = restou
        return H.verifica(not restou, f"1 ângulo gerado, carrossel '{contador}' e removido (toast='{t}')",
                          f"remoção falhou: ainda existem {restou} (toast='{t}')", ev)
    finally:
        _apagar_cands(page, ctx, ctx.mbid, novos)
        H.fechar_modal(page)


@caso("C-MOODBOARDS-21", "multishot: 'Importar fotos' abre o modal de importação com a pasta Downloads")
def multishot_importar(page, ctx):
    _editor(page, ctx)
    page.locator("#mbImported .ms-btn").first.click()
    H.modal(page).wait_for()
    page.locator("#msImport").click()
    imp = H.modal(page)
    imp.wait_for()
    page.wait_for_timeout(600)
    pasta = (imp.locator("#msImpPath").text_content() or "").strip()
    api_pasta = H.api(page, ctx, "get", f"/api/moodboards/{ctx.mbid}/downloads-folder").json()
    ev = H.evidencia(page, ctx, "mb-multishot-importar", full_page=False)
    ok = imp.locator("#msImpDrop").count() == 1 and imp.locator("#msImpDl").count() == 1 \
        and api_pasta["folder"] in pasta
    H.fechar_modal(page)
    H.fechar_modal(page)
    return H.verifica(ok, f"modal de importação com '{pasta}'",
                      f"drop={imp.locator('#msImpDrop').count()} dl={imp.locator('#msImpDl').count()} "
                      f"pasta='{pasta}' api='{api_pasta['folder']}'", ev)


# ---------- prompt de vibe ----------
@caso("C-MOODBOARDS-22", "painel 03 reflete o bot disponível e habilita os três modos")
def prompt_modos(page, ctx):
    _editor(page, ctx)
    data = H.api(page, ctx, "get", f"/api/moodboards/{ctx.mbid}").json()
    chip = (page.locator("#mbClaude").text_content() or "").strip()
    opts = page.locator("#mbMode option").evaluate_all("els => els.map(e => [e.value, e.disabled])")
    esperado = [["images", not data["available_claude"]], ["brief", not data["available_claude"]], ["template", False]]
    return H.verifica(opts == esperado and ("claude ok" in chip) == bool(data["available_claude"]),
                      f"chip='{chip}', modos={opts}",
                      f"chip='{chip}' opts={opts} esperado={esperado} available_claude={data['available_claude']}")


@caso("C-MOODBOARDS-23", "modo template gera o prompt sem modal e grava prompt.txt")
def prompt_template(page, ctx):
    _editor(page, ctx)
    page.locator("#mbMode").select_option("template")
    page.locator("#mbInstruction").fill("mais neon e neve")
    _espiar_progresso(page)
    page.locator("#btnMbGenPrompt").click()
    t = H.esperar_toast(page, "template")
    page.wait_for_selector("#mbPromptList textarea", timeout=H.TIMEOUT_MS)
    texto = page.locator("#mbPromptList textarea").input_value()
    prog = _progresso_visto(page)
    disco = (ctx.moodboards_dir / ctx.mbid / "prompt.txt")
    ev = H.evidencia(page, ctx, "mb-prompt-template")
    return H.verifica(bool(texto.strip()) and prog == 0 and disco.exists() and disco.read_text().strip() == texto.strip(),
                      f"toast='{t}', prompt de {len(texto)} chars gravado sem modal",
                      f"toast='{t}' progresso={prog} texto='{texto[:80]}' prompt.txt existe={disco.exists()}", ev)


@caso("C-MOODBOARDS-24", "modo imagens abre o modal de progresso e grava o prompt do bot em prompts.json")
def prompt_imagens(page, ctx):
    _editor(page, ctx)
    try:
        page.locator("#mbImported .use-btn").first.click()
        page.wait_for_timeout(200)
        page.locator("#mbMode").select_option("images")
        page.locator("#mbInstruction").fill("mais neon")
        _espiar_progresso(page)
        page.locator("#btnMbGenPrompt").click()
        page.wait_for_function("() => !document.querySelector('.progress-modal')", timeout=90_000)
        page.wait_for_timeout(400)
        prog = _progresso_visto(page)
        texto = page.locator("#mbPromptList textarea").input_value()
        hist = json.loads((ctx.moodboards_dir / ctx.mbid / "prompts.json").read_text())
        ultimo = hist[0] if hist else {}
        ev = H.evidencia(page, ctx, "mb-prompt-imagens")
        return H.verifica(prog >= 1 and "[QA-FAKE" in texto and ultimo.get("mode") == "images"
                          and ultimo.get("instruction") == "mais neon",
                          f"modal de progresso visto, prompt do bot ({len(texto)} chars) e entrada em prompts.json",
                          f"progresso={prog} texto='{texto[:80]}' última entrada={ {k: ultimo.get(k) for k in ('mode', 'instruction', 'source')} }", ev)
    finally:
        _selecionar(page, ctx, ctx.mbid, [])


@caso("C-MOODBOARDS-25", "modo imagens sem imagem escolhida avisa e não chama a API")
def prompt_sem_imagem(page, ctx):
    _selecionar(page, ctx, ctx.mbid, [])
    _editor(page, ctx)
    antes = len(json.loads((ctx.moodboards_dir / ctx.mbid / "prompts.json").read_text())
                if (ctx.moodboards_dir / ctx.mbid / "prompts.json").exists() else [])
    page.locator("#mbMode").select_option("images")
    _espiar_progresso(page)
    page.locator("#btnMbGenPrompt").click()
    t = H.esperar_toast(page, "ao menos uma imagem")
    page.wait_for_timeout(500)
    prog = _progresso_visto(page)
    depois = len(json.loads((ctx.moodboards_dir / ctx.mbid / "prompts.json").read_text())
                 if (ctx.moodboards_dir / ctx.mbid / "prompts.json").exists() else [])
    ev = H.evidencia(page, ctx, "mb-prompt-sem-imagem", full_page=False)
    return H.verifica(bool(t) and prog == 0 and depois == antes,
                      f"toast='{t}', sem modal e sem geração",
                      f"toast='{t}' progresso={prog} prompts.json {antes}→{depois}", ev)


@caso("C-MOODBOARDS-26", "desmarcar 'sem pessoas' é registrado no histórico do prompt")
def prompt_sem_pessoas(page, ctx):
    _editor(page, ctx)
    page.locator("#mbMode").select_option("template")
    page.locator("label:has(#mbNoPeople)").click()   # o checkbox nasce marcado
    marcado = page.locator("#mbNoPeople").is_checked()
    page.locator("#btnMbGenPrompt").click()
    H.esperar_toast(page, "template")
    page.wait_for_timeout(500)
    hist = json.loads((ctx.moodboards_dir / ctx.mbid / "prompts.json").read_text())
    ev = H.evidencia(page, ctx, "mb-prompt-no-people", full_page=False)
    return H.verifica(marcado is False and hist and hist[0].get("no_people") is False,
                      "no_people=false gravado em prompts.json",
                      f"checkbox marcado={marcado} última entrada no_people={hist[0].get('no_people') if hist else None}", ev)


# ---------- erros, exclusão e persistência ----------
@caso("C-MOODBOARDS-27", "board inexistente mostra mensagem amigável com volta para a biblioteca")
def board_inexistente(page, ctx):
    H.ir(page, ctx, "#/moodboards/nao-existe-qa", espera_ms=400)
    page.wait_for_timeout(400)
    texto = (page.locator("#main").inner_text() or "").strip()
    ev = H.evidencia(page, ctx, "mb-inexistente")
    tem_link = page.locator("#mbBack").count() == 1
    if tem_link:
        page.locator("#mbBack").click()
        page.wait_for_timeout(600)
    return H.verifica("não encontrado" in texto.lower() and tem_link and page.url.endswith("#/moodboards"),
                      "mensagem 'não encontrado' + volta à biblioteca",
                      f"texto='{texto[:150]}' link={tem_link} url={page.url}", ev)


@caso("C-MOODBOARDS-28", "apagar board: o modal avisa o efeito e cancelar não apaga")
def apagar_cancela(page, ctx):
    mbid = _board_temp(page, ctx, "QA Board Cancela")
    try:
        _editor(page, ctx, mbid)
        page.locator("#btnMbDelete").click()
        m = H.modal(page)
        m.wait_for()
        texto = m.text_content() or ""
        ev = H.evidencia(page, ctx, "mb-apagar-modal", full_page=False)
        m.locator(".modal-actions [data-act='0']").click()   # Cancelar
        page.wait_for_timeout(400)
        existe = H.api(page, ctx, "get", f"/api/moodboards/{mbid}").ok
        return H.verifica(existe and "apaga" in texto.lower() and (ctx.moodboards_dir / mbid).exists()
                          and page.url.endswith(f"#/moodboards/{mbid}"),
                          "modal explica o efeito e cancelar preserva o board",
                          f"modal='{texto[:160]}' board existe={existe} url={page.url}", ev)
    finally:
        _apagar_board(page, ctx, mbid)


@caso("C-MOODBOARDS-29", "apagar board: confirmar apaga a pasta e volta para a biblioteca")
def apagar_confirma(page, ctx):
    mbid = _board_temp(page, ctx, "QA Board Apaga")
    try:
        _editor(page, ctx, mbid)
        page.locator("#btnMbDelete").click()
        m = H.modal(page)
        m.wait_for()
        m.locator(".modal-actions [data-act='1']").click()   # Apagar
        t = H.esperar_toast(page, "apagado")
        page.wait_for_timeout(800)
        r = H.api(page, ctx, "get", f"/api/moodboards/{mbid}")
        na_lista = [b["id"] for b in H.api(page, ctx, "get", "/api/moodboards").json()]
        ev = H.evidencia(page, ctx, "mb-apagado")
        return H.verifica(r.status == 404 and not (ctx.moodboards_dir / mbid).exists()
                          and mbid not in na_lista and page.url.endswith("#/moodboards"),
                          f"toast='{t}', pasta removida e volta à lista",
                          f"toast='{t}' GET={r.status} pasta={ (ctx.moodboards_dir / mbid).exists() } "
                          f"na_lista={mbid in na_lista} url={page.url}", ev)
    finally:
        _apagar_board(page, ctx, mbid)


@caso("C-MOODBOARDS-30", "'Abrir pasta' do board não é testável offline (abre o explorador do SO)")
def abrir_pasta(page, ctx):
    _editor(page, ctx)
    presente = page.locator("#btnMbOpenFolder").count() == 1
    if not presente:
        return H.Resultado.falha("botão #btnMbOpenFolder ausente no editor")
    return H.Resultado.bloqueado(
        "clicar #btnMbOpenFolder abre o explorador do SO (proibido na rodada headless); "
        "o endpoint POST /open-folder é best-effort e não tem efeito verificável na UI")


@caso("C-MOODBOARDS-31", "seleção e prompt sobrevivem ao reload do editor")
def persistencia(page, ctx):
    cands = _cands(page, ctx)
    _selecionar(page, ctx, ctx.mbid, [cands[0]["id"]])
    H.api(page, ctx, "post", f"/api/moodboards/{ctx.mbid}/prompt/generate",
          data=json.dumps({"mode": "template", "instruction": "qa persistência"}), headers=JSON)
    try:
        _editor(page, ctx)
        page.reload()
        H.esperar_tela(page)
        page.wait_for_selector("#mbGallery", timeout=H.TIMEOUT_MS)
        gal = page.locator("#mbGallery .msc-card").count()
        counts = (page.locator("#mbCounts").text_content() or "").strip()
        prompt = page.locator("#mbPromptList textarea")
        texto = prompt.input_value() if prompt.count() else ""
        swatches = page.locator("#mbPalette span[title]").count()
        ev = H.evidencia(page, ctx, "mb-persistencia")
        return H.verifica(gal == 1 and "1 escolhidas" in counts and bool(texto.strip()) and swatches > 0,
                          f"após reload: {gal} no board, '{counts}', prompt de {len(texto)} chars",
                          f"painel02={gal} counts='{counts}' prompt='{texto[:60]}' swatches={swatches}", ev)
    finally:
        _selecionar(page, ctx, ctx.mbid, [])
