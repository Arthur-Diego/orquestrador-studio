"""Guia da etapa 6 (aula 012): leitura pura dos artefatos + validações V6.1–V6.10.

O guia é o que a tela mostra ao usuário — "o que fazer, o que falta, o que passou". Ele não
pode gravar nada: `animate.load_plan()` cria `animate/takes.json`, e por isso está proibido aqui.
"""
import json

import pytest

from tests.conftest import make_image

STORYBOARD = {
    "scenes": [
        {"id": "cena01", "shots": [
            {"id": "shot01", "file": "storyboard/cena01/shot01_final.png", "order": 1,
             "prompt": "the astronaut walks through the blizzard"},
            {"id": "shot02", "file": "storyboard/cena01/shot02_final.png", "order": 2, "prompt": "close on the helmet"},
        ]},
    ],
    "product_scene": None,
}


@pytest.fixture()
def svc(studio_env):
    return studio_env["svc"]("animate")


@pytest.fixture()
def guide(studio_env):
    from studio.etapas.animate.guide import guide as hook
    return hook


@pytest.fixture()
def project(studio_env, request):
    refs = studio_env["refs"]
    pid = refs.create_project("Gelo Zero", "energy drink", "snow neon")["id"]
    root = refs.project_dir(pid)
    board = json.loads(json.dumps(getattr(request, "param", STORYBOARD)))
    for scene in board["scenes"] + ([board["product_scene"]] if board.get("product_scene") else []):
        for shot in scene["shots"]:
            make_image(root / shot["file"])
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "storyboard.json").write_text(json.dumps(board, ensure_ascii=False))
    return pid


def _check(g, cid):
    return next(v for v in g["validations"] if v["id"] == cid)


# ---------- pureza (contrato do hook) ----------
def test_guide_never_writes_takes_json(studio_env, guide, project):
    """`load_plan` grava; o guia não. Sem isso, abrir o dashboard criaria artefato sozinho."""
    root = studio_env["refs"].project_dir(project)
    guide(project)
    assert not (root / "animate" / "takes.json").exists(), "o guia é leitura pura (wave 2 §1)"
    assert list((root / "videos").iterdir()) == []


def test_guide_without_storyboard_is_blocked(studio_env, guide):
    pid = studio_env["refs"].create_project("Sem shots")["id"]
    g = guide(pid)
    assert g["status"] == "blocked" and g["progress"] == 0.0
    assert "storyboard/storyboard.json com os frames finais (etapa 4)" in g["missing"]
    assert g["inputs"][0]["step"] == "storyboard" and "etapa 4" in g["inputs"][0]["fix"]
    assert "Volte à etapa 4" in g["next_action"]


# ---------- textos da aula (ADR-004) ----------
def test_guide_speaks_the_language_of_the_lesson(guide, project):
    g = guide(project)
    assert g["id"] == "animate" and g["n"] == 5 and g["aula"] == "012" and g["next_step"] == "music"
    assert "start frame + end frame" in g["what"] and "Seedance" in g["what"]
    assert "áudio do modelo desligado" in g["what"] and "em paralelo" in g["what"]
    assert "Pelo menos 2 takes por shot, 1 usável." in g["checklist"]
    assert "Áudio do modelo OFF; 5 s (10 s se a mudança for lenta)." in g["checklist"]


# ---------- estado ----------
def test_guide_progresses_from_todo_to_done(svc, guide, project):
    g = guide(project)
    assert g["status"] == "todo" and [o["status"] for o in g["outputs"]] == ["todo", "todo", "todo"]
    svc.load_plan(project)                                   # a tela da etapa cria o plano
    assert guide(project)["outputs"][0]["status"] == "ok"
    svc.update_shot(project, "cena01", "shot01", prompt="slow dolly in over the snow")
    svc.update_shot(project, "cena01", "shot02", fallback_black=True)
    g = guide(project)
    assert g["status"] == "in_progress" and g["progress"] == 0.67, "plano + prompts ok, finais não"
    svc.update_shot(project, "cena01", "shot01", fallback_black=True)
    g = guide(project)
    assert g["status"] == "done" and g["progress"] == 1.0 and g["missing"] == []
    assert _check(g, "v6_2_ready")["status"] == "ok" and "2/2" in _check(g, "v6_2_ready")["detail"]


# ---------- validações (auditoria §6.5) ----------
def test_all_ten_validations_are_reported(guide, project):
    ids = [v["id"] for v in guide(project)["validations"]]
    assert ids == [f"v6_{n}_" + s for n, s in [
        (1, "frames"), (2, "ready"), (3, "two_takes"), (4, "start_end"), (5, "sound_off"),
        (6, "duration"), (7, "model_switch"), (8, "naming"), (9, "motion_verb"), (10, "product")]]
    assert all(v["status"] in ("ok", "warn", "fail", "todo") for v in guide(project)["validations"])


def test_v6_1_missing_frame_is_reported_without_blocking(studio_env, svc, guide, project):
    (studio_env["refs"].project_dir(project) / "storyboard" / "cena01" / "shot02_final.png").unlink()
    g = guide(project)
    assert _check(g, "v6_1_frames")["status"] == "fail" and "cena01/shot02" in _check(g, "v6_1_frames")["detail"]
    assert g["status"] != "blocked", "validação nunca bloqueia (só entradas bloqueiam)"


def test_v6_4_start_end_without_end_frame_fails(svc, guide, project):
    svc.load_plan(project)
    svc.update_shot(project, "cena01", "shot01", mode="start_end")     # par automático: shot01 → shot02
    assert _check(guide(project), "v6_4_start_end")["status"] == "ok"
    svc.update_shot(project, "cena01", "shot02", mode="start_end")     # último da cena: sem par
    v = _check(guide(project), "v6_4_start_end")
    assert v["status"] == "fail" and "cena01/shot02" in v["detail"] and "end frame" in v["fix"]


def test_v6_3_warns_about_a_like_with_a_single_take(studio_env, svc, guide, project):
    root = studio_env["refs"].project_dir(project)
    svc.load_plan(project)
    data = json.loads((root / "animate" / "takes.json").read_text())
    data["shots"][0]["takes"] = [{"id": "take1", "file": "videos/cena01/shot01_take1.mp4", "liked": True}]
    (root / "animate" / "takes.json").write_text(json.dumps(data))
    v = _check(guide(project), "v6_3_two_takes")
    assert v["status"] == "warn" and "cena01/shot01" in v["detail"], "a aula manda gerar 2 e comparar"


def test_v6_8_warns_when_the_take_file_escapes_the_naming_convention(studio_env, svc, guide, project):
    root = studio_env["refs"].project_dir(project)
    svc.load_plan(project)
    data = json.loads((root / "animate" / "takes.json").read_text())
    data["shots"][0]["takes"] = [{"id": "take1", "file": "videos/solto.mp4", "liked": None}]
    (root / "animate" / "takes.json").write_text(json.dumps(data))
    assert _check(guide(project), "v6_8_naming")["status"] == "warn"


def test_v6_9_warns_when_the_prompt_has_no_movement(svc, guide, project):
    svc.load_plan(project)
    svc.update_shot(project, "cena01", "shot01", prompt="a beautiful red can, cinematic light")
    v = _check(guide(project), "v6_9_motion_verb")
    assert v["status"] == "warn" and "cena01/shot01" in v["detail"]
    svc.update_shot(project, "cena01", "shot01", prompt="slow dolly in, the can turns")
    assert _check(guide(project), "v6_9_motion_verb")["status"] == "ok"


def test_v6_7_suggests_adapting_the_idea_after_six_failures(studio_env, svc, guide, project):
    root = studio_env["refs"].project_dir(project)
    svc.load_plan(project)
    data = json.loads((root / "animate" / "takes.json").read_text())
    data["shots"][0]["cli_failures"] = 3
    (root / "animate" / "takes.json").write_text(json.dumps(data))
    v = _check(guide(project), "v6_7_model_switch")
    assert v["status"] == "warn" and "próximo modelo" in v["fix"]
    data["shots"][0]["cli_failures"] = 6
    (root / "animate" / "takes.json").write_text(json.dumps(data))
    assert "Adapte a ideia" in _check(guide(project), "v6_7_model_switch")["fix"]


PRODUCT = {**STORYBOARD, "product_scene": {
    "id": "cena02", "shots": [{"id": "shot03", "file": "storyboard/cena02/shot03_final.png", "order": 1,
                               "prompt": "the giant can"}]}}


@pytest.mark.parametrize("project", [PRODUCT], indirect=True)
def test_v6_10_product_scene_must_be_animated(svc, guide, project):
    svc.load_plan(project)
    v = _check(guide(project), "v6_10_product")
    assert v["status"] == "warn" and "0/1" in v["detail"] and "cena do produto" in v["fix"]
    svc.update_shot(project, "cena02", "shot03", fallback_black=True)
    assert _check(guide(project), "v6_10_product")["status"] == "ok"


def test_v6_10_is_todo_without_a_product_scene(guide, project):
    v = _check(guide(project), "v6_10_product")
    assert v["status"] == "todo" and "sem cena do produto" in v["detail"]


def test_v6_5_states_that_the_model_audio_is_always_off(guide, project):
    v = _check(guide(project), "v6_5_sound_off")
    assert v["status"] == "ok" and "sound: false" in v["detail"]


# ---------- rota do núcleo ----------
def test_guide_route_serves_the_animate_hook(client, studio_env, project):
    g = client.get(f"/api/projects/{project}/guide/animate").json()
    assert g["id"] == "animate" and g["status"] != "unknown" and g["next_step"] == "music"
    assert len(g["validations"]) == 10 and g["checklist"]
    agg = client.get(f"/api/projects/{project}/guide").json()
    assert next(s for s in agg["steps"] if s["id"] == "animate")["status"] == g["status"]


# ---------- faixa compacta do guia (wave 4, protótipo `06-animate`) ----------
def test_guide_publishes_the_strip_summary_and_next_action(svc, guide, project):
    """A contagem que saiu do painel 01 e o imperativo curto do protótipo vêm do backend."""
    svc.load_plan(project)
    g = guide(project)
    assert g["summary"] == "0/2 shots prontos" and g["summary_kind"] is None
    assert g["next_action"] == "Gerar 2 takes do shot01 e dar like no usável"
    svc.update_shot(project, "cena01", "shot01", fallback_black=True)
    g = guide(project)
    assert g["summary"] == "1/2 shots prontos"
    assert g["next_action"] == "Gerar 2 takes do shot02 e dar like no usável"


def test_guide_without_shots_has_no_summary(studio_env, guide):
    """Sem storyboard não há contagem — e a próxima ação continua sendo destravar a etapa 5."""
    pid = studio_env["refs"].create_project("Sem shots")["id"]
    g = guide(pid)
    assert g["summary"] is None and "Volte à etapa 4" in g["next_action"]
