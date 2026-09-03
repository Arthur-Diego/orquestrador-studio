// Wave 10 · E2 — `<MoodMosaic>` reproduz o DOM do `Studio.ui.moodMosaic` (grade 2×2, data-n, +N).
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { MoodMosaic } from "./MoodMosaic";

describe("MoodMosaic", () => {
  it("vazio: `.mood-mosaic.empty[role=img]` com aria-label e `.mm-empty`", () => {
    const { container } = render(<MoodMosaic urls={[]} />);
    const box = container.querySelector(".mood-mosaic.empty");
    expect(box).not.toBeNull();
    expect(box).toHaveAttribute("role", "img");
    expect(box).toHaveAttribute("aria-label", "sem imagens ainda");
    expect(container.querySelector(".mm-empty")).toHaveTextContent("sem imagens ainda");
  });

  it("título vira `.mm-title.eyebrow` acima da grade", () => {
    const { container } = render(<MoodMosaic urls={["/a.png"]} title="Neon" />);
    const t = container.querySelector(".mm-title");
    expect(t).toHaveClass("eyebrow");
    expect(t).toHaveTextContent("Neon");
  });

  it("N imagens → `data-n` e uma `.mm-cell > img[loading=lazy]` por imagem, sem overflow", () => {
    const { container } = render(<MoodMosaic urls={["/a.png", "/b.png"]} />);
    const grid = container.querySelector(".mood-mosaic");
    expect(grid).toHaveAttribute("data-n", "2");
    const cells = container.querySelectorAll(".mm-cell");
    expect(cells).toHaveLength(2);
    expect(cells[0]?.querySelector("img")).toHaveAttribute("loading", "lazy");
    expect(container.querySelector(".mm-more")).toBeNull();
  });

  it("acima de `max` mostra `max` células e `+N` na última", () => {
    const urls = ["/1", "/2", "/3", "/4", "/5", "/6"];
    const { container } = render(<MoodMosaic urls={urls} max={4} />);
    expect(container.querySelector(".mood-mosaic")).toHaveAttribute("data-n", "4");
    expect(container.querySelectorAll(".mm-cell")).toHaveLength(4);
    const more = container.querySelector(".mm-more");
    expect(more).toHaveTextContent("+2");
  });

  it("ignora URLs falsy (mesmo filtro do vanilla)", () => {
    const { container } = render(<MoodMosaic urls={["/a", "", "/b"] as string[]} />);
    expect(container.querySelectorAll(".mm-cell")).toHaveLength(2);
  });
});
