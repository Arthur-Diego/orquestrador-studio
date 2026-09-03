import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { PROJECTS, STEPS, guideFixture, fetchRoteado } from "./shell/test-utils";

// Smoke/integração do shell React E3: exercita o roteamento por hash, as queries da E1 e o
// content-root do #main de ponta a ponta em jsdom. O oráculo funcional completo (14 telas em
// claro/escuro) é a suíte Playwright — este teste garante que a fiação básica sobe sem quebrar.

function fetchDoApp() {
  return fetchRoteado({
    "GET /api/steps": STEPS,
    "GET /api/projects": PROJECTS,
    "GET /api/projects/campanha-a": { ...PROJECTS[0], progress: 0.33, current: "mood" },
    "GET /api/projects/campanha-a/guide": guideFixture("campanha-a"),
    "GET /api/higgsfield/status": { installed: false, logged_in: false },
  });
}

describe("App — shell React E3 (fiação completa)", () => {
  beforeEach(() => {
    localStorage.clear();
    history.replaceState(null, "", "#");
    vi.stubGlobal("fetch", fetchDoApp());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    document.querySelectorAll("script[data-bridge]").forEach((s) => s.remove());
    delete (window as { Studio?: unknown }).Studio;
  });

  it("monta o chrome (sidebar + topbar) e lista as etapas de /api/steps", async () => {
    render(<App />);
    await waitFor(() =>
      expect(document.querySelectorAll("#steps li").length).toBe(STEPS.length),
    );
    expect(document.querySelector("aside.side")).not.toBeNull();
    expect(document.querySelector("#topbar")).not.toBeNull();
    expect(document.querySelector("#main")).not.toBeNull();
    expect(document.querySelector("#toast")).not.toBeNull();
  });

  it("resolve a rota para a 1ª campanha e renderiza a visão geral no #main", async () => {
    render(<App />);
    await waitFor(() => expect(location.hash).toBe("#/campanha-a/overview"));
    await waitFor(() => expect(document.querySelector("#main .ovgrid")).not.toBeNull());
    expect(document.querySelector("#tbName")!.textContent).toBe("Campanha A");
  });
});
