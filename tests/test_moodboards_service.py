"""Serviço da biblioteca global de mood boards `[extensão]` (ADR-013) — sem rede (ADR-008)."""
import pytest

from tests.conftest import image_bytes


def _board_with_images(mb, name="Neon Snow", n=2):
    board = mb.create_board(name)
    mbid = board["id"]
    colors = [(10, 80, 200), (200, 30, 60), (40, 160, 90)]
    for i in range(n):
        mb.import_upload(mbid, [(f"g{i}.png", image_bytes(colors[i % len(colors)]))])
    return mbid


def test_create_list_rename_delete(studio_env):
    mb = studio_env["moodboards"]
    assert mb.list_boards() == []
    board = mb.create_board("Neon Snow", note="frio")
    assert board["id"] == "neon-snow" and board["name"] == "Neon Snow" and board["note"] == "frio"
    listed = mb.list_boards()
    assert len(listed) == 1 and listed[0]["id"] == "neon-snow" and listed[0]["count"] == 0
    # nome duplicado -> ValueError (o router traduz em 409)
    with pytest.raises(ValueError):
        mb.create_board("Neon Snow")
    r = mb.patch_board("neon-snow", name="Neon Winter", vibe="icy neon")
    assert r["name"] == "Neon Winter" and r["vibe"] == "icy neon" and r["id"] == "neon-snow"
    assert mb.get_board("neon-snow")["vibe"] == "icy neon"
    mb.delete_board("neon-snow")
    assert mb.list_boards() == []
    with pytest.raises(KeyError):
        mb.get_board("neon-snow")


def test_import_curate_and_palette(studio_env):
    mb = studio_env["moodboards"]
    mbid = _board_with_images(mb, n=3)
    cands = mb.candidates(mbid)
    assert len(cands) == 3
    ids = [c["id"] for c in cands][:2]
    res = mb.select(mbid, ids)
    assert res["selected"] == 2 and all(c.startswith("#") for c in res["palette"])
    det = mb.get_board(mbid)
    assert det["count"] == 2 and det["cover"] and det["cover"].startswith("images/")
    assert len(det["images"]) == 2 and det["palette"]["colors"]
    # as imagens curadas existem como arquivos e são acessíveis por caminho absoluto
    paths = mb.board_image_paths(mbid)
    assert len(paths) == 2 and all(p.is_file() for p in paths)
    assert mb.board_image_files(mbid) == det["images"]


def test_curate_cap_of_8(studio_env):
    mb = studio_env["moodboards"]
    mbid = mb.create_board("Big")["id"]
    with pytest.raises(ValueError, match="8"):
        mb.select(mbid, [f"x{i}" for i in range(9)])


def test_mbid_validation_never_escapes_dir(studio_env):
    mb = studio_env["moodboards"]
    for bad in ("../etc", "a/b", "UPPER", "", "with space"):
        with pytest.raises(KeyError):
            mb.board_dir(bad)


def test_reserved_name_moodboards_as_pid(studio_env):
    """A área global reserva o nome `moodboards`: nenhum projeto pode ter esse pid (ADR-013)."""
    refs = studio_env["refs"]
    assert "moodboards" in refs.RESERVED_PIDS
    with pytest.raises(ValueError, match="reservado"):
        refs.create_project("moodboards")
    # um projeto normal continua sendo criado sem problema
    assert refs.create_project("Campanha X")["id"].endswith("-campanha-x")


def test_prompt_template_is_deterministic(studio_env):
    mb = studio_env["moodboards"]
    mbid = _board_with_images(mb, n=1)
    r = mb.generate_prompt(mbid, mode="template")
    assert r["source"] == "template" and r["prompt"]
    assert mb.suggest_prompt(mbid)["prompt"] == r["prompt"]
