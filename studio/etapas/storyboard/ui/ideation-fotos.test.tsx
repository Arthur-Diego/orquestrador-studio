// `[extensão]` Wave 11 · F06 — galeria de ideias na tela, botão real, persistência imediata e
// arrastar-e-soltar (card #97).
//
// Cobre os critérios B1 a B9 e B11 do FDD §9 no lado do CLIENTE. O que este arquivo guarda, e que
// nenhum outro teste guardava:
//
//   1. o único ponto de entrada de foto na cena era um `<div role="button">` MUDO (o rótulo vinha
//      de um `::after` de 9 px em CSS);
//   2. `attachImages` SUBSTITUÍA a galeria da cena em vez de somar;
//   3. nenhum gesto de foto persistia sem clicar em "Salvar cenas";
//   4. o Risco 3 do FDD §10: numa rajada de gestos, o `PUT` mais recente tinha de refletir TODOS
//      eles — o antigo `reorderPhoto` lia `photos` de fora do `setScenes` e perdia escrita.
//
// O contrato de DOM com `scripts/qa/cenarios/storyboard.py` (que NÃO pode ser editado) também é
// asserido aqui: classe `sb-pick`, `#sbGallery .card`, `.modal-actions button.primary` como ação
// de adicionar e o botão com o texto "Sem imagem".
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, fireEvent, render, waitFor } from "@testing-library/react";

import { Ideation } from "./Ideation";
import type { Idea, Scene } from "./types";
import type { StudioCtx } from "../../../../frontend/src/shell/plugin";

const PID = "p1";
const DND_IDEA = "application/x-studio-idea";
const DND_PHOTO = "application/x-studio-photo";

const A = "storyboard/ideas/a.png";
const B = "storyboard/ideas/b.png";
const C = "storyboard/ideas/c.png";

const IDEIAS: Idea[] = [
  { id: "i1", file: A, selected: true, source: "cli" },
  { id: "i2", file: B, selected: true, source: "local", local_kind: "keyframe_local" },
  { id: "i3", file: C, selected: true, source: "local", local_kind: "inpaint_local" },
  { id: "i4", file: "storyboard/ideas/d.png", selected: false, source: "upload" },
];

const STATUS = {
  has_base: true,
  ideas: 4,
  selected: 3,
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

/** Duas cenas: a primeira já com uma foto, a segunda vazia. */
const CENAS: Scene[] = [
  { id: "cena01", text: "c1", images: [A], primary: A, photos: { [A]: { video_desc: "d1", video_prompt: "", videos: [] } } },
  { id: "cena02", text: "c2", images: [], primary: null, photos: {} },
];

interface Cenario {
  ideias?: Idea[];
  cenas?: Scene[];
  /** `POST /candidates/select` falha (fluxo alternativo do FDD §4). */
  falhaSelect?: boolean;
  /** Segura o `PUT /scenes` até `soltarPut()` — para provar a fila de um. */
  segurarPut?: boolean;
}

function fakeApi(c: Cenario = {}) {
  const presos: (() => void)[] = [];
  const api = vi.fn(async (path: string, opts?: RequestInit) => {
    const m = (opts?.method || "GET").toUpperCase();
    if (path.includes("/prompter/presets")) return { presets: [], defaults: {} };
    if (path.endsWith("/higgsfield/status")) return { installed: true, logged_in: true };
    if (path.endsWith("/storyboard")) return STATUS;
    if (path.endsWith("/instructions")) return INSTRUCTIONS;
    if (path.endsWith("/candidates")) return { ideas: c.ideias ?? IDEIAS };
    if (path.endsWith("/candidates/select")) {
      if (c.falhaSelect) throw new Error("falha ao marcar a ideia");
      return { selected: [] };
    }
    if (path.endsWith("/local/status")) return { ready: false, detail: "offline", gen_models: [], inpaint_models: [] };
    if (path.endsWith("/scenes")) {
      if (m === "PUT" && c.segurarPut) {
        await new Promise<void>((r) => presos.push(r));
        return { scenes: c.cenas ?? CENAS };
      }
      return { scenes: c.cenas ?? CENAS };
    }
    if (path.endsWith("/script")) return { script: null };
    return {};
  });
  return { api, soltarPut: () => presos.splice(0).forEach((r) => r()) };
}

function makeCtx(api: ReturnType<typeof fakeApi>["api"], toast = vi.fn()): StudioCtx {
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
  const { api, soltarPut } = fakeApi(c);
  const toast = vi.fn();
  const { container } = render(
    <Ideation ctx={makeCtx(api, toast)} refreshGuide={() => {}} bootKey={PID} onScenesReady={() => {}} />,
  );
  await waitFor(() => expect(container.querySelectorAll("#sbScenes .scene-row").length).toBeGreaterThan(0));
  return { api, toast, container, soltarPut };
}

/** Todos os corpos de `PUT /scenes` que a tela mandou, na ordem. */
function putsDeCenas(api: ReturnType<typeof fakeApi>["api"]) {
  return api.mock.calls
    .filter(([p, o]) => String(p).endsWith("/scenes") && (o as RequestInit)?.method === "PUT")
    .map(([, o]) => JSON.parse(String((o as RequestInit).body)) as { scenes: Scene[] });
}
const ultimoPut = (api: ReturnType<typeof fakeApi>["api"]) => putsDeCenas(api).at(-1);
const imagensNoPut = (api: ReturnType<typeof fakeApi>["api"], i: number) => ultimoPut(api)?.scenes[i]?.images;

const linhaDaCena = (container: HTMLElement, i: number) =>
  container.querySelectorAll("#sbScenes .scene-row")[i] as HTMLElement;

/**
 * `DataTransfer` de mentira: o jsdom não implementa o de verdade. `types` existe porque é por ele
 * que a tela distingue arrasto interno de arquivo do sistema operacional.
 */
function dt(dados: Record<string, string>) {
  return {
    types: Object.keys(dados),
    getData: (t: string) => dados[t] ?? "",
    setData: (t: string, v: string) => {
      dados[t] = v;
    },
    effectAllowed: "",
    dropEffect: "",
    files: [],
  } as unknown as DataTransfer;
}

/** Abre o picker da cena `i` e devolve o diálogo. */
async function abrirPicker(container: HTMLElement, i: number) {
  fireEvent.click(linhaDaCena(container, i).querySelector(".sb-pick") as HTMLButtonElement);
  return await waitFor(() => {
    const m = document.querySelector(".modal") as HTMLElement;
    expect(m).toBeTruthy();
    return m;
  });
}

/** Marca ideias no `#sbGallery` pelo `data-id` e aciona a ação de rótulo `label`. */
function escolherEAcionar(modal: HTMLElement, ids: string[], label: string) {
  ids.forEach((id) => fireEvent.click(modal.querySelector(`#sbGallery .card[data-id='${id}']`) as HTMLElement));
  const botao = [...modal.querySelectorAll(".modal-actions button")].find((b) => b.textContent?.includes(label));
  fireEvent.click(botao as HTMLButtonElement);
}

// =================================================================================================

describe("Galeria de ideias no painel 01 (critério B1)", () => {
  it("mostra um card por ideia, com data-* e badge legível de origem", async () => {
    const { container } = await montar();
    const grade = container.querySelector("#sbIdeasGallery") as HTMLElement;
    expect(grade).toBeTruthy();
    const cards = [...grade.querySelectorAll(".card")];
    expect(cards.length).toBe(IDEIAS.length);
    expect(cards.map((c) => c.getAttribute("data-id"))).toEqual(["i1", "i2", "i3", "i4"]);
    expect(cards[0]?.getAttribute("data-file")).toBe(A);
    expect(cards[0]?.getAttribute("data-source")).toBe("cli");
    expect(cards[0]?.textContent).toContain("Higgsfield (CLI)");
    expect(cards[1]?.textContent).toContain("Motor local (grátis)");
    expect(cards[3]?.textContent).toContain("Enviada");
    // a marca "escolhida" só aparece em quem está selecionado
    expect(cards[0]?.textContent).toContain("escolhida");
    expect(cards[3]?.textContent).not.toContain("escolhida");
  });

  it("uma ideia local de inpaint mostra 'Inpaint local', não 'Motor local'", async () => {
    const { container } = await montar();
    const card = container.querySelector("#sbIdeasGallery .card[data-id='i3']") as HTMLElement;
    // O FDD §4 parafraseia o valor como "inpaint"; o que `local.py` grava é "inpaint_local".
    expect(card.textContent).toContain("Inpaint local");
    expect(card.getAttribute("data-source")).toBe("inpaint");
  });

  it("o filtro por origem reduz a grade do painel 01 E a do PickerModal", async () => {
    const { container } = await montar();
    const filtro = container.querySelector("#sbIdeasFilter") as HTMLSelectElement;
    expect(filtro).toBeTruthy();
    expect(container.querySelectorAll("#sbIdeasGallery .card").length).toBe(4);

    fireEvent.change(filtro, { target: { value: "cli" } });
    expect(container.querySelectorAll("#sbIdeasGallery .card").length).toBe(1);

    // o MESMO filtro atravessa para o modal, sem o usuário reescolher
    const modal = await abrirPicker(container, 1);
    expect(modal.querySelectorAll("#sbGallery .card").length).toBe(1);
    expect((modal.querySelector(".sbPickerFilter") as HTMLSelectElement).value).toBe("cli");
  });

  it("o `done` de um job da própria tela refaz o GET .../storyboard/candidates", async () => {
    const { api, container } = await montar();
    const conta = () => api.mock.calls.filter(([p]) => String(p).endsWith("/candidates")).length;
    const antes = conta();
    // `progressJob` faz o poll do job pelo `fetch` global, não pelo `ctx.api`.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ json: async () => ({ state: "done", log: [], done: 1, total: 1 }) })) as unknown as typeof fetch,
    );
    try {
      // O job do roteiro é o único desta tela que não recarregava a galeria ao terminar.
      await act(async () => {
        fireEvent.click(container.querySelector("#sbScriptGen") as HTMLButtonElement);
        await new Promise((r) => setTimeout(r, 10));
      });
      await waitFor(() => expect(conta()).toBeGreaterThan(antes));
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("Botão real de adicionar foto (critério B2, C-STORYBOARD-22)", () => {
  it("é um <button> com o texto no DOM, aria-label e a classe sb-pick preservada", async () => {
    const { container } = await montar();
    const botao = linhaDaCena(container, 0).querySelector(".sb-pick") as HTMLButtonElement;
    expect(botao.tagName).toBe("BUTTON");
    expect(botao.classList.contains("sb-pick")).toBe(true);
    expect(botao.classList.contains("sbAddPhoto")).toBe(true);
    // o texto existe no DOM — antes vinha de um `::after` em CSS, ilegível para leitor de tela
    expect(botao.textContent).toContain("Adicionar foto à cena");
    expect(botao.getAttribute("aria-label")).toBe("Adicionar foto à cena 1");
    expect(linhaDaCena(container, 1).querySelector(".sb-pick")?.getAttribute("aria-label")).toBe(
      "Adicionar foto à cena 2",
    );
  });

  it("o PickerModal mantém `.modal-actions button.primary` como a ação de adicionar e o botão 'Sem imagem'", async () => {
    const { container } = await montar();
    const modal = await abrirPicker(container, 1);
    expect(modal.querySelector("#sbGallery .card")).toBeTruthy();
    const primaria = modal.querySelector(".modal-actions button.primary") as HTMLButtonElement;
    expect(primaria.textContent).toContain("Adicionar à cena");
    const semImagem = [...modal.querySelectorAll(".modal-actions button")].filter((b) =>
      b.textContent?.includes("Sem imagem"),
    );
    expect(semImagem.length).toBe(1);
  });

  it("a mensagem de vazio do picker cita o motor local do painel 01b (critério B8)", async () => {
    const { container } = await montar({ ideias: [] });
    const modal = await abrirPicker(container, 1);
    const vazio = modal.querySelector("#sbGallery .empty") as HTMLElement;
    expect(vazio.textContent).toContain("motor local");
    expect(vazio.textContent).toContain("01b");
  });
});

describe("Anexar SOMA e persiste na hora (critérios B3 e B5)", () => {
  it("anexar duas fotos a uma cena que já tem uma dá TRÊS, na ordem, e dispara PUT sem 'Salvar cenas'", async () => {
    const { api, container } = await montar();
    const modal = await abrirPicker(container, 0);
    escolherEAcionar(modal, ["i2", "i3"], "Adicionar à cena");
    await waitFor(() => expect(putsDeCenas(api).length).toBeGreaterThan(0));
    expect(imagensNoPut(api, 0)).toEqual([A, B, C]);
    // ninguém clicou em #sbSave: a persistência é do próprio gesto
    expect(api.mock.calls.some(([p, o]) => String(p).endsWith("/scenes") && (o as RequestInit)?.method === "PUT")).toBe(true);
  });

  it("anexar uma foto que já está na cena não duplica", async () => {
    const { api, container } = await montar();
    const modal = await abrirPicker(container, 0);
    escolherEAcionar(modal, ["i2"], "Adicionar à cena");
    await waitFor(() => expect(imagensNoPut(api, 0)).toEqual([A, B]));

    const modal2 = await abrirPicker(container, 0);
    escolherEAcionar(modal2, ["i2"], "Adicionar à cena");
    await waitFor(() => expect(putsDeCenas(api).length).toBeGreaterThan(1));
    expect(imagensNoPut(api, 0)).toEqual([A, B]);
  });

  it("'Substituir tudo' pede window.confirm: recusar mantém a galeria, aceitar troca", async () => {
    const { api, container } = await montar();
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    try {
      const modal = await abrirPicker(container, 0);
      // a cena 0 já tem A, então o picker nasce com i1 marcado; desmarcar i1 e marcar i2 deixa a
      // escolha em SÓ B — se "Substituir tudo" somasse (o defeito), o resultado seria [A, B].
      escolherEAcionar(modal, ["i1", "i2"], "Substituir tudo");
      expect(confirmar).toHaveBeenCalled();
      // recusou: nada de PUT e a cena continua com a foto original na tela
      expect(putsDeCenas(api).length).toBe(0);
      expect(linhaDaCena(container, 0).querySelectorAll(".sb-photorow").length).toBe(1);

      // mesma escolha, mesma ação — agora aceitando (sem reclicar card, o que desmarcaria)
      confirmar.mockReturnValue(true);
      escolherEAcionar(modal, [], "Substituir tudo");
      await waitFor(() => expect(putsDeCenas(api).length).toBe(1));
      expect(imagensNoPut(api, 0)).toEqual([B]);
    } finally {
      confirmar.mockRestore();
    }
  });
});

describe("Remoção, ★ e reordenação persistem na mesma interação (critério B4)", () => {
  async function comDuasFotos() {
    const cenas: Scene[] = [
      { id: "cena01", text: "c1", images: [A, B], primary: A, photos: {} },
      { id: "cena02", text: "c2", images: [], primary: null, photos: {} },
    ];
    return await montar({ cenas });
  }

  it("remover uma foto dispara PUT e o corpo já reflete a remoção", async () => {
    const { api, container } = await comDuasFotos();
    fireEvent.click(linhaDaCena(container, 0).querySelectorAll(".sb-rm")[0] as HTMLButtonElement);
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));
    expect(imagensNoPut(api, 0)).toEqual([B]);
    // a principal removida cede o posto para quem sobrou (ADR-018)
    expect(ultimoPut(api)?.scenes[0]?.primary).toBe(B);
  });

  it("trocar a ★ dispara PUT com a primary nova", async () => {
    const { api, container } = await comDuasFotos();
    fireEvent.click(linhaDaCena(container, 0).querySelectorAll(".sb-star")[1] as HTMLButtonElement);
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));
    expect(ultimoPut(api)?.scenes[0]?.primary).toBe(B);
  });

  it("reordenar por ↑/↓ dispara PUT com a ordem nova", async () => {
    const { api, container } = await comDuasFotos();
    fireEvent.click(linhaDaCena(container, 0).querySelectorAll(".sbPhotoDown")[0] as HTMLButtonElement);
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));
    expect(imagensNoPut(api, 0)).toEqual([B, A]);
  });

  it("remover uma foto de TODAS as cenas não dispara nenhuma desmarcação (critério B9)", async () => {
    const { api, container } = await comDuasFotos();
    const linha = linhaDaCena(container, 0);
    fireEvent.click(linha.querySelectorAll(".sb-rm")[0] as HTMLButtonElement);
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));
    fireEvent.click(linhaDaCena(container, 0).querySelectorAll(".sb-rm")[0] as HTMLButtonElement);
    await waitFor(() => expect(putsDeCenas(api).length).toBe(2));
    expect(imagensNoPut(api, 0)).toEqual([]);
    // desanexar NÃO desmarca (FDD §12 item 7): desmarcar é gesto exclusivo da galeria
    expect(api.mock.calls.some(([p]) => String(p).endsWith("/candidates/select"))).toBe(false);
  });

  it("rajada anexar → remover → estrelar: o ÚLTIMO PUT reflete os três gestos (Risco 3)", async () => {
    const cenas: Scene[] = [
      { id: "cena01", text: "c1", images: [A, B], primary: A, photos: {} },
      { id: "cena02", text: "c2", images: [], primary: null, photos: {} },
    ];
    const { api, container, soltarPut } = await montar({ cenas, segurarPut: true });

    // 1) anexar C — o PUT resultante fica preso no ar
    const modal = await abrirPicker(container, 0);
    escolherEAcionar(modal, ["i3"], "Adicionar à cena");
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));

    // 2) e 3) removem A e estrelam C enquanto o primeiro PUT ainda não voltou
    fireEvent.click(linhaDaCena(container, 0).querySelectorAll(".sb-rm")[0] as HTMLButtonElement);
    fireEvent.click(linhaDaCena(container, 0).querySelectorAll(".sb-star")[1] as HTMLButtonElement);

    // fila de UM: só um PUT no ar; os dois gestos seguintes viraram um único payload pendente
    expect(putsDeCenas(api).length).toBe(1);
    await act(async () => {
      soltarPut();
      await Promise.resolve();
    });
    await waitFor(() => expect(putsDeCenas(api).length).toBe(2));
    await act(async () => {
      soltarPut();
    });

    const ultimo = ultimoPut(api)?.scenes[0];
    expect(ultimo?.images).toEqual([B, C]); // anexou C e removeu A
    expect(ultimo?.primary).toBe(C); // e estrelou C
  });
});

describe("Arrastar e soltar (critério B6)", () => {
  it("dragstart no card da galeria grava application/x-studio-idea e soltar na cena anexa e persiste", async () => {
    const { api, container } = await montar();
    const card = container.querySelector("#sbIdeasGallery .card[data-id='i2']") as HTMLElement;
    const dados: Record<string, string> = {};
    fireEvent.dragStart(card, { dataTransfer: dt(dados) });
    expect(dados[DND_IDEA]).toBe("i2");

    const alvo = linhaDaCena(container, 1).querySelector(".sb-phototable") as HTMLElement;
    fireEvent.dragOver(alvo, { dataTransfer: dt(dados) });
    fireEvent.drop(alvo, { dataTransfer: dt(dados) });
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));
    expect(imagensNoPut(api, 1)).toEqual([B]);
  });

  it("dragstart num .sb-key grava application/x-studio-photo e soltar em OUTRA cena move num único PUT", async () => {
    const { api, container } = await montar();
    const key = linhaDaCena(container, 0).querySelector(".sb-key") as HTMLElement;
    const dados: Record<string, string> = {};
    fireEvent.dragStart(key, { dataTransfer: dt(dados) });
    expect(JSON.parse(dados[DND_PHOTO] as string)).toEqual({ sid: "cena01", img: A });

    const alvo = linhaDaCena(container, 1).querySelector(".sb-phototable") as HTMLElement;
    fireEvent.dragOver(alvo, { dataTransfer: dt(dados) });
    fireEvent.drop(alvo, { dataTransfer: dt(dados) });
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));
    // um PUT só, consistente: some da origem e aparece no destino
    expect(imagensNoPut(api, 0)).toEqual([]);
    expect(imagensNoPut(api, 1)).toEqual([A]);
    expect(ultimoPut(api)?.scenes[0]?.primary).toBeNull();
    expect(ultimoPut(api)?.scenes[1]?.primary).toBe(A);
  });

  it("soltar um .sb-key sobre outro .sb-key da MESMA cena reordena", async () => {
    const cenas: Scene[] = [
      { id: "cena01", text: "c1", images: [A, B], primary: A, photos: {} },
      { id: "cena02", text: "c2", images: [], primary: null, photos: {} },
    ];
    const { api, container } = await montar({ cenas });
    const keys = linhaDaCena(container, 0).querySelectorAll(".sb-key");
    const dados: Record<string, string> = {};
    fireEvent.dragStart(keys[1] as HTMLElement, { dataTransfer: dt(dados) });
    fireEvent.drop(keys[0] as HTMLElement, { dataTransfer: dt(dados) });
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));
    expect(imagensNoPut(api, 0)).toEqual([B, A]);
  });

  it("as classes .dragging e .dragover entram durante o gesto e saem no fim", async () => {
    const { container } = await montar();
    const card = container.querySelector("#sbIdeasGallery .card[data-id='i2']") as HTMLElement;
    const dados: Record<string, string> = {};
    fireEvent.dragStart(card, { dataTransfer: dt(dados) });
    await waitFor(() => expect(card.classList.contains("dragging")).toBe(true));

    const alvo = linhaDaCena(container, 1).querySelector(".sb-phototable") as HTMLElement;
    fireEvent.dragOver(alvo, { dataTransfer: dt(dados) });
    await waitFor(() => expect(alvo.classList.contains("dragover")).toBe(true));

    fireEvent.dragEnd(card);
    await waitFor(() => {
      expect(card.classList.contains("dragging")).toBe(false);
      expect(alvo.classList.contains("dragover")).toBe(false);
    });
  });

  it("a .sb-key ganha .dragover quando um arrasto paira sobre ela", async () => {
    const cenas: Scene[] = [
      { id: "cena01", text: "c1", images: [A, B], primary: A, photos: {} },
    ];
    const { container } = await montar({ cenas });
    const keys = linhaDaCena(container, 0).querySelectorAll(".sb-key");
    const dados: Record<string, string> = {};
    fireEvent.dragStart(keys[0] as HTMLElement, { dataTransfer: dt(dados) });
    fireEvent.dragOver(keys[1] as HTMLElement, { dataTransfer: dt(dados) });
    await waitFor(() => expect((keys[1] as HTMLElement).classList.contains("dragover")).toBe(true));
    fireEvent.dragLeave(keys[1] as HTMLElement);
    await waitFor(() => expect((keys[1] as HTMLElement).classList.contains("dragover")).toBe(false));
  });

  it("drop de arquivo do sistema operacional é IGNORADO: nenhum PUT", async () => {
    const { api, container } = await montar();
    const alvo = linhaDaCena(container, 1).querySelector(".sb-phototable") as HTMLElement;
    // o que o navegador entrega ao arrastar um arquivo da área de trabalho: nenhum MIME interno
    const arquivo = dt({ Files: "" });
    fireEvent.dragOver(alvo, { dataTransfer: arquivo });
    fireEvent.drop(alvo, { dataTransfer: arquivo });
    await Promise.resolve();
    expect(putsDeCenas(api).length).toBe(0);
    expect(alvo.classList.contains("dragover")).toBe(false);
  });
});

describe("Alternativa por teclado (critério B7)", () => {
  it("select.sbPhotoMove move a foto entre cenas com o mesmo efeito do arrasto", async () => {
    const { api, container } = await montar();
    const mover = linhaDaCena(container, 0).querySelector(".sbPhotoMove") as HTMLSelectElement;
    expect(mover).toBeTruthy();
    // lista as DEMAIS cenas, nunca a própria
    const opcoes = [...mover.querySelectorAll("option")].map((o) => o.value);
    expect(opcoes).toEqual(["", "1"]);
    expect(mover.textContent).toContain("Mover para…");

    fireEvent.change(mover, { target: { value: "1" } });
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));
    expect(imagensNoPut(api, 0)).toEqual([]);
    expect(imagensNoPut(api, 1)).toEqual([A]);
  });
});

describe("Ideia ainda não escolhida (fluxo alternativo do FDD §4)", () => {
  it("soltar uma ideia não `selected` chama POST /candidates/select ANTES do PUT /scenes", async () => {
    const { api, container } = await montar();
    const card = container.querySelector("#sbIdeasGallery .card[data-id='i4']") as HTMLElement;
    const dados: Record<string, string> = {};
    fireEvent.dragStart(card, { dataTransfer: dt(dados) });
    const alvo = linhaDaCena(container, 1).querySelector(".sb-phototable") as HTMLElement;
    fireEvent.drop(alvo, { dataTransfer: dt(dados) });
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));

    const ordem = api.mock.calls
      .map(([p, o], k) => ({ k, p: String(p), m: (o as RequestInit)?.method || "GET" }))
      .filter((c) => c.p.endsWith("/candidates/select") || (c.p.endsWith("/scenes") && c.m === "PUT"));
    expect(ordem[0]?.p).toContain("/candidates/select");
    expect(ordem[1]?.m).toBe("PUT");
  });

  it("com o select falhando, NENHUM PUT /scenes acontece e o erro aparece", async () => {
    const { api, toast, container } = await montar({ falhaSelect: true });
    const card = container.querySelector("#sbIdeasGallery .card[data-id='i4']") as HTMLElement;
    const dados: Record<string, string> = {};
    fireEvent.dragStart(card, { dataTransfer: dt(dados) });
    fireEvent.drop(linhaDaCena(container, 1).querySelector(".sb-phototable") as HTMLElement, {
      dataTransfer: dt(dados),
    });
    await waitFor(() => expect(toast).toHaveBeenCalledWith("falha ao marcar a ideia"));
    expect(putsDeCenas(api).length).toBe(0);
  });
});

describe("Rede de segurança", () => {
  let erro: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    erro = vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => erro.mockRestore());

  it("'Salvar cenas' (#sbSave) continua existindo e enviando o estado completo", async () => {
    const { api, container } = await montar();
    const salvar = container.ownerDocument.querySelector("#sbSave") as HTMLButtonElement;
    expect(salvar).toBeTruthy();
    fireEvent.click(salvar);
    await waitFor(() => expect(putsDeCenas(api).length).toBe(1));
    expect(ultimoPut(api)?.scenes.length).toBe(2);
  });
});
