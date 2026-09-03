// Wave 10 · E2 — `useProgress`/`progressJob` reproduzem o modal de progresso do vanilla.
// Cobertura React equivalente ao que `tests/test_progress_modal.py` guardava por substring no
// `ui.js` (o vanilla segue vivo até a E10; este teste prova o novo componente).
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { progressJob, useProgress } from "./ProgressModal";
import type { ProgressHandle } from "./ProgressModal";

function Harness({ onReady }: { onReady: (h: ProgressHandle) => void }) {
  const [handle, element] = useProgress();
  useEffect(() => {
    onReady(handle);
  }, [handle, onReady]);
  return <>{element}</>;
}

function montar(): ProgressHandle {
  let handle!: ProgressHandle;
  render(<Harness onReady={(h) => (handle = h)} />);
  return handle;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("useProgress", () => {
  it("fechado não renderiza nada", () => {
    montar();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("progress → step → ok: DOM, timer, ✕ e estados dos passos", () => {
    const h = montar();
    act(() => void h.progress({ title: "Gerar", subtitle: "sub" }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveClass("modal", "progress-modal");
    expect(dialog).toHaveAttribute("aria-label", "Gerar");
    expect(dialog.querySelector(".prog-timer")).toHaveTextContent("00:00");
    expect(dialog.querySelector(".prog-steps")).toHaveAttribute("aria-live", "polite");
    // ✕ nasce DESABILITADO enquanto a ação corre.
    expect(dialog.querySelector(".modal-close")).toBeDisabled();

    act(() => void h.step("Consultando o Claude"));
    let steps = dialog.querySelectorAll(".prog-step");
    expect(steps).toHaveLength(1);
    expect(steps[0]).toHaveAttribute("data-state", "active");
    expect(steps[0]?.querySelector(".prog-lbl")).toHaveTextContent("Consultando o Claude");

    act(() => void h.step("Segunda fase"));
    steps = dialog.querySelectorAll(".prog-step");
    expect(steps).toHaveLength(2);
    // o primeiro passou a done (✓); o segundo está ativo.
    expect(steps[0]).toHaveAttribute("data-state", "done");
    expect(steps[0]?.querySelector(".prog-ico")).toHaveTextContent("✓");
    expect(steps[1]).toHaveAttribute("data-state", "active");

    act(() => void h.count(2, 6));
    expect(dialog.querySelector('.prog-step[data-state="active"] .prog-count')).toHaveTextContent("2/6");

    act(() => void h.ok("Pronto"));
    steps = dialog.querySelectorAll(".prog-step");
    // último ativo vira done + passo final "Pronto".
    expect(steps[1]).toHaveAttribute("data-state", "done");
    expect(steps[2]).toHaveTextContent("Pronto");
    // ✕ habilita ao terminar.
    expect(dialog.querySelector(".modal-close")).not.toBeDisabled();
  });

  it("fail marca o passo atual como erro (✗) e mostra a nota", () => {
    const h = montar();
    act(() => void h.progress({ title: "T" }));
    act(() => void h.step("Trabalhando"));
    act(() => void h.fail("deu ruim"));
    const dialog = screen.getByRole("dialog");
    const passo = dialog.querySelector(".prog-step");
    expect(passo).toHaveAttribute("data-state", "error");
    expect(passo?.querySelector(".prog-ico")).toHaveTextContent("✗");
    const nota = dialog.querySelector(".prog-note");
    expect(nota).not.toHaveAttribute("hidden");
    expect(nota?.querySelector(".prog-err")).toHaveTextContent("deu ruim");
    expect(dialog.querySelector(".modal-close")).not.toBeDisabled();
  });

  it("close esconde o modal", () => {
    const h = montar();
    act(() => void h.progress({ title: "T" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    act(() => void h.close());
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("progressJob", () => {
  it("orquestra start → poll do log → ok, resolvendo o job final", async () => {
    let call = 0;
    const fetchMock = vi.fn(async () => ({
      json: async () =>
        call++ === 0
          ? { state: "running", log: ["linha 1"], done: 1, total: 3 }
          : { state: "done", log: ["linha 1", "linha 2"], done: 3, total: 3 },
    }));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const h = montar();
    const start = vi.fn(async () => {});
    const done = vi.fn(async () => {});

    let job: { state?: string } = {};
    await act(async () => {
      job = await progressJob(h, { title: "Job", jobUrl: "/x/job", start, done, ms: 2 });
    });

    expect(start).toHaveBeenCalledOnce();
    expect(done).toHaveBeenCalledOnce();
    expect(job.state).toBe("done");

    const dialog = screen.getByRole("dialog");
    const labels = [...dialog.querySelectorAll(".prog-lbl")].map((n) => n.textContent);
    expect(labels).toContain("Iniciando…");
    expect(labels).toContain("linha 1");
    expect(labels).toContain("linha 2");
    expect(labels).toContain("Pronto");

    // deixa o fechamento automático (setTimeout 900) rodar dentro de act.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 950));
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
