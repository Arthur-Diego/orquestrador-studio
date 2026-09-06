"""Tools de ação do MCP (ADR-037/038): gate de custo e fluxo de escolha, com cliente fake."""

from studio.mcp import actions, ui


class Fake:
    """Cliente fake: `responses[path]` para GET/POST; grava os POSTs em `self.posts`."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.posts = []

    def get(self, path, params=None):
        return self.responses.get(path, [])

    def post(self, path, json=None, params=None):
        self.posts.append((path, json))
        return self.responses.get(path, {})


# ---------- gate de custo (paid) ----------
def test_paid_terminal_sem_confirm_mostra_custo_e_nao_gera(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = Fake({"/api/projects/p/mood/cost": {"total": 12}})
    out = actions.mood_generate(cli, "p", ["um prompt"], confirm=False)
    assert "12 créditos" in out and "confirm=true" in out
    assert not any("generate" in path for path, _ in cli.posts)  # NÃO gerou


def test_paid_terminal_com_confirm_gera(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = Fake({"/api/projects/p/mood/cost": {"total": 12}})
    out = actions.mood_generate(cli, "p", ["um prompt"], confirm=True)
    assert "Geração iniciada" in out
    assert any(path.endswith("/mood/generate") for path, _ in cli.posts)


def test_paid_com_ui_confirmado_gera(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm_cost", lambda *a, **k: {"answered": True, "confirmed": True})
    cli = Fake({"/api/projects/p/mood/cost": {"total": 5}})
    out = actions.mood_generate(cli, "p", ["x"])
    assert "Geração iniciada" in out
    assert any(path.endswith("/mood/generate") for path, _ in cli.posts)


def test_paid_com_ui_recusado_nao_gera(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm_cost", lambda *a, **k: {"answered": True, "confirmed": False})
    cli = Fake({"/api/projects/p/mood/cost": {"total": 5}})
    out = actions.mood_generate(cli, "p", ["x"])
    assert "cancelada" in out
    assert not any("generate" in path for path, _ in cli.posts)


# ---------- escolha visual (pick) ----------
def test_mood_pick_seleciona_o_que_o_usuario_escolheu(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": True, "selected": ["a"]})
    cli = Fake({"/api/projects/p/mood/candidates": [
        {"id": "a", "thumb": "thumbs/a.jpg"}, {"id": "b", "thumb": "thumbs/b.jpg"}]})
    out = actions.mood_pick(cli, "p", note="ok")
    assert "1 imagem" in out
    sel = [j for path, j in cli.posts if path.endswith("/mood/select")]
    assert sel and sel[0]["ids"] == ["a"] and sel[0]["note"] == "ok"


def test_pick_sem_candidatas(monkeypatch):
    cli = Fake({"/api/projects/p/mood/candidates": []})
    assert "Nenhuma candidata" in actions.mood_pick(cli, "p")


def test_pick_sem_ui_lista_ids(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": False, "no_ui": True})
    cli = Fake({"/api/projects/p/refs/candidates": [{"id": "z", "thumb": "thumbs/z.jpg"}]})
    out = actions.refs_pick(cli, "p")
    assert "z" in out and "Sem interface" in out


# ---------- livres ----------
def test_refs_search_exige_termos():
    assert "ao menos um termo" in actions.refs_search(Fake(), "p", [])


def test_refs_search_dispara():
    cli = Fake()
    out = actions.refs_search(cli, "p", ["energy drink"])
    assert "iniciada" in out and cli.posts[0][0].endswith("/refs/search")


def test_storyboard_local_exige_prompt():
    assert "Escreva o prompt" in actions.storyboard_local_generate(Fake(), "p", "  ")


# ---------- personagem (ADR-039) ----------
def test_character_pick_fixa_o_escolhido(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": True, "selected": ["cand1"]})
    cli = Fake({
        "/api/characters/eden/candidates": [{"id": "cand1", "thumb": "thumbs/cand1.jpg", "file": "cand1.png"}],
        "/api/characters/eden/lock": {"descriptor": "silver hair, dark coat"},
    })
    out = actions.character_pick(cli, "eden")
    assert "fixado" in out and "silver hair" in out
    assert any(p.endswith("/lock") for p, _ in cli.posts)


def test_character_prefix_injeta_no_base_prompt(monkeypatch):
    cli = Fake({
        "/api/projects/p/character": {"character": {"id": "eden", "descriptor": "silver hair"}},
        "/api/projects/p/base/prompts/generate": {"prompt": "..."},
    })
    actions.base_prompt(cli, "p", instruction="on a rooftop")
    body = [j for path, j in cli.posts if path.endswith("/base/prompts/generate")][0]
    assert "silver hair" in body["instruction"] and "rooftop" in body["instruction"]


def test_character_wait_usa_a_url_de_job_do_personagem():
    # a URL do job de personagem é /api/characters/{cid}/job (não a das etapas) — regressão do 404
    cli = Fake({"/api/characters/eden/job": {"state": "done", "mode": "explore", "added": 6, "total": 6}})
    out = actions.character_wait(cli, "eden", _sleep=lambda _s: None)
    assert "concluído" in out and "6/6" in out


def test_character_pick_avisa_quando_ainda_gerando(monkeypatch):
    cli = Fake({
        "/api/characters/eden/candidates": [],
        "/api/characters/eden/job": {"state": "running", "added": 2, "total": 6},
    })
    out = actions.character_pick(cli, "eden")
    assert "gerando" in out and "2/6" in out


def test_character_bind_soul_confirma_quando_ha_ui(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: {"answered": True, "confirmed": False})
    cli = Fake()
    out = actions.character_bind_soul(cli, "eden")
    assert "cancelado" in out and cli.posts == []  # recusou → não treina
