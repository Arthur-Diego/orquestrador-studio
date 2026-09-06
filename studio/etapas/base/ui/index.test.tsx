// Substituto Vitest da etapa 3 (Imagem base) — Wave 10 · E7 (card [REACT-08]).
//
// Substitui os testes de FONTE do vanilla que liam `base/view.{html,js}` (`test_prompter_presets_view.py`
// inteiro + os ~15 testes de `test_base_api.py` que liam a view — recon §7.1). A regra de ouro (recon
// §7.2): NÃO copiar o assert-de-substring; renderizar o componente e asseverar DOM + comportamento. Os
// asserts de fidelidade ao curso (ADR-004 — um texto de aula específico na tela) são preservados.
import { render, fireEvent, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import BaseScreen from "./index";
import { api, apiUpload } from "../../../../frontend/src/api";
import type { StudioCtx } from "../../../../frontend/src/shell/plugin";
import { StudioProvider } from "../../../../frontend/src/shell/plugin";
import { ShellProvider } from "../../../../frontend/src/shell/context";
import { mockShellApi } from "../../../../frontend/src/shell/test-utils";

const PID = "camp-a";

interface Cenario {
  candidates?: unknown;
  final?: string | null;
  claude?: boolean;
  cost?: { total: number | null; per_item: number | null } | number;
  generate?: unknown;
}

function respostasBase(over: Cenario = {}): Record<string, unknown> {
  const refs = [
    {
      ref_id: "r1",
      file: "refs/brainstorming/r1.png",
      prompt: "PROMPT DA REFERENCIA R1",
      provenance: {
        paragraph: "produto na neve",
        parts: [{ label: "Composition", from: "reference", text: "hero centralizado" }],
      },
    },
    { ref_id: "r2", file: "refs/brainstorming/r2.png", prompt: "PROMPT DA REFERENCIA R2", provenance: null },
  ];
  return {
    "GET /api/projects/camp-a/base/prompts": {
      refs,
      clean_prompt: "Remove the brand from the packaging.",
      claude: over.claude ?? true,
      palette: { colors: ["#0ff0ff", "#1a1a2e"], note: "" },
      mood_files: ["mood/selected/m0.jpg"],
    },
    "GET /api/projects/camp-a/base/candidates": {
      candidates: over.candidates ?? [
        { id: "c1", kind: "situation", selected: true, file: "base/candidates/c1.png", source: "upload" },
      ],
      final: over.final === undefined ? "base/base_final.png" : over.final,
    },
    "GET /api/projects/camp-a/base/mood-sources": {
      campaign: { count: 1 },
      boards: [{ id: "b1", name: "Board X", count: 2 }],
    },
    "GET /api/prompter/presets": {
      defaults: { base: { preset: "" } },
      presets: [
        { id: "p_red", name: "RED Commercial Precision", desc_pt: "nitidez cristalina para produto" },
        { id: "p_arri", name: "ARRI Natural Narrative", desc_pt: "narrativa orgânica" },
      ],
    },
    "GET /api/projects/camp-a/base/brand-image": {},
    "GET /api/projects/camp-a/refs/validated-brand": { brand: "Marca da Etapa 1" },
    "GET /api/mood/downloads-folder": { folder: "/tmp/downloads", exists: true },
    "GET /api/projects/camp-a/guide/base": {
      id: "base",
      n: 3,
      title: "Imagem base",
      aula: "009",
      status: "in_progress",
      progress: 0.5,
      what: "",
      checklist: [],
      inputs: [],
      outputs: [],
      validations: [],
      missing: ["upscale"],
      summary: null,
      summary_kind: null,
      next_action: "Fazer o upscale 2x",
      next_step: null,
    },
    "POST /api/projects/camp-a/base/cost": over.cost ?? { total: 7, per_item: 7 },
    "POST /api/projects/camp-a/base/prompts/generate": over.generate ?? { source: "claude", seconds: 1 },
  };
}

function instalarFetch(rotas: Record<string, unknown>) {
  const fetchFalso = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const bruto = String(input);
    const semQuery = bruto.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    const metodo = (init?.method || "GET").toUpperCase();
    const chave = `${metodo} ${semQuery}`;
    const corpo = chave in rotas ? rotas[chave] : {};
    return {
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => corpo,
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", fetchFalso);
  return fetchFalso;
}

function ctxDeTeste(): StudioCtx {
  return {
    api,
    apiUpload,
    toast: vi.fn(),
    pid: () => PID,
    project: () => null,
    files: (p: string) => `/files/${PID}/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
  };
}

function renderBase() {
  const ctx = ctxDeTeste();
  const shell = mockShellApi({ pid: PID });
  const utils = render(
    <ShellProvider value={shell}>
      <StudioProvider value={ctx}>
        <BaseScreen />
      </StudioProvider>
    </ShellProvider>,
  );
  return { ...utils, ctx, shell };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Etapa 3 · Imagem base (porte React)", () => {
  it("mantém os 3 painéis do curso (01/02/03) e não traz painel 04 nem `details.lesson`", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelector("#baseClaude")?.textContent).toBe("bot: claude ok"));

    const pns = [...container.querySelectorAll(".panel-head .pn")].map((e) => e.textContent);
    expect(pns).toEqual(["01", "02", "03"]);
    // `.sb-campaign` é o bloco `[extensão]` "Padrão visual da campanha" (Wave 11 · F06), que não é
    // painel de aula: a fidelidade que este teste guarda é a de não inventar um painel 04 do CURSO.
    expect(container.querySelectorAll("section.panel:not(.sb-campaign)")).toHaveLength(3);
    expect(container.querySelector("details.lesson")).toBeNull();
    // o texto do cabeçalho é conteúdo de aula (ADR-004)
    expect(container.querySelector(".stephead .eyebrow")?.textContent).toBe("Etapa 3 · aula 009");
    expect(container.querySelector(".stephead h2")?.textContent).toBe("Imagem base");
    // o botão de reset é do shell (ADR-010), desenhado no header
    expect(container.querySelector("header.stephead .shell-reset")?.textContent).toBe("Resetar etapa [extensão]");
  });

  it("o chip do bot reflete a disponibilidade do Claude em /base/prompts", async () => {
    instalarFetch(respostasBase({ claude: false }));
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelector("#baseClaude")?.textContent).toBe("bot: sem claude"));
    expect(container.querySelector("#baseClaude")?.className).toContain("warn");
  });

  it("mostra a tira de referências + hero e troca a seleção ao clicar noutra referência", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#refGallery .card")).toHaveLength(2));

    const ids = [...container.querySelectorAll<HTMLElement>("#refGallery .card")].map((e) => e.dataset.ref);
    expect(ids).toEqual(["r1", "r2"]);
    expect(container.querySelector("#refGallery .card.sel")?.getAttribute("data-ref")).toBe("r1");
    expect(container.querySelector("#baseRefHero img")).not.toBeNull();

    // vai para o passo "situação" para ver o card da referência (o seed abre em "rótulo")
    fireEvent.click(container.querySelector("#baseChain [data-step=situation]")!);
    fireEvent.click(container.querySelectorAll("#refGallery .card")[1]!);
    await waitFor(() =>
      expect(container.querySelector("#basePrompts textarea")?.getAttribute("data-k")).toBe("p:r2"),
    );
    expect(container.querySelector("#refGallery .card.sel")?.getAttribute("data-ref")).toBe("r2");
    expect(container.querySelector("#baseRefHero img")?.getAttribute("alt")).toContain("r2");
  });

  it("card único de prompt mostra o prompt da referência selecionada (passo situação)", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#refGallery .card")).toHaveLength(2));
    fireEvent.click(container.querySelector("#baseChain [data-step=situation]")!);
    fireEvent.click(container.querySelector("#refGallery .card")!);

    await waitFor(() =>
      expect(container.querySelector("#basePrompts .eyebrow")?.textContent).toContain("situação"),
    );
    expect(container.querySelectorAll("#basePrompts .prompt")).toHaveLength(1);
    expect((container.querySelector("#basePrompts textarea") as HTMLTextAreaElement).value).toBe(
      "PROMPT DA REFERENCIA R1",
    );
  });

  it("a junção mostra a equação referência + mood → prompt com a paleta e o seletor de fonte do mood", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#refGallery .card")).toHaveLength(2));
    fireEvent.click(container.querySelector("#baseChain [data-step=situation]")!);
    await waitFor(() => expect(container.querySelector("#baseJunction .bs-fuse")).not.toBeNull());

    expect(container.querySelectorAll("#baseJunction .bs-fuse .bs-fuse-thumb")).toHaveLength(1);
    expect(container.querySelector("#baseJunction .bs-fuse-out")?.textContent).toBe("prompt");
    expect(container.querySelectorAll("#baseJunction .bs-fuse-mood .mm-cell")).toHaveLength(1);
    const cores = [...container.querySelectorAll<HTMLElement>("#baseJunction .swatches .sw")].map((e) => e.title);
    expect(cores).toEqual(["#0ff0ff", "#1a1a2e"]);
    // o seletor de fonte do mood lista a campanha e os boards da biblioteca (ADR-013)
    const opcoes = [...container.querySelectorAll("#moodSource option")].map((e) => e.textContent);
    expect(opcoes).toEqual(["Mood da campanha (1 img)", "Board: Board X (2 img) [extensão]"]);
    expect(container.querySelector<HTMLOptionElement>("#moodSource option")!.value).toBe("");
  });

  it("'De onde vem cada parte' nasce recolhido e mostra a proveniência do prompt", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#refGallery .card")).toHaveLength(2));
    fireEvent.click(container.querySelector("#baseChain [data-step=situation]")!);
    await waitFor(() => expect(container.querySelector("#baseProvenance details.bs-prov-det")).not.toBeNull());
    const det = container.querySelector<HTMLDetailsElement>("#baseProvenance details.bs-prov-det")!;
    expect(det.open).toBe(false);
    expect(container.querySelectorAll("#baseProvenance .prov-line").length).toBeGreaterThanOrEqual(1);
    expect(container.querySelector("#baseProvenance .bs-chip.from-join")?.textContent).toBe("junção");
  });

  it("no passo 'rótulo' o card de prompt vira a instrução FIXA de troca de rótulo e a junção some", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    // o seed tem 'situation' escolhido → o passo ativo default é 'label' (COURSE_CHAIN)
    await waitFor(() => expect(container.querySelector("#baseChain .st.on")?.getAttribute("data-step")).toBe("label"));
    expect(container.querySelector("#basePrompts .eyebrow")?.textContent).toContain("rótulo");
    expect(container.querySelector("#basePrompts textarea")?.getAttribute("data-k")).toBe("label");
    expect((container.querySelector("#basePrompts textarea") as HTMLTextAreaElement).value).toContain(
      "Apply the attached brand/logo image",
    );
    expect(container.querySelector("#baseJunction")?.innerHTML).toBe("");
  });

  it("o stepper traz os 4 passos (situação → limpar marca → rótulo → upscale) com done/on", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#baseChain [data-step]").length).toBe(4));
    const passos = [...container.querySelectorAll<HTMLElement>("#baseChain [data-step]")].map((e) => e.dataset.step);
    expect(passos).toEqual(["situation", "clean", "label", "upscale"]);
    // 'situation' está escolhido no seed → done; o passo ativo (label) → on
    expect(container.querySelector("#baseChain [data-step=situation]")?.className).toContain("done");
    expect(container.querySelectorAll("#baseChain .st.on")).toHaveLength(1);
  });

  it("clicar num passo troca o passo ativo e o rótulo do botão do CLI", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#baseChain [data-step]").length).toBe(4));
    fireEvent.click(container.querySelector("#baseChain [data-step=upscale]")!);
    expect(container.querySelector("#baseChain .st.on")?.getAttribute("data-step")).toBe("upscale");
    expect(container.querySelector("#btnBaseCli")?.textContent).toBe("Gerar upscale via CLI");
    fireEvent.click(container.querySelector("#baseChain [data-step=situation]")!);
    expect(container.querySelector("#btnBaseCli")?.textContent).toBe("Gerar situação via CLI");
  });

  it("o passo 'limpar marca' [extensão] tem o campo target, avisa que não é inpaint e só aparece no passo clean", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#baseChain [data-step]").length).toBe(4));
    const clean = container.querySelector<HTMLElement>("#baseCleanStep")!;
    // nasce escondido (o passo ativo do seed é 'label')
    expect(clean.style.display).toBe("none");
    expect(clean.querySelector("#cleanTarget")).not.toBeNull();
    expect(within(clean).getByText("[extensão]")).toBeTruthy();
    expect(clean.textContent).toContain("o Nano Banana não faz inpaint com máscara");
    // ao entrar no passo, aparece; e o campo vem pré-preenchido pela marca validada da etapa 1 (ADR-020)
    fireEvent.click(container.querySelector("#baseChain [data-step=clean]")!);
    expect(container.querySelector<HTMLElement>("#baseCleanStep")!.style.display).not.toBe("none");
    await waitFor(() =>
      expect((container.querySelector("#cleanTarget") as HTMLInputElement).value).toBe("Marca da Etapa 1"),
    );
  });

  it("'Trocar pela minha marca' só navega para o passo do rótulo (não gera nada)", async () => {
    const fetchFalso = instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#baseChain [data-step]").length).toBe(4));
    fireEvent.click(container.querySelector("#baseChain [data-step=clean]")!);
    fireEvent.click(container.querySelector("#btnCleanToLabel")!);
    expect(container.querySelector("#baseChain .st.on")?.getAttribute("data-step")).toBe("label");
    const gerou = fetchFalso.mock.calls.some(([u, i]) => String(u).includes("/base/generate") && i?.method === "POST");
    expect(gerou).toBe(false);
  });

  it("oferece geração via CLI nos painéis 01 e 03 com custo por passo e a linha do Higgsfield (UI ilimitada)", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelector("#baseClaude")?.textContent).toBe("bot: claude ok"));
    expect(container.querySelector("#btnBaseCli")).not.toBeNull();
    expect(container.querySelector("#baseCliCost")).not.toBeNull();
    expect(container.querySelector("#btnBasePanel01Cli")?.textContent).toBe("Gerar via CLI");
    expect(container.querySelector("#basePanel01CliCost")).not.toBeNull();
    expect(container.querySelector(".bs-hf")?.textContent).toContain("Higgsfield (UI ilimitada)");
  });

  it("'Gerar via CLI' mostra o custo antes de gastar; cancelar não gera nada", async () => {
    const fetchFalso = instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelector("#btnBaseCli")).not.toBeNull());
    fireEvent.click(container.querySelector("#btnBaseCli")!);
    // o modal de custo (ui.confirmCost) abre com a estimativa em créditos
    await waitFor(() => expect(document.querySelector(".modal[role=dialog]")).not.toBeNull());
    const modal = document.querySelector(".modal[role=dialog]")!;
    expect(modal.textContent).toContain("créditos");
    expect(container.querySelector("#baseCliCost")?.textContent).toContain("créditos");
    // Cancelar
    fireEvent.click(within(modal as HTMLElement).getByText("Cancelar"));
    const gerou = fetchFalso.mock.calls.some(([u, i]) => String(u).includes("/base/generate") && i?.method === "POST");
    expect(gerou).toBe(false);
  });

  it("sem custo (CLI deslogado) avisa em vez de estourar erro cru e não abre modal", async () => {
    const { container, ctx } = (() => {
      instalarFetch(respostasBase({ cost: { total: null, per_item: null } }));
      return renderBase();
    })();
    await waitFor(() => expect(container.querySelector("#btnBaseCli")).not.toBeNull());
    fireEvent.click(container.querySelector("#btnBaseCli")!);
    await waitFor(() => expect(ctx.toast).toHaveBeenCalled());
    expect(document.querySelector(".modal[role=dialog]")).toBeNull();
    expect(container.querySelector("#baseCliCost")?.textContent).toContain("indisponível");
  });

  it("mostra o card da imagem base final e a dica de que segue para o storyboard", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelector("#baseFinalCard .bs-final")).not.toBeNull());
    expect(container.querySelector("#baseFinalCard .chip")?.textContent).toContain("imagem base final");
    expect(container.querySelector("#baseFinalCard")?.textContent).toContain("segue para o storyboard →");
  });

  it("cada candidata vira um tile com o selo do passo e ✓ na escolhida", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#baseGallery .card")).toHaveLength(1));
    expect(container.querySelector("#baseGallery .card .src")?.textContent).toBe("situação ✓");
    expect(container.querySelector("#baseGallery .card .term")?.textContent).toBe("upload");
  });

  it("o seletor de preset de realismo [extensão] é opt-in e consome o catálogo (default resolvido)", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() =>
      expect(container.querySelectorAll("#baseRealismPreset option").length).toBe(3),
    );
    const sel = container.querySelector<HTMLSelectElement>("#baseRealismPreset")!;
    expect(sel.value).toBe(""); // default de código nulo → "(sem preset)"
    expect(sel.getAttribute("aria-label")).toBe("Preset de realismo (extensão)");
    const opcoes = [...sel.options].map((o) => o.textContent);
    expect(opcoes[0]).toBe("(sem preset)");
    expect(opcoes).toContain("RED Commercial Precision — nitidez cristalina para produto");
    // o rótulo do campo carrega o selo [extensão]
    expect(container.querySelector(".bs-preset .ext")?.textContent).toBe("[extensão]");
  });

  it("declara todos os ids que o contrato DOM da etapa exige (recon §3.12)", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelector("#baseClaude")).not.toBeNull());
    for (const id of [
      "baseClaude",
      "refGallery",
      "baseRefHero",
      "promptInstruction",
      "btnPrompt",
      "btnPromptNoBias",
      "baseRealismPreset",
      "basePrompts",
      "btnBasePanel01Cli",
      "basePanel01CliCost",
      "baseProvenance",
      "brandImage",
      "brandDrop",
      "brandPreview",
      "btnBrandClear",
      "btnBaseSelect",
      "baseChain",
      "baseCleanStep",
      "cleanTarget",
      "btnCleanToLabel",
      "baseDrop",
      "baseUpload",
      "btnBaseDownloads",
      "btnBaseHistory",
      "btnBaseCli",
      "baseCliCost",
      "baseGallery",
      "baseFinalCard",
      "baseGenResult",
    ]) {
      expect(container.querySelector(`#${id}`), id).not.toBeNull();
    }
  });

  it("'Usar como imagem base' só habilita depois de marcar uma candidata", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#baseGallery .card")).toHaveLength(1));
    expect((container.querySelector("#btnBaseSelect") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(container.querySelector("#baseGallery .card")!);
    expect((container.querySelector("#btnBaseSelect") as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(container.querySelector("#baseGallery .card")!); // desmarca
    expect((container.querySelector("#btnBaseSelect") as HTMLButtonElement).disabled).toBe(true);
  });

  it("'Gerar prompt' (Claude ok) abre o modal de progresso com a fase 'Consultando o Claude'", async () => {
    // Substitui test_progress_modal.py::test_sync_claude_calls_open_the_progress_modal (parte base) e
    // a parte de progresso de test_view_follows_the_wave2_screen_contract: chamada síncrona ao bot →
    // Studio.ui.progress (fases), não progressJob.
    const fetchFalso = instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelector("#baseClaude")?.textContent).toBe("bot: claude ok"));
    fireEvent.click(container.querySelector("#btnPrompt")!);
    await waitFor(() => {
      const modal = document.querySelector(".modal.progress-modal");
      expect(modal).not.toBeNull();
      expect(modal!.textContent).toContain("Consultando o Claude");
    });
    const gerou = fetchFalso.mock.calls.some(
      ([u, i]) => String(u).includes("/base/prompts/generate") && i?.method === "POST",
    );
    expect(gerou).toBe(true);
  });

  it("no passo 'limpar marca' o corpo de cost/generate leva o target (FDD §5)", async () => {
    // Substitui test_base_api.py::test_clean_gen_body_sends_target — asseverado pelo fluxo real.
    const fetchFalso = instalarFetch(respostasBase({ cost: { total: 5, per_item: 5 } }));
    const { container } = renderBase();
    await waitFor(() => expect(container.querySelectorAll("#baseChain [data-step]").length).toBe(4));
    fireEvent.click(container.querySelector("#baseChain [data-step=clean]")!);
    await waitFor(() =>
      expect((container.querySelector("#cleanTarget") as HTMLInputElement).value).toBe("Marca da Etapa 1"),
    );
    fireEvent.click(container.querySelector("#btnBaseCli")!);
    await waitFor(() => {
      const chamada = fetchFalso.mock.calls.find(
        ([u, i]) => String(u).includes("/base/cost") && i?.method === "POST",
      );
      expect(chamada).toBeTruthy();
      const corpo = JSON.parse(String((chamada![1] as RequestInit).body)) as { kind: string; target: string };
      expect(corpo.kind).toBe("clean");
      expect(corpo.target).toBe("Marca da Etapa 1");
    });
  });

  it("o tooltip do botão de Downloads informa a pasta e a janela de 120 min (não no corpo da tela)", async () => {
    instalarFetch(respostasBase());
    const { container } = renderBase();
    await waitFor(() =>
      expect(container.querySelector("#btnBaseDownloads")?.getAttribute("title")).toContain("/tmp/downloads"),
    );
    const title = container.querySelector("#btnBaseDownloads")?.getAttribute("title") || "";
    expect(title).toContain("120 min");
    expect(container.querySelector("#main")).toBeNull(); // o #main é do shell; a tela não o repete
  });
});
