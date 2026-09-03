// Wave 10 · E2 — `esc`/`fmtPct` reproduzem o `Studio.ui` do vanilla byte a byte.
import { describe, expect, it } from "vitest";
import { esc, fmtPct } from "./text";

describe("esc", () => {
  it("escapa os cinco caracteres do mapa do vanilla", () => {
    expect(esc(`<a href="x" class='y'>&`)).toBe("&lt;a href=&quot;x&quot; class=&#39;y&#39;&gt;&amp;");
  });
  it("trata null/undefined como string vazia (`?? \"\"` do vanilla)", () => {
    expect(esc(null)).toBe("");
    expect(esc(undefined)).toBe("");
  });
  it("faz ToString de não-strings", () => {
    expect(esc(42)).toBe("42");
  });
});

describe("fmtPct", () => {
  it("fração 0..1 vira porcentagem", () => {
    expect(fmtPct(0.42)).toBe("42%");
    expect(fmtPct(1)).toBe("100%");
  });
  it("valor já em porcentagem (>1) é mantido", () => {
    expect(fmtPct(42)).toBe("42%");
  });
  it("não-número vira 0%", () => {
    expect(fmtPct(null)).toBe("0%");
    expect(fmtPct("x")).toBe("0%");
  });
});
