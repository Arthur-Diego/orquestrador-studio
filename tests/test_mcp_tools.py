"""Tools de leitura do MCP (ADR-037): funções puras contra um cliente fake, sem rede."""

from studio.mcp import tools


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
