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


# ---------- `[extensão]` geração por cena (FDD storyboard-geracao-por-cena, contratos 6 e 7) ----------
CAND_PATH = "/api/projects/p/storyboard/angles/scenes/cena01/candidates"
COST_PATH = "/api/projects/p/storyboard/angles/scenes/cena01/cost"
GEN_PATH = "/api/projects/p/storyboard/angles/scenes/cena01/generate"
SELECT_PATH = "/api/projects/p/storyboard/angles/scenes/cena01/select"


def test_scene_generate_local_manda_a_cena_para_a_rota_local():
    """Critério 11: `engine="local"` chama a rota local COM `scene` e devolve o texto de início."""
    cli = Fake()
    out = actions.storyboard_scene_generate(cli, "p", "cena01", prompt="a lone astronaut")
    assert "cena01" in out and "LOCAL (grátis)" in out and "flux-schnell" in out
    (path, body), = [(p, j) for p, j in cli.posts if p.endswith("/local/generate")]
    assert body["scene"] == "cena01" and body["count"] == 4 and body["model"] == "flux-schnell"
    assert not any("/angles/" in p for p, _ in cli.posts)  # o caminho local não passa pelo pago


def test_scene_generate_local_injeta_a_identidade_do_personagem(monkeypatch):
    """ADR-039: o descritor reancora o prompt, como já faz `storyboard_local_generate`."""
    cli = Fake({"/api/projects/p/character": {"character": {"id": "eden", "descriptor": "silver hair"}}})
    actions.storyboard_scene_generate(cli, "p", "cena01", prompt="a lone astronaut")
    body = [j for path, j in cli.posts if path.endswith("/local/generate")][0]
    assert "silver hair" in body["prompt"] and "a lone astronaut" in body["prompt"]


def test_scene_generate_cli_sem_confirm_mostra_custo_e_nao_gera(monkeypatch):
    """Critério 11: sem interface e sem `confirm`, o gate de custo (ADR-016) barra a geração."""
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = Fake({COST_PATH: {"total": 48}})
    out = actions.storyboard_scene_generate(cli, "p", "cena01", engine="cli", prompt="x", confirm=False)
    assert "48 créditos" in out and "confirm=true" in out
    assert not any(p == GEN_PATH for p, _ in cli.posts)


def test_scene_generate_cli_com_confirm_chama_cost_e_depois_generate(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = Fake({COST_PATH: {"total": 48}})
    out = actions.storyboard_scene_generate(cli, "p", "cena01", engine="cli", prompt="x", confirm=True)
    assert "Geração iniciada (nano_banana_2)" in out and "storyboard/cena01" in out
    assert [p for p, _ in cli.posts] == [COST_PATH, GEN_PATH]
    body = dict(cli.posts)[GEN_PATH]
    assert body == {"model": "nano_banana_2", "prompts": ["x"], "count": 4, "resolution": "2k"}


def test_scene_generate_cli_sem_prompt_usa_o_builder_de_angulos(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = Fake({COST_PATH: {"total": 4},
                "/api/projects/p/storyboard/angles/scenes/cena01/prompts":
                    {"prompts": [{"label": "01", "text": "Bring me another point of view"}]}})
    actions.storyboard_scene_generate(cli, "p", "cena01", engine="cli", confirm=True)
    assert dict(cli.posts)[GEN_PATH]["prompts"] == ["Bring me another point of view"]


def test_scene_generate_engine_invalido():
    cli = Fake()
    assert actions.storyboard_scene_generate(cli, "p", "cena01", engine="midjourney") == \
        "engine inválido: midjourney (use local ou cli)."
    assert cli.posts == []


def test_scene_pick_le_o_dicionario_e_salva_a_ordem(monkeypatch):
    """Critério 12: resposta em formato de dicionário, thumbs `/files/...` e `{"shots":[{"id":…}]}`."""
    vistas = {}
    monkeypatch.setattr(ui, "choose_images",
                        lambda c, t, imgs, **k: vistas.update(imgs=imgs) or
                        {"answered": True, "selected": ["b", "a"]})
    cli = Fake({CAND_PATH: {"scene": "cena01", "base": "storyboard/cena01/base.png", "candidates": [
        {"id": "a", "thumb": "storyboard/cena01/candidates/thumbs/aaaaaaaaaaaa.jpg"},
        {"id": "b", "thumb": "storyboard/cena01/candidates/thumbs/bbbbbbbbbbbb.jpg"}]},
        SELECT_PATH: {"shots": [{"id": "shot01", "file": "storyboard/cena01/shot01_final.png"},
                                {"id": "shot02", "file": "storyboard/cena01/shot02_final.png"}]}})
    out = actions.storyboard_scene_pick(cli, "p", "cena01")
    assert vistas["imgs"][0]["thumb"] == "/files/p/storyboard/cena01/candidates/thumbs/aaaaaaaaaaaa.jpg"
    assert dict(cli.posts)[SELECT_PATH] == {"shots": [{"id": "b"}, {"id": "a"}]}  # ordem escolhida
    assert out == ("2 shot(s) escolhido(s) e ordenado(s) na cena cena01 "
                   "(shot01_final.png, shot02_final.png).")


def test_scene_pick_sem_candidatos():
    cli = Fake({CAND_PATH: {"scene": "cena01", "candidates": []}})
    out = actions.storyboard_scene_pick(cli, "p", "cena01")
    assert out.startswith("Nenhum candidato na cena cena01 ainda")
    assert cli.posts == []


def test_scene_pick_sem_interface_lista_os_ids(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": False, "no_ui": True})
    cli = Fake({CAND_PATH: {"candidates": [{"id": "z", "thumb": "storyboard/cena01/candidates/thumbs/z.jpg"}]}})
    out = actions.storyboard_scene_pick(cli, "p", "cena01")
    assert "Sem interface para escolher aqui" in out and "z" in out
    assert cli.posts == []


def test_tools_do_mcp_nunca_importam_o_servico_da_etapa():
    """Critério 13 / ADR-037: as tools são clientes HTTP — nada de `studio.storyboard.*`."""
    import ast
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[1] / "studio" / "mcp"
    for p in raiz.glob("*.py"):
        for no in ast.walk(ast.parse(p.read_text())):
            if isinstance(no, ast.Import):
                assert not any(a.name.startswith("studio.storyboard") for a in no.names), p.name
            if isinstance(no, ast.ImportFrom):
                alvo = ("." * (no.level or 0)) + (no.module or "")
                assert "storyboard" not in alvo, f"{p.name}: {alvo}"


def test_as_duas_tools_por_cena_estao_no_catalogo_curado():
    """Critério 13 / ADR-040: catálogo curado do `server.py`, com descrição em pt-BR."""
    from pathlib import Path
    fonte = (Path(__file__).resolve().parents[1] / "studio" / "mcp" / "server.py").read_text()
    for nome in ("storyboard_scene_generate", "storyboard_scene_pick"):
        assert f'name="{nome}"' in fonte
    assert "GRÁTIS" in fonte and "PAGO" in fonte
