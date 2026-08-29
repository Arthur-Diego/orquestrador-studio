"""Casos da etapa 7 (edit) — editor de vídeo completo.

Tela: `studio/etapas/edit/view.js` + `view.html` (ADR-030, FDD
`docs/domains/edit/features/editor-video-completo-fdd.md`). Backend: `studio/etapas/edit/router.py`,
`studio/edit/{service,editor,render}.py`.

Convenções deste módulo:
- todo caso que muda a timeline guarda a original (`_tl_api`) e a devolve com `_restaurar` no fim
  (PUT + reload) — o `pid_cheio` é compartilhado com as outras telas e não pode ser destruído;
- o efeito é verificado no DOM **e** no disco (`edit/timeline.json`, gravado pelo autosave via PUT).
"""
from __future__ import annotations

import json
import time

from scripts.qa import harness as H

TELA = "edit"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)

JSON = {"content-type": "application/json"}


# ---------------------------------------------------------------- helpers do módulo
def _pid(ctx, pid=None) -> str:
    return pid or ctx.pid_cheio


def _tl_api(page, ctx, pid=None) -> dict:
    """Timeline como a UI a lê (GET /edit/timeline)."""
    return H.api(page, ctx, "get", f"/api/projects/{_pid(ctx, pid)}/edit/timeline").json()["timeline"]


def _tl_disco(ctx, pid=None) -> dict:
    p = ctx.projeto(_pid(ctx, pid)) / "edit" / "timeline.json"
    return json.loads(p.read_text() or "{}") if p.exists() else {}


def _editor(tl: dict) -> dict:
    return tl.get("editor") or {}


def _track(tl: dict, tid: str) -> dict:
    for t in _editor(tl).get("tracks") or []:
        if t.get("id") == tid:
            return t
    return {}


def _esperar_disco(page, ctx, cond, pid=None, timeout_ms: int = 9000) -> tuple[bool, dict]:
    """Espera o autosave (debounce 900 ms + PUT) gravar algo que satisfaça `cond`."""
    fim = time.time() + timeout_ms / 1000
    tl: dict = {}
    while time.time() < fim:
        tl = _tl_disco(ctx, pid)
        try:
            if cond(tl):
                return True, tl
        except Exception:  # noqa: BLE001 - condição sobre timeline parcial
            pass
        page.wait_for_timeout(200)
    return False, tl


def _esperar_salvo(page, timeout_ms: int = 8000) -> None:
    try:
        page.wait_for_function(
            "() => { const e = document.getElementById('edSave');"
            " return !e || ['saved', 'error'].includes(e.dataset.s) }", timeout=timeout_ms)
    except Exception:  # noqa: BLE001
        pass


def _restaurar(page, ctx, tl: dict, pid=None) -> None:
    """Devolve a timeline original ao disco e recarrega a tela (isola o próximo caso)."""
    _esperar_salvo(page)
    H.api(page, ctx, "put", f"/api/projects/{_pid(ctx, pid)}/edit/timeline",
          data=json.dumps(tl), headers=JSON)
    page.reload()
    H.esperar_tela(page)


def _painel(page, nome: str) -> None:
    page.locator(f"#edRail button[data-panel='{nome}']").click()
    page.wait_for_timeout(250)


def _clipes(page):
    return page.locator(".ved-lane[data-tid='v1'] .ved-clip[data-uid]")


def _sel_clipe(page, i: int = 0) -> str:
    c = _clipes(page).nth(i)
    c.click()
    page.wait_for_timeout(250)
    return c.get_attribute("data-uid") or ""


def _slider(page, sel: str, valor) -> None:
    """input[type=range]: `fill` seta o valor e dispara input+change (bind do view.js)."""
    page.locator(sel).fill(str(valor))
    page.wait_for_timeout(150)


def _campo(page, sel: str, valor) -> None:
    """Campo numérico do painel direito: onchange só dispara no blur."""
    page.locator(sel).fill(str(valor))
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)


def _zoom(page, pct: int) -> None:
    _slider(page, "#zR", pct)


def _arrastar(page, box, dx: float, dy: float = 0.0, passos: int = 8) -> None:
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, passos + 1):
        page.mouse.move(x + dx * i / passos, y + dy * i / passos)
        page.wait_for_timeout(20)
    page.mouse.up()
    page.wait_for_timeout(300)


def _tc(page) -> str:
    return (page.locator("#pcTime").text_content() or "").strip()


def _no_ponto(page, seletor: str) -> str:
    """Quem realmente recebe o clique no centro de `seletor` (diagnóstico de overlay)."""
    return page.evaluate(
        """(sel) => { const el = document.querySelector(sel); if (!el) return 'ausente';
             const r = el.getBoundingClientRect();
             const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
             if (!t) return 'nada';
             return t.tagName.toLowerCase() + (t.id ? '#' + t.id : '') +
               (typeof t.className === 'string' && t.className ? '.' + t.className.trim().split(/\\s+/).join('.') : ''); }""",
        seletor)


# ---------------------------------------------------------------- barra superior
@caso("C-EDIT-01", "editor monta as 5 regiões e as 6 faixas da timeline")
def layout(page, ctx):
    regioes = {s: page.locator(s).count() for s in
               ("#ved .ved-top", "#edRail", "#edLeft", "#edStage", "#edPctl", "#edRight", "#edTimeline")}
    faixas = page.locator("#edTlHeads .ved-thead .tn").all_text_contents()
    esperado = ["TEXTO", "LEGENDAS", "VÍDEO 2", "VÍDEO 1", "MÚSICA", "SFX"]
    ev = H.evidencia(page, ctx, "C-EDIT-01-layout", full_page=False)
    return H.verifica(all(regioes.values()) and [f.strip() for f in faixas] == esperado,
                      f"5 regiões + faixas {faixas}",
                      f"regiões={regioes} faixas={faixas} esperado={esperado}", ev)


@caso("C-EDIT-02", "#edBack volta para a etapa 6 (música)")
def voltar(page, ctx):
    page.locator("#edBack").click()
    H.esperar_tela(page)
    return H.verifica(page.url.endswith(f"#/{ctx.pid_cheio}/music"), "voltou para music",
                      f"url={page.url} esperado …#/{ctx.pid_cheio}/music")


@caso("C-EDIT-03", "#edSaveBtn salva: toast, chip 'Salvo' e bloco editor no timeline.json")
def salvar(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        page.locator("#edSaveBtn").click()
        t = H.esperar_toast(page, "salvo")
        ok, tl = _esperar_disco(page, ctx, lambda x: bool(_editor(x)))
        estado = page.locator("#edSave").get_attribute("data-s")
        ev = H.evidencia(page, ctx, "C-EDIT-03-salvar", full_page=False)
        return H.verifica(bool(t) and ok and estado == "saved",
                          f"toast='{t}' status={estado} editor.version={_editor(tl).get('version')}",
                          f"toast='{t}' status={estado} editor no disco={bool(_editor(tl))}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-04", "#edAuto desligado segura a gravação; religar dispara o autosave")
def autosave(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        page.locator("#edAuto").uncheck()
        page.locator("#pLoud").click()          # toggle 'Normalizar áudio' do painel Projeto
        page.wait_for_timeout(1600)
        estado = page.locator("#edSave").get_attribute("data-s")
        gravou_cedo = _tl_disco(ctx).get("loudnorm") is False
        page.locator("#edAuto").check()
        ok, tl = _esperar_disco(page, ctx, lambda x: x.get("loudnorm") is False)
        ev = H.evidencia(page, ctx, "C-EDIT-04-autosave", full_page=False)
        return H.verifica(estado == "dirty" and not gravou_cedo and ok,
                          "autosave off segura; on grava",
                          f"status com autosave off={estado} gravou antes={gravou_cedo} "
                          f"gravou depois={tl.get('loudnorm')}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-05", "#edAspect/#edRes/#edFps mudam o projeto e persistem em editor.project")
def projeto_formato(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        page.locator("#edAspect").select_option("9:16")
        page.locator("#edRes").select_option("1280")
        page.locator("#edFps").select_option("24")
        ok, tl = _esperar_disco(page, ctx, lambda x: _editor(x).get("project", {}).get("fps") == 24)
        p = _editor(tl).get("project", {})
        painel = page.locator("#edProps").inner_text()
        ev = H.evidencia(page, ctx, "C-EDIT-05-projeto", full_page=False)
        return H.verifica(ok and p.get("aspect") == "9:16" and p.get("width") == 1280
                          and p.get("height") == 720 and "9:16" in painel and "24" in painel,
                          f"projeto={p}", f"disco={p} painel Projeto='{painel[:160]}'", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-06", "#edUndo/#edRedo e Ctrl+Z / Ctrl+Shift+Z desfazem e refazem")
def undo_redo(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        marks = lambda: page.locator("#edRuler .mk").count()  # noqa: E731
        page.locator("#tMark").click()
        page.wait_for_timeout(200)
        depois_add = marks()
        page.locator("#edUndo").click()
        page.wait_for_timeout(200)
        depois_undo = marks()
        page.locator("#edRedo").click()
        page.wait_for_timeout(200)
        depois_redo = marks()
        page.locator("#tMark").click()
        page.wait_for_timeout(200)
        dois = marks()
        page.keyboard.press("Control+z")
        page.wait_for_timeout(250)
        atalho_undo = marks()
        page.keyboard.press("Control+Shift+z")
        page.wait_for_timeout(250)
        atalho_redo = marks()
        seq = (depois_add, depois_undo, depois_redo, dois, atalho_undo, atalho_redo)
        ev = H.evidencia(page, ctx, "C-EDIT-06-undo", full_page=False)
        return H.verifica(seq == (1, 0, 1, 2, 1, 2), f"marcadores {seq}",
                          f"marcadores add/undo/redo/2x/ctrlZ/ctrlShiftZ={seq} esperado (1,0,1,2,1,2)", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-07", "#edGuide abre o guia da aula 014 em modal")
def guia(page, ctx):
    page.locator("#edGuide").click()
    m = H.modal(page)
    m.wait_for()
    page.wait_for_timeout(800)
    titulo = (m.locator(".modal-head h3").text_content() or "").strip()
    corpo = (m.locator(".modal-body").inner_text() or "").strip()
    ev = H.evidencia(page, ctx, "C-EDIT-07-guia", full_page=False)
    H.fechar_modal(page)
    sumiu = not H.modal(page).count() or not H.modal(page).is_visible()
    return H.verifica("014" in titulo and len(corpo) > 40 and "carregando" not in corpo.lower() and sumiu,
                      f"modal '{titulo}' com {len(corpo)} chars",
                      f"titulo='{titulo}' corpo='{corpo[:160]}' fechou={sumiu}", ev)


@caso("C-EDIT-08", "#edFull entra e sai de tela cheia")
def tela_cheia(page, ctx):
    if not page.evaluate("document.fullscreenEnabled"):
        return H.Resultado.bloqueado("navegador da rodada sem Fullscreen API (document.fullscreenEnabled=false)")
    page.locator("#edFull").click()
    page.wait_for_timeout(600)
    dentro = page.evaluate("!!document.fullscreenElement && document.fullscreenElement.id === 'ved'")
    page.locator("#edFull").click()
    page.wait_for_timeout(600)
    fora = page.evaluate("!document.fullscreenElement")
    return H.verifica(dentro and fora, "entrou e saiu de tela cheia",
                      f"entrou={dentro} saiu={fora}")


@caso("C-EDIT-09", "modal de exportação: pílulas e botões respondem ao clique do mouse")
def modal_export(page, ctx):
    page.locator("#edExport").click()
    m = H.modal(page)
    m.wait_for()
    res = m.locator("#exRes button").all_text_contents()
    fps = m.locator("#exFps button").all_text_contents()
    q = m.locator("#exQ button").all_text_contents()
    acoes = [a.strip() for a in m.locator(".modal-actions button").all_text_contents()]
    estrutura = (res == ["720p", "1080p", "1440p", "4K"] and len(fps) == 4
                 and q == ["baixa", "média", "alta"] and acoes == ["Rough cut", "Renderizar"])
    bloqueio = {sel: _no_ponto(page, sel) for sel in
                ("#exRes button[data-res='720p']", "#exQ button[data-q='baixa']",
                 ".modal-actions button[data-act='1']", ".modal-close")}
    clicou = True
    try:
        m.locator("#exRes button[data-res='720p']").click(timeout=3000)
    except Exception:  # noqa: BLE001 - o clique bloqueado é o achado do caso
        clicou = False
    marcada = m.locator("#exRes button[data-on]").get_attribute("data-res")
    ev = H.evidencia(page, ctx, "C-EDIT-09-modal-export", full_page=False)
    page.keyboard.press("Escape")          # o ✕ também está sob o overlay
    page.wait_for_timeout(300)
    return H.verifica(estrutura and clicou and marcada == "720p",
                      f"res={res} fps={fps} q={q} ações={acoes}; pílula marcada={marcada}",
                      f"estrutura ok={estrutura} (res={res} fps={fps} q={q} ações={acoes}); clique do mouse "
                      f"na pílula 720p funcionou={clicou}; quem recebe o clique em cada controle={bloqueio}", ev)


@caso("C-EDIT-10", "exportar 'Rough cut' roda o ffmpeg e grava edit/rough_cut.mp4")
def render_rough(page, ctx):
    orig = _tl_api(page, ctx)
    alvo = ctx.projeto(ctx.pid_cheio) / "edit" / "rough_cut.mp4"
    antes = alvo.stat().st_mtime if alvo.exists() else 0
    page.locator("#edExport").click()
    H.modal(page).wait_for()
    page.locator(".modal-actions button[data-act='0']").click()   # Rough cut
    page.wait_for_timeout(200)
    page.wait_for_timeout(500)
    prog = page.locator(".modal .prog-steps").count()
    fechou = H.esperar_modal_sumir(page, 180_000)
    page.wait_for_timeout(500)
    job = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/edit/render/job").json()
    ev = H.evidencia(page, ctx, "C-EDIT-10-rough", full_page=False)
    ok = fechou and alvo.exists() and alvo.stat().st_size > 1000 and alvo.stat().st_mtime > antes
    _restaurar(page, ctx, orig)      # o render salva a timeline antes de encodar
    return H.verifica(ok and prog > 0,
                      f"rough_cut.mp4 {alvo.stat().st_size if alvo.exists() else 0} B, job={job.get('state')}",
                      f"modal de progresso={prog} fechou={fechou} existe={alvo.exists()} "
                      f"job={job} log={job.get('log')}", ev)


@caso("C-EDIT-11", "exportar master 720p/24fps/baixa grava edit/master.mp4 e registra os parâmetros no job")
def render_master(page, ctx):
    orig = _tl_api(page, ctx)
    root = ctx.projeto(ctx.pid_cheio)
    alvo = root / "edit" / "master.mp4"
    antes = alvo.stat().st_mtime if alvo.exists() else 0
    page.locator("#edExport").click()
    H.modal(page).wait_for()
    page.locator("#exRes button[data-res='720p']").click()
    page.locator("#exFps button[data-fps='24 fps']").click()
    page.locator("#exQ button[data-q='baixa']").click()
    page.locator(".modal-actions button[data-act='1']").click()   # Renderizar
    fechou = H.esperar_modal_sumir(page, 180_000)
    page.wait_for_timeout(500)
    jobs = sorted((root / "jobs").glob("edit_render_*.json"), key=lambda p: p.stat().st_mtime)
    export = json.loads(jobs[-1].read_text()).get("export") if jobs else {}
    ev = H.evidencia(page, ctx, "C-EDIT-11-master", full_page=False)
    _restaurar(page, ctx, orig)
    ok = (fechou and alvo.exists() and alvo.stat().st_mtime > antes
          and export.get("width") == 1280 and export.get("fps") == 24 and export.get("quality") == "low")
    return H.verifica(ok, f"master.mp4 regravado, export={export}",
                      f"fechou={fechou} mtime novo={alvo.exists() and alvo.stat().st_mtime > antes} "
                      f"export={export}", ev)


# ---------------------------------------------------------------- rail e painéis
@caso("C-EDIT-12", "#edRail alterna os 10 painéis e marca o ativo")
def rail(page, ctx):
    esperado = ["media", "text", "captions", "audio", "transitions", "effects",
                "filters", "elements", "adjust", "library"]
    ids = page.locator("#edRail button").evaluate_all("els => els.map(e => e.dataset.panel)")
    titulos = {}
    for p in ["text", "transitions", "adjust", "library", "media"]:
        _painel(page, p)
        titulos[p] = ((page.locator("#edPanel .ved-phead h4").text_content() or "").strip(),
                      page.locator(f"#edRail button[data-panel='{p}'].on").count())
    ev = H.evidencia(page, ctx, "C-EDIT-12-rail", full_page=False)
    ok = ids == esperado and all(t and n == 1 for t, n in titulos.values())
    return H.verifica(ok, f"painéis {ids}", f"ids={ids} títulos/ativo={titulos}", ev)


@caso("C-EDIT-13", "painel Mídia lista os clipes do backbone e a busca filtra")
def midia_lista(page, ctx):
    _painel(page, "media")
    tl = _tl_api(page, ctx)
    cards = page.locator("#mList .ved-mcard[data-cid]")
    n = cards.count()
    page.locator("#mSearch").fill("shot02")
    page.wait_for_timeout(250)
    visiveis = page.locator("#mList .ved-mcard[data-cid]:visible").count()
    page.locator("#mSearch").fill("")
    ev = H.evidencia(page, ctx, "C-EDIT-13-midia", full_page=False)
    return H.verifica(n == len(tl["clips"]) and visiveis == 1,
                      f"{n} cards, busca deixou {visiveis}",
                      f"cards={n} clipes={len(tl['clips'])} visíveis após busca 'shot02'={visiveis}", ev)


@caso("C-EDIT-14", "#mUpload/#mUp importa mídia nova para o editor (disco + card)")
def midia_upload(page, ctx):
    _painel(page, "media")
    png = H.png_temp(ctx, "edit-media", color=(200, 60, 160))
    antes = len(H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/edit/media").json())
    H.upload(page, "#mUp", png)
    t = H.esperar_toast(page, "mídia")
    page.wait_for_timeout(600)
    media = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/edit/media").json()
    cards = page.locator("#mList .ved-mcard[data-mid]").count()
    no_disco = [f for f in H.arquivos(ctx.projeto(ctx.pid_cheio), "edit/candidates/*") if f.endswith(".png")]
    ev = H.evidencia(page, ctx, "C-EDIT-14-upload", full_page=False)
    return H.verifica(bool(t) and len(media) >= max(antes, 1) and cards == len(media) and bool(no_disco),
                      f"toast='{t}' {len(media)} mídia(s), {cards} cards, disco={no_disco[:2]}",
                      f"toast='{t}' media API={len(media)} (antes {antes}) cards={cards} disco={no_disco}", ev)


@caso("C-EDIT-15", "campanha sem takes abre o editor vazio com 'Montar a partir dos takes com like'", pid="vazio")
def vazio(page, ctx):
    _painel(page, "media")
    tl = _tl_api(page, ctx, ctx.pid_vazio)
    label = (page.locator("#edStage .ved-cliplabel").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "C-EDIT-15-vazio", full_page=False)
    ok = (not tl["clips"] and page.locator("#mReset").count() == 1
          and _clipes(page).count() == 0 and "sem clipes" in label.lower()
          and _tc(page).startswith("00:00:00"))
    return H.verifica(ok, f"timeline vazia, label='{label}', mReset presente",
                      f"clips={len(tl['clips'])} mReset={page.locator('#mReset').count()} "
                      f"label='{label}' tc='{_tc(page)}'", ev)


@caso("C-EDIT-16", "#mReset numa campanha sem takes mantém a timeline vazia sem erro", pid="vazio")
def reset_sem_takes(page, ctx):
    _painel(page, "media")
    page.locator("#mReset").click()
    page.wait_for_timeout(1200)
    erro = H.toast(page)
    tl = _tl_api(page, ctx, ctx.pid_vazio)
    quebrou = page.locator("#edTimeline").count() == 0
    ev = H.evidencia(page, ctx, "C-EDIT-16-reset-vazio", full_page=False)
    return H.verifica(not tl["clips"] and not quebrou and "erro" not in erro.lower(),
                      "timeline segue vazia e a tela continua de pé",
                      f"clips={len(tl['clips'])} toast='{erro}' timeline sumiu={quebrou}", ev)


@caso("C-EDIT-17", "painel Texto: preset 'Título' cria item na faixa TEXTO (preview, timeline e disco)")
def texto_preset(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _painel(page, "text")
        page.locator("#edPanel .ved-row[data-t='title']").click()
        page.wait_for_timeout(300)
        na_timeline = page.locator(".ved-lane[data-tid='t_txt'] .ved-clip[data-uid]").count()
        no_preview = page.locator("#edStage .ved-layer.text").count()
        ok, tl = _esperar_disco(page, ctx, lambda x: len(_track(x, "t_txt").get("items") or []) == 1)
        it = (_track(tl, "t_txt").get("items") or [{}])[0]
        ev = H.evidencia(page, ctx, "C-EDIT-17-texto", full_page=False)
        return H.verifica(ok and na_timeline == 1 and no_preview == 1 and it.get("text") == "Título",
                          f"item '{it.get('text')}' size={it.get('style', {}).get('size')}",
                          f"timeline={na_timeline} preview={no_preview} disco={it}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-18", "#capGen avisa que a geração automática depende de transcrição")
def legenda_gerar(page, ctx):
    _painel(page, "captions")
    page.locator("#capGen").click()
    t = H.esperar_toast(page, "transcrição")
    ev = H.evidencia(page, ctx, "C-EDIT-18-capgen", full_page=False)
    return H.verifica(bool(t), f"toast='{t}'",
                      f"toast esperado sobre transcrição pendente; observado='{H.toast(page)}'", ev)


@caso("C-EDIT-19", "painel Legendas oferece adicionar legenda manual (o toast do #capGen manda usar)")
def legenda_add_manual(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _painel(page, "captions")
        painel = page.locator("#edPanel")
        botoes = painel.locator("button").all_text_contents()
        add = painel.locator("button:not(#capGen):not([data-del])")
        if not add.count():
            ev = H.evidencia(page, ctx, "C-EDIT-19-legenda-add", full_page=False)
            return H.verifica(False, "",
                              "painel Legendas só tem '✨ Gerar legendas da narração' (que avisa 'Use + "
                              f"legenda manual') e os ✕ dos itens — não há como criar legenda manual. "
                              f"botões={botoes}", ev)
        add.first.click()
        ok, tl = _esperar_disco(page, ctx, lambda x: len(_track(x, "t_cap").get("items") or []) == 1)
        it = (_track(tl, "t_cap").get("items") or [{}])[0]
        na_timeline = page.locator(".ved-lane[data-tid='t_cap'] .ved-clip[data-uid]").count()
        no_preview = page.locator("#edStage .ved-layer.caption").count()
        ev = H.evidencia(page, ctx, "C-EDIT-19-legenda-add", full_page=False)
        return H.verifica(ok and na_timeline == 1 and no_preview == 1 and bool(it.get("text")),
                          f"legenda manual '{it.get('text')}' criada na faixa LEGENDAS",
                          f"botões={botoes}; item no disco={it} timeline={na_timeline} preview={no_preview}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-20", "painel Legendas lista o item da faixa e o ✕ apaga")
def legenda_delete(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        semente = json.loads(json.dumps(orig))
        semente["editor"] = {"version": 1, "project": {"width": 1920, "height": 1080, "fps": 30, "aspect": "16:9"},
                             "tracks": [{"id": "t_cap", "type": "caption", "name": "LEGENDAS", "height": 30,
                                         "items": [{"id": "cp_qa", "start": 0.0, "end": 1.0, "text": "legenda QA"}]}],
                             "clip_fx": {}, "transitions": [], "markers": [], "ui": {"zoom": 1, "snap": True}}
        H.api(page, ctx, "put", f"/api/projects/{ctx.pid_cheio}/edit/timeline",
              data=json.dumps(semente), headers=JSON)
        page.reload()
        H.esperar_tela(page)
        _painel(page, "captions")
        linhas = page.locator("#edPanel .ved-row[data-uid]").count()
        texto = (page.locator("#edPanel .ved-row[data-uid] .rn").first.text_content() or "").strip()
        page.locator("#edPanel .ved-row[data-uid] [data-del]").first.click()
        ok, tl = _esperar_disco(page, ctx, lambda x: not (_track(x, "t_cap").get("items") or []))
        restou = page.locator("#edPanel .ved-row[data-uid]").count()
        ev = H.evidencia(page, ctx, "C-EDIT-20-legenda-del", full_page=False)
        return H.verifica(linhas == 1 and texto == "legenda QA" and ok and restou == 0,
                          "legenda listada e apagada pelo ✕",
                          f"linhas={linhas} texto='{texto}' apagou no disco={ok} restou={restou} "
                          f"track={_track(tl, 't_cap')}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-21", "#sfxUp importa SFX, joga na faixa SFX e grava em edit/candidates")
def sfx_upload(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _painel(page, "audio")
        mp3 = H.mp3_temp(ctx, "edit-sfx")
        H.upload(page, "#sfxUp", mp3)
        t = H.esperar_toast(page, "sfx")
        ok, tl = _esperar_disco(page, ctx, lambda x: len(x.get("sfx") or []) >= 1, timeout_ms=12000)
        lib = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/edit/sfx").json()
        na_faixa = page.locator(".ved-lane[data-tid='t_sfx'] .ved-clip[data-uid]").count()
        ev = H.evidencia(page, ctx, "C-EDIT-21-sfx", full_page=False)
        return H.verifica(bool(t) and ok and na_faixa >= 1 and len(lib) >= 1,
                          f"toast='{t}' sfx no disco={tl.get('sfx')} biblioteca={len(lib)}",
                          f"toast='{t}' timeline.sfx={tl.get('sfx')} faixa SFX={na_faixa} lib={lib}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-22", "'+' da biblioteca de SFX insere o efeito no playhead")
def sfx_biblioteca(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        lib = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/edit/sfx").json()
        if not lib:
            mp3 = H.mp3_temp(ctx, "edit-sfx")
            H.upload(page, "#sfxUp", mp3) if page.locator("#sfxUp").count() else None
            _painel(page, "audio")
            H.upload(page, "#sfxUp", mp3)
            H.esperar_toast(page, "sfx")
            page.wait_for_timeout(1500)
            _restaurar(page, ctx, orig)
        _painel(page, "audio")
        botao = page.locator("#edPanel [data-aud^='lib:']").first
        if not botao.count():
            return H.Resultado.bloqueado("biblioteca de SFX vazia — nada para inserir")
        page.locator("#pcNext").click()
        page.wait_for_timeout(150)
        botao.click()
        ok, tl = _esperar_disco(page, ctx, lambda x: len(x.get("sfx") or []) == 1)
        s = (tl.get("sfx") or [{}])[0]
        ev = H.evidencia(page, ctx, "C-EDIT-22-sfx-lib", full_page=False)
        return H.verifica(ok and s.get("gain") == -6 and s.get("at", -1) > 0,
                          f"sfx inserido em {s.get('at')}s gain {s.get('gain')}",
                          f"timeline.sfx={tl.get('sfx')} (esperado 1 item no playhead)", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-23", "Transições: sem clipe selecionado avisa; com clipe grava a transição escolhida")
def transicao_aplica(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        page.keyboard.press("Escape")           # limpa seleção
        _painel(page, "transitions")
        page.locator("#edPanel [data-tr='Fade']").click()
        aviso = H.esperar_toast(page, "selecione")
        _sel_clipe(page, 0)
        _painel(page, "transitions")
        page.locator("#edPanel [data-tr='Glitch']").click()
        confirmacao = H.esperar_toast(page, "Glitch")
        ok, tl = _esperar_disco(page, ctx, lambda x: len(_editor(x).get("transitions") or []) == 1)
        tr = (_editor(tl).get("transitions") or [{}])[0]
        marca = page.locator(".ved-lane[data-tid='v1'] .ved-trans").count()
        ev = H.evidencia(page, ctx, "C-EDIT-23-transicao", full_page=False)
        return H.verifica(bool(aviso) and ok and marca == 1 and tr.get("type") == "glitch",
                          f"aviso='{aviso}' transição={tr.get('type')} marca na timeline={marca}",
                          f"aviso sem seleção='{aviso}' toast='{confirmacao}' indicadores={marca}; a UI mandou "
                          f"'Glitch' e o disco guardou {tr.get('type')!r} — transições no disco="
                          f"{_editor(tl).get('transitions')}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-24", "indicador de transição abre o modal e o botão Remover apaga")
def transicao_modal(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _sel_clipe(page, 0)
        _painel(page, "transitions")
        page.locator("#edPanel [data-tr='Zoom']").click()
        _esperar_disco(page, ctx, lambda x: len(_editor(x).get("transitions") or []) == 1)
        page.locator(".ved-lane[data-tid='v1'] .ved-trans").first.click()
        m = H.modal(page)
        m.wait_for()
        titulo = (m.locator(".modal-head h3").text_content() or "").strip()
        tipos = m.locator("#trT option").count()
        ev = H.evidencia(page, ctx, "C-EDIT-24-transicao-modal", full_page=False)
        m.locator(".modal-actions button[data-act='0']").click()   # Remover
        ok, tl = _esperar_disco(page, ctx, lambda x: not (_editor(x).get("transitions") or []))
        return H.verifica(titulo.startswith("Transição ·") and tipos == 12 and ok,
                          f"modal '{titulo}' com {tipos} tipos; removida",
                          f"titulo='{titulo}' opções={tipos} removeu no disco={ok} "
                          f"transições={_editor(tl).get('transitions')}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-25", "painel Efeitos aplica Blur no clipe selecionado (marca o botão e persiste)")
def efeito(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        uid = _sel_clipe(page, 0)
        _painel(page, "effects")
        page.locator("#edPanel [data-ef='Blur']").click()
        page.wait_for_timeout(300)
        marcado = page.locator("#edPanel [data-ef='Blur'].on").count()
        ok, tl = _esperar_disco(page, ctx, lambda x: bool(_editor(x).get("clip_fx", {}).get(uid, {}).get("effects")))
        fx = _editor(tl).get("clip_fx", {}).get(uid, {})
        ev = H.evidencia(page, ctx, "C-EDIT-25-efeito", full_page=False)
        return H.verifica(ok and marcado == 1 and fx.get("effects", [{}])[0].get("type") == "Blur",
                          f"efeitos={fx.get('effects')}",
                          f"botão marcado={marcado} clip_fx[{uid}]={fx}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-26", "painel Filtros: preset aplicado ao clipe é gravado na timeline")
def filtro(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        uid = _sel_clipe(page, 0)
        _painel(page, "filters")
        page.locator("#edPanel [data-fl='mono']").click()
        page.wait_for_timeout(400)
        _esperar_salvo(page)
        page.wait_for_timeout(400)
        fx = _editor(_tl_disco(ctx)).get("clip_fx", {}).get(uid, {})
        ev = H.evidencia(page, ctx, "C-EDIT-26-filtro", full_page=False)
        return H.verifica(fx.get("filters", {}).get("preset") == "mono",
                          f"preset gravado: {fx.get('filters')}",
                          f"clip_fx[{uid}] gravado={fx} — o preset escolhido (filters.preset + presetCss) "
                          "não aparece no round-trip do PUT; o filtro some ao reabrir a etapa", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-27", "painel Elementos adiciona forma na faixa VÍDEO 2 (overlay)")
def elemento(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _painel(page, "elements")
        page.locator("#edPanel [data-el='rect']").click()
        page.wait_for_timeout(300)
        na_timeline = page.locator(".ved-lane[data-tid='v2'] .ved-clip[data-uid]").count()
        no_preview = page.locator("#edStage .ved-layer.overlay").count()
        ok, tl = _esperar_disco(page, ctx, lambda x: len(_track(x, "v2").get("items") or []) == 1)
        it = (_track(tl, "v2").get("items") or [{}])[0]
        ev = H.evidencia(page, ctx, "C-EDIT-27-elemento", full_page=False)
        return H.verifica(ok and na_timeline == 1 and no_preview == 1,
                          f"overlay {it.get('id')} na v2 ({it.get('start')}→{it.get('end')})",
                          f"timeline={na_timeline} preview={no_preview} item no disco={it}", ev)
    finally:
        _restaurar(page, ctx, orig)


# ---------------------------------------------------------------- player
@caso("C-EDIT-28", "#pcPlay e a tecla Espaço tocam e pausam")
def play_pause(page, ctx):
    page.locator("#pcStart").click()
    page.locator("#pcPlay").click()
    page.wait_for_timeout(250)
    tocando = (page.locator("#pcPlay").text_content() or "").strip()
    andou = _tc(page)
    page.locator("#pcPlay").click()
    page.wait_for_timeout(200)
    parado = (page.locator("#pcPlay").text_content() or "").strip()
    page.locator("#pcStart").click()
    page.keyboard.press("Space")
    page.wait_for_timeout(250)
    por_atalho = (page.locator("#pcPlay").text_content() or "").strip()
    page.keyboard.press("Space")
    page.wait_for_timeout(200)
    ev = H.evidencia(page, ctx, "C-EDIT-28-play", full_page=False)
    return H.verifica(tocando == "❚❚" and parado == "▶" and por_atalho == "❚❚"
                      and not andou.startswith("00:00:00 /"),
                      f"play/pause ok, timecode andou para {andou}",
                      f"ícone tocando='{tocando}' parado='{parado}' via Espaço='{por_atalho}' tc='{andou}'", ev)


@caso("C-EDIT-29", "transporte: #pcStart/#pcPrev/#pcNext/#pcEnd e setas ←/→ movem o playhead")
def transporte(page, ctx):
    page.locator("#pcStart").click()
    inicio = _tc(page)
    page.locator("#pcNext").click()
    page.wait_for_timeout(120)
    um_frame = _tc(page)
    page.locator("#pcPrev").click()
    page.wait_for_timeout(120)
    voltou = _tc(page)
    page.locator("#pcEnd").click()
    page.wait_for_timeout(150)
    fim = _tc(page)
    page.keyboard.press("ArrowLeft")
    page.wait_for_timeout(150)
    seta_esq = _tc(page)
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(150)
    seta_dir = _tc(page)
    ev = H.evidencia(page, ctx, "C-EDIT-29-transporte", full_page=False)
    ok = (inicio.startswith("00:00:00") and um_frame.startswith("00:00:01") and voltou.startswith("00:00:00")
          and not fim.startswith("00:00:00") and seta_esq != fim and seta_dir == fim)
    return H.verifica(ok, f"início={inicio} +1f={um_frame} fim={fim}",
                      f"start={inicio} next={um_frame} prev={voltou} end={fim} ←={seta_esq} →={seta_dir}", ev)


@caso("C-EDIT-30", "#pcLoop, #pcMute e #pcVol alternam o estado do player")
def loop_mute(page, ctx):
    page.locator("#pcLoop").click()
    loop_on = page.locator("#pcLoop.on").count()
    page.locator("#pcMute").click()
    mudo = (page.locator("#pcMute").text_content() or "").strip()
    _slider(page, "#pcVol", 30)
    vol = page.locator("#pcVol").input_value()
    page.locator("#pcLoop").click()
    page.locator("#pcMute").click()
    loop_off = page.locator("#pcLoop.on").count()
    som = (page.locator("#pcMute").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "C-EDIT-30-loop-mute", full_page=False)
    return H.verifica(loop_on == 1 and loop_off == 0 and mudo == "🔈" and som == "🔊" and vol == "30",
                      f"loop on/off ok, mute {mudo}→{som}, volume {vol}",
                      f"loop on={loop_on} off={loop_off} mute='{mudo}' som='{som}' vol={vol}", ev)


# ---------------------------------------------------------------- painel de propriedades
@caso("C-EDIT-31", "painel Projeto (sem seleção): #pFade e #pLoud gravam fade_out e loudnorm")
def props_projeto(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        texto = page.locator("#edProps").inner_text()
        _slider(page, "#pFade", 3)
        ok1, tl = _esperar_disco(page, ctx, lambda x: abs(float(x.get("fade_out", 0)) - 3.0) < 0.01)
        page.locator("#pLoud").click()
        ok2, tl = _esperar_disco(page, ctx, lambda x: x.get("loudnorm") is False)
        ev = H.evidencia(page, ctx, "C-EDIT-31-projeto", full_page=False)
        return H.verifica(ok1 and ok2 and "Duração" in texto and "Clipes" in texto,
                          f"fade_out={tl.get('fade_out')} loudnorm={tl.get('loudnorm')}",
                          f"painel='{texto[:140]}' fade gravado={ok1} loudnorm={tl.get('loudnorm')}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-32", "aba Básico: X/Y/escala/rotação/opacidade/flip gravam clip_fx.transform")
def props_basico(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        uid = _sel_clipe(page, 0)
        page.locator("#edProps [data-tab='basico']").click()
        page.wait_for_timeout(200)
        _campo(page, "#bX", 70)
        _campo(page, "#bY", 40)
        _campo(page, "#bR", 15)
        _slider(page, "#bOp", 50)
        page.locator("#bFx").click()
        page.wait_for_timeout(200)
        ok, tl = _esperar_disco(
            page, ctx, lambda x: _editor(x).get("clip_fx", {}).get(uid, {}).get("transform", {}).get("flipX") is True)
        tf = _editor(tl).get("clip_fx", {}).get(uid, {}).get("transform", {})
        ev = H.evidencia(page, ctx, "C-EDIT-32-basico", full_page=False)
        certo = (abs(tf.get("x", 0) - 0.7) < 0.01 and abs(tf.get("y", 0) - 0.4) < 0.01
                 and abs(tf.get("rotation", 0) - 15) < 0.01 and abs(tf.get("opacity", 1) - 0.5) < 0.01
                 and tf.get("flipX") is True)
        return H.verifica(ok and certo, f"transform={tf}",
                          f"clip_fx[{uid}].transform={tf} (esperado x=.7 y=.4 rot=15 op=.5 flipX=true)", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-33", "aba Vídeo: in/out/zoom gravam o trim não destrutivo em clips[]")
def props_video(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        uid = _sel_clipe(page, 0)
        page.locator("#edProps [data-tab='video']").click()
        page.wait_for_timeout(200)
        _campo(page, "#vOut", "0.40")
        _campo(page, "#vIn", "0.10")
        _campo(page, "#vZoom", "1.20")
        ok, tl = _esperar_disco(page, ctx, lambda x: abs(float(x["clips"][0]["in"]) - 0.10) < 0.01)
        c = tl["clips"][0]
        ev = H.evidencia(page, ctx, "C-EDIT-33-video", full_page=False)
        return H.verifica(ok and c["id"] == uid and abs(c["out"] - 0.40) < 0.01 and abs(c["zoom"] - 1.2) < 0.01,
                          f"clipe in={c['in']} out={c['out']} zoom={c['zoom']}",
                          f"clipe no disco={c} (esperado in=0.1 out=0.4 zoom=1.2)", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-34", "aba Áudio do clipe: volume/mudo ficam guardados em clip_fx.audio (FDD rodada 2 §4)")
def props_audio_clipe(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        uid = _sel_clipe(page, 0)
        page.locator("#edProps [data-tab='audio']").click()
        page.wait_for_timeout(200)
        _slider(page, "#avVol", 50)
        page.locator("#edProps [data-at='muted']").click()
        page.wait_for_timeout(200)
        na_ui = page.locator("#edProps [data-at='muted'].on").count()
        _esperar_salvo(page)
        page.wait_for_timeout(500)
        fx = _editor(_tl_disco(ctx)).get("clip_fx", {}).get(uid, {})
        ev = H.evidencia(page, ctx, "C-EDIT-34-audio-clipe", full_page=False)
        a = fx.get("audio") or {}
        return H.verifica(na_ui == 1 and a.get("muted") is True and abs(a.get("volume", 1) - 0.5) < 0.01,
                          f"clip_fx.audio={a}",
                          f"UI marcou mudo={na_ui} mas clip_fx[{uid}] gravado={fx} — o bloco `audio` "
                          "(volume/mudo/fades) não sobrevive ao PUT", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-35", "aba Velocidade: preset 2x muda speed no disco e rotula o clipe na timeline")
def props_velocidade(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        uid = _sel_clipe(page, 0)
        page.locator("#edProps [data-tab='speed']").click()
        page.wait_for_timeout(200)
        page.locator("#edProps [data-sp='2']").click()
        ok, tl = _esperar_disco(page, ctx, lambda x: abs(float(x["clips"][0]["speed"]) - 2.0) < 0.01)
        rotulo = (page.locator(f".ved-clip[data-uid='{uid}'] .cl-name").first.text_content() or "").strip()
        marcado = page.locator("#edProps [data-sp='2'].on").count()
        ev = H.evidencia(page, ctx, "C-EDIT-35-velocidade", full_page=False)
        return H.verifica(ok and "2x" in rotulo and marcado == 1,
                          f"speed={tl['clips'][0]['speed']} rótulo='{rotulo}'",
                          f"speed no disco={tl['clips'][0].get('speed')} rótulo='{rotulo}' botão on={marcado}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-36", "aba Ajustes: sliders gravam clip_fx.filters e #cReset zera")
def props_ajustes(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        uid = _sel_clipe(page, 0)
        page.locator("#edProps [data-tab='ajustes']").click()
        page.wait_for_timeout(200)
        filtros = lambda x: _editor(x).get("clip_fx", {}).get(uid, {}).get("filters", {})  # noqa: E731
        _slider(page, "#cadj-contrast", 40)
        ok1, _ = _esperar_disco(page, ctx, lambda x: filtros(x).get("contrast") == 40)
        _slider(page, "#cadj-saturation", 30)          # 2ª edição, já depois do autosave da 1ª
        ok2, tl = _esperar_disco(page, ctx, lambda x: filtros(x).get("saturation") == 30, timeout_ms=6000)
        page.locator("#cReset").click()
        ok3, tl2 = _esperar_disco(page, ctx, lambda x: not filtros(x), timeout_ms=6000)
        ev = H.evidencia(page, ctx, "C-EDIT-36-ajustes", full_page=False)
        return H.verifica(ok1 and ok2 and ok3, "contraste + saturação gravados e resetados",
                          f"1ª edição gravou={ok1} ({filtros(tl)}); 2ª edição (saturação) gravou={ok2}; "
                          f"#cReset zerou={ok3} (filtros={filtros(tl2)}) — depois que o autosave conclui, "
                          "`save()` troca `St.timeline` pelo objeto devolvido no PUT e os handlers já "
                          "montados do painel seguem editando a cópia velha: a edição some sem aviso", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-37", "props de texto: #txSh e #txUp gravam sombra/maiúsculas no estilo do item")
def props_texto(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _painel(page, "text")
        page.locator("#edPanel .ved-row[data-t='subtitle']").click()
        page.wait_for_timeout(400)
        page.locator("#txSh").click()
        page.wait_for_timeout(150)
        page.locator("#txUp").click()
        ok, tl = _esperar_disco(
            page, ctx,
            lambda x: (_track(x, "t_txt").get("items") or [{}])[0].get("style", {}).get("uppercase") is True)
        st = (_track(tl, "t_txt").get("items") or [{}])[0].get("style", {})
        no_preview = (page.locator("#edStage .ved-layer.text").first.text_content() or "").strip()
        ev = H.evidencia(page, ctx, "C-EDIT-37-texto-props", full_page=False)
        return H.verifica(ok and st.get("shadow") is False and no_preview == "SUBTÍTULO",
                          f"estilo={st} preview='{no_preview}'",
                          f"style no disco={st} (esperado shadow=false uppercase=true) preview='{no_preview}'", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-38", "props da música: #mMute deixa a trilha muda e o estado persiste")
def props_musica(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        page.locator(".ved-lane[data-tid='t_mus'] .ved-clip[data-uid]").first.click()
        page.wait_for_timeout(300)
        aba = (page.locator("#edProps h4").text_content() or "").strip()
        page.locator("#mMute").click()
        page.wait_for_timeout(200)
        na_ui = page.locator("#mMute.on").count()
        _esperar_salvo(page)
        page.wait_for_timeout(500)
        tl = _tl_disco(ctx)
        ev = H.evidencia(page, ctx, "C-EDIT-38-musica", full_page=False)
        return H.verifica(aba == "Música" and na_ui == 1 and (tl.get("music") or {}).get("muted") is True,
                          f"música muda no disco: {tl.get('music')}",
                          f"painel='{aba}' switch on={na_ui} music no disco={tl.get('music')} — "
                          "`muted` some no round-trip (validate_timeline devolve só file/offset)", ev)
    finally:
        _restaurar(page, ctx, orig)


# ---------------------------------------------------------------- timeline
@caso("C-EDIT-39", "clicar num clipe seleciona (borda, contador e painel de propriedades)")
def selecao(page, ctx):
    uid = _sel_clipe(page, 1)
    sel = page.locator(f".ved-clip[data-uid='{uid}'].sel").count()
    info = (page.locator("#tSel").text_content() or "").strip()
    props = (page.locator("#edProps h4").text_content() or "").strip()
    abas = page.locator("#edProps .ved-tabs button").all_text_contents()
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    limpou = (page.locator("#tSel").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "C-EDIT-39-selecao", full_page=False)
    return H.verifica(sel == 1 and "1 selecionado" in info and props.startswith("shot02")
                      and abas == ["Básico", "Vídeo", "Áudio", "Velocidade", "Ajustes"] and "clique" in limpou,
                      f"selecionado {uid}: '{info}', props '{props}'",
                      f"sel={sel} info='{info}' props='{props}' abas={abas} após Escape='{limpou}'", ev)


@caso("C-EDIT-40", "#tSplit e Ctrl+B dividem o clipe sob o playhead")
def split(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        page.locator("#pcStart").click()
        for _ in range(8):
            page.locator("#pcNext").click()
        page.wait_for_timeout(200)
        page.locator("#tSplit").click()
        t = H.esperar_toast(page, "dividido")
        ok, tl = _esperar_disco(page, ctx, lambda x: len(x["clips"]) == len(orig["clips"]) + 1)
        page.keyboard.press("Control+z")
        page.wait_for_timeout(400)
        page.keyboard.press("Control+b")
        ok2, tl2 = _esperar_disco(page, ctx, lambda x: len(x["clips"]) == len(orig["clips"]) + 1)
        a, b = tl["clips"][0], tl["clips"][1]
        ev = H.evidencia(page, ctx, "C-EDIT-40-split", full_page=False)
        return H.verifica(ok and ok2 and abs(a["out"] - 0.267) < 0.02 and abs(b["in"] - a["out"]) < 0.001
                          and b["file"] == a["file"],
                          f"toast='{t}' {len(tl['clips'])} clipes; corte em {a['out']}s",
                          f"clipes botão={len(tl['clips'])} atalho={len(tl2['clips'])} a={a} b={b}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-41", "#tDup e Ctrl+D duplicam o clipe selecionado")
def duplicar(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        uid = _sel_clipe(page, 0)
        page.locator("#tDup").click()
        ok, tl = _esperar_disco(page, ctx, lambda x: len(x["clips"]) == len(orig["clips"]) + 1)
        page.keyboard.press("Control+z")
        page.wait_for_timeout(400)
        _sel_clipe(page, 0)
        page.keyboard.press("Control+d")
        ok2, tl2 = _esperar_disco(page, ctx, lambda x: len(x["clips"]) == len(orig["clips"]) + 1)
        copia = tl["clips"][1]
        ev = H.evidencia(page, ctx, "C-EDIT-41-dup", full_page=False)
        return H.verifica(ok and ok2 and copia["file"] == orig["clips"][0]["file"] and copia["id"] != uid,
                          f"{len(tl['clips'])} clipes; cópia {copia['id']} logo depois do original",
                          f"botão={len(tl['clips'])} atalho={len(tl2['clips'])} cópia={copia}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-42", "#tDel/Delete excluem o clipe e barram a exclusão do último")
def excluir(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _sel_clipe(page, 1)
        page.locator("#tDel").click()
        ok, tl = _esperar_disco(page, ctx, lambda x: len(x["clips"]) == 1)
        _sel_clipe(page, 0)
        page.keyboard.press("Delete")
        aviso = H.esperar_toast(page, "ao menos um clipe")
        page.wait_for_timeout(1200)
        final = _tl_disco(ctx)
        ev = H.evidencia(page, ctx, "C-EDIT-42-excluir", full_page=False)
        return H.verifica(ok and bool(aviso) and len(final["clips"]) == 1,
                          f"1 clipe restante; aviso='{aviso}'",
                          f"após #tDel={len(tl['clips'])} clipes; após Delete no último="
                          f"{len(final.get('clips', []))} aviso='{aviso}'", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-43", "#tRipple remove o clipe sem deixar a montagem sem nenhum clipe")
def ripple(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _sel_clipe(page, 1)
        page.locator("#tRipple").click()
        ok, tl = _esperar_disco(page, ctx, lambda x: len(x["clips"]) == 1)
        _sel_clipe(page, 0)
        page.locator("#tRipple").click()
        page.wait_for_timeout(1500)
        final = _tl_disco(ctx)
        aviso = H.toast(page)
        ev = H.evidencia(page, ctx, "C-EDIT-43-ripple", full_page=False)
        return H.verifica(ok and len(final.get("clips", [])) >= 1,
                          f"ripple removeu 1 clipe e parou em {len(final.get('clips', []))}",
                          f"1º ripple deixou {len(tl['clips'])} clipe(s); 2º ripple deixou "
                          f"{len(final.get('clips', []))} (esperado ≥1, como no #tDel) toast='{aviso}'", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-44", "arrastar um clipe na timeline solta-o na posição livre (modo posicional)")
def arrastar_clipe(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _zoom(page, 400)
        uid = _sel_clipe(page, 1)
        box = page.locator(f".ved-clip[data-uid='{uid}']").bounding_box()
        _arrastar(page, box, 60)
        ok, tl = _esperar_disco(page, ctx, lambda x: x["clips"][1].get("start") is not None)
        c0, c1 = tl["clips"][0], tl["clips"][1]
        esperado = round(orig["clips"][0]["out"] + 60 / (46 * 4), 3)
        ev = H.evidencia(page, ctx, "C-EDIT-44-drag", full_page=False)
        return H.verifica(ok and c0.get("start") == 0 and abs(c1.get("start", 0) - esperado) < 0.06,
                          f"clipe 2 em start={c1.get('start')}s (esperado ~{esperado})",
                          f"clips no disco: start0={c0.get('start')} start1={c1.get('start')} "
                          f"esperado ~{esperado}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-45", "arrastar a borda direita do clipe faz o trim (in/out) na timeline")
def trim_clipe(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _zoom(page, 400)
        uid = _sel_clipe(page, 0)
        alca = page.locator(f".ved-clip[data-uid='{uid}'] .cl-trim.r")
        box = alca.bounding_box()
        _arrastar(page, box, 40)
        ok, tl = _esperar_disco(page, ctx, lambda x: float(x["clips"][0]["out"]) > orig["clips"][0]["out"] + 0.1)
        c = tl["clips"][0]
        esperado = round(orig["clips"][0]["out"] + 40 / (46 * 4), 3)
        ev = H.evidencia(page, ctx, "C-EDIT-45-trim", full_page=False)
        return H.verifica(ok and abs(c["out"] - esperado) < 0.06 and c["in"] == orig["clips"][0]["in"],
                          f"out {orig['clips'][0]['out']}→{c['out']} (esperado ~{esperado})",
                          f"clipe no disco={c} esperado out~{esperado} com in intacto", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-46", "zoom da timeline (#zIn/#zOut/#zR) muda a escala e o nível sobrevive ao reload")
def zoom_timeline(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        largura = lambda: round(_clipes(page).first.bounding_box()["width"], 1)  # noqa: E731
        _zoom(page, 100)
        base = largura()
        _zoom(page, 200)
        dobro = largura()
        page.locator("#zOut").click()          # 200% - 25 pontos
        page.wait_for_timeout(250)
        menor = largura()
        rotulo = (page.locator("#edTimeline .zoom .zp").text_content() or "").strip()
        _zoom(page, 100)
        gravou, tl = _esperar_disco(page, ctx, lambda x: _editor(x).get("ui", {}).get("zoom") is not None)
        page.reload()
        H.esperar_tela(page)
        depois = (page.locator("#edTimeline .zoom .zp").text_content() or "").strip()
        ev = H.evidencia(page, ctx, "C-EDIT-46-zoom", full_page=False)
        return H.verifica(abs(dobro - 2 * base) < 3 and menor < dobro and rotulo == "175%" and depois == "100%",
                          f"clipe {base}→{dobro}px; zoom preservado em {depois}",
                          f"largura do clipe 100%={base} 200%={dobro} após #zOut={menor} (rótulo '{rotulo}'); "
                          f"gravou ui.zoom={gravou} valor no disco={_editor(tl).get('ui', {}).get('zoom')}; "
                          f"após reload a timeline abre em {depois} (esperado 100%) — o front grava o zoom "
                          "como fator (0.25–4) e `editor.normalize_editor` clampa o campo em 2–400 (px/s)", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-47", "#tMark crava um marcador no playhead (régua + editor.markers)")
def marcador(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        page.locator("#pcStart").click()
        for _ in range(6):
            page.locator("#pcNext").click()
        page.locator("#tMark").click()
        ok, tl = _esperar_disco(page, ctx, lambda x: len(_editor(x).get("markers") or []) == 1)
        mk = (_editor(tl).get("markers") or [{}])[0]
        na_regua = page.locator("#edRuler .mk").count()
        ev = H.evidencia(page, ctx, "C-EDIT-47-marcador", full_page=False)
        return H.verifica(ok and na_regua == 1 and abs(float(mk.get("at", 0)) - 0.2) < 0.03,
                          f"marcador em {mk.get('at')}s", f"régua={na_regua} marcador no disco={mk}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-48", "cabeçalhos das faixas: VÍDEO 1 é do backbone e as faixas do editor escondem/travam")
def cabecalhos(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        page.locator("#edTlHeads .ved-thead[data-tid='v1'] button[data-act='vis']").click()
        aviso = H.esperar_toast(page, "backbone")
        page.locator("#edTlHeads .ved-thead[data-tid='t_txt'] button[data-act='lock']").click()
        ok, tl = _esperar_disco(page, ctx, lambda x: _track(x, "t_txt").get("locked") is True)
        ev = H.evidencia(page, ctx, "C-EDIT-48-heads", full_page=False)
        return H.verifica(bool(aviso) and ok, f"aviso='{aviso}' faixa TEXTO travada",
                          f"toast do backbone='{aviso}' faixa t_txt no disco={_track(tl, 't_txt')}", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-49", "botão direito num clipe abre o menu de contexto com as ações do clipe")
def menu_contexto(page, ctx):
    _sel_clipe(page, 0)
    _clipes(page).nth(0).click(button="right")
    page.wait_for_timeout(300)
    itens = page.locator("#vedMenu button").all_text_contents()
    ev = H.evidencia(page, ctx, "C-EDIT-49-menu", full_page=False)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    fechou = page.locator("#vedMenu").count() == 0
    esperados = {"Dividir", "Copiar", "Duplicar", "Ripple delete", "Excluir"}
    achados = {i.split("Ctrl")[0].split("Del")[0].strip() for i in itens}
    return H.verifica(esperados <= achados and fechou, f"menu com {itens}",
                      f"itens={itens} (esperados {sorted(esperados)}) fechou com Escape={fechou}", ev)


@caso("C-EDIT-50", "preview continua mostrando o vídeo do clipe depois de uma edição")
def preview_apos_edicao(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        estado = ("() => { const s = document.getElementById('edStage'); const v = s && s.querySelector('video');"
                  " return {videos: s ? s.querySelectorAll('video').length : 0,"
                  " display: v ? v.style.display : null, pronto: v ? v.readyState : null,"
                  " label: (s && s.querySelector('.ved-cliplabel') || {}).textContent || ''} }")
        antes = page.evaluate(estado)
        page.locator("#tMark").click()          # qualquer commit reconstrói o root (renderAll)
        page.wait_for_timeout(600)
        depois = page.evaluate(estado)
        ev = H.evidencia(page, ctx, "C-EDIT-50-preview", full_page=False)
        return H.verifica(antes["videos"] == 1 and depois["videos"] == 1 and depois["display"] == "block",
                          f"vídeo no palco antes={antes} depois={depois}",
                          f"antes da edição={antes}; depois da edição={depois} — o <video> do clipe fica "
                          "fora do #edStage (videoPool não é reanexado no renderRoot) e o preview zera "
                          "até recarregar a etapa", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-51", "edições sobrevivem ao reload da tela (GET timeline + DOM)")
def persistencia(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _painel(page, "text")
        page.locator("#edPanel .ved-row[data-t='cta']").click()
        page.wait_for_timeout(300)
        page.locator("#tMark").click()
        ok, _ = _esperar_disco(page, ctx, lambda x: len(_track(x, "t_txt").get("items") or []) == 1
                               and len(_editor(x).get("markers") or []) == 1)
        page.reload()
        H.esperar_tela(page)
        via_api = _tl_api(page, ctx)
        texto_dom = page.locator(".ved-lane[data-tid='t_txt'] .ved-clip[data-uid]").count()
        markers_dom = page.locator("#edRuler .mk").count()
        ev = H.evidencia(page, ctx, "C-EDIT-51-persistencia", full_page=False)
        itens = (_track(via_api, "t_txt").get("items") or [])
        return H.verifica(ok and len(itens) == 1 and texto_dom == 1 and markers_dom == 1,
                          f"após reload: texto '{itens[0].get('text') if itens else None}' e 1 marcador",
                          f"GET itens={itens} DOM texto={texto_dom} markers={markers_dom}", ev)
    finally:
        _restaurar(page, ctx, orig)


# ---------------------------------------------------------------- áudio do preview
def _semente_longa(page, ctx, sfx=None) -> None:
    """Alonga os clipes para 2 s cada (timeline de ~4 s) — janela confortável para ouvir o áudio."""
    nova = json.loads(json.dumps(_tl_api(page, ctx)))
    for c in nova["clips"]:
        c["in"], c["out"] = 0.0, 2.0
    if sfx is not None:
        nova["sfx"] = sfx
    H.api(page, ctx, "put", f"/api/projects/{ctx.pid_cheio}/edit/timeline",
          data=json.dumps(nova), headers=JSON)
    page.reload()
    H.esperar_tela(page)


def _tocar(page) -> None:
    if (page.locator("#pcPlay").text_content() or "").strip() != "❚❚":
        page.locator("#pcPlay").click()


def _parar(page) -> None:
    if (page.locator("#pcPlay").text_content() or "").strip() == "❚❚":
        page.locator("#pcPlay").click()


@caso("C-EDIT-52", "trilha do projeto toca no preview (<audio> no palco, sai do pausado e anda)")
def musica_toca(page, ctx):
    orig = _tl_api(page, ctx)
    if not (orig.get("music") or {}).get("file"):
        return H.Resultado.bloqueado("campanha sem trilha escolhida na etapa 6 — nada para tocar")
    try:
        _semente_longa(page, ctx)
        estado = ("() => { const a = document.getElementById('edMusic'); return {existe: !!a,"
                  " no_palco: !!(a && a.parentElement && a.parentElement.id === 'edStage'),"
                  " paused: a ? a.paused : null, t: a ? +a.currentTime.toFixed(3) : null} }")
        montado = page.evaluate(estado)
        page.locator("#pcStart").click()
        page.wait_for_timeout(150)
        _tocar(page)
        tocou = True
        try:
            page.wait_for_function(
                "() => { const a = document.getElementById('edMusic');"
                " return !!a && !a.paused && a.currentTime > 0.05 }", timeout=6000)
        except Exception:  # noqa: BLE001 - trilha muda é o achado do caso
            tocou = False
        durante = page.evaluate(estado)
        _parar(page)
        ev = H.evidencia(page, ctx, "C-EDIT-52-musica-toca", full_page=False)
        return H.verifica(montado["existe"] and montado["no_palco"] and tocou,
                          f"<audio id=edMusic> no palco; durante o play {durante}",
                          f"ao montar a tela={montado}; durante o play={durante} — o elemento da trilha "
                          "é descartado pelo re-render do palco e `syncMusic` força currentTime enquanto "
                          "o arquivo carrega, então a música nunca sai do zero", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-53", "SFX ganha <audio> próprio e dispara quando o playhead cruza o seu `at`")
def sfx_toca(page, ctx):
    orig = _tl_api(page, ctx)
    fonte = (orig.get("music") or {}).get("file")
    if not fonte:
        return H.Resultado.bloqueado("sem arquivo de áudio no projeto para usar como SFX")
    try:
        _semente_longa(page, ctx, sfx=[{"file": fonte, "at": 0.8, "gain": -6}])
        estado = ("() => { const a = document.querySelector('#edStage audio[data-sfx]');"
                  " return {elementos: document.querySelectorAll('#edStage audio[data-sfx]').length,"
                  " paused: a ? a.paused : null, t: a ? +a.currentTime.toFixed(3) : null,"
                  " vol: a ? +a.volume.toFixed(3) : null} }")
        montado = page.evaluate(estado)
        page.locator("#pcStart").click()
        page.wait_for_timeout(150)
        antes = page.evaluate(estado)
        _tocar(page)
        disparou = True
        try:
            page.wait_for_function(
                "() => { const a = document.querySelector('#edStage audio[data-sfx]');"
                " return !!a && a.currentTime > 0 }", timeout=8000)
        except Exception:  # noqa: BLE001 - SFX mudo é o achado do caso
            disparou = False
        durante = page.evaluate(estado)
        _parar(page)
        ev = H.evidencia(page, ctx, "C-EDIT-53-sfx-toca", full_page=False)
        # ganho -6 dB ≈ 0.501 do volume global (80%) → ~0.40
        ganho_ok = durante["vol"] is not None and abs(durante["vol"] - 0.8 * 0.501) < 0.05
        return H.verifica(montado["elementos"] == 1 and antes["paused"] is True and disparou and ganho_ok,
                          f"1 <audio data-sfx> no palco; ao cruzar 0.8 s {durante}",
                          f"ao montar={montado} antes do play={antes} durante={durante} — o editor não "
                          "cria elemento de áudio para `timeline.sfx`, então os efeitos nunca soam", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-54", "elemento do painel guarda o id da forma e o preview desenha a forma (não um caractere)")
def elemento_forma(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _painel(page, "elements")
        page.locator("#edPanel .ved-row[data-el='circle']").click()
        ok, _ = _esperar_disco(page, ctx, lambda x: len(_track(x, "v2").get("items") or []) == 1)
        page.reload()
        H.esperar_tela(page)
        tl = _tl_api(page, ctx)
        it = (_track(tl, "v2").get("items") or [{}])[0]
        camada = page.locator("#edStage .ved-layer.overlay")
        classes = (camada.first.get_attribute("class") or "") if camada.count() else ""
        texto = (camada.first.text_content() or "").strip() if camada.count() else ""
        caixa = camada.first.bounding_box() if camada.count() else None
        ev = H.evidencia(page, ctx, "C-EDIT-54-elemento-forma", full_page=False)
        desenhou = "shape-circle" in classes and not texto and bool(caixa) and caixa["width"] > 8
        return H.verifica(ok and it.get("shape") == "circle" and desenhou,
                          f"shape='{it.get('shape')}' classes='{classes}' caixa={caixa}",
                          f"item no disco={it} (esperado shape='circle'); camada no preview classes="
                          f"'{classes}' texto='{texto}' caixa={caixa} — o painel grava o glifo em vez do "
                          "id da forma e o preview escreve o caractere no lugar de desenhar a forma", ev)
    finally:
        _restaurar(page, ctx, orig)


@caso("C-EDIT-55", "vídeo do painel Mídia vai para a faixa VÍDEO 2 (overlay com src de vídeo)")
def video_na_v2(page, ctx):
    orig = _tl_api(page, ctx)
    try:
        _painel(page, "media")
        botao = page.locator("#mList .ved-mcard[data-cid] .mv2")
        if not botao.count():
            return H.Resultado.falha("nenhum card de vídeo do painel Mídia oferece enviar para VÍDEO 2 "
                                     "— `addMediaItem` manda todo vídeo para o backbone (VÍDEO 1)")
        botao.first.click()
        ok, tl = _esperar_disco(page, ctx, lambda x: len(_track(x, "v2").get("items") or []) == 1)
        it = (_track(tl, "v2").get("items") or [{}])[0]
        na_timeline = page.locator(".ved-lane[data-tid='v2'] .ved-clip[data-uid]").count()
        no_preview = page.locator("#edStage .ved-layer.overlay video").count()
        ev = H.evidencia(page, ctx, "C-EDIT-55-video-v2", full_page=False)
        return H.verifica(ok and str(it.get("src", "")).endswith(".mp4") and na_timeline == 1
                          and no_preview == 1 and len(tl.get("clips") or []) == len(orig["clips"]),
                          f"overlay de vídeo na v2: src={it.get('src')} ({it.get('start')}→{it.get('end')})",
                          f"item no disco={it}; faixa v2 na timeline={na_timeline} <video> no preview="
                          f"{no_preview}; clipes do backbone={len(tl.get('clips') or [])} "
                          f"(esperado {len(orig['clips'])}, o vídeo não pode virar clipe do VÍDEO 1)", ev)
    finally:
        _restaurar(page, ctx, orig)
