"""Guia da etapa 10 (aula 015) — leitura pura dos artefatos do projeto.

O dever de casa da aula é *"criar pelo menos quatro vídeos e publicá-los"*: quatro **obras**,
não quatro arquivos do mesmo comercial. Por isso a saída "portfólio" é global (ADR-012) e é
lida de `PROJECTS_DIR` — a única leitura deste guia que sai da pasta do projeto, e ainda assim
leitura pura (nenhuma escrita, nenhum CLI).
"""
from __future__ import annotations

from ...common.guide import Guide, count_files
from ...publish import service as publish
from . import META

WHAT = (
    "Publique o vídeo — num perfil novo ou nas redes que você já tem — e registre aqui o link. "
    "O dever de casa da aula é ter pelo menos quatro vídeos publicados antes de procurar "
    "clientes: eles não são para perfeição, são para prática, exposição e validação. "
    "Compartilhar é o que permite feedback e evolução (aula 014); o primeiro trabalho tende a "
    "ser o pior, e isso é normal. Participe da comunidade ABRAhub: interagir, postar, comentar "
    "e dar feedback é como você passa a ser notado — e a própria comunidade já pode gerar "
    "oportunidades."
)
CHECKLIST = [
    "Publiquei mesmo imperfeito.",
    "Postei também na comunidade e interagi (comentei, dei feedback).",
    "Registrei o link e o que aprendi com este vídeo.",
    "Portfólio: quatro vídeos diferentes publicados (projetos distintos).",
]


def guide(pid: str) -> dict:
    posts = publish.load_log(pid)
    exports = count_files(pid, "export", {".mp4"})
    status = publish.portfolio_status(pid)
    glob_n, goal = status["distinct_videos"], status["goal"]
    videos = status["videos"]
    com = status["community"]

    g = Guide(META).text(WHAT, CHECKLIST)

    g.input("exports", "export/*.mp4 (etapa 9)", exports > 0,
            detail=f"{exports} arquivo(s) em export/",
            fix="Volte à etapa 9 e gere o formato da rede onde você vai publicar", step="export")

    g.output("post", "Este vídeo publicado e registrado", bool(posts),
             detail=f"{len(posts)} publicação(ões) neste projeto" if posts
             else "poste na rede e cole o link aqui")
    g.output("portfolio", f"Portfólio global {glob_n}/{goal} vídeos", status["ready"],
             detail=(f"{glob_n} projeto(s) com post registrado"
                     + ("" if status["ready"] else f" — {status['missing']} para destravar a etapa 11")))

    if videos > 1:
        g.check("mesmo_projeto", "Formatos do mesmo comercial contam como 1 vídeo", "warn",
                detail=f"{videos} arquivos deste projeto registrados",
                fix="a aula pede quatro obras diferentes: crie outro projeto para o próximo vídeo")
    elif videos == 1:
        g.check("mesmo_projeto", "Este projeto conta como 1 vídeo do portfólio", "ok")
    else:
        g.check("mesmo_projeto", "Este projeto ainda não conta no portfólio", "todo")

    g.check("comunidade", "Comunidade ABRAhub: postei, comentei, dei feedback",
            "ok" if com["done"] == com["total"] else ("warn" if com["done"] else "todo"),
            detail=f"{com['done']}/{com['total']} itens",
            fix=None if com["done"] == com["total"] else
            "interagir, postar, comentar e dar feedback é como você passa a ser notado (aula 015)")

    sem_nota = [p for p in posts if not (p["note"] or p["feedback"])]
    if not posts:
        g.check("feedback", "Nota ou feedback em cada post (aula 014)", "todo")
    elif sem_nota:
        g.check("feedback", "Nota ou feedback em cada post (aula 014)", "warn",
                detail=f"{len(sem_nota)} post(s) sem nota nem feedback",
                fix="anote o que você testou e o que ouviu — é assim que a repetição vira evolução")
    else:
        g.check("feedback", "Nota ou feedback em cada post (aula 014)", "ok")

    registrados = {p["video"] for p in posts if p["video"]}
    presentes = {f["file"] for f in publish.list_exports(pid)["files"]}
    orfaos = sorted(registrados - presentes)
    if not posts:
        g.check("arquivos", "Todo post aponta para um arquivo de export/", "todo")
    elif orfaos:
        g.check("arquivos", "Todo post aponta para um arquivo de export/", "warn",
                detail=f"não estão mais em export/: {', '.join(orfaos)}")
    else:
        g.check("arquivos", "Todo post aponta para um arquivo de export/", "ok")

    return g.build()
