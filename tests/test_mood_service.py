"""Etapa 2 — o mood board segue a aula 009: UMA vibe, sem produto/pessoas; import e paleta."""
import json

import pytest

from tests.conftest import image_bytes, make_image


@pytest.fixture()
def project(studio_env):
    refs = studio_env["refs"]
    meta = refs.create_project("Gelo Zero", "energy drink", "snow neon")
    return meta["id"]


def test_mood_prompt_is_single_vibe_without_product(studio_env, project):
    mood = studio_env["mood"]
    r = mood.suggest_prompts(project)
    assert len(r["prompts"]) == 1, "aula 009: um prompt de vibe, gerado em grid de 4"
    text = r["prompts"][0]["text"].lower()
    assert "no product" in text and "no people" in text and "no text" in text
    assert "snow neon" in text and "energy drink" in text
    assert r["aspect_ratio"] == "16:9"


def test_mood_prompt_variations_change_only_style(studio_env, project):
    mood = studio_env["mood"]
    a = mood.suggest_prompts(project, variation=0)["prompts"][0]["text"]
    b = mood.suggest_prompts(project, variation=1)["prompts"][0]["text"]
    assert a != b
    assert a.split("Wide establishing")[0] == b.split("Wide establishing")[0], "a vibe (parte inicial) não muda"


def test_mood_prompt_ignores_pinterest_ui_alt_text(studio_env, project):
    from studio.refs import pinterest
    from studio.refs import service as refs
    mood = studio_env["mood"]
    cdir = refs.project_dir(project) / "refs" / "candidates"
    make_image(cdir / "a.jpg")
    pinterest.save_candidates(cdir, [pinterest.Candidate(id="a", source="pinterest", term="energy drink snow ads",
                                                         url="u", pin_url=None, alt="Salvar Pins", file="a.jpg",
                                                         thumb="thumbs/a.jpg", selected=True)])
    text = mood.suggest_prompts(project)["prompts"][0]["text"]
    assert "Salvar Pins" not in text and "energy drink snow ads" in text


def test_import_downloads_only_recent_images(studio_env, project):
    import os
    import time
    mood = studio_env["mood"]
    dl = studio_env["tmp"] / "downloads"
    make_image(dl / "novo.jpg")
    old = make_image(dl / "velho.jpg", color=(1, 2, 3))
    os.utime(old, (time.time() - 3 * 3600, time.time() - 3 * 3600))
    (dl / "nao-imagem.txt").write_text("x")
    r = mood.import_downloads(project, since_minutes=60)
    assert r["added"] == 1 and r["scanned"] == 1
    assert mood.load(project)[0]["source"] == "downloads"


def test_import_upload_dedupes_by_content(studio_env, project):
    mood = studio_env["mood"]
    data = image_bytes()
    assert mood.import_upload(project, [("a.png", data), ("b.png", data)])["added"] == 1
    assert mood.import_upload(project, [("c.png", image_bytes(color=(1, 200, 1)))])["added"] == 1
    assert len(mood.load(project)) == 2


def test_select_writes_palette_and_md_and_caps_at_eight(studio_env, project):
    mood = studio_env["mood"]
    mood.import_upload(project, [(f"{i}.png", image_bytes(color=(10 * i, 100, 200))) for i in range(10)])
    ids = [c["id"] for c in mood.load(project)]
    r = mood.select(project, ids[:3], note="neve, neon, silêncio")
    assert r["selected"] == 3 and len(r["palette"]) >= 1 and all(c.startswith("#") for c in r["palette"])
    root = studio_env["refs"].project_dir(project)
    assert len(list((root / "mood" / "selected").iterdir())) == 3
    assert json.loads((root / "mood" / "palette.json").read_text())["note"] == "neve, neon, silêncio"
    assert "Mood board" in (root / "mood" / "mood.md").read_text()
    with pytest.raises(ValueError):
        mood.select(project, ids[:9])


def test_select_over_cap_keeps_previous_selection(studio_env, project):
    mood = studio_env["mood"]
    mood.import_upload(project, [(f"{i}.png", image_bytes(color=(20 * i, 50, 90))) for i in range(10)])
    ids = [c["id"] for c in mood.load(project)]
    mood.select(project, ids[:2])
    with pytest.raises(ValueError):
        mood.select(project, ids[:9])
    root = studio_env["refs"].project_dir(project)
    assert len(list((root / "mood" / "selected").iterdir())) == 2, "seleção válida anterior não pode ser destruída"
    assert sum(c["selected"] for c in mood.load(project)) == 2


def test_start_generate_refuses_concurrent_job(studio_env, project, monkeypatch):
    import threading
    mood = studio_env["mood"]
    gate = threading.Event()
    monkeypatch.setattr(mood.hf, "generate", lambda *a, **k: (gate.wait(5), {"urls": [], "id": "x", "raw": {}})[1])
    mood.start_generate(project, "nano_banana_2", ["p"])
    with pytest.raises(RuntimeError):
        mood.start_generate(project, "nano_banana_2", ["p"])
    gate.set()
    for _ in range(50):
        if mood.job_status(project)["state"] != "running":
            break
        threading.Event().wait(0.05)
    assert mood.job_status(project)["state"] == "done"


def test_generate_prompt_modes_and_history(studio_env, project, monkeypatch):
    mood = studio_env["mood"]
    from studio.common import prompter
    # template não precisa de Claude
    t = mood.generate_prompt(project, "template", variation=2)
    assert t["source"] == "template" and t["mode"] == "template" and "No product" in t["prompt"]
    # sem Claude, brief/images → RuntimeError (409 na API)
    monkeypatch.setattr(prompter, "BIN", None)
    with pytest.raises(RuntimeError):
        mood.generate_prompt(project, "brief")
    # com Claude fakeado: imagens de vibe + instrução
    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")
    mood.vibe_import_upload(project, [("v1.png", image_bytes(color=(0, 90, 200)))])
    vid = mood.vibe_images(project)[0]["id"]
    seen = {}
    def fake_from_images(kind, images, instruction="", brief=None):
        seen.update(kind=kind, images=[str(p) for p in images], instruction=instruction, brief=brief)
        return {"prompt": "Cold neon snowfield", "negative": "text", "camera": "RED 35mm", "notes_pt": "n", "source": "claude", "seconds": 1.0}
    monkeypatch.setattr(prompter, "from_images", fake_from_images)
    r = mood.generate_prompt(project, "images", "bastante neon", [vid])
    assert seen["kind"] == "mood" and seen["images"][0].endswith(".png") and seen["instruction"] == "bastante neon"
    assert seen["brief"]["product"] == "energy drink" and "No product" in r["prompt"] and r["images"] == [vid]
    with pytest.raises(ValueError):
        mood.generate_prompt(project, "images", "x", [])
    with pytest.raises(ValueError):
        mood.generate_prompt(project, "images", "x", ["nao-existe"])
    hist = mood.prompt_history(project)
    assert [h["mode"] for h in hist] == ["images", "template"]
