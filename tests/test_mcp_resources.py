"""Resources do MCP (ADR-037, Onda E): conhecimento citável, sem depender do pacote mcp."""
import pathlib
import re

from studio.mcp import resources


class FakeCli:
    def get(self, path, params=None):
        if path == "/api/creditos":
            return {"balance": {"installed": True, "logged_in": True, "plan": "creator",
                                "credits": 118},
                    "summary": {"today_credits": 18, "today_count": 4,
                                "total_credits": 312, "count": 74},
                    "models": [], "history": []}
        return {"progress": 0.2, "current": "mood",
                "steps": [{"n": 1, "id": "refs", "title": "Referências", "status": "done"}]}


class FakeServer:
    """Grava os resources registrados por URI (imita o decorator do FastMCP)."""

    def __init__(self):
        self.registered: dict[str, callable] = {}

    def resource(self, uri):
        def deco(fn):
            self.registered[uri] = fn
            return fn
        return deco


def test_help_geral_e_por_etapa():
    assert "Orquestrador Studio" in resources.HELP_GERAL
    assert "vibe única" in resources.HELP["mood"]
    assert set(resources.HELP) >= {"refs", "mood", "base", "storyboard", "animate", "export"}


def test_register_resources_registra_os_quatro():
    srv = FakeServer()
    resources.register_resources(srv, FakeCli())
    assert set(srv.registered) == {"studio://help", "studio://help/{etapa}",
                                   "studio://project/{pid}/guide", "studio://credits"}
    # o resource por etapa responde com a dica; o de guia usa o cliente
    assert "Aula 009" in srv.registered["studio://help/{etapa}"]("refs")
    assert "20%" in srv.registered["studio://project/{pid}/guide"]("qualquer")


# ---------- biblioteca de mood boards `[extensão]` (ADR-013) — área global, não etapa ----------
ROOT = pathlib.Path(__file__).resolve().parents[1]


def _resolver():
    srv = FakeServer()
    resources.register_resources(srv, FakeCli())
    return srv.registered["studio://help/{etapa}"]


def test_help_moodboards_descreve_a_biblioteca_e_cita_as_tools():
    texto = _resolver()("moodboards")
    for t in ("Biblioteca de mood boards", "moodboard_create", "moodboard_pick", "mood_pull",
              "vibes_pick", "mood_run", "moodboard_multishot"):
        assert t in texto, t


def test_help_por_etapa_nao_regride_com_a_area_nova():
    assert "Aula 009" in _resolver()("refs")


def test_help_desconhecido_lista_etapas_e_areas():
    texto = _resolver()("nao-existe")
    assert "refs" in texto and "moodboards" in texto


def test_biblioteca_nao_polui_a_lista_de_etapas():
    assert "moodboards" not in resources.HELP
    assert "moodboards" in resources.HELP_AREAS


def test_help_geral_menciona_a_biblioteca_sem_perder_o_texto_de_sempre():
    assert "Orquestrador Studio" in resources.HELP_GERAL
    assert "biblioteca de mood boards" in resources.HELP_GERAL


def test_prompt_de_sistema_tem_a_secao_da_biblioteca():
    """A conduta mora no prompt de sistema: sem ela, as 16 tools existem e não são usadas."""
    texto = (ROOT / "studio" / "chat" / "prompts" / "sistema.md").read_text()
    assert "## Biblioteca de mood boards `[extensão]`" in texto
    assert "mood_pull" in texto and "mood_run_wait" in texto and "moodboard_multishot_wait" in texto
    # a regra do custo: oferecer o board da biblioteca ANTES de gastar na etapa 2
    assert "antes de gerar mood pago" in texto.lower()


def test_hld_do_dominio_moodboards_existe_e_descreve_o_terreno():
    texto = (ROOT / "docs" / "domains" / "moodboards" / "hld.md").read_text()
    assert texto.startswith("### HLD:")
    for t in ("/mbfiles", "mood_run", "_vibes", "_escolhidas",
              "ADR-013", "ADR-014", "ADR-034", "29 operações"):
        assert t in texto, t


def test_fdd_da_biblioteca_nao_descreve_mais_a_rota_que_nunca_existiu():
    texto = (ROOT / "docs" / "domains" / "moodboards" / "features"
             / "moodboard-library-fdd.md").read_text()
    assert not re.search(r"\{mbid\}/generate\b", texto)
    for t in ("multishot", "prompt/generate", "downloads-folder", "open-folder"):
        assert t in texto, t


# ---------- créditos `[extensão]` (F10) ----------
def test_resource_de_creditos_traz_saldo_gasto_e_reconciliacao():
    """Critério 17: mesmo texto global do `credits_status`, sempre com o porquê de não baterem."""
    srv = FakeServer()
    resources.register_resources(srv, FakeCli())
    txt = srv.registered["studio://credits"]()
    assert "118" in txt and "creator" in txt
    assert "hoje **18**" in txt and "total **312**" in txt
    assert "não aparece aqui" in txt  # o parágrafo de reconciliação (P6 do FDD)
