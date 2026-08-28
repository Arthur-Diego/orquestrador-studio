"""Contrato HTTP da etapa 4 — Storyboard (FastAPI TestClient), sem rede, sem CLI, sem navegador."""
import json

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def pid(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink", "vibe": "snow neon"}).json()["id"]


@pytest.fixture()
def root(studio_env, pid):
    return studio_env["refs"].project_dir(pid)


@pytest.fixture()
def base(root):
    """Handoff da etapa 3 (OS-003) mockado: a base real chega na integração da wave."""
    return make_image(root / "base" / "base_final.png")


def test_step_is_registered_as_plugin(client):
    step = next(s for s in client.get("/api/steps").json() if s["id"] == "storyboard")
    assert step["n"] == 4 and step["status"] == "ready" and step["aula"] == "010+011"
    assert client.get("/steps/storyboard/view.html").status_code == 200
    assert client.get("/steps/storyboard/view.js").status_code == 200


def test_status_and_instructions_depend_on_base_image(client, pid, root):
    st = client.get(f"/api/projects/{pid}/storyboard").json()
    assert st["has_base"] is False and st["base_image"] is None and st["storyboard_md"] is None
    body = {"kind": "edit", "text": "Make the climber even smaller and more realistic", "count": 4}
    assert client.post(f"/api/projects/{pid}/storyboard/instructions", json=body).status_code == 409
    make_image(root / "base" / "base_final.png")
    assert client.get(f"/api/projects/{pid}/storyboard").json()["has_base"] is True
    r = client.post(f"/api/projects/{pid}/storyboard/instructions", json=body)
    assert r.status_code == 200
    assert r.json()["instruction"].endswith("Keep everything else identical, realistic.")


def test_instruction_rules_of_the_lesson(client, pid, base):
    url = f"/api/projects/{pid}/storyboard/instructions"
    r = client.post(url, json={"kind": "edit", "text": "1. Make it smaller 2. Remove the rope", "count": 4})
    assert r.status_code == 422 and "uma instrução por vez" in r.json()["detail"].lower()
    assert client.post(url, json={"kind": "edit", "text": "Make it smaller", "count": 2}).status_code == 422
    assert client.post(url, json={"kind": "sketch", "text": "Make it smaller", "count": 4}).status_code == 422
    presets = client.get(url).json()
    assert presets["suffix"] == "Keep everything else identical, realistic." and len(presets["kinds"]) == 3


def test_upload_import_counts_skipped_and_dedupes(client, pid):
    files = [("files", ("a.png", image_bytes(), "image/png")),
             ("files", ("b.png", image_bytes(color=(3, 200, 3)), "image/png")),
             ("files", ("nota.txt", b"nao e imagem", "text/plain"))]
    r = client.post(f"/api/projects/{pid}/storyboard/import/upload", files=files, data={"prompt": "Make it smaller"})
    assert r.json() == {"added": 2, "skipped": 1}
    assert client.post(f"/api/projects/{pid}/storyboard/import/upload", files=files).json() == {"added": 0, "skipped": 3}
    ideas = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"]
    assert len(ideas) == 2 and all(i["file"].startswith("storyboard/candidates/") for i in ideas)
    assert all(i["thumb"].startswith("storyboard/candidates/thumbs/") for i in ideas)


def test_upload_above_the_limit_is_rejected(client, pid, monkeypatch):
    from studio.etapas.storyboard import router as sb_router
    monkeypatch.setattr(sb_router, "MAX_UPLOAD_BYTES", 10)
    r = client.post(f"/api/projects/{pid}/storyboard/import/upload",
                    files=[("files", ("grande.png", image_bytes(), "image/png"))])
    assert r.status_code == 413 and "25 MB" in r.json()["detail"]


def test_downloads_import_over_http(client, pid, studio_env):
    make_image(studio_env["tmp"] / "downloads" / "idea.png")
    r = client.post(f"/api/projects/{pid}/storyboard/import/downloads",
                    json={"since_minutes": 60, "prompt": "Make it smaller"})
    assert r.status_code == 200 and r.json()["added"] == 1
    bad = client.post(f"/api/projects/{pid}/storyboard/import/downloads",
                      json={"folder": str(studio_env["tmp"] / "nao-existe")})
    assert bad.status_code == 422


def test_history_import_needs_cli_and_maps_failures(client, pid, monkeypatch):
    import studio.higgsfield as hf
    from studio.common import ingest
    url = f"/api/projects/{pid}/storyboard/import/history"
    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.post(url, json={}).status_code == 409
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": False})
    assert client.post(url, json={}).status_code == 409
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})

    def boom(kind="image", size=50):
        raise RuntimeError("cli quebrou")
    monkeypatch.setattr(hf, "history_media", boom)
    assert client.post(url, json={}).status_code == 502

    monkeypatch.setattr(hf, "history_media", lambda kind="image", size=50: [
        {"id": "j1", "prompt": "Make it smaller", "model": "nano", "created": "", "urls": ["http://x/a.png"]}])
    monkeypatch.setattr(ingest, "urlopen", lambda *a, **k: type("R", (), {"read": staticmethod(lambda: image_bytes())})())
    r = client.post(url, json={"size": 10})
    assert r.status_code == 200 and r.json() == {"added": 1, "jobs": 1}


def test_select_ideas_writes_ideas_json_and_detaches(client, pid, root):
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(color=(1, 2, 3)), "image/png")),
                       ("files", ("b.png", image_bytes(color=(7, 8, 9)), "image/png"))])
    ideas = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"]
    a, b = [i["id"] for i in ideas]
    r = client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": [a, b]})
    assert r.json() == {"selected": 2, "detached": []}
    rows = json.loads((root / "storyboard" / "ideas" / "ideas.json").read_text())
    assert sorted(r["id"] for r in rows) == sorted([a, b])

    img = next(i["file"] for i in client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"] if i["id"] == a)
    client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": [{"text": "Close", "image": img}]})
    out = client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": [b]})
    assert out.json() == {"selected": 1, "detached": ["cena01"]}
    cena01 = client.get(f"/api/projects/{pid}/storyboard/scenes").json()["scenes"][0]
    assert cena01["images"] == [] and cena01["primary"] is None
    assert client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": ["zzz"]}).status_code == 422


def test_scenes_lifecycle_over_http(client, pid, root):
    scenes = client.get(f"/api/projects/{pid}/storyboard/scenes").json()["scenes"]
    assert len(scenes) == 5 and scenes[0] == {"id": "cena01", "n": 1, "text": "", "images": [], "primary": None}
    r = client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": [
        {"text": "A lata cai e inunda tudo"}, {"text": "Close no astronauta"}, {"text": "Puxa a corda"}]})
    assert r.status_code == 200
    assert [s["id"] for s in r.json()["scenes"]] == ["cena01", "cena02", "cena03"]
    assert r.json()["scenes"][0]["text"] == "A lata cai e inunda tudo"
    md = (root / "storyboard" / "storyboard.md").read_text()
    assert "## Cena 1" in md and "A lata cai e inunda tudo" in md
    assert client.get(f"/api/projects/{pid}/storyboard").json()["storyboard_md"] == "storyboard/storyboard.md"

    assert client.put(f"/api/projects/{pid}/storyboard/scenes",
                      json={"scenes": [{"text": f"c{i}"} for i in range(11)]}).status_code == 422
    assert client.put(f"/api/projects/{pid}/storyboard/scenes",
                      json={"scenes": [{"text": "c", "image": "../base/base_final.png"}]}).status_code == 422


def test_render_requires_written_scenes(client, pid):
    assert client.post(f"/api/projects/{pid}/storyboard/render").status_code == 422
    client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": [{"text": "Close no astronauta"}]})
    r = client.post(f"/api/projects/{pid}/storyboard/render")
    assert r.status_code == 200 and r.json()["storyboard_md"] == "storyboard/storyboard.md"


def test_scene_image_written_by_put_is_readable_by_the_next_step(client, pid, root):
    """[cross-feature] scenes.json sai no schema cena-multi-keyframe (ADR-018): {id,n,text,images,primary}.

    O consumidor a jusante da etapa 4 (angles.prepare_base) passa a semear a base pela `primary`.
    A verificação integrada da cadeia scenes.json→storyboard.json→animate é pendência da W5."""
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(), "image/png"))])
    cid = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][0]["id"]
    client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": [cid]})
    img = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][0]["file"]
    client.put(f"/api/projects/{pid}/storyboard/scenes",
               json={"scenes": [{"text": "Close", "images": [img], "primary": img}]})
    data = json.loads((root / "storyboard" / "scenes.json").read_text())
    assert set(data) == {"scenes"}
    assert set(data["scenes"][0]) == {"id", "n", "text", "images", "primary"}
    assert data["scenes"][0]["images"] == [img] and data["scenes"][0]["primary"] == img
    assert data["scenes"][0]["primary"].startswith("storyboard/ideas/")
    assert (root / data["scenes"][0]["primary"]).exists()
    assert f"![cena01](ideas/{img.rsplit('/', 1)[-1]})" in (root / "storyboard" / "storyboard.md").read_text()


def test_cli_generate_and_job_polling(client, pid, base, monkeypatch):
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": 2})
    monkeypatch.setattr(hf, "generate", lambda model, params, timeout_s=600: {"raw": {}, "urls": ["http://x/a.png"], "id": "j"})
    monkeypatch.setattr(hf, "download", lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                           dest.write_bytes(image_bytes()), dest)[-1])
    body = {"model": "nano_banana_2", "kind": "edit", "text": "Make it smaller", "count": 1}
    assert client.post(f"/api/projects/{pid}/storyboard/cost", json=body).json() == {"per_image": 2, "total": 2}
    assert client.post(f"/api/projects/{pid}/storyboard/generate", json=body).json()["state"] == "running"
    for _ in range(100):
        job = client.get(f"/api/projects/{pid}/storyboard/job").json()
        if job["state"] != "running":
            break
    assert job["state"] == "done" and job["added"] == 1
    assert client.post(f"/api/projects/{pid}/storyboard/generate",
                       json={**body, "kind": "draw_to_edit"}).status_code == 422


def test_job_is_idle_before_any_generation(client, pid):
    assert client.get(f"/api/projects/{pid}/storyboard/job").json() == {
        "state": "idle", "done": 0, "total": 0, "added": 0, "error": None, "log": []}


def test_published_presets_round_trip_through_the_validator(client, pid, base):
    """Toda fórmula devolvida pelo GET tem que ser aceita pelo POST (contrato 2 x contrato 3)."""
    presets = client.get(f"/api/projects/{pid}/storyboard/instructions").json()["presets"]
    assert any(";" in p["text"] for p in presets), "o preset de inpaint da aula usa ponto-e-vírgula"
    for preset in presets:
        r = client.post(f"/api/projects/{pid}/storyboard/instructions",
                        json={"kind": preset["kind"], "text": preset["text"], "count": 4})
        assert r.status_code == 200, (preset["label"], r.status_code, r.text)


def test_unknown_project_is_404_on_every_storyboard_route(client):
    for method, path, kw in [
        ("get", "/api/projects/nope/storyboard", {}),
        ("get", "/api/projects/nope/storyboard/instructions", {}),
        ("post", "/api/projects/nope/storyboard/instructions", {"json": {"kind": "edit", "text": "x", "count": 4}}),
        ("post", "/api/projects/nope/storyboard/import/downloads", {"json": {}}),
        ("get", "/api/projects/nope/storyboard/candidates", {}),
        ("post", "/api/projects/nope/storyboard/candidates/select", {"json": {"ids": []}}),
        ("get", "/api/projects/nope/storyboard/scenes", {}),
        ("put", "/api/projects/nope/storyboard/scenes", {"json": {"scenes": [{"text": "a"}]}}),
        ("post", "/api/projects/nope/storyboard/render", {}),
        ("get", "/api/projects/nope/storyboard/job", {}),
        ("post", "/api/projects/../x/storyboard/render", {}),
    ]:
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 404, (path, r.status_code, r.text)


# ---------- wave 2: guia na tela e correções da auditoria (4.1–4.6) ----------
def test_view_follows_the_wave2_screen_contract(client):
    """A tela expõe o painel de guia, para os polls ao sair e usa os componentes compartilhados."""
    html = client.get("/steps/storyboard/view.html").text
    js = client.get("/steps/storyboard/view.js").text
    assert '<section id="guide" class="guide"></section>' in html
    assert "Etapa 4 · aulas 010 + 011" in html
    assert 'Studio.register("storyboard"' in js
    assert 'Studio.ui.renderGuide("storyboard")' in js.replace("ui.renderGuide", "Studio.ui.renderGuide")
    # Wave 4: a etapa 4 deixou de gerar pelo CLI — não há poll, e `destroy()` continua existindo.
    assert "destroy()" in js and "ui.poll(" not in js


def test_generate_buttons_say_where_the_generation_happens(client):
    """4.3 + wave 4 (4.15): os rótulos são os do protótipo — os botões só MONTAM a instrução."""
    html = client.get("/steps/storyboard/view.html").text
    assert "Montar instrução — gere 4 (incerto)" in html
    assert ">gere 1 (tweak)<" in html
    assert "Gerar 4 (estou incerto)" not in html and "Gerar 1 (é só um tweak)" not in html


def test_screen_mentions_the_narrative_arc_and_the_upscale_step(client, pid, base):
    """4.1 e 4.5: o arco fica no lede; o lugar do upscale migrou para o guia (wave 4, 4.20)."""
    html = client.get("/steps/storyboard/view.html").text
    assert "começo, descoberta, ação e desfecho" in html
    assert "etapa 5" not in html, "o `details` de aula saiu da tela (só a etapa 1 tem)"
    g = client.get(f"/api/projects/{pid}/guide").json()
    sb = next(x for x in g["steps"] if x["id"] == "storyboard")
    assert any("etapa 5" in c for c in sb["checklist"])


def test_screen_dropped_the_paid_cli_path(client):
    """Wave 4 (4.21/4.24): a aula 010 gera na UI da Higgsfield — o CLI sai da TELA, não da API."""
    html = client.get("/steps/storyboard/view.html").text
    js = client.get("/steps/storyboard/view.js").text
    for termo in ("Gerar via CLI", "usar como origem", "source_id", "confirmCost", "hfChip"):
        assert termo not in html and termo not in js, termo
    # As rotas continuam publicadas para quem quiser o caminho pago.
    assert client.get("/openapi.json").json()["paths"].get("/api/projects/{pid}/storyboard/generate")


def test_cli_generate_chains_on_the_selected_idea(client, pid, base, root, monkeypatch):
    """4.2: com `source_id`, o CLI parte da ideia escolhida, não de base/base_final.png."""
    import studio.higgsfield as hf
    seen = []
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    monkeypatch.setattr(hf, "cost", lambda model, params: (seen.append(params), {"credits": 1})[-1])
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(), "image/png"))])
    idea = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][0]
    body = {"model": "nano_banana_2", "kind": "edit", "text": "Make it smaller", "count": 1}
    client.post(f"/api/projects/{pid}/storyboard/cost", json=body)
    assert seen[-1]["image_references"][0].endswith("base_final.png")
    client.post(f"/api/projects/{pid}/storyboard/cost", json={**body, "source_id": idea["id"]})
    assert "storyboard/candidates" in seen[-1]["image_references"][0].replace("\\", "/")
    bad = client.post(f"/api/projects/{pid}/storyboard/cost", json={**body, "source_id": "nao-existe"})
    assert bad.status_code == 422


def test_model_options_come_from_the_backend_with_the_extension_mark(client, pid):
    """4.4: a aula só cita o Nano Banana; o GPT Image 2 é `[extensão]` e não é o padrão."""
    models = client.get(f"/api/projects/{pid}/storyboard/instructions").json()["models"]
    assert [m["id"] for m in models] == ["nano_banana_2", "gpt_image_2"]
    assert "[extensão]" in dict((m["id"], m["label"]) for m in models)["gpt_image_2"]
    js = client.get("/steps/storyboard/view.js").text
    assert "meta.models" not in js, "wave 4: o select de modelo saiu da tela junto com o CLI"


def test_two_sentence_instruction_is_accepted_over_http(client, pid, base):
    """4.6 pela API: "Make it smaller. Realistic." deixou de ser 422."""
    url = f"/api/projects/{pid}/storyboard/instructions"
    ok = client.post(url, json={"kind": "edit", "text": "Make it smaller. Realistic.", "count": 1})
    assert ok.status_code == 200
    two = client.post(url, json={"kind": "edit", "text": "Make it smaller. Remove the rope.", "count": 1})
    assert two.status_code == 422 and "heurística" in two.json()["detail"].lower()


# ---------- wave 3: redesign da tela (ADH-OS-20260826-05) ----------
def test_view_uses_the_shell_catalog_after_the_redesign(client):
    """Wave 4: DOIS painéis (01 ideias, 02 cenas), sem `details.lesson`, sem painel de importação."""
    html = client.get("/steps/storyboard/view.html").text
    js = client.get("/steps/storyboard/view.js").text
    for n in ("01", "02", "03", "04"):
        assert f'<span class="pn">{n}</span>' in html, n
    assert html.count('<span class="pn">') == 4, "ideação (01/02) + ângulos (03/04) na etapa fundida"
    assert '<details class="lesson">' not in html, "regra 4 da wave 4: `details` de aula só na etapa 1"
    assert '<div class="grid2 rev">' in html
    assert '<div id="sbScenes" class="rowlist">' in html
    assert '<div class="card wide static sb-base">' in html, "`.card.static` do shell = tile não clicável"
    assert "CARD_BTN" not in js, "o botão do tile é posicionado por CSS escopado, não por style inline"
    # A galeria de ideias passou a viver no picker aberto pela thumb da cena (4.23).
    assert 'id="sbGallery" class="gallery sm"' in js and "sbGallery" not in html


def test_prototype_shapes_of_the_wave4_screen(client):
    """Wave 4: chip único, caixa `.prompt.sm` com texto estático e cena com thumb clicável."""
    html = client.get("/steps/storyboard/view.html").text
    js = client.get("/steps/storyboard/view.js").text
    assert '<div class="prompt sm">' in html and '<p id="sbInstruction" class="txt">' in html
    assert "<textarea id=\"sbInstruction\"" not in html, "regra 4: a instrução montada é texto estático"
    assert 'id="sbCounts"' in html and 'id="sbBaseChip"' not in html and 'id="sbBaseWarn"' not in html
    assert 'id="sbKindHint"' not in html and 'id="sbHint"' not in html
    assert 'class="thumb pick sb-pick"' in js, "a thumb da cena abre o picker de ideias"
    assert "sbImg" not in js, "o `select` de imagem por cena saiu (4.31)"
    assert 'class="txt sbTxt"' in js, "o texto da cena é editável com cara de estático (4.33)"
    assert "Studio.ui.modal" in js.replace("ui.modal", "Studio.ui.modal")


def test_scenes_render_as_scene_rows_with_the_narrative_moment(client):
    """Wave 3: cada cena é uma `.scene-row` com `.mom[data-mom]` colorido pelo shell."""
    js = client.get("/steps/storyboard/view.js").text
    assert 'class="scene-row"' in js
    assert 'class="mom" data-mom=' in js
    assert '#sbScenes .scene-row' in js, "collect() lê as cenas pelo novo seletor"


def test_scene_buttons_stay_childless(client):
    """O handler usa `e.target.classList.contains`: ↑ ↓ ✕ não podem ganhar filhos."""
    import re
    js = client.get("/steps/storyboard/view.js").text
    for cls in ("sbUp", "sbDown", "sbDel"):
        m = re.search(r'<button[^>]*\b' + cls + r'\b[^>]*>(.*?)</button>', js)
        assert m, cls
        assert "<" not in m.group(1), (cls, m.group(1))
