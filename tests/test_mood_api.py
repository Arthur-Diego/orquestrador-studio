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


# ---------- `[extensão]` presets de realismo no body de generate (FDD prompter-presets §5) ----------
#: A tela da etapa 2 não gera prompt desde a ADR-014 (amenda A4 do FDD): o campo `preset` entra
#: aqui só para deixar o contrato do endpoint pronto — nada em `studio/etapas/mood/view.js` muda.
def _fake_claude(monkeypatch, sent: list[str]) -> list[str]:
    """Claude fakeado no padrão do repo: guarda o prompt enviado (`args[2]`) e devolve JSON fixo."""
    import subprocess

    from studio.common import prompter

    monkeypatch.setattr(prompter, "BIN", "/usr/bin/claude")

    def fake_run(args, capture_output, text, timeout):
        sent.append(args[2])
        payload = {"prompt": "Snowy neon mood frame. No people.", "negative": "blur",
                   "camera": "", "notes_pt": ""}
        return subprocess.CompletedProcess(args, 0, "```json\n" + json.dumps(payload) + "\n```", "")

    monkeypatch.setattr(prompter.subprocess, "run", fake_run)
    return sent


def _campanha(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energetico",
                                              "vibe": "snow neon"}).json()["id"]


def test_mood_generate_accepts_the_optional_preset(client, monkeypatch):
    """T3.8 — body antigo continua 200 com `preset: None`; preset explícito chega ao CLI."""
    pid = _campanha(client)
    sent = _fake_claude(monkeypatch, [])
    r = client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "brief"})
    assert r.status_code == 200 and r.json()["preset"] is None
    assert "REALISM PRESET" not in sent[0] and "Sony Venice 2" not in sent[0]

    r = client.post(f"/api/projects/{pid}/mood/prompts/generate",
                    json={"mode": "brief", "preset": "sony-venice-night"})
    assert r.status_code == 200 and r.json()["preset"] == "sony-venice-night"
    assert "Sony Venice 2" in sent[1]


def test_mood_generate_422_before_the_cli_and_preset_in_history(client, monkeypatch):
    """T3.9 — id desconhecido é 422 sem tocar no CLI; o registro do histórico grava o preset."""
    pid = _campanha(client)
    sent = _fake_claude(monkeypatch, [])
    bad = client.post(f"/api/projects/{pid}/mood/prompts/generate",
                      json={"mode": "brief", "preset": "nao-existe"})
    assert bad.status_code == 422 and sent == []
    assert "documentary-street" in json.dumps(bad.json(), ensure_ascii=False)

    client.post(f"/api/projects/{pid}/mood/prompts/generate",
                json={"mode": "brief", "preset": "anamorphic-film-look"})
    hist = client.get(f"/api/projects/{pid}/mood/prompts/history").json()
    assert hist[0]["preset"] == "anamorphic-film-look"


def test_mood_generate_gates_login_like_every_step(client, monkeypatch):
    """ADR-028 — gate único de login: /mood/generate agora barra o CLI deslogado com 409 (antes só
    checava o binário e deixava o job estourar no subprocess). O /cost segue SUAVE: devolve estimativa
    sem 409 de login."""
    import studio.higgsfield as hf
    pid = _campanha(client)
    body = {"prompts": ["a neon can"], "count": 1}

    monkeypatch.setattr(hf, "available", lambda: False)
    assert client.post(f"/api/projects/{pid}/mood/generate", json=body).status_code == 409

    # instalado mas DESLOGADO: generate barra com 409 (o buraco que o card apontou); cost não barra login
    monkeypatch.setattr(hf, "available", lambda: True)
    monkeypatch.setattr(hf, "status", lambda refresh=False: {"installed": True, "logged_in": False})
    g = client.post(f"/api/projects/{pid}/mood/generate", json=body)
    assert g.status_code == 409 and g.json()["installed"] is True
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": None, "raw": {}})
    assert client.post(f"/api/projects/{pid}/mood/cost", json=body).status_code == 200


def test_mood_template_only_obeys_an_explicit_preset(client):
    """T3.7 (metade do template, onde as strings do curso de fato vivem): o preset escolhido troca
    a linha `Camera:`; um default resolvido deixa o template do curso byte-idêntico."""
    from studio.common import settings
    pid = _campanha(client)
    settings.set_global_preset("mood", "documentary-street")

    plain = client.post(f"/api/projects/{pid}/mood/prompts/generate", json={"mode": "template"})
    assert plain.status_code == 200 and plain.json()["preset"] == "documentary-street"
    assert "RED Komodo 6K, 50mm lens, T2.8" in plain.json()["prompt"], "template do curso intocado"
    assert "Blackmagic Pocket 6K Pro" not in plain.json()["prompt"]

    com = client.post(f"/api/projects/{pid}/mood/prompts/generate",
                      json={"mode": "template", "preset": "red-commercial-precision"})
    assert com.status_code == 200 and "Camera: RED V-Raptor" in com.json()["prompt"]
