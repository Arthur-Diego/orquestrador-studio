// Tools que GASTAM crédito `[extensão]` (wave 11 · F10, ADR-016).
//
// Módulo próprio de propósito: cinco frentes da wave 11 tocam o `ChatDock.tsx`, e um mapa inline
// ali viraria conflito de rebase em todas. Aqui ele fica isolado e fácil de conferir.
//
// A lista espelha exatamente as funções que passam por `actions._paid` em `studio/mcp/actions.py`
// — as únicas que fazem POST num `gen_path` pago. Se uma tool paga nascer lá, ela entra aqui, e o
// saldo do dock volta a ficar correto sozinho.
const PAGAS = new Set([
  "mood_generate",
  "base_generate",
  "storyboard_scene_generate",
  "animate_generate",
  "music_generate",
]);

/** Tira o prefixo do MCP em qualquer das duas formas que o dock vê. */
function nu(nome: string): string {
  return nome.replace(/^mcp__studio__/, "").replace(/^studio\./, "");
}

/**
 * `true` quando o `tool_result` que chegou é de uma tool paga — o gatilho para reler o saldo.
 *
 * Aceita o nome completo (`mcp__studio__base_generate`, como vem no evento) e o encurtado
 * (`studio.base_generate`, como o `shortTool` do dock exibe), porque os dois circulam na área.
 */
export function isToolPaga(nome: string | undefined | null): boolean {
  return !!nome && PAGAS.has(nu(nome));
}

/** Espera antes de reler o saldo: `higgsfield account status` é subprocess de até 30 s, e duas
 *  tools pagas seguidas não podem empilhar duas leituras (risco 6 do FDD). */
export const DEBOUNCE_SALDO_MS = 1500;
