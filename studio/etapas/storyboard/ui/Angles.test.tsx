// `[extensão]` Barra de geração por cena do painel 05 (FDD `storyboard-geracao-por-cena`, critérios
// 4 a 8 e 14). O que estes testes fixam, em ordem de importância:
//
// 1. FIDELIDADE AO CURSO (ADR-004): o caminho da aula 011 — gerar na UI da Higgsfield e importar —
//    continua visível e funcional; os dois atalhos são rotulados `[extensão]` e dizem o custo.
// 2. ZERO CRÉDITO SEM CONFIRMAÇÃO (ADR-016): nenhum POST de `generate`/`upscale` parte sem o par
//    `cost` → confirmação; cancelar não dispara nada.
// 3. PONTES INDEPENDENTES (ADR-033): motor local offline desabilita SÓ o botão local; CLI ausente
//    desabilita SÓ o pago. Nenhuma das duas quebra a tela nem a importação.
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { StudioCtx } from "../../../../frontend/src/shell/plugin";
import { Angles } from "./Angles";

const SCENES = {
  scenes: [
    {
      id: "cena01",
      n: 1,
      text: "close no astronauta",
      image_prompt: "A lone astronaut walking through a blizzard",
      base: "storyboard/cena01/base.png",
      base_ready: true,
      candidates: 2,
      selected: 1,
      upscaled: 0,
    },
  ],
  product_scene: { ref_ready: true, selected: false },
  palette: { colors: ["#111"] },
};
const CANDS = {
  scene: "cena01",
  base: "storyboard/cena01/base.png",
  candidates: [
    { id: "c1", file: "storyboard/cena01/candidates/c1.png", thumb: "storyboard/cena01/candidates/thumbs/c1.jpg" },
    { id: "c2", file: "storyboard/cena01/candidates/c2.png" },
  ],
};

interface Opts {
  localReady?: boolean;
  localDetail?: string;
  cli?: boolean;
}

function makeApi(o: Opts = {}) {
  const { localReady = true, localDetail = "", cli = true } = o;
  // O 2º parâmetro existe para que `api.mock.calls` carregue o `RequestInit` (método e corpo) —
  // é o que os testes inspecionam para provar a ORDEM cost → confirmação → generate.
  return vi.fn(async (path: string, opts?: RequestInit) => {
    void opts;
    if (path === "/api/higgsfield/status") return { installed: cli, logged_in: cli };
    if (path.endsWith("/storyboard/local/status")) return { ready: localReady, detail: localDetail };
    if (path.endsWith("/storyboard/script")) return { script: null };
    if (path.endsWith("/angles/scenes")) return SCENES;
    if (path.includes("/scenes/cena01/candidates")) return CANDS;
    if (path.endsWith("/product/candidates")) return { candidates: [] };
    if (path.includes("/prompts")) return { prompts: [{ label: "ângulo", text: "another point of view" }] };
    if (path.includes("/cost")) return { total: 48 };
    return {};
  });
}

function makeCtx(api: ReturnType<typeof makeApi>): StudioCtx {
  return {
    api: api as unknown as StudioCtx["api"],
    apiUpload: vi.fn(async () => ({})) as unknown as StudioCtx["apiUpload"],
    toast: vi.fn(),
    pid: () => "p1",
    project: () => ({ id: "p1", name: "QA" }) as unknown as ReturnType<StudioCtx["project"]>,
    files: (p: string) => `/files/p1/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
  };
}

/** `progressJob` pola o `/job` por `fetch` cru (fonte única do vanilla) — devolve sempre `done`. */
function stubJobFetch() {
  const original = globalThis.fetch;
  globalThis.fetch = vi.fn(async () => ({
    json: async () => ({ state: "done", done: 1, total: 1, added: 1, log: [] }),
  })) as unknown as typeof fetch;
  return () => {
    globalThis.fetch = original;
  };
}

/** Botão de ação do modal (o `<Modal>` vai para um portal em `document.body`). */
function acaoDoModal(rotulo: string): HTMLButtonElement {
  const botoes = [...document.querySelectorAll<HTMLButtonElement>(".modal-backdrop .modal-actions button")];
  const alvo = botoes.find((b) => (b.textContent || "").includes(rotulo));
  if (!alvo) throw new Error(`ação "${rotulo}" ausente no modal (${botoes.map((b) => b.textContent).join(" | ")})`);
  return alvo;
}

const posts = (api: ReturnType<typeof makeApi>) =>
  api.mock.calls.filter(([, o]) => (o as RequestInit | undefined)?.method === "POST").map(([p]) => p as string);

async function montar(o: Opts = {}) {
  const api = makeApi(o);
  const r = render(<Angles ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" />);
  await waitFor(() => expect(r.container.querySelector("#btnSceneLocal")).toBeTruthy());
  await waitFor(() => expect(api.mock.calls.some(([p]) => (p as string).endsWith("/local/status"))).toBe(true));
  return { api, ...r };
}

let restaurarFetch: () => void;
beforeEach(() => {
  restaurarFetch = stubJobFetch();
});
afterEach(() => restaurarFetch());

describe("Ângulos · barra de geração por cena `[extensão]`", () => {
  it("mostra os três atalhos com o custo no rótulo, sem esconder o caminho da aula", async () => {
    const { container } = await montar();
    expect(container.querySelector("#btnSceneLocal")?.textContent).toBe("Gerar imagem da cena - local (grátis)");
    expect(container.querySelector("#btnSceneCli")?.textContent).toBe("Gerar via CLI (gasta créditos)");
    expect(container.querySelector("#btnSceneUpscale")?.textContent).toBe("Upscalar 2x (gasta créditos)");
    // rótulo de extensão (gate 2 do CLAUDE.md) e o lembrete do método da aula (ADR-004)
    expect(container.querySelector("#shotsGenBar .eyebrow")?.textContent).toBe("[extensão]");
    expect(container.querySelector("#shotsGenNote")?.textContent).toContain(
      "gerar na UI da Higgsfield e importar",
    );
    // o builder de prompt da aula e o chip de importação continuam onde estavam
    expect(container.querySelector("#btnPrompts")).toBeTruthy();
    expect(container.querySelector("#shotsCounts")).toBeTruthy();
  });

  it("o caminho da aula (gerar na UI da Higgsfield e importar) continua funcional", async () => {
    const api = makeApi();
    const { container } = render(<Angles ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" />);
    // cena do produto ainda sem candidatos → o vazio traz o texto da aula
    await waitFor(() => expect(container.querySelector("#shotsCounts")).toBeTruthy());
    fireEvent.click(container.querySelector("[data-scene='__produto__']") as HTMLElement);
    expect(await screen.findByText("Nenhum candidato — gere na UI da Higgsfield e importe.")).toBeInTheDocument();
    // e o modal de importação (Downloads/histórico/upload) abre normalmente
    fireEvent.click(container.querySelector("#shotsCounts") as HTMLButtonElement);
    await waitFor(() => expect(document.querySelector("#shImpDrop")).toBeTruthy());
    expect(document.querySelector("#shImpDownloads")).toBeTruthy();
  });

  it("pré-preenche o prompt da cena com o `image_prompt` vindo do backend", async () => {
    const { container } = await montar();
    await waitFor(() =>
      expect((container.querySelector("#shotsGenPrompt") as HTMLInputElement).value).toBe(
        "A lone astronaut walking through a blizzard",
      ),
    );
  });

  it("o motor local (grátis) manda `scene` e NÃO passa pelo gate de custo", async () => {
    const { api, container } = await montar();
    fireEvent.click(container.querySelector("#btnSceneLocal") as HTMLButtonElement);
    await waitFor(() => expect(posts(api).some((p) => p.endsWith("/storyboard/local/generate"))).toBe(true));
    const [, opts] = api.mock.calls.find(([p]) => (p as string).endsWith("/storyboard/local/generate"))!;
    expect(JSON.parse((opts as RequestInit).body as string)).toMatchObject({ scene: "cena01", count: 4 });
    // grátis: nenhuma consulta de custo e nenhum modal de custo
    expect(posts(api).some((p) => p.includes("/cost"))).toBe(false);
  });

  it("o CLI consulta o custo ANTES e só gera depois do 'Gerar' (ADR-016)", async () => {
    const { api, container } = await montar();
    fireEvent.click(container.querySelector("#btnSceneCli") as HTMLButtonElement);
    await waitFor(() => expect(document.querySelector(".modal-backdrop")).toBeTruthy());
    // o custo já foi consultado; a geração ainda NÃO partiu
    expect(posts(api)).toContain("/api/projects/p1/storyboard/angles/scenes/cena01/cost");
    expect(posts(api).some((p) => p.endsWith("/scenes/cena01/generate"))).toBe(false);
    expect(document.querySelector(".cost-line")?.textContent).toContain("48");

    fireEvent.click(acaoDoModal("Gerar via CLI"));
    await waitFor(() => expect(posts(api).some((p) => p.endsWith("/scenes/cena01/generate"))).toBe(true));
    const ordem = posts(api).filter((p) => p.includes("/scenes/cena01/"));
    expect(ordem.indexOf("/api/projects/p1/storyboard/angles/scenes/cena01/cost")).toBeLessThan(
      ordem.findIndex((p) => p.endsWith("/generate")),
    );
  });

  it("cancelar no gate de custo não dispara generate nem upscale (critério 5)", async () => {
    const { api, container } = await montar();
    fireEvent.click(container.querySelector("#btnSceneCli") as HTMLButtonElement);
    await waitFor(() => expect(document.querySelector(".modal-backdrop")).toBeTruthy());
    fireEvent.click(acaoDoModal("Cancelar"));
    await waitFor(() => expect(document.querySelector(".modal-backdrop")).toBeNull());
    expect(posts(api).some((p) => p.endsWith("/generate") || p.endsWith("/upscale"))).toBe(false);
  });

  it("o upscale 2x exige um candidato marcado e passa pelo mesmo gate", async () => {
    const { api, container } = await montar();
    // sem marcação: nada parte
    fireEvent.click(container.querySelector("#btnSceneUpscale") as HTMLButtonElement);
    await waitFor(() => expect(document.querySelector(".modal-backdrop")).toBeNull());
    expect(posts(api).some((p) => p.endsWith("/upscale"))).toBe(false);

    fireEvent.click(container.querySelector("#shotsGallery .card[data-id='c2']") as HTMLElement);
    fireEvent.click(container.querySelector("#btnSceneUpscale") as HTMLButtonElement);
    await waitFor(() => expect(document.querySelector(".modal-backdrop")).toBeTruthy());
    fireEvent.click(acaoDoModal("Upscalar 2x"));
    await waitFor(() => expect(posts(api).some((p) => p.endsWith("/scenes/cena01/upscale"))).toBe(true));
    const [, opts] = api.mock.calls.find(([p]) => (p as string).endsWith("/scenes/cena01/upscale"))!;
    expect(JSON.parse((opts as RequestInit).body as string).id).toBe("c2");
  });

  it("motor local offline desabilita SÓ o botão local, com o motivo no title (critério 6)", async () => {
    const { container } = await montar({ localReady: false, localDetail: "suba o ComfyUI local (porta 8188)" });
    const local = container.querySelector("#btnSceneLocal") as HTMLButtonElement;
    expect(local.disabled).toBe(true);
    expect(local.title).toBe("suba o ComfyUI local (porta 8188)");
    expect((container.querySelector("#btnSceneCli") as HTMLButtonElement).disabled).toBe(false);
  });

  it("CLI ausente desabilita SÓ os botões pagos (critério 6, inverso)", async () => {
    const { container } = await montar({ cli: false });
    expect((container.querySelector("#btnSceneCli") as HTMLButtonElement).disabled).toBe(true);
    expect((container.querySelector("#btnSceneUpscale") as HTMLButtonElement).disabled).toBe(true);
    expect((container.querySelector("#btnSceneLocal") as HTMLButtonElement).disabled).toBe(false);
    expect((container.querySelector("#btnSceneCli") as HTMLButtonElement).title).toContain(
      "gere na UI da Higgsfield e importe",
    );
  });

  it("um candidato da cena vira base pelo botão já existente (critério 8)", async () => {
    const { api, container } = await montar();
    fireEvent.click(container.querySelector("#shotsGallery button.asBase") as HTMLButtonElement);
    await waitFor(() => expect(posts(api).some((p) => p.endsWith("/scenes/cena01/base"))).toBe(true));
    const [, opts] = api.mock.calls.find(([p]) => (p as string).endsWith("/scenes/cena01/base"))!;
    expect(JSON.parse((opts as RequestInit).body as string)).toEqual({ source: "candidate", id: "c1" });
  });

  it("a cena do produto usa as rotas do produto, inclusive a geração local (critério 14)", async () => {
    const { api, container } = await montar();
    fireEvent.click(container.querySelector("[data-scene='__produto__']") as HTMLElement);
    await waitFor(() => expect(container.querySelector("#sceneTitle")?.textContent).toContain("Produto"));
    fireEvent.change(container.querySelector("#shotsGenPrompt") as HTMLInputElement, {
      target: { value: "the can, frozen" },
    });

    fireEvent.click(container.querySelector("#btnSceneLocal") as HTMLButtonElement);
    await waitFor(() => expect(posts(api).some((p) => p.endsWith("/storyboard/local/generate"))).toBe(true));
    const [, local] = api.mock.calls.find(([p]) => (p as string).endsWith("/storyboard/local/generate"))!;
    expect(JSON.parse((local as RequestInit).body as string).scene).toBe("product");

    fireEvent.click(container.querySelector("#btnSceneCli") as HTMLButtonElement);
    await waitFor(() => expect(document.querySelector(".modal-backdrop")).toBeTruthy());
    expect(posts(api)).toContain("/api/projects/p1/storyboard/angles/product/cost");
    fireEvent.click(acaoDoModal("Gerar via CLI"));
    await waitFor(() => expect(posts(api).some((p) => p.endsWith("/product/generate"))).toBe(true));
    const [, pago] = api.mock.calls.find(([p]) => (p as string).endsWith("/product/generate"))!;
    // o contrato do produto manda `prompt` (singular), não `prompts`
    expect(JSON.parse((pago as RequestInit).body as string).prompt).toBe("the can, frozen");
  });
});
