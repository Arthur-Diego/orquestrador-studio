"""Guia da etapa 5 (aula 011 + aula 013): entradas, saídas e as validações V5.2–V5.8.

Leitura pura: consultar o guia não pode criar nem regravar artefato nenhum.
"""
import json

import pytest

from tests.conftest import image_bytes, make_image
from tests.test_shots_service import SCENES


@pytest.fixture()
def pid(studio_env):
    """Projeto vazio: nem etapa 3 nem etapa 4 concluídas."""
    return studio_env["refs"].create_project("Gelo Zero", "energy drink")["id"]


@pytest.fixture()
def root(studio_env, pid):
    return studio_env["refs"].project_dir(pid)


@pytest.fixture()
def pronto(client, pid, root):
    """Terreno das etapas 3 e 4 (frentes irmãs desta wave), como fixture local."""
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "scenes.json").write_text(json.dumps({"scenes": SCENES}))
    make_image(root / "storyboard" / "ideas" / "a1.png", color=(10, 40, 90))
    make_image(root / "storyboard" / "ideas" / "a2.png", color=(90, 40, 10))
    make_image(root / "base" / "base_final.png", color=(200, 200, 250))
    return pid


def guide(client, pid):
    r = client.get(f"/api/projects/{pid}/guide/shots")
    assert r.status_code == 200, r.text
    return r.json()


def check(g, cid):
    return next(c for c in g["validations"] if c["id"] == cid)


def _dois_frames(client, pid, scene="cena01", upscaled=False):
    api = f"/api/projects/{pid}/shots/scenes/{scene}"
    client.post(f"{api}/base", json={})
    for name, color in (("a.png", (11, 22, 33)), ("b.png", (44, 55, 66))):
        client.post(f"{api}/import/upload", files={"files": (name, image_bytes(color=color), "image/png")})
    ids = [c["id"] for c in client.get(f"{api}/candidates").json()["candidates"]]
    client.post(f"{api}/select", json={"shots": [{"id": i, "upscaled": upscaled} for i in ids]})
    return ids


def test_guide_is_blocked_without_the_written_storyboard(client, pid):
    g = guide(client, pid)
    assert g["id"] == "shots" and g["n"] == 5 and g["aula"] == "011"
    assert g["status"] == "blocked"
    assert "storyboard/scenes.json com cenas escritas (etapa 4)" in g["missing"]
    assert [i["step"] for i in g["inputs"]] == ["storyboard", "base"]
    assert g["next_step"] == "animate"


def test_guide_texts_come_from_the_lesson(client, pronto):
    g = guide(client, pronto)
    assert "Multishot" in g["what"] and "cores e luz" in g["what"]
    assert any("upscalado" in c for c in g["checklist"])
    assert any("trilha" in c for c in g["checklist"]), "5.8: a nota da aula 013 está no guia"


def test_guide_walks_from_todo_to_done(client, pronto, root):
    g = guide(client, pronto)
    assert g["status"] == "todo" and g["progress"] == 0.0

    _dois_frames(client, pronto, "cena01", upscaled=True)
    g = guide(client, pronto)
    assert g["status"] == "in_progress"
    assert "shots/cenaNN/base.png em todas as cenas" in g["missing"]

    for s in SCENES[1:]:
        _dois_frames(client, pronto, s["id"], upscaled=True)
    g = guide(client, pronto)
    assert g["status"] == "done" and g["progress"] == 1.0 and g["missing"] == []
    assert check(g, "v52_cena_com_shot")["status"] == "ok"
    assert check(g, "v53_upscale")["status"] == "ok"
    assert check(g, "v55_variacoes")["status"] == "ok"


def test_validation_v52_lists_the_scenes_without_frames(client, pronto):
    _dois_frames(client, pronto, "cena01", upscaled=True)
    v = check(guide(client, pronto), "v52_cena_com_shot")
    assert v["status"] == "warn" and "cena02" in v["detail"] and "cena05" in v["detail"]


def test_validation_v53_counts_frames_without_upscale(client, pronto):
    _dois_frames(client, pronto, "cena01")
    v = check(guide(client, pronto), "v53_upscale")
    assert v["status"] == "warn" and v["detail"].startswith("0/2")
    assert "upscale" in v["fix"].lower()


def test_validation_v55_warns_about_a_single_framing(client, pronto):
    api = f"/api/projects/{pronto}/shots/scenes/cena01"
    client.post(f"{api}/base", json={})
    client.post(f"{api}/import/upload", files={"files": ("a.png", image_bytes(), "image/png")})
    cid = client.get(f"{api}/candidates").json()["candidates"][0]["id"]
    client.post(f"{api}/select", json={"shots": [{"id": cid, "upscaled": True}]})
    v = check(guide(client, pronto), "v55_variacoes")
    assert v["status"] == "warn" and "cena01" in v["detail"]


def test_validation_v56_warns_when_the_base_changed_after_the_candidates(client, pronto, root):
    import os
    import time
    _dois_frames(client, pronto, "cena01", upscaled=True)
    assert check(guide(client, pronto), "v56_candidatos_antigos")["status"] == "ok"
    base = root / "shots" / "cena01" / "base.png"
    futuro = time.time() + 60
    os.utime(base, (futuro, futuro))
    v = check(guide(client, pronto), "v56_candidatos_antigos")
    assert v["status"] == "warn" and "cena01" in v["detail"]


def test_validation_v57_looks_for_the_lesson_formula(client, pronto):
    api = f"/api/projects/{pronto}/shots/scenes/cena01"
    client.post(f"{api}/base", json={})
    client.post(f"{api}/import/upload", files={"files": ("a.png", image_bytes(), "image/png")},
                data={"prompt": "Bring me another point of view of this image. I want a close-up on the astronaut."})
    cid = client.get(f"{api}/candidates").json()["candidates"][0]["id"]
    client.post(f"{api}/select", json={"shots": [{"id": cid, "upscaled": True}]})
    assert check(guide(client, pronto), "v57_formula_do_angulo")["status"] == "ok"


def test_validation_v58_tracks_the_product_scene(client, pronto, root):
    assert check(guide(client, pronto), "v58_cena_do_produto")["status"] == "todo"
    api = f"/api/projects/{pronto}/shots/product"
    client.post(f"{api}/ref", files={"file": ("r.png", image_bytes(color=(3, 3, 3)), "image/png")})
    client.post(f"{api}/import/upload", files={"files": ("p.png", image_bytes(color=(120, 10, 10)), "image/png")})
    cid = client.get(f"{api}/candidates").json()["candidates"][0]["id"]
    client.post(f"{api}/select", json={"id": cid, "upscaled": True})
    assert check(guide(client, pronto), "v58_cena_do_produto")["status"] == "ok"


def test_palette_is_attention_not_a_blocking_input(client, pronto, root):
    """A paleta é `[extensão]` do Studio (OS-014): ela avisa, nunca bloqueia a etapa 5."""
    g = guide(client, pronto)
    assert all(i["id"] != "palette" for i in g["inputs"])
    v = check(g, "palette")
    assert v["status"] == "warn" and g["status"] != "blocked"
    (root / "mood").mkdir(parents=True, exist_ok=True)
    (root / "mood" / "palette.json").write_text(json.dumps({"colors": ["#0b1d3a"], "note": "neve"}))
    assert check(guide(client, pronto), "palette")["status"] == "ok"


def test_guide_never_writes_anything(client, pronto, root):
    antes = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    for _ in range(3):
        guide(client, pronto)
        client.get(f"/api/projects/{pronto}/guide")
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) == antes
    assert not (root / "shots" / "storyboard.json").exists()


def test_aggregate_guide_lists_step_five_without_unknown(client, pronto):
    steps = {s["id"]: s for s in client.get(f"/api/projects/{pronto}/guide").json()["steps"]}
    assert steps["shots"]["status"] != "unknown" and steps["shots"]["validations"]
