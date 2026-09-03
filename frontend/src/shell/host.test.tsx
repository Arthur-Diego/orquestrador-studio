import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { api, apiUpload } from "../api";
import { PluginHost, temTelaReact } from "./host";
import { useStudio, type StudioCtx } from "./plugin";
import { toast } from "./toast";

function ctxFalso(over: Partial<StudioCtx> = {}): StudioCtx {
  return {
    api,
    apiUpload,
    toast,
    pid: () => "campanha-x",
    project: () => null,
    files: (p) => `/files/campanha-x/${p}`,
    guide: vi.fn(),
    onGuide: vi.fn(),
    ...over,
  };
}

describe("host de plugin React — contrato de E4…E9", () => {
  it("em E3 nenhuma etapa tem tela React (todas são vanilla pela ponte)", () => {
    // O glob real resolve para {} — nenhuma `studio/etapas/*/ui/index.tsx` existe ainda.
    expect(temTelaReact("mood")).toBe(false);
    expect(temTelaReact("edit")).toBe(false);
  });

  it("temTelaReact enxerga um módulo descoberto pelo glob", () => {
    const modulos = { "../../../studio/etapas/mood/ui/index.tsx": async () => ({ default: () => null }) };
    expect(temTelaReact("mood", modulos)).toBe(true);
    expect(temTelaReact("edit", modulos)).toBe(false);
  });

  it("PluginHost monta a tela e entrega o ctx via useStudio()", async () => {
    function Tela() {
      const ctx = useStudio();
      return <div data-testid="tela">pid={ctx.pid()}</div>;
    }
    const modulos = { "../../../studio/etapas/mood/ui/index.tsx": async () => ({ default: Tela }) };
    render(<PluginHost stepId="mood" ctx={ctxFalso()} modulos={modulos} />);
    await waitFor(() => expect(screen.getByTestId("tela").textContent).toBe("pid=campanha-x"));
  });
});

describe("useStudio", () => {
  it("lança fora do host de plugin", () => {
    function Solta() {
      useStudio();
      return null;
    }
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Solta />)).toThrow(/useStudio\(\) fora do host/);
    spy.mockRestore();
  });
});
