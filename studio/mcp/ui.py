"""Tools `ui.*` (ADR-038): o agente pergunta, o browser responde.

Cada helper faz um POST em `/api/chats/{chat_id}/ask` (bloqueia até o usuário responder ou o
timeout) ou `/emit` (empurra um cartão sem esperar). O `chat_id` vem do env `STUDIO_CHAT_ID` que o
runtime injeta no MCP da aba. Sem `chat_id` (uso no terminal), `ask` devolve `{answered:False,
no_ui:True}` e o chamador degrada para "pergunte/confirme em texto".
"""
from __future__ import annotations

import os
from typing import Any

from .client import StudioClient


def chat_id() -> str | None:
    return os.environ.get("STUDIO_CHAT_ID") or None


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


def confirm_cost(client: StudioClient, action: str, credits: Any, model: str, detail: str = "") -> dict:
    """Sheet de custo (ADR-016/038). Retorna {answered, confirmed}."""
    return _ask(client, {"widget": "confirm_cost", "title": "Confirmar geração paga",
                         "action": action, "credits": credits, "model": model, "detail": detail})


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
