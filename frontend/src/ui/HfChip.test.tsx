// Wave 10 · E2 — `hfChipView`/`<HfChip>` reproduzem o `Studio.ui.hfChip` (textos exatos do protótipo).
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { HfChip, hfChipView } from "./HfChip";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("hfChipView", () => {
  it("null (falha) → indisponível/warn", () => {
    expect(hfChipView(null)).toEqual({ text: "● CLI · indisponível", kind: "warn" });
  });
  it("sem binário → não instalado/warn", () => {
    expect(hfChipView({ installed: false, logged_in: false })).toEqual({
      text: "● CLI · não instalado",
      kind: "warn",
    });
  });
  it("sem login → texto com o comando de auth/warn", () => {
    expect(hfChipView({ installed: true, logged_in: false })).toEqual({
      text: "● CLI · sem login (higgsfield auth login)",
      kind: "warn",
    });
  });
  it("logado → plano · créditos/ok", () => {
    expect(hfChipView({ installed: true, logged_in: true, plan: "pro", credits: 500 })).toEqual({
      text: "● CLI · pro · 500 créditos",
      kind: "ok",
    });
  });
});

describe("HfChip", () => {
  it("busca o status e pinta o chip logado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        json: async () => ({ installed: true, logged_in: true, plan: "pro", credits: 500 }),
      })) as unknown as typeof fetch,
    );
    render(<HfChip id="hfChipSide" />);
    const chip = await screen.findByText("● CLI · pro · 500 créditos");
    expect(chip).toHaveClass("chip", "ok");
    expect(chip).toHaveAttribute("id", "hfChipSide");
  });

  it("falha de rede vira indisponível", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new Error("x"))) as unknown as typeof fetch);
    render(<HfChip />);
    expect(await screen.findByText("● CLI · indisponível")).toHaveClass("chip", "warn");
  });
});
