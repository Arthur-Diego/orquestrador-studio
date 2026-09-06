"""Serviço de Personagens (ADR-039): CRUD, explore local (fake), lock+descritor, apply. Isolado."""
import pytest

from tests.conftest import image_bytes


@pytest.fixture()
def svc(studio_env):
    from studio.characters import service
    return service


def test_create_list_get_patch(svc):
    c = svc.create("Eden", "anime")
    assert c["style"] == "anime" and c["locked_ref"] is None
    assert svc.get(c["id"])["name"] == "Eden"
    assert [x["id"] for x in svc.list_characters()] == [c["id"]]
    svc.patch(c["id"], name="Eden v2")
    assert svc.get(c["id"])["name"] == "Eden v2"
    with pytest.raises(svc.CharacterError):
        svc.create("x", "voxel")  # estilo inválido


def test_explore_e_lock_geram_descritor(svc, monkeypatch):
    from studio import localengine as le
    monkeypatch.setattr(le, "require", lambda: None)
    monkeypatch.setattr(le, "generate_image", lambda *a, **k: image_bytes(color=(10, 20, 30)))
    # sem prompter real: descritor cai no fallback determinístico
    from studio.common import prompter
    monkeypatch.setattr(prompter, "available", lambda: False)

    c = svc.create("Eden", "foto")
    svc.explore(c["id"], "young woman, silver hair", count=2)
    # o job roda em thread; espera terminar
    import time
    for _ in range(50):
        if svc.job_status(c["id"]).get("state") in ("done", "error"):
            break
        time.sleep(0.05)
    cands = svc.candidates(c["id"], "explore")
    assert len(cands) >= 1
    meta = svc.lock(c["id"], cands[0]["id"])
    assert meta["locked_ref"] and meta["descriptor"]  # descritor gerado (fallback)


def test_apply_and_applied(svc, client):
    # cria uma campanha pela API e aplica o personagem
    pid = client.post("/api/projects", json={"name": "Camp"}).json()["id"]
    c = svc.create("Eden")
    svc.patch(c["id"], descriptor="silver hair, dark coat")
    svc.apply_to_project(pid, c["id"])
    ap = svc.applied(pid)
    assert ap and ap["id"] == c["id"] and "silver hair" in ap["descriptor"]
    svc.clear_from_project(pid)
    assert svc.applied(pid) is None


def test_score_sem_engine_degrada(svc, monkeypatch):
    monkeypatch.delenv("STUDIO_LOCAL_ENGINE_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _n: None)
    c = svc.create("Eden")
    svc.patch(c["id"])
    # sem locked_ref → erro de negócio
    with pytest.raises(svc.CharacterError):
        svc.score(c["id"], "zzz")
