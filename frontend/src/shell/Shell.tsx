// Shell React — Wave 10 · E3 (card [REACT-04]).
//
// O papel do `studio/web/app.js`: junta o roteamento por hash, as queries da E1 (fonte única de
// prontidão — ADR-010 a), os modais do wizard/edição/reset e a ponte vanilla (`bridge.ts`) num só
// lugar. O chrome (sidebar + topbar) é React reativo; o `#main` é gerenciado por um content-root
// dedicado quando o conteúdo é do shell (overview/sem-campanha/tela React) e CEDIDO à ponte
// quando é uma tela vanilla ou uma área global (que escrevem `#main.innerHTML` direto).
//
// Por que um content-root separado no `#main`: telas/áreas vanilla escrevem `#main.innerHTML`
// imperativamente. Misturar isso com filhos React no MESMO nó gera DOM duplicado na transição. O
// content-root deixa a troca de posse determinística: `render(null)` (síncrono via `flushSync`)
// limpa o conteúdo React antes da tela vanilla escrever; ao voltar, limpamos o resíduo vanilla
// antes de renderizar React de novo.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { createRoot, type Root } from "react-dom/client";
import { QueryClientProvider, useQueryClient } from "@tanstack/react-query";

import { api, apiUpload, useGuideSync, useProject, useProjectGuide, useProjects, useSteps } from "../api";
import type { Guide, Project } from "../api";
import { ShellProvider, type ShellApi } from "./context";
import { CR_ROUTE, MB_ROUTE } from "./constants";
import { useHashRouter } from "./router";
import { aplicarTema, proximoTema, temaSalvo, type Tema } from "./theme";
import { toast } from "./toast";
import { Bridge } from "./bridge";
import { PluginHost, temTelaReact } from "./host";
import type { StudioCtx } from "./plugin";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { NoProject, Overview } from "./Overview";
import { EditModal, ResetCampaignModal, ResetStepModal, WizardModal } from "./modals";

type ModalState =
  | { kind: "wizard" }
  | { kind: "edit" }
  | { kind: "resetStep"; stepId: string }
  | { kind: "resetCampaign" }
  | null;

export function Shell() {
  const qc = useQueryClient();

  // ----- dados (E1) -----
  const { data: steps } = useSteps();
  const { data: projects } = useProjects();
  const rota = useHashRouter(projects, steps);
  const { pid, view, area, sub } = rota;
  const { data: projectDetail } = useProject(pid);
  const { data: guideAll } = useProjectGuide(pid);
  const { onGuide } = useGuideSync(pid);

  const stepsList = useMemo(() => steps ?? [], [steps]);
  const projectsList = useMemo(() => projects ?? [], [projects]);
  const booted = Boolean(steps && projects);
  const project: Project | null =
    projectDetail ?? projectsList.find((p) => p.id === pid) ?? null;

  // ----- tema -----
  const [tema, setTema] = useState<Tema>(() => temaSalvo());
  useEffect(() => {
    aplicarTema(tema);
  }, [tema]);
  const cycleTheme = useCallback(() => setTema((t) => proximoTema(t)), []);

  // ----- modais -----
  const [modal, setModal] = useState<ModalState>(null);
  const [resetNonce, setResetNonce] = useState(0);

  // ----- refs de estado vivo para a ponte -----
  const pidRef = useRef<string | null>(pid);
  const projectRef = useRef<Project | null>(project);
  const stepsRef = useRef(stepsList);
  const navigateRef = useRef(rota.navigate);
  const onGuideRef = useRef(onGuide);
  pidRef.current = pid;
  projectRef.current = project;
  stepsRef.current = stepsList;
  navigateRef.current = rota.navigate;
  onGuideRef.current = onGuide;

  const confirmResetStep = useCallback((stepId: string) => setModal({ kind: "resetStep", stepId }), []);
  const confirmResetStepRef = useRef(confirmResetStep);
  confirmResetStepRef.current = confirmResetStep;

  // ----- ponte vanilla (criada uma vez) -----
  const bridgeRef = useRef<Bridge | null>(null);
  if (bridgeRef.current === null) {
    bridgeRef.current = new Bridge({
      getPid: () => pidRef.current,
      getProject: () => projectRef.current,
      getSteps: () => stepsRef.current,
      toast,
      navigate: (t, o) => navigateRef.current(t, o),
      onGuide: (id, g) => onGuideRef.current(id, g),
      confirmResetStep: (id) => confirmResetStepRef.current(id),
    });
  }
  const bridge = bridgeRef.current;
  useEffect(() => {
    bridge.atualizarSteps(stepsList);
  }, [bridge, stepsList]);

  // Chip do CLI e chip de créditos: geridos imperativamente pela `Studio.ui` vanilla (recon §6.4),
  // disparados no boot como o `app.js` faz.
  useEffect(() => {
    if (!booted) return;
    let vivo = true;
    void bridge.pronto.then(() => {
      if (!vivo) return;
      void window.Studio?.ui?.hfChip("#hfChipSide");
      void window.Studio?.ui?.refreshCredits(false);
    });
    return () => {
      vivo = false;
    };
  }, [bridge, booted]);

  // ----- ações do shell -----
  const navigate = rota.navigate;
  const go = useCallback(
    (target: string) => {
      const ready = stepsRef.current.some((s) => s.id === target && s.status === "ready");
      if (target === "overview" || ready) navigate(target);
    },
    [navigate],
  );
  const selectProject = useCallback((p: string) => navigate("overview", { pid: p }), [navigate]);
  const irParaMoodboards = useCallback(() => {
    if (location.hash === "#/moodboards") setResetNonce((n) => n + 1);
    else location.hash = "#/moodboards";
  }, []);
  const irParaCreditos = useCallback(() => {
    if (location.hash === "#/creditos") setResetNonce((n) => n + 1);
    else location.hash = "#/creditos";
  }, []);
  const continuar = useCallback(() => {
    const c = guideAll?.current;
    if (c) navigate(c);
  }, [guideAll, navigate]);
  const openWizard = useCallback(() => setModal({ kind: "wizard" }), []);
  const openEdit = useCallback(() => {
    if (pidRef.current) setModal({ kind: "edit" });
  }, []);
  const confirmResetCampaign = useCallback(() => {
    if (pidRef.current) setModal({ kind: "resetCampaign" });
  }, []);

  const shellApi: ShellApi = useMemo(
    () => ({
      steps: stepsList,
      projects: projectsList,
      project,
      guideAll: guideAll ?? null,
      area,
      pid,
      view,
      tema,
      booted,
      navigate,
      go,
      selectProject,
      irParaMoodboards,
      irParaCreditos,
      continuar,
      openWizard,
      openEdit,
      confirmResetStep,
      confirmResetCampaign,
      cycleTheme,
    }),
    [
      stepsList, projectsList, project, guideAll, area, pid, view, tema, booted,
      navigate, go, selectProject, irParaMoodboards, irParaCreditos, continuar,
      openWizard, openEdit, confirmResetStep, confirmResetCampaign, cycleTheme,
    ],
  );

  // ----- ctx do contrato de host do plugin React (para E4…E9) -----
  const studioCtx: StudioCtx = useMemo(
    () => ({
      api,
      apiUpload,
      toast,
      pid: () => pidRef.current,
      project: () => projectRef.current,
      files: (path: string) => `/files/${pidRef.current}/${path}`,
      guide: () => {
        const p = pidRef.current;
        const v = view;
        if (!p || !v) return;
        void api(`/api/projects/${encodeURIComponent(p)}/guide/${encodeURIComponent(v)}`)
          .then((g) => onGuideRef.current(v, g as Guide))
          .catch(() => onGuideRef.current(v, null));
      },
      onGuide: (id: string, g: Guide | null | undefined) => onGuideRef.current(id, g),
    }),
    [view],
  );

  // ----- content-root do #main -----
  const mainRef = useRef<HTMLElement>(null);
  const contentRootRef = useRef<Root | null>(null);
  const ownerRef = useRef<"react" | "vanilla" | null>(null);
  const vanillaKeyRef = useRef<string>("");

  useEffect(() => {
    const el = mainRef.current;
    if (!el) return;
    if (contentRootRef.current === null) contentRootRef.current = createRoot(el);
    const root = contentRootRef.current;

    const reactNode = computeReactNode({ booted, area, view, studioCtx });

    if (reactNode !== null) {
      if (ownerRef.current === "vanilla") el.innerHTML = ""; // remove resíduo vanilla
      ownerRef.current = "react";
      root.render(
        <QueryClientProvider client={qc}>
          <ShellProvider value={shellApi}>{reactNode}</ShellProvider>
        </QueryClientProvider>,
      );
      return;
    }

    // Conteúdo vanilla (tela por ponte ou área global).
    const key = `${area}|${view}|${sub}|${pid}|${resetNonce}`;
    if (ownerRef.current === "react") flushSync(() => root.render(null));
    if (ownerRef.current !== "vanilla" || vanillaKeyRef.current !== key) {
      ownerRef.current = "vanilla";
      vanillaKeyRef.current = key;
      if (area === MB_ROUTE) void bridge.openMoodboards(sub);
      else if (area === CR_ROUTE) void bridge.openCreditos(pid);
      else if (view) void bridge.showView(view, el);
    }
  }, [booted, area, view, sub, pid, resetNonce, shellApi, studioCtx, qc, bridge]);

  useEffect(() => {
    return () => {
      const root = contentRootRef.current;
      contentRootRef.current = null;
      if (root) setTimeout(() => root.unmount(), 0);
    };
  }, []);

  const fecharModal = useCallback(() => setModal(null), []);
  const aposReset = useCallback(() => setResetNonce((n) => n + 1), []);

  return (
    <ShellProvider value={shellApi}>
      <div className="app">
        <Sidebar />
        <div className="workspace">
          <Topbar />
          {/* #main NÃO recebe filhos do chrome: seu conteúdo é do content-root React (overview/
              sem-campanha/tela React) ou da ponte vanilla (telas/áreas que escrevem innerHTML). */}
          <main id="main" ref={mainRef} />
        </div>
      </div>
      <div id="toast" className="toast hidden" role="status" aria-live="polite" />

      {modal?.kind === "wizard" ? (
        <WizardModal onClose={fecharModal} onCreated={(p) => navigate("overview", { pid: p })} />
      ) : null}
      {modal?.kind === "edit" && pid && project ? (
        <EditModal pid={pid} atual={project} onClose={fecharModal} />
      ) : null}
      {modal?.kind === "resetStep" && pid ? (
        <ResetStepModal
          pid={pid}
          stepId={modal.stepId}
          cascata={cascataDeReset(stepsList, modal.stepId)}
          onClose={fecharModal}
          onDone={aposReset}
        />
      ) : null}
      {modal?.kind === "resetCampaign" && pid ? (
        <ResetCampaignModal pid={pid} onClose={fecharModal} onDone={aposReset} />
      ) : null}
    </ShellProvider>
  );
}

/** O que o shell renderiza no `#main`, ou `null` quando a posse é da ponte vanilla. */
function computeReactNode(args: {
  booted: boolean;
  area: string;
  view: string | null;
  studioCtx: StudioCtx;
}): React.ReactNode {
  const { booted, area, view, studioCtx } = args;
  if (!booted) return <div className="empty">Carregando…</div>;
  if (area !== "campaign") return null; // moodboards/creditos → vanilla
  if (view === "overview") return <Overview />;
  if (view === null) return <NoProject />; // sem campanhas (router zera view)
  if (view && temTelaReact(view)) return <PluginHost stepId={view} ctx={studioCtx} />;
  return null; // tela de etapa vanilla → ponte
}

/** `stepsFromHere` do vanilla: a etapa + as seguintes (a cascata que o reset apaga). */
function cascataDeReset(
  steps: readonly { id: string; n: number; title: string }[],
  stepId: string,
): { id: string; n: number; title: string }[] {
  const i = steps.findIndex((s) => s.id === stepId);
  return i < 0 ? [] : steps.slice(i).map((s) => ({ id: s.id, n: s.n, title: s.title }));
}
