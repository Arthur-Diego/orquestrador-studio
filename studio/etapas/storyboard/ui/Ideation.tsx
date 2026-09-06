// Metade 1 — ideação + cenas em texto (aula 010) + os `[extensão]` da wave 7/9 (vídeo por foto
// ADR-021/022, inpaint-marcacao ADR-004, roteiro por Claude ADR-025/028). Porte React do
// `makeIdeation` do `view.js` vanilla. Painéis 01 (ideias da base), Área marcada, Roteiro por Claude
// e 03 (a história em cenas, com uma linha por foto). Contrato DOM idêntico ao vanilla (ids/classes),
// oráculo em `scripts/qa/cenarios/storyboard.py`.
import { useCallback, useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import {
  Modal,
  copy,
  hfChipView,
  progressJob,
  useCostConfirm,
  useProgress,
  useUpload,
} from "../../../../frontend/src/ui";
import {
  CampaignPreset,
  PRESET_INHERIT,
  PRESET_OFF,
  presetLabel,
  presetsUrl,
} from "./CampaignPreset";
import { Annotate } from "./Annotate";
import { MaskEditor } from "./MaskEditor";
import type { StudioCtx } from "../../../../frontend/src/shell/plugin";
import { useStudioChange } from "../../../../frontend/src/shell/events";
import type {
  HistoryItem,
  Idea,
  InstructionsMeta,
  ModelMeta,
  PhotoMeta,
  PhotoOrigin,
  PresetDefaults,
  RealismPreset,
  Scene,
  ScriptCliDiag,
  ScriptScene,
  SbStatus,
} from "./types";

const EMPTY_INSTRUCTION = "a instrução montada aparece aqui — os botões não gastam crédito";
const SCRIPT_NO_CLI =
  "Claude CLI não encontrado: escreva as cenas à mão no painel 03 (aula 010) ou instale o Claude Code.";
const SCRIPT_TARGET = "Nano Banana Pro";
const SCRIPT_ACTION = "storyboard.script";
/** Ação de preset do prompt de vídeo por foto (`settings.resolve_preset("motion", …)`). */
const MOTION_ACTION = "motion";
const KEYFRAME_ACTION = "storyboard.keyframe";
const SCRIPT_COUNT_DEFAULT = 5;
const SCRIPT_COUNT_MAX = 10;
const SCRIPT_IDEA_IMAGES = 3;
/**
 * Rótulo do botão principal do roteiro (critério A5). Ele diz o que o clique PRODUZ — cenas — e
 * não só a ferramenta; era "Gerar roteiro (Claude) [extensão]" e ficava `disabled` sem o CLI, o
 * que escondia da tela a única funcionalidade que o card #95 pede que fique visível.
 */
const SCRIPT_GEN_LABEL = "Gerar cenas (roteiro por Claude) [extensão]";
/** Pergunta da substituição (FDD §4 fluxo 4, item 4). Só aparece sobre texto de origem `manual`. */
const SUBSTITUIR_Q = "Substituir o texto que você escreveu?";
/**
 * Espera da digitação antes de gravar (FDD §4 fluxo 4, item 5). O resultado da IA NÃO espera: ele
 * persiste na hora, porque é o único conteúdo da tela que o usuário não consegue redigitar.
 */
const PERSIST_DEBOUNCE_MS = 400;
const AREA_NO_CLI =
  "Sem CLI: marque e gere pelo inpaint na própria interface da Higgsfield (ilimitado no plano).";

/** Mensagem de vazio do picker — cita o motor local do painel 01b (critério B8). */
const PICKER_EMPTY =
  "Nenhuma ideia ainda — gere na Higgsfield com a instrução do painel 01 e importe, ou gere de graça no motor local (painel 01b).";
const PICKER_EMPTY_FILTRO = "Nenhuma ideia com essa origem — mude o filtro por origem.";

/**
 * MIME internos do arrasto (FDD §4 fluxo 2, passo 6). São dois de propósito: o `drop` só age
 * quando reconhece um deles, e por isso arquivo arrastado do sistema operacional (que chega como
 * `Files`) é IGNORADO pelas cenas — quem importa arquivo é o painel 01/`ImportIdeasModal`.
 */
const DND_IDEA = "application/x-studio-idea";
const DND_PHOTO = "application/x-studio-photo";

/** Foto arrastada: qual cena ela deixou e qual arquivo é. */
interface PhotoDrag {
  sid: string;
  img: string;
}

const pkey = (sid: string, img: string) => `${sid}:${img}`;

/** Mapa sem uma chave, preservando a identidade quando a chave não existe (evita render à toa). */
function semChave<T>(mapa: Record<string, T>, k: string): Record<string, T> {
  if (!(k in mapa)) return mapa;
  return Object.fromEntries(Object.entries(mapa).filter(([kk]) => kk !== k));
}

/**
 * Chave de origem de uma ideia para o filtro e para o badge. O motor local produz DOIS tipos com
 * o mesmo `source: "local"` (geração e inpaint) e só o `local_kind` os distingue (FDD §5.6).
 */
function ideaSourceKey(c: Idea): string {
  if (String(c.local_kind || "").includes("inpaint")) return "inpaint";
  return String(c.source || "");
}

/**
 * Badge legível de origem (FDD §4 fluxo 2, passo 1). `history` é o nome do FDD; `higgsfield` é o
 * valor que `ingest.import_history` grava de verdade — os dois caem no mesmo rótulo.
 */
function ideaSourceLabel(c: Idea): string {
  switch (ideaSourceKey(c)) {
    case "inpaint":
      return "Inpaint local";
    case "cli":
      return "Higgsfield (CLI)";
    case "local":
      return "Motor local (grátis)";
    case "upload":
      return "Enviada";
    case "downloads":
      return "Downloads";
    case "history":
    case "higgsfield":
      return "Histórico HF";
    default:
      return "Origem desconhecida";
  }
}

/** Ideias que passam pelo filtro de origem (vazio = todas). Galeria e picker usam a MESMA função. */
const filtrarIdeias = (list: Idea[], filtro: string) =>
  filtro ? list.filter((c) => ideaSourceKey(c) === filtro) : list;

/** Ordem preservada, sem repetir — o `dedup` do FDD §4 fluxo 2, passo 4. */
const dedup = (list: string[]) => [...new Set(list)];
/** Foto ainda sem estado na tela: herda o padrão da campanha e não tem procedência. */
const EMPTY_PHOTO_META: PhotoMeta = {
  desc: "",
  prompt: "",
  imgPrompt: "",
  videos: [],
  preset: PRESET_INHERIT,
  origin: {},
};
const DIACRITICS = /[̀-ͯ]/g;
const momOf = (label: string) =>
  String(label || "")
    .normalize("NFD")
    .replace(DIACRITICS, "")
    .toLowerCase()
    .replace(/[^a-z]/g, "");
const sceneLabelOf = (sid: string) => String(sid || "").replace(/^cena0*/, "cena ");

interface IdeationProps {
  ctx: StudioCtx;
  refreshGuide: () => void;
  bootKey: unknown;
  /**
   * Avisa o orquestrador que o `GET /storyboard/scenes` já respondeu (o backend cria/garante o
   * `storyboard/scenes.json`). A metade ÂNGULOS e o guia dependem desse arquivo — no vanilla a ordem
   * `ideation.onProject()` → `angles.onProject()` → `renderGuide()` garantia isso; aqui o orquestrador
   * só arma a metade ÂNGULOS e reata o guia DEPOIS deste sinal, reproduzindo a mesma ordem.
   */
  onScenesReady: (pid: string) => void;
}

type PhotoState = Record<string, PhotoMeta>;
type IdeaModal =
  | null
  | { kind: "import" }
  | { kind: "history"; items: HistoryItem[]; jobs: number }
  | { kind: "picker"; i: number }
  | { kind: "animate"; sid: string; img: string }
  | { kind: "reorder" }
  | { kind: "lightbox"; rel: string }
  | { kind: "annotate"; src: { id: string; url: string; label: string } }
  | { kind: "maskeditor"; src: { id: string; url: string; label: string } };

/** `[extensão]` motor local (ADR-033): modelo do catálogo grátis (gen/inpaint). */
interface LocalModelOpt {
  id: string;
  label: string;
  default?: boolean;
}
interface LocalStatus {
  ready: boolean;
  detail: string;
  engine_installed: boolean;
  comfy_up: boolean;
  gen_models: LocalModelOpt[];
  inpaint_models: LocalModelOpt[];
}
interface LocalJob {
  state: string;
  error?: string | null;
  result?: string | null;
  result_id?: string | null;
}

function seedPhotos(sc: Scene[]): PhotoState {
  const out: PhotoState = {};
  sc.forEach((s) => {
    const ph = s.photos || {};
    (s.images || []).forEach((img) => {
      const e = ph[img] || {};
      out[pkey(s.id || "", img)] = {
        desc: e.video_desc || "",
        prompt: e.video_prompt || "",
        imgPrompt: e.image_prompt || "",
        videos: (e.videos || []).slice(),
        // Os três estados voltam do arquivo do jeito que foram: chave ausente herda, `null` é a
        // rota de fuga "(sem preset)" e a string é o id escolhido (invariante 6).
        preset: !("preset" in e) ? PRESET_INHERIT : e.preset === null ? PRESET_OFF : e.preset,
        origin: { ...(e.origin || {}) },
      };
    });
  });
  return out;
}

/**
 * Procedência de um campo a partir da resposta de uma rota de prompt. O `source` do servidor
 * (`claude`/`template`) é traduzido para o enum de `origin` (`ia`/`template`) — o backend descarta
 * em silêncio o que não bate, e um chip de origem errado não pode custar o texto ao usuário.
 */
function originOf(source: string | undefined, preset: string | null | undefined): PhotoOrigin {
  return {
    source: source === "template" ? "template" : "ia",
    preset: typeof preset === "string" ? preset : null,
    at: new Date().toISOString(),
  };
}

/** Campos da foto que carregam procedência (`origin`), com o nome que vai para o arquivo. */
type PromptField = "image_prompt" | "video_prompt";

/**
 * Procedência de um texto DIGITADO pelo usuário. É ela que faz a pergunta "Substituir?" existir:
 * sem marcar `manual` na digitação, uma regeração posterior apagaria o texto autoral em silêncio.
 */
function manualOrigin(): PhotoOrigin {
  return { source: "manual", preset: null, at: new Date().toISOString() };
}

/** Texto do chip `.sbPromptOrigin` (critério D4): `ia` mostra também o preset que gerou. */
function originLabel(o?: PhotoOrigin): string {
  if (!o || !o.source) return "sem origem";
  if (o.source === "ia") return `ia · ${o.preset || "sem preset"}`;
  return o.source;
}

/** Uma foto no corpo do `PUT /scenes`. `preset` e `origin` são opcionais de propósito (§5.5). */
interface PhotoPayload {
  video_desc: string;
  video_prompt: string;
  image_prompt: string;
  videos: string[];
  preset?: string | null;
  origin?: Record<string, PhotoOrigin>;
}

/** Payload do PUT /scenes a partir do estado controlado — o que o `collect()` do vanilla montava. */
function buildPayload(sc: Scene[], ph: PhotoState): Scene[] {
  return sc.map((s) => {
    const sid = s.id || "";
    const photos: Record<string, PhotoPayload> = {};
    (s.images || []).forEach((img) => {
      const m = ph[pkey(sid, img)] || EMPTY_PHOTO_META;
      const photo: PhotoPayload = {
        video_desc: m.desc || "",
        video_prompt: m.prompt || "",
        image_prompt: m.imgPrompt || "",
        videos: (m.videos || []).slice(),
      };
      // A chave `preset` só existe no corpo quando o usuário decidiu algo: herdar é a AUSÊNCIA
      // dela, e é isso que faz o padrão da campanha valer na geração seguinte (critério C4).
      if (m.preset === PRESET_OFF) photo.preset = null;
      else if (m.preset) photo.preset = m.preset;
      if (m.origin && Object.keys(m.origin).length) photo.origin = { ...m.origin };
      photos[img] = photo;
    });
    const prim = s.primary ? ph[pkey(sid, s.primary)] : undefined;
    return {
      id: s.id || null,
      text: s.text,
      images: s.images,
      primary: s.primary,
      photos,
      videos: (prim?.videos || []).slice(),
    } as Scene;
  });
}

export function Ideation({ ctx, refreshGuide, bootKey, onScenesReady }: IdeationProps) {
  const onScenesReadyRef = useRef(onScenesReady);
  onScenesReadyRef.current = onScenesReady;
  const { api, apiUpload, toast } = ctx;
  const url = useCallback(
    (p?: string) => `/api/projects/${ctx.pid()}/storyboard${p || ""}`,
    [ctx],
  );

  const [meta, setMeta] = useState<InstructionsMeta>({
    kinds: [],
    models: [],
    arc: [],
    counts: { uncertain: 4, tweak: 1 },
  });
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [photos, setPhotos] = useState<PhotoState>({});
  /** Filtro por origem, compartilhado entre `#sbIdeasGallery` e o `PickerModal` (critério B1). */
  const [ideaFilter, setIdeaFilter] = useState("");
  /** O que está sendo arrastado agora — só para pintar `.dragging` (critério B6). */
  const [dragging, setDragging] = useState<{ idea?: string; photo?: PhotoDrag; fromIdx?: number } | null>(null);
  /** Alvo do arrasto: índice da cena sob o cursor e/ou a `.sb-key` sob o cursor (`.dragover`). */
  const [dragOverScene, setDragOverScene] = useState<number | null>(null);
  const [dragOverKey, setDragOverKey] = useState<string | null>(null);

  /**
   * Estado NOVO de cenas e fotos, sempre atualizado no MESMO instante em que a tela muda — a
   * mitigação do Risco 3 (§10). Todo gesto calcula o próximo estado a partir DESTAS refs (nunca
   * das variáveis de closure, que ficam congeladas no render em que o handler nasceu) e entrega o
   * resultado pronto ao `persist`. Era exatamente isso que faltava no `reorderPhoto` antigo, que
   * lia `photos` de fora do `setScenes`.
   */
  const scenesRef = useRef<Scene[]>([]);
  const photosRef = useRef<PhotoState>({});
  const [hasBase, setHasBase] = useState(false);
  const [baseImage, setBaseImage] = useState<string>("");
  const [counts, setCounts] = useState<{ ideas: number; selected: number }>({ ideas: 0, selected: 0 });
  const [kind, setKind] = useState("");
  const [text, setText] = useState("");
  const [instruction, setInstruction] = useState("");
  const [copied, setCopied] = useState(false);

  const [videoModels, setVideoModels] = useState<string[]>([]);
  const [videoModelDefaults, setVideoModelDefaults] = useState<{ single: string; start_end: string }>({
    single: "",
    start_end: "",
  });
  const [realismPresets, setRealismPresets] = useState<RealismPreset[]>([]);

  // roteiro por Claude
  const [scriptCli, setScriptCli] = useState(false);
  /** Diagnóstico do `claude` (FDD §5.1). `null` = servidor antigo, sem o campo aditivo. */
  const [scriptCliDiag, setScriptCliDiag] = useState<ScriptCliDiag | null>(null);
  /** Caixa "trazer também os prompts de imagem" do painel 02 (critério D5). */
  const [scriptWithPrompts, setScriptWithPrompts] = useState(false);
  /**
   * Sugestões RECUSADAS na pergunta "Substituir?", por `sid:img:campo`. Recusar não pode custar a
   * geração: o texto do usuário fica de pé e a sugestão continua copiável (FDD §4 fluxo 4, item 4).
   */
  const [suggestions, setSuggestions] = useState<Record<string, string>>({});
  const [scriptPresetDefault, setScriptPresetDefault] = useState("");
  const [scriptModels, setScriptModels] = useState<{ label?: string; default?: boolean }[]>([]);
  const [scriptSelectedIdeas, setScriptSelectedIdeas] = useState(0);
  /** `defaults` de `GET /api/prompter/presets?pid=` — a herança de TODAS as ações, não só a do roteiro. */
  const [presetDefaults, setPresetDefaults] = useState<PresetDefaults>({});
  const [script, setScript] = useState<import("./types").Script | null>(null);
  const [scriptPreset, setScriptPreset] = useState("");
  const [scriptCount, setScriptCount] = useState(SCRIPT_COUNT_DEFAULT);
  const [scriptInstruction, setScriptInstruction] = useState("");
  const [scriptCopied, setScriptCopied] = useState<string | null>(null);

  // área marcada
  const [areaModel, setAreaModel] = useState("");
  const [areaText, setAreaText] = useState("");
  const [areaCount, setAreaCount] = useState("4");
  const [areaSourceId, setAreaSourceId] = useState("");
  // Status COMPLETO do CLI (installed/logged_in/plan/credits) — o chip `#sbAreaCli` usa o texto do
  // `hfChipView` (mesmo do vanilla `ui.hfChip`), não um rótulo hardcoded.
  const [areaCli, setAreaCli] = useState<
    { installed: boolean; logged_in: boolean; plan?: string | undefined; credits?: number | null | undefined } | null
  >(null);
  const [area, setArea] = useState<{ sourceId: string; sourceUrl: string; label: string; ann: import("./types").AnnResult } | null>(
    null,
  );

  // `[extensão]` motor local (grátis) — ADR-033. Caminho ADICIONAL ao lado do pago (Higgsfield).
  const [localSt, setLocalSt] = useState<LocalStatus | null>(null);
  const [localPrompt, setLocalPrompt] = useState("");
  const [localCount, setLocalCount] = useState("4");
  const [localModel, setLocalModel] = useState("flux-schnell");
  const [localSourceId, setLocalSourceId] = useState("");

  const [modal, setModal] = useState<IdeaModal>(null);
  const areaBoxRef = useRef<HTMLTextAreaElement>(null);

  const [prog, progEl] = useProgress();
  const { confirm, element: costEl } = useCostConfirm();

  const models = videoModels.length ? videoModels : [videoModelDefaults.single].filter(Boolean);

  // ---------------- carregamentos ----------------
  const arcOf = useCallback(
    (n: number, total: number) => {
      const arc =
        meta.arc.length === 4
          ? meta.arc
          : [
              { id: "comeco", label: "começo", hint: "" },
              { id: "descoberta", label: "descoberta", hint: "" },
              { id: "acao", label: "ação", hint: "" },
              { id: "desfecho", label: "desfecho", hint: "" },
            ];
      const vazio = { id: "", label: "", hint: "" };
      if (n <= 1) return arc[0] || vazio;
      if (n >= total) return arc[3] || vazio;
      return (n === 2 ? arc[1] : arc[2]) || vazio;
    },
    [meta.arc],
  );

  const loadStatus = useCallback(async () => {
    const st = (await api(url())) as SbStatus;
    setHasBase(st.has_base);
    setCounts({ ideas: st.ideas, selected: st.selected });
    if (st.has_base) setBaseImage(ctx.files(st.base_image));
    setVideoModels(st.video_models || []);
    setVideoModelDefaults(st.video_model_defaults || { single: "", start_end: "" });
    setScriptCli(!!st.script_cli);
    setScriptCliDiag(st.script_cli_diag || null);
    setScriptPresetDefault(st.script_preset_default || "");
    setScriptModels(st.script_models || []);
    setScriptSelectedIdeas(+st.selected || 0);
  }, [api, url, ctx]);

  const loadIdeas = useCallback(async () => {
    if (!ctx.pid()) return [] as Idea[];
    const r = ((await api(url("/candidates"))) as { ideas: Idea[] }).ideas;
    setIdeas(r);
    return r;
  }, [api, url, ctx]);

  // `[extensão]` motor local: prontidão (engine + ComfyUI). Offline nunca quebra a tela.
  const loadLocalStatus = useCallback(async () => {
    if (!ctx.pid()) return;
    try {
      const st = (await api(url("/local/status"))) as LocalStatus;
      setLocalSt(st);
      const gen = st.gen_models || [];
      if (gen.length)
        setLocalModel((m) => (gen.some((x) => x.id === m) ? m : gen.find((x) => x.default)?.id || gen[0]!.id));
    } catch {
      setLocalSt(null);
    }
  }, [api, url, ctx]);

  const scriptModelLabel = useCallback(() => {
    const m = scriptModels.find((x) => x.default) || scriptModels[0];
    return (m && m.label) || SCRIPT_TARGET;
  }, [scriptModels]);

  /**
   * Preset que a CAMPANHA resolve para uma ação — o "X" de "(padrão da campanha: X)". Sai dos
   * `defaults` do servidor (projeto → global → código); `null` quando a campanha também não tem
   * preset, e `null` também quando o id resolvido saiu do catálogo (a tela nunca fica presa a um
   * id morto, mesma regra do `preset_default_for`).
   */
  const inheritedPreset = useCallback(
    (action: string): string | null => {
      // Para o roteiro o `script_preset_default` do `GET /storyboard` continua vencendo, como no
      // `resolveScriptPreset` que este hook substitui: é a mesma resolução, vinda de outra rota.
      const fromStatus = action === SCRIPT_ACTION ? scriptPresetDefault : "";
      const def = fromStatus || presetDefaults[action]?.preset || "";
      return realismPresets.some((p) => p.id === def) ? def : null;
    },
    [presetDefaults, realismPresets, scriptPresetDefault],
  );

  /**
   * O preset a ANUNCIAR no `RealismField` de uma foto.
   *
   * A foto tem UM `preset` só, mas ele viaja para duas ações diferentes: `motion` no
   * `POST /video-prompt` e `storyboard.keyframe` no `POST /image-prompt`. Quando as duas resolvem
   * para o MESMO id, o rótulo pode nomeá-lo; quando divergem — o "(misto)" do bloco da campanha, ou
   * alguém gravando `preset-config` por fora — nomear só o de `motion` afirmaria um preset que o
   * `/image-prompt` não vai receber, exatamente o Risco 4 (§10). Aí o rótulo fica sem o nome.
   */
  const inheritedPhotoPreset = useCallback((): string | null => {
    const motion = inheritedPreset(MOTION_ACTION);
    return motion && motion === inheritedPreset(KEYFRAME_ACTION) ? motion : null;
  }, [inheritedPreset]);

  // Boot / troca de projeto (o `onProject` do vanilla).
  useEffect(() => {
    let vivo = true;
    void (async () => {
      if (!ctx.pid()) return;
      setInstruction("");
      // presets de instrução (aula)
      try {
        const m = (await api(url("/instructions"))) as InstructionsMeta;
        if (!vivo) return;
        setMeta(m);
        setKind(m.kinds[0]?.kind || "");
      } catch (err) {
        toast((err as Error).message);
      }
      // catálogo de realismo (`[extensão]`)
      let rp: RealismPreset[] = [];
      let defaults: PresetDefaults = {};
      try {
        const r = (await api(presetsUrl(ctx.pid() || ""))) as {
          presets?: RealismPreset[];
          defaults?: PresetDefaults;
        };
        rp = r.presets || [];
        defaults = r.defaults || {};
      } catch {
        rp = [];
        defaults = {};
      }
      if (!vivo) return;
      setRealismPresets(rp);
      setPresetDefaults(defaults);
      await loadStatus();
      await loadIdeas();
      // cenas — o GET cria/garante o `storyboard/scenes.json` no backend
      try {
        const sc = ((await api(url("/scenes"))) as { scenes: Scene[] }).scenes;
        if (!vivo) return;
        putScenesState(sc);
        putPhotosState(seedPhotos(sc));
      } catch (err) {
        toast((err as Error).message);
      }
      // scenes.json garantido: agora a metade ÂNGULOS e o guia podem carregar (ordem do vanilla)
      if (vivo) onScenesReadyRef.current(ctx.pid() as string);
      // roteiro
      setScriptInstruction("");
      setScriptCount(SCRIPT_COUNT_DEFAULT);
      try {
        const r = (await api(url("/script"))) as { script?: import("./types").Script };
        if (vivo) setScript(r && r.script ? r.script : null);
      } catch {
        if (vivo) setScript(null);
      }
      // área marcada
      setArea(null);
      setAreaText("");
      setAreaSourceId("");
      try {
        const st = (await api("/api/higgsfield/status")) as {
          installed?: boolean;
          logged_in?: boolean;
          plan?: string;
          credits?: number | null;
        };
        if (vivo) setAreaCli({ installed: !!st.installed, logged_in: !!st.logged_in, plan: st.plan, credits: st.credits });
      } catch {
        if (vivo) setAreaCli(null);
      }
      // motor local (grátis) `[extensão]`
      setLocalPrompt("");
      setLocalSourceId("");
      if (vivo) await loadLocalStatus();
    })();
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bootKey]);

  // Sincronização com o chat `[extensão]` (Wave 11 · F03): `storyboard_local_generate` e
  // `storyboard_pick` mexem nas ideias/candidatas desta metade. Recarregamos SÓ as listas de
  // leitura — status (contadores, base, catálogos) e ideias. `scenes`/`photos` ficam de fora de
  // propósito: são o texto das cenas que o usuário digita e ainda não salvou, e sobrescrevê-los
  // por um evento do chat é exatamente o que a §10 Risco 5 do FDD proíbe.
  useStudioChange(
    "storyboard",
    () => {
      void (async () => {
        await loadStatus();
        await loadIdeas();
      })().catch(() => {
        /* aviso do chat é best-effort: falha de rede aqui não pode derrubar a tela */
      });
    },
    { pid: ctx.pid() },
  );

  // O seletor do roteiro nasce HERDANDO o padrão da campanha (valor vazio) — antes ele nascia com
  // o id resolvido escrito dentro, o que transformava a herança numa escolha explícita e congelada.
  useEffect(() => {
    setScriptPreset(PRESET_INHERIT);
  }, [bootKey]);

  // Modelo default do painel de área marcada quando `meta.models` chega.
  useEffect(() => {
    const def = (meta.models || []).find((m) => m.default) || (meta.models || [])[0];
    if (def) setAreaModel(def.id);
  }, [meta.models]);

  // ---------------- persistência ----------------
  const putScenes = useCallback(
    (list: Scene[]) => api(url("/scenes"), { method: "PUT", body: JSON.stringify({ scenes: list }) }),
    [api, url],
  );

  /**
   * Escrita de estado que mantém a ref em dia NO MESMO instante (antes do re-render). Todo caminho
   * que muda cenas ou fotos passa por aqui; nenhum `setScenes`/`setPhotos` solto sobrevive, senão
   * a ref envelhece e o payload volta a ser obsoleto (Risco 3).
   */
  const putScenesState = useCallback((sc: Scene[]) => {
    scenesRef.current = sc;
    setScenes(sc);
  }, []);
  const putPhotosState = useCallback((ph: PhotoState) => {
    photosRef.current = ph;
    setPhotos(ph);
  }, []);

  /**
   * Fila de UM `PUT /scenes` (§10 Risco 3). O último payload mora numa ref; enquanto uma requisição
   * está no ar, os gestos seguintes só sobrescrevem essa ref. Quando ela volta, o laço manda o
   * payload mais recente — nunca dois `PUT` concorrentes, e a resposta de um `PUT` já superado é
   * simplesmente descartada (nada aqui lê o corpo da resposta).
   */
  const pendingPayload = useRef<Scene[] | null>(null);
  const putBusy = useRef(false);
  /** Timer da digitação (400 ms). Toda persistência IMEDIATA o cancela: ela já é mais nova. */
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelDebounce = useCallback(() => {
    if (debounceTimer.current === null) return;
    clearTimeout(debounceTimer.current);
    debounceTimer.current = null;
  }, []);
  useEffect(() => () => cancelDebounce(), [cancelDebounce]);

  const flushScenes = useCallback(async () => {
    if (putBusy.current) return;
    putBusy.current = true;
    try {
      while (pendingPayload.current) {
        const payload = pendingPayload.current;
        pendingPayload.current = null;
        // A frente inteira move a persistência do botão para o GESTO: engolir o erro faria o
        // usuário ver a tela mudar e acreditar que gravou, com o disco intacto.
        await putScenes(payload).catch((err: unknown) => {
          toast(`${(err as Error).message} — não salvo; use “Salvar cenas”.`);
        });
      }
    } finally {
      putBusy.current = false;
    }
  }, [putScenes]);

  /**
   * Persistência imediata de um gesto. Recebe o estado NOVO explicitamente — quem chama já o
   * calculou a partir de `scenesRef`/`photosRef` — e nunca lê estado de closure.
   */
  const persist = useCallback(
    (sc: Scene[], ph: PhotoState) => {
      cancelDebounce();
      pendingPayload.current = buildPayload(sc, ph);
      void flushScenes();
    },
    [flushScenes, cancelDebounce],
  );

  /**
   * Persistência de DIGITAÇÃO: um `PUT` por pausa de 400 ms, não um por tecla (FDD §4 fluxo 4,
   * item 5). Lê as refs só na hora de disparar, então o payload sai com tudo que foi digitado — e
   * com qualquer outro gesto que tenha acontecido no meio.
   */
  const persistDebounced = useCallback(() => {
    cancelDebounce();
    debounceTimer.current = setTimeout(() => {
      debounceTimer.current = null;
      persist(scenesRef.current, photosRef.current);
    }, PERSIST_DEBOUNCE_MS);
  }, [persist, cancelDebounce]);

  /**
   * Save EXPLÍCITO (botão, reordenar, aplicar roteiro): grava e reidrata a tela com a resposta.
   *
   * Entra na MESMA fila dos gestos (`putBusy`) e cancela o debounce antes de enfileirar. Sem isso
   * ele disparava um `PUT` paralelo: se a resposta do save antigo chegasse por último, o
   * `putScenesState`/`seedPhotos` reidratavam a tela com o estado PRÉ-gesto e a remoção sumia do
   * disco e da tela ao mesmo tempo (§10 Risco 3).
   */
  const saveScenesAndReseed = useCallback(
    async (sc: Scene[], ph: PhotoState) => {
      cancelDebounce();
      while (putBusy.current) await new Promise((r) => setTimeout(r, 0));
      putBusy.current = true;
      try {
        // um gesto enfileirado enquanto esperávamos entra ANTES do save explícito
        while (pendingPayload.current) {
          const antes = pendingPayload.current;
          pendingPayload.current = null;
          await putScenes(antes).catch(() => {});
        }
        const r = (await putScenes(buildPayload(sc, ph))) as { scenes: Scene[] };
        putScenesState(r.scenes);
        putPhotosState(seedPhotos(r.scenes));
        await loadStatus();
        refreshGuide();
        return r;
      } finally {
        putBusy.current = false;
      }
    },
    [putScenes, putScenesState, putPhotosState, loadStatus, refreshGuide, cancelDebounce],
  );

  // ---------------- painel 01: ideias ----------------
  const build = async (count: number) => {
    try {
      const r = (await api(url("/instructions"), {
        method: "POST",
        body: JSON.stringify({ kind, text, count }),
      })) as { instruction: string; ui_hint?: string };
      setInstruction(r.instruction);
      if (r.ui_hint) toast(r.ui_hint);
    } catch (err) {
      toast((err as Error).message);
    }
  };

  const importFiles = async (files: FileList | File[]) => {
    const list = [...files];
    if (!list.length) return;
    try {
      const fd = new FormData();
      list.forEach((f) => fd.append("files", f));
      fd.append("prompt", instruction);
      const r = await fetch(url("/import/upload"), { method: "POST", body: fd });
      const body = (await r.json().catch(() => ({}))) as { detail?: string; added?: number; skipped?: number };
      if (!r.ok) throw new Error(body.detail || r.statusText);
      toast(`${body.added} ideias importadas${body.skipped ? ` · ${body.skipped} ignoradas` : ""}`);
      await refresh();
    } catch (err) {
      toast((err as Error).message);
    }
  };

  const refresh = async () => {
    await loadIdeas();
    await loadStatus();
    refreshGuide();
  };

  const panelDrop = useUpload((f) => void importFiles(f));

  // ---------------- painel 03: cenas ----------------
  const pm = (sid: string, img: string): PhotoMeta =>
    photos[pkey(sid, img)] || EMPTY_PHOTO_META;

  /**
   * Muda um campo da foto e PERSISTE — `now` para escolha (o seletor de preset), debounce para
   * digitação (`video_desc`). Sem isso, escolher "(sem preset)" ou digitar a descrição só vivia no
   * DOM até algum outro gesto disparar um `PUT` por acaso: recarregar a tela perdia a escolha,
   * contra o fluxo 3 (itens 3-5) e o critério B4.
   */
  const updatePhoto = (sid: string, img: string, patch: Partial<PhotoMeta>,
                       modo: "now" | "debounce" = "now") => {
    const k = pkey(sid, img);
    const cur = photosRef.current[k] || EMPTY_PHOTO_META;
    const next = { ...photosRef.current, [k]: { ...cur, ...patch } };
    putPhotosState(next);
    if (modo === "now") persist(scenesRef.current, next);
    else persistDebounced();
  };

  /**
   * Ponto único de mudança de cenas: calcula o próximo estado a partir da ref (sempre o mais
   * novo), grava estado e ref juntos e, quando o gesto é de FOTO, persiste na mesma interação com
   * o estado recém-calculado. Devolver o mesmo array significa "nada mudou" e não gera `PUT`.
   */
  const mutateScenes = useCallback(
    (fn: (prev: Scene[]) => Scene[], opts?: { persist?: boolean }) => {
      const prev = scenesRef.current;
      const next = fn(prev);
      if (next === prev) return prev;
      putScenesState(next);
      if (opts?.persist) persist(next, photosRef.current);
      return next;
    },
    [putScenesState, persist],
  );

  const addScene = () =>
    mutateScenes((prev) => [...prev, { id: null, text: "", images: [], primary: null, photos: {} }]);
  const delScene = (i: number) => mutateScenes((prev) => prev.filter((_, k) => k !== i));
  const moveScene = (i: number, dir: -1 | 1) =>
    mutateScenes((prev) => {
      const to = i + dir;
      if (to < 0 || to >= prev.length) return prev;
      const next = prev.slice();
      const it = next.splice(i, 1)[0];
      if (!it) return prev;
      next.splice(to, 0, it);
      return next;
    });
  const setSceneText = (i: number, t: string) =>
    mutateScenes((prev) => prev.map((s, k) => (k === i ? { ...s, text: t } : s)));

  // Estrelar, remover e reordenar persistem na MESMA interação (critérios B3 e B4): nenhum gesto
  // de foto depende mais de "Salvar cenas", que segue existindo só como rede de segurança.
  const setPrimary = (i: number, file: string) =>
    mutateScenes(
      (prev) => prev.map((s, k) => (k === i && s.images.includes(file) ? { ...s, primary: file } : s)),
      { persist: true },
    );
  const removeImage = (i: number, file: string) =>
    mutateScenes(
      (prev) =>
        prev.map((s, k) => {
          if (k !== i) return s;
          const images = s.images.filter((x) => x !== file);
          return { ...s, images, primary: s.primary === file ? images[0] || null : s.primary };
        }),
      { persist: true },
    );
  const reorderPhoto = (i: number, img: string, dir: -1 | 1) =>
    mutateScenes(
      (prev) => {
        const s = prev[i];
        if (!s) return prev;
        const from = s.images.indexOf(img);
        const to = from + dir;
        if (from < 0 || to < 0 || to >= s.images.length) return prev;
        const images = s.images.slice();
        const moved = images.splice(from, 1)[0];
        if (moved === undefined) return prev;
        images.splice(to, 0, moved);
        return prev.map((x, k) => (k === i ? { ...x, images } : x));
      },
      { persist: true },
    );

  /** Índice da cena com este `sid` (o `data-sid` do arrasto), ou -1. */
  const sceneIndexOf = (sid: string) => scenesRef.current.findIndex((s) => (s.id || "") === sid);

  /**
   * Move uma foto de uma cena para outra: some da origem e aparece no fim do destino, num único
   * `PUT` consistente (critérios B6 e B7). O estado por foto (`desc`/`prompt`/`preset`/`origin`)
   * viaja junto — a chave do mapa é `sid:img`, então trocar de cena trocaria a chave e o texto que
   * o usuário escreveu se perderia sem esta cópia.
   */
  const movePhotoToScene = (from: PhotoDrag, toIdx: number, origem?: number) => {
    const list = scenesRef.current;
    // Cena ainda não salva não tem `id`, e o `sid` do payload vira "" para TODAS elas. Quando o
    // gesto nasceu nesta tela o índice exato é conhecido; a busca por `sid` é só o fallback.
    const fromIdx = origem !== undefined && list[origem] ? origem : sceneIndexOf(from.sid);
    const dest = list[toIdx];
    if (!dest || fromIdx < 0 || fromIdx === toIdx || dest.images.includes(from.img)) return;
    const next = list.map((s, k) => {
      if (k === fromIdx) {
        const images = s.images.filter((x) => x !== from.img);
        return { ...s, images, primary: s.primary === from.img ? images[0] || null : s.primary };
      }
      if (k === toIdx) {
        const images = [...s.images, from.img];
        return { ...s, images, primary: s.primary || images[0] || null };
      }
      return s;
    });
    const meta = photosRef.current[pkey(from.sid, from.img)];
    const nextPhotos = meta
      ? { ...photosRef.current, [pkey(dest.id || "", from.img)]: { ...meta } }
      : photosRef.current;
    putScenesState(next);
    if (meta) putPhotosState(nextPhotos);
    persist(next, nextPhotos);
    refreshGuide();
  };

  /** Reordena dentro da MESMA cena soltando uma `.sb-key` sobre outra (critério B6). */
  const dropPhotoOnPhoto = (from: PhotoDrag, i: number, alvo: string) => {
    if (from.img === alvo) return;
    mutateScenes(
      (prev) => {
        const s = prev[i];
        if (!s) return prev;
        const de = s.images.indexOf(from.img);
        const para = s.images.indexOf(alvo);
        if (de < 0 || para < 0) return prev;
        const images = s.images.slice();
        const moved = images.splice(de, 1)[0];
        if (moved === undefined) return prev;
        images.splice(para, 0, moved);
        return prev.map((x, k) => (k === i ? { ...x, images } : x));
      },
      { persist: true },
    );
  };

  /**
   * Anexa ideias a uma cena. `mode="add"` (default) SOMA à galeria da cena, com dedup e ordem
   * preservada, mantendo a `primary` atual; `mode="replace"` substitui (é o que "Sem imagem" e
   * "Substituir tudo" usam). Antes do anexo, as ideias novas viram `selected`
   * (`POST /candidates/select` com a união) — se esse passo falhar, NADA é anexado e o erro aparece
   * (fluxo alternativo do FDD §4).
   */
  async function attachImages(i: number, ideaIds: string[], mode: "add" | "replace" = "add") {
    try {
      let lista = ideas;
      if (ideaIds.length) {
        const already = ideas.filter((c) => c.selected).map((c) => c.id);
        const ids = dedup(already.concat(ideaIds));
        if (ids.length !== already.length) {
          await api(url("/candidates/select"), { method: "POST", body: JSON.stringify({ ids }) });
          lista = await loadIdeas();
        }
      }
      const files = ideaIds.map((id) => lista.find((x) => x.id === id)?.file).filter(Boolean) as string[];
      mutateScenes(
        (prev) =>
          prev.map((s, k) => {
            if (k !== i) return s;
            const images = mode === "replace" ? dedup(files) : dedup([...s.images, ...files]);
            // A principal atual continua principal enquanto sobreviver à operação.
            const primary = s.primary && images.includes(s.primary) ? s.primary : images[0] || null;
            return { ...s, images, primary };
          }),
        { persist: true },
      );
      await loadStatus();
      refreshGuide();
    } catch (err) {
      toast((err as Error).message);
    }
  }

  // ---------------- campos abertos de prompt por foto (`[extensão]` critérios D2-D8) ----------------
  /** Chave de uma sugestão recusada no mapa `suggestions`. */
  const skey = (sid: string, img: string, field: PromptField) => `${pkey(sid, img)}:${field}`;

  /**
   * Digitação em um dos dois campos de prompt. Marca a origem `manual` (é ela que faz a pergunta
   * "Substituir?" existir na geração seguinte) e agenda UM `PUT` para 400 ms depois.
   */
  const typePrompt = (sid: string, img: string, field: PromptField, v: string) => {
    const k = pkey(sid, img);
    const cur = photosRef.current[k] || EMPTY_PHOTO_META;
    putPhotosState({
      ...photosRef.current,
      [k]: {
        ...cur,
        ...(field === "image_prompt" ? { imgPrompt: v } : { prompt: v }),
        origin: { ...cur.origin, [field]: manualOrigin() },
      },
    });
    persistDebounced();
  };

  /**
   * Aplica o texto que a IA devolveu a um campo. A pergunta acontece AQUI — depois da resposta, e
   * só sobre texto de origem `manual` (decisão auto-aceita 14: perguntar ANTES quebraria
   * C-STORYBOARD-27/28, que geram prompt sem interação extra). Texto de origem `ia`/`template` é
   * regeração e some sem pergunta. Recusar guarda a sugestão para o botão "Copiar" e não grava
   * nada. Devolve `true` quando o campo foi escrito.
   */
  function aplicarSugestao(
    sid: string,
    img: string,
    field: PromptField,
    texto: string,
    r: { source?: string; preset?: string | null },
    descOverride?: string,
  ): boolean {
    const k = pkey(sid, img);
    const cur = photosRef.current[k] || EMPTY_PHOTO_META;
    const atual = field === "image_prompt" ? cur.imgPrompt : cur.prompt;
    const autoral = (atual || "").trim() && cur.origin?.[field]?.source === "manual";
    if (autoral && !window.confirm(SUBSTITUIR_Q)) {
      setSuggestions((prev) => ({ ...prev, [skey(sid, img, field)]: texto }));
      return false;
    }
    const nextPhotos: PhotoState = {
      ...photosRef.current,
      [k]: {
        ...cur,
        ...(descOverride === undefined ? {} : { desc: descOverride }),
        ...(field === "image_prompt" ? { imgPrompt: texto } : { prompt: texto }),
        // O preset RESOLVIDO pelo servidor vira procedência do campo; a escolha do usuário
        // (`cur.preset`) continua intacta — herdar não pode virar escolha explícita ao gerar.
        origin: { ...cur.origin, [field]: originOf(r.source, r.preset) },
      },
    };
    putPhotosState(nextPhotos);
    // Resultado da IA persiste IMEDIATAMENTE, sem esperar o debounce (FDD §4 fluxo 4, item 5).
    persist(scenesRef.current, nextPhotos);
    setSuggestions((prev) => semChave(prev, skey(sid, img, field)));
    return true;
  }

  const dismissSuggestion = (sid: string, img: string, field: PromptField) =>
    setSuggestions((prev) => semChave(prev, skey(sid, img, field)));

  /** Corpo comum das duas rotas de prompt: `preset` só entra quando a foto NÃO herda (C2/C3). */
  const withPreset = (body: Record<string, unknown>, m: PhotoMeta) => {
    if (m.preset === PRESET_OFF) body.preset = null;
    else if (m.preset) body.preset = m.preset;
    return body;
  };

  const notaFonte = (r: { source?: string; seconds?: number }) => (
    <span className="fine">
      fonte: {r.source || "claude"}
      {r.seconds ? ` · sugestão ${r.seconds}s` : ""}
    </span>
  );

  // vídeo por foto
  async function genVideoPrompt(sid: string, img: string) {
    if (!sid) return toast("Salve as cenas primeiro.");
    const m = photosRef.current[pkey(sid, img)] || EMPTY_PHOTO_META;
    const description = (m.desc || "").trim();
    prog.progress({ title: "Gerar prompt de vídeo", subtitle: "o Claude escreve o prompt de movimento" });
    prog.step("Chamando o Claude…");
    try {
      // O POST acontece MESMO com descrição vazia: o 422 do servidor é a mensagem que o usuário
      // precisa ler (C-STORYBOARD-28), e adivinhá-la no cliente é como as duas divergem.
      const body = withPreset(
        { scene_id: sid, description, frames: { mode: "single", image: img } },
        m,
      );
      const r = (await api(url("/video-prompt"), {
        method: "POST",
        body: JSON.stringify(body),
      })) as { prompt?: string; source?: string; seconds?: number; preset?: string | null };
      const escrito = aplicarSugestao(sid, img, "video_prompt", r.prompt || "", r, description);
      prog.ok(escrito ? "Prompt pronto" : "Seu texto foi mantido · a sugestão ficou copiável");
      prog.note(notaFonte(r));
    } catch (err) {
      prog.fail((err as Error).message);
    }
  }

  /**
   * `[extensão]` prompt de IMAGEM (keyframe) da foto — `POST .../storyboard/image-prompt` (FDD
   * §5.4). Sem Claude no PATH a rota NÃO dá 409: devolve o template determinístico com
   * `source: "template"`, e é isso que o chip de origem mostra (decisão auto-aceita 3).
   */
  async function genImagePrompt(sid: string, img: string) {
    if (!sid) return toast("Salve as cenas primeiro.");
    const m = photosRef.current[pkey(sid, img)] || EMPTY_PHOTO_META;
    // O `video_desc` da foto vale como contexto quando não há instrução própria (FDD §4 fluxo 4).
    const description = (m.desc || "").trim();
    prog.progress({ title: "Gerar prompt de imagem", subtitle: "o Claude escreve o keyframe desta foto" });
    prog.step("Chamando o Claude…");
    try {
      const body = withPreset({ scene_id: sid, photo: img, description }, m);
      const r = (await api(url("/image-prompt"), {
        method: "POST",
        body: JSON.stringify(body),
      })) as { prompt?: string; source?: string; seconds?: number; preset?: string | null };
      const escrito = aplicarSugestao(sid, img, "image_prompt", r.prompt || "", r);
      prog.ok(escrito ? "Prompt pronto" : "Seu texto foi mantido · a sugestão ficou copiável");
      prog.note(notaFonte(r));
    } catch (err) {
      prog.fail((err as Error).message);
    }
  }

  /**
   * "Usar no motor local" (critério D8): leva o prompt de imagem da foto para o `#sbLocalPrompt` do
   * painel 01b e move o foco para lá. A geração POR CENA com saída em `cenaNN/` é de F07.
   */
  function enviarAoMotorLocal(sid: string, img: string) {
    const m = photosRef.current[pkey(sid, img)] || EMPTY_PHOTO_META;
    const t = (m.imgPrompt || "").trim();
    if (!t) return toast("Escreva ou gere o prompt de imagem desta foto primeiro.");
    setLocalPrompt(t);
    const el = document.getElementById("sbLocalPrompt") as HTMLTextAreaElement | null;
    // `scrollIntoView` não existe no jsdom; rolar é conforto, mover o FOCO é o critério D8.
    el?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    el?.focus();
    toast("Prompt copiado para o motor local (painel 01b).");
  }

  const onVideoDone = (sid: string, img: string, j: { video?: string }) => {
    if (!j || !j.video) {
      toast("Job concluído (sem vídeo).");
      return;
    }
    // A closure deste `done` é de MINUTOS atrás (o job de vídeo é longo): ler `photos` do state
    // aqui reverteria tudo o que o usuário digitou na foto enquanto o vídeo gerava — o antipadrão
    // exato da §10 Risco 3. A ref é a única fonte válida.
    const m = photosRef.current[pkey(sid, img)] || EMPTY_PHOTO_META;
    const nextPhotos: PhotoState = {
      ...photosRef.current,
      [pkey(sid, img)]: { ...m, videos: (m.videos || []).concat(j.video) },
    };
    putPhotosState(nextPhotos);
    toast("Vídeo gerado · usado na etapa 6 (animação)");
    persist(scenesRef.current, nextPhotos);
    void loadIdeas();
    refreshGuide();
  };

  async function saveScenesBtn() {
    try {
      const r = await saveScenesAndReseed(scenesRef.current, photosRef.current);
      toast(`${r.scenes.length} cenas salvas · storyboard.md atualizado`);
    } catch (err) {
      toast((err as Error).message);
    }
  }

  async function renderMd() {
    try {
      const r = (await api(url("/render"), { method: "POST" })) as { storyboard_md?: string };
      await loadStatus();
      refreshGuide();
      toast("storyboard.md gerado");
      if (r && r.storyboard_md) window.open(ctx.files(r.storyboard_md), "_blank");
    } catch (err) {
      toast((err as Error).message);
    }
  }

  async function saveReorder(orderIdx: number[]) {
    const reordered = orderIdx.map((idx) => scenesRef.current[idx]).filter((s): s is Scene => Boolean(s));
    try {
      await saveScenesAndReseed(reordered, photosRef.current);
      setModal(null);
      toast("Ordem salva · storyboard.md atualizado");
    } catch (err) {
      toast((err as Error).message);
    }
  }

  // ---------------- roteiro por Claude ----------------
  /**
   * Prontidão do CLI vista pela tela. O diagnóstico aditivo manda quando existe; sem ele (servidor
   * antigo) vale o `script_cli` booleano de sempre.
   */
  const cliOk = scriptCliDiag ? scriptCliDiag.available : scriptCli;

  /**
   * "Verificar de novo" (critério A2 no cliente): UMA requisição a
   * `GET .../storyboard/script/cli?refresh=true`, sem job. O `refresh` re-resolve o PATH e reatribui
   * o `BIN` do processo do servidor, então um `claude` instalado depois de o Studio subir passa a
   * valer sem reiniciar nada. Devolve a prontidão nova.
   */
  const recheckCli = useCallback(async (): Promise<boolean> => {
    try {
      const d = (await api(url("/script/cli?refresh=true"))) as ScriptCliDiag;
      setScriptCliDiag(d);
      setScriptCli(!!d.available);
      return !!d.available;
    } catch (err) {
      toast((err as Error).message);
      return false;
    }
  }, [api, url, toast]);

  async function runScript() {
    // O botão está SEMPRE habilitado (critério A1): sem CLI ele não some, re-checa. Se a re-checagem
    // achar o binário, o fluxo segue para o job na MESMA interação; se não achar, a tela atualiza o
    // diagnóstico e não dispara `POST /script/generate` — o 409 do ADR-025 seria inútil aqui.
    if (!cliOk) {
      const agora = await recheckCli();
      if (!agora) {
        document.getElementById("sbScriptCliDiag")?.focus();
        toast(SCRIPT_NO_CLI);
        return;
      }
    }
    const count = Math.min(SCRIPT_COUNT_MAX, Math.max(1, scriptCount || SCRIPT_COUNT_DEFAULT));
    // Mesmo contrato de três estados do `/video-prompt`: herdar é OMITIR a chave (o serviço resolve
    // o default de `storyboard.script`), `off` manda `null` e o id vai como está.
    const body: Record<string, unknown> = { count, instruction: scriptInstruction.trim() };
    if (scriptPreset === PRESET_OFF) body.preset = null;
    else if (scriptPreset) body.preset = scriptPreset;
    try {
      await progressJob(prog, {
        title: "Gerar roteiro (Claude) [extensão]",
        subtitle: `${count} cenas · sugestão editável, nada é aplicado sem o seu clique`,
        start: () => api(url("/script/generate"), { method: "POST", body: JSON.stringify(body) }),
        jobUrl: url("/script/job"),
        done: async () => {
          try {
            const r = (await api(url("/script"))) as { script?: import("./types").Script };
            setScript(r && r.script ? r.script : null);
          } catch {
            setScript(null);
          }
          // A galeria se atualiza no `done` de todo job desta tela (FDD §4 fluxo 2): o roteiro lê
          // as ideias escolhidas, e voltar dele sem a grade em dia esconde o que mudou no disco.
          await loadIdeas();
        },
        label: "Roteiro pronto",
      });
    } catch (err) {
      toast((err as Error).message);
    }
  }

  /**
   * "usar este" (critério D6): grava um `shot_prompt` do painel 02 no `image_prompt` da foto `k` da
   * cena correspondente. Prompt sobrando NÃO cria foto (decisão auto-aceita 13) — a tela diz
   * quantas fotos a cena tem e o usuário anexa mais uma se quiser.
   */
  function aplicarShotPrompt(i: number, k: number, texto: string) {
    const s = scenesRef.current[i];
    if (!s) return toast(`O roteiro tem mais cenas do que o painel 03 — crie a cena ${i + 1} com “+ cena”.`);
    const img = (s.images || [])[k];
    if (!img)
      return toast(
        `A cena ${i + 1} tem ${(s.images || []).length} foto(s) — anexe mais uma para usar a foto ${k + 1}.`,
      );
    const key = pkey(s.id || "", img);
    const cur = photosRef.current[key] || EMPTY_PHOTO_META;
    // O texto veio do roteiro, que o Claude escreveu: `originOf` traduz `claude` em `ia` e guarda
    // o preset com que o roteiro foi gerado (decisão auto-aceita 9).
    const nextPhotos: PhotoState = {
      ...photosRef.current,
      [key]: {
        ...cur,
        imgPrompt: texto,
        origin: { ...cur.origin, image_prompt: originOf("claude", script?.preset ?? null) },
      },
    };
    putPhotosState(nextPhotos);
    persist(scenesRef.current, nextPhotos);
    toast(`Prompt aplicado à foto ${k + 1} da cena ${i + 1}.`);
  }

  async function applyScript(all: boolean, withPrompts: boolean) {
    const cenas = script ? script.scenes || [] : [];
    if (!cenas.length) return toast("Gere o roteiro primeiro.");
    if (!scenes.length) return toast("Nenhuma cena no painel 03 para preencher.");
    const alvo = Math.min(scenes.length, cenas.length);
    const escritas: number[] = [];
    for (let i = 0; i < alvo; i++) {
      const s0 = scenes[i];
      if (s0 && String(s0.text || "").trim()) escritas.push(i + 1);
    }
    if (
      all &&
      escritas.length &&
      !window.confirm(
        `Substituir tudo sobrescreve ${escritas.length} texto(s) que você já escreveu (cena ${escritas.join(", ")}). Continuar?`,
      )
    )
      return;
    let n = 0;
    const list = scenes.map((s, i) => {
      const c = i < alvo ? cenas[i] : undefined;
      if (!c) return s;
      if (!all && String(s.text || "").trim()) return s;
      n++;
      return { ...s, text: String(c.text || "") };
    });
    if (!n)
      return toast("Nenhuma cena vazia para preencher — use “Substituir tudo” se quiser trocar o texto.");
    const sobra = cenas.length - alvo;
    // Com a caixa marcada, a cena `i` também recebe os prompts de imagem: `shot_prompts[k]` vai
    // para a k-ésima foto JÁ ANEXADA. Prompt sobrando não cria foto nenhuma — segue no painel 02,
    // com o botão "usar este" (decisão auto-aceita 13).
    let nextPhotos = photosRef.current;
    let nPrompts = 0;
    if (withPrompts) {
      const copia: PhotoState = { ...nextPhotos };
      list.forEach((s, i) => {
        const c = i < alvo ? cenas[i] : undefined;
        if (!c) return;
        // Mesma regra do texto: sem "Substituir tudo", cena já escrita fica intocada.
        if (!all && String(scenes[i]?.text || "").trim()) return;
        (s.images || []).forEach((img, k) => {
          const sp = (c.shot_prompts || [])[k];
          if (!sp) return;
          const key = pkey(s.id || "", img);
          const cur = copia[key] || EMPTY_PHOTO_META;
          copia[key] = {
            ...cur,
            imgPrompt: sp,
            origin: { ...cur.origin, image_prompt: originOf("claude", script?.preset ?? null) },
          };
          nPrompts++;
        });
      });
      nextPhotos = copia;
      putPhotosState(copia);
    }
    try {
      await saveScenesAndReseed(list, nextPhotos);
      toast(
        `${n} cena(s) preenchida(s) pelo roteiro${nPrompts ? ` · ${nPrompts} prompt(s) de imagem` : ""}${sobra > 0 ? ` · ${sobra} sugestão(ões) sobraram (use “+ cena”)` : ""}`,
      );
    } catch (err) {
      toast((err as Error).message);
    }
  }

  // ---------------- área marcada (`[extensão]` inpaint) ----------------
  const areaReady = !!(areaCli?.installed && areaCli?.logged_in);
  const cliView = hfChipView(areaCli as Parameters<typeof hfChipView>[0]);

  function areaSource(sourceId: string): { id: string; url: string; label: string } | null {
    if (sourceId) {
      const c = ideas.find((x) => x.id === sourceId);
      return c ? { id: c.id, url: ctx.files(c.file), label: c.file.split("/").pop() || "" } : null;
    }
    return hasBase && baseImage ? { id: "", url: baseImage, label: "base_final.png" } : null;
  }

  function openAnnotate(sourceId: string) {
    const src = areaSource(sourceId);
    if (!src) return toast("Imagem base ausente: conclua a etapa 3 (base).");
    setModal({ kind: "annotate", src });
  }

  async function saveAnnotation(src: { id: string; url: string; label: string }, blob: Blob) {
    const f = new File([blob], "annotation.png", { type: "image/png" });
    const r = (await apiUpload(`/api/projects/${ctx.pid()}/storyboard/annotate`, [f], "file", {
      source_id: src.id || "",
    })) as import("./types").AnnResult;
    setArea({ sourceId: src.id || "", sourceUrl: src.url, label: src.label, ann: r });
    document.getElementById("sbArea")?.scrollIntoView({ behavior: "smooth", block: "start" });
    toast(r.deduped ? "Marcação já existia · reaproveitada" : "Marcação salva");
  }

  function annotatePhoto(img: string) {
    const c = ideas.find((x) => x.file === img);
    if (!c) return toast("Esta foto não está na galeria de ideias — recarregue a etapa.");
    setAreaSourceId(c.id);
    setArea(null);
    openAnnotate(c.id);
  }

  async function runArea() {
    if (!area) return toast("Marque a região primeiro.");
    const t = areaText.trim();
    if (!t) return toast("Descreva a mudança da área marcada (uma instrução por vez).");
    const count = +areaCount || 4;
    const body = {
      model: areaModel,
      kind: "edit_area",
      text: t,
      count,
      source_id: area.sourceId || null,
      annotation_id: area.ann.id,
    };
    try {
      const ok = await confirm({
        costFn: () => api(url("/cost"), { method: "POST", body: JSON.stringify(body) }),
        label: `Gerar ${count} imagem(ns) da área marcada`,
      });
      if (!ok) return;
      await progressJob(prog, {
        title: "Gerar da área marcada [extensão]",
        subtitle: "Higgsfield via CLI — original + marcação como referências",
        start: () => api(url("/generate"), { method: "POST", body: JSON.stringify(body) }),
        jobUrl: url("/job"),
        done: async () => {
          await refresh();
        },
        label: "Imagens geradas",
      });
    } catch (err) {
      toast((err as Error).message);
    }
  }

  // ---------------- motor local (grátis) `[extensão]` — ADR-033 ----------------
  const localReady = !!localSt?.ready;

  async function runLocalGenerate() {
    const p = localPrompt.trim();
    if (!p) return toast("Escreva o prompt (em inglês, aula 007).");
    const count = +localCount || 4;
    try {
      await progressJob(prog, {
        title: "Gerar keyframes locais (grátis) [extensão]",
        subtitle: "Motor local (Flux via ComfyUI) — sem gastar crédito",
        start: () =>
          api(url("/local/generate"), {
            method: "POST",
            body: JSON.stringify({ prompt: p, count, model: localModel }),
          }),
        jobUrl: url("/local/job"),
        done: async () => {
          await refresh();
        },
        label: "Keyframes gerados",
      });
    } catch (err) {
      toast((err as Error).message);
    }
  }

  function openMaskEditor(sourceId: string) {
    if (!localReady) return toast(localSt?.detail || "Motor local offline: suba o ComfyUI.");
    const src = areaSource(sourceId);
    if (!src) return toast("Imagem base ausente: conclua a etapa 3 (base).");
    setModal({ kind: "maskeditor", src });
  }

  /** Roda o inpaint local (upload da máscara + poll do job) e devolve a URL do resultado, ou null. */
  async function runLocalInpaint(
    src: { id: string },
    maskBlob: Blob,
    instruction: string,
    opts: { model: string },
  ): Promise<string | null> {
    const f = new File([maskBlob], "mask.png", { type: "image/png" });
    try {
      await apiUpload(url("/local/inpaint"), [f], "mask", {
        instruction,
        source_id: src.id || "",
        model: opts.model,
      });
    } catch (err) {
      toast((err as Error).message);
      return null;
    }
    // inpaint é lento (dev ~3-4min): poll silencioso; o MaskEditor mostra "Processando…".
    let job: LocalJob = { state: "running" };
    for (let i = 0; i < 700 && job.state === "running"; i++) {
      await new Promise((r) => setTimeout(r, 700));
      try {
        job = (await api(url("/local/job"))) as LocalJob;
      } catch {
        job = { state: "error", error: "falha ao consultar o job local" };
      }
    }
    if (job.state === "error") {
      toast(job.error || "falha no inpaint local");
      return null;
    }
    await loadIdeas();
    if (!job.result) {
      toast("Sem mudança (resultado idêntico a um candidato existente).");
      return null;
    }
    return ctx.files(job.result);
  }

  // autosize da instrução da área quando a caixa aparece
  useEffect(() => {
    const el = areaBoxRef.current;
    if (el && area) {
      el.style.height = "auto";
      el.style.height = `${el.scrollHeight}px`;
    }
  }, [area]);

  // ---------------- arrastar e soltar (`[extensão]` critério B6) ----------------
  /**
   * O alvo aceita este arrasto? Decide SÓ pelos `types`, nunca pelo conteúdo.
   *
   * Durante `dragenter`/`dragover` o drag data store do HTML5 está em *protected mode*: `types` é
   * legível, mas `getData()` devolve `""` em Chrome, Firefox e Safari. Se o `dragover` perguntasse
   * pelo conteúdo, o `preventDefault()` nunca aconteceria, o alvo não viraria drop target válido e
   * o evento `drop` **jamais dispararia** — o critério B6 inteiro só funcionaria no jsdom, onde o
   * `DataTransfer` é um fake que sempre devolve o dado.
   *
   * Um `drop` de arquivo do sistema operacional chega com `Files` e é recusado aqui.
   */
  function aceitaArrasto(dt: DataTransfer | null): boolean {
    const tipos = [...(dt?.types || [])];
    return tipos.includes(DND_IDEA) || tipos.includes(DND_PHOTO);
  }

  /**
   * O que está no `dataTransfer`. Só vale no `drop`, quando o conteúdo é legível de novo.
   */
  function lerArrasto(dt: DataTransfer | null): { idea?: string; photo?: PhotoDrag } | null {
    if (!dt || !aceitaArrasto(dt)) return null;
    const idea = dt.getData(DND_IDEA);
    if (idea) return { idea };
    const bruto = dt.getData(DND_PHOTO);
    if (!bruto) return null;
    try {
      const p = JSON.parse(bruto) as PhotoDrag;
      return p && typeof p.img === "string" ? { photo: { sid: String(p.sid || ""), img: p.img } } : null;
    } catch {
      return null;
    }
  }

  const limparArrasto = () => {
    setDragging(null);
    setDragOverScene(null);
    setDragOverKey(null);
  };

  /** `dragover` sobre uma cena: só aceita (e pinta `.dragover`) o que a cena sabe receber. */
  const onSceneDragOver = (i: number) => (e: DragEvent) => {
    if (!aceitaArrasto(e.dataTransfer)) return;   // `dragover`: só os TIPOS são legíveis
    e.preventDefault();
    setDragOverScene(i);
  };

  /** `drop` na cena: ideia vira anexo; foto de OUTRA cena se move para cá. Tudo persiste. */
  const onSceneDrop = (i: number) => (e: DragEvent) => {
    const carga = lerArrasto(e.dataTransfer);
    limparArrasto();
    if (!carga) return;
    e.preventDefault();
    if (carga.idea) {
      void attachImages(i, [carga.idea], "add");
      return;
    }
    const origem = dragging?.fromIdx;
    if (carga.photo) movePhotoToScene(carga.photo, i, origem);
  };

  // ---------------- render ----------------
  const total = scenes.length;
  const ideiasVisiveis = filtrarIdeias(ideas, ideaFilter);
  /** Origens presentes na galeria, na ordem em que aparecem — as opções do `#sbIdeasFilter`. */
  const origensDisponiveis = dedup(ideas.map(ideaSourceKey).filter(Boolean)).map((key) => ({
    key,
    label: ideaSourceLabel(ideas.find((c) => ideaSourceKey(c) === key) as Idea),
  }));
  const kindTitle = meta.kinds.find((k) => k.kind === kind)?.ui_hint || "";
  const scriptUsadas = Math.min(scriptSelectedIdeas, SCRIPT_IDEA_IMAGES);

  return (
    <>
      <style>{STYLE}</style>

      {/* `[extensão]` Padrão visual da campanha (card #98) — no TOPO da etapa, porque ele é o
          default de tudo que vem abaixo. Só aparece com campanha aberta. */}
      {ctx.pid() ? (
        <CampaignPreset
          api={api}
          pid={ctx.pid() as string}
          toast={toast}
          presets={realismPresets}
          defaults={presetDefaults}
          onReload={setPresetDefaults}
        />
      ) : null}

      {/* Painel 01 — ideias a partir da imagem base */}
      <section
        className={`panel${panelDrop.isOver ? " over" : ""}`}
        id="sbIdeas"
        onDragOver={panelDrop.rootProps.onDragOver}
        onDragLeave={panelDrop.rootProps.onDragLeave}
        onDrop={panelDrop.rootProps.onDrop}
      >
        <input {...panelDrop.inputProps} accept="image/*" />
        <div className="panel-head">
          <h3>
            <span className="pn">01</span>Ideias a partir da imagem base
          </h3>
          <button
            id="sbCounts"
            type="button"
            className="chip mode"
            title="Importar ideias geradas na Higgsfield"
            onClick={() => setModal({ kind: "import" })}
          >
            {`${counts.ideas} ideias · ${counts.selected} escolhidas`}
          </button>
        </div>
        <div className="grid2 rev">
          <div className="card wide static sb-base">
            <img id="sbBase" className={hasBase ? "" : "hidden"} alt="imagem base da campanha" {...(hasBase ? { src: baseImage } : {})} />
            <span className="term">base/base_final.png</span>
          </div>
          <div className="col">
            <div className="row wrap">
              <select id="sbKind" title={kindTitle} value={kind} onChange={(e) => setKind(e.target.value)}>
                {meta.kinds.map((k) => (
                  <option key={k.kind} value={k.kind}>
                    {k.label}
                  </option>
                ))}
              </select>
            </div>
            <textarea
              id="sbText"
              rows={2}
              placeholder="Make the climber even smaller and more realistic"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <div className="row wrap">
              <button id="sbGen4" className="primary" disabled={!hasBase} onClick={() => void build(meta.counts.uncertain)}>
                Montar instrução — gere 4 (incerto)
              </button>
              <button id="sbGen1" className="ghost" disabled={!hasBase} onClick={() => void build(meta.counts.tweak)}>
                gere 1 (tweak)
              </button>
            </div>
            <div className="prompt sm">
              <div className="row">
                <span className="eyebrow">Cole isto na Higgsfield</span>
                <button
                  id="sbCopy"
                  type="button"
                  className="link copy"
                  onClick={async () => {
                    if (!instruction) return toast("Monte a instrução primeiro.");
                    await navigator.clipboard.writeText(instruction);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 1500);
                  }}
                >
                  Copiar
                </button>
                <span id="sbCopied" className="ok">
                  {copied ? "copiado ✓" : ""}
                </span>
              </div>
              <p id="sbInstruction" className="txt">
                {instruction || EMPTY_INSTRUCTION}
              </p>
            </div>
          </div>
        </div>

        {/* `[extensão]` Galeria de ideias na TELA (card #97, critério B1). Antes ela só existia
            dentro do `PickerModal`: quem abria a etapa não via o que já tinha. Cada card é
            arrastável para uma cena do painel 03. */}
        <div className="row wrap sb-ideas-head">
          <span className="eyebrow">Galeria de ideias</span>
          <label className="inline">
            origem
            <select
              id="sbIdeasFilter"
              aria-label="Filtrar ideias por origem"
              value={ideaFilter}
              onChange={(e) => setIdeaFilter(e.target.value)}
            >
              <option value="">todas as origens</option>
              {origensDisponiveis.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <span className="fine">arraste um card para uma cena do painel 03</span>
        </div>
        <div id="sbIdeasGallery" className="gallery sm">
          {ideiasVisiveis.length ? (
            ideiasVisiveis.map((c) => (
              <div
                key={c.id}
                className={`card sb-idea${c.selected ? " sel" : ""}${dragging?.idea === c.id ? " dragging" : ""}`}
                data-id={c.id}
                data-file={c.file}
                data-source={ideaSourceKey(c)}
                tabIndex={0}
                draggable
                title={c.prompt || ""}
                onDragStart={(e) => {
                  e.dataTransfer.setData(DND_IDEA, c.id);
                  e.dataTransfer.effectAllowed = "copy";
                  setDragging({ idea: c.id });
                }}
                onDragEnd={limparArrasto}
                onDoubleClick={() => window.open(ctx.files(c.file), "_blank")}
              >
                <img loading="lazy" src={ctx.files(c.thumb || c.file)} alt="" />
                <span className="term">
                  {ideaSourceLabel(c)}
                  {c.selected ? " · escolhida" : ""}
                </span>
              </div>
            ))
          ) : (
            <div className="empty">{ideas.length ? PICKER_EMPTY_FILTRO : PICKER_EMPTY}</div>
          )}
        </div>
      </section>

      {/* Painel Área marcada (`[extensão]` inpaint-marcacao, ADR-004) */}
      <section className="panel" id="sbArea">
        <div className="panel-head">
          <h3>
            Área marcada <span className="chip mode">[extensão]</span>
          </h3>
          {/* Como o vanilla (`ui.hfChip` + `chip.hidden = ready`): o chip fica no DOM com o texto real
              do CLI e apenas SOME quando o CLI está pronto (o texto entra no dump de textContent). */}
          <span id="sbAreaCli" className={`chip ${cliView.kind}`} hidden={areaReady}>
            {cliView.text}
          </span>
        </div>
        <p className="sb-area-warn" id="sbAreaWarn">
          Best-effort por prompt: a marcação vai como referência, não é inpaint com máscara; o
          resultado pode variar fora da área marcada (CLI sem máscara, ADR-002)
        </p>
        <div className="row wrap">
          <select
            id="sbAreaSource"
            aria-label="Imagem a marcar"
            value={areaSourceId}
            onChange={(e) => {
              setAreaSourceId(e.target.value);
              setArea(null);
            }}
          >
            <option value="">imagem base (etapa 3)</option>
            {ideas.map((c) => (
              <option key={c.id} value={c.id}>
                {`ideia ${c.id}${c.selected ? " · escolhida" : ""}`}
              </option>
            ))}
          </select>
          <button id="sbAreaMark" type="button" className="ghost" onClick={() => openAnnotate(areaSourceId)}>
            Marcar área [extensão]
          </button>
          {/* fica no DOM (`hidden` por CSS) para o texto entrar no dump de textContent, como no vanilla */}
          <span id="sbAreaHint" className="fine" hidden={areaReady}>
            {areaReady ? "" : AREA_NO_CLI}
          </span>
        </div>
        {/* O box fica SEMPRE no DOM (só ganha `.hidden`): o vanilla mantinha o par original/marcada, os
            seletores e o botão presentes (ocultos por CSS), e o texto deles conta no dump do ADR-004. */}
        <div id="sbAreaBox" className={`col${area ? "" : " hidden"}`}>
          <div className="sb-area-pair">
            <figure>
              <img id="sbAreaOrig" alt="imagem original" {...(area ? { src: area.sourceUrl } : {})} />
              <figcaption id="sbAreaOrigCap">{area ? `original · ${area.label}` : "original"}</figcaption>
            </figure>
            <figure>
              <img id="sbAreaAnn" alt="imagem com a área marcada" {...(area ? { src: ctx.files(area.ann.file) } : {})} />
              <figcaption id="sbAreaAnnCap">{area ? `marcada · ${area.ann.id}` : "marcada"}</figcaption>
            </figure>
          </div>
          <textarea
            id="sbAreaText"
            ref={areaBoxRef}
            rows={2}
            placeholder="uma instrução por vez, em inglês (ex.: make the rope thinner)"
            value={areaText}
            onChange={(e) => setAreaText(e.target.value)}
          />
          <div className="row wrap">
            <select id="sbAreaCount" aria-label="Quantas gerações" value={areaCount} onChange={(e) => setAreaCount(e.target.value)}>
              <option value="4">gere 4 (incerto)</option>
              <option value="1">gere 1 (tweak)</option>
            </select>
            <select id="sbAreaModel" aria-label="Modelo do CLI" value={areaModel} onChange={(e) => setAreaModel(e.target.value)}>
              {(meta.models || []).map((m: ModelMeta) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
            <button id="sbAreaGen" type="button" className="primary" disabled={!areaReady || !area} title={areaReady ? "" : AREA_NO_CLI} onClick={() => void runArea()}>
              Gerar via CLI (gasta créditos)
            </button>
          </div>
        </div>
      </section>

      {/* Painel motor local — geração + inpaint LOCAIS (grátis) `[extensão]` ADR-033.
          Caminho ADICIONAL ao pago (Higgsfield permanece nos painéis acima). */}
      <section className="panel" id="sbLocal">
        <div className="panel-head">
          <h3>
            <span className="pn">01b</span>Motor local (grátis) <span className="ext">[extensão]</span>
          </h3>
          <span id="sbLocalState" className="chip mode">
            {localReady ? "no ar" : localSt ? "offline" : "verificando…"}
          </span>
        </div>
        <p className="sb-script-warn">
          Alternativa GRÁTIS ao caminho pago: gere keyframes e faça inpaint real por máscara no motor
          local (ComfyUI/Flux), sem gastar crédito. A Higgsfield continua disponível nos painéis acima.
          {!localReady && localSt?.detail ? ` — ${localSt.detail}` : ""}
        </p>
        <div className="sb-script-ctrls">
          <label className="field" style={{ flex: "1 1 320px" }}>
            <span className="eyebrow lbl">prompt (inglês, aula 007)</span>
            <textarea
              id="sbLocalPrompt"
              value={localPrompt}
              placeholder="ex.: a lone climber on a snowy ridge, cinematic"
              aria-label="Prompt do motor local"
              onChange={(e) => setLocalPrompt(e.target.value)}
            />
          </label>
          <label className="field">
            <span className="eyebrow lbl">modelo</span>
            <select id="sbLocalModel" value={localModel} aria-label="Modelo local" onChange={(e) => setLocalModel(e.target.value)}>
              {(localSt?.gen_models || []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="eyebrow lbl">variações</span>
            <select id="sbLocalCount" value={localCount} aria-label="Variações locais" onChange={(e) => setLocalCount(e.target.value)}>
              <option value="4">4 (incerto)</option>
              <option value="1">1 (tweak)</option>
            </select>
          </label>
          <button
            id="sbLocalGen"
            type="button"
            className="primary"
            disabled={!localReady}
            title={localReady ? "" : localSt?.detail || "motor local offline"}
            onClick={() => void runLocalGenerate()}
          >
            Gerar local (grátis)
          </button>
        </div>
        <div className="sb-script-ctrls">
          <label className="field" style={{ flex: "1 1 320px" }}>
            <span className="eyebrow lbl">inpaint real sobre</span>
            <select id="sbLocalSource" value={localSourceId} aria-label="Imagem-fonte do inpaint" onChange={(e) => setLocalSourceId(e.target.value)}>
              <option value="">imagem base (etapa 3)</option>
              {ideas.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.file.split("/").pop()}
                </option>
              ))}
            </select>
          </label>
          <button
            id="sbLocalInpaint"
            type="button"
            className="ghost"
            disabled={!localReady}
            title={localReady ? "" : localSt?.detail || "motor local offline"}
            onClick={() => openMaskEditor(localSourceId)}
          >
            Editar por máscara (inpaint real, grátis)
          </button>
        </div>
      </section>

      {/* Painel 02 — Roteiro por Claude (`[extensão]` ADR-025/028) */}
      <section className="panel" id="sbScript">
        <div className="panel-head">
          <h3>
            <span className="pn">02</span>Roteiro por Claude <span className="ext">[extensão]</span>
          </h3>
          {script ? (
            <span id="sbScriptState" className="chip mode">
              sugestão de {String(script.generated_at || "").replace("T", " ").slice(0, 16) || "agora"}
            </span>
          ) : null}
        </div>
        <p className="sb-script-warn">
          Sugestão editável, sem gastar crédito (Claude CLI local): nada é escrito nas cenas sem o
          seu clique. O caminho da aula 010 — escrever a história à mão no painel 03 — continua
          valendo.
        </p>
        <div className="sb-script-ctrls">
          <div id="sbScriptPreset">
            <RealismField
              value={scriptPreset}
              presets={realismPresets}
              inherited={inheritedPreset(SCRIPT_ACTION)}
              onChange={setScriptPreset}
            />
          </div>
          <label className="field">
            <span className="eyebrow lbl">nº de cenas</span>
            <input
              id="sbScriptCount"
              type="number"
              min={1}
              max={10}
              step={1}
              value={scriptCount}
              aria-label="Número de cenas do roteiro"
              onChange={(e) => setScriptCount(+e.target.value)}
            />
          </label>
          <label className="field">
            <span className="eyebrow lbl">proporção (do projeto)</span>
            <span id="sbScriptAspect" className="sb-script-read">
              {(ctx.project() as { aspect_ratio?: string } | null)?.aspect_ratio || "16:9"}
            </span>
          </label>
          <label className="field">
            <span className="eyebrow lbl">alvo do prompt de imagem</span>
            <span id="sbScriptModel" className="sb-script-read">
              {scriptModelLabel()}
            </span>
          </label>
          <label className="field">
            <span className="eyebrow lbl">fotos da galeria no contexto</span>
            <span id="sbScriptIdeas" className="sb-script-read" title="Ideias escolhidas na galeria do painel 01 (multishot da base) que o Claude lê para manter o roteiro fiel a elas">
              {scriptSelectedIdeas
                ? `${scriptUsadas}${scriptSelectedIdeas > scriptUsadas ? ` de ${scriptSelectedIdeas}` : ""}`
                : "nenhuma — escolha na galeria"}
            </span>
          </label>
        </div>
        <textarea
          id="sbScriptInstruction"
          rows={2}
          maxLength={300}
          aria-label="Instrução livre para o roteiro (opcional)"
          placeholder="instrução livre em pt-BR, opcional (ex.: a história termina com o produto na mão do personagem) — até 300 caracteres"
          value={scriptInstruction}
          onChange={(e) => setScriptInstruction(e.target.value)}
        />
        <div className="row wrap">
          {/* SEMPRE habilitado (critério A1): sem CLI o clique re-checa o PATH em vez de sumir. */}
          <button id="sbScriptGen" type="button" className="primary" onClick={() => void runScript()}>
            {SCRIPT_GEN_LABEL}
          </button>
          <button
            id="sbScriptCliRecheck"
            type="button"
            className="ghost"
            title="re-resolve o PATH do processo e procura o claude de novo, sem reiniciar o Studio"
            onClick={() => void recheckCli()}
          >
            Verificar de novo
          </button>
          {cliOk ? null : (
            <span id="sbScriptHint" className="fine">
              {SCRIPT_NO_CLI}
            </span>
          )}
        </div>
        {/* Diagnóstico do binário (critério A1): o PATH que o PROCESSO enxerga é a informação que
            falta para o usuário entender por que o `claude` do terminal dele não aparece aqui. */}
        {cliOk ? null : (
          <div id="sbScriptCliDiag" className="sb-cli-diag" role="status" aria-live="polite" tabIndex={-1}>
            <span className="fine">
              Claude CLI não encontrado. PATH do processo:{" "}
              <span className="term">{scriptCliDiag?.searched_path || "(desconhecido)"}</span>
            </span>
            {scriptCliDiag?.hint ? <span className="fine">{scriptCliDiag.hint}</span> : null}
          </div>
        )}
        {/* Sempre no DOM (`.hidden` quando não há sugestão): os botões "Aplicar às cenas vazias" e
            "Substituir tudo" e o meta ficam presentes (ocultos por CSS) como no vanilla — o texto
            deles conta no dump de textContent. As cenas sugeridas (dinâmicas) só entram com a sugestão. */}
        <div id="sbScriptBox" className={`col${script && (script.scenes || []).length ? "" : " hidden"}`}>
          <div className="row wrap">
            <span id="sbScriptMeta" className="eyebrow">
              {script && (script.scenes || []).length
                ? `${(script.scenes || []).length} cenas · preset ${script.preset || "(sem preset)"} · ${script.aspect_ratio || ""} · ${scriptModelLabel()}`
                : ""}
            </span>
            <button id="sbScriptApplyEmpty" type="button" className="ghost" onClick={() => void applyScript(false, scriptWithPrompts)}>
              Aplicar às cenas vazias
            </button>
            <button id="sbScriptApplyAll" type="button" className="ghost" onClick={() => void applyScript(true, scriptWithPrompts)}>
              Substituir tudo
            </button>
            {/* Critério D5: o `shot_prompts[k]` do roteiro vai para a k-ésima foto JÁ anexada. */}
            <label className="inline" title="preenche o prompt de imagem das fotos já anexadas a cada cena">
              <input
                id="sbScriptWithPrompts"
                type="checkbox"
                checked={scriptWithPrompts}
                onChange={(e) => setScriptWithPrompts(e.target.checked)}
              />{" "}
              trazer também os prompts de imagem
            </label>
          </div>
          <p id="sbScriptNotes" className="fine" hidden={!(script && script.notes_pt)}>
            {(script && script.notes_pt) || ""}
          </p>
          <div id="sbScriptScenes">
            {script
              ? (script.scenes || []).map((s: ScriptScene, i) => {
                  const shots = s.shot_prompts && s.shot_prompts.length ? s.shot_prompts : [s.image_prompt || ""];
                  return (
                    <div className="sb-script-scene" data-i={i} key={i}>
                      <span className="mom" data-mom={s.arc || ""} title={`Cena ${i + 1}`}>
                        {arcLabelOf(meta, s.arc)}
                      </span>
                      <div className="col">
                        <p className="sb-script-txt">{s.text || ""}</p>
                        <span className="fine sb-script-shots">
                          {shots.length} foto(s) sugerida(s) para esta cena (encaixe manual)
                        </span>
                        {shots.map((p, j) => {
                          const key = `${i}:${j}`;
                          return (
                            <div className="prompt sm" key={j}>
                              <div className="row">
                                <span className="eyebrow">
                                  foto {j + 1}/{shots.length} — prompt de imagem (inglês)
                                </span>
                                <button
                                  type="button"
                                  className="link copy sbScriptCopy"
                                  onClick={async () => {
                                    const ok = await copy(p || "");
                                    setScriptCopied(ok ? key : `${key}-fail`);
                                    setTimeout(() => setScriptCopied((c) => (c && c.startsWith(key) ? null : c)), 1500);
                                  }}
                                >
                                  Copiar
                                </button>
                                <button
                                  type="button"
                                  className="link sbScriptUse"
                                  title={`gravar este prompt na foto ${j + 1} da cena ${i + 1}`}
                                  onClick={() => aplicarShotPrompt(i, j, p || "")}
                                >
                                  usar este
                                </button>
                                <span className="ok">
                                  {scriptCopied === key ? "copiado ✓" : scriptCopied === `${key}-fail` ? "copie à mão" : ""}
                                </span>
                              </div>
                              <p className="txt sbScriptPromptText">{p || ""}</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })
              : null}
          </div>
        </div>
      </section>

      {/* Painel 03 — A história em cenas */}
      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">03</span>A história em cenas
          </h3>
          <div className="row wrap">
            <button id="sbAdd" className="ghost" onClick={addScene}>
              + cena
            </button>
            <button id="sbReorder" className="ghost" title="Reordenar as cenas em um modal maior" onClick={() => (scenes.length ? setModal({ kind: "reorder" }) : toast("Nenhuma cena para reordenar."))}>
              Reordenar cenas
            </button>
            <button id="sbRender" className="ghost" onClick={() => void renderMd()}>
              Gerar storyboard.md
            </button>
            <button id="sbSave" className="primary" onClick={() => void saveScenesBtn()}>
              Salvar cenas
            </button>
          </div>
        </div>
        <div id="sbScenes" className="rowlist">
          {scenes.map((s, i) => {
            const arc = arcOf(i + 1, total);
            const sid = s.id || "";
            return (
              <div className="scene-row" data-i={i} data-sid={sid} key={sid || `new-${i}`}>
                <div className="sb-scenehead">
                  <span className="mom" data-mom={momOf(arc.label)} title={`Cena ${i + 1} · ${arc.label}`}>
                    {arc.label}
                  </span>
                  <AutoTextarea
                    className="txt sbTxt"
                    rows={1}
                    placeholder={`${arc.label}: ${arc.hint} (ex.: close no astronauta andando na nevasca)`}
                    value={s.text}
                    onChange={(v) => setSceneText(i, v)}
                  />
                  <div className="acts">
                    <button type="button" className="ghost mini sbUp" title="subir cena" onClick={() => moveScene(i, -1)}>
                      ↑
                    </button>
                    <button type="button" className="ghost mini sbDown" title="descer cena" onClick={() => moveScene(i, 1)}>
                      ↓
                    </button>
                    <button type="button" className="ghost mini sbDel" title="remover cena" onClick={() => delScene(i)}>
                      ✕
                    </button>
                  </div>
                </div>
                <div
                  className={`sb-phototable${dragOverScene === i ? " dragover" : ""}`}
                  onDragOver={onSceneDragOver(i)}
                  onDragLeave={() => setDragOverScene((cur) => (cur === i ? null : cur))}
                  onDrop={onSceneDrop(i)}
                >
                  {s.images.map((img, piIdx) => (
                    <PhotoRow
                      key={img}
                      sid={sid}
                      img={img}
                      pi={piIdx}
                      count={s.images.length}
                      isPrimary={img === s.primary}
                      meta={pm(sid, img)}
                      fileUrl={ctx.files(img)}
                      filesUrl={(rel) => ctx.files(rel)}
                      realismPresets={realismPresets}
                      inheritedPreset={inheritedPhotoPreset()}
                      isDragging={dragging?.photo?.sid === sid && dragging?.photo?.img === img}
                      isDragOver={dragOverKey === pkey(sid, img)}
                      moveTargets={scenes
                        .map((_, k) => ({ i: k, label: `cena ${k + 1}` }))
                        .filter((t) => t.i !== i)}
                      suggestions={{
                        image_prompt: suggestions[skey(sid, img, "image_prompt")],
                        video_prompt: suggestions[skey(sid, img, "video_prompt")],
                      }}
                      onDesc={(v) => updatePhoto(sid, img, { desc: v }, "debounce")}
                      onPreset={(v) => updatePhoto(sid, img, { preset: v })}
                      onImgPrompt={(v) => typePrompt(sid, img, "image_prompt", v)}
                      onVidPrompt={(v) => typePrompt(sid, img, "video_prompt", v)}
                      onDismissSuggestion={(field) => dismissSuggestion(sid, img, field)}
                      onStar={() => setPrimary(i, img)}
                      onRemove={() => removeImage(i, img)}
                      onLightbox={() => setModal({ kind: "lightbox", rel: img })}
                      onGenPrompt={() => void genVideoPrompt(sid, img)}
                      onGenImgPrompt={() => void genImagePrompt(sid, img)}
                      onUseLocal={() => enviarAoMotorLocal(sid, img)}
                      onAnim={() => (sid ? setModal({ kind: "animate", sid, img }) : toast("Salve as cenas primeiro."))}
                      onAnnotate={() => annotatePhoto(img)}
                      onUp={() => reorderPhoto(i, img, -1)}
                      onDown={() => reorderPhoto(i, img, 1)}
                      onMove={(to) => movePhotoToScene({ sid, img }, to, i)}
                      onDragStartPhoto={(e) => {
                        e.dataTransfer.setData(DND_PHOTO, JSON.stringify({ sid, img }));
                        e.dataTransfer.effectAllowed = "move";
                        setDragging({ photo: { sid, img }, fromIdx: i });
                      }}
                      onDragEndPhoto={limparArrasto}
                      onDragOverPhoto={(e) => {
                        if (!aceitaArrasto(e.dataTransfer)) return;   // `dragover`: só os TIPOS
                        e.preventDefault();
                        setDragOverKey(pkey(sid, img));
                      }}
                      onDragLeavePhoto={() => setDragOverKey((cur) => (cur === pkey(sid, img) ? null : cur))}
                      onDropPhoto={(e) => {
                        const carga = lerArrasto(e.dataTransfer);
                        // Só a reordenação DENTRO da cena para aqui; ideia e foto de outra cena
                        // seguem borbulhando para o `.sb-phototable`, que sabe anexar e mover.
                        if (!carga?.photo || carga.photo.sid !== sid) return;
                        e.preventDefault();
                        e.stopPropagation();
                        const de = carga.photo;
                        limparArrasto();
                        dropPhotoOnPhoto(de, i, img);
                      }}
                      onVideoOpen={(rel) => window.open(ctx.files(rel), "_blank")}
                    />
                  ))}
                  <button
                    type="button"
                    className="thumb pick sb-pick sbAddPhoto"
                    aria-label={`Adicionar foto à cena ${i + 1}`}
                    title="adicionar imagem à cena"
                    onClick={() => setModal({ kind: "picker", i })}
                  >
                    + Adicionar foto à cena
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {progEl}
      {costEl}

      {modal?.kind === "import" ? (
        <ImportIdeasModal
          onClose={() => setModal(null)}
          onFiles={(files) => {
            setModal(null);
            void importFiles(files);
          }}
          onDownloads={async (minutes) => {
            setModal(null);
            try {
              const r = (await api(url("/import/downloads"), {
                method: "POST",
                body: JSON.stringify({ since_minutes: minutes, prompt: instruction }),
              })) as { added?: number; scanned?: number };
              toast(`${r.added} novas de ${r.scanned} imagens recentes`);
              await refresh();
            } catch (err) {
              toast((err as Error).message);
            }
          }}
          onHistory={async () => {
            try {
              const preview = (await api(url("/history/preview?size=50"))) as { items?: HistoryItem[]; jobs: number };
              setModal({ kind: "history", items: preview.items || [], jobs: preview.jobs });
            } catch (err) {
              setModal(null);
              toast((err as Error).message);
            }
          }}
        />
      ) : null}

      {modal?.kind === "history" ? (
        <HistoryModal
          items={modal.items}
          jobs={modal.jobs}
          onClose={() => setModal(null)}
          onImport={async (keys) => {
            if (!keys.length) {
              toast("Marque ao menos uma mídia.");
              return;
            }
            try {
              const r = (await api(url("/import/history"), {
                method: "POST",
                body: JSON.stringify({ size: 50, keys }),
              })) as { added?: number };
              setModal(null);
              toast(`${r.added} imagens importadas`);
              await refresh();
            } catch (err) {
              toast((err as Error).message);
            }
          }}
        />
      ) : null}

      {modal?.kind === "picker" ? (
        <PickerModal
          i={modal.i}
          ideas={ideas}
          selected={scenes[modal.i]?.images || []}
          filtro={ideaFilter}
          origens={origensDisponiveis}
          onFiltro={setIdeaFilter}
          filesUrl={(rel) => ctx.files(rel)}
          onClose={() => setModal(null)}
          onApply={(ids) => {
            const i = modal.i;
            setModal(null);
            void attachImages(i, ids, "add");
          }}
          onReplace={(ids) => {
            const i = modal.i;
            const atual = (scenes[i]?.images || []).length;
            // Trocar a galeria inteira é destrutivo e agora é ação SEPARADA da de adicionar
            // (critério B5): sem confirmação, nada muda.
            if (
              atual &&
              !window.confirm(
                `Substituir tudo descarta as ${atual} foto(s) já anexadas à cena ${i + 1}. Continuar?`,
              )
            )
              return;
            setModal(null);
            void attachImages(i, ids, "replace");
          }}
          onNoImage={() => {
            const i = modal.i;
            setModal(null);
            void attachImages(i, [], "replace");
          }}
          onImportar={() => {
            setModal(null);
            setTimeout(() => setModal({ kind: "import" }), 0);
          }}
          onOpenFile={(rel) => window.open(ctx.files(rel), "_blank")}
        />
      ) : null}

      {modal?.kind === "animate" ? (
        <AnimateModal
          sid={modal.sid}
          img={modal.img}
          fileUrl={ctx.files(modal.img)}
          others={(scenes.find((s) => (s.id || "") === modal.sid)?.images || []).filter((x) => x !== modal.img)}
          meta={pm(modal.sid, modal.img)}
          models={models}
          modelDefaults={videoModelDefaults}
          realismPresets={realismPresets}
          inheritedPreset={inheritedPhotoPreset()}
          filesUrl={(rel) => ctx.files(rel)}
          suggestion={suggestions[skey(modal.sid, modal.img, "video_prompt")]}
          onDesc={(v) => updatePhoto(modal.sid, modal.img, { desc: v }, "debounce")}
          onPreset={(v) => updatePhoto(modal.sid, modal.img, { preset: v })}
          onVidPrompt={(v) => typePrompt(modal.sid, modal.img, "video_prompt", v)}
          onDismissSuggestion={() => dismissSuggestion(modal.sid, modal.img, "video_prompt")}
          onGenPrompt={() => void genVideoPrompt(modal.sid, modal.img)}
          onClose={() => setModal(null)}
          onVideoOpen={(rel) => window.open(ctx.files(rel), "_blank")}
          onRun={async (opts) => {
            // Critério D7: o que vale é o CAMPO (estado da tela), não o último valor gerado — um
            // prompt escrito à mão e nunca gerado tem de animar igual. Só o campo VAZIO bloqueia.
            const m = photosRef.current[pkey(modal.sid, modal.img)] || EMPTY_PHOTO_META;
            const prompt = (m.prompt || "").trim();
            // A frase MANTÉM a substring "prompt de vídeo primeiro" de propósito: o caso
            // congelado C-STORYBOARD-30 (`scripts/qa/cenarios/storyboard.py:730`) espera por ela.
            // O "Escreva ou" é o que mudou de verdade nesta frente — o campo agora é aberto.
            if (!prompt) return toast("Escreva ou gere o prompt de vídeo primeiro.");
            if (opts.mode === "start_end" && !opts.endImage) return toast("Escolha a 2ª imagem (end frame).");
            const sid = modal.sid;
            const img = modal.img;
            try {
              const ok = await confirm({
                costFn: () =>
                  api(url("/video/cost"), {
                    method: "POST",
                    body: JSON.stringify({ scene_id: sid, mode: opts.mode, duration: opts.duration, model: opts.model }),
                  }),
                label: `Gerar animação de ${sceneLabelOf(sid)} (${opts.duration}s)`,
              });
              if (!ok) return;
              const body: Record<string, unknown> = {
                scene_id: sid,
                prompt,
                mode: opts.mode,
                duration: opts.duration,
                model: opts.model,
                photo: img,
              };
              if (opts.mode === "start_end") {
                body.start_image = img;
                body.end_image = opts.endImage;
              } else body.image = img;
              setModal(null);
              void progressJob(prog, {
                title: `Gerar animação · ${sceneLabelOf(sid)}`,
                subtitle: "Higgsfield (Kling) via CLI",
                start: () => api(url("/video/generate"), { method: "POST", body: JSON.stringify(body) }),
                jobUrl: url(`/video/job?scene_id=${encodeURIComponent(sid)}&photo=${encodeURIComponent(img)}`),
                done: async (j) => onVideoDone(sid, img, j as { video?: string }),
              }).catch((err: Error) => toast(err.message));
            } catch (err) {
              toast((err as Error).message);
            }
          }}
        />
      ) : null}

      {modal?.kind === "reorder" ? (
        <ReorderModal
          scenes={scenes}
          filesUrl={(rel) => ctx.files(rel)}
          onClose={() => setModal(null)}
          onSave={(orderIdx) => void saveReorder(orderIdx)}
        />
      ) : null}

      {modal?.kind === "lightbox" ? (
        <Lightbox rel={modal.rel} fileUrl={ctx.files(modal.rel)} onClose={() => setModal(null)} />
      ) : null}

      {modal?.kind === "annotate" ? (
        <Annotate
          title="Marcar área [extensão]"
          subtitle={`${modal.src.label} · rabisque a região que deve mudar`}
          sourceUrl={modal.src.url}
          brush={10}
          onSave={(blob) => saveAnnotation(modal.src, blob)}
          onClose={() => setModal(null)}
        />
      ) : null}

      {modal?.kind === "maskeditor" ? (
        <MaskEditor
          title="Inpaint local (grátis) [extensão]"
          subtitle={`${modal.src.label} · pinte a região a mudar`}
          sourceUrl={modal.src.url}
          models={localSt?.inpaint_models || []}
          onRun={(blob, instruction, opts) => runLocalInpaint(modal.src, blob, instruction, opts)}
          onDone={() => void refresh()}
          onClose={() => setModal(null)}
        />
      ) : null}
    </>
  );
}

function arcLabelOf(meta: InstructionsMeta, id?: string): string {
  return (meta.arc || []).reduce((acc, a) => (a.id === id ? a.label : acc), id || "");
}

// ================= subcomponentes =================

/** Textarea que cresce com o conteúdo — o `ui.autosize` do vanilla. */
function AutoTextarea({
  className,
  rows,
  placeholder,
  value,
  onChange,
  ariaLabel,
}: {
  className: string;
  rows: number;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  ariaLabel?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);
  return (
    <textarea
      ref={ref}
      className={className}
      rows={rows}
      placeholder={placeholder}
      value={value}
      aria-label={ariaLabel}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

/**
 * Seletor de preset de realismo — `[extensão]`, com HERANÇA explícita (FDD §4 fluxo 3, item 3).
 *
 * Três opções distintas, e o default é a primeira: "(padrão da campanha: X)" com valor VAZIO
 * (herda — a chave `preset` sai ausente do corpo), "(sem preset)" com valor `off` (manda `null`,
 * a rota de fuga que o vanilla já tinha) e cada preset do catálogo. A classe `sbRealismPreset` e
 * o `aria-label` são contrato de DOM e não mudam.
 */
function RealismField({
  value,
  presets,
  inherited,
  onChange,
}: {
  value: string;
  presets: RealismPreset[];
  /** Preset que a campanha resolve para esta ação (`null` quando ela também não tem preset). */
  inherited: string | null;
  onChange: (v: string) => void;
}) {
  return (
    <label className="field sb-realism">
      <span className="eyebrow lbl">
        preset de realismo <span className="ext">[extensão]</span>
      </span>
      <select className="sbRealismPreset" aria-label="Preset de realismo (extensão)" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value={PRESET_INHERIT}>{`(padrão da campanha: ${presetLabel(presets, inherited)})`}</option>
        <option value={PRESET_OFF}>(sem preset)</option>
        {presets.map((p) => (
          <option key={p.id} value={p.id} title={p.desc_pt}>
            {`${p.name} — ${p.desc_pt}`}
          </option>
        ))}
      </select>
    </label>
  );
}

/**
 * Campo ABERTO de prompt de uma foto (`[extensão]` Wave 11 · F06, FDD §4 fluxo 4). Um só componente
 * para os dois campos e para as duas telas que os mostram (a linha de foto e o modal de animação),
 * porque o bloco de vídeo estava duplicado e as duas cópias precisam do mesmo contrato de DOM.
 *
 * Três coisas não são negociáveis aqui:
 *   1. `genClass` é um BOTÃO ("Gerar com IA"), nunca um campo — `.sbVidPrompt` é o que
 *      C-STORYBOARD-27/28 clicam;
 *   2. quando há `mirrorClass`, o `<p class="txt {mirrorClass}">` fica dentro da caixa com o
 *      atributo `hidden`, espelhando o valor do campo: invisível ao usuário, legível por
 *      `text_content()` (C-STORYBOARD-27/33 e o dump de `textContent` do baseline);
 *   3. a caixa fica SEMPRE visível — ela deixou de ser um resultado e virou um campo.
 */
function PromptField({
  boxClass,
  fieldClass,
  genClass,
  copyClass,
  mirrorClass,
  label,
  placeholder,
  value,
  origin,
  suggestion,
  onChange,
  onGen,
  onDismiss,
}: {
  boxClass: string;
  fieldClass: string;
  genClass: string;
  copyClass: string;
  /** Espelho de leitura para o oráculo de QA; só o prompt de vídeo tem um. */
  mirrorClass?: string | undefined;
  label: string;
  placeholder: string;
  value: string;
  origin?: PhotoOrigin | undefined;
  /** Sugestão recusada na pergunta "Substituir?" — fica copiável até o usuário dispensá-la. */
  suggestion?: string | undefined;
  onChange: (v: string) => void;
  onGen: () => void;
  onDismiss: () => void;
}) {
  const [copied, setCopied] = useState("");
  const [copiedSug, setCopiedSug] = useState("");
  return (
    <div className={`prompt sm ${boxClass}`}>
      <div className="row wrap">
        <span className="eyebrow">{label}</span>
        <span className="chip sbPromptOrigin" title="procedência deste texto">
          {originLabel(origin)}
        </span>
        <button type="button" className={`ghost mini ${genClass}`} aria-label={`Gerar ${label} com IA`} onClick={onGen}>
          Gerar com IA
        </button>
        <button
          type="button"
          className={`link ${copyClass}`}
          onClick={async () => {
            const ok = await copy(value);
            setCopied(ok ? "copiado ✓" : "copie à mão");
            setTimeout(() => setCopied(""), 1500);
          }}
        >
          Copiar
        </button>
        <span className="ok">{copied}</span>
      </div>
      <AutoTextarea
        className={`txt ${fieldClass}`}
        rows={2}
        placeholder={placeholder}
        value={value}
        ariaLabel={label}
        onChange={onChange}
      />
      {mirrorClass ? (
        <p className={`txt ${mirrorClass}`} hidden>
          {value}
        </p>
      ) : null}
      {suggestion ? (
        <div className="row wrap sbPromptSuggestion">
          <span className="eyebrow">sugestão não aplicada</span>
          <button
            type="button"
            className="link sbSuggestCopy"
            onClick={async () => {
              const ok = await copy(suggestion);
              setCopiedSug(ok ? "copiado ✓" : "copie à mão");
              setTimeout(() => setCopiedSug(""), 1500);
            }}
          >
            Copiar
          </button>
          <button type="button" className="link sbSuggestDismiss" onClick={onDismiss}>
            dispensar
          </button>
          <span className="ok">{copiedSug}</span>
          <p className="txt sbSuggestText">{suggestion}</p>
        </div>
      ) : null}
    </div>
  );
}

interface PhotoRowProps {
  sid: string;
  img: string;
  pi: number;
  count: number;
  isPrimary: boolean;
  meta: PhotoMeta;
  fileUrl: string;
  filesUrl: (rel: string) => string;
  realismPresets: RealismPreset[];
  /** Preset que a campanha resolve para a ação `motion` — o "X" de "(padrão da campanha: X)". */
  inheritedPreset: string | null;
  /** Esta foto está sendo arrastada agora (`.dragging`). */
  isDragging: boolean;
  /** Há um arrasto pairando sobre esta `.sb-key` (`.dragover`). */
  isDragOver: boolean;
  /** As DEMAIS cenas, para o "Mover para…" (alternativa por teclado ao arrasto, critério B7). */
  moveTargets: { i: number; label: string }[];
  /** Sugestões RECUSADAS por campo (a pergunta "Substituir?" continua copiável, critério D3). */
  suggestions: { image_prompt?: string | undefined; video_prompt?: string | undefined };
  onDesc: (v: string) => void;
  onPreset: (v: string) => void;
  /** Digitação nos campos abertos — o chamador marca `origin` como `manual` e agenda o debounce. */
  onImgPrompt: (v: string) => void;
  onVidPrompt: (v: string) => void;
  onDismissSuggestion: (field: PromptField) => void;
  onStar: () => void;
  onRemove: () => void;
  onLightbox: () => void;
  onGenPrompt: () => void;
  onGenImgPrompt: () => void;
  onUseLocal: () => void;
  onAnim: () => void;
  onAnnotate: () => void;
  onUp: () => void;
  onDown: () => void;
  onMove: (to: number) => void;
  onDragStartPhoto: (e: DragEvent) => void;
  onDragEndPhoto: () => void;
  onDragOverPhoto: (e: DragEvent) => void;
  onDragLeavePhoto: () => void;
  onDropPhoto: (e: DragEvent) => void;
  onVideoOpen: (rel: string) => void;
}
function PhotoRow(p: PhotoRowProps) {
  const videos = (p.meta.videos || []).filter(Boolean);
  const last = videos.length ? videos[videos.length - 1] : null;
  return (
    <div className={`sb-photorow${p.isDragging ? " dragging" : ""}`} data-img={p.img} data-pi={p.pi}>
      <div
        className={`sb-key${p.isPrimary ? " primary" : ""}${p.isDragOver ? " dragover" : ""}`}
        data-img={p.img}
        draggable
        title="clique para ver em tamanho real · arraste para reordenar ou para outra cena"
        onDragStart={p.onDragStartPhoto}
        onDragEnd={p.onDragEndPhoto}
        onDragOver={p.onDragOverPhoto}
        onDragLeave={p.onDragLeavePhoto}
        onDrop={p.onDropPhoto}
        onClick={(e) => {
          if ((e.target as HTMLElement).closest("button")) return;
          p.onLightbox();
        }}
      >
        <img loading="lazy" src={p.fileUrl} alt="" />
        <button type="button" className="sb-star" data-star={p.img} title={p.isPrimary ? "principal da cena" : "marcar como principal"} onClick={p.onStar}>
          ★
        </button>
        <button type="button" className="sb-rm" data-rm={p.img} title="remover imagem" onClick={p.onRemove}>
          ✕
        </button>
      </div>
      <div className="sb-photocol">
        <AutoTextarea
          className="txt sbVidDesc"
          rows={2}
          placeholder="o que acontece no vídeo desta foto (em inglês)"
          value={p.meta.desc}
          onChange={p.onDesc}
        />
        <RealismField
          value={p.meta.preset}
          presets={p.realismPresets}
          inherited={p.inheritedPreset}
          onChange={p.onPreset}
        />
        {/* `[extensão]` campo aberto de KEYFRAME (critério D2). Nasce nesta wave: antes o prompt de
            imagem da foto não existia na tela — só o do roteiro, que não era editável. */}
        <PromptField
          boxClass="sbImgPromptBox"
          fieldClass="sbImgPromptField"
          genClass="sbImgPrompt"
          copyClass="sbImgCopy"
          label="Prompt de imagem (keyframe)"
          placeholder="o keyframe desta foto (em inglês, aula 007) — escreva ou gere com IA"
          value={p.meta.imgPrompt}
          origin={p.meta.origin?.image_prompt}
          suggestion={p.suggestions.image_prompt}
          onChange={p.onImgPrompt}
          onGen={p.onGenImgPrompt}
          onDismiss={() => p.onDismissSuggestion("image_prompt")}
        />
        {/* A `.sbVidPromptBox` fica SEMPRE visível agora (ela contém o campo) e o
            `<p class="txt sbVidPromptText">` continua dentro dela como espelho `hidden`: invisível
            ao usuário, legível por `text_content()` (C-STORYBOARD-27/33, decisão auto-aceita 8). */}
        <PromptField
          boxClass="sbVidPromptBox"
          fieldClass="sbVidPromptField"
          genClass="sbVidPrompt"
          copyClass="sbVidCopy"
          mirrorClass="sbVidPromptText"
          label="Prompt de vídeo"
          placeholder="o movimento desta foto (em inglês) — escreva ou gere com IA"
          value={p.meta.prompt}
          origin={p.meta.origin?.video_prompt}
          suggestion={p.suggestions.video_prompt}
          onChange={p.onVidPrompt}
          onGen={p.onGenPrompt}
          onDismiss={() => p.onDismissSuggestion("video_prompt")}
        />
        <div className="sbVidView">
          {last ? (
            <>
              <video className="sbVidPlayer" src={p.filesUrl(last)} controls preload="metadata" />
              <div className="row wrap">
                <button type="button" className="link sbVidView" data-video={last} onClick={() => p.onVideoOpen(last)}>
                  Ver vídeo em tamanho real
                </button>
                <span className="fine">
                  {videos.length} take(s) · esse vídeo é usado na etapa 6 (animação)
                </span>
              </div>
            </>
          ) : null}
        </div>
      </div>
      <div className="sb-photoacts">
        {/* Critério D8: leva o prompt de imagem desta foto para o motor local (painel 01b). */}
        <button
          type="button"
          className="ghost mini sbUseLocal"
          title="levar o prompt de imagem desta foto para o motor local (grátis) [extensão]"
          onClick={p.onUseLocal}
        >
          Usar no motor local
        </button>
        <button type="button" className="primary mini sbAnim" title="gerar a animação desta foto (Higgsfield)" onClick={p.onAnim}>
          Gerar animação
        </button>
        <button type="button" className="ghost mini sbAnnotate" title="marcar uma área desta foto e pedir a mudança só ali [extensão]" onClick={p.onAnnotate}>
          Marcar área
        </button>
        <div className="sb-photo-reorder">
          <button type="button" className="ghost mini sbPhotoUp" title="subir foto" disabled={p.pi === 0} onClick={p.onUp}>
            ↑
          </button>
          <button type="button" className="ghost mini sbPhotoDown" title="descer foto" disabled={p.pi >= p.count - 1} onClick={p.onDown}>
            ↓
          </button>
        </div>
        {/* Alternativa por TECLADO ao arrasto entre cenas (critério B7): mesmo efeito, sem mouse. */}
        <select
          className="sbPhotoMove"
          aria-label={`Mover esta foto para outra cena (${p.img.split("/").pop() || ""})`}
          title="mover esta foto para outra cena"
          disabled={!p.moveTargets.length}
          value=""
          onChange={(e) => {
            const to = e.target.value;
            if (to !== "") p.onMove(+to);
          }}
        >
          <option value="">Mover para…</option>
          {p.moveTargets.map((t) => (
            <option key={t.i} value={t.i}>
              {t.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

// ---------- modais ----------
function ImportIdeasModal({
  onClose,
  onFiles,
  onDownloads,
  onHistory,
}: {
  onClose: () => void;
  onFiles: (files: FileList) => void;
  onDownloads: (minutes: number) => void;
  onHistory: () => void;
}) {
  const [minutes, setMinutes] = useState(120);
  const drop = useUpload((f) => onFiles(f));
  return (
    <Modal title="Importar ideias" subtitle="Gere na interface da Higgsfield e traga os resultados para o storyboard." onClose={onClose}>
      <div className="import-row">
        <label
          className={drop.isOver ? "drop over" : "drop"}
          id="sbDrop"
          onDragOver={drop.rootProps.onDragOver}
          onDragLeave={drop.rootProps.onDragLeave}
          onDrop={drop.rootProps.onDrop}
        >
          Arraste imagens aqui ou <input id="sbUpload" {...drop.inputProps} accept="image/*" />
          <u onClick={drop.open}>escolha arquivos</u>
        </label>
        <div className="col">
          <button type="button" id="sbBtnDownloads" className="ghost" onClick={() => onDownloads(minutes)}>
            Importar da pasta Downloads
          </button>
          <label className="inline">
            últimos <input id="sbMinutes" className="mini wide" type="number" value={minutes} min={5} onChange={(e) => setMinutes(+e.target.value)} /> min
          </label>
          <button type="button" id="sbBtnHistory" className="ghost" onClick={onHistory}>
            Importar do histórico Higgsfield
          </button>
          <span className="fine">precisa de login no CLI</span>
        </div>
      </div>
    </Modal>
  );
}

function HistoryModal({
  items,
  jobs,
  onClose,
  onImport,
}: {
  items: HistoryItem[];
  jobs: number;
  onClose: () => void;
  onImport: (keys: string[]) => void;
}) {
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const toggle = (k: string) =>
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  const all = () =>
    setPicked((prev) => (prev.size === items.length ? new Set() : new Set(items.map((it) => it.key))));
  return (
    <Modal
      title="Histórico Higgsfield — escolher o que importar"
      subtitle={`${items.length} mídias de ${jobs} jobs. Clique para marcar/desmarcar; só as marcadas entram no storyboard.`}
      onClose={onClose}
      actions={[{ label: "Importar escolhidas", kind: "primary", close: false, onClick: () => onImport([...picked]) }]}
    >
      <div className="import-row" style={{ marginBottom: 8 }}>
        <button type="button" id="sbHistAll" className="ghost" onClick={all}>
          Selecionar tudo
        </button>
        <span className="fine" id="sbHistCount">
          {picked.size} escolhidas
        </span>
      </div>
      <div id="sbHistGrid" className="gallery sm">
        {items.length ? (
          items.map((it) => (
            <div key={it.key} className={`card${picked.has(it.key) ? " sel" : ""}`} data-key={it.key} tabIndex={0} title={it.prompt || ""} onClick={() => toggle(it.key)}>
              <img loading="lazy" src={it.url} alt="" />
              {it.prompt ? <span className="term">{it.prompt.slice(0, 60)}</span> : null}
            </div>
          ))
        ) : (
          <div className="empty">Nenhuma geração no histórico Higgsfield (gere na UI e volte aqui).</div>
        )}
      </div>
    </Modal>
  );
}

/**
 * Escolha das fotos de uma cena. A ação PRIMÁRIA é a de adicionar — contrato de DOM congelado com
 * `scripts/qa/cenarios/storyboard.py` (C-STORYBOARD-22 clica `.modal-actions button.primary`), e o
 * botão "Sem imagem" continua existindo com esse texto exato (C-STORYBOARD-23). "Substituir tudo"
 * é fantasma e passa por `window.confirm` no pai (critério B5).
 */
function PickerModal({
  i,
  ideas,
  selected,
  filtro,
  origens,
  onFiltro,
  filesUrl,
  onClose,
  onApply,
  onReplace,
  onNoImage,
  onImportar,
  onOpenFile,
}: {
  i: number;
  ideas: Idea[];
  selected: string[];
  filtro: string;
  origens: { key: string; label: string }[];
  onFiltro: (v: string) => void;
  filesUrl: (rel: string) => string;
  onClose: () => void;
  onApply: (ids: string[]) => void;
  onReplace: (ids: string[]) => void;
  onNoImage: () => void;
  onImportar: () => void;
  onOpenFile: (rel: string) => void;
}) {
  const marcadas = new Set(selected);
  const [sel, setSel] = useState<Set<string>>(new Set(ideas.filter((c) => marcadas.has(c.file)).map((c) => c.id)));
  const toggle = (id: string) =>
    setSel((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  // O MESMO filtro do painel 01 (critério B1): o estado mora no pai, a grade só o aplica.
  const visiveis = filtrarIdeias(ideas, filtro);
  return (
    <Modal
      title={`Cena ${i + 1} — escolher as imagens`}
      subtitle="Clique para marcar/desmarcar várias ideias; adicionar SOMA à galeria da cena, e a 1ª vira a principal quando ainda não há uma."
      onClose={onClose}
      actions={[
        { label: "Importar ideias…", kind: "ghost", close: false, onClick: onImportar },
        { label: "Adicionar à cena", kind: "primary", close: false, onClick: () => onApply([...sel]) },
        { label: "Substituir tudo", kind: "ghost", close: false, onClick: () => onReplace([...sel]) },
        { label: "Sem imagem", kind: "ghost", close: false, onClick: onNoImage },
      ]}
    >
      <div className="row wrap">
        <label className="inline">
          origem
          <select
            className="sbPickerFilter"
            aria-label="Filtrar ideias por origem"
            value={filtro}
            onChange={(e) => onFiltro(e.target.value)}
          >
            <option value="">todas as origens</option>
            {origens.map((o) => (
              <option key={o.key} value={o.key}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div id="sbGallery" className="gallery sm">
        {visiveis.length ? (
          visiveis.map((c) => (
            <div
              key={c.id}
              className={`card ${sel.has(c.id) ? "sel" : ""}`}
              data-id={c.id}
              data-file={c.file}
              data-source={ideaSourceKey(c)}
              tabIndex={0}
              title={c.prompt || ""}
              onClick={() => toggle(c.id)}
              onDoubleClick={() => onOpenFile(c.file)}
            >
              <img loading="lazy" src={filesUrl(c.thumb || c.file)} alt="" />
              <span className="term">{ideaSourceLabel(c)}</span>
            </div>
          ))
        ) : (
          <div className="empty">{ideas.length ? PICKER_EMPTY_FILTRO : PICKER_EMPTY}</div>
        )}
      </div>
    </Modal>
  );
}

interface AnimateModalProps {
  sid: string;
  img: string;
  fileUrl: string;
  others: string[];
  meta: PhotoMeta;
  models: string[];
  modelDefaults: { single: string; start_end: string };
  realismPresets: RealismPreset[];
  /** Preset que a campanha resolve para a ação `motion`. */
  inheritedPreset: string | null;
  filesUrl: (rel: string) => string;
  suggestion?: string | undefined;
  onDesc: (v: string) => void;
  onPreset: (v: string) => void;
  onVidPrompt: (v: string) => void;
  onDismissSuggestion: () => void;
  onGenPrompt: () => void;
  onClose: () => void;
  onVideoOpen: (rel: string) => void;
  onRun: (opts: { mode: string; duration: number; model: string | null; endImage: string | null }) => void;
}
function AnimateModal(p: AnimateModalProps) {
  const [mode, setMode] = useState("single");
  const [duration, setDuration] = useState("5");
  const [model, setModel] = useState(p.modelDefaults.single && p.models.includes(p.modelDefaults.single) ? p.modelDefaults.single : p.models[0] || "");
  const [endImage, setEndImage] = useState(p.others[0] || "");
  const videos = (p.meta.videos || []).filter(Boolean);
  const last = videos.length ? videos[videos.length - 1] : null;

  const onModeChange = (v: string) => {
    setMode(v);
    const def = v === "start_end" ? p.modelDefaults.start_end : p.modelDefaults.single;
    if (def && p.models.includes(def)) setModel(def);
  };

  return (
    <Modal
      title={`Gerar animação · ${sceneLabelOf(p.sid)}`}
      subtitle="Higgsfield (Kling) via CLI — duração, modelo e start/end frame."
      onClose={p.onClose}
      actions={[
        {
          label: "Gerar animação (gasta créditos)",
          kind: "primary",
          close: false,
          onClick: () => p.onRun({ mode, duration: +duration, model: model || null, endImage: mode === "start_end" ? endImage || null : null }),
        },
      ]}
    >
      <div className="sb-anim">
        <div className="sb-anim-preview">
          <img src={p.fileUrl} alt="" />
          <span className="lbl">start / referência: {p.img.split("/").pop()}</span>
        </div>
        <div className="sb-anim-ctrls">
          <AutoTextarea className="txt sbVidDesc" rows={2} placeholder="o que acontece no vídeo (em inglês)" value={p.meta.desc} onChange={p.onDesc} />
          <RealismField
          value={p.meta.preset}
          presets={p.realismPresets}
          inherited={p.inheritedPreset}
          onChange={p.onPreset}
        />
          {/* Mesmo bloco da linha de foto — inclusive o espelho `hidden` (decisão auto-aceita 8). */}
          <PromptField
            boxClass="sbVidPromptBox"
            fieldClass="sbVidPromptField"
            genClass="sbVidPrompt"
            copyClass="sbVidCopy"
            mirrorClass="sbVidPromptText"
            label="Prompt de vídeo"
            placeholder="o movimento desta foto (em inglês) — escreva ou gere com IA"
            value={p.meta.prompt}
            origin={p.meta.origin?.video_prompt}
            suggestion={p.suggestion}
            onChange={p.onVidPrompt}
            onGen={p.onGenPrompt}
            onDismiss={p.onDismissSuggestion}
          />
          <div className="row wrap">
            <label className="field">
              <span className="eyebrow lbl">duração</span>
              <select className="sbVidDur" value={duration} onChange={(e) => setDuration(e.target.value)}>
                <option value="5">5s</option>
                <option value="10">10s</option>
              </select>
            </label>
            <label className="field">
              <span className="eyebrow lbl">modelo</span>
              <select className="sbVidModel" title="modelo de vídeo (Higgsfield)" value={model} onChange={(e) => setModel(e.target.value)}>
                {p.models.map((mm) => (
                  <option key={mm} value={mm}>
                    {mm}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="row wrap">
            <label className="field">
              <span className="eyebrow lbl">frames</span>
              <select className="sbVidMode" value={mode} onChange={(e) => onModeChange(e.target.value)}>
                <option value="single">1 frame (esta foto)</option>
                <option value="start_end" disabled={!p.others.length}>
                  start → end (2ª imagem)
                </option>
              </select>
            </label>
            <label className={`field sbVidPair${mode === "start_end" ? "" : " hidden"}`}>
              <span className="eyebrow lbl">end frame (2ª imagem)</span>
              <select className="sbVidEnd" value={endImage} onChange={(e) => setEndImage(e.target.value)}>
                {p.others.map((f) => (
                  <option key={f} value={f}>
                    {f.split("/").pop()}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <span className="fine">start = esta foto; end = a 2ª imagem escolhida (transição, aula 012).</span>
          <div className="sbVidView">
            {last ? (
              <>
                <video className="sbVidPlayer" src={p.filesUrl(last)} controls preload="metadata" />
                <div className="row wrap">
                  <button type="button" className="link sbVidView" data-video={last} onClick={() => p.onVideoOpen(last)}>
                    Ver vídeo em tamanho real
                  </button>
                  <span className="fine">{videos.length} take(s) · esse vídeo é usado na etapa 6 (animação)</span>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </Modal>
  );
}

function ReorderModal({
  scenes,
  filesUrl,
  onClose,
  onSave,
}: {
  scenes: Scene[];
  filesUrl: (rel: string) => string;
  onClose: () => void;
  onSave: (orderIdx: number[]) => void;
}) {
  const [order, setOrder] = useState<number[]>(scenes.map((_, i) => i));
  const dragIdx = useRef<number | null>(null);
  const move = (pos: number, dir: -1 | 1) => {
    const to = pos + dir;
    if (to < 0 || to >= order.length) return;
    setOrder((prev) => {
      const next = prev.slice();
      const it = next.splice(pos, 1)[0];
      if (it === undefined) return prev;
      next.splice(to, 0, it);
      return next;
    });
  };
  return (
    <Modal
      title="Reordenar cenas"
      subtitle="Arraste (ou use ↑/↓) e salve para reescrever a ordem — regrava storyboard.md."
      onClose={onClose}
      actions={[
        { label: "Cancelar", kind: "ghost" },
        { label: "Salvar ordem", kind: "primary", close: false, onClick: () => onSave(order) },
      ]}
    >
      <ol className="sb-reorder">
        {order.map((idx, pos) => {
          const s = scenes[idx];
          if (!s) return null;
          const label = (s.text || "").trim() || `cena ${idx + 1}`;
          return (
            <li
              className="sb-ro-item"
              draggable
              data-i={idx}
              key={idx}
              onDragStart={() => (dragIdx.current = pos)}
              onDragEnd={() => (dragIdx.current = null)}
              onDragOver={(e) => {
                e.preventDefault();
                const from = dragIdx.current;
                if (from == null || from === pos) return;
                setOrder((prev) => {
                  const next = prev.slice();
                  const it = next.splice(from, 1)[0];
                  if (it === undefined) return prev;
                  next.splice(pos, 0, it);
                  return next;
                });
                dragIdx.current = pos;
              }}
            >
              <span className="sb-ro-grip" title="arraste para reordenar">
                ⋮⋮
              </span>
              <span className="sb-ro-thumb">{s.primary ? <img loading="lazy" src={filesUrl(s.primary)} alt="" /> : null}</span>
              <span className="sb-ro-txt">{label}</span>
              <span className="sb-ro-acts">
                <button type="button" className="ghost mini sb-ro-up" title="subir" onClick={() => move(pos, -1)}>
                  ↑
                </button>
                <button type="button" className="ghost mini sb-ro-down" title="descer" onClick={() => move(pos, 1)}>
                  ↓
                </button>
              </span>
            </li>
          );
        })}
      </ol>
    </Modal>
  );
}

function Lightbox({ rel, fileUrl, onClose }: { rel: string; fileUrl: string; onClose: () => void }) {
  const isVid = /\.(mp4|webm|mov|m4v)$/i.test(rel);
  return (
    <Modal title="Tamanho real" subtitle={String(rel).split("/").pop() || ""} onClose={onClose}>
      <div className="sb-lightbox">
        {isVid ? (
          <video src={fileUrl} controls autoPlay className="sb-lightbox-media" />
        ) : (
          <img src={fileUrl} alt="" className="sb-lightbox-media" />
        )}
      </div>
    </Modal>
  );
}

// ---------- CSS escopado da tela (porte VERBATIM do <style> do view.html) ----------
const STYLE = `
  .sb-base{align-self:start}
  .sb-key{position:relative;width:96px;height:128px;border-radius:8px;overflow:hidden;border:1px solid var(--line-2);cursor:zoom-in;flex:0 0 auto}
  .sb-key img{width:100%;height:100%;object-fit:cover;display:block}
  .sb-key.primary{border-color:#4FC8D9;box-shadow:0 0 0 2px rgba(79,200,217,.55)}
  .sb-key.dragover{border-color:#4FC8D9;box-shadow:0 0 0 2px rgba(79,200,217,.35)}
  .sb-key .sb-star,.sb-key .sb-rm{position:absolute;top:2px;border:0;border-radius:5px;padding:0 5px;
    font-size:11px;line-height:1.5;cursor:pointer;background:rgba(0,0,0,.6);color:#9FE3EE}
  .sb-key .sb-star{left:2px}
  .sb-key.primary .sb-star{color:#FFD54A}
  .sb-key .sb-rm{right:2px;color:#F2A5A5}
  .sb-key .sb-star:hover,.sb-key .sb-rm:hover{background:rgba(0,0,0,.82);color:#D7F4F9}
  /* O rótulo vem do DOM (critério B2): era um ::after de 9px, invisível a leitor de tela e ao
     dump de textContent, no único ponto de entrada de foto na cena. */
  .sb-pick{width:96px;height:128px;position:relative;cursor:pointer;display:grid;place-items:center;
    border:1px dashed var(--line-2);border-radius:8px;background:transparent;padding:6px;
    font-family:"IBM Plex Mono",monospace;font-size:10px;line-height:1.3;color:#9FE3EE;text-align:center}
  .sb-pick:hover,.sb-pick:focus-visible{outline:1px dashed rgba(79,200,217,.5)}
  .sb-ideas-head{margin-top:14px;align-items:center}
  #sbIdeasGallery{margin-top:8px}
  #sbIdeasGallery .card{cursor:grab}
  #sbIdeasGallery .card.sel{border-color:#4FC8D9;box-shadow:0 0 0 2px rgba(79,200,217,.45)}
  #sbIdeasGallery .card.dragging{opacity:.5}
  .sb-phototable.dragover{outline:1px dashed rgba(79,200,217,.6);outline-offset:4px;border-radius:8px}
  .sbPhotoMove{width:100%;font-size:var(--fs-sm)}
  .sh-scene-id{font-size:11px;color:var(--ink-row);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sh-builder{margin-bottom:14px}
  #sceneList .rowcard{position:relative}
  #sceneList .sh-act{opacity:0;transition:opacity .15s;position:absolute;right:14px;top:14px;z-index:2;
    padding:2px 7px;border:0;border-radius:5px;background:rgba(0,0,0,.55);color:#9FE3EE;
    font-family:"IBM Plex Mono",monospace;font-size:10px;font-weight:400;line-height:1.4;text-decoration:none}
  #sceneList .sh-act:hover{background:rgba(0,0,0,.78);color:#D7F4F9}
  #sceneList .rowcard:hover .sh-act,#sceneList .rowcard:focus-within .sh-act{opacity:1}

  #sbScenes .scene-row{display:block;padding:12px 14px}
  .sb-scenehead{display:grid;grid-template-columns:76px minmax(0,1fr) auto;gap:10px;align-items:start}
  .sb-scenehead textarea.sbTxt{padding-top:2px}
  .sb-phototable{display:flex;flex-direction:column;gap:14px;margin-top:12px}
  .sb-phototable:empty{display:none}
  .sb-photorow{display:grid;grid-template-columns:96px minmax(0,1fr) minmax(120px,auto);gap:12px;align-items:start}
  .sb-photorow.dragging{opacity:.5}
  .sb-photocol{display:flex;flex-direction:column;gap:6px;min-width:0}
  .sb-photoacts{display:flex;flex-direction:column;gap:6px;align-items:stretch}
  .sb-realism{gap:3px}
  .sb-realism>select{max-width:100%}
  .sb-photo-reorder{display:flex;gap:4px}
  .sb-photo-reorder button{flex:1}
  .sbVidDesc{width:100%;background:var(--surface);border:1px solid var(--line);border-radius:8px;
    padding:8px 10px;font:inherit;font-size:var(--fs-sm);color:var(--ink);resize:none;overflow:hidden;field-sizing:content}
  .sbVidDesc:focus{outline:none;box-shadow:var(--ring)}
  .sbVidView{display:flex;flex-direction:column;gap:6px}
  .sbVidView:empty{display:none}
  .sbVidPlayer{max-width:320px;width:100%;border-radius:8px;border:1px solid var(--line-2);display:block}

  .modal:has(.sb-anim){width:min(760px,100%)}
  .sb-anim{display:grid;grid-template-columns:200px minmax(0,1fr);gap:16px;align-items:start}
  .sb-anim-preview{position:relative}
  .sb-anim-preview img{width:100%;border-radius:8px;border:1px solid var(--line-2);display:block}
  .sb-anim-preview .lbl{display:block;margin-top:6px;font-size:var(--fs-sm);color:var(--ink-3)}
  .sb-anim-ctrls{display:flex;flex-direction:column;gap:12px;min-width:0}
  .sb-anim-ctrls .row.wrap{gap:10px}
  .sb-anim-ctrls select{width:100%}
  .sb-anim .sbVidPlayer{max-width:100%}
  @media (max-width:620px){.sb-anim{grid-template-columns:1fr}}

  .modal:has(.sb-reorder){width:min(920px,100%)}
  .sb-reorder{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
  .sb-ro-item{display:flex;align-items:center;gap:12px;padding:8px 10px;background:var(--surface-2);
    border:1px solid var(--line);border-radius:var(--r-tile)}
  .sb-ro-item.dragging{opacity:.5}
  .sb-ro-grip{cursor:grab;color:var(--ink-4);font-size:14px;user-select:none}
  .sb-ro-thumb{width:64px;height:64px;flex:0 0 auto;border-radius:8px;overflow:hidden;border:1px solid var(--line-2);background:var(--stripes-sm)}
  .sb-ro-thumb img{width:100%;height:100%;object-fit:cover;display:block}
  .sb-ro-txt{flex:1;min-width:0;font-size:var(--fs-sm);color:var(--ink-row);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sb-ro-acts{display:flex;gap:5px;flex:0 0 auto}

  .modal:has(.sb-lightbox){width:min(1100px,100%)}
  .sb-lightbox{display:grid;place-items:center}
  .sb-lightbox-media{max-width:100%;max-height:78vh;display:block;border-radius:8px}

  .modal:has(.ann-wrap){width:min(980px,100%)}
  .sb-area-pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
  .sb-area-pair figure{margin:0;display:flex;flex-direction:column;gap:6px;min-width:0}
  .sb-area-pair img{width:100%;border-radius:8px;border:1px solid var(--line-2);display:block}
  .sb-area-pair figcaption{font-size:var(--fs-sm);color:var(--ink-3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sb-area-warn{margin:0;padding-left:10px;border-left:2px solid var(--line-2);
    font-size:var(--fs-sm);color:var(--ink-3)}
  @media (max-width:620px){.sb-area-pair{grid-template-columns:1fr}}

  .sb-script-ctrls{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;align-items:end}
  .sb-script-ctrls>*{min-width:0}
  #sbScriptPreset{display:flex}
  #sbScriptPreset>.field{flex:1;min-width:0}
  .sb-script-read{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--ink-2)}
  .sb-script-warn{margin:0;padding-left:10px;border-left:2px solid var(--line-2);
    font-size:var(--fs-sm);color:var(--ink-3)}
  .sb-script-scene{display:grid;grid-template-columns:76px minmax(0,1fr);gap:10px;
    padding:12px 0;border-top:1px solid var(--line)}
  .sb-script-scene:first-child{border-top:0;padding-top:0}
  /* [extensão] Wave 11 · F06 — campos abertos de prompt e diagnóstico do CLI */
  .sbPromptOrigin{font-size:11px;text-transform:none}
  .sbImgPromptField,.sbVidPromptField{width:100%;min-height:52px;resize:vertical}
  .sbPromptSuggestion{margin-top:6px;padding-top:6px;border-top:1px dashed var(--line-2)}
  .sbSuggestText{margin:4px 0 0;flex:1 1 100%;font-size:var(--fs-sm);color:var(--ink-3)}
  .sb-cli-diag{display:flex;flex-direction:column;gap:4px;margin-top:8px;padding-left:10px;
    border-left:2px solid var(--line-2)}
  .sb-cli-diag .term{overflow-wrap:anywhere}
  .sb-script-txt{margin:0 0 8px;font-size:var(--fs-sm);color:var(--ink-row)}
  @media (max-width:620px){.sb-script-scene{grid-template-columns:1fr}}
`;
