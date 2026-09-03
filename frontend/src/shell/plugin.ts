// Contrato de host do plugin de tela React — Wave 10 · E3 (card [REACT-04]).
//
// ESTE É O PRINCIPAL "PROVIDES" DA E3: a API que as seis frentes de tela (E4…E9) consomem para
// escrever `studio/etapas/<id>/ui/index.tsx`. É o equivalente React do contrato vanilla
// `Studio.register(id, ctx => ({init, onProject?, destroy?}))` documentado no recon §1.2/§1.3.
//
// ## Descoberta (sem registry central — ADR-031/ADR-032)
//
// O host descobre as telas por `import.meta.glob('../../etapas/*/ui/index.tsx')` (ver `host.tsx`),
// exatamente como o vanilla as descobria por `/steps/<id>/view.js`. Criar etapa nova continua sendo
// criar SÓ a pasta dela; ninguém edita o shell (ADR-010 c). Em E3 nenhuma tela React existe ainda:
// todas as 10 telas são vanilla, hospedadas pela ponte (`bridge.ts`). Este contrato é o terreno
// pronto para E4+.
//
// ## O ciclo `init / onProject / destroy` em React
//
// O `wave-10.md` §E3 promete o ciclo `init/onProject/destroy`. O recon §1.3 registra que, no
// vanilla, `showView` NUNCA chama `onProject` — ele é vestigial; a troca de projeto remonta a tela
// inteira via `applyRoute → showView`. A E3 formaliza a tradução para React, preservando o
// comportamento OBSERVÁVEL:
//
// | vanilla                         | React (este contrato)                                   |
// | ------------------------------- | ------------------------------------------------------- |
// | `factory(ctx)` + `inst.init()`  | montar o componente default do módulo (efeito de mount) |
// | `inst.destroy()` no `showView`  | desmontar o componente (cleanup dos efeitos)            |
// | trocar de projeto → remonta     | o host remonta com `key={pid}` (init/destroy no lugar   |
// |                                 | de `onProject`) — o vestígio vira a remontagem real     |
//
// Ou seja: uma tela React NÃO precisa de `onProject`; ela lê o projeto por `ctx.project()` e é
// remontada quando o `pid` muda, o que dá o mesmo efeito com um único caminho de código. Uma tela
// que queira reagir a troca de projeto SEM remontar continua podendo, por um `useEffect` sobre
// `ctx.pid()`.
import { createContext, useContext } from "react";

import type { api, apiUpload } from "../api";
import type { Guide, Project } from "../api";

/**
 * O contexto que cada tela React recebe — o equivalente tipado de `Studio.ctx`
 * (`studio/web/app.js:68-75`). Os campos que eram getters no vanilla continuam getters aqui,
 * porque leem estado vivo do shell (a campanha atual muda sem a tela remontar em alguns fluxos).
 */
export interface StudioCtx {
  /** `api(path, opts)` da E1 — mesmo tratamento de `detail → Error.message` do vanilla. */
  api: typeof api;
  /** POST multipart tipado da E1 (o `upload` do `ctx` vanilla saía por `Studio.ui.upload`). */
  apiUpload: typeof apiUpload;
  /** Toast global (`#toast`). */
  toast: (msg: string) => void;
  /** Campanha atual, ou `null`. Getter: reflete a troca de campanha em tempo real. */
  pid: () => string | null;
  /** `project.json` da campanha atual, ou `null`. */
  project: () => Project | null;
  /** URL servível de um arquivo do projeto: `/files/<pid>/<path>`. */
  files: (path: string) => string;
  /**
   * Recarrega o guia da etapa em exibição e reconcilia o rail/topbar/visão geral — o
   * `ctx.guide()` do vanilla (`Studio.ui.renderGuide(currentStep)`), agora via a query da E1.
   * Chamado pela tela após QUALQUER ação que mexa em artefato.
   */
  guide: () => void;
  /**
   * Avisa o shell que o guia de uma etapa chegou (ADR-010 a) — encaminha para `useGuideSync`. As
   * telas que buscam o guia por conta própria (via `<StepGuide>` da E2) já chamam isto pelo
   * `onGuide` do componente; exposto aqui para telas que buscam o guia de outro jeito.
   */
  onGuide: (stepId: string, g: Guide | null | undefined) => void;
}

const StudioContext = createContext<StudioCtx | null>(null);

/** Provider do contexto — o host o monta em volta da tela React. */
export const StudioProvider = StudioContext.Provider;

/**
 * Hook que uma tela React usa para pegar o seu `ctx`. Fora de uma tela hospedada, lança — o mesmo
 * contrato do vanilla, onde uma tela sem `Studio.ctx` também não funcionava.
 */
export function useStudio(): StudioCtx {
  const ctx = useContext(StudioContext);
  if (!ctx) {
    throw new Error(
      "useStudio() fora do host de plugin. A tela precisa estar montada por " +
        "`studio/etapas/<id>/ui/index.tsx` sob o shell da E3.",
    );
  }
  return ctx;
}
