"""Serviço da peneira de fotos de vibe `[extensão]` (ADH-OS-20260902-03).

Fixtures de PASTA, sem rede e sem navegador (ADR-008): a saída do `mood_vibe_scout` é
reproduzida no `tmp_path` do `studio_env`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import make_image

#: Nome de arquivo no padrão do `mood_vibe_scout`: `<prefixo><NN>-<slug>-<i>.jpg`.
FOTOS = [
    ("01-cyberpunk-neon-1.jpg", (10, 20, 30)),
    ("01-cyberpunk-neon-2.jpg", (11, 21, 31)),
    ("custom-02-neve-suja-1.jpg", (12, 22, 32)),
    ("custom-02-neve-suja-2.jpg", (13, 23, 33)),
    ("extra-03-brutalismo-1.jpg", (14, 24, 34)),
]


def _indice() -> dict:
    return {
        "campanha": "tênis de corrida",
        "n_por_vibe": 2,
        "legenda_prefixo": {"": "catalogo", "custom-": "usuario", "extra-": "sugestao"},
        "vibes": [
            {"num": 1, "slug": "cyberpunk-neon", "nome": "Cyberpunk neon", "origem": "catalogo",
             "salvas": [{"arquivo": "01-cyberpunk-neon-1.jpg", "origem_url": "https://pin/1", "bytes": 1},
                        {"arquivo": "01-cyberpunk-neon-2.jpg", "origem_url": "https://pin/2", "bytes": 1}]},
            {"num": 2, "slug": "neve-suja", "nome": "Neve suja", "origem": "usuario",
             "salvas": [{"arquivo": "custom-02-neve-suja-1.jpg", "origem_url": "https://pin/3", "bytes": 1},
                        {"arquivo": "custom-02-neve-suja-2.jpg", "origem_url": "https://pin/4", "bytes": 1}]},
            {"num": 3, "slug": "brutalismo", "nome": "Brutalismo", "origem": "sugestao",
             "salvas": [{"arquivo": "extra-03-brutalismo-1.jpg", "origem_url": "https://pin/5", "bytes": 1}]},
        ],
    }


def seed_vibes(env, *, fotos=None, indice: dict | str | None = "padrao", ruido: bool = True) -> Path:
    """Monta `MOODBOARDS_DIR/_vibes/`. `indice=None` não escreve o arquivo; string crua escreve
    o texto como está (para o caso corrompido)."""
    from studio.moodboards import vibes as vb

    pasta = vb.vibes_dir()
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, cor in (fotos if fotos is not None else FOTOS):
        make_image(pasta / nome, color=cor)
    if ruido:
        # o que o vibe_scout deixa na pasta e o painel NÃO pode listar
        make_image(pasta / "_folha-contato-1.jpg", color=(9, 9, 9))
        (pasta / "_indice.md").write_text("# índice")
        (pasta / "plano.json").write_text("{}")
    if indice == "padrao":
        (pasta / vb.INDEX_FILE).write_text(json.dumps(_indice(), ensure_ascii=False))
    elif isinstance(indice, str):
        (pasta / vb.INDEX_FILE).write_text(indice)
    return pasta


@pytest.fixture()
def vb(studio_env):
    from studio.moodboards import vibes as modulo
    return modulo


# ---------- listagem, metadados e ruído ----------
def test_lista_ignora_indice_folhas_e_nao_imagens(studio_env, vb):
    seed_vibes(studio_env)
    nomes = [p.name for p in vb.photo_files()]
    assert nomes == sorted(n for n, _ in FOTOS), "só as imagens, em ordem estável de nome"
    assert not any(n.startswith("_") or n.endswith(".json") for n in nomes)


def test_metadados_vem_do_indice_e_a_origem_do_prefixo(studio_env, vb):
    seed_vibes(studio_env)
    por_id = {i["id"]: i for i in vb.list_vibes()["items"]}
    catalogo = por_id["01-cyberpunk-neon-1.jpg"]
    assert (catalogo["vibe"], catalogo["vibe_nome"], catalogo["origem"]) == \
        ("cyberpunk-neon", "Cyberpunk neon", "catalogo")
    assert catalogo["origem_url"] == "https://pin/1", "rastreabilidade do pin"
    assert catalogo["url"] == "/mbfiles/_vibes/01-cyberpunk-neon-1.jpg"
    assert por_id["custom-02-neve-suja-1.jpg"]["origem"] == "usuario"
    assert por_id["extra-03-brutalismo-1.jpg"]["origem"] == "sugestao"


def test_pastas_de_vibe_sao_invisiveis_a_biblioteca_de_boards(studio_env, vb):
    """D1/risco 6: `MBID_RE` rejeita `_` inicial e `list_boards()` pula pasta sem moodboard.json."""
    seed_vibes(studio_env)
    vb.select_photos(["01-cyberpunk-neon-1.jpg"])
    assert studio_env["moodboards"].list_boards() == []
    with pytest.raises(KeyError):
        studio_env["moodboards"].board_dir("_vibes")


# ---------- E1/E2: pasta ausente ou vazia ----------
def test_pasta_ausente_nao_quebra(studio_env, vb):
    r = vb.list_vibes()
    assert (r["total"], r["items"], r["pages"]) == (0, [], 1)
    assert r["pasta"].endswith("_vibes"), "a tela mostra onde apontar o --saida do vibe_scout"
    assert vb.facets()["total"] == 0


def test_pasta_so_com_ruido_conta_zero(studio_env, vb):
    seed_vibes(studio_env, fotos=[], indice=None)
    assert vb.list_vibes()["total"] == 0


# ---------- E3/E4: índice ausente ou corrompido ----------
def test_indice_ausente_degrada_para_o_nome_do_arquivo(studio_env, vb):
    seed_vibes(studio_env, indice=None)
    r = vb.list_vibes()
    assert r["indice"] == {"ok": False, "erro": "ausente", "campanha": ""}
    assert r["total"] == len(FOTOS), "as fotos existem no disco e continuam listáveis"
    por_id = {i["id"]: i for i in r["items"]}
    assert por_id["custom-02-neve-suja-1.jpg"]["vibe"] == "neve-suja", "slug lido do nome"
    assert por_id["custom-02-neve-suja-1.jpg"]["origem"] == "usuario", "origem lida do prefixo"
    assert por_id["custom-02-neve-suja-1.jpg"]["origem_url"] is None


@pytest.mark.parametrize("cru", ['{"vibes": [', '[]', '{"vibes": {"a": 1}}', ''])
def test_indice_corrompido_degrada_e_diz_o_motivo(studio_env, vb, cru):
    seed_vibes(studio_env, indice=cru)
    r = vb.list_vibes()
    assert r["indice"]["ok"] is False and r["indice"]["erro"].startswith("corrompido")
    assert r["total"] == len(FOTOS)


def test_indice_com_entradas_lixo_ignora_so_o_lixo(studio_env, vb):
    ruim = {"campanha": "x", "vibes": [None, 42, {"slug": "cyberpunk-neon", "nome": "Cyberpunk neon",
                                                  "salvas": [None, {"arquivo": "01-cyberpunk-neon-1.jpg"}]}]}
    seed_vibes(studio_env, indice=json.dumps(ruim))
    r = vb.list_vibes()
    assert r["indice"]["ok"] is True
    por_id = {i["id"]: i for i in r["items"]}
    assert por_id["01-cyberpunk-neon-1.jpg"]["vibe_nome"] == "Cyberpunk neon"
    assert por_id["01-cyberpunk-neon-1.jpg"]["origem_url"] is None


# ---------- E5..E9: paginação e filtros ----------
def test_per_page_acima_do_teto_e_clampado_nao_e_erro(studio_env, vb):
    seed_vibes(studio_env)
    r = vb.list_vibes(per_page=999)
    assert r["per_page"] == vb.MAX_PER_PAGE == 20


def test_paginacao_percorre_tudo_sem_repetir(studio_env, vb):
    seed_vibes(studio_env)
    vistos = []
    for page in (1, 2, 3):
        vistos += [i["id"] for i in vb.list_vibes(page=page, per_page=2)["items"]]
    assert vistos == sorted(n for n, _ in FOTOS) and len(set(vistos)) == len(FOTOS)


def test_pagina_alem_do_fim_devolve_vazio_com_total_certo(studio_env, vb):
    seed_vibes(studio_env)
    r = vb.list_vibes(page=99, per_page=2)
    assert (r["items"], r["total"], r["pages"]) == ([], 5, 3)


@pytest.mark.parametrize("kw", [{"page": 0}, {"page": -1}, {"per_page": 0}])
def test_paginacao_invalida_levanta(studio_env, vb, kw):
    seed_vibes(studio_env)
    with pytest.raises(ValueError):
        vb.list_vibes(**kw)


def test_origem_invalida_levanta_listando_as_aceitas(studio_env, vb):
    seed_vibes(studio_env)
    with pytest.raises(ValueError, match="catalogo"):
        vb.list_vibes(origem="pinterest")


def test_filtro_por_vibe_e_por_origem(studio_env, vb):
    seed_vibes(studio_env)
    assert vb.list_vibes(vibe="neve-suja")["total"] == 2
    assert vb.list_vibes(origem="sugestao")["total"] == 1
    assert vb.list_vibes(vibe="neve-suja", origem="catalogo")["total"] == 0


def test_facets_bate_com_o_indice_e_segue_a_ordem_dele(studio_env, vb):
    seed_vibes(studio_env)
    f = vb.facets()
    assert [v["slug"] for v in f["vibes"]] == ["cyberpunk-neon", "neve-suja", "brutalismo"]
    assert [v["total"] for v in f["vibes"]] == [2, 2, 1]
    assert f["origens"] == [{"origem": "catalogo", "total": 2}, {"origem": "usuario", "total": 2},
                            {"origem": "sugestao", "total": 1}]
    assert f["total"] == 5 and f["escolhidas"] == 0


# ---------- seleção: copiar, deduplicar, nunca mover ----------
def test_select_copia_sem_remover_o_original(studio_env, vb):
    seed_vibes(studio_env)
    r = vb.select_photos(["01-cyberpunk-neon-1.jpg", "custom-02-neve-suja-1.jpg"])
    assert r["copiadas"] == ["01-cyberpunk-neon-1.jpg", "custom-02-neve-suja-1.jpg"]
    assert (r["duplicadas"], r["ausentes"], r["total_escolhidas"]) == ([], [], 2)
    assert (vb.vibes_dir() / "01-cyberpunk-neon-1.jpg").is_file(), "D3: copia, nunca move"
    assert len(list(vb.chosen_dir().glob("*.jpg"))) == 2
    escolhida = vb.list_chosen()["items"][0]
    assert escolhida["origem_arquivo"] == "01-cyberpunk-neon-1.jpg"
    assert escolhida["origem_url"] == "https://pin/1" and escolhida["vibe"] == "cyberpunk-neon"
    assert escolhida["caminho"] == str(vb.chosen_dir() / escolhida["arquivo"])


def test_duplicata_por_hash_e_reportada_e_nao_duplica_arquivo(studio_env, vb):
    """A mesma foto pode vir em duas vibes com nomes diferentes — dedupe é por CONTEÚDO (D4)."""
    seed_vibes(studio_env)
    gemea = vb.vibes_dir() / "extra-04-gemea-1.jpg"
    gemea.write_bytes((vb.vibes_dir() / "01-cyberpunk-neon-1.jpg").read_bytes())
    vb.select_photos(["01-cyberpunk-neon-1.jpg"])
    r = vb.select_photos(["01-cyberpunk-neon-1.jpg", "extra-04-gemea-1.jpg", "extra-03-brutalismo-1.jpg"])
    assert r["duplicadas"] == ["01-cyberpunk-neon-1.jpg", "extra-04-gemea-1.jpg"]
    assert r["copiadas"] == ["extra-03-brutalismo-1.jpg"] and r["total_escolhidas"] == 2
    assert len(list(vb.chosen_dir().glob("*.jpg"))) == 2


def test_select_sem_teto(studio_env, vb):
    """D5: o teto de 8 é do board (ADR-007), não da peneira."""
    fotos = [(f"01-muitas-{i}.jpg", (i, i, i)) for i in range(1, 21)]
    seed_vibes(studio_env, fotos=fotos, indice=None)
    r = vb.select_photos([n for n, _ in fotos])
    assert r["total_escolhidas"] == 20 and r["duplicadas"] == []


def test_id_ausente_no_disco_volta_em_ausentes(studio_env, vb):
    seed_vibes(studio_env)
    r = vb.select_photos(["01-cyberpunk-neon-1.jpg", "01-sumiu-9.jpg"])
    assert r["ausentes"] == ["01-sumiu-9.jpg"] and r["copiadas"] == ["01-cyberpunk-neon-1.jpg"]


@pytest.mark.parametrize("ruim", ["../fora.jpg", "sub/dir.jpg", "_indice.json", "plano.json",
                                  "", "..", "a" * 200 + ".jpg"])
def test_id_invalido_rejeita_o_request_inteiro(studio_env, vb, ruim):
    seed_vibes(studio_env)
    with pytest.raises(ValueError, match="id inválido"):
        vb.select_photos(["01-cyberpunk-neon-1.jpg", ruim])
    assert not vb.chosen_dir().exists(), "nada é copiado quando um id é inválido"


@pytest.mark.parametrize("ids", [[], ["a.jpg"] * 501])
def test_lista_de_ids_fora_dos_limites(studio_env, vb, ids):
    seed_vibes(studio_env)
    with pytest.raises(ValueError):
        vb.select_photos(ids)


def test_ids_repetidos_na_mesma_chamada_entram_uma_vez(studio_env, vb):
    seed_vibes(studio_env)
    r = vb.select_photos(["01-cyberpunk-neon-1.jpg", "01-cyberpunk-neon-1.jpg"])
    assert r["copiadas"] == ["01-cyberpunk-neon-1.jpg"] and r["total_escolhidas"] == 1


def test_escolhida_marcada_na_listagem_de_vibes(studio_env, vb):
    seed_vibes(studio_env)
    vb.select_photos(["01-cyberpunk-neon-1.jpg"])
    por_id = {i["id"]: i["escolhida"] for i in vb.list_vibes()["items"]}
    assert por_id["01-cyberpunk-neon-1.jpg"] is True
    assert por_id["01-cyberpunk-neon-2.jpg"] is False


# ---------- remoção ----------
def test_remover_escolhida_nao_apaga_o_original(studio_env, vb):
    seed_vibes(studio_env)
    vb.select_photos(["01-cyberpunk-neon-1.jpg"])
    alvo = vb.list_chosen()["items"][0]
    r = vb.remove_chosen(alvo["id"])
    assert r == {"removida": alvo["id"], "total_escolhidas": 0}
    assert not (vb.chosen_dir() / alvo["arquivo"]).exists(), "a cópia some"
    assert (vb.vibes_dir() / "01-cyberpunk-neon-1.jpg").is_file(), "o original fica"


def test_remover_inexistente_levanta_keyerror(studio_env, vb):
    seed_vibes(studio_env)
    with pytest.raises(KeyError):
        vb.remove_chosen("0" * 12)


@pytest.mark.parametrize("ruim", ["", "../x", "ZZZZZZZZZZZZ", "abc", "a" * 13])
def test_remover_com_id_invalido_levanta_valueerror(studio_env, vb, ruim):
    with pytest.raises(ValueError, match="id inválido"):
        vb.remove_chosen(ruim)


# ---------- E16: estado corrompido ----------
@pytest.mark.parametrize("cru", ["{", "[]", '{"itens": 3}', '{"itens": [{"id": "../x"}]}'])
def test_estado_corrompido_vira_peneira_vazia_e_e_reconstruido(studio_env, vb, cru):
    seed_vibes(studio_env)
    vb.chosen_dir().mkdir(parents=True, exist_ok=True)
    (vb.chosen_dir() / vb.CHOSEN_STATE_FILE).write_text(cru)
    assert vb.count_chosen() == 0
    assert vb.select_photos(["01-cyberpunk-neon-1.jpg"])["total_escolhidas"] == 1
    assert json.loads((vb.chosen_dir() / vb.CHOSEN_STATE_FILE).read_text())["versao"] == 1
