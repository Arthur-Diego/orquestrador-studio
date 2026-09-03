import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Topbar } from "./Topbar";
import { mockShellApi, renderNoShell } from "./test-utils";

describe("Topbar — contrato DOM do shell.py (recon §3.1)", () => {
  it("nome, eyebrow e chips de meta da campanha", () => {
    renderNoShell(<Topbar />);
    expect(document.querySelector("#tbName")!.textContent).toBe("Campanha A");
    expect(document.querySelector("#tbEyebrow")!.textContent).toBe("Campanha · campanha-a");
    const meta = document.querySelector("#tbMeta")!.textContent!;
    expect(meta).toContain("energy drink");
    expect(meta).toContain("9:16");
    expect(meta).toContain("vibe: neon");
  });

  it("#tbCount bate com done/total do guia (C-SHELL-09)", () => {
    renderNoShell(<Topbar />);
    expect(document.querySelector("#tbCount")!.textContent).toBe("1/3 etapas");
  });

  it("#tbBar existe e é hidden (recon §6.4 / test_api.py:141)", () => {
    renderNoShell(<Topbar />);
    const bar = document.querySelector("#tbBar") as HTMLElement;
    expect(bar).not.toBeNull();
    expect(bar.hidden).toBe(true);
  });

  it("#tbPipe tem um segmento por etapa", () => {
    renderNoShell(<Topbar />);
    expect(document.querySelectorAll("#tbPipe.pipe.lg > i").length).toBe(4);
  });

  it("Continuar habilitado com etapa atual; abre a etapa current (C-SHELL-08)", async () => {
    const { api } = renderNoShell(<Topbar />);
    const btn = document.querySelector("#btnContinue") as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
    await userEvent.click(btn);
    expect(api.continuar).toHaveBeenCalled();
  });

  it("campanha concluída: sem current, o botão vira 'Campanha concluída' e desabilita", () => {
    renderNoShell(
      <Topbar />,
      mockShellApi({ guideAll: { steps: [], done: 3, total: 3, progress: 1, current: null } }),
    );
    const btn = document.querySelector("#btnContinue") as HTMLButtonElement;
    expect(btn.textContent).toBe("Campanha concluída");
    expect(btn.disabled).toBe(true);
  });

  it("sem campanha: topbar.vazio, #tbCount '—', editar desabilitado", () => {
    renderNoShell(<Topbar />, mockShellApi({ pid: null, project: null, guideAll: null }));
    expect(document.querySelector("#topbar")!.classList.contains("vazio")).toBe(true);
    expect(document.querySelector("#tbCount")!.textContent).toBe("—");
    expect((document.querySelector("#btnEditCamp") as HTMLButtonElement).disabled).toBe(true);
    expect(document.querySelector("#tbName")!.textContent).toBe("Nenhuma campanha");
  });

  it("#btnCredits tem data-credits-chip (recon §6.4)", () => {
    renderNoShell(<Topbar />);
    expect(document.querySelector("#btnCredits[data-credits-chip]")).not.toBeNull();
  });
});
