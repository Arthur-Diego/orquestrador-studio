import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Sidebar } from "./Sidebar";
import { mockShellApi, renderNoShell, STEPS } from "./test-utils";

describe("Sidebar — contrato DOM do shell.py (recon §3.1)", () => {
  it("lista as etapas de /api/steps na ordem e marca as ready (C-SHELL-01)", () => {
    renderNoShell(<Sidebar />);
    const lis = document.querySelectorAll("#steps li");
    expect([...lis].map((l) => (l as HTMLElement).dataset.id)).toEqual(STEPS.map((s) => s.id));
    const ready = document.querySelectorAll("#steps li.ready");
    expect([...ready].map((l) => (l as HTMLElement).dataset.id)).toEqual(
      STEPS.filter((s) => s.status === "ready").map((s) => s.id),
    );
  });

  it("etapa ready é focável (tabindex + role=button); soon não é (C-SHELL-03)", () => {
    renderNoShell(<Sidebar />);
    const refs = document.querySelector("#steps li.ready[data-id='refs']") as HTMLElement;
    expect(refs.getAttribute("tabindex")).toBe("0");
    expect(refs.getAttribute("role")).toBe("button");
    const soon = document.querySelector("#steps li[data-id='prospect']") as HTMLElement;
    expect(soon.getAttribute("tabindex")).toBeNull();
  });

  it("clique numa etapa ready navega (C-SHELL-02)", async () => {
    const { api } = renderNoShell(<Sidebar />);
    await userEvent.click(document.querySelector("#steps li.ready[data-id='mood']") as HTMLElement);
    expect(api.navigate).toHaveBeenCalledWith("mood");
  });

  it("Enter numa etapa focada navega (C-SHELL-03)", () => {
    const { api } = renderNoShell(<Sidebar />);
    const li = document.querySelector("#steps li.ready[data-id='base']") as HTMLElement;
    fireEvent.keyDown(li, { key: "Enter" });
    expect(api.navigate).toHaveBeenCalledWith("base");
  });

  it("#railCount mostra feitas/total; #projSel reflete as campanhas e o pid ativo", () => {
    renderNoShell(<Sidebar />);
    expect(document.querySelector("#railCount")!.textContent).toBe("1/4");
    const sel = document.querySelector("#projSel") as HTMLSelectElement;
    expect(within(sel).getAllByRole("option").map((o) => (o as HTMLOptionElement).value)).toEqual([
      "campanha-a",
      "campanha-b",
    ]);
    expect(sel.value).toBe("campanha-a");
  });

  it("trocar no #projSel navega para a campanha (C-OVERVIEW-05)", async () => {
    const { api } = renderNoShell(<Sidebar />);
    await userEvent.selectOptions(document.querySelector("#projSel") as HTMLSelectElement, "campanha-b");
    expect(api.selectProject).toHaveBeenCalledWith("campanha-b");
  });

  it("rótulo e botão de tema (C-SHELL-07)", async () => {
    const { api } = renderNoShell(<Sidebar />, mockShellApi({ tema: "dark" }));
    expect(document.querySelector("#themeLabel")!.textContent).toBe("tema: escuro");
    await userEvent.click(document.querySelector("#btnTheme") as HTMLElement);
    expect(api.cycleTheme).toHaveBeenCalled();
  });

  it("#hfChipSide existe para a Studio.ui.hfChip vanilla (C-SHELL-14)", () => {
    renderNoShell(<Sidebar />);
    expect(document.querySelector("#hfChipSide")).not.toBeNull();
  });

  it("sem campanha, #railCount é '—' e não há estado de etapa", () => {
    renderNoShell(<Sidebar />, mockShellApi({ pid: null, guideAll: null }));
    expect(document.querySelector("#railCount")!.textContent).toBe("—");
    expect(screen.queryByText("Referências")).not.toBeNull();
  });
});
