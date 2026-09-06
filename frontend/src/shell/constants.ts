// Constantes do shell — Wave 10 · E3 (card [REACT-04]).
//
// Portadas de `studio/web/app.js` sem alterar valor nenhum: os textos são conteúdo visível
// (ADR-004) e os ids de formato são contrato com o backend e com os cenários de QA.

/** Formatos de vídeo pela plataforma de destino (`app.js` ASPECTS). `w`/`h` desenham o selo. */
export const ASPECTS: readonly { id: string; dest: string; w: number; h: number }[] = [
  { id: "16:9", dest: "YouTube, tela cheia", w: 28, h: 16 },
  { id: "9:16", dest: "Reels, TikTok, Shorts", w: 11, h: 20 },
  { id: "1:1", dest: "Feed quadrado", w: 18, h: 18 },
];

/** Rótulo curto do formato para o chip da topbar (`app.js` ASPECT_LABEL). */
export const ASPECT_LABEL: Record<string, string> = {
  "16:9": "16:9 · YouTube",
  "9:16": "9:16 · Reels/TikTok",
  "1:1": "1:1 · feed",
};

/** Prefixo de rota reservado da biblioteca de mood boards (`app.js` MB_ROUTE, ADR-013). */
export const MB_ROUTE = "moodboards";
/** Prefixo de rota reservado de créditos & custos (`app.js` CR_ROUTE, ADR-016). */
export const CR_ROUTE = "creditos";
/** Prefixo de rota reservado da biblioteca de personagens (ADR-039). */
export const CHAR_ROUTE = "characters";

/** Rótulo do botão de tema por estado (`app.js` TEMA_LABEL). */
export const TEMA_LABEL: Record<string, string> = {
  auto: "tema: sistema",
  light: "tema: claro",
  dark: "tema: escuro",
};

/** Chaves de `localStorage` — contrato de usuário (recon §1.4). Links salvos continuam valendo. */
export const CHAVES_STORE = {
  tema: "studio.theme",
  pid: "studio.pid",
  view: "studio.view",
} as const;

/** Área ativa do shell (`app.js` `area`). */
export type Area = "campaign" | "moodboards" | "creditos" | "characters";
