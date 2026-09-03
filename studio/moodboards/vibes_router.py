"""Rotas do painel de fotos de vibe `[extensão]` (ADH-OS-20260902-03) — GLOBAIS, sem `pid`.

Router PRÓPRIO, incluído em `studio/moodboards/router.py` por duas linhas no fim do arquivo.
Três frentes da wave 10 acrescentam rotas àquele arquivo; manter cada conjunto no seu módulo
reduz a colisão a essas duas linhas (risco 3 do `recon-wave-10.md`).

Contrato completo e matriz de erros: `docs/domains/mood/features/painel-vibes-fdd.md` (seções 5 e 6).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import vibes

router = APIRouter(tags=["vibes"])


class SelectVibesReq(BaseModel):
    """Ids (nomes de arquivo) das fotos a copiar para a peneira. Sem teto de escolhidas (D5);
    `max_length` só protege contra body absurdo."""
    ids: list[str] = Field(min_length=1, max_length=vibes.MAX_SELECT_IDS)


@router.get("/api/vibes")
def vibes_list(
    page: int = Query(1, ge=1, description="1-based; além do fim devolve items vazio"),
    per_page: int = Query(vibes.MAX_PER_PAGE, ge=1, description=f"clampado a {vibes.MAX_PER_PAGE}"),
    vibe: str | None = Query(None, description="slug da vibe, de GET /api/vibes/facets"),
    origem: str | None = Query(None, description="catalogo | usuario | sugestao"),
):
    try:
        return vibes.list_vibes(page=page, per_page=per_page, vibe=vibe, origem=origem)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/vibes/facets")
def vibes_facets():
    return vibes.facets()


@router.post("/api/vibes/select")
def vibes_select(req: SelectVibesReq):
    """Copia (nunca move) para `_escolhidas/`, deduplicando por hash."""
    try:
        return vibes.select_photos(req.ids)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/escolhidas")
def escolhidas_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(vibes.MAX_PER_PAGE, ge=1),
):
    """A peneira. `total` é o contador que a feature 01 lê para habilitar o botão dela."""
    try:
        return vibes.list_chosen(page=page, per_page=per_page)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.delete("/api/escolhidas/{escolhida_id}")
def escolhidas_remove(escolhida_id: str):
    try:
        return vibes.remove_chosen(escolhida_id)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except KeyError as e:
        # KeyError sobe para o handler global de `app.py`, que responde "projeto não encontrado" —
        # mensagem errada aqui. Traduzir na borda é o que mantém o 404 honesto.
        raise HTTPException(404, f"foto escolhida não encontrada: {escolhida_id}") from e
