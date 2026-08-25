"""Rotas da etapa 8 — Montagem no ritmo (aula 014)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from ...common import ffmpeg as ff
from ...edit import render
from ...edit import service as edit
from ...refs import service as refs

router = APIRouter(tags=["edit"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
NO_FFMPEG = "ffmpeg não disponível — instale em ~/.local/bin para renderizar e exportar o último frame"


class ClipReq(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    scene: str = ""
    shot: str = ""
    take: str = ""
    file: str
    start: float = Field(0.0, alias="in")
    out: float
    speed: float = 1.0
    blend: bool = True
    zoom: float = 1.0          # aula 014: "pequenos zooms" (1.0–1.3)


class BlackReq(BaseModel):
    at: float
    dur: float = edit.DEFAULT_BLACK_DUR


class MusicReq(BaseModel):
    file: str | None = None
    offset: float = 0.0


class SfxReq(BaseModel):
    file: str
    at: float = 0.0
    gain: float = 0.0


class TimelineReq(BaseModel):
    clips: list[ClipReq] = []
    blacks: list[BlackReq] = []
    music: MusicReq = MusicReq()
    sfx: list[SfxReq] = []
    fade_out: float = edit.DEFAULT_FADE_OUT
    loudnorm: bool = True      # [extensão]: a aula 014 não fala de loudness (auditoria 8.4)


class ProposeReq(BaseModel):
    offset: float | None = None
    black_dur: float = edit.PROPOSE_BLACK_DUR    # 0 = corte seco; o preto é escolha por corte
    apply: bool = False


class LastFrameReq(BaseModel):
    scene: str
    shot: str
    take: str | None = None


class RenderReq(BaseModel):
    target: str = "master"


def _translate(e: Exception) -> HTTPException:
    if isinstance(e, FileNotFoundError):
        return HTTPException(404, str(e))
    return HTTPException(422, str(e))


@router.get("/api/edit/ffmpeg")
def ffmpeg_status():
    """A UI usa isto para o chip de aviso: sem ffmpeg a etapa segue editável, só o render trava."""
    return {"available": ff.available()}


@router.get("/api/projects/{pid}/edit/timeline")
def get_timeline(pid: str):
    """Devolve a timeline; cria a inicial a partir de takes.json + storyboard.json na primeira vez."""
    try:
        return edit.get_timeline(pid)
    except (FileNotFoundError, ValueError) as e:
        raise _translate(e) from e


@router.put("/api/projects/{pid}/edit/timeline")
def put_timeline(pid: str, req: TimelineReq):
    root = refs.project_dir(pid)
    try:
        timeline = edit.save_timeline(pid, req.model_dump(by_alias=True))
    except (FileNotFoundError, ValueError) as e:
        raise _translate(e) from e
    return {"created": False, "duration": edit.timeline_duration(timeline),
            "timeline": edit.decorate(root, timeline)}


@router.post("/api/projects/{pid}/edit/timeline/reset")
def reset_timeline(pid: str):
    """Recria a timeline inicial — usar depois de gerar takes novos na etapa 6."""
    try:
        return edit.get_timeline(pid, force_new=True)
    except (FileNotFoundError, ValueError) as e:
        raise _translate(e) from e


@router.post("/api/projects/{pid}/edit/propose-cuts")
def propose_cuts(pid: str, req: ProposeReq):
    """Aula 014: cada corte cai num impacto da trilha (corte seco; o preto é opcional, por corte)."""
    try:
        return edit.propose_cuts(pid, req.offset, req.black_dur, req.apply)
    except (FileNotFoundError, ValueError) as e:
        raise _translate(e) from e


@router.post("/api/projects/{pid}/edit/last-frame")
def last_frame(pid: str, req: LastFrameReq):
    refs.project_dir(pid)
    if not ff.available():
        raise HTTPException(409, NO_FFMPEG)
    try:
        return edit.export_last_frame(pid, req.scene, req.shot, req.take)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@router.get("/api/projects/{pid}/edit/sfx")
def list_sfx(pid: str):
    refs.project_dir(pid)
    return edit.list_sfx(pid)


@router.post("/api/projects/{pid}/edit/sfx/upload")
async def upload_sfx(pid: str, files: list[UploadFile] = File(...), prompt: str = Form("")):  # noqa: B008
    refs.project_dir(pid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de 25 MB")
        payload.append((f.filename or "sfx.wav", data))
    try:
        return edit.import_sfx(pid, payload, prompt)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/api/projects/{pid}/edit/render")
def start_render(pid: str, req: RenderReq):
    """`rough` é a prévia de ritmo (sai sem música, com aviso); `master` exige a trilha da etapa 7."""
    refs.project_dir(pid)
    if not ff.available():
        raise HTTPException(409, NO_FFMPEG)
    try:
        return render.start_render(pid, req.target)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/api/projects/{pid}/edit/render/job")
def render_job(pid: str):
    refs.project_dir(pid)
    return render.render_status(pid)
