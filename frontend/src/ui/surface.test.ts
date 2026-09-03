// Wave 10 · E2 — superfície da biblioteca de UI + catálogo de classes.
//
// Substituto Vitest da parte de `tests/test_api.py` que afirma (a) a superfície de `window.Studio.ui`
// e (b) o catálogo de classes que as telas consomem. Aquele teste checa o VANILLA por substring e
// segue vivo até a E10; este prova que a biblioteca React expõe os 28 membros (recon-wave-10 §2) e
// que o CSS copiado carrega o catálogo. Mapeamento vanilla → React de cada membro abaixo.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import * as ui from "./index";

// Lidas do disco (não `import` de CSS: o vitest roda com `css:false` e devolveria vazio). O cwd do
// runner é a pasta do projeto npm (`frontend/`), tanto em `make frontend-verify` quanto no CI.
const styleCss = readFileSync(resolve("src/styles/style.css"), "utf8");
const uiCss = readFileSync(resolve("src/styles/ui.css"), "utf8");

// 28 membros da `Studio.ui` (recon §2) → export React equivalente.
const SUPERFICIE: Record<string, unknown> = {
  esc: ui.esc, // 1
  fmtPct: ui.fmtPct, // 2  (dead code no vanilla, mas parte do contrato)
  chip: ui.Chip, // 3
  hfChip: ui.HfChip, // 4  (+ hfChipView)
  hfChipView: ui.hfChipView,
  drop: ui.useUpload, // 5
  upload: ui.upload, // 6  (reexporta apiUpload da E1)
  autosize: ui.useAutosize, // 7
  confirmCost: ui.useCostConfirm, // 8  (+ CostSheet)
  CostSheet: ui.CostSheet,
  defaultModel: ui.defaultModel, // 12
  refreshCredits: ui.refreshCredits, // 13 (+ CreditsChip/creditsView)
  CreditsChip: ui.CreditsChip,
  creditsView: ui.creditsView,
  poll: ui.poll, // 14 (+ usePoll)
  usePoll: ui.usePoll,
  modal: ui.Modal, // 15
  progress: ui.useProgress, // 16 (+ ProgressModal)
  ProgressModal: ui.ProgressModal,
  progressJob: ui.progressJob, // 17
  STATUS_LABEL: ui.STATUS_LABEL, // 18
  ITEM_LABEL: ui.ITEM_LABEL, // 19
  STATUS_KIND: ui.STATUS_KIND, // 20
  guide: ui.Guide, // 21
  tile: ui.Tile, // 22
  moodMosaic: ui.MoodMosaic, // 23
  pipe: ui.Pipe, // 24
  beats: ui.Beats, // 25
  copyBtn: ui.CopyButton, // 26 (o listener global de data-copy vira o onClick do componente)
  copy: ui.copy, // 27
  renderGuide: ui.StepGuide, // 28
};

describe("superfície da biblioteca de UI (recon §2 — nada pode faltar)", () => {
  it.each(Object.entries(SUPERFICIE))("expõe %s", (_nome, valor) => {
    expect(valor === undefined || valor === null).toBe(false);
  });

  it("os mapas de status têm os rótulos do vanilla", () => {
    expect(ui.STATUS_LABEL.in_progress).toBe("em andamento");
    expect(ui.ITEM_LABEL.fail).toBe("falta");
    expect(ui.STATUS_KIND.blocked).toBe("blocked");
  });
});

describe("catálogo de classes (cópia byte-a-byte de style.css/ui.css)", () => {
  const noStyle = [".chip", ".chip.ok", ".chip.warn", ".modal", ".pipe", ".beats", ".card"];
  it.each(noStyle)("style.css tem %s", (cls) => {
    expect(styleCss).toContain(cls);
  });

  const noUi = [
    ".modal-backdrop",
    ".modal-actions",
    ".progress-modal",
    ".prog-steps",
    ".prog-timer",
    ".cost-sheet",
    ".cost-row",
    ".mood-mosaic",
    ".mm-cell",
    ".guide-strip",
    ".guide-body",
    ".guide-items",
  ];
  it.each(noUi)("ui.css tem %s", (cls) => {
    expect(uiCss).toContain(cls);
  });

  it("ui.css usa os tokens do catálogo (claro/escuro de style.css)", () => {
    for (const t of ["var(--accent)", "var(--ok)", "var(--gate)"]) expect(uiCss).toContain(t);
    expect(uiCss).toContain("prog-spin");
  });
});
