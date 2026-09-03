// Substituto Vitest dos asserts de `tests/test_storyboard_view.py` sobre `studio/web/annotate.js` —
// Wave 10 · E8 (card [REACT-09]). Renderiza o componente e afirma o CONTRATO e a fidelidade ao curso
// (ADR-004): traço vermelho fixo, pincel 4–24, desfazer/limpar, desenho por pointer, export PNG pelo
// canvas e — o invariante do ADR-017 — que o componente NÃO conhece rota HTTP (quem chama faz o
// upload por `onSave`).
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Annotate } from "./Annotate";

// jsdom não implementa canvas: forjamos um contexto 2D e um `toBlob` que devolve um PNG.
function mockCanvas() {
  const ctx2d = {
    clearRect: vi.fn(),
    drawImage: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    globalAlpha: 1,
    strokeStyle: "",
    lineCap: "",
    lineJoin: "",
    lineWidth: 0,
  };
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx2d) as unknown as HTMLCanvasElement["getContext"];
  HTMLCanvasElement.prototype.toBlob = function (cb: BlobCallback) {
    cb(new Blob(["png"], { type: "image/png" }));
  };
  // jsdom não carrega imagens: uma `Image` que dispara `onload` de imediato, com dimensões naturais.
  class FakeImage {
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    naturalWidth = 20;
    naturalHeight = 20;
    width = 20;
    height = 20;
    set src(_v: string) {
      queueMicrotask(() => this.onload?.());
    }
  }
  vi.stubGlobal("Image", FakeImage);
}

describe("Annotate · canvas de marcação (`[extensão]` inpaint-marcacao, ADR-004)", () => {
  beforeEach(() => mockCanvas());

  it("monta o modal com o título e o corpo escopado `.ann-*`", () => {
    render(<Annotate sourceUrl="/files/p1/base.png" onSave={() => {}} onClose={() => {}} />);
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-label", "Marcar área [extensão]");
    expect(document.querySelector(".ann-canvas")).toBeTruthy();
    expect(document.querySelector(".ann-dot")).toBeTruthy();
    expect(screen.getByText("Desfazer")).toBeInTheDocument();
    expect(screen.getByText("Limpar")).toBeInTheDocument();
  });

  it("o CSS inline é 100% escopado em `.ann-` e a cor do traço é o vermelho fixo #ff2d2d", () => {
    const { container } = render(<Annotate sourceUrl="/files/p1/base.png" onSave={() => {}} onClose={() => {}} />);
    const style = container.querySelector("style")?.textContent || document.querySelector("style")?.textContent || "";
    const classes = [...style.matchAll(/\.(-?[_a-zA-Z][\w-]*)/g)].map((m) => m[1]);
    expect(classes.length).toBeGreaterThan(0);
    expect(classes.every((c) => c?.startsWith("ann-"))).toBe(true);
    expect(style).toContain("#ff2d2d");
  });

  it("o pincel vai de 4 a 24 px e ecoa o valor escolhido", () => {
    render(<Annotate sourceUrl="/files/p1/base.png" brush={10} onSave={() => {}} onClose={() => {}} />);
    const slider = document.querySelector(".annBrush") as HTMLInputElement;
    expect(slider.min).toBe("4");
    expect(slider.max).toBe("24");
    expect(slider.value).toBe("10");
    fireEvent.change(slider, { target: { value: "20" } });
    expect(document.querySelector(".annBrushVal")?.textContent).toBe("20");
  });

  it("desenhar e salvar exporta um PNG (toBlob) e entrega o Blob a quem chamou (ADR-017)", async () => {
    const onSave = vi.fn(async () => {});
    const onClose = vi.fn();
    render(<Annotate sourceUrl="/files/p1/base.png" onSave={onSave} onClose={onClose} />);
    const canvas = document.querySelector(".ann-canvas") as HTMLCanvasElement;
    // espera a imagem "carregar" (microtask do FakeImage)
    await Promise.resolve();
    await new Promise((r) => queueMicrotask(() => r(null)));
    fireEvent.pointerDown(canvas, { pointerId: 1, clientX: 5, clientY: 5 });
    fireEvent.pointerMove(canvas, { pointerId: 1, clientX: 8, clientY: 9 });
    fireEvent.pointerUp(canvas, { pointerId: 1 });
    fireEvent.click(screen.getByText("Salvar marcação"));
    await vi.waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const args = onSave.mock.calls[0] as unknown[] | undefined;
    expect(args?.[0]).toBeInstanceOf(Blob);
    await vi.waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("não salva sem nenhum traço (nada é enviado a quem chama)", async () => {
    const onSave = vi.fn(async () => {});
    render(<Annotate sourceUrl="/files/p1/base.png" onSave={onSave} onClose={() => {}} />);
    await Promise.resolve();
    fireEvent.click(screen.getByText("Salvar marcação"));
    await new Promise((r) => setTimeout(r, 10));
    expect(onSave).not.toHaveBeenCalled();
  });
});
