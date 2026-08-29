"""Casos da etapa 5 — Animação (aula 012).

Tela: `studio/etapas/animate/view.html` + `view.js` (painel 01 = plano de takes por shot, painel
02 = importação de mp4). Backend: `studio/etapas/animate/router.py` + `studio/animate/service.py`.

O que cada caso cobre: plano vindo do storyboard, autosave do prompt, modal "Gerar take N"
(modo/duração/câmera/ação/sugestão/modelo/galeria), like e rejeição de take (com o
`shotMM_final.mp4` que a etapa 7 consome), as três importações (upload, Downloads, histórico do
CLI), o gate de custo e o job de geração paga (fake offline do `higgsfield`).

Regra de convivência: o `pid_cheio` é compartilhado com as outras telas — todo caso que escreve
tira um retrato de `animate/takes.json`, `animate/candidates.json`, `videos/` e
`animate/candidates/` (`_snap`) e devolve o estado ao final (`_restaura`).
"""
from __future__ import annotations

import json

from scripts.qa import harness as H

TELA = "animate"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)

JSON = {"content-type": "application/json"}
K_LIKE = "cena01/shot01"    # shot do seed com take1 já com like
K_VAZIO = "cena02/shot01"   # shot sem take: slot "+ gerar take 1"
K_VAZIO2 = "cena02/shot02"  # segundo shot sem take (casos que escrevem no shot)


# ---------- helpers do módulo ----------
def _base(ctx, pid: str | None = None) -> str:
    return f"/api/projects/{pid or ctx.pid_cheio}/animate"


def _plano(page, ctx, pid: str | None = None) -> dict:
    return H.api(page, ctx, "get", f"{_base(ctx, pid)}/shots").json()


def _shot(plano: dict, k: str) -> dict:
    cena, shot = k.split("/")
    return next(s for s in plano["shots"] if s["scene"] == cena and s["shot"] == shot)


def _row(page, k: str):
    return page.locator(f'.shot-row[data-k="{k}"]')


def _put(page, ctx, k: str, patch: dict):
    cena, shot = k.split("/")
    return H.api(page, ctx, "put", f"{_base(ctx)}/shots/{cena}/{shot}", data=json.dumps(patch), headers=JSON)


def _like(page, ctx, k: str, take: str, liked):
    cena, shot = k.split("/")
    return H.api(page, ctx, "post", f"{_base(ctx)}/shots/{cena}/{shot}/takes/{take}/like",
                 data=json.dumps({"liked": liked}), headers=JSON)


def _snap(ctx) -> dict:
    """Retrato do disco do animate, para desfazer o que o caso escreveu."""
    root = ctx.projeto(ctx.pid_cheio)
    return {"takes": (root / "animate" / "takes.json").read_text(),
            "cands": (root / "animate" / "candidates.json").read_text(),
            "videos": set(H.arquivos(root, "videos/**/*")),
            "cfiles": set(H.arquivos(root, "animate/candidates/**/*"))}


def _restaura(page, ctx, snap: dict) -> None:
    root = ctx.projeto(ctx.pid_cheio)
    (root / "animate" / "takes.json").write_text(snap["takes"])
    (root / "animate" / "candidates.json").write_text(snap["cands"])
    for rel in set(H.arquivos(root, "videos/**/*")) - snap["videos"]:
        (root / rel).unlink(missing_ok=True)
    for rel in set(H.arquivos(root, "animate/candidates/**/*")) - snap["cfiles"]:
        (root / rel).unlink(missing_ok=True)
    # a SPA guarda plano e candidatos em memória: sem recarregar, o próximo caso renderiza
    # thumbs de candidatos que este caso acabou de apagar (404 na sonda)
    try:
        page.locator("#anReload").click(timeout=5000)
        page.wait_for_timeout(600)
    except Exception:  # noqa: BLE001
        pass


def _mexer_takes(ctx, fn) -> None:
    """Fixture de disco: altera `animate/takes.json` para chegar a um estado caro de produzir pela
    UI (3 falhas, 6 falhas, shot órfão). Sempre em par com `_snap`/`_restaura`."""
    p = ctx.projeto(ctx.pid_cheio) / "animate" / "takes.json"
    dados = json.loads(p.read_text())
    fn(dados)
    p.write_text(json.dumps(dados, ensure_ascii=False, indent=1))


def _abrir_modal(page, k: str):
    """Abre o modal 'Gerar take N' pelo slot dashed do shot `k` e devolve o locator do modal."""
    _row(page, k).locator(".an-gen").click()
    m = H.modal(page)
    m.wait_for()
    return m


def _confirmar_custo(page, confirmar: bool = True) -> str:
    """Espera o modal de custo (`ui.confirmCost`) e clica em Cancelar/primário. Devolve o texto."""
    page.wait_for_function("() => [...document.querySelectorAll('.modal .sub')]"
                           ".some(e => /Custo antes de gerar/.test(e.textContent || ''))", timeout=20_000)
    m = H.modal(page)
    texto = m.inner_text()
    alvo = ".modal-actions button.primary" if confirmar else ".modal-actions button.ghost"
    m.locator(alvo).click()
    return texto


# ---------- painel 01: plano de takes ----------
@caso("C-ANIMATE-01", "painel 01 lista uma linha por shot do storyboard, na ordem do plano")
def linhas_do_plano(page, ctx):
    plano = _plano(page, ctx)
    ks = page.locator("#anShots .shot-row").evaluate_all("els => els.map(e => e.dataset.k)")
    esperado = [f"{s['scene']}/{s['shot']}" for s in plano["shots"]]
    ev = H.evidencia(page, ctx, "animate-plano")
    return H.verifica(ks == esperado and len(ks) > 0, f"{len(ks)} shots na ordem do plano",
                      f"DOM={ks} vs API={esperado}", ev)


@caso("C-ANIMATE-02", "shot com take escolhido mostra thumb, tile com ♥ e nota 'take 1 escolhido'")
def shot_com_like(page, ctx):
    row = _row(page, K_LIKE)
    nm = (row.locator(".nm").text_content() or "").strip()
    tile = row.locator(".take.an-like").first
    classe = tile.get_attribute("class") or ""
    nota = (row.locator(".takes .note").text_content() or "").strip()
    thumb = row.locator(".thumb img").count()
    ev = H.evidencia(page, ctx, "animate-shot-like", full_page=False)
    ok = nm.startswith("cena01") and "like" in classe and "escolhido" in nota and thumb == 1
    return H.verifica(ok, f"'{nm}' · tile com like · nota '{nota}'",
                      f"nm='{nm}' classe='{classe}' nota='{nota}' thumbs={thumb}", ev)


@caso("C-ANIMATE-03", "shot sem take mostra o slot '+ gerar take 1' e a nota da aula (gere 2 e dê like)")
def shot_sem_take(page, ctx):
    row = _row(page, K_VAZIO)
    slot = (row.locator(".take.empty.an-gen").text_content() or "").strip()
    nota = (row.locator(".takes .note").text_content() or "").strip()
    return H.verifica("gerar take 1" in slot and "sem take ainda" in nota,
                      f"slot='{slot}' nota='{nota}'", f"slot='{slot}' nota='{nota}'")


@caso("C-ANIMATE-04", "'Recarregar plano' traz o que mudou no backend para a tela")
def reload_plano(page, ctx):
    texto = "QA reload dolly-in"
    _put(page, ctx, K_VAZIO, {"prompt": texto})
    try:
        page.locator("#anReload").click()
        page.wait_for_timeout(800)
        valor = _row(page, K_VAZIO).locator(".an-prompt").input_value()
    finally:
        _put(page, ctx, K_VAZIO, {"prompt": ""})
    return H.verifica(valor == texto, f"input recarregado com '{valor}'",
                      f"input='{valor}' esperado='{texto}'")


@caso("C-ANIMATE-05", "prompt do movimento tem autosave no blur (toast + takes.json)")
def autosave_prompt(page, ctx):
    texto = "QA blur: walking through the blizzard"
    inp = _row(page, K_VAZIO).locator(".an-prompt")
    inp.fill(texto)
    inp.press("Tab")
    t = H.esperar_toast(page, "prompt")
    page.wait_for_timeout(1200)      # deixa o `loadPlan()` da própria tela terminar (ver C-ANIMATE-37)
    gravado = _shot(_plano(page, ctx), K_VAZIO)["prompt"]
    _put(page, ctx, K_VAZIO, {"prompt": ""})
    return H.verifica(gravado == texto and "salvo" in t.lower(), f"toast='{t}' e takes.json gravado",
                      f"toast='{t}' takes.json.prompt='{gravado}' esperado='{texto}'")


@caso("C-ANIMATE-06", "Enter no campo do prompt tira o foco e grava (sem botão Salvar)")
def enter_salva_prompt(page, ctx):
    texto = "QA enter: slow dramatic push in"
    inp = _row(page, K_VAZIO2).locator(".an-prompt")
    inp.fill(texto)
    inp.press("Enter")
    t = H.esperar_toast(page, "prompt")
    page.wait_for_timeout(1200)      # idem C-ANIMATE-05
    gravado = _shot(_plano(page, ctx), K_VAZIO2)["prompt"]
    _put(page, ctx, K_VAZIO2, {"prompt": ""})
    return H.verifica(gravado == texto and bool(t), f"toast='{t}' e prompt gravado por Enter",
                      f"toast='{t}' takes.json.prompt='{gravado}'")


@caso("C-ANIMATE-07", "prompt gravado sobrevive ao reload da tela")
def prompt_persiste(page, ctx):
    texto = "QA persist: the scene comes to life"
    _put(page, ctx, K_VAZIO2, {"prompt": texto})
    try:
        page.reload()
        H.esperar_tela(page)
        valor = _row(page, K_VAZIO2).locator(".an-prompt").input_value()
    finally:
        _put(page, ctx, K_VAZIO2, {"prompt": ""})
    return H.verifica(valor == texto, "prompt reaparece depois do reload", f"input='{valor}' esperado='{texto}'")


# ---------- modal "Gerar take N" ----------
@caso("C-ANIMATE-08", "slot '+ gerar take N' abre o modal com modo, duração, câmera, ação, modelo e takes")
def modal_campos(page, ctx):
    m = _abrir_modal(page, K_VAZIO)
    campos = {c: m.locator(c).count() for c in
              (".an-mode", ".an-duration", ".an-camera", ".an-action", ".an-slow", ".an-black",
               ".an-suggest", ".an-model", ".an-count", "#anGallery")}
    titulo = (m.locator(".modal-head h3").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "animate-modal-gerar", full_page=False)
    H.fechar_modal(page)
    faltando = [c for c, n in campos.items() if not n]
    return H.verifica(not faltando and "Gerar take 1" in titulo, f"título='{titulo}' com todos os campos",
                      f"título='{titulo}' faltando={faltando}", ev)


@caso("C-ANIMATE-09", "modal traz o chip do CLI e o select de modelo com a ordem viva de modelos")
def modal_modelos(page, ctx):
    plano = _plano(page, ctx)
    m = _abrir_modal(page, K_VAZIO)
    opts = m.locator(".an-model option").evaluate_all("els => els.map(e => e.value)")
    sel = m.locator(".an-model").input_value()
    # o chip do CLI perde a classe `an-cli` quando `ui.hfChip` reescreve o `className` — por isso
    # ele é procurado pelo texto, e não pela classe da marcação (ver relatório da rodada)
    chip = (m.locator(".modal-body span.chip").last.text_content() or "").strip()
    H.fechar_modal(page)
    ok = opts == plano["model_order"] and sel in opts and "CLI" in chip
    return H.verifica(ok, f"modelos={opts} selecionado={sel} chip='{chip}'",
                      f"modelos={opts} vs API={plano['model_order']} selecionado={sel} chip='{chip}'")


@caso("C-ANIMATE-10", "modo start/end revela o end frame com o próximo shot da cena e as dicas do modo")
def modal_start_end(page, ctx):
    plano = _plano(page, ctx)
    prox = _shot(plano, K_VAZIO)["next_in_scene"]
    m = _abrir_modal(page, K_VAZIO)
    escondido_antes = m.locator(".an-endrow").is_hidden()
    m.locator(".an-mode").select_option("start_end")
    page.wait_for_timeout(300)
    visivel = m.locator(".an-endrow").is_visible()
    opcoes = m.locator(".an-end option").all_text_contents()
    dicas = m.locator(".an-tips li").count()
    ev = H.evidencia(page, ctx, "animate-modal-start-end", full_page=False)
    H.fechar_modal(page)
    ok = escondido_antes and visivel and any(prox in o for o in opcoes) and dicas > 0
    return H.verifica(ok, f"end frame visível com {opcoes} e {dicas} dica(s)",
                      f"escondido_antes={escondido_antes} visível={visivel} opções={opcoes} dicas={dicas}", ev)


@caso("C-ANIMATE-11", "'Sugerir prompt' preenche o prompt do shot e mostra o exemplo da aula")
def sugerir_prompt(page, ctx):
    m = _abrir_modal(page, K_VAZIO)
    m.locator(".an-camera").fill("Dramatic dolly-in")
    m.locator(".an-action").fill("walking through the blizzard")
    m.locator(".an-mode").select_option("elaborate")
    m.locator(".an-suggest").click()
    try:
        page.wait_for_function("() => (document.querySelector('.an-example')?.textContent || '').length > 0",
                               timeout=10_000)
    except Exception:  # noqa: BLE001
        pass
    exemplo = (m.locator(".an-example").text_content() or "").strip()
    valor = _row(page, K_VAZIO).locator(".an-prompt").input_value()
    api = H.api(page, ctx, "get", f"{_base(ctx)}/prompt?scene=cena02&shot=shot01&mode=elaborate"
                                  "&camera=Dramatic+dolly-in&action=walking+through+the+blizzard").json()
    ev = H.evidencia(page, ctx, "animate-sugerir", full_page=False)
    H.fechar_modal(page)
    page.locator("#anReload").click()          # descarta o prompt sugerido (não foi salvo)
    page.wait_for_timeout(600)
    return H.verifica(valor == api["prompt"] and "Exemplo da aula" in exemplo,
                      f"prompt='{valor}' exemplo='{exemplo[:60]}'",
                      f"prompt='{valor}' esperado='{api['prompt']}' exemplo='{exemplo[:80]}'", ev)


@caso("C-ANIMATE-12", "'mudança lenta' + sugestão leva a duração para 10 s (aula 012)")
def sugerir_lento(page, ctx):
    m = _abrir_modal(page, K_VAZIO)
    antes = m.locator(".an-duration").input_value()
    m.locator("label:has(.an-slow)").click()
    m.locator(".an-suggest").click()
    page.wait_for_timeout(800)
    depois = m.locator(".an-duration").input_value()
    H.fechar_modal(page)
    page.locator("#anReload").click()
    page.wait_for_timeout(600)
    return H.verifica(antes == "5" and depois == "10", f"duração {antes}s → {depois}s",
                      f"duração antes={antes} depois={depois} (esperado 5 → 10)")


@caso("C-ANIMATE-13", "'Atribuir selecionado' só habilita depois de marcar um vídeo na galeria do modal")
def atribuir_sem_selecao(page, ctx):
    antes = len(_shot(_plano(page, ctx), K_VAZIO)["takes"])
    m = _abrir_modal(page, K_VAZIO)
    btn = m.locator(".modal-actions button.ghost")
    off_inicial = btn.is_disabled()
    card = m.locator("#anGallery .card").first
    if not card.count():
        H.fechar_modal(page)
        return H.Resultado.bloqueado("nenhum candidato importado no seed para marcar na galeria")
    card.click()
    page.wait_for_timeout(400)
    habilitado = btn.is_enabled()
    marcado = "sel" in (card.get_attribute("class") or "")
    card.click()                                  # desmarcar volta a travar o botão
    page.wait_for_timeout(400)
    off_final = btn.is_disabled()
    depois = len(_shot(_plano(page, ctx), K_VAZIO)["takes"])
    H.fechar_modal(page)
    return H.verifica(off_inicial and habilitado and marcado and off_final and antes == depois,
                      "botão travado sem seleção, liberado com o vídeo marcado",
                      f"desabilitado inicial={off_inicial} habilitado com seleção={habilitado} "
                      f"card.sel={marcado} desabilitado ao desmarcar={off_final} takes {antes}→{depois}")


@caso("C-ANIMATE-14", "atribuir um vídeo importado vira take em takes.json e videos/<cena>/")
def atribuir_take(page, ctx):
    snap = _snap(ctx)
    try:
        m = _abrir_modal(page, K_VAZIO)
        card = m.locator("#anGallery .card").first
        if not card.count():
            return H.Resultado.bloqueado("nenhum candidato importado no seed para atribuir")
        card.click()
        m.locator(".modal-actions button.ghost").click()
        t = H.esperar_toast(page, "take")
        H.esperar_modal_sumir(page, 10_000)
        page.wait_for_timeout(600)
        shot = _shot(_plano(page, ctx), K_VAZIO)
        arquivo = (shot["takes"] or [{}])[0].get("file", "")
        existe = (ctx.projeto(ctx.pid_cheio) / arquivo).exists() if arquivo else False
        tiles = _row(page, K_VAZIO).locator(".take.an-like").count()
        ev = H.evidencia(page, ctx, "animate-take-atribuido", full_page=False)
        return H.verifica(len(shot["takes"]) == 1 and arquivo == "videos/cena02/shot01_take1.mp4" and existe and tiles == 1,
                          f"take1 em {arquivo} (toast='{t}')",
                          f"takes={len(shot['takes'])} arquivo='{arquivo}' existe={existe} tiles={tiles} toast='{t}'", ev)
    finally:
        _restaura(page, ctx, snap)


# ---------- like, rejeição e reprodução ----------
@caso("C-ANIMATE-15", "✕ rejeita o take: conta falha e apaga o shotMM_final.mp4 da etapa 7")
def rejeitar_take(page, ctx):
    root = ctx.projeto(ctx.pid_cheio)
    final = root / "videos" / "cena01" / "shot01_final.mp4"
    try:
        tile = _row(page, K_LIKE).locator(".take.an-like").first
        tile.hover()
        tile.locator(".an-x").click()
        page.wait_for_timeout(1200)
        shot = _shot(_plano(page, ctx), K_LIKE)
        nota = (_row(page, K_LIKE).locator(".takes .note").text_content() or "").strip()
        rejeitado = _row(page, K_LIKE).locator(".take .an-rej").count()
        ev = H.evidencia(page, ctx, "animate-take-rejeitado", full_page=False)
        ok = shot["takes"][0]["liked"] is False and shot["failures"] == 1 and not final.exists() and rejeitado == 1
        return H.verifica(ok, f"liked=false, 1 falha, sem final.mp4 (nota '{nota}')",
                          f"liked={shot['takes'][0]['liked']} failures={shot['failures']} "
                          f"final.mp4={final.exists()} marca ✕={rejeitado} nota='{nota}'", ev)
    finally:
        _like(page, ctx, K_LIKE, "take1", True)


@caso("C-ANIMATE-16", "clique no tile dá like e recria o shotMM_final.mp4")
def like_take(page, ctx):
    root = ctx.projeto(ctx.pid_cheio)
    final = root / "videos" / "cena01" / "shot01_final.mp4"
    _like(page, ctx, K_LIKE, "take1", False)      # estado de partida: take rejeitado
    page.locator("#anReload").click()
    page.wait_for_timeout(800)
    try:
        _row(page, K_LIKE).locator(".take.an-like span").first.click()
        page.wait_for_timeout(1200)
        shot = _shot(_plano(page, ctx), K_LIKE)
        classe = _row(page, K_LIKE).locator(".take.an-like").first.get_attribute("class") or ""
        nota = (_row(page, K_LIKE).locator(".takes .note").text_content() or "").strip()
        ok = shot["takes"][0]["liked"] is True and final.exists() and "like" in classe and "escolhido" in nota
        return H.verifica(ok, f"liked=true e {final.name} recriado (nota '{nota}')",
                          f"liked={shot['takes'][0]['liked']} final.mp4={final.exists()} classe='{classe}' nota='{nota}'")
    finally:
        _like(page, ctx, K_LIKE, "take1", True)


@caso("C-ANIMATE-17", "Enter no tile focado dá like (o tile é role=button)")
def like_teclado(page, ctx):
    _like(page, ctx, K_LIKE, "take1", None)
    page.locator("#anReload").click()
    page.wait_for_timeout(800)
    try:
        tile = _row(page, K_LIKE).locator(".take.an-like").first
        tile.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(1200)
        liked = _shot(_plano(page, ctx), K_LIKE)["takes"][0]["liked"]
        return H.verifica(liked is True, "Enter no tile deu like", f"liked={liked} (esperado True)")
    finally:
        _like(page, ctx, K_LIKE, "take1", True)


@caso("C-ANIMATE-18", "▶ do tile abre o mp4 do take em nova aba")
def abrir_mp4(page, ctx):
    tile = _row(page, K_LIKE).locator(".take.an-like").first
    tile.hover()
    with page.context.expect_page(timeout=10_000) as info:
        tile.locator(".an-play").click()
    nova = info.value
    url = nova.url
    nova.close()
    return H.verifica(url.endswith("videos/cena01/shot01_take1.mp4"), f"abriu {url}",
                      f"url da nova aba='{url}'")


# ---------- painel 02: importação ----------
@caso("C-ANIMATE-19", "chip do CLI fica oculto com o CLI logado e o contador reflete /candidates")
def chips(page, ctx):
    cands = H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json()
    st = H.api(page, ctx, "get", "/api/higgsfield/status").json()
    conta = (page.locator("#anCandCount").text_content() or "").strip()
    oculto = page.locator("#anHfState").is_hidden()
    esperado_oculto = bool(st.get("installed") and st.get("logged_in"))
    return H.verifica(conta == f"{len(cands)} vídeos" and oculto == esperado_oculto,
                      f"contador='{conta}' chip oculto={oculto}",
                      f"contador='{conta}' esperado='{len(cands)} vídeos' oculto={oculto} status={st}")


@caso("C-ANIMATE-20", "upload de mp4 pelo #anUpload importa o vídeo e atualiza o contador")
def upload_mp4(page, ctx):
    snap = _snap(ctx)
    try:
        ids = {c["id"] for c in H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json()}
        antes = len(ids)
        H.upload(page, "#anUpload", H.mp4_temp(ctx, "an-upload", seconds=2))
        t = H.esperar_toast(page, "importad")
        page.wait_for_timeout(800)
        cands = H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json()
        conta = (page.locator("#anCandCount").text_content() or "").strip()
        novo = [c for c in cands if c["id"] not in ids]
        existe = all((ctx.projeto(ctx.pid_cheio) / "animate" / "candidates" / c["file"]).exists() for c in novo)
        ev = H.evidencia(page, ctx, "animate-upload", full_page=False)
        return H.verifica(len(cands) == antes + 1 and conta == f"{len(cands)} vídeos" and existe,
                          f"toast='{t}' · {antes}→{len(cands)} candidatos",
                          f"toast='{t}' candidatos {antes}→{len(cands)} contador='{conta}' arquivos={existe}", ev)
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-21", "'Importar da pasta Downloads' varre a pasta configurada e importa os mp4 recentes")
def importar_downloads(page, ctx):
    env = H.carregar_env(ctx.run_dir)
    pasta = env.get("STUDIO_DOWNLOADS")
    if not pasta:
        return H.Resultado.bloqueado("STUDIO_DOWNLOADS ausente em env.sh")
    from pathlib import Path
    from shutil import copy2
    alvo = Path(pasta) / "qa-animate-downloads.mp4"
    snap = _snap(ctx)
    try:
        copy2(H.mp4_temp(ctx, "an-downloads", seconds=1), alvo)
        antes = len(H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json())
        page.locator("#anBtnDownloads").click()
        t = H.esperar_toast(page, "novos")
        page.wait_for_timeout(800)
        cands = H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json()
        origens = {c["source"] for c in cands}
        return H.verifica(len(cands) == antes + 1 and "downloads" in origens,
                          f"toast='{t}' · candidato importado da pasta {pasta}",
                          f"toast='{t}' candidatos {antes}→{len(cands)} origens={origens} pasta={pasta}")
    finally:
        alvo.unlink(missing_ok=True)
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-22", "'Importar do histórico Higgsfield' lê o histórico do CLI e reporta jobs e vídeos")
def importar_historico(page, ctx):
    snap = _snap(ctx)
    try:
        antes = len(H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json())
        page.locator("#anBtnHistory").click()
        t = H.esperar_toast(page, "jobs", timeout_ms=30_000)
        page.wait_for_timeout(800)
        cands = H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json()
        origens = {c["source"] for c in cands}
        # o fake devolve 3 jobs; vídeos idênticos são deduplicados por conteúdo (ingest)
        return H.verifica("3 jobs" in t and len(cands) > antes and "higgsfield" in origens,
                          f"toast='{t}' · {antes}→{len(cands)} candidatos",
                          f"toast='{t}' candidatos {antes}→{len(cands)} origens={origens}")
    finally:
        _restaura(page, ctx, snap)


# ---------- geração paga (gate de custo + job) ----------
@caso("C-ANIMATE-23", "'Gerar via CLI' mostra o custo antes; Cancelar não gera nem gasta")
def custo_cancelar(page, ctx):
    snap = _snap(ctx)
    try:
        antes = len(_shot(_plano(page, ctx), K_VAZIO)["takes"])
        m = _abrir_modal(page, K_VAZIO)
        m.locator(".modal-actions button.primary").click()
        texto = _confirmar_custo(page, confirmar=False)
        page.wait_for_timeout(800)
        depois = len(_shot(_plano(page, ctx), K_VAZIO)["takes"])
        progresso = page.locator(".modal.progress-modal").count()
        ev = H.evidencia(page, ctx, "animate-custo", full_page=False)
        H.fechar_modal(page)
        return H.verifica("créditos" in texto.lower() and antes == depois and progresso == 0,
                          f"modal de custo mostrou '{texto[:60]}' e o cancelamento não gerou nada",
                          f"texto='{texto[:120]}' takes {antes}→{depois} modal de progresso={progresso}", ev)
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-24", "gerar 1 take via CLI: modal de progresso, take em takes.json e mp4 em videos/")
def gerar_take(page, ctx):
    snap = _snap(ctx)
    try:
        inp = _row(page, K_VAZIO).locator(".an-prompt")
        inp.fill("QA generate: dramatic dolly-in through the blizzard")
        inp.press("Tab")
        H.esperar_toast(page, "prompt")
        m = _abrir_modal(page, K_VAZIO)
        m.locator(".an-count").fill("1")
        m.locator(".modal-actions button.primary").click()
        _confirmar_custo(page, confirmar=True)
        page.wait_for_selector(".modal.progress-modal", timeout=20_000)
        travado = page.locator(".modal.progress-modal .modal-close").is_disabled()
        passos = page.locator(".modal.progress-modal .prog-steps li").count()
        sumiu = H.esperar_modal_sumir(page, 180_000)
        page.wait_for_timeout(1000)
        shot = _shot(_plano(page, ctx), K_VAZIO)
        arquivo = (shot["takes"] or [{}])[0].get("file", "")
        existe = (ctx.projeto(ctx.pid_cheio) / arquivo).exists() if arquivo else False
        job = H.api(page, ctx, "get", f"{_base(ctx)}/job").json()
        ev = H.evidencia(page, ctx, "animate-gerado", full_page=False)
        ok = travado and passos >= 1 and sumiu and len(shot["takes"]) == 1 and existe and job.get("state") == "done"
        return H.verifica(ok, f"job {job.get('state')} · take em {arquivo}",
                          f"close travado={travado} passos={passos} modal sumiu={sumiu} "
                          f"takes={len(shot['takes'])} arquivo='{arquivo}' existe={existe} job={job}", ev)
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-25", "gerar sem prompt falha com mensagem amigável dentro do modal de progresso")
def gerar_sem_prompt(page, ctx):
    snap = _snap(ctx)
    try:
        _put(page, ctx, K_VAZIO2, {"prompt": ""})
        page.locator("#anReload").click()
        page.wait_for_timeout(800)
        m = _abrir_modal(page, K_VAZIO2)
        m.locator(".modal-actions button.primary").click()
        _confirmar_custo(page, confirmar=True)
        page.wait_for_selector(".modal.progress-modal", timeout=20_000)
        try:
            page.wait_for_function("() => document.querySelector('.modal.progress-modal .prog-err')", timeout=30_000)
        except Exception:  # noqa: BLE001
            pass
        erro = (page.locator(".modal.progress-modal .prog-err").text_content() or "").strip()
        fechavel = page.locator(".modal.progress-modal .modal-close").is_enabled()
        takes = len(_shot(_plano(page, ctx), K_VAZIO2)["takes"])
        ev = H.evidencia(page, ctx, "animate-gerar-sem-prompt", full_page=False)
        H.fechar_modal(page)
        return H.verifica("prompt" in erro.lower() and fechavel and takes == 0,
                          f"erro no modal: '{erro}'",
                          f"erro='{erro}' close habilitado={fechavel} takes={takes}", ev)
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-26", "'corte para preto' fica gravado no shot e vira aviso na nota da linha")
def corte_para_preto(page, ctx):
    snap = _snap(ctx)
    try:
        m = _abrir_modal(page, K_VAZIO2)
        m.locator("label:has(.an-black)").click()
        m.locator(".modal-actions button.primary").click()
        _confirmar_custo(page, confirmar=False)
        page.wait_for_timeout(1000)
        H.fechar_modal(page)
        page.locator("#anReload").click()
        page.wait_for_timeout(800)
        shot = _shot(_plano(page, ctx), K_VAZIO2)
        nota = (_row(page, K_VAZIO2).locator(".takes .note").text_content() or "").strip()
        classe = _row(page, K_VAZIO2).locator(".takes .note").get_attribute("class") or ""
        return H.verifica(shot["fallback_black"] is True and "preto" in nota and "warn" in classe,
                          f"fallback_black gravado · nota '{nota}'",
                          f"fallback_black={shot['fallback_black']} nota='{nota}' classe='{classe}'")
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-27", "Escape fecha o modal 'Gerar take N' sem gravar nada")
def modal_escape(page, ctx):
    antes = _shot(_plano(page, ctx), K_VAZIO)
    m = _abrir_modal(page, K_VAZIO)
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    aberto = m.count() and m.is_visible()
    depois = _shot(_plano(page, ctx), K_VAZIO)
    return H.verifica(not aberto and antes == depois, "modal fechou por Escape sem alterar o shot",
                      f"modal aberto={bool(aberto)} shot mudou={antes != depois}")


@caso("C-ANIMATE-29", "arrastar um mp4 sobre a dropzone importa igual ao seletor de arquivos")
def drop_mp4(page, ctx):
    import base64
    snap = _snap(ctx)
    try:
        antes = len(H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json())
        dados = base64.b64encode(H.mp4_temp(ctx, "an-drop", seconds=3).read_bytes()).decode()
        page.evaluate("""(b64) => {
            const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
            const f = new File([bin], 'qa-drop.mp4', { type: 'video/mp4' });
            const dt = new DataTransfer(); dt.items.add(f);
            document.querySelector('#anDrop').dispatchEvent(
              new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
        }""", dados)
        t = H.esperar_toast(page, "importad", timeout_ms=20_000)
        page.wait_for_timeout(800)
        cands = H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json()
        nomes = [c["name"] for c in cands]
        return H.verifica(len(cands) == antes + 1 and "qa-drop.mp4" in nomes,
                          f"toast='{t}' · mp4 arrastado virou candidato",
                          f"toast='{t}' candidatos {antes}→{len(cands)} nomes={nomes}")
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-30", "arquivo que não é vídeo é recusado pelo import sem quebrar a tela")
def upload_invalido(page, ctx):
    snap = _snap(ctx)
    try:
        antes = len(H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json())
        H.upload(page, "#anUpload", H.png_temp(ctx, "an-nao-video"))
        t = H.esperar_toast(page, "importad")
        page.wait_for_timeout(600)
        depois = len(H.api(page, ctx, "get", f"{_base(ctx)}/candidates").json())
        linhas = page.locator("#anShots .shot-row").count()
        return H.verifica(antes == depois and bool(t) and linhas > 0,
                          f"toast='{t}' e nenhum candidato criado",
                          f"toast='{t}' candidatos {antes}→{depois} linhas do plano={linhas}")
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-31", "3 falhas no shot: a nota sugere o próximo modelo da ordem (aula 012)")
def sugere_modelo(page, ctx):
    snap = _snap(ctx)
    plano = _plano(page, ctx)
    esperado = plano["model_order"][1] if len(plano["model_order"]) > 1 else ""
    try:
        _mexer_takes(ctx, lambda d: [s.update(cli_failures=3) for s in d["shots"]
                                     if (s["scene"], s["shot"]) == tuple(K_VAZIO2.split("/"))])
        page.locator("#anReload").click()
        page.wait_for_timeout(1000)
        shot = _shot(_plano(page, ctx), K_VAZIO2)
        nota = (_row(page, K_VAZIO2).locator(".takes .note").text_content() or "").strip()
        classe = _row(page, K_VAZIO2).locator(".takes .note").get_attribute("class") or ""
        ev = H.evidencia(page, ctx, "animate-3-falhas", full_page=False)
        ok = shot["suggested_model"] == esperado and esperado and esperado in nota and "warn" in classe
        return H.verifica(ok, f"nota '{nota}' sugere {esperado}",
                          f"suggested_model={shot['suggested_model']} esperado={esperado} nota='{nota}' classe='{classe}'", ev)
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-32", "6 falhas no shot: a nota manda adaptar a ideia ou cortar para preto")
def adaptar_ideia(page, ctx):
    snap = _snap(ctx)
    try:
        _mexer_takes(ctx, lambda d: [s.update(cli_failures=6) for s in d["shots"]
                                     if (s["scene"], s["shot"]) == tuple(K_VAZIO2.split("/"))])
        page.locator("#anReload").click()
        page.wait_for_timeout(1000)
        shot = _shot(_plano(page, ctx), K_VAZIO2)
        nota = (_row(page, K_VAZIO2).locator(".takes .note").text_content() or "").strip()
        ev = H.evidencia(page, ctx, "animate-6-falhas", full_page=False)
        ok = (shot["adapt_idea"] and shot["suggest_fallback_black"] and "adapte a ideia" in nota.lower()
              and "preto" in nota.lower())
        return H.verifica(ok, f"nota '{nota}'",
                          f"adapt_idea={shot['adapt_idea']} suggest_fallback_black={shot['suggest_fallback_black']} nota='{nota}'", ev)
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-33", "shot que saiu do storyboard continua no plano marcado como 'fora do storyboard'")
def shot_orfao(page, ctx):
    snap = _snap(ctx)
    try:
        _mexer_takes(ctx, lambda d: d["shots"].append({"scene": "cena99", "shot": "shot01", "takes": []}))
        page.locator("#anReload").click()
        page.wait_for_timeout(1000)
        shot = _shot(_plano(page, ctx), "cena99/shot01")
        row = _row(page, "cena99/shot01")
        nota = (row.locator(".takes .note").text_content() or "").strip()
        thumb = (row.locator(".thumb").text_content() or "").strip()
        return H.verifica(shot["orphan"] and "fora do storyboard" in nota and "sem frame" in thumb,
                          f"linha órfã com nota '{nota}'",
                          f"orphan={shot['orphan']} nota='{nota}' thumb='{thumb}' linhas={row.count()}")
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-34", "pedir mais de 4 takes: o erro do backend chega legível ao usuário")
def takes_fora_da_faixa(page, ctx):
    snap = _snap(ctx)
    try:
        m = _abrir_modal(page, K_VAZIO2)
        m.locator(".an-count").fill("9")
        m.locator(".modal-actions button.primary").click()
        custo = _confirmar_custo(page, confirmar=True)
        page.wait_for_selector(".modal.progress-modal", timeout=20_000)
        try:
            page.wait_for_function("() => document.querySelector('.modal.progress-modal .prog-err')", timeout=30_000)
        except Exception:  # noqa: BLE001
            pass
        erro = (page.locator(".modal.progress-modal .prog-err").text_content() or "").strip()
        takes = len(_shot(_plano(page, ctx), K_VAZIO2)["takes"])
        ev = H.evidencia(page, ctx, "animate-takes-invalido", full_page=False)
        H.fechar_modal(page)
        return H.verifica("1 a 4" in erro and takes == 0, f"erro no modal: '{erro}' (custo: '{custo[:40]}')",
                          f"erro='{erro}' custo='{custo[:80]}' takes={takes}", ev)
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-35", "modo start/end usa o modelo de transição do plano (ADR-021: cena 2.6 / transição 3.0 Turbo)")
def modelo_da_transicao(page, ctx):
    plano = _plano(page, ctx)
    transicao = plano.get("transition_model")
    if not transicao:
        return H.Resultado.bloqueado("/animate/shots não devolve transition_model nesta versão")
    m = _abrir_modal(page, K_VAZIO)
    m.locator(".an-mode").select_option("start_end")
    page.wait_for_timeout(400)
    opts = m.locator(".an-model option").evaluate_all("els => els.map(e => e.value)")
    sel = m.locator(".an-model").input_value()
    ev = H.evidencia(page, ctx, "animate-modelo-transicao", full_page=False)
    H.fechar_modal(page)
    return H.verifica(transicao in opts and sel == transicao,
                      f"start/end selecionou {sel}",
                      f"o plano mapeia transição → '{transicao}' (plan.transition_model, ADR-021), mas o select "
                      f"do modal só oferece {opts} e ficou em '{sel}': não há como gerar a transição start/end "
                      f"com o modelo documentado", ev)


@caso("C-ANIMATE-36", "com 3 falhas, o modal já abre com o modelo sugerido pelo serviço")
def modal_modelo_sugerido(page, ctx):
    snap = _snap(ctx)
    try:
        _mexer_takes(ctx, lambda d: [s.update(cli_failures=3) for s in d["shots"]
                                     if (s["scene"], s["shot"]) == tuple(K_VAZIO2.split("/"))])
        page.locator("#anReload").click()
        page.wait_for_timeout(1000)
        sugerido = _shot(_plano(page, ctx), K_VAZIO2)["suggested_model"]
        m = _abrir_modal(page, K_VAZIO2)
        sel = m.locator(".an-model").input_value()
        H.fechar_modal(page)
        return H.verifica(sel == sugerido, f"modal abriu em {sel} (sugerido pelo serviço)",
                          f"select='{sel}' suggested_model='{sugerido}'")
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-37", "salvar o prompt e recarregar o plano ao mesmo tempo não pode devolver erro")
def escrita_concorrente(page, ctx):
    """A própria tela dispara PUT (autosave) e GET /shots (loadPlan + guia) quase juntos; os dois
    gravam `animate/takes.json` pelo mesmo arquivo temporário (`_save_data`)."""
    snap = _snap(ctx)
    try:
        respostas = page.evaluate("""async (base) => {
            const out = [];
            for (let i = 0; i < 6; i++) {
                const r = await Promise.all([
                    fetch(`${base}/shots`),
                    fetch(`${base}/shots/cena02/shot02`, { method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ prompt: `QA concorrente ${i}` }) }),
                    fetch(`${base}/shots`),
                ]);
                for (const x of r) out.push({ status: x.status, detail: x.ok ? '' : (await x.json().catch(() => ({}))).detail || '' });
            }
            return out;
        }""", _base(ctx))
        ruins = [r for r in respostas if r["status"] >= 400]
        ev = H.evidencia(page, ctx, "animate-concorrencia", full_page=False)
        return H.verifica(not ruins, f"{len(respostas)} requisições simultâneas, todas 2xx",
                          f"{len(ruins)} de {len(respostas)} requisições falharam: {ruins[:3]}", ev)
    finally:
        _restaura(page, ctx, snap)


@caso("C-ANIMATE-28", "campanha sem storyboard: estado vazio aponta a etapa 4 e a importação segue disponível", pid="vazio")
def sem_storyboard(page, ctx):
    vazio = (page.locator("#anShots .empty").text_content() or "").strip()
    drop = page.locator("#anDrop").count()
    conta = (page.locator("#anCandCount").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "animate-vazio")
    return H.verifica("storyboard" in vazio.lower() and drop == 1 and conta == "0 vídeos",
                      f"vazio='{vazio[:60]}' · drop e contador presentes",
                      f"vazio='{vazio}' drop={drop} contador='{conta}'", ev)
