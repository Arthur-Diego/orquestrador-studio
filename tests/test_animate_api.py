"""Etapa 6 — contratos HTTP da animação (sem rede: CLI da Higgsfield sempre fakeado)."""
import json

import pytest

from studio.common import ffmpeg as ff
from tests.conftest import make_image, make_video

needs_ffmpeg = pytest.mark.skipif(not ff.available(), reason="sem ffmpeg (fixtures de vídeo)")

STORYBOARD = {
    "scenes": [
        {"id": "cena01", "base": "shots/cena01/base.png", "shots": [
            {"id": "shot01", "file": "shots/cena01/shot01_final.png", "order": 1, "prompt": "the astronaut walks"},
            {"id": "shot02", "file": "shots/cena01/shot02_final.png", "order": 2, "prompt": "close on the helmet"},
        ]},
    ],
    "product_scene": None,
}


@pytest.fixture()
def project(studio_env):
    refs = studio_env["refs"]
    pid = refs.create_project("Gelo Zero", "energy drink", "snow neon")["id"]
    root = refs.project_dir(pid)
    for shot in STORYBOARD["scenes"][0]["shots"]:
        make_image(root / shot["file"])
    (root / "shots").mkdir(parents=True, exist_ok=True)
    (root / "shots" / "storyboard.json").write_text(json.dumps(STORYBOARD, ensure_ascii=False))
    return pid


@pytest.fixture()
def hf(studio_env, monkeypatch):
    """CLI presente mas inerte — nenhuma chamada real de subprocess nos testes."""
    from studio import higgsfield as hf_mod
    monkeypatch.setattr(hf_mod, "BIN", "/bin/true")
    return hf_mod


def _upload(client, pid, name, data):
    return client.post(f"/api/projects/{pid}/animate/import/upload",
                       files=[("files", (name, data, "video/mp4"))])


def _candidate_id(client, pid):
    return client.get(f"/api/projects/{pid}/animate/candidates").json()[-1]["id"]


# ---------- plugin ----------
def test_step_is_registered_as_ready(client):
    steps = {s["id"]: s for s in client.get("/api/steps").json()}
    assert steps["animate"]["status"] == "ready" and steps["animate"]["n"] == 6
    assert steps["animate"]["aula"] == "012" and steps["animate"]["title"] == "Animação"
    assert client.get("/steps/animate/view.html").status_code == 200
    assert client.get("/steps/animate/view.js").status_code == 200


def test_view_follows_the_wave_2_screen_contract(client):
    """Convenção da wave 2: painel do guia na tela, `Studio.ui` e `destroy()` sem timer órfão."""
    html = client.get("/steps/animate/view.html").text
    assert "Etapa 6 · aula 012" in html, "string fixada: não mexer"
    assert '<section id="guide" class="guide">' in html
    assert "O que fazer aqui:" in html and "O que a aula manda:" in html
    js = client.get("/steps/animate/view.js").text
    assert 'Studio.register("animate"' in js
    assert "destroy()" in js and "job.stop()" in js, "o polling não pode sobreviver à troca de tela"
    assert "Studio.ui" in js and 'ui.renderGuide("animate")' in js
    assert "an-end" in js, "campo de end frame do modo start/end (correção 6.1)"
    assert 'endrow.style.display' in js, "`.row {display:flex}` vence o atributo `hidden` (smoke Playwright)"


def test_view_uses_the_wave_3_redesign_catalog(client):
    """Wave 3: painéis numerados com `.pn`, texto de aula em `details.lesson`, shots como linhas."""
    html = client.get("/steps/animate/view.html").text
    assert '<span class="pn">01</span>' in html and '<span class="pn">02</span>' in html
    assert 'details class="lesson"' in html, "texto longo da aula vai para `details.lesson`"
    assert 'id="anShots" class="rowlist"' in html
    assert 'id="anGallery" class="gallery sm"' in html
    js = client.get("/steps/animate/view.js").text
    assert 'class="shot-row"' in js, "cada shot é uma `.shot-row` (protótipo l. 540)"
    assert '.shot-row[data-k=' in js, "o seletor acompanhou a troca de `section.panel`"
    assert 'class="take an-like' in js and '"take empty an-gen"' in js
    assert 'class="like-lbl"' in js, '`♥ like` no take escolhido'
    assert "ui.tile(" in js, "galeria de candidatos usa o helper do shell"


def test_view_keeps_every_control_of_the_step(client):
    """Regra 1 da wave 3: o redesign não remove funcionalidade — todo hook `.an-*` continua."""
    html = client.get("/steps/animate/view.html").text
    for anchor in ("anReady", "anHfState", "anReload", "anModelNote", "anWarnings", "anShots",
                   "anCandCount", "anDrop", "anUpload", "anBtnDownloads", "anDlFolder",
                   "anDlMinutes", "anBtnHistory", "anParallel", "anGallery"):
        assert f'id="{anchor}"' in html, f"id do contrato DOM sumiu: #{anchor}"
    js = client.get("/steps/animate/view.js").text
    for cls in ("an-mode", "an-camera", "an-action", "an-slow", "an-suggest", "an-endrow",
                "an-end", "an-prompt", "an-example", "an-tips", "an-duration", "an-save",
                "an-black", "an-assign", "an-model", "an-count", "an-gen", "an-aspect",
                "an-climode", "an-like", "an-takes"):
        assert cls in js, f"controle do contrato DOM sumiu: .{cls}"


# ---------- plano ----------
def test_get_shots_returns_the_plan_and_404_without_storyboard(client, studio_env, project):
    r = client.get(f"/api/projects/{project}/animate/shots")
    assert r.status_code == 200
    body = r.json()
    assert [s["shot"] for s in body["shots"]] == ["shot01", "shot02"]
    assert body["total"] == 2 and body["ready"] == 0 and body["model_order"][0] == "kling3_0"
    assert client.get("/api/projects/nao-existe/animate/shots").status_code == 404
    other = studio_env["refs"].create_project("Vazio")["id"]
    r = client.get(f"/api/projects/{other}/animate/shots")
    assert r.status_code == 404 and "storyboard.json" in r.json()["detail"]


def test_put_shot_updates_and_validates(client, project):
    client.get(f"/api/projects/{project}/animate/shots")
    url = f"/api/projects/{project}/animate/shots/cena01/shot01"
    r = client.put(url, json={"prompt": "Dramatic dolly-in", "mode": "elaborate", "duration": 10})
    assert r.status_code == 200 and r.json()["duration"] == 10 and r.json()["mode"] == "elaborate"
    assert client.put(url, json={"duration": 7}).status_code == 422
    assert client.put(url, json={"mode": "magic"}).status_code == 422
    assert client.put(url, json={"start_end": {"end": "edit/last_frames/nope.png"}}).status_code == 422
    assert client.put(f"/api/projects/{project}/animate/shots/cena09/shot01", json={"prompt": "x"}).status_code == 404
    r = client.put(url, json={"fallback_black": True})
    assert r.status_code == 200 and r.json()["fallback_black"] is True
    plan = client.get(f"/api/projects/{project}/animate/shots").json()
    assert plan["shots"][0]["fallback_black"] is True and plan["ready"] == 1


def test_put_shot_start_end_mode_saves_the_pair_over_http(client, project):
    """6.1: a UI salva o modo e o par nasce pronto — `takes.json` registra start e end."""
    client.get(f"/api/projects/{project}/animate/shots")
    url = f"/api/projects/{project}/animate/shots/cena01/shot01"
    r = client.put(url, json={"mode": "start_end", "prompt": "slow dramatic camera"})
    assert r.status_code == 200
    assert r.json()["start_end"] == {"start": "shots/cena01/shot01_final.png",
                                     "end": "shots/cena01/shot02_final.png"}
    assert r.json()["next_image"] == "shots/cena01/shot02_final.png"
    assert client.put(url, json={"mode": "simple"}).json()["start_end"] is None


def test_put_shot_validates_the_extension_overrides(client, project):
    """6.7: proporção e modo do CLI são `[extensão]` com override; valor inválido é 422."""
    client.get(f"/api/projects/{project}/animate/shots")
    url = f"/api/projects/{project}/animate/shots/cena01/shot01"
    assert client.put(url, json={"aspect_ratio": "9:16"}).json()["aspect_ratio"] == "9:16"
    assert client.put(url, json={"cli_mode": "fast"}).json()["cli_mode"] == "fast"
    assert client.put(url, json={"aspect_ratio": "21:9"}).status_code == 422
    assert client.put(url, json={"cli_mode": "turbo"}).status_code == 422
    r = client.put(url, json={"prompt": "walk"})
    assert r.json()["aspect_ratio"] == "9:16" and r.json()["cli_mode"] == "fast", "campo ausente não apaga"
    assert client.put(url, json={"aspect_ratio": None}).json()["aspect_ratio"] is None


def test_get_shots_carries_the_screen_notes(client, project):
    """6.3, 6.5 e as opções de end frame chegam à tela pelo próprio plano."""
    body = client.get(f"/api/projects/{project}/animate/shots").json()
    assert "Kling 2.6" in body["model_note"] and "Kling 3.0" in body["model_note"]
    assert "paralelo" in body["parallel_hint"] and body["last_frames"] == []
    assert body["aspect_ratio"] == "16:9" and body["adapt_threshold"] == 6
    assert set(body["mode_tips"]) == {"simple", "elaborate", "start_end"}


def test_get_prompt_suggests_by_mode(client, project):
    base = f"/api/projects/{project}/animate/prompt?scene=cena01&shot=shot01"
    r = client.get(f"{base}&mode=simple&slow=true")
    assert r.status_code == 200 and r.json()["duration"] == 10
    assert r.json()["example_pt"].startswith("Quero que ele esteja caminhando")
    assert client.get(f"{base}&mode=start_end").status_code == 200          # shot02 é o par
    assert client.get(f"{base}&mode=magic").status_code == 422
    assert client.get(f"/api/projects/{project}/animate/prompt?scene=cena01&shot=shot02"
                      f"&mode=start_end").status_code == 422                # último da cena, sem end
    assert client.get(f"/api/projects/{project}/animate/prompt?scene=x&shot=y").status_code == 404


# ---------- importação ----------
@needs_ffmpeg
def test_upload_import_dedupes_and_lists_candidates(client, project, tmp_path):
    data = make_video(tmp_path / "a.mp4", seconds=1).read_bytes()
    assert _upload(client, project, "a.mp4", data).json() == {"added": 1}
    assert _upload(client, project, "b.mp4", data).json() == {"added": 0}
    cands = client.get(f"/api/projects/{project}/animate/candidates").json()
    assert len(cands) == 1 and cands[0]["kind"] == "video" and cands[0]["thumb"]
    assert _upload(client, "nao-existe", "a.mp4", data).status_code == 404


def test_downloads_folder_and_missing_folder(client, project):
    r = client.get("/api/animate/downloads-folder").json()
    assert "folder" in r and "exists" in r
    r = client.post(f"/api/projects/{project}/animate/import/downloads",
                    json={"folder": "/tmp/nao-existe-animate", "since_minutes": 60})
    assert r.status_code == 404


def test_history_requires_the_cli(client, project, monkeypatch):
    from studio import higgsfield as hf_mod
    monkeypatch.setattr(hf_mod, "BIN", None)
    r = client.post(f"/api/projects/{project}/animate/import/history", json={"size": 5})
    assert r.status_code == 409 and "CLI" in r.json()["detail"]


def test_history_maps_cli_failure_to_502(client, project, hf, monkeypatch):
    monkeypatch.setattr(hf, "_run", lambda args, timeout=120: (1, "", "boom"))
    r = client.post(f"/api/projects/{project}/animate/import/history", json={"size": 5})
    assert r.status_code == 502


# ---------- takes ----------
@needs_ffmpeg
def test_take_lifecycle_from_candidate_to_final(client, studio_env, project, tmp_path):
    client.get(f"/api/projects/{project}/animate/shots")
    _upload(client, project, "a.mp4", make_video(tmp_path / "a.mp4", seconds=1).read_bytes())
    cid = _candidate_id(client, project)
    url = f"/api/projects/{project}/animate/shots/cena01/shot01/takes"
    r = client.post(url, json={"candidate_id": cid})
    assert r.status_code == 201
    take = r.json()["take"]
    assert take["id"] == "take1" and take["file"] == "videos/cena01/shot01_take1.mp4"
    assert client.post(url, json={"candidate_id": cid}).status_code == 409, "mesmo vídeo duas vezes no shot"
    assert client.post(url, json={"candidate_id": "xxx"}).status_code == 404
    _upload(client, project, "b.mp4", make_video(tmp_path / "b.mp4", seconds=1, size="160x120").read_bytes())
    assert client.post(url, json={"candidate_id": _candidate_id(client, project),
                                  "model": "wan2_7"}).status_code == 422
    r = client.post(f"{url}/take1/like", json={"liked": True})
    assert r.status_code == 200 and r.json()["ready"] is True
    root = studio_env["refs"].project_dir(project)
    assert (root / "videos" / "cena01" / "shot01_final.mp4").exists()
    assert client.post(f"{url}/take9/like", json={"liked": True}).status_code == 404
    r = client.post(f"{url}/take1/like", json={"liked": False})
    assert r.json()["failures"] == 1 and not (root / "videos" / "cena01" / "shot01_final.mp4").exists()


@needs_ffmpeg
def test_takes_json_matches_the_wave_handoff_schema(client, studio_env, project, tmp_path):
    """[cross-feature] a etapa 8 (edit) lê este arquivo sem adaptação."""
    client.get(f"/api/projects/{project}/animate/shots")
    _upload(client, project, "a.mp4", make_video(tmp_path / "a.mp4", seconds=1).read_bytes())
    cid = _candidate_id(client, project)
    client.post(f"/api/projects/{project}/animate/shots/cena01/shot01/takes", json={"candidate_id": cid})
    client.post(f"/api/projects/{project}/animate/shots/cena01/shot01/takes/take1/like", json={"liked": True})
    root = studio_env["refs"].project_dir(project)
    data = json.loads((root / "animate" / "takes.json").read_text())
    assert set(data) >= {"shots"}
    shot = data["shots"][0]
    assert {"scene", "shot", "takes", "fallback_black"} <= set(shot)
    take = shot["takes"][0]
    assert {"id", "file", "liked", "model", "prompt", "duration", "start_end"} <= set(take)
    assert take["liked"] is True and (root / take["file"]).exists()
    assert take["file"] == "videos/cena01/shot01_take1.mp4" and take["start_end"] is None


# ---------- geração pelo CLI ----------
def test_cost_and_generate_need_the_cli(client, project, monkeypatch):
    from studio import higgsfield as hf_mod
    monkeypatch.setattr(hf_mod, "BIN", None)
    body = {"scene": "cena01", "shot": "shot01", "model": "kling3_0", "count": 2}
    assert client.post(f"/api/projects/{project}/animate/cost", json=body).status_code == 409
    assert client.post(f"/api/projects/{project}/animate/generate", json=body).status_code == 409
    assert client.get(f"/api/projects/{project}/animate/job").json()["state"] == "idle"


def test_cost_returns_estimate(client, project, hf, monkeypatch):
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": 25, "raw": {}})
    r = client.post(f"/api/projects/{project}/animate/cost",
                    json={"scene": "cena01", "shot": "shot01", "model": "kling3_0", "count": 2})
    assert r.status_code == 200 and r.json()["per_take"] == 25 and r.json()["total"] == 50
    assert r.json()["credits_unknown"] is False


def test_generate_validates_and_starts_a_job(client, project, hf, monkeypatch):
    import threading
    client.get(f"/api/projects/{project}/animate/shots")
    url = f"/api/projects/{project}/animate/generate"
    body = {"scene": "cena01", "shot": "shot01", "model": "kling3_0", "count": 2}
    assert client.post(url, json=body).status_code == 422, "sem prompt não gasta crédito"
    client.put(f"/api/projects/{project}/animate/shots/cena01/shot01", json={"prompt": "the astronaut walks"})
    assert client.post(url, json={**body, "model": "wan2_7"}).status_code == 422
    assert client.post(url, json={**body, "count": 9}).status_code == 422
    assert client.post(url, json={**body, "scene": "cena09"}).status_code == 404
    gate = threading.Event()
    monkeypatch.setattr(hf, "generate", lambda *a, **k: (gate.wait(5), {"raw": {}, "urls": [], "id": "x"})[1])
    r = client.post(url, json=body)
    assert r.status_code == 202 and r.json()["state"] == "running" and r.json()["total"] == 2
    assert client.post(url, json=body).status_code == 409, "um job por projeto"
    assert client.get(f"/api/projects/{project}/animate/job").json()["shot"] == "shot01"
    gate.set()
    for _ in range(200):
        if client.get(f"/api/projects/{project}/animate/job").json()["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert client.get(f"/api/projects/{project}/animate/job").json()["state"] == "done"
