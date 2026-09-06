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

/**
 * Item de mídia de um cartão do dock — formato do `ui.show` (`{url, label?, kind?}`) mais os dois
 * campos de pareamento do Contrato 4 (Wave 11 · F11): `role` diz de que lado do antes/depois o item
 * está e `pair` é o `id` da candidata nova a que ele pertence. Os dois só existem quando o produtor
 * é `base_review`; item de `ui.show` (e dos `*_pick`) não tem nenhum dos dois.
 */
export interface AskMediaItem {
  url: string;
  label?: string;
  kind?: string;
  role?: "before" | "after";
  pair?: string;
}

/**
 * Botão de ação de um `ask` estendido (Contrato 4, ADR-038). `value` é o objeto EXATO que o dock
 * devolve como resposta do `ask`; `for` amarra o botão ao cartão daquela candidata e, sem ele, o
 * botão é global e aparece abaixo da grade.
 */
export interface AskAction {
  label: string;
  value: unknown;
  for?: string;
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
    | "state_changed"
    // Wave 11 · F02 (ADR-041), aditivo: ciclo de vida do turno (persistidos, com `seq`)…
    | "turn_started"
    | "turn_ended"
    // …e os efêmeros, que chegam sem `seq` e nunca são gravados no `events.jsonl`.
    | "assistant_delta"
    | "tool_progress";
  widget?: string;
  media?: unknown;
  title?: string;
  options?: unknown;
  images?: unknown;
  // payload `ask` estendido (Wave 11 · F11, Contrato 4): botões que respondem o ask com um `value`
  // pronto. Aditivo e opcional — `ask` vindo dos `*_pick` não traz a chave, e o dock guarda o ramo
  // novo por `actions?.length`. `unknown` como as irmãs acima: a validação é do consumidor.
  actions?: unknown;
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
  /** `turn_started`/`turn_ended`/`assistant_delta`/`tool_progress`: o turno a que o evento pertence. */
  turn_id?: string;
  /** `turn_ended`: por que o turno terminou. */
  reason?: ChatTurnReason;
  /** `tool_progress`: 0 a 100, ou `null` quando o job não expõe `total` (nunca inventar 0 %). */
  pct?: number | null;
  /** `tool_progress`: o `state` do job lido pelo servidor. */
  state?: ChatJobState;
  /** `[extensão]` wave 11 (ADR-016): o `CostPreview` inteiro no `ask` de `confirm_cost`, para o
   *  dock renderizar as mesmas linhas do `CostSheet`. Ausente = cartão legado de duas linhas. */
  breakdown?: unknown;
  // payload de `ask` (Onda B): kind do widget, imagens, opções…
  [k: string]: unknown;
}

/** Motivo do `turn_ended` (contrato 2 do FDD chat-feedback). */
export type ChatTurnReason = "done" | "error" | "stopped";

/** `state` do job carregado pelo `tool_progress` (contrato 4). */
export type ChatJobState = "running" | "done" | "error" | "idle";

/** Progresso vivo de uma tool pendente, indexado pelo `tool_call.id` correspondente. */
export interface ChatToolProgress {
  id: string;
  /** 0 a 100, ou `null` quando o total é desconhecido — a tela omite o `%` nesse caso. */
  pct: number | null;
  /** Texto curto já em português, montado pelo servidor (`Etapa refs: 13/31`). Não remontar. */
  label?: string | undefined;
  state?: ChatJobState | undefined;
}

/**
 * Estado **vivo** do turno: o que chega pelo WS e não é persistido no transcript.
 * Fica fora do array `events` de propósito (invariante 2 do FDD) e é zerado a cada `turn_ended`.
 */
export interface ChatTurn {
  /** `turn_id` do turno aberto, ou `null` fora de turno (inclusive turno obsoleto). */
  id: string | null;
  /** Texto do bloco em construção, já coalescido; some quando o `assistant_text` do bloco chega. */
  text: string;
  /** Progresso corrente por `tool_call.id`. */
  progress: Record<string, ChatToolProgress>;
}
