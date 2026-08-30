"""Rotas da etapa 7 — Montagem no ritmo (aula 014)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from ...common import ffmpeg as ff
from ...edit import render
from ...edit import service as edit
from ...edit.captions import service as captions
from ...edit.captions.transcribe import ProviderError
from ...refs import service as refs

router = APIRouter(tags=["edit"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_MEDIA_BYTES = 200 * 1024 * 1024   # [extensão] vídeos/imagens do editor podem ser maiores que SFX
NO_FFMPEG = "ffmpeg não disponível — instale em ~/.local/bin para renderizar e exportar o último frame"


class ClipReq(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str | None = None      # [extensão]: id estável do clipe (editor)
    scene: str = ""
    shot: str = ""
    take: str = ""
    file: str
    src_in: float = Field(0.0, alias="in")   # ponto de entrada NO ARQUIVO (aula: `in`)
    out: float
    start: float | None = None   # [extensão]: posição livre do clipe NA timeline (gaps)
    speed: float = 1.0
    blend: bool = True
    zoom: float = 1.0          # aula 014: "pequenos zooms" (1.0–1.3)


class BlackReq(BaseModel):
    at: float
    dur: float = edit.DEFAULT_BLACK_DUR


class MusicReq(BaseModel):
    file: str | None = None
    offset: float = 0.0
    # [extensão] painel de propriedades da trilha (editor): ausentes = não tocados pelo usuário
    volume: float | None = None
    muted: bool | None = None


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
    editor: dict | None = None    # [extensão]: modelo do editor completo (validado em service/editor.py)


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
    # [extensão] opções do modal de exportação; ausentes = master 1920x1080/30 (aula 014)
    width: int | None = None
    height: int | None = None
    fps: int | None = None
    quality: str | None = None


class CaptionStyleReq(BaseModel):
    """[extensão] Preset de legenda do editor. `extra="allow"` deixa fonte/sombra/uppercase
    do preset atravessarem intactos até o item — quem normaliza `style` é o `PUT /timeline`."""
    model_config = ConfigDict(extra="allow")
    size: int = 34
    weight: int = 700
    align: str = "center"
    color: str = "#FFFFFF"
    bg: str = "transparent"


class CaptionsGenerateReq(BaseModel):
    """[extensão] Pedido de geração de legendas (contrato congelado da wave 8)."""
    source: Literal["script", "audio"]
    text: str | None = None
    file: str | None = None
    start: float = 0.0
    duration: float | None = None
    mode: Literal["karaoke", "linha", "bloco"] = "karaoke"
    chunk: int = Field(6, ge=0, le=20)     # 0 = uma janela por linha de largura
    hi: str = Field("#C8F751", pattern=r"^#[0-9A-Fa-f]{6}$")
    position: Literal["top", "middle", "bottom"] = "bottom"
    style: CaptionStyleReq = CaptionStyleReq()


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
    """Recria a timeline inicial — usar depois de gerar takes novos na etapa 5."""
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


@router.get("/api/projects/{pid}/edit/media")
def list_media(pid: str):
    refs.project_dir(pid)
    return edit.list_media(pid)


@router.post("/api/projects/{pid}/edit/media/upload")
async def upload_media(pid: str, files: list[UploadFile] = File(...)):  # noqa: B008
    """[extensão] Upload de imagens/vídeos novos para o editor (overlay ou clipe)."""
    refs.project_dir(pid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_MEDIA_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de {MAX_MEDIA_BYTES // (1024 * 1024)} MB")
        payload.append((f.filename or "media", data))
    try:
        return edit.import_media(pid, payload)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


# ---------- legendas [extensão] (a aula 014 monta sem legenda; ver ADR-024) ----------
@router.post("/api/projects/{pid}/edit/captions/generate")
def captions_generate(pid: str, req: CaptionsGenerateReq):
    """Itens prontos para a faixa de legenda, a partir do roteiro colado ou de um áudio do projeto.

    Síncrono e sem persistência: quem grava é o `PUT /timeline` que o front já chama. O 409 vem
    antes do serviço porque sem ffmpeg não há como extrair o wav — a etapa segue editável, só a
    geração por áudio trava (mesma regra do render e do último frame).
    """
    root = refs.project_dir(pid)
    if req.source == "audio" and not ff.available():
        raise HTTPException(409, NO_FFMPEG)
    try:
        return captions.generate(root, req.model_dump())
    except ProviderError as e:
        raise HTTPException(502, str(e)) from e
    except (FileNotFoundError, ValueError) as e:
        raise _translate(e) from e


@router.post("/api/projects/{pid}/edit/captions/narration/upload")
async def upload_narration(pid: str, files: list[UploadFile] = File(...)):  # noqa: B008
    """[extensão] Biblioteca de narração do projeto — a fonte de áudio da legenda."""
    root = refs.project_dir(pid)
    payload = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_MEDIA_BYTES:
            raise HTTPException(413, f"{f.filename}: arquivo acima de {MAX_MEDIA_BYTES // (1024 * 1024)} MB")
        payload.append((f.filename or "narracao.wav", data))
    try:
        return captions.import_narration(root, payload)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/projects/{pid}/edit/captions/narration")
def list_narration(pid: str):
    return captions.list_narration(refs.project_dir(pid))


@router.post("/api/projects/{pid}/edit/render")
def start_render(pid: str, req: RenderReq):
    """`rough` é a prévia de ritmo (sai sem música, com aviso); `master` exige a trilha da etapa 6."""
    refs.project_dir(pid)
    if not ff.available():
        raise HTTPException(409, NO_FFMPEG)
    try:
        export = {"width": req.width, "height": req.height, "fps": req.fps, "quality": req.quality}
        return render.start_render(pid, req.target, export)
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
