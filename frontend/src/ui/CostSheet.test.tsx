// Wave 10 · E2 — `<CostSheet>` e `useCostConfirm` reproduzem o `confirmCost` do vanilla (ADR-016).
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CostSheet, useCostConfirm } from "./CostSheet";
import type { RichCostOpts, SimpleCostOpts } from "./CostSheet";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CostSheet", () => {
  it("linhas viram `.cost-row` (total com `.total`) + nota padrão", () => {
    const { container } = render(
      <CostSheet
        rows={[
          { label: "Modelo", value: "Nano" },
          { label: "Total estimado", value: "6 créditos", total: true },
        ]}
      />,
    );
    const rows = container.querySelectorAll(".cost-sheet .cost-row");
    expect(rows).toHaveLength(2);
    expect(rows[1]).toHaveClass("total");
    expect(rows[0]?.querySelector("b")).toHaveTextContent("Nano");
    expect(container.querySelector(".cost-note")).toHaveTextContent("Isso gasta créditos");
  });

  it("modo simples usa `.cost-line`", () => {
    const { container } = render(<CostSheet line="Estimativa de custo indisponível." />);
    expect(container.querySelector(".cost-line")).toHaveTextContent("Estimativa de custo indisponível.");
    expect(container.querySelector(".cost-sheet")).toBeNull();
  });

  it("aviso vira `.cost-warn`", () => {
    const { container } = render(<CostSheet rows={[]} warn="⚠ CLI sem login" />);
    expect(container.querySelector(".cost-warn")).toHaveTextContent("CLI sem login");
  });
});

function Harness({ onReady }: { onReady: (c: (o: RichCostOpts | SimpleCostOpts) => Promise<boolean>) => void }) {
  const { confirm, element } = useCostConfirm();
  useEffect(() => {
    onReady(confirm);
  }, [confirm, onReady]);
  return <>{element}</>;
}

function montar(): (o: RichCostOpts | SimpleCostOpts) => Promise<boolean> {
  let confirm!: (o: RichCostOpts | SimpleCostOpts) => Promise<boolean>;
  render(<Harness onReady={(c) => (confirm = c)} />);
  return confirm;
}

describe("useCostConfirm (rico, ADR-016)", () => {
  it("consulta o custo, monta a planilha e resolve true no Gerar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          model: "nano",
          label: "Nano",
          variant: "pro",
          credits: 2,
          source: "cli",
          balance: { installed: true, logged_in: true, credits: 500 },
        }),
      })) as unknown as typeof fetch,
    );
    const confirm = montar();

    let p!: Promise<boolean>;
    await act(async () => {
      p = confirm({ action: "mood.multishot", pid: "p1", count: 3 });
    });

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-label", "Gerar via CLI");
    const texto = dialog.textContent ?? "";
    expect(texto).toContain("Nano · pro");
    expect(texto).toContain("2 créditos (CLI)");
    expect(texto).toContain("3×");
    expect(texto).toContain("6 créditos"); // total 2×3
    expect(texto).toContain("494 créditos"); // saldo depois 500-6
    // logado: sem aviso.
    expect(dialog.querySelector(".cost-warn")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Gerar" }));
    await expect(p).resolves.toBe(true);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("CLI deslogado mostra `.cost-warn`; Cancelar resolve false", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ credits: 2, balance: { installed: true, logged_in: false } }),
      })) as unknown as typeof fetch,
    );
    const confirm = montar();
    let p!: Promise<boolean>;
    await act(async () => {
      p = confirm({ action: "animate.video" });
    });
    expect(screen.getByRole("dialog").querySelector(".cost-warn")).toHaveTextContent("CLI sem login");
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    await expect(p).resolves.toBe(false);
  });
});

describe("useCostConfirm (simples/legado)", () => {
  it("costFn vira `.cost-line`; Esc resolve false", async () => {
    const confirm = montar();
    let p!: Promise<boolean>;
    await act(async () => {
      p = confirm({ costFn: () => ({ credits: 5 }), label: "Gerar via CLI" });
    });
    expect(screen.getByRole("dialog").querySelector(".cost-line")).toHaveTextContent("5");
    await userEvent.keyboard("{Escape}");
    await expect(p).resolves.toBe(false);
  });
});
