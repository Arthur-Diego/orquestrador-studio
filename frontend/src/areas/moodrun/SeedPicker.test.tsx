// Teste do componente `SeedPicker` `[extensão]` (ADH-OS-20260905-03) — escolha da foto-semente.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SeedPicker } from "./SeedPicker";

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
  const f = vi.fn(async (...args: [RequestInfo | URL, RequestInit?]) => {
    const url = String(args[0]);
    const r = rotas.find((x) => url.includes(x.match));
    return {
      ok: r?.ok ?? true,
      status: r?.ok === false ? 400 : 200,
      statusText: "OK",
      json: async () => r?.corpo ?? {},
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", f);
  return f;
}

const FACETS = {
  vibes: [{ slug: "neon-city", nome: "Neon City", origem: "usuario", total: 3 }],
  origens: [{ origem: "usuario", total: 3 }],
  total: 3,
  escolhidas: 1,
};
const VIBES = {
  items: [
    { id: "custom-01-neon-city-1.jpg", arquivo: "custom-01-neon-city-1.jpg", url: "/mbfiles/_vibes/a.jpg",
      vibe: "neon-city", vibe_nome: "Neon City", origem: "usuario", escolhida: false },
  ],
  page: 1, pages: 1, total: 3, indice: { ok: true, erro: null },
};
const CHOSEN = {
  items: [{ id: "aaaaaaaaaaaa", url: "/mbfiles/_escolhidas/aaaaaaaaaaaa.jpg",
            caminho: "/abs/_escolhidas/aaaaaaaaaaaa.jpg", vibe_nome: "Neon City" }],
  total: 1,
};

function base(scoutReady = true): Rota[] {
  return [
    { match: "/api/vibes/facets", corpo: FACETS },
    { match: "/api/vibes/scout-run/options", corpo: { available_claude: scoutReady, defaults: { n: 3 }, limites: { n_min: 1 } } },
    { match: "/api/vibes?", corpo: VIBES },
    { match: "/api/escolhidas", corpo: CHOSEN },
  ];
}

describe("SeedPicker", () => {
  it("mostra a peneira, a grade de vibes e a coleta; 'usar semente' devolve o caminho", async () => {
    stubFetch(base());
    const onPick = vi.fn();
    const onClose = vi.fn();
    render(<SeedPicker onPick={onPick} onClose={onClose} />);

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    // peneira carregada (1 escolhida) com o botão de usar como semente
    await waitFor(() => expect(screen.getByText("usar semente")).toBeInTheDocument());
    // grade de vibes carregada (1 item)
    await waitFor(() => expect(document.querySelectorAll(".sp-grid").length).toBeGreaterThanOrEqual(1));

    await userEvent.click(screen.getByText("usar semente"));
    expect(onPick).toHaveBeenCalledWith("/abs/_escolhidas/aaaaaaaaaaaa.jpg");
    expect(onClose).toHaveBeenCalled();
  });

  it("coleta headless desabilitada sem claude no PATH", async () => {
    stubFetch(base(false));
    render(<SeedPicker onPick={() => {}} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText("Coletar")).toBeInTheDocument());
    expect(screen.getByText("Coletar")).toBeDisabled();
    expect(screen.getByText("sem claude")).toBeInTheDocument();
  });

  it("salva na peneira as fotos marcadas", async () => {
    const f = stubFetch([
      ...base(),
      { match: "/api/vibes/select", corpo: { copiadas: ["custom-01-neon-city-1.jpg"], duplicadas: [], total_escolhidas: 2 } },
    ]);
    render(<SeedPicker onPick={() => {}} onClose={() => {}} />);
    await waitFor(() => expect(document.querySelector(".sp-card")).toBeInTheDocument());

    // marca a foto da grade (o card sem botão "usar semente" é o da grade de vibes)
    const grade = [...document.querySelectorAll<HTMLDivElement>(".sp-grid")].at(-1)!;
    await userEvent.click(grade.querySelector<HTMLDivElement>(".sp-card")!);
    const salvar = screen.getByText(/Salvar na peneira/);
    expect(salvar).not.toBeDisabled();
    await userEvent.click(salvar);

    await waitFor(() =>
      expect(f.mock.calls.some(([u, o]) => String(u).includes("/api/vibes/select") && (o as RequestInit)?.method === "POST")).toBe(true),
    );
  });
});
