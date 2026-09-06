// Tipos do assistente de chat (ADR-036) — área global do shell.

/** Uma aba de chat (espelha `studio/chat/sessions.Session`). */
export interface ChatSession {
  id: string;
  title: string;
  pid: string | null;
  turns: number;
  status: "idle" | "running" | "error" | "archived";
  created: string;
  updated: string;
}

/** Evento do transcript/stream (protocolo do WebSocket, `studio/chat/runtime.normalize_event`). */
export interface ChatEvent {
  seq?: number;
  ts?: string;
  kind: "user" | "assistant_text" | "tool_call" | "tool_result" | "result" | "ask" | "notify" | "show" | "system" | "raw";
  widget?: string;
  media?: unknown;
  title?: string;
  options?: unknown;
  images?: unknown;
  fields?: unknown;
  target?: string;
  label?: string;
  text?: string;
  name?: string;
  input?: Record<string, unknown>;
  id?: string;
  is_error?: boolean;
  cost?: number | null;
  level?: string;
  ask_id?: string;
  // payload de `ask` (Onda B): kind do widget, imagens, opções…
  [k: string]: unknown;
}
