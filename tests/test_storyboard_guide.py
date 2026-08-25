"""Guia da etapa 4 (aula 010): o que fazer, o que falta e as validações V4.1–V4.6.

O guia é leitura pura: nenhum destes testes deixa o projeto diferente de como o encontrou.
"""
import json

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def pid(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()["id"]


@pytest.fixture()
def root(studio_env, pid):
    return studio_env["refs"].project_dir(pid)


def guide(client, pid):
    r = client.get(f"/api/projects/{pid}/guide/storyboard")
    assert r.status_code == 200, r.text
    return r.json()


def check(g, cid):
    return next(c for c in g["validations"] if c["id"] == cid)


def _idea(client, pid, color=(10, 20, 30)):
    """Importa uma ideia e a escolhe — devolve o caminho dela em storyboard/ideas/."""
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(color=color), "image/png"))])
    ideas = client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"]
    client.post(f"/api/projects/{pid}/storyboard/candidates/select", json={"ids": [ideas[-1]["id"]]})
    return client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"][-1]["file"]


def test_guide_is_blocked_without_the_campaign_base(client, pid):
    g = guide(client, pid)
    assert g["id"] == "storyboard" and g["n"] == 4 and g["aula"] == "010"
    assert g["status"] == "blocked" and g["progress"] == 0.0
    assert "base/base_final.png (etapa 3)" in g["missing"]
    assert g["inputs"][0]["step"] == "base", "o painel oferece o atalho para a etapa que produz"
    assert "etapa 3" in g["next_action"]
    assert g["next_step"] == "shots"


def test_guide_texts_come_from_the_lesson(client, pid, root):
    make_image(root / "base" / "base_final.png")
    g = guide(client, pid)
    assert "Draw to Edit" in g["what"] and "Multi Shot" in g["what"]
    assert "começo, descoberta, ação e desfecho" in g["what"]
    assert any("4 imagens quando incerto" in c for c in g["checklist"])
    assert any("etapa 5" in c for c in g["checklist"]), "V4.1: o upscale mora na etapa 5"


def test_guide_walks_from_todo_to_done(client, pid, root):
    make_image(root / "base" / "base_final.png")
    g = guide(client, pid)
    assert g["status"] == "todo" and [o["status"] for o in g["outputs"]] == ["todo", "todo", "todo"]

    img = _idea(client, pid)
    g = guide(client, pid)
    assert g["status"] == "in_progress" and 0 < g["progress"] < 1

    scenes = [{"text": f"cena {i}", "image": img} for i in range(1, 6)]
    client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": scenes})
    g = guide(client, pid)
    assert g["status"] == "done" and g["progress"] == 1.0 and g["missing"] == []
    assert "siga para a" in g["next_action"].lower()


def test_validation_v41_counts_written_scenes(client, pid, root):
    make_image(root / "base" / "base_final.png")
    client.put(f"/api/projects/{pid}/storyboard/scenes",
               json={"scenes": [{"text": "a"}, {"text": ""}, {"text": ""}, {"text": ""}, {"text": ""}]})
    v = check(guide(client, pid), "v41_cinco_cenas")
    assert v["status"] == "warn" and "1 de 5" in v["detail"]
    client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": [{"text": "a"}, {"text": "b"}]})
    assert check(guide(client, pid), "v41_cinco_cenas")["status"] == "ok", "storyboard reduzido: todas escritas"


def test_validation_v42_flags_scenes_without_an_idea(client, pid, root):
    make_image(root / "base" / "base_final.png")
    img = _idea(client, pid)
    client.put(f"/api/projects/{pid}/storyboard/scenes",
               json={"scenes": [{"text": "a", "image": img}, {"text": "b"}]})
    v = check(guide(client, pid), "v42_cena_com_imagem")
    assert v["status"] == "warn" and "cena02" in v["detail"]


def test_validation_v44_flags_numbered_instructions_in_imported_ideas(client, pid, root):
    make_image(root / "base" / "base_final.png")
    client.post(f"/api/projects/{pid}/storyboard/import/upload",
                files=[("files", ("a.png", image_bytes(), "image/png"))],
                data={"prompt": "1. Make it smaller 2. Remove the rope"})
    v = check(guide(client, pid), "v44_instrucao_unica")
    assert v["status"] == "warn" and "1 ideia" in v["detail"]


def test_validation_v46_compares_the_document_with_the_scenes(client, pid, root):
    make_image(root / "base" / "base_final.png")
    client.put(f"/api/projects/{pid}/storyboard/scenes", json={"scenes": [{"text": "abre na nevasca"}]})
    assert check(guide(client, pid), "v46_md_atualizado")["status"] == "ok"
    # cenas gravadas por fora (sem passar pelo serviço) deixam o documento para trás
    import os
    import time
    f = root / "storyboard" / "scenes.json"
    f.write_text(json.dumps({"scenes": [{"id": "cena01", "n": 1, "text": "outra", "image": None}]}))
    os.utime(f, (time.time() + 10, time.time() + 10))
    assert check(guide(client, pid), "v46_md_atualizado")["status"] == "warn"


def test_guide_never_writes_anything(client, pid, root):
    """ADR-003 + contrato do hook: consultar o guia não cria nem regrava artefato."""
    make_image(root / "base" / "base_final.png")
    antes = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    for _ in range(3):
        guide(client, pid)
        client.get(f"/api/projects/{pid}/guide")
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) == antes
    assert not (root / "storyboard" / "scenes.json").exists(), "o guia não materializa as 5 cenas"


def test_aggregate_guide_lists_step_four_without_unknown(client, pid):
    steps = {s["id"]: s for s in client.get(f"/api/projects/{pid}/guide").json()["steps"]}
    assert steps["storyboard"]["status"] != "unknown"
    assert steps["storyboard"]["validations"], "a etapa 4 publica suas validações no agregado"
