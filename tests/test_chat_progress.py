"""Poller de progresso de job (chat-feedback, FDD contratos 4 e 6) `[extensão]`.

As quatro funções puras são exercitadas direto; `watch` só roda com `fetch`/`sleep` FALSOS
(ADR-008) — nenhum teste deste arquivo toca a rede nem espera de verdade.
"""
import asyncio

import pytest

from studio.chat import progress


# ---------- job_url_for (T-PG-01..05) ----------
def test_t_pg_01_url_do_job_de_etapa():
    assert progress.job_url_for("mcp__studio__job_wait", {"pid": "p1", "step": "refs"}) == \
        "/api/projects/p1/refs/job"


def test_t_pg_02_url_do_job_de_personagem():
    # o job de personagem tem URL PRÓPRIA, diferente da URL de job das etapas
    assert progress.job_url_for("mcp__studio__character_wait", {"cid": "c3f1"}) == \
        "/api/characters/c3f1/job"


def test_t_pg_03_tool_nao_observada_nao_tem_url():
    assert progress.job_url_for("mcp__studio__refs_search", {"pid": "p1"}) is None
    assert progress.job_url_for("job", {"pid": "p1", "step": "refs"}) is None
    assert progress.job_url_for("", {}) is None


@pytest.mark.parametrize("nome,entrada", [
    ("job_wait", {"step": "refs"}),          # sem pid
    ("job_wait", {"pid": "p1"}),             # sem step
    ("job_wait", {"pid": "", "step": "refs"}),
    ("job_wait", {"pid": "p1", "step": None}),
    ("job_wait", {"pid": 7, "step": "refs"}),
    ("job_wait", {"pid": "../../etc", "step": "refs"}),  # travessia de caminho
    ("character_wait", {}),
    ("character_wait", {"cid": "  "}),
])
def test_t_pg_04_input_malformado_devolve_none_sem_levantar(nome, entrada):
    assert progress.job_url_for(nome, entrada) is None


def test_t_pg_05_aceita_nome_cru_e_curto():
    cru = progress.job_url_for("mcp__studio__job_wait", {"pid": "p1", "step": "refs"})
    curto = progress.job_url_for("job_wait", {"pid": "p1", "step": "refs"})
    assert cru == curto == "/api/projects/p1/refs/job"
    assert progress.job_url_for("character_wait", {"cid": "c3f1"}) == "/api/characters/c3f1/job"


# ---------- pct_of (T-PG-06..08) ----------
def test_t_pg_06_percentual_a_partir_de_done_e_total():
    assert progress.pct_of({"done": 13, "total": 31}) == 42
    assert progress.pct_of({"done": 0, "total": 4}) == 0
    assert progress.pct_of({"done": 4, "total": 4}) == 100


@pytest.mark.parametrize("job", [
    {"done": 3, "total": 0}, {"done": 3}, {"done": 3, "total": -1},
    {"done": 3, "total": None}, {"done": 3, "total": "muitos"}, {},
])
def test_t_pg_07_sem_total_nao_inventa_percentual(job):
    assert progress.pct_of(job) is None


def test_t_pg_08_satura_em_0_e_100():
    assert progress.pct_of({"done": 99, "total": 4}) == 100
    assert progress.pct_of({"done": -5, "total": 4}) == 0
    assert progress.pct_of({"total": 4}) == 0  # sem `done` é 0, não é erro


# ---------- label_of (T-PG-09) ----------
def test_t_pg_09_rotulo_de_etapa_e_de_personagem():
    etapa = progress.label_of("mcp__studio__job_wait", {"pid": "p1", "step": "refs"},
                              {"state": "running", "done": 13, "total": 31})
    assert etapa == "Etapa refs: 13/31"
    # personagem sem total conhecido cai no estado, nunca num percentual inventado
    assert progress.label_of("character_wait", {"cid": "c3f1"}, {"state": "running"}) == \
        "Personagem c3f1: gerando"
    assert progress.label_of("character_wait", {"cid": "c3f1"}, {"state": "done", "done": 4,
                                                                 "total": 4}) == "Personagem c3f1: 4/4"
    # o rótulo carrega SÓ pid/step/cid e contadores — nunca prompt (FDD §7)
    assert "prompt" not in progress.label_of("job_wait", {"step": "mood", "prompt": "segredo"}, {})


# ---------- as DUAS formas de job que a API publica (rodada de review 001, issue 001) ----------
#
# A etapa `refs` tem registro próprio (`studio/refs/service.py::job_status`) e NÃO publica `done`:
# ela manda `{terms, total, meta, log, last}`, com `total` sendo o contador corrente e `meta` o teto
# pedido. Ler `done`/`total` nas duas formas dava `0 %` eterno e `Etapa refs: 0/94` com o
# denominador subindo — justo na etapa que o FDD usa de exemplo.
def test_forma_do_registry_padrao_le_done_sobre_total():
    """`{done, total, added}` — o `JobRegistry` (ADR-006) que mood/base/storyboard/animate usam."""
    job = {"state": "running", "done": 13, "total": 31, "added": 13}
    assert progress.contadores(job) == (13, 31)
    assert progress.pct_of(job) == 42
    assert progress.label_of("job_wait", {"step": "mood"}, job) == "Etapa mood: 13/31"


def test_forma_do_refs_le_total_sobre_meta():
    """`{total, meta}` — o scraper da etapa 1: `total` é o que já veio, `meta` é o teto."""
    job = {"state": "running", "terms": ["café"], "total": 47, "meta": 94, "log": []}
    assert progress.contadores(job) == (47, 94)
    assert progress.pct_of(job) == 50
    assert progress.label_of("job_wait", {"pid": "p1", "step": "refs"}, job) == "Etapa refs: 47/94"


def test_forma_do_refs_ociosa_nao_inventa_percentual():
    """Sem scrape nenhum o refs devolve `{"state": "idle"}` — sem teto, sem percentual."""
    job = {"state": "idle"}
    assert progress.pct_of(job) is None
    assert progress.label_of("job_wait", {"step": "refs"}, job) == "Etapa refs: aguardando"


@pytest.mark.parametrize("meta", [0, -3, None, "muitas", True])
def test_meta_invalida_cai_na_leitura_padrao(meta):
    """`meta` zerada, negativa ou não numérica não vira denominador.

    Sem um `meta` utilizável a forma volta a ser ambígua, e a leitura cai na do `JobRegistry`:
    `total` é o teto e o `done` ausente vale 0 — exatamente o que T-PG-08 já fixa. É a escolha
    conservadora: `meta` inválida nunca inverte o significado de `total`.
    """
    assert progress.contadores({"total": 5, "meta": meta}) == (0, 5)
    assert progress.pct_of({"total": 5, "meta": meta}) == 0


# ---------- should_emit (T-PG-10..13) ----------
def test_t_pg_10_primeira_leitura_sempre_emite():
    assert progress.should_emit(None, {"pct": None, "state": "running", "ts": 0.0}, 0.0) is True


def test_t_pg_11_mudanca_de_pct_ou_de_state_emite():
    ant = {"pct": 10, "state": "running", "ts": 100.0}
    assert progress.should_emit(ant, {"pct": 20, "state": "running", "ts": 101.0}, 101.0) is True
    assert progress.should_emit(ant, {"pct": 10, "state": "done", "ts": 101.0}, 101.0) is True
    # de percentual conhecido para desconhecido também é mudança
    assert progress.should_emit(ant, {"pct": None, "state": "running", "ts": 101.0}, 101.0) is True


def test_t_pg_12_sem_mudanca_e_dentro_do_batimento_fica_calado():
    ant = {"pct": 10, "state": "running", "ts": 100.0}
    atual = {"pct": 10, "state": "running", "ts": 100.0}
    assert progress.should_emit(ant, atual, 102.0) is False
    assert progress.should_emit(ant, atual, 100.0 + progress.HEARTBEAT_S - 0.1) is False


def test_t_pg_13_batimento_emite_mesmo_sem_mudanca():
    ant = {"pct": 10, "state": "running", "ts": 100.0}
    atual = {"pct": 10, "state": "running", "ts": 100.0}
    assert progress.should_emit(ant, atual, 100.0 + progress.HEARTBEAT_S) is True
    assert progress.should_emit(ant, atual, 130.0) is True


# ---------- watch (T-PG-14..17), sempre com fetch/sleep falsos ----------
class _Relogio:
    """Relógio falso que só anda quando o `sleep` falso anda — nada espera de verdade."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    async def sleep(self, s: float) -> None:
        self.t += s


@pytest.fixture
def relogio(monkeypatch):
    r = _Relogio()
    monkeypatch.setattr(progress, "_agora", r)
    return r


def _coletor():
    empurrados: list[tuple[str, dict]] = []

    async def push(chat_id: str, event: dict) -> None:
        empurrados.append((chat_id, event))

    return empurrados, push


def test_t_pg_14_running_running_done_empurra_e_encerra_sozinha(relogio):
    leituras = [
        {"state": "running", "done": 3, "total": 31},
        {"state": "running", "done": 13, "total": 31},
        {"state": "done", "done": 31, "total": 31, "added": 31},
        {"state": "idle"},  # nunca deve ser lida: a task encerra ao sair de `running`
    ]
    lidas = []

    async def fetch(url):
        lidas.append(url)
        return leituras[len(lidas) - 1]

    empurrados, push = _coletor()
    asyncio.run(progress.watch("chat1", "toolu_01A9", "/api/projects/p1/refs/job", push,
                               fetch=fetch, sleep=relogio.sleep))

    assert lidas == ["/api/projects/p1/refs/job"] * 3  # a 1ª leitura é imediata, antes do 1º sleep
    assert relogio.t == 2 * progress.POLL_S  # dormiu entre as leituras, não depois da última
    eventos = [e for _, e in empurrados]
    assert [e["pct"] for e in eventos] == [10, 42, 100]  # percentual crescente
    assert [e["state"] for e in eventos] == ["running", "running", "done"]
    assert all(e["kind"] == "tool_progress" and e["id"] == "toolu_01A9" for e in eventos)
    assert eventos[1]["label"] == "Etapa refs: 13/31"
    assert all("seq" not in e for e in eventos)  # efêmero: nunca ganha seq


def test_t_pg_14b_sem_mudanca_so_o_batimento_empurra(relogio):
    async def fetch(url):
        return {"state": "running"}  # sem total: pct None, nada muda nunca

    empurrados, push = _coletor()

    async def sleep(s):
        await relogio.sleep(s)
        if relogio.t >= 30.0:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(progress.watch("chat1", "id", "/api/characters/c3f1/job", push,
                                   fetch=fetch, sleep=sleep))
    # 1ª leitura (t=0) + um batimento a cada 10 s (t=10, t=20); em t=30 o sleep já cancelou
    assert [e["pct"] for _, e in empurrados] == [None, None, None]
    assert all(e["label"] == "Personagem c3f1: gerando" for _, e in empurrados)


def test_t_pg_15_tres_falhas_seguidas_encerram_em_silencio(relogio, caplog):
    tentativas = []

    async def fetch(url):
        tentativas.append(url)
        raise RuntimeError("connection refused")

    empurrados, push = _coletor()
    with caplog.at_level("WARNING"):
        asyncio.run(progress.watch("chat1", "id", "/api/projects/p1/refs/job", push,
                                   fetch=fetch, sleep=relogio.sleep))

    assert len(tentativas) == progress.MAX_FALHAS  # desistiu na terceira, sem levantar
    assert empurrados == []  # nenhum push de erro: progresso é enfeite, não contrato
    assert "desisti de acompanhar /api/projects/p1/refs/job após 3 falhas" in caplog.text


def test_t_pg_15b_falha_isolada_nao_derruba_o_acompanhamento(relogio):
    respostas = [RuntimeError("500"), {"state": "running", "done": 1, "total": 4},
                 RuntimeError("500"), RuntimeError("500"),
                 {"state": "done", "done": 4, "total": 4}]
    n = []

    async def fetch(url):
        r = respostas[len(n)]
        n.append(url)
        if isinstance(r, Exception):
            raise r
        return r

    empurrados, push = _coletor()
    asyncio.run(progress.watch("chat1", "id", "/api/projects/p1/refs/job", push,
                               fetch=fetch, sleep=relogio.sleep))
    # o contador zera na leitura boa: duas falhas seguidas não bastam para desistir
    assert len(n) == 5
    assert [e["pct"] for _, e in empurrados] == [25, 100]


def test_t_pg_16_cancelamento_encerra_sem_push_extra(relogio):
    async def fetch(url):
        return {"state": "running", "done": 1, "total": 10}

    empurrados, push = _coletor()

    async def cenario():
        task = asyncio.create_task(progress.watch("chat1", "id", "/api/projects/p1/refs/job", push,
                                                  fetch=fetch, sleep=asyncio.sleep))
        await asyncio.sleep(0)  # deixa a primeira leitura acontecer
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return task

    task = asyncio.run(cenario())
    assert task.cancelled()  # morreu de verdade, não ficou pendurada
    assert len(empurrados) == 1  # só a primeira leitura; o cancelamento não empurra nada


def test_t_pg_17_teto_duro_de_tempo_encerra_a_task(relogio):
    lidas = []

    async def fetch(url):
        lidas.append(url)
        return {"state": "running", "done": len(lidas), "total": 10_000_000}

    empurrados, push = _coletor()
    asyncio.run(progress.watch("chat1", "id", "/api/projects/p1/refs/job", push,
                               fetch=fetch, sleep=relogio.sleep))

    # o job nunca sai de `running`; quem encerra é o teto duro, não o job
    assert relogio.t >= progress.TETO_S
    assert len(lidas) == progress.TETO_S / progress.POLL_S
    assert empurrados  # e o que foi lido até lá foi mesmo contado ao browser


# ---------- fetch default: loopback na própria API (ADR-037) ----------
def test_fetch_padrao_le_a_api_em_loopback_sem_importar_o_servico(monkeypatch):
    monkeypatch.setenv("STUDIO_URL", "http://127.0.0.1:9999")
    chamadas = {}

    class _Resp:
        def raise_for_status(self):
            chamadas["status"] = True

        def json(self):
            return {"state": "running", "done": 2, "total": 5}

    class _Cli:
        def __init__(self, **kw):
            chamadas["kw"] = kw

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            chamadas["url"] = url
            return _Resp()

    monkeypatch.setattr(progress.httpx, "AsyncClient", _Cli)
    job = asyncio.run(progress._fetch_padrao("/api/projects/p1/refs/job"))

    assert job == {"state": "running", "done": 2, "total": 5}
    assert chamadas["url"] == "/api/projects/p1/refs/job"
    assert chamadas["kw"]["base_url"] == "http://127.0.0.1:9999"  # mesma env do runtime/MCP
    assert chamadas["kw"]["timeout"] == progress.FETCH_TIMEOUT_S
    assert chamadas["status"] is True
