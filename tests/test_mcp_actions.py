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


def aprova(monkeypatch, *, token=True):
    """Stub de `confirm_cost` que aprova e emite um token REAL, como o helper faz de verdade.

    `[extensão]` wave 11 (ADR-038 §3): aprovar passou a emitir `_confirm_token`, e `_paid` só gera
    depois de consumi-lo. `token=False` simula a aprovação SEM token — o caso de recusa 3.
    """
    guardado = {}

    def _confirm(client, action, credits, model, detail="", *, breakdown=None):
        guardado["breakdown"] = breakdown
        ans = {"answered": True, "confirmed": True}
        if token:
            ans["_confirm_token"] = ui.issue_confirm_token(action, model)
        return ans

    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm_cost", _confirm)
    return guardado


def test_paid_com_ui_confirmado_gera(monkeypatch):
    aprova(monkeypatch)
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


# ---------- breakdown e `confirm_token` `[extensão]` (wave 11 · F10, ADR-016/038 §3) ----------
COST_RICO = {
    "per_prompt": [{"credits": 4}], "total": 12,
    "action": "mood.grid", "model": "nano_banana_2", "label": "Nano Banana Pro", "variant": "2k",
    "kind": "image", "unit_credits": 4, "count": 3, "source": "cli", "note": None,
    "balance": {"installed": True, "logged_in": True, "plan": "creator", "credits": 118},
}


@pytest.fixture(autouse=True)
def _limpa_tokens():
    ui._CONFIRM_TOKENS.clear()
    yield
    ui._CONFIRM_TOKENS.clear()
    ui.CONFIRM_TOKEN_REQUIRED = True


def gerou(cli) -> bool:
    return any("generate" in path for path, _ in cli.posts)


def test_paid_envia_o_breakdown_completo(monkeypatch):
    """Critério 3: com aba de chat, o gate recebe o `CostPreview` inteiro, não só o escalar."""
    visto = aprova(monkeypatch)
    cli = Fake({"/api/projects/p/mood/cost": COST_RICO})
    actions.mood_generate(cli, "p", ["x"])
    b = visto["breakdown"]
    for k in ("model", "unit_credits", "count", "total", "source", "balance"):
        assert k in b, f"breakdown sem {k}"
    assert b["label"] == "Nano Banana Pro" and b["variant"] == "2k"
    assert b["balance_after"] == 106  # 118 - 12, derivado


def test_breakdown_sem_saldo_ou_sem_total_nao_deriva_saldo_depois():
    assert "balance_after" not in actions._breakdown(
        {"total": 12, "balance": {"credits": None}}, model="m", credits=12)
    assert "balance_after" not in actions._breakdown(
        {"total": None, "balance": {"credits": 118}}, model="m", credits=None)


def test_recusa_token_ausente_nao_gera(monkeypatch):
    """Recusa 3: aprovou, mas nenhum token veio — não gera."""
    aprova(monkeypatch, token=False)
    cli = Fake({"/api/projects/p/mood/cost": COST_RICO})
    out = actions.mood_generate(cli, "p", ["x"])
    assert "Confirmação de gasto inválida" in out and not gerou(cli)


def test_recusa_token_de_outra_acao_nao_gera(monkeypatch):
    """Recusa 4: o token existe, mas é de outra ação."""
    def _confirm(client, action, credits, model, detail="", *, breakdown=None):
        return {"answered": True, "confirmed": True,
                "_confirm_token": ui.issue_confirm_token("OUTRA AÇÃO", model)}
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm_cost", _confirm)
    cli = Fake({"/api/projects/p/mood/cost": COST_RICO})
    out = actions.mood_generate(cli, "p", ["x"])
    assert "Confirmação de gasto inválida" in out and not gerou(cli)


def test_recusa_token_expirado_nao_gera(monkeypatch):
    """Recusa 5: o token nasceu válido, mas o TTL passou antes do consumo."""
    aprova(monkeypatch)
    cli = Fake({"/api/projects/p/mood/cost": COST_RICO})
    relogio_real, consumo_real = ui.time.monotonic, ui.consume_confirm_token

    def _consome(token, *, action, model):
        # o token nasceu válido; entre a emissão e o consumo o TTL passou
        monkeypatch.setattr(ui.time, "monotonic", lambda: relogio_real() + ui.CONFIRM_TTL + 1)
        return consumo_real(token, action=action, model=model)

    monkeypatch.setattr(ui, "consume_confirm_token", _consome)
    out = actions.mood_generate(cli, "p", ["x"])
    assert "Confirmação de gasto inválida" in out and not gerou(cli)


def test_recusa_token_ja_consumido_nao_gera(monkeypatch):
    """Recusa 6 + critério 5: o token do caminho feliz não serve uma segunda vez."""
    def _confirm(client, action, credits, model, detail="", *, breakdown=None):
        # o mesmo token nas duas chamadas: a segunda tem de ser recusada
        tok = _confirm.tok or ui.issue_confirm_token(action, model)
        _confirm.tok = tok
        return {"answered": True, "confirmed": True, "_confirm_token": tok}
    _confirm.tok = None
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm_cost", _confirm)

    cli = Fake({"/api/projects/p/mood/cost": COST_RICO})
    assert "Geração iniciada" in actions.mood_generate(cli, "p", ["x"])
    cli2 = Fake({"/api/projects/p/mood/cost": COST_RICO})
    out = actions.mood_generate(cli2, "p", ["x"])
    assert "Confirmação de gasto inválida" in out and not gerou(cli2)


def test_caminho_feliz_gera_uma_vez_so(monkeypatch):
    """Critério 5: exatamente um POST no gen_path."""
    aprova(monkeypatch)
    cli = Fake({"/api/projects/p/mood/cost": COST_RICO})
    actions.mood_generate(cli, "p", ["x"])
    assert len([p for p, _ in cli.posts if p.endswith("/mood/generate")]) == 1


def test_flag_desligada_volta_ao_gate_de_hoje(monkeypatch):
    """Escape hatch do risco 2: sem exigir token, aprovação basta."""
    aprova(monkeypatch, token=False)
    monkeypatch.setattr(ui, "CONFIRM_TOKEN_REQUIRED", False)
    cli = Fake({"/api/projects/p/mood/cost": COST_RICO})
    assert "Geração iniciada" in actions.mood_generate(cli, "p", ["x"]) and gerou(cli)


def test_terminal_mostra_o_breakdown_em_markdown(monkeypatch):
    """Critério 6: no terminal o único canal é texto, então as linhas vão no texto."""
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = Fake({"/api/projects/p/mood/cost": COST_RICO})
    out = actions.mood_generate(cli, "p", ["x"], confirm=False)
    assert "Nano Banana Pro · 2k" in out and "4 créditos (CLI)" in out
    assert "Quantidade: 3×" in out and "Saldo atual: 118" in out and "Saldo depois: 106" in out
    assert "confirm=true" in out and not gerou(cli)


def test_terminal_com_confirm_gera_sem_exigir_token(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = Fake({"/api/projects/p/mood/cost": COST_RICO})
    assert "Geração iniciada" in actions.mood_generate(cli, "p", ["x"], confirm=True)
    assert gerou(cli) and ui._CONFIRM_TOKENS == {}


def test_terminal_avisa_saldo_insuficiente_sem_bloquear(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    pobre = {**COST_RICO, "balance": {**COST_RICO["balance"], "credits": 5}}
    cli = Fake({"/api/projects/p/mood/cost": pobre})
    out = actions.mood_generate(cli, "p", ["x"], confirm=False)
    assert "Saldo menor que o total" in out


def test_erro_da_rota_de_custo_nao_gera_nem_emite_token(monkeypatch):
    aprova(monkeypatch)
    cli = Fake({"/api/projects/p/mood/cost": StudioApiError("409: CLI da Higgsfield ausente")})
    out = actions.mood_generate(cli, "p", ["x"])
    assert "409" in out and not gerou(cli) and ui._CONFIRM_TOKENS == {}


def test_token_nunca_aparece_no_texto_devolvido(monkeypatch):
    guardado = {}

    def _confirm(client, action, credits, model, detail="", *, breakdown=None):
        guardado["tok"] = ui.issue_confirm_token(action, model)
        return {"answered": True, "confirmed": True, "_confirm_token": guardado["tok"]}
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm_cost", _confirm)
    cli = Fake({"/api/projects/p/mood/cost": COST_RICO})
    out = actions.mood_generate(cli, "p", ["x"])
    assert guardado["tok"] not in out
    assert guardado["tok"] not in jsonlib.dumps(cli.posts)


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
# ---------- base_review `[extensão]` (F11, critérios 5-8 e 14) ----------
JOB = "/api/projects/p/base/job"
CANDS = "/api/projects/p/base/candidates"
SELECT = "/api/projects/p/base/select"


def espia(monkeypatch, resposta: dict) -> dict:
    """Substitui `ui.show` e `ui.choose_images` pelo dock: conta as chamadas e guarda os payloads.

    É assim que os critérios 5 a 7 medem "exatamente 1 `ui.show` e 1 `ui.choose_images`" sem subir
    o WebSocket do chat.
    """
    visto: dict = {"shows": [], "asks": []}

    def _show(cli, images, title=""):
        visto["shows"].append({"images": images, "title": title})
        return "ok"

    def _choose(cli, title, images, **kw):
        visto["asks"].append({"title": title, "images": images, **kw})
        return resposta

    monkeypatch.setattr(ui, "show", _show)
    monkeypatch.setattr(ui, "choose_images", _choose)
    return visto


def job_upscale(source_id="s1", state="done", **extra) -> dict:
    return {"state": state, "done": 1, "total": 1, "added": 1, "error": None, "new_candidates": [
        {"id": "n1", "kind": "upscale", "source_id": source_id,
         "thumb_url": "/files/p/base/candidates/thumbs/n1.jpg",
         "file_url": "/files/p/base/candidates/n1.png"}], **extra}


def etapa_com_origem() -> dict:
    return {"candidates": [
        {"id": "s1", "kind": "situation", "source_id": None, "selected": True,
         "file": "base/candidates/s1.png", "thumb": "base/candidates/thumbs/s1.jpg"}],
        "final": "base/base_final.png"}


def test_base_review_mostra_o_par_antes_depois_e_abre_a_grade(monkeypatch):
    """Critério 5: 1 `ui.show` com o par, 1 `ui.choose_images` com `media` e `actions`."""
    visto = espia(monkeypatch, {"answered": False})
    cli = Fake({JOB: job_upscale(), CANDS: etapa_com_origem()})
    actions.base_review(cli, "p")

    assert len(visto["shows"]) == 1 and len(visto["asks"]) == 1
    assert visto["shows"][0]["title"] == "Upscale 2x pronto"
    assert [i["role"] for i in visto["shows"][0]["images"]] == ["before", "after"]
    ask = visto["asks"][0]
    assert ask["minimum"] == 0 and ask["maximum"] == 1
    assert [i["id"] for i in ask["images"]] == ["n1"]
    assert ask["images"][0]["thumb"] == "/files/p/base/candidates/thumbs/n1.jpg"
    antes = [m for m in ask["media"] if m["role"] == "before"]
    depois = [m for m in ask["media"] if m["role"] == "after"]
    assert len(antes) == 1 and len(depois) == 1
    assert antes[0]["pair"] == "n1" and depois[0]["pair"] == "n1"
    assert antes[0]["url"] == "/files/p/base/candidates/s1.png"     # origem: sem prefixo duplicado
    assert depois[0]["url"] == "/files/p/base/candidates/n1.png"
    assert ask["actions"] == [
        {"label": "Usar como imagem base", "value": {"selected": ["n1"]}, "for": "n1"},
        {"label": "Manter a atual", "value": {"selected": [], "keep": True}}]


def test_base_review_sem_origem_mostra_so_a_imagem_nova(monkeypatch):
    """Critério 5 (origem nula): `source_id: null` não bloqueia a escolha, só omite o par (§6)."""
    visto = espia(monkeypatch, {"answered": False})
    cli = Fake({JOB: job_upscale(source_id=None), CANDS: etapa_com_origem()})
    actions.base_review(cli, "p")

    assert len(visto["shows"]) == 1
    assert visto["shows"][0]["images"] == [
        {"url": "/files/p/base/candidates/n1.png", "label": "depois (upscale 2x)", "kind": "image"}]
    ask = visto["asks"][0]
    assert [i["id"] for i in ask["images"]] == ["n1"]
    assert [m for m in ask["media"] if m.get("pair") == "n1"] == []


def test_base_review_com_origem_apagada_tambem_omite_o_par(monkeypatch):
    """§6: `source_id` apontando para candidata que sumiu do JSON degrada como origem nula."""
    visto = espia(monkeypatch, {"answered": False})
    cli = Fake({JOB: job_upscale(source_id="sumiu"), CANDS: {"candidates": [], "final": None}})
    actions.base_review(cli, "p")
    assert visto["asks"][0]["media"] == []
    assert [i["id"] for i in visto["asks"][0]["images"]] == ["n1"]


def test_base_review_seleciona_o_que_o_usuario_escolheu(monkeypatch):
    """Critério 6: exatamente 1 `POST /base/select` e o sufixo JSON de F04 na última linha."""
    espia(monkeypatch, {"answered": True, "selected": ["n1"]})
    cli = Fake({JOB: job_upscale(), CANDS: etapa_com_origem(),
                "/api/projects/p/guide": {"current": "storyboard"}})
    out = actions.base_review(cli, "p")

    assert cli.posts == [(SELECT, {"id": "n1", "note": ""})]
    assert "Imagem base atualizada" in out and "`n1`" in out and "origem `s1`" in out
    assert sufixo(out) == {"selected": ["n1"], "next_step": "storyboard"}
    assert out.splitlines()[-1] == actions._result_json(["n1"], "storyboard")


def test_base_review_repassa_a_nota_ao_select(monkeypatch):
    espia(monkeypatch, {"answered": True, "selected": ["n1"]})
    cli = Fake({JOB: job_upscale(), CANDS: etapa_com_origem()})
    actions.base_review(cli, "p", note="ficou melhor")
    assert cli.posts == [(SELECT, {"id": "n1", "note": "ficou melhor"})]


@pytest.mark.parametrize("resposta, trecho", [
    ({"answered": True, "selected": [], "keep": True}, "Mantive a imagem base atual."),
    ({"answered": True, "selected": []}, "Mantive a imagem base atual."),
    ({"answered": False}, "O usuário não escolheu (sem resposta)"),
])
def test_base_review_sem_selecao_nao_chama_select(monkeypatch, resposta, trecho):
    """Critério 7: `keep`, seleção vazia e ausência de resposta não gravam nada e não têm sufixo."""
    espia(monkeypatch, resposta)
    cli = Fake({JOB: job_upscale(), CANDS: etapa_com_origem()})
    out = actions.base_review(cli, "p")
    assert cli.posts == []
    assert trecho in out and not tem_sufixo(out)


def test_base_review_sem_interface_lista_ids_e_urls(monkeypatch):
    """Critério 7 (sem UI): degradação do terminal, mesma do `_pick` (ADR-038 §3)."""
    espia(monkeypatch, {"answered": False, "no_ui": True})
    cli = Fake({JOB: job_upscale(), CANDS: etapa_com_origem()})
    out = actions.base_review(cli, "p")
    assert cli.posts == []
    assert out.startswith("Sem interface para escolher aqui.")
    assert "n1" in out and "/files/p/base/candidates/n1.png" in out and not tem_sufixo(out)


def test_base_review_sem_nenhuma_candidata_nao_abre_ask(monkeypatch):
    """Critério 8: sem job e sem candidatas na etapa, orientação em texto e nenhum `ask`."""
    visto = espia(monkeypatch, {"answered": True, "selected": ["n1"]})
    cli = Fake({JOB: {"state": "idle", "new_candidates": []}, CANDS: {"candidates": [], "final": None}})
    out = actions.base_review(cli, "p")
    assert "Nenhuma candidata nova na etapa 3" in out
    assert visto["asks"] == [] and cli.posts == []


def test_base_review_cai_para_as_candidatas_da_etapa(monkeypatch):
    """Fallback: sem job, a grade vem de `_images_for` sobre o `kind` mais avançado sem seleção."""
    visto = espia(monkeypatch, {"answered": False})
    cli = Fake({JOB: {"state": "idle", "new_candidates": []}, CANDS: {"candidates": [
        {"id": "s1", "kind": "situation", "selected": True, "source_id": None,
         "file": "base/candidates/s1.png", "thumb": "base/candidates/thumbs/s1.jpg"},
        {"id": "u1", "kind": "upscale", "selected": False, "source_id": "s1",
         "file": "base/candidates/u1.png", "thumb": "base/candidates/thumbs/u1.jpg"}],
        "final": "base/base_final.png"}})
    actions.base_review(cli, "p")

    assert len(visto["asks"]) == 1
    assert visto["asks"][0]["images"] == [
        {"id": "u1", "thumb": "/files/p/base/candidates/thumbs/u1.jpg", "label": "upscale 2x"}]
    assert [m["url"] for m in visto["asks"][0]["media"]] == [
        "/files/p/base/candidates/s1.png", "/files/p/base/candidates/u1.png"]


def test_base_review_com_ids_filtra_a_grade_e_avisa_o_que_nao_existe(monkeypatch):
    """Fallback com `ids`: o parâmetro substitui a heurística de `kind`; id inexistente vira aviso."""
    visto = espia(monkeypatch, {"answered": False})
    cli = Fake({JOB: {"state": "idle", "new_candidates": []}, CANDS: {"candidates": [
        {"id": "s1", "kind": "situation", "selected": True, "source_id": None,
         "file": "base/candidates/s1.png", "thumb": "base/candidates/thumbs/s1.jpg"},
        {"id": "u1", "kind": "upscale", "selected": False, "source_id": "s1",
         "file": "base/candidates/u1.png", "thumb": "base/candidates/thumbs/u1.jpg"}],
        "final": "base/base_final.png"}})
    out = actions.base_review(cli, "p", ids=["u1", "x"])

    assert [i["id"] for i in visto["asks"][0]["images"]] == ["u1"]
    assert "x" in out and "Ignorei ids que não existem" in out


def test_base_review_com_ids_todos_invalidos_nao_abre_ask(monkeypatch):
    visto = espia(monkeypatch, {"answered": True, "selected": ["u1"]})
    cli = Fake({JOB: {"state": "idle", "new_candidates": []}, CANDS: {"candidates": [
        {"id": "u1", "kind": "upscale", "selected": False, "source_id": None,
         "file": "base/candidates/u1.png", "thumb": "base/candidates/thumbs/u1.jpg"}],
        "final": None}})
    out = actions.base_review(cli, "p", ids=["x"])
    assert visto["asks"] == [] and cli.posts == []
    assert "Ignorei ids que não existem" in out and "Nenhuma candidata nova na etapa 3" in out


def test_base_review_com_job_rodando_pede_job_wait(monkeypatch):
    visto = espia(monkeypatch, {"answered": True, "selected": ["n1"]})
    cli = Fake({JOB: {"state": "running", "done": 0, "total": 1, "new_candidates": []}})
    out = actions.base_review(cli, "p")
    assert out.startswith("Ainda gerando (0/1).") and "job_wait" in out
    assert visto["asks"] == [] and visto["shows"] == [] and cli.posts == []


def test_base_review_com_job_com_erro_reporta_e_segue(monkeypatch):
    """§6: `state:"error"` informa o erro e, havendo candidatas, continua para a escolha."""
    visto = espia(monkeypatch, {"answered": False})
    cli = Fake({JOB: job_upscale(state="error", error="boom"), CANDS: etapa_com_origem()})
    out = actions.base_review(cli, "p")
    assert "falhou: boom" in out
    assert len(visto["asks"]) == 1


def test_base_review_com_job_com_erro_e_sem_candidata_so_reporta(monkeypatch):
    visto = espia(monkeypatch, {"answered": False})
    cli = Fake({JOB: {"state": "error", "error": "boom", "new_candidates": []},
                CANDS: {"candidates": [], "final": None}})
    out = actions.base_review(cli, "p")
    assert "falhou: boom" in out and "Nenhuma candidata nova na etapa 3" in out
    assert visto["asks"] == []


def test_base_review_erro_de_api_no_job_vira_texto(monkeypatch):
    espia(monkeypatch, {"answered": False})
    cli = Fake({JOB: StudioApiError("404 projeto não encontrado")})
    assert actions.base_review(cli, "p") == "404 projeto não encontrado"


def test_base_review_erro_de_api_no_select_vira_texto_sem_sufixo(monkeypatch):
    espia(monkeypatch, {"answered": True, "selected": ["n1"]})
    cli = Fake({JOB: job_upscale(), CANDS: etapa_com_origem(),
                SELECT: StudioApiError("404 candidata não encontrada")})
    out = actions.base_review(cli, "p")
    assert out == "404 candidata não encontrada" and not tem_sufixo(out)


def test_base_review_nunca_chama_rota_de_custo(monkeypatch):
    """Decisão auto-aceita 7: `base_review` não gera, então não passa por `_paid` nem por `/cost`."""
    espia(monkeypatch, {"answered": True, "selected": ["n1"]})
    cli = Fake({JOB: job_upscale(), CANDS: etapa_com_origem()})
    actions.base_review(cli, "p")
    assert not any("cost" in path or "generate" in path for path, _ in cli.posts)


def test_base_review_esta_no_catalogo_curado():
    """ADR-040: a tool só existe para o agente se estiver registrada no `server.py`."""
    from pathlib import Path
    fonte = (Path(__file__).resolve().parents[1] / "studio" / "mcp" / "server.py").read_text()
    assert 'name="base_review"' in fonte
    bloco = fonte.split("ações: 3 Imagem base")[1].split("ações: 4 Storyboard")[0]
    assert 'name="base_review"' in bloco and "[extensão]" in bloco


def test_prompt_do_sistema_manda_chamar_base_review_depois_do_job_wait():
    """Critério 14: a cadeia da etapa 3 e o tópico do par antes/depois no prompt do agente."""
    from pathlib import Path
    texto = (Path(__file__).resolve().parents[1] / "studio" / "chat" / "prompts" / "sistema.md").read_text()
    etapa3 = texto.split("**Imagem base (aula 009):**")[1].split("**Storyboard")[0]
    assert etapa3.index("job_wait pid base") < etapa3.index("base_review")
    assert "antes" in etapa3 and "depois" in etapa3 and "upscale" in etapa3


# ---------- `[extensão]` Wave 11 · F06: roteiro, anexo e prompt por foto ----------
# Nenhum destes toca rede: o `StudioClient` é fingido e o `claude` nunca é invocado (quem chamaria
# o CLI é o servidor, do outro lado do HTTP). Invariante 8 do FDD: nada é escrito em `scenes.json`
# sem `ui.confirm`/`ui.choose_images` ou `confirm=true`.
P = "/api/projects/p/storyboard"


class SbFake(Fake):
    """Fake do storyboard: GET com fila por path (para polling), erros por path e PUTs gravados."""

    def __init__(self, responses=None, fila=None, erros=None):
        super().__init__(responses)
        self.fila = fila or {}
        self.erros = erros or {}
        self.puts = []

    def get(self, path, params=None):
        if path in self.fila:
            seq = self.fila[path]
            return seq.pop(0) if len(seq) > 1 else seq[0]
        return self.responses.get(path, {})

    def post(self, path, json=None, params=None):
        if path in self.erros:
            raise self.erros[path]
        self.posts.append((path, json))
        return self.responses.get(path, {})

    def put(self, path, json=None, params=None):
        if path in self.erros:
            raise self.erros[path]
        self.puts.append((path, json))
        return {"scenes": (json or {}).get("scenes", [])}


def _cena(n, text="", images=(), primary=None, photos=None):
    return {"id": f"cena{n:02d}", "n": n, "text": text, "images": list(images), "primary": primary,
            "video_desc": "", "video_prompt": "", "videos": [], "photos": photos or {}}


def _cenas(cli):
    """As cenas do ÚLTIMO PUT."""
    return cli.puts[-1][1]["scenes"]


# ---------- storyboard_script ----------
def test_script_dispara_e_manda_acompanhar():
    cli = SbFake()
    out = actions.storyboard_script(cli, "p", count=5, arc="começa na chuva",
                                    preset="documentary-street")
    assert out == ("Roteiro em geração: 5 cenas (preset documentary-street). "
                   "Acompanhe com `storyboard_script_wait`.")
    path, body = cli.posts[0]
    assert path == f"{P}/script/generate"
    assert body == {"count": 5, "instruction": "começa na chuva", "preset": "documentary-street"}


def test_script_sem_preset_omite_a_chave_para_o_servidor_resolver():
    cli = SbFake()
    actions.storyboard_script(cli, "p")
    assert "preset" not in cli.posts[0][1]


def test_script_409_sem_cli_devolve_a_mensagem_literal_do_servidor():
    msg = ("Claude CLI não encontrado no PATH: escreva as cenas manualmente (aula 010) ou "
           "instale o Claude Code")
    cli = SbFake(erros={f"{P}/script/generate": StudioApiError(msg, status=409, detail=msg)})
    assert actions.storyboard_script(cli, "p") == msg


# ---------- storyboard_script_wait ----------
def test_script_wait_running_para_done_resume_o_roteiro():
    cli = SbFake(
        responses={f"{P}/script": {"script": {
            "count": 5, "preset": "documentary-street",
            "scenes": [{"n": 1, "arc": "comeco", "shot_prompts": ["a", "b", "c"]},
                       {"n": 2, "arc": "descoberta", "shot_prompts": ["a"] * 5},
                       {"n": 3, "arc": "acao", "shot_prompts": ["a"] * 4},
                       {"n": 4, "arc": "acao", "shot_prompts": ["a"] * 3},
                       {"n": 5, "arc": "desfecho", "shot_prompts": ["a"] * 4}]}}},
        fila={f"{P}/script/job": [{"state": "running"}, {"state": "done"}]})
    out = actions.storyboard_script_wait(cli, "p", _sleep=lambda s: None)
    assert out == ("Roteiro pronto: 5 cenas (comeco, descoberta, acao, acao, desfecho), "
                   "3 a 5 fotos por cena, preset documentary-street. Aplique com "
                   "`storyboard_apply_script` (mode=empty não sobrescreve o que você escreveu).")


def test_script_wait_erro_cita_a_ultima_linha_do_log_e_diz_que_nada_foi_gravado():
    cli = SbFake(fila={f"{P}/script/job": [
        {"state": "error", "error": "boom", "log": ["começou", "roteiro falhou: timeout do CLI"]}]})
    out = actions.storyboard_script_wait(cli, "p", _sleep=lambda s: None)
    assert out == "O roteiro falhou: roteiro falhou: timeout do CLI. Nada foi gravado; peça de novo."


def test_script_wait_timeout_pede_nova_chamada():
    """O relógio entra por `_now`, não por monkeypatch de `time.monotonic`.

    Regressão da rodada de review 001 (issue_021): `actions.time` É o módulo `time` da stdlib, então
    substituir `monotonic` ali valia para o PROCESSO inteiro, apoiado num iterador de 3 itens —
    qualquer outro código que lesse o relógio na janela do teste levantava `StopIteration`."""
    marcas = iter([0.0, 1.0, 700.0])
    cli = SbFake(fila={f"{P}/script/job": [{"state": "running"}]})
    out = actions.storyboard_script_wait(cli, "p", _sleep=lambda s: None, _now=lambda: next(marcas))
    assert out == ("O roteiro ainda está rodando depois de 600 s. "
                   "Chame `storyboard_script_wait` de novo.")


def test_script_wait_nao_anuncia_roteiro_de_outra_sessao_quando_nada_rodou():
    """Job `idle` sem nunca ter passado por `running` NÃO é "roteiro pronto".

    Regressão da rodada de review 001 (issue_011): o laço caía direto no resumo e anunciava o
    `script.json` que estivesse em disco — de outra sessão, ou de antes de um 409 que o agente
    ignorou — e o agente então o aplicava às cenas. Mesmo cuidado do `tools.job_wait`."""
    cli = SbFake({f"{P}/script": {"script": {"count": 5, "preset": "documentary-street",
                                             "scenes": [{"arc": "acao", "text": "velho"}]}}},
                 fila={f"{P}/script/job": [{"state": "idle"}]})
    out = actions.storyboard_script_wait(cli, "p", _sleep=lambda s: None)
    assert "Nenhuma geração de roteiro em andamento" in out
    assert "Roteiro pronto" not in out


def test_script_wait_com_2xx_nao_json_nao_levanta_excecao_crua():
    """§6: `_call` devolve `str` para 2xx não-JSON; a tool tem de virar texto, não `AttributeError`."""
    cli = SbFake(fila={f"{P}/script/job": ["<html>proxy</html>"]})
    assert isinstance(actions.storyboard_script_wait(cli, "p", _sleep=lambda s: None), str)


# ---------- storyboard_apply_script ----------
def _cli_apply(cenas, sugeridas=None, preset="documentary-street"):
    sugeridas = sugeridas or [{"n": i + 1, "arc": "acao", "text": f"texto {i + 1}",
                               "image_prompt": f"prompt {i + 1}",
                               "shot_prompts": [f"prompt {i + 1}"]} for i in range(len(cenas))]
    return SbFake({f"{P}/scenes": {"scenes": cenas},
                   f"{P}/script": {"script": {"count": len(sugeridas), "preset": preset,
                                              "scenes": sugeridas}}})


def test_apply_sem_chat_e_sem_confirm_nao_escreve(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = _cli_apply([_cena(1), _cena(2)])
    out = actions.storyboard_apply_script(cli, "p")
    assert "confirm=true" in out and "Nada foi escrito" in out
    assert cli.puts == []


def test_apply_com_ui_recusada_nao_escreve(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: {"answered": True, "confirmed": False})
    cli = _cli_apply([_cena(1), _cena(2)])
    out = actions.storyboard_apply_script(cli, "p")
    assert out == "Aplicação cancelada pelo usuário. Nada foi escrito em scenes.json."
    assert cli.puts == []


def test_apply_empty_so_preenche_as_cenas_sem_texto(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: {"answered": True, "confirmed": True})
    cli = _cli_apply([_cena(1, "escrito à mão"), _cena(2), _cena(3)])
    out = actions.storyboard_apply_script(cli, "p")
    assert "2 cena(s) preenchida(s)" in out and "mode=empty" in out
    assert "1 sugestão(ões) sobraram" in out
    textos = [s["text"] for s in _cenas(cli)]
    assert textos == ["escrito à mão", "texto 2", "texto 3"]


def test_apply_replace_sobrescreve_todas(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: {"answered": True, "confirmed": True})
    cli = _cli_apply([_cena(1, "escrito à mão"), _cena(2)])
    out = actions.storyboard_apply_script(cli, "p", mode="replace")
    assert "2 cena(s) preenchida(s)" in out and "mode=replace" in out
    assert [s["text"] for s in _cenas(cli)] == ["texto 1", "texto 2"]


def test_apply_mode_invalido_nao_escreve():
    cli = _cli_apply([_cena(1)])
    out = actions.storyboard_apply_script(cli, "p", mode="lixo")
    assert "mode inválido" in out and "Nada foi escrito" in out
    assert cli.puts == []


def test_apply_com_prompts_leva_shot_prompts_para_as_fotos_ja_anexadas(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: {"answered": True, "confirmed": True})
    imgs = ["storyboard/ideas/a1.png", "storyboard/ideas/b2.png"]
    cli = _cli_apply([_cena(1, images=imgs, primary=imgs[0])],
                     sugeridas=[{"n": 1, "arc": "comeco", "text": "chove",
                                 "image_prompt": "p1", "shot_prompts": ["p1", "p2", "p3"]}])
    actions.storyboard_apply_script(cli, "p", with_prompts=True)
    photos = _cenas(cli)[0]["photos"]
    assert set(photos) == set(imgs)                     # o 3º prompt NÃO criou foto nenhuma
    assert photos[imgs[0]]["image_prompt"] == "p1" and photos[imgs[1]]["image_prompt"] == "p2"
    assert photos[imgs[0]]["origin"]["image_prompt"] == {"source": "ia",
                                                         "preset": "documentary-street"}


# ---------- storyboard_scene_attach ----------
def _ideia(i, selected=True):
    return {"id": i, "file": f"storyboard/ideas/{i}.png",
            "thumb": f"storyboard/candidates/thumbs/{i}.jpg", "prompt": f"prompt {i}",
            "selected": selected, "source": "local"}


def _cli_attach(cenas, ideias):
    return SbFake({f"{P}/scenes": {"scenes": cenas}, f"{P}/candidates": {"ideas": ideias}})


def test_attach_sem_ids_monta_o_thumb_relativo_a_raiz_do_projeto(monkeypatch):
    vistos = {}

    def _choose(client, title, images, minimum=1, maximum=None):
        vistos["title"], vistos["images"] = title, images
        return {"answered": True, "selected": ["a1"]}

    monkeypatch.setattr(ui, "choose_images", _choose)
    cli = _cli_attach([_cena(1), _cena(2)], [_ideia("a1"), _ideia("b2")])
    actions.storyboard_scene_attach(cli, "p", "cena02")
    assert "cena 2" in vistos["title"]
    urls = [i["thumb"] for i in vistos["images"]]
    assert urls == ["/files/p/storyboard/candidates/thumbs/a1.jpg",
                    "/files/p/storyboard/candidates/thumbs/b2.jpg"]
    assert not any("candidates/candidates" in u for u in urls)   # não passou por `_images_for`


def test_attach_soma_a_galeria_sem_duplicar_e_devolve_a_proxima_acao(monkeypatch):
    monkeypatch.setattr(ui, "choose_images",
                        lambda *a, **k: {"answered": True, "selected": ["a1", "b2", "c3"]})
    ja = "storyboard/ideas/a1.png"
    cli = _cli_attach([_cena(1, images=[ja], primary=ja)],
                      [_ideia("a1"), _ideia("b2"), _ideia("c3")])
    out = actions.storyboard_scene_attach(cli, "p", "cena01")
    assert out == ("2 foto(s) anexada(s) à cena01 (agora com 3). Próxima ação: "
                   "`storyboard_keyframe_prompt` para escrever o prompt de imagem de cada foto, "
                   "ou `storyboard_scenes` para revisar.")
    assert _cenas(cli)[0]["images"] == [ja, "storyboard/ideas/b2.png", "storyboard/ideas/c3.png"]


def test_attach_define_primary_so_quando_a_cena_nao_tinha(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)                # caminho de terminal
    cli = _cli_attach([_cena(1)], [_ideia("a1"), _ideia("b2")])
    actions.storyboard_scene_attach(cli, "p", "cena01", ids=["b2", "a1"])
    # a ★ é a PRIMEIRA escolha do usuário, não a primeira da listagem de candidatas
    # (regressão da rodada de review 001, issue_019).
    assert _cenas(cli)[0]["images"] == ["storyboard/ideas/b2.png", "storyboard/ideas/a1.png"]
    assert _cenas(cli)[0]["primary"] == "storyboard/ideas/b2.png"

    ja = "storyboard/ideas/z9.png"
    cli2 = _cli_attach([_cena(1, images=[ja], primary=ja)], [_ideia("a1")])
    actions.storyboard_scene_attach(cli2, "p", "cena01", ids=["a1"])
    assert _cenas(cli2)[0]["primary"] == ja                        # preservada


def test_attach_sem_ideias_escolhidas_orienta_e_nao_escreve():
    cli = _cli_attach([_cena(1)], [_ideia("a1", selected=False)])
    out = actions.storyboard_scene_attach(cli, "p", "cena01")
    assert out == ("Nenhuma ideia escolhida ainda. Use `storyboard_pick` para o usuário escolher, "
                   "ou `storyboard_local_generate` para gerar de graça no motor local.")
    assert cli.puts == []


def test_attach_ignora_ideia_nao_escolhida_mesmo_com_id_explicito(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = _cli_attach([_cena(1)], [_ideia("a1"), _ideia("b2", selected=False)])
    actions.storyboard_scene_attach(cli, "p", "cena01", ids=["a1", "b2"])
    assert _cenas(cli)[0]["images"] == ["storyboard/ideas/a1.png"]


# ---------- storyboard_keyframe_prompt ----------
IMG = "storyboard/ideas/a1.png"


def _cli_kf(photos=None, respostas=None, erros=None):
    resp = {f"{P}/scenes": {"scenes": [_cena(1), _cena(2, images=[IMG], primary=IMG,
                                                      photos=photos or {})]}}
    resp.update(respostas or {})
    return SbFake(resp, erros=erros)


def test_keyframe_prompt_image_grava_e_marca_a_origem(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = _cli_kf(respostas={f"{P}/image-prompt": {"prompt": "A lone courier steps off the curb",
                                                   "source": "claude",
                                                   "preset": "documentary-street"}})
    out = actions.storyboard_keyframe_prompt(cli, "p", "cena02", IMG, description="na chuva")
    assert cli.posts[0] == (f"{P}/image-prompt",
                            {"scene_id": "cena02", "photo": IMG, "description": "na chuva"})
    foto = _cenas(cli)[1]["photos"][IMG]
    assert foto["image_prompt"] == "A lone courier steps off the curb"
    # `claude` é o produtor; o enum que `scenes.json` aceita é `ia`/`manual`/`template`
    # (`service.ORIGIN_SOURCES`). Antes o teste assertava "claude" sobre o payload FALSO e dava
    # sinal verde a um valor que o servidor real descartava — o critério D9 não fechava.
    assert foto["origin"]["image_prompt"] == {"source": "ia", "preset": "documentary-street"}
    assert "Prompt de imagem escrito para cena02/a1.png" in out
    assert "fonte: claude, preset documentary-street" in out and "`storyboard_keyframe_set`" in out


def test_keyframe_prompt_video_usa_a_rota_de_video(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = _cli_kf(respostas={f"{P}/video-prompt": {"prompt": "A photorealistic animation",
                                                   "source": "template", "preset": None}})
    out = actions.storyboard_keyframe_prompt(cli, "p", "cena02", IMG, kind="video")
    assert cli.posts[0] == (f"{P}/video-prompt",
                            {"scene_id": "cena02", "description": "",
                             "frames": {"mode": "single", "image": IMG}})
    assert _cenas(cli)[1]["photos"][IMG]["video_prompt"] == "A photorealistic animation"
    assert "Prompt de vídeo escrito" in out and "preset nenhum" in out


def test_keyframe_prompt_kind_invalido_nao_chama_rota_nenhuma():
    cli = _cli_kf()
    out = actions.storyboard_keyframe_prompt(cli, "p", "cena02", IMG, kind="lixo")
    assert "kind inválido" in out and "Nada foi escrito" in out
    assert cli.posts == [] and cli.puts == []


def test_keyframe_prompt_nao_sobrescreve_texto_manual_sem_chat(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = _cli_kf(photos={IMG: {"image_prompt": "escrito por mim",
                                "origin": {"image_prompt": {"source": "manual", "preset": None}}}},
                  respostas={f"{P}/image-prompt": {"prompt": "sugestão da IA",
                                                   "source": "claude", "preset": None}})
    out = actions.storyboard_keyframe_prompt(cli, "p", "cena02", IMG)
    assert cli.puts == []
    assert "NÃO foi sobrescrito" in out and "sugestão da IA" in out
    assert "`storyboard_keyframe_set`" in out


def test_keyframe_prompt_aceita_so_o_nome_do_arquivo(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    cli = _cli_kf(respostas={f"{P}/image-prompt": {"prompt": "x", "source": "template",
                                                   "preset": None}})
    actions.storyboard_keyframe_prompt(cli, "p", "cena02", "a1.png")
    assert cli.posts[0][1]["photo"] == IMG          # resolvido contra as imagens da cena
    assert IMG in _cenas(cli)[1]["photos"]


# ---------- storyboard_keyframe_set ----------
def test_keyframe_set_escreve_e_marca_manual():
    cli = _cli_kf()
    out = actions.storyboard_keyframe_set(cli, "p", "cena02", IMG, "video_prompt", "texto à mão")
    foto = _cenas(cli)[1]["photos"][IMG]
    assert foto["video_prompt"] == "texto à mão"
    assert foto["origin"]["video_prompt"] == {"source": "manual", "preset": None}
    assert "video_prompt de cena02/a1.png atualizado (manual, 11 chars)" in out


def test_keyframe_set_field_invalido_nao_escreve():
    cli = _cli_kf()
    out = actions.storyboard_keyframe_set(cli, "p", "cena02", IMG, "lixo", "x")
    assert "field inválido" in out and "Nada foi escrito" in out
    assert cli.puts == []


def test_keyframe_set_422_do_teto_volta_como_texto():
    msg = "Entrada inválida: cena02: prompt de imagem acima de 4000 caracteres"
    cli = _cli_kf(erros={f"{P}/scenes": StudioApiError(msg, status=422, detail=msg)})
    out = actions.storyboard_keyframe_set(cli, "p", "cena02", IMG, "image_prompt", "x" * 4001)
    assert out == msg


# ---------- registro no servidor MCP ----------
def test_as_seis_tools_novas_estao_registradas():
    from studio.mcp import server as mcp_server
    srv = mcp_server.build_server(SbFake())
    nomes = {t.name for t in srv._tool_manager.list_tools()}
    assert {"storyboard_script", "storyboard_script_wait", "storyboard_apply_script",
            "storyboard_scene_attach", "storyboard_keyframe_prompt",
            "storyboard_keyframe_set"} <= nomes
    assert {"storyboard_local_generate", "storyboard_pick", "storyboard_scenes"} <= nomes


# ---------- invariante 8: nenhuma escrita em scenes.json sem autorização humana ----------
# Rodada de review 001 (issues 012, 013 e 015): os testes de `scene_attach` cobriam o caminho
# feliz, mas nenhum deles falhava se o portão de autorização fosse APAGADO. Estes falham.
def test_attach_sem_ui_e_sem_ids_nao_escreve_nada(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: None)
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": False, "no_ui": True})
    cli = _cli_attach([_cena(1)], [_ideia("a1")])
    out = actions.storyboard_scene_attach(cli, "p", "cena01")
    assert cli.puts == []
    assert "Sem interface" in out and "a1" in out


def test_attach_com_usuario_sem_responder_nao_escreve_nada(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": False})
    cli = _cli_attach([_cena(1)], [_ideia("a1")])
    out = actions.storyboard_scene_attach(cli, "p", "cena01")
    assert cli.puts == [] and "não escolheu" in out


def test_attach_com_selecao_vazia_nao_escreve_nada(monkeypatch):
    monkeypatch.setattr(ui, "choose_images", lambda *a, **k: {"answered": True, "selected": []})
    cli = _cli_attach([_cena(1)], [_ideia("a1")])
    out = actions.storyboard_scene_attach(cli, "p", "cena01")
    assert cli.puts == [] and "não selecionou" in out


def test_attach_com_chat_ignora_ids_e_sempre_mostra_o_seletor(monkeypatch):
    """Invariante 8: dentro do chat, a escolha visual é do USUÁRIO (ADR-038).

    O agente já conhece os ids (de `storyboard_pick`), então aceitá-los aqui deixaria o seletor a
    um argumento de ser contornado — era o único `PUT /scenes` alcançável sem nenhuma das duas
    cláusulas da invariante 8 (rodada de review 001, issue_012)."""
    chamou = []
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "choose_images",
                        lambda *a, **k: chamou.append(1) or {"answered": False})
    cli = _cli_attach([_cena(1)], [_ideia("a1"), _ideia("b2")])
    actions.storyboard_scene_attach(cli, "p", "cena01", ids=["a1", "b2"])
    assert chamou == [1], "com chat, o seletor visual tem de aparecer mesmo com ids"
    assert cli.puts == []


def test_keyframe_prompt_com_chat_confirma_antes_de_sobrescrever_manual(monkeypatch):
    """Critério D3 no lado do agente: o ramo COM chat não tinha teste nenhum (issue_013)."""
    perguntas = []
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm",
                        lambda cli, t, d="": perguntas.append(t) or {"answered": True, "confirmed": False})
    manual = {IMG: {"image_prompt": "escrito à mão",
                    "origin": {"image_prompt": {"source": "manual", "preset": None}}}}
    cli = _cli_kf(photos=manual,
                  respostas={f"{P}/image-prompt": {"prompt": "sugestão da IA", "source": "claude",
                                                   "preset": "documentary-street"}})
    out = actions.storyboard_keyframe_prompt(cli, "p", "cena02", IMG)
    assert perguntas and "manual" in perguntas[0]
    assert cli.puts == [], "recusar a confirmação não pode escrever"
    assert "Mantido" in out and "sugestão da IA" in out


def test_keyframe_prompt_com_chat_sobrescreve_quando_o_usuario_aceita(monkeypatch):
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: {"answered": True, "confirmed": True})
    manual = {IMG: {"image_prompt": "escrito à mão",
                    "origin": {"image_prompt": {"source": "manual", "preset": None}}}}
    cli = _cli_kf(photos=manual,
                  respostas={f"{P}/image-prompt": {"prompt": "sugestão da IA", "source": "claude",
                                                   "preset": None}})
    actions.storyboard_keyframe_prompt(cli, "p", "cena02", IMG)
    foto = _cenas(cli)[1]["photos"][IMG]
    assert foto["image_prompt"] == "sugestão da IA"
    assert foto["origin"]["image_prompt"]["source"] == "ia"


def test_keyframe_prompt_regenera_sobre_origem_ia_sem_perguntar(monkeypatch):
    """Texto de origem `ia`/`template` é regeneração: não pergunta nada (§4, fluxo 4, passo 4)."""
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm", lambda *a, **k: pytest.fail("não devia perguntar"))
    antes = {IMG: {"image_prompt": "da IA", "origin": {"image_prompt": {"source": "ia", "preset": None}}}}
    cli = _cli_kf(photos=antes,
                  respostas={f"{P}/image-prompt": {"prompt": "novo", "source": "claude", "preset": None}})
    actions.storyboard_keyframe_prompt(cli, "p", "cena02", IMG)
    assert _cenas(cli)[1]["photos"][IMG]["image_prompt"] == "novo"


def test_origin_source_escrito_pelas_tools_esta_no_enum_do_servidor():
    """Guarda cruzada: o que a tool escreve tem de ser aceito por `service._photo_origin`."""
    from studio.storyboard import service as sb
    assert actions._sb_source("claude") in sb.ORIGIN_SOURCES
    assert actions._sb_source("template") in sb.ORIGIN_SOURCES
    assert actions._sb_source(None) in sb.ORIGIN_SOURCES
    for field in ("image_prompt", "video_prompt", "video_desc"):
        assert field in sb.ORIGIN_FIELDS, f"{field} é aceito por keyframe_set mas o servidor descarta"


def test_apply_script_com_prompts_preserva_o_prompt_escrito_a_mao(monkeypatch):
    """Rodada de review 001 (issue_015): o lote sobrescrevia texto autoral sem dizer nada."""
    detalhes = []
    monkeypatch.setattr(ui, "chat_id", lambda: "cid")
    monkeypatch.setattr(ui, "confirm",
                        lambda cli, t, d="": detalhes.append(d) or {"answered": True, "confirmed": True})
    a, b = "storyboard/ideas/a1.png", "storyboard/ideas/b2.png"
    cena = _cena(1, images=[a, b], primary=a, photos={
        a: {"image_prompt": "meu prompt", "origin": {"image_prompt": {"source": "manual", "preset": None}}},
        b: {"image_prompt": ""}})
    cli = _cli_apply([cena], sugeridas=[{"n": 1, "arc": "acao", "text": "t",
                                         "shot_prompts": ["do roteiro A", "do roteiro B"]}])
    actions.storyboard_apply_script(cli, "p", mode="empty", with_prompts=True)
    fotos = _cenas(cli)[0]["photos"]
    assert fotos[a]["image_prompt"] == "meu prompt", "prompt manual não pode ser sobrescrito"
    assert fotos[b]["image_prompt"] == "do roteiro B"
    assert detalhes and "escrito à mão" in detalhes[0] and "cena01/a1.png" in detalhes[0]
