// Barramento de mudanças do shell — UT-10…UT-14 do `_tests.md` (Wave 11 · F03, card #87).
//
// Temporizadores FALSOS em toda a suíte: a janela de debounce é de 400 ms e nenhum teste pode
// depender de `setTimeout` real (ADR-008 — testes rápidos, sem rede e sem navegador).
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEBOUNCE_GUIA_MS } from "../api/guide-sync";
import { emitStudioChange, useStudioChange } from "./events";
import type { MudancaDoStudio } from "./events";

/** Atalho: o evento que o `ChatDock` publica a partir de um `state_changed` do WebSocket. */
function mudanca(pid: string | null, step: string, tool = "refs_search"): MudancaDoStudio {
  return { pid, step, scope: "job", tool };
}

describe("useStudioChange — filtro por step e por pid (UT-10)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("chama cb uma vez para o próprio step e o próprio pid", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("refs", cb, { pid: "p1" }));

    emitStudioChange(mudanca("p1", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith(mudanca("p1", "refs"));
  });

  it("não chama para evento de OUTRA campanha", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("refs", cb, { pid: "p1" }));

    emitStudioChange(mudanca("p2", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).not.toHaveBeenCalled();
  });

  it("não chama para evento de OUTRA etapa", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("refs", cb, { pid: "p1" }));

    emitStudioChange(mudanca("p1", "base"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).not.toHaveBeenCalled();
  });

  it("assinante sem pid declarado (área global) aceita qualquer campanha", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("characters", cb));

    emitStudioChange({ pid: "p9", step: "characters", scope: "selection", tool: "character_apply" });
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("assinante que declarou pid null (tela sem campanha) ignora evento de campanha", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("refs", cb, { pid: null }));

    emitStudioChange(mudanca("p1", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).not.toHaveBeenCalled();
  });
});

describe("useStudioChange — debounce de 400 ms, o último vence (UT-11)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("três eventos do mesmo (pid, step) na janela viram UMA chamada, com o último", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("base", cb, { pid: "p1" }));

    emitStudioChange({ pid: "p1", step: "base", scope: "job", tool: "base_generate" });
    vi.advanceTimersByTime(100);
    emitStudioChange({ pid: "p1", step: "base", scope: "candidates", tool: "job_wait" });
    vi.advanceTimersByTime(100);
    emitStudioChange({ pid: "p1", step: "base", scope: "selection", tool: "base_pick" });

    // Ainda dentro da janela do terceiro evento: nada rodou.
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS - 1);
    expect(cb).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith({ pid: "p1", step: "base", scope: "selection", tool: "base_pick" });
  });

  it("opts.debounceMs sobrescreve a janela default", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("mood", cb, { pid: "p1", debounceMs: 50 }));

    emitStudioChange(mudanca("p1", "mood", "mood_generate"));
    vi.advanceTimersByTime(50);

    expect(cb).toHaveBeenCalledTimes(1);
  });
});

describe("useStudioChange — mudança global chega a todos (UT-12)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("evento com pid null chega a um assinante que declarou pid p1", () => {
    const cb = vi.fn();
    renderHook(() => useStudioChange("characters", cb, { pid: "p1" }));

    const global: MudancaDoStudio = {
      pid: null,
      step: "characters",
      scope: "candidates",
      tool: "character_wait",
    };
    emitStudioChange(global);
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith(global);
  });
});

describe("useStudioChange — unmount cancela o timer pendente (UT-13)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("desmontar antes do fim do debounce não chama cb", () => {
    const cb = vi.fn();
    const { unmount } = renderHook(() => useStudioChange("refs", cb, { pid: "p1" }));

    emitStudioChange(mudanca("p1", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS - 1);
    unmount();
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS * 10);

    expect(cb).not.toHaveBeenCalled();
  });

  it("depois do unmount o assinante sai do barramento e não recebe mais nada", () => {
    const cb = vi.fn();
    const { unmount } = renderHook(() => useStudioChange("refs", cb, { pid: "p1" }));
    unmount();

    emitStudioChange(mudanca("p1", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(cb).not.toHaveBeenCalled();
  });
});

describe("emitStudioChange — assinante que lança não cala os demais (UT-14)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("o throw de um assinante não impede o outro assinante do mesmo step de receber", () => {
    const erro = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const explode = vi.fn(() => {
      throw new Error("tela quebrada");
    });
    const ok = vi.fn();
    renderHook(() => useStudioChange("refs", explode, { pid: "p1" }));
    renderHook(() => useStudioChange("refs", ok, { pid: "p1" }));

    emitStudioChange(mudanca("p1", "refs"));
    vi.advanceTimersByTime(DEBOUNCE_GUIA_MS);

    expect(explode).toHaveBeenCalledTimes(1);
    expect(ok).toHaveBeenCalledTimes(1);
    // O erro não é engolido em silêncio: deixa rastro no console de desenvolvimento.
    expect(erro).toHaveBeenCalled();
  });
});
