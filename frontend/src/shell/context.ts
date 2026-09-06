// Contexto interno do shell — Wave 10 · E3 (card [REACT-04]).
//
// O estado que `studio/web/app.js` guardava em 12 variáveis de módulo (`steps`, `projects`, `pid`,
// `project`, `guideAll`, `view`, `area`, …) vive aqui, alimentado pelos hooks TanStack Query da E1
// (fonte única de prontidão — ADR-010 a) e pelo roteador de hash. As `renderMenu/renderTopbar` do
// vanilla viram re-render dos assinantes deste contexto.
import { createContext, useContext } from "react";

import type { GuideAll, Project, Step } from "../api";
import type { Area } from "./constants";
import type { Tema } from "./theme";

/** Alvo de navegação: id de etapa ou `"overview"`. */
export type AlvoNav = string;

export interface ShellApi {
  // ----- estado (derivado das queries da E1 + rota) -----
  steps: readonly Step[];
  projects: readonly Project[];
  /** `project.json` da campanha atual (pode ser o item da lista enquanto o detalhe carrega). */
  project: Project | null;
  guideAll: GuideAll | null;
  area: Area;
  pid: string | null;
  /** `"overview"` | id de etapa | `null` (nas áreas globais). */
  view: string | null;
  tema: Tema;
  /** `false` até `/api/steps` + `/api/projects` responderem — o `#main` mostra "Carregando…". */
  booted: boolean;

  // ----- ações (equivalentes aos handlers do bootstrap do `app.js`) -----
  navigate: (target: AlvoNav, opts?: { pid?: string; replace?: boolean }) => void;
  /** `Studio.go` — navega só para alvo válido (etapa `ready`/registrada ou `overview`). */
  go: (target: AlvoNav) => void;
  selectProject: (pid: string) => void;
  irParaMoodboards: () => void;
  irParaCreditos: () => void;
  irParaPersonagens: () => void;
  continuar: () => void;
  openWizard: () => void;
  openEdit: () => void;
  confirmResetStep: (stepId: string) => void;
  confirmResetCampaign: () => void;
  cycleTheme: () => void;
}

const ShellContext = createContext<ShellApi | null>(null);

export const ShellProvider = ShellContext.Provider;

/** Hook dos componentes do chrome (Sidebar, Rail, Topbar, Overview…). */
export function useShell(): ShellApi {
  const ctx = useContext(ShellContext);
  if (!ctx) throw new Error("useShell() fora do <ShellProvider>");
  return ctx;
}
