// Tipo ambiente de `window.Studio` — Wave 10 · E10 (card [REACT-11]).
//
// Antes da E10 esta declaração morava em `frontend/src/shell/bridge.ts`, a ponte strangler que
// hospedava as telas vanilla. Com a ponte removida (todas as 10 telas e as 3 áreas globais são
// React), o global `window.Studio` sobrevive APENAS como escape hatch imperativo que os cenários de
// QA dirigem — `window.Studio.{moodboards,creditos}.open(...)` (recon §3.10/§3.11) — mais o shim
// `ui.refreshCredits` que a Topbar instala para que uma geração paga reflita o novo saldo no chip
// global (recon §6.4). Não há mais `register/go/onGuide/ctx/steps`: o shell React é o dono do
// roteamento e do ciclo de vida das telas.
interface StudioUiShim {
  /** Instalado pela Topbar (E10): relê o saldo e atualiza o chip `#btnCredits`. */
  refreshCredits?: (refresh?: boolean) => unknown;
}

interface StudioGlobal {
  /** Instalado pela `MoodboardsArea` React (E6) — dirigido por `scripts/qa/cenarios/moodboards.py`. */
  moodboards?: { open: (mbid: string | null) => void; goList: () => void; goEditor: (mbid: string) => void };
  /** Instalado pela `CreditosArea` React (E6) — dirigido por `scripts/qa/cenarios/creditos.py`. */
  creditos?: { open: (pid: string | null) => void };
  /** Escape hatch do saldo, instalado pela Topbar (E10). */
  ui?: StudioUiShim;
}

declare global {
  interface Window {
    Studio?: StudioGlobal;
  }
}

export {};
