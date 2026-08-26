"""Rotas da etapa 11 — Prospecção (aula 001).

Tradução de exceções do serviço (padrão das outras etapas): `FileNotFoundError` → 404,
`ValueError` → 422, `RuntimeError` (inclui `GateClosed` e job em andamento) → 409.
`KeyError` de projeto vira 404 no núcleo.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...prospect import service as prospect
from ...refs import service as refs

router = APIRouter(tags=["prospect"])


@contextmanager
def _translated():
    try:
        yield
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:      # GateClosed, ffmpeg ausente, job em andamento
        raise HTTPException(409, str(e)) from e


def _project(pid: str) -> tuple[Path, dict]:
    root = refs.project_dir(pid)
    meta = json.loads((root / "project.json").read_text(encoding="utf-8"))
    return root, meta


class LeadIn(BaseModel):
    business: str
    handle: str
    post_ref: str = ""
    why: str = ""
    role: str = "fã"


class LeadPatch(BaseModel):
    business: str | None = None
    handle: str | None = None
    post_ref: str | None = None
    why: str | None = None
    role: str | None = None


class SentIn(BaseModel):
    sent_at: str | None = None


class RepliedIn(BaseModel):
    replied: bool = True


class TeaserIn(BaseModel):
    take: dict | None = None
    duration: float = prospect.DEFAULT_TEASER
    take_offset: float = 0.0
    #: Ausente = sugestão do primeiro impacto da trilha (11.8); número explícito manda.
    music_offset: float | None = None


class PitchIn(BaseModel):
    """Ancoragem da call: valor por etapa e o total que você quer cobrar (aula 001)."""
    values: dict[str, float] | None = None
    total: float | None = None


class CallIn(BaseModel):
    call_at: str
    done: bool = False
    note: str = ""


def _counters(root: Path) -> dict:
    leads = prospect.load_leads(root)
    return {"today_sent": prospect.today_sent(leads), "daily_limit": prospect.DAILY_LIMIT}


# ---------- gate ----------
@router.get("/api/projects/{pid}/prospect/gate")
def prospect_gate(pid: str):
    root = refs.project_dir(pid)
    with _translated():
        return {**prospect.gate(root), **_counters(root)}


# ---------- leads ----------
@router.get("/api/projects/{pid}/prospect/leads")
def prospect_leads(pid: str):
    root = refs.project_dir(pid)
    with _translated():
        leads = prospect.load_leads(root)
        return {"leads": leads, "today_sent": prospect.today_sent(leads), "daily_limit": prospect.DAILY_LIMIT,
                "by_status": prospect.by_status(leads), "gate": prospect.gate(root),
                "segments": list(prospect.SEGMENTS),
                "teaser_hint": prospect.suggest_music_offset(root)}


@router.post("/api/projects/{pid}/prospect/leads")
def prospect_create_lead(pid: str, req: LeadIn):
    root = refs.project_dir(pid)
    with _translated():
        return prospect.create_lead(root, req.business, req.handle, req.post_ref, req.why, req.role)


@router.get("/api/projects/{pid}/prospect/leads/{lid}")
def prospect_lead(pid: str, lid: str):
    root = refs.project_dir(pid)
    with _translated():
        return prospect.get_lead(root, lid)


@router.put("/api/projects/{pid}/prospect/leads/{lid}")
def prospect_update_lead(pid: str, lid: str, req: LeadPatch):
    root = refs.project_dir(pid)
    with _translated():
        return prospect.update_lead(root, lid, **req.model_dump(exclude_unset=True))


@router.delete("/api/projects/{pid}/prospect/leads/{lid}")
def prospect_delete_lead(pid: str, lid: str):
    root = refs.project_dir(pid)
    with _translated():
        prospect.delete_lead(root, lid)
        return {"removed": True}


# ---------- DM ----------
@router.get("/api/projects/{pid}/prospect/leads/{lid}/dm")
def prospect_dm(pid: str, lid: str):
    root = refs.project_dir(pid)
    with _translated():
        text = prospect.get_lead(root, lid).get("dm_text") or ""
        return {"text": text, "chars": len(text)}


@router.post("/api/projects/{pid}/prospect/leads/{lid}/sent")
def prospect_mark_sent(pid: str, lid: str, req: SentIn | None = None):
    root = refs.project_dir(pid)
    with _translated():
        lead = prospect.mark_sent(root, lid, (req or SentIn()).sent_at)
        counters = _counters(root)
        return {"lead": lead, **counters, "over_limit": counters["today_sent"] > prospect.DAILY_LIMIT}


@router.post("/api/projects/{pid}/prospect/leads/{lid}/replied")
def prospect_mark_replied(pid: str, lid: str, req: RepliedIn | None = None):
    root = refs.project_dir(pid)
    with _translated():
        return prospect.mark_replied(root, lid, (req or RepliedIn()).replied)


# ---------- teaser ----------
@router.post("/api/projects/{pid}/prospect/leads/{lid}/teaser")
def prospect_teaser(pid: str, lid: str, req: TeaserIn | None = None):
    root = refs.project_dir(pid)
    r = req or TeaserIn()
    with _translated():
        return prospect.start_teaser(root, pid, lid, r.take, r.duration, r.take_offset, r.music_offset)


@router.get("/api/projects/{pid}/prospect/job")
def prospect_job(pid: str):
    refs.project_dir(pid)
    return prospect.job_status(pid)


# ---------- follow-up e call ----------
@router.get("/api/projects/{pid}/prospect/leads/{lid}/followup")
def prospect_followup(pid: str, lid: str):
    root = refs.project_dir(pid)
    with _translated():
        lead = prospect.get_lead(root, lid)
        return {"text": prospect.followup_text(), "teaser": lead.get("teaser")}


@router.post("/api/projects/{pid}/prospect/leads/{lid}/call")
def prospect_call(pid: str, lid: str, req: CallIn):
    root = refs.project_dir(pid)
    with _translated():
        return prospect.register_call(root, lid, req.call_at, req.done, req.note)


# ---------- pitch ----------
@router.get("/api/projects/{pid}/prospect/pitch")
def prospect_pitch(pid: str):
    root, meta = _project(pid)
    with _translated():
        markdown = prospect.read_pitch(root, meta)
        return {"file": "prospect/pitch.md", "markdown": markdown, **prospect.load_pitch_values(root),
                "steps": prospect.PITCH_STEPS, "min_price": prospect.MIN_PRICE, "max_price": prospect.MAX_PRICE}


@router.post("/api/projects/{pid}/prospect/pitch")
def prospect_write_pitch(pid: str, req: PitchIn | None = None):
    """Grava os valores por etapa (quando vierem) e regrava `prospect/pitch.md`."""
    root, meta = _project(pid)
    body = req or PitchIn()
    with _translated():
        prospect.require_gate(root)
        if body.values is not None or body.total is not None:
            prospect.save_pitch_values(root, body.values, body.total)
        prospect.write_pitch(root, meta)
        pitch = prospect.load_pitch_values(root)
        return {"file": "prospect/pitch.md", "markdown": prospect.pitch_markdown(meta, pitch), **pitch,
                "steps": prospect.PITCH_STEPS, "min_price": prospect.MIN_PRICE, "max_price": prospect.MAX_PRICE}
