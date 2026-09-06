"""Resources do MCP (ADR-037, Onda E): conhecimento citável do assistente.

Resources são texto que o agente lê como referência (mais barato que uma tool por chamada). Aqui:
- `studio://help` — o método do curso e como conduzir cada etapa (fonte de verdade do assistente);
- `studio://help/<etapa>` — a dica curta de uma etapa (ou de uma ÁREA global, ver `HELP_AREAS`);
- `studio://project/<pid>/guide` — o guia AO VIVO da campanha (via a API, ADR-010).
"""
from __future__ import annotations

from . import tools
from .client import StudioClient

#: Dica curta por etapa (espelha o roteiro do prompt de sistema; fonte única do "como conduzir").
HELP: dict[str, str] = {
    "refs": "Aula 009. Sugira termos, busque no Pinterest (grátis) e deixe o usuário escolher as referências.",
    "mood": "Aula 009. UMA vibe única (luz/cor/atmosfera, sem pessoas). Gere o grid (pago, confirme o custo) e escolha até 8.",
    "base": "Aula 009. O produto na situação da referência, no mood. Gere (pago) e escolha a base final.",
    "storyboard": "Aulas 010/011. Explore keyframes no motor local (grátis) e escolha; cenas em texto.",
    "animate": "Aula 012. Anime cada take (pago, image-to-video), 2 takes, escolha o melhor.",
    "music": "Aula 013. Trilha por prompt (pago), escolha sentindo.",
    "edit": "Aula 014. Montagem por ffmpeg (grátis): cortes no ritmo, transições.",
    "export": "Aula 014. Formatos 16:9/9:16/1:1 + QA técnico (grátis).",
    "publish": "Aula 015. Registro dos posts; portfólio com 4 vídeos distintos.",
    "prospect": "Aula 001. Leads e DM com o script; teaser de 5–10 s.",
}

#: Dica curta por ÁREA global `[extensão]` — o que não é etapa do curso e não tem `pid` (ADR-013).
#: Fica FORA de `HELP` de propósito: `HELP_GERAL` monta a lista "Etapas:" a partir dele, e a
#: biblioteca de mood boards não é etapa. O resolvedor de `studio://help/{etapa}` consulta os dois.
HELP_AREAS: dict[str, str] = {
    "moodboards": (
        "Biblioteca de mood boards `[extensão]` (ADR-013): global, sem campanha. Um board é UMA vibe (até 8\n"
        "imagens curadas, ADR-007). Caminho: moodboard_create, moodboard_import (downloads|history),\n"
        "moodboard_pick (o usuário escolhe), moodboard_patch (grava a VIBE em palavras),\n"
        "moodboard_prompt, e mood_pull para semear a etapa 2 de uma\n"
        "campanha. Peneira de vibes: vibes_list, vibes_pick, escolhidas_list. Cadeia gratuita de skills:\n"
        "mood_run + mood_run_wait (demora minutos). Pago: moodboard_multishot (confirma o custo).\n"
        "Upload de arquivo é pela tela: o assistente nunca manipula bytes."
    ),
}

HELP_GERAL = (
    "Orquestrador Studio — método do curso 'O Orquestrador'. O assistente conduz a campanha do "
    "início ao fim, sempre pelo guia (tool `guide`/`guide_step`), deixando a escolha visual e o "
    "gasto com o usuário. Grátis na exploração (motor local), pago só na versão final (Higgsfield, "
    "com confirmação de custo). Etapas: "
    + " | ".join(f"{k}: {v}" for k, v in HELP.items())
    + " Fora das etapas há áreas globais `[extensão]`, sem campanha: a biblioteca de mood boards "
      "(`studio://help/moodboards`)."
)


def register_resources(server, client: StudioClient) -> None:
    @server.resource("studio://help")
    def help_geral() -> str:
        return HELP_GERAL

    @server.resource("studio://help/{etapa}")
    def help_etapa(etapa: str) -> str:
        """Dica de uma etapa do curso ou de uma área global (`HELP` primeiro, `HELP_AREAS` depois).

        Um resolvedor só, sem resource concreto por área: assim a resposta não depende da ordem em
        que o FastMCP casa um resource literal com este template.
        """
        if etapa in HELP:
            return HELP[etapa]
        if etapa in HELP_AREAS:
            return HELP_AREAS[etapa]
        return (f"Tópico desconhecido: {etapa}. Etapas: {', '.join(HELP)}. "
                f"Áreas globais: {', '.join(HELP_AREAS)}.")

    @server.resource("studio://project/{pid}/guide")
    def project_guide(pid: str) -> str:
        return tools.guide_overview(client, pid)

    @server.resource("studio://credits")
    def creditos() -> str:
        """`[extensão]` wave 11: saldo e gasto no escopo global, com o porquê de não baterem."""
        return tools.credits_status(client)
