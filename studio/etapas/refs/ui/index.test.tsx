// Substituto Vitest dos asserts de tela do vanilla (Wave 10 · E5, card [REACT-06]).
//
// Cobre o que `tests/test_refs_view.py` (7 de 9 testes) e o `test_view_offers_the_url_import…` de
// `tests/test_refs_import_url.py` afirmavam sobre `refs/view.{html,js}` — renderizando o componente
// React e asseverando DOM + comportamento (recon §7.2), inclusive as fidelidades à aula 009
// (ADR-004). Os endpoints de backend (marca validada, suggest-terms, import por URL) seguem cobertos
// em pytest.
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { api, apiUpload } from "../../../../frontend/src/api";
import { StudioProvider, type StudioCtx } from "../../../../frontend/src/shell/plugin";
import Refs from "./index";

function jsonResp(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => data,
    text: async () => JSON.stringify(data),
  } as unknown as Response;
}

const CANDS = [
  { id: "a", term: "qa termo a", source: "pinterest", thumb: "a.jpg", file: "a.jpg", selected: false },
  { id: "b", term: "qa termo b", source: "upload", thumb: "b.jpg", file: "b.jpg", selected: true },
];
const GUIA = {
  id: "refs", n: 1, status: "todo", progress: 0, summary: null, next_action: null,
  missing: [], inputs: [], outputs: [], validations: [], next_step: null,
};

function router(url: string): Response {
  const u = url.split("?")[0] ?? url;
  if (u.endsWith("/pinterest/login")) return jsonResp({ state: "idle" });
  if (u.endsWith("/refs/candidates")) return jsonResp(CANDS);
  if (u.endsWith("/refs/validated-brand")) return jsonResp({ brand: "" });
  if (u.endsWith("/refs/job")) return jsonResp({ state: "idle" });
  if (u.includes("/guide/refs")) return jsonResp(GUIA);
  return jsonResp({});
}

function ctxFalso(): StudioCtx {
  return {
    api,
    apiUpload,
    toast: vi.fn(),
    pid: () => "camp-1",
    project: () => ({ id: "camp-1", product: "energy drink", vibe: "" }) as never,
    files: (p) => `/files/camp-1/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
  };
}

function renderTela() {
  return render(
    <StudioProvider value={ctxFalso()}>
      <Refs />
    </StudioProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => Promise.resolve(router(String(url)))),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("refs — contrato de tela (aula 009)", () => {
  it("cabeçalho fiel à aula, o painel do guia após o header e os dois painéis numerados", async () => {
    const { container } = renderTela();
    expect(screen.getByText("Etapa 1 · aula 009")).toBeInTheDocument();
    const head = container.querySelector("header.stephead");
    const guide = container.querySelector("#guide");
    expect(guide).not.toBeNull();
    // o painel do guia vem logo após o header
    expect(head?.nextElementSibling).toBe(guide);
    const pns = [...container.querySelectorAll(".pn")].map((e) => e.textContent);
    expect(pns).toEqual(["01", "02"]);
    // só a etapa 1 tem o `details.lesson`
    expect(container.querySelector("details.lesson")).not.toBeNull();
    expect(screen.getByText("O que a aula 009 manda fazer aqui")).toBeInTheDocument();
    expect(container.querySelector(".primary.cta")).not.toBeNull();
    expect(container.querySelector(".progress-lbl")).toHaveTextContent("Último scrape");
  });

  it("oferece a marca validada e o seletor de arquivos oculto do Explore, sem painel de upload", () => {
    const { container } = renderTela();
    expect(container.querySelector("#brand")).not.toBeNull();
    expect(container.querySelector("#btnSaveBrand")).toHaveTextContent("Salvar marca validada");
    const up = container.querySelector("#refsUpload") as HTMLInputElement;
    expect(up).not.toBeNull();
    expect(up.hidden).toBe(true);
    expect(up.multiple).toBe(true);
    // o painel de escolha inteiro é o alvo do drop
    expect(container.querySelector("#refsPick")).not.toBeNull();
    // o campo "por quê" e a marca de extensão do upload saíram da tela (wave 4)
    expect(container.textContent).not.toContain("Adicionar referências salvas à mão");
  });

  it("import por URL é um bloco aditivo no painel 01, com o aviso de ToS da aula", () => {
    const { container } = renderTela();
    expect(container.querySelector("#refsUrl")).not.toBeNull();
    expect(container.querySelector("#btnImportUrl")).toHaveTextContent("Importar URL");
    expect((container.querySelector("#maxPins") as HTMLInputElement).max).toBe("100");
    expect(container.textContent).toContain("Extensão do Studio");
    expect(container.textContent).toContain("conta secundária");
    expect(container.textContent).toContain("termos do Pinterest");
    // sem painel novo: seguem só os dois `.pn`
    expect(container.querySelectorAll(".pn").length).toBe(2);
  });

  it("cada candidata vira um tile com selo de fonte e legenda do termo; o contador bate", async () => {
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelectorAll("#gallery .card").length).toBe(2));
    const fontes = [...container.querySelectorAll("#gallery .card .src")].map((e) => e.textContent);
    const termos = [...container.querySelectorAll("#gallery .card .term")].map((e) => e.textContent);
    expect(fontes.sort()).toEqual(["pinterest", "upload"]);
    expect(termos.sort()).toEqual(["qa termo a", "qa termo b"]);
    // 2 candidatas, 1 já escolhida no disco
    expect(container.querySelector("#counts")).toHaveTextContent("2 candidatas · 1 escolhidas");
  });

  it("clicar num tile alterna a marcação e o contador, sem salvar (nenhum POST /select)", async () => {
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelectorAll("#gallery .card").length).toBe(2));
    const naoEscolhida = container.querySelector('#gallery .card[data-id="a"]') as HTMLElement;
    expect(naoEscolhida.className).not.toContain("sel");
    fireEvent.click(naoEscolhida);
    await waitFor(() => expect(naoEscolhida.className).toContain("sel"));
    expect(container.querySelector("#counts")).toHaveTextContent("2 candidatas · 2 escolhidas");
    const chamou = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.some((c: unknown[]) =>
      String(c[0]).includes("/refs/select"),
    );
    expect(chamou).toBe(false);
  });

  it("filtros por termo e por fonte só aparecem com mais de um valor e filtram a grade (interseção entre grupos)", async () => {
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelectorAll("#refsFilters .rf-fgroup").length).toBe(2));
    const rotulos = [...container.querySelectorAll("#refsFilters .rf-flabel")].map((e) => e.textContent);
    expect(rotulos).toEqual(["termos", "fontes"]);
    expect(container.querySelectorAll("#refsFilters input[data-filter]").length).toBe(4);
    // marca o termo A → 1 tile; soma a fonte upload → interseção 0
    fireEvent.click(container.querySelector('input[data-filter="term"][value="qa termo a"]') as Element);
    await waitFor(() => expect(container.querySelectorAll("#gallery .card").length).toBe(1));
    fireEvent.click(container.querySelector('input[data-filter="source"][value="upload"]') as Element);
    await waitFor(() => expect(container.querySelectorAll("#gallery .card").length).toBe(0));
    // o contador segue global (não filtra)
    expect(container.querySelector("#counts")).toHaveTextContent("2 candidatas");
    // 'limpar filtros' devolve a grade inteira e some do DOM
    fireEvent.click(container.querySelector("#refsFilters .rf-clear") as Element);
    await waitFor(() => expect(container.querySelectorAll("#gallery .card").length).toBe(2));
    expect(container.querySelector("#refsFilters .rf-clear")).toBeNull();
  });
});
