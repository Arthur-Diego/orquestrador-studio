"""Casos da etapa 8 — Export e QA (`studio/etapas/export/view.js` + `studio/export/service.py`).

A tela tem três comandos de verdade: renderizar um formato, renderizar todos e gerar o QA
técnico. O preview do corte central sai do clique na própria caixa da proporção (`.ex-box`).
O `reframe` do CLI (alternativa paga) continua nas rotas, mas a wave 4 tirou o botão da tela —
os casos que o exercitam batem direto na API e registram a lacuna de UI.
"""
from __future__ import annotations

import json

from scripts.qa import harness as H

TELA = "export"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)

FORMATOS = ("16x9", "9x16", "1x1")
PROPORCAO = {"16x9": "16:9", "9x16": "9:16", "1x1": "1:1"}


# ---------- helpers locais (harness.py é compartilhado: nada de helper novo lá) ----------
class dialogos:  # noqa: N801  (usado como context manager, não como classe pública)
    """Responde aos `confirm()` nativos da tela enquanto o bloco estiver aberto.

    Sem isto o Playwright **recusa** todo diálogo por padrão — e a tela cancela a ação.
    """

    def __init__(self, page, aceitar: bool = True) -> None:
        self.page, self.aceitar = page, aceitar
        self.vistos: list[str] = []

    def _handler(self, d) -> None:
        self.vistos.append(d.message)
        d.accept() if self.aceitar else d.dismiss()

    def __enter__(self) -> dialogos:
        self.page.on("dialog", self._handler)
        return self

    def __exit__(self, *exc) -> bool:
        self.page.remove_listener("dialog", self._handler)
        return False


def status(page, ctx, pid: str | None = None) -> dict:
    return H.api(page, ctx, "get", f"/api/projects/{pid or ctx.pid_cheio}/export/status").json()


def esperar_job_parar(page, ctx, pid: str | None = None, timeout_s: int = 120) -> dict:
    return H.esperar_job(ctx, page, f"/api/projects/{pid or ctx.pid_cheio}/export/job", timeout_s)


def esperar_progresso(page, timeout_ms: int = 10_000):
    """Espera o modal de progresso (`ui.progressJob`) aparecer e devolve o locator."""
    page.wait_for_selector(".modal[role=dialog] .prog-steps", timeout=timeout_ms)
    return H.modal(page)


def garantir_formatos(page, ctx) -> None:
    """Rede de segurança: nenhum caso pode deixar o seed cheio sem os três `export/*.mp4`."""
    faltam = [f for f in FORMATOS if not (ctx.projeto(ctx.pid_cheio) / "export" / f"{f}.mp4").exists()]
    if not faltam:
        return
    H.api(page, ctx, "post", f"/api/projects/{ctx.pid_cheio}/export/render",
          data=json.dumps({"formats": faltam}), headers={"content-type": "application/json"})
    esperar_job_parar(page, ctx)


# ---------- painel 01: formatos ----------
@caso("C-EXPORT-01", "um card por formato, com proporção, destino e chip igual ao /export/status")
def cards(page, ctx):
    st = status(page, ctx)
    cards = page.locator("#expFormats .fmt-card")
    dados = cards.evaluate_all(
        "els => els.map(e => ({fmt: e.dataset.fmt, ratio: e.querySelector('.ratio').textContent.trim(),"
        " dest: e.querySelector('.dest').textContent.trim(), chip: e.querySelector('.chip.sm').textContent.trim()}))")
    esperado = [{"fmt": f, "ratio": PROPORCAO[f],
                 "chip": "renderizado" if st["outputs"][f] else "a renderizar"} for f in FORMATOS]
    obtido = [{k: d[k] for k in ("fmt", "ratio", "chip")} for d in dados]
    ev = H.evidencia(page, ctx, "export-cards")
    return H.verifica(obtido == esperado and all(d["dest"] for d in dados),
                      f"{len(dados)} cards conferem com o status",
                      f"cards={dados} esperado={esperado}", ev)


@caso("C-EXPORT-02", "formato já renderizado mostra 'Ver arquivo' com medidas no title")
def ver_arquivo_title(page, ctx):
    st = status(page, ctx)
    fmt = next((f for f in FORMATOS if st["outputs"][f]), None)
    if not fmt:
        return H.Resultado.bloqueado("nenhum formato renderizado no seed cheio")
    btn = page.locator(f"#expFormats .fmt-card[data-fmt='{fmt}'] button.open")
    title = btn.get_attribute("title") or ""
    o = st["outputs"][fmt]
    return H.verifica(btn.count() == 1 and f"export/{fmt}.mp4" in title and f"{o['width']}x{o['height']}" in title,
                      f"title='{title}'",
                      f"botão 'Ver arquivo' count={btn.count()} title='{title}' (esperado conter export/{fmt}.mp4 e medidas)")


@caso("C-EXPORT-03", "'Ver arquivo' abre /files/<pid>/export/<fmt>.mp4 em nova aba")
def ver_arquivo_abre(page, ctx):
    st = status(page, ctx)
    fmt = next((f for f in FORMATOS if st["outputs"][f]), None)
    if not fmt:
        return H.Resultado.bloqueado("nenhum formato renderizado no seed cheio")
    # `window.open` é substituído para não abrir uma aba de vídeo (e não depender do player).
    page.evaluate("() => { window.__abertos = []; window.open = (u) => { window.__abertos.push(u); return null; }; }")
    page.locator(f"#expFormats .fmt-card[data-fmt='{fmt}'] button.open").click()
    page.wait_for_timeout(300)
    abertos = page.evaluate("() => window.__abertos || []")
    esperado = f"/files/{ctx.pid_cheio}/export/{fmt}.mp4"
    return H.verifica(abertos == [esperado], f"abriu {esperado}", f"window.open recebeu {abertos}, esperado [{esperado}]")


@caso("C-EXPORT-04", "'Renderizar todos' habilitado e com as medidas do master no title")
def render_all_habilitado(page, ctx):
    st = status(page, ctx)
    btn = page.locator("#btnRenderAll")
    title = btn.get_attribute("title") or ""
    m = st["master"]
    ok = btn.is_enabled() and f"{m['width']}x{m['height']}" in title and "master.mp4" in title
    return H.verifica(ok, f"habilitado, title='{title}'",
                      f"enabled={btn.is_enabled()} title='{title}' master={m['width']}x{m['height']}")


@caso("C-EXPORT-05", "chips de bloqueio ficam ocultos quando há ffmpeg e master")
def chips_ocultos(page, ctx):
    st = status(page, ctx)
    ffm = page.locator("#expFfmpeg")
    mst = page.locator("#expMaster")
    ok = st["ffmpeg"] and st["master"]["exists"] and not ffm.is_visible() and not mst.is_visible()
    return H.verifica(ok, "nenhum chip de falta visível",
                      f"ffmpeg={st['ffmpeg']} master={st['master']['exists']} "
                      f"chipFfmpeg visível={ffm.is_visible()} chipMaster visível={mst.is_visible()}")


@caso("C-EXPORT-06", "clique na caixa da proporção gera o preview do corte central em disco")
def preview_corte(page, ctx):
    fmt = "9x16"
    alvo = ctx.projeto(ctx.pid_cheio) / "export" / "previews" / f"{fmt}.jpg"
    alvo.unlink(missing_ok=True)
    page.reload()
    H.esperar_tela(page)
    page.locator(f"#expFormats .ex-box[data-fmt='{fmt}']").click()
    try:
        page.wait_for_selector(f"#expFormats .fmt-card[data-fmt='{fmt}'] .ex-box img", timeout=30_000)
    except Exception:  # noqa: BLE001
        return H.Resultado.falha(f"preview não apareceu na caixa {fmt} (arquivo em disco? {alvo.exists()})",
                                 H.evidencia(page, ctx, "export-preview-ausente"))
    st = status(page, ctx)
    ev = H.evidencia(page, ctx, "export-preview")
    return H.verifica(alvo.exists() and st["previews"].get(fmt) == f"export/previews/{fmt}.jpg",
                      f"export/previews/{fmt}.jpg gerado",
                      f"arquivo={alvo.exists()} previews={st['previews']}", ev)


@caso("C-EXPORT-07", "renderizar um formato faltante: modal de progresso, log real e arquivo em disco")
def render_um(page, ctx):
    fmt = "1x1"
    dest = ctx.projeto(ctx.pid_cheio) / "export" / f"{fmt}.mp4"
    try:
        dest.unlink(missing_ok=True)
        page.reload()
        H.esperar_tela(page)
        btn = page.locator(f"#expFormats .fmt-card[data-fmt='{fmt}'] button.render")
        if not btn.count():
            return H.Resultado.falha(f"card {fmt} não ofereceu o botão 'Renderizar' com o arquivo ausente",
                                     H.evidencia(page, ctx, "export-render-sem-botao"))
        btn.click()
        m = esperar_progresso(page)
        fechavel = m.locator(".modal-close").is_enabled()
        ev = H.evidencia(page, ctx, "export-render-modal", full_page=False)
        sumiu = H.esperar_modal_sumir(page, 120_000)
        job = esperar_job_parar(page, ctx)
        passos = job.get("log") or []
        chip = (page.locator(f"#expFormats .fmt-card[data-fmt='{fmt}'] .chip.sm").text_content() or "").strip()
        return H.verifica(dest.exists() and not fechavel and sumiu and job.get("state") == "done"
                          and any(fmt in str(p) for p in passos) and chip == "renderizado",
                          f"{fmt}.mp4 gerado; log={passos}",
                          f"arquivo={dest.exists()} close habilitado durante o job={fechavel} modal sumiu={sumiu} "
                          f"job={job.get('state')} log={passos} chip='{chip}'", ev)
    finally:
        garantir_formatos(page, ctx)


@caso("C-EXPORT-08", "'Renderizar todos' com arquivos existentes pede confirmação; cancelar não mexe no disco")
def render_all_cancela(page, ctx):
    garantir_formatos(page, ctx)
    page.reload()
    H.esperar_tela(page)
    antes = {f: (ctx.projeto(ctx.pid_cheio) / "export" / f"{f}.mp4").stat().st_mtime for f in FORMATOS}
    with dialogos(page, aceitar=False) as d:
        page.locator("#btnRenderAll").click()
        page.wait_for_timeout(1500)
    depois = {f: (ctx.projeto(ctx.pid_cheio) / "export" / f"{f}.mp4").stat().st_mtime for f in FORMATOS}
    modal_aberto = page.locator(".modal[role=dialog]").count() > 0
    return H.verifica(bool(d.vistos) and antes == depois and not modal_aberto,
                      f"confirm='{(d.vistos or [''])[0][:60]}' e nada foi regravado",
                      f"confirms={d.vistos} mtimes iguais={antes == depois} modal aberto={modal_aberto}")


@caso("C-EXPORT-09", "'Renderizar todos' confirmado regrava os três formatos com um passo por formato")
def render_all(page, ctx):
    try:
        antes = {f: (ctx.projeto(ctx.pid_cheio) / "export" / f"{f}.mp4").stat().st_mtime for f in FORMATOS}
        with dialogos(page, aceitar=True):
            page.locator("#btnRenderAll").click()
            m = esperar_progresso(page)
            titulo = (m.locator(".modal-head h3").text_content() or "").strip()
            ev = H.evidencia(page, ctx, "export-render-all", full_page=False)
            sumiu = H.esperar_modal_sumir(page, 180_000)
        job = esperar_job_parar(page, ctx, timeout_s=180)
        passos = [str(x) for x in (job.get("log") or [])]
        depois = {f: (ctx.projeto(ctx.pid_cheio) / "export" / f"{f}.mp4").stat().st_mtime for f in FORMATOS}
        cobertos = all(any(f in p for p in passos) for f in FORMATOS)
        return H.verifica(sumiu and job.get("state") == "done" and cobertos and depois != antes,
                          f"3 formatos regravados; título='{titulo}'",
                          f"modal sumiu={sumiu} job={job.get('state')} log={passos} "
                          f"mtimes mudaram={depois != antes} título='{titulo}'", ev)
    finally:
        garantir_formatos(page, ctx)


@caso("C-EXPORT-10", "#expLog e a barra de progresso ficam escondidos quando não há job em erro")
def log_escondido(page, ctx):
    job = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/export/job").json()
    log_vis = page.locator("#expLog").is_visible()
    prog_vis = page.locator("#expProgress").is_visible()
    return H.verifica(job.get("state") != "error" and not log_vis and not prog_vis,
                      f"job={job.get('state')}, log e barra ocultos",
                      f"job={job.get('state')} #expLog visível={log_vis} #expProgress visível={prog_vis}")


# ---------- painel 02: QA técnico ----------
@caso("C-EXPORT-11", "'Gerar QA' grava export/qa_report.md e desenha o grid de checks")
def qa(page, ctx):
    alvo = ctx.projeto(ctx.pid_cheio) / "export" / "qa_report.md"
    alvo.unlink(missing_ok=True)
    page.reload()
    H.esperar_tela(page)
    page.locator("#btnQa").click()
    t = H.esperar_toast(page, "QA gerado")
    page.wait_for_timeout(600)
    itens = page.locator("#expQa .checks.qa .it").count()
    st = status(page, ctx)
    checks = (st["outputs"].get("qa_report") or {}).get("checks") or []
    ev = H.evidencia(page, ctx, "export-qa")
    return H.verifica(alvo.exists() and itens == len(checks) and itens > 0 and bool(t),
                      f"qa_report.md gerado, {itens} checks, toast='{t}'",
                      f"arquivo={alvo.exists()} itens no grid={itens} checks na API={len(checks)} toast='{t}'", ev)


@caso("C-EXPORT-12", "grid do QA persiste depois de recarregar a tela (vem do status, não do POST)")
def qa_persiste(page, ctx):
    st = status(page, ctx)
    if not st["outputs"].get("qa_report"):
        H.api(page, ctx, "post", f"/api/projects/{ctx.pid_cheio}/export/qa")
    page.reload()
    H.esperar_tela(page)
    st = status(page, ctx)
    checks = (st["outputs"].get("qa_report") or {}).get("checks") or []
    itens = page.locator("#expQa .checks.qa .it").count()
    return H.verifica(itens == len(checks) and itens > 0, f"{itens} checks após reload",
                      f"grid={itens} checks no status={len(checks)}")


@caso("C-EXPORT-13", "cada check do grid usa a marca do seu tipo (✓ ok · ! atenção · ✕ falha)")
def qa_marcas(page, ctx):
    st = status(page, ctx)
    checks = (st["outputs"].get("qa_report") or {}).get("checks") or []
    if not checks:
        return H.Resultado.bloqueado("QA ainda não gerado neste projeto")
    esperado = [{"ok": "✓", "fail": "✕"}.get(c["kind"], "!") for c in checks]
    obtido = [(x or "").strip() for x in page.locator("#expQa .it .mark").all_text_contents()]
    textos = [(x or "").strip() for x in page.locator("#expQa .it .lbl").all_text_contents()]
    ok = obtido == esperado and textos == [c["text"] for c in checks]
    return H.verifica(ok, f"marcas={obtido}", f"marcas={obtido} esperado={esperado}; textos={textos}")


# ---------- estado vazio (gate da etapa 7) ----------
@caso("C-EXPORT-14", "sem master: chip explica a etapa 7 e todos os comandos ficam desabilitados", pid="vazio")
def vazio_bloqueado(page, ctx):
    st = status(page, ctx, ctx.pid_vazio)
    chip = page.locator("#expMaster")
    texto = (chip.text_content() or "").strip()
    render_all = page.locator("#btnRenderAll")
    qa_btn = page.locator("#btnQa")
    renders = page.locator("#expFormats button.render")
    desabilitados = renders.evaluate_all("els => els.every(e => e.disabled)") if renders.count() else False
    ev = H.evidencia(page, ctx, "export-vazio")
    ok = (not st["master"]["exists"] and chip.is_visible() and "etapa 7" in texto
          and render_all.is_disabled() and qa_btn.is_disabled() and renders.count() == 3 and desabilitados)
    return H.verifica(ok, f"bloqueio amigável: '{texto}'",
                      f"master={st['master']['exists']} chip='{texto}' visível={chip.is_visible()} "
                      f"renderAll disabled={render_all.is_disabled()} qa disabled={qa_btn.is_disabled()} "
                      f"botões render={renders.count()} todos disabled={desabilitados}", ev)


@caso("C-EXPORT-15", "sem master: clicar na caixa da proporção não gera preview nem erro na tela", pid="vazio")
def vazio_preview(page, ctx):
    prev_dir = ctx.projeto(ctx.pid_vazio) / "export" / "previews"
    page.locator("#expFormats .ex-box[data-fmt='9x16']").click()
    page.wait_for_timeout(1200)
    gerados = H.arquivos(prev_dir) if prev_dir.exists() else []
    t = H.toast(page)
    return H.verifica(not gerados and not t, "clique ignorado (ready() falso), sem toast de erro",
                      f"arquivos em export/previews={gerados} toast='{t}'")


@caso("C-EXPORT-16", "sem master: title do 'Renderizar todos' aponta a etapa 7", pid="vazio")
def vazio_title(page, ctx):
    title = page.locator("#btnRenderAll").get_attribute("title") or ""
    return H.verifica("etapa 7" in title, f"title='{title}'", f"title='{title}' (esperado citar a etapa 7)")


# ---------- reframe via CLI (alternativa paga; sem botão na tela desde a wave 4) ----------
@caso("C-EXPORT-17", "reframe: custo do CLI responde em créditos (fake offline) mas não tem comando na tela")
def reframe_custo(page, ctx):
    r = H.api(page, ctx, "post", f"/api/projects/{ctx.pid_cheio}/export/reframe/cost",
              data=json.dumps({"aspect_ratio": "9:16"}), headers={"content-type": "application/json"})
    body = r.json() if r.ok else {"status": r.status}
    # A wave 4 tirou o botão: nenhum elemento da tela dispara /export/reframe.
    na_tela = page.locator("#main [data-act='reframe'], #main button:has-text('reframe'), #main button:has-text('Reenquadrar')").count()
    return H.verifica(r.ok and isinstance(body.get("credits"), int) and body["credits"] > 0 and na_tela == 0,
                      f"custo={body.get('credits')} créditos; tela não expõe o comando",
                      f"http={r.status} body={body} elementos de reframe na tela={na_tela}")


@caso("C-EXPORT-18", "reframe: proporção inválida responde 422 com mensagem amigável")
def reframe_invalido(page, ctx):
    r = H.api(page, ctx, "post", f"/api/projects/{ctx.pid_cheio}/export/reframe/cost",
              data=json.dumps({"aspect_ratio": "4:3"}), headers={"content-type": "application/json"})
    detalhe = (r.json() or {}).get("detail", "") if r.status == 422 else r.text()
    return H.verifica(r.status == 422 and "proporção inválida" in str(detalhe),
                      f"422 '{detalhe}'", f"http={r.status} detail='{detalhe}'")


@caso("C-EXPORT-19", "reframe sem master responde 404 apontando a etapa 7", pid="vazio")
def reframe_sem_master(page, ctx):
    r = H.api(page, ctx, "post", f"/api/projects/{ctx.pid_vazio}/export/reframe/cost",
              data=json.dumps({"aspect_ratio": "9:16"}), headers={"content-type": "application/json"})
    detalhe = (r.json() or {}).get("detail", "") if r.status == 404 else r.text()
    return H.verifica(r.status == 404 and "etapa 7" in str(detalhe), f"404 '{detalhe}'",
                      f"http={r.status} detail='{detalhe}'")


# ---------- integração com o resto do app ----------
@caso("C-EXPORT-20", "guia da etapa reflete o estado do export depois de gerar o QA")
def guia(page, ctx):
    guide = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/guide").json()
    passo = next((s for s in guide["steps"] if s["id"] == "export"), None)
    if not passo:
        return H.Resultado.falha("etapa export ausente em /guide")
    painel = page.locator("#guide")
    texto = (painel.text_content() or "").strip()
    ev = H.evidencia(page, ctx, "export-guia", full_page=False)
    return H.verifica(painel.count() == 1 and bool(texto) and passo["status"] in ("done", "in_progress"),
                      f"guia renderizado; status={passo['status']}",
                      f"#guide count={painel.count()} texto='{texto[:120]}' status={passo['status']}", ev)


@caso("C-EXPORT-21", "os formatos renderizados aparecem para a etapa 9 em /publish/exports")
def contrato_etapa9(page, ctx):
    garantir_formatos(page, ctx)
    files = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/publish/exports").json()["files"]
    nomes = sorted(f["name"] for f in files)
    esperado = sorted(f"{f}.mp4" for f in FORMATOS)
    return H.verifica(nomes == esperado, f"etapa 9 enxerga {nomes}", f"exports={nomes} esperado={esperado}")
