"""Etapa 1 — projetos, termos de busca e seleção de referências (sem tocar na rede)."""
import json

import pytest

from tests.conftest import make_image


def test_create_project_builds_course_tree(studio_env):
    refs = studio_env["refs"]
    meta = refs.create_project("Gelo Zero", "energy drink", "snow neon")
    root = refs.project_dir(meta["id"])
    assert meta["id"].endswith("-gelo-zero")
    for sub in ("refs/candidates/thumbs", "refs/brainstorming", "mood", "videos"):
        assert (root / sub).is_dir()
    assert json.loads((root / "project.json").read_text())["product"] == "energy drink"


def test_create_project_rejects_duplicate(studio_env):
    refs = studio_env["refs"]
    refs.create_project("Dup")
    with pytest.raises(ValueError):
        refs.create_project("Dup")


def test_suggest_terms_are_english_and_include_vibe(studio_env):
    refs = studio_env["refs"]
    terms = refs.suggest_terms("energy drink", "snow neon")
    assert "energy drink ad campaign" in terms
    assert any("snow neon" in t for t in terms)
    assert all(t == t.strip() and t for t in terms)


def test_select_copies_to_brainstorming_and_writes_readme(studio_env):
    refs = studio_env["refs"]
    from studio.refs import pinterest
    meta = refs.create_project("Sel")
    root = refs.project_dir(meta["id"])
    cdir = root / "refs" / "candidates"
    cands = []
    for i, cid in enumerate(("aaa111", "bbb222", "ccc333")):
        make_image(cdir / f"{cid}.jpg")
        cands.append(pinterest.Candidate(id=cid, source="pinterest", term=f"term {i}", url=f"https://x/{cid}.jpg",
                                         pin_url=None, alt="", file=f"{cid}.jpg", thumb=f"thumbs/{cid}.jpg"))
    pinterest.save_candidates(cdir, cands)

    r = refs.select(meta["id"], ["aaa111", "ccc333"], {"aaa111": "gostei do gelo"})
    assert r == {"selected": 2}
    assert sorted(p.name for p in (root / "refs" / "brainstorming").iterdir()) == ["aaa111.jpg", "ccc333.jpg"]
    readme = (root / "refs" / "README.md").read_text()
    assert "gostei do gelo" in readme and "Nunca entram no vídeo final" in readme
    assert {c["id"]: c["selected"] for c in refs.candidates(meta["id"])} == {"aaa111": True, "bbb222": False, "ccc333": True}

    # desmarcar remove da pasta de brainstorming
    refs.select(meta["id"], ["bbb222"])
    assert [p.name for p in (root / "refs" / "brainstorming").iterdir()] == ["bbb222.jpg"]


def test_pinterest_best_url_upgrades_to_originals(studio_env):
    from studio.refs.pinterest import _best_url
    assert _best_url("https://i.pinimg.com/236x/ab/cd/ef.jpg") == "https://i.pinimg.com/originals/ab/cd/ef.jpg"
    assert _best_url("https://i.pinimg.com/originals/ab/cd/ef.jpg") == "https://i.pinimg.com/originals/ab/cd/ef.jpg"


def test_project_dir_rejects_unsafe_ids(studio_env):
    refs = studio_env["refs"]
    for bad in ("../etc", "a/b", "", "X Y", "a" * 90):
        with pytest.raises(KeyError):
            refs.project_dir(bad)
