"""Etapa 11 — Prospecção (aula 001).

A aula manda, nesta ordem: publicar 4 vídeos criativos antes de prospectar; mandar 10 DMs por dia
com o script literal (fã/consumidor → post que ressoou → "produzo anúncios criativos" → "tive uma
inspiração e criei algo para o seu negócio, quer ver como ficou?"), sem links; mandar um teaser de
5 a 10 s **com música** para quem responder; convidar para uma call de 15 minutos; e, na call,
ancorar valor com a tabela de etapas de produção.

O Studio redige e registra; **enviar é humano** — não existe aqui nenhuma integração com rede
social, nenhum envio automático e nenhum bloqueio duro de 10/dia (a aula dá o número como meta de
disciplina, não como trava: o Studio conta e avisa).

Artefatos: `prospect/leads.json`, `prospect/teasers/<lead>.mp4`, `prospect/pitch.md`.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import date, datetime
from pathlib import Path

from ..common import ffmpeg as ff
from ..common.jobs import JobRegistry

log = logging.getLogger("studio.prospect")
_registry = JobRegistry()

REQUIRED_VIDEOS = 4          # aula 015: "publicar esses 4 vídeos" antes de prospectar
DAILY_LIMIT = 10             # aula 001: 10 DMs por dia (meta, não trava)
MIN_TEASER = 5.0             # aula 001: teaser de 5 a 10 s com música
MAX_TEASER = 10.0
DEFAULT_TEASER = 8.0
MAX_FIELD = 2000
ROLES = ("fã", "consumidor")
STATUSES = ("new", "dm_sent", "replied", "teaser_ready", "call_scheduled", "call_done")

# Script literal do instrutor (aula 001), com as quatro substituições. Sem nenhuma URL:
# a aula avisa que DM com link cai em spam.
DM_TEMPLATE = (
    "Oi {business}. Eu sou {role} da sua marca. O seu post a respeito de {post_ref} realmente ressoou comigo. "
    "Quero ser bem direto: eu produzo anúncios criativos para marcas. Você pode acompanhar meu portfólio no meu "
    "perfil. Tive uma inspiração e criei algo para o seu negócio. Quer ver como ficou?"
)
FOLLOWUP_TEXT = (
    "Aqui está o início. Se quiser, podemos agendar uma call de 15 minutinhos e te explico a minha ideia para "
    "esse anúncio completo."
)


class GateClosed(RuntimeError):
    """Portfólio ainda sem 4 vídeos publicados (aula 015 → 001). Vira 409 no router."""


# ---------- utilidades ----------
def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _text(value, field: str, required: bool = False) -> str:
    v = (value or "").strip() if isinstance(value, str) or value is None else str(value).strip()
    if required and not v:
        raise ValueError(f"{field} é obrigatório")
    if len(v) > MAX_FIELD:
        raise ValueError(f"{field} acima de {MAX_FIELD} caracteres")
    return v


def _role(value: str) -> str:
    v = (value or "").strip().lower()
    if v == "fa":
        v = "fã"
    if v not in ROLES:
        raise ValueError("role deve ser 'fã' ou 'consumidor' (a aula manda escolher um dos dois)")
    return v


def _iso(value: str, field: str) -> str:
    try:
        return datetime.fromisoformat(value).isoformat(timespec="seconds")
    except (TypeError, ValueError) as e:
        raise ValueError(f"{field} deve ser uma data ISO 8601 (ex.: 2026-08-27T15:00:00)") from e


# ---------- gate: 4 vídeos publicados (etapa 10) ----------
def _published_videos(root: Path) -> list[str]:
    """Vídeos distintos registrados em `publish/log.json` (decisão 1 da wave: 4 vídeos, não 4 posts).

    Arquivo ausente, ilegível ou inválido conta como zero — nunca levanta.
    """
    f = root / "publish" / "log.json"
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        log.warning("publish_log_invalid file=%s", f)
        return []
    if not isinstance(data, list):
        log.warning("publish_log_invalid file=%s", f)
        return []
    return [v for e in data if isinstance(e, dict) and (v := str(e.get("video") or "").strip())]


def gate(root: Path) -> dict:
    """`{published, posts, required, ok, message}` — `published` = vídeos DISTINTOS publicados."""
    posted = _published_videos(root)
    published = len(set(posted))
    ok = published >= REQUIRED_VIDEOS
    message = (
        f"Portfólio pronto: {published} vídeos publicados. Pode prospectar."
        if ok else
        f"A aula manda publicar {REQUIRED_VIDEOS} vídeos criativos antes de prospectar. "
        f"Você tem {published}/{REQUIRED_VIDEOS}."
    )
    return {"published": published, "posts": len(posted), "required": REQUIRED_VIDEOS, "ok": ok, "message": message}


def require_gate(root: Path) -> None:
    g = gate(root)
    if not g["ok"]:
        log.warning("gate_closed published=%s required=%s", g["published"], g["required"])
        raise GateClosed(g["message"])


# ---------- leads ----------
def leads_file(root: Path) -> Path:
    return root / "prospect" / "leads.json"


def load_leads(root: Path) -> list[dict]:
    f = leads_file(root)
    if not f.exists():
        return []
    data = json.loads(f.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("prospect/leads.json inválido: esperava uma lista")
    return data


def save_leads(root: Path, leads: list[dict]) -> None:
    _write_atomic(leads_file(root), json.dumps(leads, ensure_ascii=False, indent=1))


def get_lead(root: Path, lid: str) -> dict:
    for lead in load_leads(root):
        if lead.get("id") == lid:
            return lead
    raise FileNotFoundError(f"lead não encontrado: {lid}")


def dm_text(lead: dict) -> str:
    """O script literal da aula 001 com as quatro substituições. Nunca contém link."""
    return DM_TEMPLATE.format(
        business=lead.get("business", "").strip(),
        role=_role(lead.get("role") or "fã"),
        post_ref=lead.get("post_ref", "").strip(),
    )


def followup_text() -> str:
    """Texto literal do follow-up (aula 001): convite para a call de 15 minutos."""
    return FOLLOWUP_TEXT


def create_lead(root: Path, business: str, handle: str, post_ref: str = "", why: str = "", role: str = "fã") -> dict:
    require_gate(root)
    business = _text(business, "business", required=True)
    handle = _text(handle, "handle", required=True).lstrip("@").strip().lower()
    lid = _slug(handle)
    if not lid:
        raise ValueError("handle inválido")
    leads = load_leads(root)
    if any(x.get("id") == lid for x in leads):
        raise ValueError(f"handle já cadastrado: @{handle}")
    lead = {
        "id": lid,
        "business": business,
        "handle": handle,
        "post_ref": _text(post_ref, "post_ref"),
        "why": _text(why, "why"),
        "role": _role(role),
        "dm_text": "",
        "sent_at": None,
        "replied": False,
        "teaser": None,
        "call_at": None,
        "call_note": "",
        "status": "new",
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    lead["dm_text"] = dm_text(lead)
    leads.append(lead)
    save_leads(root, leads)
    log.info("lead_created lead=%s status=%s", lid, lead["status"])
    return lead


def _replace(root: Path, lead: dict) -> dict:
    leads = [lead if x.get("id") == lead["id"] else x for x in load_leads(root)]
    save_leads(root, leads)
    return lead


EDITABLE = ("business", "handle", "post_ref", "why", "role")


def update_lead(root: Path, lid: str, **fields) -> dict:
    require_gate(root)
    leads = load_leads(root)
    lead = next((x for x in leads if x.get("id") == lid), None)
    if lead is None:
        raise FileNotFoundError(f"lead não encontrado: {lid}")
    for key, value in fields.items():
        if value is None or key not in EDITABLE:
            continue
        if key == "role":
            lead["role"] = _role(value)
        elif key == "handle":
            handle = _text(value, "handle", required=True).lstrip("@").strip().lower()
            if not _slug(handle):
                raise ValueError("handle inválido")
            if any(x.get("handle") == handle and x.get("id") != lid for x in leads):
                raise ValueError(f"handle já cadastrado: @{handle}")
            lead["handle"] = handle
        else:
            lead[key] = _text(value, key, required=(key == "business"))
    # DM já enviada não muda mais: o texto tem de continuar sendo o que o lead recebeu.
    if not lead.get("sent_at"):
        lead["dm_text"] = dm_text(lead)
    save_leads(root, leads)
    return lead


def delete_lead(root: Path, lid: str) -> None:
    require_gate(root)
    leads = load_leads(root)
    if not any(x.get("id") == lid for x in leads):
        raise FileNotFoundError(f"lead não encontrado: {lid}")
    save_leads(root, [x for x in leads if x.get("id") != lid])
    (root / "prospect" / "teasers" / f"{lid}.mp4").unlink(missing_ok=True)
    log.info("lead_deleted lead=%s", lid)


# ---------- DM: marcações e contador ----------
def today_sent(leads: list[dict], today: date | None = None) -> int:
    """Quantas DMs foram marcadas como enviadas hoje (aula 001: a meta é 10 por dia)."""
    today = today or date.today()
    n = 0
    for lead in leads:
        raw = lead.get("sent_at")
        if not raw:
            continue
        try:
            if datetime.fromisoformat(raw).date() == today:
                n += 1
        except (TypeError, ValueError):
            continue
    return n


def mark_sent(root: Path, lid: str, sent_at: str | None = None) -> dict:
    require_gate(root)
    lead = get_lead(root, lid)
    lead["sent_at"] = _iso(sent_at, "sent_at") if sent_at else datetime.now().isoformat(timespec="seconds")
    lead["status"] = "dm_sent"
    _replace(root, lead)
    n = today_sent(load_leads(root))
    log.info("dm_sent lead=%s today_sent=%s", lid, n)
    if n > DAILY_LIMIT:
        log.warning("over_daily_limit lead=%s today_sent=%s limit=%s", lid, n, DAILY_LIMIT)
    return lead


def mark_replied(root: Path, lid: str, replied: bool = True) -> dict:
    require_gate(root)
    lead = get_lead(root, lid)
    if replied and not lead.get("sent_at"):
        raise ValueError("marque a DM como enviada antes de registrar a resposta")
    lead["replied"] = bool(replied)
    if replied:
        lead["status"] = "replied"
    elif lead.get("status") == "replied":
        lead["status"] = "dm_sent"
    log.info("replied lead=%s replied=%s", lid, bool(replied))
    return _replace(root, lead)


def by_status(leads: list[dict]) -> dict:
    counts = dict.fromkeys(STATUSES, 0)
    for lead in leads:
        s = lead.get("status")
        if s in counts:
            counts[s] += 1
    return counts


def register_call(root: Path, lid: str, call_at: str, done: bool = False, note: str = "") -> dict:
    """Registra a call de 15 minutos (aula 001)."""
    require_gate(root)
    lead = get_lead(root, lid)
    lead["call_at"] = _iso(call_at, "call_at")
    lead["call_note"] = _text(note, "note")
    lead["status"] = "call_done" if done else "call_scheduled"
    log.info("call_registered lead=%s status=%s", lid, lead["status"])
    return _replace(root, lead)


# ---------- teaser: um take da etapa 6 + a trilha da etapa 7 ----------
def _take_duration(root: Path, entry: dict) -> float:
    d = entry.get("duration")
    if isinstance(d, (int, float)) and d > 0:
        return float(d)
    path = root / str(entry.get("file") or "")
    if path.exists() and ff.available():
        try:
            return float(ff.probe(path)["duration"])
        except RuntimeError:
            return 0.0
    return 0.0


def pick_take(root: Path, take: dict | None = None) -> dict:
    """Escolhe o take do teaser: o informado; senão o primeiro com `liked`; senão o primeiro."""
    f = root / "animate" / "takes.json"
    if not f.exists():
        raise FileNotFoundError("Etapa 6 (animação) sem takes: gere e importe pelo menos um take antes do teaser.")
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        raise FileNotFoundError("Etapa 6 (animação) com takes.json ilegível.") from e
    flat: list[dict] = []
    for shot in (data or {}).get("shots", []) or []:
        for t in shot.get("takes", []) or []:
            if not t.get("file"):
                continue
            flat.append({"scene": shot.get("scene", ""), "shot": shot.get("shot", ""), "take": t.get("id", ""),
                         "file": t["file"], "liked": bool(t.get("liked")), "entry": t})
    if not flat:
        raise FileNotFoundError("Etapa 6 (animação) sem takes: gere e importe pelo menos um take antes do teaser.")
    if take:
        wanted = {k: take.get(k) for k in ("scene", "shot", "take") if take.get(k)}
        chosen = next((t for t in flat if all(t.get(k) == v for k, v in wanted.items())), None) if wanted else None
        if chosen is None:
            raise ValueError(f"take não encontrado em animate/takes.json: {take}")
    else:
        chosen = next((t for t in flat if t["liked"]), flat[0])
    path = root / chosen["file"]
    if not path.exists():
        raise FileNotFoundError(f"arquivo do take não encontrado: {chosen['file']}")
    return {"scene": chosen["scene"], "shot": chosen["shot"], "take": chosen["take"], "file": chosen["file"],
            "duration": _take_duration(root, chosen["entry"])}


def find_music(root: Path) -> Path:
    """A trilha escolhida na etapa 7 — a aula manda o teaser sair COM música."""
    for ext in ("wav", "mp3", "m4a", "ogg"):
        p = root / "audio" / f"music.{ext}"
        if p.exists():
            return p
    raise FileNotFoundError("Etapa 7 (trilha) sem música: escolha a trilha antes de gerar o teaser.")


def _floor_tenth(v: float) -> float:
    return math.floor(v * 10) / 10


def start_teaser(root: Path, pid: str, lid: str, take: dict | None = None, duration: float = DEFAULT_TEASER,
                 take_offset: float = 0.0, music_offset: float = 0.0) -> dict:
    """Monta `prospect/teasers/<lid>.mp4` (5 a 10 s, com música) num job em thread."""
    require_gate(root)
    get_lead(root, lid)
    if not ff.available():
        raise RuntimeError("ffmpeg não disponível")
    if _registry.status(pid).get("state") == "running":
        # falha cedo (o registry ainda guarda a corrida): um job de teaser por projeto
        raise RuntimeError("Já existe um trabalho em andamento para este projeto.")
    duration = float(duration)
    if not (MIN_TEASER <= duration <= MAX_TEASER):
        raise ValueError(f"duration deve estar entre {MIN_TEASER:g} e {MAX_TEASER:g} segundos (aula 001)")
    take_offset, music_offset = max(0.0, float(take_offset)), max(0.0, float(music_offset))
    chosen = pick_take(root, take)
    music = find_music(root)
    available = _floor_tenth(max(0.0, chosen["duration"] - take_offset)) if chosen["duration"] else duration
    effective = min(duration, available) if available else duration
    if effective < MIN_TEASER:
        raise ValueError(f"take com menos de {MIN_TEASER:g} s a partir do offset: escolha outro take (aula 001 pede 5 a 10 s)")
    out = root / "prospect" / "teasers" / f"{lid}.mp4"
    log.info("teaser_started lead=%s take=%s/%s/%s duration=%s", lid, chosen["scene"], chosen["shot"],
             chosen["take"], effective)

    def fn(job: dict) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        vtmp, atmp = out.with_name(f".{lid}.v.mp4"), out.with_name(f".{lid}.a.m4a")
        try:
            try:
                ff.run(["-ss", f"{take_offset}", "-i", str(root / chosen["file"]), "-t", f"{effective}", "-an",
                        "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(vtmp)], timeout=120)
                job["done"] = 1
                job["log"].append(
                    f"take {chosen['scene']}/{chosen['shot']}/{chosen['take']} "
                    f"({chosen['duration']:g} s) cortado em {effective:g} s")
                fade = max(0.0, effective - 0.5)
                ff.run(["-stream_loop", "-1", "-ss", f"{music_offset}", "-i", str(music), "-t", f"{effective}",
                        "-af", f"afade=t=out:st={fade}:d=0.5", "-c:a", "aac", str(atmp)], timeout=120)
                job["done"] = 2
                job["log"].append(f"música audio/{music.name} cortada em {effective:g} s com fade de saída")
                ff.run(["-i", str(vtmp), "-i", str(atmp), "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
                        "-crf", "20", "-c:a", "aac", "-shortest", str(out)], timeout=120)
            except RuntimeError as e:
                raise RuntimeError(str(e)[:400]) from e
            info = ff.probe(out)
            if not info["has_audio"]:
                raise RuntimeError("teaser saiu sem faixa de áudio (a aula pede o teaser COM música)")
            if not (MIN_TEASER - 0.25 <= info["duration"] <= MAX_TEASER + 0.25):
                raise RuntimeError(f"teaser com {info['duration']:.2f} s fora da faixa de 5 a 10 s")
            job["done"], job["added"] = 3, 1
            job["duration"] = round(info["duration"], 2)
            rel = f"prospect/teasers/{lid}.mp4"
            lead = get_lead(root, lid)
            lead["teaser"] = rel
            lead["status"] = "teaser_ready"
            _replace(root, lead)
            job["teaser"] = rel
            job["log"].append(f"teaser gravado em {rel}")
            log.info("teaser_done lead=%s duration=%s", lid, job["duration"])
        except Exception as e:
            out.unlink(missing_ok=True)
            log.error("teaser_failed lead=%s error=%s", lid, str(e)[:400])
            raise
        finally:
            vtmp.unlink(missing_ok=True)
            atmp.unlink(missing_ok=True)

    return _registry.start(pid, 3, fn, lead=lid, teaser=None, duration=effective)


def job_status(pid: str) -> dict:
    return _registry.status(pid)


# ---------- pitch da call ----------
PITCH_ROWS = [
    ("Conceito", "ideia central e mensagem", "uma frase de conceito"),
    ("Mood board", "referências de estilo, cor e clima", "painel de referências"),
    ("Roteirização", "história em cenas", "roteiro de 5 cenas"),
    ("Direção criativa", "ângulos, câmera, ritmo", "storyboard com ângulos"),
    ("Produção", "geração das cenas e takes", "takes por cena"),
    ("Montagem", "cortes na trilha, transições, som", "vídeo base"),
    ("Entrega", "formatos e publicação", "16:9, 9:16 e 1:1"),
]


def pitch_markdown(project: dict) -> str:
    """Tabela de etapas para ancorar valor na call + lembretes da aula (sem preço na tabela)."""
    rows = "\n".join(f"| {etapa} | {envolve} | {entrega} |" for etapa, envolve, entrega in PITCH_ROWS)
    return f"""# Pitch: {project.get("name", "projeto")}

## Etapas de produção (ancoragem de valor, sem preço na tabela)
| Etapa | O que envolve | Entrega |
| --- | --- | --- |
{rows}

## Lembretes da aula 001
- Oferta só-agora: 50% de desconto no primeiro trabalho, válida só nesta conversa.
- Pagamento 50% na entrada e 50% na entrega.
- Faixa inicial: R$ 100 a R$ 500 por vídeo de 30 s a 1 min.
- Vender o resultado (o anúncio), não a IA.
- A call dura 15 minutos: mostrar o teaser, explicar a ideia, apresentar a tabela.
"""


def pitch_file(root: Path) -> Path:
    return root / "prospect" / "pitch.md"


def write_pitch(root: Path, project: dict) -> Path:
    f = pitch_file(root)
    _write_atomic(f, pitch_markdown(project))
    log.info("pitch_written file=%s", f.name)
    return f


def read_pitch(root: Path, project: dict) -> str:
    """Devolve o pitch; grava o arquivo na primeira leitura. Edição à mão é preservada.

    Com o gate fechado o texto é devolvido para leitura, mas nada é escrito em `prospect/`
    (invariante: o portfólio de 4 vídeos vem antes de qualquer artefato de prospecção).
    """
    f = pitch_file(root)
    if f.exists():
        return f.read_text(encoding="utf-8")
    if gate(root)["ok"]:
        return write_pitch(root, project).read_text(encoding="utf-8")
    return pitch_markdown(project)
