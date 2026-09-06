"""Store das abas de chat (ADR-036), persistido em arquivo (ADR-003).

Uma aba = uma sessão do Claude (`id` é também o `--session-id`). Cada aba tem `meta.json` (título,
campanha vinculada, contagem de turnos, status) e `events.jsonl` (o transcript: um evento por
linha, na ordem em que o stream os produziu). O `seq` de um evento é a sua posição no arquivo — é
o que o WebSocket usa para o replay depois de uma reconexão (Onda C).
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from ..common import atomic
from ..config import STATE_DIR

CHATS_DIR = STATE_DIR / "chats"
STATUSES = ("idle", "running", "error", "archived")


@dataclass
class Session:
    id: str
    title: str
    pid: str | None
    turns: int
    status: str
    created: str
    updated: str

    def public(self) -> dict:
        return asdict(self)


def now() -> str:
    """`ts` do transcript, em UTC. Público porque o router carimba o evento ANTES de gravar.

    `append_event` faz `{"ts": now(), **event}`, então um `ts` que já venha no evento vence — é
    assim que o mesmo instante vai para o disco e para o WebSocket, sem duas leituras do relógio.
    """
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


#: Alias interno histórico — o módulo inteiro chamava `_now()` antes de o `ts` precisar ser público.
_now = now


def _dir(chat_id: str) -> Path:
    d = CHATS_DIR / chat_id
    return d


def _meta_path(chat_id: str) -> Path:
    return _dir(chat_id) / "meta.json"


def _events_path(chat_id: str) -> Path:
    return _dir(chat_id) / "events.jsonl"


def _load(chat_id: str) -> Session:
    p = _meta_path(chat_id)
    if not p.is_file():
        raise KeyError(chat_id)
    return Session(**json.loads(p.read_text(encoding="utf-8")))


def _save(s: Session) -> None:
    _dir(s.id).mkdir(parents=True, exist_ok=True)
    atomic.write_json_atomic(_meta_path(s.id), s.public(), ensure_ascii=False, indent=1)


# ---------- API pública ----------
def create(title: str = "", pid: str | None = None) -> Session:
    """Cria uma aba nova. O `id` é um UUID canônico (com hifens) — é também o `--session-id` do
    Claude, que exige o formato UUID."""
    chat_id = str(uuid.uuid4())
    now = _now()
    s = Session(id=chat_id, title=(title or "Nova conversa").strip()[:120],
                pid=pid, turns=0, status="idle", created=now, updated=now)
    _save(s)
    return s


def get(chat_id: str) -> Session:
    return _load(chat_id)


def list_sessions(include_archived: bool = False) -> list[Session]:
    """Todas as abas, mais recentes primeiro (por `updated`)."""
    if not CHATS_DIR.is_dir():
        return []
    out: list[Session] = []
    for d in CHATS_DIR.iterdir():
        if not d.is_dir():
            continue
        try:
            s = _load(d.name)
        except (KeyError, json.JSONDecodeError, TypeError):
            continue
        if s.status == "archived" and not include_archived:
            continue
        out.append(s)
    return sorted(out, key=lambda s: s.updated, reverse=True)


def patch(chat_id: str, **fields) -> Session:
    """Atualiza campos permitidos de uma aba (`title`, `pid`, `status`, `turns`)."""
    s = _load(chat_id)
    allowed = {"title", "pid", "status", "turns"}
    for k, v in fields.items():
        if k in allowed and v is not None:
            if k == "status" and v not in STATUSES:
                raise ValueError(f"status inválido: {v}")
            setattr(s, k, v)
    s.updated = _now()
    _save(s)
    return s


def bump_turn(chat_id: str) -> Session:
    s = _load(chat_id)
    s.turns += 1
    s.updated = _now()
    _save(s)
    return s


def append_event(chat_id: str, event: dict) -> int:
    """Grava um evento no transcript e devolve o seq (posição no arquivo)."""
    _dir(chat_id).mkdir(parents=True, exist_ok=True)
    path = _events_path(chat_id)
    seq = _count_events(chat_id)
    line = json.dumps({"ts": _now(), **event}, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return seq


def read_events(chat_id: str, after: int = 0) -> list[dict]:
    """Eventos do transcript com `seq >= after`, cada um com seu `seq`."""
    path = _events_path(chat_id)
    if not path.is_file():
        return []
    out = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if i < after or not raw.strip():
            continue
        try:
            out.append({"seq": i, **json.loads(raw)})
        except json.JSONDecodeError:
            continue
    return out


def _count_events(chat_id: str) -> int:
    path = _events_path(chat_id)
    if not path.is_file():
        return 0
    return sum(1 for _ in path.open("r", encoding="utf-8"))
