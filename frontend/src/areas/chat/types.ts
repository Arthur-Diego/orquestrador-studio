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
  kind:
    | "user"
    | "assistant_text"
    | "tool_call"
    | "tool_result"
    | "result"
    | "ask"
    | "notify"
    | "show"
    | "system"
    | "raw"
    // Wave 11 · F03 (ADR-041): aviso de "a etapa X da campanha Y mudou". Aditivo — nenhum kind
    // existente muda de forma, e um cliente antigo o ignora (o `switch` do dock cai em `default`).
    | "state_changed";
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
  // payload de `state_changed` (Wave 11 · F03): campanha afetada (`null` = mudança global da
  // biblioteca), id da etapa, o que mudou e o nome curto da tool que causou. A interface já tem
  // index signature, então isto é precisão de tipo, não campo novo no wire.
  pid?: string | null;
  step?: string;
  scope?: string;
  tool?: string;
  /** `[extensão]` wave 11 (ADR-016): o `CostPreview` inteiro no `ask` de `confirm_cost`, para o
   *  dock renderizar as mesmas linhas do `CostSheet`. Ausente = cartão legado de duas linhas. */
  breakdown?: unknown;
  // payload de `ask` (Onda B): kind do widget, imagens, opções…
  [k: string]: unknown;
}
