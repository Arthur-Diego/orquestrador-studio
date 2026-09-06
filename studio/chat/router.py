"""Rotas do chat (ADR-036): REST das abas + WebSocket do turno + endpoints internos do MCP.

O WebSocket `/ws/chat/{id}` recebe mensagens do usuário e transmite os eventos do turno; os
endpoints `/api/chats/{id}/ask|answer` são a ponte humano-no-laço (ADR-038), chamados pelo
subprocess do MCP e pelo browser. Tudo no mesmo processo (ADR-001) — sem segundo runtime.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from . import runtime, sessions
from .uibridge import bridge

router = APIRouter()


class NewChat(BaseModel):
    title: str = ""
    pid: str | None = None


class ChatPatch(BaseModel):
    title: str | None = None
    pid: str | None = None
    status: str | None = None


class AskBody(BaseModel):
    payload: dict
    timeout: float = 1800.0


class AnswerBody(BaseModel):
    ask_id: str
    answer: dict = {}


class EmitBody(BaseModel):
    event: dict


# ---------- gerenciador de WebSocket (chat_id -> sockets) ----------
class WSManager:
    def __init__(self) -> None:
        self._socks: dict[str, set[WebSocket]] = {}

    async def connect(self, chat_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._socks.setdefault(chat_id, set()).add(ws)

    def disconnect(self, chat_id: str, ws: WebSocket) -> None:
        self._socks.get(chat_id, set()).discard(ws)

    async def push(self, chat_id: str, event: dict) -> None:
        for ws in list(self._socks.get(chat_id, set())):
            try:
                await ws.send_json(event)
            except Exception:  # noqa: BLE001 — socket morto; a limpeza vem no disconnect
                self.disconnect(chat_id, ws)


manager = WSManager()
_turns: dict[str, asyncio.Task] = {}


# ---------- REST das abas ----------
@router.get("/api/chat/status")
def chat_status():
    """Saúde do runtime do chat para a UI: o CLI `claude` está disponível?"""
    return {"available": runtime.available()}


@router.get("/api/chats")
def list_chats(include_archived: bool = False):
    return [s.public() for s in sessions.list_sessions(include_archived=include_archived)]


@router.post("/api/chats")
def create_chat(req: NewChat):
    return sessions.create(req.title, req.pid).public()


@router.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    try:
        return sessions.get(chat_id).public()
    except KeyError as e:
        raise HTTPException(404, f"conversa não encontrada: {chat_id}") from e


@router.patch("/api/chats/{chat_id}")
def patch_chat(chat_id: str, req: ChatPatch):
    try:
        return sessions.patch(chat_id, **req.model_dump(exclude_none=True)).public()
    except KeyError as e:
        raise HTTPException(404, f"conversa não encontrada: {chat_id}") from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/chats/{chat_id}/events")
def chat_events(chat_id: str, after: int = 0):
    try:
        sessions.get(chat_id)
    except KeyError as e:
        raise HTTPException(404, f"conversa não encontrada: {chat_id}") from e
    return {"events": sessions.read_events(chat_id, after=after), "pending": bridge.pending(chat_id)}


@router.post("/api/chats/{chat_id}/stop")
def stop_chat(chat_id: str):
    task = _turns.get(chat_id)
    if task and not task.done():
        task.cancel()
    return {"stopped": bool(task)}


# ---------- ponte humano-no-laço (chamada pelo MCP e pelo browser) ----------
@router.post("/api/chats/{chat_id}/ask")
async def chat_ask(chat_id: str, req: AskBody):
    """Cria uma pergunta ao humano, empurra pelo WS e aguarda a resposta (ADR-038).

    Chamada pelo subprocess do MCP (tool `ui.*`). Bloqueia até o browser responder ou o timeout.
    """
    try:
        sessions.get(chat_id)
    except KeyError as e:
        raise HTTPException(404, f"conversa não encontrada: {chat_id}") from e
    ask = bridge.create(chat_id, req.payload)
    await manager.push(chat_id, {"kind": "ask", "ask_id": ask.id, **req.payload})
    return await bridge.wait(ask.id, timeout=req.timeout)


@router.post("/api/chats/{chat_id}/answer")
def chat_answer(req: AnswerBody):
    """Resolve uma pergunta pendente com a resposta do browser (ADR-038)."""
    return {"resolved": bridge.resolve(req.ask_id, req.answer)}


@router.post("/api/chats/{chat_id}/emit")
async def chat_emit(chat_id: str, req: EmitBody):
    """Empurra um cartão ao browser SEM esperar resposta (tools `ui.notify`/`ui.show`, ADR-038).

    Diferente de `/ask`, que bloqueia até o usuário responder. Persiste o evento no transcript.
    """
    try:
        sessions.get(chat_id)
    except KeyError as e:
        raise HTTPException(404, f"conversa não encontrada: {chat_id}") from e
    seq = sessions.append_event(chat_id, req.event)
    await manager.push(chat_id, {"seq": seq, **req.event})
    return {"emitted": True}


# ---------- WebSocket do turno ----------
@router.websocket("/ws/chat/{chat_id}")
async def chat_ws(ws: WebSocket, chat_id: str):
    try:
        sessions.get(chat_id)
    except KeyError:
        await ws.close(code=4004)
        return
    await manager.connect(chat_id, ws)
    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            if kind == "user":
                await _handle_user(chat_id, msg)
            elif kind == "answer":
                bridge.resolve(msg.get("ask_id", ""), msg.get("answer", {}))
            elif kind == "stop":
                task = _turns.get(chat_id)
                if task and not task.done():
                    task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(chat_id, ws)


async def _handle_user(chat_id: str, msg: dict) -> None:
    """Dispara o turno como task de fundo; o WS segue livre para `answer`/`stop`."""
    running = _turns.get(chat_id)
    if running and not running.done():
        await manager.push(chat_id, {"kind": "notify", "level": "warn",
                                     "text": "Ainda estou respondendo o turno anterior desta aba."})
        return
    text = (msg.get("text") or "").strip()
    if not text:
        return
    seq = sessions.append_event(chat_id, {"kind": "user", "text": text, "context": msg.get("context")})
    await manager.push(chat_id, {"seq": seq, "kind": "user", "text": text})
    _turns[chat_id] = asyncio.create_task(_run_turn(chat_id, text))


async def _run_turn(chat_id: str, text: str) -> None:
    sessions.patch(chat_id, status="running")
    try:
        async for event in runtime.run_turn(chat_id, text):
            seq = sessions.append_event(chat_id, event)
            await manager.push(chat_id, {"seq": seq, **event})
        sessions.patch(chat_id, status="idle")
    except asyncio.CancelledError:
        sessions.append_event(chat_id, {"kind": "notify", "level": "info", "text": "Turno interrompido."})
        await manager.push(chat_id, {"kind": "notify", "level": "info", "text": "Turno interrompido."})
        sessions.patch(chat_id, status="idle")
        raise
    except Exception as e:  # noqa: BLE001 — nunca deixa a aba presa em running
        sessions.append_event(chat_id, {"kind": "result", "is_error": True, "text": f"{type(e).__name__}: {e}"})
        await manager.push(chat_id, {"kind": "result", "is_error": True, "text": f"{type(e).__name__}: {e}"})
        sessions.patch(chat_id, status="error")
