// Substituto Vitest dos asserts de `view.*` de `tests/test_music_api.py` — Wave 10 · E4.
// Renderiza o componente e assevera DOM + comportamento (recon §7.2), espelhando os casos
// C-MUSIC-* do oráculo. O player de áudio (C-MUSIC-10/11) depende de mídia real e fica com o
// cenário de QA. Textos de aula preservados (ADR-004); DOM idêntico.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import MusicScreen from "./index";
import { StudioProvider, type StudioCtx } from "../../../../frontend/src/shell/plugin";

type ApiFn = (path: string, opts?: RequestInit) => Promise<unknown>;

const STORY = { ffmpeg: true, clips: 3, video: "audio/rough_sequence.mp4", warning: "", check: null };
const CANDS = [
  { id: "c1", file: "faixa-a.mp3", name: "Faixa A", duration: 95, bpm: 120, selected: true },
  { id: "c2", file: "faixa-b.mp3", name: "Faixa B", duration: 60, selected: false },
];
const BEATS = { duration: 90, beats: [1, 2, 3, 4], impacts: [2, 4] };

function routed(over: {
  story?: unknown;
  cands?: unknown[];
  beats?: unknown | "404";
  onPost?: (path: string, opts?: RequestInit) => unknown;
} = {}): ApiFn {
  return async (path: string, opts?: RequestInit) => {
    if (opts && opts.method && opts.method !== "GET") return over.onPost ? over.onPost(path, opts) : {};
    if (path.endsWith("/story")) return over.story ?? STORY;
    if (path.endsWith("/candidates")) return over.cands ?? CANDS;
    if (path.endsWith("/beats")) {
      if (over.beats === "404") throw new Error("404");
      return over.beats ?? BEATS;
    }
    return {};
  };
}

function fakeCtx(over: Partial<StudioCtx>, api: ApiFn): StudioCtx {
  return {
    api: api as StudioCtx["api"],
    apiUpload: (async () => ({ added: 1 })) as StudioCtx["apiUpload"],
    toast: vi.fn(),
    pid: () => "pid-1",
    project: () => null,
    files: (p: string) => `/files/pid-1/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
    ...over,
  };
}

function renderMusic(ctx: StudioCtx) {
  return render(
    <StudioProvider value={ctx}>
      <MusicScreen />
    </StudioProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        id: "music", n: 6, title: "Trilha", aula: "013", status: "in_progress", progress: 0.5,
        what: "", checklist: [], inputs: [], outputs: [], validations: [], missing: [],
        summary: null, summary_kind: null, next_action: null, next_step: null,
      }),
    })) as unknown as typeof fetch,
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("MusicScreen (etapa 6 · aula 013)", () => {
  it("C-MUSIC-01: painel 01 com clipes+ffmpeg habilita o botão, esconde o chip e mostra o vídeo", async () => {
    renderMusic(fakeCtx({}, routed()));
    await waitFor(() => expect(screen.getByRole("button", { name: "Montar sequência bruta" })).toBeEnabled());
    expect(document.querySelector("#musStoryChip")).toHaveClass("hidden");
    expect(document.querySelector("#musStoryVideo")).not.toHaveClass("hidden");
    expect(document.querySelector("#musStoryPlay")).toHaveClass("hidden");
  });

  it("C-MUSIC-16: sem takes, o botão desabilita e o chip avisa; o placeholder ▶ aparece", async () => {
    const story = { ffmpeg: true, clips: 0, video: null, warning: "sem takes com like para montar a sequência", check: null };
    renderMusic(fakeCtx({}, routed({ story, cands: [], beats: "404" })));
    await waitFor(() => expect(screen.getByRole("button", { name: "Montar sequência bruta" })).toBeDisabled());
    expect(document.querySelector("#musStoryChip")).not.toHaveClass("hidden");
    expect(document.querySelector("#musStoryChip")).toHaveTextContent("sem takes");
    expect(document.querySelector("#musStoryPlay")).not.toHaveClass("hidden");
  });

  it("C-MUSIC-03: 'Salvar decisão' sem responder avisa e não faz POST", async () => {
    const toast = vi.fn();
    let posted = false;
    renderMusic(fakeCtx({ toast }, routed({ story: { ...STORY, check: null }, onPost: () => ((posted = true), {}) })));
    await userEvent.click(await screen.findByRole("button", { name: "Salvar decisão" }));
    expect(toast).toHaveBeenCalledWith("Responda se a história fecha ou se falta cena.");
    expect(posted).toBe(false);
  });

  it("C-MUSIC-04: 'A história fecha' faz POST /story/check com closed=true e dá toast", async () => {
    const toast = vi.fn();
    let body = "";
    renderMusic(
      fakeCtx({ toast }, routed({ story: { ...STORY, check: null }, onPost: (p, o) => {
        if (p.endsWith("/story/check")) body = String(o?.body ?? "");
        return {};
      } })),
    );
    await userEvent.click(await screen.findByLabelText("A história fecha"));
    await userEvent.click(screen.getByRole("button", { name: "Salvar decisão" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Decisão registrada"));
    expect(body).toContain('"closed":true');
  });

  it("C-MUSIC-06/07: chip conta candidatas (for=musUpload, accept=audio/*) e a linha traz nome e meta", async () => {
    renderMusic(fakeCtx({}, routed()));
    await waitFor(() => expect(document.querySelectorAll("#musList .track-row")).toHaveLength(2));
    expect(document.querySelector("#musCounts")).toHaveTextContent("2 candidatas");
    expect(document.querySelector("#musCounts")).toHaveAttribute("for", "musUpload");
    expect(document.querySelector("#musUpload")).toHaveAttribute("accept", "audio/*");
    const row = document.querySelector(".track-row[data-id='c1']")!;
    expect(row.querySelector(".nm")).toHaveTextContent("Faixa A");
    expect(row.querySelector(".mt")).toHaveTextContent("120 bpm");
  });

  it("C-MUSIC-12: a candidata escolhida mostra o chip 'escolhida' e perde o botão 'Escolher'", async () => {
    renderMusic(fakeCtx({}, routed()));
    const escolhida = await screen.findByText("Faixa A");
    const row = escolhida.closest(".track-row")!;
    expect(row).toHaveClass("sel");
    expect(row.querySelector(".chip.ok")).toHaveTextContent("escolhida");
    expect(row.querySelector("button.pick")).toBeNull();
    // a não-escolhida oferece 'Escolher' e dispara POST /music/select
    let selectPath = "";
    cleanup();
    renderMusic(
      fakeCtx({}, routed({ onPost: (p) => ((selectPath = p), { beats: BEATS }) })),
    );
    await userEvent.click((await screen.findAllByRole("button", { name: "Escolher" }))[0]!);
    await waitFor(() => expect(selectPath).toBe("/api/projects/pid-1/music/select"));
  });

  it("C-MUSIC-13: painel 03 mostra 'N batidas · M impactos' e uma barra por batida", async () => {
    renderMusic(fakeCtx({}, routed()));
    await waitFor(() => expect(document.querySelector("#musBeatsChip")).toHaveTextContent("4 batidas · 2 impactos"));
    expect(document.querySelector("#musBeatsChip")).toHaveClass("ok");
    expect(document.querySelectorAll("#musRuler .beats i")).toHaveLength(4);
    expect(document.querySelectorAll("#musRuler .beats i.imp")).toHaveLength(2);
  });

  it("C-MUSIC-15: campanha sem trilha — chip 'nenhuma trilha escolhida', régua vazia e dropzone", async () => {
    const story = { ffmpeg: true, clips: 0, video: null, warning: "", check: null };
    renderMusic(fakeCtx({}, routed({ story, cands: [], beats: "404" })));
    await waitFor(() => expect(document.querySelector("#musBeatsChip")).toHaveTextContent("nenhuma trilha escolhida"));
    expect(document.querySelectorAll("#musRuler .beats i")).toHaveLength(0);
    expect(document.querySelector("#musList label.drop")).toHaveTextContent("Arraste músicas aqui");
    expect(document.querySelector("#musCounts")).toHaveTextContent("0 candidatas");
  });

  it("C-MUSIC-18: trilha escolhida sem beats — o chip avisa em vez de fingir batidas", async () => {
    renderMusic(fakeCtx({}, routed({ beats: "404" })));
    await waitFor(() =>
      expect(document.querySelector("#musBeatsChip")).toHaveTextContent("trilha escolhida, sem batidas detectadas"),
    );
    expect(document.querySelector("#musBeatsChip")).toHaveClass("warn");
    expect(document.querySelectorAll("#musRuler .beats i")).toHaveLength(0);
  });
});
