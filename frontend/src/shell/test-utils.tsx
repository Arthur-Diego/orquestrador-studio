// Utilitários dos testes do shell — Wave 10 · E3. Não entra no bundle (só os `*.test.tsx` importam).
import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";

import { criarQueryClient } from "../api";
import type { GuideAll, Project, Step } from "../api";
import { ShellProvider, type ShellApi } from "./context";

export const STEPS: Step[] = [
  { id: "refs", n: 1, title: "Referências", aula: "001", desc: "Colete referências visuais", status: "ready" },
  { id: "mood", n: 2, title: "Mood board", aula: "009", desc: "Defina a vibe", status: "ready" },
  { id: "base", n: 3, title: "Imagem base", aula: "010+011", desc: "Gere a base", status: "ready" },
  { id: "prospect", n: 10, title: "Prospecção", aula: "015", desc: "Prospecte clientes", status: "soon" },
];

export const PROJECTS: Project[] = [
  { id: "campanha-a", name: "Campanha A", product: "energy drink", vibe: "neon", created: "2026-09-01", aspect_ratio: "9:16" },
  { id: "campanha-b", name: "Campanha B", product: "", vibe: "", created: "2026-09-02" },
];

/** Agregado do guia coerente com STEPS (refs done, mood in_progress, base todo). */
export function guideFixture(pid: string): GuideAll {
  const g = (id: string, n: number, title: string, status: GuideAll["steps"][number]["status"], progress = 0) => ({
    id, n, title, aula: "0", status, progress,
    what: "", checklist: [], inputs: [], outputs: [], validations: [],
    missing: status === "done" ? [] : ["algo"], summary: null, summary_kind: null,
    next_action: status === "done" ? "" : `próximo passo de ${title}`, next_step: null,
  });
  void pid;
  const steps = [
    g("refs", 1, "Referências", "done", 1),
    g("mood", 2, "Mood board", "in_progress", 0.5),
    g("base", 3, "Imagem base", "todo", 0),
  ];
  return { steps, done: 1, total: 3, progress: 1 / 3, current: "mood" };
}

/** ShellApi de teste com ações espionáveis e estado default sobrescrevível. */
export function mockShellApi(over: Partial<ShellApi> = {}): ShellApi {
  return {
    steps: STEPS,
    projects: PROJECTS,
    project: PROJECTS[0]!,
    guideAll: guideFixture("campanha-a"),
    area: "campaign",
    pid: "campanha-a",
    view: "overview",
    tema: "auto",
    booted: true,
    navigate: vi.fn(),
    go: vi.fn(),
    selectProject: vi.fn(),
    irParaMoodboards: vi.fn(),
    irParaCreditos: vi.fn(),
    irParaPersonagens: vi.fn(),
    continuar: vi.fn(),
    openWizard: vi.fn(),
    openEdit: vi.fn(),
    confirmResetStep: vi.fn(),
    confirmResetCampaign: vi.fn(),
    cycleTheme: vi.fn(),
    ...over,
  };
}

export function renderNoShell(ui: ReactElement, api: ShellApi = mockShellApi()) {
  return { api, ...render(<ShellProvider value={api}>{ui}</ShellProvider>) };
}

/** Wrapper com QueryClient para testar componentes que usam hooks/mutações da E1 (modais). */
export function renderComQuery(ui: ReactElement) {
  const qc = criarQueryClient();
  return { qc, ...render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>) };
}

/** `fetch` falso que roteia por (método, path) — para os modais que batem no backend. */
export function fetchRoteado(rotas: Record<string, unknown>) {
  return vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input, init) => {
    const url = String(input);
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    const metodo = (init?.method || "GET").toUpperCase();
    const chave = `${metodo} ${path}`;
    const corpo = chave in rotas ? rotas[chave] : (path in rotas ? rotas[path] : {});
    return {
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => corpo,
    } as unknown as Response;
  });
}
