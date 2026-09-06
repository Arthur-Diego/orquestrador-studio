"""Shape comum de custo `[extensão]` (ADR-016, wave 11 · F10): `CostPreview` + as 7 rotas `cost`.

Dois blocos, nesta ordem de propósito:

1. **contrato por rota** — para cada uma das 7 rotas em escopo, as chaves que ela devolve HOJE
   continuam presentes, com o mesmo tipo. Estes testes foram escritos e rodados ANTES de qualquer
   mudança nas rotas, justamente para travar o contrato atual: a adoção do `CostPreview` é
   **aditiva**, e em colisão de chave o valor LEGADO vence;
2. **construtor puro** — `pricing.cost_preview` sem I/O: colisão, total derivado, precedência de
   fonte (`cli` › `measured` › `unknown`) e idempotência.

Sem rede e sem CLI real: a ponte `studio.higgsfield` é sempre fake (ADR-008).
"""
from __future__ import annotations

import json

import pytest

from tests.conftest import image_bytes, make_image

#: Chaves que cada rota devolve HOJE, com o tipo aceito (`None` entra sempre, é o degradado).
CHAVES_DE_HOJE: dict[str, dict[str, type | tuple[type, ...]]] = {
    "mood": {"per_prompt": list, "total": (int, float)},
    "base": {"per_item": (int, float), "count": int, "total": (int, float), "raw": dict},
    "animate": {"per_take": (int, float), "total": (int, float), "credits_unknown": bool,
                "model": str, "count": int, "error": str},
    "music": {"per_track": (int, float), "total": (int, float), "raw": dict, "error": str},
    "storyboard": {"per_image": (int, float), "total": (int, float)},
    "storyboard_video": {"model": str, "per_item": (int, float), "total": (int, float)},
    "multishot": {"model": str, "count": int, "per_image": (int, float), "total": (int, float),
                  "source": str},
}

#: Chaves que o `CostPreview` acrescenta em TODA rota (C1 do FDD).
CAMPOS_DO_PREVIEW = ("action", "model", "label", "variant", "kind", "unit_credits", "count",
                     "total", "source", "balance", "note")


def confere_contrato(body: dict, rota: str) -> None:
    """Todas as chaves de hoje presentes, com o tipo de hoje (ou `None`)."""
    for chave, tipo in CHAVES_DE_HOJE[rota].items():
        assert chave in body, f"{rota}: a rota deixou de devolver {chave!r}"
        valor = body[chave]
        assert valor is None or isinstance(valor, tipo), f"{rota}.{chave} mudou de tipo: {valor!r}"
        assert not isinstance(valor, bool) or tipo is bool, f"{rota}.{chave} virou bool"


def confere_preview(body: dict, action: str) -> None:
    """As chaves do `CostPreview` foram somadas e a `action` existe no catálogo (R6)."""
    from studio.common import settings
    faltando = [c for c in CAMPOS_DO_PREVIEW if c not in body]
    assert not faltando, f"CostPreview incompleto: faltam {faltando}"
    assert body["action"] == action
    assert body["action"] in settings.ACTION_KEYS, "a feature não inventa chave de ação"
    assert isinstance(body["count"], int) and body["count"] >= 1
    assert body["source"] in ("cli", "measured", "unknown")
    assert body["balance"] is None or isinstance(body["balance"], dict)


@pytest.fixture()
def hf(studio_env, monkeypatch):
    """CLI presente e logado, mas inerte: `cost` devolve 4 créditos e nada vira subprocess."""
    import studio.higgsfield as hf_mod
    monkeypatch.setattr(hf_mod, "available", lambda: True)
    monkeypatch.setattr(hf_mod, "cost", lambda model, params: {"credits": 4, "raw": {"model": model}})
    monkeypatch.setattr(hf_mod, "status", lambda refresh=False: {
        "installed": True, "logged_in": True, "plan": "creator", "credits": 118})
    return hf_mod


@pytest.fixture()
def pid(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink",
                                              "vibe": "snow neon"}).json()["id"]


# ---------- contrato por rota (critério 1 da seção 9 do FDD) ----------
def test_contrato_mood_cost(client, hf, pid):
    body = {"prompts": ["a neon can in the snow"], "count": 1}
    r = client.post(f"/api/projects/{pid}/mood/cost", json=body)
    assert r.status_code == 200, r.text
    confere_contrato(r.json(), "mood")
    confere_preview(r.json(), "mood.grid")
    assert r.json()["per_prompt"] and r.json()["total"] == 4


def _projeto_base(client, studio_env, pid):
    """Etapa 3 pronta: referências da etapa 1 + uma situação escolhida (origem do upscale)."""
    root = studio_env["refs"].project_dir(pid)
    cands = []
    for i in range(2):
        rid = f"{i}f8e7d6c5b4a"
        make_image(root / "refs" / "brainstorming" / f"{rid}.jpg", color=(20 * i + 10, 60, 200))
        cands.append({"id": rid, "source": "pinterest", "term": "energy drink", "url": "u",
                      "pin_url": None, "alt": "", "file": f"{rid}.jpg",
                      "thumb": f"thumbs/{rid}.jpg", "selected": True})
    (root / "refs" / "candidates").mkdir(parents=True, exist_ok=True)
    (root / "refs" / "candidates" / "candidates.json").write_text(json.dumps(cands))
    make_image(root / "mood" / "selected" / "m0.jpg", color=(0, 200, 200))
    (root / "mood" / "palette.json").write_text(
        json.dumps({"colors": ["#0ff0ff", "#1a1a2e"], "note": "neon frio"}))
    client.post(f"/api/projects/{pid}/base/import/upload",
                files=[("files", ("s.png", image_bytes(), "image/png"))],
                data={"kind": "situation", "ref_id": "0f8e7d6c5b4a"})
    cid = client.get(f"/api/projects/{pid}/base/candidates").json()["candidates"][0]["id"]
    client.post(f"/api/projects/{pid}/base/select", json={"id": cid})
    return root


def test_contrato_base_cost(client, hf, studio_env, pid):
    _projeto_base(client, studio_env, pid)
    body = {"kind": "upscale", "model": "bytedance_image_upscale", "count": 1}
    r = client.post(f"/api/projects/{pid}/base/cost", json=body)
    assert r.status_code == 200, r.text
    confere_contrato(r.json(), "base")
    confere_preview(r.json(), "base.upscale")
    assert r.json()["per_item"] == 4 and r.json()["count"] == 1 and r.json()["total"] == 4


def test_contrato_base_cost_resolve_a_acao_pelo_kind(client, hf, studio_env, pid):
    """`base/cost` não tem ação fixa: a `KIND_ACTION` existente é a fonte única (R6)."""
    _projeto_base(client, studio_env, pid)
    for kind, action in (("situation", "base.image"), ("clean", "base.clean"),
                         ("upscale", "base.upscale")):
        r = client.post(f"/api/projects/{pid}/base/cost",
                        json={"kind": kind, "ref_ids": ["0f8e7d6c5b4a"], "target": "Red Bull"})
        assert r.status_code == 200, (kind, r.text)
        confere_contrato(r.json(), "base")
        confere_preview(r.json(), action)


STORYBOARD_JSON = {
    "scenes": [
        {"id": "cena01", "base": "storyboard/cena01/base.png", "shots": [
            {"id": "shot01", "file": "storyboard/cena01/shot01_final.png", "order": 1,
             "prompt": "the astronaut walks"},
        ]},
    ],
    "product_scene": None,
}


def test_contrato_animate_cost(client, hf, studio_env, pid):
    root = studio_env["refs"].project_dir(pid)
    make_image(root / "storyboard" / "cena01" / "shot01_final.png")
    (root / "storyboard" / "storyboard.json").write_text(json.dumps(STORYBOARD_JSON, ensure_ascii=False))
    body = {"scene": "cena01", "shot": "shot01", "model": "kling3_0", "count": 2}
    r = client.post(f"/api/projects/{pid}/animate/cost", json=body)
    assert r.status_code == 200, r.text
    confere_contrato(r.json(), "animate")
    confere_preview(r.json(), "animate.video")
    assert r.json()["per_take"] == 4 and r.json()["total"] == 8
    assert r.json()["model"] == "kling3_0" and r.json()["credits_unknown"] is False


def test_contrato_music_cost(client, hf, pid):
    body = {"prompt": "icy neon, strong beats", "duration": 35, "count": 3}
    r = client.post(f"/api/projects/{pid}/music/generate/cost", json=body)
    assert r.status_code == 200, r.text
    confere_contrato(r.json(), "music")
    confere_preview(r.json(), "music.track")
    assert r.json()["per_track"] == 4 and r.json()["total"] == 12


def test_contrato_storyboard_cost(client, hf, studio_env, pid):
    make_image(studio_env["refs"].project_dir(pid) / "base" / "base_final.png")
    body = {"model": "nano_banana_2", "kind": "edit", "text": "Make it smaller", "count": 4}
    r = client.post(f"/api/projects/{pid}/storyboard/cost", json=body)
    assert r.status_code == 200, r.text
    confere_contrato(r.json(), "storyboard")
    confere_preview(r.json(), "storyboard.scene")
    assert r.json()["per_image"] == 4 and r.json()["total"] == 16


@pytest.mark.parametrize("mode,action,model", [
    ("single", "storyboard.video.scene", "kling2_6"),
    ("start_end", "storyboard.video.transition", "kling3_0"),
])
def test_contrato_storyboard_video_cost(client, hf, pid, mode, action, model):
    """A ação do vídeo é a MESMA que resolve o modelo (`video_action`), nunca `storyboard.video`."""
    r = client.post(f"/api/projects/{pid}/storyboard/video/cost",
                    json={"scene_id": "cena01", "mode": mode, "duration": 5})
    assert r.status_code == 200, r.text
    confere_contrato(r.json(), "storyboard_video")
    confere_preview(r.json(), action)
    assert r.json()["model"] == model and r.json()["per_item"] == 10


def test_contrato_multishot_cost(client, hf, studio_env):
    mbid = client.post("/api/moodboards", json={"name": "Neon Snow"}).json()["id"]
    client.post(f"/api/moodboards/{mbid}/import/upload",
                files=[("files", ("vibe.png", image_bytes(), "image/png"))])
    cid = client.get(f"/api/moodboards/{mbid}/candidates").json()[0]["id"]
    r = client.post(f"/api/moodboards/{mbid}/multishot/cost", json={"source_id": cid, "count": 4})
    assert r.status_code == 200, r.text
    confere_contrato(r.json(), "multishot")
    confere_preview(r.json(), "mood.multishot")
    assert r.json()["count"] == 4 and r.json()["per_image"] == 4 and r.json()["total"] == 16
    assert r.json()["source"] == "cli"


def _rotas_do_app(app):
    """Rotas folha do app — o `include_router` desta versão do FastAPI embrulha o router incluído."""
    fila = list(app.routes)
    while fila:
        rota = fila.pop()
        incluido = getattr(rota, "original_router", None)
        if incluido is not None:
            fila.extend(incluido.routes)
        elif hasattr(rota, "path"):
            yield rota


def test_nenhuma_rota_de_custo_ganhou_response_model(studio_env):
    """Decisão 2 da seção 12 do FDD: o modelo documenta o shape, o construtor produz — nenhuma
    revalidação Pydantic entra num caminho pago (e o `schema.ts` não muda por causa desta task)."""
    alvos = {"/api/projects/{pid}/mood/cost", "/api/projects/{pid}/base/cost",
             "/api/projects/{pid}/animate/cost", "/api/projects/{pid}/music/generate/cost",
             "/api/projects/{pid}/storyboard/cost", "/api/projects/{pid}/storyboard/video/cost",
             "/api/moodboards/{mbid}/multishot/cost"}
    vistas = set()
    for rota in _rotas_do_app(studio_env["app"]):
        if rota.path in alvos:
            vistas.add(rota.path)
            assert getattr(rota, "response_model", None) is None, f"{rota.path} ganhou response_model"
    assert vistas == alvos, f"rota de custo sumiu do app: {alvos - vistas}"


# ---------- construtor puro (critério 2 da seção 9 do FDD) ----------
def test_cost_preview_o_valor_legado_vence_a_colisao():
    from studio.common import pricing
    r = pricing.cost_preview(action="a", model="nano_banana_2", count=3, unit_credits=4,
                             source="cli", legacy={"total": 99, "per_item": 33})
    assert r["total"] == 99, "chave existente é intocável: o legado vence"
    assert r["per_item"] == 33 and r["unit_credits"] == 4 and r["count"] == 3


def test_cost_preview_deriva_o_total_do_unitario():
    from studio.common import pricing
    assert pricing.cost_preview(action="a", model=None, count=3, unit_credits=4,
                                source="cli")["total"] == 12
    assert pricing.cost_preview(action="a", model=None, count=3)["total"] is None


def test_cost_preview_precedencia_da_fonte():
    """`cli` › `measured` › `unknown` — a política de fallback da seção 6 do FDD."""
    from studio.common import pricing
    vivo = pricing.cost_preview(action="a", model="nano_banana_2", variant="2k",
                                unit_credits=7, source="cli")
    assert vivo["source"] == "cli" and vivo["unit_credits"] == 7, "o vivo vence a tabela"
    medido = pricing.cost_preview(action="a", model="nano_banana_2", variant="2k", source="cli")
    assert medido["source"] == "measured" and medido["unit_credits"] == 2, "sem vivo, cai na tabela"
    nada = pricing.cost_preview(action="a", model="reframe", source="cli")
    assert nada["source"] == "unknown" and nada["unit_credits"] is None, "nunca inventa número"
    assert pricing.cost_preview(action=None, model=None)["source"] == "unknown"


def test_cost_preview_descreve_o_modelo_pelo_catalogo():
    from studio.common import pricing
    r = pricing.cost_preview(action="base.upscale", model="bytedance_image_upscale")
    assert r["label"] == "Bytedance Upscale" and r["kind"] == "upscale"
    assert r["variant"] is None, "modelo sem variação medida não reporta variação"
    v = pricing.cost_preview(action="animate.video", model="kling2_6", variant="10s")
    assert v["variant"] == "10s" and v["unit_credits"] == 20 and v["kind"] == "video"
    fora = pricing.cost_preview(action="a", model="modelo-fantasma")
    assert fora["label"] == "modelo-fantasma" and fora["kind"] is None


def test_cost_preview_e_pura(monkeypatch):
    """Sem disco e sem subprocess: duas chamadas iguais devolvem dicionários iguais."""
    import subprocess

    from studio.common import pricing
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("subprocess no custo puro"))
    kwargs = dict(action="mood.grid", model="nano_banana_2", count=2, unit_credits=3,
                  source="cli", variant="2k", balance={"credits": 10}, legacy={"per_prompt": []})
    assert pricing.cost_preview(**kwargs) == pricing.cost_preview(**kwargs)


def test_cost_preview_carrega_o_aviso_do_cli_para_o_widget():
    """`note` é o aviso do CLI: o único que as rotas em escopo carregam hoje é o `error`."""
    from studio.common import pricing
    r = pricing.cost_preview(action="music.track", model="sonilo_music",
                             legacy={"per_track": None, "error": "No workspace selected"})
    assert r["note"] == "No workspace selected" and r["error"] == "No workspace selected"
    assert pricing.cost_preview(action="music.track", model="sonilo_music",
                                legacy={"error": None})["note"] is None


def test_cost_preview_modelo_pydantic_aceita_as_chaves_legadas():
    from studio.common.pricing import CostPreview
    m = CostPreview(action="base.upscale", model="bytedance_image_upscale", unit_credits=2,
                    count=1, total=2, source="cli", per_item=2, raw={"credits": 2})
    assert m.model_dump()["per_item"] == 2, "extra=allow preserva o contrato legado da etapa"
    assert CostPreview().source == "unknown" and CostPreview().count == 1
