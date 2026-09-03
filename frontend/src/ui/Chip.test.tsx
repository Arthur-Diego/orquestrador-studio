// Wave 10 · E2 — `<Chip>` emite `span.chip.<kind>`, igual ao `Studio.ui.chip`.
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Chip } from "./Chip";

describe("Chip", () => {
  it("default é `chip mode`", () => {
    const { container } = render(<Chip>a fazer</Chip>);
    const span = container.querySelector("span.chip");
    expect(span).not.toBeNull();
    expect(span).toHaveClass("chip", "mode");
    expect(span).toHaveTextContent("a fazer");
  });

  it("aplica o kind pedido", () => {
    const { container } = render(<Chip kind="ok">ok</Chip>);
    expect(container.querySelector("span.chip")).toHaveClass("chip", "ok");
  });
});
