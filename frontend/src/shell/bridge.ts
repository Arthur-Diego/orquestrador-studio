// Ponte de compatibilidade `window.Studio` — Wave 10 · E3 (card [REACT-04]).
//
// Estratégia strangler-fig (ADR-032): enquanto as 10 telas ainda são vanilla, o shell React as
// HOSPEDA com o contrato IDÊNTICO ao do `studio/web/app.js` (recon §1.2/§1.3). As telas vanilla
// dependem do `window.Studio.ui` IMPERATIVO (modal, progressJob, upload, drop, poll, renderGuide,
// tile…) — que não tem equivalente chamável nos componentes React da E2. Por isso a ponte REUSA os
// próprios assets vanilla, que seguem servidos por `/static` e intocados até a E10:
//
//   /static/ui.js         → cria `window.Studio.ui` (biblioteca imperativa) + o listener de data-copy
//   /static/multishot.js  → `window.Studio.multishot` (ADR-017)
//   /static/moodboards.js → `window.Studio.moodboards` (ADR-013) — renderiza em `#main`
//   /static/creditos.js   → `window.Studio.creditos` (ADR-016) — renderiza em `#main`
//
// O shell React assume o papel do `app.js`: monta `window.Studio.{register, go, onGuide, ctx,
// steps}` e reproduz `showView`. `ui.js` faz `window.Studio = window.Studio || {}`, então montar o
// nosso `window.Studio` ANTES de carregá-lo preserva tudo; ui.js só acrescenta `.ui`.
//
// Os cenários `shell.py`/`overview.py` são o oráculo: rodam nas DUAS UIs. Zero timers órfãos após
// trocar de etapa exige que `destroyCurrent()` chame o `destroy()` da tela vanilla (que para os
// polls) — igual ao vanilla.
import type { Guide, Project, Step } from "../api";
import { api, apiUpload } from "../api";

/** Interface real devolvida por uma fábrica de tela vanilla (`recon §1.3`). */
interface InstanciaVanilla {
  init: () => void;
  onProject?: () => void;
  destroy?: () => void;
}
type FabricaVanilla = (ctx: StudioCtxVanilla) => InstanciaVanilla;

/** O `Studio.ctx` que as telas vanilla recebem (`app.js:68-75`). */
interface StudioCtxVanilla {
  $: (sel: string) => Element | null;
  api: typeof api;
  toast: (m: string) => void;
  pid: () => string | null;
  project: () => Project | null;
  files: (path: string) => string;
  guide: () => unknown;
}

interface StudioGlobal {
  ui?: Record<string, (...args: unknown[]) => unknown> & {
    renderGuide: (stepId: string, el?: Element | null) => Promise<Guide | null>;
    hfChip: (elOrSel: string | Element) => Promise<unknown>;
    refreshCredits: (refresh?: boolean) => Promise<unknown>;
  };
  moodboards?: { open: (mbid: string | null) => void };
  creditos?: { open: (pid: string | null) => void };
  register?: (id: string, factory: FabricaVanilla) => void;
  go?: (target: string) => void;
  onGuide?: (stepId: string, g: Guide | null | undefined) => void;
  ctx?: StudioCtxVanilla;
  steps?: readonly Step[];
}

declare global {
  interface Window {
    Studio?: StudioGlobal;
  }
}

/** Dependências que o shell React injeta na ponte. */
export interface BridgeDeps {
  getPid: () => string | null;
  getProject: () => Project | null;
  getSteps: () => readonly Step[];
  toast: (m: string) => void;
  navigate: (target: string, opts?: { pid?: string; replace?: boolean }) => void;
  /** Encaminha para `useGuideSync().onGuide` (ADR-010 a): rail/topbar/visão geral reagem. */
  onGuide: (stepId: string, g: Guide | null | undefined) => void;
  /** O reset é do shell (ADR-010): injetado no `header.stephead`, abre o modal React. */
  confirmResetStep: (stepId: string) => void;
}

const VANILLA_SCRIPTS = ["/static/ui.js", "/static/multishot.js", "/static/moodboards.js", "/static/creditos.js"];

function carregarScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    // Idempotente: em HMR/te teste o script pode já estar no DOM.
    if (document.querySelector(`script[data-bridge='${src}']`)) return resolve();
    const s = document.createElement("script");
    s.src = src;
    s.dataset.bridge = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`falha ao carregar ${src}`));
    document.body.appendChild(s);
  });
}

export class Bridge {
  private readonly deps: BridgeDeps;
  private readonly factories: Record<string, FabricaVanilla> = {};
  private readonly instances: Record<string, InstanciaVanilla> = {};
  private readonly loaded = new Set<string>();
  private currentStep: string | null = null;
  readonly pronto: Promise<void>;

  constructor(deps: BridgeDeps) {
    this.deps = deps;
    this.instalarGlobal();
    this.pronto = this.carregarVanilla();
  }

  /** Monta `window.Studio.{register, go, onGuide, ctx, steps}` — o papel do `app.js`. */
  private instalarGlobal(): void {
    const g: StudioGlobal = (window.Studio = window.Studio || {});
    const ctx: StudioCtxVanilla = {
      $: (sel) => document.querySelector(sel),
      api,
      toast: this.deps.toast,
      pid: this.deps.getPid,
      project: this.deps.getProject,
      files: (path) => `/files/${this.deps.getPid()}/${path}`,
      guide: () => this.currentStep && g.ui?.renderGuide(this.currentStep),
    };
    g.ctx = ctx;
    g.register = (id, factory) => {
      this.factories[id] = factory;
    };
    g.go = (target) => {
      const rd = this.deps.getSteps().some((s) => s.id === target && s.status === "ready");
      if (target === "overview" || this.factories[target] || rd) this.deps.navigate(target);
    };
    g.onGuide = (stepId, guia) => this.deps.onGuide(stepId, guia);
  }

  private async carregarVanilla(): Promise<void> {
    for (const src of VANILLA_SCRIPTS) await carregarScript(src);
    // `Studio.steps` é lido por `Studio.ui.guide` para "Ir para a etapa N".
    if (window.Studio) window.Studio.steps = this.deps.getSteps();
  }

  /** Mantém `Studio.steps` fresco quando o catálogo chega/atualiza. */
  atualizarSteps(steps: readonly Step[]): void {
    if (window.Studio) window.Studio.steps = steps;
  }

  /** `destroyCurrent` do vanilla: para os polls da tela anterior (zero timers órfãos no QA). */
  destroyCurrent(): void {
    const cur = this.currentStep;
    if (cur && this.instances[cur]?.destroy) {
      try {
        this.instances[cur]!.destroy!();
      } catch {
        /* uma tela quebrada não impede a troca */
      }
    }
    this.currentStep = null;
  }

  get etapaAtual(): string | null {
    return this.currentStep;
  }

  /**
   * `showView` do vanilla (`app.js:349-370`): busca o `view.html`, injeta o `view.js` uma vez por
   * sessão, garante o slot de guia, injeta o reset do shell, instancia a fábrica e renderiza o guia.
   * Escreve DIRETO no `#main` (que o shell React cede à ponte), como o vanilla.
   */
  async showView(id: string, main: HTMLElement): Promise<void> {
    this.destroyCurrent();
    await this.pronto;
    try {
      const r = await fetch(`/steps/${encodeURIComponent(id)}/view.html`);
      if (!r.ok) throw new Error(`etapa ${id}: tela indisponível (${r.status})`);
      main.innerHTML = await r.text();
      if (!this.loaded.has(id)) {
        await carregarScript(`/steps/${encodeURIComponent(id)}/view.js`);
        this.loaded.add(id);
      }
      if (!this.factories[id]) throw new Error(`etapa ${id}: view.js não registrou a tela`);
      this.ensureGuideSlot(main);
      this.injectStepReset(main, id);
      this.currentStep = id;
      const inst = this.factories[id]!(window.Studio!.ctx!);
      this.instances[id] = inst;
      inst.init();
      // 1º render do guia — a tela também o chama nas ações (`ctx.guide()`).
      void window.Studio?.ui?.renderGuide(id);
    } catch (err) {
      this.currentStep = null;
      main.innerHTML = `<div class="empty">Não foi possível abrir esta etapa: ${escapeHtml(
        (err as Error).message,
      )}</div>`;
      this.deps.toast((err as Error).message);
    }
  }

  /**
   * Área global de mood boards (ADR-013): `window.Studio.moodboards.open(mbid)`, que escreve no
   * `#main`. O vanilla chama `destroyCurrent()` antes (applyRoute), então fazemos o mesmo.
   */
  async openMoodboards(sub: string | null): Promise<void> {
    this.destroyCurrent();
    await this.pronto;
    window.Studio?.moodboards?.open(sub);
  }

  /** Área global de créditos & custos (ADR-016): `window.Studio.creditos.open(pid)` no `#main`. */
  async openCreditos(pid: string | null): Promise<void> {
    this.destroyCurrent();
    await this.pronto;
    window.Studio?.creditos?.open(pid);
  }

  /** `ensureGuideSlot` do vanilla: `<section id="guide" class="guide">` após o `header.stephead`. */
  private ensureGuideSlot(main: HTMLElement): void {
    if (main.querySelector("#guide")) return;
    const sec = document.createElement("section");
    sec.id = "guide";
    sec.className = "guide";
    const head = main.querySelector("header.stephead");
    if (head?.parentNode) head.after(sec);
    else main.prepend(sec);
  }

  /**
   * `injectStepReset` do vanilla: o SHELL desenha o botão de reset no `header.stephead` (ADR-010).
   * A diferença é que o `onClick` abre o modal React do shell, não o modal imperativo do vanilla.
   */
  private injectStepReset(main: HTMLElement, stepId: string): void {
    const head = main.querySelector("header.stephead");
    if (!head || head.querySelector(".shell-reset")) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "shell-reset ghost";
    btn.textContent = "Resetar etapa [extensão]";
    btn.title = "Apaga o que esta etapa e as seguintes produziram; mantém nome, produto, vibe e formato";
    btn.onclick = () => this.deps.confirmResetStep(stepId);
    head.appendChild(btn);
  }
}

function escapeHtml(s: string): string {
  return String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!,
  );
}

export type { StudioCtxVanilla, InstanciaVanilla };
export { apiUpload };
