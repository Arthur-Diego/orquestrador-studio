"""Tools de ação do MCP (ADR-037/038): gate de custo e fluxo de escolha, com cliente fake."""
import json as jsonlib

import pytest

from studio.mcp import actions, ui
from studio.mcp.client import StudioApiError


class Fake:
    """Cliente fake: `responses[path]` para GET/POST; grava os POSTs em `self.posts`.

    Um valor `Exception` em `responses` é LEVANTADO no lugar de devolvido — é assim que os testes
    simulam 4xx/5xx do guia ou do `select` sem subir a API.
    """

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.posts = []

    def get(self, path, params=None):
        r = self.responses.get(path, [])
        if isinstance(r, Exception):
            raise r
        return r

    def post(self, path, json=None, params=None):
        self.posts.append((path, json))
        r = self.responses.get(path, {})
        if isinstance(r, Exception):
            raise r
        return r


def sufixo(saida: str) -> dict:
    """Faz o parse do sufixo EXATAMENTE como a seção 5 do FDD manda o consumidor fazer."""
    ultima = saida.strip().splitlines()[-1]
    assert ultima.startswith('{"selected":'), f"sufixo ausente ou fora do formato: {ultima!r}"
    return jsonlib.loads(ultima)


def tem_sufixo(saida: str) -> bool:
    return saida.strip().splitlines()[-1].startswith('{"selected":')


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


# ---------- shape das candidatas (card #93, defeito 1) ----------
@pytest.mark.parametrize("payload, esperado", [
    ([{"id": "a"}, {"id": "b"}], [{"id": "a"}, {"id": "b"}]),
    ({"candidates": [{"id": "a"}], "final": "base/base_final.png"}, [{"id": "a"}]),   # base
    ({"ideas": [{"id": "i"}]}, [{"id": "i"}]),                                        # storyboard
    ({"items": [{"id": "x"}]}, [{"id": "x"}]),
    ({}, []),
    ({"final": None}, []),
    ({"candidates": None}, []),
    (None, []),
    ("texto", []),
    ([1, 2], []),                       # itens que não são dict são descartados
    ([{"id": "a"}, "lixo"], [{"id": "a"}]),
])
def test_candidate_rows_normaliza_todos_os_shapes_publicados(payload, esperado):
    assert actions._candidate_rows(payload) == esperado


# ---------- URL da thumb (card #93, defeito 2) ----------
@pytest.mark.parametrize("thumb, url", [
    ("base/candidates/thumbs/x.jpg", "/files/p/base/candidates/thumbs/x.jpg"),   # já prefixado
    ("thumbs/x.jpg", "/files/p/base/candidates/thumbs/x.jpg"),                   # relativo
    ("/files/p/base/candidates/thumbs/x.jpg", "/files/p/base/candidates/thumbs/x.jpg"),
    ("http://host/x.jpg", "http://host/x.jpg"),
])
def test_media_url_nao_duplica_o_prefixo_da_etapa(thumb, url):
    assert actions._media_url("/files/p", "base", thumb) == url


def test_images_for_nunca_levanta_e_pula_linha_sem_thumb():
    for ruim in (None, {}, "texto", [1, 2], {"candidates": None}, [{"id": "x"}], [{"thumb": "t.jpg"}]):
        assert actions._images_for("p", "base", ruim) == []


def test_images_for_rotulo_cai_na_cadeia_de_fallback():
    rows = [{"id": "a", "thumb": "t.jpg", "kind": "upscale"},
            {"id": "b", "thumb": "t.jpg", "term": "energy drink"},
            {"id": "c", "thumb": "t.jpg", "prompt": "x" * 200},
            {"id": "d", "thumb": "t.jpg"}]
    labels = [i["label"] for i in actions._images_for("p", "base", rows)]
    assert labels[0] == "upscale" and labels[1] == "energy drink" and labels[3] == ""
    assert len(labels[2]) == actions.LABEL_MAX and labels[2].endswith("…")


def test_base_pick_aceita_dict_e_thumb_ja_prefixado(monkeypatch):
    vistos = {}
    monkeypatch.setattr(ui, "choose_images",
                        lambda cli, t, imgs, **k: vistos.update(imgs=imgs) or {"answered": True, "selected": ["9a1b"]})
    cli = Fake({
        "/api/projects/p/base/candidates": {
            "candidates": [{"id": "9a1b", "file": "base/candidates/9a1b.png",
                            "thumb": "base/candidates/thumbs/9a1b.jpg", "kind": "upscale"}],
            "final": "base/base_final.png"},
        "/api/projects/p/guide": {"current": "storyboard"},
    })
    out = actions.base_pick(cli, "p", note="ok")
    assert vistos["imgs"] == [{"id": "9a1b", "thumb": "/files/p/base/candidates/thumbs/9a1b.jpg",
                               "label": "upscale"}]
    assert out.splitlines()[0] == "Imagem base escolhida e salva."   # texto humano preservado
    assert sufixo(out) == {"selected": ["9a1b"], "next_step": "storyboard"}
    sel = [j for path, j in cli.posts if path.endswith("/base/select")]
    assert sel and sel[0] == {"id": "9a1b", "note": "ok"}


def test_storyboard_pick_aceita_dict_com_chave_ideas(monkeypatch):
    vistos = {}
    monkeypatch.setattr(ui, "choose_images",
                        lambda cli, t, imgs, **k: vistos.update(imgs=imgs) or {"answered": True, "selected": ["i1"]})
    cli = Fake({
        "/api/projects/p/storyboard/candidates": {
            "ideas": [{"id": "i1", "file": "storyboard/candidates/i1.png",
                       "thumb": "storyboard/candidates/thumbs/i1.jpg", "prompt": "a neon can"}]},
        "/api/projects/p/guide": {"current": "storyboard"},
    })
    out = actions.storyboard_pick(cli, "p")
    assert vistos["imgs"][0]["thumb"] == "/files/p/storyboard/candidates/thumbs/i1.jpg"
    assert vistos["imgs"][0]["label"] == "a neon can"
    assert sufixo(out) == {"selected": ["i1"], "next_step": "storyboard"}


def test_pick_com_shape_desconhecido_nao_estoura_e_pede_para_gerar(monkeypatch):
    cli = Fake({"/api/projects/p/base/candidates": {"final": None}})
    assert actions.base_pick(cli, "p") == "Nenhuma candidata de base ainda — gere com `base_generate` antes."
    cli = Fake({"/api/projects/p/storyboard/candidates": {"desconhecido": [{"id": "i"}]}})
    assert "Nenhuma candidata" in actions.storyboard_pick(cli, "p")


# ---------- sufixo JSON (contrato consumido por F08 e F11) ----------
def test_sufixo_traz_selected_e_next_step_do_guia(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": True, "selected": ["a", "b"]})
    cli = Fake({"/api/projects/p/refs/candidates": [{"id": "a", "thumb": "thumbs/a.jpg"},
                                                    {"id": "b", "thumb": "thumbs/b.jpg"}],
                "/api/projects/p/guide": {"current": "mood", "progress": 0.1}})
    out = actions.refs_pick(cli, "p")
    assert out.splitlines()[0] == "2 imagem(ns) selecionada(s) e salva(s) na etapa refs."
    assert sufixo(out) == {"selected": ["a", "b"], "next_step": "mood"}


def test_next_step_e_null_quando_o_guia_falha(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": True, "selected": ["a"]})
    cli = Fake({"/api/projects/p/mood/candidates": [{"id": "a", "thumb": "thumbs/a.jpg"}],
                "/api/projects/p/guide": StudioApiError("Não encontrado: projeto", status=404)})
    out = actions.mood_pick(cli, "p")
    assert out.splitlines()[0] == "1 imagem(ns) selecionada(s) e salva(s) na etapa mood."
    assert sufixo(out) == {"selected": ["a"], "next_step": None}


def test_next_step_e_null_quando_a_campanha_acabou(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": True, "selected": ["a"]})
    cli = Fake({"/api/projects/p/mood/candidates": [{"id": "a", "thumb": "thumbs/a.jpg"}],
                "/api/projects/p/guide": {"current": None, "progress": 1.0}})
    assert sufixo(actions.mood_pick(cli, "p"))["next_step"] is None


@pytest.mark.parametrize("resposta", [
    {"answered": False, "no_ui": True},
    {"answered": False},
    {"answered": True, "selected": []},
])
def test_sem_selecao_nao_emite_sufixo(monkeypatch, resposta):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: resposta)
    cands = {"/api/projects/p/mood/candidates": [{"id": "a", "thumb": "thumbs/a.jpg"}]}
    assert not tem_sufixo(actions.mood_pick(cli := Fake(cands), "p"))
    assert not any("select" in path for path, _ in cli.posts)
    assert not tem_sufixo(actions.base_pick(Fake({"/api/projects/p/base/candidates": {"candidates": [
        {"id": "a", "thumb": "base/candidates/thumbs/a.jpg"}]}}), "p"))


def test_sem_candidata_nao_emite_sufixo():
    assert not tem_sufixo(actions.mood_pick(Fake({"/api/projects/p/mood/candidates": []}), "p"))


def test_erro_no_select_devolve_a_mensagem_e_nao_emite_sufixo(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": True, "selected": ["a"]})
    cli = Fake({"/api/projects/p/base/candidates": {"candidates": [{"id": "a", "thumb": "thumbs/a.jpg"}]},
                "/api/projects/p/base/select": StudioApiError("Entrada inválida: id desconhecido", status=422)})
    out = actions.base_pick(cli, "p")
    assert out == "Entrada inválida: id desconhecido" and not tem_sufixo(out)


def test_erro_ao_listar_candidatas_devolve_a_mensagem():
    cli = Fake({"/api/projects/p/base/candidates": StudioApiError("Não encontrado: projeto p", status=404)})
    assert actions.base_pick(cli, "p") == "Não encontrado: projeto p"


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


def test_character_pick_monta_a_url_em_cfiles_e_devolve_next_step_null(monkeypatch):
    vistos = {}
    monkeypatch.setattr(ui, "choose_images",
                        lambda cli, t, imgs, **k: vistos.update(imgs=imgs) or {"answered": True, "selected": ["cand1"]})
    cli = Fake({
        "/api/characters/eden/candidates": [{"id": "cand1", "thumb": "thumbs/cand1.jpg", "file": "cand1.png",
                                             "kind": "image", "name": "a.png"}],
        "/api/characters/eden/lock": {"descriptor": "silver hair, dark coat"},
    })
    out = actions.character_pick(cli, "eden")
    # personagem é biblioteca global (ADR-039): mount /cfiles e sem etapa seguinte
    assert vistos["imgs"] == [{"id": "cand1", "thumb": "/cfiles/eden/explore/candidates/thumbs/cand1.jpg",
                               "label": "a.png"}]
    assert out.splitlines()[:2] == ["Personagem fixado. Descritor de identidade:", "silver hair, dark coat"]
    assert sufixo(out) == {"selected": ["cand1"], "next_step": None}


def test_erro_no_lock_devolve_a_mensagem_e_nao_emite_sufixo(monkeypatch):
    # mesma regra da matriz de erros dos picks de etapa: `lock` 4xx/5xx vira texto acionável, e o
    # consumidor a jusante nunca vê `selected` de uma fixação que não foi gravada
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": True, "selected": ["c1"]})
    cli = Fake({"/api/characters/eden/candidates": [{"id": "c1", "thumb": "thumbs/c1.jpg"}],
                "/api/characters/eden/lock": StudioApiError("Não encontrado: candidato c1", status=404)})
    out = actions.character_pick(cli, "eden")
    assert out == "Não encontrado: candidato c1" and not tem_sufixo(out)


def test_character_pick_sem_selecao_nao_emite_sufixo(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": True, "selected": []})
    cli = Fake({"/api/characters/eden/candidates": [{"id": "c1", "thumb": "thumbs/c1.jpg"}]})
    out = actions.character_pick(cli, "eden")
    assert out == "O usuário não escolheu o personagem." and not tem_sufixo(out)


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
