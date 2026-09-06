// Biblioteca de UI do Orquestrador Studio — Wave 10 · E2 (card [REACT-03], ADR-031/ADR-032).
//
// Componentes e hooks React equivalentes ao `Studio.ui` do vanilla (`studio/web/ui.js`), com o
// MESMO contrato DOM (ids, classes, atributos ARIA) — os cenários de `scripts/qa/cenarios/` e o
// `ui.css`/`style.css` copiados em `../styles/` continuam sendo o oráculo. As telas migradas na
// sub-wave 5 (E4+) importam daqui em vez de recopiar componente.
//
// O POST multipart (`upload`) e o mapeamento de erro moram na camada de API (E1) e são reexportados
// por `useUpload`; nada de segunda cópia (ver `frontend/src/api/http.ts`).
export { esc, fmtPct } from "./text";

export { Chip } from "./Chip";
export type { ChipKind, ChipProps } from "./Chip";

export { STATUS_LABEL, ITEM_LABEL, STATUS_KIND } from "./status";

export { MoodMosaic } from "./MoodMosaic";
export type { MoodMosaicProps } from "./MoodMosaic";

export { Tile } from "./Tile";
export type { TileProps } from "./Tile";

export { Pipe } from "./Pipe";
export type { PipeProps } from "./Pipe";

export { Beats } from "./Beats";
export type { Beat, Cut, BeatsProps } from "./Beats";

export { CopyButton, copy } from "./CopyButton";
export type { CopyButtonProps } from "./CopyButton";

export { HfChip, hfChipView } from "./HfChip";
export type { HfChipProps } from "./HfChip";

export { CreditsChip, refreshCredits, defaultModel, creditsView } from "./credits";
export type { CreditsStatus, CreditsChipProps } from "./credits";

export { Guide, StepGuide } from "./Guide";
export type { GuideProps, StepGuideProps } from "./Guide";

export { Modal } from "./Modal";
export type { ModalAction, ModalProps } from "./Modal";

export { ProgressModal, useProgress, progressJob } from "./ProgressModal";
export type {
  ProgressHandle,
  ProgressState,
  ProgressStep,
  ProgressModalProps,
  ProgressJobOpts,
  Job,
} from "./ProgressModal";

export { CostSheet, useCostConfirm, avisoCli } from "./CostSheet";
export type { CostRow, CostSheetProps, RichCostOpts, SimpleCostOpts } from "./CostSheet";

// Fonte única das linhas do gate de custo (wave 11 · F10): o `CostSheet` das telas e o widget
// `confirm_cost` do dock renderizam o MESMO array. Só ganha exports; nada foi removido.
export { costRows, costWarn, saldoInsuficiente, NOTA_PADRAO } from "./costRows";
export type { CostInfoLike, CostWarn } from "./costRows";

export { useAutosize } from "./useAutosize";
export { usePoll, poll } from "./usePoll";
export type { PollFn, PollHandle } from "./usePoll";
export { useUpload, upload } from "./useUpload";
export type { UploadDropzone, CamposExtras } from "./useUpload";
