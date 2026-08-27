"""Guia da etapa 2 — fluxo "etapa2-pick" (ADR-014, estende ADR-013/ADR-007).

A etapa 2 agora só ESCOLHE um board da biblioteca e o aplica; `done` = há mood aplicado
(`mood/selected` não vazio). Saíram as checagens de criação (gerar prompt/importar grid); o texto
de aula continua no `what` como contexto (ADR-004).
"""
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


def _board(studio_env, name="Winter", n=2, vibe="icy winter"):
    mb = studio_env["moodboards"]
    mbid = mb.create_board(name)["id"]
    for i, col in enumerate([(10, 80, 200), (200, 30, 60), (40, 160, 90)][:n]):
        mb.import_upload(mbid, [(f"g{i}.png", image_bytes(col))])
    mb.select(mbid, [c["id"] for c in mb.candidates(mbid)])
    if vibe:
        mb.patch_board(mbid, vibe=vibe)
    return mbid


def test_guide_without_product_is_blocked(client):
    pid = client.post("/api/projects", json={"name": "Sem Produto"}).json()["id"]
    g = _guide(client, pid)
    assert g["status"] == "blocked" and g["inputs"][0]["id"] == "product"
    assert g["next_action"].startswith("Antes de continuar:")


def test_guide_of_an_empty_project_is_todo_and_asks_to_pick_a_board(client, project):
    """Sem mood aplicado: a próxima ação é escolher um board da biblioteca e aplicá-lo."""
    g = _guide(client, project)
    assert g["status"] == "todo" and g["next_step"] == "base"
    assert [i["id"] for i in g["inputs"]] == ["product"], "referências da etapa 1 não são entrada"
    assert _checks(g)["refs_from_step1"] == "todo"
    assert g["next_action"] == "Escolha um mood board da biblioteca e aplique à campanha"
    assert g["summary"] is None, "a faixa compacta do protótipo desta tela não tem chip extra"
    # o texto de aula (contexto) e a nova ação (escolher da biblioteca) convivem no `what`
    for frase in ("biblioteca", "Aplicar a esta campanha", "sentimento",
                  "Produto, texto e logo não são proibidos"):
        assert frase in g["what"], frase


def test_guide_is_done_after_applying_a_board(client, studio_env, project):
    """`done` = mood/selected populado. Aplicar um board via pull_board satisfaz a etapa."""
    mbid = _board(studio_env, n=2, vibe="icy winter")
    r = client.post(f"/api/projects/{project}/mood/pull/{mbid}")
    assert r.status_code == 200 and r.json()["selected"] == 2

    g = _guide(client, project)
    assert g["status"] == "done" and g["progress"] == 1.0 and g["missing"] == []
    checks = _checks(g)
    assert checks["selected_range"] == "ok"
    assert checks["project_vibe"] == "ok", "aplicar um board com vibe grava project.vibe"
    assert checks["same_mood"] in ("ok", "warn"), "a paleta por imagem alimenta a validação"
    assert g["next_action"] == "montar a imagem base do produto"


def test_guide_is_done_when_a_legacy_mood_was_curated_in_step_2(client, project):
    """Campanha antiga que criou o mood na etapa 2 (import + select) continua válida — done."""
    client.post(f"/api/projects/{project}/mood/import/upload",
                files=[("files", ("a.png", image_bytes(color=(10, 20, 30)), "image/png")),
                       ("files", ("b.png", image_bytes(color=(12, 22, 32)), "image/png"))],
                data={"prompt": "Cold neon snowfield at dusk"})
    ids = [c["id"] for c in client.get(f"/api/projects/{project}/mood/candidates").json()]
    sel = client.post(f"/api/projects/{project}/mood/select", json={"ids": ids, "note": "neve, neon, silêncio"})
    assert sel.status_code == 200

    g = _guide(client, project)
    assert g["status"] == "done"
    assert _checks(g)["project_vibe"] == "ok"


def test_guide_warns_when_the_applied_images_look_like_different_moods(client, studio_env, project):
    mb = studio_env["moodboards"]
    mbid = mb.create_board("Confuso")["id"]
    mb.import_upload(mbid, [("a.png", image_bytes(color=(5, 5, 5)))])
    mb.import_upload(mbid, [("b.png", image_bytes(color=(250, 250, 250)))])
    mb.select(mbid, [c["id"] for c in mb.candidates(mbid)])
    client.post(f"/api/projects/{project}/mood/pull/{mbid}")
    assert _checks(_guide(client, project))["same_mood"] == "warn"


def test_guide_does_not_write_anything(client, studio_env, project):
    root = studio_env["refs"].project_dir(project)
    before = json.loads((root / "project.json").read_text())
    _guide(client, project)
    assert json.loads((root / "project.json").read_text()) == before
    assert list((root / "mood").glob("*.json")) == [] and list((root / "mood").glob("*.md")) == []
