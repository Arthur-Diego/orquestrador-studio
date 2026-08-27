"""API da etapa 2 no fluxo "etapa2-pick" (ADR-014): escolher um board da biblioteca e aplicá-lo.

Cobre o novo `GET /api/projects/{pid}/mood` (mood atual — painel "Mood atual") e o `pull_board`
aplicando um board da biblioteca (`STUDIO_MOODBOARDS` isolado do conftest) → `mood/selected`
populado + `project.vibe`/`palette`. Sem rede/navegador (ADR-008).
"""
import json

from tests.conftest import image_bytes


def _board(studio_env, name="Winter", n=2, vibe="icy winter"):
    mb = studio_env["moodboards"]
    mbid = mb.create_board(name)["id"]
    for i, col in enumerate([(10, 80, 200), (200, 30, 60), (40, 160, 90)][:n]):
        mb.import_upload(mbid, [(f"g{i}.png", image_bytes(col))])
    mb.select(mbid, [c["id"] for c in mb.candidates(mbid)])
    if vibe:
        mb.patch_board(mbid, vibe=vibe)
    return mbid


# ---------- GET /api/projects/{pid}/mood (mood atual) ----------
def test_mood_status_is_empty_before_any_mood(client):
    pid = client.post("/api/projects", json={"name": "Vazia", "product": "soda"}).json()["id"]
    r = client.get(f"/api/projects/{pid}/mood")
    assert r.status_code == 200
    body = r.json()
    assert body["selected"] == [] and body["count"] == 0
    assert body["palette"] == [] and body["vibe"] == ""


def test_mood_status_404_for_unknown_project(client):
    assert client.get("/api/projects/nao-existe/mood").status_code == 404


def test_pick_a_board_and_apply_shows_in_the_current_mood(client, studio_env):
    """Escolher (via /api/moodboards) + aplicar (pull) → o mood atual expõe imagens/paleta/vibe."""
    mbid = _board(studio_env, n=2, vibe="icy winter")
    pid = client.post("/api/projects", json={"name": "Camp", "product": "soda"}).json()["id"]

    # painel 01: a grade de escolha vem de GET /api/moodboards, com capa/contagem/vibe
    boards = client.get("/api/moodboards").json()
    board = next(b for b in boards if b["id"] == mbid)
    assert board["count"] == 2 and board["cover"] and board["vibe"] == "icy winter"

    # aplicar: pull_board copia para a campanha
    r = client.post(f"/api/projects/{pid}/mood/pull/{mbid}")
    assert r.status_code == 200 and r.json()["selected"] == 2

    # painel 02: o mood atual reflete o board aplicado
    cur = client.get(f"/api/projects/{pid}/mood").json()
    assert cur["count"] == 2 and len(cur["selected"]) == 2
    assert all(s["file"] for s in cur["selected"])
    assert cur["palette"] and all(c.startswith("#") for c in cur["palette"])
    assert cur["vibe"] == "icy winter", "a vibe do board vira a vibe da campanha"


def test_apply_is_idempotent_swapping_the_mood(client, studio_env):
    """Reaplicar (Trocar) sobrescreve o mood — não acumula (pull_board idempotente)."""
    a = _board(studio_env, name="Alpha", n=3, vibe="alpha vibe")
    b = _board(studio_env, name="Beta", n=2, vibe="beta vibe")
    pid = client.post("/api/projects", json={"name": "Swap", "product": "soda"}).json()["id"]

    client.post(f"/api/projects/{pid}/mood/pull/{a}")
    assert client.get(f"/api/projects/{pid}/mood").json()["count"] == 3

    client.post(f"/api/projects/{pid}/mood/pull/{b}")
    cur = client.get(f"/api/projects/{pid}/mood").json()
    assert cur["count"] == 2 and cur["vibe"] == "beta vibe", "trocar substitui, não soma"


def test_apply_writes_palette_and_project_vibe_on_disk(client, studio_env):
    """A prova em disco: mood/selected populado + palette.json + project.vibe."""
    mbid = _board(studio_env, n=2, vibe="icy winter")
    pid = client.post("/api/projects", json={"name": "Disk", "product": "soda"}).json()["id"]
    client.post(f"/api/projects/{pid}/mood/pull/{mbid}")

    root = studio_env["refs"].project_dir(pid)
    copied = [p.name for p in (root / "mood" / "selected").iterdir() if p.is_file()]
    assert len(copied) == 2
    pal = json.loads((root / "mood" / "palette.json").read_text())
    assert pal["colors"] and pal["note"] == "icy winter"
    assert json.loads((root / "project.json").read_text())["vibe"] == "icy winter"
    assert (root / "mood" / "mood.md").exists()
