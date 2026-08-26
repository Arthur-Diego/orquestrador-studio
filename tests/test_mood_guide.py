"""Guia da etapa 2 (aula 009) — a vibe é encontrada aqui; validações da auditoria §2.5."""
import json

import pytest

from tests.conftest import image_bytes


@pytest.fixture()
def project(client):
    return client.post("/api/projects", json={"name": "Mood Guia", "product": "energy drink"}).json()["id"]


def _guide(client, pid):
    r = client.get(f"/api/projects/{pid}/guide/mood")
    assert r.status_code == 200, r.text
    return r.json()


def _checks(g):
    return {c["id"]: c["status"] for c in g["validations"]}


def test_guide_without_product_is_blocked(client):
    pid = client.post("/api/projects", json={"name": "Sem Produto"}).json()["id"]
    g = _guide(client, pid)
    assert g["status"] == "blocked" and g["inputs"][0]["id"] == "product"
    assert g["next_action"].startswith("Antes de continuar:")


def test_guide_of_an_empty_project_is_todo_and_does_not_require_step_1(client, project):
    """Aula 009: a vibe é encontrada no Explore — a etapa 1 não bloqueia a etapa 2."""
    g = _guide(client, project)
    assert g["status"] == "todo" and g["next_step"] == "base"
    assert [i["id"] for i in g["inputs"]] == ["product"], "referências da etapa 1 não são entrada"
    assert _checks(g)["refs_from_step1"] == "todo"
    assert "sentimento" in g["what"] and "o produto em si pode aparecer" in g["what"]
    assert any("meio-termo" in c or "mesmo mood" in c for c in g["checklist"])


def test_guide_is_done_after_selecting_the_mood(client, project):
    client.post(f"/api/projects/{project}/mood/import/upload",
                files=[("files", ("a.png", image_bytes(color=(10, 20, 30)), "image/png")),
                       ("files", ("b.png", image_bytes(color=(12, 22, 32)), "image/png"))],
                data={"prompt": "Cold neon snowfield at dusk"})
    ids = [c["id"] for c in client.get(f"/api/projects/{project}/mood/candidates").json()]
    sel = client.post(f"/api/projects/{project}/mood/select", json={"ids": ids, "note": "neve, neon, silêncio"})
    assert sel.status_code == 200 and sel.json()["vibe"] == "neve, neon, silêncio"

    g = _guide(client, project)
    assert g["status"] == "done" and g["progress"] == 1.0 and g["missing"] == []
    checks = _checks(g)
    assert checks["selected_range"] == "ok" and checks["single_vibe"] == "ok"
    assert checks["project_vibe"] == "ok", "G2: a etapa 2 grava project.vibe ao salvar"
    assert checks["same_mood"] == "ok", "as duas imagens têm tons próximos"


def test_guide_asks_for_the_vibe_prompt_when_the_mood_md_has_none(client, project):
    """Imagens importadas sem prompt de origem: o mood.md não registra vibe nenhuma."""
    client.post(f"/api/projects/{project}/mood/import/upload",
                files=[("files", ("a.png", image_bytes(), "image/png"))])
    cid = client.get(f"/api/projects/{project}/mood/candidates").json()[0]["id"]
    client.post(f"/api/projects/{project}/mood/select", json={"ids": [cid], "note": "neve"})
    assert _checks(_guide(client, project))["single_vibe"] == "todo"


def test_guide_warns_when_the_selected_images_look_like_different_moods(client, project):
    client.post(f"/api/projects/{project}/mood/import/upload",
                files=[("files", ("a.png", image_bytes(color=(5, 5, 5)), "image/png")),
                       ("files", ("b.png", image_bytes(color=(250, 250, 250)), "image/png"))])
    ids = [c["id"] for c in client.get(f"/api/projects/{project}/mood/candidates").json()]
    client.post(f"/api/projects/{project}/mood/select", json={"ids": ids, "note": "confuso"})
    assert _checks(_guide(client, project))["same_mood"] == "warn"


def test_guide_reads_the_last_prompt(client, project, monkeypatch):
    from studio.common import prompter
    client.post(f"/api/projects/{project}/mood/vibe/import/upload",
                files=[("files", ("v.png", image_bytes(), "image/png"))])
    vid = client.get(f"/api/projects/{project}/mood/vibe").json()["images"][0]["id"]
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter, "from_images", lambda kind, images, instruction="", brief=None: {
        "prompt": "Cold neon snowfield at dusk, RED Komodo, 35mm", "negative": "", "camera": "",
        "notes_pt": "", "source": "claude", "seconds": 1.0})
    client.post(f"/api/projects/{project}/mood/prompts/generate", json={"mode": "images", "image_ids": [vid]})

    checks = _checks(_guide(client, project))
    assert checks["vibe_images"] == "ok" and checks["images_mode_ref"] == "ok"
    assert checks["prompt_en"] == "ok" and checks["no_forced_negatives"] == "ok"


def test_guide_warns_on_portuguese_prompt_and_on_forced_negatives(client, project, monkeypatch):
    from studio.common import prompter
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    monkeypatch.setattr(prompter, "from_brief", lambda kind, brief: {
        "prompt": "Uma paisagem com neve para uma campanha. No product, no logos.",
        "negative": "", "camera": "", "notes_pt": "", "source": "claude", "seconds": 1.0})
    client.post(f"/api/projects/{project}/mood/prompts/generate", json={"mode": "brief"})

    checks = _checks(_guide(client, project))
    assert checks["prompt_en"] == "warn", "aula 007: o prompt é escrito em inglês"
    assert checks["no_forced_negatives"] == "warn", "M1: a aula não proíbe produto nem logo no mood"


def test_guide_does_not_write_anything(client, studio_env, project):
    root = studio_env["refs"].project_dir(project)
    before = json.loads((root / "project.json").read_text())
    _guide(client, project)
    assert json.loads((root / "project.json").read_text()) == before
    assert list((root / "mood").glob("*.json")) == [] and list((root / "mood").glob("*.md")) == []
