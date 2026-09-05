// Wave 10 · E2 — `copy` + `<CopyButton>` reproduzem o `Studio.ui.copy`/`copyBtn` (sem listener global).
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { copy, CopyButton } from "./CopyButton";

function mockClipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  return writeText;
}

afterEach(cleanup);

describe("copy", () => {
  it("usa a Clipboard API e devolve true", async () => {
    const writeText = mockClipboard();
    await expect(copy("olá")).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith("olá");
  });
});

describe("CopyButton", () => {
  it("`button.link.copy`; clique copia o texto literal", async () => {
    const writeText = mockClipboard();
    const onResult = vi.fn();
    render(<CopyButton text="prompt X" onResult={onResult} />);
    const btn = screen.getByRole("button", { name: "Copiar" });
    expect(btn).toHaveClass("link", "copy");
    await userEvent.click(btn);
    expect(writeText).toHaveBeenCalledWith("prompt X");
    expect(onResult).toHaveBeenCalledWith(true);
  });

  it("`from` copia o valor do campo apontado pelo seletor", async () => {
    const writeText = mockClipboard();
    render(
      <>
        <input aria-label="campo" defaultValue="conteúdo do campo" id="alvo" />
        <CopyButton from="#alvo" />
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Copiar" }));
    expect(writeText).toHaveBeenCalledWith("conteúdo do campo");
  });
});
