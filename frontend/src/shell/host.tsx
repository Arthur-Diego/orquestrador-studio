// Host de descoberta de telas React — Wave 10 · E3 (card [REACT-04]).
//
// Descobre as telas React por `import.meta.glob`, sem registry central (ADR-031/ADR-032): criar
// etapa nova é criar SÓ `studio/etapas/<id>/ui/index.tsx`. É o equivalente React do
// `/steps/<id>/view.js` que o vanilla injetava.
//
// NOTA sobre o caminho do glob: o `wave-10.md` §E3 escreve `'../../etapas/*/ui/index.tsx'` de forma
// esquemática. Deste arquivo (`frontend/src/shell/host.tsx`), o caminho REAL até `studio/etapas/`
// é `../../../studio/etapas/*/ui/index.tsx` (o `studio/` é irmão de `frontend/` na raiz). O padrão
// de teste do Vitest já aponta para lá (`vite.config.ts`: `../studio/etapas/*/ui/**`).
//
// As 10 telas migraram nas E4…E9: o glob resolve para os 10 `ui/index.tsx` e `temTelaReact` é `true`
// para todas. A ponte vanilla foi removida na E10 (card [REACT-11]) — este host é o único caminho.
import { Suspense, lazy, useEffect } from "react";
import type { ComponentType } from "react";

import { StudioProvider, type StudioCtx } from "./plugin";

/** Cada módulo default-exporta o componente React da tela. */
type ModuloDeTela = { default: ComponentType };
type MapaDeModulos = Record<string, () => Promise<ModuloDeTela>>;

/**
 * O mapa de telas React descobertas em build. `eager: false` = import dinâmico (code-splitting por
 * tela), como o vanilla carregava o `view.js` sob demanda.
 */
const MODULOS: MapaDeModulos = import.meta.glob("../../../studio/etapas/*/ui/index.tsx") as MapaDeModulos;

function chaveDoModulo(stepId: string): string {
  return `../../../studio/etapas/${stepId}/ui/index.tsx`;
}

/** Existe uma tela React para esta etapa? (Falso em E3 para todas — todas são vanilla.) */
export function temTelaReact(stepId: string, modulos: MapaDeModulos = MODULOS): boolean {
  return chaveDoModulo(stepId) in modulos;
}

export interface PluginHostProps {
  stepId: string;
  ctx: StudioCtx;
  /**
   * Abre o reset da etapa (o modal `ResetStepModal` do shell). O SHELL é dono desse botão
   * (ADR-010: a tela nunca o conhece); o host o injeta no `header.stephead` da tela React, como a
   * ponte `bridge.injectStepReset` faz para as telas vanilla. Ausente = sem injeção (ex.: teste).
   */
  onResetStep?: (stepId: string) => void;
  /** Injeção para teste — o default é o glob real. */
  modulos?: MapaDeModulos;
}

/**
 * Injeta o botão `.shell-reset` ("Resetar etapa [extensão]") no `header.stephead` da tela React —
 * paridade com `bridge.injectStepReset` do vanilla (recon §1.3, passo 5). A tela renderiza só o
 * conteúdo do stephead (eyebrow/h2/lede); o botão do shell é acrescentado como último filho, na
 * mesma posição textual do vanilla (importa para o diff de `textContent` do ADR-004). O botão é
 * anexado imperativamente e o `MutationObserver` reinjeta se algum re-render o remover — as telas
 * do lote têm stephead de estrutura fixa, então na prática ele fica no lugar sem churn.
 */
function useShellReset(stepId: string, onResetStep?: (stepId: string) => void): void {
  useEffect(() => {
    if (!onResetStep) return;
    const main = document.getElementById("main");
    if (!main) return; // fora do shell (ex.: render de teste do PluginHost) — nada a injetar
    const injetar = () => {
      const head = main.querySelector("header.stephead");
      if (!head || head.querySelector(".shell-reset")) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "shell-reset ghost";
      btn.textContent = "Resetar etapa [extensão]";
      btn.title = "Apaga o que esta etapa e as seguintes produziram; mantém nome, produto, vibe e formato";
      btn.addEventListener("click", () => onResetStep(stepId));
      head.appendChild(btn);
    };
    injetar();
    const obs = new MutationObserver(injetar);
    obs.observe(main, { childList: true, subtree: true });
    return () => {
      obs.disconnect();
      main.querySelector("header.stephead .shell-reset")?.remove();
    };
  }, [stepId, onResetStep]);
}

/**
 * Monta a tela React da etapa dentro do `<StudioProvider>`, dando-lhe o `ctx` do contrato de host
 * (`plugin.ts`). O ciclo init/onProject/destroy é o do React: mount = init, unmount = destroy; a
 * troca de projeto remonta via `key={pid}` no chamador (recon §1.3, `wave-10.md` §E3).
 */
export function PluginHost({ stepId, ctx, onResetStep, modulos = MODULOS }: PluginHostProps) {
  useShellReset(stepId, onResetStep);
  const carregar = modulos[chaveDoModulo(stepId)];
  if (!carregar) {
    // Não deveria acontecer: o chamador só monta o host quando `temTelaReact` é verdadeiro.
    return <div className="empty">Tela React não encontrada para a etapa {stepId}.</div>;
  }
  const Tela = lazy(carregar);
  return (
    <StudioProvider value={ctx}>
      <Suspense fallback={<div className="empty">Carregando…</div>}>
        <Tela />
      </Suspense>
    </StudioProvider>
  );
}
