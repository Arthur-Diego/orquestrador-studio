"""Etapa 6 — a animação segue a aula 012: prompt por take, start/end frame, 2 takes, like,
troca de modelo sugerida após 3 falhas e corte para preto como fallback."""
import json
import threading

import pytest

from studio.common import ffmpeg as ff
from tests.conftest import make_image, make_video

needs_ffmpeg = pytest.mark.skipif(not ff.available(), reason="sem ffmpeg (fixtures de vídeo)")

STORYBOARD = {
    "scenes": [
        {"id": "cena01", "base": "shots/cena01/base.png", "shots": [
            {"id": "shot02", "file": "shots/cena01/shot02_final.png", "order": 2, "prompt": "close on the helmet"},
            {"id": "shot01", "file": "shots/cena01/shot01_final.png", "order": 1,
             "prompt": "the astronaut walks through the blizzard"},
        ]},
        {"id": "cena02", "base": "shots/cena02/base.png", "shots": [
            {"id": "shot03", "file": "shots/cena02/shot03_final.png", "order": 1, "prompt": "the giant can"},
        ]},
    ],
    "product_scene": None,
}


@pytest.fixture()
def svc(studio_env):
    return studio_env["svc"]("animate")


@pytest.fixture()
def project(studio_env, request):
    refs = studio_env["refs"]
    pid = refs.create_project("Gelo Zero", "energy drink", "snow neon")["id"]
    root = refs.project_dir(pid)
    board = json.loads(json.dumps(getattr(request, "param", STORYBOARD)))
    for scene in board["scenes"] + ([board["product_scene"]] if board.get("product_scene") else []):
        for shot in scene["shots"]:
            if shot.get("file"):
                make_image(root / shot["file"])
    (root / "shots").mkdir(parents=True, exist_ok=True)
    (root / "shots" / "storyboard.json").write_text(json.dumps(board, ensure_ascii=False))
    return pid


def _root(studio_env, pid):
    return studio_env["refs"].project_dir(pid)


def _candidate(svc, studio_env, pid, tmp_path, name="take.mp4", seconds=1, size="320x240"):
    v = make_video(tmp_path / name, seconds=seconds, size=size)
    svc.import_upload(pid, [(name, v.read_bytes())])
    return svc.list_candidates(pid)[-1]["id"]


def _wait(svc, pid, timeout_s=15):
    for _ in range(int(timeout_s / 0.05)):
        if svc.job_status(pid)["state"] != "running":
            break
        threading.Event().wait(0.05)
    return svc.job_status(pid)


# ---------- plano ----------
def test_plan_follows_storyboard_order_and_creates_takes_json(svc, studio_env, project):
    plan = svc.load_plan(project)
    assert [(s["scene"], s["shot"]) for s in plan["shots"]] == [
        ("cena01", "shot01"), ("cena01", "shot02"), ("cena02", "shot03")], "ordem do storyboard, não do JSON"
    assert [s["next_in_scene"] for s in plan["shots"]] == ["shot02", None, None]
    assert plan["total"] == 3 and plan["ready"] == 0
    assert plan["model_order"] == ["kling3_0", "seedance_2_0", "veo3_1_lite"]
    data = json.loads((_root(studio_env, project) / "animate" / "takes.json").read_text())
    assert [s["shot"] for s in data["shots"]] == ["shot01", "shot02", "shot03"]


def test_plan_requires_storyboard(svc, studio_env):
    refs = studio_env["refs"]
    pid = refs.create_project("Sem shots")["id"]
    with pytest.raises(FileNotFoundError):
        svc.load_plan(pid)


def test_plan_warns_about_missing_frame_without_blocking(svc, studio_env, project):
    root = _root(studio_env, project)
    (root / "shots" / "cena02" / "shot03_final.png").unlink()
    plan = svc.load_plan(project)
    shot = plan["shots"][-1]
    assert shot["image"] is None
    assert any("shot03" in w for w in plan["warnings"])


@pytest.mark.parametrize("project", [{**STORYBOARD, "product_scene": {
    "id": "cena03", "shots": [{"id": "shot04", "file": "shots/cena03/shot04_final.png", "order": 1,
                               "prompt": "the frozen fridge"}]}}], indirect=True)
def test_product_scene_is_the_last_scene(svc, project):
    plan = svc.load_plan(project)
    assert [s["scene"] for s in plan["shots"]][-1] == "cena03", "aula 013: cena do produto entra no fim"


def test_merge_keeps_takes_of_shot_removed_from_storyboard(svc, studio_env, project):
    svc.load_plan(project)
    svc.update_shot(project, "cena02", "shot03", prompt="keep me")
    root = _root(studio_env, project)
    board = json.loads((root / "shots" / "storyboard.json").read_text())
    board["scenes"] = board["scenes"][:1]
    (root / "shots" / "storyboard.json").write_text(json.dumps(board))
    plan = svc.load_plan(project)
    orphan = [s for s in plan["shots"] if s["shot"] == "shot03"]
    assert orphan and orphan[0]["orphan"] is True and orphan[0]["prompt"] == "keep me"


# ---------- update ----------
def test_update_shot_validates_duration_and_mode(svc, project):
    assert svc.update_shot(project, "cena01", "shot01", duration=10)["duration"] == 10
    with pytest.raises(ValueError):
        svc.update_shot(project, "cena01", "shot01", duration=7)
    with pytest.raises(ValueError):
        svc.update_shot(project, "cena01", "shot01", mode="magic")
    with pytest.raises(FileNotFoundError):
        svc.update_shot(project, "cena09", "shot01", duration=5)


def test_fallback_black_is_persisted_and_counts_as_ready(svc, project):
    svc.update_shot(project, "cena01", "shot02", fallback_black=True)
    plan = svc.load_plan(project)
    shot = [s for s in plan["shots"] if s["shot"] == "shot02"][0]
    assert shot["fallback_black"] is True and shot["ready"] is True
    assert plan["ready"] == 1


def test_start_end_requires_an_existing_end_frame(svc, studio_env, project):
    with pytest.raises(ValueError):
        svc.update_shot(project, "cena01", "shot01", start_end={"end": "edit/last_frames/nope.png"})
    root = _root(studio_env, project)
    make_image(root / "edit" / "last_frames" / "shot01_last.png")
    out = svc.update_shot(project, "cena01", "shot01",
                          start_end={"end": "edit/last_frames/shot01_last.png"})
    assert out["start_end"] == {"start": "shots/cena01/shot01_final.png",
                                "end": "edit/last_frames/shot01_last.png"}
    assert svc.update_shot(project, "cena01", "shot01", start_end=None)["start_end"] is None


# ---------- sugestão de prompt ----------
def test_suggest_prompt_covers_the_three_modes_of_the_lesson(svc, project):
    simple = svc.suggest_prompt(project, "cena01", "shot01")
    assert simple["prompt"] == "the astronaut walks through the blizzard, realistic, natural motion"
    assert simple["duration"] == 5 and "áudio do modelo OFF" in simple["ui_hint"]
    elaborate = svc.suggest_prompt(project, "cena01", "shot01", mode="elaborate",
                                   camera="Dramatic dolly-in", action="focusing on the reflection in his helmet")
    assert elaborate["prompt"] == ("Dramatic dolly-in camera movement, "
                                   "focusing on the reflection in his helmet. Realistic, cinematic")
    se = svc.suggest_prompt(project, "cena01", "shot01", mode="start_end", action="The weather changes quickly")
    assert se["prompt"].startswith("This is a start frame and end frame scene.")
    assert "slow and dramatic" in se["prompt"]


def test_suggest_prompt_slow_uses_ten_seconds_and_is_deterministic(svc, project):
    a = svc.suggest_prompt(project, "cena01", "shot01", slow=True)
    b = svc.suggest_prompt(project, "cena01", "shot01", slow=True)
    assert a == b, "mesma entrada, mesmo texto"
    assert a["duration"] == 10, "aula 012: 10 s para mudanças lentas"


def test_suggest_prompt_start_end_needs_a_pair(svc, studio_env, project):
    with pytest.raises(ValueError):
        svc.suggest_prompt(project, "cena02", "shot03", mode="start_end")   # última da cena, sem end manual
    make_image(_root(studio_env, project) / "edit" / "last_frames" / "x.png")
    svc.update_shot(project, "cena02", "shot03", start_end={"end": "edit/last_frames/x.png"})
    assert svc.suggest_prompt(project, "cena02", "shot03", mode="start_end")["prompt"]
    with pytest.raises(ValueError):
        svc.suggest_prompt(project, "cena01", "shot01", mode="magic")


# ---------- importação e takes ----------
@needs_ffmpeg
def test_import_upload_and_downloads_dedupe(svc, studio_env, project, tmp_path):
    v = make_video(tmp_path / "a.mp4", seconds=1)
    assert svc.import_upload(project, [("a.mp4", v.read_bytes())])["added"] == 1
    assert svc.import_upload(project, [("b.mp4", v.read_bytes())])["added"] == 0, "dedupe por conteúdo"
    dl = studio_env["tmp"] / "downloads"
    make_video(dl / "kling.mp4", seconds=1, size="160x120")
    (dl / "nota.txt").write_text("x")
    r = svc.import_downloads(project, since_minutes=60)
    assert r["added"] == 1 and r["scanned"] == 1
    assert {c["source"] for c in svc.list_candidates(project)} == {"upload", "downloads"}
    assert all(c["kind"] == "video" and c["duration"] > 0 for c in svc.list_candidates(project))


@needs_ffmpeg
def test_import_history_uses_the_video_kind(svc, studio_env, project, tmp_path, monkeypatch):
    v = make_video(tmp_path / "hist.mp4", seconds=1)
    from studio.common import ingest
    monkeypatch.setattr(ingest.hf, "history_media",
                        lambda kind, size=50: [{"id": "j1", "prompt": "p", "model": "kling3_0",
                                                "urls": [f"https://cdn/x.mp4?kind={kind}"]}])
    monkeypatch.setattr(ingest, "urlopen", lambda *a, **k: type("R", (), {"read": lambda _s: v.read_bytes()})())
    assert svc.import_history(project)["added"] == 1
    cand = svc.list_candidates(project)[0]
    assert cand["source"] == "higgsfield" and cand["job_id"] == "j1"


@needs_ffmpeg
def test_attach_take_numbers_takes_and_refuses_the_same_video_twice(svc, studio_env, project, tmp_path):
    svc.load_plan(project)
    c1 = _candidate(svc, studio_env, project, tmp_path, "t1.mp4")
    c2 = _candidate(svc, studio_env, project, tmp_path, "t2.mp4", size="160x120")
    root = _root(studio_env, project)
    r1 = svc.attach_take(project, "cena01", "shot01", c1)
    assert r1["take"]["file"] == "videos/cena01/shot01_take1.mp4"
    assert (root / r1["take"]["file"]).exists() and r1["take"]["liked"] is None
    assert r1["take"]["model"] == "kling3_0", "modelo sugerido quando não informado"
    r2 = svc.attach_take(project, "cena01", "shot01", c2, model="seedance_2_0")
    assert r2["take"]["file"] == "videos/cena01/shot01_take2.mp4"
    with pytest.raises(RuntimeError):
        svc.attach_take(project, "cena01", "shot01", c1)
    with pytest.raises(ValueError):
        svc.attach_take(project, "cena01", "shot02", c1, model="wan2_7")
    with pytest.raises(FileNotFoundError):
        svc.attach_take(project, "cena01", "shot01", "nao-existe")
    assert svc.list_candidates(project)[0]["selected"] is True


@needs_ffmpeg
def test_like_writes_final_copy_and_rejection_counts_as_failure(svc, studio_env, project, tmp_path):
    svc.load_plan(project)
    root = _root(studio_env, project)
    c1 = _candidate(svc, studio_env, project, tmp_path, "t1.mp4")
    c2 = _candidate(svc, studio_env, project, tmp_path, "t2.mp4", size="160x120")
    svc.attach_take(project, "cena01", "shot01", c1)
    svc.attach_take(project, "cena01", "shot01", c2)
    shot = svc.set_like(project, "cena01", "shot01", "take1", True)
    final = root / "videos" / "cena01" / "shot01_final.mp4"
    assert final.read_bytes() == (root / "videos" / "cena01" / "shot01_take1.mp4").read_bytes()
    assert shot["ready"] is True and svc.load_plan(project)["ready"] == 1
    shot = svc.set_like(project, "cena01", "shot01", "take2", True)
    assert [t["liked"] for t in shot["takes"]] == [None, True], "só um like por shot"
    assert final.read_bytes() == (root / "videos" / "cena01" / "shot01_take2.mp4").read_bytes()
    shot = svc.set_like(project, "cena01", "shot01", "take2", None)
    assert not final.exists(), "_final existe se e somente se há take com like"
    shot = svc.set_like(project, "cena01", "shot01", "take1", False)
    assert shot["failures"] == 1
    with pytest.raises(FileNotFoundError):
        svc.set_like(project, "cena01", "shot01", "take9", True)


# ---------- troca de modelo ----------
def test_model_suggestion_walks_the_order_then_gives_up(svc):
    assert svc.suggested_model(0) == "kling3_0"
    assert svc.suggested_model(2) == "kling3_0"
    assert svc.suggested_model(3) == "seedance_2_0", "aula 012: após 3 falhas, troque de modelo"
    assert svc.suggested_model(6) == "veo3_1_lite"
    assert svc.suggested_model(9) is None, "esgotada a ordem: corte para preto na montagem"


def test_model_order_is_configurable_by_env(svc, monkeypatch):
    monkeypatch.setenv("STUDIO_ANIMATE_MODELS", "kling3_0, wan2_7")
    assert svc.model_order() == ["kling3_0", "wan2_7"]
    assert svc.suggested_model(6) is None


def test_failures_count_rejections_and_cli_errors(svc):
    shot = {"cli_failures": 2, "takes": [{"liked": False}, {"liked": True}, {"liked": None}]}
    assert svc.failures_of(shot) == 3


# ---------- params do CLI ----------
def test_build_params_always_turns_the_model_audio_off(svc, project, studio_env):
    root = _root(studio_env, project)
    entry = {"image": "shots/cena01/shot01_final.png", "prompt": "walk", "duration": 5, "start_end": None}
    p = svc.build_params(entry, "kling3_0", root=root)
    assert p["sound"] is False and p["duration"] == 5 and p["aspect_ratio"] == "16:9" and p["mode"] == "pro"
    assert p["start_image"].endswith("shots/cena01/shot01_final.png") and p["start_image"].startswith("/")
    assert "end_image" not in p
    se = {**entry, "start_end": {"start": "shots/cena01/shot01_final.png", "end": "shots/cena01/shot02_final.png"}}
    assert svc.build_params(se, "kling3_0", root=root)["duration"] == 5
    veo = svc.build_params(se, "veo3_1_lite", root=root)
    assert veo["duration"] == 8, "veo3_1_lite com start+end exige 8 s"
    assert veo["end_image"].endswith("shot02_final.png") and veo["sound"] is False


# ---------- geração pelo CLI ----------
@needs_ffmpeg
def test_generate_creates_two_takes(svc, studio_env, project, tmp_path, monkeypatch):
    svc.load_plan(project)
    svc.update_shot(project, "cena01", "shot01", prompt="the astronaut walks, realistic")
    sent = {}
    seq = [make_video(tmp_path / "g1.mp4", seconds=1), make_video(tmp_path / "g2.mp4", seconds=1, size="160x120")]

    def fake_generate(model, params, timeout_s=600):
        sent.update({"model": model, "params": params, "timeout": timeout_s})
        return {"raw": {"id": "j1"}, "urls": ["https://cdn/out.mp4"], "id": f"j{len(sent)}"}

    monkeypatch.setattr(svc.hf, "generate", fake_generate)
    monkeypatch.setattr(svc.hf, "download", lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                               dest.write_bytes(seq.pop(0).read_bytes()), dest)[-1])
    svc.start_generate(project, "cena01", "shot01", "kling3_0", 2)
    job = _wait(svc, project)
    assert job["state"] == "done" and job["added"] == 2 and job["done"] == 2
    assert sent["params"]["sound"] is False and sent["timeout"] == svc.GENERATE_TIMEOUT_S
    shot = [s for s in svc.load_plan(project)["shots"] if s["shot"] == "shot01"][0]
    assert [t["file"] for t in shot["takes"]] == ["videos/cena01/shot01_take1.mp4",
                                                  "videos/cena01/shot01_take2.mp4"]
    assert all(t["model"] == "kling3_0" for t in shot["takes"])
    assert list((_root(studio_env, project) / "jobs").glob("animate_*.json"))


@needs_ffmpeg
def test_generate_survives_a_failing_take(svc, studio_env, project, tmp_path, monkeypatch):
    svc.load_plan(project)
    svc.update_shot(project, "cena01", "shot01", prompt="walk")
    calls = {"n": 0}
    video = make_video(tmp_path / "ok.mp4", seconds=1)

    def fake_generate(model, params, timeout_s=600):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("model overloaded")
        return {"raw": {}, "urls": ["https://cdn/out.mp4"], "id": "j2"}

    monkeypatch.setattr(svc.hf, "generate", fake_generate)
    monkeypatch.setattr(svc.hf, "download", lambda url, dest: (dest.parent.mkdir(parents=True, exist_ok=True),
                                                               dest.write_bytes(video.read_bytes()), dest)[-1])
    svc.start_generate(project, "cena01", "shot01", "kling3_0", 2)
    job = _wait(svc, project)
    assert job["state"] == "done" and job["added"] == 1 and job["done"] == 2
    assert any("failed" in line for line in job["log"])
    shot = [s for s in svc.load_plan(project)["shots"] if s["shot"] == "shot01"][0]
    assert shot["failures"] == 1 and len(shot["takes"]) == 1


def test_generate_without_video_url_is_a_failure_not_a_crash(svc, project, monkeypatch):
    svc.load_plan(project)
    svc.update_shot(project, "cena01", "shot01", prompt="walk")
    monkeypatch.setattr(svc.hf, "generate", lambda *a, **k: {"raw": {}, "urls": ["https://cdn/x.png"], "id": "j"})
    svc.start_generate(project, "cena01", "shot01", "kling3_0", 1)
    job = _wait(svc, project)
    assert job["state"] == "done" and job["added"] == 0 and any("failed" in ln for ln in job["log"])


def test_generate_validates_before_spending_credits(svc, project):
    svc.load_plan(project)
    with pytest.raises(ValueError):
        svc.start_generate(project, "cena01", "shot01", "kling3_0", 1)          # sem prompt
    svc.update_shot(project, "cena01", "shot01", prompt="walk")
    with pytest.raises(ValueError):
        svc.start_generate(project, "cena01", "shot01", "wan2_7", 1)            # modelo fora da ordem
    with pytest.raises(ValueError):
        svc.start_generate(project, "cena01", "shot01", "kling3_0", 9)          # count fora de 1..4
    with pytest.raises(ValueError):
        svc.start_generate(project, "cena01", "shot01", "kling3_0", 1, duration=7)
    with pytest.raises(FileNotFoundError):
        svc.start_generate(project, "cena09", "shot01", "kling3_0", 1)


def test_generate_refuses_a_concurrent_job(svc, project, monkeypatch):
    svc.load_plan(project)
    svc.update_shot(project, "cena01", "shot01", prompt="walk")
    gate = threading.Event()
    monkeypatch.setattr(svc.hf, "generate",
                        lambda *a, **k: (gate.wait(5), {"raw": {}, "urls": [], "id": "x"})[1])
    svc.start_generate(project, "cena01", "shot01", "kling3_0", 1)
    with pytest.raises(RuntimeError):
        svc.start_generate(project, "cena01", "shot01", "kling3_0", 1)
    gate.set()
    assert _wait(svc, project)["state"] == "done"


def test_cost_reports_unknown_credits(svc, project, monkeypatch):
    svc.load_plan(project)
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: {"credits": 25, "raw": {}})
    assert svc.cost(project, "cena01", "shot01", "kling3_0", 2) == {
        "per_take": 25, "total": 50, "credits_unknown": False, "model": "kling3_0", "count": 2, "error": None}
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: {"credits": None, "error": "not authenticated"})
    out = svc.cost(project, "cena01", "shot01", "kling3_0", 2)
    assert out["credits_unknown"] is True and out["total"] is None and out["error"]


def test_cost_sends_the_same_params_as_generate(svc, project, studio_env, monkeypatch):
    svc.load_plan(project)
    svc.update_shot(project, "cena01", "shot01", prompt="walk", duration=10)
    seen = {}
    monkeypatch.setattr(svc.hf, "cost", lambda model, params: seen.update(params) or {"credits": 1})
    svc.cost(project, "cena01", "shot01", "kling3_0", 2)
    root = _root(studio_env, project)
    entry = {"image": "shots/cena01/shot01_final.png", "prompt": "walk", "duration": 10, "start_end": None}
    assert seen == svc.build_params(entry, "kling3_0", root=root)
