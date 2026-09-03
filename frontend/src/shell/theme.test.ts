import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { aplicarTema, proximoTema, rotuloTema, temaSalvo } from "./theme";

describe("tema — ciclo e persistência (C-SHELL-07, recon §1.4)", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });
  afterEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it("ciclo auto → light → dark → auto", () => {
    expect(proximoTema("auto")).toBe("light");
    expect(proximoTema("light")).toBe("dark");
    expect(proximoTema("dark")).toBe("auto");
  });

  it("auto REMOVE data-theme (cai no prefers-color-scheme); light/dark fixam", () => {
    aplicarTema("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    aplicarTema("auto");
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("persiste em localStorage['studio.theme'] e relê", () => {
    aplicarTema("light");
    expect(localStorage.getItem("studio.theme")).toBe("light");
    expect(temaSalvo()).toBe("light");
  });

  it("temaSalvo default é auto quando não há chave válida", () => {
    expect(temaSalvo()).toBe("auto");
    localStorage.setItem("studio.theme", "roxo");
    expect(temaSalvo()).toBe("auto");
  });

  it("rótulos", () => {
    expect(rotuloTema("auto")).toBe("tema: sistema");
    expect(rotuloTema("light")).toBe("tema: claro");
    expect(rotuloTema("dark")).toBe("tema: escuro");
  });
});
