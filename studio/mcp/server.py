"""Servidor MCP stdio do Studio (ADR-037): registra as tools de `tools.py`, `actions.py` e `ui.py`.

Rode com `python -m studio.mcp`. O nome do servidor é `studio`, então as tools chegam ao agente
como `mcp__studio__<nome>`. Um único cliente HTTP (loopback) é compartilhado por todas.

O import do `mcp` é tardio (dentro de `build_server`) para que as funções puras e os testes não
dependam do pacote `mcp` instalado.
"""
from __future__ import annotations

from typing import Any

from . import actions, tools, ui
from .client import StudioClient


def build_server(client: StudioClient | None = None):
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("studio")
    cli = client or StudioClient()
    t = server.tool

    # ---------- leitura (Onda A) ----------
    @t(name="projects", description="Lista as campanhas (projetos de vídeo) existentes.")
    def projects() -> str:
        return tools.projects_list(cli)

    @t(name="project", description="Detalhe de uma campanha: nome, produto, vibe, formato, progresso e etapa atual.")
    def project(pid: str) -> str:
        return tools.project_get(cli, pid)

    @t(name="guide", description="Panorama das 10 etapas da campanha: status, progresso e etapa atual. Use para 'o que falta'.")
    def guide(pid: str) -> str:
        return tools.guide_overview(cli, pid)

    @t(name="guide_step", description="Detalhe de uma etapa: o que a aula manda, o que falta, validações e próxima ação. Use para 'por que está bloqueada'.")
    def guide_step(pid: str, step: str) -> str:
        return tools.guide_step(cli, pid, step)

    @t(name="steps", description="Catálogo das 10 etapas do método do curso, na ordem, com a aula de origem.")
    def steps() -> str:
        return tools.steps_catalog(cli)

    @t(name="doctor", description="Saúde das ferramentas externas: Higgsfield (pago) e motor local (grátis).")
    def doctor() -> str:
        return tools.doctor(cli)

    @t(name="job", description="Estado atual (sem esperar) do job de uma etapa: running/done/error + progresso.")
    def job(pid: str, step: str) -> str:
        return tools.job_status(cli, pid, step)

    @t(name="job_wait", description="Espera o job de uma etapa terminar (até `timeout` s) e devolve o resumo. Use após disparar geração/busca.")
    def job_wait(pid: str, step: str, timeout: int = 600) -> str:
        return tools.job_wait(cli, pid, step, timeout=timeout)

    @t(name="api_get", description="Escape hatch SOMENTE-LEITURA: GET de qualquer rota /api/... do Studio.")
    def api_get(path: str) -> Any:
        return tools.api_get(cli, path)

    # ---------- ações: 1 Referências ----------
    @t(name="refs_suggest_terms", description="Sugere termos de busca de referências no Pinterest a partir do produto/vibe/marca.")
    def refs_suggest_terms(product: str = "", vibe: str = "", brand: str = "", pid: str = "") -> str:
        return actions.refs_suggest_terms(cli, product, vibe, brand, pid)

    @t(name="refs_search", description="Busca e baixa referências no Pinterest para os termos dados (grátis, assíncrono).")
    def refs_search(pid: str, terms: list[str], max_per_term: int = 30) -> str:
        return actions.refs_search(cli, pid, terms, max_per_term)

    @t(name="refs_pick", description="Mostra as referências baixadas para o USUÁRIO escolher e salva a seleção (etapa 1).")
    def refs_pick(pid: str) -> str:
        return actions.refs_pick(cli, pid)

    # ---------- ações: 2 Mood board ----------
    @t(name="mood_prompt", description="Escreve o prompt de vibe da campanha (bot da aula 009). mode: brief|images.")
    def mood_prompt(pid: str, mode: str = "brief", instruction: str = "", purpose: str = "",
                    tone: str = "", reference: str = "") -> str:
        return actions.mood_prompt(cli, pid, mode, instruction, purpose, tone, reference)

    @t(name="mood_generate", description="Gera o grid de mood (PAGO — Higgsfield). Confirma o custo com o usuário antes.")
    def mood_generate(pid: str, prompts: list[str], count: int = 2, model: str = "nano_banana_2",
                      confirm: bool = False) -> str:
        return actions.mood_generate(cli, pid, prompts, count, model, confirm=confirm)

    @t(name="mood_pick", description="Mostra as imagens de mood para o USUÁRIO escolher (mesma vibe, até 8) e aplica.")
    def mood_pick(pid: str, note: str = "") -> str:
        return actions.mood_pick(cli, pid, note)

    # ---------- ações: 3 Imagem base ----------
    @t(name="base_prompt", description="Escreve o prompt da imagem base (produto na situação da referência + mood).")
    def base_prompt(pid: str, ref_id: str = "", mode: str = "images", instruction: str = "") -> str:
        return actions.base_prompt(cli, pid, ref_id or None, mode, instruction)

    @t(name="base_generate", description="Gera a imagem base (PAGO). kind: situation|label|upscale. Confirma o custo antes.")
    def base_generate(pid: str, kind: str = "situation", prompt: str = "", count: int = 0,
                      model: str = "", confirm: bool = False) -> str:
        return actions.base_generate(cli, pid, kind, prompt, count or None, model or None, confirm=confirm)

    @t(name="base_pick", description="Mostra as candidatas de base para o USUÁRIO escolher a final (uma) e salva.")
    def base_pick(pid: str, note: str = "") -> str:
        return actions.base_pick(cli, pid, note)

    # ---------- ações: 4 Storyboard (motor local grátis) ----------
    @t(name="storyboard_local_generate", description="Gera keyframes do storyboard no motor LOCAL (grátis, Flux). Prompt em inglês.")
    def storyboard_local_generate(pid: str, prompt: str, count: int = 4, model: str = "flux-schnell") -> str:
        return actions.storyboard_local_generate(cli, pid, prompt, count, model)

    @t(name="storyboard_pick", description="Mostra os keyframes gerados para o USUÁRIO escolher e salva a seleção.")
    def storyboard_pick(pid: str) -> str:
        return actions.storyboard_pick(cli, pid)

    @t(name="storyboard_scenes", description="Lista as cenas em texto do storyboard.")
    def storyboard_scenes(pid: str) -> str:
        return actions.storyboard_scenes(cli, pid)

    # ---------- ações: 5-9 ----------
    @t(name="animate_shots", description="Lista os shots prontos para animar (etapa 5).")
    def animate_shots(pid: str) -> str:
        return actions.animate_shots(cli, pid)

    @t(name="animate_generate", description="Anima um take de um shot (PAGO, image-to-video). Confirma o custo antes.")
    def animate_generate(pid: str, scene: str, shot: str, model: str = "kling3_0", count: int = 2,
                         prompt: str = "", confirm: bool = False) -> str:
        return actions.animate_generate(cli, pid, scene, shot, model, count, prompt, confirm=confirm)

    @t(name="music_generate", description="Gera a trilha por prompt (PAGO — sonilo_music). Confirma o custo antes.")
    def music_generate(pid: str, prompt: str, duration: int = 30, confirm: bool = False) -> str:
        return actions.music_generate(cli, pid, prompt, duration, confirm=confirm)

    @t(name="edit_render", description="Renderiza o master da montagem por ffmpeg (grátis). Acompanhe com job_wait.")
    def edit_render(pid: str) -> str:
        return actions.edit_render(cli, pid)

    @t(name="export_render", description="Exporta os formatos finais (16x9/9x16/1x1) por ffmpeg (grátis).")
    def export_render(pid: str, formats: list[str] = []) -> str:  # noqa: B006
        return actions.export_render(cli, pid, formats or None)

    @t(name="export_qa", description="Roda o QA técnico do export (checklist, sem juízo estético).")
    def export_qa(pid: str) -> str:
        return actions.export_qa(cli, pid)

    @t(name="portfolio", description="Estado do portfólio (contagem de vídeos distintos publicados).")
    def portfolio() -> str:
        return actions.portfolio(cli)

    # ---------- ui.* (humano-no-laço, ADR-038) ----------
    @t(name="ui_choose_one", description="Pede ao usuário que escolha UMA opção. options: [{label,value}].")
    def ui_choose_one(title: str, options: list[dict]) -> dict:
        return ui.choose_one(cli, title, options)

    @t(name="ui_confirm", description="Pede uma confirmação sim/não ao usuário antes de uma ação relevante.")
    def ui_confirm(title: str, detail: str = "") -> dict:
        return ui.confirm(cli, title, detail)

    @t(name="ui_notify", description="Mostra um aviso curto ao usuário no chat (não espera resposta).")
    def ui_notify(text: str, level: str = "info") -> str:
        return ui.notify(cli, text, level)

    @t(name="ui_show", description="Mostra mídia no chat. images: [{url,label?,kind?}] (url servível, ex.: /files/<pid>/...).")
    def ui_show(images: list[dict], title: str = "") -> str:
        return ui.show(cli, images, title)

    @t(name="ui_open", description="Pede ao usuário para abrir uma tela do Studio (ex.: 'storyboard') e concluir a edição fina lá (máscara, timeline). target = id da etapa.")
    def ui_open(target: str, title: str = "", detail: str = "", label: str = "") -> dict:
        return ui.open_screen(cli, target, title, detail, label)

    return server


def run() -> None:
    """Entrypoint stdio (usado por `python -m studio.mcp`)."""
    build_server().run()
