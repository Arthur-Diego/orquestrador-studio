// Hook do WebSocket do chat (ADR-036): conecta em /ws/chat/{id}, faz replay do transcript e
// acumula os eventos do turno. Reconexão robusta e replay incremental por `seq` vêm na Onda C;
// aqui a conexão é única por aba, com replay inicial via GET /events.
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../../api";
import type { ChatEvent } from "./types";

interface EventsResponse {
  events: ChatEvent[];
  pending: ChatEvent[];
}

export function useChatSocket(chatId: string | null) {
  const [events, setEvents] = useState<ChatEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!chatId) {
      setEvents([]);
      setConnected(false);
      return;
    }
    let cancelled = false;
    setEvents([]);
    void api(`/api/chats/${chatId}/events`)
      .then((r) => {
        if (!cancelled) setEvents((r as EventsResponse).events ?? []);
      })
      .catch(() => undefined);

    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/chat/${chatId}`);
    wsRef.current = ws;
    ws.onopen = () => !cancelled && setConnected(true);
    ws.onclose = () => !cancelled && setConnected(false);
    ws.onmessage = (m) => {
      if (cancelled) return;
      try {
        const ev = JSON.parse(m.data) as ChatEvent;
        setEvents((prev) => (ev.seq != null && prev.some((p) => p.seq === ev.seq) ? prev : [...prev, ev]));
      } catch {
        /* linha inválida ignorada */
      }
    };
    return () => {
      cancelled = true;
      ws.close();
      wsRef.current = null;
    };
  }, [chatId]);

  const send = useCallback((text: string, context?: unknown) => {
    wsRef.current?.send(JSON.stringify({ type: "user", text, context }));
  }, []);
  const answer = useCallback((askId: string, value: unknown) => {
    wsRef.current?.send(JSON.stringify({ type: "answer", ask_id: askId, answer: value }));
  }, []);
  const stop = useCallback(() => wsRef.current?.send(JSON.stringify({ type: "stop" })), []);

  return { events, connected, send, answer, stop };
}
