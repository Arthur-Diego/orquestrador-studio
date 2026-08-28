"""Etapa 4 pela API: status HTTP da matriz de erros do FDD §6 e o fluxo "modo UI + importar".

Sem rede e sem CLI: `hf.available`/`hf.status` são fakeados; nenhum teste sobe navegador.
"""
from __future__ import annotations

import json

import pytest

from tests.conftest import image_bytes, make_image
from tests.test_storyboard_angles_service import SCENES


@pytest.fixture()
def project(studio_env):
    refs = studio_env["refs"]
    pid = refs.create_project("Gelo Zero", "energy drink", "snow neon")["id"]
    root = refs.project_dir(pid)
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "scenes.json").write_text(json.dumps({"scenes": SCENES}))
    make_image(root / "storyboard" / "ideas" / "a1.png", color=(10, 40, 90))
    make_image(root / "storyboard" / "ideas" / "a2.png", color=(90, 40, 10))
    make_image(root / "base" / "base_final.png", color=(200, 200, 250))
    return pid


@pytest.fixture()
def no_cli(monkeypatch, studio_env):
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: False)
    monkeypatch.setattr(hf, "status", lambda: {"installed": False, "logged_in": False})


@pytest.fixture()
def with_cli(monkeypatch, studio_env):
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True, "credits": 500})


def _png(name="a.png", color=(11, 22, 33)):
    return {"files": (name, image_bytes(color=color), "image/png")}


# ---------- catálogo e assets do plugin ----------
def test_angles_live_inside_the_storyboard_step(client):
    steps = {s["id"]: s for s in client.get("/api/steps").json()}
    assert "shots" not in steps, "ADR-015: a etapa 5 (shots) foi absorvida pela etapa 4"
    assert steps["storyboard"]["status"] == "ready"
    assert steps["storyboard"]["n"] == 4 and steps["storyboard"]["aula"] == "010+011"
    assert steps["storyboard"]["title"] == "Storyboard"
    assert client.get("/steps/storyboard/view.html").status_code == 200
    assert client.get("/steps/storyboard/view.js").status_code == 200


def test_unknown_project_is_404(client):
    assert client.get("/api/projects/nao-existe/storyboard/angles/scenes").status_code == 404


# ---------- cenas e base ----------
def test_scenes_requires_step_four(client, studio_env):
    pid = studio_env["refs"].create_project("Sem Storyboard")["id"]
    r = client.get(f"/api/projects/{pid}/storyboard/angles/scenes")
    assert r.status_code == 409 and "etapa 4" in r.json()["detail"]


def test_scenes_returns_warning_palette_and_status(client, project, studio_env):
    root = studio_env["refs"].project_dir(project)
    (root / "mood").mkdir(parents=True, exist_ok=True)
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": ["#0b1d3a"], "note": "neve"}))
    body = client.get(f"/api/projects/{project}/storyboard/angles/scenes").json()
    assert "ANTES do multishot" in body["warning"] and body["palette"]["colors"] == ["#0b1d3a"]
    assert len(body["scenes"]) == 5 and body["scenes"][0]["base_ready"] is False
    assert body["product_scene"] == {"ref_ready": False, "selected": False}


def test_prepare_base_routes(client, project):
    r = client.post(f"/api/projects/{project}/storyboard/angles/scenes/cena01/base", json={"source": "storyboard"})
    assert r.status_code == 200 and r.json()["base"] == "storyboard/cena01/base.png"
    assert client.post(f"/api/projects/{project}/storyboard/angles/scenes/cena09/base", json={}).status_code == 404
    assert client.post(f"/api/projects/{project}/storyboard/angles/scenes/nao-cena/base", json={}).status_code == 422
    up = client.post(f"/api/projects/{project}/storyboard/angles/scenes/cena03/base/upload",
                     files={"file": ("b.png", image_bytes(), "image/png")})
    assert up.status_code == 200 and up.json()["source"] == "upload"
    bad = client.post(f"/api/projects/{project}/storyboard/angles/scenes/cena03/base/upload",
                      files={"file": ("b.txt", b"nao e imagem", "text/plain")})
    assert bad.status_code == 422
    corrupt = client.post(f"/api/projects/{project}/storyboard/angles/scenes/cena03/base/upload",
                          files={"file": ("b.png", b"nao e imagem", "image/png")})
    assert corrupt.status_code == 422, "conteúdo corrompido é erro do usuário, não 500"


def test_prepare_base_without_image_is_409(client, project, studio_env):
    (studio_env["refs"].project_dir(project) / "base" / "base_final.png").unlink()
    r = client.post(f"/api/projects/{project}/storyboard/angles/scenes/cena03/base", json={})
    assert r.status_code == 409 and "etapa 3" in r.json()["detail"]


# ---------- prompts ----------
def test_prompt_routes(client, project):
    url = f"/api/projects/{project}/storyboard/angles/scenes/cena01/prompts"
    body = client.get(url, params={"kind": "angle", "subject": "the astronaut"}).json()
    assert "Bring me another point of view of this image" in body["prompts"][0]["text"]
    assert "ANTES do multishot" in body["warning"]
    plain = client.get(url, params={"kind": "angle", "realism": "false"}).json()
    assert "RED Komodo" not in plain["prompts"][0]["text"]
    edit = client.get(url, params={"kind": "edit", "edits": ["Remove the can", "Tint the visor"]}).json()
    assert edit["prompts"][0]["text"].endswith("Keep everything else identical, realistic.")
    assert client.get(url, params={"kind": "edit"}).status_code == 422
    assert client.get(url, params={"kind": "coisa"}).status_code == 422
    assert client.get(f"/api/projects/{project}/storyboard/angles/scenes/cena09/prompts").status_code == 404


# ---------- importação ----------
def test_import_upload_flow(client, project):
    scene = f"/api/projects/{project}/storyboard/angles/scenes/cena01"
    assert client.post(f"{scene}/import/upload", files=_png()).status_code == 409, "base não preparada"
    client.post(f"{scene}/base", json={})
    assert client.post(f"{scene}/import/upload", files=_png()).json()["added"] == 1
    assert client.post(f"{scene}/import/upload", files=_png()).json()["added"] == 0, "dedupe por conteúdo"
    body = client.get(f"{scene}/candidates").json()
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["thumb"].startswith("storyboard/cena01/candidates/thumbs/")


def test_import_downloads_missing_folder_is_404(client, project):
    scene = f"/api/projects/{project}/storyboard/angles/scenes/cena01"
    client.post(f"{scene}/base", json={})
    r = client.post(f"{scene}/import/downloads", json={"folder": "/nao/existe"})
    assert r.status_code == 404


def test_downloads_folder_route(client):
    body = client.get("/api/storyboard/angles/downloads-folder").json()
    assert "folder" in body and isinstance(body["exists"], bool)


def test_import_history_without_cli_is_409(client, project, no_cli):
    scene = f"/api/projects/{project}/storyboard/angles/scenes/cena01"
    client.post(f"{scene}/base", json={})
    assert client.post(f"{scene}/import/history", json={}).status_code == 409


def test_import_history_cli_failure_is_502(client, project, with_cli, monkeypatch):
    import studio.higgsfield as hf
    scene = f"/api/projects/{project}/storyboard/angles/scenes/cena01"
    client.post(f"{scene}/base", json={})

    def boom(*a, **k):
        raise RuntimeError("higgsfield: sessão expirada")

    monkeypatch.setattr(hf, "history_media", boom)
    assert client.post(f"{scene}/import/history", json={}).status_code == 502


# ---------- seleção e storyboard ----------
def _import_two(client, project, scene="cena01"):
    base = f"/api/projects/{project}/storyboard/angles/scenes/{scene}"
    client.post(f"{base}/base", json={})
    client.post(f"{base}/import/upload", files=_png("a.png", (11, 22, 33)))
    client.post(f"{base}/import/upload", files=_png("b.png", (44, 55, 66)))
    return [c["id"] for c in client.get(f"{base}/candidates").json()["candidates"]]


def test_select_and_storyboard_routes(client, project):
    assert client.get(f"/api/projects/{project}/storyboard/angles/storyboard").status_code == 404
    a, b = _import_two(client, project)
    r = client.post(f"/api/projects/{project}/storyboard/angles/scenes/cena01/select",
                    json={"shots": [{"id": b, "upscaled": True}, {"id": a}]})
    assert r.status_code == 200
    assert [s["file"] for s in r.json()["shots"]] == ["storyboard/cena01/shot01_final.png",
                                                      "storyboard/cena01/shot02_final.png"]
    board = client.get(f"/api/projects/{project}/storyboard/angles/storyboard").json()
    assert [s["id"] for s in board["scenes"]] == [s["id"] for s in SCENES]
    assert board["product_scene"] is None
    bad = client.post(f"/api/projects/{project}/storyboard/angles/scenes/cena01/select",
                      json={"shots": [{"id": "naoexiste"}]})
    assert bad.status_code == 422
    assert client.post(f"/api/projects/{project}/storyboard/angles/scenes/cena09/select",
                       json={"shots": []}).status_code == 404


def test_selected_frames_are_served_as_project_files(client, project):
    a, _b = _import_two(client, project)
    client.post(f"/api/projects/{project}/storyboard/angles/scenes/cena01/select", json={"shots": [{"id": a}]})
    assert client.get(f"/files/{project}/storyboard/cena01/shot01_final.png").status_code == 200


# ---------- cena do produto (aula 013) ----------
def test_product_routes(client, project, studio_env):
    api = f"/api/projects/{project}/storyboard/angles/product"
    assert client.get(f"{api}/prompts").status_code == 409, "sem imagem de referência ainda"
    root = studio_env["refs"].project_dir(project)
    (root / "base" / "base_final.png").unlink()
    r = client.post(f"{api}/ref", files={"file": ("geladeira.png", image_bytes(), "image/png")})
    assert r.status_code == 409 and "etapa 3" in r.json()["detail"]

    make_image(root / "base" / "base_final.png", color=(200, 200, 250))
    assert client.post(f"{api}/ref", files={"file": ("geladeira.png", image_bytes(), "image/png")}).status_code == 200
    assert client.post(f"{api}/ref", files={"file": ("x.png", b"lixo", "image/png")}).status_code == 422
    assert (root / "storyboard" / "product" / "ref.png").exists(), "envio inválido não destrói a referência válida"
    prompts = client.get(f"{api}/prompts").json()
    assert "Replace the can in image 1 with the can from image 2" in prompts["prompts"][0]["text"]
    assert "frozen" in prompts["prompts"][1]["text"]

    client.post(f"{api}/import/upload", files=_png("p.png", (120, 10, 10)))
    cid = client.get(f"{api}/candidates").json()["candidates"][0]["id"]
    sel = client.post(f"{api}/select", json={"id": cid, "upscaled": False}).json()
    assert sel["product_scene"]["shots"][0]["file"] == "storyboard/product/product_final.png"
    assert client.get(f"/api/projects/{project}/storyboard/angles/scenes").json()["product_scene"]["selected"] is True
    assert client.post(f"{api}/select", json={"id": None}).json()["product_scene"] is None
    assert client.post(f"{api}/select", json={"id": "naoexiste"}).status_code == 422


# ---------- CLI ----------
def test_cli_routes_are_409_without_cli(client, project, no_cli):
    scene = f"/api/projects/{project}/storyboard/angles/scenes/cena01"
    client.post(f"{scene}/base", json={})
    body = {"model": "nano_banana_2", "prompts": ["p"], "count": 1}
    assert client.post(f"{scene}/cost", json=body).status_code == 409
    assert client.post(f"{scene}/generate", json=body).status_code == 409
    assert client.post(f"{scene}/upscale", json={"id": "x"}).status_code == 409
    assert client.get(f"/api/projects/{project}/storyboard/angles/job").json()["state"] == "idle"


def test_generate_route_validates_and_starts_a_job(client, project, with_cli, monkeypatch):
    import studio.higgsfield as hf
    scene = f"/api/projects/{project}/storyboard/angles/scenes/cena01"
    client.post(f"{scene}/base", json={})
    assert client.post(f"{scene}/generate", json={"prompts": [], "count": 1}).status_code == 422
    assert client.post(f"{scene}/generate", json={"prompts": ["p"], "count": 99}).status_code == 422

    import threading
    gate = threading.Event()
    monkeypatch.setattr(hf, "generate", lambda *a, **k: (gate.wait(5), {"urls": [], "id": "x", "raw": {}})[1])
    assert client.post(f"{scene}/generate", json={"prompts": ["p"], "count": 1}).status_code == 200
    assert client.get(f"/api/projects/{project}/storyboard/angles/job").json()["state"] == "running"
    assert client.post(f"{scene}/generate", json={"prompts": ["p"], "count": 1}).status_code == 409
    gate.set()
    for _ in range(100):
        if client.get(f"/api/projects/{project}/storyboard/angles/job").json()["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert client.get(f"/api/projects/{project}/storyboard/angles/job").json()["state"] == "done"


def test_upscale_route_404_for_unknown_candidate(client, project, with_cli):
    scene = f"/api/projects/{project}/storyboard/angles/scenes/cena01"
    client.post(f"{scene}/base", json={})
    assert client.post(f"{scene}/upscale", json={"id": "naoexiste"}).status_code == 404


# ---------- wave 2: guia na tela e correções da auditoria (5.1–5.8) ----------
def test_view_follows_the_wave2_screen_contract(client):
    html = client.get("/steps/storyboard/view.html").text
    js = client.get("/steps/storyboard/view.js").text
    assert '<section id="guide" class="guide"></section>' in html
    assert "Etapa 4 · aulas 010 + 011" in html
    assert 'Studio.register("storyboard"' in js
    assert 'renderGuide("storyboard")' in js
    # A etapa 4 não gera/upscala pelo CLI pela tela — não há poll, `destroy()` continua.
    assert "destroy()" in js and "ui.poll(" not in js


def test_promote_candidate_to_scene_base_over_http(client, project):
    """5.2: POST .../base {source:"candidate", id} promove o resultado a base da cena."""
    scene = f"/api/projects/{project}/storyboard/angles/scenes/cena01"
    client.post(f"{scene}/base", json={})
    client.post(f"{scene}/import/upload", files=_png("a.png", (7, 7, 7)))
    cid = client.get(f"{scene}/candidates").json()["candidates"][0]["id"]
    r = client.post(f"{scene}/base", json={"source": "candidate", "id": cid})
    assert r.status_code == 200 and r.json()["source"] == "candidate" and r.json()["candidate"] == cid
    assert client.post(f"{scene}/base", json={"source": "candidate"}).status_code == 422
    assert client.post(f"{scene}/base", json={"source": "candidate", "id": "zzz"}).status_code == 404
    assert "Usar como base da cena" in client.get("/steps/storyboard/view.html").text \
        or "Usar como base da cena" in client.get("/steps/storyboard/view.js").text


def test_prompt_route_accepts_a_camera_preset(client, project):
    """5.3 e 5.7: bloco de câmera oferecido também na edição; presets trocáveis."""
    url = f"/api/projects/{project}/storyboard/angles/scenes/cena01/prompts"
    body = client.get(url, params={"kind": "edit", "edits": ["Remove the can"], "camera": "documentario"}).json()
    assert "Documentary style" in body["prompts"][0]["text"]
    assert [c["id"] for c in body["cameras"]] == ["red", "documentario", "wide"]
    angle = client.get(url, params={"kind": "angle", "camera": "wide"}).json()
    assert "Anamorphic lens" in angle["prompts"][0]["text"]


def test_scenes_route_publishes_aspect_ratio_and_upscale_count(client, project, studio_env):
    """5.1 e 5.6: a tela lê a proporção do projeto e o N/M de upscalados por cena."""
    body = client.get(f"/api/projects/{project}/storyboard/angles/scenes").json()
    assert body["aspect_ratio"] == "16:9" and body["scenes"][0]["upscaled"] == 0
    assert "trilha" in body["product_note"]
    client.patch(f"/api/projects/{project}", json={"aspect_ratio": "9:16"})
    assert client.get(f"/api/projects/{project}/storyboard/angles/scenes").json()["aspect_ratio"] == "9:16"


def test_select_route_returns_the_upscale_warning_and_the_document(client, project, studio_env):
    """5.1 e 5.4: o `select` avisa o que falta upscalar e regrava storyboard/frames.md."""
    scene = f"/api/projects/{project}/storyboard/angles/scenes/cena01"
    client.post(f"{scene}/base", json={})
    a, b = _import_two(client, project)
    r = client.post(f"{scene}/select", json={"shots": [{"id": a, "upscaled": True}, {"id": b}]}).json()
    assert "sem upscale" in r["warning"] and r["storyboard_md"] == "storyboard/frames.md"
    root = studio_env["refs"].project_dir(project)
    assert (root / "storyboard" / "frames.md").exists()
    ok = client.post(f"{scene}/select",
                     json={"shots": [{"id": a, "upscaled": True}, {"id": b, "upscaled": True}]}).json()
    assert ok["warning"] is None


def test_screen_shows_the_lesson_focus_examples_and_the_base_order(client, project):
    """5.5 e 5.2: exemplos de enquadramento (agora no `title`) e a ordem "base primeiro"."""
    html = client.get("/steps/storyboard/view.html").text
    js = client.get("/steps/storyboard/view.js").text
    assert "close no rosto" in html
    assert "Usar como base da cena" in js
    body = client.get(f"/api/projects/{project}/storyboard/angles/scenes/cena01/prompts").json()
    assert any("rosto" in e for e in body["focus_examples"])


# ---------- wave 3: redesign da tela (ADH-OS-20260826-05) ----------
def test_view_uses_the_shell_catalog_after_the_redesign(client):
    """Wave 4: DOIS painéis (01 cenas, 02 cena aberta), sem `details.lesson`, sem painel do produto."""
    html = client.get("/steps/storyboard/view.html").text
    js = client.get("/steps/storyboard/view.js").text
    for n in ("01", "02", "03", "04"):
        assert f'<span class="pn">{n}</span>' in html, n
    assert html.count('<span class="pn">') == 4, "ideação (01/02) + ângulos (03/04) na etapa fundida"
    assert '<details class="lesson">' not in html, "regra 4 da wave 4: `details` de aula só na etapa 1"
    assert 'id="shotsPalette" class="palette sm' in html
    assert '<div id="shotsGallery" class="gallery sm">' in html
    assert '<p class="note">' in html
    assert "CARD_BTN" not in js, "o botão do tile é posicionado por CSS escopado, não por style inline"
    # A cena do produto (aula 013) virou um card do grid do painel 01, sem galeria própria.
    assert "prodGallery" not in html and "prodGallery" not in js
    assert '"produto"' in js and 'id="prodStatus"' not in html


def test_screen_dropped_the_paid_cli_path(client):
    """Wave 4 (5.22/5.28/5.32): CLI e controles de câmera da metade ÂNGULOS saem da TELA; rotas ficam.

    `confirmCost` deixou de ser proibido no arquivo inteiro: a wave 7 (`[extensão]`, ADR-021)
    adicionou o caminho pago de VÍDEO na metade IDEAÇÃO do mesmo `view.js` (coberto por
    `test_storyboard_api::test_screen_dropped_the_paid_cli_path`). Os marcadores da metade ângulos
    (controles de câmera/lente, `hfChip`, `Upscale do último escolhido`, etc.) seguem fora da tela.
    """
    html = client.get("/steps/storyboard/view.html").text
    js = client.get("/steps/storyboard/view.js").text
    for termo in ("Gerar via CLI", "Upscale do último escolhido", "hfChip",
                  "promptCamera", "promptLens", "promptAperture", "promptRealism",
                  "shotsRatio", "shotsWarn", "btnShotsReload", "sceneText", "sh-subhead"):
        assert termo not in html and termo not in js, termo
    paths = client.get("/openapi.json").json()["paths"]
    assert paths.get("/api/projects/{pid}/storyboard/angles/scenes/{scene}/upscale")


def test_prototype_shapes_of_the_wave4_screen(client):
    """Wave 4: paleta no cabeçalho, chip/checkbox/Salvar no `.panel-head`, builder de uma linha."""
    html = client.get("/steps/storyboard/view.html").text
    js = client.get("/steps/storyboard/view.js").text
    head = html.split('<span class="pn">04</span>', 1)[1].split("</div>\n  </div>", 1)[0]
    for ident in ("shotsCounts", "shotsUpscaled", "btnShotsSave"):
        assert ident in head, ident
    assert '<div class="row wrap sh-builder" id="shotsBuilder">' in html
    assert '<div id="shotsPrompts" class="prompts one hidden">' in html, "o prompt só aparece após o clique"
    assert '<div class="prompt sm">' in js and '<p class="txt"' in js
    assert 'class="upcount' in js and 'chip sm' not in js, "o contador de upscale é texto puro (5.16)"
    assert '<span class="src">' not in js, "o selo de origem saiu dos tiles (5.37)"
    assert "Studio.ui.modal" in js.replace("ui.modal", "Studio.ui.modal")


def test_scene_cards_and_tiles_follow_the_prototype(client):
    """Wave 3: cenas como `.rowcard`, tiles com `data-ord` e selo `span.up`."""
    js = client.get("/steps/storyboard/view.js").text
    assert 'class="rowcard col pick' in js, "card de cena usa o `.rowcard.col`/.pick do shell"
    assert 'data-ord=' in js, "o check do tile escolhido vira o número da ordem"
    assert '<span class="up' in js
    assert 'class="lbl">paleta do mood' in js


def test_scene_title_keeps_the_panel_number_outside(client):
    """`#sceneTitle` é reescrito por textContent: o `.pn` fica fora dele."""
    html = client.get("/steps/storyboard/view.html").text
    assert '<span class="pn">04</span><span id="sceneTitle">' in html
    # Wave 4 (5.23): o texto da cena virou `title` do card, não uma linha abaixo do título.
    assert 'id="sceneText"' not in html
