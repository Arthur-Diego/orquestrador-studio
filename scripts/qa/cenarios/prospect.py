"""Casos da etapa 10 — Prospecção (`studio/etapas/prospect/view.js` + `studio/prospect/service.py`).

Ordem da aula 001: gate de 4 obras publicadas → lead → DM (script literal, sem link) → "marquei
como enviada" → "respondeu" → teaser de 5 a 10 s com música → follow-up → call de 15 min → pitch
ancorado por etapa. O gate é GLOBAL (ADR-012): vale o portfólio inteiro, não o projeto aberto.
"""
from __future__ import annotations

import json

from scripts.qa import harness as H

TELA = "prospect"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)

#: Lead exclusivo dos casos — recriado do zero em cada caso e removido no fim (idempotência).
LEAD_ID = "qaleadteste"
LEAD = {"business": "Padaria QA", "handle": "@qaleadteste", "post_ref": "o pão das 6h",
        "why": "anotação interna do QA", "role": "fã", "segment": "comércios"}


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


def base(ctx, pid: str | None = None) -> str:
    return f"/api/projects/{pid or ctx.pid_cheio}/prospect"


def leads(page, ctx, pid: str | None = None) -> dict:
    return jsonp(page, ctx, "get", f"{base(ctx, pid)}/leads").json()


def apagar_lead(page, ctx, lid: str = LEAD_ID) -> None:
    jsonp(page, ctx, "delete", f"{base(ctx)}/leads/{lid}")


def preparar_lead(page, ctx, estado: str = "new") -> str:
    """Recria o lead do QA via API no estado pedido e recarrega a tela.

    `estado`: "new" | "dm_sent" | "replied". O seed cheio nunca é tocado (o lead é só do caso).
    """
    apagar_lead(page, ctx)
    r = jsonp(page, ctx, "post", f"{base(ctx)}/leads", LEAD)
    if r.status not in (200, 201):
        raise RuntimeError(f"não foi possível criar o lead do caso: {r.status} {r.text()[:160]}")
    if estado in ("dm_sent", "replied"):
        jsonp(page, ctx, "post", f"{base(ctx)}/leads/{LEAD_ID}/sent", {})
    if estado == "replied":
        jsonp(page, ctx, "post", f"{base(ctx)}/leads/{LEAD_ID}/replied", {"replied": True})
    recarregar(page)
    return LEAD_ID


def recarregar(page) -> None:
    page.reload()
    H.esperar_tela(page)


def linha(page, lid: str = LEAD_ID):
    return page.locator(f"#leadList .lead-row[data-id='{lid}']")


def abrir_corpo(page, lid: str = LEAD_ID) -> None:
    """Abre o corpo do lead (o protótipo abre pelo clique na própria linha)."""
    if linha(page, lid).locator(".body").count():
        return
    linha(page, lid).locator(".lead-biz .nm").click()
    linha(page, lid).locator(".body").wait_for()


def liberar_clipboard(page, ctx) -> bool:
    try:
        page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=ctx.base)
        return True
    except Exception:  # noqa: BLE001  (navegador sem suporte: o caso cai no rótulo do botão)
        return False


def clipboard(page) -> str:
    try:
        return page.evaluate("() => navigator.clipboard.readText()") or ""
    except Exception:  # noqa: BLE001
        return ""


# ---------- gate do portfólio ----------
@caso("C-PROSPECT-01", "gate aberto: chip N/4, pipe com um segmento por obra e '+ Novo lead' habilitado")
def gate_aberto(page, ctx):
    recarregar(page)
    g = jsonp(page, ctx, "get", f"{base(ctx)}/gate").json()
    chip = (page.locator("#gateChip").text_content() or "").strip()
    msg = (page.locator("#gateMsg").text_content() or "").strip()
    segmentos = page.locator("#gatePipe .seg, #gatePipe > *").count()
    classe = page.locator("#gatePanel").get_attribute("class") or ""
    novo = page.locator("#btnNewLead")
    ev = H.evidencia(page, ctx, "prospect-gate")
    ok = (chip == f"{g['published']}/{g['required']} obras publicadas" and msg == g["message"]
          and novo.is_enabled() == bool(g["ok"]) and ("warn" in classe) != bool(g["ok"]) and segmentos > 0)
    return H.verifica(ok, f"chip='{chip}' · {segmentos} segmentos · botão habilitado={novo.is_enabled()}",
                      f"chip='{chip}' msg='{msg}' api={ {k: g[k] for k in ('published', 'required', 'ok')} } "
                      f"segmentos={segmentos} classe='{classe}' botão={novo.is_enabled()}", ev)


@caso("C-PROSPECT-02", "gate é GLOBAL (ADR-012): campanha sem publicação mostra o mesmo estado", pid="vazio")
def gate_global(page, ctx):
    g_vazio = jsonp(page, ctx, "get", f"{base(ctx, ctx.pid_vazio)}/gate").json()
    g_cheio = jsonp(page, ctx, "get", f"{base(ctx, ctx.pid_cheio)}/gate").json()
    chip = (page.locator("#gateChip").text_content() or "").strip()
    novo = page.locator("#btnNewLead")
    ev = H.evidencia(page, ctx, "prospect-gate-vazio")
    ok = (g_vazio["published"] == g_cheio["published"] and g_vazio["ok"] == g_cheio["ok"]
          and g_vazio["this_project_published"] is False
          and chip == f"{g_vazio['published']}/{g_vazio['required']} obras publicadas"
          and novo.is_enabled() == bool(g_vazio["ok"]))
    return H.verifica(ok, f"mesmo gate nas duas campanhas ({g_vazio['published']}/{g_vazio['required']})",
                      f"vazio={g_vazio['published']}/{g_vazio['ok']} cheio={g_cheio['published']}/{g_cheio['ok']} "
                      f"this_project_published={g_vazio['this_project_published']} chip='{chip}'", ev)


@caso("C-PROSPECT-03", "portfólio abaixo de 4 obras fecha o gate: '+ Novo lead' desabilitado e formulário escondido")
def gate_fechado(page, ctx):
    glob = H.api(page, ctx, "get", "/api/portfolio").json()
    doador = next((p for p in glob["projects"] if p["project_id"] != ctx.pid_cheio and p["posts"] == 1), None)
    if not doador:
        return H.Resultado.bloqueado("nenhum projeto-irmão com exatamente 1 post para fechar o gate sem risco")
    pid_doador = doador["project_id"]
    post = jsonp(page, ctx, "get", f"/api/projects/{pid_doador}/publish/log").json()["posts"][0]
    try:
        jsonp(page, ctx, "delete", f"/api/projects/{pid_doador}/publish/log/{post['id']}")
        recarregar(page)
        g = jsonp(page, ctx, "get", f"{base(ctx)}/gate").json()
        chip = (page.locator("#gateChip").text_content() or "").strip()
        classe_chip = page.locator("#gateChip").get_attribute("class") or ""
        classe = page.locator("#gatePanel").get_attribute("class") or ""
        novo = page.locator("#btnNewLead")
        title = novo.get_attribute("title") or ""
        escondido = "hidden" in (page.locator("#newLeadPanel").get_attribute("class") or "")
        ev = H.evidencia(page, ctx, "prospect-gate-fechado")
        ok = (g["ok"] is False and chip == f"{g['published']}/4 obras publicadas" and "warn" in classe_chip
              and "warn" in classe and novo.is_disabled() and title == g["message"] and escondido
              and "faltam" in g["message"].lower() or "falta" in g["message"].lower())
        return H.verifica(ok and novo.is_disabled(), f"gate fechado em {g['published']}/4; botão desabilitado",
                          f"gate={g} chip='{chip}' classes='{classe}'/'{classe_chip}' "
                          f"botão disabled={novo.is_disabled()} title='{title}' painel escondido={escondido}", ev)
    finally:
        jsonp(page, ctx, "post", f"/api/projects/{pid_doador}/publish/log",
              {"video": post["video"], "network": post["network"], "url": post["url"],
               "posted_at": post["posted_at"], "note": post["note"]})


@caso("C-PROSPECT-04", "gate fechado recusa a criação de lead no backend (409 com a frase da aula)")
def gate_backend(page, ctx):
    glob = H.api(page, ctx, "get", "/api/portfolio").json()
    doador = next((p for p in glob["projects"] if p["project_id"] != ctx.pid_cheio and p["posts"] == 1), None)
    if not doador:
        return H.Resultado.bloqueado("nenhum projeto-irmão com exatamente 1 post para fechar o gate sem risco")
    pid_doador = doador["project_id"]
    post = jsonp(page, ctx, "get", f"/api/projects/{pid_doador}/publish/log").json()["posts"][0]
    try:
        jsonp(page, ctx, "delete", f"/api/projects/{pid_doador}/publish/log/{post['id']}")
        r = jsonp(page, ctx, "post", f"{base(ctx)}/leads", {**LEAD, "handle": "@qagatefechado"})
        detalhe = (r.json() or {}).get("detail", "") if r.status == 409 else r.text()[:160]
        existe = any(x["id"] == "qagatefechado" for x in leads(page, ctx)["leads"])
        return H.verifica(r.status == 409 and "quatro obras" in str(detalhe) and not existe,
                          f"409 '{detalhe}'", f"http={r.status} detail='{detalhe}' lead criado={existe}")
    finally:
        jsonp(page, ctx, "post", f"/api/projects/{pid_doador}/publish/log",
              {"video": post["video"], "network": post["network"], "url": post["url"],
               "posted_at": post["posted_at"], "note": post["note"]})
        apagar_lead(page, ctx, "qagatefechado")


# ---------- painel 01: leads ----------
@caso("C-PROSPECT-05", "'+ Novo lead' revela o formulário inline e põe o foco no negócio")
def abre_formulario(page, ctx):
    recarregar(page)
    escondido_antes = "hidden" in (page.locator("#newLeadPanel").get_attribute("class") or "")
    page.locator("#btnNewLead").click()
    page.wait_for_timeout(300)
    visivel = page.locator("#newLeadPanel").is_visible()
    focado = page.evaluate("() => document.activeElement && document.activeElement.id")
    ev = H.evidencia(page, ctx, "prospect-form", full_page=False)
    page.locator("#btnNewLead").click()          # o botão alterna: devolve a tela ao estado inicial
    page.wait_for_timeout(200)
    fechou = "hidden" in (page.locator("#newLeadPanel").get_attribute("class") or "")
    return H.verifica(escondido_antes and visivel and focado == "lfBusiness" and fechou,
                      "formulário alterna e foca #lfBusiness",
                      f"escondido antes={escondido_antes} visível={visivel} foco='{focado}' fechou={fechou}", ev)


@caso("C-PROSPECT-06", "campos obrigatórios: submit vazio é barrado e nenhum lead é criado")
def obrigatorios(page, ctx):
    recarregar(page)
    antes = len(leads(page, ctx)["leads"])
    page.locator("#btnNewLead").click()
    page.locator("#leadForm button[type=submit]").click()
    page.wait_for_timeout(600)
    invalidos = page.locator("#leadForm input:invalid").evaluate_all("els => els.map(e => e.id)")
    depois = len(leads(page, ctx)["leads"])
    ev = H.evidencia(page, ctx, "prospect-obrigatorios", full_page=False)
    return H.verifica(sorted(invalidos) == ["lfBusiness", "lfHandle", "lfPostRef"] and depois == antes,
                      f"campos inválidos={invalidos}, nada criado",
                      f"inválidos={invalidos} leads {antes}→{depois}", ev)


@caso("C-PROSPECT-07", "sem o post citado, a API recusa com a frase da aula ('cite um post específico')")
def post_ref_obrigatorio(page, ctx):
    r = jsonp(page, ctx, "post", f"{base(ctx)}/leads", {**LEAD, "handle": "@qasempostref", "post_ref": ""})
    detalhe = (r.json() or {}).get("detail", "") if r.status == 422 else r.text()[:160]
    apagar_lead(page, ctx, "qasempostref")
    campo_obrigatorio = page.locator("#lfPostRef").get_attribute("required") is not None
    return H.verifica(r.status == 422 and "cite um post" in str(detalhe) and campo_obrigatorio,
                      f"422 '{str(detalhe)[:80]}' e #lfPostRef required",
                      f"http={r.status} detail='{detalhe}' #lfPostRef required={campo_obrigatorio}")


@caso("C-PROSPECT-08", "cadastrar lead: linha na lista, DM com o script literal e prospect/leads.json em disco")
def cadastrar(page, ctx):
    apagar_lead(page, ctx)
    recarregar(page)
    try:
        page.locator("#btnNewLead").click()
        page.locator("#lfBusiness").fill(LEAD["business"])
        page.locator("#lfHandle").fill(LEAD["handle"])
        page.locator("#lfPostRef").fill(LEAD["post_ref"])
        page.locator("#lfWhy").fill(LEAD["why"])
        page.locator("#lfSegment").select_option(LEAD["segment"])
        page.locator("#lfRole").select_option("fã")
        page.locator("#leadForm button[type=submit]").click()
        t = H.esperar_toast(page, LEAD["business"])
        linha(page).wait_for()
        page.wait_for_timeout(400)
        arquivo = ctx.projeto(ctx.pid_cheio) / "prospect" / "leads.json"
        gravados = json.loads(arquivo.read_text())
        lead = next((x for x in gravados if x["id"] == LEAD_ID), None)
        dm = (linha(page).locator("pre.script").text_content() or "").strip()
        cabecalho = (linha(page).locator(".lead-biz").text_content() or "")
        escondido = "hidden" in (page.locator("#newLeadPanel").get_attribute("class") or "")
        ev = H.evidencia(page, ctx, "prospect-lead-criado")
        ok = (lead is not None and lead["status"] == "new" and lead["segment"] == LEAD["segment"]
              and "produzo anúncios criativos" in dm and "http" not in dm
              and LEAD["post_ref"] in dm and LEAD["business"] in cabecalho and escondido and bool(t))
        return H.verifica(ok, f"lead {LEAD_ID} criado com a DM da aula",
                          f"disco={lead} dm='{dm[:90]}' cabeçalho='{cabecalho.strip()[:60]}' "
                          f"form escondido={escondido} toast='{t}'", ev)
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-09", "handle repetido: toast de duplicidade e nenhum lead novo")
def handle_duplicado(page, ctx):
    preparar_lead(page, ctx, "new")
    try:
        antes = len(leads(page, ctx)["leads"])
        page.locator("#btnNewLead").click()
        page.locator("#lfBusiness").fill("Outro negócio")
        page.locator("#lfHandle").fill(LEAD["handle"])
        page.locator("#lfPostRef").fill("outro post")
        page.locator("#leadForm button[type=submit]").click()
        t = H.esperar_toast(page, "já cadastrado")
        depois = len(leads(page, ctx)["leads"])
        return H.verifica(bool(t) and depois == antes, f"toast='{t}'", f"toast='{t}' leads {antes}→{depois}")
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-10", "'Gerar DM (script da aula)' abre o corpo do lead com o script e as ações")
def gerar_dm(page, ctx):
    preparar_lead(page, ctx, "new")
    try:
        botao = linha(page).locator(f"button[data-open='{LEAD_ID}']")
        rotulo = (botao.text_content() or "").strip()
        botao.click()
        linha(page).locator(".body").wait_for()
        dm = (linha(page).locator("pre.script").text_content() or "").strip()
        acoes = linha(page).locator(".body button[data-act]").evaluate_all("els => els.map(e => e.dataset.act)")
        ev = H.evidencia(page, ctx, "prospect-dm")
        return H.verifica("Gerar DM" in rotulo and "produzo anúncios criativos" in dm
                          and set(acoes) == {"copy", "sent", "del"},
                          f"corpo aberto com ações {acoes}",
                          f"rótulo='{rotulo}' dm='{dm[:80]}' ações={acoes}", ev)
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-11", "'Copiar DM' põe o script na área de transferência")
def copiar_dm(page, ctx):
    preparar_lead(page, ctx, "new")
    try:
        liberado = liberar_clipboard(page, ctx)
        abrir_corpo(page)
        botao = linha(page).locator("button[data-act='copy']")
        botao.click()
        page.wait_for_timeout(600)
        rotulo = (botao.text_content() or "").strip()
        texto = clipboard(page) if liberado else ""
        esperado = leads(page, ctx)["leads"]
        dm = next(x["dm_text"] for x in esperado if x["id"] == LEAD_ID)
        ok = "copiado" in rotulo and (not liberado or texto == dm)
        return H.verifica(ok, f"botão='{rotulo}' e clipboard com {len(texto)} caracteres",
                          f"rótulo='{rotulo}' clipboard='{texto[:60]}' esperado='{dm[:60]}' (permissão={liberado})")
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-12", "'Marquei como enviada' muda o status para 'DM enviada' e sobe o contador do dia")
def marcar_enviada(page, ctx):
    preparar_lead(page, ctx, "new")
    try:
        antes = leads(page, ctx)["today_sent"]
        abrir_corpo(page)
        linha(page).locator("button[data-act='sent']").click()
        t = H.esperar_toast(page, "DMs hoje")
        page.wait_for_timeout(600)
        d = leads(page, ctx)
        lead = next(x for x in d["leads"] if x["id"] == LEAD_ID)
        chip = (page.locator("#todayChip").text_content() or "").strip()
        estado = (linha(page).locator(".chip.xs").text_content() or "").strip()
        ev = H.evidencia(page, ctx, "prospect-enviada")
        return H.verifica(lead["status"] == "dm_sent" and bool(lead["sent_at"]) and d["today_sent"] == antes + 1
                          and chip == f"{d['today_sent']}/{d['daily_limit']} hoje" and estado == "DM enviada",
                          f"status={lead['status']} chip='{chip}' toast='{t}'",
                          f"status={lead['status']} sent_at={lead['sent_at']} today {antes}→{d['today_sent']} "
                          f"chip='{chip}' estado da linha='{estado}' toast='{t}'", ev)
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-13", "'Marcar respondeu' muda o estado e a ação principal vira 'Gerar teaser 5–10s'")
def marcar_respondeu(page, ctx):
    preparar_lead(page, ctx, "dm_sent")
    try:
        principal = linha(page).locator("button[data-act='replied']")
        principal.click()
        page.wait_for_timeout(900)
        lead = next(x for x in leads(page, ctx)["leads"] if x["id"] == LEAD_ID)
        estado = (linha(page).locator(".chip.xs").text_content() or "").strip()
        proxima = (linha(page).locator("button[data-act='teaser']").first.text_content() or "").strip()
        ev = H.evidencia(page, ctx, "prospect-respondeu")
        return H.verifica(lead["replied"] is True and lead["status"] == "replied" and bool(lead["replied_at"])
                          and estado == "respondeu" and "teaser" in proxima.lower(),
                          f"estado='{estado}', próxima ação='{proxima}'",
                          f"lead={ {k: lead[k] for k in ('status', 'replied', 'replied_at')} } "
                          f"chip='{estado}' próxima='{proxima}'", ev)
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-14", "responder antes de enviar a DM é recusado (422) — a tela nem oferece o caminho")
def responder_sem_enviar(page, ctx):
    preparar_lead(page, ctx, "new")
    try:
        na_tela = linha(page).locator("button[data-act='replied']").count()
        r = jsonp(page, ctx, "post", f"{base(ctx)}/leads/{LEAD_ID}/replied", {"replied": True})
        detalhe = (r.json() or {}).get("detail", "") if r.status == 422 else r.text()[:160]
        lead = next(x for x in leads(page, ctx)["leads"] if x["id"] == LEAD_ID)
        return H.verifica(r.status == 422 and "enviada" in str(detalhe) and lead["replied"] is False and na_tela == 0,
                          f"422 '{detalhe}'",
                          f"http={r.status} detail='{detalhe}' replied={lead['replied']} botão na tela={na_tela}")
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-15", "'Gerar teaser 5–10s': modal de progresso e prospect/teasers/<lead>.mp4 com música")
def teaser(page, ctx):
    preparar_lead(page, ctx, "replied")
    arquivo = ctx.projeto(ctx.pid_cheio) / "prospect" / "teasers" / f"{LEAD_ID}.mp4"
    try:
        arquivo.unlink(missing_ok=True)
        linha(page).locator("button[data-act='teaser']").first.click()
        page.wait_for_selector(".modal[role=dialog] .prog-steps", timeout=15_000)
        fechavel = H.modal(page).locator(".modal-close").is_enabled()
        ev = H.evidencia(page, ctx, "prospect-teaser-modal", full_page=False)
        sumiu = H.esperar_modal_sumir(page, 180_000)
        job = H.esperar_job(ctx, page, f"{base(ctx)}/job", 180)
        page.wait_for_timeout(800)
        lead = next(x for x in leads(page, ctx)["leads"] if x["id"] == LEAD_ID)
        abrir_corpo(page)          # a linha volta fechada depois do job: o player mora no corpo
        video = linha(page).locator(".body video").count()
        ok = (arquivo.exists() and arquivo.stat().st_size > 0 and not fechavel and sumiu
              and job.get("state") == "done" and 5 <= float(job.get("duration") or 0) <= 10
              and lead["teaser"] == f"prospect/teasers/{LEAD_ID}.mp4" and lead["status"] == "teaser_ready"
              and video == 1)
        return H.verifica(ok, f"teaser de {job.get('duration')}s gravado e listado no lead",
                          f"arquivo={arquivo.exists()} close habilitado durante={fechavel} modal sumiu={sumiu} "
                          f"job={job.get('state')}/{job.get('duration')}s lead.teaser={lead['teaser']} "
                          f"status={lead['status']} <video> no corpo={video}", ev)
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-16", "'Refazer teaser' pede confirmação; recusar não regrava o arquivo")
def refazer_teaser_cancela(page, ctx):
    preparar_lead(page, ctx, "replied")
    arquivo = ctx.projeto(ctx.pid_cheio) / "prospect" / "teasers" / f"{LEAD_ID}.mp4"
    try:
        r = jsonp(page, ctx, "post", f"{base(ctx)}/leads/{LEAD_ID}/teaser", {})
        if r.status not in (200, 201, 202):
            return H.Resultado.falha(f"não foi possível preparar o teaser: {r.status} {r.text()[:120]}")
        H.esperar_job(ctx, page, f"{base(ctx)}/job", 180)
        recarregar(page)
        abrir_corpo(page)
        antes = arquivo.stat().st_mtime
        with dialogos(page, aceitar=False) as d:
            linha(page).locator("button[data-act='teaser']").first.click()
            page.wait_for_timeout(1500)
        depois = arquivo.stat().st_mtime
        modal = page.locator(".modal[role=dialog]").count()
        return H.verifica(bool(d.vistos) and antes == depois and modal == 0,
                          f"confirm='{(d.vistos or [''])[0][:60]}' e o teaser não foi refeito",
                          f"confirms={d.vistos} mtime igual={antes == depois} modal aberto={modal}")
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-17", "'Copiar follow-up' copia o texto literal da aula (convite para a call de 15 min)")
def follow_up(page, ctx):
    preparar_lead(page, ctx, "replied")
    try:
        r = jsonp(page, ctx, "post", f"{base(ctx)}/leads/{LEAD_ID}/teaser", {})
        if r.status not in (200, 201, 202):
            return H.Resultado.falha(f"não foi possível preparar o teaser: {r.status} {r.text()[:120]}")
        H.esperar_job(ctx, page, f"{base(ctx)}/job", 180)
        recarregar(page)
        liberado = liberar_clipboard(page, ctx)
        botao = linha(page).locator("button[data-act='copyfollow']")
        if not botao.count():
            return H.Resultado.falha("linha do lead com teaser não ofereceu 'Copiar follow-up'",
                                     H.evidencia(page, ctx, "prospect-followup-ausente"))
        esperado = jsonp(page, ctx, "get", f"{base(ctx)}/leads/{LEAD_ID}/followup").json()["text"]
        botao.click()
        page.wait_for_timeout(600)
        rotulo = (botao.text_content() or "").strip()
        texto = clipboard(page) if liberado else ""
        ok = "copiado" in rotulo and "15 minutinhos" in esperado and (not liberado or texto == esperado)
        return H.verifica(ok, f"follow-up copiado ('{esperado[:50]}…')",
                          f"rótulo='{rotulo}' clipboard='{texto[:60]}' esperado='{esperado[:60]}'")
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-18", "'Registrar call' sem data mostra toast pedindo a data e não grava nada")
def call_sem_data(page, ctx):
    preparar_lead(page, ctx, "replied")
    try:
        abrir_corpo(page)
        linha(page).locator("button[data-act='call']").click()
        t = H.esperar_toast(page, "data da call")
        lead = next(x for x in leads(page, ctx)["leads"] if x["id"] == LEAD_ID)
        return H.verifica(bool(t) and lead["call_at"] is None and lead["status"] == "replied",
                          f"toast='{t}'", f"toast='{t}' call_at={lead['call_at']} status={lead['status']}")
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-19", "'Registrar call' com data e nota grava call_at e muda o estado para 'call agendada'")
def call_agendada(page, ctx):
    preparar_lead(page, ctx, "replied")
    try:
        abrir_corpo(page)
        linha(page).locator(f"input[data-call='{LEAD_ID}']").fill("2026-09-10T15:00")
        linha(page).locator(f"input[data-note='{LEAD_ID}']").fill("call de 15 min")
        linha(page).locator("button[data-act='call']").click()
        page.wait_for_timeout(900)
        lead = next(x for x in leads(page, ctx)["leads"] if x["id"] == LEAD_ID)
        estado = (linha(page).locator(".chip.xs").text_content() or "").strip()
        ev = H.evidencia(page, ctx, "prospect-call")
        return H.verifica(lead["call_at"] == "2026-09-10T15:00:00" and lead["call_note"] == "call de 15 min"
                          and lead["status"] == "call_scheduled" and estado == "call agendada",
                          f"call agendada em {lead['call_at']}",
                          f"lead={ {k: lead[k] for k in ('call_at', 'call_note', 'status')} } chip='{estado}'", ev)
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-20", "marcar 'feita' junto com a data registra a call como concluída")
def call_feita(page, ctx):
    preparar_lead(page, ctx, "replied")
    try:
        abrir_corpo(page)
        linha(page).locator(f"input[data-call='{LEAD_ID}']").fill("2026-09-11T09:30")
        linha(page).locator(f"label:has(input[data-done='{LEAD_ID}'])").click()
        linha(page).locator("button[data-act='call']").click()
        page.wait_for_timeout(900)
        lead = next(x for x in leads(page, ctx)["leads"] if x["id"] == LEAD_ID)
        estado = (linha(page).locator(".chip.xs").text_content() or "").strip()
        return H.verifica(lead["status"] == "call_done" and estado == "call feita",
                          f"status={lead['status']}", f"status={lead['status']} chip='{estado}'")
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-21", "'Remover' apaga o lead e o teaser dele do disco")
def remover(page, ctx):
    preparar_lead(page, ctx, "replied")
    arquivo = ctx.projeto(ctx.pid_cheio) / "prospect" / "teasers" / f"{LEAD_ID}.mp4"
    try:
        r = jsonp(page, ctx, "post", f"{base(ctx)}/leads/{LEAD_ID}/teaser", {})
        if r.status not in (200, 201, 202):
            return H.Resultado.falha(f"não foi possível preparar o teaser: {r.status} {r.text()[:120]}")
        H.esperar_job(ctx, page, f"{base(ctx)}/job", 180)
        recarregar(page)
        abrir_corpo(page)
        with dialogos(page, aceitar=True) as d:
            linha(page).locator("button[data-act='del']").click()
            page.wait_for_timeout(1200)
        restantes = [x["id"] for x in leads(page, ctx)["leads"]]
        ev = H.evidencia(page, ctx, "prospect-removido")
        return H.verifica(bool(d.vistos) and LEAD_ID not in restantes and not arquivo.exists()
                          and linha(page).count() == 0,
                          f"lead removido e teaser apagado (confirm='{(d.vistos or [''])[0][:50]}')",
                          f"confirms={d.vistos} leads={restantes} teaser em disco={arquivo.exists()} "
                          f"linha na tela={linha(page).count()}", ev)
    finally:
        apagar_lead(page, ctx)


@caso("C-PROSPECT-22", "campanha sem leads: empty-state cita os segmentos do mar azul da aula", pid="vazio")
def vazio(page, ctx):
    d = leads(page, ctx, ctx.pid_vazio)
    texto = (page.locator("#leadList .empty").text_content() or "").strip()
    chip = (page.locator("#todayChip").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "prospect-vazio")
    return H.verifica(not d["leads"] and all(s in texto for s in d["segments"]) and chip == "0/10 hoje",
                      f"empty-state com {len(d['segments'])} segmentos",
                      f"leads={len(d['leads'])} texto='{texto[:120]}' chip='{chip}' segmentos={d['segments']}", ev)


# ---------- painel 02: pitch da call ----------
@caso("C-PROSPECT-23", "caixa do pitch traz os lembretes da aula e aponta prospect/pitch.md")
def pitch_caixa(page, ctx):
    recarregar(page)
    p = jsonp(page, ctx, "get", f"{base(ctx)}/pitch").json()
    texto = (page.locator("#pitchBox").text_content() or "").strip()
    fim = (page.locator("#pitchBox .end").text_content() or "").strip()
    linhas = page.locator("#pitchValues .pitch-table .tr").count()
    ev = H.evidencia(page, ctx, "prospect-pitch")
    return H.verifica(all(r in texto for r in p["reminders"]) and fim == "→ prospect/pitch.md"
                      and linhas == len(p["steps"]),
                      f"{len(p['reminders'])} lembretes e {linhas} etapas",
                      f"texto='{texto[:120]}' fim='{fim}' linhas={linhas} etapas={len(p['steps'])}", ev)


@caso("C-PROSPECT-24", "'Copiar' do pitch põe o markdown (tabela de etapas) na área de transferência")
def pitch_copiar(page, ctx):
    recarregar(page)
    liberado = liberar_clipboard(page, ctx)
    esperado = jsonp(page, ctx, "get", f"{base(ctx)}/pitch").json()["markdown"]
    botao = page.locator("#btnPitchCopy")
    botao.click()
    page.wait_for_timeout(600)
    rotulo = (botao.text_content() or "").strip()
    texto = clipboard(page) if liberado else ""
    ok = "copiado" in rotulo and (not liberado or ("Etapas de produção" in texto and texto == esperado))
    return H.verifica(ok, f"markdown copiado ({len(texto)} caracteres)",
                      f"rótulo='{rotulo}' clipboard[:80]='{texto[:80]}' esperado[:80]='{esperado[:80]}'")


@caso("C-PROSPECT-25", "'Salvar valores e regerar' grava prospect/pitch.json e regrava prospect/pitch.md")
def pitch_salvar(page, ctx):
    recarregar(page)
    valores = {"Conceito": 40, "Mood board": 30, "Roteirização": 40, "Direção criativa": 40,
               "Produção": 60, "Montagem": 50, "Entrega": 40}
    for etapa, v in valores.items():
        page.locator(f"#pitchValues input[data-pitch='{etapa}']").fill(str(v))
    page.locator("#pitchValues [data-pitch-total]").fill(str(sum(valores.values())))
    page.locator("#btnPitchSave").click()
    t = H.esperar_toast(page, "pitch.md salvo")
    page.wait_for_timeout(600)
    arquivo = ctx.projeto(ctx.pid_cheio) / "prospect" / "pitch.json"
    md = ctx.projeto(ctx.pid_cheio) / "prospect" / "pitch.md"
    gravado = json.loads(arquivo.read_text()) if arquivo.exists() else {}
    api = jsonp(page, ctx, "get", f"{base(ctx)}/pitch").json()
    ev = H.evidencia(page, ctx, "prospect-pitch-salvo")
    ok = (gravado.get("values") == {k: float(v) for k, v in valores.items()}
          and gravado.get("total") == float(sum(valores.values())) and api["matches"] is True
          and md.exists() and "Conceito" in md.read_text() and bool(t))
    return H.verifica(ok, f"pitch.json com total R$ {sum(valores.values())}; toast='{t}'",
                      f"pitch.json={gravado} api.matches={api.get('matches')} pitch.md={md.exists()} toast='{t}'", ev)


@caso("C-PROSPECT-26", "total diferente da soma das etapas avisa no toast e no title do total")
def pitch_soma_diferente(page, ctx):
    recarregar(page)
    for etapa in ("Conceito", "Mood board", "Roteirização", "Direção criativa", "Produção", "Montagem", "Entrega"):
        page.locator(f"#pitchValues input[data-pitch='{etapa}']").fill("30")
    page.locator("#pitchValues [data-pitch-total]").fill("400")
    page.locator("#btnPitchSave").click()
    t = H.esperar_toast(page, "soma")
    page.wait_for_timeout(600)
    api = jsonp(page, ctx, "get", f"{base(ctx)}/pitch").json()
    title = page.locator("#pitchValues .total .v").first.get_attribute("title") or ""
    return H.verifica(bool(t) and api["matches"] is False and api["sum"] == 210 and api["total"] == 400
                      and "soma" in title.lower(),
                      f"toast='{t}' e title='{title}'",
                      f"toast='{t}' sum={api.get('sum')} total={api.get('total')} matches={api.get('matches')} title='{title}'")


@caso("C-PROSPECT-27", "total fora da faixa de R$ 100 a R$ 500 avisa a ancoragem inicial da aula")
def pitch_fora_da_faixa(page, ctx):
    recarregar(page)
    valores = {"Conceito": 200, "Mood board": 200, "Roteirização": 200, "Direção criativa": 200,
               "Produção": 200, "Montagem": 200, "Entrega": 200}
    for etapa, v in valores.items():
        page.locator(f"#pitchValues input[data-pitch='{etapa}']").fill(str(v))
    page.locator("#pitchValues [data-pitch-total]").fill(str(sum(valores.values())))
    page.locator("#btnPitchSave").click()
    t = H.esperar_toast(page, "R$")
    page.wait_for_timeout(600)
    api = jsonp(page, ctx, "get", f"{base(ctx)}/pitch").json()
    return H.verifica(bool(t) and api["in_range"] is False and str(int(api["min_price"])) in t
                      and str(int(api["max_price"])) in t,
                      f"toast='{t}'",
                      f"toast='{t}' in_range={api.get('in_range')} faixa={api.get('min_price')}–{api.get('max_price')}")


@caso("C-PROSPECT-28", "a tela não desenha o painel do guia: a faixa do gate ocupa o lugar dele")
def sem_guia(page, ctx):
    recarregar(page)
    guia = page.locator("#main #guide").count()
    gate = page.locator("#main #gatePanel").count()
    return H.verifica(guia == 0 and gate == 1, "#guide removido, #gatePanel presente",
                      f"#guide={guia} #gatePanel={gate}")
