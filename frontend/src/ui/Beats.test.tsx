// Wave 10 · E2 — `<Beats>` reproduz o `Studio.ui.beats` (barras + cortes).
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Beats } from "./Beats";

describe("Beats", () => {
  it("barras com altura/clamp e `.imp`; cortes `.cut[.off]`", () => {
    const { container } = render(
      <Beats
        lista={[0.5, { h: 80, imp: true, title: "pico" }, {}]}
        cuts={[{ at: 50, title: "corte" }, { at: 10, off: true }]}
        sm
      />,
    );
    const beats = container.querySelector(".beats");
    expect(beats).toHaveClass("beats", "sm");
    const barras = container.querySelectorAll(".beats > i");
    expect(barras).toHaveLength(3);
    expect(barras[0]).toHaveStyle({ height: "50%" });
    expect(barras[1]).toHaveClass("imp");
    expect(barras[1]).toHaveStyle({ height: "100%" });
    expect(barras[2]).toHaveStyle({ height: "40%" }); // {} → h nulo → 40
    const cortes = container.querySelectorAll(".beats > .cut");
    expect(cortes).toHaveLength(2);
    expect(cortes[0]).toHaveStyle({ left: "50%" });
    expect(cortes[0]).toHaveAttribute("title", "corte");
    expect(cortes[1]).toHaveClass("off");
    expect(cortes[1]).toHaveStyle({ left: "10%" });
  });
});
