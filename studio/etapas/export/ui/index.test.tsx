// Substituto Vitest dos asserts de `view.*` de `tests/test_export_api.py`/`test_export_guide.py`
// — Wave 10 · E4. Renderiza o componente e assevera DOM + comportamento (recon §7.2), espelhando
// os casos C-EXPORT-* do oráculo. O fluxo de JOB (render via ProgressModal) é coberto pelo cenário
// de QA (C-EXPORT-07/09); aqui cobrimos grade, chips, QA e estados. Textos de aula preservados.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ExportScreen from "./index";
import { StudioProvider, type StudioCtx } from "../../../../frontend/src/shell/plugin";

type ApiFn = (path: string, opts?: RequestInit) => Promise<unknown>;

const STATUS_CHEIO = {
  ffmpeg: true,
  master: { exists: true, width: 1080, height: 1920, duration: 12.3, has_audio: true },
  outputs: {
    "16x9": { file: "export/16x9.mp4", width: 1920, height: 1080, duration: 12.3 },
    "9x16": undefined,
    "1x1": undefined,
    qa_report: { checks: [{ kind: "ok", text: "áudio presente" }, { kind: "warn", text: "1:1 não renderizado" }] },
  },
  previews: {},
  job: { state: "idle" },
};

const STATUS_VAZIO = {
  ffmpeg: true,
  master: { exists: false },
  outputs: {},
  previews: {},
  job: { state: "idle" },
};

function routed(status: unknown, onPost?: (path: string, opts?: RequestInit) => unknown): ApiFn {
  return async (path: string, opts?: RequestInit) => {
    if (opts && opts.method && opts.method !== "GET") return onPost ? onPost(path, opts) : {};
    if (path.endsWith("/status")) return status;
    if (path.endsWith("/job")) return { state: "idle" };
    return {};
  };
}

function fakeCtx(over: Partial<StudioCtx>, api: ApiFn): StudioCtx {
  return {
    api: api as StudioCtx["api"],
    apiUpload: (async () => ({})) as StudioCtx["apiUpload"],
    toast: vi.fn(),
    pid: () => "pid-1",
    project: () => ({ aspect_ratio: "9:16" }) as never,
    files: (p: string) => `/files/pid-1/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
    ...over,
  };
}

function renderExport(ctx: StudioCtx) {
  return render(
    <StudioProvider value={ctx}>
      <ExportScreen />
    </StudioProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        id: "export", n: 8, title: "Export", aula: "014", status: "in_progress", progress: 0.3,
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

describe("ExportScreen (etapa 8 · aula 014)", () => {
  it("C-EXPORT-01: um card por formato, com proporção, destino e chip conforme o status", async () => {
    renderExport(fakeCtx({}, routed(STATUS_CHEIO)));
    await waitFor(() => expect(document.querySelectorAll("#expFormats .fmt-card")).toHaveLength(3));
    const cards = [...document.querySelectorAll("#expFormats .fmt-card")].map((c) => ({
      fmt: c.getAttribute("data-fmt"),
      ratio: c.querySelector(".ratio")?.textContent,
      dest: c.querySelector(".dest")?.textContent,
      chip: c.querySelector(".chip.sm")?.textContent,
    }));
    expect(cards).toEqual([
      { fmt: "16x9", ratio: "16:9", dest: "YouTube", chip: "renderizado" },
      { fmt: "9x16", ratio: "9:16", dest: "Reels · TikTok", chip: "a renderizar" },
      { fmt: "1x1", ratio: "1:1", dest: "feed · opcional", chip: "a renderizar" },
    ]);
  });

  it("C-EXPORT-02/03: formato renderizado mostra 'Ver arquivo' com medidas e abre /files/... em nova aba", async () => {
    const open = vi.fn();
    vi.stubGlobal("open", open);
    renderExport(fakeCtx({}, routed(STATUS_CHEIO)));
    const btn = await screen.findByRole("button", { name: "Ver arquivo" });
    expect(btn.getAttribute("title")).toContain("export/16x9.mp4");
    expect(btn.getAttribute("title")).toContain("1920x1080");
    await userEvent.click(btn);
    expect(open).toHaveBeenCalledWith("/files/pid-1/export/16x9.mp4", "_blank", "noopener");
  });

  it("C-EXPORT-04/05: com ffmpeg e master, 'Renderizar todos' habilita e os chips de falta somem", async () => {
    renderExport(fakeCtx({}, routed(STATUS_CHEIO)));
    const btn = await screen.findByRole("button", { name: "Renderizar todos" });
    expect(btn).toBeEnabled();
    expect(btn.getAttribute("title")).toContain("1080x1920");
    expect(btn.getAttribute("title")).toContain("master.mp4");
    expect(document.querySelector("#expFfmpeg")).toHaveClass("hidden");
    expect(document.querySelector("#expMaster")).toHaveClass("hidden");
  });

  it("C-EXPORT-11/13: 'Gerar QA' desenha o grid com a marca de cada tipo e dá toast", async () => {
    const toast = vi.fn();
    const api = routed(STATUS_CHEIO, () => ({ checks: STATUS_CHEIO.outputs.qa_report.checks, blocking: false }));
    renderExport(fakeCtx({ toast }, api));
    await waitFor(() => expect(document.querySelectorAll("#expQa .checks.qa .it")).toHaveLength(2));
    const marcas = [...document.querySelectorAll("#expQa .it .mark")].map((m) => m.textContent);
    expect(marcas).toEqual(["✓", "!"]);
    await userEvent.click(screen.getByRole("button", { name: "Gerar QA" }));
    await waitFor(() => expect(toast).toHaveBeenCalled());
    expect((toast.mock.calls.at(-1) as string[])[0]).toContain("QA gerado");
  });

  it("C-EXPORT-10: sem job em erro, #expLog e a barra de progresso ficam ocultos", async () => {
    renderExport(fakeCtx({}, routed(STATUS_CHEIO)));
    await screen.findByRole("button", { name: "Renderizar todos" });
    expect(document.querySelector("#expLog")).toHaveClass("hidden");
    expect(document.querySelector("#expProgress")).toHaveClass("hidden");
  });

  it("C-EXPORT-14/16: sem master, o chip aponta a etapa 7 e todos os comandos ficam desabilitados", async () => {
    renderExport(fakeCtx({}, routed(STATUS_VAZIO)));
    await waitFor(() => expect(document.querySelector("#expMaster")).not.toHaveClass("hidden"));
    expect(document.querySelector("#expMaster")).toHaveTextContent("etapa 7");
    expect(screen.getByRole("button", { name: "Renderizar todos" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Gerar QA" })).toBeDisabled();
    const renders = document.querySelectorAll("#expFormats button.render");
    expect(renders).toHaveLength(3);
    expect([...renders].every((b) => (b as HTMLButtonElement).disabled)).toBe(true);
    expect(screen.getByRole("button", { name: "Renderizar todos" }).getAttribute("title")).toContain("etapa 7");
  });
});
