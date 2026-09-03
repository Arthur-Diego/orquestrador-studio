// Substituto Vitest dos asserts de `view.*` de `tests/test_publish_api.py` — Wave 10 · E4.
// Renderiza o componente e assevera DOM + comportamento (recon §7.2), espelhando os casos
// C-PUBLISH-* do oráculo de QA. Preserva textos de aula (ADR-004) e o contrato DOM.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import PublishScreen from "./index";
import { StudioProvider, type StudioCtx } from "../../../../frontend/src/shell/plugin";

const EXPORTS = { files: [{ file: "9x16.mp4" }, { file: "16x9.mp4" }] };
const POST = {
  id: "p1",
  network: "instagram",
  url: "https://www.instagram.com/reel/abc",
  video: "9x16.mp4",
  posted_at: "2026-09-01",
  note: "",
  feedback: "",
};
const PORTFOLIO = { count: 1, community: { posted: true, commented: false, feedback: false, done: 1, total: 3 } };

type ApiFn = (path: string, opts?: RequestInit) => Promise<unknown>;

function routed(over: {
  posts?: unknown[];
  portfolio?: unknown;
  onPost?: (path: string, opts?: RequestInit) => unknown;
} = {}): ApiFn {
  return async (path: string, opts?: RequestInit) => {
    if (opts && opts.method && opts.method !== "GET") {
      return over.onPost ? over.onPost(path, opts) : {};
    }
    if (path.endsWith("/exports")) return EXPORTS;
    if (path.endsWith("/log")) return { posts: over.posts ?? [POST] };
    if (path.endsWith("/portfolio")) return over.portfolio ?? PORTFOLIO;
    return {};
  };
}

function fakeCtx(over: Partial<StudioCtx>, api: ApiFn): StudioCtx {
  return {
    api: api as StudioCtx["api"],
    apiUpload: (async () => ({})) as StudioCtx["apiUpload"],
    toast: vi.fn(),
    pid: () => "pid-1",
    project: () => null,
    files: (p: string) => `/files/pid-1/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
    ...over,
  };
}

function renderPublish(ctx: StudioCtx) {
  return render(
    <StudioProvider value={ctx}>
      <PublishScreen />
    </StudioProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        id: "publish", n: 9, title: "Publicar", aula: "015", status: "todo", progress: 0,
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

describe("PublishScreen (etapa 9 · aula 015)", () => {
  it("C-PUBLISH-01/03/02: select lista os exports, datalist tem a comunidade ABRAhub, data é hoje", async () => {
    renderPublish(fakeCtx({}, routed()));
    await waitFor(() =>
      expect(document.querySelectorAll("#pubVideo option")).toHaveLength(2),
    );
    const opts = [...document.querySelectorAll("#pubVideo option")].map((o) => (o as HTMLOptionElement).value);
    expect(opts).toEqual(["9x16.mp4", "16x9.mp4"]);
    const redes = [...document.querySelectorAll("#pubNetworks option")].map((o) => (o as HTMLOptionElement).value);
    expect(redes).toContain("comunidade ABRAhub");
    expect(document.querySelector("#pubNetwork")).toHaveAttribute("list", "pubNetworks");
    const hoje = new Date();
    const iso = new Date(hoje.getTime() - hoje.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
    expect((document.querySelector("#pubDate") as HTMLInputElement).value).toBe(iso);
  });

  it("C-PUBLISH-07: registrar faz POST /log, limpa os campos e dá toast", async () => {
    const toast = vi.fn();
    let postPath = "";
    let postBody = "";
    const api = routed({
      onPost: (path, opts) => {
        postPath = path;
        postBody = String(opts?.body ?? "");
        return {};
      },
    });
    renderPublish(fakeCtx({ toast }, api));
    await screen.findByRole("button", { name: "Registrar publicação" });
    await userEvent.type(screen.getByPlaceholderText(/instagram\.com\/reel/), "https://x.com/y");
    await userEvent.type(screen.getByPlaceholderText(/nota livre/), "teste");
    await userEvent.click(screen.getByRole("button", { name: "Registrar publicação" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Publicação registrada"));
    expect(postPath).toBe("/api/projects/pid-1/publish/log");
    expect(postBody).toContain("x.com/y");
    expect((document.querySelector("#pubUrl") as HTMLInputElement).value).toBe("");
    expect((document.querySelector("#pubNote") as HTMLInputElement).value).toBe("");
  });

  it("C-PUBLISH-04: erro do backend vira toast e nada é limpo (a validação é do servidor)", async () => {
    const toast = vi.fn();
    const api = routed({
      onPost: () => {
        throw new Error("informe a rede da publicação");
      },
    });
    renderPublish(fakeCtx({ toast }, api));
    await userEvent.type(await screen.findByPlaceholderText(/instagram\.com\/reel/), "https://x.com/y");
    await userEvent.click(screen.getByRole("button", { name: "Registrar publicação" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("informe a rede da publicação"));
    expect((document.querySelector("#pubUrl") as HTMLInputElement).value).toBe("https://x.com/y");
  });

  it("C-PUBLISH-08: cada linha traz chip da rede, URL encurtada e data/arquivo no title", async () => {
    renderPublish(fakeCtx({}, routed()));
    const row = await screen.findByText("instagram");
    const pubRow = row.closest(".pub-row")!;
    expect(pubRow).toHaveAttribute("data-id", "p1");
    expect(pubRow.querySelector("a.url")).toHaveAttribute("href", POST.url);
    expect(pubRow.querySelector("a.url")).toHaveTextContent("instagram.com/reel/abc");
    expect(pubRow.getAttribute("title")).toContain("2026-09-01");
    expect(pubRow.getAttribute("title")).toContain("9x16.mp4");
  });

  it("C-PUBLISH-09/10: anotar feedback — Enter grava; Escape descarta", async () => {
    const toast = vi.fn();
    let feedbackPath = "";
    const api = routed({
      onPost: (path) => {
        if (path.endsWith("/feedback")) feedbackPath = path;
        return {};
      },
    });
    renderPublish(fakeCtx({ toast }, api));
    // Escape: descarta
    await userEvent.click(await screen.findByText("“nota”"));
    let campo = document.querySelector(".pub-row .nt-edit") as HTMLInputElement;
    expect(campo).toBeInTheDocument();
    await userEvent.type(campo, "não deve salvar{Escape}");
    expect(document.querySelector(".pub-row .nt-edit")).toBeNull();
    expect(feedbackPath).toBe("");
    // Enter: grava
    await userEvent.click(screen.getByText("“nota”"));
    campo = document.querySelector(".pub-row .nt-edit") as HTMLInputElement;
    await userEvent.type(campo, "gostaram{Enter}");
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Feedback salvo"));
    expect(feedbackPath).toBe("/api/projects/pid-1/publish/log/p1/feedback");
  });

  it("C-PUBLISH-11/12: 'Remover' pede confirmação — recusar mantém, aceitar faz DELETE", async () => {
    const toast = vi.fn();
    let deletePath = "";
    const api = routed({
      onPost: (path, opts) => {
        if (opts?.method === "DELETE") deletePath = path;
        return {};
      },
    });
    renderPublish(fakeCtx({ toast }, api));
    await screen.findByText("instagram");
    vi.spyOn(window, "confirm").mockReturnValueOnce(false);
    await userEvent.click(screen.getByRole("button", { name: "Remover" }));
    expect(deletePath).toBe("");
    vi.spyOn(window, "confirm").mockReturnValueOnce(true);
    await userEvent.click(screen.getByRole("button", { name: "Remover" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Registro removido"));
    expect(deletePath).toBe("/api/projects/pid-1/publish/log/p1");
  });

  it("C-PUBLISH-13/14: chip conta publicações + comunidade e marcar posta faz POST /community", async () => {
    let comBody = "";
    const api = routed({
      onPost: (path, opts) => {
        if (path.endsWith("/community")) comBody = String(opts?.body ?? "");
        return {};
      },
    });
    renderPublish(fakeCtx({}, api));
    await waitFor(() => expect(document.querySelector("#pubComChip")).toHaveTextContent("1 publicação · comunidade 1/3"));
    const commented = document.querySelector("#pubCommunity input[data-com='commented']") as HTMLInputElement;
    expect(commented.checked).toBe(false);
    await userEvent.click(commented);
    await waitFor(() => expect(comBody).toContain("commented"));
  });

  it("C-PUBLISH-18: campanha sem export mostra o aviso e o empty-state da lista", async () => {
    const api = routed({ posts: [], portfolio: { count: 0, community: { done: 0, total: 3 } } });
    const semExports: ApiFn = async (path, opts) => {
      if (path.endsWith("/exports")) return { files: [] };
      return api(path, opts);
    };
    renderPublish(fakeCtx({}, semExports));
    await waitFor(() =>
      expect(document.querySelector("#pubVideo option")).toHaveTextContent("nenhum export disponível"),
    );
    expect(document.querySelector("#pubLog .empty")).toHaveTextContent("Nenhuma publicação registrada");
  });
});
