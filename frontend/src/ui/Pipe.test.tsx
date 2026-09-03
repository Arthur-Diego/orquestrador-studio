// Wave 10 · E2 — `<Pipe>` reproduz o `Studio.ui.pipe` (div.pipe > i.<status>).
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Pipe } from "./Pipe";

describe("Pipe", () => {
  it("um `i` por estado, `todo` no vazio, `.lg` e title", () => {
    const { container } = render(<Pipe estados={["done", "in_progress", null]} titles={["a", "b"]} lg />);
    const pipe = container.querySelector(".pipe");
    expect(pipe).toHaveClass("pipe", "lg");
    const segs = container.querySelectorAll(".pipe > i");
    expect(segs).toHaveLength(3);
    expect(segs[0]).toHaveClass("done");
    expect(segs[0]).toHaveAttribute("title", "a");
    expect(segs[1]).toHaveClass("in_progress");
    expect(segs[2]).toHaveClass("todo");
  });
});
