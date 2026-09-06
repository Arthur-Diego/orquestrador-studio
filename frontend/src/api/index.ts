/**
 * Contrato tipado da API do Orquestrador Studio — Wave 10 · E1 (card [REACT-02], ADR-031).
 *
 * ```
 * schema.ts     gerado do /openapi.json que o FastAPI publica. NÃO editar à mão.
 * types.ts      as formas de RESPOSTA, escritas à mão (o backend não declara response_model).
 * http.ts       `api()` e `apiUpload()` — equivalentes exatos do vanilla, mapeamento de erro incluído.
 * client.ts     rotas, parâmetros e corpos tipados a partir do schema; `resposta<T>()`.
 * keys.ts       chaves de cache.
 * guide-sync.ts `onGuide` + recompute do agregado + debounce de 400 ms (ADR-010 item a mora aqui).
 * queries.ts    os hooks TanStack Query.
 * ```
 *
 * Consumidores: E2 (biblioteca de UI — `confirmCost`/`refreshCredits` batem em `/api/creditos/*`),
 * E3 (shell e a ponte `window.Studio`) e as seis frentes de tela da sub-wave 5.
 */
export { api, apiUpload, isApiError } from "./http";
export type { ApiError, CamposExtras } from "./http";

export { apiDelete, apiGet, apiPatch, apiPost, apiPut, request, resposta, rota } from "./client";
export type { Metodo, Opcoes, ParamsDaRota, Rota, RotasCom } from "./client";

export { chaves } from "./keys";

export {
  AgendadorDeRefresh,
  agendadorDoGuia,
  aplicarGuiaDaEtapa,
  DEBOUNCE_GUIA_MS,
  recomputarAgregado,
} from "./guide-sync";

export {
  criarQueryClient,
  invalidarGuia,
  useCreateProject,
  useGuideSync,
  useHiggsfieldStatus,
  usePatchProject,
  useProject,
  useProjectGuide,
  useProjects,
  useResetCampaign,
  useResetStep,
  useStepGuide,
  useSteps,
} from "./queries";
export type { CamposDaCampanha, NovaCampanha } from "./queries";

export type {
  Guide,
  GuideAll,
  GuideItem,
  HiggsfieldStatus,
  ItemStatus,
  Project,
  ProjectDetail,
  Step,
  StepStatus,
  SummaryKind,
} from "./types";

export type { components, operations, paths } from "./schema";
