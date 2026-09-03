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
// Em E3 nenhuma tela React existe: o glob resolve para `{}`, `temTelaReact` é sempre `false` e toda
// etapa cai na ponte vanilla (`bridge.ts`). Este host é o terreno pronto para E4…E9.
import { Suspense, lazy } from "react";
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
  /** Injeção para teste — o default é o glob real. */
  modulos?: MapaDeModulos;
}

/**
 * Monta a tela React da etapa dentro do `<StudioProvider>`, dando-lhe o `ctx` do contrato de host
 * (`plugin.ts`). O ciclo init/onProject/destroy é o do React: mount = init, unmount = destroy; a
 * troca de projeto remonta via `key={pid}` no chamador (recon §1.3, `wave-10.md` §E3).
 */
export function PluginHost({ stepId, ctx, modulos = MODULOS }: PluginHostProps) {
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
