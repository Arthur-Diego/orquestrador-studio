// Hook do WebSocket do chat (ADR-036, protocolo v2 do ADR-041): conecta em /ws/chat/{id}, faz
// replay do transcript e separa as duas naturezas do stream — o que é **transcript** (persistido,
// com `seq`) fica no array `events`; o que é **efêmero** (`assistant_delta`, `tool_progress`)
// alimenta o estado vivo `turn` e nunca entra no array. `busy` vem do par turn_started/turn_ended
// do servidor, com a heurística antiga de fallback. Reconexão robusta e replay incremental por
// `seq` seguem fora de escopo; aqui a conexão é única por aba, com replay inicial via GET /events.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../../api";
import type { ChatEvent, ChatSession, ChatToolProgress, ChatTurn } from "./types";

interface EventsResponse {
  events: ChatEvent[];
  pending: ChatEvent[];
}

/**
 * Eventos efêmeros do protocolo v2: chegam sem `seq`, nunca são gravados no `events.jsonl` e por
 * isso não entram no transcript do cliente. Evento efêmero novo entra nesta constante e ganha um
 * caso em `aplicarEfemero` — não um `if` paralelo no `onmessage`.
 */
const EFEMEROS = new Set<ChatEvent["kind"]>(["assistant_delta", "tool_progress"]);

/** Coalescência dos deltas: ~12 quadros por segundo de texto, sem re-render por caractere. */
const FLUSH_MS = 80;

const TURNO_VAZIO: ChatTurn = { id: null, text: "", progress: {} };

/** Último turno aberto do transcript: `turn_started` sem o `turn_ended` do mesmo `turn_id`. */
function turnoAbertoNoTranscript(evs: ChatEvent[]): string | null {
  let aberto: string | null = null;
  for (const ev of evs) {
    if (ev.kind === "turn_started") aberto = ev.turn_id ?? null;
    else if (ev.kind === "turn_ended" && (ev.turn_id == null || ev.turn_id === aberto)) aberto = null;
  }
  return aberto;
}

/** Heurística das conversas antigas (sem par de turno): último `user` depois do último `result`. */
function busyHeuristico(evs: ChatEvent[]): boolean {
  let r = -1;
  let u = -1;
  evs.forEach((e, i) => {
    if (e.kind === "result") r = i;
    if (e.kind === "user") u = i;
  });
  return u > r;
}

function semChave(mapa: Record<string, ChatToolProgress>, chave: string): Record<string, ChatToolProgress> {
  const copia = { ...mapa };
  delete copia[chave];
  return copia;
}

/**
 * @param chatId aba ativa; `null` desconecta e zera tudo.
 * @param onEvent (Wave 11 · F03) chamado APENAS para mensagens que chegam ao vivo pelo WebSocket,
 *   nunca no replay de `GET /api/chats/{id}/events`. É o seam que separa "o transcript tem isto" de
 *   "isto acabou de acontecer": um efeito sobre o array `events` reprocessaria o replay inteiro ao
 *   abrir a aba e dispararia recarga de todas as etapas tocadas na história da conversa.
 * @param status (Wave 11 · F02) status da aba vindo do polling de `GET /api/chats` que o dock já
 *   faz. É opcional de propósito: mantém a chamada de um argumento só (contrato `[cross-feature]`
 *   com a F09) e evita que o hook abra uma requisição própria. Sem ele, um turno aberto no replay é
 *   tratado como obsoleto — o pior caso vira o comportamento de hoje, nunca um dock preso em
 *   "Respondendo…".
 *
 * Os dois parâmetros novos são opcionais e o retorno só cresce: chamadores antigos seguem válidos.
 */
export function useChatSocket(
  chatId: string | null,
  onEvent?: (ev: ChatEvent) => void,
  status?: ChatSession["status"] | null,
) {
  const [events, setEvents] = useState<ChatEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [turn, setTurn] = useState<ChatTurn>(TURNO_VAZIO);
  const wsRef = useRef<WebSocket | null>(null);
  // Os deltas se acumulam fora do estado: o React só vê o texto no flush.
  const bufferRef = useRef("");
  const flushRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Turnos que o replay trouxe abertos mas que já morreram; ignorados para sempre.
  const obsoletosRef = useRef<Set<string>>(new Set());
  /** Persistidos que chegaram pelo socket ANTES de o replay resolver — fundidos quando ele chega. */
  const vivosRef = useRef<ChatEvent[]>([]);
  const replayResolvidoRef = useRef(false);
  const statusRef = useRef(status);
  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  const limparFlush = useCallback(() => {
    if (flushRef.current !== null) {
      clearTimeout(flushRef.current);
      flushRef.current = null;
    }
    bufferRef.current = "";
  }, []);

  const aplicarEfemero = useCallback((ev: ChatEvent) => {
    if (ev.kind === "assistant_delta") {
      bufferRef.current += ev.text ?? "";
      if (flushRef.current === null) {
        flushRef.current = setTimeout(() => {
          flushRef.current = null;
          const texto = bufferRef.current;
          setTurn((t) => (t.text === texto ? t : { ...t, text: texto }));
        }, FLUSH_MS);
      }
      return;
    }
    // `tool_progress`: estado vivo indexado pelo `tool_use_id` do `tool_call` correspondente.
    const id = ev.id;
    if (!id) return;
    const progresso: ChatToolProgress = { id, pct: ev.pct ?? null, label: ev.label, state: ev.state };
    setTurn((t) => ({ ...t, progress: { ...t.progress, [id]: progresso } }));
  }, []);

  const aplicarPersistido = useCallback(
    (ev: ChatEvent) => {
      switch (ev.kind) {
        case "turn_started": {
          const id = ev.turn_id ?? null;
          if (id && obsoletosRef.current.has(id)) return;
          limparFlush();
          setTurn({ id, text: "", progress: {} });
          return;
        }
        case "turn_ended":
          limparFlush();
          setTurn(TURNO_VAZIO);
          return;
        case "assistant_text":
          // Invariante: o texto final é sempre o do evento persistido, nunca a soma dos deltas.
          limparFlush();
          setTurn((t) => (t.text === "" ? t : { ...t, text: "" }));
          return;
        case "tool_result": {
          // A tool fechou: o progresso dela deixa de ser corrente (o chip passa a ler o transcript).
          const id = ev.id;
          setTurn((t) => (id && t.progress[id] ? { ...t, progress: semChave(t.progress, id) } : t));
          return;
        }
        default:
          return;
      }
    },
    [limparFlush],
  );

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
      setTurn(TURNO_VAZIO);
      return;
    }
    let cancelled = false;
    setEvents([]);
    setTurn(TURNO_VAZIO);
    bufferRef.current = "";
    obsoletosRef.current = new Set();
    vivosRef.current = [];
    replayResolvidoRef.current = false;

    void api(`/api/chats/${chatId}/events`)
      .then((r) => {
        if (cancelled) return;
        const replay = (r as EventsResponse).events ?? [];
        // O socket abre junto com esta requisição: um evento AO VIVO pode chegar antes de a
        // resposta do replay resolver. `setEvents(replay)` puro apagaria esse evento — e se o que
        // se perdeu foi o `turn_ended`, o dock reabriria um turno já morto e travaria em
        // "Respondendo…". Por isso a fusão, com o vivo mandando (ele é mais novo por construção).
        const vistos = new Set(replay.map((e) => e.seq).filter((s) => s != null));
        const vivos = vivosRef.current.filter((e) => e.seq == null || !vistos.has(e.seq));
        vivosRef.current = [];
        replayResolvidoRef.current = true;
        const completo = [...replay, ...vivos];
        setEvents(completo);
        const aberto = turnoAbertoNoTranscript(completo);
        if (!aberto) return;
        if (statusRef.current === "running") {
          // Turno de verdade em andamento: o dock reabriu no meio dele.
          setTurn((t) => ({ ...t, id: aberto }));
        } else {
          // Turno aberto no disco com a aba fora de `running`. O `status` vem do polling de 4 s do
          // dock, então ele pode estar velho: a marca é PROVISÓRIA e qualquer evento ao vivo com
          // este `turn_id` a desfaz (ver `reviver`). Sem isso, trocar de aba no meio de um turno
          // dentro da janela do polling mataria o feedback pelo resto do turno.
          obsoletosRef.current.add(aberto);
          setTurn((t) => (t.id === aberto ? TURNO_VAZIO : t));
        }
      })
      .catch(() => undefined);

    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/chat/${chatId}`);
    wsRef.current = ws;
    ws.onopen = () => !cancelled && setConnected(true);
    ws.onclose = () => !cancelled && setConnected(false);
    ws.onmessage = (m) => {
      if (cancelled) return;
      let ev: ChatEvent;
      try {
        ev = JSON.parse(m.data) as ChatEvent;
      } catch {
        return; /* linha inválida ignorada */
      }
      // Só aqui: o replay acima (`GET /events`) alimenta `setEvents` e não passa por este ramo.
      // Vale para todo evento ao vivo, efêmero inclusive — quem filtra por `kind` é o assinante.
      onEventRef.current?.(ev);
      // Um evento AO VIVO deste turno é a prova mais forte que existe de que ele não é obsoleto —
      // mais forte que o `status`, que vem do polling de 4 s e pode estar velho. A marca cai aqui.
      if (ev.turn_id && obsoletosRef.current.delete(ev.turn_id) && ev.kind !== "turn_ended") {
        setTurn((t) => (t.id === ev.turn_id ? t : { id: ev.turn_id!, text: "", progress: {} }));
      }
      if (EFEMEROS.has(ev.kind)) {
        aplicarEfemero(ev);
        return;
      }
      // Persistidos: transcript (dedup por `seq`, que o efêmero não tem) e ciclo de vida do turno.
      if (!replayResolvidoRef.current) vivosRef.current.push(ev);
      setEvents((prev) => (ev.seq != null && prev.some((p) => p.seq === ev.seq) ? prev : [...prev, ev]));
      aplicarPersistido(ev);
    };
    return () => {
      cancelled = true;
      limparFlush();
      ws.close();
      wsRef.current = null;
    };
  }, [chatId, aplicarEfemero, aplicarPersistido, limparFlush]);

  const send = useCallback((text: string, context?: unknown) => {
    wsRef.current?.send(JSON.stringify({ type: "user", text, context }));
  }, []);
  const answer = useCallback((askId: string, value: unknown) => {
    wsRef.current?.send(JSON.stringify({ type: "answer", ask_id: askId, answer: value }));
  }, []);
  const stop = useCallback(() => wsRef.current?.send(JSON.stringify({ type: "stop" })), []);

  const busy = useMemo(() => {
    // Com pares de turno no transcript quem manda é o servidor; sem eles, a heurística de sempre.
    if (events.some((e) => e.kind === "turn_started")) return turn.id !== null;
    return busyHeuristico(events);
  }, [events, turn.id]);

  return { events, connected, send, answer, stop, turn, busy };
}
