"""Casos da etapa 9 — Publicar (`studio/etapas/publish/view.js` + `studio/publish/service.py`).

Publicar é ato humano: a tela só **registra** (vídeo de `export/`, rede, URL, data, nota),
guarda o feedback recebido, marca o checklist de comunidade e lê o portfólio GLOBAL
(`GET /api/portfolio`, ADR-012 — conta projetos distintos com post, não arquivos).
"""
from __future__ import annotations

import json
from datetime import date

from scripts.qa import harness as H

TELA = "publish"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)

#: URLs que só os casos usam — sempre limpas antes e depois (idempotência exigida pelo runner).
URL_CASO = "https://qa.example.com/publish-caso"
URL_NOTA = "https://qa.example.com/publish-nota"
URL_DEL = "https://qa.example.com/publish-remover"
URL_ORFAO = "https://qa.example.com/publish-orfao"


# ---------- helpers locais ----------
class dialogos:  # noqa: N801
    """Responde aos `confirm()` nativos (o Playwright recusa todos por padrão)."""

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


def jsonp(page, ctx, method: str, path: str, body: dict | None = None):
    kw = {"data": json.dumps(body), "headers": {"content-type": "application/json"}} if body is not None else {}
    return H.api(page, ctx, method, path, **kw)


def posts(page, ctx, pid: str) -> list[dict]:
    return jsonp(page, ctx, "get", f"/api/projects/{pid}/publish/log").json()["posts"]


def limpar(page, ctx, pid: str, *urls: str) -> None:
    """Apaga os registros criados pelos casos (nunca toca nos posts do seed)."""
    for p in posts(page, ctx, pid):
        if p["url"] in urls:
            jsonp(page, ctx, "delete", f"/api/projects/{pid}/publish/log/{p['id']}")


def registrar(page, url: str, rede: str = "instagram", nota: str = "", video: str | None = None) -> None:
    """Preenche o formulário do painel 01 e clica em 'Registrar publicação'."""
    if video is not None:
        page.locator("#pubVideo").select_option(video)
    page.locator("#pubNetwork").fill(rede)
    page.locator("#pubUrl").fill(url)
    page.locator("#pubNote").fill(nota)
    page.locator("#btnPubAdd").click()


def recarregar(page) -> None:
    page.reload()
    H.esperar_tela(page)


# ---------- painel 01: formulário ----------
@caso("C-PUBLISH-01", "select de vídeo lista os exports de /publish/exports")
def select_exports(page, ctx):
    recarregar(page)
    files = jsonp(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/publish/exports").json()["files"]
    opcoes = page.locator("#pubVideo option").evaluate_all("els => els.map(e => e.value)")
    ev = H.evidencia(page, ctx, "publish-select")
    return H.verifica(opcoes == [f["file"] for f in files] and len(opcoes) > 0,
                      f"select com {len(opcoes)} exports",
                      f"select={opcoes} api={[f['file'] for f in files]}", ev)


@caso("C-PUBLISH-02", "campo de data já vem com a data de hoje")
def data_hoje(page, ctx):
    valor = page.locator("#pubDate").input_value()
    return H.verifica(valor == date.today().isoformat(), f"data={valor}",
                      f"#pubDate='{valor}' esperado '{date.today().isoformat()}'")


@caso("C-PUBLISH-03", "datalist de redes sugere as redes da aula, inclusive a comunidade ABRAhub")
def datalist_redes(page, ctx):
    vals = page.locator("#pubNetworks option").evaluate_all("els => els.map(e => e.value)")
    lista = page.locator("#pubNetwork").get_attribute("list")
    return H.verifica(lista == "pubNetworks" and "comunidade ABRAhub" in vals and "instagram" in vals,
                      f"sugestões={vals}", f"list='{lista}' opções={vals}")


@caso("C-PUBLISH-04", "sem rede: toast pedindo a rede e nada gravado no log")
def sem_rede(page, ctx):
    antes = len(posts(page, ctx, ctx.pid_cheio))
    registrar(page, URL_CASO, rede="")
    t = H.esperar_toast(page, "rede")
    depois = len(posts(page, ctx, ctx.pid_cheio))
    ev = H.evidencia(page, ctx, "publish-sem-rede", full_page=False)
    return H.verifica(bool(t) and depois == antes, f"toast='{t}'",
                      f"toast='{t}' posts {antes}→{depois}", ev)


@caso("C-PUBLISH-05", "URL sem http/https: toast explicando o formato e nada gravado")
def url_invalida(page, ctx):
    antes = len(posts(page, ctx, ctx.pid_cheio))
    registrar(page, "instagram.com/reel/abc")
    t = H.esperar_toast(page, "http")
    depois = len(posts(page, ctx, ctx.pid_cheio))
    return H.verifica(bool(t) and depois == antes, f"toast='{t}'", f"toast='{t}' posts {antes}→{depois}")


@caso("C-PUBLISH-06", "URL já registrada: toast de duplicidade e log intacto")
def url_duplicada(page, ctx):
    existentes = posts(page, ctx, ctx.pid_cheio)
    if not existentes:
        return H.Resultado.bloqueado("seed cheio sem publicações registradas")
    antes = len(existentes)
    registrar(page, existentes[0]["url"], rede="tiktok")
    t = H.esperar_toast(page, "já registrada")
    depois = len(posts(page, ctx, ctx.pid_cheio))
    return H.verifica(bool(t) and depois == antes, f"toast='{t}'", f"toast='{t}' posts {antes}→{depois}")


@caso("C-PUBLISH-07", "registrar publicação: linha na lista, entrada em publish/log.json e portfolio.md regravado")
def registrar_ok(page, ctx):
    limpar(page, ctx, ctx.pid_cheio, URL_CASO)
    recarregar(page)
    try:
        antes = len(posts(page, ctx, ctx.pid_cheio))
        video = page.locator("#pubVideo option").first.get_attribute("value")
        registrar(page, URL_CASO, rede="tiktok", nota="teste de QA", video=video)
        t = H.esperar_toast(page, "registrada")
        page.wait_for_timeout(600)
        novos = posts(page, ctx, ctx.pid_cheio)
        gravado = next((p for p in novos if p["url"] == URL_CASO), None)
        linhas = page.locator("#pubLog .pub-row").count()
        campos_limpos = page.locator("#pubUrl").input_value() == "" and page.locator("#pubNote").input_value() == ""
        md = (ctx.projeto(ctx.pid_cheio) / "publish" / "portfolio.md").read_text()
        ev = H.evidencia(page, ctx, "publish-registrado")
        ok = (gravado is not None and gravado["video"] == video and gravado["network"] == "tiktok"
              and gravado["note"] == "teste de QA" and linhas == antes + 1 and campos_limpos
              and URL_CASO in md and bool(t))
        return H.verifica(ok, f"post {gravado and gravado['id']} gravado e listado",
                          f"gravado={gravado} linhas={linhas} (antes {antes}) campos limpos={campos_limpos} "
                          f"url no portfolio.md={URL_CASO in md} toast='{t}'", ev)
    finally:
        limpar(page, ctx, ctx.pid_cheio, URL_CASO)


@caso("C-PUBLISH-08", "cada linha traz chip da rede, URL encurtada e data/arquivo no title")
def lista_espelha_log(page, ctx):
    recarregar(page)   # a SPA não remonta ao repetir o mesmo hash: a lista tem de vir do estado atual
    log = posts(page, ctx, ctx.pid_cheio)
    if not log:
        return H.Resultado.bloqueado("seed cheio sem publicações registradas")
    linhas = page.locator("#pubLog .pub-row").evaluate_all(
        "els => els.map(e => ({id: e.dataset.id, rede: e.querySelector('.chip').textContent.trim(),"
        " href: e.querySelector('a.url').getAttribute('href'), title: e.getAttribute('title')}))")
    esperado_ids = [p["id"] for p in log]
    por_id = {p["id"]: p for p in log}
    ok = [x["id"] for x in linhas] == esperado_ids and all(
        x["rede"] == por_id[x["id"]]["network"] and x["href"] == por_id[x["id"]]["url"]
        and por_id[x["id"]]["posted_at"] in (x["title"] or "") and por_id[x["id"]]["video"] in (x["title"] or "")
        for x in linhas)
    ev = H.evidencia(page, ctx, "publish-lista")
    return H.verifica(ok, f"{len(linhas)} linhas conferem com o log", f"linhas={linhas} log={log}", ev)


@caso("C-PUBLISH-09", "anotar feedback: Enter grava em log.json e a linha passa a mostrar a nota")
def nota_salva(page, ctx):
    limpar(page, ctx, ctx.pid_cheio, URL_NOTA)
    recarregar(page)
    try:
        video = page.locator("#pubVideo option").first.get_attribute("value")
        registrar(page, URL_NOTA, rede="youtube", video=video)
        H.esperar_toast(page, "registrada")
        page.wait_for_timeout(600)
        pid_post = next(p["id"] for p in posts(page, ctx, ctx.pid_cheio) if p["url"] == URL_NOTA)
        page.locator(f"#pubLog .pub-row[data-id='{pid_post}'] .nt").click()
        campo = page.locator(f"#pubLog .pub-row[data-id='{pid_post}'] input.nt-edit")
        campo.wait_for()
        campo.fill("gostaram do corte")
        campo.press("Enter")
        t = H.esperar_toast(page, "Feedback salvo")
        page.wait_for_timeout(600)
        gravado = next(p for p in posts(page, ctx, ctx.pid_cheio) if p["url"] == URL_NOTA)
        texto = (page.locator(f"#pubLog .pub-row[data-id='{pid_post}'] .nt").text_content() or "").strip()
        ev = H.evidencia(page, ctx, "publish-nota")
        return H.verifica(gravado["feedback"] == "gostaram do corte" and "gostaram do corte" in texto and bool(t),
                          f"feedback gravado e exibido ('{texto}')",
                          f"log.feedback='{gravado['feedback']}' linha='{texto}' toast='{t}'", ev)
    finally:
        limpar(page, ctx, ctx.pid_cheio, URL_NOTA)


@caso("C-PUBLISH-10", "anotar feedback: Escape descarta a edição sem gravar")
def nota_escape(page, ctx):
    limpar(page, ctx, ctx.pid_cheio, URL_NOTA)
    recarregar(page)
    try:
        video = page.locator("#pubVideo option").first.get_attribute("value")
        registrar(page, URL_NOTA, rede="youtube", video=video)
        H.esperar_toast(page, "registrada")
        page.wait_for_timeout(600)
        pid_post = next(p["id"] for p in posts(page, ctx, ctx.pid_cheio) if p["url"] == URL_NOTA)
        page.locator(f"#pubLog .pub-row[data-id='{pid_post}'] .nt").click()
        campo = page.locator(f"#pubLog .pub-row[data-id='{pid_post}'] input.nt-edit")
        campo.wait_for()
        campo.fill("texto que não deve ser salvo")
        campo.press("Escape")
        page.wait_for_timeout(800)
        gravado = next(p for p in posts(page, ctx, ctx.pid_cheio) if p["url"] == URL_NOTA)
        aberto = page.locator(f"#pubLog .pub-row[data-id='{pid_post}'] input.nt-edit").count()
        return H.verifica(gravado["feedback"] == "" and aberto == 0, "edição descartada",
                          f"log.feedback='{gravado['feedback']}' campo ainda aberto={aberto}")
    finally:
        limpar(page, ctx, ctx.pid_cheio, URL_NOTA)


@caso("C-PUBLISH-11", "'Remover' com a confirmação recusada mantém o registro")
def remover_cancela(page, ctx):
    limpar(page, ctx, ctx.pid_cheio, URL_DEL)
    recarregar(page)
    try:
        video = page.locator("#pubVideo option").first.get_attribute("value")
        registrar(page, URL_DEL, rede="tiktok", video=video)
        H.esperar_toast(page, "registrada")
        page.wait_for_timeout(600)
        pid_post = next(p["id"] for p in posts(page, ctx, ctx.pid_cheio) if p["url"] == URL_DEL)
        with dialogos(page, aceitar=False) as d:
            page.locator(f"#pubLog .pub-row[data-id='{pid_post}'] button.del").click()
            page.wait_for_timeout(800)
        ainda = any(p["id"] == pid_post for p in posts(page, ctx, ctx.pid_cheio))
        return H.verifica(bool(d.vistos) and ainda, f"confirm='{(d.vistos or [''])[0][:60]}' e o post continua",
                          f"confirms={d.vistos} post ainda existe={ainda}")
    finally:
        limpar(page, ctx, ctx.pid_cheio, URL_DEL)


@caso("C-PUBLISH-12", "'Remover' confirmado faz DELETE, tira a linha da lista e do log.json")
def remover_ok(page, ctx):
    limpar(page, ctx, ctx.pid_cheio, URL_DEL)
    recarregar(page)
    try:
        video = page.locator("#pubVideo option").first.get_attribute("value")
        registrar(page, URL_DEL, rede="tiktok", video=video)
        H.esperar_toast(page, "registrada")
        page.wait_for_timeout(600)
        pid_post = next(p["id"] for p in posts(page, ctx, ctx.pid_cheio) if p["url"] == URL_DEL)
        antes = page.locator("#pubLog .pub-row").count()
        with dialogos(page, aceitar=True):
            page.locator(f"#pubLog .pub-row[data-id='{pid_post}'] button.del").click()
            t = H.esperar_toast(page, "removido")
        page.wait_for_timeout(600)
        restantes = posts(page, ctx, ctx.pid_cheio)
        linhas = page.locator("#pubLog .pub-row").count()
        md = (ctx.projeto(ctx.pid_cheio) / "publish" / "portfolio.md").read_text()
        ev = H.evidencia(page, ctx, "publish-removido")
        ok = (not any(p["id"] == pid_post for p in restantes) and linhas == antes - 1
              and URL_DEL not in md and bool(t))
        return H.verifica(ok, f"post removido; toast='{t}'",
                          f"ainda no log={any(p['id'] == pid_post for p in restantes)} linhas {antes}→{linhas} "
                          f"url ainda no portfolio.md={URL_DEL in md} toast='{t}'", ev)
    finally:
        limpar(page, ctx, ctx.pid_cheio, URL_DEL)


# ---------- painel 02: comunidade e portfólio ----------
@caso("C-PUBLISH-13", "chip do painel 02 conta publicações e o checklist de comunidade")
def chip_resumo(page, ctx):
    recarregar(page)
    st = jsonp(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/publish/portfolio").json()
    txt = (page.locator("#pubComChip").text_content() or "").strip()
    c = st["community"]
    esperado = f"{st['count']} {'publicação' if st['count'] == 1 else 'publicações'} · comunidade {c['done']}/{c['total']}"
    return H.verifica(txt == esperado, f"chip='{txt}'", f"chip='{txt}' esperado='{esperado}'")


@caso("C-PUBLISH-14", "marcar 'postei na comunidade' grava publish/community.json e atualiza o chip")
def comunidade_marca(page, ctx):
    original = jsonp(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/publish/community").json()
    try:
        jsonp(page, ctx, "post", f"/api/projects/{ctx.pid_cheio}/publish/community", {"posted": False})
        recarregar(page)
        page.locator("#pubCommunity label:has(input[data-com='posted'])").click()
        page.wait_for_timeout(900)
        arquivo = ctx.projeto(ctx.pid_cheio) / "publish" / "community.json"
        gravado = json.loads(arquivo.read_text()) if arquivo.exists() else {}
        chip = (page.locator("#pubComChip").text_content() or "").strip()
        marcado = page.locator("#pubCommunity input[data-com='posted']").is_checked()
        ev = H.evidencia(page, ctx, "publish-comunidade")
        return H.verifica(gravado.get("posted") is True and marcado and "comunidade 1/3" in chip,
                          f"community.json={gravado} chip='{chip}'",
                          f"arquivo={gravado} checkbox={marcado} chip='{chip}'", ev)
    finally:
        jsonp(page, ctx, "post", f"/api/projects/{ctx.pid_cheio}/publish/community",
              {k: original[k] for k in ("posted", "commented", "feedback")})


@caso("C-PUBLISH-15", "desmarcar um item da comunidade volta o arquivo para false")
def comunidade_desmarca(page, ctx):
    original = jsonp(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/publish/community").json()
    try:
        jsonp(page, ctx, "post", f"/api/projects/{ctx.pid_cheio}/publish/community", {"commented": True})
        recarregar(page)
        antes = page.locator("#pubCommunity input[data-com='commented']").is_checked()
        page.locator("#pubCommunity label:has(input[data-com='commented'])").click()
        page.wait_for_timeout(900)
        depois = jsonp(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/publish/community").json()
        return H.verifica(antes and depois["commented"] is False, "item desmarcado e persistido",
                          f"checkbox antes={antes} api depois={depois}")
    finally:
        jsonp(page, ctx, "post", f"/api/projects/{ctx.pid_cheio}/publish/community",
              {k: original[k] for k in ("posted", "commented", "feedback")})


@caso("C-PUBLISH-16", "os três checkboxes data-com refletem o arquivo depois de recarregar a tela")
def comunidade_persiste(page, ctx):
    original = jsonp(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/publish/community").json()
    try:
        jsonp(page, ctx, "post", f"/api/projects/{ctx.pid_cheio}/publish/community",
              {"posted": True, "commented": False, "feedback": True})
        recarregar(page)
        estados = page.locator("#pubCommunity input[data-com]").evaluate_all(
            "els => Object.fromEntries(els.map(e => [e.dataset.com, e.checked]))")
        chip = (page.locator("#pubComChip").text_content() or "").strip()
        return H.verifica(estados == {"posted": True, "commented": False, "feedback": True}
                          and "comunidade 2/3" in chip, f"checkboxes={estados} chip='{chip}'",
                          f"checkboxes={estados} chip='{chip}'")
    finally:
        jsonp(page, ctx, "post", f"/api/projects/{ctx.pid_cheio}/publish/community",
              {k: original[k] for k in ("posted", "commented", "feedback")})


@caso("C-PUBLISH-17", "portfólio global conta PROJETOS distintos com post (ADR-012), não arquivos")
def portfolio_global(page, ctx):
    glob = H.api(page, ctx, "get", "/api/portfolio").json()
    local = jsonp(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/publish/portfolio").json()
    projetos_com_post = len(glob["projects"])
    ev = H.evidencia(page, ctx, "publish-portfolio")
    ok = (glob["distinct_videos"] == projetos_com_post and local["distinct_videos"] == glob["distinct_videos"]
          and local["videos"] <= local["count"] and glob["goal"] == 4
          and glob["ready"] == (projetos_com_post >= 4))
    return H.verifica(ok, f"global={glob['distinct_videos']} obras / {glob['posts']} posts; "
                          f"neste projeto {local['videos']} arquivos em {local['count']} posts",
                      f"global={ {k: glob[k] for k in ('distinct_videos', 'posts', 'goal', 'ready')} } "
                      f"projetos={projetos_com_post} local={ {k: local[k] for k in ('count', 'videos', 'distinct_videos')} }", ev)


# ---------- estado vazio ----------
@caso("C-PUBLISH-18", "campanha sem export: select avisa e a lista mostra o empty-state", pid="vazio")
def vazio(page, ctx):
    opcoes = page.locator("#pubVideo option").evaluate_all("els => els.map(e => e.textContent.trim())")
    vazio_txt = (page.locator("#pubLog .empty").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "publish-vazio")
    return H.verifica(opcoes == ["nenhum export disponível"] and "Nenhuma publicação registrada" in vazio_txt,
                      f"select='{opcoes}' lista='{vazio_txt[:60]}'",
                      f"select={opcoes} empty='{vazio_txt}'", ev)


@caso("C-PUBLISH-19", "campanha sem export: registrar mostra o erro amigável do backend", pid="vazio")
def vazio_registrar(page, ctx):
    antes = len(posts(page, ctx, ctx.pid_vazio))
    page.locator("#pubNetwork").fill("instagram")
    page.locator("#pubUrl").fill(URL_CASO)
    page.locator("#btnPubAdd").click()
    t = H.esperar_toast(page)
    depois = len(posts(page, ctx, ctx.pid_vazio))
    ev = H.evidencia(page, ctx, "publish-vazio-erro", full_page=False)
    return H.verifica(bool(t) and "export" in t.lower() and depois == antes, f"toast='{t}'",
                      f"toast='{t}' posts {antes}→{depois}", ev)


@caso("C-PUBLISH-21", "todo campo do formulário tem rótulo acessível (label, aria-label ou placeholder)")
def campos_com_rotulo(page, ctx):
    recarregar(page)
    sem_rotulo = page.locator("#main input:not([type=hidden]), #main select").evaluate_all(
        "els => els.filter(e => !(e.id && document.querySelector(`label[for=\"${CSS.escape(e.id)}\"]`))"
        " && !e.closest('label') && !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby')"
        " && !e.getAttribute('placeholder') && !e.getAttribute('title'))"
        ".map(e => e.tagName.toLowerCase() + '#' + e.id)")
    ev = H.evidencia(page, ctx, "publish-rotulos")
    return H.verifica(not sem_rotulo, "todos os campos têm rótulo",
                      f"campos sem rótulo acessível: {sem_rotulo}", ev)


@caso("C-PUBLISH-20", "arquivo que saiu de export/ vira aviso no title da linha", pid="vazio")
def orfao(page, ctx):
    root = ctx.projeto(ctx.pid_vazio)
    fonte = ctx.projeto(ctx.pid_cheio) / "export" / "9x16.mp4"
    alvo = root / "export" / "orfao.mp4"
    outro = root / "export" / "ancora.mp4"
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(fonte.read_bytes())
        outro.write_bytes(fonte.read_bytes())     # sem outro export, `renderLog` não marca o órfão
        r = jsonp(page, ctx, "post", f"/api/projects/{ctx.pid_vazio}/publish/log",
                  {"video": "export/orfao.mp4", "network": "instagram", "url": URL_ORFAO, "note": ""})
        if r.status not in (200, 201):
            return H.Resultado.falha(f"não foi possível preparar o caso: POST /publish/log → {r.status} {r.text()[:120]}")
        alvo.unlink()
        recarregar(page)
        linha = page.locator("#pubLog .pub-row").first
        title = linha.get_attribute("title") or ""
        ev = H.evidencia(page, ctx, "publish-orfao")
        return H.verifica("não está mais em export/" in title, f"title='{title}'",
                          f"title='{title}' (esperado avisar que o arquivo saiu de export/)", ev)
    finally:
        limpar(page, ctx, ctx.pid_vazio, URL_ORFAO)
        alvo.unlink(missing_ok=True)
        outro.unlink(missing_ok=True)
