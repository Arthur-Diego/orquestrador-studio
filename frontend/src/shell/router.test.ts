import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { parseHash, useHashRouter } from "./router";
import { PROJECTS, STEPS } from "./test-utils";

describe("parseHash — mesma gramática do vanilla (recon §1.4)", () => {
  it("#/<pid>/<view>", () => {
    expect(parseHash("#/campanha-a/mood")).toEqual({ pid: "campanha-a", view: "mood" });
  });
  it("#/<pid> → view default overview", () => {
    expect(parseHash("#/campanha-a")).toEqual({ pid: "campanha-a", view: "overview" });
  });
  it("áreas globais são <pid> reservado", () => {
    expect(parseHash("#/moodboards")).toEqual({ pid: "moodboards", view: "overview" });
    expect(parseHash("#/moodboards/mb1")).toEqual({ pid: "moodboards", view: "mb1" });
    expect(parseHash("#/creditos")).toEqual({ pid: "creditos", view: "overview" });
  });
  it("hash vazio ou fora da gramática → null", () => {
    expect(parseHash("")).toBeNull();
    expect(parseHash("#")).toBeNull();
    expect(parseHash("#/a/b/c")).toBeNull();
  });
  it("decodifica componentes", () => {
    expect(parseHash("#/camp%20a/over")).toEqual({ pid: "camp a", view: "over" });
  });
});

describe("useHashRouter — resolução e fallbacks (C-SHELL-12/13)", () => {
  beforeEach(() => {
    localStorage.clear();
    history.replaceState(null, "", "#");
  });
  afterEach(() => {
    history.replaceState(null, "", "#");
  });

  it("hash vazio cai na 1ª campanha, view overview", async () => {
    const { result } = renderHook(() => useHashRouter(PROJECTS, STEPS));
    await waitFor(() => expect(result.current.pid).toBe("campanha-a"));
    expect(result.current.view).toBe("overview");
    expect(result.current.area).toBe("campaign");
  });

  it("pid inexistente cai na 1ª campanha (C-SHELL-12)", async () => {
    history.replaceState(null, "", "#/nao-existe/overview");
    const { result } = renderHook(() => useHashRouter(PROJECTS, STEPS));
    await waitFor(() => expect(result.current.pid).toBe("campanha-a"));
    expect(location.hash).toBe("#/campanha-a/overview");
  });

  it("etapa inexistente cai em overview (C-SHELL-13)", async () => {
    history.replaceState(null, "", "#/campanha-a/etapa-que-nao-existe");
    const { result } = renderHook(() => useHashRouter(PROJECTS, STEPS));
    await waitFor(() => expect(result.current.view).toBe("overview"));
    expect(location.hash).toBe("#/campanha-a/overview");
  });

  it("etapa ready é preservada", async () => {
    history.replaceState(null, "", "#/campanha-a/mood");
    const { result } = renderHook(() => useHashRouter(PROJECTS, STEPS));
    await waitFor(() => expect(result.current.view).toBe("mood"));
  });

  it("#/moodboards vira área moodboards, com sub", async () => {
    history.replaceState(null, "", "#/moodboards/mb7");
    const { result } = renderHook(() => useHashRouter(PROJECTS, STEPS));
    await waitFor(() => expect(result.current.area).toBe("moodboards"));
    expect(result.current.sub).toBe("mb7");
    expect(result.current.view).toBeNull();
  });

  it("#/creditos vira área creditos", async () => {
    history.replaceState(null, "", "#/creditos");
    const { result } = renderHook(() => useHashRouter(PROJECTS, STEPS));
    await waitFor(() => expect(result.current.area).toBe("creditos"));
  });
});
