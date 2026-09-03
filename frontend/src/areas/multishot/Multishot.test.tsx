// Wave 10 · E6 (card [REACT-07]) — teste NOVO do componente compartilhado `Multishot` (ADR-017).
//
// O `test_multishot.py` (pytest) é BACKEND puro (`studio/common/multishot.py` + rotas) e PERMANECE
// intocado; este é o teste do COMPONENTE React, que o vanilla não tinha. Reproduz o contrato de DOM
// que os cenários `moodboards.py` C-MOODBOARDS-18…21 exercem: modal com imagem de origem, contador
// `#msCount`, botão `#msGen` atrás do gate de custo (ADR-016), botão `#msImport` e o carrossel das
// candidatas `role=multishot` (contador `n/total`, `remover`).
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Multishot, type MultishotOpts } from "./Multishot";

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
      status: r?.ok === false ? 400 : 200,
      statusText: "OK",
      json: async () => r?.corpo ?? {},
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", f);
  return f;
}

const OPTS: MultishotOpts = {
  title: "Multishot da imagem de vibe",
  sourceUrl: "/mbfiles/b1/candidates/src.jpg",
  action: "mood.multishot",
  parentId: "src1",
  count: 4,
  canRemove: true,
  fileUrl: (rel) => `/mbfiles/b1/candidates/${rel}`,
  endpoints: {
    generate: "/api/moodboards/b1/multishot/generate",
    job: "/api/moodboards/b1/multishot/job",
    candidates: "/api/moodboards/b1/candidates",
    upload: "/api/moodboards/b1/import/upload",
    downloadsFolder: "/api/moodboards/b1/downloads-folder",
  },
};

describe("Multishot", () => {
  it("modal com imagem de origem, contador de ângulos (4), gerar e importar", async () => {
    stubFetch([{ match: "/candidates", corpo: [] }]);
    render(<Multishot opts={OPTS} onClose={() => {}} />);

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    const src = document.querySelector<HTMLImageElement>(".ms-source img");
    expect(src?.getAttribute("src")).toContain("/mbfiles/");
    expect(document.querySelector<HTMLInputElement>("#msCount")?.value).toBe("4");
    expect(document.querySelector("#msGen")).toBeInTheDocument();
    // endpoints.upload presente → botão "Importar fotos".
    expect(document.querySelector("#msImport")).toBeInTheDocument();
    // sem resultados → mensagem vazia do carrossel.
    expect(document.querySelector(".msc-empty")).toBeInTheDocument();
  });

  it("carrossel mostra a candidata role=multishot do parent, com contador e 'remover'", async () => {
    stubFetch([
      {
        match: "/candidates",
        corpo: [
          { id: "m1", file: "m1.jpg", role: "multishot", parent: "src1", prompt: "outro ângulo" },
          { id: "x9", file: "x9.jpg", role: "vibe", parent: "src1" }, // filtrada (não é multishot)
        ],
      },
    ]);
    render(<Multishot opts={OPTS} onClose={() => {}} />);

    await waitFor(() => expect(document.querySelector(".msc-count")).toBeInTheDocument());
    expect(document.querySelector(".msc-count")?.textContent).toContain("1/1");
    const frameImg = document.querySelector<HTMLImageElement>(".msc-frame img");
    expect(frameImg?.getAttribute("src")).toBe("/mbfiles/b1/candidates/m1.jpg");
    expect(document.querySelector(".msc-tag")?.textContent).toBe("multishot");
    // canRemove → botão remover.
    expect(document.querySelector(".msc-remove")).toBeInTheDocument();
  });

  it("'Gerar' abre o gate de custo (ADR-016); cancelar não POSTa a geração", async () => {
    const f = stubFetch([
      { match: "/candidates", corpo: [] },
      {
        match: "/creditos/cost",
        corpo: {
          model: "nano",
          label: "Nano",
          credits: 7,
          source: "cli",
          balance: { installed: true, logged_in: true, credits: 100 },
        },
      },
    ]);
    render(<Multishot opts={OPTS} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText("Gerar ângulos via CLI")).toBeInTheDocument());

    await userEvent.click(screen.getByText("Gerar ângulos via CLI"));
    // o modal de custo empilha com a planilha `.cost-sheet`.
    await waitFor(() => expect(document.querySelector(".cost-sheet")).toBeInTheDocument());
    const sheet = document.querySelector(".cost-sheet")?.textContent ?? "";
    expect(sheet).toContain("Total estimado");
    expect(sheet).toContain("Saldo atual");
    expect(sheet).toContain("7"); // custo unitário

    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    // nada foi POSTado para o endpoint de geração.
    const gerou = f.mock.calls.some((c) => String(c[0]).includes("/multishot/generate"));
    expect(gerou).toBe(false);
  });
});
