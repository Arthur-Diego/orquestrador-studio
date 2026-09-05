// Substituto Vitest de `tests/test_storyboard_view.py` (metade view) e dos asserts sobre `view.*` de
// `test_storyboard_api.py`/`test_storyboard_angles_api.py` — Wave 10 · E8 (card [REACT-09]).
//
// A regra de ouro (recon §7.2): o substituto NÃO copia a técnica de "substring sobre o fonte" do
// pytest; ele RENDERIZA o componente e afirma DOM + comportamento. O que se preserva com mais rigor
// são os asserts de FIDELIDADE AO CURSO (ADR-004): os textos de aula e os rótulos `[extensão]` que a
// tela mostra, a ordem dos painéis, e as rotas do contrato congelado que os botões acionam.
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { StudioCtx } from "../../../../frontend/src/shell/plugin";
import { Ideation } from "./Ideation";
import { Angles } from "./Angles";

const STATUS = {
  has_base: true,
  ideas: 2,
  selected: 1,
  base_image: "base/base_final.png",
  video_models: ["kling-2", "kling-1"],
  video_model_defaults: { single: "kling-2", start_end: "kling-1" },
  script_cli: true,
  script_preset_default: "real1",
  script_models: [{ label: "Nano Banana Pro", default: true }],
};
const INSTRUCTIONS = {
  kinds: [
    { kind: "edit", label: "Edição numerada", ui_hint: "uma instrução por vez" },
    { kind: "multishot", label: "Multi Shot", ui_hint: "varie o ângulo" },
  ],
  models: [{ id: "nano_banana_2", label: "Nano Banana 2", default: true }],
  arc: [
    { id: "comeco", label: "começo", hint: "h" },
    { id: "descoberta", label: "descoberta", hint: "h" },
    { id: "acao", label: "ação", hint: "h" },
    { id: "desfecho", label: "desfecho", hint: "h" },
  ],
  counts: { uncertain: 4, tweak: 1 },
};
const PRESETS = {
  presets: [{ id: "real1", name: "Realista", desc_pt: "mais real" }],
  defaults: { motion: { preset: "real1" }, "storyboard.script": { preset: "real1" } },
};
const IDEAS = [
  { id: "i1", file: "storyboard/candidates/i1.png", prompt: "p1", selected: true },
  { id: "i2", file: "storyboard/candidates/i2.png", selected: false },
];
const SCENES = [
  {
    id: "cena01",
    text: "começo qa",
    images: ["storyboard/ideas/i1.png"],
    primary: "storyboard/ideas/i1.png",
    photos: { "storyboard/ideas/i1.png": { video_desc: "d", video_prompt: "vp existente", videos: [] } },
  },
  { id: "cena02", text: "descoberta qa", images: [], primary: null, photos: {} },
];
const SCRIPT = {
  script: {
    scenes: [{ arc: "comeco", text: "cena um", image_prompt: "ip", shot_prompts: ["sp1", "sp2"] }],
    generated_at: "2026-09-03T10:00:00",
    preset: "real1",
    aspect_ratio: "16:9",
    notes_pt: "nota do roteiro",
  },
};

function ideationApi() {
  return vi.fn(async (path: string, opts?: RequestInit) => {
    const post = opts?.method === "POST";
    if (path.endsWith("/higgsfield/status")) return { installed: true, logged_in: true };
    if (path.endsWith("/storyboard")) return STATUS;
    if (path.includes("/prompter/presets")) return PRESETS;
    if (path.endsWith("/instructions") && post) return { instruction: "INSTRUÇÃO MONTADA", ui_hint: "4 variações" };
    if (path.endsWith("/instructions")) return INSTRUCTIONS;
    if (path.endsWith("/candidates")) return { ideas: IDEAS };
    if (path.endsWith("/scenes") && !post) return { scenes: SCENES };
    if (path.endsWith("/script")) return SCRIPT;
    if (path.endsWith("/video-prompt")) return { prompt: "PROMPT DE VÍDEO GERADO", source: "claude", seconds: 5 };
    if (path.endsWith("/scenes")) return { scenes: SCENES };
    return {};
  });
}

function makeCtx(api: ReturnType<typeof vi.fn>): StudioCtx {
  return {
    api: api as unknown as StudioCtx["api"],
    apiUpload: vi.fn(async () => ({})) as unknown as StudioCtx["apiUpload"],
    toast: vi.fn(),
    pid: () => "p1",
    project: () => ({ id: "p1", name: "QA", aspect_ratio: "16:9" }) as unknown as ReturnType<StudioCtx["project"]>,
    files: (p: string) => `/files/p1/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
  };
}

describe("Storyboard · metade ideação (aula 010 + `[extensão]`)", () => {
  it("desenha os painéis na ordem 01 ideias · área marcada · 02 roteiro · 03 história", async () => {
    const api = ideationApi();
    const { container } = render(<Ideation ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" onScenesReady={() => {}} />);
    await waitFor(() => expect(container.querySelector("#sbScenes .scene-row")).toBeTruthy());

    // numeração e rótulos `[extensão]` (ADR-004 / ADR-025)
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText("Ideias a partir da imagem base")).toBeInTheDocument();
    const roteiro = screen.getByText("Roteiro por Claude");
    const historia = screen.getByText("A história em cenas");
    // o painel do roteiro (02) precede a história (03) — card V2ROuQ23
    expect(roteiro.compareDocumentPosition(historia) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.getByText("03")).toBeInTheDocument();
  });

  it("mostra o aviso fixo best-effort e o rótulo do painel de área marcada (ADR-004)", async () => {
    const api = ideationApi();
    render(<Ideation ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" onScenesReady={() => {}} />);
    await screen.findByText("Área marcada");
    expect(
      screen.getByText(
        "Best-effort por prompt: a marcação vai como referência, não é inpaint com máscara; o resultado pode variar fora da área marcada (CLI sem máscara, ADR-002)",
      ),
    ).toBeInTheDocument();
    // rótulos [extensão] presentes (área + roteiro)
    expect(screen.getAllByText("[extensão]").length).toBeGreaterThanOrEqual(2);
  });

  it("expõe o alvo fixo 'Nano Banana Pro' como leitura no painel do roteiro (gate W3 P3)", async () => {
    const api = ideationApi();
    const { container } = render(<Ideation ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" onScenesReady={() => {}} />);
    await waitFor(() => expect(container.querySelector("#sbScriptModel")?.textContent).toContain("Nano Banana Pro"));
    // o alvo do prompt de imagem e a proporção do projeto são LEITURA (<span>), não seletores —
    // gate W3 P3: v1 não tem seletor de modelo (só o de realismo, que é outra coisa)
    expect(container.querySelector("#sbScriptModel")?.tagName).toBe("SPAN");
    expect(container.querySelector("#sbScriptAspect")?.tagName).toBe("SPAN");
    expect(container.querySelector("#sbScriptAspect")?.textContent).toBe("16:9");
  });

  it("desenha uma linha por foto com o bloco de vídeo (ADR-022) e o seletor de realismo `(sem preset)`", async () => {
    const api = ideationApi();
    const { container } = render(<Ideation ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" onScenesReady={() => {}} />);
    const linha = await waitFor(() => {
      const el = container.querySelector("#sbScenes .scene-row[data-sid='cena01'] .sb-photorow");
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    // vídeo por foto: descrição, prompt (box visível pois há prompt existente), animação, reorder
    expect(linha.querySelector(".sbVidDesc")).toBeTruthy();
    expect(linha.querySelector(".sbAnim")).toBeTruthy();
    expect(linha.querySelector(".sbAnnotate")).toBeTruthy();
    expect(linha.querySelector(".sbPhotoUp")).toBeTruthy();
    expect(linha.querySelector(".sbVidPromptText")?.textContent).toBe("vp existente");
    // preset de realismo `[extensão]` com a rota de fuga
    const realism = linha.querySelector(".sbRealismPreset") as HTMLSelectElement;
    expect(realism).toBeTruthy();
    expect(within(realism).getByText("(sem preset)")).toBeInTheDocument();
    // a foto vertical é a alça de reordenar (a .sb-key)
    expect(linha.querySelector(".sb-key")).toBeTruthy();
  });

  it("lista os momentos do arco da aula por cena (começo · descoberta …)", async () => {
    const api = ideationApi();
    const { container } = render(<Ideation ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" onScenesReady={() => {}} />);
    await waitFor(() => expect(container.querySelectorAll("#sbScenes .scene-row .mom").length).toBe(2));
    // com 2 cenas o arco vai direto de começo (n<=1) a desfecho (n>=total) — os dois extremos da aula
    const moms = [...container.querySelectorAll("#sbScenes .scene-row .mom")].map((n) => n.textContent);
    expect(moms).toEqual(["começo", "desfecho"]);
  });

  it("o botão 'Montar instrução — gere 4' posta em /instructions com count 4 e mostra o texto montado", async () => {
    const api = ideationApi();
    const { container } = render(<Ideation ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" onScenesReady={() => {}} />);
    await waitFor(() => expect((container.querySelector("#sbGen4") as HTMLButtonElement)?.disabled).toBe(false));
    fireEvent.change(container.querySelector("#sbText") as HTMLTextAreaElement, { target: { value: "make it smaller" } });
    fireEvent.click(container.querySelector("#sbGen4") as HTMLButtonElement);
    await waitFor(() =>
      expect(api.mock.calls.some(([p, o]) => p.endsWith("/instructions") && o?.method === "POST" && JSON.parse(o.body as string).count === 4)).toBe(true),
    );
    await waitFor(() => expect(container.querySelector("#sbInstruction")?.textContent).toBe("INSTRUÇÃO MONTADA"));
    // gerador DETERMINÍSTICO: montar a instrução NÃO abre modal de progresso (substituto do pytest
    // test_progress_modal::test_deterministic_generators_do_not_open_a_modal)
    expect(document.querySelector(".modal.progress-modal")).toBeNull();
  });

  it("'Gerar prompt' da foto aciona /video-prompt (wave 7) e ABRE o modal de progresso (não determinístico)", async () => {
    const api = ideationApi();
    const { container } = render(<Ideation ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" onScenesReady={() => {}} />);
    const linha = await waitFor(() => {
      const el = container.querySelector("#sbScenes .scene-row[data-sid='cena01'] .sb-photorow");
      expect(el).toBeTruthy();
      return el as HTMLElement;
    });
    fireEvent.click(linha.querySelector(".sbVidPrompt") as HTMLButtonElement);
    // o vídeo por foto chama o Claude via `ui.progress` — ao contrário dos geradores determinísticos,
    // ESTE abre um modal de progresso
    await waitFor(() => expect(document.querySelector(".modal.progress-modal")).toBeTruthy());
    await waitFor(() => expect(api.mock.calls.some(([p, o]) => p.endsWith("/video-prompt") && o?.method === "POST")).toBe(true));
  });

  it("o roteiro lista as fotos inferidas por cena (shot_prompts), cada uma copiável (ADR-028)", async () => {
    const api = ideationApi();
    const { container } = render(<Ideation ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" onScenesReady={() => {}} />);
    await waitFor(() => expect(container.querySelectorAll("#sbScriptScenes .prompt").length).toBe(2));
    const blocos = container.querySelectorAll("#sbScriptScenes .prompt .sbScriptPromptText");
    expect([...blocos].map((n) => n.textContent)).toEqual(["sp1", "sp2"]);
    expect(container.querySelector("#sbScriptScenes .sb-script-shots")?.textContent).toContain("2 foto(s)");
  });

  it("mantém os controles da história: + cena, Reordenar cenas, Gerar storyboard.md, Salvar", async () => {
    const api = ideationApi();
    const { container } = render(<Ideation ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" onScenesReady={() => {}} />);
    await waitFor(() => expect(container.querySelector("#sbReorder")).toBeTruthy());
    for (const id of ["#sbAdd", "#sbReorder", "#sbRender", "#sbSave"]) {
      expect(container.querySelector(id)).toBeTruthy();
    }
  });
});

// ================= metade ângulos =================
const ANG_SCENES = {
  scenes: [
    { id: "cena01", text: "c1", base: "storyboard/cena01/base.png", base_ready: true, candidates: 3, selected: 2, upscaled: 1 },
    { id: "cena02", text: "c2", base: "", base_ready: false, candidates: 0, selected: 0, upscaled: 0 },
  ],
  product_scene: { ref_ready: false, selected: false },
  palette: { colors: ["#111", "#222"] },
};
const ANG_CANDS = {
  candidates: [
    { id: "c1", file: "storyboard/cena01/candidates/c1.png", upscaled: false, selected: true, selected_order: 1 },
    { id: "c2", file: "storyboard/cena01/candidates/c2.png", upscaled: false },
  ],
};

function anglesApi() {
  return vi.fn(async (path: string) => {
    if (path.endsWith("/angles/scenes")) return ANG_SCENES;
    if (path.endsWith("/product/candidates")) return { candidates: [] };
    if (path.includes("/scenes/cena01/candidates")) return ANG_CANDS;
    if (path.includes("/scenes/cena01/prompts")) return { prompts: [{ label: "01. ângulo", text: "a low angle wide shot of the astronaut" }] };
    return { candidates: [] };
  });
}

describe("Storyboard · metade ângulos (aula 011 + produto aula 013)", () => {
  it("lista um card por cena + o card do produto, com a paleta do mood", async () => {
    const api = anglesApi();
    const { container } = render(<Angles ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" />);
    await waitFor(() => expect(container.querySelectorAll("#sceneList [data-scene]").length).toBe(3));
    const ids = [...container.querySelectorAll("#sceneList [data-scene]")].map((n) => (n as HTMLElement).dataset.scene);
    expect(ids).toEqual(["cena01", "cena02", "__produto__"]);
    // paleta do mood (2 cores + rótulo)
    expect(container.querySelectorAll("#shotsPalette span").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("paleta do mood")).toBeInTheDocument();
    // contagem N/M upscalados da 1ª cena
    expect(container.querySelector("#sceneList [data-scene='cena01'] .upcount")?.textContent).toBe("1/2 upscalados");
  });

  it("abre a cena e carrega candidatos, título e chip do painel 05", async () => {
    const api = anglesApi();
    const { container } = render(<Angles ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" />);
    await waitFor(() => expect(container.querySelector("#shotsGallery .card")).toBeTruthy());
    // cena01 abre por padrão (1ª cena): título "Cena 01"
    expect(container.querySelector("#sceneTitle")?.textContent).toContain("Cena 01");
    expect(container.querySelectorAll("#shotsGallery .card").length).toBe(2);
    expect(container.querySelector("#shotsCounts")?.textContent).toContain("2 candidatos");
    // reidrata a escolha salva (selected/selected_order) — 1 escolhido
    expect(container.querySelector("#shotsCounts")?.textContent).toContain("1 escolhidos");
    expect(container.querySelectorAll("#shotsGallery .card.sel").length).toBe(1);
  });

  it("#btnPrompts monta o prompt de ângulo com foco/escala/ângulo pela rota /prompts", async () => {
    const api = anglesApi();
    const { container } = render(<Angles ctx={makeCtx(api)} refreshGuide={() => {}} bootKey="p1" />);
    await waitFor(() => expect(container.querySelector("#btnPrompts")).toBeTruthy());
    fireEvent.change(container.querySelector("#promptSubject") as HTMLInputElement, { target: { value: "the astronaut's face" } });
    fireEvent.click(container.querySelector("#btnPrompts") as HTMLButtonElement);
    await waitFor(() => expect(api.mock.calls.some(([p]) => p.includes("/scenes/cena01/prompts"))).toBe(true));
    await waitFor(() => expect(container.querySelector("#shotsPrompts .txt")?.textContent).toContain("low angle wide shot"));
    // gerador DETERMINÍSTICO (prompt de ângulo): NÃO abre modal de progresso (substituto do pytest
    // test_progress_modal::test_deterministic_generators_do_not_open_a_modal)
    expect(document.querySelector(".modal.progress-modal")).toBeNull();
  });
});
