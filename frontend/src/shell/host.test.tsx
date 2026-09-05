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
  it("o glob real enxerga as telas do lote A (E4) e ignora as ainda-vanilla", () => {
    // Wave 10 · E4: as 4 telas do lote A já têm `studio/etapas/<id>/ui/index.tsx`, descobertas pelo
    // glob real (`import.meta.glob`), sem registry central (ADR-032).
    expect(temTelaReact("mood")).toBe(true);
    expect(temTelaReact("publish")).toBe(true);
    expect(temTelaReact("export")).toBe(true);
    expect(temTelaReact("music")).toBe(true);
    // Uma etapa sem `ui/index.tsx` (vanilla na ponte, ou inexistente) não é vista como React — o
    // glob não alucina. Usamos um id inexistente para o teste ser robusto às migrações seguintes
    // (na integração da wave, `edit`/`storyboard`/etc. deixam de ser vanilla um a um).
    expect(temTelaReact("etapa-inexistente")).toBe(false);
  });

  it("temTelaReact enxerga um módulo descoberto pelo glob", () => {
    const modulos = { "../../../studio/etapas/mood/ui/index.tsx": async () => ({ default: () => null }) };
    expect(temTelaReact("mood", modulos)).toBe(true);
    expect(temTelaReact("etapa-inexistente", modulos)).toBe(false);
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
