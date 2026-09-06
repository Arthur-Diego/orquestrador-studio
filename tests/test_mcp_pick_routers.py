"""As 5 tools `*_pick` do MCP contra os ROUTERS REAIS (card #93, ADH-OS-20260906-06).

Por que este arquivo existe: `tests/test_mcp_actions.py` exercita as tools contra um cliente fake,
e o fake sempre devolveu lista pura — foi assim que `base_pick` e `storyboard_pick` chegaram
quebradas em produção, porque as rotas de verdade devolvem **dict** (`{candidates, final}` e
`{ideas}`) e a `thumb` já vem prefixada com o id da etapa. Aqui o `StudioClient` fala com o
`TestClient` do FastAPI pelo `runner` injetável (`studio/mcp/client.py`), sem rede e sem navegador
(ADR-008), e cada thumb montada é buscada de verdade nos mounts `/files` e `/cfiles`.
"""
from __future__ import annotations

import json as jsonlib

import pytest

from studio.mcp import actions, ui
from studio.mcp.client import StudioClient
from tests.conftest import image_bytes


def mcp_client(tc) -> StudioClient:
    """`StudioClient` com base vazia e o `runner` apontando para o TestClient: o caminho relativo
    chega inteiro em `tc.request`, que resolve contra `http://testserver`. Sem rede.

    Mora aqui de propósito, e não em `tests/conftest.py`: o conftest é compartilhado por todas as
    frentes da wave, e um helper local não gera conflito de rebase.
    """
    return StudioClient("", runner=lambda method, url, **kw: tc.request(method, url, **kw))


def sufixo(saida: str) -> dict:
    """Parse do sufixo JSON exatamente como o consumidor (F08/F11) deve fazer: última linha não
    vazia, começando por `{"selected":`."""
    ultima = saida.strip().splitlines()[-1]
    assert ultima.startswith('{"selected":'), f"sufixo ausente ou fora do formato: {ultima!r}"
    return jsonlib.loads(ultima)


def escolhe(monkeypatch, ids: list[str]) -> dict:
    """Substitui a grade do dock (`ui.choose_images`) pela escolha do "usuário", guardando o payload
    que a UI teria recebido — é ele que carrega as URLs de thumb sob teste."""
    visto: dict = {}

    def fake(client, title, images, minimum=1, maximum=None):
        visto["images"] = images
        visto["title"] = title
        return {"answered": True, "selected": ids}

    monkeypatch.setattr(ui, "choose_images", fake)
    return visto


def thumbs_respondem_200(tc, visto: dict) -> None:
    """Critério 3 do FDD: toda thumb da grade resolve para um arquivo servido de verdade."""
    assert visto["images"], "a grade foi montada vazia"
    for img in visto["images"]:
        r = tc.get(img["thumb"])
        assert r.status_code == 200, f"thumb 404: {img['thumb']}"


@pytest.fixture()
def pid(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energetico",
                                              "vibe": "snow neon"}).json()["id"]


def semeia(studio_env, pid: str, step: str, n: int = 2) -> list[str]:
    """Candidatas reais da etapa pelo mesmo ingest que a aplicação usa (arquivo + thumb + registro).
    Base e storyboard aplicam o prefixo do step na LEITURA (`_normalize`, `_idea_row`) — a fixture
    não precisa saber disso, e é justamente esse prefixo que o bug duplicava."""
    from studio.common import ingest
    root = studio_env["refs"].project_dir(pid)
    ids = []
    for i in range(n):
        c = ingest.ingest_bytes(root, step, image_bytes(color=(10 + 40 * i, 90, 200)), "upload", f"a{i}.png",
                                prompt=f"a neon can, take {i}")
        assert c, "fixture não ingeriu a candidata"
        ids.append(c["id"])
    return ids


# ---------- 1 · refs (lista pura, thumb relativo — já funcionava) ----------
def test_refs_pick_contra_o_router(client, studio_env, pid, monkeypatch):
    from tests.conftest import make_image
    root = studio_env["refs"].project_dir(pid)
    cands = []
    for i in range(2):
        rid = f"{i}f8e7d6c5b4a"
        make_image(root / "refs" / "candidates" / f"{rid}.jpg", color=(20 * i + 10, 60, 200))
        make_image(root / "refs" / "candidates" / "thumbs" / f"{rid}.jpg", color=(20 * i + 10, 60, 200))
        cands.append({"id": rid, "source": "pinterest", "term": "energy drink", "url": "u", "pin_url": None,
                      "alt": "", "file": f"{rid}.jpg", "thumb": f"thumbs/{rid}.jpg"})
    (root / "refs" / "candidates" / "candidates.json").write_text(jsonlib.dumps(cands))

    visto = escolhe(monkeypatch, [cands[0]["id"], cands[1]["id"]])
    out = actions.refs_pick(mcp_client(client), pid)

    assert visto["images"][0]["thumb"] == f"/files/{pid}/refs/candidates/thumbs/{cands[0]['id']}.jpg"
    assert visto["images"][0]["label"] == "energy drink"
    thumbs_respondem_200(client, visto)
    assert out.splitlines()[0] == "2 imagem(ns) selecionada(s) e salva(s) na etapa refs."
    assert sufixo(out) == {"selected": [c["id"] for c in cands],
                           "next_step": client.get(f"/api/projects/{pid}/guide").json()["current"]}
    assert client.get(f"/api/projects/{pid}/refs/candidates").json()[0]["selected"] is True


# ---------- 2 · mood (lista pura, thumb relativo — já funcionava) ----------
def test_mood_pick_contra_o_router(client, studio_env, pid, monkeypatch):
    ids = semeia(studio_env, pid, "mood")
    visto = escolhe(monkeypatch, ids[:1])
    out = actions.mood_pick(mcp_client(client), pid, note="vibe fria")

    assert visto["images"][0]["thumb"] == f"/files/{pid}/mood/candidates/thumbs/{ids[0]}.jpg"
    assert visto["images"][0]["label"] == "grid_01"
    thumbs_respondem_200(client, visto)
    assert out.splitlines()[0] == "1 imagem(ns) selecionada(s) e salva(s) na etapa mood."
    assert sufixo(out)["selected"] == ids[:1]


# ---------- 3 · base (DICT `{candidates, final}` + thumb prefixado — bug do card) ----------
def test_base_pick_contra_o_router_com_dict_e_thumb_prefixado(client, studio_env, pid, monkeypatch):
    ids = semeia(studio_env, pid, "base")
    payload = client.get(f"/api/projects/{pid}/base/candidates").json()
    assert isinstance(payload, dict) and "candidates" in payload      # o shape que quebrava a tool
    assert payload["candidates"][0]["thumb"].startswith("base/")      # o prefixo que duplicava a URL

    visto = escolhe(monkeypatch, ids[:1])
    out = actions.base_pick(mcp_client(client), pid, note="a escolhida")

    thumb = visto["images"][0]["thumb"]
    assert thumb == f"/files/{pid}/base/candidates/thumbs/{ids[0]}.jpg"
    assert thumb.count("base/candidates") == 1                        # nunca duplicado
    thumbs_respondem_200(client, visto)
    assert out.splitlines()[0] == "Imagem base escolhida e salva."
    assert sufixo(out) == {"selected": ids[:1],
                           "next_step": client.get(f"/api/projects/{pid}/guide").json()["current"]}
    assert client.get(f"/api/projects/{pid}/base/candidates").json()["final"] == "base/base_final.png"


# ---------- 4 · storyboard (DICT `{ideas}` + thumb prefixado — bug encontrado na conferência) ----------
def test_storyboard_pick_contra_o_router_com_chave_ideas(client, studio_env, pid, monkeypatch):
    ids = semeia(studio_env, pid, "storyboard")
    payload = client.get(f"/api/projects/{pid}/storyboard/candidates").json()
    assert isinstance(payload, dict) and "ideas" in payload           # chave `ideas`, não `candidates`

    visto = escolhe(monkeypatch, ids)
    out = actions.storyboard_pick(mcp_client(client), pid)

    assert visto["images"][0]["thumb"] == f"/files/{pid}/storyboard/candidates/thumbs/{ids[0]}.jpg"
    assert visto["images"][0]["thumb"].count("storyboard/candidates") == 1
    assert visto["images"][0]["label"] == "a neon can, take 0"        # legenda pelo prompt da ideia
    thumbs_respondem_200(client, visto)
    assert out.splitlines()[0] == "2 imagem(ns) selecionada(s) e salva(s) na etapa storyboard."
    assert sufixo(out)["selected"] == ids
    assert all(i["selected"] for i in client.get(f"/api/projects/{pid}/storyboard/candidates").json()["ideas"])


# ---------- 5 · personagem (lista pura, mount /cfiles — já funcionava) ----------
def test_character_pick_contra_o_router(client, studio_env, monkeypatch):
    from studio.characters import service as chars
    from studio.common import ingest
    # o descritor sai do prompter (`claude -p`); mockado para False, o lock usa o fallback
    # determinístico e NENHUM binário externo é chamado (regra da retro da Wave 9).
    monkeypatch.setattr("studio.characters.service.prompter.available", lambda: False)

    cid = client.post("/api/characters", json={"name": "Eden", "style": "anime"}).json()["id"]
    c = ingest.ingest_bytes(chars._dir(cid), "explore", image_bytes(), "engine", "v0.png")
    assert c

    visto = escolhe(monkeypatch, [c["id"]])
    out = actions.character_pick(mcp_client(client), cid)

    assert visto["images"][0]["thumb"] == f"/cfiles/{cid}/explore/candidates/thumbs/{c['id']}.jpg"
    thumbs_respondem_200(client, visto)
    assert out.startswith("Personagem fixado. Descritor de identidade:\n")
    assert "consistent recurring character 'Eden'" in out
    # personagem é biblioteca global (ADR-039): fora da cadeia das 10 etapas → next_step null
    assert sufixo(out) == {"selected": [c["id"]], "next_step": None}
    assert client.get(f"/api/characters/{cid}").json()["locked_ref"].startswith("explore/candidates/")


# ---------- guarda contra regressão de shape ----------
def test_next_step_e_o_current_do_guia_do_backend(client, studio_env, pid, monkeypatch):
    """ADR-010 (a): a próxima etapa NUNCA é calculada no MCP — é cópia literal do guia."""
    ids = semeia(studio_env, pid, "mood")
    escolhe(monkeypatch, ids[:1])
    antes = client.get(f"/api/projects/{pid}/guide").json()["current"]
    out = actions.mood_pick(mcp_client(client), pid)
    assert sufixo(out)["next_step"] == antes == "refs"   # refs ainda não concluída → segue sendo a atual


def test_pick_sem_candidata_no_router_nao_estoura(client, pid, monkeypatch):
    escolhe(monkeypatch, [])
    cli = mcp_client(client)
    assert "Nenhuma candidata" in actions.base_pick(cli, pid)         # dict `{candidates: [], final: null}`
    assert "Nenhuma candidata" in actions.storyboard_pick(cli, pid)   # dict `{ideas: []}`
    assert "Nenhuma candidata" in actions.refs_pick(cli, pid)
    assert "Nenhuma candidata" in actions.mood_pick(cli, pid)


def test_pick_em_projeto_inexistente_devolve_texto_e_nao_levanta(client, monkeypatch):
    escolhe(monkeypatch, [])
    cli = mcp_client(client)
    for out in (actions.base_pick(cli, "nao-existe"), actions.storyboard_pick(cli, "nao-existe")):
        assert "Não encontrado" in out and not out.strip().endswith("}")
