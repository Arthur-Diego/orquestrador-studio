"""Casos da etapa 6 — Trilha (aula 013).

Tela: `studio/etapas/music/view.html` + `view.js` — painel 01 (assistir a história inteira:
`audio/rough_sequence.mp4` + a decisão "a história fecha?"), painel 02 (candidatas: importar,
ouvir e escolher) e painel 03 (batidas da trilha escolhida). Backend:
`studio/etapas/music/router.py` + `studio/music/service.py` + `studio/music/beats.py`.

O `pid_cheio` já vem com uma trilha escolhida (`audio/music.wav` + `audio/beats.json`): todo caso
que escreve tira um retrato de `audio/` (`_snap`) e devolve o estado ao final (`_restaura`), que
reescolhe a candidata original — é isso que recria `music.wav` e `beats.json` byte a byte.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from scripts.qa import harness as H

TELA = "music"
CASOS: list[H.Caso] = []
caso = H.registrador(TELA, CASOS)

JSON = {"content-type": "application/json"}


# ---------- helpers do módulo ----------
def _base(ctx, pid: str | None = None) -> str:
    return f"/api/projects/{pid or ctx.pid_cheio}/music"


def _audio(ctx, pid: str | None = None) -> Path:
    return ctx.projeto(pid or ctx.pid_cheio) / "audio"


def _cands(page, ctx, pid: str | None = None) -> list[dict]:
    return H.api(page, ctx, "get", f"{_base(ctx, pid)}/candidates").json()


def _snap(ctx) -> dict:
    """Retrato de `audio/` para desfazer o que o caso escreveu."""
    a = _audio(ctx)
    cands = json.loads((a / "candidates.json").read_text())
    return {"sel": next((c["id"] for c in cands if c.get("selected")), None),
            "cands": (a / "candidates.json").read_text(),
            "license": (a / "license.txt").read_text() if (a / "license.txt").exists() else None,
            "arquivos": set(H.arquivos(a))}


def _restaura(page, ctx, snap: dict) -> None:
    a = _audio(ctx)
    if snap["sel"]:
        H.api(page, ctx, "post", f"{_base(ctx)}/select",
              data=json.dumps({"id": snap["sel"], "license": ""}), headers=JSON)
    (a / "candidates.json").write_text(snap["cands"])
    if snap["license"] is not None:
        (a / "license.txt").write_text(snap["license"])
    for rel in set(H.arquivos(a)) - snap["arquivos"]:
        (a / rel).unlink(missing_ok=True)
    # a tela guarda candidatas e batidas em memória e só relê no boot da etapa: sem o reload, o
    # próximo caso lê um DOM que fala de arquivos que este caso acabou de apagar
    page.reload()
    H.esperar_tela(page)


def _snap_check(ctx) -> str | None:
    f = _audio(ctx) / "story_check.json"
    return f.read_text() if f.exists() else None


def _restaura_check(ctx, texto: str | None) -> None:
    f = _audio(ctx) / "story_check.json"
    if texto is None:
        f.unlink(missing_ok=True)
    else:
        f.write_text(texto)


def _importar(page, ctx, arquivo: Path) -> dict:
    """Importa uma candidata pela própria tela (input do painel 02)."""
    H.upload(page, "#musUpload", arquivo)
    H.esperar_toast(page, "importad")
    page.wait_for_timeout(600)
    return {c["id"]: c for c in _cands(page, ctx)}


def _linha(page, cid: str):
    return page.locator(f'.track-row[data-id="{cid}"]')


# ---------- painel 01: assistir a história inteira ----------
@caso("C-MUSIC-01", "painel 01 reflete /music/story: botão habilitado com clipes e ffmpeg, chip só no aviso")
def story_estado(page, ctx):
    story = H.api(page, ctx, "get", f"{_base(ctx)}/story").json()
    btn_off = page.locator("#btnMusStory").is_disabled()
    chip_oculto = page.locator("#musStoryChip").is_hidden()
    video_oculto = page.locator("#musStoryVideo").is_hidden()
    ev = H.evidencia(page, ctx, "music-painel01")
    esperado_off = not (story["ffmpeg"] and story["clips"])
    esperado_video = story["video"] is None
    ok = btn_off == esperado_off and chip_oculto == (not story.get("warning")) and video_oculto == esperado_video
    return H.verifica(ok, f"clips={story['clips']} ffmpeg={story['ffmpeg']} botão off={btn_off}",
                      f"story={ {k: story[k] for k in ('video', 'clips', 'ffmpeg', 'warning')} } "
                      f"botão off={btn_off} chip oculto={chip_oculto} vídeo oculto={video_oculto}", ev)


@caso("C-MUSIC-02", "'Montar sequência bruta' roda o job com ffmpeg e produz audio/rough_sequence.mp4")
def montar_sequencia(page, ctx):
    story = H.api(page, ctx, "get", f"{_base(ctx)}/story").json()
    if not story["ffmpeg"] or not story["clips"]:
        return H.Resultado.bloqueado(f"sem ffmpeg ou sem clipes com like (clips={story['clips']})")
    alvo = _audio(ctx) / "rough_sequence.mp4"
    alvo.unlink(missing_ok=True)
    page.locator("#btnMusStory").click()
    page.wait_for_selector(".modal.progress-modal", timeout=20_000)
    travado = page.locator(".modal.progress-modal .modal-close").is_disabled()
    desabilitado = page.locator("#btnMusStory").is_disabled()
    ev = H.evidencia(page, ctx, "music-progresso", full_page=False)
    sumiu = H.esperar_modal_sumir(page, 300_000)
    page.wait_for_timeout(1500)
    depois = H.api(page, ctx, "get", f"{_base(ctx)}/story").json()
    video_visivel = page.locator("#musStoryVideo").is_visible()
    src = page.locator("#musStoryVideo").get_attribute("src") or ""
    reabilitado = not page.locator("#btnMusStory").is_disabled()
    ok = (travado and desabilitado and sumiu and alvo.exists() and depois["video"] == "audio/rough_sequence.mp4"
          and video_visivel and "rough_sequence.mp4" in src and reabilitado)
    return H.verifica(ok, f"{alvo.name} com {alvo.stat().st_size if alvo.exists() else 0} bytes",
                      f"close travado={travado} botão off durante={desabilitado} modal sumiu={sumiu} "
                      f"arquivo={alvo.exists()} story.video={depois['video']} vídeo visível={video_visivel} "
                      f"src='{src[:60]}' botão reabilitado={reabilitado}", ev)


@caso("C-MUSIC-03", "'Salvar decisão' sem responder avisa e não grava story_check.json")
def decisao_obrigatoria(page, ctx):
    antes = _snap_check(ctx)
    try:
        _restaura_check(ctx, None)
        page.reload()
        H.esperar_tela(page)
        marcados = page.locator("input[name=musClosed]:checked").count()
        page.locator("#btnMusStoryCheck").click()
        t = H.esperar_toast(page, "responda")
        existe = (_audio(ctx) / "story_check.json").exists()
        return H.verifica(bool(t) and marcados == 0 and not existe, f"toast='{t}' e nada gravado",
                          f"toast='{t}' radios marcados={marcados} story_check.json={existe}")
    finally:
        _restaura_check(ctx, antes)


@caso("C-MUSIC-04", "'A história fecha' grava story_check.json e volta marcado depois do reload")
def decisao_fecha(page, ctx):
    antes = _snap_check(ctx)
    try:
        page.locator("label:has(input[name=musClosed][value='1'])").click()
        page.locator("#btnMusStoryCheck").click()
        t = H.esperar_toast(page, "decisão")
        page.wait_for_timeout(600)
        dados = json.loads((_audio(ctx) / "story_check.json").read_text())
        page.reload()
        H.esperar_tela(page)
        marcado = page.locator("input[name=musClosed][value='1']").is_checked()
        return H.verifica(dados.get("closed") is True and bool(t) and marcado,
                          f"toast='{t}' · closed=true · radio marcado após reload",
                          f"toast='{t}' story_check={dados} radio marcado={marcado}")
    finally:
        _restaura_check(ctx, antes)


@caso("C-MUSIC-05", "'Falta cena / encerramento mais forte' grava closed=false")
def decisao_falta_cena(page, ctx):
    antes = _snap_check(ctx)
    try:
        page.locator("label:has(input[name=musClosed][value='0'])").click()
        page.locator("#btnMusStoryCheck").click()
        H.esperar_toast(page, "decisão")
        page.wait_for_timeout(600)
        dados = json.loads((_audio(ctx) / "story_check.json").read_text())
        story = H.api(page, ctx, "get", f"{_base(ctx)}/story").json()
        return H.verifica(dados.get("closed") is False and story["check"]["closed"] is False,
                          "closed=false gravado e devolvido por /music/story",
                          f"story_check={dados} api.check={story['check']}")
    finally:
        _restaura_check(ctx, antes)


# ---------- painel 02: candidatas ----------
@caso("C-MUSIC-06", "chip do painel 02 conta as candidatas de /music/candidates e abre o seletor de arquivos")
def contador_candidatas(page, ctx):
    cands = _cands(page, ctx)
    txt = (page.locator("#musCounts").text_content() or "").strip()
    alvo = page.locator("#musCounts").get_attribute("for")
    aceita = page.locator("#musUpload").get_attribute("accept")
    plural = "candidata" if len(cands) == 1 else "candidatas"
    return H.verifica(txt == f"{len(cands)} {plural}" and alvo == "musUpload" and aceita == "audio/*",
                      f"chip='{txt}' for={alvo}", f"chip='{txt}' esperado='{len(cands)} {plural}' for={alvo} accept={aceita}")


@caso("C-MUSIC-07", "linha da candidata mostra nome, duração e bpm vindos da API")
def linha_candidata(page, ctx):
    cands = _cands(page, ctx)
    if not cands:
        return H.Resultado.bloqueado("seed sem candidatas de trilha")
    c = cands[0]
    row = _linha(page, c["id"])
    nome = (row.locator(".nm").text_content() or "").strip()
    meta = (row.locator(".mt").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "music-candidata", full_page=False)
    ok = nome == (c["name"] or c["file"]) and (not c.get("bpm") or f"{round(c['bpm'])} bpm" in meta)
    return H.verifica(ok, f"'{nome}' · '{meta}'", f"nome='{nome}' meta='{meta}' api={c}", ev)


@caso("C-MUSIC-08", "upload pelo painel 02 importa a música e cria a linha na lista")
def upload_musica(page, ctx):
    snap = _snap(ctx)
    try:
        ids = {c["id"] for c in _cands(page, ctx)}
        antes = len(ids)
        H.upload(page, "#musUpload", H.mp3_temp(ctx, "mus-upload", seconds=6))
        t = H.esperar_toast(page, "importad")
        page.wait_for_timeout(800)
        cands = _cands(page, ctx)
        novos = [c for c in cands if c["id"] not in ids]
        linhas = page.locator("#musList .track-row").count()
        chip = (page.locator("#musCounts").text_content() or "").strip()
        arquivo = all((_audio(ctx) / "candidates" / c["file"]).exists() for c in novos)
        ev = H.evidencia(page, ctx, "music-upload", full_page=False)
        return H.verifica(len(cands) == antes + 1 and linhas == len(cands) and arquivo,
                          f"toast='{t}' · {antes}→{len(cands)} candidatas · chip='{chip}'",
                          f"toast='{t}' candidatas {antes}→{len(cands)} linhas={linhas} chip='{chip}' arquivos={arquivo}", ev)
    finally:
        _restaura(page, ctx, snap)


@caso("C-MUSIC-09", "arrastar um arquivo sobre o painel 02 importa igual ao seletor")
def drop_musica(page, ctx):
    snap = _snap(ctx)
    try:
        antes = len(_cands(page, ctx))
        dados = base64.b64encode(H.mp3_temp(ctx, "mus-drop", seconds=5).read_bytes()).decode()
        page.evaluate("""(b64) => {
            const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
            const f = new File([bin], 'qa-drop.mp3', { type: 'audio/mpeg' });
            const dt = new DataTransfer(); dt.items.add(f);
            document.querySelector('#musPanel').dispatchEvent(
              new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
        }""", dados)
        t = H.esperar_toast(page, "importad")
        page.wait_for_timeout(800)
        cands = _cands(page, ctx)
        nomes = [c["name"] for c in cands]
        return H.verifica(len(cands) == antes + 1 and "qa-drop.mp3" in nomes,
                          f"toast='{t}' · arquivo arrastado virou candidata",
                          f"toast='{t}' candidatas {antes}→{len(cands)} nomes={nomes}")
    finally:
        _restaura(page, ctx, snap)


@caso("C-MUSIC-10", "▶ toca a faixa da linha e tocar outra pausa a primeira")
def player_faixas(page, ctx):
    snap = _snap(ctx)
    try:
        antes = _cands(page, ctx)
        mapa = _importar(page, ctx, H.mp3_temp(ctx, "mus-player", seconds=6))
        novos = [c for c in mapa.values() if c["id"] not in {c["id"] for c in antes}]
        if not novos:
            return H.Resultado.bloqueado("upload não criou a segunda candidata (dedupe)")
        a, b = antes[0]["id"], novos[0]["id"]
        _linha(page, a).locator("button.play").click()
        page.wait_for_timeout(700)
        tocando_a = page.evaluate("(id) => !document.querySelector(`.track-row[data-id='${id}'] audio`).paused", a)
        rotulo_a = (_linha(page, a).locator("button.play").text_content() or "").strip()
        _linha(page, b).locator("button.play").click()
        page.wait_for_timeout(700)
        estado = page.evaluate("""([a, b]) => ({
            a: document.querySelector(`.track-row[data-id='${a}'] audio`).paused,
            b: document.querySelector(`.track-row[data-id='${b}'] audio`).paused })""", [a, b])
        page.evaluate("() => document.querySelectorAll('#musList audio').forEach((x) => x.pause())")
        return H.verifica(tocando_a and estado["a"] and not estado["b"],
                          f"faixa 1 tocou (botão '{rotulo_a}') e pausou quando a 2ª começou",
                          f"tocando_a={tocando_a} rótulo='{rotulo_a}' depois={estado}")
    finally:
        _restaura(page, ctx, snap)


@caso("C-MUSIC-11", "clique na onda posiciona a faixa (currentTime e marcador --p)")
def onda_posiciona(page, ctx):
    cands = _cands(page, ctx)
    if not cands:
        return H.Resultado.bloqueado("seed sem candidatas de trilha")
    cid = cands[0]["id"]
    row = _linha(page, cid)
    page.evaluate("(id) => { const a = document.querySelector(`.track-row[data-id='${id}'] audio`); a.load(); }", cid)
    try:
        page.wait_for_function("(id) => (document.querySelector(`.track-row[data-id='${id}'] audio`)||{}).duration > 0",
                               arg=cid, timeout=10_000)
    except Exception:  # noqa: BLE001
        return H.Resultado.bloqueado("metadados do áudio não carregaram no navegador")
    onda = row.locator(".wave")
    box = onda.bounding_box()
    onda.click(position={"x": box["width"] * 0.75, "y": box["height"] / 2})
    page.wait_for_timeout(500)
    estado = page.evaluate("""(id) => { const r = document.querySelector(`.track-row[data-id='${id}']`);
        return { t: r.querySelector('audio').currentTime, d: r.querySelector('audio').duration,
                 p: r.querySelector('.wave').style.getPropertyValue('--p') }; }""", cid)
    frac = estado["t"] / estado["d"] if estado["d"] else 0
    return H.verifica(0.6 < frac < 0.9 and estado["p"].endswith("%"),
                      f"currentTime em {frac:.0%} da faixa (--p={estado['p']})",
                      f"estado={estado} fração={frac:.2f} (esperado ~0,75)")


@caso("C-MUSIC-12", "'Escolher' grava audio/music.*, detecta as batidas e marca a linha como escolhida")
def escolher_trilha(page, ctx):
    snap = _snap(ctx)
    try:
        antes = {c["id"] for c in _cands(page, ctx)}
        mapa = _importar(page, ctx, H.mp3_temp(ctx, "mus-escolha", seconds=10))
        novos = [c for c in mapa.values() if c["id"] not in antes]
        if not novos:
            return H.Resultado.bloqueado("upload não criou a candidata a escolher (dedupe)")
        cid = novos[0]["id"]
        _linha(page, cid).locator("button.pick").click()
        t = H.esperar_toast(page, "trilha escolhida", timeout_ms=30_000)
        page.wait_for_timeout(1500)
        arquivos = H.arquivos(_audio(ctx), "music.*")
        beats = H.api(page, ctx, "get", f"{_base(ctx)}/beats").json()
        chip = (_linha(page, cid).locator(".chip.ok").text_content() or "").strip()
        classe = _linha(page, cid).get_attribute("class") or ""
        sem_botao = _linha(page, cid).locator("button.pick").count() == 0
        ev = H.evidencia(page, ctx, "music-escolhida", full_page=False)
        ok = (arquivos == ["music.mp3"] and beats.get("duration", 0) > 0 and chip == "escolhida"
              and "sel" in classe and sem_botao)
        return H.verifica(ok, f"toast='{t}' · {arquivos} · {len(beats.get('beats', []))} batidas",
                          f"toast='{t}' arquivos={arquivos} beats.duration={beats.get('duration')} "
                          f"chip='{chip}' classe='{classe}' sem botão Escolher={sem_botao}", ev)
    finally:
        _restaura(page, ctx, snap)


# ---------- painel 03: batidas ----------
@caso("C-MUSIC-13", "painel 03 mostra 'N batidas · M impactos' e uma barra por batida de /music/beats")
def regua_batidas(page, ctx):
    page.reload()          # a tela só relê /music/beats no boot da etapa
    H.esperar_tela(page)
    beats = H.api(page, ctx, "get", f"{_base(ctx)}/beats")
    if beats.status == 404:
        return H.Resultado.bloqueado("campanha sem trilha escolhida no seed")
    b = beats.json()
    chip = (page.locator("#musBeatsChip").text_content() or "").strip()
    barras = page.locator("#musRuler .beats i").count()
    impactos = page.locator("#musRuler .beats i.imp").count()
    ev = H.evidencia(page, ctx, "music-batidas", full_page=False)
    ok = (chip == f"{len(b['beats'])} batidas · {len(b['impacts'])} impactos"
          and barras == len(b["beats"]) and impactos == len(b["impacts"]))
    return H.verifica(ok, f"chip='{chip}' · {barras} barras ({impactos} impactos)",
                      f"chip='{chip}' barras={barras}/{len(b['beats'])} impactos={impactos}/{len(b['impacts'])}", ev)


@caso("C-MUSIC-14", "redetectar batidas com outro limiar (POST /music/beats) muda a régua da tela")
def recalcular_batidas(page, ctx):
    antes = H.api(page, ctx, "get", f"{_base(ctx)}/beats")
    if antes.status == 404:
        return H.Resultado.bloqueado("campanha sem trilha escolhida no seed")
    base = antes.json()
    try:
        novo = H.api(page, ctx, "post", f"{_base(ctx)}/beats", data=json.dumps({"k": 6.0}), headers=JSON).json()
        page.reload()
        H.esperar_tela(page)
        chip = (page.locator("#musBeatsChip").text_content() or "").strip()
        impactos = page.locator("#musRuler .beats i.imp").count()
        ok = (len(novo["impacts"]) < len(base["impacts"]) and impactos == len(novo["impacts"])
              and chip == f"{len(novo['beats'])} batidas · {len(novo['impacts'])} impactos")
        return H.verifica(ok, f"impactos {len(base['impacts'])} → {len(novo['impacts'])}, régua e chip acompanham",
                          f"impactos api {len(base['impacts'])}→{len(novo['impacts'])} régua={impactos} chip='{chip}'")
    finally:
        H.api(page, ctx, "post", f"{_base(ctx)}/beats", data=json.dumps({"k": 1.5}), headers=JSON)


@caso("C-MUSIC-18", "trilha escolhida sem beats.json: o chip avisa em vez de fingir que há batidas")
def sem_beats(page, ctx):
    f = _audio(ctx) / "beats.json"
    if not f.exists():
        return H.Resultado.bloqueado("seed sem beats.json para remover")
    conteudo = f.read_text()
    try:
        f.unlink()
        page.reload()
        H.esperar_tela(page)
        chip = (page.locator("#musBeatsChip").text_content() or "").strip()
        classe = page.locator("#musBeatsChip").get_attribute("class") or ""
        barras = page.locator("#musRuler .beats i").count()
        ev = H.evidencia(page, ctx, "music-sem-beats", full_page=False)
        return H.verifica(chip == "trilha escolhida, sem batidas detectadas" and "warn" in classe and barras == 0,
                          f"chip='{chip}'", f"chip='{chip}' classe='{classe}' barras={barras}", ev)
    finally:
        f.write_text(conteudo)


@caso("C-MUSIC-19", "arquivo que não é áudio é recusado pelo import sem quebrar a tela")
def upload_invalido(page, ctx):
    snap = _snap(ctx)
    try:
        antes = len(_cands(page, ctx))
        H.upload(page, "#musUpload", H.png_temp(ctx, "mus-nao-audio"))
        t = H.esperar_toast(page, "importad")
        page.wait_for_timeout(600)
        depois = len(_cands(page, ctx))
        linhas = page.locator("#musList .track-row").count()
        return H.verifica(antes == depois and bool(t) and linhas == depois,
                          f"toast='{t}' e nenhuma candidata criada",
                          f"toast='{t}' candidatas {antes}→{depois} linhas={linhas}")
    finally:
        _restaura(page, ctx, snap)


@caso("C-MUSIC-15", "campanha sem trilha: chip 'nenhuma trilha escolhida', régua vazia e dropzone no painel 02",
      pid="vazio")
def estado_vazio(page, ctx):
    chip = (page.locator("#musBeatsChip").text_content() or "").strip()
    barras = page.locator("#musRuler .beats i").count()
    drop = (page.locator("#musList label.drop").text_content() or "").strip()
    conta = (page.locator("#musCounts").text_content() or "").strip()
    ev = H.evidencia(page, ctx, "music-vazio")
    ok = chip == "nenhuma trilha escolhida" and barras == 0 and "Arraste músicas aqui" in drop and conta == "0 candidatas"
    return H.verifica(ok, f"chip='{chip}' · dropzone visível", f"chip='{chip}' barras={barras} drop='{drop}' chip02='{conta}'", ev)


@caso("C-MUSIC-16", "campanha sem takes: painel 01 avisa e não deixa montar a sequência bruta", pid="vazio")
def story_vazio(page, ctx):
    story = H.api(page, ctx, "get", f"{_base(ctx, ctx.pid_vazio)}/story").json()
    off = page.locator("#btnMusStory").is_disabled()
    chip = (page.locator("#musStoryChip").text_content() or "").strip()
    play = page.locator("#musStoryPlay").is_visible()
    return H.verifica(off and bool(chip) and play and story["clips"] == 0,
                      f"botão desabilitado e chip '{chip}'",
                      f"botão off={off} chip='{chip}' placeholder ▶={play} story={ {k: story[k] for k in ('clips', 'warning')} }")


@caso("C-MUSIC-17", "geração de trilha por CLI: rota só por API (decisão AP-21), sem comando na tela")
def gerar_por_cli(page, ctx):
    """Decisão do dono do produto (ADH-OS-20260829-37, QA AP-21): `POST /music/generate/cost` e
    `/music/generate` ficam como `[extensão]` **só por API** — a wave 4 tirou o bloco da tela (a aula
    013 gera a trilha na UI da Higgsfield e o Studio importa) e as rotas não voltam para a UI nem são
    removidas (testes + coleção Postman)."""
    botoes = page.locator("#main button").evaluate_all("els => els.map(e => (e.textContent || '').trim())")
    na_tela = [b for b in botoes if "gerar" in b.lower() and ("cli" in b.lower() or "crédito" in b.lower())]
    custo = H.api(page, ctx, "post", f"{_base(ctx)}/generate/cost",
                  data=json.dumps({"prompt": "qa", "duration": 30, "count": 1}), headers=JSON)
    estado = custo.json() if custo.ok else {"status": custo.status}
    viva = (custo.ok and isinstance(estado.get("per_track"), (int, float)) and estado["per_track"] > 0) \
        or 400 <= custo.status < 500
    res = H.verifica(not na_tela and viva,
                     f"tela sem comando de geração paga e /music/generate/cost vivo: {estado}",
                     f"comandos na tela={na_tela} · /music/generate/cost http={custo.status} body={estado}")
    return res.esperando(custo.status) if not custo.ok else res
