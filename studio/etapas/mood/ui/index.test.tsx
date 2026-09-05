// Substituto Vitest de `tests/test_mood_view.py` — Wave 10 · E4 (card [REACT-05]).
//
// O pytest afirmava substrings sobre o fonte (`mood/view.{html,js}`). O substituto renderiza o
// componente e assevera DOM + comportamento (recon §7.2), espelhando os casos C-MOOD-* do cenário
// de QA (o oráculo). Preserva os textos de aula (ADR-004) e o contrato DOM (ids/classes).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import MoodScreen from "./index";
import { StudioProvider, type StudioCtx } from "../../../../frontend/src/shell/plugin";

type ApiFn = (path: string, opts?: RequestInit) => Promise<unknown>;

const BOARD_CURADO = { id: "b-curado", name: "QA Mood", count: 2, vibe: "gelo neon", thumbs: ["a.png", "b.png"] };
const BOARD_VAZIO = { id: "b-vazio", name: "Sem Curadoria", count: 0 };
const MOOD_ATUAL = {
  vibe: "gelo neon",
  palette: ["#112233", "#445566"],
  selected: [{ file: "s1.png" }, { file: "s2.png" }],
};

function fakeCtx(over: Partial<StudioCtx> = {}, api?: ApiFn): StudioCtx {
  return {
    api: (api ?? (async () => ({}))) as StudioCtx["api"],
    apiUpload: (async () => ({})) as StudioCtx["apiUpload"],
    toast: vi.fn(),
    pid: () => "pid-1",
    project: () => null,
    files: (p: string) => `/files/pid-1/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
    ...over,
  };
}

/** api de `ctx` roteada por path (boards + mood atual). */
function apiRoteada(boards: unknown[], mood: unknown, onPost?: (p: string) => unknown): ApiFn {
  return async (path: string, opts?: RequestInit) => {
    if (opts?.method === "POST") return onPost ? onPost(path) : { selected: 2, vibe: "gelo neon" };
    if (path === "/api/moodboards") return boards;
    if (path.endsWith("/mood")) return mood;
    return {};
  };
}

function renderMood(ctx: StudioCtx) {
  return render(
    <StudioProvider value={ctx}>
      <MoodScreen />
    </StudioProvider>,
  );
}

beforeEach(() => {
  // StepGuide (E2) busca o guia pelo `fetch` global; devolve um guia mínimo para não poluir.
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        id: "mood", n: 2, title: "Mood board", aula: "009", status: "todo", progress: 0,
        what: "", checklist: [], inputs: [], outputs: [], validations: [], missing: [],
        summary: null, summary_kind: null, next_action: null, next_step: null,
      }),
    })) as unknown as typeof fetch,
  );
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("MoodScreen (etapa 2 · aula 009)", () => {
  it("C-MOOD-18: dois painéis, sem input de arquivo nem controles de criação (ADR-014)", async () => {
    renderMood(fakeCtx({}, apiRoteada([BOARD_CURADO], MOOD_ATUAL)));
    await screen.findByText(/QA Mood · 2 img/);
    expect(document.querySelectorAll(".panel .panel-head h3")).toHaveLength(2);
    expect(document.querySelectorAll("input[type=file]")).toHaveLength(0);
    expect(document.querySelector("#btnMoodGen, #btnMoodPrompt, #btnMbOpenFolder")).toBeNull();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("Mood board");
  });

  it("C-MOOD-01: um card por board, com legenda 'nome · N img · vibe' e data-mb", async () => {
    renderMood(fakeCtx({}, apiRoteada([BOARD_CURADO, BOARD_VAZIO], MOOD_ATUAL)));
    const card = await screen.findByTitle("QA Mood");
    expect(card).toHaveAttribute("data-mb", "b-curado");
    expect(card.querySelector(".term")).toHaveTextContent("QA Mood · 2 img · gelo neon");
    expect(document.querySelectorAll("#mbGrid .card")).toHaveLength(2);
  });

  it("C-MOOD-02: board sem curadoria nasce .is-empty, sem tabindex, não selecionável", async () => {
    renderMood(fakeCtx({}, apiRoteada([BOARD_VAZIO], { selected: [] })));
    const card = await screen.findByTitle("Sem Curadoria");
    expect(card).toHaveClass("is-empty");
    expect(card).not.toHaveAttribute("tabindex");
    await userEvent.click(card);
    expect(document.querySelector("#mbCount")).toHaveTextContent("nenhum selecionado");
    expect(screen.getByRole("button", { name: "Aplicar a esta campanha" })).toBeDisabled();
  });

  it("C-MOOD-03/04: clicar escolhe (.sel + chip + botão habilitado); reclicar desfaz", async () => {
    renderMood(fakeCtx({}, apiRoteada([BOARD_CURADO], MOOD_ATUAL)));
    const card = await screen.findByTitle("QA Mood");
    await userEvent.click(card);
    expect(card).toHaveClass("sel");
    expect(document.querySelector("#mbCount")).toHaveTextContent("QA Mood selecionado");
    expect(screen.getByRole("button", { name: "Aplicar a esta campanha" })).toBeEnabled();
    await userEvent.click(card);
    expect(card).not.toHaveClass("sel");
    expect(document.querySelector("#mbCount")).toHaveTextContent("nenhum selecionado");
    expect(screen.getByRole("button", { name: "Aplicar a esta campanha" })).toBeDisabled();
  });

  it("C-MOOD-05: Enter no card focado escolhe (teclado)", async () => {
    renderMood(fakeCtx({}, apiRoteada([BOARD_CURADO], MOOD_ATUAL)));
    const card = await screen.findByTitle("QA Mood");
    card.focus();
    await userEvent.keyboard("{Enter}");
    expect(document.querySelector("#mbCount")).toHaveTextContent("QA Mood selecionado");
  });

  it("C-MOOD-06/08: aplicar faz POST /mood/pull, dá toast e limpa a escolha", async () => {
    const toast = vi.fn();
    let postPath = "";
    const api = apiRoteada([BOARD_CURADO], MOOD_ATUAL, (p) => {
      postPath = p;
      return { selected: 2, vibe: "gelo neon" };
    });
    renderMood(fakeCtx({ toast }, api));
    const card = await screen.findByTitle("QA Mood");
    await userEvent.click(card);
    await userEvent.click(screen.getByRole("button", { name: "Aplicar a esta campanha" }));
    expect(postPath).toBe("/api/projects/pid-1/mood/pull/b-curado");
    expect(toast).toHaveBeenCalledWith("2 imagens aplicadas · vibe: gelo neon");
    expect(document.querySelector("#mbCount")).toHaveTextContent("nenhum selecionado");
  });

  it("C-MOOD-12/13: painel 02 mostra chip de vibe, swatches por cor e o rótulo da paleta", async () => {
    renderMood(fakeCtx({}, apiRoteada([BOARD_CURADO], MOOD_ATUAL)));
    await screen.findByText(/QA Mood · 2 img/);
    expect(document.querySelector("#moodVibe")).toHaveTextContent("vibe: gelo neon");
    const swatches = document.querySelectorAll("#palette span[title]");
    expect([...swatches].map((s) => s.getAttribute("title"))).toEqual(["#112233", "#445566"]);
    expect(document.querySelector("#palette .lbl")).toHaveTextContent("palette.json");
  });

  it("C-MOOD-14: campanha sem mood mostra o vazio e 'vibe: —'", async () => {
    renderMood(fakeCtx({}, apiRoteada([BOARD_CURADO], { vibe: "", palette: [], selected: [] })));
    await screen.findByText(/QA Mood · 2 img/);
    expect(document.querySelector("#moodVibe")).toHaveTextContent("vibe: —");
    expect(document.querySelector("#moodGallery .empty")).toHaveTextContent("Nenhum mood aplicado ainda");
  });

  it("C-MOOD-17: biblioteca vazia mostra empty-state com botão que navega à biblioteca", async () => {
    renderMood(fakeCtx({}, apiRoteada([], MOOD_ATUAL)));
    const vazio = await screen.findByText(/Nenhum mood board ainda/);
    const btn = within(vazio).getByRole("button", { name: /Ir para a biblioteca/ });
    await userEvent.click(btn);
    expect(location.hash).toBe("#/moodboards");
  });

  it("C-MOOD-16: 'Criar / gerenciar mood boards' abre a biblioteca global", async () => {
    renderMood(fakeCtx({}, apiRoteada([BOARD_CURADO], MOOD_ATUAL)));
    await screen.findByText(/QA Mood · 2 img/);
    await userEvent.click(screen.getByRole("button", { name: "Criar / gerenciar mood boards" }));
    expect(location.hash).toBe("#/moodboards");
  });
});
