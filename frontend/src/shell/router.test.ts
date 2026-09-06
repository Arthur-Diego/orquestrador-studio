import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

// UT-21…UT-27 do `_tests.md` (Wave 11 · F10, card #88): `navigate` passou a MONTAR as áreas globais
// que o efeito de resolução já entendia. A não-regressão dos alvos de campanha é parte do contrato.
describe("navigate — áreas globais montáveis (UT-21…UT-27)", () => {
  beforeEach(() => {
    localStorage.clear();
    history.replaceState(null, "", "#/campanha-a/overview");
  });
  afterEach(() => {
    history.replaceState(null, "", "#");
  });

  /** Roteador já bootado na campanha A (ou sem campanha nenhuma, para o caso de `pidRef` nulo). */
  async function roteador(projetos = PROJECTS) {
    const { result } = renderHook(() => useHashRouter(projetos, STEPS));
    await waitFor(() => expect(result.current.pid).toBe(projetos.length ? "campanha-a" : null));
    return result;
  }

  it("UT-21 navigate('moodboards/mb123') → #/moodboards/mb123", async () => {
    const r = await roteador();
    act(() => r.current.navigate("moodboards/mb123"));
    expect(location.hash).toBe("#/moodboards/mb123");
  });

  it("UT-22 as três áreas globais e a sub-tela de characters", async () => {
    const casos: [string, string][] = [
      ["moodboards", "#/moodboards"],
      ["creditos", "#/creditos"],
      ["characters", "#/characters"],
      ["characters/c1", "#/characters/c1"],
    ];
    for (const [alvo, esperado] of casos) {
      history.replaceState(null, "", "#/campanha-a/overview");
      const r = await roteador();
      act(() => r.current.navigate(alvo));
      expect(location.hash).toBe(esperado);
    }
  });

  it("UT-23 navigate('creditos/qualquer-coisa') → #/creditos (a área não tem sub-tela)", async () => {
    const r = await roteador();
    act(() => r.current.navigate("creditos/qualquer-coisa"));
    expect(location.hash).toBe("#/creditos");
  });

  it("UT-24 alvos de campanha continuam idênticos", async () => {
    const r = await roteador();
    act(() => r.current.navigate("mood"));
    expect(location.hash).toBe("#/campanha-a/mood");
    act(() => r.current.navigate("overview"));
    expect(location.hash).toBe("#/campanha-a/overview");
    // E `opts.pid` continua sobrepondo a campanha corrente.
    act(() => r.current.navigate("base", { pid: "campanha-b" }));
    expect(location.hash).toBe("#/campanha-b/base");
  });

  it("UT-24 alvo de campanha sem campanha nenhuma continua não mexendo no hash", async () => {
    history.replaceState(null, "", "#");
    const antes = location.hash; // jsdom devolve "" para um `#` pelado
    const r = await roteador([]);
    act(() => r.current.navigate("mood"));
    expect(location.hash).toBe(antes);
  });

  it("UT-25 área global navega mesmo com pidRef nulo", async () => {
    history.replaceState(null, "", "#");
    const r = await roteador([]);
    act(() => r.current.navigate("moodboards"));
    expect(location.hash).toBe("#/moodboards");
  });

  it("UT-26 replace usa history.replaceState e não empurra entrada nova", async () => {
    const r = await roteador();
    const spy = vi.spyOn(history, "replaceState");
    const antes = history.length;

    act(() => r.current.navigate("creditos", { replace: true }));

    expect(location.hash).toBe("#/creditos");
    expect(spy).toHaveBeenCalledTimes(1);
    expect(history.length).toBe(antes);
    spy.mockRestore();
  });

  it("UT-27 a resolução das áreas globais continua igual, e preserva o pid corrente", async () => {
    const r = await roteador();
    act(() => r.current.navigate("moodboards/mb7"));

    await waitFor(() => expect(r.current.area).toBe("moodboards"));
    expect(r.current.sub).toBe("mb7");
    expect(r.current.view).toBeNull();
    expect(r.current.pid).toBe("campanha-a"); // pidRef não é limpo ao entrar na área global

    act(() => r.current.navigate("mood"));
    await waitFor(() => expect(r.current.area).toBe("campaign"));
    expect(location.hash).toBe("#/campanha-a/mood");
    expect(r.current.view).toBe("mood");
  });
});
