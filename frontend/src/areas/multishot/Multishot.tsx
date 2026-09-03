// Componente reutilizável de MULTISHOT [extensão] (ADR-017) — Wave 10 · E6 (card [REACT-07]).
//
// "Gerar vários ângulos a partir de uma imagem" (aula 011). Porte React do `studio/web/multishot.js`
// + `window.Studio.multishot.open` do vanilla: a decisão do ADR-017 ("existe UM componente único e
// reutilizável") permanece; muda só o ENDEREÇO — de IIFE global para componente React compartilhado.
// Hoje o único consumidor é a área de mood boards (recon §0.2); o storyboard (ADR-018) passa a
// consumi-lo na reescrita futura.
//
// Reproduz o mesmo DOM e comportamento do vanilla (o oráculo são os cenários `moodboards.py`
// C-MOODBOARDS-18…21): modal com imagem de origem, contador de ângulos (`#msCount`), "Gerar via CLI"
// (`#msGen`) atrás do gate de custo (ADR-016) + `progressJob`, "Importar fotos" (`#msImport`) e um
// CARROSSEL das candidatas `role=multishot` do dono (prev/‹ ›/next, contador `n/total`, "remover").
// O CSS do carrossel é 100% escopado em `.msc-` num `<style>` do próprio componente (não toca
// ui.css/style.css), como no vanilla.
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../../api";
import { Modal, useCostConfirm, useProgress, progressJob, useUpload, upload } from "../../ui";
import { toast } from "../../shell/toast";

/** URLs do dono (board/cena) que o componente consome. */
export interface MultishotEndpoints {
  /** POST que cria o job de geração. */
  generate: string;
  /** Endpoint `/job` a pollar durante a geração. */
  job: string;
  /** GET das candidatas do dono (a galeria filtra `role=multishot` por `parentId`). */
  candidates: string;
  /** Opcionais — habilitam "Importar fotos". */
  upload?: string;
  importDownloads?: string;
  downloadsFolder?: string;
  openFolder?: string;
}

/** Opções de abertura — equivalente ao objeto de `Studio.multishot.open(opts)` do vanilla. */
export interface MultishotOpts {
  title?: string;
  subtitle?: string;
  /** URL servível da imagem de origem. */
  sourceUrl: string;
  /** Ação do gate de custo (ex.: `"mood.multishot"`). */
  action: string;
  /** Opcional — habilita override de modelo por projeto no custo. */
  pid?: string;
  /** Quantidade default de ângulos (default 4). */
  count?: number;
  endpoints: MultishotEndpoints;
  /** `true` habilita "remover" no item ativo do carrossel. */
  canRemove?: boolean;
  /** Como transformar o `file` de uma candidata em URL servível. */
  fileUrl?: (rel: string) => string;
  /** Id da imagem de origem — filtra a galeria de resultados. */
  parentId?: string;
  /** Callback após gerar/remover/importar (recarregar o dono). */
  onChanged?: () => void | Promise<void>;
}

export interface MultishotProps {
  opts: MultishotOpts;
  /** Fecha o modal (controlado pelo pai — no vanilla o modal era imperativo). */
  onClose: () => void;
}

/** Candidata do dono, na forma que o carrossel lê. */
interface Cand {
  id: string;
  file: string;
  role?: string;
  parent?: string;
  prompt?: string;
}

/** CSS do carrossel, escopado em `.msc-` — mesmas regras do `<style>` inline do vanilla. */
const MSC_CSS = `
    .msc-wrap{display:flex;flex-direction:column;gap:12px}
    .msc-empty{opacity:.7;font-size:.9rem;padding:18px 8px;text-align:center}
    .msc-count{font-size:.85rem;opacity:.8}
    .msc-stage{display:flex;align-items:center;gap:10px;justify-content:center}
    .msc-frame{position:relative;flex:1;min-width:0;display:flex;align-items:center;justify-content:center;
      background:rgba(0,0,0,.18);border-radius:12px;overflow:hidden;min-height:220px;max-height:52vh}
    .msc-frame img{max-width:100%;max-height:52vh;object-fit:contain;display:block}
    .msc-tag{position:absolute;top:8px;left:8px;font-size:.7rem;padding:2px 8px;border-radius:999px;
      background:rgba(0,0,0,.55);color:#fff;letter-spacing:.04em;text-transform:uppercase}
    .msc-nav{flex:0 0 auto;width:40px;height:40px;border-radius:50%;border:none;cursor:pointer;
      font-size:1.3rem;line-height:1;background:rgba(120,120,120,.22);color:inherit}
    .msc-nav:hover{background:rgba(120,120,120,.4)}
    .msc-nav:disabled{opacity:.3;cursor:default}
    .msc-bar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
    .msc-bar-actions{display:flex;gap:8px;flex-wrap:wrap}
    .msc-prompt{font-size:.78rem;opacity:.65;margin:0}
`;

const msg = (e: unknown): string => (e as Error)?.message || String(e);

async function fetchResults(opts: MultishotOpts): Promise<Cand[]> {
  if (!opts.endpoints.candidates) return [];
  try {
    const r = (await api(opts.endpoints.candidates)) as Cand[] | { candidates?: Cand[] };
    const list = Array.isArray(r) ? r : (r.candidates ?? []);
    return list.filter(
      (c) => c && c.role === "multishot" && (!opts.parentId || c.parent === opts.parentId),
    );
  } catch {
    return [];
  }
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

/** Carrossel dos ângulos gerados (item ativo por vez), com prev/next e "remover". */
function Carousel({
  opts,
  results,
  idx,
  onStep,
  onRemove,
}: {
  opts: MultishotOpts;
  results: Cand[];
  idx: number;
  onStep: (delta: number) => void;
  onRemove: () => void;
}) {
  if (!results.length) {
    return (
      <p className="msc-empty">
        Nenhum ângulo gerado ainda a partir desta imagem. Gere pelo CLI (custo abaixo) ou pela UI da
        Higgsfield e importe.
      </p>
    );
  }
  const c = results[idx]!;
  const src = opts.fileUrl ? opts.fileUrl(c.file) : c.file;
  const single = results.length <= 1;
  return (
    <>
      <div className="msc-stage">
        <button
          className="msc-nav msc-prev"
          type="button"
          title="Anterior"
          disabled={single}
          onClick={() => onStep(-1)}
        >
          ‹
        </button>
        <div className="msc-frame">
          <span className="msc-tag">multishot</span>
          <img src={src} alt="" loading="lazy" />
        </div>
        <button
          className="msc-nav msc-next"
          type="button"
          title="Próximo"
          disabled={single}
          onClick={() => onStep(1)}
        >
          ›
        </button>
      </div>
      <div className="msc-bar">
        <span className="msc-count">
          {idx + 1}/{results.length} ângulo(s) gerado(s) desta imagem
        </span>
        <div className="msc-bar-actions">
          {opts.canRemove ? (
            <button className="ghost danger msc-remove" type="button" onClick={onRemove}>
              remover
            </button>
          ) : null}
        </div>
      </div>
      {c.prompt ? <p className="msc-prompt">{c.prompt}</p> : null}
    </>
  );
}

/** Modal "Importar novas fotos" — upload, pasta Downloads e abrir pasta (reusa import/upload). */
function ImportModal({
  opts,
  onClose,
  onDone,
}: {
  opts: MultishotOpts;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const ep = opts.endpoints;
  const [pasta, setPasta] = useState("");

  useEffect(() => {
    if (!ep.downloadsFolder) return;
    let vivo = true;
    void api(ep.downloadsFolder)
      .then((d) => {
        const info = d as { folder?: string; exists?: boolean };
        if (vivo && info.folder != null) {
          setPasta(`pasta Downloads: ${info.folder}${info.exists ? "" : " (não encontrada)"}`);
        }
      })
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, [ep.downloadsFolder]);

  const enviar = useCallback(
    async (files: FileList) => {
      if (!files || !files.length || !ep.upload) return;
      try {
        const r = (await upload(ep.upload, files)) as { added?: number };
        toast(`${r.added} imagem(ns) importada(s)`);
        onClose();
        await onDone();
      } catch (e) {
        toast(msg(e));
      }
    },
    [ep.upload, onClose, onDone],
  );

  const dz = useUpload(enviar);

  const importarDownloads = useCallback(async () => {
    if (!ep.importDownloads) return;
    try {
      const r = (await api(ep.importDownloads, {
        method: "POST",
        body: JSON.stringify({ since_minutes: 120 }),
      })) as { added?: number; scanned?: number };
      toast(`${r.added} novas de ${r.scanned} imagens recentes`);
      onClose();
      await onDone();
    } catch (e) {
      toast(msg(e));
    }
  }, [ep.importDownloads, onClose, onDone]);

  const abrirPasta = useCallback(async () => {
    if (!ep.openFolder) return;
    try {
      const r = (await api(ep.openFolder, {
        method: "POST",
        body: JSON.stringify({ target: "downloads" }),
      })) as { opened?: boolean; path?: string };
      toast(r.opened ? "Pasta de Downloads aberta" : `Pasta: ${r.path}`);
    } catch (e) {
      toast(msg(e));
    }
  }, [ep.openFolder]);

  return (
    <Modal
      title="Importar novas fotos"
      subtitle="Adicione imagens ao board — por upload ou da pasta Downloads"
      onClose={onClose}
    >
      <div className="msc-wrap">
        <label className={`drop${dz.isOver ? " over" : ""}`} id="msImpDrop" {...dz.rootProps}>
          Arraste imagens aqui ou <input id="msImpFile" accept="image/*" {...dz.inputProps} />
          <u>escolha arquivos</u>
        </label>
        <div className="msc-bar-actions">
          <button className="ghost" id="msImpDl" type="button" onClick={importarDownloads}>
            Importar da pasta Downloads
          </button>
          <button
            className="ghost"
            id="msImpOpen"
            type="button"
            title="Abrir a pasta de Downloads no explorador"
            onClick={abrirPasta}
          >
            Abrir pasta de Downloads
          </button>
        </div>
        <p className="msc-prompt" id="msImpPath">
          {pasta}
        </p>
      </div>
    </Modal>
  );
}

/** Modal do multishot — porte de `Studio.multishot.open`. Controlado: monte quando aberto. */
export function Multishot({ opts, onClose }: MultishotProps) {
  const [results, setResults] = useState<Cand[]>([]);
  const [idx, setIdx] = useState(0);
  const [count, setCount] = useState(String(Number(opts.count) || 4));
  const [importOpen, setImportOpen] = useState(false);
  const { confirm, element: costEl } = useCostConfirm();
  const [prog, progEl] = useProgress();
  const canImport = !!opts.endpoints.upload;

  const refresh = useCallback(async () => {
    const r = await fetchResults(opts);
    setResults(r);
    setIdx((i) => clamp(i, 0, Math.max(0, r.length - 1)));
  }, [opts]);

  // Busca inicial (equivale ao `let results = await fetchResults(o)` antes de montar o modal).
  const carregado = useRef(false);
  useEffect(() => {
    if (carregado.current) return;
    carregado.current = true;
    void refresh();
  }, [refresh]);

  const step = useCallback(
    (delta: number) => {
      setIdx((i) => (results.length ? (i + delta + results.length) % results.length : 0));
    },
    [results.length],
  );

  const removeCurrent = useCallback(async () => {
    const cur = results[idx];
    if (!cur) return;
    try {
      await api(`${opts.endpoints.candidates}/${encodeURIComponent(cur.id)}`, { method: "DELETE" });
      toast("Ângulo removido");
      await refresh();
      await opts.onChanged?.();
    } catch (e) {
      toast(msg(e));
    }
  }, [results, idx, opts, refresh]);

  const gerar = useCallback(async () => {
    const n = clamp(Number(count) || 4, 1, 8);
    const ok = await confirm({
      action: opts.action,
      count: n,
      label: `Gerar ${n} ângulo(s)`,
      ...(opts.pid ? { pid: opts.pid } : {}),
    });
    if (!ok) return;
    try {
      await progressJob(prog, {
        title: "Gerar multishot",
        subtitle: "Outro ponto de vista (aula 011)",
        start: () =>
          api(opts.endpoints.generate, {
            method: "POST",
            body: JSON.stringify({ source_id: opts.parentId, count: n }),
          }),
        jobUrl: opts.endpoints.job,
        done: async () => {
          await refresh();
          await opts.onChanged?.();
          // Paridade com o vanilla: toda geração paga reflete o novo saldo na topbar (recon §6.4).
          window.Studio?.ui?.refreshCredits?.(false);
        },
        label: "Ângulos gerados",
      });
    } catch (e) {
      toast(msg(e));
    }
  }, [count, confirm, opts, prog, refresh]);

  return (
    <>
      <Modal
        title={opts.title || "Multishot — outro ponto de vista"}
        subtitle={opts.subtitle || "Aula 011 · vários ângulos a partir de uma imagem [extensão]"}
        onClose={onClose}
      >
        <style>{MSC_CSS}</style>
        <div className="msc-wrap">
          <div className="ms-source">
            <span className="eyebrow">Imagem de origem</span>
            <img src={opts.sourceUrl} alt="" loading="lazy" />
          </div>
          <div className="ms-controls">
            <label className="inline">
              ângulos{" "}
              <input
                type="number"
                id="msCount"
                value={count}
                min={1}
                max={8}
                onChange={(e) => setCount(e.target.value)}
              />
            </label>
            <button className="primary" id="msGen" type="button" onClick={gerar}>
              Gerar ângulos via CLI
            </button>
            {canImport ? (
              <button
                className="ghost"
                id="msImport"
                type="button"
                title="Importar novas fotos ao board"
                onClick={() => setImportOpen(true)}
              >
                Importar fotos
              </button>
            ) : null}
            <span className="fine ms-hint">
              O custo aparece antes de gastar. Sem CLI, gere na UI da Higgsfield (ilimitado) e importe.
            </span>
          </div>
          <div className="ms-results">
            <Carousel
              opts={opts}
              results={results}
              idx={idx}
              onStep={step}
              onRemove={() => void removeCurrent()}
            />
          </div>
        </div>
      </Modal>
      {costEl}
      {progEl}
      {importOpen ? (
        <ImportModal
          opts={opts}
          onClose={() => setImportOpen(false)}
          onDone={async () => {
            await refresh();
            await opts.onChanged?.();
          }}
        />
      ) : null}
    </>
  );
}
