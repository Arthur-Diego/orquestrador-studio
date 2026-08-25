"""Etapa 4 — o storyboard segue a aula 010: uma instrução por vez, 4/1 gerações, ~5 cenas em texto."""
import json
import threading

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def project(studio_env):
    meta = studio_env["refs"].create_project("Gelo Zero", "energy drink", "snow neon")
    return meta["id"]


@pytest.fixture()
def sb(studio_env):
    return studio_env["svc"]("storyboard")


@pytest.fixture()
def root(studio_env, project):
    return studio_env["refs"].project_dir(project)


@pytest.fixture()
def base(root):
    """Handoff da etapa 3 (OS-003, em voo na mesma wave): fixture no lugar da base real."""
    return make_image(root / "base" / "base_final.png")


# ---------- instruções (aula 010) ----------
def test_instruction_keeps_course_formula_and_suffix(sb, project, base):
    r = sb.build_instruction(project, "edit", "Make the climber even smaller and more realistic", 4)
    assert r["instruction"] == "Make the climber even smaller and more realistic. Keep everything else identical, realistic."
    assert r["count"] == 4 and r["base_image"] == "base/base_final.png"
    assert "4 variações" in r["ui_hint"], "aula 010: 4 gerações quando está incerto"
    assert sb.build_instruction(project, "draw_to_edit", "the climber climbs the can", 1)["instruction"].startswith("Follow the sketch:")
    ms = sb.build_instruction(project, "multishot", "a close-up on the character", 1)["instruction"]
    assert ms.startswith("Another point of view of this exact scene:") and "1 variação" in \
        sb.build_instruction(project, "multishot", "a close-up on the character", 1)["ui_hint"]


def test_instruction_refuses_more_than_one_edit(sb, project, base):
    with pytest.raises(sb.Invalid) as e:
        sb.build_instruction(project, "edit", "1. Make it smaller 2. Remove the rope", 4)
    assert "uma instrução por vez" in str(e.value).lower()
    assert "Make it smaller" in str(e.value), "a mensagem sugere a primeira instrução"
    with pytest.raises(sb.Invalid):
        sb.build_instruction(project, "edit", "Make it smaller. Remove the rope.", 4)


def test_instruction_count_is_four_or_one(sb, project, base):
    for bad in (0, 2, 3, 10):
        with pytest.raises(sb.Invalid):
            sb.build_instruction(project, "edit", "Make it smaller", bad)


def test_instruction_validates_kind_and_text(sb, project, base):
    with pytest.raises(sb.Invalid):
        sb.build_instruction(project, "inpaint", "Make it smaller", 4)
    with pytest.raises(sb.Invalid):
        sb.build_instruction(project, "edit", "   ", 4)
    with pytest.raises(sb.Invalid):
        sb.build_instruction(project, "edit", "x" * 301, 4)


def test_instruction_requires_base_image_from_step_three(sb, project):
    with pytest.raises(sb.Precondition):
        sb.build_instruction(project, "edit", "Make it smaller", 4)
    assert sb.status(project)["has_base"] is False


def test_presets_are_in_english_with_ptbr_labels(sb):
    p = sb.presets()
    assert p["counts"] == {"uncertain": 4, "tweak": 1}
    assert {k["kind"] for k in p["kinds"]} == {"draw_to_edit", "edit", "multishot"}
    assert any(x["text"] == "a close-up on the character" for x in p["presets"])


# ---------- cenas ----------
def test_scenes_default_to_five_empty_scenes(sb, project, root):
    scenes = sb.load_scenes(project)["scenes"]
    assert [s["id"] for s in scenes] == [f"cena{i:02d}" for i in range(1, 6)]
    assert all(s["text"] == "" and s["image"] is None for s in scenes)
    assert [s["n"] for s in scenes] == [1, 2, 3, 4, 5]
    on_disk = json.loads((root / "storyboard" / "scenes.json").read_text())
    assert on_disk == {"scenes": scenes}, "schema do wave-1.md, persistido na primeira leitura"


def test_save_scenes_renumbers_by_order_and_writes_md(sb, project, root):
    r = sb.save_scenes(project, [{"text": "Close no astronauta", "image": None},
                                 {"text": "Ele encontra a lata gigante", "image": None},
                                 {"text": "A lata cai", "image": None}])
    assert [s["id"] for s in r["scenes"]] == ["cena01", "cena02", "cena03"]
    assert r["storyboard_md"] == "storyboard/storyboard.md"
    md = (root / "storyboard" / "storyboard.md").read_text()
    assert "# Storyboard: Gelo Zero" in md and "## Cena 1" in md and "Close no astronauta" in md
    reordered = sb.save_scenes(project, [{"text": "A lata cai"}, {"text": "Close no astronauta"}])["scenes"]
    assert reordered[0] == {"id": "cena01", "n": 1, "text": "A lata cai", "image": None}


def test_save_scenes_limits_and_image_must_live_in_ideas(sb, project, base):
    with pytest.raises(sb.Invalid):
        sb.save_scenes(project, [])
    with pytest.raises(sb.Invalid):
        sb.save_scenes(project, [{"text": f"c{i}"} for i in range(11)])
    with pytest.raises(sb.Invalid):
        sb.save_scenes(project, [{"text": "x" * 501}])
    for bad in ("../base/base_final.png", "storyboard/ideas/../../base/base_final.png",
                "storyboard/ideas/nao-existe.png", "storyboard/candidates/x.png"):
        with pytest.raises(sb.Invalid):
            sb.save_scenes(project, [{"text": "c", "image": bad}])


def test_corrupted_scenes_json_falls_back_to_default(sb, project, root):
    (root / "storyboard").mkdir(parents=True, exist_ok=True)
    (root / "storyboard" / "scenes.json").write_text("{quebrado")
    assert len(sb.load_scenes(project)["scenes"]) == 5


def test_render_requires_at_least_one_written_scene(sb, project):
    with pytest.raises(sb.Invalid):
        sb.render(project)
    sb.save_scenes(project, [{"text": "Close no astronauta"}])
    assert sb.render(project)["storyboard_md"] == "storyboard/storyboard.md"


# ---------- ideias ----------
def test_upload_reports_skipped_and_dedupes(sb, project, root):
    data = image_bytes()
    assert sb.import_upload(project, [("a.png", data), ("nota.txt", b"nao e imagem")]) == {"added": 1, "skipped": 1}
    assert sb.import_upload(project, [("a.png", data)]) == {"added": 0, "skipped": 1}
    assert (root / "storyboard" / "candidates").exists()
    assert list((root / "storyboard" / "candidates" / "thumbs").glob("*.jpg"))


def test_downloads_import_records_the_prompt_used(sb, project, studio_env):
    make_image(studio_env["tmp"] / "downloads" / "idea.png")
    r = sb.import_downloads(project, since_minutes=60, prompt="Make it smaller. Keep everything else identical, realistic.")
    assert r["added"] == 1
    idea = sb.list_ideas(project)["ideas"][0]
    assert idea["prompt"].startswith("Make it smaller") and idea["source"] == "downloads"


def test_downloads_import_rejects_unknown_folder(sb, project, studio_env):
    with pytest.raises(sb.Invalid):
        sb.import_downloads(project, folder=str(studio_env["tmp"] / "nao-existe"))


def test_select_copies_to_ideas_and_detaches_scene_on_deselect(sb, project, root):
    sb.import_upload(project, [("a.png", image_bytes(color=(1, 2, 3))), ("b.png", image_bytes(color=(9, 9, 9)))])
    a, b = [i["id"] for i in sb.list_ideas(project)["ideas"]]
    r = sb.select_ideas(project, [a, b])
    assert r == {"selected": 2, "detached": []}
    ideas_dir = root / "storyboard" / "ideas"
    assert len([p for p in ideas_dir.iterdir() if p.name != "ideas.json"]) == 2
    rows = json.loads((ideas_dir / "ideas.json").read_text())
    assert all(set(row) == {"id", "file", "thumb", "prompt", "selected"} for row in rows)
    assert all(row["file"].startswith("storyboard/ideas/") for row in rows)

    img = next(i["file"] for i in sb.list_ideas(project)["ideas"] if i["id"] == a)
    sb.save_scenes(project, [{"text": "Close no astronauta", "image": img}, {"text": "A lata cai"}])
    out = sb.select_ideas(project, [b])
    assert out == {"selected": 1, "detached": ["cena01"]}
    assert sb.load_scenes(project)["scenes"][0]["image"] is None
    assert len([p for p in ideas_dir.iterdir() if p.name != "ideas.json"]) == 1, "ideias/ guarda só as selecionadas (decisão 7)"


def test_select_rejects_unknown_id(sb, project):
    with pytest.raises(sb.Invalid):
        sb.select_ideas(project, ["nao-existe"])


def test_status_counts_ideas_scenes_and_base(sb, project, root, base):
    sb.import_upload(project, [("a.png", image_bytes())])
    sb.select_ideas(project, [sb.list_ideas(project)["ideas"][0]["id"]])
    sb.save_scenes(project, [{"text": "Close no astronauta"}, {"text": ""}])
    st = sb.status(project)
    assert st == {"base_image": "base/base_final.png", "has_base": True, "ideas": 1, "selected": 1,
                  "scenes": 2, "scenes_with_text": 1, "storyboard_md": "storyboard/storyboard.md"}


# ---------- alternativa paga pelo CLI ----------
def _fake_cli(monkeypatch, sb, urls=("http://x/a.png", "http://x/b.png"), gate=None):
    monkeypatch.setattr(sb.hf, "available", lambda: True)
    monkeypatch.setattr(sb.hf, "status", lambda: {"installed": True, "logged_in": True, "credits": 100})
    colors = iter([(10, 20, 30), (40, 50, 60), (70, 80, 90), (100, 110, 120)])

    def fake_generate(model, params, timeout_s=600):
        if gate is not None:
            gate.wait(5)
        return {"raw": {"model": model, "params": params}, "urls": list(urls), "id": "job1"}

    def fake_download(url, dest):
        from pathlib import Path
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(image_bytes(color=next(colors)))
        return dest

    monkeypatch.setattr(sb.hf, "generate", fake_generate)
    monkeypatch.setattr(sb.hf, "download", fake_download)


def _wait_job(sb, project, tries=100):
    for _ in range(tries):
        if sb.job_status(project)["state"] != "running":
            break
        threading.Event().wait(0.05)
    return sb.job_status(project)


def test_cli_generate_imports_results_as_candidates(sb, project, base, monkeypatch, root):
    _fake_cli(monkeypatch, sb)
    sb.start_generate(project, "nano_banana_2", "edit", "Make it smaller", 1)
    job = _wait_job(sb, project)
    assert job["state"] == "done" and job["added"] == 2 and job["done"] == 1
    ideas = sb.list_ideas(project)["ideas"]
    assert len(ideas) == 2 and all(i["source"] == "cli" for i in ideas)
    assert all(i["prompt"] == "Make it smaller. Keep everything else identical, realistic." for i in ideas)
    assert list((root / "jobs").glob("storyboard_*.json"))


def test_cli_generate_refuses_concurrent_job(sb, project, base, monkeypatch):
    gate = threading.Event()
    _fake_cli(monkeypatch, sb, gate=gate)
    sb.start_generate(project, "nano_banana_2", "edit", "Make it smaller", 1)
    with pytest.raises(sb.Precondition):
        sb.start_generate(project, "nano_banana_2", "edit", "Make it smaller", 1)
    gate.set()
    assert _wait_job(sb, project)["state"] == "done"


def test_cli_has_no_draw_to_edit(sb, project, base, monkeypatch):
    _fake_cli(monkeypatch, sb)
    with pytest.raises(sb.Invalid):
        sb.start_generate(project, "nano_banana_2", "draw_to_edit", "the climber climbs", 1)


def test_cli_requires_login_and_reports_cost(sb, project, base, monkeypatch):
    monkeypatch.setattr(sb.hf, "available", lambda: False)
    with pytest.raises(sb.Precondition):
        sb.cost(project, "nano_banana_2", "edit", "Make it smaller", 4)
    _fake_cli(monkeypatch, sb)
    monkeypatch.setattr(sb.hf, "cost", lambda model, params: {"credits": 3})
    assert sb.cost(project, "nano_banana_2", "edit", "Make it smaller", 4) == {"per_image": 3, "total": 12}
    monkeypatch.setattr(sb.hf, "cost", lambda model, params: {"credits": None, "error": "x"})
    assert sb.cost(project, "nano_banana_2", "edit", "Make it smaller", 1) == {"per_image": None, "total": None}
