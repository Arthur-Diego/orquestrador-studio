"""Ponte humano-no-laço (ADR-038): o agente pergunta, o browser responde.

Uma tool `ui.*` (Onda B) roda dentro do subprocess do MCP e faz um POST em
`/api/chats/{id}/ask`. O router chama `bridge.create(...)`, empurra o pedido pelo WebSocket para
o browser e **aguarda** a Future. O browser mostra o widget (grade de imagens, custo, formulário),
o usuário responde e o browser faz POST em `/api/chats/{id}/answer`, que resolve a Future — a tool
recebe a resposta e devolve ao agente.

Sem browser conectado (uso no terminal) a tool detecta a ausência de contexto e degrada para
"pergunte em texto" — este bridge nunca é acionado ali.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field


@dataclass
class Ask:
    id: str
    chat_id: str
    payload: dict
    future: asyncio.Future = field(repr=False)


class UiBridge:
    """Mapa `ask_id -> Future`, vivo no processo do Studio (ADR-001, single-process)."""

    def __init__(self) -> None:
        self._asks: dict[str, Ask] = {}

    def create(self, chat_id: str, payload: dict) -> Ask:
        ask_id = uuid.uuid4().hex
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        ask = Ask(id=ask_id, chat_id=chat_id, payload=payload, future=fut)
        self._asks[ask_id] = ask
        return ask

    async def wait(self, ask_id: str, timeout: float) -> dict:
        """Espera a resposta do browser. Timeout devolve `{answered: False}` (a tool re-pergunta)."""
        ask = self._asks.get(ask_id)
        if ask is None:
            return {"answered": False, "error": "ask desconhecido"}
        try:
            return await asyncio.wait_for(ask.future, timeout=timeout)
        except asyncio.TimeoutError:
            return {"answered": False, "error": "timeout — o usuário não respondeu a tempo"}
        finally:
            self._asks.pop(ask_id, None)

    def resolve(self, ask_id: str, answer: dict) -> bool:
        """Resolve o ask com a resposta do browser. Retorna False se o ask não existe mais."""
        ask = self._asks.get(ask_id)
        if ask is None or ask.future.done():
            return False
        ask.future.set_result({"answered": True, **answer})
        return True

    def pending(self, chat_id: str) -> list[dict]:
        """Perguntas em aberto de uma aba (para o browser re-render após reconexão)."""
        return [{"ask_id": a.id, **a.payload} for a in self._asks.values() if a.chat_id == chat_id]


#: Instância única do processo (ADR-001). O router e as tools `ui.*` a compartilham.
bridge = UiBridge()
