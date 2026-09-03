// Substituto Vitest dos asserts de tela do vanilla (Wave 10 · E5, card [REACT-06]).
//
// Cobre o que os `test_view_*` de `tests/test_animate_api.py` afirmavam sobre `animate/view.{html,js}`
// — inclusive as guardas "removido pela wave 4, não pode voltar" — renderizando o componente React e
// asseverando DOM + comportamento (recon §7.2), com as fidelidades à aula 012 (ADR-004). Os testes de
// backend/API do `test_animate_api.py` NÃO saíram: continuam em pytest.
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { api, apiUpload } from "../../../../frontend/src/api";
import { StudioProvider, type StudioCtx } from "../../../../frontend/src/shell/plugin";
import Animate from "./index";

function jsonResp(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => data,
    text: async () => JSON.stringify(data),
  } as unknown as Response;
}

const PLAN = {
  shots: [
    {
      scene: "cena01", shot: "shot01", prompt: "", image: "videos/cena01/f.jpg",
      next_image: "videos/cena01/f2.jpg", next_in_scene: "shot02", failures: 0,
      takes: [{ id: "take1", file: "videos/cena01/shot01_take1.mp4", liked: true, duration: 5 }],
    },
    { scene: "cena02", shot: "shot01", prompt: "", image: "videos/cena02/f.jpg", next_image: "videos/cena02/f2.jpg", next_in_scene: "shot02", failures: 0, takes: [] },
    { scene: "cena03", shot: "shot01", prompt: "", image: "videos/cena03/f.jpg", failures: 1, takes: [] },
  ],
  model_order: ["kling-2.6", "kling-3.0"],
  scene_model: "kling-2.6",
  transition_model: "kling-3.0",
  mode_tips: { simple: ["dica simples"], start_end: ["dica start/end"] },
  last_frames: [],
  warnings: [],
  model_note: "ordem viva",
};
const CANDS = [
  { id: "c1", thumb: "c1.jpg", source: "upload", model: "kling-2.6", name: "c1.mp4", duration: 4, file: "c1.mp4", prompt: "p" },
];
const GUIA = {
  id: "animate", n: 5, status: "todo", progress: 0, summary: null, next_action: null,
  missing: [], inputs: [], outputs: [], validations: [], next_step: null,
};

function router(url: string): Response {
  const u = url.split("?")[0] ?? url;
  if (u.endsWith("/animate/candidates")) return jsonResp(CANDS);
  if (u.endsWith("/animate/shots")) return jsonResp(PLAN);
  if (u.endsWith("/animate/job")) return jsonResp({ state: "idle" });
  if (u.endsWith("/animate/downloads-folder")) return jsonResp({ folder: "/tmp/dl", exists: true });
  if (u.endsWith("/animate/cost")) return jsonResp({ credits: 5 });
  if (u.includes("/animate/shots/")) return jsonResp({});
  if (u.endsWith("/higgsfield/status")) return jsonResp({ installed: true, logged_in: true, plan: "pro", credits: 100 });
  if (u.includes("/creditos/cost")) return jsonResp({ model: "kling-2.6", credits: 5 });
  if (u.includes("/guide/animate")) return jsonResp(GUIA);
  return jsonResp({});
}

function ctxFalso(): StudioCtx {
  return {
    api,
    apiUpload,
    toast: vi.fn(),
    pid: () => "camp-1",
    project: () => null,
    files: (p) => `/files/camp-1/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
  };
}

function renderTela() {
  return render(
    <StudioProvider value={ctxFalso()}>
      <Animate />
    </StudioProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => Promise.resolve(router(String(url)))),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("animate — contrato de tela (aula 012)", () => {
  it("cabeçalho, guia e os dois painéis do protótipo (plano de takes + importação)", async () => {
    const { container } = renderTela();
    expect(screen.getByText("Etapa 5 · aula 012")).toBeInTheDocument();
    expect(container.querySelector("#guide")).not.toBeNull();
    const pns = [...container.querySelectorAll(".pn")].map((e) => e.textContent);
    expect(pns).toEqual(["01", "02"]);
    expect(container.querySelector("#anShots.rowlist")).not.toBeNull();
    expect(container.querySelector("#anReload")).toHaveTextContent("Recarregar plano");
    expect(container.querySelector(".import-row")).not.toBeNull();
    for (const id of ["anDrop", "anUpload", "anBtnDownloads", "anBtnHistory", "anCandCount", "anHfState"]) {
      expect(container.querySelector(`#${id}`)).not.toBeNull();
    }
    expect(container.textContent).toContain(
      "Dica da aula: enquanto um take gera, dispare os outros shots em paralelo na UI e importe os mp4 depois.",
    );
  });

  it("uma linha por shot na ordem do plano; like, slot vazio e a nota singular '1 falha'", async () => {
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelectorAll("#anShots .shot-row").length).toBe(3));
    const ks = [...container.querySelectorAll(".shot-row")].map((e) => (e as HTMLElement).dataset.k);
    expect(ks).toEqual(["cena01/shot01", "cena02/shot01", "cena03/shot01"]);
    // shot com like: thumb, tile .like, nota 'escolhido'
    const c1 = container.querySelector('.shot-row[data-k="cena01/shot01"]') as HTMLElement;
    expect(c1.querySelector(".thumb img")).not.toBeNull();
    expect((c1.querySelector(".take.an-like") as HTMLElement).className).toContain("like");
    expect(c1.querySelector(".like-lbl")).toHaveTextContent("♥ like");
    expect(c1.querySelector(".takes .note")).toHaveTextContent("escolhido");
    // shot sem take: slot '+ gerar take 1' e a nota da aula
    const c2 = container.querySelector('.shot-row[data-k="cena02/shot01"]') as HTMLElement;
    expect(c2.querySelector(".take.empty.an-gen")).toHaveTextContent("gerar take 1");
    expect(c2.querySelector(".takes .note")).toHaveTextContent("sem take ainda");
    // nota singular: 1 falha (não 'falhas')
    const c3 = container.querySelector('.shot-row[data-k="cena03/shot01"]') as HTMLElement;
    expect(c3.querySelector(".takes .note")).toHaveTextContent("1 falha — na 3ª, troque de modelo");
  });

  it("o slot '+ gerar take N' abre o modal com todos os controles e a galeria de candidatos", async () => {
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelector('.shot-row[data-k="cena02/shot01"] .an-gen')).not.toBeNull());
    // a galeria de candidatos só existe DENTRO do modal (guarda: `#anGallery` não vem no view.html)
    expect(container.querySelector("#anGallery")).toBeNull();
    fireEvent.click(container.querySelector('.shot-row[data-k="cena02/shot01"] .an-gen') as Element);
    const modal = await screen.findByRole("dialog");
    expect(modal.querySelector(".modal-head h3")).toHaveTextContent("Gerar take 1 · cena02 · shot01");
    for (const cls of [".an-mode", ".an-duration", ".an-camera", ".an-action", ".an-slow", ".an-black", ".an-suggest", ".an-model", ".an-count", "#anGallery", ".an-cli"]) {
      expect(modal.querySelector(cls)).not.toBeNull();
    }
    // select de modelo com a ordem viva; chip do CLI com "CLI"
    const opts = [...modal.querySelectorAll(".an-model option")].map((o) => (o as HTMLOptionElement).value);
    expect(opts).toEqual(["kling-2.6", "kling-3.0"]);
    const chips = [...modal.querySelectorAll(".modal-body span.chip")];
    expect(chips[chips.length - 1]?.textContent).toContain("CLI");
    // 'Atribuir selecionado' começa desabilitado (nada marcado na galeria)
    expect((modal.querySelector(".modal-actions button.ghost") as HTMLButtonElement).disabled).toBe(true);
  });

  it("modo start/end revela o end frame com o próximo shot da cena, as dicas e o modelo de transição", async () => {
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelector('.shot-row[data-k="cena02/shot01"] .an-gen')).not.toBeNull());
    fireEvent.click(container.querySelector('.shot-row[data-k="cena02/shot01"] .an-gen') as Element);
    const modal = await screen.findByRole("dialog");
    const endrow = modal.querySelector(".an-endrow") as HTMLElement;
    expect(endrow.hidden).toBe(true);
    fireEvent.change(modal.querySelector(".an-mode") as Element, { target: { value: "start_end" } });
    await waitFor(() => expect((modal.querySelector(".an-endrow") as HTMLElement).hidden).toBe(false));
    expect(modal.querySelector(".an-end")).toHaveTextContent("shot02");
    expect(modal.querySelectorAll(".an-tips li").length).toBeGreaterThan(0);
    // ADR-023: a transição usa o transition_model
    expect((modal.querySelector(".an-model") as HTMLSelectElement).value).toBe("kling-3.0");
  });

  it("o chip do CLI fica oculto com o CLI logado e o contador reflete /candidates", async () => {
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelector("#anCandCount")).toHaveTextContent("1 vídeos"));
    await waitFor(() => expect((container.querySelector("#anHfState") as HTMLElement).hidden).toBe(true));
  });

  it("guarda: o que a wave 4 tirou da tela não voltou", () => {
    const { container } = renderTela();
    for (const id of ["anReady", "anModelNote", "anWarnings", "anDlFolder", "anDlMinutes", "anParallel"]) {
      expect(container.querySelector(`#${id}`)).toBeNull();
    }
    // `details.lesson` só na etapa 1 (refs), não na animação
    expect(container.querySelector("details.lesson")).toBeNull();
  });

  it("'Gerar via CLI' passa pelo gate de custo (confirmCost) ANTES de qualquer geração paga (FDD §2B)", async () => {
    // Substituto do `test_confirm_cost_still_precedes_paid_generations` de `test_progress_modal.py`
    // (que lia `animate/view.js`): a geração paga abre o modal de custo (aula 008) e o de progresso
    // só existiria DEPOIS da confirmação — aqui provamos que ele ainda não apareceu.
    const { container } = renderTela();
    await waitFor(() => expect(container.querySelector('.shot-row[data-k="cena02/shot01"] .an-gen')).not.toBeNull());
    fireEvent.click(container.querySelector('.shot-row[data-k="cena02/shot01"] .an-gen') as Element);
    const modal = await screen.findByRole("dialog");
    fireEvent.click(modal.querySelector(".modal-actions button.primary") as Element);
    await waitFor(() => {
      const subs = [...document.querySelectorAll(".modal .sub")].map((e) => e.textContent || "");
      expect(subs.some((t) => /Custo antes de gerar/.test(t))).toBe(true);
    });
    expect(document.querySelector(".modal.progress-modal")).toBeNull();
  });
});
