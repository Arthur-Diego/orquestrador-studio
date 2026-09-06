// Teste do componente `MoodRun` `[extensão]` (ADH-OS-20260905-03) — corrida da cadeia mood.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MoodRun, type MoodRunOpts } from "./MoodRun";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
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

const OPTS: MoodRunOpts = { mbid: "b1", boardName: "Neon Snow" };

function options(available_claude = true) {
  return {
    available_claude,
    objetivos: ["ambiente", "campanha", "produto", "personagem"],
    agregador: "todos",
    fundos: ["escuro", "claro"],
    defaults: { board: 8, n: 3, fundo: "escuro" },
    limites: { board_min: 4, n_min: 1 },
    escolhidas: { total: 2, pasta: "/x/_escolhidas" },
  };
}

describe("MoodRun", () => {
  it("carrega options do manifesto, mostra objetivos e o botão de rodar", async () => {
    stubFetch([
      { match: "/mood-run/options", corpo: options() },
      { match: "/mood-run/result", corpo: {}, ok: false },
    ]);
    render(<MoodRun opts={OPTS} onClose={() => {}} />);

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("ambiente")).toBeInTheDocument());
    expect(screen.getByText("campanha")).toBeInTheDocument();
    expect(screen.getByText("claude: no ar")).toBeInTheDocument();
    expect(screen.getByText("Rodar corrida (grátis)")).toBeEnabled();
  });

  it("sem claude: botão de rodar desabilitado, tela não quebra", async () => {
    stubFetch([
      { match: "/mood-run/options", corpo: options(false) },
      { match: "/mood-run/result", corpo: {}, ok: false },
    ]);
    render(<MoodRun opts={OPTS} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText("claude: offline")).toBeInTheDocument());
    expect(screen.getByText("Rodar corrida (grátis)")).toBeDisabled();
  });

  it("selecionar objetivo dispara a estimativa e mostra os downloads", async () => {
    stubFetch([
      { match: "/mood-run/options", corpo: options() },
      { match: "/mood-run/estimate", corpo: { downloads: 42 } },
      { match: "/mood-run/result", corpo: {}, ok: false },
    ]);
    render(<MoodRun opts={OPTS} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText("ambiente")).toBeInTheDocument());

    await userEvent.click(screen.getByText("ambiente"));
    await waitFor(() => expect(screen.getByText(/42 downloads/)).toBeInTheDocument());
  });

  it("mostra as pranchas quando já há resultado", async () => {
    stubFetch([
      { match: "/mood-run/options", corpo: options() },
      {
        match: "/mood-run/result",
        corpo: {
          boards: [
            { objetivo: "ambiente", prancha_url: "/mbfiles/b1/mood_run/board-x-ambiente/_moodboard.jpg",
              leitura_url: "/mbfiles/b1/mood_run/board-x-ambiente/leitura.md" },
          ],
        },
      },
    ]);
    render(<MoodRun opts={OPTS} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText("Pranchas da corrida vigente")).toBeInTheDocument());
    expect(document.querySelector<HTMLImageElement>(".mr-board img")?.src).toContain("_moodboard.jpg");
    expect(screen.getByText("leitura")).toBeInTheDocument();
  });
});
