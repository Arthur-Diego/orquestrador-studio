import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { NoProject, Overview } from "./Overview";
import { mockShellApi, renderNoShell, STEPS } from "./test-utils";

describe("Overview — contrato DOM do overview.py (recon §3.2)", () => {
  it("um card por etapa do catálogo (C-OVERVIEW-01)", () => {
    // O vanilla renderiza `steps.map(cardHtml)`: um card por etapa de /api/steps. No backend real
    // o agregado do guia tem o mesmo tamanho — a paridade cards==guide.steps é validada pelo QA.
    renderNoShell(<main id="main"><Overview /></main>);
    expect(document.querySelectorAll("#main .ovgrid > *").length).toBe(STEPS.length);
  });

  it("card de etapa ready tem [data-go]; soon vira 'Em breve' desabilitado", () => {
    renderNoShell(<main id="main"><Overview /></main>);
    expect(document.querySelectorAll(".ovgrid [data-go]").length).toBe(3);
    const emBreve = [...document.querySelectorAll(".ovgrid .act button")].find(
      (b) => (b as HTMLButtonElement).disabled,
    );
    expect(emBreve?.textContent).toBe("Em breve");
  });

  it("resumo de chips soma o total de etapas (C-OVERVIEW-03)", () => {
    renderNoShell(<main id="main"><Overview /></main>);
    const chips = [...document.querySelectorAll(".ov-summary .chip")].map((c) => c.textContent || "");
    const soma = chips.reduce((acc, t) => acc + (parseInt(t, 10) || 0), 0);
    expect(soma).toBe(STEPS.length);
  });

  it("textos de aula (ADR-004): eyebrow, lede e aponta a etapa atual", () => {
    renderNoShell(<main id="main"><Overview /></main>);
    expect(document.querySelector(".stephead.ov .eyebrow")!.textContent).toBe(
      "Etapas 1 a 4 · aulas 009 → 015 · 001",
    );
    const main = document.querySelector("#main")!.textContent!;
    expect(main).toContain("As 10 etapas do curso");
    expect(main).toContain("Você está na");
    expect(main).toContain("Mood board"); // current = mood (etapa 2) na fixture
  });

  it("campanha concluída: lede diz 'Todas as etapas estão concluídas'", () => {
    renderNoShell(
      <main id="main"><Overview /></main>,
      mockShellApi({ guideAll: { steps: [], done: 0, total: 0, progress: 0, current: null } }),
    );
    expect(document.querySelector(".lede")!.textContent).toContain("Todas as etapas estão concluídas");
  });

  it("clique no card ready navega via go (C-OVERVIEW-02)", async () => {
    const { api } = renderNoShell(<main id="main"><Overview /></main>);
    await userEvent.click(document.querySelector(".ovgrid [data-go]") as HTMLElement);
    expect(api.go).toHaveBeenCalled();
  });

  it("#btnResetCamp abre o reset da campanha (é do shell — ADR-010)", async () => {
    const { api } = renderNoShell(<main id="main"><Overview /></main>);
    const btn = document.querySelector("#btnResetCamp") as HTMLElement;
    expect(btn).not.toBeNull();
    await userEvent.click(btn);
    expect(api.confirmResetCampaign).toHaveBeenCalled();
  });

  it("NoProject mostra o empty-state com #btnFirst", async () => {
    const { api } = renderNoShell(<NoProject />, mockShellApi({ pid: null, projects: [], project: null }));
    expect(document.querySelector(".empty-state h2")!.textContent).toBe("Nenhuma campanha ainda");
    await userEvent.click(document.querySelector("#btnFirst") as HTMLElement);
    expect(api.openWizard).toHaveBeenCalled();
  });
});
