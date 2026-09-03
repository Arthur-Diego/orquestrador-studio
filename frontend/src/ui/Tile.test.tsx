// Wave 10 · E2 — `<Tile>` reproduz o `Studio.ui.tile` (div.card + selos).
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Tile } from "./Tile";

describe("Tile", () => {
  it("card completo: classes, data-attrs, img e selos", () => {
    const { container } = render(
      <Tile src="/a.png" badge="mj" term="uma base" up="2x" upOk sel ord={3} id="i1" title="t" cls="foo" />,
    );
    const card = container.querySelector(".card")!;
    expect(card).toHaveClass("card", "sel", "foo");
    expect(card).toHaveAttribute("data-id", "i1");
    expect(card).toHaveAttribute("data-ord", "3");
    expect(card).toHaveAttribute("title", "t");
    expect(card).toHaveAttribute("tabindex", "0");
    expect(card.querySelector("img")).toHaveAttribute("loading", "lazy");
    expect(card.querySelector(".src")).toHaveTextContent("mj");
    expect(card.querySelector(".term")).toHaveTextContent("uma base");
    expect(card.querySelector(".up")).toHaveClass("up", "ok");
  });

  it("card mínimo: só `.card`, sem data-id nem selos", () => {
    const { container } = render(<Tile />);
    const card = container.querySelector(".card")!;
    expect(card).toHaveClass("card");
    expect(card).not.toHaveAttribute("data-id");
    expect(card.querySelector("img")).toBeNull();
    expect(card.querySelector(".src")).toBeNull();
  });
});
