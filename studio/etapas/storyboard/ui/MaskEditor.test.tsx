// `[extensão]` motor local (ADR-033) — testes do MaskEditor (inpaint real por máscara).
// Afirma o contrato da tela de edição: pinta a máscara, exporta um PNG (toBlob), NÃO conhece rota
// HTTP (quem chama roda o inpaint via `onRun`), e o loop antes/depois com Refinar/Concluir.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MaskEditor } from "./MaskEditor";

const MODELS = [
  { id: "flux-dev", label: "Qualidade (dev, ~3-4min)", default: true },
  { id: "flux-schnell", label: "Rápido (schnell, ~40s)" },
];

function mockCanvas() {
  const ctx2d = {
    clearRect: vi.fn(),
    drawImage: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    fillRect: vi.fn(),
    globalCompositeOperation: "source-over",
    globalAlpha: 1,
    strokeStyle: "",
    fillStyle: "",
    lineCap: "",
    lineJoin: "",
    lineWidth: 0,
  };
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx2d) as unknown as HTMLCanvasElement["getContext"];
  HTMLCanvasElement.prototype.toBlob = function (cb: BlobCallback) {
    cb(new Blob(["png"], { type: "image/png" }));
  };
  class FakeImage {
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    naturalWidth = 32;
    naturalHeight = 24;
    width = 32;
    height = 24;
    set src(_v: string) {
      queueMicrotask(() => this.onload?.());
    }
  }
  vi.stubGlobal("Image", FakeImage);
}

async function loaded() {
  await Promise.resolve();
  await new Promise((r) => queueMicrotask(() => r(null)));
}

function paint(canvas: HTMLCanvasElement) {
  fireEvent.pointerDown(canvas, { pointerId: 1, clientX: 5, clientY: 5 });
  fireEvent.pointerMove(canvas, { pointerId: 1, clientX: 12, clientY: 10 });
  fireEvent.pointerUp(canvas, { pointerId: 1 });
}

describe("MaskEditor · inpaint real por máscara (`[extensão]` ADR-033)", () => {
  beforeEach(() => mockCanvas());

  it("monta o modal com canvas, pincel 6–80, borracha, instrução e modelos", () => {
    render(<MaskEditor sourceUrl="/files/p1/idea.png" models={MODELS} onRun={vi.fn()} onDone={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-label", "Inpaint local (grátis) [extensão]");
    expect(document.querySelector(".me-canvas")).toBeTruthy();
    const brush = document.querySelector(".meBrush") as HTMLInputElement;
    expect(brush.min).toBe("6");
    expect(brush.max).toBe("80");
    expect(document.querySelector(".meErase")).toBeTruthy();
    expect(document.querySelector(".meInstruction")).toBeTruthy();
    const model = document.querySelector(".meModel") as HTMLSelectElement;
    expect(model.value).toBe("flux-dev"); // o default do catálogo
    expect(model.querySelectorAll("option").length).toBe(2);
  });

  it("o CSS inline é 100% escopado em `.me-`", () => {
    const { container } = render(
      <MaskEditor sourceUrl="/files/p1/idea.png" models={MODELS} onRun={vi.fn()} onDone={vi.fn()} onClose={vi.fn()} />,
    );
    const style = container.querySelector("style")?.textContent || document.querySelector("style")?.textContent || "";
    const classes = [...style.matchAll(/\.(-?[_a-zA-Z][\w-]*)/g)].map((m) => m[1]);
    expect(classes.length).toBeGreaterThan(0);
    expect(classes.every((c) => c?.startsWith("me-"))).toBe(true);
  });

  it("a borracha alterna o modo", () => {
    render(<MaskEditor sourceUrl="/files/p1/idea.png" models={MODELS} onRun={vi.fn()} onDone={vi.fn()} onClose={vi.fn()} />);
    const btn = document.querySelector(".meErase") as HTMLButtonElement;
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-pressed")).toBe("true");
    expect(btn.textContent).toContain("ativa");
  });

  it("pintar + instrução + Rodar chama onRun com o Blob da máscara e o modelo (não conhece HTTP)", async () => {
    const onRun = vi.fn(async () => "/files/p1/storyboard/candidates/out.png");
    render(<MaskEditor sourceUrl="/files/p1/idea.png" models={MODELS} onRun={onRun} onDone={vi.fn()} onClose={vi.fn()} />);
    await loaded();
    paint(document.querySelector(".me-canvas") as HTMLCanvasElement);
    fireEvent.change(document.querySelector(".meInstruction") as HTMLTextAreaElement, {
      target: { value: "remove the book" },
    });
    fireEvent.click(screen.getByText("Rodar (grátis)"));
    await vi.waitFor(() => expect(onRun).toHaveBeenCalledTimes(1));
    const args = onRun.mock.calls[0] as unknown[];
    expect(args[0]).toBeInstanceOf(Blob);
    expect(args[1]).toBe("remove the book");
    expect(args[2]).toEqual({ model: "flux-dev" });
    // antes/depois aparece com a URL do resultado
    await vi.waitFor(() => expect(document.querySelector(".meAfter")).toBeTruthy());
    expect((document.querySelector(".meAfter") as HTMLImageElement).getAttribute("src")).toBe(
      "/files/p1/storyboard/candidates/out.png",
    );
    expect(screen.getByText("Refinar nesta")).toBeInTheDocument();
    expect(screen.getByText("Concluir")).toBeInTheDocument();
  });

  it("não roda sem instrução (onRun não é chamado)", async () => {
    const onRun = vi.fn(async () => null);
    render(<MaskEditor sourceUrl="/files/p1/idea.png" models={MODELS} onRun={onRun} onDone={vi.fn()} onClose={vi.fn()} />);
    await loaded();
    paint(document.querySelector(".me-canvas") as HTMLCanvasElement);
    fireEvent.click(screen.getByText("Rodar (grátis)"));
    await new Promise((r) => setTimeout(r, 10));
    expect(onRun).not.toHaveBeenCalled();
  });

  it("Concluir chama onDone e onClose", async () => {
    const onDone = vi.fn();
    const onClose = vi.fn();
    render(
      <MaskEditor
        sourceUrl="/files/p1/idea.png"
        models={MODELS}
        onRun={async () => "/files/p1/out.png"}
        onDone={onDone}
        onClose={onClose}
      />,
    );
    await loaded();
    paint(document.querySelector(".me-canvas") as HTMLCanvasElement);
    fireEvent.change(document.querySelector(".meInstruction") as HTMLTextAreaElement, { target: { value: "x" } });
    fireEvent.click(screen.getByText("Rodar (grátis)"));
    await vi.waitFor(() => expect(screen.getByText("Concluir")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Concluir"));
    expect(onDone).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });
});
