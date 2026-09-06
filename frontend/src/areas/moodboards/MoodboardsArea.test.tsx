// Wave 10 · E6 (card [REACT-07]) — substituto Vitest da área global de mood boards (ADR-013), que
// migrou de `studio/web/moodboards.js` para React. Afirma o contrato de DOM que os cenários
// `moodboards.py` exercem (biblioteca, editor de 3 painéis, curadoria) e que o pytest apagado
// (`test_api.py::test_shell_area_global_de_moodboards`, `test_progress_modal.py`) verificava sobre o
// fonte vanilla.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { MoodboardsArea } from "./MoodboardsArea";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  location.hash = "";
});

interface Rota {
  match: string;
  corpo: unknown;
  ok?: boolean;
}
function stubFetch(rotas: Rota[]) {
  const f = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const r = rotas.find((x) => url.includes(x.match));
    return {
      ok: r?.ok ?? true,
      status: r?.ok === false ? 404 : 200,
      statusText: "OK",
      json: async () => r?.corpo ?? {},
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", f);
  return f;
}

function renderArea(sub: string | null) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MoodboardsArea sub={sub} />
    </QueryClientProvider>,
  );
}

const BOARD = {
  id: "b1",
  name: "Neon Snow",
  vibe: "",
  note: "",
  folder: "/tmp/mb/b1",
  candidates: [
    { id: "c1", thumb: "c1.jpg", file: "c1.jpg", name: "a", source: "upload", role: "vibe", selected: false },
    { id: "c2", thumb: "c2.jpg", file: "c2.jpg", name: "b", source: "upload", role: "vibe", selected: true },
  ],
  palette: { colors: ["#fff", "#000"] },
  prompt: "",
  available_claude: true,
};

describe("MoodboardsArea — biblioteca", () => {
  it("lista um card por board, com contagem e mosaico, e instala o global open()", async () => {
    stubFetch([
      {
        match: "/api/moodboards",
        corpo: [
          { id: "b1", name: "Neon Snow", vibe: "gelo", count: 3, thumbs: ["c1.jpg"] },
          { id: "b2", name: "Deserto", vibe: "", count: 0, thumbs: [] },
        ],
      },
    ]);
    renderArea(null);

    await waitFor(() => expect(document.querySelectorAll(".mb-grid .mb-card")).toHaveLength(2));
    const cards = [...document.querySelectorAll<HTMLElement>(".mb-grid .mb-card")];
    expect(cards.map((c) => c.dataset.mb)).toEqual(["b1", "b2"]);
    expect(cards[0]?.textContent).toContain("3 imagem(ns)");
    expect(cards[0]?.textContent).toContain("Neon Snow");
    // escape hatch imperativo para o QA.
    expect(typeof window.Studio?.moodboards?.open).toBe("function");
  });

  it("'Novo mood board' abre modal com nome (required) e nota", async () => {
    stubFetch([{ match: "/api/moodboards", corpo: [] }]);
    renderArea(null);
    await waitFor(() => expect(document.querySelector("#btnNewBoard2")).toBeInTheDocument());

    await userEvent.click(screen.getByText("Criar o primeiro mood board"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    const nome = document.querySelector<HTMLInputElement>("#mbName");
    expect(nome).toBeInTheDocument();
    expect(nome?.hasAttribute("required")).toBe(true);
    expect(document.querySelector("#mbNote")).toBeInTheDocument();
    expect(document.querySelector('#mbForm button[type="submit"]')).toBeInTheDocument();
  });
});

describe("MoodboardsArea — editor", () => {
  it("mostra nome, pasta e os quatro painéis, com a curadoria dividida por seleção", async () => {
    stubFetch([{ match: "/api/moodboards/b1", corpo: BOARD }]);
    renderArea("b1");

    await waitFor(() => expect(document.querySelector("#mbGallery")).toBeInTheDocument());
    expect(document.querySelector("#mbTitle")?.textContent).toBe("Neon Snow");
    expect(document.querySelector("#mbFolder")?.textContent).toBe("/tmp/mb/b1");
    // painel 04 `[extensão]`: corrida das skills de mood.
    expect(document.querySelectorAll("section.panel")).toHaveLength(4);
    expect(document.querySelector("#btnMbMoodRun")).toBeInTheDocument();
    // não-selecionada no painel 01, selecionada no 02.
    expect(document.querySelectorAll("#mbImported .msc-card")).toHaveLength(1);
    expect(document.querySelectorAll("#mbGallery .msc-card")).toHaveLength(1);
    expect(document.querySelector("#mbCounts")?.textContent).toBe("2 candidatas · 1 escolhidas (máx. 8)");
    expect(document.querySelector("#mbImpCount")?.textContent).toBe("1 aguardando");
    // paleta com swatches.
    expect(document.querySelectorAll("#mbPalette span[title]")).toHaveLength(2);
    // painel 03: chip do bot e os três modos.
    expect(document.querySelector("#mbClaude")?.textContent).toBe("bot: claude ok");
    expect(document.querySelectorAll("#mbMode option")).toHaveLength(3);
  });

  it("'usar no board' promove a candidata do painel 01 ao 02 e atualiza a contagem", async () => {
    stubFetch([{ match: "/api/moodboards/b1", corpo: BOARD }]);
    renderArea("b1");
    await waitFor(() => expect(document.querySelector("#mbImported .use-btn")).toBeInTheDocument());

    await userEvent.click(document.querySelector("#mbImported .use-btn") as HTMLElement);
    await waitFor(() => expect(document.querySelectorAll("#mbGallery .msc-card")).toHaveLength(2));
    expect(document.querySelectorAll("#mbImported .msc-card")).toHaveLength(0);
    expect(document.querySelector("#mbCounts")?.textContent).toBe("2 candidatas · 2 escolhidas (máx. 8)");
  });

  it("board inexistente mostra mensagem amigável com volta à biblioteca", async () => {
    stubFetch([{ match: "/api/moodboards/none", corpo: { detail: "não encontrado" }, ok: false }]);
    renderArea("none");
    await waitFor(() => expect(document.querySelector("#mbBack")).toBeInTheDocument());
    expect(document.querySelector("#main, .empty")?.textContent ?? document.body.textContent ?? "").toContain(
      "não encontrado",
    );
  });
});
