"""Etapa 8 pela API: timeline, cortes nos impactos, SFX, último frame e render."""
from __future__ import annotations

import pytest

from tests.conftest import make_audio
from tests.test_edit_service import has_ffmpeg, seed


@pytest.fixture()
def project(studio_env):
    meta = studio_env["refs"].create_project("Gelo Zero", "energy drink", "snow neon")
    return meta["id"]


@pytest.fixture()
def root(studio_env, project):
    return studio_env["refs"].project_dir(project)


def url(pid: str, path: str = "") -> str:
    return f"/api/projects/{pid}/edit{path}"


def body(timeline: dict) -> dict:
    return {k: timeline[k] for k in ("clips", "blacks", "music", "sfx", "fade_out")}


# ---------- timeline ----------
def test_get_timeline_creates_then_reads(client, project, root):
    seed(root)
    first = client.get(url(project, "/timeline"))
    assert first.status_code == 200
    data = first.json()
    assert data["created"] is True and len(data["timeline"]["clips"]) == 3
    assert data["duration"] == 15.0
    second = client.get(url(project, "/timeline")).json()
    assert second["created"] is False


def test_get_timeline_without_inputs_is_404(client, project, root):
    r = client.get(url(project, "/timeline"))
    assert r.status_code == 404 and "etapa 6" in r.json()["detail"]


def test_get_timeline_without_liked_is_422(client, project, root):
    seed(root, liked=(False, False, False))
    r = client.get(url(project, "/timeline"))
    assert r.status_code == 422 and "liked" in r.json()["detail"]


def test_unknown_project_is_404(client, root):
    assert client.get(url("nao-existe", "/timeline")).status_code == 404
    assert client.get(url("nao-existe", "/sfx")).status_code == 404


def test_put_timeline_saves_and_returns_duration(client, project, root):
    seed(root)
    tl = body(client.get(url(project, "/timeline")).json()["timeline"])
    tl["clips"] = [{**tl["clips"][0], "in": 0.4, "out": 2.6, "speed": 1.6, "blend": True}]
    tl["blacks"] = [{"at": 1.375, "dur": 0.2}]
    tl["music"] = {"file": "audio/music.wav", "offset": 12.0}
    tl["fade_out"] = 1.5
    r = client.put(url(project, "/timeline"), json=tl)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] is False
    assert data["duration"] == pytest.approx(2.2 / 1.6 + 0.2, abs=0.01)
    assert data["timeline"]["music"]["offset"] == 12.0
    stored = client.get(url(project, "/timeline")).json()["timeline"]
    assert stored["clips"][0]["speed"] == 1.6 and "duration" in stored["clips"][0]


@pytest.mark.parametrize("patch", [
    {"in": 3.0, "out": 3.0},
    {"in": 0.0, "out": 9.0},
    {"in": 0.0, "out": 5.0, "speed": 8.0},
])
def test_put_timeline_rejects_invalid_clip(client, project, root, patch):
    seed(root)
    tl = body(client.get(url(project, "/timeline")).json()["timeline"])
    tl["clips"] = [{**tl["clips"][0], **patch}]
    r = client.put(url(project, "/timeline"), json=tl)
    assert r.status_code == 422 and "clipe 1" in r.json()["detail"]


def test_put_timeline_rejects_fade_and_escape_path(client, project, root):
    seed(root)
    tl = body(client.get(url(project, "/timeline")).json()["timeline"])
    assert client.put(url(project, "/timeline"), json={**tl, "fade_out": 9.0}).status_code == 422
    escaped = {**tl, "clips": [{**tl["clips"][0], "file": "../../../etc/passwd"}]}
    assert client.put(url(project, "/timeline"), json=escaped).status_code == 422


def test_put_timeline_missing_file_is_404(client, project, root):
    seed(root)
    tl = body(client.get(url(project, "/timeline")).json()["timeline"])
    tl["clips"] = [{**tl["clips"][0], "file": "videos/cena01/sumiu.mp4"}]
    assert client.put(url(project, "/timeline"), json=tl).status_code == 404


def test_reset_timeline(client, project, root):
    seed(root)
    tl = body(client.get(url(project, "/timeline")).json()["timeline"])
    client.put(url(project, "/timeline"), json={**tl, "clips": []})
    r = client.post(url(project, "/timeline/reset"))
    assert r.status_code == 200 and r.json()["created"] is True
    assert len(r.json()["timeline"]["clips"]) == 3


# ---------- cortes ----------
def test_propose_cuts_without_beats_is_404(client, project, root):
    seed(root)
    client.get(url(project, "/timeline"))
    r = client.post(url(project, "/propose-cuts"), json={})
    assert r.status_code == 404 and "etapa 7" in r.json()["detail"]


def test_propose_cuts_and_apply(client, project, root):
    seed(root, impacts=[1.0, 2.5, 4.0])
    client.get(url(project, "/timeline"))
    r = client.post(url(project, "/propose-cuts"), json={"offset": 0.0, "black_dur": 0.2, "apply": False})
    assert r.status_code == 200
    assert r.json()["impacts_used"] == [1.0, 2.5, 4.0] and r.json()["applied"] is False
    assert [b["at"] for b in r.json()["timeline"]["blacks"]] == [1.0, 2.5], "preto só quando pedido"
    applied = client.post(url(project, "/propose-cuts"), json={"apply": True}).json()
    assert applied["applied"] is True
    stored = client.get(url(project, "/timeline")).json()["timeline"]
    assert stored["blacks"] == [], "sem black_dur o corte é seco (auditoria 8.1)"


def test_propose_cuts_rejects_negative_offset(client, project, root):
    seed(root, impacts=[1.0, 2.5])
    client.get(url(project, "/timeline"))
    assert client.post(url(project, "/propose-cuts"), json={"offset": -1}).status_code == 422


# ---------- SFX ----------
def test_sfx_upload_dedupe_and_extension(client, project, root, tmp_path):
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    seed(root)
    data = make_audio(tmp_path / "sfx.wav", seconds=1).read_bytes()
    r = client.post(url(project, "/sfx/upload"), files=[("files", ("respiracao.wav", data, "audio/wav"))],
                    data={"prompt": "respiração do astronauta"})
    assert r.status_code == 200 and r.json()["added"] == 1
    again = client.post(url(project, "/sfx/upload"), files=[("files", ("copia.wav", data, "audio/wav"))])
    assert again.json()["added"] == 0
    lib = client.get(url(project, "/sfx")).json()
    assert len(lib) == 1 and lib[0]["file"].startswith("edit/candidates/")
    bad = client.post(url(project, "/sfx/upload"), files=[("files", ("nota.txt", b"nada", "text/plain"))])
    assert bad.status_code == 422


def test_sfx_list_is_empty_by_default(client, project, root):
    seed(root)
    assert client.get(url(project, "/sfx")).json() == []


def test_timeline_accepts_sfx_placement(client, project, root, tmp_path):
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    seed(root)
    data = make_audio(tmp_path / "sfx.wav", seconds=1).read_bytes()
    client.post(url(project, "/sfx/upload"), files=[("files", ("respiracao.wav", data, "audio/wav"))])
    sfx = client.get(url(project, "/sfx")).json()[0]
    tl = body(client.get(url(project, "/timeline")).json()["timeline"])
    tl["sfx"] = [{"file": sfx["file"], "at": 0.5, "gain": -6.0}]
    r = client.put(url(project, "/timeline"), json=tl)
    assert r.status_code == 200 and r.json()["timeline"]["sfx"][0]["gain"] == -6.0


# ---------- último frame ----------
def test_last_frame_returns_png_and_instruction(client, project, root):
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    seed(root, real=True, seconds=1)
    r = client.post(url(project, "/last-frame"), json={"scene": "cena01", "shot": "shot01", "take": "take1"})
    assert r.status_code == 200, r.text
    assert r.json()["file"] == "edit/last_frames/shot01_last.png"
    assert "etapa 6" in r.json()["instruction"]
    assert (root / "edit" / "last_frames" / "shot01_last.png").exists()


def test_last_frame_unknown_shot_is_404(client, project, root):
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    seed(root)
    assert client.post(url(project, "/last-frame"), json={"scene": "cena09", "shot": "shot99"}).status_code == 404


def test_last_frame_without_ffmpeg_is_409(client, project, root, monkeypatch):
    from studio.etapas.edit import router as edit_router
    seed(root)
    monkeypatch.setattr(edit_router.ff, "available", lambda: False)
    r = client.post(url(project, "/last-frame"), json={"scene": "cena01", "shot": "shot01"})
    assert r.status_code == 409 and "ffmpeg" in r.json()["detail"]


# ---------- render ----------
def test_render_without_ffmpeg_is_409(client, project, root, monkeypatch):
    from studio.etapas.edit import router as edit_router
    seed(root)
    client.get(url(project, "/timeline"))
    monkeypatch.setattr(edit_router.ff, "available", lambda: False)
    assert client.post(url(project, "/render"), json={"target": "master"}).status_code == 409


def test_render_without_timeline_is_404(client, project, root):
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    seed(root)
    assert client.post(url(project, "/render"), json={"target": "master"}).status_code == 404


def test_render_bad_target_is_422(client, project, root):
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    seed(root)
    client.get(url(project, "/timeline"))
    assert client.post(url(project, "/render"), json={"target": "4k"}).status_code == 422


def test_render_job_is_idle_before_any_render(client, project, root):
    seed(root)
    assert client.get(url(project, "/render/job")).json() == {"state": "idle"}


def test_ffmpeg_chip_endpoint(client):
    r = client.get("/api/edit/ffmpeg")
    assert r.status_code == 200 and isinstance(r.json()["available"], bool)


def test_render_master_end_to_end(client, project, root):
    """[cross-feature] a UI dispara o render e acompanha por polling até o master ficar pronto."""
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    import threading
    seed(root, real=True, seconds=2, impacts=[1.0, 1.8, 2.6])
    client.get(url(project, "/timeline"))
    client.post(url(project, "/propose-cuts"), json={"apply": True})
    started = client.post(url(project, "/render"), json={"target": "master"})
    assert started.status_code == 200 and started.json()["state"] == "running"
    assert client.post(url(project, "/render"), json={"target": "master"}).status_code == 409
    job = {}
    for _ in range(1200):
        job = client.get(url(project, "/render/job")).json()
        if job["state"] != "running":
            break
        threading.Event().wait(0.2)
    assert job["state"] == "done", job.get("error")
    assert job["output"] == "edit/master.mp4" and job["done"] == job["total"]
    assert (root / "edit" / "master.mp4").exists()
    assert client.get(f"/files/{project}/edit/master.mp4").status_code == 200


# ---------- fidelidade à aula (wave 2) ----------
def test_master_without_track_is_409(client, project, root):
    """Auditoria 8.2: o master não sai sem a trilha da etapa 7; o rough continua liberado."""
    if not has_ffmpeg():
        pytest.skip("ffmpeg não disponível")
    seed(root, music=False)
    client.get(url(project, "/timeline"))
    r = client.post(url(project, "/render"), json={"target": "master"})
    assert r.status_code == 409 and "etapa 7" in r.json()["detail"]
    assert client.post(url(project, "/render"), json={"target": "rough"}).status_code == 200


def test_timeline_accepts_zoom_and_loudnorm(client, project, root):
    seed(root)
    tl = body(client.get(url(project, "/timeline")).json()["timeline"])
    assert all(c["zoom"] == 1.0 for c in tl["clips"])
    tl["clips"][0]["zoom"] = 1.15
    tl["loudnorm"] = False
    r = client.put(url(project, "/timeline"), json=tl)
    assert r.status_code == 200, r.text
    stored = client.get(url(project, "/timeline")).json()["timeline"]
    assert stored["clips"][0]["zoom"] == 1.15 and stored["loudnorm"] is False

    tl["clips"][0]["zoom"] = 1.9
    assert client.put(url(project, "/timeline"), json=tl).status_code == 422


def test_step_screen_carries_the_lesson_texts(client):
    """Auditoria 8.5, 8.9, 8.10 + convenção de tela da wave 2."""
    html = client.get("/steps/edit/view.html").text
    js = client.get("/steps/edit/view.js").text
    assert "Etapa 8 · aula 014" in html
    assert '<section id="guide" class="guide"></section>' in html
    assert "gelo, ambiência, respiração e impacto" in html, "lista literal da aula (8.9)"
    assert "publique o seu trabalho, mesmo imperfeito" in html, "dever de casa da aula (8.10)"
    assert "pequeno zoom" in html and "[extensão]" in html
    assert 'id="editRuler"' in html and "marcador ▾" in html, "régua de impactos sobre a timeline (8.5)"
    assert "corte seco" in html, "o preto deixou de ser regra de todo corte (8.1)"
    assert "Studio.ui" in js and "destroy()" in js and "ctx.guide()" in js


def test_step_screen_consumes_the_shell_catalog(client):
    """Wave 3 (ADH-OS-20260826-07): a tela usa o catálogo de classes do shell, não markup próprio."""
    html = client.get("/steps/edit/view.html").text
    js = client.get("/steps/edit/view.js").text
    # 04 painéis numerados com `.pn`; texto de aula em `details.lesson`
    assert html.count('<span class="pn">') == 4
    assert '<span class="pn">01</span>' in html and '<span class="pn">04</span>' in html
    assert '<details class="lesson">' in html
    # régua da trilha: `.beats.sm` pelo helper + eixo `.beats-axis` do protótipo
    assert 'id="editRuler"' in html and 'class="beats-axis' in html
    assert "ui.beats(" in js and "sm: true" in js
    # clipes em `.rowlist`/`.clip-row` com `input.mini`
    assert 'id="clips" class="rowlist"' in html
    assert "clip-row" in js and "cin mini" in js
    # os hooks de JS continuam existindo (nenhuma funcionalidade removida)
    for hook in ("cin", "cout", "cspeed", "czoom", "cblend", "black", "mv", "del", "sfxrow", "use"):
        assert hook in js, hook
    # nada mais é posicionado/colorido por style inline (era o desenho antigo da régua)
    assert "position:absolute" not in js and "crimson" not in js
