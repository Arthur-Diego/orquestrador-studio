"""Casos da etapa 2 — Mood board (`studio/etapas/mood/view.html|view.js|router.py`).

Fluxo `etapa2-pick` (ADR-014): a etapa NÃO cria nem cura mood — ela só **escolhe** um board da
biblioteca global e o **aplica** à campanha (`POST /mood/pull/<mbid>`), e mostra o mood atual
(`GET /api/projects/<pid>/mood`). Os casos cobrem os dois painéis, o teclado, a idempotência do
"aplicar", a biblioteca vazia e os dois atalhos para a biblioteca.
"""
from __future__ import annotations

import json
import shutil

from scripts.qa import harness as H

TELA = "mood"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)

JSON_H = {"content-type": "application/json"}
BOARD_NOME = "QA Mood Aplicar"
BOARD_VIBE = "qa vibe gelo neon"


# ---------- helpers locais ----------
def _post(page, ctx, path: str, corpo: dict | None = None):
    kw = {"data": json.dumps(corpo), "headers": JSON_H} if corpo is not None else {}
    return H.api(page, ctx, "post", path, **kw)


def _descartavel(page, ctx, nome: str) -> str:
    """Campanha descartável (o `pid_cheio` nunca é usado para aplicar board — isso trocaria o
    mood do seed do qual as outras etapas dependem)."""
    for p in H.api(page, ctx, "get", "/api/projects").json():
        if p["name"] == nome:
            return p["id"]
    r = _post(page, ctx, "/api/projects", {"name": nome, "product": "produto de teste", "vibe": ""})
    if r.status >= 400:
        raise RuntimeError(f"POST /api/projects → {r.status}: {r.text()[:200]}")
    pid = r.json()["id"]
    page.reload()
    H.esperar_tela(page)
    return pid


def _board_curado(page, ctx) -> dict:
    """Board da biblioteca COM curadoria (2 imagens em `images/`) — o seed (`ctx.mbid`) tem só
    candidatas importadas, e um board sem curadoria não é aplicável."""
    for b in H.api(page, ctx, "get", "/api/moodboards").json():
        if b["name"] == BOARD_NOME and b["count"] >= 2:
            return b
    r = _post(page, ctx, "/api/moodboards", {"name": BOARD_NOME, "note": "board curado do qa-studio"})
    mbid = r.json()["id"] if r.status < 400 else BOARD_NOME.lower().replace(" ", "-")
    for nome, cor in (("mood-a", (30, 180, 200)), ("mood-b", (200, 60, 120))):
        p = H.png_temp(ctx, nome, color=cor)
        H.api(page, ctx, "post", f"/api/moodboards/{mbid}/import/upload",
              multipart={"files": {"name": p.name, "mimeType": "image/png", "buffer": p.read_bytes()}})
    ids = [c["id"] for c in H.api(page, ctx, "get", f"/api/moodboards/{mbid}/candidates").json()]
    _post(page, ctx, f"/api/moodboards/{mbid}/select", {"ids": ids, "note": ""})
    H.api(page, ctx, "patch", f"/api/moodboards/{mbid}", data=json.dumps({"vibe": BOARD_VIBE}),
          headers=JSON_H)
    return next(b for b in H.api(page, ctx, "get", "/api/moodboards").json() if b["id"] == mbid)


def _zerar_mood(ctx, pid: str) -> None:
    root = ctx.projeto(pid)
    shutil.rmtree(root / "mood", ignore_errors=True)
    for sub in ("mood", "mood/vibe"):
        (root / sub).mkdir(parents=True, exist_ok=True)


def _abrir(page, ctx, pid: str | None = None) -> None:
    """Abre a etapa GARANTINDO remontagem: a SPA só remonta quando o hash muda, e vários casos
    precisam ver dados criados depois do último render (board novo, mood recém-aplicado)."""
    H.abrir_tela(page, ctx, "overview", pid)
    H.abrir_tela(page, ctx, TELA, pid)


def _card(page, mbid: str):
    return page.locator(f"#mbGrid .card[data-mb='{mbid}']")


# ---------- painel 01: escolher um mood board ----------
@caso("C-MOOD-01", "a grade lista um card por board de /api/moodboards, com 'nome · N img'")
def lista_boards(page, ctx):
    _board_curado(page, ctx)
    _abrir(page, ctx)
    boards = H.api(page, ctx, "get", "/api/moodboards").json()
    ids = page.locator("#mbGrid .card").evaluate_all("els => els.map(e => e.dataset.mb)")
    legendas = [t.strip() for t in page.locator("#mbGrid .card .term").all_text_contents()]
    esperado = [f"{b['name']} · {b['count']} img" + (f" · {b['vibe']}" if b.get("vibe") else "")
                for b in boards]
    ev = H.evidencia(page, ctx, "mood-lista-boards")
    return H.verifica(ids == [b["id"] for b in boards] and legendas == esperado,
                      f"{len(ids)} boards listados",
                      f"ids={ids} vs api={[b['id'] for b in boards]}; legendas={legendas} vs {esperado}", ev)


@caso("C-MOOD-02", "board sem imagens curadas nasce inativo e não pode ser escolhido")
def board_vazio(page, ctx):
    _board_curado(page, ctx)
    _abrir(page, ctx)
    card = _card(page, ctx.mbid)
    if not card.count():
        return H.Resultado.falha(f"board do seed ({ctx.mbid}) não aparece na grade")
    classe = card.get_attribute("class") or ""
    tab = card.get_attribute("tabindex")
    card.click(force=True)
    page.wait_for_timeout(200)
    chip = (page.locator("#mbCount").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "mood-board-vazio", full_page=False)
    return H.verifica("is-empty" in classe and tab is None and chip == "nenhum selecionado"
                      and page.locator("#btnApplyBoard").is_disabled(),
                      "board sem curadoria fica inativo",
                      f"classe='{classe}' tabindex={tab} chip='{chip}' "
                      f"botão desabilitado={page.locator('#btnApplyBoard').is_disabled()}", ev)


@caso("C-MOOD-03", "clicar num board curado marca a escolha e habilita 'Aplicar a esta campanha'")
def escolher_board(page, ctx):
    b = _board_curado(page, ctx)
    _abrir(page, ctx)
    _card(page, b["id"]).click()
    page.wait_for_timeout(250)
    classe = _card(page, b["id"]).get_attribute("class") or ""
    chip = (page.locator("#mbCount").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "mood-escolher-board", full_page=False)
    return H.verifica("sel" in classe and chip == f"{b['name']} selecionado"
                      and page.locator("#btnApplyBoard").is_enabled(),
                      f"chip='{chip}' e botão habilitado",
                      f"classe='{classe}' chip='{chip}' "
                      f"botão habilitado={page.locator('#btnApplyBoard').is_enabled()}", ev)


@caso("C-MOOD-04", "clicar no board já escolhido desfaz a escolha e desabilita o botão")
def desescolher_board(page, ctx):
    b = _board_curado(page, ctx)
    _abrir(page, ctx)
    _card(page, b["id"]).click()
    page.wait_for_timeout(200)
    _card(page, b["id"]).click()
    page.wait_for_timeout(200)
    classe = _card(page, b["id"]).get_attribute("class") or ""
    chip = (page.locator("#mbCount").text_content() or "").strip()
    return H.verifica("sel" not in classe.split() and chip == "nenhum selecionado"
                      and page.locator("#btnApplyBoard").is_disabled(),
                      "escolha desfeita",
                      f"classe='{classe}' chip='{chip}' "
                      f"botão desabilitado={page.locator('#btnApplyBoard').is_disabled()}")


@caso("C-MOOD-05", "Enter num board focado escolhe (acessibilidade por teclado)")
def escolher_teclado(page, ctx):
    b = _board_curado(page, ctx)
    _abrir(page, ctx)
    card = _card(page, b["id"])
    card.focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(250)
    chip = (page.locator("#mbCount").text_content() or "").strip()
    return H.verifica(chip == f"{b['name']} selecionado", "Enter escolheu o board",
                      f"chip='{chip}' (tabindex={card.get_attribute('tabindex')})")


@caso("C-MOOD-06", "'Aplicar a esta campanha' copia as imagens do board para mood/selected")
def aplicar(page, ctx):
    b = _board_curado(page, ctx)
    pid = _descartavel(page, ctx, "QA Mood Alvo")
    _zerar_mood(ctx, pid)
    _abrir(page, ctx, pid)
    _card(page, b["id"]).click()
    page.locator("#btnApplyBoard").click()
    t = H.esperar_toast(page, "aplicadas")
    page.wait_for_timeout(700)
    disco = H.arquivos(ctx.projeto(pid), "mood/selected/*")
    api = H.api(page, ctx, "get", f"/api/projects/{pid}/mood").json()
    ev = H.evidencia(page, ctx, "mood-aplicar")
    return H.verifica(len(disco) == b["count"] and api["count"] == b["count"] and bool(t),
                      f"{len(disco)} imagens aplicadas (toast='{t}')",
                      f"disco={disco} api.count={api['count']} board.count={b['count']} toast='{t}'", ev)


@caso("C-MOOD-07", "aplicar grava mood.md, palette.json e a vibe do board na campanha")
def aplicar_artefatos(page, ctx):
    b = _board_curado(page, ctx)
    pid = _descartavel(page, ctx, "QA Mood Alvo")
    _zerar_mood(ctx, pid)
    _abrir(page, ctx, pid)
    _card(page, b["id"]).click()
    page.locator("#btnApplyBoard").click()
    H.esperar_toast(page, "aplicadas")
    page.wait_for_timeout(700)
    root = ctx.projeto(pid)
    md = (root / "mood" / "mood.md").read_text() if (root / "mood" / "mood.md").exists() else ""
    pal = json.loads((root / "mood" / "palette.json").read_text()) if (root / "mood" / "palette.json").exists() else {}
    vibe = json.loads((root / "project.json").read_text()).get("vibe", "")
    return H.verifica(bool(md) and b["name"] in md and bool(pal.get("colors")) and vibe == BOARD_VIBE,
                      f"mood.md + palette ({len(pal.get('colors', []))} cores) + vibe='{vibe}'",
                      f"mood.md={'ok' if md else 'ausente'} cores={pal.get('colors')} vibe='{vibe}' "
                      f"esperado='{BOARD_VIBE}'")


@caso("C-MOOD-08", "depois de aplicar, a escolha é limpa e o painel 02 mostra o mood novo")
def aplicar_reseta_escolha(page, ctx):
    b = _board_curado(page, ctx)
    pid = _descartavel(page, ctx, "QA Mood Alvo")
    _zerar_mood(ctx, pid)
    _abrir(page, ctx, pid)
    _card(page, b["id"]).click()
    page.locator("#btnApplyBoard").click()
    H.esperar_toast(page, "aplicadas")
    page.wait_for_timeout(700)
    chip = (page.locator("#mbCount").text_content() or "").strip()
    marcados = page.locator("#mbGrid .card.sel").count()
    celulas = page.locator("#moodGallery .mood-mosaic .mm-cell").count()
    vibe = (page.locator("#moodVibe").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "mood-apos-aplicar")
    return H.verifica(chip == "nenhum selecionado" and marcados == 0
                      and celulas == b["count"] and vibe == f"vibe: {BOARD_VIBE}",
                      f"escolha limpa e mosaico com {celulas} imagens",
                      f"chip='{chip}' marcados={marcados} células={celulas} (board={b['count']}) "
                      f"vibe='{vibe}'", ev)


@caso("C-MOOD-09", "reaplicar o mesmo board é idempotente (mood/selected não acumula)")
def aplicar_idempotente(page, ctx):
    b = _board_curado(page, ctx)
    pid = _descartavel(page, ctx, "QA Mood Alvo")
    _abrir(page, ctx, pid)
    for _ in range(2):
        _card(page, b["id"]).click()
        page.locator("#btnApplyBoard").click()
        H.esperar_toast(page, "aplicadas")
        page.wait_for_timeout(700)
    disco = H.arquivos(ctx.projeto(pid), "mood/selected/*")
    api = H.api(page, ctx, "get", f"/api/projects/{pid}/mood").json()
    return H.verifica(len(disco) == b["count"] and api["count"] == b["count"],
                      f"{len(disco)} imagens após aplicar 2×",
                      f"disco={disco} api.count={api['count']} esperado={b['count']}")


@caso("C-MOOD-10", "aplicar não altera o board na biblioteca (a cópia é da campanha)")
def board_intacto(page, ctx):
    b = _board_curado(page, ctx)
    antes = H.api(page, ctx, "get", f"/api/moodboards/{b['id']}").json()
    pid = _descartavel(page, ctx, "QA Mood Alvo")
    _abrir(page, ctx, pid)
    _card(page, b["id"]).click()
    page.locator("#btnApplyBoard").click()
    H.esperar_toast(page, "aplicadas")
    page.wait_for_timeout(700)
    depois = H.api(page, ctx, "get", f"/api/moodboards/{b['id']}").json()
    return H.verifica(antes["images"] == depois["images"] and antes["count"] == depois["count"],
                      f"board segue com {depois['count']} imagens",
                      f"antes={antes['images']} depois={depois['images']}")


# ---------- painel 02: mood atual da campanha ----------
@caso("C-MOOD-11", "mosaico do mood atual tem uma célula por imagem de GET /mood")
def mosaico(page, ctx):
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/mood").json()
    celulas = page.locator("#moodGallery .mood-mosaic .mm-cell").count()
    quebradas = page.locator("#moodGallery img").evaluate_all(
        "els => els.filter(i => i.complete && i.naturalWidth === 0).length")
    ev = H.evidencia(page, ctx, "mood-atual")
    return H.verifica(celulas == min(api["count"], 4) and quebradas == 0,
                      f"{celulas} células para {api['count']} imagens",
                      f"células={celulas} api.count={api['count']} imagens quebradas={quebradas}", ev)


@caso("C-MOOD-12", "chip de vibe do painel 02 reflete a vibe da campanha")
def chip_vibe(page, ctx):
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/mood").json()
    txt = (page.locator("#moodVibe").text_content() or "").strip()
    esperado = f"vibe: {api['vibe']}" if api["vibe"] else "vibe: —"
    return H.verifica(txt == esperado, txt, f"chip='{txt}' esperado='{esperado}'")


@caso("C-MOOD-13", "paleta desenha um swatch por cor de palette.json e mantém o rótulo")
def paleta(page, ctx):
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/mood").json()
    cores = page.locator("#palette span[title]").evaluate_all("els => els.map(e => e.title)")
    lbl = (page.locator("#palette .lbl").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "mood-paleta", full_page=False)
    return H.verifica(cores == api["palette"] and "palette.json" in lbl,
                      f"{len(cores)} swatches + rótulo",
                      f"swatches={cores} api={api['palette']} rótulo='{lbl}'", ev)


@caso("C-MOOD-14", "campanha sem mood mostra o vazio apontando para o painel 01", pid="vazio")
def sem_mood(page, ctx):
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_vazio}/mood").json()
    txt = (page.locator("#moodGallery .empty").text_content() or "").strip()
    vibe = (page.locator("#moodVibe").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "mood-vazio")
    return H.verifica(api["count"] == 0 and "Nenhum mood aplicado ainda" in txt and vibe == "vibe: —",
                      "empty-state do mood atual",
                      f"api.count={api['count']} texto='{txt[:80]}' vibe='{vibe}'", ev)


@caso("C-MOOD-15", "'Trocar' devolve o usuário ao painel de escolha")
def trocar(page, ctx):
    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(300)
    antes = page.evaluate("() => document.querySelector('#panelPick').getBoundingClientRect().top")
    page.locator("#btnSwap").click()
    page.wait_for_timeout(900)
    depois = page.evaluate("() => document.querySelector('#panelPick').getBoundingClientRect().top")
    visivel = page.evaluate("() => { const r = document.querySelector('#panelPick').getBoundingClientRect();"
                            " return r.top < innerHeight && r.bottom > 0; }")
    return H.verifica(visivel and depois >= antes, "painel 01 trazido para a viewport",
                      f"top antes={round(antes)} depois={round(depois)} visível={visivel}")


@caso("C-MOOD-16", "'Criar / gerenciar mood boards' abre a biblioteca global")
def gerenciar(page, ctx):
    page.locator("#btnManageBoards").click()
    H.esperar_tela(page)
    titulo = (page.locator("#main h2").first.text_content() or "").strip()
    ev = H.evidencia(page, ctx, "mood-biblioteca")
    return H.verifica(page.url.endswith("#/moodboards"), f"abriu a biblioteca ('{titulo}')",
                      f"url={page.url} título='{titulo}'", ev)


@caso("C-MOOD-17", "biblioteca vazia: empty-state com 'Ir para a biblioteca' que navega")
def biblioteca_vazia(page, ctx):
    assert ctx.moodboards_dir is not None
    bak = ctx.run_dir / "_mb_bak"
    bak.mkdir(exist_ok=True)
    movidos = []
    try:
        for d in sorted(ctx.moodboards_dir.iterdir()):
            if d.is_dir():
                shutil.move(str(d), str(bak / d.name))
                movidos.append(d.name)
        page.reload()
        H.esperar_tela(page)
        vazio = page.locator("#mbGrid .empty")
        txt = (vazio.text_content() or "").strip()
        ev = H.evidencia(page, ctx, "mood-biblioteca-vazia")
        tem_botao = vazio.locator("#btnGoLibEmpty").count() == 1
        if tem_botao:
            vazio.locator("#btnGoLibEmpty").click()
            H.esperar_tela(page)
        foi = page.url.endswith("#/moodboards")
        return H.verifica("Nenhum mood board ainda" in txt and tem_botao and foi,
                          f"empty-state levou à biblioteca (boards movidos: {len(movidos)})",
                          f"texto='{txt[:90]}' botão={tem_botao} url={page.url}", ev)
    finally:
        for nome in movidos:
            destino = ctx.moodboards_dir / nome
            if not destino.exists():
                shutil.move(str(bak / nome), str(destino))
        shutil.rmtree(bak, ignore_errors=True)


@caso("C-MOOD-18", "ADR-014: a etapa não oferece importar, curar nem gerar prompt de mood")
def sem_criacao(page, ctx):
    inputs = page.locator("#main input[type=file]").count()
    paineis = [t.strip() for t in page.locator("#main .panel .panel-head h3").all_text_contents()]
    proibidos = page.locator("#main #btnMbOpenFolder, #main #btnMoodGen, #main #btnMoodPrompt, "
                             "#main #btnMoodUpload, #main #btnMoodSelect").count()
    ev = H.evidencia(page, ctx, "mood-sem-criacao")
    return H.verifica(inputs == 0 and proibidos == 0 and len(paineis) == 2,
                      f"2 painéis, sem upload nem geração: {paineis}",
                      f"inputs de arquivo={inputs} controles de criação={proibidos} painéis={paineis}", ev)
