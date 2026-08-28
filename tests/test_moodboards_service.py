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


def test_list_thumbs_selected_with_fallback(studio_env):
    """wave 5 · ponto 4: o `list` expõe `thumbs` (até 4) para o mosaico quadricular — as imagens
    selecionadas quando há curadoria, senão as candidatas importadas."""
    mb = studio_env["moodboards"]
    # 5 imagens DISTINTAS (o ingest deduplica por conteúdo): garante o teto de 4 no fallback
    mbid = mb.create_board("Mosaic")["id"]
    for i in range(5):
        mb.import_upload(mbid, [(f"m{i}.png", image_bytes((20 + i * 40, 60, 200 - i * 30)))])
    # sem curadoria ainda: thumbs caem para as candidatas, com teto de 4
    board = next(b for b in mb.list_boards() if b["id"] == mbid)
    assert board["count"] == 0
    assert len(board["thumbs"]) == 4
    assert all(t.startswith("candidates/") for t in board["thumbs"])
    # depois de curar: thumbs são as selecionadas (imagens curadas), servidas por images/<f>
    cands = mb.candidates(mbid)
    mb.select(mbid, [c["id"] for c in cands[:2]])
    board = next(b for b in mb.list_boards() if b["id"] == mbid)
    assert board["count"] == 2
    assert board["thumbs"] == mb.board_image_files(mbid)
    assert all(t.startswith("images/") for t in board["thumbs"])
    # board vazio: sem imagens nem candidatas, thumbs é lista vazia (mosaico desenha o placeholder)
    empty = mb.create_board("Empty")["id"]
    assert next(b for b in mb.list_boards() if b["id"] == empty)["thumbs"] == []


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


def test_remove_candidate_deletes_file_thumb_and_entry(studio_env):
    """§3 da FDD: remover apaga o arquivo, a thumb e a entrada de `candidates.json`."""
    mb = studio_env["moodboards"]
    mbid = _board_with_images(mb, n=3)
    d = mb.board_dir(mbid)
    cands = mb.candidates(mbid)
    victim = cands[0]
    fpath = d / "candidates" / victim["file"]
    tpath = d / "candidates" / victim["thumb"]
    assert fpath.is_file() and tpath.is_file()
    r = mb.remove_candidate(mbid, victim["id"])
    assert r["removed"] == victim["id"] and r["candidates"] == 2
    assert not fpath.exists() and not tpath.exists()
    remaining = mb.candidates(mbid)
    assert len(remaining) == 2 and all(c["id"] != victim["id"] for c in remaining)


def test_remove_candidate_unselects_and_rederives_palette(studio_env):
    """Se a candidata estava selecionada: sai da seleção, some de `images/` e a paleta é refeita."""
    mb = studio_env["moodboards"]
    mbid = _board_with_images(mb, n=3)
    d = mb.board_dir(mbid)
    cands = mb.candidates(mbid)
    chosen = [c["id"] for c in cands[:2]]
    mb.select(mbid, chosen)
    victim = next(c for c in mb.candidates(mbid) if c["id"] == chosen[0])
    assert (d / "images" / victim["file"]).is_file()
    r = mb.remove_candidate(mbid, victim["id"])
    assert r["was_selected"] is True
    assert not (d / "images" / victim["file"]).exists()
    det = mb.get_board(mbid)
    # a candidata some da lista e da contagem de curadas (só resta 1 selecionada)
    assert all(c["id"] != victim["id"] for c in det["candidates"])
    assert det["count"] == 1


def test_remove_candidate_missing_raises_keyerror(studio_env):
    """Candidata inexistente → KeyError (o router traduz em 404)."""
    mb = studio_env["moodboards"]
    mbid = _board_with_images(mb, n=1)
    with pytest.raises(KeyError):
        mb.remove_candidate(mbid, "nao_existe")


def test_downloads_folder_reuses_ingest_default(studio_env):
    """§3 da FDD: `downloads-folder` reusa `ingest._default_downloads` e informa se existe."""
    mb = studio_env["moodboards"]
    from studio.common import ingest
    r = mb.downloads_folder()
    assert r["folder"] == str(ingest._default_downloads())
    assert r["exists"] is True   # o conftest cria tmp/downloads e aponta STUDIO_DOWNLOADS para ela


def test_open_folder_best_effort_never_raises(studio_env, monkeypatch):
    """§3 da FDD: abrir pasta é best-effort com o subprocess mockado — nunca lança (nunca 500)."""
    mb = studio_env["moodboards"]
    from studio.moodboards import service as svc
    mbid = mb.create_board("Openable")["id"]
    calls = {"popen": 0}
    monkeypatch.setattr(svc.shutil, "which", lambda name: "/usr/bin/xdg-open" if name == "xdg-open" else None)
    monkeypatch.setattr(svc.subprocess, "Popen", lambda *a, **k: calls.__setitem__("popen", calls["popen"] + 1))
    r = mb.open_board_folder(mbid)
    assert r["opened"] is True and r["path"] == str(mb.board_dir(mbid)) and calls["popen"] == 1
    # se o subprocess estourar, ainda assim retorna opened=False sem propagar
    monkeypatch.setattr(svc.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    r2 = mb.open_board_folder(mbid)
    assert r2["opened"] is False and "path" in r2


def test_prompt_template_is_deterministic(studio_env):
    mb = studio_env["moodboards"]
    mbid = _board_with_images(mb, n=1)
    r = mb.generate_prompt(mbid, mode="template")
    assert r["source"] == "template" and r["prompt"]
    assert mb.suggest_prompt(mbid)["prompt"] == r["prompt"]
