import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("fundação do frontend React", () => {
  it("monta o esqueleto sem tela nenhuma (E0 não entrega UI)", () => {
    const { container } = render(<App />);
    const raiz = container.querySelector("[data-studio-ui='react']");
    expect(raiz).toBeInTheDocument();
    expect(raiz).toHaveClass("app");
  });

  it("não renderiza texto visível: nenhum texto de aula pode nascer nesta frente (ADR-004)", () => {
    render(<App />);
    expect(screen.queryByText(/\S/)).toBeNull();
  });
});
