"""Tools de leitura do MCP (ADR-037): funções puras contra um cliente fake, sem rede."""
import ast
import pathlib

from studio.mcp import tools
from studio.mcp.client import StudioApiError


class FakeClient:
    """Devolve respostas canônicas por path (GET). `raises` mapeia path → exceção."""

    def __init__(self, routes: dict, raises: dict | None = None):
        self.routes = routes
        self.raises = raises or {}

    def get(self, path, params=None):
        if path in self.raises:
            raise self.raises[path]
        return self.routes[path]


def test_projects_list_vazio_e_cheio():
    assert "Nenhuma campanha" in tools.projects_list(FakeClient({"/api/projects": []}))
    txt = tools.projects_list(FakeClient({"/api/projects": [{"id": "gelo", "name": "Gelo Zero", "product": "energy"}]}))
    assert "Gelo Zero" in txt and "gelo" in txt and "energy" in txt


def test_project_get_formata_campos():
    cli = FakeClient({"/api/projects/gelo": {
        "name": "Gelo Zero", "product": "energy", "vibe": "", "aspect_ratio": "9:16",
        "progress": 0.3, "current": "mood"}})
    txt = tools.project_get(cli, "gelo")
    assert "Gelo Zero" in txt and "9:16" in txt and "30%" in txt and "mood" in txt
    assert "a encontrar na etapa 2" in txt  # vibe vazia


def test_guide_overview_lista_status_traduzido():
    cli = FakeClient({"/api/projects/gelo/guide": {
        "progress": 0.2, "current": "mood",
        "steps": [
            {"n": 1, "id": "refs", "title": "Referências", "status": "done"},
            {"n": 2, "id": "mood", "title": "Mood board", "status": "in_progress", "summary": "1/4"},
        ]}})
    txt = tools.guide_overview(cli, "gelo")
    assert "20%" in txt and "concluída" in txt and "em andamento" in txt and "1/4" in txt


def test_guide_step_detalha_missing_e_proxima_acao():
    cli = FakeClient({"/api/projects/gelo/guide/base": {
        "title": "Imagem base", "status": "blocked", "text": "Coloque o produto na situação da ref",
        "missing": [{"label": "≥ 1 referência escolhida"}],
        "next_action": "Volte à etapa 1 e salve a seleção"}})
    txt = tools.guide_step(cli, "gelo", "base")
    assert "Imagem base" in txt and "bloqueada" in txt
    assert "referência escolhida" in txt and "Próxima ação" in txt


def test_doctor_lê_status_higgsfield():
    cli = FakeClient({"/api/higgsfield/status": {"installed": True, "logged_in": False}})
    assert "deslogado" in tools.doctor(cli)


def test_job_status_idle_e_running():
    idle = FakeClient({"/api/projects/gelo/mood/job": {"state": "idle"}})
    assert "nenhum trabalho" in tools.job_status(idle, "gelo", "mood")
    run = FakeClient({"/api/projects/gelo/mood/job": {"state": "running", "done": 1, "total": 4, "added": 1}})
    assert "running (1/4" in tools.job_status(run, "gelo", "mood")


def test_api_get_recusa_fora_de_api():
    assert "Recusado" in tools.api_get(FakeClient({}), "/etc/passwd")
    assert tools.api_get(FakeClient({"/api/portfolio": {"count": 2}}), "/api/portfolio") == {"count": 2}


# ---------- créditos `[extensão]` (wave 11 · F10, ADR-016/037) ----------
CATALOGO = [{"model": "bytedance_image_upscale", "label": "ByteDance Image Upscale"},
            {"model": "nano_banana_2", "label": "Nano Banana Pro"}]

SALDO = {"installed": True, "logged_in": True, "plan": "creator", "credits": 114}


def _dashboard(history, *, balance=None, summary=None, glob=None):
    return {"balance": SALDO if balance is None else balance,
            "summary": summary or {"today_credits": 18, "today_count": 4,
                                   "total_credits": 46, "count": 12},
            "summary_global": glob or {"total_credits": 312, "count": 74},
            "models": CATALOGO, "history": history}


class ClienteDeGasto:
    """Fake que serve o job e o dashboard, e grava os `emit` do `notify`."""

    def __init__(self, job, dashboard=None, erro_creditos=None):
        self.job, self.dashboard, self.erro = job, dashboard, erro_creditos
        self.posts = []

    def get(self, path, params=None):
        if path.endswith("/creditos"):
            if self.erro:
                raise self.erro
            return self.dashboard
        return self.job

    def post(self, path, json=None, params=None):
        self.posts.append((path, json))
        return {}

    def notificacoes(self):
        return [b["event"]["text"] for p, b in self.posts if p.endswith("/emit")]


def test_job_wait_anuncia_o_gasto_registrado(monkeypatch):
    """Critério 13: notify com créditos, rótulo do modelo e saldo, e a mesma frase no retorno."""
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    linha = {"at": "2999-01-01T00:00:00+00:00", "model": "bytedance_image_upscale", "credits": 4}
    cli = ClienteDeGasto({"state": "done", "added": 1, "total": 1}, _dashboard([linha]))
    out = tools.job_wait(cli, "gelo", "base", _sleep=lambda s: None)
    esperado = "Gastou 4 créditos (ByteDance Image Upscale) · saldo 114 créditos."
    assert cli.notificacoes() == [esperado]
    assert esperado in out and "concluído (1/1 adicionados)" in out


def test_job_wait_usa_a_variante_no_rotulo(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    linha = {"at": "2999-01-01T00:00:00+00:00", "model": "nano_banana_2",
             "variant": "2k", "credits": 6}
    cli = ClienteDeGasto({"state": "done", "added": 1, "total": 1},
                         _dashboard([linha], balance={**SALDO, "credits": 108}))
    tools.job_wait(cli, "gelo", "base", _sleep=lambda s: None)
    assert cli.notificacoes() == ["Gastou 6 créditos (Nano Banana Pro · 2k) · saldo 108 créditos."]


def test_job_wait_agrega_varias_linhas(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    linhas = [{"at": "2999-01-01T00:00:0%d+00:00" % i, "model": "nano_banana_2", "credits": 4}
              for i in range(3)]
    cli = ClienteDeGasto({"state": "done", "added": 3, "total": 3},
                         _dashboard(linhas, balance={**SALDO, "credits": 106}))
    tools.job_wait(cli, "gelo", "base", _sleep=lambda s: None)
    assert cli.notificacoes() == ["Gastou 12 créditos (3 gerações) · saldo 106 créditos."]


def test_job_wait_sem_saldo_legivel_omite_o_sufixo(monkeypatch):
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    linha = {"at": "2999-01-01T00:00:00+00:00", "model": "bytedance_image_upscale", "credits": 4}
    cli = ClienteDeGasto({"state": "done", "added": 1, "total": 1},
                         _dashboard([linha], balance={"installed": True, "logged_in": False}))
    tools.job_wait(cli, "gelo", "base", _sleep=lambda s: None)
    assert cli.notificacoes() == ["Gastou 4 créditos (ByteDance Image Upscale)."]


def test_job_wait_sem_linha_nova_nao_notifica(monkeypatch):
    """Critério 14: linha antiga (anterior ao t0) não é gasto desta espera — nada de ruído."""
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    antiga = {"at": "2000-01-01T00:00:00+00:00", "model": "nano_banana_2", "credits": 4}
    cli = ClienteDeGasto({"state": "done", "added": 1, "total": 1}, _dashboard([antiga]))
    out = tools.job_wait(cli, "gelo", "base", _sleep=lambda s: None)
    assert cli.notificacoes() == []
    assert out == "Etapa base: concluído (1/1 adicionados)."


def test_job_wait_com_erro_nao_anuncia_gasto(monkeypatch):
    """Critério 15: gasto parcial segue no ledger e no credits_status, mas não vira cartão."""
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    linha = {"at": "2999-01-01T00:00:00+00:00", "model": "nano_banana_2", "credits": 4}
    cli = ClienteDeGasto({"state": "error", "error": "o CLI caiu"}, _dashboard([linha]))
    out = tools.job_wait(cli, "gelo", "base", _sleep=lambda s: None)
    assert cli.notificacoes() == [] and out == "Etapa base: job falhou — o CLI caiu"


def test_job_wait_com_ledger_indisponivel_nao_derruba(monkeypatch):
    """A checagem de gasto é best effort: falhar em ler créditos não estraga a espera do job."""
    monkeypatch.setenv("STUDIO_CHAT_ID", "cid")
    cli = ClienteDeGasto({"state": "done", "added": 2, "total": 2},
                         erro_creditos=StudioApiError("502: livro-caixa indisponível"))
    out = tools.job_wait(cli, "gelo", "base", _sleep=lambda s: None)
    assert out == "Etapa base: concluído (2/2 adicionados)." and cli.notificacoes() == []


def test_job_wait_preserva_os_retornos_de_sempre(monkeypatch):
    monkeypatch.delenv("STUDIO_CHAT_ID", raising=False)
    sem = ClienteDeGasto({"state": "idle"}, _dashboard([]))
    assert tools.job_wait(sem, "gelo", "base", _sleep=lambda s: None) == \
        "Etapa base: nenhum trabalho em andamento."
    fim = ClienteDeGasto({"state": "done", "added": 4, "total": 4}, _dashboard([]))
    assert tools.job_wait(fim, "gelo", "base", _sleep=lambda s: None) == \
        "Etapa base: concluído (4/4 adicionados)."


def test_credits_status_global(monkeypatch):
    """Critério 16: saldo, plano, gasto de hoje, gasto total e as últimas linhas."""
    linha = {"at": "2026-09-06T14:02:11+00:00", "action": "storyboard.upscale",
             "model": "bytedance_image_upscale", "credits": 4, "project_name": "Gelo Zero"}
    cli = FakeClient({"/api/creditos": _dashboard([linha])})
    txt = tools.credits_status(cli)
    assert "**114** créditos" in txt and "`creator`" in txt
    assert "hoje **18**" in txt and "total **312**" in txt and "74 gerações" in txt
    assert "campanha" not in txt  # sem pid, não há linha de campanha
    assert "storyboard.upscale" in txt and "ByteDance Image Upscale" in txt and "Gelo Zero" in txt
    assert "não aparece aqui" in txt


def test_credits_status_por_projeto_acrescenta_a_campanha():
    cli = FakeClient({"/api/projects/gelo/creditos": _dashboard([])})
    txt = tools.credits_status(cli, "gelo")
    assert "campanha `gelo` **46**" in txt and "12 gerações" in txt
    assert "total **312**" in txt


def test_credits_status_deslogado_ainda_mostra_o_ledger():
    """Critério 16: sem CLI o saldo some, mas o livro-caixa local continua legível."""
    cli = FakeClient({"/api/creditos": _dashboard(
        [], balance={"installed": True, "logged_in": False})})
    txt = tools.credits_status(cli)
    assert "sem login" in txt and "higgsfield auth login" in txt
    assert "hoje **18**" in txt and "total **312**" in txt


def test_credits_status_com_pid_inexistente_devolve_o_texto_do_erro():
    cli = FakeClient({}, raises={"/api/projects/nao-existe/creditos":
                                 StudioApiError("404: campanha não encontrada")})
    assert "404" in tools.credits_status(cli, "nao-existe")


def test_credits_status_so_faz_get():
    """ADR-037: é tool de LEITURA — só GET, nunca POST."""
    class SoGet(FakeClient):
        def post(self, path, json=None, params=None):  # pragma: no cover - não pode ser chamado
            raise AssertionError(f"credits_status não pode fazer POST (tentou {path})")

    tools.credits_status(SoGet({"/api/creditos": _dashboard([])}))


def test_tools_nao_importa_servico():
    """ADR-037: o MCP é cliente HTTP da própria API — nada de importar o serviço por dentro.

    Checagem por AST, não por texto: a docstring de `credits_status` CITA
    `studio.creditos.service` justamente para dizer que não o importa.
    """
    fonte = (pathlib.Path(__file__).resolve().parents[1] / "studio/mcp/tools.py").read_text()
    importados = set()
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Import):
            importados.update(a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom):
            importados.add(("." * (no.level or 0)) + (no.module or ""))
            importados.update(("." * (no.level or 0)) + (no.module or "") + "." + a.name
                              for a in no.names)
    proibidos = {"studio.creditos", "studio.common.settings", "studio.common.pricing",
                 "..creditos", "..common", "..creditos.service", "..common.settings",
                 "..common.pricing"}
    assert not (importados & proibidos), f"tools.py importou serviço: {importados & proibidos}"


def test_gasto_sem_pid_cai_no_rotulo_biblioteca():
    linha = {"at": "2026-09-06T11:20:02+00:00", "action": "mood.multishot",
             "model": "nano_banana_2", "credits": 8}
    cli = FakeClient({"/api/creditos": _dashboard([linha])})
    assert "Biblioteca" in tools.credits_status(cli)
