"""Contrato HTTP da etapa 4 — Storyboard (FastAPI TestClient), sem rede, sem CLI, sem navegador."""
import json
import logging
import threading

import pytest

from tests.conftest import image_bytes, make_image

# Wave 10 · E8 (card [REACT-09]): a tela do storyboard virou React (`studio/etapas/storyboard/ui/`).
# Os testes que liam o fonte de `view.{html,js}` (contrato de DOM caixa-branca) saíram daqui e viraram
# testes Vitest de renderização em `studio/etapas/storyboard/ui/storyboard.test.tsx` — os asserts de
# BACKEND (rotas HTTP, guia, contrato do serviço) permanecem intocados neste arquivo.


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
    # A tela React vive em `studio/etapas/storyboard/ui/` e é servida pelo bundle (não pela rota
    # `/steps/<id>/view.*`, que a E10 remove). A cobertura de DOM está no substituto Vitest.


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
    # 3 kinds da aula 010 + `edit_area` `[extensão]` (inpaint-marcacao), aditivo.
    assert presets["suffix"] == "Keep everything else identical, realistic." and len(presets["kinds"]) == 4


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
    """Gate de login unificado (ADR-028): importar do histórico é o CAMINHO SUAVE — só exige o
    binário, NÃO o login. É o escape do usuário deslogado ("gere na UI e importe aqui"), então não
    barra com 409 de login como as rotas de geração paga; uma falha do CLI (inclusive deslogado)
    vira 502."""
    import studio.higgsfield as hf
    from studio.common import ingest
    url = f"/api/projects/{pid}/storyboard/import/history"
    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.post(url, json={}).status_code == 409
    monkeypatch.setattr(hf, "available", lambda: True)
    # deslogado NÃO barra o histórico (contraste com /generate): a falha do CLI mapeia para 502
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": False})

    def boom(kind="image", size=50):
        raise RuntimeError("cli quebrou")
    monkeypatch.setattr(hf, "history_media", boom)
    assert client.post(url, json={}).status_code == 502

    monkeypatch.setattr(hf, "history_media", lambda kind="image", size=50: [
        {"id": "j1", "prompt": "Make it smaller", "model": "nano", "created": "", "urls": ["http://x/a.png"]}])
    monkeypatch.setattr(ingest, "urlopen", lambda *a, **k: type("R", (), {"read": staticmethod(lambda: image_bytes())})())
    r = client.post(url, json={"size": 10})
    assert r.status_code == 200 and r.json() == {"added": 1, "jobs": 1}


def test_history_preview_lists_without_downloading(client, pid, monkeypatch):
    """`[extensão]` seletor: o preview lista as mídias com uma `key` estável e NÃO baixa nada
    (não toca em `ingest.urlopen`). Caminho SUAVE (ADR-028): só exige o binário — deslogado NÃO
    barra (como a importação do histórico), só a ausência do CLI vira 409."""
    import studio.higgsfield as hf
    from studio.common import ingest
    url = f"/api/projects/{pid}/storyboard/history/preview"
    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.get(url).status_code == 409
    monkeypatch.setattr(hf, "available", lambda: True)
    # deslogado NÃO barra o preview do histórico (contraste com /generate)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": False})

    def _no_download(*a, **k):
        raise AssertionError("preview não pode baixar mídia")
    monkeypatch.setattr(ingest, "urlopen", _no_download)
    monkeypatch.setattr(hf, "history_media", lambda kind="image", size=50: [
        {"id": "j1", "prompt": "Make it smaller", "model": "nano", "created": "", "urls": ["http://x/a.png", "http://x/b.png"]},
        {"id": "j2", "prompt": "Zoom out", "model": "nano", "created": "", "urls": ["http://x/c.png"]}])
    body = client.get(url).json()
    assert body["jobs"] == 2 and len(body["items"]) == 3
    keys = [it["key"] for it in body["items"]]
    assert len(set(keys)) == 3 and all(it["url"].startswith("http://x/") for it in body["items"])
    # filtro por prompt reduz a lista sem baixar nada
    assert len(client.get(url, params={"prompt_filter": "zoom"}).json()["items"]) == 1


def test_history_import_only_selected_keys(client, pid, monkeypatch):
    """Com `keys`, a importação baixa só as mídias escolhidas no seletor."""
    import studio.higgsfield as hf
    from studio.common import ingest
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    jobs = [{"id": "j1", "prompt": "a", "model": "nano", "created": "", "urls": ["http://x/a.png", "http://x/b.png"]}]
    monkeypatch.setattr(hf, "history_media", lambda kind="image", size=50: jobs)
    monkeypatch.setattr(ingest, "urlopen",
                        lambda *a, **k: type("R", (), {"read": staticmethod(lambda: image_bytes())})())
    only = ingest._media_key("http://x/b.png")
    r = client.post(f"/api/projects/{pid}/storyboard/import/history", json={"keys": [only]})
    assert r.status_code == 200 and r.json() == {"added": 1, "jobs": 1}
    # só a escolhida virou candidata
    assert len(client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"]) == 1


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
    assert len(scenes) == 5 and scenes[0] == {"id": "cena01", "n": 1, "text": "", "images": [], "primary": None,
                                              "video_desc": "", "video_prompt": "", "videos": [], "photos": {}}
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
    # `[extensão]` wave 7 (ADR-021): campos aditivos de vídeo por cena (retrocompat ADR-018).
    assert set(data["scenes"][0]) == {"id", "n", "text", "images", "primary",
                                      "video_desc", "video_prompt", "videos", "photos"}
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


# [ADR-035] O combo de fórmulas da aula (`presets`) foi removido; o antigo round-trip
# `test_published_presets_round_trip_through_the_validator` saiu junto com a chave publicada.


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
# Os asserts de DOM (painel de guia, rótulos dos botões, `.scene-row`/`.mom`, catálogo de classes do
# shell, formas do protótipo, ausência de caminho pago de ideação na tela) migraram para o substituto
# Vitest `studio/etapas/storyboard/ui/storyboard.test.tsx` (Wave 10 · E8). O que segue aqui é backend.
def test_narrative_arc_upscale_step_lives_in_the_guide(client, pid, base):
    """4.5 (wave 4, 4.20): o lugar do upscale é o GUIA do backend, não a tela — assert de guia."""
    g = client.get(f"/api/projects/{pid}/guide").json()
    sb = next(x for x in g["steps"] if x["id"] == "storyboard")
    assert any("etapa 5" in c for c in sb["checklist"])


def test_paid_ideation_route_stays_published(client):
    """Decisão AP-21 (wave 4): o caminho pago de IDEAÇÃO saiu da tela mas as rotas ficam publicadas."""
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
    """4.4: a aula só cita o Nano Banana; o GPT Image 2 é `[extensão]` e não é o padrão (backend)."""
    models = client.get(f"/api/projects/{pid}/storyboard/instructions").json()["models"]
    assert [m["id"] for m in models] == ["nano_banana_2", "gpt_image_2"]
    assert "[extensão]" in dict((m["id"], m["label"]) for m in models)["gpt_image_2"]


def test_two_sentence_instruction_is_accepted_over_http(client, pid, base):
    """4.6 pela API: "Make it smaller. Realistic." deixou de ser 422."""
    url = f"/api/projects/{pid}/storyboard/instructions"
    ok = client.post(url, json={"kind": "edit", "text": "Make it smaller. Realistic.", "count": 1})
    assert ok.status_code == 200
    two = client.post(url, json={"kind": "edit", "text": "Make it smaller. Remove the rope.", "count": 1})
    assert two.status_code == 422 and "heurística" in two.json()["detail"].lower()


# ---------- wave 3/4: redesign da tela ----------
# Os asserts de DOM (numeração 01–05, roteiro antes da história, catálogo de classes, formas do
# protótipo, cenas como `.scene-row`, botões sem filhos) migraram para o substituto Vitest
# `studio/etapas/storyboard/ui/storyboard.test.tsx` (Wave 10 · E8, card [REACT-09]).


# ---------- `[extensão]` wave 7 (ADR-021): vídeo por cena (contrato congelado) ----------
def _select_idea(client, pid):
    """Sobe e seleciona uma ideia; devolve o caminho relativo em storyboard/ideas/."""
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(), "image/png"))])
    cid = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][0]["id"]
    client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": [cid]})
    return client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][0]["file"]


def test_video_prompt_route_returns_template_without_claude(client, pid, monkeypatch):
    from studio.storyboard import service as sb
    monkeypatch.setattr(sb.prompter, "available", lambda: False)
    r = client.post(f"/api/projects/{pid}/storyboard/video-prompt",
                    json={"scene_id": "cena01", "description": "an astronaut walking",
                          "frames": {"mode": "single"}})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "template" and body["seconds"] == 5
    assert body["prompt"].startswith("A photorealistic cinematic animation of an astronaut walking")
    assert client.post(f"/api/projects/{pid}/storyboard/video-prompt",
                       json={"scene_id": "cena01", "description": "  "}).status_code == 422


def test_video_cost_route_resolves_model_by_mode(client, pid):
    single = client.post(f"/api/projects/{pid}/storyboard/video/cost",
                         json={"scene_id": "cena01", "mode": "single", "duration": 5})
    assert single.json() == {"model": "kling2_6", "per_item": 10, "total": 10}
    trans = client.post(f"/api/projects/{pid}/storyboard/video/cost",
                        json={"scene_id": "cena01", "mode": "start_end", "duration": 10})
    assert trans.json() == {"model": "kling3_0", "per_item": 20, "total": 20}   # ADR-023


def test_video_generate_and_job_polling(client, pid, monkeypatch):
    import studio.higgsfield as hf
    img = _select_idea(client, pid)
    client.put(f"/api/projects/{pid}/storyboard/scenes",
               json={"scenes": [{"text": "cena", "images": [img], "primary": img}]})
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    monkeypatch.setattr(hf, "generate",
                        lambda model, params, timeout_s=600: {"raw": {}, "urls": ["http://x/out.mp4"], "id": "v1"})
    monkeypatch.setattr(hf, "download", lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                           dest.write_bytes(b"mp4"), dest)[-1])
    gen = client.post(f"/api/projects/{pid}/storyboard/video/generate",
                      json={"scene_id": "cena01", "prompt": "slow dolly", "mode": "single",
                            "duration": 5, "image": img})
    assert gen.status_code == 200 and gen.json()["state"] == "running"
    for _ in range(100):
        job = client.get(f"/api/projects/{pid}/storyboard/video/job", params={"scene_id": "cena01"}).json()
        if job["state"] != "running":
            break
    assert job["state"] == "done" and job["video"] == "storyboard/cena01/video/take_1.mp4"
    scene = client.get(f"/api/projects/{pid}/storyboard/scenes").json()["scenes"][0]
    assert scene["videos"] == ["storyboard/cena01/video/take_1.mp4"] and scene["video_prompt"] == "slow dolly"


def test_video_generate_grava_no_livro_caixa_a_acao_resolvida(client, pid, monkeypatch):
    """Wave 11 (card #92): a ação do ledger é a MESMA que resolve o modelo, nunca `storyboard.video`.

    A chave genérica não existe em `settings.ACTION_KEYS`: gravá-la deixava o gasto de vídeo fora do
    painel admin e fazia `POST /api/creditos/spend` reprovar com 422 uma geração que já aconteceu.
    """
    import studio.higgsfield as hf
    from studio.common import settings
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(color=(1, 2, 3)), "image/png")),
                       ("files", ("b.png", image_bytes(color=(7, 8, 9)), "image/png"))])
    ideas = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"]
    client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": [i["id"] for i in ideas]})
    start, end = [i["file"] for i in client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"]]
    client.put(f"/api/projects/{pid}/storyboard/scenes",
               json={"scenes": [{"text": "cena", "images": [start, end], "primary": start}]})
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    monkeypatch.setattr(hf, "generate",
                        lambda model, params, timeout_s=600: {"raw": {}, "urls": ["http://x/out.mp4"], "id": "v1"})
    monkeypatch.setattr(hf, "download", lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                           dest.write_bytes(b"mp4"), dest)[-1])

    def gerar(body: dict) -> None:
        assert client.post(f"/api/projects/{pid}/storyboard/video/generate", json=body).status_code == 200
        for _ in range(100):
            job = client.get(f"/api/projects/{pid}/storyboard/video/job",
                             params={"scene_id": "cena01"}).json()
            if job["state"] != "running":
                break
        assert job["state"] == "done", job

    gerar({"scene_id": "cena01", "prompt": "slow dolly", "mode": "single", "duration": 5, "image": start})
    gerar({"scene_id": "cena01", "prompt": "morph", "mode": "start_end", "duration": 5,
           "start_image": start, "end_image": end})

    acoes = [r["action"] for r in settings.history(pid)]
    assert set(acoes) == {"storyboard.video.scene", "storyboard.video.transition"}
    assert set(acoes) <= settings.ACTION_KEYS
    # cada modo grava o modelo que a resolução por servidor escolheu (ADR-021/023)
    por_acao = {r["action"]: r["model"] for r in settings.history(pid)}
    assert por_acao == {"storyboard.video.scene": "kling2_6", "storyboard.video.transition": "kling3_0"}


def test_video_generate_requires_cli_and_prompt(client, pid, monkeypatch):
    import studio.higgsfield as hf
    img = _select_idea(client, pid)
    monkeypatch.setattr(hf, "available", lambda: False)
    r = client.post(f"/api/projects/{pid}/storyboard/video/generate",
                    json={"scene_id": "cena01", "prompt": "p", "mode": "single", "duration": 5, "image": img})
    assert r.status_code == 409, "sem CLI é pré-condição (409)"
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    assert client.post(f"/api/projects/{pid}/storyboard/video/generate",
                       json={"scene_id": "cena01", "prompt": "", "mode": "single", "duration": 5,
                             "image": img}).status_code == 422


def test_video_job_is_idle_before_any_generation(client, pid):
    job = client.get(f"/api/projects/{pid}/storyboard/video/job", params={"scene_id": "cena01"}).json()
    assert job["state"] == "idle" and job["video"] is None


def test_scenes_put_persists_per_photo_map(client, pid):
    """`[extensão]` ADR-022: o PUT /scenes grava o mapa `photos` por foto (desc/prompt) via SceneIn."""
    img = _select_idea(client, pid)
    r = client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": [
        {"text": "cena", "images": [img], "primary": img,
         "photos": {img: {"video_desc": "a can falls", "video_prompt": "slow dolly", "videos": []}}}]})
    assert r.status_code == 200
    scene = client.get(f"/api/projects/{pid}/storyboard/scenes").json()["scenes"][0]
    assert scene["photos"][img] == {"video_desc": "a can falls", "video_prompt": "slow dolly", "videos": []}


def test_status_exposes_video_models_for_the_animate_modal(client, pid):
    """`[extensão]` ADR-022: o status expõe a lista de modelos de vídeo e o default por modo."""
    st = client.get(f"/api/projects/{pid}/storyboard").json()
    assert "kling2_6" in st["video_models"] and "kling3_0_turbo" in st["video_models"]
    assert st["video_model_defaults"] == {"single": "kling2_6", "start_end": "kling3_0"}   # ADR-023


# ---------- `[extensão]` inpaint-marcacao: rota da marcação e kind `edit_area` ----------
def _post_annotation(client, pid, color=(9, 9, 9), source_id=None):
    data = {"source_id": source_id} if source_id else None
    return client.post(f"/api/projects/{pid}/storyboard/annotate",
                       files={"file": ("marcacao.png", image_bytes(color=color), "image/png")},
                       data=data)


def _fake_cli(monkeypatch, seen):
    """Fakes de `hf.*` (ADR-008): sem rede, sem CLI. `seen` acumula os params de cada chamada."""
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda: {"installed": True, "logged_in": True})
    monkeypatch.setattr(hf, "cost", lambda model, params: (seen.append(params), {"credits": 1.0})[-1])
    monkeypatch.setattr(hf, "generate",
                        lambda model, params, timeout_s=600: (seen.append(params),
                                                              {"raw": {}, "urls": ["http://x/a.png"], "id": "job1"})[-1])

    def fake_download(url, dest):
        from pathlib import Path
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(image_bytes(color=(123, 45, 67)))
        return dest
    monkeypatch.setattr(hf, "download", fake_download)


def test_annotate_route_returns_the_contract_and_serves_the_file(client, pid, base):
    """Contrato 1 do FDD: `{id, file, thumb, parent, role, deduped}` e arquivo servível por /files."""
    r = _post_annotation(client, pid)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"id", "file", "thumb", "parent", "role", "deduped"}
    assert body["parent"] == "base" and body["role"] == "annotation" and body["deduped"] is False
    assert body["file"] == f"storyboard/candidates/{body['id']}.png"
    assert client.get(f"/files/{pid}/{body['file']}").status_code == 200
    assert _post_annotation(client, pid).json()["deduped"] is True, "idempotente por SHA-1"


def test_annotate_route_error_matrix(client, pid, root):
    """404 projeto, 409 base ausente, 422 `source_id` inexistente, 413 acima de MAX_UPLOAD_BYTES."""
    assert _post_annotation(client, "nao-existe").status_code == 404
    assert _post_annotation(client, pid).status_code == 409, "sem base/base_final.png"
    make_image(root / "base" / "base_final.png")
    r = _post_annotation(client, pid, source_id="nao-existe")
    assert r.status_code == 422 and r.json()["detail"] == "ideia inexistente: nao-existe"
    from studio.etapas.storyboard.router import MAX_UPLOAD_BYTES
    grande = client.post(f"/api/projects/{pid}/storyboard/annotate",
                         files={"file": ("g.png", b"x" * (MAX_UPLOAD_BYTES + 1), "image/png")})
    assert grande.status_code == 413 and "25 MB" in grande.json()["detail"]
    ruim = client.post(f"/api/projects/{pid}/storyboard/annotate",
                       files={"file": ("r.png", b"nao sou imagem", "image/png")})
    assert ruim.status_code == 422
    assert ruim.json()["detail"] == "arquivo de marcação inválido (envie o PNG exportado pelo canvas)"


def test_edit_area_cost_requires_the_annotation_id(client, pid, base, monkeypatch):
    _fake_cli(monkeypatch, [])
    body = {"model": "nano_banana_2", "kind": "edit_area", "text": "make the rope thinner", "count": 1}
    r = client.post(f"/api/projects/{pid}/storyboard/cost", json=body)
    assert r.status_code == 422
    assert r.json()["detail"] == "o modo área marcada exige a marcação salva (annotation_id)"


def test_edit_area_cost_refuses_an_unknown_or_common_candidate(client, pid, base, monkeypatch):
    """`annotation_id` inexistente OU apontando para candidato comum (`role != "annotation"`)."""
    _fake_cli(monkeypatch, [])
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(color=(2, 2, 2)), "image/png"))])
    comum = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][0]["id"]
    body = {"model": "nano_banana_2", "kind": "edit_area", "text": "make the rope thinner", "count": 1}
    for aid in ("nao-existe", comum):
        r = client.post(f"/api/projects/{pid}/storyboard/cost", json={**body, "annotation_id": aid})
        assert r.status_code == 422 and r.json()["detail"] == f"marcação inexistente: {aid}"


def test_edit_area_cost_refuses_an_annotation_of_another_image(client, pid, base, monkeypatch):
    _fake_cli(monkeypatch, [])
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(color=(2, 2, 2)), "image/png"))])
    idea = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][0]["id"]
    ann = _post_annotation(client, pid).json()          # parent == "base"
    body = {"model": "nano_banana_2", "kind": "edit_area", "text": "make the rope thinner", "count": 1,
            "annotation_id": ann["id"], "source_id": idea}
    r = client.post(f"/api/projects/{pid}/storyboard/cost", json=body)
    assert r.status_code == 422
    assert r.json()["detail"] == f"a marcação {ann['id']} pertence a outra imagem; marque a imagem escolhida"


def test_edit_area_cost_and_generate_keep_the_current_response_shape(client, pid, base, monkeypatch):
    """Contratos 2 e 3: `{per_image,total}` e o payload do JobRegistry; a anotação some da galeria."""
    seen = []
    _fake_cli(monkeypatch, seen)
    ann = _post_annotation(client, pid).json()
    body = {"model": "nano_banana_2", "kind": "edit_area", "text": "make the rope thinner", "count": 1,
            "annotation_id": ann["id"]}
    cost = client.post(f"/api/projects/{pid}/storyboard/cost", json=body)
    assert cost.status_code == 200 and cost.json() == {"per_image": 1.0, "total": 1.0}
    assert len(seen[-1]["image_references"]) == 2
    assert seen[-1]["image_references"][0].replace("\\", "/").endswith("base/base_final.png")
    gen = client.post(f"/api/projects/{pid}/storyboard/generate", json=body)
    assert gen.status_code == 200 and gen.json()["total"] == 1
    for _ in range(100):
        job = client.get(f"/api/projects/{pid}/storyboard/job").json()
        if job["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert job["state"] == "done" and job["added"] == 1
    ideas = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"]
    assert len(ideas) == 1 and ann["id"] not in [i["id"] for i in ideas]


def test_legacy_kinds_are_unchanged_without_annotation_id(client, pid, base, monkeypatch):
    """Contrato 2 (compatibilidade): pedido antigo, sem o campo novo, com o mesmo status/mensagem."""
    seen = []
    _fake_cli(monkeypatch, seen)
    body = {"model": "nano_banana_2", "kind": "edit", "text": "Make it smaller", "count": 1}
    assert client.post(f"/api/projects/{pid}/storyboard/cost", json=body).json() == {"per_image": 1.0, "total": 1.0}
    assert len(seen[-1]["image_references"]) == 1
    r = client.post(f"/api/projects/{pid}/storyboard/cost", json={**body, "kind": "draw_to_edit"})
    assert r.status_code == 422 and "Draw to Edit" in r.json()["detail"]
    r = client.post(f"/api/projects/{pid}/storyboard/cost", json={**body, "source_id": "nao-existe"})
    assert r.status_code == 422 and r.json()["detail"] == "ideia inexistente: nao-existe"
def test_video_prompt_route_rejects_an_unknown_realism_preset(client, pid, monkeypatch):
    """T3.11 — `[extensão]`: preset de realismo fora do catálogo é 422 no router, antes do CLI."""
    from studio.storyboard import service as sb
    chamou = []
    monkeypatch.setattr(sb.prompter, "available", lambda: chamou.append(1) or True)
    r = client.post(f"/api/projects/{pid}/storyboard/video-prompt",
                    json={"scene_id": "cena01", "description": "x", "preset": "nao-existe"})
    assert r.status_code == 422 and chamou == []
    ok = client.post(f"/api/projects/{pid}/storyboard/video-prompt",
                     json={"scene_id": "cena01", "description": "x", "preset": None})
    assert ok.status_code == 200 and ok.json()["preset"] is None


# ---------- `[extensão]` wave 9 (ADR-025): roteiro por LLM (Claude fake, sem rede) ----------
def _script_fake(calls, notes="Arco fechado com o produto em primeiro plano.", short_by=0,
                 scene_text=None, broken=False, sem_rig=()):
    """Fake do Claude CLI para o roteiro: um bot OBEDIENTE.

    Lê do próprio prompt quantas cenas foram pedidas e qual rig foi exigido, e devolve esse rig
    literalmente dentro de cada `image_prompt` — é assim que o teste do critério 3a mede o
    SERVIÇO: se o preset não chegar ao prompter, o rig não aparece no roteiro gravado.

    `sem_rig` é a lista de cenas em que o bot DESOBEDECE (devolve `image_prompt` sem o rig pedido):
    é o cenário que a validação do serviço tem de barrar.
    """
    import json as _json
    import re as _re
    import subprocess

    def run(args, capture_output=True, text=True, timeout=None, **kw):
        prompt = args[2]
        calls.append({"args": args, "prompt": prompt, "timeout": timeout})
        if broken:
            return subprocess.CompletedProcess(args, 0, "sem json aqui", "")
        pedidas = int(_re.search(r"Write EXACTLY (\d+) scenes", prompt).group(1))
        rig = _re.search(r"MANDATORY RIG, IDENTICAL IN EVERY SCENE: (.+?) — write", prompt, _re.S)
        rig_text = rig.group(1) if rig else "no fixed rig"
        cenas = [{"n": i, "arc": "ignorado-pelo-modelo",
                  "text": scene_text or f"Cena {i}: o personagem age e o produto aparece.",
                  "image_prompt": (f"A cinematic photograph of scene {i}. Shot on a nice camera."
                                   if i in sem_rig else
                                   f"A cinematic photograph of scene {i}. Shot on {rig_text}."),
                  "negative": "plastic skin, HDR glow"}
                 for i in range(1, pedidas + 1 - short_by)]
        body = _json.dumps({"scenes": cenas, "notes_pt": notes}, ensure_ascii=False)
        return subprocess.CompletedProcess(args, 0, "Segue o roteiro.\n```json\n" + body + "\n```\n", "")

    return run


@pytest.fixture()
def claude(monkeypatch):
    """Claude CLI fake instalado; devolve a lista de chamadas feitas ao `subprocess.run`."""
    from studio.common import prompter
    calls = []
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter.subprocess, "run", _script_fake(calls))
    return calls


def _run_script_job(client, pid, body=None):
    """Dispara o job e faz o polling limitado da rota (padrão da etapa: sem sleep)."""
    r = client.post(f"/api/projects/{pid}/storyboard/script/generate", json=body or {})
    assert r.status_code == 200, r.text
    # Estado INICIAL do job: com o CLI fake a thread pode terminar antes da serialização da
    # resposta, então o contrato aqui é a FORMA do estado — o job nasceu (nunca "idle").
    inicial = r.json()
    assert {"state", "done", "total", "error", "log"} <= set(inicial)
    assert inicial["state"] != "idle" and inicial["total"] == 1
    for _ in range(100):
        job = client.get(f"/api/projects/{pid}/storyboard/script/job").json()
        if job["state"] != "running":
            break
        threading.Event().wait(0.05)
    return job


def test_script_generate_writes_the_suggestion_file(client, pid, base, root, claude):
    """T2.1 (critério 1): job termina `done` e grava `script.json` com as N cenas válidas."""
    job = _run_script_job(client, pid, {"count": 5})
    assert job["state"] == "done" and job["error"] is None
    data = json.loads((root / "storyboard" / "script.json").read_text())
    assert data["count"] == 5 and len(data["scenes"]) == 5
    assert data["source"] == "claude" and data["model_target"] == "nano_banana_2"
    assert [s["n"] for s in data["scenes"]] == [1, 2, 3, 4, 5]
    for s in data["scenes"]:
        assert s["text"].strip() and len(s["text"]) <= 500
        assert s["image_prompt"].strip()


def test_script_arc_comes_from_the_lesson_map(client, pid, base, root, claude):
    """T2.2 (critério 2): o arco é do servidor (`scene_arc`), não do modelo."""
    _run_script_job(client, pid, {"count": 5})
    data = json.loads((root / "storyboard" / "script.json").read_text())
    assert [s["arc"] for s in data["scenes"]] == ["comeco", "descoberta", "acao", "acao", "desfecho"]


def test_script_carries_the_preset_rig_into_every_scene(client, pid, base, root, claude):
    """T2.3 `[cross-feature]` (critério 3a): o rig do preset aparece LITERALMENTE em cada cena."""
    from studio.common import prompter
    _run_script_job(client, pid, {"count": 5, "preset": "documentary-street"})
    rig = prompter.REALISM_PRESETS["documentary-street"]["rig"]
    data = json.loads((root / "storyboard" / "script.json").read_text())
    assert data["preset"] == "documentary-street"
    for s in data["scenes"]:
        for chave in ("camera", "lens", "format"):
            assert rig[chave] in s["image_prompt"], (s["n"], chave)


def test_script_action_shows_up_in_the_provider_catalog(client, pid):
    """T2.4 `[cross-feature]` (R3): o handoff da wave — a chave da ação registrada em import time.

    O endpoint da provedora devolve `{preset, source}` por ação (contrato congelado em
    `creditos/router.py::_preset_defaults`); o `kind` fica na resolução in-process.
    """
    from studio.common import settings
    for url in ("/api/prompter/presets", f"/api/prompter/presets?pid={pid}"):
        defaults = client.get(url).json()["defaults"]
        assert defaults["storyboard.script"] == {"preset": "documentary-street", "source": "code"}
    assert settings.preset_default_for("storyboard.script", pid) == {
        "kind": "storyboard.script", "preset": "documentary-street", "source": "code"}


def test_script_without_preset_uses_the_resolved_default(client, pid, base, root, claude):
    """T2.5 (critério 4): campo AUSENTE resolve o default por settings e o registra no arquivo."""
    from studio.common import prompter
    _run_script_job(client, pid, {"count": 2})
    data = json.loads((root / "storyboard" / "script.json").read_text())
    assert data["preset"] == "documentary-street"
    rig = prompter.REALISM_PRESETS["documentary-street"]["rig"]
    assert all(rig["camera"] in s["image_prompt"] for s in data["scenes"])


def test_script_with_null_preset_sends_no_rig(client, pid, base, root, claude):
    """T2.6: `preset: null` é escolha explícita de "sem rig" — nem no arquivo nem no prompt."""
    _run_script_job(client, pid, {"count": 2, "preset": None})
    data = json.loads((root / "storyboard" / "script.json").read_text())
    assert data["preset"] is None
    assert "MANDATORY RIG" not in claude[0]["prompt"]


def test_script_honours_the_project_preset_override(client, pid, base, root, claude):
    """T2.7: override de projeto (rota da provedora) vence o default de código."""
    r = client.put(f"/api/projects/{pid}/prompter/preset-config",
                   json={"kind": "storyboard.script", "preset": "arri-natural-narrative"})
    assert r.status_code == 200
    assert client.get(f"/api/projects/{pid}/storyboard").json()["script_preset_default"] == "arri-natural-narrative"
    _run_script_job(client, pid, {"count": 2})
    data = json.loads((root / "storyboard" / "script.json").read_text())
    assert data["preset"] == "arri-natural-narrative"


def test_script_unknown_preset_is_422_before_the_cli(client, pid, base, root, claude):
    """T2.8: preset fora do catálogo → 422 com os ids válidos, sem tocar no CLI nem no disco."""
    r = client.post(f"/api/projects/{pid}/storyboard/script/generate", json={"preset": "nao-existe"})
    assert r.status_code == 422 and "documentary-street" in r.json()["detail"]
    assert claude == [] and not (root / "storyboard" / "script.json").exists()


def test_script_aspect_ratio_comes_from_the_project(client, pid, base, root, claude):
    """T2.9 (critério 5): a proporção é a da campanha (não vem do body); ausente → 16:9."""
    _run_script_job(client, pid, {"count": 2})
    data = json.loads((root / "storyboard" / "script.json").read_text())
    assert data["aspect_ratio"] == "16:9" and "16:9" in claude[0]["prompt"]
    meta = json.loads((root / "project.json").read_text())
    (root / "project.json").write_text(json.dumps({**meta, "aspect_ratio": "9:16"}))
    _run_script_job(client, pid, {"count": 2})
    data = json.loads((root / "storyboard" / "script.json").read_text())
    assert data["aspect_ratio"] == "9:16" and "9:16" in claude[-1]["prompt"]


def test_script_without_claude_is_409_and_writes_nothing(client, pid, base, root, monkeypatch):
    """T2.10 (critério 8): sem Claude no PATH a geração não existe — 409 apontando o modo manual."""
    from studio.common import prompter
    monkeypatch.setattr(prompter, "BIN", None)
    r = client.post(f"/api/projects/{pid}/storyboard/script/generate", json={})
    assert r.status_code == 409 and "Claude CLI não encontrado no PATH" in r.json()["detail"]
    assert "aula 010" in r.json()["detail"]
    assert not (root / "storyboard" / "script.json").exists()
    assert client.get(f"/api/projects/{pid}/storyboard").json()["script_cli"] is False


def test_script_without_base_image_is_409(client, pid, root, claude):
    """T2.11: sem a base da etapa 3 o roteiro não começa (mesma mensagem de precondição da etapa)."""
    r = client.post(f"/api/projects/{pid}/storyboard/script/generate", json={})
    assert r.status_code == 409 and r.json()["detail"] == "Imagem base ausente: conclua a etapa 3 (base)"
    assert claude == [] and not (root / "storyboard" / "script.json").exists()


def test_script_job_is_one_per_project(client, pid, base, studio_env, claude):
    """T2.12: um job de roteiro por projeto — o segundo pedido é 409 enquanto o primeiro corre.

    Usa o fixture `claude` para o CLI parecer instalado: sem ele, num ambiente sem Claude no
    PATH (CI), o endpoint responde 409 "CLI não encontrado" antes de chegar na guarda de
    concorrência, e a asserção da mensagem falha."""
    sb = studio_env["svc"]("storyboard")
    sb._story_registry._jobs[pid] = {"state": "running"}
    r = client.post(f"/api/projects/{pid}/storyboard/script/generate", json={})
    assert r.status_code == 409 and "roteiro em andamento" in r.json()["detail"]
    sb._story_registry.clear(pid)


def test_script_count_out_of_range_is_422(client, pid, base, claude):
    """T2.13: `count` segue a régua de `MAX_SCENES` (1..10)."""
    for count in (0, 11):
        r = client.post(f"/api/projects/{pid}/storyboard/script/generate", json={"count": count})
        assert r.status_code == 422, count
        assert "1..10" in r.json()["detail"]
    assert claude == []


def test_script_model_target_is_nano_banana_only(client, pid, base, claude):
    """T2.14 (gate W3 P3): v1 aceita só `nano_banana_2`; `gpt_image_2` (da ideação) é 422."""
    r = client.post(f"/api/projects/{pid}/storyboard/script/generate",
                    json={"count": 1, "model_target": "gpt_image_2"})
    assert r.status_code == 422 and "nano_banana_2" in r.json()["detail"] and claude == []
    job = _run_script_job(client, pid, {"count": 1, "model_target": "nano_banana_2"})
    assert job["state"] == "done"


def test_script_long_instruction_is_422(client, pid, base, claude):
    """T2.15: a instrução livre respeita o teto `MAX_TEXT` (300) da etapa."""
    r = client.post(f"/api/projects/{pid}/storyboard/script/generate",
                    json={"count": 1, "instruction": "a" * 301})
    assert r.status_code == 422 and "300" in r.json()["detail"] and claude == []
    ok = client.post(f"/api/projects/{pid}/storyboard/script/generate",
                     json={"count": 1, "instruction": "a" * 300})
    assert ok.status_code == 200


def test_script_incomplete_answer_keeps_the_previous_file(client, pid, base, root, monkeypatch, claude):
    """T2.16 (critério 9): cenas de menos → job em erro; o roteiro anterior fica byte a byte igual."""
    from studio.common import prompter
    assert _run_script_job(client, pid, {"count": 5})["state"] == "done"
    antes = (root / "storyboard" / "script.json").read_bytes()
    monkeypatch.setattr(prompter.subprocess, "run", _script_fake([], short_by=2))
    job = _run_script_job(client, pid, {"count": 5})
    assert job["state"] == "error" and "5 cenas pedidas, 3 recebidas" in job["error"]
    assert (root / "storyboard" / "script.json").read_bytes() == antes


def test_script_scene_without_the_preset_rig_is_an_error(client, pid, base, root, monkeypatch, claude):
    """Review 001 · issue_002 (critério 3 `[cross-feature]`, §6): o SERVIÇO cobra o rig de cada cena.

    O bot desobediente devolve a cena 2 sem corpo/lente/formato do preset. Leitura estrita do FDD:
    resposta inválida → job em `error`, mensagem dizendo QUAL cena e QUAL parte do rig faltou, e o
    `script.json` anterior byte a byte igual (nada de completar com conteúdo inventado).
    """
    from studio.common import prompter
    assert _run_script_job(client, pid, {"count": 3, "preset": "documentary-street"})["state"] == "done"
    antes = (root / "storyboard" / "script.json").read_bytes()
    monkeypatch.setattr(prompter.subprocess, "run", _script_fake([], sem_rig=(2,)))
    job = _run_script_job(client, pid, {"count": 3, "preset": "documentary-street"})
    rig = prompter.REALISM_PRESETS["documentary-street"]["rig"]
    assert job["state"] == "error"
    assert "cena 2 sem" in job["error"] and "documentary-street" in job["error"]
    for chave in ("camera", "lens", "format"):
        assert f'{chave} ("{rig[chave]}")' in job["error"], chave
    assert "cena 1 sem" not in job["error"] and "cena 3 sem" not in job["error"]
    assert any("roteiro falhou" in linha for linha in job["log"])
    assert (root / "storyboard" / "script.json").read_bytes() == antes


def test_script_without_preset_does_not_demand_any_rig(client, pid, base, root, monkeypatch, claude):
    """Review 001 · issue_002: `preset: null` é "sem rig" — a cobrança não pode disparar aí."""
    from studio.common import prompter
    monkeypatch.setattr(prompter.subprocess, "run", _script_fake([], sem_rig=(1, 2)))
    job = _run_script_job(client, pid, {"count": 2, "preset": None})
    assert job["state"] == "done" and job["error"] is None
    data = json.loads((root / "storyboard" / "script.json").read_text())
    assert data["preset"] is None and data["count"] == 2


def test_script_write_failure_logs_the_error_event_and_keeps_the_file(
        client, pid, base, root, studio_env, monkeypatch, claude, caplog):
    """Review 001 · issue_003 (§7 do FDD, task_02 R15): falha DEPOIS do prompter também é observável.

    Com `write_json_atomic` levantando `OSError`, o job vai a `error`, a linha `script_job` de erro
    sai UMA vez no logger `studio.storyboard` com `{pid, state, scenes, seconds, source}`, o detalhe
    aparece no `log` do job (que é o que o `progressJob` mostra) e o roteiro anterior fica intacto.
    """
    sb = studio_env["svc"]("storyboard")
    assert _run_script_job(client, pid, {"count": 2})["state"] == "done"
    antes = (root / "storyboard" / "script.json").read_bytes()

    def explode(*a, **kw):
        raise OSError("disco cheio")

    monkeypatch.setattr(sb, "write_json_atomic", explode)
    with caplog.at_level(logging.INFO, logger="studio.storyboard"):
        job = _run_script_job(client, pid, {"count": 2})
    assert job["state"] == "error" and "disco cheio" in job["error"]
    assert any("roteiro falhou: disco cheio" in linha for linha in job["log"])
    eventos = [r.getMessage() for r in caplog.records if r.getMessage().startswith("script_job ")]
    erros = [e for e in eventos if "'state': 'error'" in e]
    assert len(erros) == 1, eventos
    for campo in ("'pid'", "'state'", "'scenes'", "'seconds'", "'source'"):
        assert campo in erros[0], campo
    assert not [e for e in eventos if "'state': 'done'" in e], "não há evento de fim `done` aqui"
    assert (root / "storyboard" / "script.json").read_bytes() == antes


def test_script_get_is_200_with_null_before_any_generation(client, pid, base, claude):
    """T2.17 (critério 10): ausência de sugestão é estado normal, não 404."""
    r = client.get(f"/api/projects/{pid}/storyboard/script")
    assert r.status_code == 200 and r.json() == {"script": None}
    # §5.2: o job do roteiro também nasce `idle`, no formato do contrato.
    assert client.get(f"/api/projects/{pid}/storyboard/script/job").json() == {
        "state": "idle", "done": 0, "total": 0, "error": None, "log": []}
    _run_script_job(client, pid, {"count": 2})
    got = client.get(f"/api/projects/{pid}/storyboard/script").json()["script"]
    assert set(got) == {"generated_at", "preset", "model_target", "aspect_ratio", "count",
                        "source", "seconds", "notes_pt", "scenes"}
    # ADR-028: cada cena ganhou `shots` (nº de fotos inferido) e `shot_prompts` (fotos coesas);
    # `image_prompt` continua sendo a primeira foto (compat com o consumidor de uma foto por cena).
    assert set(got["scenes"][0]) == {"n", "arc", "text", "image_prompt", "shots", "shot_prompts",
                                     "negative"}


def test_script_status_fields_are_additive(client, pid, base, claude):
    """T2.21 (§5.4): campos novos no status, com todos os antigos preservados."""
    antes = client.get(f"/api/projects/{pid}/storyboard").json()
    assert antes["script"] == {"exists": False, "generated_at": None}
    assert antes["script_preset_default"] == "documentary-street"
    assert antes["script_models"] == [{"id": "nano_banana_2", "label": "Nano Banana Pro", "default": True}]
    assert antes["script_cli"] is True
    _run_script_job(client, pid, {"count": 2})
    depois = client.get(f"/api/projects/{pid}/storyboard").json()
    assert depois["script"]["exists"] is True and depois["script"]["generated_at"]
    antigos = [k for k in antes if not k.startswith("script")]
    assert {k: depois[k] for k in antigos} == {k: antes[k] for k in antigos}


def test_script_routes_are_404_for_an_unknown_project(client):
    """As rotas novas seguem o 404 padrão da etapa para projeto inexistente."""
    assert client.post("/api/projects/nope/storyboard/script/generate", json={}).status_code == 404
    assert client.get("/api/projects/nope/storyboard/script/job").status_code == 404
    assert client.get("/api/projects/nope/storyboard/script").status_code == 404
