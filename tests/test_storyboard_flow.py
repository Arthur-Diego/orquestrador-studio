"""Fluxo novo do storyboard guiado por pré-roteiro `[extensão]` (ADR-018).

Sem rede e sem Claude real: o CLI da Higgsfield e o `common/prescript` são fakes (ADR-008). Valida
o pipeline base → sementes + pré-roteiro → por cena (semente → prompt → foto → frames → ordem) e,
sobretudo, que o CONTRATO DE SAÍDA `storyboard/storyboard.json` que a animação consome é mantido."""
from __future__ import annotations

import io
import time

import pytest
from PIL import Image


def _png(color=(40, 90, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture()
def stubbed(monkeypatch, client, studio_env):
    """CLI fake (gera/baixa/estima) e Claude fake (pré-roteiro + prompt realista)."""
    import studio.common.prescript as pre
    import studio.higgsfield as hf
    n = {"i": 0}

    def fake_generate(model, params, timeout_s=600):
        n["i"] += 1
        return {"urls": [f"http://fake/img_{n['i']}.png"], "id": f"j{n['i']}", "raw": {}}

    def fake_download(url, dest):
        from pathlib import Path
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_png((n["i"] * 20 % 255, 100, 140)))
        return dest

    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "generate", fake_generate)
    monkeypatch.setattr(hf, "download", fake_download)
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": 2})
    monkeypatch.setattr(hf, "status", lambda refresh=False: {"installed": True, "logged_in": True, "credits": 500})

    def fake_prescript(base_path, seed_paths, product="", vibe="", n_scenes=4, aspect_ratio="16:9"):
        return {"scenes": [{"title": f"Cena {i}", "text": f"Plano {i}", "arc": pre.ARC[min(3, i - 1)]["id"]}
                           for i in range(1, n_scenes + 1)], "source": "template"}

    monkeypatch.setattr(pre, "generate_prescript", fake_prescript)
    monkeypatch.setattr(pre, "realistic_prompt", lambda scene_text, photo_path, aspect_ratio="16:9", product="":
                        {"prompt": f"ultra realistic cinematic photograph of {scene_text}, natural light, film grain, "
                                   "sharp focus, hyper detailed textures, no digital art look, photorealistic",
                         "negative": "cartoon, cgi", "source": "skill", "seconds": 0.0})
    return hf


def _project_with_base(client, studio_env):
    pid = client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()["id"]
    from studio.refs.service import project_dir
    base = project_dir(pid) / "base" / "base_final.png"
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_bytes(_png())
    return pid


def _wait_job(client, pid, url_suffix="/storyboard/job"):
    for _ in range(60):
        job = client.get(f"/api/projects/{pid}{url_suffix}").json()
        if job.get("state") in ("done", "error", "idle") and job.get("state") != "running":
            if job.get("state") != "running":
                return job
        time.sleep(0.1)
    return job


def test_full_flow_preserves_output_contract(client, stubbed, studio_env):
    pid = _project_with_base(client, studio_env)

    # (b) fotos-semente: 1º multishot da base
    assert client.post(f"/api/projects/{pid}/storyboard/seeds/generate", json={"count": 3}).status_code == 200
    job = _wait_job(client, pid)
    assert job["state"] == "done", job
    seeds = client.get(f"/api/projects/{pid}/storyboard/seeds").json()
    assert seeds["count"] == 3
    seed_id = seeds["seeds"][0]["id"]

    # (b) pré-roteiro
    r = client.post(f"/api/projects/{pid}/storyboard/prescript/generate", json={"n_scenes": 3})
    assert r.status_code == 200 and len(r.json()["scenes"]) == 3
    scenes = r.json()["scenes"]
    assert [s["id"] for s in scenes] == ["cena01", "cena02", "cena03"]
    assert [s["arc"] for s in scenes] == ["comeco", "descoberta", "acao"] or all(s["arc"] for s in scenes)

    scene = "cena01"
    # (c) semente da cena
    assert client.post(f"/api/projects/{pid}/storyboard/scenes/{scene}/seed", json={"seed_id": seed_id}).status_code == 200
    # (d) prompt realista
    pr = client.post(f"/api/projects/{pid}/storyboard/scenes/{scene}/prompt").json()
    assert pr["source"] == "skill" and len(pr["prompt"].split()) >= 15
    # (e) foto da cena
    assert client.post(f"/api/projects/{pid}/storyboard/scenes/{scene}/photo/generate").status_code == 200
    assert _wait_job(client, pid)["state"] == "done"
    ov = {s["id"]: s for s in client.get(f"/api/projects/{pid}/storyboard/overview").json()["scenes"]}
    assert ov[scene]["photo_ready"] is True
    # (f) frames = multishot da foto
    assert client.post(f"/api/projects/{pid}/storyboard/scenes/{scene}/frames/generate", json={"count": 2}).status_code == 200
    assert _wait_job(client, pid)["state"] == "done"
    cands = client.get(f"/api/projects/{pid}/storyboard/scenes/{scene}/candidates").json()["candidates"]
    assert len(cands) == 2
    # (g) ordenar os frames
    shots = [{"id": cands[0]["id"], "upscaled": True}, {"id": cands[1]["id"], "upscaled": True}]
    r = client.post(f"/api/projects/{pid}/storyboard/scenes/{scene}/order", json={"shots": shots})
    assert r.status_code == 200

    # CONTRATO DE SAÍDA que a animação consome (inalterado)
    board = client.get(f"/api/projects/{pid}/storyboard/angles/storyboard").json()
    assert "scenes" in board and "product_scene" in board
    c1 = next(s for s in board["scenes"] if s["id"] == "cena01")
    assert c1["base"] == "storyboard/cena01/base.png"
    assert [sh["order"] for sh in c1["shots"]] == [1, 2]
    for sh in c1["shots"]:
        assert {"id", "order", "file", "prompt"} <= set(sh)
        assert sh["file"].startswith("storyboard/cena01/shot")

    # gasto registrado (ADR-016): sementes (3) + foto (1) + frames (2) = 6 gerações
    from studio.common import settings
    s = settings.summary(pid)
    assert s["count"] == 6
    actions = {r["step"] for r in s["by_step"]}
    assert "storyboard" in actions


def test_prescript_edit_preserves_seed(client, stubbed, studio_env):
    pid = _project_with_base(client, studio_env)
    client.post(f"/api/projects/{pid}/storyboard/seeds/generate", json={"count": 2})
    _wait_job(client, pid)
    seeds = client.get(f"/api/projects/{pid}/storyboard/seeds").json()["seeds"]
    client.post(f"/api/projects/{pid}/storyboard/prescript/generate", json={"n_scenes": 2})
    client.post(f"/api/projects/{pid}/storyboard/scenes/cena01/seed", json={"seed_id": seeds[0]["id"]})
    # editar o texto do pré-roteiro não pode perder a semente já escolhida da cena
    client.put(f"/api/projects/{pid}/storyboard/prescript",
               json={"scenes": [{"title": "Nova", "text": "novo texto", "arc": "comeco"}, {"text": "b"}]})
    ov = {s["id"]: s for s in client.get(f"/api/projects/{pid}/storyboard/overview").json()["scenes"]}
    assert ov["cena01"]["text"] == "novo texto"
    assert ov["cena01"]["seed_ready"] is True


def test_photo_requires_prompt_and_seed(client, stubbed, studio_env):
    pid = _project_with_base(client, studio_env)
    client.post(f"/api/projects/{pid}/storyboard/prescript/generate", json={"n_scenes": 2})
    # sem semente/prompt → 409
    assert client.post(f"/api/projects/{pid}/storyboard/scenes/cena01/photo/generate").status_code == 409


def test_seeds_require_base(client, stubbed, studio_env):
    pid = client.post("/api/projects", json={"name": "Sem Base"}).json()["id"]
    assert client.post(f"/api/projects/{pid}/storyboard/seeds/generate", json={"count": 2}).status_code == 409


def _guide(client, pid):
    return client.get(f"/api/projects/{pid}/guide/storyboard").json()


def test_guide_reflects_the_new_flow(client, stubbed, studio_env):
    # sem base: a etapa fica bloqueada e a próxima ação aponta a etapa 3
    pid = client.post("/api/projects", json={"name": "G"}).json()["id"]
    g = _guide(client, pid)
    assert g["status"] == "blocked"
    assert "etapa 3" in (g["next_action"] or "")
    ids = {v["id"] for v in g["validations"]}
    assert {"v_seeds", "v_prescript", "v_seed_cena", "v_foto_cena", "v_frames", "v_upscale", "v_produto"} <= ids

    # com base mas sem sementes: pede as fotos-semente
    from studio.refs.service import project_dir
    base = project_dir(pid) / "base" / "base_final.png"
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_bytes(_png())
    g = _guide(client, pid)
    assert "semente" in (g["next_action"] or "").lower()
