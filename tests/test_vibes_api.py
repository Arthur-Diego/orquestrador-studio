"""Contrato HTTP do painel de fotos de vibe `[extensão]` (ADH-OS-20260902-03).

Cobre a matriz de erros da seção 6 do FDD `docs/domains/mood/features/painel-vibes-fdd.md`
e os asserts de tela (a tela é lida como TEXTO, padrão de `tests/test_mood_view.py`).
"""
from __future__ import annotations

import pytest

from tests.test_vibes_service import FOTOS, seed_vibes


def _ids(payload: dict) -> list[str]:
    return [i["id"] for i in payload["items"]]


def _escolher(client, ids: list[str]) -> dict:
    r = client.post("/api/vibes/select", json={"ids": ids})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- E1/E2: pasta ausente ou vazia ----------
def test_pasta_ausente_responde_200_vazio_e_diz_onde_ela_fica(client):
    r = client.get("/api/vibes")
    assert r.status_code == 200
    body = r.json()
    assert (body["total"], body["items"], body["page"], body["pages"]) == (0, [], 1, 1)
    assert body["pasta"].endswith("_vibes")
    assert body["indice"] == {"ok": False, "erro": "ausente", "campanha": ""}
    assert client.get("/api/escolhidas").json()["total"] == 0
    assert client.get("/api/vibes/facets").json() == {
        "vibes": [], "origens": [], "total": 0, "escolhidas": 0,
        "indice": {"ok": False, "erro": "ausente", "campanha": ""}, "pasta": body["pasta"]}


# ---------- D1: servido por /mbfiles, sem tocar app.py ----------
def test_as_fotos_sao_servidas_pelo_mount_que_ja_existe(client, studio_env):
    """Risco 6 do recon: `_vibes/` mora em MOODBOARDS_DIR, logo `/mbfiles` já a serve."""
    seed_vibes(studio_env)
    assert client.get("/mbfiles/_vibes/01-cyberpunk-neon-1.jpg").status_code == 200
    url = client.get("/api/vibes").json()["items"][0]["url"]
    assert client.get(url).status_code == 200, "a `url` do contrato é buscável como está"


def test_as_pastas_nao_viram_board_fantasma_na_biblioteca(client, studio_env):
    seed_vibes(studio_env)
    _escolher(client, ["01-cyberpunk-neon-1.jpg"])
    assert client.get("/api/moodboards").json() == []
    assert client.get("/api/moodboards/_vibes").status_code == 404
    assert client.get("/api/moodboards/_escolhidas").status_code == 404


# ---------- E3/E4: índice ausente ou corrompido ----------
def test_indice_ausente_lista_pelo_nome_do_arquivo(client, studio_env):
    seed_vibes(studio_env, indice=None)
    body = client.get("/api/vibes").json()
    assert body["indice"]["erro"] == "ausente" and body["total"] == len(FOTOS)
    por_id = {i["id"]: i for i in body["items"]}
    assert por_id["extra-03-brutalismo-1.jpg"]["origem"] == "sugestao"
    assert por_id["extra-03-brutalismo-1.jpg"]["origem_url"] is None


def test_indice_corrompido_nao_derruba_o_painel(client, studio_env):
    seed_vibes(studio_env, indice='{"vibes": [')
    body = client.get("/api/vibes").json()
    assert body["indice"]["ok"] is False and body["indice"]["erro"].startswith("corrompido")
    assert body["total"] == len(FOTOS)
    assert client.get("/api/vibes/facets").json()["total"] == len(FOTOS)


# ---------- E5..E9: paginação e filtros ----------
def test_pagina_cheia_traz_no_maximo_20(client, studio_env):
    fotos = [(f"01-muitas-{i:02d}.jpg", (i, i, i)) for i in range(1, 26)]
    seed_vibes(studio_env, fotos=fotos, indice=None)
    body = client.get("/api/vibes").json()
    assert len(body["items"]) == 20 and body["total"] == 25 and body["pages"] == 2
    assert len(client.get("/api/vibes?page=2").json()["items"]) == 5


def test_per_page_acima_de_20_e_clampado_nao_e_erro(client, studio_env):
    seed_vibes(studio_env)
    body = client.get("/api/vibes?per_page=100").json()
    assert body["per_page"] == 20
    assert client.get("/api/escolhidas?per_page=100").json()["per_page"] == 20


@pytest.mark.parametrize("qs", ["page=0", "page=-3", "per_page=0", "page=abc"])
def test_paginacao_invalida_e_422(client, studio_env, qs):
    seed_vibes(studio_env)
    assert client.get(f"/api/vibes?{qs}").status_code == 422
    assert client.get(f"/api/escolhidas?{qs}").status_code == 422


def test_pagina_alem_do_fim_e_200_vazio(client, studio_env):
    seed_vibes(studio_env)
    body = client.get("/api/vibes?page=99&per_page=2").json()
    assert body["items"] == [] and body["total"] == 5 and body["pages"] == 3


def test_origem_invalida_e_422_listando_as_aceitas(client, studio_env):
    seed_vibes(studio_env)
    r = client.get("/api/vibes?origem=pinterest")
    assert r.status_code == 422 and "catalogo" in r.json()["detail"]


def test_filtros_e_facets(client, studio_env):
    seed_vibes(studio_env)
    assert client.get("/api/vibes?vibe=neve-suja").json()["total"] == 2
    assert _ids(client.get("/api/vibes?origem=sugestao").json()) == ["extra-03-brutalismo-1.jpg"]
    facets = client.get("/api/vibes/facets").json()
    assert [(v["slug"], v["total"]) for v in facets["vibes"]] == \
        [("cyberpunk-neon", 2), ("neve-suja", 2), ("brutalismo", 1)]
    assert facets["escolhidas"] == 0 and facets["indice"]["campanha"] == "tênis de corrida"


# ---------- seleção ----------
def test_select_copia_dedupe_e_reporta_as_tres_listas(client, studio_env):
    seed_vibes(studio_env)
    gemea = studio_env["tmp"] / "moodboards" / "_vibes" / "extra-04-gemea-1.jpg"
    gemea.write_bytes((gemea.parent / "01-cyberpunk-neon-1.jpg").read_bytes())

    primeiro = _escolher(client, ["01-cyberpunk-neon-1.jpg"])
    assert primeiro["total_escolhidas"] == 1
    segundo = _escolher(client, ["extra-04-gemea-1.jpg", "custom-02-neve-suja-1.jpg", "01-sumiu-9.jpg"])
    assert segundo == {"copiadas": ["custom-02-neve-suja-1.jpg"],
                       "duplicadas": ["extra-04-gemea-1.jpg"],
                       "ausentes": ["01-sumiu-9.jpg"], "total_escolhidas": 2}

    assert client.get("/mbfiles/_vibes/01-cyberpunk-neon-1.jpg").status_code == 200, "D3: não moveu"
    escolhidas = client.get("/api/escolhidas").json()
    assert escolhidas["total"] == 2
    item = escolhidas["items"][0]
    assert item["origem_arquivo"] == "01-cyberpunk-neon-1.jpg"
    assert item["origem_url"] == "https://pin/1" and item["origem"] == "catalogo"
    assert client.get(item["url"]).status_code == 200
    assert item["caminho"].endswith(f"_escolhidas/{item['arquivo']}"), "caminho para o --foto (feat. 01)"
    assert {i["id"]: i["escolhida"] for i in client.get("/api/vibes").json()["items"]} \
        ["01-cyberpunk-neon-1.jpg"] is True


@pytest.mark.parametrize("ruim", ["../fora.jpg", "sub/dir.jpg", "_indice.json", "plano.json", ""])
def test_select_com_id_invalido_e_422_e_nao_copia_nada(client, studio_env, ruim):
    seed_vibes(studio_env)
    r = client.post("/api/vibes/select", json={"ids": ["01-cyberpunk-neon-1.jpg", ruim]})
    assert r.status_code == 422
    assert client.get("/api/escolhidas").json()["total"] == 0


@pytest.mark.parametrize("body", [{"ids": []}, {"ids": ["a.jpg"] * 501}, {}, {"ids": "x"}])
def test_select_com_body_invalido_e_422(client, studio_env, body):
    seed_vibes(studio_env)
    assert client.post("/api/vibes/select", json=body).status_code == 422


def test_select_sem_teto_de_escolhidas(client, studio_env):
    """D5: `MAX_SELECTED = 8` é do board (ADR-007) e não vale para a peneira."""
    fotos = [(f"01-muitas-{i:02d}.jpg", (i, i, i)) for i in range(1, 21)]
    seed_vibes(studio_env, fotos=fotos, indice=None)
    assert _escolher(client, [n for n, _ in fotos])["total_escolhidas"] == 20


# ---------- remoção ----------
def test_remover_apaga_so_a_copia(client, studio_env):
    seed_vibes(studio_env)
    _escolher(client, ["01-cyberpunk-neon-1.jpg"])
    alvo = client.get("/api/escolhidas").json()["items"][0]
    r = client.delete(f"/api/escolhidas/{alvo['id']}")
    assert r.status_code == 200 and r.json() == {"removida": alvo["id"], "total_escolhidas": 0}
    assert client.get(alvo["url"]).status_code == 404, "a cópia some"
    assert client.get("/mbfiles/_vibes/01-cyberpunk-neon-1.jpg").status_code == 200, "o original fica"


def test_remover_inexistente_e_404_com_mensagem_propria(client, studio_env):
    seed_vibes(studio_env)
    r = client.delete("/api/escolhidas/000000000000")
    assert r.status_code == 404
    assert "foto escolhida não encontrada" in r.json()["detail"], "não é o 404 de projeto"


@pytest.mark.parametrize("ruim", ["ZZZZZZZZZZZZ", "abc", "aaaaaaaaaaaaa"])
def test_remover_com_id_invalido_e_422(client, studio_env, ruim):
    assert client.delete(f"/api/escolhidas/{ruim}").status_code == 422




def test_a_etapa_2_nao_ganhou_controle_nenhum(client):
    """ADR-014 de novo, pelo lado negativo (risco 9 do recon)."""
    for path in ("/steps/mood/view.html", "/steps/mood/view.js"):
        texto = client.get(path).text
        assert "/api/vibes" not in texto and "escolhidas" not in texto
