// `[extensão]` Wave 11 · F06 — padrão visual da campanha e herança de preset por foto (card #98).
//
// Cobre os critérios C1, C2, C3, C4 e C6 do FDD §9 no lado do CLIENTE: o bloco `#sbCampaignPreset`
// grava as cinco ações em um clique pelas rotas `preset-config` que JÁ existiam, o `RealismField`
// por foto ganha herança explícita, e `genVideoPrompt`/`buildPayload` preservam os TRÊS estados do
// preset (chave ausente ≠ `null` ≠ id — invariante 6).
//
// A asserção que mais importa aqui é sobre `Object.keys` do corpo, não sobre o valor: mandar
// `preset: null` é o que ANULAVA o default da campanha, e um teste sobre o valor não pegaria isso.
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, waitFor, within } from "@testing-library/react";

import { Ideation } from "./Ideation";
import BaseScreen from "../../base/ui/index";
import { api } from "../../../../frontend/src/api";
import type { StudioCtx } from "../../../../frontend/src/shell/plugin";
import { StudioProvider } from "../../../../frontend/src/shell/plugin";
import { ShellProvider } from "../../../../frontend/src/shell/context";
import { mockShellApi } from "../../../../frontend/src/shell/test-utils";

const PID = "p1";
const CINCO = ["storyboard.script", "storyboard.keyframe", "storyboard.angles", "motion", "base"];

const PRESETS = [
  { id: "real1", name: "Realista", desc_pt: "mais real" },
  { id: "doc2", name: "Documental", desc_pt: "rua" },
];

/** `defaults` de `GET /api/prompter/presets` com o MESMO valor para as cinco ações do conjunto. */
function defaultsUniformes(preset: string | null, source = "project") {
  const out: Record<string, { preset: string | null; source: string }> = {};
  for (const k of CINCO) out[k] = { preset, source };
  out["mood"] = { preset, source };
  return out;
}

const STATUS = {
  has_base: true,
  ideas: 1,
  selected: 1,
  base_image: "base/base_final.png",
  video_models: ["kling-2"],
  video_model_defaults: { single: "kling-2", start_end: "kling-1" },
  script_cli: true,
  script_models: [{ label: "Nano Banana Pro", default: true }],
};
const INSTRUCTIONS = {
  kinds: [{ kind: "edit", label: "Edição numerada", ui_hint: "uma por vez" }],
  models: [{ id: "nano_banana_2", label: "Nano Banana 2", default: true }],
  arc: [
    { id: "comeco", label: "começo", hint: "" },
    { id: "descoberta", label: "descoberta", hint: "" },
    { id: "acao", label: "ação", hint: "" },
    { id: "desfecho", label: "desfecho", hint: "" },
  ],
  counts: { uncertain: 4, tweak: 1 },
};
const IMG = "storyboard/ideas/i1.png";

interface Cenario {
  /** `defaults` devolvidos por `GET /api/prompter/presets` (o 1º e os seguintes, se diferirem). */
  defaults?: Record<string, unknown>[];
  /** `kind`s cujo `PUT .../preset-config` deve falhar. */
  falha?: string[];
  /** `photos[IMG]` da cena devolvida por `GET /scenes`. */
  photo?: Record<string, unknown>;
  /** preset devolvido por `POST /video-prompt`. */
  vidPreset?: string | null;
}

function cenas(photo: Record<string, unknown>) {
  return {
    scenes: [
      { id: "cena01", text: "c1", images: [IMG], primary: IMG, photos: { [IMG]: photo } },
    ],
  };
}

function fakeApi(c: Cenario = {}) {
  const defs = c.defaults ?? [defaultsUniformes("real1")];
  let leiturasDePreset = 0;
  return vi.fn(async (path: string, opts?: RequestInit) => {
    const m = (opts?.method || "GET").toUpperCase();
    if (path.includes("/prompter/preset-config")) {
      const kind =
        m === "DELETE"
          ? decodeURIComponent(path.split("/").pop() as string)
          : (JSON.parse(String(opts?.body || "{}")) as { kind?: string }).kind;
      if (c.falha?.includes(kind || "")) throw new Error(`falhou ${kind}`);
      return { kind, preset: null, source: "project" };
    }
    if (path.includes("/prompter/presets")) {
      const d = defs[Math.min(leiturasDePreset, defs.length - 1)];
      leiturasDePreset += 1;
      return { presets: PRESETS, defaults: d };
    }
    if (path.endsWith("/higgsfield/status")) return { installed: true, logged_in: true };
    if (path.endsWith("/storyboard")) return STATUS;
    if (path.endsWith("/instructions")) return INSTRUCTIONS;
    if (path.endsWith("/candidates")) return { ideas: [] };
    if (path.endsWith("/video-prompt"))
      return { prompt: "VP", source: "claude", seconds: 5, preset: c.vidPreset ?? "real1" };
    if (path.endsWith("/scenes")) return cenas(c.photo ?? { video_desc: "d", video_prompt: "vp", videos: [] });
    if (path.endsWith("/script")) return { script: null };
    return {};
  });
}

function makeCtx(api: ReturnType<typeof fakeApi>, toast = vi.fn()): StudioCtx {
  return {
    api: api as unknown as StudioCtx["api"],
    apiUpload: vi.fn(async () => ({})) as unknown as StudioCtx["apiUpload"],
    toast,
    pid: () => PID,
    project: () => ({ id: PID, name: "QA", aspect_ratio: "16:9" }) as unknown as ReturnType<StudioCtx["project"]>,
    files: (p: string) => `/files/${PID}/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
  };
}

async function montarIdeacao(c: Cenario = {}) {
  const api = fakeApi(c);
  const toast = vi.fn();
  const { container } = render(
    <Ideation ctx={makeCtx(api, toast)} refreshGuide={() => {}} bootKey={PID} onScenesReady={() => {}} />,
  );
  const bloco = await waitFor(() => {
    const el = container.querySelector("#sbCampaignPreset");
    expect(el).toBeTruthy();
    return el as HTMLElement;
  });
  const sel = () => bloco.querySelector(".sbCampaignPresetSel") as HTMLSelectElement;
  await waitFor(() => expect(sel().querySelectorAll("option").length).toBeGreaterThan(2));
  return { api, toast, container, bloco, sel };
}

/** Corpos JSON dos `PUT .../prompter/preset-config` que a tela mandou, na ordem. */
function corposDePut(api: ReturnType<typeof fakeApi>) {
  return api.mock.calls
    .filter(([p, o]) => String(p).endsWith("/prompter/preset-config") && (o as RequestInit)?.method === "PUT")
    .map(([, o]) => JSON.parse(String((o as RequestInit).body)) as { kind: string; preset: string | null });
}

function kindsDeDelete(api: ReturnType<typeof fakeApi>) {
  return api.mock.calls
    .filter(([p, o]) => String(p).includes("/prompter/preset-config/") && (o as RequestInit)?.method === "DELETE")
    .map(([p]) => decodeURIComponent(String(p).split("/").pop() as string));
}

describe("Padrão visual da campanha (`#sbCampaignPreset`, critério C1)", () => {
  it("renderiza com o valor resolvido de GET /api/prompter/presets?pid=", async () => {
    const { api, sel } = await montarIdeacao();
    expect(api.mock.calls.some(([p]) => String(p) === `/api/prompter/presets?pid=${PID}`)).toBe(true);
    expect(sel().value).toBe("real1");
    // o valor resolvido é o do catálogo, com o nome legível
    expect(within(sel()).getByText("Realista — mais real")).toBeInTheDocument();
  });

  it("mostra '(misto)' quando as cinco ações resolvem para presets diferentes", async () => {
    const misto = { ...defaultsUniformes("real1"), motion: { preset: "doc2", source: "project" } };
    const { sel, bloco } = await montarIdeacao({ defaults: [misto] });
    expect(within(sel()).getByText("(misto)")).toBeInTheDocument();
    expect(sel().value).toBe("__misto__");
    expect(bloco.querySelector(".sbCampaignSource")?.textContent).toBe("(misto)");
  });

  it("escolher um preset dispara CINCO PUT, um por kind, com o kind certo em cada corpo", async () => {
    const { api, sel } = await montarIdeacao({ defaults: [defaultsUniformes(null, "code")] });
    fireEvent.change(sel(), { target: { value: "doc2" } });
    await waitFor(() => expect(corposDePut(api).length).toBe(5));
    expect(corposDePut(api).map((b) => b.kind)).toEqual(CINCO);
    expect(corposDePut(api).every((b) => b.preset === "doc2")).toBe(true);
    // nivelar tudo é o ponto: escolher um valor não deixa nenhuma ação para trás
    expect(kindsDeDelete(api)).toEqual([]);
  });

  it("com 'aplicar também ao mood board' marcada, dispara SEIS", async () => {
    const { api, bloco, sel } = await montarIdeacao({ defaults: [defaultsUniformes(null, "code")] });
    fireEvent.click(bloco.querySelector(".sbCampaignMood") as HTMLInputElement);
    fireEvent.change(sel(), { target: { value: "real1" } });
    await waitFor(() => expect(corposDePut(api).length).toBe(6));
    expect(corposDePut(api).map((b) => b.kind)).toEqual([...CINCO, "mood"]);
  });

  it("escolher '(herdar do global)' dispara CINCO DELETE, um por kind", async () => {
    const { api, sel } = await montarIdeacao();
    fireEvent.change(sel(), { target: { value: "" } });
    await waitFor(() => expect(kindsDeDelete(api).length).toBe(5));
    expect(kindsDeDelete(api)).toEqual(CINCO);
    expect(corposDePut(api)).toEqual([]);
  });

  it("falha em dois dos cinco PUT cita OS DOIS kind e refaz o GET /api/prompter/presets", async () => {
    const { api, toast, sel } = await montarIdeacao({
      defaults: [defaultsUniformes(null, "code"), defaultsUniformes("doc2")],
      falha: ["storyboard.angles", "motion"],
    });
    const lidosAntes = api.mock.calls.filter(([p]) => String(p).includes("/prompter/presets")).length;
    fireEvent.change(sel(), { target: { value: "doc2" } });
    await waitFor(() => expect(toast).toHaveBeenCalled());
    const msg = String(toast.mock.calls.at(-1)?.[0]);
    expect(msg).toContain("storyboard.angles");
    expect(msg).toContain("motion");
    // sem retry automático: cinco tentativas, nem uma a mais
    expect(api.mock.calls.filter(([p, o]) => String(p).endsWith("/prompter/preset-config") && (o as RequestInit)?.method === "PUT").length).toBe(5);
    // e o estado exibido volta a ser o do SERVIDOR
    const lidosDepois = api.mock.calls.filter(([p]) => String(p).includes("/prompter/presets")).length;
    expect(lidosDepois).toBe(lidosAntes + 1);
    await waitFor(() => expect(sel().value).toBe("doc2"));
  });

  it("o bloco espelhado aparece na etapa 3 e grava pelos MESMOS kind", async () => {
    // A etapa 3 usa o `api()` real sobre `fetch` (como no vitest dela), então aqui o fingido é o
    // `fetch` — o bloco é o MESMO componente, e o que se prova é que ele escreve os mesmos `kind`.
    const fetchFalso = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      void init;
      const rota = String(input).replace(/^https?:\/\/[^/]+/, "").split("?")[0] as string;
      let corpo: unknown = {};
      if (rota.endsWith("/base/prompts"))
        corpo = { refs: [], clean_prompt: null, claude: true, palette: { colors: [] }, mood_files: [] };
      else if (rota.endsWith("/base/candidates")) corpo = { candidates: [], final: null };
      else if (rota.endsWith("/base/mood-sources")) corpo = { campaign: { count: 0 }, boards: [] };
      else if (rota.endsWith("/prompter/presets")) corpo = { presets: PRESETS, defaults: defaultsUniformes(null, "code") };
      return { ok: true, status: 200, statusText: "OK", json: async () => corpo } as unknown as Response;
    });
    vi.stubGlobal("fetch", fetchFalso);
    try {
      const ctx = makeCtx(fakeApi());
      const { container } = render(
        <ShellProvider value={mockShellApi({ pid: PID })}>
          <StudioProvider value={{ ...ctx, api }}>
            <BaseScreen />
          </StudioProvider>
        </ShellProvider>,
      );
      const bloco = await waitFor(() => {
        const el = container.querySelector("#baseCampaignPreset");
        expect(el).toBeTruthy();
        return el as HTMLElement;
      });
      const sel = bloco.querySelector(".sbCampaignPresetSel") as HTMLSelectElement;
      await waitFor(() => expect(sel.querySelectorAll("option").length).toBeGreaterThan(2));
      fireEvent.change(sel, { target: { value: "real1" } });
      const puts = () =>
        fetchFalso.mock.calls
          .filter(([, init]) => (init as RequestInit | undefined)?.method === "PUT")
          .map(([url, init]) => ({
            url: String(url),
            body: JSON.parse(String((init as RequestInit).body)) as { kind: string; preset: string | null },
          }));
      await waitFor(() => expect(puts().length).toBe(5));
      expect(puts().map((c) => c.body.kind)).toEqual(CINCO);
      expect(puts().every((c) => c.url === `/api/projects/${PID}/prompter/preset-config`)).toBe(true);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

// ---------------------------------------------------------------------------------------------

/** A linha da foto da cena01, já montada. */
async function montarFoto(c: Cenario = {}) {
  const api = fakeApi(c);
  const { container } = render(
    <Ideation ctx={makeCtx(api)} refreshGuide={() => {}} bootKey={PID} onScenesReady={() => {}} />,
  );
  const linha = await waitFor(() => {
    const el = container.querySelector("#sbScenes .scene-row[data-sid='cena01'] .sb-photorow");
    expect(el).toBeTruthy();
    return el as HTMLElement;
  });
  const realism = linha.querySelector(".sbRealismPreset") as HTMLSelectElement;
  await waitFor(() => expect(realism.querySelectorAll("option").length).toBe(4));
  return { api, container, linha, realism };
}

/** Corpo do último `POST .../video-prompt`. */
function corpoDoVideoPrompt(api: ReturnType<typeof fakeApi>) {
  const call = api.mock.calls.filter(([p, o]) => String(p).endsWith("/video-prompt") && (o as RequestInit)?.method === "POST").at(-1);
  return JSON.parse(String((call?.[1] as RequestInit).body)) as Record<string, unknown>;
}

/** Corpo do último `PUT /scenes`. */
function corpoDoPutScenes(api: ReturnType<typeof fakeApi>) {
  const call = api.mock.calls.filter(([p, o]) => String(p).endsWith("/scenes") && (o as RequestInit)?.method === "PUT").at(-1);
  return JSON.parse(String((call?.[1] as RequestInit).body)) as {
    scenes: { photos: Record<string, Record<string, unknown>> }[];
  };
}

describe("Herança de preset por foto (critérios C2, C3 e C4)", () => {
  it("o RealismField tem as três opções, com '(padrão da campanha: X)' selecionada por default", async () => {
    const { realism } = await montarFoto();
    const opcoes = [...realism.querySelectorAll("option")].map((o) => [o.value, o.textContent]);
    expect(opcoes).toEqual([
      ["", "(padrão da campanha: Realista)"],
      ["off", "(sem preset)"],
      ["real1", "Realista — mais real"],
      ["doc2", "Documental — rua"],
    ]);
    // o vazio (herdar) é o default de uma foto que nunca teve preset gravado
    expect(realism.value).toBe("");
  });

  it("'(padrão da campanha: sem preset)' quando a campanha também não tem preset", async () => {
    const { realism } = await montarFoto({ defaults: [defaultsUniformes(null, "code")] });
    expect(realism.querySelector("option")?.textContent).toBe("(padrão da campanha: sem preset)");
  });

  it("herdando, o corpo do /video-prompt NÃO contém a chave `preset` (C2)", async () => {
    const { api, linha } = await montarFoto();
    fireEvent.click(linha.querySelector(".sbVidPrompt") as HTMLButtonElement);
    await waitFor(() => expect(api.mock.calls.some(([p]) => String(p).endsWith("/video-prompt"))).toBe(true));
    const body = corpoDoVideoPrompt(api);
    // a asserção é sobre a AUSÊNCIA da chave: `preset: null` significaria "sem preset explícito"
    // e anularia o default da ação `motion` — o defeito 3 do FDD.
    expect(Object.keys(body)).not.toContain("preset");
    expect(Object.keys(body).sort()).toEqual(["description", "frames", "scene_id"]);
  });

  it("com '(sem preset)' na foto, o corpo contém `preset: null` (C3)", async () => {
    const { api, linha, realism } = await montarFoto({ vidPreset: null });
    fireEvent.change(realism, { target: { value: "off" } });
    fireEvent.click(linha.querySelector(".sbVidPrompt") as HTMLButtonElement);
    await waitFor(() => expect(api.mock.calls.some(([p]) => String(p).endsWith("/video-prompt"))).toBe(true));
    const body = corpoDoVideoPrompt(api);
    expect(Object.keys(body)).toContain("preset");
    expect(body.preset).toBeNull();
  });

  it("com um id escolhido na foto, o corpo contém esse id", async () => {
    const { api, linha, realism } = await montarFoto();
    fireEvent.change(realism, { target: { value: "doc2" } });
    fireEvent.click(linha.querySelector(".sbVidPrompt") as HTMLButtonElement);
    await waitFor(() => expect(api.mock.calls.some(([p]) => String(p).endsWith("/video-prompt"))).toBe(true));
    expect(corpoDoVideoPrompt(api).preset).toBe("doc2");
  });

  it("grava o preset RESOLVIDO da resposta em origin.video_prompt.preset no PUT /scenes seguinte", async () => {
    const { api, linha } = await montarFoto({ vidPreset: "real1" });
    fireEvent.click(linha.querySelector(".sbVidPrompt") as HTMLButtonElement);
    await waitFor(() =>
      expect(api.mock.calls.some(([p, o]) => String(p).endsWith("/scenes") && (o as RequestInit)?.method === "PUT")).toBe(true),
    );
    const foto = corpoDoPutScenes(api).scenes[0]!.photos[IMG]!;
    expect(foto.origin).toEqual({
      video_prompt: { source: "ia", preset: "real1", at: expect.any(String) as unknown as string },
    });
    // a escolha do usuário continua sendo "herdar": gerar não pode congelar a herança
    expect(Object.keys(foto)).not.toContain("preset");
  });

  it("buildPayload envia os três estados de photos[img].preset (ausente / null / id)", async () => {
    const { api, linha, realism } = await montarFoto();
    const salvar = () => fireEvent.click(linha.ownerDocument.querySelector("#sbSave") as HTMLButtonElement);

    // 1) herdando: a chave nem aparece
    salvar();
    await waitFor(() => expect(corpoDoPutScenes(api)).toBeTruthy());
    expect(Object.keys(corpoDoPutScenes(api).scenes[0]!.photos[IMG]!)).not.toContain("preset");

    // 2) "(sem preset)": `null` explícito
    fireEvent.change(realism, { target: { value: "off" } });
    salvar();
    await waitFor(() => expect("preset" in corpoDoPutScenes(api).scenes[0]!.photos[IMG]!).toBe(true));
    expect(corpoDoPutScenes(api).scenes[0]!.photos[IMG]!.preset).toBeNull();

    // 3) id escolhido
    fireEvent.change(realism, { target: { value: "doc2" } });
    salvar();
    await waitFor(() => expect(corpoDoPutScenes(api).scenes[0]!.photos[IMG]!.preset).toBe("doc2"));
  });

  it("seedPhotos relê os três estados de um GET /scenes (C4 no cliente)", async () => {
    // (a) chave AUSENTE → herda (valor vazio no seletor)
    const semChave = await montarFoto({ photo: { video_desc: "d", video_prompt: "vp", videos: [] } });
    expect(semChave.realism.value).toBe("");

    // (b) `null` → "(sem preset)"
    const nulo = await montarFoto({ photo: { video_desc: "d", video_prompt: "vp", videos: [], preset: null } });
    expect(nulo.realism.value).toBe("off");

    // (c) id → esse id
    const comId = await montarFoto({ photo: { video_desc: "d", video_prompt: "vp", videos: [], preset: "doc2" } });
    expect(comId.realism.value).toBe("doc2");
  });

  it("origin lido do GET /scenes sobrevive ao PUT seguinte (metadado não se perde ao salvar)", async () => {
    const origem = { image_prompt: { source: "manual", preset: null, at: "2026-09-06T10:00:00" } };
    const { api, linha } = await montarFoto({
      photo: { video_desc: "d", video_prompt: "vp", videos: [], origin: origem },
    });
    fireEvent.click(linha.ownerDocument.querySelector("#sbSave") as HTMLButtonElement);
    await waitFor(() => expect(corpoDoPutScenes(api)).toBeTruthy());
    expect(corpoDoPutScenes(api).scenes[0]!.photos[IMG]!.origin).toEqual(origem);
  });
});

describe("Herança anunciada na foto (rodada de review 001, issue_022)", () => {
  it("nomeia o preset só quando `motion` e `storyboard.keyframe` resolvem para o MESMO id", async () => {
    const { realism } = await montarFoto({ defaults: [defaultsUniformes("real1")] });
    const herda = [...realism.options].find((o) => o.value === "");
    expect(herda?.textContent).toContain("padrão da campanha: Realista");
  });

  it("não nomeia nada quando as duas ações divergem — o rótulo mentiria (§10 Risco 4)", async () => {
    // A foto tem UM preset só, mas ele viaja para `motion` (/video-prompt) E para
    // `storyboard.keyframe` (/image-prompt). Nomear o de `motion` quando os dois divergem
    // afirmaria um preset que o `/image-prompt` não vai receber.
    const divergente = { ...defaultsUniformes("real1"), "storyboard.keyframe": { preset: "doc2", source: "project" } };
    const { realism } = await montarFoto({ defaults: [divergente] });
    const herda = [...realism.options].find((o) => o.value === "");
    expect(herda?.textContent).toContain("padrão da campanha");
    expect(herda?.textContent).not.toContain("Realista");
    expect(herda?.textContent).not.toContain("Documental");
  });
});
