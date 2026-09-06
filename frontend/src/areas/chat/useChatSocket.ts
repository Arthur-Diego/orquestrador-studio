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

export function useChatSocket(
  chatId: string | null,
  /**
   * Chamado APENAS para mensagens que chegam ao vivo pelo WebSocket, nunca no replay de
   * `GET /api/chats/{id}/events` (Wave 11 · F03, Contrato 5). É o seam que separa "o transcript
   * tem isto" de "isto acabou de acontecer": um efeito sobre o array `events` reprocessaria o
   * replay inteiro ao abrir a aba e dispararia recarga de todas as etapas tocadas na história da
   * conversa. O parâmetro é opcional e o retorno não muda — chamadores atuais seguem válidos.
   */
  onEvent?: (ev: ChatEvent) => void,
) {
  const [events, setEvents] = useState<ChatEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // A ref existe para o efeito NÃO depender da identidade do callback: o dock passa uma arrow nova
  // a cada render, e pôr `onEvent` no array de dependências reconectaria o socket a cada render.
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  });

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
        // Só aqui: o replay acima (`GET /events`) alimenta `setEvents` e não passa por este ramo.
        onEventRef.current?.(ev);
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
