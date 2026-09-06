"""API da tela "Créditos & Custos" `[extensão]` (ADR-016). Sem rede: o CLI é fake (ADR-008)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


@pytest.fixture()
def stub_hf(monkeypatch):
    """Fixa o saldo e a estimativa ao vivo do CLI — os testes nunca tocam o CLI real."""
    import studio.higgsfield as hf
    monkeypatch.setattr(hf, "status", lambda refresh=False: {
        "installed": True, "logged_in": True, "plan": "pro", "credits": 1000})
    monkeypatch.setattr(hf, "cost", lambda model, params: {"credits": None})   # força fallback medido
    return hf


@pytest.fixture()
def project(client):
    return client.post("/api/projects", json={"name": "Gelo Zero", "product": "energy drink"}).json()["id"]


def test_models_catalog(client, stub_hf):
    r = client.get("/api/creditos/models")
    assert r.status_code == 200
    body = r.json()
    ids = {m["id"] for m in body["models"]}
    assert "nano_banana_2" in ids and "kling3_0" in ids
    assert body["kind_label"]["image"] == "Imagem"


def test_dashboard_and_balance(client, stub_hf):
    r = client.get("/api/creditos")
    assert r.status_code == 200
    d = r.json()
    assert d["balance"]["credits"] == 1000 and d["balance"]["logged_in"] is True
    assert len(d["actions"]) >= 7
    assert d["summary"]["count"] == 0


def test_cost_preview_uses_measured_when_cli_silent(client, stub_hf):
    r = client.get("/api/creditos/cost", params={"action": "base.image"})
    assert r.status_code == 200
    c = r.json()
    assert c["model"] == "nano_banana_2" and c["credits"] == 2 and c["source"] == "measured"
    assert c["balance"]["credits"] == 1000


def test_global_default_persists_and_screens_read_it(client, stub_hf):
    assert client.put("/api/creditos/config", json={"action": "base.image", "model": "gpt_image_2"}).status_code == 200
    cfg = {a["key"]: a for a in client.get("/api/creditos/config").json()["defaults"]}
    assert cfg["base.image"]["model"] == "gpt_image_2" and cfg["base.image"]["source"] == "global"
    # a estimativa passa a usar o modelo configurado
    assert client.get("/api/creditos/cost", params={"action": "base.image"}).json()["model"] == "gpt_image_2"


def test_project_override_beats_global(client, stub_hf, project):
    client.put("/api/creditos/config", json={"action": "storyboard.scene", "model": "gpt_image_2"})
    client.put(f"/api/projects/{project}/creditos/config",
               json={"action": "storyboard.scene", "model": "nano_banana_2", "variant": "4k"})
    r = client.get(f"/api/projects/{project}/creditos/cost", params={"action": "storyboard.scene"})
    assert r.json()["model"] == "nano_banana_2" and r.json()["variant"] == "4k"
    # remover o override do projeto volta ao global
    assert client.delete(f"/api/projects/{project}/creditos/config/storyboard.scene").status_code == 200
    assert client.get(f"/api/projects/{project}/creditos/cost", params={"action": "storyboard.scene"}).json()["model"] == "gpt_image_2"


def test_bad_action_and_model_rejected(client, stub_hf):
    assert client.put("/api/creditos/config", json={"action": "nope", "model": "nano_banana_2"}).status_code == 422
    assert client.put("/api/creditos/config", json={"action": "base.image", "model": "ghost"}).status_code == 422


def test_spend_endpoint_and_history(client, stub_hf, project):
    r = client.post("/api/creditos/spend", json={"action": "base.image", "model": "nano_banana_2",
                                                 "credits": 2, "step": "base", "pid": project, "project_name": "Gelo Zero"})
    assert r.status_code == 200
    hist = client.get("/api/creditos/history").json()
    assert hist["summary"]["total_credits"] == 2 and hist["summary"]["count"] == 1
    assert client.post("/api/creditos/spend", json={"action": "nope", "model": "x"}).status_code == 422


def test_creditos_pid_is_reserved(client, stub_hf):
    # um projeto nunca pode se chamar "creditos" (colidiria com a rota global)
    assert client.post("/api/projects", json={"name": "creditos"}).status_code == 409


def test_project_dashboard_404_for_unknown(client, stub_hf):
    assert client.get("/api/projects/naoexiste/creditos").status_code == 404


# ---------- catálogo íntegro: "quem grava usa a chave que configura" (wave 11, card #92) ----------
#
# O defeito corrigido: quatro gerações reais escreviam no livro-caixa com chaves que não estavam em
# `ACTIONS` — logo não apareciam no painel admin (o usuário não podia trocar o modelo default
# delas) e `POST /api/creditos/spend` as reprovava com 422. Três viraram entrada de catálogo
# (`storyboard.angles`, `storyboard.upscale`, `export.reframe`); a quarta era o lado que grava que
# estava errado (`storyboard.video` → a chave já resolvida, `.scene`/`.transition`).

ACOES_NOVAS = ("storyboard.angles", "storyboard.upscale", "export.reframe")


def test_config_lista_as_acoes_novas_com_a_ficha_completa(client, stub_hf):
    linhas = {a["key"]: a for a in client.get("/api/creditos/config").json()["defaults"]}
    from studio.common import settings
    assert set(linhas) == settings.ACTION_KEYS and len(linhas) == 15
    for key in ACOES_NOVAS:
        a = linhas[key]
        assert set(a) >= {"screen", "kind", "label", "model", "variant", "source", "credits"}
        assert a["source"] == "code"
    # o default de código é o que o serviço já usava — catalogar não muda comportamento
    assert linhas["storyboard.angles"]["model"] == "nano_banana_2"
    assert linhas["storyboard.upscale"]["model"] == "bytedance_image_upscale"
    # `reframe` não tem custo MEDIDO (só o `generate cost` ao vivo do CLI sabe): a linha mostra "—"
    assert linhas["export.reframe"] == {**linhas["export.reframe"], "model": "reframe", "credits": None}


@pytest.mark.parametrize("action", ACOES_NOVAS)
def test_config_global_e_de_projeto_aceitam_as_acoes_novas(client, stub_hf, project, action):
    modelo = {"storyboard.angles": "gpt_image_2", "storyboard.upscale": "bytedance_image_upscale",
              "export.reframe": "reframe"}[action]
    assert client.put("/api/creditos/config",
                      json={"action": action, "model": modelo}).status_code == 200
    r = client.put(f"/api/projects/{project}/creditos/config", json={"action": action, "model": modelo})
    assert r.status_code == 200 and r.json()["source"] == "project"

    def linha_do_painel() -> dict:
        painel = client.get(f"/api/projects/{project}/creditos").json()["actions"]
        return next(a for a in painel if a["key"] == action)

    assert linha_do_painel()["source"] == "project"
    # e o DELETE do override devolve a linha ao global
    assert client.delete(f"/api/projects/{project}/creditos/config/{action}").status_code == 200
    assert linha_do_painel()["source"] == "global"


@pytest.mark.parametrize("action", [*ACOES_NOVAS, "storyboard.video.scene", "storyboard.video.transition"])
def test_spend_para_de_reprovar_gasto_real(client, stub_hf, action):
    r = client.post("/api/creditos/spend",
                    json={"action": action, "model": "nano_banana_2", "credits": 2, "step": "x"})
    assert r.status_code == 200
    # a chave genérica antiga (e qualquer invenção) continua sendo 422
    assert client.post("/api/creditos/spend",
                       json={"action": "storyboard.video", "model": "kling2_6"}).status_code == 422


def test_cost_das_acoes_novas_degrada_por_linha(client, stub_hf):
    """`GET /api/creditos/cost` para as 3 ações novas. `stub_hf` zera o `generate cost` ao vivo.

    A cadeia da rota é `cli › measured › unknown` — `source` aqui responde "de onde veio o número",
    e não "consultei a tabela" (que é o `source` de `pricing.estimate`). Sem custo medido E sem
    valor ao vivo, o certo é `unknown` com `credits: None`: a tela mostra "—" e a linha segue
    configurável, em vez de inventar um número.
    """
    def cost(action: str) -> dict:
        r = client.get("/api/creditos/cost", params={"action": action})
        assert r.status_code == 200, r.text
        return r.json()

    assert cost("storyboard.angles")["credits"] == 2          # nano_banana_2 @ 2k
    assert cost("storyboard.upscale")["credits"] == 2         # bytedance_image_upscale
    reframe = cost("export.reframe")
    assert reframe["model"] == "reframe" and reframe["kind"] == "reframe"
    assert reframe["credits"] is None and reframe["measured"] is None
    assert reframe["source"] == "unknown" and reframe["live"] is None


def test_catalogo_de_acoes_e_de_modelos_batem_entre_si(client, stub_hf):
    from studio.common import pricing, settings
    assert settings.ACTION_KEYS == {a["key"] for a in settings.ACTIONS}
    assert set(settings.DEFAULTS) == settings.ACTION_KEYS
    assert all(pricing.known(d["model"]) for d in settings.DEFAULTS.values())
    # I5: uma família fora de KIND_ORDER sumiria da tabela de custos, que itera `order`
    familias = {spec["kind"] for spec in pricing.CATALOG.values()}
    assert familias <= set(pricing.KIND_ORDER) and familias <= set(pricing.KIND_LABEL)
    # e todo `kind` de ação tem pelo menos um modelo ofertável no `<select>` do painel
    for a in settings.ACTIONS:
        assert [m for m in pricing.CATALOG.values() if m["kind"] == a["kind"]], a["key"]


def test_models_inclui_reframe_em_familia_propria(client, stub_hf):
    body = client.get("/api/creditos/models").json()
    reframe = next(m for m in body["models"] if m["id"] == "reframe")
    assert reframe["kind"] == "reframe" and reframe["rows"] == [{"variant": None, "credits": None}]
    assert body["kind_label"]["reframe"] == "Reenquadramento"
    assert body["kind_order"][-1] == "reframe"
    # família PRÓPRIA: `reframe` nunca é ofertável para as ações de vídeo
    assert "reframe" not in {m["id"] for m in body["models"] if m["kind"] == "video"}


def test_record_spend_avisa_fora_do_catalogo_e_grava_assim_mesmo(client, stub_hf, caplog):
    """Rede de segurança em produção do teste estático: avisa, mas NUNCA derruba a geração."""
    from studio.common import settings
    with caplog.at_level("WARNING", logger="studio.creditos.ledger"):
        entry = settings.record_spend(action="inventada.x", model="nano_banana_2", credits=2)
    assert entry["action"] == "inventada.x"
    assert "gasto fora do catálogo" in caplog.text and "inventada.x" in caplog.text
    assert settings.history()[0]["action"] == "inventada.x"


# ---------- cobertura estática do catálogo (o "alerta" desta tela: reprova no CI, não no usuário) ----------

STUDIO_DIR = Path(__file__).resolve().parents[1] / "studio"

#: Arquivo que DEFINE o catálogo. Citar uma chave ali não é uso — por isso ele fica fora da varredura.
CATALOGO_FONTE = STUDIO_DIR / "common" / "settings.py"

#: Funções de `studio.common.settings` cujo primeiro assunto é uma ação do catálogo.
FUNCOES_DE_ACAO = {"record_generation", "record_spend", "default_for"}

#: Chamadas em que a ação chega por EXPRESSÃO, não por literal. Não são exceções cegas: cada uma é
#: verificada pelo outro lado em `test_toda_indirecao_declarada_so_produz_acoes_do_catalogo`. A
#: chave é o `ast.unparse` da expressão, que muda com o código e não com o número da linha — se um
#: serviço passar a resolver a ação por outro caminho, o par deixa de bater e o teste avisa.
INDIRECOES_DECLARADAS = {
    ("studio/base/service.py", "KIND_ACTION.get(kind, ACTION_DEFAULT)"),
    ("studio/common/multishot.py", "spend_action"),
    ("studio/creditos/router.py", "req.action"),
    ("studio/creditos/service.py", "action"),
    ("studio/storyboard/service.py", "video_action(mode)"),
}

#: Ações catalogadas que NENHUM código referencia hoje. Ficam no catálogo de propósito (removê-las
#: apagaria overrides já gravados no `config.json` dos usuários), mas o conjunto é fixo: uma órfã
#: NOVA reprova o CI, e é o sinal de que alguém catalogou uma ação sem ligar o serviço nela.
ORFAS_CONHECIDAS = {"storyboard.scene", "storyboard.multishot"}


def _acoes_passadas_a_settings() -> list[tuple[str, int, str, bool]]:
    """`(arquivo, linha, fonte da ação, é_literal)` de cada chamada que nomeia uma ação."""
    achados = []
    for path in sorted(STUDIO_DIR.rglob("*.py")):
        if path == CATALOGO_FONTE:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            nome = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            arg = None
            if nome in FUNCOES_DE_ACAO:
                arg = next((kw.value for kw in node.keywords if kw.arg == "action"), None)
                if arg is None and nome == "default_for" and node.args:
                    arg = node.args[0]           # `default_for(action, pid)` posicional
            if arg is None:                      # repasse ao multishot comum (ADR-013)
                arg = next((kw.value for kw in node.keywords if kw.arg == "spend_action"), None)
            if arg is None:
                continue
            literal = isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            achados.append((str(path.relative_to(STUDIO_DIR.parent)), node.lineno,
                            arg.value if literal else ast.unparse(arg), literal))
    return achados


def test_toda_acao_nomeada_por_codigo_esta_no_catalogo():
    from studio.common import settings
    fora = [(f, ln, a) for f, ln, a, lit in _acoes_passadas_a_settings()
            if lit and a not in settings.ACTION_KEYS]
    assert not fora, (
        "ação fora de `settings.ACTIONS` — o painel não a mostra e o `spend` a reprova com 422. "
        "Catalogue a chave ou corrija quem grava:\n" +
        "\n".join(f"  {f}:{ln} → {a!r}" for f, ln, a in fora))


def test_nenhuma_indirecao_de_acao_nova_passa_sem_declaracao():
    achadas = {(f, a) for f, _, a, lit in _acoes_passadas_a_settings() if not lit}
    novas = achadas - INDIRECOES_DECLARADAS
    assert not novas, (
        "ação resolvida por expressão sem verificação do outro lado. Declare em "
        "`INDIRECOES_DECLARADAS` e prove que o conjunto de valores cabe em `ACTION_KEYS`:\n" +
        "\n".join(f"  {f} → {a}" for f, a in sorted(novas)))
    assert not INDIRECOES_DECLARADAS - achadas, "indireção declarada que não existe mais no código"


def test_toda_indirecao_declarada_so_produz_acoes_do_catalogo():
    """O outro lado de cada indireção: o conjunto de valores possíveis cabe em `ACTION_KEYS`."""
    from studio.base import service as base
    from studio.common import settings
    from studio.storyboard import service as storyboard
    assert set(base.KIND_ACTION.values()) | {base.ACTION_DEFAULT} <= settings.ACTION_KEYS
    assert {storyboard.video_action(m) for m in ("single", "start_end")} <= settings.ACTION_KEYS
    # `multishot.spend_action` e `req.action`/`action` das rotas são parâmetros: quem os fornece é
    # verificado como literal (moodboards) ou barrado pelo `_valid` do router (422 antes de gravar).


def test_acoes_orfas_sao_exatamente_as_registradas():
    from studio.common import settings
    citadas = set()
    for path in sorted(STUDIO_DIR.rglob("*.py")):
        if path == CATALOGO_FONTE:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                citadas.add(node.value)
    assert settings.ACTION_KEYS - citadas == ORFAS_CONHECIDAS
