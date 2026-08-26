"""Guia da etapa 8 (aula 014): a trilha bloqueia, as batidas conferem o ritmo, o resto é aviso."""
from __future__ import annotations

import json

import pytest

from tests.test_edit_service import seed


@pytest.fixture()
def project(studio_env):
    return studio_env["refs"].create_project("Montagem", "energy drink", "snow neon")["id"]


@pytest.fixture()
def root(studio_env, project):
    return studio_env["refs"].project_dir(project)


def guide(client, pid: str) -> dict:
    r = client.get(f"/api/projects/{pid}/guide/edit")
    assert r.status_code == 200, r.text
    return r.json()


def check(g: dict, cid: str) -> dict:
    return next(v for v in g["validations"] if v["id"] == cid)


def test_guide_text_comes_from_the_lesson(client, project):
    g = guide(client, project)
    assert g["id"] == "edit" and g["n"] == 8 and g["aula"] == "014" and g["next_step"] == "export"
    assert "o ritmo vem primeiro, o refinamento depois" in g["what"]
    assert "um pequeno zoom" in g["what"] and "SFX, ambiência, respiração, gelo, impacto" in g["what"]
    assert "Vou publicar mesmo imperfeito — o primeiro sempre será o pior." in g["checklist"]


def test_guide_blocks_without_the_track(client, project, root):
    """Aula 013: não se monta antes de escolher a trilha — é o mesmo gate do 409 no master."""
    seed(root, music=False)
    g = guide(client, project)
    assert g["status"] == "blocked"
    assert "audio/music.* — trilha escolhida (etapa 7)" in g["missing"]
    trilha = next(i for i in g["inputs"] if i["id"] == "music")
    assert trilha["step"] == "music" and "não deve editar antes de escolher a trilha" in trilha["fix"]

    seed(root)
    g = guide(client, project)
    assert g["status"] == "todo" and [i["status"] for i in g["inputs"]] == ["ok", "ok"]
    assert [o["id"] for o in g["outputs"]] == ["rough", "master"]


def test_guide_counts_cuts_on_the_beat(client, project, root, studio_env):
    edit = studio_env["svc"]("edit")
    seed(root, impacts=[1.0, 2.5, 4.0])
    assert check(guide(client, project), "cuts_on_beats")["status"] == "todo"

    edit.get_timeline(project)                       # 3 clipes de 5 s, cortes em 5 s e 10 s
    fora = check(guide(client, project), "cuts_on_beats")
    assert fora["status"] == "warn" and fora["detail"] == "0/2 cortes no ritmo"

    edit.propose_cuts(project, offset=0.0, apply=True)
    dentro = check(guide(client, project), "cuts_on_beats")
    assert dentro["status"] == "ok" and dentro["detail"] == "2/2 cortes no ritmo"


def test_guide_warns_about_sfx_and_the_product_scene(client, project, root, studio_env):
    edit = studio_env["svc"]("edit")
    seed(root, impacts=[1.0, 2.5])
    edit.get_timeline(project)
    g = guide(client, project)
    assert check(g, "sfx")["status"] == "warn"
    assert "formiguinha" in check(g, "sfx")["fix"]
    produto = check(g, "product_last")
    assert produto["status"] == "todo" and "etapa 5" in produto["fix"]

    data = json.loads((root / "shots" / "storyboard.json").read_text())
    data["product_scene"] = {"id": "produto", "shots": []}
    (root / "shots" / "storyboard.json").write_text(json.dumps(data))
    fora = check(guide(client, project), "product_last")
    assert fora["status"] == "warn" and "cena03" in fora["detail"]


def test_guide_reports_progress_from_the_rendered_files(client, project, root):
    seed(root)
    (root / "edit").mkdir(parents=True, exist_ok=True)
    (root / "edit" / "rough_cut.mp4").write_bytes(b"rough")
    g = guide(client, project)
    assert g["status"] == "in_progress" and g["progress"] == 0.5
    assert g["missing"] == ["edit/master.mp4 (com SFX, fade e trilha)"]
    (root / "edit" / "master.mp4").write_bytes(b"master")
    assert guide(client, project)["status"] == "done"


def test_guide_never_writes_the_timeline(client, project, root):
    """`edit.get_timeline()` grava ao ler; o guia lê `edit/timeline.json` direto (ADR-010)."""
    seed(root)
    guide(client, project)
    client.get(f"/api/projects/{project}/guide")
    assert not (root / "edit" / "timeline.json").exists()


def test_guide_warns_when_beats_are_missing(client, project, root):
    seed(root)
    g = guide(client, project)
    assert check(g, "beats")["status"] == "warn", "a etapa monta sem beats (decisão 6 da wave 1), com aviso"
    assert g["status"] != "blocked", "validação nunca bloqueia"


def test_guide_strip_speaks_in_short_imperatives(client, project, root):
    """Wave 4: `next_action` e `summary` são o que a faixa compacta do protótipo desenha."""
    seed(root, music=False)
    bloqueado = guide(client, project)
    assert bloqueado["status"] == "blocked" and bloqueado["summary"] is None
    assert bloqueado["next_action"].startswith("Antes de continuar:"), "bloqueio mantém o texto padrão"

    seed(root)
    g = guide(client, project)
    # Estado que o protótipo desenha: "a fazer" + a próxima ação, sem chip extra.
    assert g["status"] == "todo" and g["summary"] is None and g["summary_kind"] is None
    assert g["next_action"] == "Propor cortes nos impactos e renderizar o rough cut"

    (root / "edit").mkdir(parents=True, exist_ok=True)
    (root / "edit" / "rough_cut.mp4").write_bytes(b"rough")
    g = guide(client, project)
    assert g["summary"] == "rough: pronto" and g["summary_kind"] is None
    assert g["next_action"] == "Adicionar SFX e renderizar o master"

    (root / "edit" / "master.mp4").write_bytes(b"master")
    g = guide(client, project)
    assert g["status"] == "done" and g["summary"] == "master: pronto" and g["summary_kind"] == "ok"
    assert "etapa 9" in g["next_action"], "etapa concluída mantém o texto padrão"
