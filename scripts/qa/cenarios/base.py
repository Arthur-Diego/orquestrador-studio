"""Casos da etapa 3 — Imagem base (`studio/etapas/base/view.html|view.js|router.py`).

Três painéis: 01 o prompt escrito pelo bot (junção referência × mood, proveniência, geração via
CLI da situação), 02 a marca do rótulo e 03 a cadeia situação → rótulo → upscale (stepper,
importação por upload/Downloads/histórico, geração paga via CLI e fechamento da imagem base).

O `claude` e o `higgsfield` da rodada são os fakes de `scripts/qa/fakes/` (offline): o bot devolve
um prompt `[QA-FAKE]` e cada geração "custa" 7 créditos e produz um PNG sintético.
"""
from __future__ import annotations

import base64
import json
import shutil

from scripts.qa import harness as H

TELA = "base"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)

JSON_H = {"content-type": "application/json"}
BOARD_NOME = "QA Base Mood"


# ---------- helpers locais (harness.py é compartilhado: nada de helper novo lá) ----------
def _post(page, ctx, path: str, corpo: dict | None = None):
    kw = {"data": json.dumps(corpo), "headers": JSON_H} if corpo is not None else {}
    return H.api(page, ctx, "post", path, **kw)


def _abrir(page, ctx, pid: str | None = None) -> None:
    """Abre a etapa GARANTINDO remontagem (a SPA só remonta quando o hash muda)."""
    H.abrir_tela(page, ctx, "overview", pid)
    H.abrir_tela(page, ctx, TELA, pid)


def _descartavel(page, ctx, nome: str) -> str:
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


def _zerar_base(ctx, pid: str) -> None:
    """Estado determinístico: esvazia `base/` da campanha DESCARTÁVEL e recria o layout."""
    root = ctx.projeto(pid)
    shutil.rmtree(root / "base", ignore_errors=True)
    (root / "base").mkdir(parents=True, exist_ok=True)


def _board_curado(page, ctx) -> dict:
    """Board da biblioteca com curadoria — fonte alternativa de mood no seletor do painel 01."""
    for b in H.api(page, ctx, "get", "/api/moodboards").json():
        if b["name"] == BOARD_NOME and b["count"] >= 2:
            return b
    r = _post(page, ctx, "/api/moodboards", {"name": BOARD_NOME, "note": "board do qa-studio (etapa 3)"})
    mbid = r.json()["id"] if r.status < 400 else "qa-base-mood"
    for nome, cor in (("base-mood-a", (40, 200, 160)), ("base-mood-b", (180, 80, 40))):
        p = H.png_temp(ctx, nome, color=cor)
        H.api(page, ctx, "post", f"/api/moodboards/{mbid}/import/upload",
              multipart={"files": {"name": p.name, "mimeType": "image/png", "buffer": p.read_bytes()}})
    ids = [c["id"] for c in H.api(page, ctx, "get", f"/api/moodboards/{mbid}/candidates").json()]
    _post(page, ctx, f"/api/moodboards/{mbid}/select", {"ids": ids, "note": ""})
    return next(b for b in H.api(page, ctx, "get", "/api/moodboards").json() if b["id"] == mbid)


def _cands(page, ctx, pid: str) -> list[dict]:
    return H.api(page, ctx, "get", f"/api/projects/{pid}/base/candidates").json()["candidates"]


def _tiles(page):
    return page.locator("#baseGallery .card")


def _passos_do_modal(page, timeout_ms: int = 6000) -> list[str]:
    """Textos dos passos do modal de progresso — capturados antes de ele se autofechar."""
    try:
        page.wait_for_selector(".modal.progress-modal .prog-steps", timeout=timeout_ms)
        return page.evaluate("""() => [...document.querySelectorAll('.modal.progress-modal .prog-step')]
            .map(li => (li.textContent || '').trim())""")
    except Exception:  # noqa: BLE001 — modal rápido demais não invalida o resultado da ação
        return []


def _passo_situacao(page) -> None:
    """Fixa o passo ativo em "situação".

    Obrigatório antes de olhar o painel 01: `load()` move o passo ativo para o 1º passo sem
    escolha (na campanha do seed, "rótulo") e, a partir daí, qualquer re-render do card troca o
    prompt da situação pela instrução de rótulo (ver C-BASE-33).
    """
    page.locator("#baseChain [data-step=situation]").click()
    page.wait_for_timeout(400)


def _confirmar_custo(page, aceitar: bool) -> str:
    """Espera o modal de custo (`ui.confirmCost`), lê a estimativa e clica Cancelar/Gerar."""
    m = H.modal(page)
    m.wait_for(timeout=20000)
    texto = (m.text_content() or "").strip()
    botoes = m.locator(".modal-actions button")
    botoes.nth(1 if aceitar else 0).click()
    return texto


# ---------- painel 01: o prompt da aula ----------
@caso("C-BASE-01", "chip do bot reflete a disponibilidade do Claude em /base/prompts")
def chip_bot(page, ctx):
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts").json()
    txt = (page.locator("#baseClaude").text_content() or "").strip()
    classe = page.locator("#baseClaude").get_attribute("class") or ""
    esperado = "bot: claude ok" if api["claude"] else "bot: sem claude"
    ev = H.evidencia(page, ctx, "base-chip-bot", full_page=False)
    return H.verifica(txt == esperado and ("ok" in classe) == bool(api["claude"]),
                      f"chip='{txt}'", f"chip='{txt}' classe='{classe}' api.claude={api['claude']}", ev)


@caso("C-BASE-02", "tira de referências e preview grande mostram as escolhidas na etapa 1")
def referencias(page, ctx):
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts").json()
    ids = page.locator("#refGallery .card").evaluate_all("els => els.map(e => e.dataset.ref)")
    sel = page.locator("#refGallery .card.sel").evaluate_all("els => els.map(e => e.dataset.ref)")
    hero = page.locator("#baseRefHero img").count()
    quebradas = page.locator("#refGallery img, #baseRefHero img").evaluate_all(
        "els => els.filter(i => i.complete && i.naturalWidth === 0).length")
    ev = H.evidencia(page, ctx, "base-referencias")
    return H.verifica(ids == [r["ref_id"] for r in api["refs"]] and sel == [api["refs"][0]["ref_id"]]
                      and hero == 1 and quebradas == 0,
                      f"{len(ids)} referências, 1ª selecionada, hero preenchido",
                      f"tira={ids} api={[r['ref_id'] for r in api['refs']]} selecionada={sel} "
                      f"hero={hero} imagens quebradas={quebradas}", ev)


@caso("C-BASE-03", "clicar noutra referência troca a seleção, o preview e o prompt exibido")
def trocar_referencia(page, ctx):
    cards = page.locator("#refGallery .card")
    if cards.count() < 2:
        return H.Resultado.bloqueado("a campanha do seed tem menos de 2 referências escolhidas")
    _passo_situacao(page)
    alvo = cards.nth(1).get_attribute("data-ref")
    cards.nth(1).click()
    page.wait_for_timeout(400)
    sel = page.locator("#refGallery .card.sel").evaluate_all("els => els.map(e => e.dataset.ref)")
    chave = page.locator("#basePrompts textarea").get_attribute("data-k")
    hero_alt = page.locator("#baseRefHero img").get_attribute("alt") or ""
    ev = H.evidencia(page, ctx, "base-troca-referencia")
    return H.verifica(sel == [alvo] and chave == f"p:{alvo}" and alvo in hero_alt,
                      f"referência {alvo} selecionada",
                      f"selecionadas={sel} textarea data-k='{chave}' hero alt='{hero_alt}'", ev)


@caso("C-BASE-04", "card único de prompt mostra o prompt da referência selecionada")
def card_prompt(page, ctx):
    _passo_situacao(page)
    page.locator("#refGallery .card").first.click()
    page.wait_for_timeout(400)
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts").json()
    ref = api["refs"][0]
    rotulo = (page.locator("#basePrompts .eyebrow").first.text_content() or "").strip()
    n = page.locator("#basePrompts .prompt").count()
    texto = page.locator("#basePrompts textarea").input_value()
    ev = H.evidencia(page, ctx, "base-card-prompt")
    return H.verifica(n == 1 and texto == ref["prompt"] and "situação" in rotulo,
                      f"1 card '{rotulo}' com o prompt da referência",
                      f"cards={n} rótulo='{rotulo}' texto='{texto[:60]}' api='{ref['prompt'][:60]}'", ev)


@caso("C-BASE-05", "junção mostra a equação referência + mood → prompt com a paleta da campanha")
def juncao(page, ctx):
    _passo_situacao(page)
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts").json()
    ref_thumb = page.locator("#baseJunction .bs-fuse .bs-fuse-thumb").count()
    celulas = page.locator("#baseJunction .bs-fuse-mood .mm-cell").count()
    saida = (page.locator("#baseJunction .bs-fuse-out").text_content() or "").strip()
    cores = page.locator("#baseJunction .swatches .sw").evaluate_all("els => els.map(e => e.title)")
    ev = H.evidencia(page, ctx, "base-juncao")
    return H.verifica(ref_thumb == 1 and celulas == min(len(api["mood_files"]), 4)
                      and saida == "prompt" and cores == api["palette"]["colors"],
                      f"equação com {celulas} imagens de mood e {len(cores)} cores",
                      f"thumb_ref={ref_thumb} células={celulas} (mood={len(api['mood_files'])}) "
                      f"saída='{saida}' cores={cores} api={api['palette']['colors']}", ev)


@caso("C-BASE-06", "seletor de fonte do mood lista a campanha e os boards da biblioteca")
def mood_source(page, ctx):
    _board_curado(page, ctx)
    _abrir(page, ctx)
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/mood-sources").json()
    opcoes = page.locator("#moodSource option").evaluate_all(
        "els => els.map(e => ({v: e.value, t: e.textContent.trim()}))")
    esperado = [f"Mood da campanha ({api['campaign']['count']} img)"] + [
        f"Board: {b['name']} ({b['count']} img) [extensão]" for b in api["boards"]]
    ev = H.evidencia(page, ctx, "base-mood-source", full_page=False)
    return H.verifica([o["t"] for o in opcoes] == esperado and opcoes[0]["v"] == ""
                      and len(api["boards"]) >= 1,
                      f"{len(opcoes)} fontes de mood",
                      f"opções={[o['t'] for o in opcoes]} esperado={esperado}", ev)


@caso("C-BASE-07", "escolher um board como fonte de mood repinta o mosaico com as imagens dele")
def trocar_mood_source(page, ctx):
    b = _board_curado(page, ctx)
    _abrir(page, ctx)
    _passo_situacao(page)
    antes = page.locator("#baseJunction .bs-fuse-mood .mm-cell").count()
    page.locator("#moodSource").select_option(b["id"])
    page.wait_for_timeout(900)
    depois = page.locator("#baseJunction .bs-fuse-mood .mm-cell").count()
    srcs = page.locator("#baseJunction .bs-fuse-mood .mm-cell img").evaluate_all(
        "els => els.map(i => i.getAttribute('src'))")
    quebradas = page.locator("#baseJunction .bs-fuse-mood img").evaluate_all(
        "els => els.filter(i => i.complete && i.naturalWidth === 0).length")
    ev = H.evidencia(page, ctx, "base-mood-source-board")
    return H.verifica(depois == min(b["count"], 4) and all("/mbfiles/" in s for s in srcs) and quebradas == 0,
                      f"mosaico do board com {depois} imagens (campanha tinha {antes})",
                      f"antes={antes} depois={depois} board.count={b['count']} srcs={srcs} "
                      f"quebradas={quebradas}", ev)


@caso("C-BASE-08", "'De onde vem cada parte' nasce recolhido e abre com a proveniência do prompt")
def proveniencia(page, ctx):
    det = page.locator("#baseProvenance details.bs-prov-det")
    if not det.count():
        api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts").json()
        return H.Resultado.falha(
            f"bloco de proveniência ausente (provenance da 1ª referência = {api['refs'][0]['provenance']})",
            H.evidencia(page, ctx, "base-proveniencia-ausente"))
    fechado = det.evaluate("el => el.open")
    det.locator("summary").click()
    page.wait_for_timeout(300)
    aberto = det.evaluate("el => el.open")
    linhas = page.locator("#baseProvenance .prov-line").count()
    chips = [t.strip() for t in page.locator("#baseProvenance .bs-chip").all_text_contents()]
    ev = H.evidencia(page, ctx, "base-proveniencia")
    return H.verifica(fechado is False and aberto is True and linhas >= 1,
                      f"{linhas} linha(s) de proveniência: {chips}",
                      f"open inicial={fechado} após clique={aberto} linhas={linhas} chips={chips}", ev)


@caso("C-BASE-09", "'Gerar prompt' abre o modal de fases e traz o texto escrito pelo bot")
def gerar_prompt(page, ctx):
    _passo_situacao(page)
    antes = len(H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts/history").json())
    page.locator("#promptInstruction").fill("")
    page.locator("#btnPrompt").click()
    passos = _passos_do_modal(page)
    fechou = H.esperar_modal_sumir(page, 60000)
    t = H.esperar_toast(page, "prompt")
    page.wait_for_timeout(600)
    texto = page.locator("#basePrompts textarea").input_value()
    hist = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts/history").json()
    ev = H.evidencia(page, ctx, "base-gerar-prompt")
    return H.verifica(len(passos) >= 2 and fechou and "[QA-FAKE" in texto and len(hist) == antes + 1
                      and hist[0]["source"] == "claude",
                      f"modal com {len(passos)} passos e prompt do bot (toast='{t}')",
                      f"passos={passos} fechou={fechou} texto='{texto[:70]}' "
                      f"histórico {antes}→{len(hist)} source={hist[0].get('source') if hist else None}", ev)


@caso("C-BASE-10", "'Gerar sem viés' usa sessão nova e registra no_bias no histórico")
def gerar_sem_vies(page, ctx):
    antes = len(H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts/history").json())
    page.locator("#btnPromptNoBias").click()
    passos = _passos_do_modal(page)
    fechou = H.esperar_modal_sumir(page, 60000)
    page.wait_for_timeout(600)
    hist = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts/history").json()
    rotulo = (page.locator("#btnPromptNoBias").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "base-gerar-sem-vies")
    return H.verifica(len(hist) == antes + 1 and hist[0]["no_bias"] is True and fechou
                      and rotulo == "Gerar sem viés"
                      and any("sess" in p.lower() for p in passos),
                      f"histórico com no_bias (passos={passos})",
                      f"passos={passos} fechou={fechou} histórico {antes}→{len(hist)} "
                      f"no_bias={hist[0].get('no_bias') if hist else None} botão='{rotulo}'", ev)


@caso("C-BASE-11", "a instrução digitada vai junto ao bot e fica registrada no histórico")
def instrucao(page, ctx):
    texto = "lata de energético sobre a neve"
    page.locator("#promptInstruction").fill(texto)
    page.locator("#btnPrompt").click()
    _passos_do_modal(page)
    H.esperar_modal_sumir(page, 60000)
    page.wait_for_timeout(600)
    hist = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts/history").json()
    page.locator("#promptInstruction").fill("")
    return H.verifica(bool(hist) and hist[0]["instruction"] == texto and hist[0]["no_bias"] is False,
                      "instrução gravada no histórico",
                      f"histórico[0].instruction='{hist[0].get('instruction') if hist else None}'")


@caso("C-BASE-12", "botão 'Copiar' do card de prompt confirma a cópia na própria linha")
def copiar_prompt(page, ctx):
    permissao = page.evaluate("""async () => { try {
        return (await navigator.permissions.query({name: 'clipboard-write'})).state;
      } catch (e) { return 'indisponivel'; } }""")
    btn = page.locator("#basePrompts button.copy").first
    btn.click()
    page.wait_for_timeout(700)
    eco = (page.locator("#basePrompts .prompt .ok").first.text_content() or "").strip()
    ev = H.evidencia(page, ctx, "base-copiar-prompt", full_page=False)
    if eco != "copiado ✓" and permissao != "granted":
        return H.Resultado.bloqueado(
            "o Chromium do harness não concede `clipboard-write` (permissão="
            f"'{permissao}') e o `H.Navegador` não chama `grant_permissions`. Observado: "
            "o handler do card usa `navigator.clipboard.writeText` sem `catch` nem o fallback "
            "de `Studio.ui.copy`, então o usuário não recebe retorno nenhum quando a cópia falha.",
            ev)
    return H.verifica(eco == "copiado ✓", f"eco='{eco}'",
                      f"eco='{eco}' (esperado 'copiado ✓'); permissão clipboard-write='{permissao}'", ev)


@caso("C-BASE-13", "histórico de prompts guarda referência, modo e proveniência de cada geração")
def historico(page, ctx):
    hist = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts/history").json()
    if not hist:
        return H.Resultado.falha("histórico vazio — rode C-BASE-09 antes")
    e = hist[0]
    refs = {r["ref_id"] for r in
            H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts").json()["refs"]}
    campos = {k: e.get(k) for k in ("ref_id", "mode", "source", "created")}
    return H.verifica(e.get("ref_id") in refs and e.get("mode") in ("images", "brief", "template")
                      and isinstance(e.get("provenance"), dict) and len(hist) <= 50,
                      f"{len(hist)} entradas; topo={campos}",
                      f"topo={campos} refs conhecidas={sorted(refs)} provenance={type(e.get('provenance'))}")


# ---------- painel 02: marca do rótulo ----------
@caso("C-BASE-14", "'Salvar marca' persiste nome e descrição da marca do rótulo")
def salvar_marca(page, ctx):
    original = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/brand").json()
    try:
        page.locator("#brandName").fill("QA Marca")
        page.locator("#brandDesc").fill("logo em traço fino")
        page.locator("#btnBrand").click()
        t = H.esperar_toast(page, "marca salva")
        page.wait_for_timeout(600)
        api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/brand").json()
        disco = json.loads((ctx.projeto(ctx.pid_cheio) / "base" / "brand.json").read_text())
        ev = H.evidencia(page, ctx, "base-marca", full_page=False)
        return H.verifica(api == {"name": "QA Marca", "description": "logo em traço fino"}
                          and disco["name"] == "QA Marca" and bool(t),
                          f"marca gravada (toast='{t}')", f"api={api} disco={disco} toast='{t}'", ev)
    finally:   # o seed depende da marca original para o prompt de rótulo
        _post(page, ctx, f"/api/projects/{ctx.pid_cheio}/base/brand", original)


@caso("C-BASE-15", "'Salvar marca' sem nome mostra o erro da aula e não grava nada")
def marca_sem_nome(page, ctx):
    original = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/brand").json()
    page.locator("#brandName").fill("")
    page.locator("#btnBrand").click()
    t = H.esperar_toast(page, "nome da marca")
    page.wait_for_timeout(500)
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/brand").json()
    ev = H.evidencia(page, ctx, "base-marca-sem-nome", full_page=False)
    return H.verifica(bool(t) and api == original, f"erro amigável: '{t}'",
                      f"toast='{t}' marca antes={original} depois={api}", ev)


@caso("C-BASE-16", "no passo 'rótulo' o card de prompt vira a instrução de troca de rótulo")
def prompt_rotulo(page, ctx):
    _abrir(page, ctx)          # remonta: o `labelPrompt` do JS é cache da última carga
    api = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/prompts").json()
    if not api["label_prompt_ready"]:
        return H.Resultado.bloqueado("campanha do seed sem marca salva — sem prompt de rótulo")
    _passo_situacao(page)
    page.locator("#baseChain [data-step=label]").click()
    page.wait_for_timeout(400)
    rotulo = (page.locator("#basePrompts .eyebrow").first.text_content() or "").strip()
    texto = page.locator("#basePrompts textarea").input_value()
    chave = page.locator("#basePrompts textarea").get_attribute("data-k")
    juncao = page.locator("#baseJunction").inner_html().strip()
    ev = H.evidencia(page, ctx, "base-prompt-rotulo")
    return H.verifica(chave == "label" and texto == api["label_prompt"] and "rótulo" in rotulo
                      and juncao == "",
                      f"card '{rotulo}' com a instrução de rótulo",
                      f"data-k='{chave}' rótulo='{rotulo}' texto='{texto[:60]}' "
                      f"api='{(api['label_prompt'] or '')[:60]}' junção='{juncao[:40]}'", ev)


# ---------- painel 03: cadeia situação → rótulo → upscale ----------
@caso("C-BASE-17", "stepper tem os 3 passos da aula, com 'done' no escolhido e 'on' no ativo")
def stepper(page, ctx):
    cands = _cands(page, ctx, ctx.pid_cheio)
    escolhidos = {c["kind"] for c in cands if c["selected"]}
    passos = page.locator("#baseChain [data-step]").evaluate_all(
        "els => els.map(e => ({k: e.dataset.step, c: e.className}))")
    ativos = [p["k"] for p in passos if " on" in f" {p['c']}"]
    prontos = {p["k"] for p in passos if "done" in p["c"]}
    ev = H.evidencia(page, ctx, "base-stepper", full_page=False)
    return H.verifica([p["k"] for p in passos] == ["situation", "label", "upscale"]
                      and prontos == escolhidos and len(ativos) == 1,
                      f"passos ok; done={sorted(prontos)} ativo={ativos}",
                      f"passos={passos} escolhidos_api={sorted(escolhidos)} ativos={ativos}", ev)


@caso("C-BASE-18", "clicar num passo do stepper troca o passo ativo e o rótulo do botão do CLI")
def trocar_passo(page, ctx):
    page.locator("#baseChain [data-step=upscale]").click()
    page.wait_for_timeout(300)
    ativo = page.locator("#baseChain .st.on").get_attribute("data-step")
    botao = (page.locator("#btnBaseCli").text_content() or "").strip()
    page.locator("#baseChain [data-step=situation]").click()
    page.wait_for_timeout(300)
    ativo2 = page.locator("#baseChain .st.on").get_attribute("data-step")
    botao2 = (page.locator("#btnBaseCli").text_content() or "").strip()
    return H.verifica(ativo == "upscale" and botao == "Gerar upscale via CLI"
                      and ativo2 == "situation" and botao2 == "Gerar situação via CLI",
                      f"'{botao}' → '{botao2}'",
                      f"ativo={ativo} botão='{botao}'; depois ativo={ativo2} botão='{botao2}'")


@caso("C-BASE-19", "Enter num passo focado do stepper também troca o passo ativo (teclado)")
def stepper_teclado(page, ctx):
    page.locator("#baseChain [data-step=situation]").click()
    page.wait_for_timeout(250)
    alvo = page.locator("#baseChain [data-step=label]")
    alvo.focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(300)
    ativo = page.locator("#baseChain .st.on").get_attribute("data-step")
    return H.verifica(ativo == "label", "Enter trocou o passo ativo",
                      f"passo ativo={ativo} (role={alvo.get_attribute('role')} "
                      f"tabindex={alvo.get_attribute('tabindex')})")


@caso("C-BASE-20", "upload no painel 03 importa a imagem no passo ativo do stepper")
def upload(page, ctx):
    pid = _descartavel(page, ctx, "QA Base Upload")
    _zerar_base(ctx, pid)
    _abrir(page, ctx, pid)
    p = H.png_temp(ctx, "base-upload", color=(90, 140, 220))
    H.upload(page, "#baseUpload", p)
    t = H.esperar_toast(page, "importada")
    page.wait_for_timeout(800)
    cands = _cands(page, ctx, pid)
    disco = H.arquivos(ctx.projeto(pid), "base/candidates/*.png") + \
        H.arquivos(ctx.projeto(pid), "base/candidates/*.jpg")
    ev = H.evidencia(page, ctx, "base-upload")
    return H.verifica(len(cands) == 1 and cands[0]["kind"] == "situation" and _tiles(page).count() == 1
                      and len(disco) == 1 and bool(t),
                      f"1 candidata de situação (toast='{t}')",
                      f"api={[(c['id'], c['kind']) for c in cands]} tiles={_tiles(page).count()} "
                      f"disco={disco} toast='{t}'", ev)


@caso("C-BASE-21", "arrastar sobre a área de drop do painel 03 importa igual ao upload")
def drop(page, ctx):
    pid = _descartavel(page, ctx, "QA Base Drop")
    _zerar_base(ctx, pid)
    _abrir(page, ctx, pid)
    b64 = base64.b64encode(H.png_temp(ctx, "base-drop", color=(200, 200, 60)).read_bytes()).decode()
    over = page.evaluate("""(b64) => {
      const bin = atob(b64), arr = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
      const dt = new DataTransfer();
      dt.items.add(new File([arr], 'qa-base-drop.png', {type: 'image/png'}));
      const el = document.querySelector('#baseDrop');
      el.dispatchEvent(new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: dt}));
      const over = el.classList.contains('over');
      el.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt}));
      return over;
    }""", b64)
    t = H.esperar_toast(page, "importada")
    page.wait_for_timeout(800)
    cands = _cands(page, ctx, pid)
    ev = H.evidencia(page, ctx, "base-drop")
    return H.verifica(over and len(cands) == 1 and bool(t), f"drop importou 1 candidata (toast='{t}')",
                      f"classe .over no dragover={over} candidatas={len(cands)} toast='{t}'", ev)


@caso("C-BASE-22", "'Importar da pasta Downloads' traz a mídia recente da pasta da rodada")
def downloads(page, ctx):
    pid = _descartavel(page, ctx, "QA Base Downloads")
    _zerar_base(ctx, pid)
    pasta = H.api(page, ctx, "get", "/api/mood/downloads-folder").json()
    from pathlib import Path
    destino = Path(pasta["folder"])
    destino.mkdir(parents=True, exist_ok=True)
    origem = H.png_temp(ctx, "base-downloads", color=(30, 200, 90))
    alvo = destino / "qa-base-downloads.png"
    alvo.write_bytes(origem.read_bytes())
    alvo.touch()
    _abrir(page, ctx, pid)
    page.locator("#btnBaseDownloads").click()
    t = H.esperar_toast(page, "importada")
    page.wait_for_timeout(900)
    cands = _cands(page, ctx, pid)
    fontes = {c["source"] for c in cands}
    ev = H.evidencia(page, ctx, "base-downloads")
    return H.verifica(len(cands) >= 1 and fontes == {"downloads"} and bool(t),
                      f"{len(cands)} candidata(s) de {destino} (toast='{t}')",
                      f"pasta={pasta} candidatas={len(cands)} fontes={fontes} toast='{t}'", ev)


@caso("C-BASE-23", "'Importar do histórico Higgsfield' traz os itens que o CLI devolve")
def historico_hf(page, ctx):
    pid = _descartavel(page, ctx, "QA Base Historico")
    _zerar_base(ctx, pid)
    _abrir(page, ctx, pid)
    page.locator("#btnBaseHistory").click()
    t = H.esperar_toast(page, "importada")
    page.wait_for_timeout(1500)
    cands = _cands(page, ctx, pid)
    fontes = {c["source"] for c in cands}
    prompts = {(c.get("prompt") or "")[:9] for c in cands}
    ev = H.evidencia(page, ctx, "base-historico-hf")
    return H.verifica(len(cands) == 3 and fontes == {"higgsfield"} and prompts == {"[QA-FAKE]"},
                      f"3 itens do histórico (toast='{t}')",
                      f"candidatas={len(cands)} fontes={fontes} prompts={prompts} toast='{t}'", ev)


@caso("C-BASE-24", "'Usar como imagem base' só habilita depois de marcar uma candidata")
def gate_select(page, ctx):
    pid = _descartavel(page, ctx, "QA Base Upload")
    _zerar_base(ctx, pid)
    _abrir(page, ctx, pid)
    vazio_desabilitado = page.locator("#btnBaseSelect").is_disabled()
    H.upload(page, "#baseUpload", H.png_temp(ctx, "base-upload", color=(90, 140, 220)))
    H.esperar_toast(page, "importada")
    page.wait_for_timeout(800)
    ainda = page.locator("#btnBaseSelect").is_disabled()
    _tiles(page).first.click()
    page.wait_for_timeout(300)
    habilitado = page.locator("#btnBaseSelect").is_enabled()
    _tiles(page).first.click()          # desmarca: o caso não fecha a imagem base
    page.wait_for_timeout(300)
    voltou = page.locator("#btnBaseSelect").is_disabled()
    return H.verifica(vazio_desabilitado and ainda and habilitado and voltou,
                      "gate do botão respeita a marcação",
                      f"sem candidatas={vazio_desabilitado} sem marcar={ainda} "
                      f"marcado habilitado={habilitado} desmarcado={voltou}")


@caso("C-BASE-25", "'Usar como imagem base' grava base_final.png + base.md e mostra o card final")
def fechar_base(page, ctx):
    pid = _descartavel(page, ctx, "QA Base Fechar")
    _zerar_base(ctx, pid)
    _abrir(page, ctx, pid)
    H.upload(page, "#baseUpload", H.png_temp(ctx, "base-fechar", color=(160, 60, 200)))
    H.esperar_toast(page, "importada")
    page.wait_for_timeout(800)
    _tiles(page).first.click()
    page.locator("#btnBaseSelect").click()
    t = H.esperar_toast(page, "imagem base")
    page.wait_for_timeout(900)
    root = ctx.projeto(pid)
    api = H.api(page, ctx, "get", f"/api/projects/{pid}/base/candidates").json()
    card = page.locator("#baseFinalCard .bs-final").count()
    chip = (page.locator("#baseFinalCard .chip").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "base-fechar")
    return H.verifica((root / "base" / "base_final.png").exists() and (root / "base" / "base.md").exists()
                      and api["final"] == "base/base_final.png" and card == 1 and "final" in chip,
                      f"imagem base fechada (toast='{t}')",
                      f"base_final={(root / 'base' / 'base_final.png').exists()} "
                      f"base.md={(root / 'base' / 'base.md').exists()} api.final={api['final']} "
                      f"card={card} chip='{chip}' toast='{t}'", ev)


@caso("C-BASE-26", "cada candidata vira um tile com o selo do passo e ✓ na escolhida")
def tiles_galeria(page, ctx):
    cands = _cands(page, ctx, ctx.pid_cheio)
    rotulos = {"situation": "situação", "label": "rótulo", "upscale": "upscale"}
    badges = [t.strip() for t in page.locator("#baseGallery .card .src").all_text_contents()]
    esperado = [rotulos[c["kind"]] + (" ✓" if c["selected"] else "") for c in cands]
    ev = H.evidencia(page, ctx, "base-galeria")
    return H.verifica(_tiles(page).count() == len(cands) and badges == esperado,
                      f"{len(badges)} tiles: {badges}",
                      f"tiles={_tiles(page).count()} api={len(cands)} badges={badges} esperado={esperado}", ev)


@caso("C-BASE-27", "duplo clique numa candidata abre a imagem em tamanho real")
def abrir_imagem(page, ctx):
    cands = _cands(page, ctx, ctx.pid_cheio)
    if not cands:
        return H.Resultado.bloqueado("campanha do seed sem candidatas na etapa 3")
    url = ""
    try:
        with page.context.expect_page(timeout=6000) as nova:
            _tiles(page).first.dblclick()
        aba = nova.value
        url = aba.url
        aba.close()
    except Exception:  # noqa: BLE001 — sem aba nova o caso falha com o diagnóstico abaixo
        pass
    ev = H.evidencia(page, ctx, "base-abrir-imagem")
    return H.verifica(bool(url) and cands[0]["file"] in url, f"abriu {url.rsplit('/', 1)[-1]}",
                      "nenhuma aba nova abriu (url=" + (url or "—") + "): o 1º clique do duplo "
                      "clique chama `render()`, que reescreve o `innerHTML` de #baseGallery — o "
                      "`dblclick` passa a ter como alvo o container e `closest('.card')` dá null", ev)


@caso("C-BASE-28", "'Gerar via CLI' mostra o custo antes de gastar e cancelar não gera nada")
def custo_cancelar(page, ctx):
    antes = len(_cands(page, ctx, ctx.pid_cheio))
    page.locator("#baseChain [data-step=situation]").click()
    page.wait_for_timeout(300)
    page.locator("#btnBaseCli").click()
    texto = _confirmar_custo(page, aceitar=False)
    page.wait_for_timeout(900)
    depois = len(_cands(page, ctx, ctx.pid_cheio))
    custo = (page.locator("#baseCliCost").text_content() or "").strip()
    job = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/base/job").json()
    ev = H.evidencia(page, ctx, "base-custo-cancelar")
    return H.verifica(depois == antes and "créditos" in texto and "créditos" in custo
                      and job.get("state") != "running",
                      f"custo exibido ('{custo}') e nada gerado",
                      f"modal='{texto[:120]}' rodapé='{custo}' candidatas {antes}→{depois} "
                      f"job={job.get('state')}", ev)


@caso("C-BASE-29", "'Gerar via CLI' do painel 01 gera a situação e mostra o antes → depois")
def gerar_cli(page, ctx):
    antes = len(_cands(page, ctx, ctx.pid_cheio))
    page.locator("#btnBasePanel01Cli").click()
    texto = _confirmar_custo(page, aceitar=True)
    passos = _passos_do_modal(page, 20000)
    fechou = H.esperar_modal_sumir(page, 120000)
    page.wait_for_timeout(1200)
    cands = _cands(page, ctx, ctx.pid_cheio)
    novas = [c for c in cands if c["source"] == "cli" and c["kind"] == "situation" and c.get("job_id")]
    pares = page.locator("#baseGenResult .pair").count()
    custo = (page.locator("#basePanel01CliCost").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "base-gerar-cli")
    return H.verifica(len(cands) == antes + 1 and novas and fechou and pares >= 1,
                      f"1 candidata gerada; {pares} par(es) antes → depois ({custo})",
                      f"candidatas {antes}→{len(cands)} novas_cli={len(novas)} passos={passos} "
                      f"fechou={fechou} pares={pares} custo='{custo}' modal='{texto[:80]}'", ev)


@caso("C-BASE-30", "sem referência da etapa 1, o CLI avisa em vez de estourar erro cru")
def cli_sem_insumo(page, ctx):
    pid = _descartavel(page, ctx, "QA Base Sem Ref")
    _zerar_base(ctx, pid)
    _abrir(page, ctx, pid)
    page.locator("#btnBaseCli").click()
    t = H.esperar_toast(page)
    page.wait_for_timeout(900)
    custo = (page.locator("#baseCliCost").text_content() or "").strip()
    modais = page.locator(".modal[role=dialog]").count()
    job = H.api(page, ctx, "get", f"/api/projects/{pid}/base/job").json()
    cands = _cands(page, ctx, pid)
    ev = H.evidencia(page, ctx, "base-cli-sem-insumo")
    return H.verifica(bool(t) and modais == 0 and not cands and job.get("state") != "running",
                      f"aviso sem modal nem job (toast='{t}', rodapé='{custo}')",
                      f"toast='{t}' rodapé='{custo}' modais={modais} job={job.get('state')} "
                      f"candidatas={len(cands)}", ev)


@caso("C-BASE-31", "campanha sem referência mostra o gate da etapa 1 no painel do prompt", pid="vazio")
def gate_etapa1(page, ctx):
    txt = (page.locator("#basePrompts .empty").text_content() or "").strip()
    refs = page.locator("#refGallery .card").count()
    r = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_vazio}/base/prompts")
    ev = H.evidencia(page, ctx, "base-gate-etapa1")
    return H.verifica(r.status == 422 and "etapa 1" in txt.lower() and refs == 0,
                      f"gate exibido: '{txt[:70]}'",
                      f"HTTP={r.status} texto='{txt[:90]}' tiles de referência={refs}", ev)


@caso("C-BASE-32", "o botão de Downloads informa a pasta e a janela de tempo no tooltip")
def tooltip_downloads(page, ctx):
    pasta = H.api(page, ctx, "get", "/api/mood/downloads-folder").json()
    title = page.locator("#btnBaseDownloads").get_attribute("title") or ""
    visivel = page.locator("#main").inner_text()
    return H.verifica(pasta["folder"] in title and "120 min" in title and pasta["folder"] not in visivel,
                      f"tooltip='{title}'",
                      f"title='{title}' pasta={pasta} (caminho aparece no corpo da tela? "
                      f"{pasta['folder'] in visivel})")


@caso("C-BASE-33", "ao abrir a etapa, o card de prompt e o passo ativo do stepper concordam")
def card_x_stepper(page, ctx):
    _abrir(page, ctx)
    ativo = page.locator("#baseChain .st.on").get_attribute("data-step")
    rotulo = (page.locator("#basePrompts .eyebrow").first.text_content() or "").strip()
    chave = page.locator("#basePrompts textarea").get_attribute("data-k")
    juncao = page.locator("#baseJunction").inner_html().strip() != ""
    ev = H.evidencia(page, ctx, "base-card-x-stepper")
    esperado = {"situation": "situação", "label": "rótulo", "upscale": "upscale"}[ativo]
    return H.verifica(esperado in rotulo,
                      f"passo ativo '{ativo}' e card '{rotulo}'",
                      f"o stepper abre em '{ativo}' (load() avança para o 1º passo sem escolha) mas o "
                      f"card do painel 01 continua no prompt de situação: rótulo='{rotulo}' "
                      f"data-k='{chave}' junção visível={juncao}. Basta clicar numa referência ou "
                      f"gerar um prompt para o card virar a instrução de rótulo sem o usuário ter "
                      f"tocado no stepper (renderPrompt lê `step`, mas load() muda `step` sem "
                      f"chamar renderPrompt)", ev)
