// Etapa 3 — Imagem base (aula 009) · Wave 10 · E7 (card [REACT-08]).
//
// Porte React da tela vanilla `studio/etapas/base/view.{html,js}` (918 LOC). REFATORAÇÃO PURA:
// mesmo DOM (ids/classes/atributos), mesmo comportamento e mesmos textos de aula (ADR-004 — o diff
// de `textContent` contra o baseline `-react-e0-v2` tem de ser vazio). A biblioteca de UI da E2
// (`frontend/src/ui`) e o contrato de host da E3 (`frontend/src/shell/plugin`) substituem o
// `Studio.ui`/`Studio.ctx` imperativos.
//
// O estado de domínio da tela (o closure do `Studio.register("base", …)`) vive num único `ref`
// mutável (`st`) e um `forceRender` dispara o re-render — o porte 1:1 do view.js imperativo, sem
// stale-closure. A ORDEM das interações do CLI é preservada: `confirmCost` antes de `progressJob`
// (o bot de prompts usa `progress` síncrono).
import { Fragment, useEffect, useReducer, useRef } from "react";

import {
  MoodMosaic,
  Tile,
  StepGuide,
  useProgress,
  useCostConfirm,
  progressJob,
  useUpload,
  useAutosize,
} from "../../../../frontend/src/ui";
import { useStudio } from "../../../../frontend/src/shell/plugin";
// O bloco "Padrão visual da campanha" é o MESMO das duas etapas (a ação `base` é uma das cinco
// que ele nivela). Ele é importado, nunca copiado: duas cópias divergiriam na primeira mudança.
import { CampaignPreset } from "../../storyboard/ui/CampaignPreset";
import type { PresetDefaults } from "../../storyboard/ui/types";
import { useShell } from "../../../../frontend/src/shell/context";
import { useStudioChange } from "../../../../frontend/src/shell/events";

// ---------- constantes espelhadas do view.js ----------
type Step = "situation" | "clean" | "label" | "upscale";

const KINDS: Record<Step, string> = {
  situation: "situação",
  clean: "limpeza de marca",
  label: "rótulo",
  upscale: "upscale",
};
// base-clean-marca [extensão] (wave 9): o passo "limpar marca" entra ENTRE situação e rótulo.
const CHAIN: readonly (readonly [Step, string])[] = [
  ["situation", "situação"],
  ["clean", "limpar marca"],
  ["label", "rótulo"],
  ["upscale", "upscale 2x"],
];
// Espelha o `COURSE_KINDS` do backend: os três passos da aula 009 (a limpeza fica de fora).
const COURSE_CHAIN = CHAIN.filter(([k]) => k !== "clean");
const SINCE_MINUTES = 120;
// Prompt fixo do rótulo por marca-imagem (espelha LABEL_IMAGE_PROMPT do backend).
const LABEL_PROMPT =
  "Apply the attached brand/logo image onto the product label. " +
  "Keep the product colors, shape and everything else identical, realistic.";
// Rótulo descritivo por linha (FDD §1) e o texto/cor de cada proveniência.
const PART_LABEL: Record<string, string> = {
  Composition: "referência (situação/enquadramento)",
  Lighting: "mood (luz)",
  "Color grading": "mood (cor/paleta)",
  Style: "mood (estética/atmosfera)",
  Camera: "técnico",
};
const FROM_LABEL: Record<string, string> = {
  reference: "referência",
  mood: "mood",
  technical: "técnico",
};

// ---------- formas de resposta do backend (só o que a tela lê) ----------
interface ProvPart {
  label: string;
  from: string;
  text: string;
}
interface Provenance {
  paragraph?: string;
  parts?: ProvPart[];
}
interface RefItem {
  ref_id: string;
  file: string;
  prompt: string;
  provenance?: Provenance | null;
}
interface Palette {
  colors: string[];
  note: string;
}
interface PromptsResp {
  refs: RefItem[];
  clean_prompt?: string | null;
  claude?: boolean;
  palette?: Palette;
  mood_files?: string[];
}
interface Candidate {
  id: string;
  kind: Step;
  selected?: boolean;
  thumb?: string;
  file: string;
  source: string;
  ref_id?: string;
  prompt?: string;
  name?: string;
  job_id?: string;
  /**
   * Candidata de ORIGEM deste passo (upscale/rótulo/limpeza), gravada pelo backend `[extensão]`.
   * `null` em `situation`, em candidatas antigas e quando o import não tinha origem selecionada —
   * nesse caso o antes/depois cai na heurística `originFor` (§9 critério 13 do FDD).
   */
  source_id?: string | null;
}
interface CandidatesResp {
  candidates: Candidate[];
  final?: string | null;
}
interface Board {
  id: string;
  name: string;
  count: number;
}
interface MoodSources {
  campaign: { count: number; files?: string[] };
  boards: Board[];
}
interface Preset {
  id: string;
  name: string;
  desc_pt: string;
}
interface PresetsResp {
  defaults?: PresetDefaults;
  presets?: Preset[];
}
interface CostResp {
  total: number | null;
  per_item: number | null;
}
interface ImportResp {
  added: number;
  warnings?: string[];
}
interface GenResp {
  source?: string;
  seconds?: number;
}

type Chain = Record<Step, string | null>;
type Slot = "panel01" | "panel03";

interface Estado {
  cands: Candidate[];
  sel: string | null;
  chain: Chain;
  finalRel: string | null;
  finalV: number;
  refs: RefItem[];
  cleanPrompt: string | null;
  claudeOk: boolean;
  // O chip do bot (#baseClaude) só muda no caminho de SUCESSO de loadPrompts, como no vanilla:
  // numa campanha sem referência (prompts 422) ele permanece no "bot: ?" inicial (ADR-004).
  claudeChipText: string;
  claudeChipCls: string;
  palette: Palette;
  moodFiles: string[];
  boardImgUrls: string[];
  promptsError: string | null;
  edits: Record<string, string>;
  refId: string;
  step: Step;
  stepTouched: boolean;
  moodSources: MoodSources | null;
  boardSel: string | null;
  presets: Preset[];
  presetValue: string;
  /** `defaults` resolvidos de TODAS as ações — o bloco do padrão da campanha lê o conjunto. */
  presetDefaults: PresetDefaults;
  brandFile: string | null;
  brandV: number;
  cleanTarget: string;
  instruction: string;
  cliCost: string;
  panel01Cost: string;
  downloadsTitle: string;
  resultIds: string[];
  resultKind: Step;
  genBusy: "prompt" | "noBias" | null;
  copied: boolean;
  guiaNonce: number;
}

function estadoInicial(): Estado {
  return {
    cands: [],
    sel: null,
    chain: { situation: null, clean: null, label: null, upscale: null },
    finalRel: null,
    finalV: 0,
    refs: [],
    cleanPrompt: null,
    claudeOk: false,
    claudeChipText: "bot: ?",
    claudeChipCls: "chip mode",
    palette: { colors: [], note: "" },
    moodFiles: [],
    boardImgUrls: [],
    promptsError: null,
    edits: {},
    refId: "",
    step: "situation",
    stepTouched: false,
    moodSources: null,
    boardSel: null,
    presets: [],
    presetValue: "",
    presetDefaults: {},
    brandFile: null,
    brandV: 0,
    cleanTarget: "",
    instruction: "",
    cliCost: "",
    panel01Cost: "",
    downloadsTitle: "",
    resultIds: [],
    resultKind: "situation",
    genBusy: null,
    copied: false,
    guiaNonce: 0,
  };
}

function errMsg(e: unknown): string {
  return (e as Error)?.message || String(e);
}

/**
 * Entrada da tela: um wrapper com `key={pid}` para que a troca de campanha REMONTE a etapa —
 * o `onProject` do vanilla vira o efeito de mount (recon §1.3, contrato de host da E3).
 */
export default function BaseScreen() {
  const ctx = useStudio();
  const pid = ctx.pid();
  return <BaseInner key={pid ?? "sem-campanha"} pid={pid} />;
}

function BaseInner({ pid }: { pid: string | null }) {
  const ctx = useStudio();
  const shell = useShell();
  const [, forceRender] = useReducer((x: number) => x + 1, 0);
  const stRef = useRef<Estado | null>(null);
  if (stRef.current === null) stRef.current = estadoInicial();
  const st = stRef.current;

  const [prog, progEl] = useProgress();
  const { confirm, element: costEl } = useCostConfirm();

  const url = (p: string) => `/api/projects/${pid}/base/${p}`;

  // ---------- leitura do card de prompt (painel 01) ----------
  function cardInfo(): { label: string; text: string; key: string } | null {
    const f = st.refs.find((r) => r.ref_id === st.refId) || st.refs[0];
    if (st.step === "clean" && st.cleanPrompt !== null) {
      return { label: "Prompt · limpar marca · editável", text: st.cleanPrompt, key: "clean" };
    }
    if (st.step === "label") {
      return { label: "Prompt · rótulo · editável", text: LABEL_PROMPT, key: "label" };
    }
    if (f) return { label: "Prompt · situação · editável", text: f.prompt, key: `p:${f.ref_id}` };
    return null;
  }

  // O texto EDITADO na tela é o que vale (B4): só existe para o card do passo ativo.
  function promptText(key: string): string {
    const ci = cardInfo();
    if (!ci || ci.key !== key) return "";
    return st.edits[key] ?? ci.text;
  }

  function importPrompt(kind: Step = st.step): string {
    if (kind === "upscale") return "";
    if (kind === "clean") return promptText("clean");
    if (kind === "label") return promptText("label");
    const live = promptText(`p:${st.refId}`);
    if (live) return live;
    const f = st.refs.find((r) => r.ref_id === st.refId) || st.refs[0];
    return f ? f.prompt : "";
  }

  function realismPreset(): string | null {
    return st.presetValue || null;
  }

  // Descarta o texto editado quando o backend traz um texto novo que deve mandar (C-BASE-09).
  function descartarEdicao(chave?: string) {
    if (chave) delete st.edits[chave];
    else st.edits = {};
  }

  function currentMoodThumbs(): string[] {
    if (st.boardSel) return st.boardImgUrls;
    return (st.moodFiles || []).map((f) => ctx.files(f));
  }

  function refreshGuide() {
    st.guiaNonce += 1;
    forceRender();
  }

  // ---------- carregamentos ----------
  async function loadPrompts(): Promise<void> {
    st.refs = [];
    st.cleanPrompt = null;
    try {
      const r = (await ctx.api(url("prompts"))) as PromptsResp;
      st.refs = r.refs;
      st.cleanPrompt = r.clean_prompt || null;
      st.claudeOk = !!r.claude;
      st.claudeChipText = st.claudeOk ? "bot: claude ok" : "bot: sem claude";
      st.claudeChipCls = st.claudeOk ? "chip ok" : "chip warn";
      st.palette = r.palette || { colors: [], note: "" };
      st.moodFiles = r.mood_files || [];
      st.promptsError = null;
      const first = st.refs[0];
      st.refId = st.refs.some((f) => f.ref_id === st.refId) ? st.refId : first ? first.ref_id : "";
      forceRender();
    } catch (err) {
      st.refs = [];
      st.promptsError = errMsg(err);
      forceRender();
    }
  }

  function selectRef(id: string) {
    st.refId = id || "";
    forceRender();
  }

  async function loadRealismPresets(): Promise<void> {
    try {
      const r = (await ctx.api(`/api/prompter/presets?pid=${encodeURIComponent(pid ?? "")}`)) as PresetsResp;
      st.presets = r.presets || [];
      st.presetDefaults = r.defaults || {};
      const def = (st.presetDefaults["base"] || {}).preset || "";
      st.presetValue = st.presets.some((p) => p.id === def) ? def : "";
      forceRender();
    } catch {
      st.presets = [];
      st.presetValue = "";
      st.presetDefaults = {};
      forceRender();
    }
  }

  async function loadBrand(): Promise<void> {
    const b = (await ctx.api(url("brand-image")).catch(() => ({}))) as { file?: string };
    st.brandFile = b && b.file ? b.file : null;
    st.brandV = Date.now();
    forceRender();
  }

  async function uploadBrand(file?: File): Promise<void> {
    if (!file) return;
    try {
      const body = (await ctx.apiUpload(url("brand-image"), [file], "file", {})) as { file?: string };
      st.brandFile = body && body.file ? body.file : null;
      st.brandV = Date.now();
      forceRender();
      refreshGuide();
      void loadPrompts();
    } catch (err) {
      ctx.toast(errMsg(err));
    }
  }

  // ---------- passo "limpar marca" [extensão] ----------
  async function loadValidatedBrand(): Promise<void> {
    try {
      const r = (await ctx.api(`/api/projects/${pid}/refs/validated-brand`)) as { brand?: string };
      if (r && r.brand) {
        st.cleanTarget = r.brand;
        forceRender();
      }
    } catch {
      /* sem marca validada (ou rota indisponível): o campo fica vazio e o usuário digita */
    }
  }

  // ---------- mood de referência [extensão] (ADR-013) ----------
  async function loadMoodSources(): Promise<void> {
    try {
      st.moodSources = (await ctx.api(url("mood-sources"))) as MoodSources;
    } catch {
      st.moodSources = { campaign: { files: [], count: 0 }, boards: [] };
    }
    if (st.boardSel && !st.moodSources.boards.some((b) => b.id === st.boardSel)) st.boardSel = null;
    await renderMoodSourceGallery();
  }

  async function renderMoodSourceGallery(): Promise<void> {
    if (!st.boardSel) {
      st.boardImgUrls = [];
      forceRender();
      return;
    }
    try {
      const d = (await ctx.api(`/api/moodboards/${encodeURIComponent(st.boardSel)}`)) as { images: string[] };
      const board = st.boardSel;
      st.boardImgUrls = d.images.map((rel) => `/mbfiles/${encodeURIComponent(board)}/${rel}`);
    } catch (e) {
      st.boardImgUrls = [];
      ctx.toast(errMsg(e));
    }
    forceRender();
  }

  // ---------- candidatas (painel 03) ----------
  async function load(): Promise<Candidate[]> {
    if (!pid) {
      st.cands = [];
      st.finalRel = null;
      forceRender();
      return [];
    }
    const r = (await ctx.api(url("candidates"))) as CandidatesResp;
    st.cands = r.candidates;
    const novoFinal = r.final || null;
    if (novoFinal !== st.finalRel) st.finalV = Date.now();
    st.finalRel = novoFinal;
    const novaChain: Chain = { situation: null, clean: null, label: null, upscale: null };
    st.cands.filter((c) => c.selected).forEach((c) => {
      novaChain[c.kind] = c.id;
    });
    st.chain = novaChain;
    if (st.sel && !st.cands.some((c) => c.id === st.sel)) st.sel = null;
    if (!st.stepTouched) {
      // O passo ativo default segue a cadeia da AULA (`COURSE_CHAIN`): a limpeza é opcional.
      const proximo = COURSE_CHAIN.find(([k]) => !novaChain[k]);
      const novo: Step = proximo ? proximo[0] : "upscale";
      if (novo !== st.step) st.step = novo;
    }
    forceRender();
    return st.cands;
  }

  function setStep(k: Step) {
    if (!k || k === st.step) return;
    st.step = k;
    st.stepTouched = true;
    st.resultIds = []; // o resultado é do passo anterior
    forceRender();
  }

  async function afterImport(r: ImportResp, before: Set<string>): Promise<void> {
    (r.warnings || []).forEach((w) => ctx.toast(w));
    ctx.toast(`${r.added} imagem(ns) importada(s)`);
    const novas = await load();
    showResult(novas.filter((c) => !before.has(c.id)).map((c) => c.id));
    refreshGuide();
  }

  async function importar(files: FileList): Promise<void> {
    if (!files.length) return;
    const before = new Set(st.cands.map((c) => c.id));
    try {
      const extra: Record<string, string> = { kind: st.step, prompt: importPrompt() };
      if (st.refId) extra.ref_id = st.refId;
      const body = (await ctx.apiUpload(url("import/upload"), files, "files", extra)) as ImportResp;
      await afterImport(body, before);
    } catch (err) {
      ctx.toast(errMsg(err));
    }
  }

  // ---------- geração paga via CLI [extensão] ----------
  function genBody(kind: Step = st.step): Record<string, unknown> {
    const body: Record<string, unknown> = {
      kind,
      ref_ids: kind === "situation" && st.refId ? [st.refId] : null,
      prompt: importPrompt(kind),
    };
    if (kind === "clean") {
      body.target = st.cleanTarget.trim();
      if (body.prompt === st.cleanPrompt) body.prompt = "";
    }
    return body;
  }

  function originFor(kind: Step): { url: string; label: string } | null {
    if (kind === "upscale") {
      const c = st.cands.find((x) => x.id === (st.chain.label || st.chain.clean || st.chain.situation));
      return c ? { url: ctx.files(c.file), label: KINDS[c.kind] || c.kind } : null;
    }
    if (kind === "label") {
      const c = st.cands.find((x) => x.id === (st.chain.clean || st.chain.situation));
      return c ? { url: ctx.files(c.file), label: KINDS[c.kind] || c.kind } : null;
    }
    if (kind === "clean") {
      const c = st.cands.find((x) => x.id === st.chain.situation);
      return c ? { url: ctx.files(c.file), label: "situação" } : null;
    }
    const f = st.refs.find((r) => r.ref_id === st.refId) || st.refs[0];
    return f ? { url: ctx.files(f.file), label: "referência" } : null;
  }

  // O "antes" do par é da CANDIDATA, não da cadeia selecionada agora: `source_id` diz de que
  // candidata este passo saiu, então o par continua certo mesmo que a seleção mude depois (ou que o
  // resultado tenha vindo do chat). Sem `source_id` — candidata antiga, `situation`, import sem
  // origem — vale a heurística de sempre. §9 critério 13 do FDD. `[extensão]`
  function originDe(c: Candidate): { url: string; label: string } | null {
    if (c.source_id) {
      const src = st.cands.find((x) => x.id === c.source_id);
      if (src) return { url: ctx.files(src.file), label: KINDS[src.kind] || src.kind };
    }
    return originFor(st.resultKind);
  }

  function showResult(newIds: string[], kind: Step = st.step): void {
    const results = st.cands.filter((c) => newIds.includes(c.id));
    if (!results.length) {
      st.resultIds = [];
      forceRender();
      return;
    }
    st.resultIds = newIds;
    st.resultKind = kind;
    forceRender();
  }

  async function gerarPrompt(noBias: boolean): Promise<void> {
    const usaBot = noBias || st.claudeOk;
    const body = {
      ref_id: st.refId || null,
      mode: usaBot ? "images" : "template",
      instruction: st.instruction,
      no_bias: !!noBias,
      no_people: false,
      board: st.boardSel,
      preset: realismPreset(),
    };
    const gen = () =>
      ctx.api(url("prompts/generate"), { method: "POST", body: JSON.stringify(body) }) as Promise<GenResp>;
    const aplicar = async (e: GenResp) => {
      ctx.toast(`Prompt ${e.source === "claude" ? "escrito pelo bot" : "do template"} (${e.seconds || 0}s)`);
      descartarEdicao(); // o texto novo do bot manda
      await loadPrompts();
      refreshGuide();
    };
    if (!usaBot) {
      try {
        await aplicar(await gen());
      } catch (err) {
        ctx.toast(errMsg(err));
      }
      return;
    }
    prog.progress({
      title: noBias ? "Gerar prompt sem viés" : "Gerar prompt da base",
      subtitle: "Bot de prompts (Claude) — aula 009",
    });
    prog.step(
      noBias ? "Preparando referência + mood (sessão nova, sem o prompt anterior)" : "Preparando referência + mood",
    );
    prog.step("Consultando o Claude…");
    st.genBusy = noBias ? "noBias" : "prompt";
    forceRender();
    try {
      const e = await gen();
      prog.step("Formatando no padrão do bot");
      await aplicar(e);
      prog.ok("Pronto");
      setTimeout(() => prog.close(), 700);
    } catch (err) {
      prog.fail(errMsg(err));
      ctx.toast(errMsg(err));
    }
    st.genBusy = null;
    forceRender();
  }

  async function gerarViaCli(kind: Step, slot: Slot): Promise<void> {
    const label = KINDS[kind] || kind;
    const body = genBody(kind);
    const setCost = (t: string) => {
      if (slot === "panel03") st.cliCost = t;
      else st.panel01Cost = t;
      forceRender();
    };
    let cost: CostResp | null = null;
    setCost("consultando custo…");
    try {
      cost = (await ctx.api(url("cost"), { method: "POST", body: JSON.stringify(body) })) as CostResp;
    } catch {
      cost = null;
    }
    if (!cost || cost.total == null) {
      setCost("custo indisponível (sem login)");
      ctx.toast(
        "Faça login no Higgsfield (higgsfield auth login) para gerar via CLI e ver o custo. " +
          "Você também pode gerar na UI ilimitada do Higgsfield e importar aqui.",
      );
      return;
    }
    const cotado = cost;
    setCost(`${label}: ${cotado.total} créditos (${cotado.per_item}/item)`);
    if (!(await confirm({ costFn: () => cotado, label: `Gerar ${label} via CLI` }))) return;
    const before = new Set(st.cands.map((c) => c.id));
    try {
      await progressJob(prog, {
        title: `Gerar ${label} via CLI`,
        subtitle: `Higgsfield CLI · custo estimado ${cotado.total} créditos (${cotado.per_item}/item)`,
        start: () => ctx.api(url("generate"), { method: "POST", body: JSON.stringify(body) }),
        jobUrl: url("job"),
        label: "Geração concluída",
        done: () => load(),
      });
      showResult(st.cands.filter((c) => !before.has(c.id)).map((c) => c.id), kind);
      refreshGuide();
    } catch (err) {
      ctx.toast(errMsg(err));
    }
  }

  // ---------- efeito de mount = onProject do vanilla ----------
  useEffect(() => {
    if (!pid) return;
    void loadBrand();
    void loadValidatedBrand();
    void loadMoodSources();
    void loadRealismPresets();
    void loadPrompts().then(() => load());
    void ctx.api("/api/mood/downloads-folder").then((raw) => {
      const d = raw as { folder: string; exists: boolean };
      st.downloadsTitle = `Últimos ${SINCE_MINUTES} min de ${d.folder}${d.exists ? "" : " (não encontrada)"}`;
      forceRender();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  // ---------- sincronização com o chat `[extensão]` (Wave 11 · F03) ----------
  // `base_generate` e `base_pick` escrevem as candidatas desta etapa por fora da tela. Reusamos o
  // `load()` do painel 03, que é idempotente e já reconstrói cadeia, seleção e passo ativo.
  // Só ele: `loadPrompts()` alimenta o textarea do painel 02, e recarregar campo de texto em
  // edição é exatamente o que a §10 Risco 5 do FDD proíbe.
  useStudioChange(
    "base",
    () => {
      void load().catch(() => {
        /* aviso do chat é best-effort: falha de rede aqui não pode derrubar a tela */
      });
    },
    { pid },
  );

  // ---------- drag & drop do painel 03 ----------
  // `useUpload` da E2 cuida do <input type=file> (#baseUpload) — reset de `value`, seleção múltipla.
  // O drag é tratado à mão sobre um `ref` porque o cenário de QA (`base.py` C-BASE-21) lê
  // `el.classList.contains("over")` SÍNCRONO logo após despachar `dragover`, e o `useState(isOver)`
  // do hook só reflete a classe no próximo render (assíncrono) — o `ui.drop` vanilla adicionava a
  // classe imperativamente, na hora. Aqui reproduzimos esse contrato DOM.
  const drop = useUpload(importar, { multiple: true });
  const baseDropRef = useRef<HTMLLabelElement>(null);

  // ---------- render ----------
  const heroRef = st.refs.find((r) => r.ref_id === st.refId) || st.refs[0];
  const juncaoRef = st.step === "label" || st.step === "clean" ? undefined : heroRef;
  const prov = heroRef && st.step !== "label" && st.step !== "clean" ? heroRef.provenance : null;
  const ci = cardInfo();
  const brandHas = !!st.brandFile;
  const results = st.cands.filter((c) => st.resultIds.includes(c.id));
  const depoisLbl = KINDS[st.resultKind] || st.resultKind;
  const stepsParaGuia = shell.steps.map((s) => ({ id: s.id, n: s.n }));

  const onCopy = async () => {
    const ta = document.querySelector<HTMLTextAreaElement>("#basePrompts textarea");
    if (!ta) return;
    await navigator.clipboard.writeText(ta.value);
    st.copied = true;
    forceRender();
    setTimeout(() => {
      st.copied = false;
      forceRender();
    }, 1500);
  };

  return (
    <>
      <style>{BASE_CSS}</style>

      <header className="stephead">
        <span className="eyebrow">Etapa 3 · aula 009</span>
        <h2>Imagem base</h2>
        <p className="lede">
          O bot olha a referência e o seu mood e escreve o prompt do produto na{" "}
          <b>exata mesma situação</b> da referência. Cadeia: situação → limpar marca (opcional,
          [extensão]) → rótulo → upscale 2x.
        </p>
        <button
          type="button"
          className="shell-reset ghost"
          title="Apaga o que esta etapa e as seguintes produziram; mantém nome, produto, vibe e formato"
          onClick={() => shell.confirmResetStep("base")}
        >
          Resetar etapa [extensão]
        </button>
      </header>

      <section id="guide" className="guide">
        <StepGuide
          key={st.guiaNonce}
          stepId="base"
          pid={pid}
          steps={stepsParaGuia}
          onGo={shell.go}
          onGuide={ctx.onGuide}
        />
      </section>

      {pid ? (
        <CampaignPreset
          id="baseCampaignPreset"
          api={ctx.api}
          pid={pid}
          toast={ctx.toast}
          presets={st.presets}
          defaults={st.presetDefaults}
          onReload={(d) => {
            st.presetDefaults = d;
            const def = (d["base"] || {}).preset || "";
            st.presetValue = st.presets.some((p) => p.id === def) ? def : "";
            forceRender();
          }}
        />
      ) : null}

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">01</span>O prompt da aula — quem escreve é o bot
          </h3>
          <span id="baseClaude" className={st.claudeChipCls}>
            {st.claudeChipText}
          </span>
        </div>
        <div className="bs-p1grid">
          <div className="bs-p1-left">
            <div className="refpick bs-refpick">
              <span className="eyebrow lbl">Referência (etapa 1) — clique para escolher</span>
              <div id="baseRefHero" className="bs-refhero">
                {heroRef ? (
                  <img
                    src={ctx.files(heroRef.file)}
                    alt={`referência ${heroRef.ref_id} (selecionada)`}
                    loading="lazy"
                  />
                ) : null}
              </div>
              <div id="refGallery" className="gallery xs">
                {st.refs.map((f) => (
                  <div
                    key={f.ref_id}
                    className={`card${f.ref_id === st.refId ? " sel" : ""}`}
                    data-ref={f.ref_id}
                    tabIndex={0}
                    title={`referência ${f.ref_id}`}
                    onClick={() => selectRef(f.ref_id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") selectRef(f.ref_id);
                    }}
                  >
                    <img src={ctx.files(f.file)} alt={`referência ${f.ref_id}`} loading="lazy" />
                  </div>
                ))}
              </div>
            </div>
            <div id="baseJunction" className="bs-junction" style={juncaoRef ? undefined : { display: "none" }}>
              {juncaoRef ? (
                <>
                  <div className="bs-fuse" title="O prompt funde a situação da referência com a vibe do mood">
                    <figure className="bs-fuse-item">
                      <img
                        className="bs-fuse-thumb"
                        src={ctx.files(juncaoRef.file)}
                        alt={`referência ${juncaoRef.ref_id}`}
                        loading="lazy"
                      />
                      <figcaption className="bs-fuse-cap">referência</figcaption>
                    </figure>
                    <span className="bs-fuse-op">+</span>
                    <figure className="bs-fuse-item bs-fuse-mood">
                      <MoodMosaic urls={currentMoodThumbs()} />
                      <figcaption className="bs-fuse-cap">mood</figcaption>
                    </figure>
                    <span className="bs-fuse-arrow">→</span>
                    <span className="bs-fuse-out">prompt</span>
                  </div>
                  <div className="row wrap bs-moodhead">
                    <span className="eyebrow lbl">🎨 Fonte do mood</span>
                    <span className="ext">[extensão]</span>
                  </div>
                  <select
                    id="moodSource"
                    title="qual mood o bot usa como referência de estilo"
                    value={st.boardSel ?? ""}
                    onChange={(e) => {
                      st.boardSel = e.target.value || null;
                      forceRender();
                      void renderMoodSourceGallery();
                    }}
                  >
                    <option value="">{`Mood da campanha (${(st.moodSources?.campaign.count ?? 0)} img)`}</option>
                    {(st.moodSources?.boards ?? []).map((b) => (
                      <option key={b.id} value={b.id}>{`Board: ${b.name} (${b.count} img) [extensão]`}</option>
                    ))}
                  </select>
                  {st.palette.colors.length ? (
                    <div className="swatches">
                      {st.palette.colors.slice(0, 8).map((c, i) => (
                        <span key={i} className="sw" style={{ background: c }} title={c} />
                      ))}
                    </div>
                  ) : null}
                  <p className="fine bs-mood-note">
                    A <b>situação</b> vem da referência; a <b>vibe, luz e cor</b> vêm do mood (campanha ou um
                    mood board). O prompt ao lado é a <b>junção</b> dos dois.
                  </p>
                </>
              ) : null}
            </div>
          </div>
          <div className="bs-p1-right">
            <div className="row wrap bs-instr">
              <input
                id="promptInstruction"
                className="grow"
                placeholder="o que muda nesta referência"
                value={st.instruction}
                onChange={(e) => {
                  st.instruction = e.target.value;
                  forceRender();
                }}
              />
              <button
                id="btnPrompt"
                className="primary"
                disabled={st.genBusy === "prompt"}
                onClick={() => gerarPrompt(false)}
              >
                {st.genBusy === "prompt" ? "Perguntando ao bot…" : "Gerar prompt"}
              </button>
              <button
                id="btnPromptNoBias"
                className="ghost"
                title="Sessão nova do bot, sem nada sobre a campanha"
                disabled={st.genBusy === "noBias"}
                onClick={() => gerarPrompt(true)}
              >
                {st.genBusy === "noBias" ? "Perguntando ao bot (sessão nova)…" : "Gerar sem viés"}
              </button>
            </div>
            <label className="field bs-preset">
              <span className="eyebrow lbl">
                Preset de realismo <span className="ext">[extensão]</span>
              </span>
              <select
                id="baseRealismPreset"
                aria-label="Preset de realismo (extensão)"
                value={st.presetValue}
                onChange={(e) => {
                  st.presetValue = e.target.value;
                  forceRender();
                }}
              >
                <option value="">(sem preset)</option>
                {st.presets.map((p) => (
                  <option key={p.id} value={p.id} title={p.desc_pt}>{`${p.name} — ${p.desc_pt}`}</option>
                ))}
              </select>
            </label>
            <div id="basePrompts" className="prompts one bs-one">
              {st.promptsError ? (
                <div className="empty">{st.promptsError}</div>
              ) : ci ? (
                <div className="prompt">
                  <div className="row">
                    <span className="eyebrow">{ci.label}</span>
                    <button type="button" className="link copy" data-k={ci.key} onClick={onCopy}>
                      Copiar
                    </button>
                    <span className="ok">{st.copied ? "copiado ✓" : ""}</span>
                  </div>
                  <PromptTextarea
                    value={st.edits[ci.key] ?? ci.text}
                    dataK={ci.key}
                    label={ci.label}
                    onChange={(v) => {
                      st.edits[ci.key] = v;
                      forceRender();
                    }}
                  />
                </div>
              ) : null}
            </div>
            <div className="row wrap bs-p1cli">
              <button id="btnBasePanel01Cli" className="primary" onClick={() => gerarViaCli("situation", "panel01")}>
                Gerar via CLI
              </button>
              <span className="ext">[extensão]</span>
              <span id="basePanel01CliCost" className="fine">
                {st.panel01Cost}
              </span>
            </div>
            <div id="baseProvenance" className="bs-prov" style={prov ? undefined : { display: "none" }}>
              {prov ? (
                <details className="bs-prov-det">
                  <summary>
                    <span className="eyebrow lbl">De onde vem cada parte</span> <span className="ext">[extensão]</span>
                  </summary>
                  <div className="bs-prov-body">
                    {prov.paragraph || (prov.parts && prov.parts.length) ? (
                      <>
                        {prov.paragraph ? (
                          <div className="prov-line">
                            <span className="bs-chip from-join">junção</span>
                            <span className="prov-text">
                              <b>produto da referência na vibe do mood.</b> {prov.paragraph}
                            </span>
                          </div>
                        ) : null}
                        {(prov.parts || []).map((p, i) => {
                          const desc = PART_LABEL[p.label] || FROM_LABEL[p.from] || p.from;
                          return (
                            <div className="prov-line" key={i}>
                              <span className={`bs-chip from-${p.from}`}>{FROM_LABEL[p.from] || p.from}</span>
                              <span className="prov-text">
                                <b>{p.label}</b> <span className="fine">({desc})</span> — {p.text}
                              </span>
                            </div>
                          );
                        })}
                      </>
                    ) : (
                      <p className="fine">Prompt fora do formato de 5 linhas — copie o texto completo acima.</p>
                    )}
                  </div>
                </details>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">02</span>Marca do rótulo <span className="ext">[extensão]</span>
          </h3>
        </div>
        <p className="fine">
          Anexe a <b>imagem da sua marca</b> (a logo/rótulo que você criou, ex.: no Higgsfield). Ela é aplicada na
          imagem base ao gerar o rótulo — sem descrever a marca por texto.
        </p>
        <div className="row wrap bs-brand">
          <label className={brandHas ? "drop has" : "drop"} id="brandDrop">
            Arraste a imagem da marca ou{" "}
            <input
              id="brandImage"
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => {
                const f = e.target.files && e.target.files[0];
                e.target.value = "";
                descartarEdicao("label");
                void uploadBrand(f ?? undefined);
              }}
            />
            <u>escolha um arquivo</u>
          </label>
          <img
            id="brandPreview"
            className="bs-brand-preview"
            alt="marca anexada"
            hidden={!brandHas}
            {...(brandHas && st.brandFile
              ? { src: `${ctx.files(`base/${st.brandFile}`)}?v=${st.brandV}` }
              : {})}
          />
          <button
            id="btnBrandClear"
            className="ghost"
            hidden={!brandHas}
            onClick={async () => {
              await ctx.api(url("brand-image"), { method: "DELETE" }).catch(() => ({}));
              st.brandFile = null;
              forceRender();
              descartarEdicao("label");
              await loadPrompts();
              refreshGuide();
            }}
          >
            Remover marca
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">03</span>Escolher e fechar a imagem base
          </h3>
          <button
            id="btnBaseSelect"
            className="ghost"
            disabled={!st.sel}
            onClick={async () => {
              if (!st.sel) return;
              try {
                const r = (await ctx.api(url("select"), {
                  method: "POST",
                  body: JSON.stringify({ id: st.sel }),
                })) as { final: string; kind: string };
                ctx.toast(`Imagem base: ${r.final} (${KINDS[r.kind as Step] || r.kind})`);
                await loadPrompts();
                void load();
                refreshGuide();
              } catch (err) {
                ctx.toast(errMsg(err));
              }
            }}
          >
            Usar como imagem base
          </button>
        </div>
        <div id="baseChain" className="stepper">
          {CHAIN.map(([k, rotulo], i) => {
            const escolhida = st.chain[k] ? `${rotulo}: ${st.chain[k]}` : `${rotulo}: ainda não escolhido`;
            const t = `${escolhida} — clique para importar neste passo`;
            const cls = k === st.step ? (st.chain[k] ? "st on done" : "st on") : st.chain[k] ? "st done" : "st";
            return (
              <Fragment key={k}>
                {i > 0 ? <span className="sep" /> : null}
                <span
                  className={cls}
                  data-step={k}
                  role="button"
                  tabIndex={0}
                  title={t}
                  onClick={() => setStep(k)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setStep(k);
                    }
                  }}
                >
                  <i>{i + 1}</i>
                  {rotulo}
                </span>
              </Fragment>
            );
          })}
        </div>
        <div id="baseCleanStep" className="bs-clean" style={st.step === "clean" ? undefined : { display: "none" }}>
          <div className="row wrap bs-clean-head">
            <span className="eyebrow lbl">Limpar a marca da embalagem antes do rótulo</span>
            <span className="ext">[extensão]</span>
          </div>
          <div className="row wrap bs-clean-row">
            <input
              id="cleanTarget"
              className="grow"
              aria-label="marca a remover da imagem"
              placeholder="marca a remover (vem da marca validada da etapa 1 — dá para editar ou apagar)"
              value={st.cleanTarget}
              onChange={(e) => {
                st.cleanTarget = e.target.value;
                forceRender();
              }}
            />
            <button
              id="btnCleanToLabel"
              className="ghost"
              title="Ir para o passo do rótulo e aplicar a sua marca"
              onClick={() => setStep("label")}
            >
              Trocar pela minha marca
            </button>
          </div>
          <p className="fine bs-clean-warn">
            A limpeza é uma aproximação por prompt (o Nano Banana não faz inpaint com máscara): gere 3 e escolha a
            melhor.
          </p>
        </div>
        <div className="row wrap stretch bs-io">
          <label
            ref={baseDropRef}
            className="drop"
            id="baseDrop"
            onDragOver={(e) => {
              e.preventDefault();
              baseDropRef.current?.classList.add("over");
            }}
            onDragLeave={() => baseDropRef.current?.classList.remove("over")}
            onDrop={(e) => {
              e.preventDefault();
              baseDropRef.current?.classList.remove("over");
              const f = e.dataTransfer?.files;
              if (f && f.length) void importar(f);
            }}
          >
            Arraste o grid gerado na UI ou <input {...drop.inputProps} id="baseUpload" accept="image/*" />
            <u>escolha arquivos</u>
          </label>
          <div className="col">
            <button
              id="btnBaseDownloads"
              className="ghost"
              title={st.downloadsTitle}
              onClick={async () => {
                const before = new Set(st.cands.map((c) => c.id));
                try {
                  const body = (await ctx.api(url("import/downloads"), {
                    method: "POST",
                    body: JSON.stringify({
                      since_minutes: SINCE_MINUTES,
                      kind: st.step,
                      ref_id: st.refId || null,
                      prompt: importPrompt(),
                    }),
                  })) as ImportResp;
                  await afterImport(body, before);
                } catch (err) {
                  ctx.toast(errMsg(err));
                }
              }}
            >
              Importar da pasta Downloads
            </button>
            <button
              id="btnBaseHistory"
              className="ghost"
              onClick={async () => {
                const before = new Set(st.cands.map((c) => c.id));
                try {
                  const body = (await ctx.api(url("import/history"), {
                    method: "POST",
                    body: JSON.stringify({ kind: st.step, ref_id: st.refId || null }),
                  })) as ImportResp;
                  await afterImport(body, before);
                } catch (err) {
                  ctx.toast(errMsg(err));
                }
              }}
            >
              Importar do histórico Higgsfield
            </button>
          </div>
        </div>
        <div className="row wrap bs-cli">
          <button id="btnBaseCli" className="primary" onClick={() => gerarViaCli(st.step, "panel03")}>
            {`Gerar ${KINDS[st.step] || st.step} via CLI`}
          </button>
          <span className="ext">[extensão]</span>
          <span id="baseCliCost" className="fine">
            {st.cliCost}
          </span>
        </div>
        <p className="fine bs-hf">
          Você também pode fazer no <b>Higgsfield (UI ilimitada)</b>: gere lá e importe aqui. O CLI é o caminho pago
          (gasta crédito por passo — o upscale custa diferente).
        </p>
        <div
          id="baseGallery"
          className="gallery sm"
          onClick={(e) => {
            const card = (e.target as HTMLElement).closest<HTMLElement>(".card");
            if (!card) return;
            const id = card.dataset.id ?? null;
            st.sel = st.sel === id ? null : id;
            forceRender();
          }}
          onDoubleClick={(e) => {
            const card = (e.target as HTMLElement).closest<HTMLElement>(".card");
            if (!card) return;
            const c = st.cands.find((x) => x.id === card.dataset.id);
            if (c) window.open(ctx.files(c.file), "_blank");
          }}
        >
          {st.cands.map((c) => (
            <Tile
              key={c.id}
              id={c.id}
              src={ctx.files(c.thumb || c.file)}
              badge={`${KINDS[c.kind] || c.kind}${c.selected ? " ✓" : ""}`}
              term={`${c.ref_id ? "ref " + c.ref_id + " · " : ""}${c.source}`}
              sel={st.sel === c.id}
              title={c.prompt || c.name || ""}
            />
          ))}
        </div>
        <div id="baseFinalCard">
          {st.finalRel ? (
            <div className="bs-final">
              <figure>
                <img src={`${ctx.files(st.finalRel)}?v=${st.finalV}`} alt="imagem base final" loading="lazy" />
              </figure>
              <div className="bs-final-body">
                <span className="chip ok">imagem base final ✓</span>
                <p className="bs-final-hint">segue para o storyboard →</p>
                <p className="fine">
                  Gravada em <code>base/base_final.png</code> — é a imagem que a etapa 4 (storyboard) usa.
                </p>
              </div>
            </div>
          ) : null}
        </div>
        <div id="baseGenResult" className="bs-result" style={results.length ? undefined : { display: "none" }}>
          {results.length ? (
            <>
              <div className="row">
                <span className="eyebrow lbl">Modificação — antes → depois</span>
                <span className="ext">[extensão]</span>
              </div>
              {results.map((c) => {
                const after = ctx.files(c.file);
                const origem = originDe(c);
                return (
                  <div className="pair" key={c.id}>
                    <div className="ba">
                      {origem ? (
                        <>
                          <figure>
                            <img src={origem.url} alt={`antes (${origem.label})`} loading="lazy" />
                            <figcaption>antes · {origem.label}</figcaption>
                          </figure>
                          <span className="arrow">→</span>
                        </>
                      ) : null}
                      <figure>
                        <img src={after} alt={`depois (${depoisLbl})`} loading="lazy" />
                        <figcaption>depois · {depoisLbl}</figcaption>
                        <a className="link dl" download href={after}>
                          Baixar imagem
                        </a>
                      </figure>
                    </div>
                  </div>
                );
              })}
            </>
          ) : null}
        </div>
        <p className="note bs-note">
          Escolha uma imagem por passo — a limpeza de marca é um passo opcional [extensão] entre a situação e o
          rótulo, e trocar a situação recomeça a cadeia. Ao fechar: <code>base/base_final.png</code> +{" "}
          <code>base.md</code>.
        </p>
      </section>

      {progEl}
      {costEl}
    </>
  );
}

/** Textarea copiável com auto-size (equivale ao `ui.autosize` do vanilla). */
function PromptTextarea({
  value,
  dataK,
  label,
  onChange,
}: {
  value: string;
  dataK: string;
  label: string;
  onChange: (v: string) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useAutosize(ref, [value]);
  return (
    <textarea
      ref={ref}
      data-k={dataK}
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

// CSS `.bs-` da etapa 3 (byte-a-byte do `view.html`; wave 4 · regra 6). Renderizado num
// `<style>` que monta/desmonta com a tela — nao e import global (wave-10 §6.4).
const BASE_CSS = `
  /* Escopo \`.bs-\` da etapa 3 (regra 6 da wave 4). Só o que o catálogo do shell ainda não cobre:
     os gaps de 10/14 px medidos no protótipo, a margem zero do card único de prompt e o
     cursor do stepper (que aqui também é o seletor do passo da importação). */
  .bs-instr{gap:10px;margin-bottom:12px}
  .bs-instr>input{min-width:220px}
  /* \`[extensão]\` seletor de preset de realismo (opt-in): fica colado na linha da instrução. */
  .bs-preset{margin:-4px 0 12px}
  .bs-preset>select{max-width:100%}
  .bs-brand{gap:10px;align-items:center}
  .bs-brand-preview{max-height:72px;border-radius:6px;border:1px solid var(--line,#333)}
  .bs-io{gap:14px;margin:0}
  .bs-io .col{min-width:220px}
  /* Vazia, a galeria de candidatas não ocupa nada (é o estado do protótipo); com imagens,
     ela ganha o respiro que a linha de importação teria dado. */
  #baseGallery:not(:empty){margin-top:14px}
  #baseChain .st{cursor:pointer}
  /* base-prompt-provenance: cabeçalho de junção (mood × referência) + visão anotada das 5 linhas.
     Cores por proveniência via tokens do shell: --accent (mood), --info (referência), --ink-4
     (técnico). Só o que o catálogo do shell não cobre fica escopado \`.bs-\`. */
  /* Card de MOOD do painel 01 (a referência é o hero grande ao lado): bloco vertical enxuto. */
  .bs-junction{display:block;margin:12px 0;padding:14px;
    border:1px solid var(--line);border-radius:12px;background:var(--surface-2)}
  .bs-junction .swatches{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
  .bs-junction .sw{width:22px;height:22px;border-radius:6px;border:1px solid var(--line)}
  .bs-prov{margin-top:12px}
  .bs-prov .prov-line{display:flex;gap:10px;align-items:baseline;padding:6px 0;border-top:1px solid var(--line)}
  .bs-prov .prov-line:first-of-type{border-top:0}
  .bs-prov .prov-text{flex:1;color:var(--ink-2);font-size:13px;line-height:1.45}
  .bs-prov .prov-text b{color:var(--ink);font-weight:600}
  .bs-chip{flex:0 0 auto;font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px;
    border:1px solid transparent;white-space:nowrap}
  .bs-chip.from-mood{color:var(--accent);background:var(--accent-soft-2);border-color:var(--accent-line)}
  .bs-chip.from-reference{color:var(--info);background:var(--info-soft);border-color:var(--info)}
  .bs-chip.from-technical{color:var(--ink-4);background:var(--surface-3);border-color:var(--line)}
  .bs-chip.from-join{color:var(--ink);background:var(--surface-3);border-color:var(--line)}
  /* base-cli-generation [extensão] (ADH-OS-20260827-09): geração paga via CLI DENTRO do passo 03.
     O botão age no passo ativo do stepper; o custo aparece por passo (upscale usa outro modelo);
     a linha do Higgsfield deixa claro que a UI ilimitada é o caminho não pago. */
  .bs-cli{gap:10px;align-items:center;margin-top:14px}
  #baseCliCost{color:var(--ink-3)}
  .bs-hf{margin:8px 0 0;color:var(--ink-3)}
  .bs-hf b{color:var(--ink-2)}
  .bs-result{margin-top:16px}
  .bs-result .pair{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-start;padding:12px;
    border:1px solid var(--line);border-radius:12px;background:var(--surface-2);margin-top:10px}
  .bs-result .ba{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  .bs-result figure{margin:0;text-align:center}
  .bs-result figure img{width:150px;height:150px;object-fit:cover;border-radius:10px;
    border:1px solid var(--line);display:block}
  .bs-result figcaption{font-size:12px;color:var(--ink-3);margin-top:5px}
  .bs-result .arrow{font-size:22px;color:var(--ink-3);align-self:center}
  .bs-result .dl{display:inline-block;margin-top:8px}
  /* wave 5 · ponto 1: painel "M" fundido na junção — o seletor de fonte do mood e o mosaico
     quadricular vivem dentro do lado 🎨 Mood; a proveniência vira <details> recolhido. */
  .bs-junction .bs-moodhead{gap:8px;align-items:center;margin-bottom:10px}
  .bs-junction select#moodSource{width:100%;max-width:100%;margin-bottom:10px}
  .bs-junction .mood-mosaic{max-width:260px}
  .bs-junction .bs-mood-note{margin:10px 0 0;color:var(--ink-3);line-height:1.45}
  /* "equação" da junção: [referência] + [mood] → prompt (a soma visível que vira o prompt). */
  .bs-fuse{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px;
    padding-bottom:14px;border-bottom:1px solid var(--line)}
  .bs-fuse-item{margin:0;display:flex;flex-direction:column;align-items:center;gap:5px}
  .bs-fuse-cap{font-family:"IBM Plex Mono",monospace;font-size:10px;color:var(--ink-3);
    text-transform:uppercase;letter-spacing:.04em}
  .bs-fuse-thumb{width:76px;height:76px;object-fit:cover;border-radius:9px;border:1px solid var(--line)}
  .bs-fuse-mood .mood-mosaic{max-width:120px}
  .bs-fuse-op,.bs-fuse-arrow{font-size:20px;color:var(--ink-4);font-weight:700;line-height:1}
  .bs-fuse-out{align-self:center;padding:7px 13px;border-radius:9px;background:var(--accent-soft);
    color:var(--accent);font-weight:600;font-size:13px;border:1px solid var(--accent-line)}
  .bs-prov-det{margin-top:12px}
  .bs-prov-det>summary{cursor:pointer;list-style:none;display:flex;gap:8px;align-items:center;padding:6px 0}
  .bs-prov-det>summary::-webkit-details-marker{display:none}
  .bs-prov-det>summary::before{content:"▸";color:var(--ink-4);font-size:12px}
  .bs-prov-det[open]>summary::before{content:"▾"}
  .bs-prov-det .bs-prov-body{margin-top:2px}
  /* ADH-OS-20260828-22 (wave 6 · frente D): painel 01 sem espaço morto — PREVIEW GRANDE da
     referência selecionada (#baseRefHero) ocupando a largura útil do painel + a tira compacta
     (#refGallery) para trocar a seleção. Só apresentação; a lógica de selectRef não muda. */
  .bs-refhero{margin:10px 0 12px;border:1px solid var(--line);border-radius:14px;overflow:hidden;
    background:var(--surface-2)}
  .bs-refhero:empty{display:none}
  .bs-refhero img{display:block;width:100%;height:clamp(200px,22vw,300px);object-fit:cover}
  /* ADH-OS-20260828-24: painel 01 em DUAS COLUNAS — referência+mood à esquerda, instrução e o
     PROMPT à direita (visível no topo, sem ficar soterrado abaixo do hero). Colapsa em 1 coluna
     no estreito. Corrige a regressão em que o prompt caía a ~1800px da dobra. */
  .bs-p1grid{display:grid;grid-template-columns:minmax(260px,1fr) minmax(320px,1.15fr);gap:20px;align-items:start}
  .bs-p1-left,.bs-p1-right{min-width:0}
  @media (max-width:860px){.bs-p1grid{grid-template-columns:1fr}}
  /* a tira das referências vira compacta e de largura plena (sem o cap de 560px que deixava a
     faixa morta à direita): thumbs menores, fluxo por toda a largura. */
  .bs-refpick .gallery.xs{max-width:none;grid-template-columns:repeat(auto-fill,minmax(88px,1fr))}
  /* botão "Gerar via CLI" do painel 01: age SEMPRE sobre a situação (força kind:"situation"),
     sem tocar o stepper do painel 03. */
  .bs-p1cli{gap:10px;align-items:center;margin-top:12px}
  #basePanel01CliCost{color:var(--ink-3)}
  /* wave 5 · ponto 2: card da imagem base final — deixa claro que ela segue para o storyboard. */
  .bs-final{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:16px;padding:12px;
    border:1px solid var(--accent-line);border-radius:12px;background:var(--accent-soft)}
  .bs-final figure{margin:0}
  .bs-final figure img{width:120px;height:120px;object-fit:cover;border-radius:10px;
    border:1px solid var(--line);display:block}
  .bs-final .bs-final-body{display:flex;flex-direction:column;gap:6px;min-width:0}
  .bs-final .bs-final-hint{margin:0;font-weight:600;color:var(--accent)}
  /* base-clean-marca [extensão] (wave 9): o passo opcional "limpar marca" mora DENTRO do painel 03,
     colado no stepper, e só aparece quando ele é o passo ativo (display controlado no render, como
     #baseJunction/#baseGenResult). Só o que o catálogo do shell não cobre, escopado \`.bs-\`. */
  .bs-clean{margin-top:14px;padding:12px;border:1px solid var(--line);border-radius:12px;
    background:var(--surface-2)}
  .bs-clean-head{gap:8px;align-items:center;margin-bottom:10px}
  .bs-clean-row{gap:10px;align-items:center}
  .bs-clean-warn{margin:10px 0 0;color:var(--ink-3);line-height:1.45}
`;
