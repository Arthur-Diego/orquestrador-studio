// Área global "Mood boards [extensão]" (ADR-013) — Wave 10 · E6 (card [REACT-07]).
//
// Biblioteca de mood boards reutilizáveis, independente de campanha. Porte React de
// `studio/web/moodboards.js` + `window.Studio.moodboards`. Rota reservada `#/moodboards` (lista) e
// `#/moodboards/<mbid>` (editor), resolvida pelo roteador da E3 (`router.ts` → `area="moodboards"`,
// `sub=<mbid>`); esta área é hospedada pelo content-root React do `Shell` (não mais pela ponte
// vanilla). Reusa a biblioteca de UI da E2 (`MoodMosaic`, `Modal`, `Chip`, `CopyButton`,
// `useUpload`, `useAutosize`, `useProgress`) e o componente compartilhado `Multishot` (ADR-017).
//
// O oráculo é `scripts/qa/cenarios/moodboards.py` (31 casos), que dirige a área por
// `window.Studio.moodboards.open(mbid)` — por isso a área REINSTALA esse global como escape hatch
// imperativo (força um refetch quando já se está na rota). Nada aqui muda o modelo de vibe única
// por campanha (ADR-007): o board é uma semente que a etapa 2 puxa e a etapa 3 referencia.
import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api";
import {
  Chip,
  CopyButton,
  MoodMosaic,
  Modal,
  useAutosize,
  useProgress,
  useUpload,
  upload,
} from "../../ui";
import { toast } from "../../shell/toast";
import { Multishot, type MultishotOpts } from "../multishot/Multishot";

// ---------- tipos das respostas ----------
interface BoardListItem {
  id: string;
  name: string;
  vibe?: string;
  note?: string;
  count: number;
  thumbs?: string[];
  cover?: string;
}

interface BoardCand {
  id: string;
  thumb: string;
  file: string;
  name?: string;
  source?: string;
  role?: string;
  selected?: boolean;
  parent?: string;
  prompt?: string;
}

interface BoardData {
  id: string;
  name: string;
  vibe?: string;
  note?: string;
  folder?: string;
  candidates: BoardCand[];
  palette: { colors?: string[] };
  prompt?: string;
  available_claude?: boolean;
}

const msg = (e: unknown): string => (e as Error)?.message || String(e);
const mb = (mbid: string, rel: string): string => `/mbfiles/${encodeURIComponent(mbid)}/${rel}`;

const KEY_LISTA = ["mb", "list"] as const;
const keyBoard = (mbid: string) => ["mb", "board", mbid] as const;

// =====================================================================================
// Área — decide lista × editor pela sub-rota e instala o escape hatch `window.Studio.moodboards`.
// =====================================================================================
export interface MoodboardsAreaProps {
  /** mbid do editor, ou `null` para a biblioteca (vem do `router.ts` da E3). */
  sub: string | null;
  /** Muda de valor para forçar um refresh (clique repetido no item da sidebar). */
  refreshKey?: number;
}

export function MoodboardsArea({ sub, refreshKey = 0 }: MoodboardsAreaProps) {
  const qc = useQueryClient();

  // `window.Studio.moodboards.open/goList/goEditor` — o cenário de QA dirige a área por aqui.
  useEffect(() => {
    const goList = () => {
      if (location.hash === "#/moodboards") void qc.invalidateQueries({ queryKey: KEY_LISTA });
      else location.hash = "#/moodboards";
    };
    const goEditor = (mbid: string) => {
      location.hash = `#/moodboards/${encodeURIComponent(mbid)}`;
    };
    const open = (mbid: string | null) => {
      if (mbid) {
        const alvo = `#/moodboards/${encodeURIComponent(mbid)}`;
        if (location.hash === alvo) void qc.invalidateQueries({ queryKey: keyBoard(mbid) });
        else location.hash = alvo;
      } else {
        if (location.hash === "#/moodboards") void qc.invalidateQueries({ queryKey: KEY_LISTA });
        else location.hash = "#/moodboards";
      }
    };
    const g = (window.Studio = window.Studio || {});
    g.moodboards = { open, goList, goEditor };
  }, [qc]);

  // Refresh externo (clique repetido na sidebar): revalida a rota ativa.
  useEffect(() => {
    if (refreshKey <= 0) return;
    if (sub) void qc.invalidateQueries({ queryKey: keyBoard(sub) });
    else void qc.invalidateQueries({ queryKey: KEY_LISTA });
  }, [refreshKey, sub, qc]);

  return sub ? <BoardEditor key={sub} mbid={sub} /> : <BoardLibrary />;
}

// =====================================================================================
// Biblioteca (lista)
// =====================================================================================
function BoardLibrary() {
  const [novo, setNovo] = useState(false);
  const { data: boards, isLoading } = useQuery({
    queryKey: KEY_LISTA,
    queryFn: () => api("/api/moodboards") as Promise<BoardListItem[]>,
  });

  const abrirEditor = (mbid: string) => {
    location.hash = `#/moodboards/${encodeURIComponent(mbid)}`;
  };

  if (isLoading || !boards) return <div className="empty">Carregando a biblioteca…</div>;

  return (
    <>
      <header className="stephead ov">
        <span className="eyebrow">Biblioteca · independente de campanha</span>
        <h2>
          Mood boards <span className="ext">[extensão]</span>
        </h2>
        <p className="lede">
          Mood boards reutilizáveis: monte uma vez e use em qualquer campanha. A etapa 2 pode{" "}
          <b>puxar</b> um board e a etapa 3 pode referenciá-lo visualmente. Estende a vibe única do
          curso (ADR-007).
        </p>
        <div className="ov-actions">
          <button type="button" className="primary" id="btnNewBoard" onClick={() => setNovo(true)}>
            Novo mood board
          </button>
        </div>
      </header>
      {boards.length ? (
        <div className="ovgrid mb-grid">
          {boards.map((b) => {
            const rels = b.thumbs && b.thumbs.length ? b.thumbs : b.cover ? [b.cover] : [];
            const thumbs = rels.map((rel) => mb(b.id, rel));
            return (
              <article
                key={b.id}
                className="ovcard mb-card"
                data-mb={b.id}
                tabIndex={0}
                role="button"
                title={b.name}
                onClick={() => abrirEditor(b.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    abrirEditor(b.id);
                  }
                }}
              >
                <MoodMosaic urls={thumbs} />
                <h4>{b.name}</h4>
                <p className="desc">{b.vibe || b.note || ""}</p>
                <div className="mb-meta">
                  <Chip kind="mode">{`${b.count} imagem(ns)`}</Chip>
                  {b.vibe ? <Chip kind="info">{`vibe: ${b.vibe}`}</Chip> : null}
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="empty-state">
          <span className="eyebrow">Biblioteca vazia</span>
          <h2>Nenhum mood board ainda</h2>
          <p className="lede">
            Crie um mood board reutilizável — importe imagens que definem uma vibe e use-o quando
            quiser.
          </p>
          <button className="primary" id="btnNewBoard2" type="button" onClick={() => setNovo(true)}>
            Criar o primeiro mood board
          </button>
        </div>
      )}
      {novo ? (
        <NewBoardModal onClose={() => setNovo(false)} onCreated={(mbid) => abrirEditor(mbid)} />
      ) : null}
    </>
  );
}

function NewBoardModal({ onClose, onCreated }: { onClose: () => void; onCreated: (mbid: string) => void }) {
  const nameRef = useRef<HTMLInputElement>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const form = e.currentTarget as HTMLFormElement;
    const name = (form.elements.namedItem("name") as HTMLInputElement).value.trim();
    const note = (form.elements.namedItem("note") as HTMLInputElement).value.trim();
    if (!name) {
      toast("Dê um nome ao mood board");
      nameRef.current?.focus();
      return;
    }
    try {
      const board = (await api("/api/moodboards", {
        method: "POST",
        body: JSON.stringify({ name, note }),
      })) as { id: string; name: string };
      onClose();
      toast(`Mood board ${board.name} criado`);
      onCreated(board.id);
    } catch (err) {
      toast(msg(err));
    }
  };

  return (
    <Modal
      title="Novo mood board"
      subtitle="Um mood board reutilizável — independente de campanha."
      onClose={onClose}
    >
      <form id="mbForm" noValidate onSubmit={submit}>
        <label className="field" htmlFor="mbName">
          <span className="eyebrow">Nome do mood board</span>
          <input id="mbName" name="name" required maxLength={80} placeholder="ex.: Neon Snow" ref={nameRef} />
        </label>
        <label className="field" htmlFor="mbNote">
          <span className="eyebrow">Nota — opcional</span>
          <input id="mbNote" name="note" placeholder="do que se trata este mood" />
        </label>
        <div className="modal-actions">
          <button type="button" className="ghost lg" data-close onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="primary lg">
            Criar mood board
          </button>
        </div>
      </form>
    </Modal>
  );
}

// =====================================================================================
// Editor de um board
// =====================================================================================
const EDITOR_CSS = `
        .msc-folder{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:.8rem;opacity:.8;margin:.3rem 0 0}
        .msc-folder code{font-family:ui-monospace,monospace;background:rgba(120,120,120,.16);padding:2px 6px;border-radius:6px;word-break:break-all}
        .msc-hint{font-size:.82rem;opacity:.72;margin:.2rem 0 .6rem}
        .msc-card .use-btn{position:absolute;bottom:6px;left:6px;font-size:.72rem;padding:2px 8px;border-radius:999px;
          border:none;cursor:pointer;background:rgba(60,150,90,.9);color:#fff;z-index:2}
        .msc-card .use-btn:hover{background:rgba(60,170,100,1)}
`;

type PromptMode = "images" | "brief" | "template";

function BoardEditor({ mbid }: { mbid: string }) {
  const qc = useQueryClient();
  const {
    data,
    isLoading,
    error,
  } = useQuery({
    queryKey: keyBoard(mbid),
    queryFn: () => api(`/api/moodboards/${encodeURIComponent(mbid)}`) as Promise<BoardData>,
  });

  const [sel, setSel] = useState<Set<string>>(new Set());
  const [promptText, setPromptText] = useState("");
  const [mode, setMode] = useState<PromptMode>("images");
  const [noPeople, setNoPeople] = useState(true);
  const [instrucao, setInstrucao] = useState("");
  const [copiado, setCopiado] = useState("");
  const [multishot, setMultishot] = useState<MultishotOpts | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [prog, progEl] = useProgress();
  const promptRef = useRef<HTMLTextAreaElement>(null);
  useAutosize(promptRef, [promptText]);

  const reload = useCallback(() => qc.invalidateQueries({ queryKey: keyBoard(mbid) }), [qc, mbid]);
  const goList = () => {
    location.hash = "#/moodboards";
  };

  // Sincroniza a seleção/prompt/modo com os dados sempre que uma nova busca chega (montar/reload).
  useEffect(() => {
    if (!data) return;
    setSel(new Set(data.candidates.filter((c) => c.selected).map((c) => c.id)));
    setPromptText(data.prompt || "");
    setMode(data.available_claude ? "images" : "template");
  }, [data]);

  const uploadFiles = useCallback(
    async (files: FileList) => {
      if (!files || !files.length) return;
      try {
        const r = (await upload(`/api/moodboards/${encodeURIComponent(mbid)}/import/upload`, files)) as {
          added?: number;
        };
        toast(`${r.added} imagem(ns) importada(s)`);
        await reload();
      } catch (err) {
        toast(msg(err));
      }
    },
    [mbid, reload],
  );
  const dz = useUpload(uploadFiles);

  if (isLoading) return <div className="empty">Carregando o mood board…</div>;
  if (error || !data) {
    return (
      <div className="empty">
        Mood board não encontrado: {msg(error)}{" "}
        <button className="link" id="mbBack" onClick={goList}>
          ← voltar à biblioteca
        </button>
      </div>
    );
  }

  const waiting = data.candidates.filter((c) => !sel.has(c.id));
  const chosen = data.candidates.filter((c) => sel.has(c.id));
  const colors = data.palette?.colors ?? [];

  const usarNoBoard = (id: string) => setSel((prev) => new Set(prev).add(id));
  const tirarDoBoard = (id: string) =>
    setSel((prev) => {
      const n = new Set(prev);
      n.delete(id);
      return n;
    });

  const abrirMultishot = (id: string) => {
    const cand = data.candidates.find((c) => c.id === id);
    if (!cand) {
      toast("Imagem não encontrada");
      return;
    }
    setMultishot({
      title: "Multishot da imagem de vibe",
      subtitle: `Mood board "${data.name}" · outros ângulos da mesma vibe (aula 011) [extensão]`,
      sourceUrl: mb(mbid, "candidates/" + cand.file),
      action: "mood.multishot",
      parentId: id,
      canRemove: true,
      endpoints: {
        generate: `/api/moodboards/${encodeURIComponent(mbid)}/multishot/generate`,
        job: `/api/moodboards/${encodeURIComponent(mbid)}/multishot/job`,
        candidates: `/api/moodboards/${encodeURIComponent(mbid)}/candidates`,
        upload: `/api/moodboards/${encodeURIComponent(mbid)}/import/upload`,
        importDownloads: `/api/moodboards/${encodeURIComponent(mbid)}/import/downloads`,
        downloadsFolder: `/api/moodboards/${encodeURIComponent(mbid)}/downloads-folder`,
        openFolder: `/api/moodboards/${encodeURIComponent(mbid)}/open-folder`,
      },
      fileUrl: (rel) => mb(mbid, "candidates/" + rel),
      onChanged: () => void reload(),
    });
  };

  const importDownloads = async () => {
    try {
      const r = (await api(`/api/moodboards/${encodeURIComponent(mbid)}/import/downloads`, {
        method: "POST",
        body: JSON.stringify({ since_minutes: 120 }),
      })) as { added?: number; scanned?: number };
      toast(`${r.added} novas de ${r.scanned} imagens recentes`);
      await reload();
    } catch (err) {
      toast(msg(err));
    }
  };

  const importHistory = async () => {
    try {
      const r = (await api(`/api/moodboards/${encodeURIComponent(mbid)}/import/history`, {
        method: "POST",
      })) as { added?: number; jobs?: number };
      toast(`${r.added} imagens de ${r.jobs} jobs`);
      await reload();
    } catch (err) {
      toast(msg(err));
    }
  };

  const saveSelection = async () => {
    try {
      const r = (await api(`/api/moodboards/${encodeURIComponent(mbid)}/select`, {
        method: "POST",
        body: JSON.stringify({ ids: [...sel] }),
      })) as { selected?: number };
      toast(`${r.selected} imagem(ns) no board`);
      await reload();
    } catch (err) {
      toast(msg(err));
    }
  };

  const openBoardFolder = async () => {
    try {
      const r = (await api(`/api/moodboards/${encodeURIComponent(mbid)}/open-folder`, {
        method: "POST",
        body: JSON.stringify({ target: "board" }),
      })) as { opened?: boolean; path?: string };
      toast(r.opened ? "Pasta do board aberta no explorador" : `Pasta do board: ${r.path}`);
    } catch (err) {
      toast(msg(err));
    }
  };

  const genPrompt = async () => {
    if (mode === "images" && !sel.size) {
      toast("Salve/escolha ao menos uma imagem para o bot olhar");
      return;
    }
    const gen = () =>
      api(`/api/moodboards/${encodeURIComponent(mbid)}/prompt/generate`, {
        method: "POST",
        body: JSON.stringify({ mode, instruction: instrucao, image_ids: [...sel], no_people: noPeople }),
      }) as Promise<{ prompt: string; source?: string; seconds?: number }>;
    const aplicar = (r: { prompt: string; source?: string; seconds?: number }) => {
      setPromptText(r.prompt);
      toast(`Prompt ${r.source === "claude" ? "escrito pelo bot" : "do template"} (${r.seconds || 0}s)`);
    };
    // Modo template é instantâneo (sem Claude): não pisca o modal de progresso.
    if (mode === "template") {
      try {
        aplicar(await gen());
      } catch (err) {
        toast(msg(err));
      }
      return;
    }
    // Chamada síncrona ao Claude: modal com as FASES reais + cronômetro (progresso honesto).
    prog.progress({ title: "Gerar prompt de vibe", subtitle: "Bot de prompts (Claude) — mood board [extensão]" });
    prog.step(mode === "images" ? `Preparando as imagens do board (${sel.size})` : "Preparando o brief");
    prog.step("Consultando o Claude…");
    try {
      const r = await gen();
      prog.step("Formatando no padrão do bot");
      aplicar(r);
      prog.ok("Pronto");
      setTimeout(() => prog.close(), 700);
    } catch (err) {
      prog.fail(msg(err));
      toast(msg(err));
    }
  };

  return (
    <>
      <style>{EDITOR_CSS}</style>
      <header className="stephead">
        <span className="eyebrow">
          <button className="link" id="mbBack" onClick={goList}>
            ← Biblioteca
          </button>{" "}
          · Mood board <span className="ext">[extensão]</span>
        </span>
        <h2 id="mbTitle">{data.name}</h2>
        <p className="lede" id="mbSub">
          {data.vibe ||
            data.note ||
            "Importe imagens que definem a vibe deste board, cure a galeria e gere um prompt de vibe."}
        </p>
        <p className="msc-folder">
          <span>Pasta do board:</span> <code id="mbFolder">{data.folder || ""}</code>
        </p>
        <div className="ov-actions">
          <button
            type="button"
            className="ghost"
            id="btnMbOpenFolder"
            title="Abrir a pasta do board no explorador do SO — fácil de copiar as fotos"
            onClick={() => void openBoardFolder()}
          >
            Abrir pasta
          </button>
          <button type="button" className="ghost" id="btnMbRename" onClick={() => setRenaming(true)}>
            Renomear
          </button>
          <button
            type="button"
            className="ghost danger"
            id="btnMbDelete"
            onClick={() => setDeleting(true)}
          >
            Apagar mood board
          </button>
        </div>
      </header>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">01</span>Importar imagens
          </h3>
          <span id="mbImpCount" className="chip mode">
            {`${waiting.length} aguardando`}
          </span>
        </div>
        <div className="import-row">
          <label className={`drop${dz.isOver ? " over" : ""}`} id="mbDrop" {...dz.rootProps}>
            Arraste imagens aqui ou <input id="mbUpload" accept="image/*" {...dz.inputProps} />
            <u>escolha arquivos</u>
          </label>
          <div className="col">
            <button
              id="btnMbDownloads"
              className="ghost"
              title="Imagens recentes da pasta Downloads"
              onClick={() => void importDownloads()}
            >
              Importar da pasta Downloads
            </button>
            <button
              id="btnMbHistory"
              className="ghost"
              title="via higgsfield generate list --image (precisa de login no CLI)"
              onClick={() => void importHistory()}
            >
              Importar do histórico Higgsfield
            </button>
          </div>
        </div>
        <p className="msc-hint">
          Importadas ficam aqui até você mandá-las ao board. Cada uma pode gerar outros ângulos (
          <b>▨ ângulos</b>) e é promovida à curadoria com <b>usar no board</b>.
        </p>
        <div id="mbImported" className="gallery sm">
          {waiting.length ? (
            waiting.map((c) => (
              <CandCard
                key={c.id}
                mbid={mbid}
                cand={c}
                promotable
                onMultishot={() => abrirMultishot(c.id)}
                onUse={() => usarNoBoard(c.id)}
              />
            ))
          ) : (
            <div className="empty">Nenhuma imagem aguardando — importe acima ou gere ângulos.</div>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">02</span>Curar a galeria
          </h3>
          <div className="row wrap">
            <span id="mbCounts" className="chip mode">
              {`${data.candidates.length} candidatas · ${sel.size} escolhidas (máx. 8)`}
            </span>
            <button id="btnMbSave" className="primary" onClick={() => void saveSelection()}>
              Salvar seleção
            </button>
          </div>
        </div>
        <p className="fine">
          Só as imagens escolhidas do painel 01 aparecem aqui (um board é uma vibe só — até 8). Clique
          numa imagem para tirá-la do board. O que você salvar é o que a etapa 2 puxa e a etapa 3
          mostra.
        </p>
        <div id="mbPalette" className="palette">
          {colors.map((c, i) => (
            <span key={i} style={{ background: c }} title={c} />
          ))}
          <span className="lbl">palette.json · derivado técnico [extensão]</span>
        </div>
        <div id="mbGallery" className="gallery sm">
          {chosen.length ? (
            chosen.map((c) => (
              <CandCard
                key={c.id}
                mbid={mbid}
                cand={c}
                promotable={false}
                onMultishot={() => abrirMultishot(c.id)}
                onRemove={() => tirarDoBoard(c.id)}
              />
            ))
          ) : (
            <div className="empty">Nenhuma imagem no board ainda — use "usar no board" no painel 01.</div>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">03</span>Prompt de vibe do board
          </h3>
          <div className="row wrap">
            <select
              id="mbMode"
              value={mode}
              onChange={(e) => setMode(e.target.value as PromptMode)}
            >
              <option value="images" disabled={!data.available_claude}>
                imagens do board + instrução
              </option>
              <option value="brief" disabled={!data.available_claude}>
                brief profissional
              </option>
              <option value="template">template fixo</option>
            </select>
            <span id="mbClaude" className={`chip ${data.available_claude ? "ok" : "warn"}`}>
              {data.available_claude ? "bot: claude ok" : "bot: sem claude"}
            </span>
          </div>
        </div>
        <div className="col g10">
          <input
            id="mbInstruction"
            className="lg"
            placeholder="sua instrução para o bot (ex.: mais neon e neve)"
            value={instrucao}
            onChange={(e) => setInstrucao(e.target.value)}
          />
          <div className="row opts wrap">
            <label className="inline">
              <input
                id="mbNoPeople"
                type="checkbox"
                checked={noPeople}
                onChange={(e) => setNoPeople(e.target.checked)}
              />{" "}
              sem pessoas
            </label>
            <button id="btnMbGenPrompt" className="primary" onClick={() => void genPrompt()}>
              Gerar prompt
            </button>
          </div>
          <div id="mbPromptList">
            {promptText ? (
              <div className="prompt">
                <div className="row">
                  <span className="eyebrow">Prompt de vibe</span>
                  <CopyButton
                    from="#mbPromptList textarea"
                    onResult={(ok) => setCopiado(ok ? "copiado ✓" : "copie à mão")}
                  />
                  <span className="ok">{copiado}</span>
                </div>
                <textarea data-i="0" ref={promptRef} defaultValue={promptText} key={promptText} />
              </div>
            ) : null}
          </div>
        </div>
      </section>

      {progEl}
      {renaming ? (
        <RenameModal mbid={mbid} data={data} onClose={() => setRenaming(false)} onDone={() => void reload()} />
      ) : null}
      {deleting ? (
        <DeleteModal mbid={mbid} name={data.name} onClose={() => setDeleting(false)} onDeleted={goList} />
      ) : null}
      {multishot ? <Multishot opts={multishot} onClose={() => setMultishot(null)} /> : null}
    </>
  );
}

// ---------- card de candidata ----------
function CandCard({
  mbid,
  cand,
  promotable,
  onMultishot,
  onUse,
  onRemove,
}: {
  mbid: string;
  cand: BoardCand;
  promotable: boolean;
  onMultishot: () => void;
  onUse?: () => void;
  onRemove?: () => void;
}) {
  return (
    <div
      className={`card msc-card${promotable ? "" : " sel"}`}
      data-id={cand.id}
      tabIndex={0}
      title={cand.name || ""}
      onClick={() => {
        if (!promotable) onRemove?.();
      }}
    >
      <img loading="lazy" src={mb(mbid, "candidates/" + cand.thumb)} alt="" />
      {cand.role === "multishot" ? <span className="src">multishot</span> : null}
      <button
        className="ms-btn"
        type="button"
        data-ms={cand.id}
        title="Gerar multishot (outros ângulos) desta imagem [extensão]"
        onClick={(e) => {
          e.stopPropagation();
          onMultishot();
        }}
      >
        ▨ ângulos
      </button>
      {promotable ? (
        <button
          className="use-btn"
          type="button"
          data-use={cand.id}
          title="Adicionar esta imagem ao board (painel 02)"
          onClick={(e) => {
            e.stopPropagation();
            onUse?.();
          }}
        >
          usar no board
        </button>
      ) : null}
      <span className="term">{`${cand.source || ""} · ${cand.name || ""}`}</span>
    </div>
  );
}

// ---------- renomear / apagar ----------
function RenameModal({
  mbid,
  data,
  onClose,
  onDone,
}: {
  mbid: string;
  data: BoardData;
  onClose: () => void;
  onDone: () => void;
}) {
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const form = e.currentTarget as HTMLFormElement;
    const name = (form.elements.namedItem("name") as HTMLInputElement).value.trim();
    const vibe = (form.elements.namedItem("vibe") as HTMLInputElement).value.trim();
    try {
      await api(`/api/moodboards/${encodeURIComponent(mbid)}`, {
        method: "PATCH",
        body: JSON.stringify({ name, vibe }),
      });
      onClose();
      toast("Mood board atualizado");
      onDone();
    } catch (err) {
      toast(msg(err));
    }
  };
  return (
    <Modal title="Renomear mood board" subtitle={`O id (${data.id}) permanece o mesmo.`} onClose={onClose}>
      <form id="mbRen" noValidate onSubmit={submit}>
        <label className="field">
          <span className="eyebrow">Nome</span>
          <input name="name" maxLength={80} defaultValue={data.name} />
        </label>
        <label className="field">
          <span className="eyebrow">Vibe em palavras — opcional</span>
          <input name="vibe" defaultValue={data.vibe || ""} />
        </label>
        <div className="modal-actions">
          <button type="button" className="ghost lg" data-close onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="primary lg">
            Salvar
          </button>
        </div>
      </form>
    </Modal>
  );
}

function DeleteModal({
  mbid,
  name,
  onClose,
  onDeleted,
}: {
  mbid: string;
  name: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  return (
    <Modal
      title="Apagar mood board [extensão]"
      subtitle="Ação destrutiva"
      onClose={onClose}
      actions={[
        { label: "Cancelar", kind: "ghost" },
        {
          label: "Apagar",
          kind: "primary",
          onClick: () => {
            void (async () => {
              try {
                await api(`/api/moodboards/${encodeURIComponent(mbid)}`, { method: "DELETE" });
                toast("Mood board apagado");
                onDeleted();
              } catch (err) {
                toast(msg(err));
              }
            })();
          },
        },
      ]}
    >
      <p>
        Isto apaga o mood board <b>{name}</b> e todas as suas imagens.
      </p>
      <p>
        A biblioteca é global: campanhas que já <b>puxaram</b> este board <b>não</b> são afetadas — a
        cópia para a campanha é independente.
      </p>
    </Modal>
  );
}
