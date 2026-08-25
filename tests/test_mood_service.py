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
