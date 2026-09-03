// Wave 10 · E2 — `useUpload` reproduz o drag&drop do `Studio.ui.drop` (classe `over`, input, reset).
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useUpload } from "./useUpload";

afterEach(cleanup);

function Dropzone({ onFiles }: { onFiles: (f: FileList) => void }) {
  const u = useUpload(onFiles);
  return (
    <label aria-label="zona" className={`drop${u.isOver ? " over" : ""}`} {...u.rootProps}>
      <input aria-label="arquivo" {...u.inputProps} />
    </label>
  );
}

const png = () => new File(["x"], "a.png", { type: "image/png" });

describe("useUpload", () => {
  it("dragover marca `.over` e dragleave remove", () => {
    render(<Dropzone onFiles={() => {}} />);
    const zona = screen.getByLabelText("zona");
    expect(zona).not.toHaveClass("over");
    fireEvent.dragOver(zona);
    expect(zona).toHaveClass("over");
    fireEvent.dragLeave(zona);
    expect(zona).not.toHaveClass("over");
  });

  it("drop entrega os arquivos e limpa o `.over`", () => {
    const onFiles = vi.fn();
    render(<Dropzone onFiles={onFiles} />);
    const zona = screen.getByLabelText("zona");
    fireEvent.dragOver(zona);
    fireEvent.drop(zona, { dataTransfer: { files: [png()] } });
    expect(onFiles).toHaveBeenCalledOnce();
    expect(onFiles.mock.calls[0]?.[0]).toHaveLength(1);
    expect(zona).not.toHaveClass("over");
  });

  it("escolher no input dispara onFiles e reseta o value", () => {
    const onFiles = vi.fn();
    render(<Dropzone onFiles={onFiles} />);
    const input = screen.getByLabelText("arquivo") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [png()] } });
    expect(onFiles).toHaveBeenCalledOnce();
    expect(input.value).toBe("");
  });

  it("o input é oculto e múltiplo por padrão", () => {
    render(<Dropzone onFiles={() => {}} />);
    const input = screen.getByLabelText("arquivo") as HTMLInputElement;
    expect(input).toHaveAttribute("type", "file");
    expect(input.multiple).toBe(true);
    expect(input.hidden).toBe(true);
  });
});
