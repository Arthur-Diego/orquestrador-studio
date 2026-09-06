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

// Wave 11 (card #92) — o histórico ficou legível para o gasto que não tem campanha e a tabela de
// custo aguenta modelo sem custo medido.
describe("CreditosArea · histórico da biblioteca e custo não medido", () => {
  /** Multishot da BIBLIOTECA global (ADR-013): grava `pid: null` com o nome do board. */
  const BIBLIOTECA = {
    ...DASH,
    summary: {
      total_credits: 7,
      count: 1,
      by_step: [{ step: "moodboard", credits: 7, count: 1 }],
      by_project: [{ pid: null, name: "Board X", credits: 7, count: 1 }],
    },
    history: [
      { at: "2026-09-06T10:00:00Z", pid: null, project_name: "Board X", step: "moodboard", model: "nano", variant: "2k", credits: 7 },
    ],
  };

  const textos = (sel: string) => [...document.querySelectorAll(sel)].map((e) => e.textContent);
  /** Célula da i-ésima tabela da grade do histórico (0 = "Por etapa", 1 = "Por projeto"). */
  const celulasDaGrade = (i: number): (string | null)[] => {
    const bloco = [...document.querySelectorAll(".cr-hist-grid > div")][i];
    if (!bloco) throw new Error(`a tabela ${i} do histórico não renderizou`);
    return [...bloco.querySelectorAll("tbody tr td")].map((e) => e.textContent);
  };

  it("rotula 'Biblioteca · <board>' o gasto sem campanha nas duas tabelas e dá nome à etapa", async () => {
    stubFetch(BIBLIOTECA);
    renderArea(null);
    await waitFor(() => expect(document.querySelector(".cr-hist-scroll tbody tr")).toBeInTheDocument());

    // "Gerações recentes": a coluna Projeto não mostra mais só o nome do board (que parecia campanha)
    const recente = textos(".cr-hist-scroll tbody tr td");
    expect(recente).toContain("Biblioteca · Board X");
    // "Por projeto" (2ª tabela da grade do histórico) diz o mesmo
    expect(celulasDaGrade(1)).toContain("Biblioteca · Board X");
    // "Por etapa" deixa de exibir a chave crua `moodboard`
    expect(celulasDaGrade(0)).toContain("Biblioteca › Mood boards");
    expect(celulasDaGrade(0)).not.toContain("moodboard");
  });

  it("sem nome de board o rótulo é só 'Biblioteca'", async () => {
    stubFetch({
      ...BIBLIOTECA,
      history: [{ at: "2026-09-06T10:00:00Z", pid: null, step: "moodboard", model: "nano", credits: 7 }],
    });
    renderArea(null);
    await waitFor(() => expect(document.querySelector(".cr-hist-scroll tbody tr")).toBeInTheDocument());
    expect(textos(".cr-hist-scroll tbody tr td")).toContain("Biblioteca");
  });

  it("modelo sem custo medido (reframe) mostra '—' na tabela de custo, nunca 'null cr'", async () => {
    stubFetch({
      ...DASH,
      models: [
        ...DASH.models,
        { id: "reframe", label: "Reframe (CLI)", kind: "reframe", rows: [{ variant: null, credits: null }], note: "custo ao vivo" },
      ],
      kind_order: ["image", "reframe"],
      kind_label: { image: "Imagem", reframe: "Reenquadramento" },
    });
    renderArea(null);
    await waitFor(() => expect(document.querySelector(".cr-table.admin tbody tr")).toBeInTheDocument());

    const secao = [...document.querySelectorAll(".cr-kind")].find((h) => h.textContent === "Reenquadramento");
    expect(secao).toBeInTheDocument();
    const linha = secao?.nextElementSibling?.querySelector("tbody tr");
    expect([...(linha?.querySelectorAll("td") ?? [])].map((t) => t.textContent)).toContain("—");
    expect(document.body.textContent).not.toContain("null cr");
  });
});

// ---------- gasto registrado e reconciliação `[extensão]` (wave 11 · F10, card #91) ----------
const GASTO = {
  ...DASH,
  summary: { ...DASH.summary, today_credits: 18, today_count: 4, total_credits: 46, count: 12 },
  summary_global: { total_credits: 312, count: 74, by_step: [], by_project: [] },
};

const numeros = () =>
  [...document.querySelectorAll(".cr-gasto-item")].map((el) => [
    el.querySelector("span")?.textContent,
    el.querySelector("b")?.textContent,
  ]);

describe("BalanceCard · gasto registrado e a reconciliação explicada (critério 19)", () => {
  it("com campanha, mostra hoje, nesta campanha e total", async () => {
    stubFetch(GASTO);
    renderArea("cheio");
    await waitFor(() => expect(document.querySelector(".cr-gasto")).toBeInTheDocument());

    expect(document.querySelector(".cr-saldo b")?.textContent).toBe("120");
    expect(numeros()).toEqual([
      ["Hoje", "18"],
      ["Nesta campanha", "46"],
      ["Total", "312"],
    ]);
  });

  it("sem campanha, a linha da campanha não aparece e o total sai do escopo global", async () => {
    stubFetch({ ...GASTO, summary_global: undefined });
    renderArea(null);
    await waitFor(() => expect(document.querySelector(".cr-gasto")).toBeInTheDocument());
    expect(numeros()).toEqual([["Hoje", "18"], ["Total", "46"]]);
  });

  it("CLI sem login: o saldo some, mas os números do livro-caixa ficam", async () => {
    stubFetch({ ...GASTO, balance: { installed: true, logged_in: false } });
    renderArea("cheio");
    await waitFor(() => expect(document.querySelector(".cr-gasto")).toBeInTheDocument());

    expect(document.querySelector(".cr-saldo b")?.textContent).toBe("—");
    expect(document.querySelector(".cr-balance .chip")?.textContent).toBe("sem login");
    expect(numeros()).toEqual([["Hoje", "18"], ["Nesta campanha", "46"], ["Total", "312"]]);
  });

  it("CLI não instalado: idem, a mensagem de sempre continua", async () => {
    stubFetch({ ...GASTO, balance: { installed: false } });
    renderArea("cheio");
    await waitFor(() => expect(document.querySelector(".cr-gasto")).toBeInTheDocument());
    expect(document.querySelector(".cr-balance .chip")?.textContent).toBe("CLI não instalado");
    expect(numeros()).toEqual([["Hoje", "18"], ["Nesta campanha", "46"], ["Total", "312"]]);
  });

  it("livro-caixa vazio mostra zero, nunca traço nem vazio", async () => {
    stubFetch({
      ...DASH,
      summary: { total_credits: 0, count: 0, today_credits: 0, today_count: 0, by_step: [], by_project: [] },
      summary_global: { total_credits: 0, count: 0, by_step: [], by_project: [] },
    });
    renderArea("cheio");
    await waitFor(() => expect(document.querySelector(".cr-gasto")).toBeInTheDocument());
    expect(numeros()).toEqual([["Hoje", "0"], ["Nesta campanha", "0"], ["Total", "0"]]);
  });

  it("sem os agregados no payload (backend antigo), degrada para zero sem quebrar", async () => {
    stubFetch(DASH);
    renderArea("cheio");
    await waitFor(() => expect(document.querySelector(".cr-gasto")).toBeInTheDocument());
    expect(numeros()).toEqual([["Hoje", "0"], ["Nesta campanha", "14"], ["Total", "14"]]);
  });

  it("explica por que saldo e histórico não batem (P6: reconciliar é impossível)", async () => {
    stubFetch(GASTO);
    renderArea("cheio");
    await waitFor(() => expect(document.querySelector(".cr-gasto-msg")).toBeInTheDocument());
    const txt = document.querySelector(".cr-gasto-msg")?.textContent ?? "";
    expect(txt).toContain("CLI da Higgsfield");
    expect(txt).toContain("livro-caixa local");
    expect(txt).toContain("não aparece aqui");
  });

  it("não regrediu: o botão Atualizar saldo continua lá", async () => {
    stubFetch(GASTO);
    renderArea("cheio");
    await waitFor(() => expect(document.querySelector("#crRefresh")).toBeInTheDocument());
  });
});
