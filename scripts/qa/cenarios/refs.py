"""Casos da etapa 1 — Referências (`studio/etapas/refs/view.html|view.js|router.py`).

Comandos cobertos: painel 01 (marca validada, sugestão de termos, máx. por termo, "ver o
navegador", buscar) e painel 02 (grade de candidatas, multi-seleção, salvar seleção, upload por
link/drop, filtros por termo e por fonte, "limpar filtros").

Regra da rodada offline: `#btnSearch` sai para a rede do Pinterest — só o caminho de erro
*client-side* (nenhum termo) é exercido; o caminho feliz fica BLOQUEADO (ver `C-REFS-10`).
"""
from __future__ import annotations

import base64
import json
import shutil

from scripts.qa import harness as H

TELA = "refs"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)

JSON_H = {"content-type": "application/json"}


# ---------- helpers locais (harness.py é compartilhado: nada de helper novo lá) ----------
def _post(page, ctx, path: str, corpo: dict):
    return H.api(page, ctx, "post", path, data=json.dumps(corpo), headers=JSON_H)


def _put(page, ctx, path: str, corpo: dict):
    return H.api(page, ctx, "put", path, data=json.dumps(corpo), headers=JSON_H)


def _descartavel(page, ctx, nome: str, product: str = "produto de teste") -> str:
    """Campanha descartável (criada uma vez por rodada) — nunca mexe no `pid_cheio`.

    A SPA só conhece as campanhas carregadas no boot: depois de criar, recarrega a página.
    """
    for p in H.api(page, ctx, "get", "/api/projects").json():
        if p["name"] == nome:
            return p["id"]
    r = _post(page, ctx, "/api/projects", {"name": nome, "product": product, "vibe": ""})
    if r.status >= 400:
        raise RuntimeError(f"POST /api/projects → {r.status}: {r.text()[:200]}")
    pid = r.json()["id"]
    page.reload()
    H.esperar_tela(page)
    return pid


def _zerar_refs(ctx, pid: str) -> None:
    """Estado determinístico do caso: esvazia `refs/` da campanha DESCARTÁVEL e recria o layout
    (`PROJECT_LAYOUT`) que a criação da campanha e o reset garantem."""
    root = ctx.projeto(pid)
    shutil.rmtree(root / "refs", ignore_errors=True)
    for sub in ("refs/candidates/thumbs", "refs/brainstorming"):
        (root / sub).mkdir(parents=True, exist_ok=True)


def _subir(page, ctx, pid: str, nome: str, cor) -> None:
    """Sobe uma imagem como candidata via a API que a tela usa (setup de fixture)."""
    p = H.png_temp(ctx, nome, color=cor)
    H.api(page, ctx, "post", f"/api/projects/{pid}/refs/import/upload",
          multipart={"files": {"name": p.name, "mimeType": "image/png", "buffer": p.read_bytes()}})


def _com_filtros(page, ctx) -> str:
    """Campanha com 2 candidatas de termos e fontes DIFERENTES (a API de upload só grava
    `term=upload`/`source=upload`, então o fixture é escrito no disco depois)."""
    pid = _descartavel(page, ctx, "QA Refs Filtros")
    _zerar_refs(ctx, pid)
    _subir(page, ctx, pid, "refs-filtro-a", (210, 40, 40))
    _subir(page, ctx, pid, "refs-filtro-b", (40, 170, 90))
    f = ctx.projeto(pid) / "refs" / "candidates" / "candidates.json"
    dados = json.loads(f.read_text())
    dados[0]["term"], dados[0]["source"] = "qa termo a", "pinterest"
    dados[1]["term"], dados[1]["source"] = "qa termo b", "upload"
    f.write_text(json.dumps(dados, ensure_ascii=False, indent=1))
    H.abrir_tela(page, ctx, TELA, pid)
    return pid


def _cards(page):
    return page.locator("#gallery .card")


# ---------- painel 01: buscar no Pinterest ----------
@caso("C-REFS-01", "chip de sessão e rótulo do botão de login refletem /api/pinterest/login")
def sessao(page, ctx):
    s = H.api(page, ctx, "get", "/api/pinterest/login").json()
    chip = (page.locator("#loginState").text_content() or "").strip()
    btn = (page.locator("#btnLogin").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "refs-sessao", full_page=False)
    if s.get("state") == "idle":
        return H.verifica(chip == "sessão: ?" and btn == "Refazer login", f"chip='{chip}' botão='{btn}'",
                          f"state=idle mas chip='{chip}' botão='{btn}'", ev)
    return H.verifica(bool(chip), f"chip='{chip}' (state={s.get('state')})",
                      f"chip vazio para state={s.get('state')}", ev)


@caso("C-REFS-02", "'Salvar marca validada' persiste a marca e mostra a nota + toast")
def salvar_marca(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Marca")
    H.abrir_tela(page, ctx, TELA, pid)
    page.locator("#brand").fill("Red Bull")
    page.locator("#btnSaveBrand").click()
    t = H.esperar_toast(page, "marca validada salva")
    page.wait_for_timeout(300)
    nota = (page.locator("#brandSaved").text_content() or "").strip()
    api = H.api(page, ctx, "get", f"/api/projects/{pid}/refs/validated-brand").json()
    ev = H.evidencia(page, ctx, "refs-marca-salva", full_page=False)
    return H.verifica(api.get("brand") == "Red Bull" and nota == "marca validada salva" and bool(t),
                      f"marca='{api.get('brand')}' nota='{nota}'",
                      f"api={api} nota='{nota}' toast='{t}'", ev)


@caso("C-REFS-03", "a marca validada volta preenchida no campo ao reabrir a etapa")
def marca_persiste(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Marca")
    _put(page, ctx, f"/api/projects/{pid}/refs/validated-brand", {"brand": "Nike"})
    H.abrir_tela(page, ctx, TELA, pid)
    v = page.locator("#brand").input_value()
    return H.verifica(v == "Nike", "campo preenchido com a marca persistida",
                      f"#brand='{v}' esperado 'Nike'")


@caso("C-REFS-04", "salvar com o campo vazio limpa a marca validada")
def limpar_marca(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Marca")
    _put(page, ctx, f"/api/projects/{pid}/refs/validated-brand", {"brand": "Nike"})
    H.abrir_tela(page, ctx, TELA, pid)
    page.locator("#brand").fill("")
    page.locator("#btnSaveBrand").click()
    t = H.esperar_toast(page, "limpa")
    api = H.api(page, ctx, "get", f"/api/projects/{pid}/refs/validated-brand").json()
    return H.verifica(api.get("brand") == "" and bool(t), f"marca limpa (toast='{t}')",
                      f"api={api} toast='{t}'")


@caso("C-REFS-05", "'Sugerir termos' preenche o textarea com os termos da marca validada")
def sugerir(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Marca")
    _put(page, ctx, f"/api/projects/{pid}/refs/validated-brand", {"brand": "Red Bull"})
    H.abrir_tela(page, ctx, TELA, pid)
    page.locator("#terms").fill("")
    page.locator("#btnSuggest").click()
    page.wait_for_function("() => (document.querySelector('#terms').value || '').trim().length > 0")
    linhas = [x for x in page.locator("#terms").input_value().split("\n") if x.strip()]
    esperado = H.api(page, ctx, "get",
                     f"/api/suggest-terms?product=&vibe=&brand=Red%20Bull&pid={pid}").json()
    ev = H.evidencia(page, ctx, "refs-sugerir", full_page=False)
    return H.verifica(linhas == esperado and len(linhas) >= 12 and all(x.startswith("Red Bull") for x in linhas),
                      f"{len(linhas)} termos sugeridos a partir da marca",
                      f"tela={linhas[:3]}… ({len(linhas)}) api={esperado[:3]}… ({len(esperado)})", ev)


@caso("C-REFS-06", "'Sugerir termos' sem marca e sem produto avisa em vez de chamar a API")
def sugerir_sem_insumo(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Sem Produto", product="")
    H.abrir_tela(page, ctx, TELA, pid)
    page.locator("#brand").fill("")
    page.locator("#terms").fill("")
    page.locator("#btnSuggest").click()
    t = H.esperar_toast(page, "marca validada ou o produto")
    valor = page.locator("#terms").input_value()
    ev = H.evidencia(page, ctx, "refs-sugerir-sem-insumo", full_page=False)
    return H.verifica(bool(t) and not valor.strip(), f"toast='{t}' e textarea intacto",
                      f"toast='{t}' textarea='{valor[:60]}'", ev)


@caso("C-REFS-07", "'máx. por termo' declara faixa 5–100 e marca valor fora dela como inválido")
def max_por_termo(page, ctx):
    el = page.locator("#maxPer")
    minimo, maximo, valor = el.get_attribute("min"), el.get_attribute("max"), el.input_value()
    el.fill("500")
    over = page.evaluate("() => document.querySelector('#maxPer').validity.rangeOverflow")
    el.fill("1")
    under = page.evaluate("() => document.querySelector('#maxPer').validity.rangeUnderflow")
    el.fill("30")
    ok = page.evaluate("() => document.querySelector('#maxPer').validity.valid")
    return H.verifica(minimo == "5" and maximo == "100" and over and under and ok,
                      f"faixa {minimo}–{maximo} (default {valor})",
                      f"min={minimo} max={maximo} over={over} under={under} valido(30)={ok}")


@caso("C-REFS-08", "'ver o navegador' é um checkbox desmarcado por padrão e alterna pelo rótulo")
def headed(page, ctx):
    chk = page.locator("#headed")
    inicial = chk.is_checked()
    page.locator("label.inline:has(#headed)").click()
    depois = chk.is_checked()
    page.locator("label.inline:has(#headed)").click()
    volta = chk.is_checked()
    return H.verifica(inicial is False and depois is True and volta is False,
                      "desmarcado por padrão e alterna pelo rótulo",
                      f"inicial={inicial} após clique={depois} após 2º clique={volta}")


@caso("C-REFS-09", "'Buscar e baixar' sem termo avisa e não dispara job nem modal")
def buscar_sem_termo(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Marca")
    H.abrir_tela(page, ctx, TELA, pid)
    page.locator("#terms").fill("   \n  ")
    page.locator("#btnSearch").click()
    t = H.esperar_toast(page, "termo")
    page.wait_for_timeout(600)
    job = H.api(page, ctx, "get", f"/api/projects/{pid}/refs/job").json()
    modal = page.locator(".modal[role=dialog]").count()
    habilitado = page.locator("#btnSearch").is_enabled()
    ev = H.evidencia(page, ctx, "refs-busca-sem-termo", full_page=False)
    return H.verifica(bool(t) and job.get("state") == "idle" and modal == 0 and habilitado,
                      f"toast='{t}', job idle, UI livre",
                      f"toast='{t}' job={job.get('state')} modais={modal} botão habilitado={habilitado}", ev)


@caso("C-REFS-10", "caminho feliz de 'Buscar e baixar' (scrape real do Pinterest)")
def buscar_real(page, ctx):
    return H.Resultado.bloqueado(
        "o scrape usa rede externa (i.pinimg.com/pinterest.com) e a sessão real do usuário — "
        "proibido na rodada offline; só o caminho de erro client-side é coberto (C-REFS-09)")


@caso("C-REFS-11", "coluna 'Último scrape' nasce derivada das candidatas, sem dado de exemplo")
def ultimo_scrape(page, ctx):
    cands = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/refs/candidates").json()
    job = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/refs/job").json()
    txt = (page.locator("#scrapeCount").text_content() or "").strip()
    largura = page.evaluate("() => document.querySelector('#progress .bar').style.width || '0%'")
    esperado = f"{len(cands)} candidatas" if cands else "—"
    if job.get("last_job"):
        lj = job["last_job"]
        esperado = f"{lj.get('total', 0)}/{lj.get('meta', 0)}" if lj.get("meta") else esperado
    ev = H.evidencia(page, ctx, "refs-ultimo-scrape", full_page=False)
    return H.verifica(txt == esperado, f"'{txt}' (barra {largura})",
                      f"rótulo='{txt}' esperado='{esperado}' (job={job.get('state')} barra={largura})", ev)


# ---------- painel 02: escolher o que você gosta ----------
@caso("C-REFS-12", "contador do painel 02 bate com /refs/candidates (candidatas × escolhidas)")
def contador(page, ctx):
    cands = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/refs/candidates").json()
    txt = (page.locator("#counts").text_content() or "").strip()
    esperado = f"{len(cands)} candidatas · {sum(1 for c in cands if c['selected'])} escolhidas"
    return H.verifica(txt == esperado, txt, f"chip='{txt}' esperado='{esperado}'")


@caso("C-REFS-13", "cada candidata vira um tile com selo de fonte e legenda do termo")
def tiles(page, ctx):
    cands = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/refs/candidates").json()
    n = _cards(page).count()
    fontes = page.locator("#gallery .card .src").all_text_contents()
    termos = page.locator("#gallery .card .term").all_text_contents()
    ev = H.evidencia(page, ctx, "refs-tiles")
    return H.verifica(n == len(cands) and sorted(fontes) == sorted(c["source"] for c in cands)
                      and sorted(termos) == sorted(c["term"] for c in cands),
                      f"{n} tiles com fonte e termo",
                      f"tiles={n} api={len(cands)} fontes={fontes} termos={termos}", ev)


@caso("C-REFS-14", "clicar num tile alterna a marcação e atualiza o contador (sem salvar)")
def marcar(page, ctx):
    antes = (page.locator("#counts").text_content() or "").strip()
    card = _cards(page).first
    marcado = "sel" in (card.get_attribute("class") or "")
    card.click()
    page.wait_for_timeout(200)
    depois = (page.locator("#counts").text_content() or "").strip()
    virou = "sel" in (card.get_attribute("class") or "")
    disco = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/refs/candidates").json()
    card.click()          # desfaz: o caso não persiste nada
    page.wait_for_timeout(200)
    n_disco = sum(1 for c in disco if c["selected"])
    return H.verifica(virou is not marcado and antes != depois and n_disco == len(disco),
                      f"'{antes}' → '{depois}'",
                      f"classe {marcado}→{virou} contador '{antes}'→'{depois}' "
                      f"(disco continua com {n_disco} escolhidas de {len(disco)})")


@caso("C-REFS-15", "Espaço num tile focado alterna a marcação (acessibilidade por teclado)")
def marcar_teclado(page, ctx):
    card = _cards(page).first
    antes = "sel" in (card.get_attribute("class") or "")
    card.focus()
    page.keyboard.press(" ")
    page.wait_for_timeout(200)
    depois = "sel" in (card.get_attribute("class") or "")
    card.focus()
    page.keyboard.press(" ")
    page.wait_for_timeout(200)
    return H.verifica(depois is not antes, "Espaço alterna a marcação",
                      f"antes sel={antes} depois sel={depois} (tabindex={card.get_attribute('tabindex')})")


@caso("C-REFS-16", "'Salvar seleção' copia as escolhidas para refs/brainstorming e avisa")
def salvar_selecao(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Selecao")
    _zerar_refs(ctx, pid)
    _subir(page, ctx, pid, "refs-sel-a", (60, 60, 200))
    _subir(page, ctx, pid, "refs-sel-b", (200, 160, 40))
    H.abrir_tela(page, ctx, TELA, pid)
    _cards(page).first.click()
    page.locator("#btnSave").click()
    t = H.esperar_toast(page, "brainstorming")
    page.wait_for_timeout(500)
    root = ctx.projeto(pid)
    disco = H.arquivos(root, "refs/brainstorming/*")
    api = H.api(page, ctx, "get", f"/api/projects/{pid}/refs/candidates").json()
    ev = H.evidencia(page, ctx, "refs-salvar-selecao")
    return H.verifica(len(disco) == 1 and sum(1 for c in api if c["selected"]) == 1
                      and (root / "refs" / "README.md").exists() and bool(t),
                      f"1 escolhida em brainstorming (toast='{t}')",
                      f"disco={disco} escolhidas_api={sum(1 for c in api if c['selected'])} toast='{t}'", ev)


@caso("C-REFS-17", "desmarcar tudo e salvar remove os arquivos de refs/brainstorming")
def desmarcar_tudo(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Selecao")
    _zerar_refs(ctx, pid)
    _subir(page, ctx, pid, "refs-sel-a", (60, 60, 200))
    _post(page, ctx, f"/api/projects/{pid}/refs/select",
          {"ids": [c["id"] for c in H.api(page, ctx, "get", f"/api/projects/{pid}/refs/candidates").json()]})
    H.abrir_tela(page, ctx, TELA, pid)
    antes = H.arquivos(ctx.projeto(pid), "refs/brainstorming/*")
    for i in range(_cards(page).count()):
        _cards(page).nth(i).click()
    page.locator("#btnSave").click()
    H.esperar_toast(page, "brainstorming")
    page.wait_for_timeout(500)
    depois = H.arquivos(ctx.projeto(pid), "refs/brainstorming/*")
    return H.verifica(len(antes) == 1 and depois == [], "brainstorming esvaziado",
                      f"antes={antes} depois={depois}")


@caso("C-REFS-18", "'trazer imagens' + upload adiciona candidatas em refs/candidates")
def upload(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Upload")
    _zerar_refs(ctx, pid)
    H.abrir_tela(page, ctx, TELA, pid)
    p = H.png_temp(ctx, "refs-upload", color=(120, 40, 160))
    H.upload(page, "#refsUpload", p)
    t = H.esperar_toast(page, "adicionadas")
    page.wait_for_timeout(500)
    api = H.api(page, ctx, "get", f"/api/projects/{pid}/refs/candidates").json()
    disco = H.arquivos(ctx.projeto(pid), "refs/candidates/*.jpg")
    ev = H.evidencia(page, ctx, "refs-upload")
    return H.verifica(len(api) == 1 and len(disco) == 1 and _cards(page).count() == 1 and bool(t),
                      f"1 candidata importada (toast='{t}')",
                      f"api={len(api)} disco={disco} tiles={_cards(page).count()} toast='{t}'", ev)


@caso("C-REFS-19", "upload de arquivo que não é imagem é ignorado sem quebrar a tela")
def upload_invalido(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Upload Ruim")
    _zerar_refs(ctx, pid)
    H.abrir_tela(page, ctx, TELA, pid)
    lixo = ctx.run_dir / "fixtures" / "nao-e-imagem.png"
    lixo.parent.mkdir(exist_ok=True)
    lixo.write_bytes(b"isto nao e um PNG")
    H.upload(page, "#refsUpload", lixo)
    t = H.esperar_toast(page, "adicionadas")
    page.wait_for_timeout(500)
    api = H.api(page, ctx, "get", f"/api/projects/{pid}/refs/candidates").json()
    vazio = page.locator("#gallery .empty").count()
    ev = H.evidencia(page, ctx, "refs-upload-invalido")
    return H.verifica(api == [] and vazio == 1 and t.startswith("0 "),
                      f"nada importado (toast='{t}')",
                      f"api={len(api)} empty-state={vazio} toast='{t}'", ev)


@caso("C-REFS-20", "'trazer imagens' abre o seletor de arquivos do painel 02")
def btn_bring(page, ctx):
    with page.expect_file_chooser() as fc:
        page.locator("#btnBring").click()
    chooser = fc.value
    alvo = chooser.element.get_attribute("id")
    return H.verifica(alvo == "refsUpload" and chooser.is_multiple(),
                      "abre #refsUpload (múltiplo)", f"input='{alvo}' multiple={chooser.is_multiple()}")


@caso("C-REFS-21", "campanha sem candidatas mostra o vazio com o atalho 'traga imagens'", pid="vazio")
def vazio(page, ctx):
    empty = page.locator("#gallery .empty")
    txt = (empty.text_content() or "").strip()
    filtros = (page.locator("#refsFilters").inner_html() or "").strip()
    with page.expect_file_chooser() as fc:
        empty.locator("[data-bring]").click()
    alvo = fc.value.element.get_attribute("id")
    ev = H.evidencia(page, ctx, "refs-vazio")
    return H.verifica("Nenhuma candidata ainda" in txt and filtros == "" and alvo == "refsUpload",
                      "vazio com atalho de upload e sem filtros",
                      f"texto='{txt[:80]}' filtros='{filtros[:40]}' input='{alvo}'", ev)


@caso("C-REFS-22", "arrastar imagem sobre o painel 02 marca `.over` e importa como candidata")
def drop(page, ctx):
    pid = _descartavel(page, ctx, "QA Refs Drop")
    _zerar_refs(ctx, pid)
    H.abrir_tela(page, ctx, TELA, pid)
    b64 = base64.b64encode(H.png_temp(ctx, "refs-drop", color=(20, 160, 160)).read_bytes()).decode()
    over = page.evaluate("""(b64) => {
      const bin = atob(b64), arr = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
      const dt = new DataTransfer();
      dt.items.add(new File([arr], 'qa-drop.png', {type: 'image/png'}));
      const el = document.querySelector('#refsPick');
      el.dispatchEvent(new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: dt}));
      const over = el.classList.contains('over');
      el.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt}));
      return over;
    }""", b64)
    t = H.esperar_toast(page, "adicionadas")
    page.wait_for_timeout(500)
    api = H.api(page, ctx, "get", f"/api/projects/{pid}/refs/candidates").json()
    classe = page.locator("#refsPick").get_attribute("class") or ""
    ev = H.evidencia(page, ctx, "refs-drop")
    return H.verifica(over and len(api) == 1 and "over" not in classe and bool(t),
                      f"drop importou 1 candidata (toast='{t}')",
                      f"over_no_dragover={over} api={len(api)} classe_final='{classe}' toast='{t}'", ev)


@caso("C-REFS-23", "filtros por termo e por fonte só aparecem quando há mais de um valor")
def filtros_aparecem(page, ctx):
    sem = page.locator("#refsFilters").inner_html().strip()      # pid_cheio: 1 termo, 1 fonte
    _com_filtros(page, ctx)
    grupos = page.locator("#refsFilters .rf-fgroup").count()
    rotulos = [t.strip() for t in page.locator("#refsFilters .rf-flabel").all_text_contents()]
    chks = page.locator("#refsFilters input[data-filter]").count()
    ev = H.evidencia(page, ctx, "refs-filtros")
    return H.verifica(sem == "" and grupos == 2 and rotulos == ["termos", "fontes"] and chks == 4,
                      "2 grupos (termos, fontes) com 4 marcações",
                      f"cheio='{sem[:40]}' grupos={grupos} rótulos={rotulos} checkboxes={chks}", ev)


@caso("C-REFS-24", "marcar um termo filtra a grade; somar uma fonte é interseção entre grupos")
def filtros_filtram(page, ctx):
    _com_filtros(page, ctx)
    total = _cards(page).count()
    page.locator("#refsFilters input[data-filter=term][value='qa termo a']").check()
    page.wait_for_timeout(200)
    so_termo = _cards(page).count()
    page.locator("#refsFilters input[data-filter=source][value='upload']").check()
    page.wait_for_timeout(200)
    interseccao = _cards(page).count()
    contador = (page.locator("#counts").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "refs-filtros-interseccao")
    return H.verifica(total == 2 and so_termo == 1 and interseccao == 0 and contador.startswith("2 candidatas"),
                      "termo=1 tile, termo∩fonte=0 tiles, contador segue global",
                      f"total={total} só_termo={so_termo} interseção={interseccao} contador='{contador}'", ev)


@caso("C-REFS-25", "'limpar filtros' desmarca tudo, some do DOM e devolve a grade inteira")
def limpar_filtros(page, ctx):
    _com_filtros(page, ctx)
    page.locator("#refsFilters input[data-filter=term][value='qa termo a']").check()
    page.wait_for_timeout(200)
    com = _cards(page).count()
    tinha_botao = page.locator("#refsFilters .rf-clear").count()
    page.locator("#refsFilters .rf-clear").click()
    page.wait_for_timeout(200)
    depois = _cards(page).count()
    marcadas = page.locator("#refsFilters input[data-filter]:checked").count()
    sobrou = page.locator("#refsFilters .rf-clear").count()
    return H.verifica(tinha_botao == 1 and com == 1 and depois == 2 and marcadas == 0 and sobrou == 0,
                      "filtros limpos e grade completa",
                      f"botão_antes={tinha_botao} com_filtro={com} depois={depois} "
                      f"marcadas={marcadas} botão_depois={sobrou}")


@caso("C-REFS-26", "filtros são por campanha: trocar de projeto zera as marcações")
def filtros_por_projeto(page, ctx):
    _com_filtros(page, ctx)
    page.locator("#refsFilters input[data-filter=term][value='qa termo a']").check()
    page.wait_for_timeout(200)
    H.abrir_tela(page, ctx, TELA, ctx.pid_cheio)
    limpo = page.locator("#refsFilters").inner_html().strip()
    _com_filtros(page, ctx)
    marcadas = page.locator("#refsFilters input[data-filter]:checked").count()
    return H.verifica(limpo == "" and marcadas == 0, "marcações zeradas ao trocar de campanha",
                      f"filtros no pid_cheio='{limpo[:40]}' marcadas ao voltar={marcadas}")


@caso("C-REFS-27", "a seleção salva volta marcada ao reabrir a etapa (persistência)")
def persistencia(page, ctx):
    cands = H.api(page, ctx, "get", f"/api/projects/{ctx.pid_cheio}/refs/candidates").json()
    esperado = {c["id"] for c in cands if c["selected"]}
    H.abrir_tela(page, ctx, TELA, ctx.pid_cheio)
    na_tela = set(page.locator("#gallery .card.sel").evaluate_all("els => els.map(e => e.dataset.id)"))
    return H.verifica(na_tela == esperado, f"{len(na_tela)} tiles marcados como no disco",
                      f"tela={sorted(na_tela)} disco={sorted(esperado)}")
