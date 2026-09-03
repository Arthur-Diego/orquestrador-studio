// Etapa 2 — Mood board (aula 009), fluxo "etapa2-pick" (ADR-014) — Wave 10 · E4 (card [REACT-05]).
//
// Porta React de `studio/etapas/mood/view.{html,js}`. REFATORAÇÃO PURA: mesmo DOM (ids/classes),
// mesmo comportamento, mesmos textos de aula (ADR-004). A CRIAÇÃO de mood boards vive na biblioteca
// global (#/moodboards); esta etapa só ESCOLHE um board e o APLICA à campanha (`POST /mood/pull`).
//
// Contrato de host (E3, `frontend/src/shell/plugin.ts`): default export = componente React que pega
// o `ctx` por `useStudio()`. O ciclo init/destroy é o do React (mount/unmount); a troca de campanha
// remonta a tela. O CSS da tela mora num `<style>` renderizado no JSX — some com o unmount, como o
// `main.innerHTML=…` do vanilla removia o `<style>` do `view.html` (recon §6.4).
import { useCallback, useEffect, useRef, useState } from "react";

import { MoodMosaic, StepGuide } from "../../../../frontend/src/ui";
import { useStudio } from "../../../../frontend/src/shell/plugin";

const STEP_ID = "mood";

/** Um board da biblioteca global (`GET /api/moodboards`). */
interface Board {
  id: string;
  name: string;
  count: number;
  vibe?: string;
  cover?: string | null;
  thumbs?: string[];
}

/** Mood atual da campanha (`GET /api/projects/{pid}/mood`). */
interface MoodAtual {
  vibe?: string;
  palette?: string[];
  selected?: { file: string }[];
}

/** Navega para a biblioteca global usando o MESMO mecanismo do shell (roteamento por hash). */
function goLibrary(): void {
  location.hash = "#/moodboards";
}

export default function MoodScreen() {
  const ctx = useStudio();
  const [boards, setBoards] = useState<Board[]>([]);
  const [current, setCurrent] = useState<MoodAtual | null>(null);
  const [pick, setPick] = useState<string>("");
  const [guideNonce, setGuideNonce] = useState(0);
  const [aplicando, setAplicando] = useState(false);
  const panelPickRef = useRef<HTMLElement>(null);

  const pid = ctx.pid();

  // ---------- carga (o `load()` do vanilla) ----------
  const load = useCallback(async () => {
    if (!ctx.pid()) {
      setBoards([]);
      setCurrent(null);
      return;
    }
    const [b, c] = await Promise.all([
      ctx.api("/api/moodboards").catch(() => []),
      ctx.api(`/api/projects/${ctx.pid()}/mood`).catch(() => null),
    ]);
    setBoards((b as Board[]) || []);
    setCurrent((c as MoodAtual) || null);
  }, [ctx]);

  // Mount + troca de campanha: recarrega e limpa a escolha (o `onProject()` do vanilla).
  useEffect(() => {
    setPick("");
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  // A escolha que sumiu da lista deixa de valer (o `if (pick && !boards.some…)` do vanilla).
  useEffect(() => {
    if (pick && !boards.some((x) => x.id === pick)) setPick("");
  }, [boards, pick]);

  const boardEscolhido = boards.find((x) => x.id === pick);
  const mbCount = boardEscolhido ? `${boardEscolhido.name} selecionado` : "nenhum selecionado";
  const aplicarDesabilitado = !boardEscolhido || !boardEscolhido.count;

  function escolher(id: string): void {
    setPick((atual) => (atual === id ? "" : id));
  }

  async function applyBoard(): Promise<void> {
    const b = boards.find((x) => x.id === pick);
    if (!b || !b.count) return;
    setAplicando(true);
    try {
      const r = (await ctx.api(
        `/api/projects/${ctx.pid()}/mood/pull/${encodeURIComponent(b.id)}`,
        { method: "POST" },
      )) as { selected: number; vibe?: string };
      ctx.toast(
        r.vibe
          ? `${r.selected} imagens aplicadas · vibe: ${r.vibe}`
          : `${r.selected} imagens aplicadas do board`,
      );
      setPick("");
      await load();
      setGuideNonce((n) => n + 1); // recarrega o guia e reconcilia o rail (o `ctx.guide()` do vanilla)
    } catch (err) {
      ctx.toast((err as Error).message);
    } finally {
      setAplicando(false);
    }
  }

  // "Trocar": volta a escolher — leva a rolagem ao painel de escolha.
  function trocar(): void {
    panelPickRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const moodFiles = current?.selected ?? [];
  const vibeTxt = current?.vibe ? `vibe: ${current.vibe}` : "vibe: —";
  const cores = current?.palette ?? [];

  return (
    <>
      <style>{`
  /* Etapa 2 (etapa2-pick): a tela só ESCOLHE um board da biblioteca e o aplica. \`#mbGrid .card\`
     é selecionável (cursor/anel de seleção); os tiles do "Mood atual" são só leitura. */
  #mbGrid .card{cursor:pointer}
  #mbGrid .card.is-empty{opacity:.55;cursor:not-allowed}
  #mbGrid .mb-nocover{display:flex;align-items:center;justify-content:center;width:100%;height:100%;font-size:.8rem;opacity:.6}
  .md-current #moodGallery .card{cursor:default}
`}</style>

      <header className="stephead">
        <span className="eyebrow">Etapa 2 · aula 009</span>
        <h2>Mood board</h2>
        <p className="lede">
          Uma vibe só para a campanha inteira — ambiente, luz e cor. A criação de moods vive na{" "}
          <b>biblioteca global</b>; aqui você <b>escolhe</b> um mood board e o <b>aplica</b> a esta
          campanha.
        </p>
      </header>

      <section id="guide" className="guide">
        <StepGuide key={guideNonce} stepId={STEP_ID} pid={pid} onGuide={ctx.onGuide} />
      </section>

      <section className="panel" id="panelPick" ref={panelPickRef}>
        <div className="panel-head">
          <h3>
            <span className="pn">01</span>Escolher um mood board
          </h3>
          <div className="row wrap">
            <span id="mbCount" className="chip mode">
              {mbCount}
            </span>
            <button
              id="btnApplyBoard"
              className={aplicando ? "primary loading" : "primary"}
              disabled={aplicarDesabilitado || aplicando}
              onClick={applyBoard}
            >
              Aplicar a esta campanha
            </button>
          </div>
        </div>
        <p className="fine">
          A criação e a curadoria de mood boards ficam na biblioteca global{" "}
          <span className="ext">[extensão]</span>. Aqui você só escolhe um board existente e o aplica
          — as imagens dele são <b>copiadas</b> para o mood desta campanha (o board fica intacto).
        </p>
        <div id="mbGrid" className="gallery sm">
          {boards.length ? (
            boards.map((b) => {
              const disabled = !b.count;
              const legenda = `${b.name} · ${b.count} img${b.vibe ? " · " + b.vibe : ""}`;
              const rels = b.thumbs && b.thumbs.length ? b.thumbs : b.cover ? [b.cover] : [];
              const thumbs = rels.map((rel) => `/mbfiles/${encodeURIComponent(b.id)}/${rel}`);
              const cls = `card ${pick === b.id ? "sel" : ""}${disabled ? " is-empty" : ""}`;
              return (
                <div
                  key={b.id}
                  className={cls}
                  data-mb={b.id}
                  {...(disabled ? {} : { tabIndex: 0 })}
                  title={b.name}
                  onClick={() => {
                    if (!disabled) escolher(b.id);
                  }}
                  onKeyDown={(e) => {
                    if (disabled) return;
                    if (e.key !== "Enter" && e.key !== " ") return;
                    e.preventDefault();
                    escolher(b.id);
                  }}
                >
                  {thumbs.length ? (
                    <MoodMosaic urls={thumbs} />
                  ) : (
                    <span className="mb-nocover">sem imagens</span>
                  )}
                  <span className="term">{legenda}</span>
                </div>
              );
            })
          ) : (
            <div className="empty">
              Nenhum mood board ainda — crie um na biblioteca global.{" "}
              <button type="button" className="link" id="btnGoLibEmpty" onClick={goLibrary}>
                Ir para a biblioteca →
              </button>
            </div>
          )}
        </div>
      </section>

      <section className="panel md-current" id="panelCurrent">
        <div className="panel-head">
          <h3>
            <span className="pn">02</span>Mood atual da campanha
          </h3>
          <div className="row wrap">
            <span id="moodVibe" className="chip info">
              {vibeTxt}
            </span>
            <button id="btnSwap" className="ghost" onClick={trocar}>
              Trocar
            </button>
            <button id="btnManageBoards" className="ghost" onClick={goLibrary}>
              Criar / gerenciar mood boards
            </button>
          </div>
        </div>
        <div id="palette" className="palette">
          {cores.map((c, i) => (
            <span key={i} style={{ background: c }} title={c} />
          ))}
          <span className="lbl">palette.json · derivado técnico [extensão]</span>
        </div>
        <div id="moodGallery" className="gallery sm">
          {moodFiles.length ? (
            <MoodMosaic urls={moodFiles.map((f) => ctx.files(`mood/selected/${f.file}`))} />
          ) : (
            <div className="empty">
              Nenhum mood aplicado ainda — escolha um mood board acima e clique em “Aplicar a esta
              campanha”.
            </div>
          )}
        </div>
      </section>
    </>
  );
}
