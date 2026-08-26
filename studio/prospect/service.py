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
from ..publish import service as publish

log = logging.getLogger("studio.prospect")
_registry = JobRegistry()

REQUIRED_VIDEOS = 4          # aula 015: "pelo menos quatro vídeos" — obras distintas (ADR-012)
DAILY_LIMIT = 10             # aula 001: 10 DMs por dia (meta, não trava)
MIN_TEASER = 5.0             # aula 001: teaser de 5 a 10 s com música
MAX_TEASER = 10.0
DEFAULT_TEASER = 8.0
MAX_FIELD = 2000
MIN_PRICE = 100.0            # aula 016: "R$100 a R$500 por um vídeo de 30 s a 1 min"
MAX_PRICE = 500.0
FIRST_JOB_DISCOUNT = 0.5     # aula 001: 50% off no primeiro trabalho
#: Mar azul da aula 001 — os segmentos que o instrutor cita, na ordem em que ele cita.
SEGMENTS = ("clínicas", "academias", "advogados", "estética", "dentistas", "comércios")
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


def _segment(value: str) -> str:
    """Segmento do lead (um dos `SEGMENTS` da aula 001). Vazio = ainda não classificado."""
    v = (value or "").strip().lower()
    if not v:
        return ""
    if v not in SEGMENTS:
        raise ValueError(f"segmento deve ser um de: {', '.join(SEGMENTS)}")
    return v


def _iso(value: str, field: str) -> str:
    try:
        return datetime.fromisoformat(value).isoformat(timespec="seconds")
    except (TypeError, ValueError) as e:
        raise ValueError(f"{field} deve ser uma data ISO 8601 (ex.: 2026-08-27T15:00:00)") from e


# ---------- gate: 4 vídeos publicados (etapa 10, portfólio GLOBAL) ----------
def gate(root: Path) -> dict:
    """`{published, posts, required, ok, message, projects}` a partir do portfólio **global**.

    `published` = **projetos distintos** com pelo menos um post registrado (ADR-012). O teaser
    desta etapa sai de um projeto criado para o negócio do lead — esse projeto nunca terá quatro
    vídeos publicados, então contar dentro dele deixava a etapa inutilizável no uso real
    (auditoria 10.1/11.2). `root` continua no contrato porque o gate é sempre consultado no
    contexto de um projeto.
    """
    p = publish.global_portfolio()
    published = p["distinct_videos"]
    ok = p["ready"]
    faltam = max(REQUIRED_VIDEOS - published, 0)
    message = (
        f"Portfólio pronto: {published} vídeos publicados. Pode prospectar."
        if ok else
        "A aula pede quatro obras diferentes antes de prospectar — "
        + ("falta 1 campanha." if faltam == 1 else f"faltam {faltam} campanhas.")
    )
    return {"published": published, "posts": p["posts"], "required": REQUIRED_VIDEOS, "ok": ok,
            "message": message, "projects": p["projects"],
            "this_project_published": bool(publish.posts_at(root))}


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
    # `segment` entrou na wave 4: leads gravados antes voltam com o campo vazio, nunca ausente.
    for lead in data:
        if isinstance(lead, dict):
            lead.setdefault("segment", "")
    return data


def save_leads(root: Path, leads: list[dict]) -> None:
    _write_atomic(leads_file(root), json.dumps(leads, ensure_ascii=False, indent=1))


def get_lead(root: Path, lid: str) -> dict:
    for lead in load_leads(root):
        if lead.get("id") == lid:
            return lead
    raise FileNotFoundError(f"lead não encontrado: {lid}")


POST_REF_REQUIRED = ("cite um post específico do perfil: é isso que a aula manda mostrar "
                     "(\"olhou o perfil e menciona um post\") e é o que faz a DM não ser spam")


def _post_ref(value) -> str:
    """`post_ref` é obrigatório (auditoria 11.3): sem ele a DM sai com um buraco no meio."""
    v = _text(value, "post_ref")
    if not v:
        raise ValueError(POST_REF_REQUIRED)
    return v


def dm_text(lead: dict) -> str:
    """O script literal da aula 001 com as quatro substituições. Nunca contém link."""
    if not (lead.get("post_ref") or "").strip():
        raise ValueError(POST_REF_REQUIRED)
    return DM_TEMPLATE.format(
        business=lead.get("business", "").strip(),
        role=_role(lead.get("role") or "fã"),
        post_ref=lead.get("post_ref", "").strip(),
    )


def followup_text() -> str:
    """Texto literal do follow-up (aula 001): convite para a call de 15 minutos."""
    return FOLLOWUP_TEXT


def create_lead(root: Path, business: str, handle: str, post_ref: str = "", why: str = "",
                role: str = "fã", segment: str = "") -> dict:
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
        "post_ref": _post_ref(post_ref),
        "why": _text(why, "why"),
        "role": _role(role),
        #: Segmento do mar azul da aula 001 — a linha do lead mostra "@handle · segmento".
        "segment": _segment(segment),
        "dm_text": "",
        "sent_at": None,
        "replied": False,
        "replied_at": None,     # quando a empresa respondeu — base do follow-up de 7 dias
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


EDITABLE = ("business", "handle", "post_ref", "why", "role", "segment")


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
        elif key == "segment":
            lead["segment"] = _segment(value)
        elif key == "handle":
            handle = _text(value, "handle", required=True).lstrip("@").strip().lower()
            if not _slug(handle):
                raise ValueError("handle inválido")
            if any(x.get("handle") == handle and x.get("id") != lid for x in leads):
                raise ValueError(f"handle já cadastrado: @{handle}")
            lead["handle"] = handle
        elif key == "post_ref":
            lead["post_ref"] = _post_ref(value)
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
        lead["replied_at"] = datetime.now().isoformat(timespec="seconds")
    else:
        lead["replied_at"] = None
        if lead.get("status") == "replied":
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


#: Quanto antes do primeiro impacto a trilha do teaser começa, para o impacto cair no início.
IMPACT_LEAD_IN = 0.5


def suggest_music_offset(root: Path) -> dict:
    """Sugestão de `music_offset`: primeiro impacto de `audio/beats.json` − 0,5 s.

    A aula pede o teaser *"com música e impacto"* (001). Isto é **sugestão, não imposição**:
    quem informar `music_offset` explicitamente manda. Sem `beats.json` (ou sem impactos),
    devolve `music_offset: None` e a etapa segue com 0,0.
    """
    none = {"music_offset": None, "impact": None, "source": "audio/beats.json"}
    f = root / "audio" / "beats.json"
    if not f.exists():
        return none
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        log.warning("beats_invalid file=%s", f)
        return none
    impacts = [float(t) for t in (data or {}).get("impacts") or []]
    if not impacts:
        return none
    first = min(impacts)
    return {"music_offset": max(0.0, round(first - IMPACT_LEAD_IN, 2)), "impact": round(first, 3),
            "source": "audio/beats.json"}


def start_teaser(root: Path, pid: str, lid: str, take: dict | None = None, duration: float = DEFAULT_TEASER,
                 take_offset: float = 0.0, music_offset: float | None = None) -> dict:
    """Monta `prospect/teasers/<lid>.mp4` (5 a 10 s, com música) num job em thread.

    `music_offset=None` usa a sugestão do primeiro impacto (11.8); um número explícito manda.
    """
    require_gate(root)
    lead = get_lead(root, lid)
    if not lead.get("replied"):
        # "Você só cria de verdade se a empresa responder" (aula 001) — 422 no router.
        raise ValueError("a aula manda criar só depois que a empresa responder")
    if not ff.available():
        raise RuntimeError("ffmpeg não disponível")
    if _registry.status(pid).get("state") == "running":
        # falha cedo (o registry ainda guarda a corrida): um job de teaser por projeto
        raise RuntimeError("Já existe um trabalho em andamento para este projeto.")
    duration = float(duration)
    if not (MIN_TEASER <= duration <= MAX_TEASER):
        raise ValueError(f"duration deve estar entre {MIN_TEASER:g} e {MAX_TEASER:g} segundos (aula 001)")
    if music_offset is None:
        music_offset = suggest_music_offset(root)["music_offset"] or 0.0
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

    return _registry.start(pid, 3, fn, lead=lid, teaser=None, duration=effective,
                           music_offset=music_offset)


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
PITCH_STEPS = [row[0] for row in PITCH_ROWS]
#: As quatro frases da aula 001 que a caixa do script mostra (o `pitch.md` guarda a lista longa).
PITCH_REMINDERS = (
    "Revele o valor por etapa até o total.",
    "Condição especial na hora, ou válida por 24h.",
    "50% na entrada, 50% na entrega.",
    "Venda o resultado, não a IA.",
)
PITCH_REL = "prospect/pitch.json"


def _money(v: float) -> str:
    return f"{v:,.2f}".replace(",", "·").replace(".", ",").replace("·", ".")


def clean_values(values: dict | None) -> dict[str, float]:
    """Valores por etapa, só das etapas conhecidas, não negativos. Zero = "ainda não precifiquei"."""
    out: dict[str, float] = {}
    for etapa, raw in (values or {}).items():
        if etapa not in PITCH_STEPS:
            raise ValueError(f"etapa desconhecida no pitch: {etapa}")
        try:
            v = float(raw)
        except (TypeError, ValueError) as e:
            raise ValueError(f"valor inválido para {etapa}: {raw!r}") from e
        if v < 0:
            raise ValueError(f"valor negativo para {etapa}")
        out[etapa] = round(v, 2)
    return out


def load_pitch_values(root: Path) -> dict:
    """`{values, total, sum, matches, in_range}` — leitura pura de `prospect/pitch.json`."""
    f = root / PITCH_REL
    data: dict = {}
    if f.exists():
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            data = raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            log.warning("pitch_values_invalid file=%s", f)
    values: dict[str, float] = {}
    for etapa in PITCH_STEPS:
        try:
            v = float((data.get("values") or {}).get(etapa, 0) or 0)
        except (TypeError, ValueError):
            v = 0.0
        values[etapa] = round(max(0.0, v), 2)
    soma = round(sum(values.values()), 2)
    try:
        total = round(float(data["total"]), 2) if data.get("total") is not None else soma
    except (TypeError, ValueError):
        total = soma
    return {"values": values, "total": total, "sum": soma,
            "matches": abs(total - soma) < 0.01,
            "priced": soma > 0,
            "in_range": MIN_PRICE <= total <= MAX_PRICE if total else False,
            "discount": round(total * (1 - FIRST_JOB_DISCOUNT), 2)}


def save_pitch_values(root: Path, values: dict | None = None, total: float | None = None) -> dict:
    """Grava `prospect/pitch.json`. `total` ausente = soma das etapas (ancoragem da aula)."""
    vals = clean_values(values)
    merged = {**load_pitch_values(root)["values"], **vals} if vals else load_pitch_values(root)["values"]
    soma = round(sum(merged.values()), 2)
    if total is not None:
        try:
            total = round(float(total), 2)
        except (TypeError, ValueError) as e:
            raise ValueError(f"total inválido: {total!r}") from e
        if total < 0:
            raise ValueError("total negativo")
    payload = {"values": merged, "total": total if total is not None else soma,
               "updated": datetime.now().isoformat(timespec="seconds")}
    _write_atomic(root / PITCH_REL, json.dumps(payload, ensure_ascii=False, indent=1))
    log.info("pitch_values_saved total=%s sum=%s", payload["total"], soma)
    return load_pitch_values(root)


def pitch_markdown(project: dict, pitch: dict | None = None) -> str:
    """Tabela de etapas com valor por etapa (ancoragem da aula 001) + lembretes literais."""
    pitch = pitch or {"values": dict.fromkeys(PITCH_STEPS, 0.0), "total": 0.0, "sum": 0.0,
                      "matches": True, "priced": False, "in_range": False, "discount": 0.0}
    values, total = pitch["values"], pitch["total"]
    rows = "\n".join(
        f"| {etapa} | {envolve} | {entrega} | "
        f"{('R$ ' + _money(values.get(etapa, 0.0))) if values.get(etapa) else '—'} |"
        for etapa, envolve, entrega in PITCH_ROWS)
    total_txt = f"R$ {_money(total)}" if total else "—"
    desconto_txt = f"R$ {_money(pitch['discount'])}" if total else "—"
    aviso = ("" if pitch["matches"] else
             f"\n> A soma das etapas (R$ {_money(pitch['sum'])}) é diferente do total. "
             "Confira antes da call — a ancoragem só funciona se as contas fecharem.\n")
    return f"""# Pitch: {project.get("name", "projeto")}

## Etapas de produção (ancoragem: revele o valor etapa por etapa até chegar no total)
| Etapa | O que envolve | Entrega | Valor (R$) |
| --- | --- | --- | --- |
{rows}
| **Total** | o que você quer cobrar | vídeo pronto para publicar | **{total_txt}** |
| **Total com 50 % off no 1º trabalho** | condição de entrada | mesmo escopo | **{desconto_txt}** |
{aviso}
## Lembretes da aula 001
- Condição especial na hora, ou válida por 24h.
- 50 % off no primeiro trabalho, deixando claro o valor cheio para os próximos.
- Pagamento 50 % na entrada e 50 % na entrega — não trabalhe sem entrada.
- Faixa inicial: R$ 100 a R$ 500 por vídeo de 30 s a 1 min.
- Vender o resultado (o anúncio traz mais clientes), não a IA.
- A call dura 15 minutos: mostrar o teaser, explicar a ideia, apresentar a tabela.
"""


def pitch_file(root: Path) -> Path:
    return root / "prospect" / "pitch.md"


def write_pitch(root: Path, project: dict) -> Path:
    f = pitch_file(root)
    _write_atomic(f, pitch_markdown(project, load_pitch_values(root)))
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
    return pitch_markdown(project, load_pitch_values(root))
