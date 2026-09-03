// Etapa 9 — Publicar (aula 015) — Wave 10 · E4 (card [REACT-05]).
//
// Porta React de `studio/etapas/publish/view.{html,js}`. REFATORAÇÃO PURA: registro manual dos
// posts, portfólio global (ADR-012) e checklist de comunidade. A validação (rede vazia, URL sem
// http, URL duplicada, export inexistente) é do BACKEND — a tela POSTa e joga `err.message` no
// toast, como o vanilla. Textos de aula preservados (ADR-004); DOM idêntico (ids/classes/ARIA).
import { useCallback, useEffect, useRef, useState } from "react";

import { StepGuide } from "../../../../frontend/src/ui";
import { useStudio } from "../../../../frontend/src/shell/plugin";

const STEP_ID = "publish";

interface ExportFile {
  file: string;
}
interface Post {
  id: string;
  network: string;
  url: string;
  video: string;
  posted_at: string;
  note?: string;
  feedback?: string;
}
interface Community {
  posted?: boolean;
  commented?: boolean;
  feedback?: boolean;
  done: number;
  total: number;
}
interface Status {
  count: number;
  community: Community;
}

const STATUS_INICIAL: Status = { count: 0, community: { done: 0, total: 3 } };

/** Data de hoje em ISO local (o `today()` do vanilla). */
function today(): string {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
}

/** URL como o protótipo a desenha: sem protocolo/www e cortada — a íntegra fica no `title`. */
function urlCurta(u: string): string {
  const limpa = String(u || "").replace(/^https?:\/\/(www\.)?/, "");
  return limpa.length > 28 ? limpa.slice(0, 28) + "…" : limpa;
}

export default function PublishScreen() {
  const ctx = useStudio();
  const [exports, setExports] = useState<ExportFile[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [status, setStatus] = useState<Status>(STATUS_INICIAL);
  const [video, setVideo] = useState("");
  const [network, setNetwork] = useState("");
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [data, setData] = useState(today());
  const [editing, setEditing] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [guideNonce, setGuideNonce] = useState(0);
  const savingNoteRef = useRef(false);

  const pid = ctx.pid();
  const base = useCallback(() => `/api/projects/${ctx.pid()}/publish`, [ctx]);

  const load = useCallback(async () => {
    if (!ctx.pid()) {
      setExports([]);
      setPosts([]);
      setStatus(STATUS_INICIAL);
      return;
    }
    const [ex, lg, st] = await Promise.all([
      ctx.api(`${base()}/exports`) as Promise<{ files: ExportFile[] }>,
      ctx.api(`${base()}/log`) as Promise<{ posts: Post[] }>,
      ctx.api(`${base()}/portfolio`) as Promise<Status>,
    ]);
    setExports(ex.files);
    setPosts(lg.posts);
    setStatus(st);
  }, [ctx, base]);

  // Mount + troca de campanha (o `onProject` do vanilla): data de hoje e recarga.
  useEffect(() => {
    setData(today());
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  // O select mantém a escolha se ainda existir; senão cai no primeiro export (renderExports).
  useEffect(() => {
    if (!exports.some((f) => f.file === video)) setVideo(exports[0]?.file ?? "");
  }, [exports, video]);

  function reconciliar(): void {
    setGuideNonce((n) => n + 1); // recarrega o guia + reconcilia o rail (o `ctx.guide()` do vanilla)
  }

  async function adicionar(): Promise<void> {
    const body = { video, network, url, posted_at: data || null, note };
    try {
      await ctx.api(`${base()}/log`, { method: "POST", body: JSON.stringify(body) });
      setUrl("");
      setNote("");
      ctx.toast("Publicação registrada");
      await load();
      reconciliar();
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }

  async function marcarComunidade(com: "posted" | "commented" | "feedback", checked: boolean): Promise<void> {
    // atualização otimista para o checkbox controlado; revertida no erro (como o vanilla)
    setStatus((s) => ({ ...s, community: { ...s.community, [com]: checked } }));
    try {
      await ctx.api(`${base()}/community`, { method: "POST", body: JSON.stringify({ [com]: checked }) });
      await load();
      reconciliar();
    } catch (err) {
      ctx.toast((err as Error).message);
      setStatus((s) => ({ ...s, community: { ...s.community, [com]: !checked } }));
    }
  }

  async function remover(id: string): Promise<void> {
    if (!confirm("Remover este registro de publicação? O post continua no ar na rede.")) return;
    try {
      await ctx.api(`${base()}/log/${id}`, { method: "DELETE" });
      ctx.toast("Registro removido");
      await load();
      reconciliar();
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }

  function abrirNota(p: Post): void {
    if (editing === p.id) return;
    savingNoteRef.current = false;
    setEditDraft(p.feedback || p.note || "");
    setEditing(p.id);
  }

  async function salvarNota(id: string, gravar: boolean): Promise<void> {
    if (savingNoteRef.current) return;
    savingNoteRef.current = true;
    setEditing(null);
    if (!gravar) return;
    try {
      await ctx.api(`${base()}/log/${id}/feedback`, {
        method: "POST",
        body: JSON.stringify({ feedback: editDraft }),
      });
      ctx.toast("Feedback salvo");
      await load();
      reconciliar();
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }

  const c = status.community || { done: 0, total: 3 };
  const chip = `${status.count} ${status.count === 1 ? "publicação" : "publicações"} · comunidade ${c.done}/${c.total}`;

  return (
    <>
      <style>{`
  /* Lacunas do catálogo do shell — escopo \`.pb-\` da etapa 9. */
  .pb-form{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
  .pb-form:last-of-type{margin-bottom:0}
  .pb-form .grow-lg{min-width:240px}
  #pubNetwork{width:170px}
  .pb-com{display:flex;gap:16px;flex-wrap:wrap;margin:14px 0 0}
  #pubLog{gap:8px;margin-bottom:14px}
  #pubLog:empty{margin-bottom:0}
  .pub-row .del{margin-left:auto}
  .pub-row .nt{cursor:text}
  .pub-row .nt-edit{width:100%;min-width:200px;background:transparent;border:0;border-bottom:1px solid var(--accent);border-radius:0;padding:0;font:inherit;font-size:var(--fs-fine);color:var(--ink-2)}
  .pub-row .nt-edit:focus{outline:none;box-shadow:none}
`}</style>

      <header className="stephead">
        <span className="eyebrow">Etapa 9 · aula 015</span>
        <h2>Publicar</h2>
        <p className="lede">
          Publique à mão na interface de cada rede e registre o link. Dever de casa:{" "}
          <strong>4 vídeos publicados</strong> antes de prospectar — prática, exposição e validação.
        </p>
      </header>

      <section id="guide" className="guide">
        <StepGuide key={guideNonce} stepId={STEP_ID} pid={pid} onGuide={ctx.onGuide} />
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">01</span>Registrar uma publicação
          </h3>
        </div>
        <div className="pb-form">
          <select
            id="pubVideo"
            aria-label="Vídeo exportado a publicar"
            value={video}
            onChange={(e) => setVideo(e.target.value)}
          >
            {exports.length ? (
              exports.map((f) => (
                <option key={f.file} value={f.file}>
                  {f.file}
                </option>
              ))
            ) : (
              <option value="">nenhum export disponível</option>
            )}
          </select>
          <input
            id="pubNetwork"
            list="pubNetworks"
            placeholder="rede (instagram, tiktok…)"
            value={network}
            onChange={(e) => setNetwork(e.target.value)}
          />
          <datalist id="pubNetworks">
            <option value="instagram" />
            <option value="tiktok" />
            <option value="youtube" />
            <option value="comunidade ABRAhub" />
            <option value="outro" />
          </datalist>
          <input
            id="pubDate"
            type="date"
            aria-label="Data da publicação"
            value={data}
            onChange={(e) => setData(e.target.value)}
          />
        </div>
        <div className="pb-form">
          <input
            id="pubUrl"
            className="grow-lg"
            placeholder="https://www.instagram.com/reel/…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <input
            id="pubNote"
            className="grow-md"
            placeholder="nota livre (o que você testou)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button id="btnPubAdd" className="primary" onClick={adicionar}>
            Registrar publicação
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">02</span>Publicações e comunidade
          </h3>
          <div className="row wrap">
            <span id="pubComChip" className="chip mode">
              {chip}
            </span>
          </div>
        </div>
        <div id="pubLog" className="rowlist">
          {posts.length ? (
            posts.map((p) => {
              const orfao = exports.length > 0 && !exports.some((f) => f.file === p.video);
              const texto = p.feedback || p.note || "";
              const dica = `${p.posted_at} · ${p.video}${orfao ? " — arquivo não está mais em export/" : ""}`;
              const emEdicao = editing === p.id;
              return (
                <div className="pub-row" data-id={p.id} title={dica} key={p.id}>
                  <span className="chip info">{p.network}</span>
                  <a className="url" href={p.url} target="_blank" rel="noopener" title={p.url}>
                    {urlCurta(p.url)}
                  </a>
                  <span
                    className="nt"
                    data-note={p.id}
                    tabIndex={0}
                    role="button"
                    title="clique para anotar o feedback recebido"
                    style={emEdicao ? { flex: "1 1 240px" } : undefined}
                    onClick={() => abrirNota(p)}
                    onKeyDown={(e) => {
                      if (!emEdicao && (e.key === "Enter" || e.key === " ")) {
                        e.preventDefault();
                        abrirNota(p);
                      }
                    }}
                  >
                    {emEdicao ? (
                      <input
                        className="nt-edit"
                        placeholder="feedback recebido"
                        autoFocus
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        onBlur={() => void salvarNota(p.id, true)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            void salvarNota(p.id, true);
                          } else if (e.key === "Escape") {
                            void salvarNota(p.id, false);
                          }
                        }}
                      />
                    ) : texto ? (
                      `“${texto}”`
                    ) : (
                      "“nota”"
                    )}
                  </span>
                  <button
                    className="link del act"
                    data-id={p.id}
                    title="remover este registro"
                    onClick={() => void remover(p.id)}
                  >
                    Remover
                  </button>
                </div>
              );
            })
          ) : (
            <div className="empty">Nenhuma publicação registrada. Poste na rede e cole o link aqui.</div>
          )}
        </div>
        <div className="row wrap pb-com" id="pubCommunity">
          <label className="inline">
            <input
              type="checkbox"
              data-com="posted"
              checked={!!c.posted}
              onChange={(e) => void marcarComunidade("posted", e.target.checked)}
            />{" "}
            postei na comunidade
          </label>
          <label className="inline">
            <input
              type="checkbox"
              data-com="commented"
              checked={!!c.commented}
              onChange={(e) => void marcarComunidade("commented", e.target.checked)}
            />{" "}
            comentei no trabalho de outra pessoa
          </label>
          <label className="inline">
            <input
              type="checkbox"
              data-com="feedback"
              checked={!!c.feedback}
              onChange={(e) => void marcarComunidade("feedback", e.target.checked)}
            />{" "}
            dei feedback
          </label>
        </div>
      </section>
    </>
  );
}
