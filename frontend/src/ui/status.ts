// Mapas de status do guia — Wave 10 · E2 (card [REACT-03]).
//
// Equivalentes de `Studio.ui.STATUS_LABEL`, `ITEM_LABEL` e `STATUS_KIND` do vanilla
// (`studio/web/ui.js`). O menu, a visão geral e o painel de guia usam os MESMOS mapas, então eles
// vivem num módulo só (o `<Guide>` e o shell da E3 importam daqui).
import type { ItemStatus, StepStatus } from "../api";

/** Rótulo pt-BR de cada status de etapa. */
export const STATUS_LABEL: Record<StepStatus, string> = {
  todo: "a fazer",
  blocked: "bloqueada",
  in_progress: "em andamento",
  done: "concluída",
  unknown: "sem guia",
};

/** Rótulo pt-BR de cada status de item (entrada, saída, validação). */
export const ITEM_LABEL: Record<ItemStatus, string> = {
  ok: "ok",
  fail: "falta",
  todo: "a fazer",
  warn: "atenção",
};

/** Status da etapa → `kind` do chip (menu, visão geral e painel usam o mesmo mapa). */
export const STATUS_KIND: Record<StepStatus, string> = {
  done: "done",
  in_progress: "in_progress",
  blocked: "blocked",
  todo: "todo",
  unknown: "unknown",
};
