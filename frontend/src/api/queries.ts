/**
 * Hooks TanStack Query do núcleo — catálogo de etapas, campanhas, guia e status do CLI.
 *
 * Este é o único lugar do frontend onde as respostas do backend ganham tipo (`as GuideAll`,
 * `as Step[]`…). A asserção é consciente e está justificada em `types.ts`: o FastAPI não declara
 * `response_model`, então o contrato publicado descreve caminhos, parâmetros e corpos de
 * requisição, mas não respostas. Concentrar as asserções aqui é o que evita que cada tela invente
 * a sua.
 *
 * Os defaults de cache reproduzem o vanilla, que não tinha camada de cache nenhuma: sem retry
 * automático, sem refetch ao focar a janela, e cada tela pedindo o que precisa quando precisa.
 * Ver `criarQueryClient()`.
 */
import {
  QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";

import { apiGet, apiPatch, apiPost, resposta } from "./client";
import type { components } from "./schema";
import { agendadorDoGuia, aplicarGuiaDaEtapa, type AgendadorDeRefresh } from "./guide-sync";
import { chaves } from "./keys";
import type { Guide, GuideAll, HiggsfieldStatus, Project, ProjectDetail, Step } from "./types";

/**
 * `QueryClient` com os defaults desta aplicação.
 *
 * - `retry: false` — o vanilla não retenta nada. Um POST de geração que falhou por 409 (CLI
 *   deslogado) retentado 3 vezes viraria 3 toasts e, em rotas não idempotentes, 3 efeitos.
 * - `refetchOnWindowFocus: false` — o vanilla só refaz request por ação do usuário ou pelo
 *   `scheduleGuideRefresh`. Refetch ao focar a aba dispararia requests que hoje não existem, e o
 *   harness de QA alterna foco entre janelas.
 * - `staleTime: 0` — default do vanilla: sempre que alguém pede, vai ao servidor. Os hooks que
 *   têm razão para divergir disso a declaram explicitamente (ver `useSteps`).
 */
export function criarQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

/** Opções que um chamador pode ajustar sem poder trocar a chave nem a função de fetch. */
type Ajustes<T> = Omit<UseQueryOptions<T, Error, T, readonly unknown[]>, "queryKey" | "queryFn">;

/**
 * `GET /api/steps` — o catálogo do curso.
 *
 * `staleTime: Infinity` porque o catálogo é imutável enquanto o processo do backend vive: ele sai
 * de `studio/steps.py::SOON` fundido com os plugins descobertos no import. O vanilla carrega isto
 * uma única vez, no `boot()`, e guarda na variável de módulo `steps` pelo resto da sessão — este é
 * o equivalente.
 */
export function useSteps(ajustes?: Ajustes<Step[]>): UseQueryResult<Step[], Error> {
  return useQuery({
    queryKey: chaves.etapas(),
    queryFn: () => resposta<Step[]>(apiGet("/api/steps")),
    staleTime: Infinity,
    ...ajustes,
  });
}

/**
 * `GET /api/projects` — as campanhas.
 *
 * O erro NÃO é engolido aqui, ao contrário do `loadProjects()` do vanilla, que faz
 * `.catch(() => [])`. Aquilo é política do shell (campanha nenhuma → empty-state com `#btnFirst`),
 * não do transporte: quem decide o que fazer com a falha é a E3, lendo `isError`. Um hook que
 * transforma falha em lista vazia mente para todo consumidor futuro.
 */
export function useProjects(ajustes?: Ajustes<Project[]>): UseQueryResult<Project[], Error> {
  return useQuery({
    queryKey: chaves.projetos(),
    queryFn: () => resposta<Project[]>(apiGet("/api/projects")),
    ...ajustes,
  });
}

/** `GET /api/projects/{pid}` — `project.json` + progresso. Desabilitado enquanto `pid` for nulo. */
export function useProject(
  pid: string | null | undefined,
  ajustes?: Ajustes<ProjectDetail>,
): UseQueryResult<ProjectDetail, Error> {
  return useQuery({
    queryKey: chaves.projeto(pid ?? ""),
    queryFn: () =>
      resposta<ProjectDetail>(apiGet("/api/projects/{pid}", { params: { pid: pid as string } })),
    enabled: Boolean(pid),
    ...ajustes,
  });
}

/**
 * `GET /api/projects/{pid}/guide` — o agregado das 11 etapas.
 *
 * É a **única** fonte de prontidão de etapa no frontend (ADR-010, item a). O rail, o pipeline
 * segmentado da topbar e a visão geral leem daqui; ninguém deriva status de artefato.
 */
export function useProjectGuide(
  pid: string | null | undefined,
  ajustes?: Ajustes<GuideAll>,
): UseQueryResult<GuideAll, Error> {
  return useQuery({
    queryKey: chaves.guia(pid ?? ""),
    queryFn: () =>
      resposta<GuideAll>(apiGet("/api/projects/{pid}/guide", { params: { pid: pid as string } })),
    enabled: Boolean(pid),
    ...ajustes,
  });
}

/**
 * `GET /api/projects/{pid}/guide/{step}` — o guia de uma etapa.
 *
 * Equivale ao `fetch` de `Studio.ui.renderGuide` (`studio/web/ui.js:700`). Quem usar este hook
 * dentro de uma tela precisa avisar o agregado do resultado, como o `renderGuide` faz ao chamar
 * `Studio.onGuide` — use `useGuideSync().onGuide` para isso.
 */
export function useStepGuide(
  pid: string | null | undefined,
  step: string | null | undefined,
  ajustes?: Ajustes<Guide>,
): UseQueryResult<Guide, Error> {
  return useQuery({
    queryKey: chaves.guiaDaEtapa(pid ?? "", step ?? ""),
    queryFn: () =>
      resposta<Guide>(
        apiGet("/api/projects/{pid}/guide/{step}", { params: { pid: pid as string, step: step as string } }),
      ),
    enabled: Boolean(pid && step),
    ...ajustes,
  });
}

/**
 * `GET /api/higgsfield/status` — o chip do CLI (`Studio.ui.hfChip`, `studio/web/ui.js:83`).
 *
 * Sem opção de `refresh`, de propósito: a rota aceita `?refresh=1`, mas **nenhum consumidor do
 * frontend a usa** hoje (o único `fetch` é o do `hfChip`, sem query). O backend já cacheia o
 * status por 60 s (`studio/higgsfield.py::STATUS_TTL`), que é o que torna o parâmetro dispensável
 * na UI. Se algum dia a E2 precisar forçar, o caminho é `apiGet("/api/higgsfield/status",
 * { query: { refresh: true } })` seguido de `setQueryData(chaves.higgsfield(), ...)` — e NÃO uma
 * segunda chave de cache, que deixaria o chip visível mostrando o valor velho.
 */
export function useHiggsfieldStatus(
  ajustes?: Ajustes<HiggsfieldStatus>,
): UseQueryResult<HiggsfieldStatus, Error> {
  return useQuery({
    queryKey: chaves.higgsfield(),
    queryFn: () => resposta<HiggsfieldStatus>(apiGet("/api/higgsfield/status")),
    ...ajustes,
  });
}

// ---------- mutações do núcleo ----------

/** Corpo de `POST /api/projects` — o modelo Pydantic `NewProject`, direto do contrato publicado. */
export type NovaCampanha = components["schemas"]["NewProject"];
/** Corpo de `PATCH /api/projects/{pid}` — o modelo Pydantic `ProjectPatch`. */
export type CamposDaCampanha = components["schemas"]["ProjectPatch"];

/** `POST /api/projects`. Invalida a lista de campanhas; 409 (nome duplicado/reservado) chega como `Error`. */
export function useCreateProject(): UseMutationResult<Project, Error, NovaCampanha> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => resposta<Project>(apiPost("/api/projects", { body })),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: chaves.projetos(), exact: true });
    },
  });
}

/** `PATCH /api/projects/{pid}`. Invalida a campanha e a lista — nome e formato aparecem nas duas. */
export function usePatchProject(): UseMutationResult<
  Project,
  Error,
  { pid: string; campos: CamposDaCampanha }
> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pid, campos }) =>
      resposta<Project>(apiPatch("/api/projects/{pid}", { params: { pid }, body: campos })),
    onSuccess: (_dado, { pid }) => {
      void qc.invalidateQueries({ queryKey: chaves.projeto(pid), exact: true });
      void qc.invalidateQueries({ queryKey: chaves.projetos(), exact: true });
    },
  });
}

/**
 * `POST /api/projects/{pid}/steps/{step}/reset` — reset em cascata `[extensão]`.
 *
 * Invalida o agregado do guia e o guia da etapa: o reset apaga artefatos de várias etapas, então o
 * status de todas elas muda. Aqui NÃO cabe atualização otimista — só o backend sabe o que caiu.
 */
export function useResetStep(): UseMutationResult<unknown, Error, { pid: string; step: string }> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pid, step }) =>
      apiPost("/api/projects/{pid}/steps/{step}/reset", { params: { pid, step } }),
    onSuccess: (_dado, { pid }) => invalidarGuia(qc, pid),
  });
}

/** `POST /api/projects/{pid}/reset` — reset da campanha inteira `[extensão]`. */
export function useResetCampaign(): UseMutationResult<unknown, Error, { pid: string }> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ pid }) => apiPost("/api/projects/{pid}/reset", { params: { pid } }),
    onSuccess: (_dado, { pid }) => invalidarGuia(qc, pid),
  });
}

/**
 * Depois de um reset o guia inteiro é suspeito: agregado, guias por etapa e o progresso do projeto.
 *
 * Pública desde a Wave 11 · F03 (Contrato 6) para o `ChatDock` chamá-la ao receber `state_changed`.
 * **Só invalida**: não escreve cache, não deriva prontidão e não decide navegação — é por isso que
 * serve ao chat sem abrir exceção ao ADR-010 item a. O corpo não mudou; só a visibilidade.
 */
export function invalidarGuia(qc: QueryClient, pid: string): void {
  void qc.invalidateQueries({ queryKey: chaves.guia(pid), exact: true });
  void qc.invalidateQueries({ queryKey: ["studio", "guia-etapa", pid] });
  void qc.invalidateQueries({ queryKey: chaves.projeto(pid), exact: true });
}

// ---------- a ponte `Studio.onGuide` ----------

/**
 * Devolve o `onGuide` que a E3 pendura em `window.Studio.onGuide` e que as telas React chamam
 * depois de renderizar o próprio guia.
 *
 * O `pid` é lido de um `ref` atualizado a cada render — e não capturado na closure — porque o
 * vanilla lê a variável de módulo `pid` **dentro** do `setTimeout` do debounce: trocar de campanha
 * durante os 400 ms cancela o refresh da campanha antiga em vez de disparar um GET dela.
 *
 * `cancelar` existe para o teardown do shell e para os testes. O hook não cancela sozinho no
 * unmount de propósito: o timer do vanilla é global e sobrevive a qualquer troca de tela, e
 * abortá-lo mudaria o comportamento observável (o rail deixaria de reconciliar depois da última
 * ação de uma tela que acabou de sair).
 */
export function useGuideSync(
  pid: string | null | undefined,
  agendador: AgendadorDeRefresh = agendadorDoGuia,
): {
  onGuide: (stepId: string, g: Guide | null | undefined) => void;
  cancelar: () => void;
} {
  const qc = useQueryClient();
  const { data: etapas } = useSteps();

  const pidRef = useRef<string | null>(pid ?? null);
  const ordemRef = useRef<readonly string[]>([]);
  useEffect(() => {
    pidRef.current = pid ?? null;
  }, [pid]);
  useEffect(() => {
    ordemRef.current = (etapas ?? []).map((s) => s.id);
  }, [etapas]);

  const lerPid = useCallback(() => pidRef.current, []);

  const onGuide = useCallback(
    (stepId: string, g: Guide | null | undefined) => {
      aplicarGuiaDaEtapa(qc, lerPid, stepId, g, ordemRef.current, agendador);
    },
    [qc, lerPid, agendador],
  );

  const cancelar = useCallback(() => agendador.cancelar(), [agendador]);

  return { onGuide, cancelar };
}
