"""Servidor MCP stdio do Studio (ADR-037): registra as tools puras de `tools.py` num `FastMCP`.

Rode com `python -m studio.mcp`. O nome do servidor é `studio`, então as tools chegam ao agente
como `mcp__studio__<nome>`. Um único cliente HTTP (loopback) é compartilhado por todas as tools.

O import do `mcp` é tardio (dentro de `build_server`/`run`) para que `tools.py` e os testes das
funções puras não dependam do pacote `mcp` estar instalado.
"""
from __future__ import annotations

from typing import Any

from . import tools
from .client import StudioClient


def build_server(client: StudioClient | None = None):
    """Monta o `FastMCP` com as tools de leitura da Onda A. `client` injetável para teste."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("studio")
    cli = client or StudioClient()

    @server.tool(name="projects", description="Lista as campanhas (projetos de vídeo) existentes.")
    def projects() -> str:
        return tools.projects_list(cli)

    @server.tool(name="project", description="Detalhe de uma campanha: nome, produto, vibe, formato, progresso e etapa atual.")
    def project(pid: str) -> str:
        return tools.project_get(cli, pid)

    @server.tool(name="guide", description="Panorama das 10 etapas da campanha: status de cada uma, progresso e etapa atual. Use para responder 'o que falta'.")
    def guide(pid: str) -> str:
        return tools.guide_overview(cli, pid)

    @server.tool(name="guide_step", description="Detalhe de uma etapa: o que a aula manda, o que falta, validações e a próxima ação. Use para 'por que está bloqueada'.")
    def guide_step(pid: str, step: str) -> str:
        return tools.guide_step(cli, pid, step)

    @server.tool(name="steps", description="Catálogo das 10 etapas do método do curso, na ordem, com a aula de origem.")
    def steps() -> str:
        return tools.steps_catalog(cli)

    @server.tool(name="doctor", description="Saúde das ferramentas externas: Higgsfield (pago) e motor local (grátis).")
    def doctor() -> str:
        return tools.doctor(cli)

    @server.tool(name="job", description="Estado do job em andamento de uma etapa (geração/scraping): running/done/error + progresso.")
    def job(pid: str, step: str) -> str:
        return tools.job_status(cli, pid, step)

    @server.tool(name="api_get", description="Escape hatch SOMENTE-LEITURA: GET de qualquer rota /api/... do Studio, para inspecionar dados sem tool dedicada.")
    def api_get(path: str) -> Any:
        return tools.api_get(cli, path)

    return server


def run() -> None:
    """Entrypoint stdio (usado por `python -m studio.mcp`)."""
    build_server().run()
