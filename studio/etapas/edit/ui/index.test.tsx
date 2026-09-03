// Substituto Vitest dos testes de FONTE DE TELA que liam `edit/view.{html,js}` em
// `tests/test_edit_api.py` (Wave 10 · E9, card [REACT-10]). Aqueles afirmavam substrings sobre o
// fonte; aqui montamos o editor REAL e asseveramos DOM + comportamento (recon §7.2), espelhando os
// casos do oráculo `scripts/qa/cenarios/edit.py`. Preserva as marcas de aula (ADR-004: "Etapa 7 ·
// aula 014", "[extensão]", guia no modal) e o contrato de karaokê da frente C.
//
// O guard de espelho Python↔JS (`WPS`, `CAPTION_MODES`, `HI_COLORS`, `CHUNK_OPTS`) continua em
// pytest, repontado para `studio/etapas/edit/ui/editor.ts` (o porte preserva as linhas exatas).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import EditView from "./index";
import { StudioProvider, type StudioCtx } from "../../../../frontend/src/shell/plugin";

type ApiFn = (path: string, opts?: RequestInit) => Promise<unknown>;

const PID = "pid-1";

/** Timeline semente: um clipe na VÍDEO 1 e uma legenda karaokê com palavras na janela do playhead. */
function timeline() {
  return {
    clips: [
      { id: "c1", scene: "c", shot: "s", take: "t", file: "videos/x.mp4", in: 0, out: 2, speed: 1, blend: true, zoom: 1 },
    ],
    blacks: [],
    music: { file: null, offset: 0 },
    sfx: [],
    fade_out: 1.5,
    loudnorm: true,
    editor: {
      version: 1,
      project: { width: 1920, height: 1080, fps: 30, aspect: "16:9" },
      tracks: [
        {
          id: "t_cap",
          type: "caption",
          name: "LEGENDAS",
          height: 30,
          visible: true,
          locked: false,
          muted: false,
          items: [
            {
              id: "cap1",
              start: 0,
              end: 2,
              mode: "karaoke",
              hi: "#C8F751",
              chunk: 6,
              words: [
                { w: "ola", start_s: 0.0, end_s: 0.5 },
                { w: "mundo", start_s: 0.6, end_s: 1.0 },
              ],
              style: { size: 40, weight: 800, align: "center", color: "#FFFFFF", uppercase: true },
              transform: { x: 0.5, y: 0.82, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 },
              effects: [],
              filters: {},
            },
          ],
        },
      ],
      clip_fx: {},
      transitions: [],
      markers: [],
      ui: { zoom: 1, snap: true },
    },
  };
}

/** `ctx.api` roteada pelos endpoints que o editor consulta no `onProject`/`load`/`save`. */
function apiRoteada(): ApiFn {
  return async (path: string, opts?: RequestInit) => {
    if (path === "/api/edit/ffmpeg") return { available: true };
    if (path.endsWith("/edit/sfx")) return [];
    if (path.endsWith("/edit/media")) return [];
    if (path.endsWith("/music/beats")) return { beats: [] };
    if (path.endsWith("/edit/timeline")) {
      if (opts?.method === "PUT") return { timeline: JSON.parse(String(opts.body)).editor ? timeline() : timeline(), duration: 2 };
      return { timeline: timeline() };
    }
    return {};
  };
}

function fakeCtx(over: Partial<StudioCtx> = {}): StudioCtx {
  return {
    api: apiRoteada() as StudioCtx["api"],
    apiUpload: (async () => ({ added: 0, files: [] })) as StudioCtx["apiUpload"],
    toast: vi.fn(),
    pid: () => PID,
    project: () => ({ id: PID, name: "QA Montagem" }) as unknown as ReturnType<StudioCtx["project"]>,
    files: (p: string) => `/files/${PID}/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
    ...over,
  };
}

function renderEdit(ctx: StudioCtx = fakeCtx()) {
  return render(
    <StudioProvider value={ctx}>
      <EditView />
    </StudioProvider>,
  );
}

/** O `#ved` só é preenchido depois do `load()` async do editor. */
async function esperarEditor(container: HTMLElement) {
  await waitFor(() => expect(container.querySelector(".ved-top")).not.toBeNull());
}

beforeEach(() => {
  // jsdom não implementa play/pause/load de mídia (lança "Not implemented"). O editor cria
  // <video>/<audio> e os toca/pausa; stubá-los deixa o palco montar sem ruído nem exceção.
  const proto = window.HTMLMediaElement.prototype;
  vi.spyOn(proto, "play").mockImplementation(() => Promise.resolve());
  vi.spyOn(proto, "pause").mockImplementation(() => {});
  vi.spyOn(proto, "load").mockImplementation(() => {});
  // O guia (StepGuide da E2) e o `capPost` do editor batem no `fetch` global.
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const u = String(url);
      if (u.includes("/guide/")) {
        return {
          ok: true,
          json: async () => ({
            id: "edit",
            status: "todo",
            title: "Studio de vídeo",
            summary: "Monte o vídeo da aula 014: gelo, ambiência, respiração e impacto.",
            what: "SFX, ambiência, respiração, gelo, impacto — o ritmo da aula 014.",
            next: "Exporte o master quando o corte estiver no ponto.",
            percent: 0,
            missing: [],
            checks: [],
          }),
        } as unknown as Response;
      }
      // capPost: /captions/generate
      return { ok: true, status: 200, json: async () => ({ items: [], word_count: 0 }) } as unknown as Response;
    }),
  );
});

afterEach(() => {
  cleanup();
  // Os modais são imperativos (`helpers.modal` faz `document.body.appendChild`) — o `cleanup` do
  // testing-library só desmonta a árvore React, então um modal aberto num teste (ex.: o guia)
  // sobreviveria e poluiria o `document.querySelector('.modal')` do teste seguinte.
  document.querySelectorAll(".modal-backdrop, .ved-menu").forEach((n) => n.remove());
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  try {
    localStorage.clear();
  } catch {
    /* jsdom sem storage */
  }
});

describe("edit · casca da tela (ADR-004 + contrato de host)", () => {
  it("marca a aula 014 como extensão e preserva o slot do guia e o root .ved#ved", async () => {
    const { container } = renderEdit();
    // marca de aula (a fidelidade ao curso vive no header + no guia — ADR-004/ADR-030)
    expect(container.textContent).toContain("Etapa 7 · aula 014");
    expect(container.textContent).toContain("[extensão]");
    // slot do guia preservado (mesmo escondido pelo editor fixo)
    const guide = container.querySelector("section#guide.guide");
    expect(guide).not.toBeNull();
    // container do editor
    const ved = container.querySelector<HTMLElement>(".ved#ved");
    expect(ved).not.toBeNull();
    // e o editor imperativo se monta dentro dele
    await esperarEditor(container);
    expect(container.querySelector("#edExport")).not.toBeNull();
    expect(container.querySelector("#edRail")).not.toBeNull();
    expect(container.querySelector("#edSave")).not.toBeNull();
  });

  it("não usa cor solta fora do tema (sem 'crimson' no DOM)", async () => {
    const { container } = renderEdit();
    await esperarEditor(container);
    expect(container.innerHTML.toLowerCase()).not.toContain("crimson");
  });
});

describe("edit · guia da aula no modal (C-EDIT-07)", () => {
  it("#edGuide abre o guia da aula 014 em modal", async () => {
    const { container } = renderEdit();
    await esperarEditor(container);
    const btn = container.querySelector<HTMLButtonElement>("#edGuide");
    expect(btn).not.toBeNull();
    await userEvent.click(btn!);
    await waitFor(() => {
      const m = document.querySelector(".modal[role=dialog]");
      expect(m).not.toBeNull();
      expect((m!.querySelector(".modal-head h3")?.textContent || "")).toContain("014");
    });
    // o corpo deixa de mostrar "Carregando…" quando o StepGuide resolve
    await waitFor(() => {
      const body = document.querySelector(".modal[role=dialog] .modal-body")?.textContent || "";
      expect(body.toLowerCase()).not.toContain("carregando");
    });
  });
});

describe("edit · legendas com karaokê (frente C, contrato congelado)", () => {
  it("monta a linha de karaokê por spans (data-cap-karaoke / data-cap-widx) no palco", async () => {
    const { container } = renderEdit();
    await esperarEditor(container);
    // a legenda semente está na janela do playhead (0s): o palco reconcilia e monta os spans
    await waitFor(() => {
      const stage = container.querySelector("#edStage");
      expect(stage?.querySelector("[data-cap-karaoke]")).not.toBeNull();
      expect(stage?.querySelectorAll("[data-cap-widx]").length).toBeGreaterThan(0);
    });
  });

  it("#capGen abre o modal de geração falando com o contrato congelado", async () => {
    const { container } = renderEdit();
    await esperarEditor(container);
    // vai para o painel Legendas pelo rail
    const railCap = container.querySelector<HTMLButtonElement>('#edRail button[data-panel="captions"]');
    expect(railCap).not.toBeNull();
    // botões internos do editor são `onclick` imperativo (DOM gerado por JS) — `fireEvent.click`
    // dispara o handler de forma determinística, sem a sequência de ponteiro do userEvent que
    // corre com o re-render do painel esquerdo.
    fireEvent.click(railCap!);
    const capGen = container.querySelector<HTMLButtonElement>("#capGen");
    expect(capGen).not.toBeNull();
    fireEvent.click(capGen!);
    await waitFor(() => {
      const m = document.querySelector(".modal[role=dialog]");
      expect(m).not.toBeNull();
      // controles do contrato de legendas
      expect(m!.querySelector("#capScript")).not.toBeNull();
      expect(m!.querySelector("#capPreset")).not.toBeNull();
      expect(m!.querySelector("#capHi")).not.toBeNull();
    });
  });
});
