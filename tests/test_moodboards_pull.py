"""Puxar/referenciar a biblioteca nas etapas 2 e 3 `[extensão]` (ADR-013) — sem rede (ADR-008)."""
import json

from tests.conftest import image_bytes
from tests.test_base_service import _fake_claude, prepare


def _board(mb, name="Winter", n=2, vibe="icy winter"):
    mbid = mb.create_board(name)["id"]
    for i, col in enumerate([(10, 80, 200), (200, 30, 60), (40, 160, 90)][:n]):
        mb.import_upload(mbid, [(f"g{i}.png", image_bytes(col))])
    mb.select(mbid, [c["id"] for c in mb.candidates(mbid)])
    if vibe:
        mb.patch_board(mbid, vibe=vibe)
    return mbid


# ---------- etapa 2: puxar do board ----------
def test_pull_board_copies_images_and_seeds_vibe(studio_env):
    mb = studio_env["moodboards"]
    mood = studio_env["mood"]
    refs = studio_env["refs"]
    mbid = _board(mb, n=2, vibe="icy winter")
    pid = refs.create_project("Camp", "soda")["id"]
    res = mood.pull_board(pid, mbid)
    assert res["selected"] == 2 and res["vibe"] == "icy winter" and res["board"] == mbid
    root = refs.project_dir(pid)
    copied = sorted(p.name for p in (root / "mood" / "selected").iterdir() if p.is_file())
    assert len(copied) == 2
    # semeia palette.json, mood.md e project.vibe
    pal = json.loads((root / "mood" / "palette.json").read_text())
    assert pal["colors"] and pal["note"] == "icy winter"
    assert (root / "mood" / "mood.md").exists()
    assert json.loads((root / "project.json").read_text())["vibe"] == "icy winter"


def test_pull_is_idempotent_and_board_independent(studio_env):
    mb = studio_env["moodboards"]
    mood = studio_env["mood"]
    refs = studio_env["refs"]
    mbid = _board(mb, n=3)
    pid = refs.create_project("Camp2")["id"]
    mood.pull_board(pid, mbid)
    mood.pull_board(pid, mbid)   # reexecutar sobrescreve, não acumula
    root = refs.project_dir(pid)
    assert len(list((root / "mood" / "selected").iterdir())) == 3
    # apagar o board depois NÃO afeta a campanha (a cópia é independente)
    mb.delete_board(mbid)
    assert len(list((root / "mood" / "selected").iterdir())) == 3


def test_pull_over_http(client, studio_env):
    mb = studio_env["moodboards"]
    mbid = _board(mb, n=2)
    pid = client.post("/api/projects", json={"name": "HttpCamp"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/mood/pull/{mbid}")
    assert r.status_code == 200 and r.json()["selected"] == 2
    assert client.post(f"/api/projects/{pid}/mood/pull/nope").status_code == 404
    assert client.post(f"/api/projects/nope/mood/pull/{mbid}").status_code == 404


# ---------- etapa 3: seletor + galeria visual + bot usa as imagens do board ----------
def test_mood_sources_lists_campaign_and_boards(client, studio_env):
    mb = studio_env["moodboards"]
    mbid = _board(mb, name="Ref Board", n=2)
    pid = client.post("/api/projects", json={"name": "Base Camp", "product": "soda"}).json()["id"]
    prepare(studio_env, pid, mood=2)   # refs + mood da campanha
    ms = client.get(f"/api/projects/{pid}/base/mood-sources").json()
    assert ms["campaign"]["count"] == 2 and len(ms["campaign"]["files"]) == 2
    assert any(b["id"] == mbid and b["count"] == 2 for b in ms["boards"])


def test_base_bot_uses_board_images_when_chosen(studio_env, monkeypatch):
    """Com um board escolhido, o bot recebe as imagens DELE, não as de mood/selected da campanha."""
    mb = studio_env["moodboards"]
    base = studio_env["svc"]("base")
    refs = studio_env["refs"]
    mbid = _board(mb, name="StyleRef", n=2)
    pid = refs.create_project("Gelo", "energetico", "snow")["id"]
    prepare(studio_env, pid, mood=2)
    calls = _fake_claude(base, monkeypatch)
    entry = base.generate_prompt(pid, mode="images", board=mbid)
    assert entry["board"] == mbid
    sent = calls[0][2]   # o texto do prompt lista os caminhos das imagens lidas pelo bot
    assert f"/{mbid}/images/" in sent, "as imagens do board vão ao bot"
    assert "mood/selected" not in sent, "o mood da campanha não é usado quando um board é escolhido"


def test_base_bot_uses_campaign_mood_by_default(studio_env, monkeypatch):
    base = studio_env["svc"]("base")
    refs = studio_env["refs"]
    pid = refs.create_project("Gelo2", "energetico", "snow")["id"]
    prepare(studio_env, pid, mood=2)
    calls = _fake_claude(base, monkeypatch)
    base.generate_prompt(pid, mode="images")   # sem board
    sent = calls[0][2]
    assert "mood/selected" in sent
