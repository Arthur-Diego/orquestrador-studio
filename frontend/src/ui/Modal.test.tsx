// Wave 10 · E2 — `<Modal>` reproduz o DOM e a acessibilidade do `Studio.ui.modal`.
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "./Modal";

describe("Modal", () => {
  it("monta `.modal-backdrop > .modal[role=dialog]` com cabeçalho, ✕ e corpo", () => {
    render(
      <Modal title="Título" subtitle="sub" onClose={() => {}}>
        <p>conteúdo</p>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveClass("modal");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-label", "Título");
    expect(dialog.closest(".modal-backdrop")).not.toBeNull();
    expect(dialog.querySelector(".modal-head h3")).toHaveTextContent("Título");
    expect(dialog.querySelector(".modal-head .sub")).toHaveTextContent("sub");
    expect(dialog.querySelector(".modal-close")).toHaveAttribute("aria-label", "Fechar");
    expect(dialog.querySelector(".modal-body")).toHaveTextContent("conteúdo");
  });

  it("sem subtitle não desenha `.sub`", () => {
    render(<Modal title="T" onClose={() => {}} />);
    expect(screen.getByRole("dialog").querySelector(".sub")).toBeNull();
  });

  it("ações viram `.modal-actions` com `.ghost.lg`/`.primary.lg` e `data-act`", () => {
    render(
      <Modal
        title="T"
        onClose={() => {}}
        actions={[
          { label: "Cancelar", kind: "ghost" },
          { label: "Gerar", kind: "primary" },
        ]}
      />,
    );
    const acts = screen.getByRole("dialog").querySelector(".modal-actions");
    expect(acts).not.toBeNull();
    const botoes = acts!.querySelectorAll("button");
    expect(botoes[0]).toHaveClass("ghost", "lg");
    expect(botoes[0]).toHaveAttribute("data-act", "0");
    expect(botoes[1]).toHaveClass("primary", "lg");
    expect(botoes[1]).toHaveAttribute("data-act", "1");
  });

  it("clique numa ação chama `onClick` e fecha; `close:false` não fecha", async () => {
    const onClose = vi.fn();
    const primaria = vi.fn();
    const fica = vi.fn();
    render(
      <Modal
        title="T"
        onClose={onClose}
        actions={[
          { label: "Gerar", kind: "primary", onClick: primaria },
          { label: "Manter", kind: "ghost", close: false, onClick: fica },
        ]}
      />,
    );
    await userEvent.click(screen.getByText("Gerar"));
    expect(primaria).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();

    onClose.mockClear();
    await userEvent.click(screen.getByText("Manter"));
    expect(fica).toHaveBeenCalledOnce();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("Esc fecha", async () => {
    const onClose = vi.fn();
    render(<Modal title="T" onClose={onClose} />);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("clique no ✕ fecha", async () => {
    const onClose = vi.fn();
    render(<Modal title="T" onClose={onClose} />);
    await userEvent.click(screen.getByLabelText("Fechar"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("mousedown no fundo fecha; no diálogo não", () => {
    const onClose = vi.fn();
    render(<Modal title="T" onClose={onClose} />);
    const dialog = screen.getByRole("dialog");
    fireEvent.mouseDown(dialog);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.mouseDown(dialog.closest(".modal-backdrop")!);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("foca o primeiro campo ao abrir (não o ✕)", () => {
    render(
      <Modal title="T" onClose={() => {}}>
        <input aria-label="nome" />
      </Modal>,
    );
    expect(document.activeElement).toBe(screen.getByLabelText("nome"));
  });
});
