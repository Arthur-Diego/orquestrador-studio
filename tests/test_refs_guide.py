"""Guia da etapa 1 (aula 009) — status, entradas, saídas e validações por leitura pura."""
import json

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def project(client):
    return client.post("/api/projects", json={"name": "Refs Guia", "product": "energy drink"}).json()["id"]


def _guide(client, pid):
    r = client.get(f"/api/projects/{pid}/guide/refs")
    assert r.status_code == 200, r.text
    return r.json()


def _checks(g):
    return {c["id"]: c["status"] for c in g["validations"]}


def _fixture_refs(studio_env, pid, ids, terms=None, alt="", selected=True):
    """Escreve candidatas (e as cópias em brainstorming) sem passar pelo Pinterest."""
    from studio.refs import pinterest
    refs = studio_env["refs"]
    root = refs.project_dir(pid)
    cdir = root / "refs" / "candidates"
    cands = []
    for i, cid in enumerate(ids):
        make_image(cdir / f"{cid}.jpg")
        term = (terms or ["energy drink ad campaign"])[i % len(terms or [1])]
        cands.append(pinterest.Candidate(id=cid, source="pinterest", term=term, url=f"https://x/{cid}",
                                         pin_url=None, alt=alt, file=f"{cid}.jpg", thumb=f"thumbs/{cid}.jpg"))
    pinterest.save_candidates(cdir, cands)
    if selected:
        refs.select(pid, list(ids))
    return root


def test_guide_of_an_empty_project_is_todo_and_never_blocked(client, project):
    g = _guide(client, project)
    assert g["id"] == "refs" and g["n"] == 1 and g["aula"] == "009"
    assert g["status"] == "todo" and g["progress"] == 0.0
    assert g["next_step"] == "mood"
    assert g["inputs"][0]["status"] == "ok", "a etapa 1 é a primeira do curso: nada a bloquear"
    assert "Seleção salva em refs/brainstorming/" in g["missing"], "rótulos do protótipo (wave 4)"
    assert g["summary"] is None and g["summary_kind"] is None, "sem resumo antes de salvar nada"
    assert "marca já validada" in g["what"] and "Explore do Midjourney" in g["what"]
    assert any("marca validada" in c for c in g["checklist"])
    assert _checks(g)["candidates"] == "todo" and _checks(g)["min_refs"] == "todo"


def test_guide_is_done_when_references_are_saved(client, studio_env, project):
    _fixture_refs(studio_env, project, ["aaa111", "bbb222", "ccc333"],
                  terms=["Red Bull snow ads", "energy drink ad campaign"])
    g = _guide(client, project)
    assert g["status"] == "done" and g["progress"] == 1.0 and g["missing"] == []
    checks = _checks(g)
    assert checks["min_refs"] == "ok" and checks["brainstorming_sync"] == "ok"
    assert checks["brand_term"] == "ok" and checks["alt_junk"] == "ok" and checks["product"] == "ok"
    assert g["next_action"] == "encontrar a vibe no mood board", "texto do protótipo (wave 4)"
    assert g["summary"] == "3 escolhidas em refs/brainstorming/ · origem registrada no README.md"
    assert any(c["label"].startswith("Candidatas baixadas do Pinterest (") for c in g["validations"])


def test_guide_warns_on_few_references_and_generic_terms(client, studio_env, project):
    _fixture_refs(studio_env, project, ["aaa111"], terms=["energy drink ad campaign"])
    g = _guide(client, project)
    assert g["status"] == "done", "uma referência já fecha a etapa; o resto é atenção"
    checks = _checks(g)
    assert checks["min_refs"] == "warn", "a aula fica com ~6 referências"
    assert checks["brand_term"] == "warn", "nenhum termo aponta uma marca validada"
    assert all(v["status"] != "fail" for v in g["validations"] if v["id"] == "min_refs")


def test_guide_flags_the_brainstorming_invariant_without_blocking(client, studio_env, project):
    root = _fixture_refs(studio_env, project, ["aaa111", "bbb222"], terms=["Red Bull ads"])
    for f in (root / "refs" / "brainstorming").iterdir():
        f.unlink()
    g = _guide(client, project)
    assert _checks(g)["brainstorming_sync"] == "fail"
    assert g["status"] != "blocked", "validação nunca bloqueia a etapa"


def test_guide_warns_on_pinterest_junk_and_missing_product(client, studio_env):
    pid = client.post("/api/projects", json={"name": "Sem Produto"}).json()["id"]
    _fixture_refs(studio_env, pid, ["aaa111"], terms=["Red Bull ads"], alt="Salvar Pins no Pinterest")
    checks = _checks(_guide(client, pid))
    assert checks["alt_junk"] == "warn" and checks["product"] == "warn"


def test_guide_sees_references_added_by_upload(client, project):
    """R2: imagens do Explore entram por upload e contam como referência da etapa 1."""
    up = client.post(f"/api/projects/{project}/refs/import/upload",
                     files=[("files", ("explore.png", image_bytes(), "image/png"))])
    assert up.json() == {"added": 1}
    cid = client.get(f"/api/projects/{project}/refs/candidates").json()[0]["id"]
    client.post(f"/api/projects/{project}/refs/select", json={"ids": [cid], "notes": {cid: "gostei da luz"}})
    g = _guide(client, project)
    assert g["status"] == "done"
    assert _checks(g)["candidates"] == "ok"


def test_guide_does_not_write_anything(client, studio_env, project):
    """O hook é puro: chamar o guia não pode criar nem regravar artefato (contrato da wave)."""
    root = studio_env["refs"].project_dir(project)
    before = json.loads((root / "project.json").read_text())
    _guide(client, project)
    assert json.loads((root / "project.json").read_text()) == before
    assert not (root / "refs" / "README.md").exists()
    assert list((root / "refs" / "brainstorming").iterdir()) == []
