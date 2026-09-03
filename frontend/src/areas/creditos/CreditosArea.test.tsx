// Wave 10 · E6 (card [REACT-07]) — substituto Vitest da área global de créditos & custos (ADR-016),
// que migrou de `studio/web/creditos.js` para React. Afirma o contrato de DOM que os cenários
// `creditos.py` exercem: card de saldo, painel ADMIN por ação, tabela de custo e histórico, além do
// seletor de escopo Global × Esta campanha (só com campanha aberta) e do deep link sem campanha.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CreditosArea } from "./CreditosArea";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
  location.hash = "";
});

const DASH = {
  balance: { installed: true, logged_in: true, plan: "pro", credits: 120 },
  models: [
    {
      id: "nano",
      label: "Nano",
      kind: "image",
      variant_key: "resolution",
      variant_options: ["1k", "2k"],
      default_variant: "2k",
      rows: [{ variant: "1k", credits: 2 }, { variant: "2k", credits: 7 }],
      note: "",
    },
    { id: "gpt", label: "GPT", kind: "image", rows: [{ variant: "1k", credits: 8 }], note: "" },
  ],
  actions: [
    { key: "mood.grid", kind: "image", label: "Grid de mood", screen: "Mood", model: "nano", variant: "2k", credits: 7, source: "global" },
  ],
  kind_order: ["image"],
  kind_label: { image: "Imagem" },
  summary: { total_credits: 14, count: 2, by_step: [{ step: "mood", credits: 7, count: 1 }], by_project: [{ name: "Camp", credits: 7, count: 1 }] },
  history: [{ at: "2026-09-03T10:00:00Z", project_name: "Camp", step: "mood", model: "nano", variant: "2k", credits: 7 }],
};

function stubFetch(corpo: unknown) {
  const f = vi.fn(async () => ({ ok: true, status: 200, statusText: "OK", json: async () => corpo }) as unknown as Response);
  vi.stubGlobal("fetch", f);
  return f;
}

function renderArea(pid: string | null) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CreditosArea pid={pid} />
    </QueryClientProvider>,
  );
}

describe("CreditosArea", () => {
  it("mostra saldo, plano, tabela admin por ação, custo e histórico; instala o global open()", async () => {
    stubFetch(DASH);
    renderArea("cheio");

    await waitFor(() => expect(document.querySelector(".cr-table.admin tbody tr")).toBeInTheDocument());
    // saldo + plano
    expect(document.querySelector(".cr-saldo b")?.textContent).toBe("120");
    expect(document.querySelector(".cr-balance .chip")?.textContent).toBe("pro");
    // admin: uma linha por ação, com custo e select do próprio tipo
    const linha = document.querySelector<HTMLElement>("tr[data-action='mood.grid']");
    expect(linha).toBeInTheDocument();
    expect(linha?.querySelector(".cr-cost")?.textContent).toBe("7 cr");
    const modelo = linha?.querySelector<HTMLSelectElement>(".cr-model");
    expect(modelo?.value).toBe("nano");
    expect([...(modelo?.options ?? [])].map((o) => o.value)).toEqual(["nano", "gpt"]);
    expect(linha?.querySelector(".cr-variant")).toBeInTheDocument();
    // tabela de custo: agrupada por tipo, uma linha por variação (2 do nano + 1 do gpt)
    expect(document.querySelector(".cr-kind")?.textContent).toBe("Imagem");
    const costCard = [...document.querySelectorAll(".cr-card")].find((c) => c.querySelector(".cr-kind"));
    expect(costCard?.querySelectorAll(".cr-table tbody tr")).toHaveLength(3);
    // histórico
    const chips = [...document.querySelectorAll(".cr-card-head .chip")].map((c) => c.textContent);
    expect(chips).toContain("total 14 cr");
    expect(chips).toContain("2 gerações");
    // escape hatch imperativo para o QA.
    expect(typeof window.Studio?.creditos?.open).toBe("function");
  });

  it("com campanha aberta aparece o seletor de escopo Global × Esta campanha", async () => {
    stubFetch(DASH);
    renderArea("cheio");
    await waitFor(() => expect(document.querySelector(".cr-scope")).toBeInTheDocument());
    const botoes = [...document.querySelectorAll(".cr-scope .seg-btn")].map((b) => b.textContent);
    expect(botoes).toEqual(["Global", "Esta campanha"]);
    expect(document.querySelector(".seg-btn[data-scope='global']")?.className).toContain("on");
  });

  it("sem campanha (deep link) não há toggle de escopo e a nota pede abrir uma campanha", async () => {
    stubFetch(DASH);
    renderArea(null);
    await waitFor(() => expect(document.querySelector(".cr-table.admin tbody tr")).toBeInTheDocument());
    expect(document.querySelector(".cr-scope")).toBeNull();
    const notas = [...document.querySelectorAll(".cr-note")].map((n) => n.textContent).join(" ");
    expect(notas.toLowerCase()).toContain("abra uma campanha");
  });
});
