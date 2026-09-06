// Formas de dados do storyboard (etapa 4) que a tela React lê do backend. O backend não declara
// `response_model` nas rotas (o `/openapi.json` traz `schema: {}`), então o `ctx.api()` devolve
// `unknown`; estes tipos são o contrato que a tela assume ao ler cada resposta — os mesmos campos
// que o `view.js` vanilla lia. Nomes de campo em inglês, como no JSON do serviço.

export interface KindMeta {
  kind: string;
  label: string;
  ui_hint: string;
}
export interface ModelMeta {
  id: string;
  label: string;
  default?: boolean;
}
export interface ArcMeta {
  id: string;
  label: string;
  hint: string;
}
export interface InstructionsMeta {
  kinds: KindMeta[];
  models: ModelMeta[];
  arc: ArcMeta[];
  counts: { uncertain: number; tweak: number };
}

export interface SbStatus {
  has_base: boolean;
  ideas: number;
  selected: number;
  base_image: string;
  video_models?: string[];
  video_model_defaults?: { single: string; start_end: string };
  script_cli?: boolean;
  script_preset_default?: string;
  script_models?: { label?: string; default?: boolean }[];
}

export interface Idea {
  id: string;
  file: string;
  thumb?: string;
  prompt?: string;
  selected?: boolean;
}

export interface PhotoEntry {
  video_desc?: string;
  video_prompt?: string;
  videos?: string[];
}

export interface Scene {
  id: string | null;
  text: string;
  images: string[];
  primary: string | null;
  photos?: Record<string, PhotoEntry>;
  videos?: string[];
}

/** Estado por foto no ponto único da tela (o mapa `photoState` do vanilla). */
export interface PhotoMeta {
  desc: string;
  prompt: string;
  videos: string[];
  /** `null` = o usuário não mexeu no seletor → vale o default resolvido; string = escolha explícita. */
  preset: string | null;
}

export interface RealismPreset {
  id: string;
  name: string;
  desc_pt: string;
}

export interface ScriptScene {
  arc?: string;
  text?: string;
  image_prompt?: string;
  shot_prompts?: string[];
}
export interface Script {
  scenes?: ScriptScene[];
  generated_at?: string;
  preset?: string;
  aspect_ratio?: string;
  notes_pt?: string;
}

export interface HistoryItem {
  key: string;
  url: string;
  prompt?: string;
}

export interface AnnResult {
  id: string;
  file: string;
  deduped?: boolean;
}

// ----- ângulos por cena (metade 2) -----
export interface AngleScene {
  id: string;
  n?: number;
  text?: string;
  /** `[extensão]` geração por cena: prompt de imagem da cena (string vazia quando não há). */
  image_prompt?: string;
  base: string;
  base_ready: boolean;
  candidates: number;
  selected: number;
  upscaled: number;
}

/** `[extensão]` prontidão do motor local (ADR-033) — mesmo contrato do painel 01b. */
export interface LocalStatus {
  ready?: boolean;
  detail?: string;
}
export interface ProductScene {
  ref_ready: boolean;
  selected: boolean;
}
export interface Candidate {
  id: string;
  file: string;
  thumb?: string;
  prompt?: string;
  name?: string;
  source?: string;
  upscaled?: boolean;
  selected?: boolean;
  selected_order?: number;
}
export interface PromptOut {
  label: string;
  text: string;
}
