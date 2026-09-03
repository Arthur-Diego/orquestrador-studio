// Wave 10 · E2 — `refreshCredits`/`defaultModel`/`creditsView`/`<CreditsChip>` (ADR-016).
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { creditsView, CreditsChip, defaultModel, refreshCredits } from "./credits";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stubFetch(body: unknown, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok, json: async () => body, statusText: "err" })) as unknown as typeof fetch,
  );
}

describe("creditsView", () => {
  it("logado → saldo/ok com título de custos", () => {
    const v = creditsView({ installed: true, logged_in: true, plan: "pro", credits: 500 });
    expect(v.text).toBe("● 500 créditos");
    expect(v.kind).toBe("ok");
    expect(v.title).toContain("Plano pro");
  });
  it("deslogado → sem login/warn", () => {
    expect(creditsView({ installed: true, logged_in: false }).text).toBe("● CLI · sem login");
  });
});

describe("refreshCredits", () => {
  it("lê o saldo do balance", async () => {
    stubFetch({ installed: true, logged_in: true, credits: 12 });
    await expect(refreshCredits()).resolves.toMatchObject({ credits: 12 });
  });
  it("falha vira estado neutro", async () => {
    stubFetch({ detail: "boom" }, false);
    await expect(refreshCredits()).resolves.toEqual({ installed: false, logged_in: false });
  });
});

describe("defaultModel", () => {
  it("devolve model/variant da ação", async () => {
    stubFetch({ model: "nano", variant: "pro" });
    await expect(defaultModel("animate.video", "p1")).resolves.toEqual({ model: "nano", variant: "pro" });
  });
  it("falha vira objeto vazio", async () => {
    stubFetch({ detail: "x" }, false);
    await expect(defaultModel("animate.video")).resolves.toEqual({});
  });
});

describe("CreditsChip", () => {
  it("renderiza `[data-credits-chip]` e atualiza com o saldo", async () => {
    stubFetch({ installed: true, logged_in: true, credits: 7 });
    const { container } = render(<CreditsChip id="tbCredits" />);
    expect(container.querySelector("[data-credits-chip]")).not.toBeNull();
    expect(await screen.findByText("● 7 créditos")).toHaveClass("chip", "ok");
  });
});
