import { afterEach, describe, expect, it, vi } from "vitest";

import { Bridge } from "./bridge";
import { PROJECTS, STEPS } from "./test-utils";

function novaPonte(over: Partial<ConstructorParameters<typeof Bridge>[0]> = {}) {
  const deps = {
    getPid: () => "campanha-a",
    getProject: () => PROJECTS[0]!,
    getSteps: () => STEPS,
    toast: vi.fn(),
    navigate: vi.fn(),
    onGuide: vi.fn(),
    confirmResetStep: vi.fn(),
    ...over,
  };
  return { bridge: new Bridge(deps), deps };
}

afterEach(() => {
  // limpa os <script> vanilla que o construtor injeta (jsdom não os executa)
  document.querySelectorAll("script[data-bridge]").forEach((s) => s.remove());
  delete (window as { Studio?: unknown }).Studio;
});

describe("Bridge — o contrato window.Studio para as telas vanilla (recon §1.2)", () => {
  it("instala register/go/onGuide/ctx/steps em window.Studio (papel do app.js)", () => {
    novaPonte();
    const S = window.Studio!;
    expect(typeof S.register).toBe("function");
    expect(typeof S.go).toBe("function");
    expect(typeof S.onGuide).toBe("function");
    expect(S.ctx).toBeTruthy();
  });

  it("ctx expõe $, api, toast, pid(), project(), files() como o vanilla", () => {
    const { deps } = novaPonte();
    const ctx = window.Studio!.ctx!;
    expect(ctx.pid()).toBe("campanha-a");
    expect(ctx.project()).toBe(PROJECTS[0]);
    expect(ctx.files("mood/x.jpg")).toBe("/files/campanha-a/mood/x.jpg");
    ctx.toast("oi");
    expect(deps.toast).toHaveBeenCalledWith("oi");
    expect(typeof ctx.api).toBe("function");
    expect(typeof ctx.$).toBe("function");
  });

  it("Studio.go só navega para alvo válido (overview, fábrica registrada ou etapa ready)", () => {
    const { deps } = novaPonte();
    const S = window.Studio!;
    S.go!("overview");
    S.go!("refs"); // ready em STEPS
    S.go!("prospect"); // soon → não navega
    S.go!("inexistente");
    expect(deps.navigate).toHaveBeenCalledTimes(2);
    expect(deps.navigate).toHaveBeenNthCalledWith(1, "overview");
    expect(deps.navigate).toHaveBeenNthCalledWith(2, "refs");
  });

  it("uma fábrica registrada torna a etapa navegável por Studio.go", () => {
    const { deps } = novaPonte();
    const S = window.Studio!;
    S.register!("mood", () => ({ init: vi.fn() }));
    S.go!("mood");
    expect(deps.navigate).toHaveBeenCalledWith("mood");
  });

  it("onGuide encaminha para o guide-sync do shell (ADR-010 a)", () => {
    const { deps } = novaPonte();
    const g = { id: "mood", status: "in_progress" };
    window.Studio!.onGuide!("mood", g as never);
    expect(deps.onGuide).toHaveBeenCalledWith("mood", g);
  });
});
