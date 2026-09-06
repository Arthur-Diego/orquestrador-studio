"""Tools `ui.*` (ADR-038): o agente pergunta, o browser responde.

Cada helper faz um POST em `/api/chats/{chat_id}/ask` (bloqueia até o usuário responder ou o
timeout) ou `/emit` (empurra um cartão sem esperar). O `chat_id` vem do env `STUDIO_CHAT_ID` que o
runtime injeta no MCP da aba. Sem `chat_id` (uso no terminal), `ask` devolve `{answered:False,
no_ui:True}` e o chamador degrada para "pergunte/confirme em texto".
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Any

from .client import StudioClient

log = logging.getLogger(__name__)


def chat_id() -> str | None:
    return os.environ.get("STUDIO_CHAT_ID") or None


# ---------- token de confirmação de gasto `[extensão]` (ADR-038 §3, wave 11 · F10) ----------
#: Validade de um token de confirmação, em segundos. Folgado de propósito: entre aprovar o custo
#: e o POST de geração há só uma chamada, mas o usuário pode demorar a clicar.
CONFIRM_TTL = 900.0

#: Escape hatch do risco 2 do FDD: com `False`, `_paid` volta ao gate de hoje (só `confirmed`).
#: Existe para desligar a exigência sem reverter commit se o token travar geração legítima.
CONFIRM_TOKEN_REQUIRED = True

#: Tokens vivos: token -> {"action", "model", "chat_id", "exp"}. Estado EFÊMERO de processo, como
#: o registro de jobs em memória do ADR-006 — nunca vai a disco (ADR-003 não se aplica), nunca ao
#: WebSocket e nunca ao modelo.
_CONFIRM_TOKENS: dict[str, dict] = {}


def _purge_expired(agora: float) -> None:
    for tok in [t for t, d in _CONFIRM_TOKENS.items() if d["exp"] <= agora]:
        _CONFIRM_TOKENS.pop(tok, None)


def issue_confirm_token(action: str, model: str) -> str:
    """Emite um token opaco escopado na ação/modelo aprovados e no `chat_id` corrente.

    Chamado só por `confirm_cost`, e só quando o usuário aprova — logo é impossível haver
    aprovação sem token. Uma emissão nova para o mesmo par `(action, model)` na mesma aba
    substitui a anterior (no máximo um token vivo por par).
    """
    agora = time.monotonic()
    _purge_expired(agora)
    cid = chat_id()
    for tok in [t for t, d in _CONFIRM_TOKENS.items()
                if (d["action"], d["model"], d["chat_id"]) == (action, model, cid)]:
        _CONFIRM_TOKENS.pop(tok, None)
    token = secrets.token_urlsafe(16)
    _CONFIRM_TOKENS[token] = {"action": action, "model": model, "chat_id": cid,
                              "exp": agora + CONFIRM_TTL}
    return token


def consume_confirm_token(token: str | None, *, action: str, model: str) -> bool:
    """Consome o token UMA vez. `False` quando ausente, expirado, já usado, de outra ação, de
    outro modelo ou de outra aba. Nunca levanta. Limpa os expirados a cada chamada.
    """
    agora = time.monotonic()
    _purge_expired(agora)
    if not token:
        return False
    dados = _CONFIRM_TOKENS.pop(token, None)
    if dados is None:
        return False
    return (dados["action"], dados["model"], dados["chat_id"]) == (action, model, chat_id())


def _ask(client: StudioClient, payload: dict, timeout: float = 1800.0) -> dict:
    cid = chat_id()
    if not cid:
        return {"answered": False, "no_ui": True}
    try:
        return client.post(f"/api/chats/{cid}/ask", {"payload": payload, "timeout": timeout}) or {"answered": False}
    except Exception as e:  # noqa: BLE001 — nunca deixa a tool estourar por causa da ponte
        return {"answered": False, "error": str(e)}


def _emit(client: StudioClient, event: dict) -> None:
    cid = chat_id()
    if not cid:
        return
    try:
        client.post(f"/api/chats/{cid}/emit", {"event": event})
    except Exception:  # noqa: BLE001
        pass


# ---------- perguntas que bloqueiam ----------
def choose_one(client: StudioClient, title: str, options: list[dict]) -> dict:
    """options: [{label, value}]. Retorna {answered, choice}."""
    return _ask(client, {"widget": "choose_one", "title": title, "options": options})


def choose_images(client: StudioClient, title: str, images: list[dict], minimum: int = 1,
                  maximum: int | None = None) -> dict:
    """images: [{id, thumb, label}]. Retorna {answered, selected:[ids], order?}."""
    return _ask(client, {"widget": "choose_images", "title": title, "images": images,
                         "min": minimum, "max": maximum})


def form(client: StudioClient, title: str, fields: list[dict]) -> dict:
    """fields: [{name, label, type?, value?}]. Retorna {answered, values:{}}."""
    return _ask(client, {"widget": "form", "title": title, "fields": fields})


def confirm(client: StudioClient, title: str, detail: str = "") -> dict:
    return _ask(client, {"widget": "confirm", "title": title, "detail": detail})


def confirm_cost(client: StudioClient, action: str, credits: Any, model: str, detail: str = "",
                 *, breakdown: dict | None = None) -> dict:
    """Sheet de custo (ADR-016/038). Retorna {answered, confirmed, _confirm_token?}.

    `breakdown` `[extensão]` (wave 11) é o `CostPreview` inteiro; com ele o dock renderiza as
    MESMAS linhas do `CostSheet` das telas, em vez das duas linhas de antes. Compatível para
    trás nos dois sentidos: sem `breakdown` o widget cai no par credits+model de hoje, e os
    campos `action`/`credits`/`model`/`detail` seguem no payload, então um dock antigo continua
    funcionando.

    `_confirm_token` só existe quando `confirmed` é True (ADR-038 §3). Ele NÃO vai no payload do
    `ask` — nunca trafega no WebSocket nem chega ao modelo; volta apenas neste dict, para o
    chamador Python consumir antes de gerar.
    """
    payload = {"widget": "confirm_cost", "title": "Confirmar geração paga",
               "action": action, "credits": credits, "model": model, "detail": detail}
    if breakdown:
        payload["breakdown"] = breakdown
    ans = _ask(client, payload)
    if ans.get("answered") and ans.get("confirmed"):
        return {**ans, "_confirm_token": issue_confirm_token(action, model)}
    return ans


def open_screen(client: StudioClient, target: str, title: str = "", detail: str = "",
                label: str = "", params: dict | None = None) -> dict:
    """Pede ao usuário para abrir uma tela do Studio e concluir a edição lá (ADR-038, Onda C).

    `target` é o id da etapa/rota (ex.: "storyboard"); o dock navega e mostra "Concluí"/"Pular".
    Retorna {answered, done|skipped}.
    """
    return _ask(client, {"widget": "open", "title": title or f"Abrir a tela {target}",
                         "target": target, "detail": detail, "label": label or "Abrir a tela",
                         "params": params or {}})


# ---------- cartões que não bloqueiam ----------
def notify(client: StudioClient, text: str, level: str = "info") -> str:
    _emit(client, {"kind": "notify", "text": text, "level": level})
    return "ok"


def show(client: StudioClient, images: list[dict], title: str = "") -> str:
    """Mostra mídia no chat (imagens/vídeos). images: [{url, label?, kind?}]."""
    _emit(client, {"kind": "show", "title": title, "media": images})
    return "ok"
