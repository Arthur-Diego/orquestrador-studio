/**
 * Os hooks contra um `fetch` falso — inclusive o caminho inteiro do `onGuide`, do clique da tela
 * até o request de reconciliação 400 ms depois.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { AgendadorDeRefresh, DEBOUNCE_GUIA_MS } from "./guide-sync";
import { chaves } from "./keys";
import {
  criarQueryClient,
  useGuideSync,
  useHiggsfieldStatus,
  useProjectGuide,
  useProjects,
  useSteps,
} from "./queries";
import type { Guide, GuideAll, Step } from "./types";

const ETAPAS: Step[] = [
  { id: "refs", n: 1, title: "Referências", aula: "009", desc: "", status: "ready" },
  { id: "mood", n: 2, title: "Mood board", aula: "009", desc: "", status: "ready" },
  { id: "base", n: 3, title: "Imagem base", aula: "009", desc: "", status: "ready" },
];

function guia(id: string, status: Guide["status"]): Guide {
  return {
    id, n: null, title: id, aula: "009", status, progress: 0, what: "", checklist: [],
    inputs: [], outputs: [], validations: [], missing: [], summary: null, summary_kind: null,
    next_action: "", next_step: null,
  };
}

const GUIA_INICIAL: GuideAll = {
  steps: [guia("refs", "done"), guia("mood", "todo"), guia("base", "todo")],
  done: 1,
  total: 3,
  progress: 0.33,
  current: "mood",
};

/** `fetch` roteado por URL — o backend fake destes testes. */
function instalarBackend(rotas: Record<string, unknown>) {
  const chamadas: string[] = [];
  const f = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) => {
    const url = String(input);
    chamadas.push(url);
    const corpo = rotas[url];
    const achou = corpo !== undefined;
    return {
      ok: achou,
      status: achou ? 200 : 404,
      statusText: achou ? "OK" : "Not Found",
      json: async () => (achou ? corpo : { detail: `sem rota falsa para ${url}` }),
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", f);
  return { f, chamadas };
}

function comProvider() {
  const qc = criarQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  return { qc, wrapper };
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.useRealTimers());

describe("hooks de leitura", () => {
  it("useSteps pega o catálogo e não repete o request (staleTime: Infinity)", async () => {
    const { chamadas } = instalarBackend({ "/api/steps": ETAPAS });
    const { qc, wrapper } = comProvider();

    const a = renderHook(() => useSteps(), { wrapper });
    await waitFor(() => expect(a.result.current.data).toEqual(ETAPAS));

    // um segundo consumidor do mesmo catálogo não gera request novo
    const b = renderHook(() => useSteps(), { wrapper });
    await waitFor(() => expect(b.result.current.data).toEqual(ETAPAS));
    expect(chamadas.filter((u) => u === "/api/steps")).toHaveLength(1);
    qc.clear();
  });

  it("useProjects NÃO engole o erro — quem decide o empty-state é o shell (E3)", async () => {
    instalarBackend({}); // 404 em tudo
    const { qc, wrapper } = comProvider();
    const { result } = renderHook(() => useProjects(), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error?.message).toMatch(/sem rota falsa/);
    qc.clear();
  });

  it("useProjectGuide fica desabilitado sem pid e busca com pid, com encode", async () => {
    const { chamadas } = instalarBackend({ "/api/projects/2026-09%20x/guide": GUIA_INICIAL });
    const { qc, wrapper } = comProvider();

    const semPid = renderHook(() => useProjectGuide(null), { wrapper });
    expect(semPid.result.current.fetchStatus).toBe("idle");
    expect(chamadas).toHaveLength(0);

    const comPid = renderHook(() => useProjectGuide("2026-09 x"), { wrapper });
    await waitFor(() => expect(comPid.result.current.data).toEqual(GUIA_INICIAL));
    expect(chamadas).toEqual(["/api/projects/2026-09%20x/guide"]);
    qc.clear();
  });

  it("useHiggsfieldStatus bate na rota sem query — é o que o `hfChip` do vanilla faz", async () => {
    const { chamadas } = instalarBackend({
      "/api/higgsfield/status": { installed: true, logged_in: true, plan: "pro", credits: 120 },
    });
    const { qc, wrapper } = comProvider();

    const { result } = renderHook(() => useHiggsfieldStatus(), { wrapper });
    await waitFor(() => expect(result.current.data?.plan).toBe("pro"));
    expect(chamadas).toEqual(["/api/higgsfield/status"]);
    qc.clear();
  });
});

describe("useGuideSync — o caminho inteiro do `Studio.onGuide`", () => {
  it("update otimista imediato e UM refetch do agregado 400 ms depois", async () => {
    const { chamadas } = instalarBackend({
      "/api/steps": ETAPAS,
      "/api/projects/p1/guide": GUIA_INICIAL,
    });
    const { qc, wrapper } = comProvider();
    const agendador = new AgendadorDeRefresh();

    const guiaHook = renderHook(() => useProjectGuide("p1"), { wrapper });
    const sync = renderHook(() => useGuideSync("p1", agendador), { wrapper });
    await waitFor(() => expect(guiaHook.result.current.data).toEqual(GUIA_INICIAL));
    await waitFor(() => expect(chamadas).toContain("/api/steps"));

    const antes = chamadas.filter((u) => u === "/api/projects/p1/guide").length;
    expect(antes).toBe(1);

    // a tela terminou uma ação e o guia da etapa voltou `done`
    sync.result.current.onGuide("mood", guia("mood", "done"));

    // o rail já mostra o novo estado, sem esperar servidor nenhum
    await waitFor(() => expect(guiaHook.result.current.data?.done).toBe(2));
    expect(guiaHook.result.current.data?.current).toBe("base");
    expect(chamadas.filter((u) => u === "/api/projects/p1/guide")).toHaveLength(antes);

    // e um único refetch reconcilia depois do debounce
    await waitFor(
      () => expect(chamadas.filter((u) => u === "/api/projects/p1/guide")).toHaveLength(antes + 1),
      { timeout: DEBOUNCE_GUIA_MS + 2000 },
    );

    agendador.cancelar();
    qc.clear();
  });

  it("rajada de 3 chamadas: 3 updates otimistas, 1 refetch", async () => {
    const { chamadas } = instalarBackend({
      "/api/steps": ETAPAS,
      "/api/projects/p1/guide": GUIA_INICIAL,
    });
    const { qc, wrapper } = comProvider();
    const agendador = new AgendadorDeRefresh();

    const guiaHook = renderHook(() => useProjectGuide("p1"), { wrapper });
    const sync = renderHook(() => useGuideSync("p1", agendador), { wrapper });
    await waitFor(() => expect(guiaHook.result.current.data).toEqual(GUIA_INICIAL));
    await waitFor(() => expect(chamadas).toContain("/api/steps"));
    const antes = chamadas.filter((u) => u === "/api/projects/p1/guide").length;

    for (const id of ["refs", "mood", "base"]) sync.result.current.onGuide(id, guia(id, "done"));

    await waitFor(() => expect(guiaHook.result.current.data?.done).toBe(3));
    await waitFor(
      () => expect(chamadas.filter((u) => u === "/api/projects/p1/guide")).toHaveLength(antes + 1),
      { timeout: DEBOUNCE_GUIA_MS + 2000 },
    );
    // e continua sendo UM só depois que a poeira baixa
    await new Promise((r) => setTimeout(r, DEBOUNCE_GUIA_MS + 100));
    expect(chamadas.filter((u) => u === "/api/projects/p1/guide")).toHaveLength(antes + 1);

    agendador.cancelar();
    qc.clear();
  });

  it("o guia da etapa também vai para o cache dela", async () => {
    instalarBackend({ "/api/steps": ETAPAS, "/api/projects/p1/guide": GUIA_INICIAL });
    const { qc, wrapper } = comProvider();
    const agendador = new AgendadorDeRefresh();

    const sync = renderHook(() => useGuideSync("p1", agendador), { wrapper });
    const g = guia("mood", "in_progress");
    sync.result.current.onGuide("mood", g);

    expect(qc.getQueryData(chaves.guiaDaEtapa("p1", "mood"))).toEqual(g);
    agendador.cancelar();
    qc.clear();
  });
});
