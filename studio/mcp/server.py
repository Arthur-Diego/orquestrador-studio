"""Servidor MCP stdio do Studio (ADR-037): registra as tools de `tools.py`, `actions.py` e `ui.py`.

Rode com `python -m studio.mcp`. O nome do servidor é `studio`, então as tools chegam ao agente
como `mcp__studio__<nome>`. Um único cliente HTTP (loopback) é compartilhado por todas.

O import do `mcp` é tardio (dentro de `build_server`) para que as funções puras e os testes não
dependam do pacote `mcp` instalado.
"""
from __future__ import annotations

from typing import Any

from . import actions, resources, tools, ui
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

    @t(name="credits_status", description="Saldo de créditos da Higgsfield, plano e gasto já registrado (hoje, campanha, total) com os últimos gastos. Somente leitura, não gasta nada.")
    def credits_status(pid: str = "") -> str:
        return tools.credits_status(cli, pid)

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

    # `[extensão]` geração POR CENA (ângulos da aula 011 e cena do produto da aula 013).
    @t(name="storyboard_scene_generate", description="Gera a imagem/os ângulos de UMA cena (cena01… ou 'product'). engine='local' é GRÁTIS (motor local); engine='cli' é PAGO (Higgsfield) e confirma o custo antes.")
    def storyboard_scene_generate(pid: str, scene: str, engine: str = "local", prompt: str = "",
                                  count: int = 4, model: str = "", confirm: bool = False) -> str:
        return actions.storyboard_scene_generate(cli, pid, scene, engine, prompt, count, model,
                                                 confirm=confirm)

    @t(name="storyboard_scene_pick", description="Mostra os candidatos de UMA cena para o USUÁRIO escolher e ORDENAR os frames (shot01, shot02…) e salva a ordem.")
    def storyboard_scene_pick(pid: str, scene: str) -> str:
        return actions.storyboard_scene_pick(cli, pid, scene)

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

    # ---------- ações: biblioteca de mood boards `[extensão]` (ADR-013) ----------
    @t(name="moodboard_list", description="Lista os mood boards da biblioteca (global, sem campanha). Comece por aqui; depois `moodboard_get`.")
    def moodboard_list() -> str:
        return actions.moodboard_list(cli)

    @t(name="moodboard_get", description="Detalhe de um mood board: vibe, nota, paleta, prompt e as candidatas a curar. Depois use `moodboard_pick`.")
    def moodboard_get(mbid: str) -> str:
        return actions.moodboard_get(cli, mbid)

    @t(name="moodboard_create", description="Cria um mood board na biblioteca (uma vibe só, ADR-007). Depois use `moodboard_import`.")
    def moodboard_create(name: str, note: str = "") -> str:
        return actions.moodboard_create(cli, name, note)

    @t(name="moodboard_patch", description="Edita os metadados de um mood board: name (só o rótulo — o id não muda), note e vibe. É a única forma de gravar a VIBE em palavras, que `mood_pull` leva para a campanha.")
    def moodboard_patch(mbid: str, name: str = "", note: str = "", vibe: str = "") -> str:
        return actions.moodboard_patch(cli, mbid, name, note, vibe)

    @t(name="moodboard_import", description="Importa candidatas para o board a partir da pasta Downloads ou do histórico da Higgsfield. source: downloads|history (upload é só pela tela). Depois use `moodboard_pick`.")
    def moodboard_import(mbid: str, source: str = "downloads", since_minutes: int = 120) -> str:
        return actions.moodboard_import(cli, mbid, source, since_minutes)

    @t(name="moodboard_pick", description="Mostra as candidatas do board para o USUÁRIO escolher (até 8) e salva a curadoria + a paleta. Depois use `moodboard_prompt` ou `mood_pull`.")
    def moodboard_pick(mbid: str, note: str = "") -> str:
        return actions.moodboard_pick(cli, mbid, note)

    @t(name="moodboard_prompt", description="Escreve o prompt de vibe do board a partir das imagens curadas (grátis). mode: template|brief|images.")
    def moodboard_prompt(mbid: str, mode: str = "images", instruction: str = "",
                         no_people: bool = True) -> str:
        return actions.moodboard_prompt(cli, mbid, mode, instruction, no_people)

    @t(name="moodboard_delete", description="Apaga um mood board da biblioteca (irreversível). Confirma com o usuário antes; no terminal exige confirm=true.")
    def moodboard_delete(mbid: str, confirm: bool = False) -> str:
        return actions.moodboard_delete(cli, mbid, confirm)

    @t(name="vibes_list", description="Lista o catálogo de fotos de vibe (global) com as vibes disponíveis e quantas já estão na peneira. Filtros: vibe (slug), origem (catalogo|usuario|sugestao).")
    def vibes_list(vibe: str = "", origem: str = "", page: int = 1) -> str:
        return actions.vibes_list(cli, vibe, origem, page)

    @t(name="vibes_pick", description="Mostra as fotos de vibe para o USUÁRIO escolher e copia as escolhidas para a peneira (`_escolhidas/`). Depois use `escolhidas_list`.")
    def vibes_pick(vibe: str = "", origem: str = "", page: int = 1) -> str:
        return actions.vibes_pick(cli, vibe, origem, page)

    @t(name="escolhidas_list", description="Lista a peneira de fotos escolhidas com o caminho absoluto de cada uma — é esse caminho que vai em `mood_run(foto=...)`.")
    def escolhidas_list(page: int = 1) -> str:
        return actions.escolhidas_list(cli, page)

    @t(name="mood_run", description="Roda a cadeia de skills mood_ sobre uma foto-semente da peneira e monta pranchas no board. GRÁTIS em crédito, mas baixa dezenas de imagens e leva vários minutos: estima e confirma antes; no terminal exige confirm=true. Depois use `mood_run_wait`.")
    def mood_run(mbid: str, foto: str = "", objetivos: list[str] | None = None,
                 board: int | None = None, n: int | None = None, fundo: str = "",
                 confirm: bool = False) -> str:
        return actions.mood_run(cli, mbid, foto, objetivos, board, n, fundo, confirm)

    @t(name="mood_run_wait", description="Espera a corrida de mood do board terminar e mostra as pranchas no chat. USE ESTA, não `job_wait` — a URL do job da corrida é própria.")
    def mood_run_wait(mbid: str, timeout: int = 1800) -> str:
        return actions.mood_run_wait(cli, mbid, timeout=timeout)

    @t(name="moodboard_multishot", description="Gera ângulos novos de uma candidata do board (PAGA — Higgsfield, ADR-017). Estima e confirma o custo com o usuário antes; no terminal exige confirm=true. Depois use `moodboard_multishot_wait`.")
    def moodboard_multishot(mbid: str, source_id: str, count: int = 4, model: str = "",
                            confirm: bool = False) -> str:
        return actions.moodboard_multishot(cli, mbid, source_id, count, model, confirm=confirm)

    @t(name="moodboard_multishot_wait", description="Espera o multishot do board terminar e relata quantas candidatas novas entraram. USE ESTA, não `job_wait` — a URL do job do multishot é própria.")
    def moodboard_multishot_wait(mbid: str, timeout: int = 600) -> str:
        return actions.moodboard_multishot_wait(cli, mbid, timeout=timeout)

    @t(name="mood_pull", description="Puxa um mood board da biblioteca para a etapa 2 de uma campanha (grátis): copia as imagens curadas, a paleta e a vibe. A cópia é independente do board; confira a prontidão com `guide_step`.")
    def mood_pull(pid: str, mbid: str) -> str:
        return actions.mood_pull(cli, pid, mbid)

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

    # ---------- personagem e identidade (ADR-039) ----------
    @t(name="character_list", description="Lista os personagens da biblioteca (identidade reutilizável entre campanhas).")
    def character_list() -> str:
        return actions.character_list(cli)

    @t(name="character_create", description="Cria um personagem novo. style: foto|anime|3d.")
    def character_create(name: str, style: str = "foto") -> str:
        return actions.character_create(cli, name, style)

    @t(name="character_explore", description="Explora variações do personagem no motor LOCAL (grátis) a partir de um brief em inglês.")
    def character_explore(cid: str, brief: str, count: int = 6) -> str:
        return actions.character_explore(cli, cid, brief, count)

    @t(name="character_pick", description="Mostra as variações para o USUÁRIO escolher o personagem e o fixa (gera o descritor de identidade).")
    def character_pick(cid: str) -> str:
        return actions.character_pick(cli, cid)

    @t(name="character_sheet", description="Gera o character sheet (frente/3-4/perfil/corpo) no motor local, ancorado no descritor.")
    def character_sheet(cid: str) -> str:
        return actions.character_sheet(cli, cid)

    @t(name="character_wait", description="Espera o job de um personagem (explore/sheet) terminar. USE ESTA (não job_wait) para personagem — a URL do job é própria.")
    def character_wait(cid: str, timeout: int = 900) -> str:
        return actions.character_wait(cli, cid, timeout=timeout)

    @t(name="character_apply", description="Aplica o personagem a uma campanha: o descritor passa a reancorar os prompts das etapas 3–5.")
    def character_apply(pid: str, cid: str) -> str:
        return actions.character_apply(cli, pid, cid)

    @t(name="character_bind_soul", description="Treina um Soul ID (Higgsfield, PAGO, plano Basic+) para identidade fiel em foto/vídeo. Confirma antes.")
    def character_bind_soul(cid: str, variant: str = "soul-2") -> str:
        return actions.character_bind_soul(cli, cid, variant)

    @t(name="character_score", description="Nota de identidade (similaridade facial) entre o personagem fixado e uma candidata (motor local, opcional).")
    def character_score(cid: str, candidate_id: str, step: str = "explore") -> str:
        return actions.character_score(cli, cid, candidate_id, step)

    # ---------- resources de conhecimento (ADR-037, Onda E) ----------
    resources.register_resources(server, cli)

    return server


def run() -> None:
    """Entrypoint stdio (usado por `python -m studio.mcp`)."""
    build_server().run()
