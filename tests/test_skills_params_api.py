"""Contrato HTTP do manifesto de parâmetros das skills `mood_`.

Complementa `tests/test_skills_params.py`, que cuida da divergência manifesto × `SKILL.md`: aqui o
alvo é o shape que o consumidor recebe (a seção "Provides" do FDD).

A auditoria do formulário gerado mora em `tests/test_skills_params_front.py`, que viaja no patch
de `docs/domains/mood/features/pendencias/` — `studio/web/*` é núcleo e pertence à frente de
preparo/shell (ADR-010). Ver §3.1 do FDD.
"""
from __future__ import annotations

from studio.moodboards import skills_params as sp

ROTA = "/api/skills/mood/params"

CHAVES_DECLARADAS = {"nome", "flag", "posicional", "tipo", "opcoes", "agregador", "default"}
CHAVES_APRESENTACAO = {"rotulo", "ajuda", "grupo", "min", "max", "obrigatorio_em_auto"}


def test_a_rota_devolve_o_manifesto(client):
    r = client.get(ROTA)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["versao"] == sp.MANIFESTO_VERSAO
    assert [s["nome"] for s in corpo["skills"]] == [s.nome for s in sp.SKILLS]


def test_a_rota_esta_no_openapi(client):
    caminhos = client.get("/openapi.json").json()["paths"]
    assert ROTA in caminhos and "get" in caminhos[ROTA]


def test_cada_param_traz_as_duas_camadas_separadas(client):
    for skill in client.get(ROTA).json()["skills"]:
        assert set(skill) == {"nome", "rotulo", "resumo", "skill_md", "params", "parametros_ignorados"}
        assert skill["params"], f"{skill['nome']} sem parâmetros"
        for p in skill["params"]:
            assert CHAVES_DECLARADAS <= set(p)
            assert set(p["apresentacao"]) == CHAVES_APRESENTACAO
            assert p["tipo"] in ("enum", "multi", "inteiro", "texto", "caminho", "lista", "booleano")
            assert p["apresentacao"]["grupo"] in ("principal", "avancado")


def test_o_manifesto_e_serializavel_e_estavel_entre_chamadas(client):
    assert client.get(ROTA).json() == client.get(ROTA).json()


def test_a_vibe_scout_nao_tem_gate_e_o_n_dela_nao_tem_teto(client):
    scout = next(s for s in client.get(ROTA).json()["skills"] if s["nome"] == "mood_vibe_scout")
    assert not [p for p in scout["params"] if p["nome"] == "gate"]
    n = next(p for p in scout["params"] if p["nome"] == "n")
    assert n["default"] == 3 and n["apresentacao"]["max"] is None


def test_a_board_builder_nao_inventa_defaults_que_o_skill_md_nao_declara(client):
    builder = next(s for s in client.get(ROTA).json()["skills"] if s["nome"] == "mood_board_builder")
    herdados = {p["nome"]: p["default"] for p in builder["params"] if p["nome"] in ("n", "board", "saida", "fundo")}
    assert herdados == {"n": None, "board": None, "saida": None, "fundo": None}


def test_a_visual_dna_fica_de_fora_com_motivo_registrado(client):
    corpo = client.get(ROTA).json()
    assert "mood_visual_dna" not in [s["nome"] for s in corpo["skills"]]
    fora = {f["nome"]: f["motivo"] for f in corpo["fora_do_manifesto"]}
    assert fora["mood_visual_dna"].strip()
