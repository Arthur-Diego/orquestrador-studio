// MoodRun — corrida da cadeia `mood_orquestrador` pela tela `[extensão]` (ADH-OS-20260905-03).
//
// Roda a cadeia de skills de mood (foto-semente → DNA → prancha, um board por objetivo) headless
// via `claude -p`, de graça, e mostra as pranchas com os links de leitura/curadoria. Tudo — objetivos,
// fundos, defaults e pisos — vem de `/mood-run/options` (o manifesto das skills); nada é hardcoded.
// A prontidão é `available_claude` (mesmo padrão do "01b Motor local" do storyboard): sem `claude`
// no PATH, o botão desabilita e nada quebra.
//
// Modal controlado (montado quando aberto), no molde do `Multishot`. A escolha da semente é
// delegada ao `SeedPicker`. A cadeia `mood_` é gratuita: sem gate de custo (ADR-002, ADR-016).
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../../api";
import { Modal, useProgress, progressJob } from "../../ui";
import { toast } from "../../shell/toast";
import { SeedPicker } from "./SeedPicker";

interface MoodRunOptions {
  available_claude: boolean;
  objetivos: string[];
  agregador: string;
  fundos: string[];
  defaults: { board: number; n: number; fundo: string };
  limites: { board_min: number; n_min: number };
  escolhidas: { total: number; pasta: string };
}
interface ResultBoard {
  objetivo: string;
  imagens?: number;
  prancha_url?: string;
  leitura_url?: string;
  curadoria_url?: string;
}
interface RunResult {
  boards: ResultBoard[];
}

export interface MoodRunOpts {
  mbid: string;
  boardName?: string;
  onChanged?: () => void | Promise<void>;
}
export interface MoodRunProps {
  opts: MoodRunOpts;
  onClose: () => void;
}

const msg = (e: unknown): string => (e as Error)?.message || String(e);

const MR_CSS = `
    .mr-wrap{display:flex;flex-direction:column;gap:14px;max-height:72vh;overflow:auto}
    .mr-row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
    .mr-obj{display:flex;gap:8px;flex-wrap:wrap}
    .mr-obj label{display:inline-flex;gap:5px;align-items:center;font-size:.86rem;
      border:1px solid rgba(120,120,120,.35);border-radius:999px;padding:3px 10px;cursor:pointer}
    .mr-seed{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
    .mr-seed code{font-family:ui-monospace,monospace;background:rgba(120,120,120,.16);padding:2px 6px;
      border-radius:6px;max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .mr-est{font-size:.86rem;opacity:.85}
    .mr-boards{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
    .mr-board{border:1px solid rgba(120,120,120,.3);border-radius:12px;overflow:hidden;display:flex;
      flex-direction:column}
    .mr-board img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:rgba(0,0,0,.15)}
    .mr-board .mr-b-body{padding:8px 10px;display:flex;flex-direction:column;gap:4px}
    .mr-board .mr-b-links{display:flex;gap:10px;font-size:.78rem}
    .mr-empty{opacity:.7;font-size:.88rem;padding:8px 4px}
`;

const base = (mbid: string) => `/api/moodboards/${encodeURIComponent(mbid)}/mood-run`;

export function MoodRun({ opts, onClose }: MoodRunProps) {
  const { mbid } = opts;
  const [opt, setOpt] = useState<MoodRunOptions | null>(null);
  const [objs, setObjs] = useState<Set<string>>(new Set());
  const [todos, setTodos] = useState(false);
  const [board, setBoard] = useState("");
  const [n, setN] = useState("");
  const [fundo, setFundo] = useState("");
  const [foto, setFoto] = useState("");
  const [est, setEst] = useState<{ downloads: number } | null>(null);
  const [seedOpen, setSeedOpen] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [prog, progEl] = useProgress();
  // Guarda contra setState após desmontar (o portal do modal tocaria `window` fora do ciclo).
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  const loadResult = useCallback(async () => {
    try {
      const r = (await api(`${base(mbid)}/result`)) as RunResult;
      if (alive.current) setResult(r);
    } catch {
      if (alive.current) setResult(null); // 404 = nenhuma corrida ainda; erro degrada para "sem resultado"
    }
  }, [mbid]);

  useEffect(() => {
    let vivo = true;
    void api(`${base(mbid)}/options`)
      .then((o) => {
        if (!vivo) return;
        const op = o as MoodRunOptions;
        setOpt(op);
        setBoard((b) => (b === "" ? String(op.defaults.board) : b));
        setN((v) => (v === "" ? String(op.defaults.n) : v));
        setFundo((f) => (f === "" ? op.defaults.fundo : f));
      })
      .catch(() => setOpt(null));
    void loadResult();
    return () => {
      vivo = false;
    };
  }, [mbid, loadResult]);

  // Estimativa (contrato do backend): recalcula quando objetivos/board/n mudam. Latest-wins.
  useEffect(() => {
    const alvos = todos ? (opt ? [opt.agregador] : []) : [...objs];
    if (!alvos.length) {
      setEst(null);
      return;
    }
    let vivo = true;
    void api(`${base(mbid)}/estimate`, {
      method: "POST",
      body: JSON.stringify({ objetivos: alvos, board: Number(board) || undefined, n: Number(n) || undefined }),
    })
      .then((r) => {
        if (vivo) setEst(r as { downloads: number });
      })
      .catch(() => {
        if (vivo) setEst(null);
      });
    return () => {
      vivo = false;
    };
  }, [mbid, objs, todos, board, n, opt]);

  const toggleObj = (o: string) =>
    setObjs((prev) => {
      const s = new Set(prev);
      if (s.has(o)) s.delete(o);
      else s.add(o);
      return s;
    });

  const rodar = async () => {
    const alvos = todos ? [opt?.agregador].filter(Boolean) : [...objs];
    if (!alvos.length) {
      toast("Escolha ao menos um objetivo");
      return;
    }
    if (!foto) {
      toast("Escolha a foto-semente");
      return;
    }
    try {
      await progressJob(prog, {
        title: "Corrida de mood (grátis) [extensão]",
        subtitle: "Cadeia mood_orquestrador — um board por objetivo, sem gastar crédito",
        start: () =>
          api(base(mbid), {
            method: "POST",
            body: JSON.stringify({
              foto,
              objetivos: alvos,
              board: Number(board) || undefined,
              n: Number(n) || undefined,
              fundo: fundo || undefined,
            }),
          }),
        jobUrl: `${base(mbid)}/job`,
        done: async () => {
          await loadResult();
          await opts.onChanged?.();
        },
        label: "Pranchas geradas",
      });
    } catch (e) {
      toast(msg(e));
    }
  };

  const ready = !!opt?.available_claude;
  const fotoNome = foto ? foto.split("/").pop() : "";

  return (
    <>
      <Modal
        title="Corrida de mood (skills, grátis)"
        subtitle={`${opts.boardName ? `Mood board "${opts.boardName}" · ` : ""}mood_orquestrador headless [extensão]`}
        onClose={onClose}
      >
        <style>{MR_CSS}</style>
        <div className="mr-wrap">
          <div className="mr-row">
            <span className={`chip ${ready ? "ok" : "warn"}`}>
              {ready ? "claude: no ar" : opt ? "claude: offline" : "verificando…"}
            </span>
            <span className="fine">
              {opt ? `${opt.escolhidas.total} foto(s) na peneira` : ""}
            </span>
          </div>
          {!ready && opt ? (
            <p className="mr-empty">
              Sem <code>claude</code> no PATH — instale o Claude Code para rodar a cadeia. Você ainda
              pode montar a peneira e navegar as vibes.
            </p>
          ) : null}

          {/* objetivos */}
          <div className="mr-obj">
            <label>
              <input type="checkbox" checked={todos} onChange={(e) => setTodos(e.target.checked)} /> todos
            </label>
            {opt?.objetivos.map((o) => (
              <label key={o} style={{ opacity: todos ? 0.5 : 1 }}>
                <input
                  type="checkbox"
                  disabled={todos}
                  checked={objs.has(o)}
                  onChange={() => toggleObj(o)}
                />{" "}
                {o}
              </label>
            ))}
          </div>

          {/* board / n / fundo */}
          <div className="mr-row">
            <label className="inline">
              board{" "}
              <input type="number" min={opt?.limites.board_min ?? 4} value={board}
                     onChange={(e) => setBoard(e.target.value)} style={{ width: 64 }} />
            </label>
            <label className="inline">
              n{" "}
              <input type="number" min={opt?.limites.n_min ?? 1} value={n}
                     onChange={(e) => setN(e.target.value)} style={{ width: 64 }} />
            </label>
            <label className="inline">
              fundo{" "}
              <select value={fundo} onChange={(e) => setFundo(e.target.value)}>
                {opt?.fundos.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* semente */}
          <div className="mr-seed">
            <span className="eyebrow">Foto-semente:</span>
            {fotoNome ? <code title={foto}>{fotoNome}</code> : <span className="fine">nenhuma</span>}
            <button className="ghost" type="button" onClick={() => setSeedOpen(true)}>
              Escolher da vibe…
            </button>
          </div>

          {/* estimativa + rodar */}
          <div className="mr-row">
            <span className="mr-est">
              {est ? `≈ ${est.downloads} downloads (objetivos × (board − 1) × n)` : "escolha objetivos para estimar"}
            </span>
            <button
              className="primary"
              type="button"
              disabled={!ready}
              title={ready ? "" : "sem claude no PATH"}
              onClick={() => void rodar()}
            >
              Rodar corrida (grátis)
            </button>
          </div>

          {/* pranchas */}
          {result && result.boards.length ? (
            <div className="mr-sec">
              <span className="eyebrow">Pranchas da corrida vigente</span>
              <div className="mr-boards">
                {result.boards.map((b, i) => (
                  <div key={`${b.objetivo}-${i}`} className="mr-board">
                    {b.prancha_url ? (
                      <a href={b.prancha_url} target="_blank" rel="noreferrer">
                        <img src={b.prancha_url} alt={b.objetivo} loading="lazy" />
                      </a>
                    ) : (
                      <div className="mr-empty" style={{ padding: 16 }}>
                        prancha ainda não disponível
                      </div>
                    )}
                    <div className="mr-b-body">
                      <b>{b.objetivo}</b>
                      <div className="mr-b-links">
                        {b.leitura_url ? (
                          <a href={b.leitura_url} target="_blank" rel="noreferrer">
                            leitura
                          </a>
                        ) : null}
                        {b.curadoria_url ? (
                          <a href={b.curadoria_url} target="_blank" rel="noreferrer">
                            curadoria
                          </a>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </Modal>
      {progEl}
      {seedOpen ? (
        <SeedPicker
          onPick={(caminho) => setFoto(caminho)}
          onClose={() => {
            setSeedOpen(false);
            void api(`${base(mbid)}/options`)
              .then((o) => {
                if (alive.current) setOpt(o as MoodRunOptions);
              })
              .catch(() => {});
          }}
        />
      ) : null}
    </>
  );
}
