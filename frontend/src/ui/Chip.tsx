// Chip — Wave 10 · E2 (card [REACT-03]).
//
// Equivalente de `Studio.ui.chip(text, kind)` do vanilla: `<span class="chip <kind>">text</span>`.
// Todos os `kind` existem em `style.css` (ok, done, warn, fail, blocked, todo, info, in_progress,
// unknown, mode). O default é "mode", como no vanilla.
import type { ReactNode } from "react";

/** Variação de cor do chip; cada valor tem regra em `style.css`. */
export type ChipKind =
  | "ok"
  | "done"
  | "warn"
  | "fail"
  | "blocked"
  | "todo"
  | "info"
  | "in_progress"
  | "unknown"
  | "mode";

export interface ChipProps {
  kind?: ChipKind;
  children: ReactNode;
}

/** `<span class="chip <kind>">…</span>` — mesmo DOM que o `Studio.ui.chip` do vanilla emite. */
export function Chip({ kind = "mode", children }: ChipProps) {
  return <span className={`chip ${kind}`}>{children}</span>;
}
