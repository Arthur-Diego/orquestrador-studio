"""Resources do MCP (ADR-037, Onda E): conhecimento citável, sem depender do pacote mcp."""
from studio.mcp import resources


class FakeCli:
    def get(self, path, params=None):
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


def test_register_resources_registra_tres():
    srv = FakeServer()
    resources.register_resources(srv, FakeCli())
    assert set(srv.registered) == {"studio://help", "studio://help/{etapa}", "studio://project/{pid}/guide"}
    # o resource por etapa responde com a dica; o de guia usa o cliente
    assert "Aula 009" in srv.registered["studio://help/{etapa}"]("refs")
    assert "20%" in srv.registered["studio://project/{pid}/guide"]("qualquer")
