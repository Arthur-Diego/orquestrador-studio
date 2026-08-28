"""Rotas da etapa 9 — Publicar (aula 015).

O núcleo converte `KeyError` (projeto ou post inexistente) em 404. Aqui só traduzimos
`FileNotFoundError` (vídeo fora de `export/`) em 404 e `ValueError` (validação) em 422.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...publish import service as publish

router = APIRouter(tags=["publish"])


class PostReq(BaseModel):
    video: str
    network: str
    url: str
    posted_at: str | None = None
    note: str = ""


class FeedbackReq(BaseModel):
    feedback: str = ""     # ausente ou "" limpa o feedback (é como a tela apaga um texto errado)


class CommunityReq(BaseModel):
    """Checklist de comunidade da aula 015. Campo ausente (`None`) não muda o item."""
    posted: bool | None = None
    commented: bool | None = None
    feedback: bool | None = None


@router.get("/api/portfolio")
def portfolio_global():
    """Portfólio da aula 015 — **projetos distintos** com post registrado (ADR-012).

    Rota sem `pid` de propósito: o dever de casa é ter quatro obras publicadas, e nenhuma delas
    mora no projeto onde a prospecção acontece. `prospect.gate` consome exatamente isto.
    """
    return publish.global_portfolio()


@router.get("/api/projects/{pid}/publish/exports")
def publish_exports(pid: str):
    """Arquivos de `export/` prontos para postar, com flag `published`."""
    return publish.list_exports(pid)


@router.get("/api/projects/{pid}/publish/log")
def publish_log(pid: str):
    """`distinct_videos` vai junto de propósito: `count >= goal` é a leitura que a decisão 1 proíbe."""
    posts = publish.load_log(pid)
    return {"posts": posts, "count": len(posts),
            "distinct_videos": len({p["video"] for p in posts if p["video"]}),
            "goal": publish.PORTFOLIO_GOAL}


@router.post("/api/projects/{pid}/publish/log", status_code=201)
def publish_add(pid: str, req: PostReq):
    try:
        return publish.add_post(pid, req.video, req.network, req.url, req.posted_at, req.note)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/api/projects/{pid}/publish/log/{post_id}/feedback")
def publish_feedback(pid: str, post_id: str, req: FeedbackReq):
    return publish.set_feedback(pid, post_id, req.feedback)


@router.delete("/api/projects/{pid}/publish/log/{post_id}")
def publish_remove(pid: str, post_id: str):
    return {"removed": post_id, "count": publish.remove_post(pid, post_id)}


@router.get("/api/projects/{pid}/publish/portfolio")
def publish_portfolio(pid: str):
    """Contadores deste projeto + do portfólio global (`ready` vem do global, ADR-012)."""
    return publish.portfolio_status(pid)


@router.get("/api/projects/{pid}/publish/community")
def publish_community(pid: str):
    """Checklist de comunidade (aula 015). Nunca bloqueia — é lembrete de prática."""
    return publish.load_community(pid)


@router.post("/api/projects/{pid}/publish/community")
def publish_set_community(pid: str, req: CommunityReq):
    return publish.set_community(pid, **req.model_dump())
