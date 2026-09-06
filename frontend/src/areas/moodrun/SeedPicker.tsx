// SeedPicker — escolher a foto-semente da corrida de mood `[extensão]` (ADH-OS-20260905-03).
//
// Navega a saída do `mood_vibe_scout` (`/api/vibes`, paginada, com filtro por facetas), copia as
// escolhidas para a "peneira" (`/api/vibes/select` → `/api/escolhidas`) e devolve o `caminho` de
// uma delas como semente. Traz também a SEGUNDA via da coleta: dispara o próprio `mood_vibe_scout`
// headless (`/api/vibes/scout-run`) sem sair da tela — ao lado da via CLI, nunca no lugar dela.
//
// Modal controlado (montado quando aberto), no molde do `Multishot`. CSS escopado em `.sp-` num
// `<style>` do próprio componente — não toca style.css/ui.css.
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../../api";
import { Modal, useProgress, progressJob } from "../../ui";
import { toast } from "../../shell/toast";

interface VibeItem {
  id: string;
  arquivo: string;
  url: string;
  vibe: string;
  vibe_nome: string;
  origem: string;
  escolhida: boolean;
}
interface VibesPage {
  items: VibeItem[];
  page: number;
  pages: number;
  total: number;
  indice: { ok: boolean; erro: string | null };
}
interface Facets {
  vibes: { slug: string; nome: string; origem: string; total: number }[];
  origens: { origem: string; total: number }[];
  total: number;
  escolhidas: number;
}
interface ChosenItem {
  id: string;
  url: string;
  caminho: string;
  vibe_nome: string;
}
interface ChosenPage {
  items: ChosenItem[];
  total: number;
}
interface ScoutOptions {
  available_claude: boolean;
  defaults: { n: number };
  limites: { n_min: number };
}

export interface SeedPickerProps {
  /** Recebe o `caminho` absoluto da foto escolhida como semente. */
  onPick: (caminho: string) => void;
  onClose: () => void;
}

const msg = (e: unknown): string => (e as Error)?.message || String(e);

const SP_CSS = `
    .sp-wrap{display:flex;flex-direction:column;gap:14px;max-height:70vh;overflow:auto}
    .sp-sec{display:flex;flex-direction:column;gap:8px}
    .sp-filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .sp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px}
    .sp-card{position:relative;border-radius:10px;overflow:hidden;cursor:pointer;aspect-ratio:1;
      background:rgba(0,0,0,.16);border:2px solid transparent}
    .sp-card.sel{border-color:rgba(90,150,240,.95)}
    .sp-card.done{outline:2px solid rgba(60,170,100,.9);outline-offset:-2px}
    .sp-card img{width:100%;height:100%;object-fit:cover;display:block}
    .sp-badge{position:absolute;top:4px;left:4px;font-size:.62rem;padding:1px 6px;border-radius:999px;
      background:rgba(0,0,0,.6);color:#fff;text-transform:uppercase;letter-spacing:.03em}
    .sp-pick{position:absolute;bottom:4px;left:4px;right:4px;font-size:.7rem;padding:2px 0;border:none;
      cursor:pointer;border-radius:6px;background:rgba(60,150,90,.92);color:#fff}
    .sp-pick:hover{background:rgba(60,170,100,1)}
    .sp-pager{display:flex;gap:10px;align-items:center;justify-content:center}
    .sp-scout{border:1px dashed rgba(120,120,120,.4);border-radius:12px;padding:10px 12px;display:flex;
      flex-direction:column;gap:8px}
    .sp-scout .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .sp-empty{opacity:.7;font-size:.88rem;padding:14px 6px;text-align:center}
`;

export function SeedPicker({ onPick, onClose }: SeedPickerProps) {
  const [facets, setFacets] = useState<Facets | null>(null);
  const [page, setPage] = useState<VibesPage | null>(null);
  const [pageNum, setPageNum] = useState(1);
  const [fVibe, setFVibe] = useState("");
  const [fOrigem, setFOrigem] = useState("");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [chosen, setChosen] = useState<ChosenPage | null>(null);
  const [scoutOpt, setScoutOpt] = useState<ScoutOptions | null>(null);
  const [desc, setDesc] = useState("");
  const [vibesGar, setVibesGar] = useState("");
  const [scoutN, setScoutN] = useState("");
  const [prog, progEl] = useProgress();
  // Guarda contra setState após desmontar: `api()` em voo não pode atualizar um modal já removido
  // (o portal tocaria `document`/`window` fora do ciclo). Mesmo espírito do `vivo` do `Multishot`.
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  const loadFacets = useCallback(async () => {
    try {
      const r = (await api("/api/vibes/facets")) as Facets;
      if (alive.current) setFacets(r);
    } catch {
      if (alive.current) setFacets(null);
    }
  }, []);

  const loadChosen = useCallback(async () => {
    try {
      const r = (await api("/api/escolhidas?per_page=20")) as ChosenPage;
      if (alive.current) setChosen(r);
    } catch {
      if (alive.current) setChosen(null);
    }
  }, []);

  const loadPage = useCallback(async () => {
    const qs = new URLSearchParams({ page: String(pageNum), per_page: "20" });
    if (fVibe) qs.set("vibe", fVibe);
    if (fOrigem) qs.set("origem", fOrigem);
    try {
      const r = (await api(`/api/vibes?${qs.toString()}`)) as VibesPage;
      if (alive.current) setPage(r);
    } catch (e) {
      if (!alive.current) return;
      toast(msg(e));
      setPage({ items: [], page: 1, pages: 1, total: 0, indice: { ok: false, erro: null } });
    }
  }, [pageNum, fVibe, fOrigem]);

  useEffect(() => {
    void loadFacets();
    void loadChosen();
    void api("/api/vibes/scout-run/options")
      .then((o) => {
        if (alive.current) setScoutOpt(o as ScoutOptions);
      })
      .catch(() => {
        if (alive.current) setScoutOpt(null);
      });
  }, [loadFacets, loadChosen]);

  useEffect(() => {
    void loadPage();
  }, [loadPage]);

  useEffect(() => {
    if (scoutOpt && scoutN === "") setScoutN(String(scoutOpt.defaults.n));
  }, [scoutOpt, scoutN]);

  const toggle = (id: string) =>
    setSel((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const salvarNaPeneira = async () => {
    if (!sel.size) {
      toast("Marque ao menos uma foto");
      return;
    }
    try {
      const r = (await api("/api/vibes/select", {
        method: "POST",
        body: JSON.stringify({ ids: [...sel] }),
      })) as { copiadas: string[]; duplicadas: string[]; total_escolhidas: number };
      toast(`${r.copiadas.length} na peneira (${r.duplicadas.length} já estavam) · total ${r.total_escolhidas}`);
      setSel(new Set());
      await Promise.all([loadFacets(), loadChosen(), loadPage()]);
    } catch (e) {
      toast(msg(e));
    }
  };

  const removerDaPeneira = async (id: string) => {
    try {
      await api(`/api/escolhidas/${encodeURIComponent(id)}`, { method: "DELETE" });
      await Promise.all([loadFacets(), loadChosen(), loadPage()]);
    } catch (e) {
      toast(msg(e));
    }
  };

  const coletar = async () => {
    const alvos = vibesGar
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!alvos.length) {
      toast("Informe ao menos uma vibe garantida (ex.: neon-city, anime-night)");
      return;
    }
    try {
      await progressJob(prog, {
        title: "Coletar referências de vibe (grátis) [extensão]",
        subtitle: "mood_vibe_scout headless — sem entrevista, sem gastar crédito",
        start: () =>
          api("/api/vibes/scout-run", {
            method: "POST",
            body: JSON.stringify({ descricao: desc, vibes: alvos, n: Number(scoutN) || undefined }),
          }),
        jobUrl: "/api/vibes/scout-run/job",
        done: async () => {
          setPageNum(1);
          await Promise.all([loadFacets(), loadPage()]);
        },
        label: "Imagens coletadas",
      });
    } catch (e) {
      toast(msg(e));
    }
  };

  const scoutReady = !!scoutOpt?.available_claude;

  return (
    <Modal
      title="Escolher foto-semente"
      subtitle="Navegue as referências de vibe, junte na peneira e escolha a semente da corrida [extensão]"
      onClose={onClose}
    >
      <style>{SP_CSS}</style>
      <div className="sp-wrap">
        {/* peneira atual */}
        <div className="sp-sec">
          <div className="row" style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
            <span className="eyebrow">
              Peneira · {facets?.escolhidas ?? chosen?.total ?? 0} escolhida(s)
            </span>
          </div>
          {chosen && chosen.items.length ? (
            <div className="sp-grid">
              {chosen.items.map((c) => (
                <div key={c.id} className="sp-card" title={c.vibe_nome}>
                  <img src={c.url} alt="" loading="lazy" />
                  <button
                    className="sp-pick"
                    type="button"
                    onClick={() => {
                      onPick(c.caminho);
                      onClose();
                    }}
                  >
                    usar semente
                  </button>
                  <button
                    className="sp-badge"
                    type="button"
                    title="remover da peneira"
                    onClick={() => void removerDaPeneira(c.id)}
                    style={{ cursor: "pointer", border: "none" }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="sp-empty">Peneira vazia — marque fotos abaixo e salve, ou colete novas.</p>
          )}
        </div>

        {/* coleta headless do scout (2ª via) */}
        <div className="sp-scout">
          <span className="eyebrow">
            Coletar novas referências (grátis) <span className="ext">[extensão]</span> ·{" "}
            <span className={`chip ${scoutReady ? "ok" : "warn"}`}>
              {scoutReady ? "no ar" : scoutOpt ? "sem claude" : "verificando…"}
            </span>
          </span>
          <input
            className="lg"
            placeholder="sobre a campanha (opcional) — ex.: neon noir, neve, cidade à noite"
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
          />
          <div className="row">
            <input
              placeholder="vibes garantidas, separadas por vírgula"
              value={vibesGar}
              onChange={(e) => setVibesGar(e.target.value)}
              style={{ flex: 1, minWidth: 180 }}
            />
            <label className="inline">
              n{" "}
              <input
                type="number"
                min={scoutOpt?.limites.n_min ?? 1}
                value={scoutN}
                onChange={(e) => setScoutN(e.target.value)}
                style={{ width: 64 }}
              />
            </label>
            <button
              className="primary"
              type="button"
              disabled={!scoutReady}
              title={scoutReady ? "" : "sem claude no PATH — use /mood_vibe_scout no terminal"}
              onClick={() => void coletar()}
            >
              Coletar
            </button>
          </div>
          <span className="fine">
            A entrevista de diretor de arte é do CLI (<code>/mood_vibe_scout</code>); aqui a coleta é
            direta, com as vibes que você já sabe.
          </span>
        </div>

        {/* navegação das vibes */}
        <div className="sp-sec">
          <div className="sp-filters">
            <span className="eyebrow">Referências ({page?.total ?? 0})</span>
            <select value={fVibe} onChange={(e) => { setFVibe(e.target.value); setPageNum(1); }}>
              <option value="">todas as vibes</option>
              {facets?.vibes.map((v) => (
                <option key={v.slug} value={v.slug}>
                  {v.nome} ({v.total})
                </option>
              ))}
            </select>
            <select value={fOrigem} onChange={(e) => { setFOrigem(e.target.value); setPageNum(1); }}>
              <option value="">todas as origens</option>
              {facets?.origens.map((o) => (
                <option key={o.origem} value={o.origem}>
                  {o.origem} ({o.total})
                </option>
              ))}
            </select>
            <button className="primary" type="button" disabled={!sel.size} onClick={() => void salvarNaPeneira()}>
              Salvar na peneira ({sel.size})
            </button>
          </div>
          {page && page.items.length ? (
            <>
              <div className="sp-grid">
                {page.items.map((it) => (
                  <div
                    key={it.id}
                    className={`sp-card${sel.has(it.id) ? " sel" : ""}${it.escolhida ? " done" : ""}`}
                    title={`${it.vibe_nome} · ${it.origem}`}
                    onClick={() => toggle(it.id)}
                  >
                    <img src={it.url} alt="" loading="lazy" />
                    {it.escolhida ? <span className="sp-badge">na peneira</span> : null}
                  </div>
                ))}
              </div>
              <div className="sp-pager">
                <button
                  className="ghost"
                  type="button"
                  disabled={pageNum <= 1}
                  onClick={() => setPageNum((p) => Math.max(1, p - 1))}
                >
                  ‹ anterior
                </button>
                <span className="fine">
                  {page.page}/{page.pages}
                </span>
                <button
                  className="ghost"
                  type="button"
                  disabled={pageNum >= page.pages}
                  onClick={() => setPageNum((p) => p + 1)}
                >
                  próxima ›
                </button>
              </div>
            </>
          ) : (
            <p className="sp-empty">
              Nenhuma referência {page && !page.indice.ok ? "(rode a coleta acima ou /mood_vibe_scout)" : "com esse filtro"}.
            </p>
          )}
        </div>
      </div>
      {progEl}
    </Modal>
  );
}
