"""Rotas do chat (ADR-036): REST das abas + WebSocket do turno + endpoints internos do MCP.

O WebSocket `/ws/chat/{id}` recebe mensagens do usuário e transmite os eventos do turno; os
endpoints `/api/chats/{id}/ask|answer` são a ponte humano-no-laço (ADR-038), chamados pelo
subprocess do MCP e pelo browser. Tudo no mesmo processo (ADR-001) — sem segundo runtime.
"""
from __future__ import annotations

import asyncio
import calendar
import contextlib
import os
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from . import mudancas, runtime, sessions
from .uibridge import bridge

router = APIRouter()

#: Teto de conversas gerando AO MESMO TEMPO (abas paralelas, Onda C). Protege GPU/assinatura/memória
#: numa máquina local. Uma aba a mais espera o usuário liberar uma; não há fila automática.
MAX_ACTIVE = int(os.environ.get("STUDIO_CHAT_MAX_ACTIVE", "3"))

#: Eventos de FEEDBACK, não de transcript: vão direto ao WS, sem `seq` e sem `events.jsonl`.
#: O texto do delta é reemitido inteiro pelo `assistant_text` e o progresso é transitório —
#: persistir duplicaria o transcript e quebraria o replay (FDD §6, invariante 2).
EFEMEROS = frozenset({"assistant_delta", "tool_progress"})


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
    """Lista as abas. Resposta idêntica à de sempre; antes de listar, sanea aba órfã.

    Aba com `status == "running"` sem task viva em `_turns` é resíduo de reinício do servidor: sem
    o saneamento, o pontinho da aba e o `busy` derivado do transcript ficariam presos para sempre
    (FDD contrato 8).
    """
    return [_saneada(s).public() for s in sessions.list_sessions(include_archived=include_archived)]


def _saneada(s):
    """`running` sem task viva → `idle`. Qualquer outro estado passa intacto."""
    if s.status != "running":
        return s
    task = _turns.get(s.id)
    if task is not None and not task.done():
        return s
    try:
        return sessions.patch(s.id, status="idle")
    except (KeyError, ValueError, OSError):  # aba sumiu do disco entre o list e o patch
        return s


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


@router.get("/api/chats/{chat_id}/trace")
def chat_trace(chat_id: str):
    """Observabilidade (Onda E): o que o assistente fez nesta aba — tools chamadas, custo, turnos.

    Derivado do transcript (`events.jsonl`), sem estado novo. Alimenta o painel "o que o assistente
    fez" por campanha e a contagem de uso por aba.
    """
    try:
        sess = sessions.get(chat_id)
    except KeyError as e:
        raise HTTPException(404, f"conversa não encontrada: {chat_id}") from e
    eventos = sessions.read_events(chat_id)
    tools_por_nome: dict[str, int] = {}
    custo = 0.0
    erros = 0
    for e in eventos:
        if e.get("kind") == "tool_call":
            nome = (e.get("name") or "").replace("mcp__studio__", "")
            tools_por_nome[nome] = tools_por_nome.get(nome, 0) + 1
        elif e.get("kind") == "result":
            if isinstance(e.get("cost"), (int, float)):
                custo += float(e["cost"])
            if e.get("is_error"):
                erros += 1
    return {"chat_id": chat_id, "title": sess.title, "pid": sess.pid, "turns": sess.turns,
            "events": len(eventos), "tools": tools_por_nome, "usd_estimado": round(custo, 4),
            "erros": erros, **_metricas_de_turno(eventos)}


def _metricas_de_turno(eventos: list[dict]) -> dict:
    """Métricas derivadas dos pares `turn_started`/`turn_ended` do transcript (FDD §7).

    O par funciona como o span do turno: `turnos_iniciados` conta as aberturas,
    `turnos_interrompidos` os fechamentos com `reason == "stopped"` e `duracao_media_s` é a média
    dos `ts` de cada par correlacionado por `turn_id`. Transcript antigo (sem pares) devolve zeros.
    """
    iniciados = 0
    interrompidos = 0
    abertos: dict[str, str] = {}
    duracoes: list[float] = []
    for e in eventos:
        kind = e.get("kind")
        if kind == "turn_started":
            iniciados += 1
            if e.get("turn_id"):
                abertos[e["turn_id"]] = e.get("ts") or ""
        elif kind == "turn_ended":
            if e.get("reason") == "stopped":
                interrompidos += 1
            inicio = abertos.pop(e.get("turn_id") or "", None)
            dur = _duracao_s(inicio, e.get("ts"))
            if dur is not None:
                duracoes.append(dur)
    media = round(sum(duracoes) / len(duracoes), 1) if duracoes else 0
    return {"turnos_iniciados": iniciados, "turnos_interrompidos": interrompidos,
            "duracao_media_s": media}


def _duracao_s(inicio: str | None, fim: str | None) -> float | None:
    """Segundos entre dois `ts` do transcript (`%Y-%m-%dT%H:%M:%SZ`), ou None se ilegível."""
    if not inicio or not fim:
        return None
    try:
        a = calendar.timegm(time.strptime(inicio, "%Y-%m-%dT%H:%M:%SZ"))
        b = calendar.timegm(time.strptime(fim, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return None
    return max(0.0, float(b - a))


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
    ativos = sum(1 for cid, t in _turns.items() if cid != chat_id and not t.done())
    if ativos >= MAX_ACTIVE:
        await manager.push(chat_id, {"kind": "notify", "level": "warn",
                                     "text": f"Já há {ativos} conversas gerando ao mesmo tempo (limite {MAX_ACTIVE}). "
                                             "Espere uma terminar e envie de novo."})
        return
    text = (msg.get("text") or "").strip()
    if not text:
        return
    seq = sessions.append_event(chat_id, {"kind": "user", "text": text, "context": msg.get("context")})
    await manager.push(chat_id, {"seq": seq, "kind": "user", "text": text})
    _turns[chat_id] = asyncio.create_task(_run_turn(chat_id, text))


async def _run_turn(chat_id: str, text: str) -> None:
    """Roda um turno e conta ao browser quando ele começa e quando acaba.

    O par `turn_started`/`turn_ended` é o estado ocupado vindo do SERVIDOR (antes o cliente
    adivinhava pelo transcript). `turn_started` é o primeiro evento depois do `user`, antes de
    tocar no subprocess; `turn_ended` sai do `finally` — e não dos ramos — porque é a única forma
    de garantir o par em TODOS os caminhos de saída (FDD §6, invariante 1).

    `reason` (FDD contrato 2): `done` quando o `result` do CLI chegou (com ou sem `is_error`);
    `error` quando o turno morreu por exceção OU terminou sem `result` (o runtime sintetizou um);
    `stopped` quando o usuário cancelou.
    """
    turn_id = uuid4().hex[:12]
    reason = "error"  # sem passar por nenhum caminho conhecido, o turno morreu
    sem_resultado = False
    sessions.patch(chat_id, status="running")
    # `tool_call.id` -> mudança pendente. Local ao turno: um `tool_call` órfão morre com ele.
    pendentes: dict[str, tuple[str, str, str, str | None]] = {}
    try:
        await _persistir_e_empurrar(chat_id, {"kind": "turn_started", "turn_id": turn_id})
        async for event in runtime.run_turn(chat_id, text):
            if event.get("kind") in EFEMEROS:  # feedback: WS direto, sem seq e sem disco
                await manager.push(chat_id, {"turn_id": turn_id, **event})
                continue  # efêmero nunca vira `state_changed`: não é evento de transcript
            if event.get("kind") == "result" and event.get("synthetic"):
                sem_resultado = True  # o CLI não fechou o ciclo (runtime sintetizou o result)
            await _persistir_e_empurrar(chat_id, event)
            for mudanca in mudancas.derivar(event, pendentes):  # F03: chat → telas
                await _persistir_e_empurrar(chat_id, mudanca)
        sessions.patch(chat_id, status="idle")
        reason = "error" if sem_resultado else "done"
    except asyncio.CancelledError:
        reason = "stopped"
        sessions.append_event(chat_id, {"kind": "notify", "level": "info", "text": "Turno interrompido."})
        await manager.push(chat_id, {"kind": "notify", "level": "info", "text": "Turno interrompido."})
        sessions.patch(chat_id, status="idle")
        raise
    except Exception as e:  # noqa: BLE001 — nunca deixa a aba presa em running
        reason = "error"
        sessions.append_event(chat_id, {"kind": "result", "is_error": True, "text": f"{type(e).__name__}: {e}"})
        await manager.push(chat_id, {"kind": "result", "is_error": True, "text": f"{type(e).__name__}: {e}"})
        sessions.patch(chat_id, status="error")
    finally:
        fim = {"kind": "turn_ended", "turn_id": turn_id, "reason": reason}
        seq = sessions.append_event(chat_id, fim)  # o par no disco é o que o replay lê
        # O WS pode já ter morrido junto com o turno; o transcript acima é a garantia.
        with contextlib.suppress(Exception):
            await manager.push(chat_id, {"seq": seq, **fim})


async def _persistir_e_empurrar(chat_id: str, event: dict) -> None:
    """Evento de transcript: grava (ganha `seq` e `ts`) e empurra pelo WS."""
    seq = sessions.append_event(chat_id, event)
    await manager.push(chat_id, {"seq": seq, **event})
