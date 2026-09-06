// `[extensão]` Wave 11 · F06 — campos abertos de prompt por foto e roteiro visível na tela
// (cards #99 e #95, leitura A). Cobre os critérios A1, A5 e D2-D8 do FDD §9 no lado do CLIENTE.
//
// O que este arquivo guarda, e que nenhum outro teste guardava:
//
//   1. o prompt de vídeo era um `<p>` de LEITURA: dava para gerar, nunca para escrever;
//   2. o prompt de imagem por foto não existia na tela — só o do roteiro, que também não era
//      editável, e por isso o keyframe do usuário não tinha onde morar;
//   3. `#sbScriptGen` nascia `disabled` sem o Claude no PATH: a tela escondia a funcionalidade em
//      vez de explicar a falta (critério A1);
//   4. `applyScript` copiava só o `text` do roteiro — os `shot_prompts` ficavam para o
//      copiar-e-colar manual.
//
// O CONTRATO DE DOM com `scripts/qa/cenarios/storyboard.py` (que NÃO pode ser editado) é asserido
// aqui e é a razão de o `<p class="txt sbVidPromptText">` continuar existindo, agora `hidden`:
// C-STORYBOARD-27 e C-STORYBOARD-33 leem esse elemento por `text_content()`, e C-STORYBOARD-28
// exige que `.sbVidPrompt` continue sendo um BOTÃO que POSTa mesmo com a descrição vazia.
import { describe, expect, it, vi, afterEach } from "vitest";
import { act, fireEvent, render, waitFor } from "@testing-library/react";

import { Ideation } from "./Ideation";
import type { Scene, Script, ScriptCliDiag } from "./types";
import type { StudioCtx } from "../../../../frontend/src/shell/plugin";

const PID = "p1";
/** O mesmo `PERSIST_DEBOUNCE_MS` da tela (FDD §4 fluxo 4, item 5). */
const PERSIST_MS = 400;
const A = "storyboard/ideas/a.png";
const B = "storyboard/ideas/b.png";
const C = "storyboard/ideas/c.png";

const DIAG_OFF: ScriptCliDiag = {
  name: "claude",
  available: false,
  path: null,
  searched_path: "/usr/bin:/bin",
  checked_at: "2026-09-06T14:03:11",
  hint: "Instale o Claude Code ou suba o Studio por ./run.sh e clique em Verificar de novo.",
};
const DIAG_ON: ScriptCliDiag = {
  ...DIAG_OFF,
  available: true,
  path: "/Users/x/.local/bin/claude",
  hint: "",
};

const PRESETS = {
  presets: [
    { id: "real1", name: "Realista", desc_pt: "mais real" },
    { id: "doc2", name: "Documental", desc_pt: "rua" },
  ],
  defaults: { motion: { preset: "real1" }, "storyboard.keyframe": { preset: "real1" } },
};

const IDEIAS = [
  { id: "i1", file: A, selected: true, source: "cli" },
  { id: "i2", file: B, selected: true, source: "cli" },
  { id: "i3", file: C, selected: true, source: "cli" },
];

/** Uma cena com duas fotos; a segunda cena já tem texto escrito (para o "sem tocar" do D5). */
const CENAS: Scene[] = [
  {
    id: "cena01",
    text: "",
    images: [A, B],
    primary: A,
    photos: {
      [A]: { video_desc: "d1", video_prompt: "", image_prompt: "", videos: [] },
      [B]: { video_desc: "d2", video_prompt: "", image_prompt: "", videos: [] },
    },
  },
  {
    id: "cena02",
    text: "já escrito à mão",
    images: [C],
    primary: C,
    photos: { [C]: { video_desc: "", video_prompt: "", image_prompt: "", videos: [] } },
  },
];

const SCRIPT: Script = {
  scenes: [
    { arc: "comeco", text: "t1", shot_prompts: ["s1a", "s1b", "s1c"] },
    { arc: "desfecho", text: "t2", shot_prompts: ["s2a"] },
  ],
  generated_at: "2026-09-06T10:00:00",
  preset: "doc2",
  aspect_ratio: "16:9",
  notes_pt: "nota",
};

type PromptResp = { prompt?: string; source?: string; seconds?: number; preset?: string | null };

interface Cenario {
  cenas?: Scene[];
  script?: Script | null;
  /** `script_cli_diag` do `GET /storyboard`; `null` finge servidor antigo (só `script_cli`). */
  diag?: ScriptCliDiag | null;
  scriptCli?: boolean;
  /** Respostas de `GET /script/cli?refresh=true`, consumidas na ordem. */
  refresh?: ScriptCliDiag[];
  imagePrompt?: PromptResp;
  videoPrompt?: PromptResp;
  /** Erro que `/video-prompt` levanta (o 422 de descrição vazia, C-STORYBOARD-28). */
  erroVideoPrompt?: string;
}

function fakeApi(c: Cenario = {}) {
  const refresh = [...(c.refresh || [])];
  return vi.fn(async (path: string, opts?: RequestInit) => {
    const m = (opts?.method || "GET").toUpperCase();
    if (path.includes("/prompter/presets")) return PRESETS;
    if (path.endsWith("/higgsfield/status")) return { installed: true, logged_in: true };
    if (path.includes("/script/cli")) return refresh.shift() || c.diag || DIAG_OFF;
    if (path.endsWith("/storyboard"))
      return {
        has_base: true,
        ideas: 3,
        selected: 3,
        base_image: "base/base_final.png",
        video_models: ["kling-2"],
        video_model_defaults: { single: "kling-2", start_end: "kling-1" },
        script_cli: c.scriptCli ?? false,
        ...(c.diag === null ? {} : { script_cli_diag: c.diag || DIAG_OFF }),
        script_models: [{ label: "Nano Banana Pro", default: true }],
      };
    if (path.endsWith("/instructions"))
      return {
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
    if (path.endsWith("/candidates")) return { ideas: IDEIAS };
    if (path.endsWith("/local/status")) return { ready: false, detail: "offline", gen_models: [], inpaint_models: [] };
    if (path.endsWith("/image-prompt"))
      return c.imagePrompt || { prompt: "KEYFRAME GERADO", source: "claude", seconds: 3, preset: "real1" };
    if (path.endsWith("/video-prompt")) {
      if (c.erroVideoPrompt) throw new Error(c.erroVideoPrompt);
      return c.videoPrompt || { prompt: "MOTION GERADO", source: "claude", seconds: 5, preset: "real1" };
    }
    if (path.endsWith("/video/cost")) return { credits: 10, label: "animação" };
    if (path.endsWith("/scenes")) return { scenes: c.cenas ?? CENAS };
    if (path.endsWith("/script")) return { script: c.script === undefined ? SCRIPT : c.script };
    if (m === "POST") return { started: true };
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

async function montar(c: Cenario = {}) {
  const api = fakeApi(c);
  const toast = vi.fn();
  const { container } = render(
    <Ideation ctx={makeCtx(api, toast)} refreshGuide={() => {}} bootKey={PID} onScenesReady={() => {}} />,
  );
  const linha = await waitFor(() => {
    const el = container.querySelector("#sbScenes .scene-row[data-sid='cena01'] .sb-photorow") as HTMLElement;
    expect(el).toBeTruthy();
    return el;
  });
  return { api, toast, container, linha };
}

/** Corpos de `PUT /scenes`, na ordem. */
function puts(api: ReturnType<typeof fakeApi>) {
  return api.mock.calls
    .filter(([p, o]) => String(p).endsWith("/scenes") && (o as RequestInit)?.method === "PUT")
    .map(([, o]) => JSON.parse(String((o as RequestInit).body)) as { scenes: Scene[] });
}
const ultimoPut = (api: ReturnType<typeof fakeApi>) => puts(api).at(-1);
const fotoNoPut = (api: ReturnType<typeof fakeApi>, i: number, img: string) =>
  (ultimoPut(api)?.scenes[i]?.photos || {})[img] as Record<string, unknown> | undefined;

/** Corpo do último POST em `rota`. */
function corpoDe(api: ReturnType<typeof fakeApi>, rota: string) {
  const call = api.mock.calls.filter(([p, o]) => String(p).endsWith(rota) && (o as RequestInit)?.method === "POST").at(-1);
  return call ? (JSON.parse(String((call[1] as RequestInit).body)) as Record<string, unknown>) : undefined;
}
const chamou = (api: ReturnType<typeof fakeApi>, trecho: string, metodo = "POST") =>
  api.mock.calls.some(([p, o]) => String(p).includes(trecho) && ((o as RequestInit)?.method || "GET").toUpperCase() === metodo);

const campoImg = (linha: HTMLElement) => linha.querySelector(".sbImgPromptField") as HTMLTextAreaElement;
const campoVid = (linha: HTMLElement) => linha.querySelector(".sbVidPromptField") as HTMLTextAreaElement;
const chip = (linha: HTMLElement, box: string) =>
  linha.querySelector(`.${box} .sbPromptOrigin`)?.textContent || "";

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

// =================================================================================================
describe("Contrato de DOM com o oráculo de QA (C-STORYBOARD-27/28/33)", () => {
  it("a `.sbVidPromptBox` tem o campo VISÍVEL e o `<p class='txt sbVidPromptText'>` como espelho `hidden`", async () => {
    const { linha } = await montar();
    const box = linha.querySelector(".sbVidPromptBox") as HTMLElement;
    expect(box).toBeTruthy();
    // a caixa deixou de ser "resultado" e virou campo: nunca mais nasce com a classe `hidden`
    expect(box.classList.contains("hidden")).toBe(false);
    const campo = box.querySelector(".sbVidPromptField") as HTMLTextAreaElement;
    const espelho = box.querySelector("p.txt.sbVidPromptText") as HTMLParagraphElement;
    expect(campo.tagName).toBe("TEXTAREA");
    expect(espelho).toBeTruthy();
    expect(espelho.hidden).toBe(true);
  });

  it("o espelho acompanha o campo ao DIGITAR e ao GERAR", async () => {
    const { api, linha } = await montar();
    const espelho = () => (linha.querySelector(".sbVidPromptText")?.textContent || "").trim();

    fireEvent.change(campoVid(linha), { target: { value: "a mão, em inglês" } });
    expect(espelho()).toBe("a mão, em inglês");

    // digitar marcou a origem como `manual`, então a geração seguinte PERGUNTA (critério D3)
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(linha.querySelector(".sbVidPrompt") as HTMLButtonElement);
    await waitFor(() => expect(espelho()).toBe("MOTION GERADO"));
    // e o que o espelho mostra é o que foi para o disco (a asserção do C-STORYBOARD-27)
    await waitFor(() => expect(fotoNoPut(api, 0, A)?.video_prompt).toBe("MOTION GERADO"));
  });

  it("`.sbVidPrompt` continua sendo um BOTÃO, não um campo", async () => {
    const { linha } = await montar();
    expect((linha.querySelector(".sbVidPrompt") as HTMLElement).tagName).toBe("BUTTON");
  });

  it("gerar com `video_desc` VAZIO ainda faz o POST e mostra a mensagem da API (C-STORYBOARD-28)", async () => {
    const cenas: Scene[] = [
      { id: "cena01", text: "", images: [A], primary: A, photos: { [A]: { video_desc: "", video_prompt: "", videos: [] } } },
    ];
    const { api, linha } = await montar({ cenas, erroVideoPrompt: "Descreva o que acontece no vídeo (descrição vazia)." });
    fireEvent.click(linha.querySelector(".sbVidPrompt") as HTMLButtonElement);
    // o POST tem de acontecer: adivinhar o 422 no cliente é como as duas pontas divergem
    await waitFor(() => expect(corpoDe(api, "/video-prompt")).toBeTruthy());
    expect(corpoDe(api, "/video-prompt")?.description).toBe("");
    await waitFor(() =>
      expect(document.querySelector(".modal.progress-modal .prog-err")?.textContent?.toLowerCase()).toContain("descrição"),
    );
  });
});

// =================================================================================================
describe("Prompt de imagem (keyframe) por foto (critérios D1 e D4)", () => {
  it("`button.sbImgPrompt` chama `/image-prompt` com scene_id, photo e o `video_desc` como descrição", async () => {
    const { api, linha } = await montar();
    fireEvent.click(linha.querySelector(".sbImgPrompt") as HTMLButtonElement);
    await waitFor(() => expect(corpoDe(api, "/image-prompt")).toBeTruthy());
    const body = corpoDe(api, "/image-prompt") as Record<string, unknown>;
    expect(body.scene_id).toBe("cena01");
    expect(body.photo).toBe(A);
    expect(body.description).toBe("d1");
    // herdando o padrão da campanha, a chave `preset` NÃO vai no corpo (C2)
    expect(Object.keys(body)).not.toContain("preset");
  });

  it("`source: \"claude\"` preenche o campo e o chip mostra `ia` com o preset resolvido", async () => {
    const { linha } = await montar();
    fireEvent.click(linha.querySelector(".sbImgPrompt") as HTMLButtonElement);
    await waitFor(() => expect(campoImg(linha).value).toBe("KEYFRAME GERADO"));
    expect(chip(linha, "sbImgPromptBox")).toContain("ia");
    expect(chip(linha, "sbImgPromptBox")).toContain("real1");
  });

  it("`source: \"template\"` (sem CLI) preenche igual e o chip mostra `template`", async () => {
    const { linha } = await montar({ imagePrompt: { prompt: "TEMPLATE", source: "template", preset: null } });
    fireEvent.click(linha.querySelector(".sbImgPrompt") as HTMLButtonElement);
    await waitFor(() => expect(campoImg(linha).value).toBe("TEMPLATE"));
    expect(chip(linha, "sbImgPromptBox")).toBe("template");
  });

  it("digitar marca o chip como `manual`", async () => {
    const { linha } = await montar();
    fireEvent.change(campoImg(linha), { target: { value: "meu keyframe" } });
    expect(chip(linha, "sbImgPromptBox")).toBe("manual");
  });
});

// =================================================================================================
describe("Pergunta \"Substituir?\" (critério D3)", () => {
  it("pergunta DEPOIS da resposta quando o texto é `manual`; recusar mantém o texto e oferece Copiar", async () => {
    const { api, linha } = await montar();
    fireEvent.change(campoImg(linha), { target: { value: "meu keyframe autoral" } });

    let postAntes = false;
    const conf = vi.spyOn(window, "confirm").mockImplementation(() => {
      postAntes = chamou(api, "/image-prompt");
      return false;
    });

    fireEvent.click(linha.querySelector(".sbImgPrompt") as HTMLButtonElement);
    await waitFor(() => expect(conf).toHaveBeenCalled());
    // a pergunta é feita com a sugestão já na mão — perguntar ANTES quebraria C-STORYBOARD-27/28
    expect(postAntes).toBe(true);
    expect(conf.mock.calls[0]?.[0]).toBe("Substituir o texto que você escreveu?");
    // o texto do usuário fica de pé, e a sugestão continua copiável
    expect(campoImg(linha).value).toBe("meu keyframe autoral");
    const sug = await waitFor(() => {
      const el = linha.querySelector(".sbImgPromptBox .sbPromptSuggestion") as HTMLElement;
      expect(el).toBeTruthy();
      return el;
    });
    expect(sug.querySelector(".sbSuggestText")?.textContent).toBe("KEYFRAME GERADO");
    expect(sug.querySelector(".sbSuggestCopy")).toBeTruthy();
  });

  it("aceitar substitui o texto", async () => {
    const { linha } = await montar();
    fireEvent.change(campoImg(linha), { target: { value: "meu keyframe autoral" } });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(linha.querySelector(".sbImgPrompt") as HTMLButtonElement);
    await waitFor(() => expect(campoImg(linha).value).toBe("KEYFRAME GERADO"));
  });

  it("texto de origem `ia` é regeração: NÃO pergunta nada", async () => {
    const cenas: Scene[] = [
      {
        id: "cena01",
        text: "",
        images: [A],
        primary: A,
        photos: {
          [A]: {
            video_desc: "d1",
            video_prompt: "",
            image_prompt: "keyframe anterior da IA",
            videos: [],
            origin: { image_prompt: { source: "ia", preset: "real1", at: "2026-09-06T10:00:00" } },
          },
        },
      },
    ];
    const { linha } = await montar({ cenas });
    const conf = vi.spyOn(window, "confirm").mockReturnValue(false);
    fireEvent.click(linha.querySelector(".sbImgPrompt") as HTMLButtonElement);
    await waitFor(() => expect(campoImg(linha).value).toBe("KEYFRAME GERADO"));
    expect(conf).not.toHaveBeenCalled();
  });
});

// =================================================================================================
describe("Persistência dos campos (critério D2)", () => {
  it("digitar dispara UM `PUT /scenes` depois do debounce de 400 ms, não um por tecla", async () => {
    const { api, linha } = await montar();
    const antes = puts(api).length;
    vi.useFakeTimers();
    const campo = campoImg(linha);
    fireEvent.change(campo, { target: { value: "u" } });
    fireEvent.change(campo, { target: { value: "um" } });
    fireEvent.change(campo, { target: { value: "um k" } });
    // ainda nada: três teclas, zero `PUT`
    expect(puts(api).length).toBe(antes);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(PERSIST_MS);
    });
    expect(puts(api).length).toBe(antes + 1);
    const foto = fotoNoPut(api, 0, A) as Record<string, unknown>;
    expect(foto.image_prompt).toBe("um k");
    expect((foto.origin as Record<string, { source: string }>).image_prompt?.source).toBe("manual");
  });

  it("o resultado da IA persiste IMEDIATAMENTE, sem esperar o debounce", async () => {
    const { api, linha } = await montar();
    const antes = puts(api).length;
    vi.useFakeTimers();
    fireEvent.click(linha.querySelector(".sbImgPrompt") as HTMLButtonElement);
    // nenhum avanço de relógio: só as promessas em voo
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(puts(api).length).toBe(antes + 1);
    const foto = fotoNoPut(api, 0, A) as Record<string, unknown>;
    expect(foto.image_prompt).toBe("KEYFRAME GERADO");
    expect((foto.origin as Record<string, { source: string; preset: string | null }>).image_prompt).toMatchObject({
      source: "ia",
      preset: "real1",
    });
  });
});
// =================================================================================================
describe("Roteiro visível na tela (critérios A1 e A5)", () => {
  it("`#sbScriptGen` está no DOM, HABILITADO e com o rótulo novo mesmo sem Claude no PATH", async () => {
    const { container } = await montar();
    const btn = container.querySelector("#sbScriptGen") as HTMLButtonElement;
    expect(btn).toBeTruthy();
    expect(btn.disabled).toBe(false);
    expect(btn.textContent).toBe("Gerar cenas (roteiro por Claude) [extensão]");
  });

  it("`#sbScriptCliDiag` mostra o PATH do processo e a dica, com role/aria-live", async () => {
    const { container } = await montar();
    const diag = container.querySelector("#sbScriptCliDiag") as HTMLElement;
    expect(diag).toBeTruthy();
    expect(diag.getAttribute("role")).toBe("status");
    expect(diag.getAttribute("aria-live")).toBe("polite");
    expect(diag.textContent).toContain("Claude CLI não encontrado. PATH do processo:");
    expect(diag.textContent).toContain("/usr/bin:/bin");
    expect(diag.textContent).toContain(DIAG_OFF.hint);
  });

  it("com o CLI disponível o bloco de diagnóstico não existe", async () => {
    const { container } = await montar({ diag: DIAG_ON, scriptCli: true });
    expect(container.querySelector("#sbScriptCliDiag")).toBeNull();
  });

  it("clicar sem CLI re-checa com `?refresh=true` e NÃO dispara `/script/generate` quando continua falso", async () => {
    const { api, container } = await montar();
    fireEvent.click(container.querySelector("#sbScriptGen") as HTMLButtonElement);
    await waitFor(() => expect(chamou(api, "/script/cli?refresh=true", "GET")).toBe(true));
    // o 409 do ADR-025 seria inútil: sem CLI o roteiro não tem como sair
    expect(chamou(api, "/script/generate")).toBe(false);
    expect(container.querySelector("#sbScriptCliDiag")).toBeTruthy();
  });

  it("clicar sem CLI e a re-checagem voltando `true` segue para o job NA MESMA interação", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ json: async () => ({ state: "running" }) })));
    const { api, container } = await montar({ refresh: [DIAG_ON] });
    fireEvent.click(container.querySelector("#sbScriptGen") as HTMLButtonElement);
    await waitFor(() => expect(chamou(api, "/script/generate")).toBe(true));
    expect(chamou(api, "/script/cli?refresh=true", "GET")).toBe(true);
    vi.unstubAllGlobals();
  });

  it("`#sbScriptCliRecheck` chama a rota com `refresh=true` e atualiza o bloco", async () => {
    const { api, container } = await montar({ refresh: [DIAG_ON] });
    fireEvent.click(container.querySelector("#sbScriptCliRecheck") as HTMLButtonElement);
    await waitFor(() => expect(chamou(api, "/script/cli?refresh=true", "GET")).toBe(true));
    // o binário apareceu depois de o servidor subir: o diagnóstico some sem reiniciar nada
    await waitFor(() => expect(container.querySelector("#sbScriptCliDiag")).toBeNull());
    expect(chamou(api, "/script/generate")).toBe(false);
  });
});

// =================================================================================================
describe("Prompts do roteiro nas fotos (critérios D5 e D6)", () => {
  const marcarCaixa = (container: HTMLElement) =>
    fireEvent.click(container.querySelector("#sbScriptWithPrompts") as HTMLInputElement);

  it("\"Aplicar às cenas vazias\" com a caixa marcada leva `shot_prompts[k]` à k-ésima foto, sem tocar em cena com texto", async () => {
    const { api, container } = await montar();
    await waitFor(() => expect(container.querySelectorAll("#sbScriptScenes .sbScriptPromptText").length).toBe(4));
    marcarCaixa(container);
    fireEvent.click(container.querySelector("#sbScriptApplyEmpty") as HTMLButtonElement);
    await waitFor(() => expect(fotoNoPut(api, 0, A)?.image_prompt).toBe("s1a"));
    expect(fotoNoPut(api, 0, B)?.image_prompt).toBe("s1b");
    expect((fotoNoPut(api, 0, A)?.origin as Record<string, { source: string }>).image_prompt?.source).toBe("ia");
    // a cena 2 já tinha texto: nem o texto nem o prompt dela são tocados
    expect(ultimoPut(api)?.scenes[1]?.text).toBe("já escrito à mão");
    expect(fotoNoPut(api, 1, C)?.image_prompt).toBe("");
  });

  it("prompt sobrando NÃO cria foto nenhuma e continua listado no painel 02", async () => {
    const { api, container } = await montar();
    marcarCaixa(container);
    fireEvent.click(container.querySelector("#sbScriptApplyEmpty") as HTMLButtonElement);
    await waitFor(() => expect(fotoNoPut(api, 0, A)?.image_prompt).toBe("s1a"));
    // a cena 1 tem 2 fotos e 3 sugestões: continua com 2
    expect(ultimoPut(api)?.scenes[0]?.images).toEqual([A, B]);
    expect(Object.keys(ultimoPut(api)?.scenes[0]?.photos || {})).toEqual([A, B]);
    // e "s1c" segue visível no painel 02, com o botão "usar este"
    const textos = [...container.querySelectorAll("#sbScriptScenes .sbScriptPromptText")].map((n) => n.textContent);
    expect(textos).toEqual(["s1a", "s1b", "s1c", "s2a"]);
    expect(container.querySelectorAll("#sbScriptScenes .sbScriptUse").length).toBe(4);
  });

  it("\"usar este\" grava o prompt na foto correspondente", async () => {
    const { api, container } = await montar();
    const usar = await waitFor(() => {
      const l = container.querySelectorAll("#sbScriptScenes .sbScriptUse");
      expect(l.length).toBe(4);
      return l;
    });
    fireEvent.click(usar[1] as HTMLButtonElement); // cena 1, foto 2
    await waitFor(() => expect(fotoNoPut(api, 0, B)?.image_prompt).toBe("s1b"));
    expect((fotoNoPut(api, 0, B)?.origin as Record<string, { source: string; preset: string | null }>).image_prompt).toMatchObject({
      source: "ia",
      preset: "doc2",
    });
  });

  it("sem a foto `k` na cena, a tela avisa quantas fotos a cena tem", async () => {
    const { api, toast, container } = await montar();
    const usar = await waitFor(() => {
      const l = container.querySelectorAll("#sbScriptScenes .sbScriptUse");
      expect(l.length).toBe(4);
      return l;
    });
    fireEvent.click(usar[2] as HTMLButtonElement); // cena 1, foto 3 — que não existe
    expect(toast).toHaveBeenCalledWith("A cena 1 tem 2 foto(s) — anexe mais uma para usar a foto 3.");
    expect(puts(api).length).toBe(0);
  });
});

// =================================================================================================
describe("Consumidores do campo (critérios D7 e D8)", () => {
  it("\"Gerar animação\" usa o CAMPO: prompt escrito à mão e nunca gerado inicia o fluxo de custo", async () => {
    const { api, toast, linha } = await montar();
    fireEvent.change(campoVid(linha), { target: { value: "a slow dolly in" } });
    fireEvent.click(linha.querySelector(".sbAnim") as HTMLButtonElement);
    const modal = await waitFor(() => {
      const m = document.querySelector(".modal") as HTMLElement;
      expect(m).toBeTruthy();
      return m;
    });
    fireEvent.click(modal.querySelector(".modal-actions button.primary") as HTMLButtonElement);
    await waitFor(() => expect(chamou(api, "/video/cost")).toBe(true));
    expect(toast).not.toHaveBeenCalledWith("Escreva ou gere o prompt de vídeo desta foto.");
  });

  it("com o campo de vídeo VAZIO, \"Gerar animação\" avisa e não consulta custo", async () => {
    const { api, toast, linha } = await montar();
    fireEvent.click(linha.querySelector(".sbAnim") as HTMLButtonElement);
    const modal = await waitFor(() => {
      const m = document.querySelector(".modal") as HTMLElement;
      expect(m).toBeTruthy();
      return m;
    });
    fireEvent.click(modal.querySelector(".modal-actions button.primary") as HTMLButtonElement);
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Escreva ou gere o prompt de vídeo desta foto."));
    expect(chamou(api, "/video/cost")).toBe(false);
  });

  it("\"Usar no motor local\" preenche `#sbLocalPrompt` com o prompt de imagem e move o foco", async () => {
    const { container, linha } = await montar();
    fireEvent.change(campoImg(linha), { target: { value: "a lone climber on a snowy ridge" } });
    fireEvent.click(linha.querySelector(".sbUseLocal") as HTMLButtonElement);
    const local = container.querySelector("#sbLocalPrompt") as HTMLTextAreaElement;
    await waitFor(() => expect(local.value).toBe("a lone climber on a snowy ridge"));
    expect(document.activeElement).toBe(local);
  });
});
