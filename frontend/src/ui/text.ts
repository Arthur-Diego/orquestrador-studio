// Helpers de texto do design system — Wave 10 · E2 (card [REACT-03]).
//
// Equivalentes exatos de `Studio.ui.esc` e `Studio.ui.fmtPct` do vanilla (`studio/web/ui.js`).
// No React o JSX já escapa interpolações, então `esc` raramente é necessário na marcação; ele
// permanece no contrato porque alguns pontos ainda montam string (ex.: `aria-label`, ou telas
// que constroem HTML derivado) e para paridade 1:1 com o vanilla enquanto os dois mundos convivem.

/** Escapa texto para interpolar em HTML. Mesmo mapa de caracteres do `Studio.ui.esc` do vanilla. */
export function esc(s: unknown): string {
  return String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] ?? c,
  );
}

/** `0.42 → "42%"` (aceita também 42 quando o valor já vem em porcentagem). Igual ao vanilla. */
export function fmtPct(x: unknown): string {
  const v = Number(x) || 0;
  return `${Math.round(v <= 1 ? v * 100 : v)}%`;
}
