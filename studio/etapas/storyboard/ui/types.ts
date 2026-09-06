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

/**
 * Procedência de UM campo da foto (`[extensão]` Wave 11 · F06, FDD §5.5). Metadado LENIENTE: o
 * backend descarta em silêncio o que não bate com o enum, nunca 422.
 */
export interface PhotoOrigin {
  /** `ia` (o Claude escreveu), `manual` (o usuário digitou) ou `template` (fallback sem CLI). */
  source: string;
  /** Preset de realismo RESOLVIDO na geração, ou `null` quando não houve preset. */
  preset: string | null;
  /** ISO 8601. */
  at: string;
}

export interface PhotoEntry {
  video_desc?: string;
  video_prompt?: string;
  image_prompt?: string;
  videos?: string[];
  /**
   * `[extensão]` preset de realismo por foto — TRÊS estados preservados literalmente
   * (invariante 6 do FDD): chave **AUSENTE** herda o default da ação, `null` é "sem preset" e
   * `"<id>"` é o id escolhido. Colapsar ausente em `null` apaga a rota de fuga do usuário.
   */
  preset?: string | null;
  /** `{campo: {source, preset, at}}`, com `campo ∈ {image_prompt, video_prompt}`. */
  origin?: Record<string, PhotoOrigin>;
}

export interface Scene {
  id: string | null;
  text: string;
  images: string[];
  primary: string | null;
  photos?: Record<string, PhotoEntry>;
  videos?: string[];
}

/**
 * Escolha de preset de realismo no cliente — os MESMOS três valores do `<select>` do
 * `RealismField`, para que a tela não precise de uma segunda tradução: `""` herda o padrão da
 * campanha (a chave sai AUSENTE do corpo e do arquivo), `"off"` é "sem preset" (vira `null`) e
 * qualquer outro valor é o id do catálogo. Invariante 6 do FDD.
 */
export type PresetChoice = string;

/** Estado por foto no ponto único da tela (o mapa `photoState` do vanilla). */
export interface PhotoMeta {
  desc: string;
  prompt: string;
  videos: string[];
  /** Três estados (`PresetChoice`): `""` herda · `"off"` sem preset · `"<id>"` esse id. */
  preset: PresetChoice;
  /** Procedência por campo, relida do servidor e reenviada no `PUT /scenes` seguinte. */
  origin: Record<string, PhotoOrigin>;
}

/**
 * `defaults` de `GET /api/prompter/presets?pid=` — preset resolvido por ação, com a camada que
 * venceu a cadeia projeto → global → código.
 */
export type PresetDefaults = Record<
  string,
  { preset?: string | null; source?: string } | undefined
>;

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
