"""API dos presets de realismo do prompter `[extensão]` (T2.1–T2.15).

Rotas hospedadas em `studio/creditos/router.py` (ADR-010: área campanha-independente). Nada aqui
toca o Claude CLI — o catálogo é dict em memória e a resolução de default lê `config.json`.
"""
from __future__ import annotations

import json

import pytest

CATALOG_IDS = {"documentary-street", "arri-natural-narrative", "red-commercial-precision",
               "sony-venice-night", "anamorphic-film-look"}
ITEM_KEYS = {"id", "name", "default", "desc_pt", "rig", "light", "grade", "negative"}
RIG_KEYS = {"camera", "lens", "format", "focal", "aperture"}


@pytest.fixture()
def project(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()["id"]


@pytest.fixture()
def settings_mod(studio_env):
    """`studio.common.settings` do processo recarregado pela fixture de ambiente."""
    from studio.common import settings
    return settings


def test_catalog_shape(client):
    """T2.1 — os 5 presets no shape literal da seção 5 do FDD."""
    r = client.get("/api/prompter/presets")
    assert r.status_code == 200
    presets = r.json()["presets"]
    assert len(presets) == 5
    assert {p["id"] for p in presets} == CATALOG_IDS
    for p in presets:
        assert ITEM_KEYS <= set(p) and set(p["rig"]) == RIG_KEYS
        assert isinstance(p["default"], bool) and isinstance(p["negative"], list)
    defaults = [p for p in presets if p["default"] is True]
    assert [p["id"] for p in defaults] == ["documentary-street"]
    doc = next(p for p in presets if p["id"] == "documentary-street")
    assert doc["name"] == "Documentary Street Realism"
    assert doc["rig"]["camera"] == "Blackmagic Pocket 6K Pro" and doc["rig"]["focal"] == "24-35mm"
    assert "plastic skin" in doc["negative"]


def test_catalog_defaults_are_opt_in(client):
    """T2.2 — sem override, toda ação do prompter resolve para "sem preset" vindo do código."""
    body = client.get("/api/prompter/presets").json()
    # A consumidora da wave 9 (`storyboard-roteiro-llm`, ADR-025) registra `storyboard.script` em
    # import time e é a única ação com default ATIVO (gate W3 P1) — os três papéis do prompter,
    # que são os do curso, continuam opt-in com default `None`.
    assert {"mood", "base", "motion"} <= set(body["defaults"])
    for kind in ("mood", "base", "motion"):
        assert body["defaults"][kind] == {"preset": None, "source": "code"}


def test_defaults_iterate_the_action_registry(client, settings_mod, monkeypatch):
    """T2.3 — contrato do handoff: a ação registrada pela consumidora aparece sozinha na resposta,
    sem nenhuma alteração de código de rota (amenda A1 do gate W3)."""
    monkeypatch.setitem(settings_mod.PRESET_ACTIONS, "storyboard.script", "documentary-street")
    body = client.get("/api/prompter/presets").json()
    assert body["defaults"]["storyboard.script"] == {"preset": "documentary-street", "source": "code"}
    assert body["defaults"]["mood"] == {"preset": None, "source": "code"}
    # o `setitem` mexe no VALOR de uma chave existente: o conjunto de chaves não cresce por causa
    # dele. O conjunto cresce a cada CONSUMIDORA que se registra em import time, sempre por
    # `setdefault` e sem editar `studio/common/settings.py`: a wave 9 trouxe `storyboard.script`;
    # a wave 11 trouxe `storyboard.angles` — registrada pelas DUAS frentes de forma idempotente,
    # em `studio/storyboard/angles.py` (F07, ADH-OS-20260906-09) e em
    # `studio/storyboard/service.py` (F06, FDD §5.11) — e `storyboard.keyframe` (F06).
    assert set(settings_mod.PRESET_ACTIONS) == {"mood", "base", "motion", "storyboard.script",
                                                "storyboard.angles", "storyboard.keyframe"}
    for kind in ("storyboard.angles", "storyboard.keyframe"):
        assert body["defaults"][kind] == {"preset": None, "source": "code"}


def test_pid_query_reflects_project_override(client, project):
    """T2.4 — `?pid=` resolve com o override do projeto; sem pid o global segue intocado."""
    r = client.put(f"/api/projects/{project}/prompter/preset-config",
                   json={"kind": "base", "preset": "sony-venice-night"})
    assert r.status_code == 200
    with_pid = client.get("/api/prompter/presets", params={"pid": project}).json()
    assert with_pid["defaults"]["base"] == {"preset": "sony-venice-night", "source": "project"}
    assert client.get("/api/prompter/presets").json()["defaults"]["base"] == {"preset": None, "source": "code"}


def test_pid_query_404_for_unknown_project(client):
    """T2.5."""
    assert client.get("/api/prompter/presets", params={"pid": "nao-existe"}).status_code == 404


def test_global_put_persists_in_state_config(client, studio_env):
    """T2.6 — a escolha global vira `prompter_presets` no `config.json` do STATE_DIR."""
    r = client.put("/api/prompter/preset-config", json={"kind": "mood", "preset": "arri-natural-narrative"})
    assert r.status_code == 200
    assert r.json() == {"kind": "mood", "preset": "arri-natural-narrative", "source": "global"}
    cfg = json.loads((studio_env["tmp"] / "state" / "config.json").read_text())
    assert cfg["prompter_presets"]["mood"] == "arri-natural-narrative"
    assert client.get("/api/prompter/presets").json()["defaults"]["mood"] == \
        {"preset": "arri-natural-narrative", "source": "global"}


def test_global_put_does_not_touch_model_defaults(client):
    """T2.7 — a chave `defaults` (modelos, ADR-016) fica intacta ao gravar preset."""
    assert client.put("/api/creditos/config", json={"action": "base.image", "model": "gpt_image_2"}).status_code == 200
    before = client.get("/api/creditos/config").json()
    assert client.put("/api/prompter/preset-config",
                      json={"kind": "base", "preset": "red-commercial-precision"}).status_code == 200
    assert client.get("/api/creditos/config").json() == before
    assert {a["key"]: a for a in before["defaults"]}["base.image"]["model"] == "gpt_image_2"


def test_null_preset_is_a_valid_choice(client):
    """T2.8 — `null` é "sem preset" ESCOLHIDO: encerra a cadeia com `source: global`."""
    r = client.put("/api/prompter/preset-config", json={"kind": "base", "preset": None})
    assert r.status_code == 200
    assert r.json() == {"kind": "base", "preset": None, "source": "global"}
    assert client.get("/api/prompter/presets").json()["defaults"]["base"] == {"preset": None, "source": "global"}


def test_unknown_kind_is_422(client):
    """T2.9."""
    r = client.put("/api/prompter/preset-config", json={"kind": "nao-existe", "preset": "documentary-street"})
    assert r.status_code == 422


def test_unknown_preset_is_422_listing_valid_ids(client):
    """T2.10 — a mensagem cita os ids do catálogo para a UI não adivinhar."""
    r = client.put("/api/prompter/preset-config", json={"kind": "base", "preset": "preset-que-nao-existe"})
    assert r.status_code == 422
    assert "documentary-street" in json.dumps(r.json())


def test_project_delete_clears_override(client, project):
    """T2.11."""
    client.put(f"/api/projects/{project}/prompter/preset-config",
               json={"kind": "base", "preset": "sony-venice-night"})
    r = client.delete(f"/api/projects/{project}/prompter/preset-config/base")
    assert r.status_code == 200
    assert r.json() == {"kind": "base", "preset": None, "source": "code"}
    assert client.get("/api/prompter/presets", params={"pid": project}).json()["defaults"]["base"]["source"] != "project"


def test_project_routes_404_for_unknown_project(client):
    """T2.12."""
    assert client.put("/api/projects/nao-existe/prompter/preset-config",
                      json={"kind": "base", "preset": "documentary-street"}).status_code == 404
    assert client.delete("/api/projects/nao-existe/prompter/preset-config/base").status_code == 404


def test_get_preset_config_lists_every_action(client, settings_mod, monkeypatch):
    """T2.13 — uma entrada por chave de `PRESET_ACTIONS`, no shape do bloco `defaults`."""
    monkeypatch.setitem(settings_mod.PRESET_ACTIONS, "storyboard.script", "documentary-street")
    r = client.get("/api/prompter/preset-config")
    assert r.status_code == 200
    defaults = r.json()["defaults"]
    assert set(defaults) == set(settings_mod.PRESET_ACTIONS)
    assert defaults["motion"] == {"preset": None, "source": "code"}
    assert defaults["storyboard.script"] == {"preset": "documentary-street", "source": "code"}


def test_catalog_response_is_a_copy(client, studio_env):
    """T2.14 — a rota devolve cópia: mutar a resposta não contamina `REALISM_PRESETS`."""
    from studio.common import prompter
    from studio.creditos import router as creditos_router
    body = client.get("/api/prompter/presets").json()
    body["presets"][0]["rig"]["camera"] = "CÂMERA FALSA"
    body["presets"][0]["negative"].append("lixo")
    assert prompter.REALISM_PRESETS["documentary-street"]["rig"]["camera"] == "Blackmagic Pocket 6K Pro"
    # prova em processo (o JSON do client já seria cópia por serialização)
    served = creditos_router._preset_catalog()
    served[0]["rig"]["camera"] = "CÂMERA FALSA"
    served[0]["negative"].append("lixo")
    doc = prompter.REALISM_PRESETS["documentary-street"]
    assert doc["rig"]["camera"] == "Blackmagic Pocket 6K Pro" and "lixo" not in doc["negative"]


def test_existing_creditos_routes_untouched(client, monkeypatch):
    """T2.15 — regressão: as rotas antigas do módulo seguem no mesmo shape."""
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "status", lambda refresh=False: {
        "installed": True, "logged_in": True, "plan": "pro", "credits": 1000})
    assert {a["key"] for a in client.get("/api/creditos/config").json()["defaults"]}
    models = client.get("/api/creditos/models").json()
    assert "nano_banana_2" in {m["id"] for m in models["models"]} and models["kind_label"]["image"] == "Imagem"
    d = client.get("/api/creditos").json()
    assert d["balance"]["credits"] == 1000 and len(d["actions"]) >= 7
