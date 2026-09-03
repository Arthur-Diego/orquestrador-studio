// Wave 10 · E2 — `useAutosize` fixa a altura do textarea (porte do `Studio.ui.autosize`).
//
// jsdom não faz layout, então `scrollHeight` é 0 e a altura resolvida também: o que se prova aqui é
// o CONTRATO do hook — ele mede na montagem e a cada `input`, ligando/desligando o listener sem
// vazar. A prova visual da altura real fica na prova visual do PR (navegador de verdade).
import { useRef } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useAutosize } from "./useAutosize";

afterEach(cleanup);

function Campo({ value }: { value: string }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useAutosize(ref, [value]);
  return <textarea aria-label="txt" ref={ref} defaultValue={value} />;
}

describe("useAutosize", () => {
  it("define `style.height` na montagem", () => {
    render(<Campo value="uma linha" />);
    const ta = screen.getByLabelText("txt") as HTMLTextAreaElement;
    expect(ta.style.height).toMatch(/px$/);
  });

  it("reajusta ao receber input, sem lançar", () => {
    render(<Campo value="" />);
    const ta = screen.getByLabelText("txt") as HTMLTextAreaElement;
    expect(() => fireEvent.input(ta, { target: { value: "muito\ntexto\naqui" } })).not.toThrow();
    expect(ta.style.height).toMatch(/px$/);
  });
});
