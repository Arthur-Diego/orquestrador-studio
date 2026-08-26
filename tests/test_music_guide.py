"""Guia da etapa 7 (aula 013): assistir a história inteira, decidir, e só então a trilha.

O hook é puro (ADR-010): nenhum teste aqui grava artefato por fora do serviço da etapa, e o guia
não pode criar nada — inclusive `edit/timeline.json`, que `edit.get_timeline()` criaria.
"""
from __future__ import annotations

import json

import pytest

from tests.test_edit_service import seed


@pytest.fixture()
def project(studio_env):
    return studio_env["refs"].create_project("Trilha", "energy drink", "snow neon")["id"]


@pytest.fixture()
def root(studio_env, project):
    return studio_env["refs"].project_dir(project)


def guide(client, pid: str) -> dict:
    r = client.get(f"/api/projects/{pid}/guide/music")
    assert r.status_code == 200, r.text
    return r.json()


def labels(items) -> list[str]:
    return [i["label"] for i in items]


def check(g: dict, cid: str) -> dict:
    return next(v for v in g["validations"] if v["id"] == cid)


def test_guide_speaks_the_lesson_before_anything_else(client, project):
    g = guide(client, project)
    assert g["id"] == "music" and g["n"] == 7 and g["aula"] == "013" and g["next_step"] == "edit"
    assert "assista tudo de uma vez, sem cortar nada" in g["what"]
    assert "Não edite antes de escolher a trilha" in g["what"]
    assert "A trilha foi escolhida antes de qualquer corte." in g["checklist"]
    assert any("sequência completa" in c for c in g["checklist"])


def test_guide_blocks_without_storyboard_and_liked_takes(client, project, root):
    g = guide(client, project)
    assert g["status"] == "blocked" and g["progress"] == 0.0
    assert "shots/storyboard.json com a ordem das cenas (etapa 5)" in g["missing"]
    assert "≥ 1 take com like por cena (etapa 6)" in g["missing"]
    assert [i["step"] for i in g["inputs"]] == ["shots", "animate"]

    seed(root, liked=(True, False, True), music=False)
    g = guide(client, project)
    faltando = next(i for i in g["inputs"] if i["id"] == "takes_liked")
    assert faltando["status"] == "fail" and "cena02" in faltando["detail"]
    assert g["status"] == "blocked"


def test_guide_outputs_follow_the_lesson_order(client, project, root, studio_env):
    """Sequência assistida → decisão → trilha → batidas: a ordem da aula 013."""
    seed(root, music=False)
    g = guide(client, project)
    assert g["status"] == "todo"
    assert labels(g["outputs"]) == ['audio/story_check.json (decisão "a história fecha?")',
                                    "audio/music.* (trilha escolhida)",
                                    "audio/beats.json (batidas fortes)"]
    assert check(g, "rough_sequence")["status"] == "todo"

    music = studio_env["svc"]("music")
    music.set_story_check(project, closed=False, note="falta a geladeira congelando")
    g = guide(client, project)
    assert g["status"] == "in_progress" and g["progress"] == round(1 / 3, 2)
    decisao = next(o for o in g["outputs"] if o["id"] == "story_check")
    assert decisao["status"] == "ok" and "falta cena" in decisao["detail"]


def test_guide_warns_about_a_missing_product_scene(client, project, root):
    seed(root, music=False)
    aviso = check(guide(client, project), "product_scene")
    assert aviso["status"] == "warn" and "Crie a cena do produto na etapa 5" in aviso["fix"]
    assert "termine mostrando o produto" in aviso["detail"]

    data = json.loads((root / "shots" / "storyboard.json").read_text())
    data["product_scene"] = {"id": "produto", "shots": []}
    (root / "shots" / "storyboard.json").write_text(json.dumps(data))
    assert check(guide(client, project), "product_scene")["status"] == "ok"


def test_guide_warns_when_the_track_is_shorter_than_the_story(client, project, root):
    seed(root, music=False)          # 3 takes de 5 s = 15 s de história
    assert check(guide(client, project), "track_length")["status"] == "todo"

    (root / "audio" / "beats.json").write_text(json.dumps(
        {"bpm": 120, "beats": [1.0, 2.0], "impacts": [1.0], "duration": 8.0}))
    curta = check(guide(client, project), "track_length")
    assert curta["status"] == "warn" and "8.0s" in curta["detail"] and "15.0s" in curta["detail"]

    (root / "audio" / "beats.json").write_text(json.dumps(
        {"bpm": 120, "beats": [1.0, 2.0], "impacts": [1.0], "duration": 30.0}))
    assert check(guide(client, project), "track_length")["status"] == "ok"


def test_guide_is_done_after_the_whole_lesson(ffmpeg_or_skip, client, project, root, studio_env, tmp_path):
    from tests.test_music_service import audio_bytes
    music = studio_env["svc"]("music")
    seed(root, music=False)
    music.set_story_check(project, closed=True)
    music.import_upload(project, [("a.wav", audio_bytes(tmp_path, "a.wav", seconds=20, bpm=120))])
    cid = music.list_candidates(project)[0]["id"]
    music.select(project, cid, "")

    g = guide(client, project)
    assert g["status"] == "done" and g["progress"] == 1.0 and g["missing"] == []
    assert "etapa 8" in g["next_action"]
    origem = check(g, "license")
    assert origem["status"] == "warn" and "[extensão]" in origem["label"], "licença é extensão, não da aula"


def test_guide_never_creates_artifacts(client, project, root):
    """O hook é leitura pura: nem `edit/timeline.json` nem `audio/rough_sequence.mp4` nascem daqui."""
    seed(root)
    guide(client, project)
    client.get(f"/api/projects/{project}/guide")
    assert not (root / "edit" / "timeline.json").exists()
    assert not (root / "audio" / "rough_sequence.mp4").exists()
    assert not (root / "audio" / "story_check.json").exists()


def test_guide_strip_speaks_in_short_imperatives(client, project, root, studio_env, tmp_path):
    """Wave 4: `next_action` e `summary` são o que a faixa compacta do protótipo desenha."""
    bloqueado = guide(client, project)
    assert bloqueado["status"] == "blocked" and bloqueado["summary"] is None
    assert bloqueado["next_action"].startswith("Antes de continuar:")

    seed(root, music=False)
    g = guide(client, project)
    # Estado que o protótipo desenha: "a fazer" + a próxima ação, sem chip extra.
    assert g["status"] == "todo" and g["summary"] is None and g["summary_kind"] is None
    assert g["next_action"] == "Montar a sequência bruta e decidir se a história fecha"

    music = studio_env["svc"]("music")
    music.set_story_check(project, closed=True)
    g = guide(client, project)
    assert g["summary"] == "história decidida, sem trilha"
    assert g["next_action"] == "Ouvir as candidatas e escolher a trilha"
