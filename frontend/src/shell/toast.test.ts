import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { _cancelarToast, toast } from "./toast";

describe("toast — #toast global, único, auto-hide 3200 ms (recon §6.4)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    const t = document.createElement("div");
    t.id = "toast";
    t.className = "toast hidden";
    document.body.appendChild(t);
  });
  afterEach(() => {
    _cancelarToast();
    document.getElementById("toast")?.remove();
    vi.useRealTimers();
  });

  it("escreve a mensagem e tira o .hidden", () => {
    toast("salvo");
    const el = document.getElementById("toast")!;
    expect(el.textContent).toBe("salvo");
    expect(el.classList.contains("hidden")).toBe(false);
  });

  it("re-esconde após 3200 ms", () => {
    toast("oi");
    const el = document.getElementById("toast")!;
    vi.advanceTimersByTime(3199);
    expect(el.classList.contains("hidden")).toBe(false);
    vi.advanceTimersByTime(1);
    expect(el.classList.contains("hidden")).toBe(true);
  });

  it("o último toast vence (timer único, sem fila)", () => {
    toast("primeiro");
    vi.advanceTimersByTime(2000);
    toast("segundo");
    const el = document.getElementById("toast")!;
    expect(el.textContent).toBe("segundo");
    vi.advanceTimersByTime(3199);
    expect(el.classList.contains("hidden")).toBe(false); // o timer foi reiniciado
    vi.advanceTimersByTime(1);
    expect(el.classList.contains("hidden")).toBe(true);
  });
});
