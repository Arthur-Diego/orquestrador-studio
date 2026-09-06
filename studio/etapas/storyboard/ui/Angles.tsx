// Metade 2 — ângulos por cena (aula 011) + cena do produto (aula 013). Porte React do `makeAngles`
// do `view.js` vanilla. Painel 04 (lista de cenas + card do produto) e painel 05 (cena aberta:
// prompts de ângulo, galeria de candidatos, ordem dos frames). Escreve `storyboard/storyboard.json`.
import { useCallback, useEffect, useState } from "react";
import {
  Modal,
  progressJob,
  useCostConfirm,
  useProgress,
  useUpload,
} from "../../../../frontend/src/ui";
import type { StudioCtx } from "../../../../frontend/src/shell/plugin";
import type { AngleScene, Candidate, LocalStatus, ProductScene, PromptOut, Script } from "./types";

const PRODUCT = "__produto__"; // cena virtual: o card "produto" do painel 04
const sceneLabel = (id: string) => String(id || "").replace(/^cena/, "cena ");
/** Id de cena que o BACKEND entende (o card virtual do painel 04 é o literal `product`). */
const sceneId = (s: string | null) => (s === PRODUCT ? "product" : s || "");
//: `[extensão]` — o caminho da aula 011 (gerar na UI da Higgsfield e importar) continua sendo o
//: primeiro da tela; os dois atalhos abaixo são adicionais e trazem o custo no rótulo (ADR-004).
const AULA_NOTE =
  "O caminho da aula continua sendo gerar na UI da Higgsfield e importar (chip acima). Os atalhos abaixo são extras.";

interface AnglesProps {
  ctx: StudioCtx;
  refreshGuide: () => void;
  /** Chave que muda quando o projeto troca — força o boot (onProject). */
  bootKey: unknown;
}

type ModalKind = null | { kind: "import" } | { kind: "base"; id: string };

export function Angles({ ctx, refreshGuide, bootKey }: AnglesProps) {
  const { api, apiUpload, toast } = ctx;
  const base = useCallback(() => `/api/projects/${ctx.pid()}/storyboard/angles`, [ctx]);
  //: `[extensão]` as rotas do motor local vivem FORA do namespace `angles` (`.../storyboard/local`).
  const sbBase = useCallback(() => `/api/projects/${ctx.pid()}/storyboard`, [ctx]);

  const [scenes, setScenes] = useState<AngleScene[]>([]);
  const [scene, setScene] = useState<string | null>(null);
  const [cands, setCands] = useState<Candidate[]>([]);
  const [prod, setProd] = useState<Candidate[]>([]);
  const [order, setOrder] = useState<string[]>([]);
  const [prodState, setProdState] = useState<ProductScene>({ ref_ready: false, selected: false });
  const [prodTick, setProdTick] = useState(0);
  const [palette, setPalette] = useState<string[]>([]);
  const [erroLista, setErroLista] = useState<string>("");
  const [prompts, setPrompts] = useState<PromptOut[]>([]);
  const [modal, setModal] = useState<ModalKind>(null);
  const [folder, setFolder] = useState<string>("");

  // controles do builder de prompt
  const [promptKind, setPromptKind] = useState<"angle" | "edit">("angle");
  const [subject, setSubject] = useState("");
  const [scale, setScale] = useState("close");
  const [angle, setAngle] = useState("eye-level");
  const [edits, setEdits] = useState("");
  const [upscaled, setUpscaled] = useState(false);
  const [minutes, setMinutes] = useState(120);
  const [copied, setCopied] = useState<number | null>(null);

  // `[extensão]` barra de geração por cena (motor local grátis + CLI pago) — ADR-016/033.
  const [localSt, setLocalSt] = useState<LocalStatus | null>(null);
  const [hf, setHf] = useState<{ installed?: boolean; logged_in?: boolean } | null>(null);
  const [script, setScript] = useState<Script | null>(null);
  const [genPrompt, setGenPrompt] = useState("");
  const [genCount, setGenCount] = useState(4);
  const [prog, progEl] = useProgress();
  const { confirm, element: costEl } = useCostConfirm();

  const isProduct = scene === PRODUCT;
  const prodPick = () => prod.find((c) => c.selected) || null;
  const localReady = !!localSt?.ready;
  const cliReady = !!hf && !!hf.installed && !!hf.logged_in;
  const localWhy = localReady ? "" : localSt?.detail || "Motor local offline: suba o ComfyUI (porta 8188).";
  const cliWhy = cliReady ? "" : "CLI da Higgsfield ausente ou deslogado — gere na UI da Higgsfield e importe.";

  // ------- carregamentos -------
  const loadScenes = useCallback(async () => {
    if (!ctx.pid()) return;
    try {
      const r = (await api(`${base()}/scenes`)) as {
        scenes: AngleScene[];
        product_scene?: ProductScene;
        palette: { colors?: string[] };
      };
      setScenes(r.scenes);
      setProdState(r.product_scene || { ref_ready: false, selected: false });
      setPalette(r.palette.colors || []);
      setErroLista("");
    } catch (err) {
      setErroLista((err as Error).message);
    }
  }, [api, base, ctx]);

  const loadProd = useCallback(async () => {
    if (!ctx.pid()) return;
    try {
      setProd(((await api(`${base()}/product/candidates`)) as { candidates: Candidate[] }).candidates);
    } catch {
      setProd([]);
    }
    setProdTick(Date.now());
  }, [api, base, ctx]);

  const loadCands = useCallback(
    async (sid: string) => {
      try {
        const lista = ((await api(`${base()}/scenes/${sid}/candidates`)) as { candidates: Candidate[] })
          .candidates;
        setCands(lista);
        // Reidrata a escolha JÁ SALVA da cena (o backend devolve `selected`/`selected_order`):
        // sem isso, reabrir a cena mostrava "0 escolhidos" e "Salvar ordem" apagava os shots.
        const salvos = lista
          .filter((c) => c.selected)
          .sort((a, b) => (a.selected_order || 0) - (b.selected_order || 0))
          .map((c) => c.id);
        setOrder(salvos);
      } catch (err) {
        setCands([]);
        toast((err as Error).message);
      }
    },
    [api, base, toast],
  );

  /**
   * Prompt sugerido da cena, na ordem do FDD §4: `image_prompt` da cena → `image_prompt` da cena
   * correspondente do roteiro (`script.json`) → o texto da cena. Tudo opcional: F07 não depende da
   * persistência que outra frente vai criar.
   */
  const promptOf = useCallback(
    (id: string, lista: AngleScene[], sc: Script | null): string => {
      const s = lista.find((x) => x.id === id);
      if (!s) return "";
      if (s.image_prompt) return s.image_prompt;
      const i = (s.n || lista.indexOf(s) + 1) - 1;
      const doRoteiro = (sc?.scenes || [])[i];
      return doRoteiro?.image_prompt || s.text || "";
    },
    [],
  );

  const openScene = useCallback(
    async (id: string, lista?: AngleScene[], sc?: Script | null) => {
      setScene(id);
      setOrder([]);
      setPrompts([]);
      setGenPrompt(id === PRODUCT ? "" : promptOf(id, lista ?? scenes, sc === undefined ? script : sc));
      if (id === PRODUCT) {
        await loadProd();
      } else {
        await loadCands(id);
      }
    },
    [loadCands, loadProd, promptOf, scenes, script],
  );

  // Boot / troca de projeto: carrega tudo e abre a 1ª cena (ou o produto) — o `onProject` do vanilla.
  useEffect(() => {
    let vivo = true;
    void (async () => {
      if (!ctx.pid()) return;
      setScene(null);
      setOrder([]);
      setPrompts([]);
      let sc: AngleScene[] = [];
      try {
        const r = (await api(`${base()}/scenes`)) as {
          scenes: AngleScene[];
          product_scene?: ProductScene;
          palette: { colors?: string[] };
        };
        if (!vivo) return;
        sc = r.scenes;
        setScenes(sc);
        setProdState(r.product_scene || { ref_ready: false, selected: false });
        setPalette(r.palette.colors || []);
        setErroLista("");
      } catch (err) {
        if (vivo) setErroLista((err as Error).message);
      }
      // `[extensão]`: prontidão das pontes + roteiro (para o prompt sugerido), uma vez por montagem.
      let roteiro: Script | null = null;
      try {
        const st = (await api(`${sbBase()}/local/status`)) as LocalStatus;
        if (vivo) setLocalSt(st);
      } catch {
        if (vivo) setLocalSt(null);
      }
      try {
        const st = (await api("/api/higgsfield/status")) as { installed?: boolean; logged_in?: boolean };
        if (vivo) setHf(st);
      } catch {
        if (vivo) setHf(null);
      }
      try {
        roteiro = ((await api(`${sbBase()}/script`)) as { script?: Script }).script || null;
      } catch {
        roteiro = null;
      }
      if (vivo) setScript(roteiro);
      await loadProd();
      if (!vivo) return;
      await openScene(sc[0] ? sc[0].id : PRODUCT, sc, roteiro);
    })();
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bootKey]);

  // ------- ordem da galeria -------
  const reload = useCallback(async () => {
    if (isProduct) {
      await loadProd();
      await loadScenes();
    } else if (scene) {
      await loadCands(scene);
      await loadScenes();
    }
  }, [isProduct, scene, loadProd, loadScenes, loadCands]);

  async function prepareBase(source: string, file?: File, id?: string) {
    if (!scene || isProduct) return toast("Abra uma cena primeiro.");
    try {
      if (file) await apiUpload(`${base()}/scenes/${scene}/base/upload`, [file], "file");
      else
        await api(`${base()}/scenes/${scene}/base`, {
          method: "POST",
          body: JSON.stringify({ source, id: id || null }),
        });
      toast(source === "candidate" ? "Este resultado é a nova base da cena" : "Base da cena pronta");
      await loadScenes();
      await openScene(scene);
      refreshGuide();
    } catch (err) {
      toast((err as Error).message);
    }
  }

  async function runPrompts() {
    if (!scene) return toast("Abra uma cena primeiro.");
    if (isProduct) {
      try {
        const ps = ((await api(`${base()}/product/prompts`)) as { prompts: PromptOut[] }).prompts;
        setPrompts(ps);
        // `[extensão]`: o prompt montado alimenta a barra de geração — um só campo é enviado.
        if (ps[0]) setGenPrompt(ps[0].text);
      } catch (err) {
        toast((err as Error).message);
      }
      return;
    }
    const q = new URLSearchParams({ kind: promptKind, scale, angle });
    if (subject.trim()) q.set("subject", subject.trim());
    if (promptKind === "edit") {
      const e = edits
        .split("\n")
        .map((t) => t.trim())
        .filter(Boolean);
      if (!e.length) return toast("Escreva ao menos uma modificação.");
      e.forEach((v) => q.append("edits", v));
    }
    try {
      const r = (await api(`${base()}/scenes/${scene}/prompts?${q}`)) as { prompts: PromptOut[] };
      setPrompts(r.prompts);
      if (r.prompts[0]) setGenPrompt(r.prompts[0].text);
    } catch (err) {
      toast((err as Error).message);
    }
  }

  // ---------- `[extensão]` atalhos de geração da cena (FDD storyboard-geracao-por-cena §4) ----------
  // Duas pontes ADICIONAIS ao caminho da aula (gerar na UI da Higgsfield e importar), que continua
  // sendo o primeiro da tela. A grátis (motor local, ADR-033) não gasta nada; a paga (CLI, ADR-002)
  // NUNCA parte sem o gate de custo (ADR-016) — `confirm` antes de qualquer POST de generate.
  /** Rota da cena aberta: as do produto vivem em `/product/...`, as demais em `/scenes/{id}/...`. */
  const sceneUrl = useCallback(
    (sufixo: string) => (isProduct ? `${base()}/product/${sufixo}` : `${base()}/scenes/${scene}/${sufixo}`),
    [base, isProduct, scene],
  );

  /** Corpo de custo/geração paga: a cena manda `prompts[]`, o produto manda `prompt` (contrato). */
  function paidBody(texto: string, count: number, model = "nano_banana_2") {
    return isProduct
      ? { model, prompt: texto, count, resolution: "2k" }
      : { model, prompts: [texto], count, resolution: "2k" };
  }

  async function runSceneLocal() {
    if (!scene) return toast("Abra uma cena primeiro.");
    if (!localReady) return toast(localWhy);
    const p = genPrompt.trim();
    if (!p) return toast("Escreva o prompt (em inglês, aula 007).");
    try {
      await progressJob(prog, {
        title: "Gerar imagem da cena — motor local (grátis) [extensão]",
        subtitle: "Flux via ComfyUI — sem gastar crédito; o resultado cai na galeria desta cena",
        start: () =>
          api(`${sbBase()}/local/generate`, {
            method: "POST",
            body: JSON.stringify({ prompt: p, count: genCount, model: "flux-schnell", scene: sceneId(scene) }),
          }),
        jobUrl: `${sbBase()}/local/job`,
        done: async () => {
          await reload();
        },
        label: "Imagens da cena geradas",
      });
      refreshGuide();
    } catch (err) {
      toast((err as Error).message);
    }
  }

  async function runSceneCli() {
    if (!scene) return toast("Abra uma cena primeiro.");
    if (!cliReady) return toast(cliWhy);
    const p = genPrompt.trim();
    if (!p) return toast("Escreva ou gere o prompt do ângulo antes.");
    const body = paidBody(p, 1);
    try {
      // Modo SIMPLES do gate de custo: `costFn` bate na rota `cost` REAL dos ângulos, porque
      // `storyboard.angles` ainda não está em `settings.ACTIONS` (FDD §12, auto-aceite 2).
      const ok = await confirm({
        costFn: () => api(sceneUrl("cost"), { method: "POST", body: JSON.stringify(body) }),
        label: "Gerar via CLI (gasta créditos)",
      });
      if (!ok) return;
      await progressJob(prog, {
        title: "Gerar ângulos via CLI (gasta créditos) [extensão]",
        subtitle: "Higgsfield via CLI oficial — a base da cena vai como referência",
        start: () => api(sceneUrl("generate"), { method: "POST", body: JSON.stringify(body) }),
        jobUrl: `${base()}/job`,
        done: async () => {
          await reload();
        },
        label: "Ângulos gerados",
      });
      refreshGuide();
    } catch (err) {
      toast((err as Error).message);
    }
  }

  async function runSceneUpscale() {
    if (!scene) return toast("Abra uma cena primeiro.");
    if (!cliReady) return toast(cliWhy);
    if (order.length !== 1) return toast("Marque exatamente um candidato para upscalar.");
    const id = order[0] as string;
    const model = "bytedance_image_upscale";
    const body = { id, model };
    try {
      // A estimativa usa o MODELO DO UPSCALE (não o de geração): a planilha tem de mostrar o custo
      // do que vai ser feito. `cost` é grátis — consultar preço nunca gasta crédito (ADR-016).
      const ok = await confirm({
        costFn: () =>
          api(sceneUrl("cost"), { method: "POST", body: JSON.stringify(paidBody("upscale 2x", 1, model)) }),
        label: "Upscalar 2x (gasta créditos)",
      });
      if (!ok) return;
      await progressJob(prog, {
        title: "Upscalar 2x (gasta créditos) [extensão]",
        subtitle: "O 2x High Fidelity da aula 011, sem sair do Studio",
        start: () => api(sceneUrl("upscale"), { method: "POST", body: JSON.stringify(body) }),
        jobUrl: `${base()}/job`,
        done: async () => {
          await reload();
        },
        label: "Upscale pronto",
      });
      refreshGuide();
    } catch (err) {
      toast((err as Error).message);
    }
  }

  async function importFiles(files: FileList | File[]) {
    const list = [...files];
    if (!list.length || !scene) return;
    const uploadUrl = isProduct
      ? `${base()}/product/import/upload`
      : `${base()}/scenes/${scene}/import/upload`;
    try {
      const r = (await apiUpload(uploadUrl, list)) as { added?: number };
      toast(r.added ? `${r.added} imagem(ns) importada(s)` : "Nada novo: já estavam importadas");
      await reload();
      refreshGuide();
    } catch (err) {
      toast((err as Error).message);
    }
  }

  async function saveOrder() {
    if (!scene) return toast("Abra uma cena primeiro.");
    try {
      if (isProduct) {
        const id = order[0] || null;
        const c = prod.find((x) => x.id === id);
        await api(`${base()}/product/select`, {
          method: "POST",
          body: JSON.stringify({ id, upscaled: !!(c && c.upscaled) || upscaled }),
        });
        toast(id ? "Cena do produto salva · storyboard.md atualizado" : "Cena do produto removida");
        await loadProd();
        await loadScenes();
        refreshGuide();
        return;
      }
      const shots = order.map((id) => {
        const c = cands.find((x) => x.id === id);
        return { id, upscaled: !!(c && c.upscaled) || upscaled };
      });
      const r = (await api(`${base()}/scenes/${scene}/select`, {
        method: "POST",
        body: JSON.stringify({ shots }),
      })) as { warning?: string; shots: unknown[] };
      toast(r.warning || `${r.shots.length} frame(s) salvos em ${scene} · storyboard.md atualizado`);
      await loadCands(scene);
      await loadScenes();
      refreshGuide();
    } catch (err) {
      toast((err as Error).message);
    }
  }

  function toggleCard(id: string) {
    setOrder((prev) => {
      const i = prev.indexOf(id);
      if (isProduct) return i >= 0 ? [] : [id];
      if (i >= 0) return prev.filter((x) => x !== id);
      return [...prev, id];
    });
  }

  function openBaseMenu(id: string) {
    if (scene !== id) void openScene(id);
    setModal({ kind: "base", id });
  }

  async function clearProduct() {
    try {
      await api(`${base()}/product/select`, { method: "POST", body: JSON.stringify({ id: null }) });
      toast("Cena do produto removida");
      await loadProd();
      await loadScenes();
      refreshGuide();
    } catch (err) {
      toast((err as Error).message);
    }
  }

  // dropzone do painel inteiro (o vanilla liga `ui.drop($("#scenePanel"), importFiles)`)
  const panelDrop = useUpload((f) => void importFiles(f));

  const lista = isProduct ? prod : cands;
  const title = isProduct
    ? "Produto — escolher e ordenar"
    : scene
      ? `${sceneLabel(scene).replace("cena", "Cena")} — escolher e ordenar`
      : "Cena — escolher e ordenar";

  return (
    <>
      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">04</span>Ângulos por cena
          </h3>
          <div id="shotsPalette" className="palette sm">
            {palette.length ? (
              <>
                {palette.map((c, i) => (
                  <span key={i} style={{ background: c }} title={c} />
                ))}
                <span className="lbl">paleta do mood</span>
              </>
            ) : (
              <span className="lbl">sem mood/palette.json ainda (etapa 2)</span>
            )}
          </div>
        </div>
        <div id="sceneList" className="gallery">
          {erroLista ? (
            <div className="empty">{erroLista}</div>
          ) : (
            <>
              {scenes.map((s) => {
                const up = s.upscaled;
                const total = s.selected;
                const falta = total > 0 && up < total;
                const done = total > 0 && up === total;
                const dica = `${s.text ? s.text + " · " : ""}${s.candidates} candidatos · ${s.selected} shot(s) escolhidos`;
                return (
                  <div
                    key={s.id}
                    className={`rowcard col pick ${scene === s.id ? "cur" : ""}`}
                    data-scene={s.id}
                    tabIndex={0}
                    title={dica}
                    onClick={() => void openScene(s.id)}
                  >
                    <div className="thumb">
                      {s.base_ready ? <img loading="lazy" src={ctx.files(s.base)} alt="" /> : null}
                    </div>
                    <div className="row">
                      <span className="mono sh-scene-id">{sceneLabel(s.id)}</span>
                      <span className={`upcount${falta ? " warn" : done ? " ok" : ""}`}>
                        {`${up}/${total} upscalados`}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="sh-act shBase"
                      data-scene-base={s.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        openBaseMenu(s.id);
                      }}
                    >
                      base ▾
                    </button>
                  </div>
                );
              })}
              {(() => {
                const pick = prodPick();
                const up = prodState.selected && pick && pick.upscaled ? 1 : 0;
                const total = prodState.selected ? 1 : 0;
                const falta = total > 0 && up < total;
                const done = total > 0 && up === total;
                const dica = prodState.selected
                  ? "cena do produto salva (aula 013)"
                  : prodState.ref_ready
                    ? "imagem 1 enviada — rode as duas instruções e importe o resultado"
                    : "cena do produto (aula 013): envie a imagem 1 e rode as duas instruções";
                return (
                  <div
                    className={`rowcard col pick ${scene === PRODUCT ? "cur" : ""}`}
                    data-scene={PRODUCT}
                    tabIndex={0}
                    title={dica}
                    onClick={() => void openScene(PRODUCT)}
                  >
                    <div className="thumb">
                      {prodState.selected ? (
                        <img
                          loading="lazy"
                          src={`${ctx.files("storyboard/product/product_final.png")}?t=${prodTick}`}
                          alt=""
                        />
                      ) : null}
                    </div>
                    <div className="row">
                      <span className="mono sh-scene-id">produto</span>
                      <span className={`upcount${falta ? " warn" : done ? " ok" : ""}`}>
                        {`${up}/${total} upscalados`}
                      </span>
                    </div>
                    {prodState.selected ? (
                      <button
                        type="button"
                        className="sh-act shProdClear"
                        onClick={(e) => {
                          e.stopPropagation();
                          void clearProduct();
                        }}
                      >
                        remover
                      </button>
                    ) : null}
                  </div>
                );
              })()}
            </>
          )}
        </div>
      </section>

      <section
        className="panel"
        id="scenePanel"
        onDragOver={panelDrop.rootProps.onDragOver}
        onDragLeave={panelDrop.rootProps.onDragLeave}
        onDrop={panelDrop.rootProps.onDrop}
      >
        <input {...panelDrop.inputProps} />
        <div className="panel-head">
          <h3>
            <span className="pn">05</span>
            <span id="sceneTitle">{title}</span>
          </h3>
          <div className="row wrap">
            <button
              id="shotsCounts"
              type="button"
              className="chip mode"
              title="Importar os resultados gerados na Higgsfield"
              onClick={() => {
                if (!scene) return toast("Abra uma cena primeiro.");
                setFolder("");
                setModal({ kind: "import" });
              }}
            >
              {`${lista.length} candidatos · ${order.length} escolhidos`}
            </button>
            <label className="inline">
              <input
                id="shotsUpscaled"
                type="checkbox"
                checked={upscaled}
                onChange={(e) => setUpscaled(e.target.checked)}
              />{" "}
              já upscalei estes na UI
            </label>
            <button id="btnShotsSave" className="primary" onClick={() => void saveOrder()}>
              Salvar ordem da cena
            </button>
          </div>
        </div>
        <div className="row wrap sh-builder" id="shotsBuilder">
          <select
            id="promptKind"
            aria-label="Tipo de prompt"
            className={isProduct ? "hidden" : ""}
            value={promptKind}
            onChange={(e) => {
              setPromptKind(e.target.value as "angle" | "edit");
              setPrompts([]);
            }}
          >
            <option value="angle">Outro ponto de vista (Multi Shot)</option>
            <option value="edit">Edição numerada (uma rodada por vez)</option>
          </select>
          <input
            id="promptSubject"
            className={isProduct ? "grow-md hidden" : "grow-md"}
            placeholder="foco (ex.: the astronaut's face)"
            title="Enquadramentos da aula: close no rosto, foco nos pés, foco nas mãos, plano aberto com cenário"
            value={subject}
            onChange={(e) => {
              setSubject(e.target.value);
              setPrompts([]);
            }}
          />
          <select
            id="promptScale"
            aria-label="Enquadramento"
            className={isProduct ? "hidden" : ""}
            value={scale}
            onChange={(e) => {
              setScale(e.target.value);
              setPrompts([]);
            }}
          >
            <option value="close">close</option>
            <option value="medium">médio</option>
            <option value="wide">aberto</option>
          </select>
          <select
            id="promptAngle"
            aria-label="Ângulo de câmera"
            className={isProduct ? "hidden" : ""}
            value={angle}
            onChange={(e) => {
              setAngle(e.target.value);
              setPrompts([]);
            }}
          >
            <option value="eye-level">altura dos olhos</option>
            <option value="low">contra-plongée</option>
            <option value="high">plongée</option>
          </select>
          <button id="btnPrompts" className="ghost" onClick={() => void runPrompts()}>
            Gerar prompt
          </button>
        </div>
        <div
          id="editsBox"
          className={`row wrap sh-builder${isProduct || promptKind !== "edit" ? " hidden" : ""}`}
        >
          <textarea
            id="promptEdits"
            rows={3}
            placeholder="uma modificação por linha, em inglês (ex.: Make the helmet visor tinted) — a aula manda numerar e fazer uma rodada por vez"
            value={edits}
            onChange={(e) => setEdits(e.target.value)}
          />
        </div>
        {/* `[extensão]` atalhos de geração da cena — o caminho da aula continua acima e intacto. */}
        <p className="note" id="shotsGenNote">
          {AULA_NOTE}
        </p>
        <div className="row wrap sh-builder" id="shotsGenBar">
          <span className="eyebrow lbl">[extensão]</span>
          <input
            id="shotsGenPrompt"
            className="grow-md"
            placeholder="prompt desta cena (em inglês, aula 007)"
            title="Sugestão: o prompt de imagem da cena; edite à vontade antes de gerar"
            value={genPrompt}
            onChange={(e) => setGenPrompt(e.target.value)}
          />
          <select
            id="shotsGenCount"
            aria-label="Quantas imagens no motor local"
            value={genCount}
            onChange={(e) => setGenCount(+e.target.value)}
          >
            <option value={4}>4 (quando está incerto)</option>
            <option value={1}>1 (só um tweak)</option>
          </select>
          <button
            type="button"
            id="btnSceneLocal"
            className="ghost"
            disabled={!localReady}
            title={localWhy}
            onClick={() => void runSceneLocal()}
          >
            Gerar imagem da cena - local (grátis)
          </button>
          <button
            type="button"
            id="btnSceneCli"
            className="primary"
            disabled={!cliReady}
            title={cliWhy}
            onClick={() => void runSceneCli()}
          >
            Gerar via CLI (gasta créditos)
          </button>
          <button
            type="button"
            id="btnSceneUpscale"
            className="ghost"
            disabled={!cliReady}
            title={cliWhy || "Marque exatamente um candidato e upscale o 2x High Fidelity da aula 011"}
            onClick={() => void runSceneUpscale()}
          >
            Upscalar 2x (gasta créditos)
          </button>
        </div>
        <div id="shotsPrompts" className={`prompts one${prompts.length ? "" : " hidden"}`}>
          {prompts.map((p, i) => (
            <div className="prompt sm" key={i}>
              <div className="row">
                <span className="eyebrow">{p.label}</span>
                <button
                  type="button"
                  className="link copy"
                  data-i={i}
                  onClick={() => {
                    void navigator.clipboard.writeText(p.text);
                    setCopied(i);
                    setTimeout(() => setCopied((c) => (c === i ? null : c)), 1500);
                  }}
                >
                  Copiar
                </button>
                <span className="ok">{copied === i ? "copiado ✓" : ""}</span>
              </div>
              <p className="txt" data-i={i}>
                {p.text}
              </p>
            </div>
          ))}
        </div>
        <div id="shotsGallery" className="gallery sm">
          {lista.length ? (
            lista.map((c) => {
              const pos = order.indexOf(c.id);
              return (
                <div
                  key={c.id}
                  className={`card ${pos >= 0 ? "sel" : ""}`}
                  {...(pos >= 0 ? { "data-ord": pos + 1 } : {})}
                  data-id={c.id}
                  tabIndex={0}
                  title={c.prompt || c.name || c.source || ""}
                  onClick={(e) => {
                    if ((e.target as HTMLElement).closest("button.asBase")) return;
                    toggleCard(c.id);
                  }}
                  onDoubleClick={() => window.open(ctx.files(c.file), "_blank")}
                >
                  <img loading="lazy" src={ctx.files(c.thumb || c.file)} alt="" />
                  <span className={`up${c.upscaled ? " ok" : ""}`}>
                    {c.upscaled ? "upscalado 2x" : "sem upscale"}
                  </span>
                  {isProduct ? null : (
                    <button
                      type="button"
                      className="link asBase card-act"
                      data-base={c.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        void prepareBase("candidate", undefined, c.id);
                      }}
                    >
                      Usar como base da cena
                    </button>
                  )}
                </div>
              );
            })
          ) : (
            <div className="empty">Nenhum candidato — gere na UI da Higgsfield e importe.</div>
          )}
        </div>
        <p className="note">
          Clique na ordem em que os frames entram na cena — o número é a ordem (shot01_final.png,
          shot02_final.png…).
        </p>
      </section>

      {modal?.kind === "import" ? (
        <ImportModal
          ctx={ctx}
          produto={isProduct}
          sceneLabelTxt={sceneLabel(scene || "")}
          minutes={minutes}
          setMinutes={setMinutes}
          folder={folder}
          onFolder={setFolder}
          onClose={() => setModal(null)}
          onDrop={(files) => {
            setModal(null);
            void importFiles(files);
          }}
          onProdRef={async (file) => {
            setModal(null);
            try {
              await apiUpload(`${base()}/product/ref`, [file], "file");
              toast("Imagem 1 salva");
              await loadScenes();
              refreshGuide();
            } catch (err) {
              toast((err as Error).message);
            }
          }}
          onDownloads={async () => {
            const dlUrl = isProduct
              ? `${base()}/product/import/downloads`
              : `${base()}/scenes/${scene}/import/downloads`;
            setModal(null);
            try {
              const r = (await api(dlUrl, {
                method: "POST",
                body: JSON.stringify({ since_minutes: minutes }),
              })) as { added?: number; scanned?: number };
              toast(`${r.added} novas de ${r.scanned || 0} recentes`);
              await reload();
              refreshGuide();
            } catch (err) {
              toast((err as Error).message);
            }
          }}
          onHistory={async () => {
            setModal(null);
            try {
              const r = (await api(`${base()}/scenes/${scene}/import/history`, {
                method: "POST",
                body: JSON.stringify({}),
              })) as { added?: number; jobs?: number };
              toast(`${r.added} imagens de ${r.jobs} jobs`);
              await reload();
              refreshGuide();
            } catch (err) {
              toast((err as Error).message);
            }
          }}
          onFolderRequest={() => {
            void api("/api/storyboard/angles/downloads-folder")
              .then((d) => {
                const dd = d as { folder: string; exists: boolean };
                setFolder(dd.folder + (dd.exists ? "" : " (não encontrada)"));
              })
              .catch(() => {});
          }}
        />
      ) : null}

      {modal?.kind === "base" ? (
        <BaseMenuModal
          idLabel={sceneLabel(modal.id).replace("cena", "cena")}
          onClose={() => setModal(null)}
          onScene={() => {
            setModal(null);
            void prepareBase("storyboard");
          }}
          onCampaign={() => {
            setModal(null);
            void prepareBase("base");
          }}
          onUpload={(file) => {
            setModal(null);
            void prepareBase("upload", file);
          }}
        />
      ) : null}

      {/* `[extensão]` gate de custo (ADR-016) e progresso honesto dos jobs por cena. */}
      {costEl}
      {progEl}
    </>
  );
}

// ---------- modal: importar candidatos da cena / do produto ----------
interface ImportModalProps {
  ctx: StudioCtx;
  produto: boolean;
  sceneLabelTxt: string;
  minutes: number;
  setMinutes: (n: number) => void;
  folder: string;
  onFolder: (s: string) => void;
  onClose: () => void;
  onDrop: (files: FileList) => void;
  onProdRef: (file: File) => void;
  onDownloads: () => void;
  onHistory: () => void;
  onFolderRequest: () => void;
}
function ImportModal(p: ImportModalProps) {
  const impDrop = useUpload((f) => p.onDrop(f));
  const prodRefDrop = useUpload(
    (f) => {
      const file = f[0];
      if (file) p.onProdRef(file);
    },
    { multiple: false },
  );

  useEffect(() => {
    p.onFolderRequest();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Modal
      title={p.produto ? "Cena do produto (aula 013)" : `Importar candidatos da ${p.sceneLabelTxt}`}
      subtitle={
        p.produto
          ? "Imagem 1 é a cena (ex.: geladeira); a imagem 2 é sempre base/base_final.png."
          : "Gere na interface da Higgsfield (Multi Shot, Cinema Studio, Upscale 2x) e traga os resultados."
      }
      onClose={p.onClose}
    >
      <div className="import-row">
        <label
          className={impDrop.isOver ? "drop over" : "drop"}
          id="shImpDrop"
          onDragOver={impDrop.rootProps.onDragOver}
          onDragLeave={impDrop.rootProps.onDragLeave}
          onDrop={impDrop.rootProps.onDrop}
        >
          Arraste imagens aqui ou <input id="shImpUpload" {...impDrop.inputProps} accept="image/*" />
          <u onClick={impDrop.open}>escolha arquivos</u>
        </label>
        <div className="col">
          {p.produto ? (
            <label
              className={prodRefDrop.isOver ? "drop sm over" : "drop sm"}
              id="shProdRefDrop"
              onDragOver={prodRefDrop.rootProps.onDragOver}
              onDragLeave={prodRefDrop.rootProps.onDragLeave}
              onDrop={prodRefDrop.rootProps.onDrop}
            >
              imagem 1 (a cena)
              <input id="shProdRefUpload" {...prodRefDrop.inputProps} accept="image/*" />
            </label>
          ) : null}
          <button type="button" id="shImpDownloads" className="ghost" onClick={p.onDownloads}>
            Importar da pasta Downloads
          </button>
          <label className="inline">
            últimos{" "}
            <input
              id="shImpMinutes"
              className="mini wide"
              type="number"
              value={p.minutes}
              min={5}
              onChange={(e) => p.setMinutes(+e.target.value)}
            />{" "}
            min
          </label>
          {p.produto ? null : (
            <>
              <button type="button" id="shImpHistory" className="ghost" onClick={p.onHistory}>
                Importar do histórico Higgsfield
              </button>
              <span className="fine">precisa de login no CLI</span>
            </>
          )}
          <span id="shImpFolder" className="fine mono">
            {p.folder}
          </span>
        </div>
      </div>
    </Modal>
  );
}

// ---------- modal: menu de base da cena ----------
interface BaseMenuProps {
  idLabel: string;
  onClose: () => void;
  onScene: () => void;
  onCampaign: () => void;
  onUpload: (file: File) => void;
}
function BaseMenuModal(p: BaseMenuProps) {
  const drop = useUpload(
    (f) => {
      const file = f[0];
      if (file) p.onUpload(file);
    },
    { multiple: false },
  );
  return (
    <Modal
      title={`Base da ${p.idLabel.replace("cena", "cena ")}`}
      subtitle="A base define cor e luz de tudo: acerte-a antes do Multi Shot."
      onClose={p.onClose}
    >
      <div className="col">
        <button type="button" id="shBaseScene" className="ghost" onClick={p.onScene}>
          Imagem da cena (ideia do painel 03)
        </button>
        <button type="button" id="shBaseCampaign" className="ghost" onClick={p.onCampaign}>
          Imagem base da campanha
        </button>
        <label
          className={drop.isOver ? "drop sm over" : "drop sm"}
          id="shBaseDrop"
          onDragOver={drop.rootProps.onDragOver}
          onDragLeave={drop.rootProps.onDragLeave}
          onDrop={drop.rootProps.onDrop}
        >
          Arraste uma imagem ou <input id="shBaseUpload" {...drop.inputProps} accept="image/*" />
          <u onClick={drop.open}>envie um arquivo</u>
        </label>
      </div>
    </Modal>
  );
}
