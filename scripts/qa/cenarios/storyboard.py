"""Casos da etapa 4 — Storyboard (`studio/etapas/storyboard/view.js`, ADR-015/018/021/022).

A tela junta quatro painéis na mesma rota:
- 01 ideias a partir da imagem base (instrução montada + importação dos resultados da Higgsfield);
- 02 a história em cenas (galeria de keyframes por cena + prompt/animação POR FOTO, ADR-022);
- 03 ângulos por cena (lista de cenas + a cena do produto da aula 013);
- 04 painel da cena aberta (prompts de ângulo, candidatos, ordem dos frames).

Convenções deste módulo:
- o `pid_cheio` do seed NUNCA é destruído: as ações aditivas (importar ideias, salvar a mesma
  seleção de frames) rodam nele; o que reescreve `scenes.json` (reordenar, add/remover cena,
  anexar fotos, gerar vídeo) roda numa campanha descartável criada por `_projeto_qa`;
- cada caso é idempotente: ou repõe o estado que mexeu, ou só acrescenta.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from scripts.qa import harness as H

TELA = "storyboard"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)

NOME_QA = "QA Storyboard 4"
INSTRUCAO = "Make the climber even smaller and more realistic"


# ======================================================================================
# helpers locais (o harness é compartilhado: nada é adicionado lá)
# ======================================================================================
def _json(page, ctx, method: str, path: str, body=None):
    kw = {}
    if body is not None:
        kw = {"data": json.dumps(body), "headers": {"content-type": "application/json"}}
    return H.api(page, ctx, method, path, **kw)


def _sb(pid: str, sufixo: str = "") -> str:
    return f"/api/projects/{pid}/storyboard{sufixo}"


def _ang(pid: str, sufixo: str = "") -> str:
    return f"/api/projects/{pid}/storyboard/angles{sufixo}"


def _downloads(ctx) -> Path:
    return Path(H.carregar_env(ctx.run_dir)["STUDIO_DOWNLOADS"])


def _png_unico(ctx, prefixo: str) -> Path:
    """PNG com CONTEÚDO inédito a cada chamada — o ingest deduplica por hash, então repetir a
    mesma cor faria o caso passar na 1ª rodada e falhar ('já estavam importadas') na 2ª."""
    n = int(time.time() * 1000) % 8_000_000
    cor = (n % 200 + 30, (n // 200) % 200 + 30, (n // 40_000) % 200 + 30)
    return H.png_temp(ctx, f"{prefixo}-{n}", cor)


def _upload_png(page, ctx, url: str, nome: str, cor, campo: str = "files"):
    """POST multipart de UM png sintético (o endpoint aceita `files` ou `file`)."""
    p = H.png_temp(ctx, nome, cor)
    return H.api(page, ctx, "post", url,
                 multipart={campo: {"name": f"{nome}.png", "mimeType": "image/png", "buffer": p.read_bytes()}})


def _ideias(page, ctx, pid: str) -> list[dict]:
    return _json(page, ctx, "get", _sb(pid, "/candidates")).json()["ideas"]


def _garantir_ideias(page, ctx, pid: str, n: int = 2) -> list[dict]:
    ideias = _ideias(page, ctx, pid)
    tentativas = 0
    while len(ideias) < n and tentativas < n + 2:
        tentativas += 1
        _upload_png(page, ctx, _sb(pid, "/import/upload"), f"qa-ideia-{tentativas}",
                    (20 + 37 * tentativas % 200, 90, 200))
        ideias = _ideias(page, ctx, pid)
    return ideias


def _selecionar_ideias(page, ctx, pid: str, ids: list[str]) -> list[dict]:
    """Marca `ids` MANTENDO o que já estava selecionado (o endpoint recebe o conjunto inteiro)."""
    atuais = [c["id"] for c in _ideias(page, ctx, pid) if c["selected"]]
    todos = list(dict.fromkeys(atuais + ids))
    _json(page, ctx, "post", _sb(pid, "/candidates/select"), {"ids": todos})
    return _ideias(page, ctx, pid)


def _cenas(page, ctx, pid: str) -> list[dict]:
    return _json(page, ctx, "get", _sb(pid, "/scenes")).json()["scenes"]


def _salvar_cenas(page, ctx, pid: str, cenas: list[dict]):
    return _json(page, ctx, "put", _sb(pid, "/scenes"), {"scenes": cenas})


def _projeto_qa(page, ctx) -> str:
    """Campanha descartável (criada uma vez por rodada) com imagem base e 5 cenas com texto."""
    lista = H.api(page, ctx, "get", "/api/projects").json()
    achado = next((p for p in lista if p["name"] == NOME_QA), None)
    if achado:
        pid = achado["id"]
    else:
        r = _json(page, ctx, "post", "/api/projects", {"name": NOME_QA, "product": "energético", "vibe": "gelo neon"})
        pid = r.json()["id"]
    root = ctx.projeto(pid)
    (root / "base").mkdir(parents=True, exist_ok=True)
    dst = root / "base" / "base_final.png"
    if not dst.exists():
        shutil.copy2(ctx.projeto(ctx.pid_cheio) / "base" / "base_final.png", dst)
    cenas = _cenas(page, ctx, pid)
    if not any((c.get("text") or "").strip() for c in cenas):
        textos = ["começo qa", "descoberta qa", "ação qa", "ação 2 qa", "desfecho qa"]
        for c, t in zip(cenas, textos, strict=False):
            c["text"] = t
        _salvar_cenas(page, ctx, pid, cenas)
    page.reload()          # a SPA só conhece as campanhas carregadas no boot
    H.esperar_tela(page)
    return pid


def _cena_com_fotos(page, ctx, pid: str, idx: int = 0, n: int = 2) -> tuple[str, list[str]]:
    """Garante que a cena `idx` tenha `n` fotos (ideias selecionadas) salvas em scenes.json."""
    ideias = _garantir_ideias(page, ctx, pid, n)
    alvo = [c["id"] for c in ideias[:n]]
    ideias = _selecionar_ideias(page, ctx, pid, alvo)
    arquivos = [c["file"] for c in ideias if c["id"] in alvo]
    cenas = _cenas(page, ctx, pid)
    cenas[idx]["images"] = arquivos
    cenas[idx]["primary"] = arquivos[0]
    r = _salvar_cenas(page, ctx, pid, cenas)
    cena = r.json()["scenes"][idx]
    return cena["id"], cena["images"]


def _garantir_prompt_video(page, ctx, pid: str, sid: str, img: str) -> str:
    """Gera (via API) e persiste o prompt de vídeo da foto — pré-condição do 'Gerar animação'."""
    cenas = _cenas(page, ctx, pid)
    cena = next(c for c in cenas if c["id"] == sid)
    atual = (cena["photos"].get(img) or {}).get("video_prompt") or ""
    if atual:
        return atual
    r = _json(page, ctx, "post", _sb(pid, "/video-prompt"),
              {"scene_id": sid, "description": "the can falls into the snow",
               "frames": {"mode": "single", "image": img}})
    prompt = r.json()["prompt"]
    cena["photos"][img] = {"video_desc": "the can falls into the snow", "video_prompt": prompt, "videos": []}
    _salvar_cenas(page, ctx, pid, cenas)
    return prompt


def _linha_foto(page, sid: str, i: int = 0):
    return page.locator(f"#sbScenes .scene-row[data-sid='{sid}'] .sb-photorow").nth(i)


def _abrir_cena_angulos(page, ctx, sid: str) -> None:
    page.locator(f"#sceneList [data-scene='{sid}']").first.click()
    page.wait_for_timeout(900)


def _mp4s(ctx, pid: str, sid: str) -> list[str]:
    d = ctx.projeto(pid) / "storyboard" / sid / "video"
    return sorted(p.name for p in d.glob("*.mp4")) if d.exists() else []


# ======================================================================================
# painel 01 — ideias a partir da imagem base (aula 010)
# ======================================================================================
@caso("C-STORYBOARD-01", "painel 01 mostra a imagem base e o chip de contagem bate com a API")
def p01_estado(page, ctx):
    st = _json(page, ctx, "get", _sb(ctx.pid_cheio)).json()
    chip = (page.locator("#sbCounts").text_content() or "").strip()
    base_visivel = page.locator("#sbBase").is_visible()
    ev = H.evidencia(page, ctx, "sb-painel01")
    esperado = f"{st['ideas']} ideias · {st['selected']} escolhidas"
    return H.verifica(chip == esperado and base_visivel == st["has_base"],
                      f"chip='{chip}' base visível={base_visivel}",
                      f"chip='{chip}' esperado '{esperado}'; base visível={base_visivel} has_base={st['has_base']}", ev)


@caso("C-STORYBOARD-02", "#sbKind lista os modos de ideação de /instructions e o title segue o modo")
def p01_kind(page, ctx):
    meta = _json(page, ctx, "get", _sb(ctx.pid_cheio, "/instructions")).json()
    valores = page.locator("#sbKind option").evaluate_all("els => els.map(e => e.value)")
    page.locator("#sbKind").select_option("multishot")
    page.wait_for_timeout(200)
    dica = page.locator("#sbKind").get_attribute("title") or ""
    esperada = next(k["ui_hint"] for k in meta["kinds"] if k["kind"] == "multishot")
    page.locator("#sbKind").select_option(meta["kinds"][0]["kind"])
    return H.verifica(valores == [k["kind"] for k in meta["kinds"]] and dica == esperada,
                      f"{len(valores)} modos, title do multishot ok",
                      f"options={valores} esperado={[k['kind'] for k in meta['kinds']]}; title='{dica}' esperado='{esperada}'")


@caso("C-STORYBOARD-03", "#sbPreset preenche modo e texto com a fórmula da aula")
def p01_preset(page, ctx):
    meta = _json(page, ctx, "get", _sb(ctx.pid_cheio, "/instructions")).json()
    alvo = 2   # preset de inpaint (ponto-e-vírgula) — o mais sensível da lista
    page.locator("#sbPreset").select_option(str(alvo))
    page.wait_for_timeout(250)
    kind = page.locator("#sbKind").input_value()
    texto = page.locator("#sbText").input_value()
    p = meta["presets"][alvo]
    return H.verifica(kind == p["kind"] and texto == p["text"], f"preset '{p['label']}' aplicado",
                      f"kind='{kind}' (esperado {p['kind']}) texto='{texto[:60]}' esperado='{p['text'][:60]}'")


@caso("C-STORYBOARD-04", "#sbGen4 e #sbGen1 montam a instrução com o sufixo da aula e a dica de quantas gerar")
def p01_gen(page, ctx):
    page.locator("#sbKind").select_option("edit")
    page.locator("#sbText").fill(INSTRUCAO)
    page.locator("#sbGen4").click()
    t4 = H.esperar_toast(page, "4 varia")
    txt4 = (page.locator("#sbInstruction").text_content() or "").strip()
    page.wait_for_timeout(3300)          # o toast some sozinho (3,2 s) — evita ler o anterior
    page.locator("#sbGen1").click()
    t1 = H.esperar_toast(page, "1 varia")
    ev = H.evidencia(page, ctx, "sb-instrucao")
    ok = txt4.endswith("Keep everything else identical, realistic.") and INSTRUCAO in txt4 and bool(t4) and bool(t1)
    return H.verifica(ok, f"instrução='{txt4[:70]}…'",
                      f"instrução='{txt4}' toast4='{t4}' toast1='{t1}'", ev)


@caso("C-STORYBOARD-05", "#sbGen4 com texto vazio: erro amigável e instrução em repouso")
def p01_gen_vazio(page, ctx):
    page.reload()                    # remonta a etapa: a instrução volta ao texto de repouso
    H.esperar_tela(page)
    page.locator("#sbText").fill("")
    page.locator("#sbGen4").click()
    t = H.esperar_toast(page, "Escreva a instrução")
    txt = (page.locator("#sbInstruction").text_content() or "").strip()
    return H.verifica(bool(t) and txt.startswith("a instrução montada aparece aqui"),
                      f"toast='{t}'", f"toast='{t}' instrução='{txt[:80]}'")


@caso("C-STORYBOARD-06", "heurística 'uma instrução por vez': dois pedidos são recusados com sugestão")
def p01_uma_instrucao(page, ctx):
    page.locator("#sbKind").select_option("edit")
    page.locator("#sbText").fill("Remove the rope on the right. Make the can smaller.")
    page.locator("#sbGen4").click()
    t = H.esperar_toast(page, "Uma instrução por vez")
    ev = H.evidencia(page, ctx, "sb-uma-instrucao")
    return H.verifica("Remove the rope on the right" in t, f"toast='{t[:90]}…'",
                      f"toast='{t}' (esperado recusa citando o 1º pedido)", ev)


@caso("C-STORYBOARD-07", "#sbCopy: sem instrução avisa; com instrução copia e ecoa 'copiado ✓'")
def p01_copiar(page, ctx):
    try:
        page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=ctx.base)
    except Exception:  # noqa: BLE001 — sem permissão o teste do eco ainda vale
        pass
    page.reload()                    # remonta a etapa: começa sem instrução montada
    H.esperar_tela(page)
    page.locator("#sbCopy").click()
    t_sem = H.esperar_toast(page, "Monte a instrução")
    page.locator("#sbKind").select_option("edit")
    page.locator("#sbText").fill(INSTRUCAO)
    page.locator("#sbGen1").click()
    page.wait_for_timeout(600)
    page.locator("#sbCopy").click()
    page.wait_for_timeout(400)
    eco = (page.locator("#sbCopied").text_content() or "").strip()
    clip = ""
    try:
        clip = page.evaluate("navigator.clipboard.readText()")
    except Exception:  # noqa: BLE001
        clip = "(clipboard indisponível)"
    return H.verifica(bool(t_sem) and eco.startswith("copiado"),
                      f"toast sem instrução='{t_sem}' eco='{eco}' clipboard='{clip[:40]}'",
                      f"toast='{t_sem}' eco='{eco}' clipboard='{clip[:80]}'")


@caso("C-STORYBOARD-08", "#sbCounts abre o modal 'Importar ideias' com os três caminhos")
def p01_modal_importar(page, ctx):
    page.locator("#sbCounts").click()
    m = H.modal(page)
    m.wait_for()
    tem = {
        "drop": m.locator("#sbDrop").count() > 0,
        "downloads": m.locator("#sbBtnDownloads").count() > 0,
        "minutos": m.locator("#sbMinutes").input_value() if m.locator("#sbMinutes").count() else None,
        "historico": m.locator("#sbBtnHistory").count() > 0,
    }
    ev = H.evidencia(page, ctx, "sb-modal-importar", full_page=False)
    H.fechar_modal(page)
    return H.verifica(tem["drop"] and tem["downloads"] and tem["historico"] and tem["minutos"] == "120",
                      f"modal com {tem}", f"modal={tem}", ev)


@caso("C-STORYBOARD-09", "importar ideias por upload (modal) grava candidato em storyboard/candidates/")
def p01_import_upload(page, ctx):
    antes = len(_ideias(page, ctx, ctx.pid_cheio))
    page.locator("#sbCounts").click()
    m = H.modal(page)
    m.wait_for()
    png = _png_unico(ctx, "sb-upload")
    H.upload(page, "#sbUpload", png)
    t = H.esperar_toast(page, "ideias importadas")
    page.wait_for_timeout(600)
    depois = _ideias(page, ctx, ctx.pid_cheio)
    disco = H.arquivos(ctx.projeto(ctx.pid_cheio), "storyboard/candidates/*.png")
    chip = (page.locator("#sbCounts").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "sb-import-upload")
    return H.verifica(len(depois) == antes + 1 and len(disco) >= len(depois) - 0 and chip.startswith(f"{len(depois)} ideias"),
                      f"{antes}→{len(depois)} ideias, toast='{t}', {len(disco)} arquivos",
                      f"{antes}→{len(depois)} ideias; toast='{t}'; chip='{chip}'; disco={len(disco)}", ev)


@caso("C-STORYBOARD-10", "importar da pasta Downloads traz as imagens recentes")
def p01_import_downloads(page, ctx):
    dl = _downloads(ctx)
    dl.mkdir(parents=True, exist_ok=True)
    origem = _png_unico(ctx, "sb-dl")
    alvo = dl / origem.name
    shutil.copy2(origem, alvo)
    antes = len(_ideias(page, ctx, ctx.pid_cheio))
    page.locator("#sbCounts").click()
    H.modal(page).wait_for()
    page.locator("#sbBtnDownloads").click()
    t = H.esperar_toast(page, "recentes")
    page.wait_for_timeout(700)
    depois = len(_ideias(page, ctx, ctx.pid_cheio))
    alvo.unlink(missing_ok=True)
    ev = H.evidencia(page, ctx, "sb-import-downloads")
    return H.verifica(depois > antes and "de" in t, f"{antes}→{depois} ideias, toast='{t}'",
                      f"{antes}→{depois} ideias; toast='{t}'; pasta={dl}", ev)


@caso("C-STORYBOARD-11", "importar do histórico do CLI traz os jobs (fake higgsfield)")
def p01_import_historico(page, ctx):
    antes = len(_ideias(page, ctx, ctx.pid_cheio))
    page.locator("#sbCounts").click()
    H.modal(page).wait_for()
    page.locator("#sbBtnHistory").click()
    t = H.esperar_toast(page, "jobs", timeout_ms=20000)
    page.wait_for_timeout(800)
    depois = len(_ideias(page, ctx, ctx.pid_cheio))
    log = ctx.fakes_log()
    ev = H.evidencia(page, ctx, "sb-import-historico")
    return H.verifica(depois > antes and "generate list" in log,
                      f"{antes}→{depois} ideias, toast='{t}'",
                      f"{antes}→{depois} ideias; toast='{t}'; fakes.log tem 'generate list'? {'generate list' in log}", ev)


@caso("C-STORYBOARD-12", "arrastar imagem no painel 01 importa sem abrir o modal")
def p01_drop_painel(page, ctx):
    campo = page.locator("#sbIdeas > input[type=file]")
    if not campo.count():
        return H.Resultado.falha("ui.drop não criou o <input type=file> no painel #sbIdeas")
    antes = len(_ideias(page, ctx, ctx.pid_cheio))
    png = _png_unico(ctx, "sb-drop")
    campo.set_input_files(str(png))
    t = H.esperar_toast(page, "importadas")
    page.wait_for_timeout(600)
    depois = len(_ideias(page, ctx, ctx.pid_cheio))
    return H.verifica(depois == antes + 1, f"{antes}→{depois} ideias (toast='{t}')",
                      f"{antes}→{depois} ideias; toast='{t}'")


@caso("C-STORYBOARD-13", "geração paga de ideias pelo CLI (/cost + /generate) não tem comando na tela")
def p01_gerar_cli(page, ctx):
    botoes = page.locator("#sbIdeas button").evaluate_all(
        "els => els.map(e => (e.id || '') + ':' + (e.textContent || '').trim())")
    if any("crédito" in b.lower() or "gerar via cli" in b.lower() for b in botoes):
        return H.Resultado.falha(f"apareceu um comando pago no painel 01: {botoes}")
    return H.Resultado.bloqueado(
        "o router expõe POST /storyboard/cost, /generate e GET /storyboard/job (geração paga das "
        f"ideias), mas nenhum controle do painel 01 os aciona — botões presentes: {botoes}. "
        "Sem comando na UI não há como exercitar o caminho pago da ideação nem o modal de custo dele.")


# ======================================================================================
# painel 02 — a história em cenas (+ vídeo por foto, ADR-021/022)
# ======================================================================================
@caso("C-STORYBOARD-14", "painel 02 desenha uma cena por linha, com o momento do arco da aula")
def p02_lista(page, ctx):
    cenas = _cenas(page, ctx, ctx.pid_cheio)
    linhas = page.locator("#sbScenes .scene-row")
    momentos = page.locator("#sbScenes .scene-row .mom").all_text_contents()
    textos = page.locator("#sbScenes .scene-row textarea.sbTxt").evaluate_all("els => els.map(e => e.value)")
    esperado = ["começo", "descoberta", "ação", "ação", "desfecho"][:len(cenas)]
    ev = H.evidencia(page, ctx, "sb-painel02")
    return H.verifica(linhas.count() == len(cenas) and momentos == esperado
                      and textos == [c["text"] for c in cenas],
                      f"{linhas.count()} cenas, momentos={momentos}",
                      f"linhas={linhas.count()} cenas={len(cenas)} momentos={momentos} esperado={esperado} textos={textos}", ev)


@caso("C-STORYBOARD-15", "#sbAdd acrescenta a cena só no DOM (scenes.json só muda ao salvar)")
def p02_add(page, ctx):
    antes_dom = page.locator("#sbScenes .scene-row").count()
    antes_disco = len(_cenas(page, ctx, ctx.pid_cheio))
    page.locator("#sbAdd").click()
    page.wait_for_timeout(300)
    depois_dom = page.locator("#sbScenes .scene-row").count()
    depois_disco = len(_cenas(page, ctx, ctx.pid_cheio))
    H.abrir_tela(page, ctx, TELA, ctx.pid_cheio)     # descarta a cena não salva
    return H.verifica(depois_dom == antes_dom + 1 and depois_disco == antes_disco,
                      f"DOM {antes_dom}→{depois_dom}, disco estável em {depois_disco}",
                      f"DOM {antes_dom}→{depois_dom}; disco {antes_disco}→{depois_disco}")


@caso("C-STORYBOARD-16", "#sbSave grava o texto da cena em scenes.json e regrava storyboard.md")
def p02_salvar(page, ctx):
    original = _cenas(page, ctx, ctx.pid_cheio)
    md = ctx.projeto(ctx.pid_cheio) / "storyboard" / "storyboard.md"
    mtime = md.stat().st_mtime if md.exists() else 0
    marca = f"{original[0]['text']} · qa{int(time.time()) % 1000}"
    page.locator("#sbScenes .scene-row textarea.sbTxt").first.fill(marca)
    page.locator("#sbSave").click()
    t = H.esperar_toast(page, "cenas salvas")
    page.wait_for_timeout(500)
    depois = _cenas(page, ctx, ctx.pid_cheio)
    conteudo = md.read_text() if md.exists() else ""
    _salvar_cenas(page, ctx, ctx.pid_cheio, original)      # repõe o seed
    ev = H.evidencia(page, ctx, "sb-salvar-cenas")
    return H.verifica(depois[0]["text"] == marca and marca in conteudo and md.stat().st_mtime > mtime,
                      f"texto persistido e .md regravado (toast='{t}')",
                      f"disco='{depois[0]['text']}' esperado='{marca}'; no .md? {marca in conteudo}; toast='{t}'", ev)


@caso("C-STORYBOARD-17", "#sbRender regera o storyboard.md e abre o arquivo")
def p02_render(page, ctx):
    md = ctx.projeto(ctx.pid_cheio) / "storyboard" / "storyboard.md"
    antes = md.stat().st_mtime if md.exists() else 0
    page.wait_for_timeout(1100)      # o mtime tem resolução de 1 s no destino
    popup = None
    try:
        with page.context.expect_page(timeout=8000) as info:
            page.locator("#sbRender").click()
        popup = info.value
    except Exception:  # noqa: BLE001 — sem popup o resto do caso ainda vale
        page.locator("#sbRender").click()
    t = H.esperar_toast(page, "storyboard.md gerado")
    page.wait_for_timeout(400)
    url_popup = popup.url if popup else ""
    if popup:
        popup.close()
    depois = md.stat().st_mtime if md.exists() else 0
    return H.verifica(depois > antes and bool(t) and "storyboard.md" in url_popup,
                      f"md regravado e aberto em {url_popup.rsplit('/', 1)[-1]}",
                      f"mtime {antes}→{depois}; toast='{t}'; popup='{url_popup}'")


@caso("C-STORYBOARD-18", "#sbRender sem nenhuma cena escrita recusa com mensagem da aula", pid="vazio")
def p02_render_vazio(page, ctx):
    page.locator("#sbRender").click()
    t = H.esperar_toast(page, "Escreva pelo menos uma cena")
    ev = H.evidencia(page, ctx, "sb-render-vazio")
    return H.verifica(bool(t), f"toast='{t}'", f"toast='{t}' (esperado recusa 422 do /render)", ev)


@caso("C-STORYBOARD-19", "campanha sem imagem base: #sbGen4/#sbGen1 desabilitados e base escondida", pid="vazio")
def p02_sem_base(page, ctx):
    st = _json(page, ctx, "get", _sb(ctx.pid_vazio)).json()
    g4 = page.locator("#sbGen4").is_disabled()
    g1 = page.locator("#sbGen1").is_disabled()
    escondida = page.locator("#sbBase").is_hidden()
    ev = H.evidencia(page, ctx, "sb-sem-base")
    return H.verifica(not st["has_base"] and g4 and g1 and escondida,
                      "botões de instrução travados sem base",
                      f"has_base={st['has_base']} gen4_disabled={g4} gen1_disabled={g1} base_escondida={escondida}", ev)


@caso("C-STORYBOARD-20", "#sbReorder: ↑ no modal reordena as cenas e 'Salvar ordem' regrava scenes.json")
def p02_reordenar(page, ctx):
    pid = _projeto_qa(page, ctx)
    H.abrir_tela(page, ctx, TELA, pid)
    antes = [c["text"] for c in _cenas(page, ctx, pid)]
    page.locator("#sbReorder").click()
    m = H.modal(page)
    m.wait_for()
    itens = m.locator(".sb-reorder .sb-ro-item")
    if itens.count() < 2:
        H.fechar_modal(page)
        return H.Resultado.falha(f"modal de reordenação com {itens.count()} item(ns)")
    ev = H.evidencia(page, ctx, "sb-reordenar", full_page=False)
    itens.nth(1).locator(".sb-ro-up").click()          # sobe a 2ª cena
    page.wait_for_timeout(200)
    m.locator(".modal-actions button.primary").click()
    t = H.esperar_toast(page, "Ordem salva")
    page.wait_for_timeout(600)
    depois = [c["text"] for c in _cenas(page, ctx, pid)]
    esperado = [antes[1], antes[0]] + antes[2:]
    # repõe a ordem original (o caso é idempotente)
    cenas = _cenas(page, ctx, pid)
    volta = [cenas[1], cenas[0]] + cenas[2:]
    _salvar_cenas(page, ctx, pid, volta)
    return H.verifica(depois == esperado, f"ordem {antes[:2]} → {depois[:2]} (toast='{t}')",
                      f"antes={antes} depois={depois} esperado={esperado} toast='{t}'", ev)


@caso("C-STORYBOARD-21", "+ cena → salvar → ✕ → salvar volta ao número original de cenas")
def p02_add_remove_salvar(page, ctx):
    pid = _projeto_qa(page, ctx)
    H.abrir_tela(page, ctx, TELA, pid)
    n0 = len(_cenas(page, ctx, pid))
    page.locator("#sbAdd").click()
    page.wait_for_timeout(200)
    page.locator("#sbScenes .scene-row").last.locator("textarea.sbTxt").fill("cena extra qa")
    page.locator("#sbSave").click()
    H.esperar_toast(page, "cenas salvas")
    page.wait_for_timeout(500)
    n1 = len(_cenas(page, ctx, pid))
    page.locator("#sbScenes .scene-row").last.locator(".sbDel").click()
    page.wait_for_timeout(200)
    page.locator("#sbSave").click()
    H.esperar_toast(page, "cenas salvas")
    page.wait_for_timeout(500)
    n2 = len(_cenas(page, ctx, pid))
    return H.verifica(n1 == n0 + 1 and n2 == n0, f"{n0} → {n1} → {n2} cenas",
                      f"cenas {n0} → {n1} (após +cena) → {n2} (após ✕); esperado {n0}/{n0 + 1}/{n0}")


@caso("C-STORYBOARD-22", "'+ foto' abre o picker; marcar e Aplicar anexa as ideias como keyframes")
def p02_picker(page, ctx):
    pid = _projeto_qa(page, ctx)
    _garantir_ideias(page, ctx, pid, 2)
    cenas = _cenas(page, ctx, pid)
    cenas[1]["images"] = []
    cenas[1]["primary"] = None
    _salvar_cenas(page, ctx, pid, cenas)
    H.abrir_tela(page, ctx, TELA, pid)
    linha = page.locator("#sbScenes .scene-row").nth(1)
    linha.locator(".sb-pick").click()
    m = H.modal(page)
    m.wait_for()
    cards = m.locator("#sbGallery .card")
    if not cards.count():
        H.fechar_modal(page)
        return H.Resultado.falha("picker sem ideias para escolher")
    cards.nth(0).click()
    ev = H.evidencia(page, ctx, "sb-picker", full_page=False)
    m.locator(".modal-actions button.primary").click()   # Aplicar
    page.wait_for_timeout(800)
    fotos = linha.locator(".sb-photorow").count()
    principal = linha.locator(".sb-key.primary").count()
    page.locator("#sbSave").click()
    H.esperar_toast(page, "cenas salvas")
    page.wait_for_timeout(500)
    disco = _cenas(page, ctx, pid)[1]
    ideias_dir = H.arquivos(ctx.projeto(pid), "storyboard/ideas/*.png")
    return H.verifica(fotos == 1 and principal == 1 and len(disco["images"]) == 1 and disco["primary"] == disco["images"][0]
                      and ideias_dir,
                      f"1 keyframe anexado e copiado para storyboard/ideas/ ({len(ideias_dir)} arquivos)",
                      f"linhas-foto={fotos} principal={principal} disco.images={disco['images']} primary={disco['primary']} ideas={ideias_dir}", ev)


@caso("C-STORYBOARD-23", "'Sem imagem' no picker limpa a galeria de keyframes da cena")
def p02_picker_sem_imagem(page, ctx):
    pid = _projeto_qa(page, ctx)
    _cena_com_fotos(page, ctx, pid, idx=1, n=1)
    H.abrir_tela(page, ctx, TELA, pid)
    linha = page.locator("#sbScenes .scene-row").nth(1)
    antes = linha.locator(".sb-photorow").count()
    linha.locator(".sb-pick").click()
    m = H.modal(page)
    m.wait_for()
    m.locator(".modal-actions button", has_text="Sem imagem").click()
    page.wait_for_timeout(700)
    depois = page.locator("#sbScenes .scene-row").nth(1).locator(".sb-photorow").count()
    return H.verifica(antes >= 1 and depois == 0, f"{antes} → {depois} keyframes",
                      f"keyframes {antes} → {depois} (esperado terminar em 0)")


@caso("C-STORYBOARD-24", "★ troca a foto principal e ✕ remove a foto da cena")
def p02_star_remove(page, ctx):
    pid = _projeto_qa(page, ctx)
    sid, imgs = _cena_com_fotos(page, ctx, pid, idx=0, n=2)
    H.abrir_tela(page, ctx, TELA, pid)
    linha = page.locator(f"#sbScenes .scene-row[data-sid='{sid}']")
    linha.locator(".sb-photorow").nth(1).locator(".sb-star").click()
    page.wait_for_timeout(300)
    nova_primaria = linha.locator(".sb-photorow .sb-key.primary").first.get_attribute("data-img")
    ev = H.evidencia(page, ctx, "sb-star")
    linha.locator(".sb-photorow").nth(0).locator(".sb-rm").click()
    page.wait_for_timeout(300)
    restantes = linha.locator(".sb-photorow").count()
    _cena_com_fotos(page, ctx, pid, idx=0, n=2)         # repõe
    return H.verifica(nova_primaria == imgs[1] and restantes == 1,
                      f"principal={nova_primaria.rsplit('/', 1)[-1]}, sobrou {restantes} foto",
                      f"principal='{nova_primaria}' esperado='{imgs[1]}'; restantes={restantes} (esperado 1)", ev)


@caso("C-STORYBOARD-25", "↑/↓ da foto reordena e persiste a ordem em scenes.json")
def p02_reordenar_foto(page, ctx):
    pid = _projeto_qa(page, ctx)
    sid, imgs = _cena_com_fotos(page, ctx, pid, idx=0, n=2)
    H.abrir_tela(page, ctx, TELA, pid)
    linha = page.locator(f"#sbScenes .scene-row[data-sid='{sid}']")
    linha.locator(".sb-photorow").nth(1).locator(".sbPhotoDown").is_disabled()
    linha.locator(".sb-photorow").nth(1).locator(".sbPhotoUp").click()
    page.wait_for_timeout(900)
    disco = next(c for c in _cenas(page, ctx, pid) if c["id"] == sid)
    dom = linha.locator(".sb-photorow").evaluate_all("els => els.map(e => e.dataset.img)")
    _cena_com_fotos(page, ctx, pid, idx=0, n=2)         # repõe a ordem original
    return H.verifica(disco["images"] == [imgs[1], imgs[0]] and dom == [imgs[1], imgs[0]],
                      "ordem invertida no DOM e no disco",
                      f"disco={disco['images']} dom={dom} esperado={[imgs[1], imgs[0]]}")


@caso("C-STORYBOARD-26", "clique na foto abre o lightbox em tamanho real")
def p02_lightbox(page, ctx):
    pid = _projeto_qa(page, ctx)
    sid, imgs = _cena_com_fotos(page, ctx, pid, idx=0, n=1)
    H.abrir_tela(page, ctx, TELA, pid)
    _linha_foto(page, sid).locator(".sb-key img").click()
    m = H.modal(page)
    m.wait_for()
    media = m.locator(".sb-lightbox-media")
    n_media = media.count()
    src = media.get_attribute("src") if n_media else ""
    titulo = (m.locator(".modal-head h3").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "sb-lightbox", full_page=False)
    H.fechar_modal(page)
    return H.verifica(n_media == 1 and imgs[0].rsplit("/", 1)[-1] in (src or "") and titulo == "Tamanho real",
                      f"lightbox de {imgs[0].rsplit('/', 1)[-1]}",
                      f"título='{titulo}' src='{src}' esperado conter '{imgs[0]}'", ev)


@caso("C-STORYBOARD-27", "'Gerar prompt' da foto chama o Claude (fake) e mostra a fonte no progresso")
def p02_prompt_video(page, ctx):
    pid = _projeto_qa(page, ctx)
    sid, imgs = _cena_com_fotos(page, ctx, pid, idx=0, n=1)
    cenas = _cenas(page, ctx, pid)
    cenas[0]["photos"] = {}
    _salvar_cenas(page, ctx, pid, cenas)
    H.abrir_tela(page, ctx, TELA, pid)
    linha = _linha_foto(page, sid)
    linha.locator(".sbVidDesc").fill("the giant can falls and floods the street")
    linha.locator(".sbVidPrompt").click()
    prog = page.locator(".modal.progress-modal")
    prog.wait_for()
    page.wait_for_function("() => { const n = document.querySelector('.modal.progress-modal .prog-note');"
                           " return n && !n.hidden && n.textContent.trim(); }", timeout=60000)
    nota = (prog.locator(".prog-note").text_content() or "").strip()
    fechavel = prog.locator(".modal-close").is_enabled()
    ev = H.evidencia(page, ctx, "sb-prompt-video", full_page=False)
    H.fechar_modal(page)
    page.wait_for_timeout(800)
    prompt_dom = (linha.locator(".sbVidPromptText").text_content() or "").strip()
    caixa_visivel = linha.locator(".sbVidPromptBox").is_visible()
    disco = next(c for c in _cenas(page, ctx, pid) if c["id"] == sid)["photos"].get(imgs[0], {})
    return H.verifica(bool(prompt_dom) and caixa_visivel and "fonte:" in nota and fechavel
                      and disco.get("video_prompt") == prompt_dom,
                      f"prompt gerado ({len(prompt_dom)} chars), nota='{nota[:50]}'",
                      f"prompt='{prompt_dom[:80]}' caixa={caixa_visivel} nota='{nota}' fechável={fechavel} disco='{(disco.get('video_prompt') or '')[:60]}'", ev)


@caso("C-STORYBOARD-28", "'Gerar prompt' sem descrição falha no modal de progresso com a mensagem da API")
def p02_prompt_video_vazio(page, ctx):
    pid = _projeto_qa(page, ctx)
    sid, _ = _cena_com_fotos(page, ctx, pid, idx=0, n=1)
    H.abrir_tela(page, ctx, TELA, pid)
    linha = _linha_foto(page, sid)
    linha.locator(".sbVidDesc").fill("")
    linha.locator(".sbVidPrompt").click()
    prog = page.locator(".modal.progress-modal")
    prog.wait_for()
    page.wait_for_function("() => { const n = document.querySelector('.modal.progress-modal .prog-err');"
                           " return n && n.textContent.trim(); }", timeout=30000)
    err = (prog.locator(".prog-err").text_content() or "").strip()
    fechavel = prog.locator(".modal-close").is_enabled()
    ev = H.evidencia(page, ctx, "sb-prompt-video-vazio", full_page=False)
    H.fechar_modal(page)
    return H.verifica("descrição" in err.lower() and fechavel, f"erro='{err[:70]}'",
                      f"erro='{err}' fechável={fechavel}", ev)


@caso("C-STORYBOARD-29", "modal 'Gerar animação' traz preview, duração, modelo default e start→end")
def p02_modal_animacao(page, ctx):
    pid = _projeto_qa(page, ctx)
    sid, imgs = _cena_com_fotos(page, ctx, pid, idx=0, n=2)
    st = _json(page, ctx, "get", _sb(pid)).json()
    H.abrir_tela(page, ctx, TELA, pid)
    _linha_foto(page, sid).locator(".sbAnim").click()
    m = H.modal(page)
    m.wait_for()
    modelo = m.locator(".sbVidModel").input_value()
    duracoes = m.locator(".sbVidDur option").evaluate_all("els => els.map(e => e.value)")
    m.locator(".sbVidMode").select_option("start_end")
    page.wait_for_timeout(250)
    par_visivel = m.locator(".sbVidPair").is_visible()
    end_opts = m.locator(".sbVidEnd option").evaluate_all("els => els.map(e => e.value)")
    modelo_se = m.locator(".sbVidModel").input_value()
    preview = m.locator(".sb-anim-preview img").count()
    ev = H.evidencia(page, ctx, "sb-modal-animacao", full_page=False)
    H.fechar_modal(page)
    ok = (preview == 1 and duracoes == ["5", "10"] and modelo == st["video_model_defaults"]["single"]
          and modelo_se == st["video_model_defaults"]["start_end"] and par_visivel and end_opts == [imgs[1]])
    return H.verifica(ok, f"modelo single={modelo}, start_end={modelo_se}, end frame={end_opts}",
                      f"preview={preview} durações={duracoes} modelo={modelo} (esperado {st['video_model_defaults']['single']}) "
                      f"modelo_start_end={modelo_se} (esperado {st['video_model_defaults']['start_end']}) "
                      f"par visível={par_visivel} end_opts={end_opts} esperado={[imgs[1]]}", ev)


@caso("C-STORYBOARD-30", "'Gerar animação' sem prompt de vídeo avisa e não abre o modal de custo")
def p02_animar_sem_prompt(page, ctx):
    pid = _projeto_qa(page, ctx)
    sid, imgs = _cena_com_fotos(page, ctx, pid, idx=0, n=1)
    cenas = _cenas(page, ctx, pid)
    cenas[0]["photos"] = {}
    _salvar_cenas(page, ctx, pid, cenas)
    H.abrir_tela(page, ctx, TELA, pid)
    _linha_foto(page, sid).locator(".sbAnim").click()
    m = H.modal(page)
    m.wait_for()
    m.locator(".modal-actions button.primary").click()
    t = H.esperar_toast(page, "prompt de vídeo primeiro")
    modais = page.locator(".modal[role=dialog]").count()
    ev = H.evidencia(page, ctx, "sb-animar-sem-prompt", full_page=False)
    H.fechar_modal(page)
    return H.verifica(bool(t) and modais == 1, f"toast='{t}' (só o modal da animação aberto)",
                      f"toast='{t}' modais abertos={modais} (esperado 1, sem o de custo)", ev)


@caso("C-STORYBOARD-31", "gerar animação: modal de custo → job → mp4 no disco e player na linha-foto")
def p02_gerar_animacao(page, ctx):
    pid = _projeto_qa(page, ctx)
    sid, imgs = _cena_com_fotos(page, ctx, pid, idx=0, n=1)
    _garantir_prompt_video(page, ctx, pid, sid, imgs[0])
    antes = _mp4s(ctx, pid, sid)
    H.abrir_tela(page, ctx, TELA, pid)
    _linha_foto(page, sid).locator(".sbAnim").click()
    m = H.modal(page)
    m.wait_for()
    m.locator(".sbVidDur").select_option("5")
    m.locator(".modal-actions button.primary").click()
    custo = H.modal(page)
    custo.wait_for()
    page.wait_for_timeout(400)
    texto_custo = (custo.text_content() or "").strip()
    ev = H.evidencia(page, ctx, "sb-modal-custo", full_page=False)
    custo.locator(".modal-actions button.primary").click()
    page.wait_for_timeout(500)
    prog = page.locator(".modal.progress-modal")
    if prog.count():
        H.esperar_modal_sumir(page, 180000)
    t = H.esperar_toast(page, "Vídeo gerado", timeout_ms=20000)
    page.wait_for_timeout(1200)
    depois = _mp4s(ctx, pid, sid)
    player = _linha_foto(page, sid).locator("video.sbVidPlayer").count()
    disco = next(c for c in _cenas(page, ctx, pid) if c["id"] == sid)["photos"].get(imgs[0], {})
    ev2 = H.evidencia(page, ctx, "sb-video-gerado")
    ok = len(depois) == len(antes) + 1 and player == 1 and len(disco.get("videos") or []) >= 1 and "créditos" in texto_custo
    return H.verifica(ok, f"mp4 {antes}→{depois}, player na linha, toast='{t}'",
                      f"mp4 {antes}→{depois}; player={player}; scenes.json videos={disco.get('videos')}; "
                      f"toast='{t}'; modal de custo='{texto_custo[:120]}'", ev, ev2)


@caso("C-STORYBOARD-32", "cancelar no modal de custo não gera vídeo nem chama o CLI")
def p02_custo_cancelar(page, ctx):
    pid = _projeto_qa(page, ctx)
    sid, imgs = _cena_com_fotos(page, ctx, pid, idx=0, n=1)
    _garantir_prompt_video(page, ctx, pid, sid, imgs[0])
    antes = _mp4s(ctx, pid, sid)
    H.abrir_tela(page, ctx, TELA, pid)
    _linha_foto(page, sid).locator(".sbAnim").click()
    H.modal(page).wait_for()
    page.locator(".modal[role=dialog] .modal-actions button.primary").last.click()
    custo = H.modal(page)
    custo.wait_for()
    custo.locator(".modal-actions button.ghost").first.click()   # Cancelar
    page.wait_for_timeout(2500)
    depois = _mp4s(ctx, pid, sid)
    prog = page.locator(".modal.progress-modal").count()
    H.fechar_modal(page)
    return H.verifica(depois == antes and prog == 0, f"nenhum mp4 novo ({len(antes)})",
                      f"mp4 antes={antes} depois={depois}; modal de progresso aberto={prog}")


@caso("C-STORYBOARD-33", "recarregar a tela mantém fotos, prompt e vídeo da cena")
def p02_persistencia(page, ctx):
    pid = _projeto_qa(page, ctx)
    sid, imgs = _cena_com_fotos(page, ctx, pid, idx=0, n=1)
    prompt = _garantir_prompt_video(page, ctx, pid, sid, imgs[0])
    H.abrir_tela(page, ctx, TELA, pid)
    page.reload()
    H.esperar_tela(page)
    linha = _linha_foto(page, sid)
    fotos = page.locator(f"#sbScenes .scene-row[data-sid='{sid}'] .sb-photorow").count()
    desc = linha.locator(".sbVidDesc").input_value() if fotos else ""
    txt = (linha.locator(".sbVidPromptText").text_content() or "").strip() if fotos else ""
    ev = H.evidencia(page, ctx, "sb-persistencia")
    return H.verifica(fotos == 1 and txt == prompt and desc.strip() != "",
                      "foto, descrição e prompt reidratados após reload",
                      f"fotos={fotos} desc='{desc[:40]}' prompt_dom='{txt[:50]}' esperado='{prompt[:50]}'", ev)


# ======================================================================================
# painéis 03/04 — ângulos por cena (aula 011) e cena do produto (aula 013)
# ======================================================================================
@caso("C-STORYBOARD-34", "painel 03 lista um card por cena + o card do produto, com N/M upscalados")
def p03_lista(page, ctx):
    r = _json(page, ctx, "get", _ang(ctx.pid_cheio, "/scenes")).json()
    cards = page.locator("#sceneList [data-scene]")
    ids = cards.evaluate_all("els => els.map(e => e.dataset.scene)")
    contagens = page.locator("#sceneList .upcount").all_text_contents()
    paleta = page.locator("#shotsPalette span").count()
    ev = H.evidencia(page, ctx, "sb-painel03")
    esperado = [s["id"] for s in r["scenes"]] + ["__produto__"]
    esperado_up = [f"{s['upscaled']}/{s['selected']} upscalados" for s in r["scenes"]]
    return H.verifica(ids == esperado and contagens[:len(esperado_up)] == esperado_up and paleta > 0,
                      f"{len(ids)} cards, contagens={contagens[:2]}, paleta com {paleta} itens",
                      f"cards={ids} esperado={esperado}; contagens={contagens} esperado={esperado_up}; paleta={paleta}", ev)


@caso("C-STORYBOARD-35", "abrir uma cena no painel 03 carrega candidatos e título no painel 04")
def p04_abrir_cena(page, ctx):
    r = _json(page, ctx, "get", _ang(ctx.pid_cheio, "/scenes/cena01/candidates")).json()
    _abrir_cena_angulos(page, ctx, "cena01")
    titulo = (page.locator("#sceneTitle").text_content() or "").strip()
    cards = page.locator("#shotsGallery .card").count()
    chip = (page.locator("#shotsCounts").text_content() or "").strip()
    marcada = page.locator("#sceneList [data-scene='cena01'].cur").count()
    ev = H.evidencia(page, ctx, "sb-painel04")
    return H.verifica(titulo.startswith("Cena 01") and cards == len(r["candidates"]) and marcada == 1
                      and chip.startswith(f"{cards} candidatos"),
                      f"'{titulo}' com {cards} candidatos",
                      f"título='{titulo}' cards={cards} api={len(r['candidates'])} chip='{chip}' card marcado={marcada}", ev)


@caso("C-STORYBOARD-36", "reabrir uma cena já salva deveria remarcar os frames escolhidos")
def p04_ordem_persistida(page, ctx):
    sel = json.loads((ctx.projeto(ctx.pid_cheio) / "storyboard" / "cena01" / "selection.json").read_text())["shots"]
    if not sel:
        return H.Resultado.bloqueado("cena01 sem selection.json no seed")
    _abrir_cena_angulos(page, ctx, "cena01")
    marcados = page.locator("#shotsGallery .card.sel").count()
    chip = (page.locator("#shotsCounts").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "sb-ordem-persistida")
    return H.verifica(marcados == len(sel), f"{marcados} frames remarcados",
                      f"selection.json tem {len(sel)} shot(s) e a galeria remarcou {marcados}; chip='{chip}'. "
                      "Reabrir a cena zera a ordem: 'Salvar ordem da cena' (botão primário) apagaria os "
                      f"shot0N_final.png já escolhidos.", ev)


@caso("C-STORYBOARD-37", "'base ▾' abre o menu de base e 'Imagem base da campanha' regrava base.png")
def p04_base(page, ctx):
    alvo = ctx.projeto(ctx.pid_cheio) / "storyboard" / "cena02" / "base.png"
    antes = alvo.stat().st_mtime if alvo.exists() else 0
    page.wait_for_timeout(1100)
    page.locator("#sceneList [data-scene-base='cena02']").click()
    m = H.modal(page)
    m.wait_for()
    opcoes = {
        "cena": m.locator("#shBaseScene").count(),
        "campanha": m.locator("#shBaseCampaign").count(),
        "upload": m.locator("#shBaseDrop").count(),
    }
    ev = H.evidencia(page, ctx, "sb-menu-base", full_page=False)
    m.locator("#shBaseCampaign").click()
    t = H.esperar_toast(page, "Base da cena pronta")
    page.wait_for_timeout(900)
    depois = alvo.stat().st_mtime if alvo.exists() else 0
    return H.verifica(all(opcoes.values()) and depois > antes and bool(t),
                      f"base regravada (toast='{t}')",
                      f"opções={opcoes}; mtime {antes}→{depois}; toast='{t}'", ev)


@caso("C-STORYBOARD-38", "#btnPrompts monta o prompt de ângulo com foco, escala e ângulo escolhidos")
def p04_prompt_angulo(page, ctx):
    _abrir_cena_angulos(page, ctx, "cena01")
    page.locator("#promptKind").select_option("angle")
    page.locator("#promptSubject").fill("the astronaut's face")
    page.locator("#promptScale").select_option("wide")
    page.locator("#promptAngle").select_option("low")
    page.locator("#btnPrompts").click()
    page.wait_for_timeout(700)
    caixas = page.locator("#shotsPrompts .prompt")
    texto = (page.locator("#shotsPrompts .txt").first.text_content() or "").strip()
    ev = H.evidencia(page, ctx, "sb-prompt-angulo")
    ok = (caixas.count() == 1 and "the astronaut's face" in texto and "a wide shot of" in texto
          and "low angle" in texto and not page.locator("#shotsPrompts").is_hidden())
    return H.verifica(ok, f"prompt='{texto[:80]}…'", f"caixas={caixas.count()} texto='{texto}'", ev)


@caso("C-STORYBOARD-39", "modo 'Edição numerada': sem linhas avisa; com linhas numera as modificações")
def p04_prompt_edicao(page, ctx):
    _abrir_cena_angulos(page, ctx, "cena01")
    page.locator("#promptKind").select_option("edit")
    page.wait_for_timeout(300)
    caixa_visivel = not page.locator("#editsBox").is_hidden()
    page.locator("#promptEdits").fill("")
    page.locator("#btnPrompts").click()
    t = H.esperar_toast(page, "ao menos uma modificação")
    page.wait_for_timeout(3300)
    page.locator("#promptEdits").fill("Make the helmet visor tinted\nRemove the antenna")
    page.locator("#btnPrompts").click()
    page.wait_for_timeout(700)
    texto = (page.locator("#shotsPrompts .txt").first.text_content() or "").strip()
    ev = H.evidencia(page, ctx, "sb-prompt-edicao")
    page.locator("#promptKind").select_option("angle")
    ok = caixa_visivel and bool(t) and "1. Make the helmet visor tinted." in texto and "2. Remove the antenna." in texto
    return H.verifica(ok, f"editsBox visível, prompt numerado ('{texto[:60]}…')",
                      f"editsBox visível={caixa_visivel}; toast vazio='{t}'; prompt='{texto}'", ev)


@caso("C-STORYBOARD-40", "copiar o prompt de ângulo ecoa 'copiado ✓'")
def p04_copiar_prompt(page, ctx):
    try:
        page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=ctx.base)
    except Exception:  # noqa: BLE001
        pass
    _abrir_cena_angulos(page, ctx, "cena01")
    page.locator("#btnPrompts").click()
    page.wait_for_timeout(700)
    page.locator("#shotsPrompts button.copy").first.click()
    page.wait_for_timeout(400)
    eco = (page.locator("#shotsPrompts .ok").first.text_content() or "").strip()
    return H.verifica(eco.startswith("copiado"), f"eco='{eco}'", f"eco='{eco}' (esperado 'copiado ✓')")


@caso("C-STORYBOARD-41", "#shotsCounts abre 'Importar candidatos' e o upload entra na cena")
def p04_import_cena(page, ctx):
    _abrir_cena_angulos(page, ctx, "cena02")
    antes = len(_json(page, ctx, "get", _ang(ctx.pid_cheio, "/scenes/cena02/candidates")).json()["candidates"])
    page.locator("#shotsCounts").click()
    m = H.modal(page)
    m.wait_for()
    titulo = (m.locator(".modal-head h3").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "sb-modal-import-cena", full_page=False)
    png = _png_unico(ctx, "sb-cena02")
    H.upload(page, "#shImpUpload", png)
    t = H.esperar_toast(page, "importada")
    page.wait_for_timeout(900)
    depois = len(_json(page, ctx, "get", _ang(ctx.pid_cheio, "/scenes/cena02/candidates")).json()["candidates"])
    galeria = page.locator("#shotsGallery .card").count()
    disco = H.arquivos(ctx.projeto(ctx.pid_cheio), "storyboard/cena02/candidates/*.png")
    return H.verifica(depois == antes + 1 and galeria == depois and "Cena 02" in titulo.replace("cena 02", "Cena 02"),
                      f"{antes}→{depois} candidatos ({len(disco)} pngs no disco)",
                      f"título='{titulo}' candidatos {antes}→{depois}; galeria={galeria}; disco={len(disco)}; toast='{t}'", ev)


@caso("C-STORYBOARD-42", "escolher frames numera a ordem e #btnShotsSave grava shots + storyboard.json")
def p04_salvar_ordem(page, ctx):
    root = ctx.projeto(ctx.pid_cheio)
    _abrir_cena_angulos(page, ctx, "cena01")
    cards = page.locator("#shotsGallery .card")
    if cards.count() < 2:
        return H.Resultado.bloqueado(f"cena01 com {cards.count()} candidato(s) — o caso precisa de 2")
    page.locator("#shotsUpscaled").uncheck()
    cards.nth(0).click()
    cards.nth(1).click()
    page.wait_for_timeout(300)
    ordens = page.locator("#shotsGallery .card.sel").evaluate_all("els => els.map(e => e.dataset.ord)")
    chip = (page.locator("#shotsCounts").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "sb-ordem-frames")
    page.locator("#btnShotsSave").click()
    t = H.esperar_toast(page, "upscale", timeout_ms=10000) or H.esperar_toast(page, "salvos")
    page.wait_for_timeout(900)
    sel = json.loads((root / "storyboard" / "cena01" / "selection.json").read_text())["shots"]
    board = json.loads((root / "storyboard" / "storyboard.json").read_text())
    cena01 = next((s for s in board["scenes"] if s["id"] == "cena01"), {})
    frames_md = (root / "storyboard" / "frames.md").exists()
    ok = (ordens == ["1", "2"] and len(sel) == 2 and [s["id"] for s in sel] == ["shot01", "shot02"]
          and len(cena01.get("shots") or []) == 2 and frames_md and "sem upscale" in t)
    return H.verifica(ok, f"2 frames salvos, aviso de upscale (chip='{chip}')",
                      f"data-ord={ordens}; selection={[s['id'] for s in sel]}; storyboard.json shots={len(cena01.get('shots') or [])}; "
                      f"frames.md={frames_md}; toast='{t}'", ev)


@caso("C-STORYBOARD-43", "#shotsUpscaled marca os frames como upscalados e some o aviso da aula 011")
def p04_upscaled(page, ctx):
    root = ctx.projeto(ctx.pid_cheio)
    _abrir_cena_angulos(page, ctx, "cena01")
    cards = page.locator("#shotsGallery .card")
    if cards.count() < 2:
        return H.Resultado.bloqueado("cena01 sem candidatos suficientes")
    page.locator("#shotsUpscaled").check()
    cards.nth(0).click()
    cards.nth(1).click()
    page.locator("#btnShotsSave").click()
    t = H.esperar_toast(page, "salvos", timeout_ms=10000)
    page.wait_for_timeout(900)
    sel = json.loads((root / "storyboard" / "cena01" / "selection.json").read_text())["shots"]
    contagem = (page.locator("#sceneList [data-scene='cena01'] .upcount").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "sb-upscaled")
    # repõe o estado do seed (sem upscale)
    _json(page, ctx, "post", _ang(ctx.pid_cheio, "/scenes/cena01/select"),
          {"shots": [{"id": s["candidate"], "upscaled": False} for s in sel]})
    return H.verifica(all(s["upscaled"] for s in sel) and "2/2" in contagem and "sem upscale" not in t,
                      f"selection upscalada, card diz '{contagem}'",
                      f"upscaled={[s['upscaled'] for s in sel]}; card='{contagem}'; toast='{t}'", ev)


@caso("C-STORYBOARD-44", "'Usar como base da cena' promove o candidato a nova base da cena")
def p04_usar_como_base(page, ctx):
    alvo = ctx.projeto(ctx.pid_cheio) / "storyboard" / "cena02" / "base.png"
    _abrir_cena_angulos(page, ctx, "cena02")
    botao = page.locator("#shotsGallery button.asBase").first
    if not botao.count():
        return H.Resultado.falha("nenhum botão 'Usar como base da cena' na galeria")
    antes = alvo.read_bytes() if alvo.exists() else b""
    page.wait_for_timeout(1100)
    botao.click()
    t = H.esperar_toast(page, "nova base da cena")
    page.wait_for_timeout(1000)
    depois = alvo.read_bytes() if alvo.exists() else b""
    ev = H.evidencia(page, ctx, "sb-usar-como-base")
    return H.verifica(bool(t) and depois and depois != antes, f"base trocada (toast='{t}')",
                      f"toast='{t}'; base mudou={depois != antes}; bytes={len(antes)}→{len(depois)}", ev)


@caso("C-STORYBOARD-45", "cena do produto: sem a imagem 1 os prompts da aula 013 são recusados")
def p04_produto_sem_ref(page, ctx):
    ref = ctx.projeto(ctx.pid_cheio) / "storyboard" / "product" / "ref.png"
    ref.unlink(missing_ok=True)
    H.abrir_tela(page, ctx, TELA, ctx.pid_cheio)
    _abrir_cena_angulos(page, ctx, "__produto__")
    titulo = (page.locator("#sceneTitle").text_content() or "").strip()
    escondidos = [page.locator(s).is_hidden() for s in ("#promptKind", "#promptSubject", "#promptScale", "#promptAngle")]
    page.locator("#btnPrompts").click()
    t = H.esperar_toast(page, "imagem de referência")
    ev = H.evidencia(page, ctx, "sb-produto-sem-ref")
    return H.verifica(titulo.startswith("Produto") and all(escondidos) and bool(t),
                      f"'{titulo}' sem os selects de ângulo, toast='{t}'",
                      f"título='{titulo}' selects escondidos={escondidos} toast='{t}'", ev)


@caso("C-STORYBOARD-46", "cena do produto: enviar a imagem 1 grava storyboard/product/ref.png")
def p04_produto_ref(page, ctx):
    ref = ctx.projeto(ctx.pid_cheio) / "storyboard" / "product" / "ref.png"
    ref.unlink(missing_ok=True)
    H.abrir_tela(page, ctx, TELA, ctx.pid_cheio)
    _abrir_cena_angulos(page, ctx, "__produto__")
    page.locator("#shotsCounts").click()
    m = H.modal(page)
    m.wait_for()
    titulo = (m.locator(".modal-head h3").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "sb-modal-produto", full_page=False)
    png = H.png_temp(ctx, "sb-produto-ref", (30, 160, 90))
    H.upload(page, "#shProdRefUpload", png)
    t = H.esperar_toast(page, "Imagem 1 salva")
    page.wait_for_timeout(900)
    st = _json(page, ctx, "get", _ang(ctx.pid_cheio, "/scenes")).json()["product_scene"]
    return H.verifica(ref.exists() and st["ref_ready"] and bool(t) and "produto" in titulo.lower(),
                      f"ref.png gravado (toast='{t}')",
                      f"modal='{titulo}'; ref.png existe={ref.exists()}; product_scene={st}; toast='{t}'", ev)


@caso("C-STORYBOARD-47", "cena do produto: #btnPrompts traz as duas instruções da aula 013")
def p04_produto_prompts(page, ctx):
    _upload_png(page, ctx, _ang(ctx.pid_cheio, "/product/ref"), "sb-produto-ref", (30, 160, 90), campo="file")
    H.abrir_tela(page, ctx, TELA, ctx.pid_cheio)
    _abrir_cena_angulos(page, ctx, "__produto__")
    page.locator("#btnPrompts").click()
    page.wait_for_timeout(800)
    textos = page.locator("#shotsPrompts .txt").all_text_contents()
    rotulos = page.locator("#shotsPrompts .eyebrow").all_text_contents()
    ev = H.evidencia(page, ctx, "sb-produto-prompts")
    ok = (len(textos) == 2 and "Replace the can in image 1" in textos[0]
          and "Remove the text below the can" in textos[1] and rotulos[0].startswith("1."))
    return H.verifica(ok, f"2 instruções ({rotulos[0][:30]}… / {rotulos[1][:30] if len(rotulos) > 1 else ''}…)",
                      f"rótulos={rotulos} textos={textos}", ev)


@caso("C-STORYBOARD-48", "cena do produto: importar, escolher e salvar grava product_final.png")
def p04_produto_salvar(page, ctx):
    root = ctx.projeto(ctx.pid_cheio)
    _upload_png(page, ctx, _ang(ctx.pid_cheio, "/product/ref"), "sb-produto-ref", (30, 160, 90), campo="file")
    H.abrir_tela(page, ctx, TELA, ctx.pid_cheio)
    _abrir_cena_angulos(page, ctx, "__produto__")
    if not page.locator("#shotsGallery .card").count():
        page.locator("#shotsCounts").click()
        H.modal(page).wait_for()
        H.upload(page, "#shImpUpload", _png_unico(ctx, "sb-produto-cand"))
        H.esperar_toast(page, "importada")
        page.wait_for_timeout(900)
    cards = page.locator("#shotsGallery .card")
    if not cards.count():
        return H.Resultado.falha("nenhuma candidata na cena do produto após importar")
    # clicar num card já marcado DESMARCA (a escolha do produto é única) — só clica se preciso
    if "sel" not in (cards.first.get_attribute("class") or ""):
        cards.first.click()
    page.wait_for_timeout(200)
    page.locator("#btnShotsSave").click()
    t = H.esperar_toast(page, "produto salva", timeout_ms=10000)
    page.wait_for_timeout(1000)
    final = root / "storyboard" / "product" / "product_final.png"
    board = json.loads((root / "storyboard" / "storyboard.json").read_text())
    ev = H.evidencia(page, ctx, "sb-produto-salvo")
    return H.verifica(final.exists() and board.get("product_scene") and bool(t),
                      f"product_final.png + product_scene no storyboard.json (toast='{t}')",
                      f"final existe={final.exists()}; product_scene={board.get('product_scene')}; toast='{t}'", ev)


@caso("C-STORYBOARD-49", "cena do produto: 'remover' apaga a escolha e volta o card ao estado inicial")
def p04_produto_remover(page, ctx):
    root = ctx.projeto(ctx.pid_cheio)
    final = root / "storyboard" / "product" / "product_final.png"
    if not final.exists():
        cands = _json(page, ctx, "get", _ang(ctx.pid_cheio, "/product/candidates")).json()["candidates"]
        if not cands:
            _upload_png(page, ctx, _ang(ctx.pid_cheio, "/product/ref"), "sb-produto-ref", (30, 160, 90), campo="file")
            _upload_png(page, ctx, _ang(ctx.pid_cheio, "/product/import/upload"), "sb-produto-cand", (220, 90, 30))
            cands = _json(page, ctx, "get", _ang(ctx.pid_cheio, "/product/candidates")).json()["candidates"]
        _json(page, ctx, "post", _ang(ctx.pid_cheio, "/product/select"), {"id": cands[0]["id"], "upscaled": False})
        H.abrir_tela(page, ctx, TELA, ctx.pid_cheio)
    botao = page.locator("#sceneList .shProdClear")
    if not botao.count():
        return H.Resultado.falha("botão 'remover' ausente no card do produto mesmo com cena escolhida",
                                 H.evidencia(page, ctx, "sb-produto-sem-remover"))
    botao.click()
    t = H.esperar_toast(page, "produto removida")
    page.wait_for_timeout(900)
    st = _json(page, ctx, "get", _ang(ctx.pid_cheio, "/scenes")).json()["product_scene"]
    ev = H.evidencia(page, ctx, "sb-produto-removido")
    return H.verifica(not final.exists() and not st["selected"] and bool(t),
                      f"cena do produto removida (toast='{t}')",
                      f"product_final existe={final.exists()}; product_scene={st}; toast='{t}'", ev)


@caso("C-STORYBOARD-51", "depois de remover, a cena do produto reabre sem candidata marcada")
def p04_produto_remover_estado(page, ctx):
    root = ctx.projeto(ctx.pid_cheio)
    cands = _json(page, ctx, "get", _ang(ctx.pid_cheio, "/product/candidates")).json()["candidates"]
    if not cands:
        return H.Resultado.bloqueado("cena do produto sem candidatas para o cenário de remoção")
    _json(page, ctx, "post", _ang(ctx.pid_cheio, "/product/select"), {"id": cands[0]["id"], "upscaled": False})
    _json(page, ctx, "post", _ang(ctx.pid_cheio, "/product/select"), {"id": None})
    H.abrir_tela(page, ctx, TELA, ctx.pid_cheio)
    _abrir_cena_angulos(page, ctx, "__produto__")
    chip = (page.locator("#shotsCounts").text_content() or "").strip()
    marcadas = page.locator("#shotsGallery .card.sel").count()
    st = _json(page, ctx, "get", _ang(ctx.pid_cheio, "/scenes")).json()["product_scene"]
    final = (root / "storyboard" / "product" / "product_final.png").exists()
    ev = H.evidencia(page, ctx, "sb-produto-estado-apos-remover")
    return H.verifica(marcadas == 0 and "0 escolhidos" in chip,
                      f"nenhuma candidata marcada (chip='{chip}')",
                      f"product_scene={st} product_final existe={final}, mas a galeria marca {marcadas} candidata(s) "
                      f"e o chip diz '{chip}': `select_product(None)` não limpa `selected` em "
                      "storyboard/product/candidates.json, então o painel 04 diz que há escolha onde não há.", ev)


@caso("C-STORYBOARD-50", "upscale e geração paga dos ângulos não têm comando na tela")
def p04_upscale(page, ctx):
    _abrir_cena_angulos(page, ctx, "cena01")
    botoes = page.locator("#scenePanel button, #shotsGallery button").evaluate_all(
        "els => els.map(e => (e.textContent || '').trim()).filter(Boolean)")
    if any("upscale" in b.lower() and "já upscalei" not in b.lower() for b in botoes):
        return H.Resultado.falha(f"apareceu comando de upscale na tela: {botoes}")
    return H.Resultado.bloqueado(
        "o router expõe POST /angles/scenes/{cena}/upscale, /cost e /generate (aula 011 pelo CLI), mas o "
        f"painel 04 só oferece o checkbox 'já upscalei estes na UI' — botões visíveis: {botoes}. "
        "Sem comando na UI não dá para exercitar o upscale 2x nem a geração paga dos ângulos offline.")
