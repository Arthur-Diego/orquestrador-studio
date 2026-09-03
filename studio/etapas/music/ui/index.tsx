// Etapa 6 — Trilha (aula 013) — Wave 10 · E4 (card [REACT-05]).
//
// Porta React de `studio/etapas/music/view.{html,js}`. REFATORAÇÃO PURA: assistir a história inteira
// (job ffmpeg atrás do `ProgressModal` da E2), ouvir/escolher candidatas (player por linha + import
// por seletor e arraste, via `useUpload`) e a régua de batidas (`Beats`). Textos de aula preservados
// (ADR-004); DOM idêntico (ids/classes/ARIA). `music/view.html` é o único sem bloco `<style>`.
import { useCallback, useEffect, useRef, useState } from "react";

import { Beats, Chip, StepGuide, useProgress, progressJob, useUpload } from "../../../../frontend/src/ui";
import { useStudio } from "../../../../frontend/src/shell/plugin";

const STEP_ID = "music";

interface StoryData {
  ffmpeg: boolean;
  clips: number;
  video: string | null;
  warning?: string;
  check?: { closed: boolean } | null;
}
interface Candidate {
  id: string;
  file: string;
  name?: string;
  duration?: number;
  bpm?: number;
  selected?: boolean;
}
interface BeatsData {
  duration: number;
  beats: number[];
  impacts: number[];
}

/** mm:ss (o `fmt` do vanilla); vazio para duração ausente/inválida. */
function fmt(s: number | undefined): string {
  return s == null || !isFinite(s) || s <= 0
    ? ""
    : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
}

export default function MusicScreen() {
  const ctx = useStudio();
  const [story, setStory] = useState<StoryData | null>(null);
  const [musClosed, setMusClosed] = useState<"" | "0" | "1">("");
  const [videoNonce, setVideoNonce] = useState(0);
  const [cands, setCands] = useState<Candidate[]>([]);
  const [beats, setBeats] = useState<BeatsData | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [storyBusy, setStoryBusy] = useState(false);
  const [guideNonce, setGuideNonce] = useState(0);
  const [handle, progressEl] = useProgress();
  const audioRefs = useRef(new Map<string, HTMLAudioElement>());
  const waveRefs = useRef(new Map<string, HTMLDivElement>());

  const pid = ctx.pid();

  function reconciliar(): void {
    setGuideNonce((n) => n + 1);
  }

  const loadStory = useCallback(async () => {
    if (!ctx.pid()) return;
    try {
      const s = (await ctx.api(`/api/projects/${ctx.pid()}/music/story`)) as StoryData;
      setStory(s);
      setVideoNonce(Date.now());
      setMusClosed(s.check ? (s.check.closed ? "1" : "0") : "");
    } catch {
      setStory(null);
    }
  }, [ctx]);

  const load = useCallback(async () => {
    if (!ctx.pid()) {
      setCands([]);
      setBeats(null);
      return;
    }
    const c = (await ctx.api(`/api/projects/${ctx.pid()}/music/candidates`)) as Candidate[];
    setCands(c);
    try {
      setBeats((await ctx.api(`/api/projects/${ctx.pid()}/music/beats`)) as BeatsData);
    } catch {
      setBeats(null);
    }
  }, [ctx]);

  // Mount + troca de campanha (o `onProject` do vanilla).
  useEffect(() => {
    void loadStory();
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  function renderStory(): void {
    setStoryBusy(true);
    progressJob(handle, {
      title: "Montar a história inteira",
      subtitle: "Sequência bruta dos takes com like (ffmpeg)",
      start: () => ctx.api(`/api/projects/${ctx.pid()}/music/story/render`, { method: "POST", body: "{}" }),
      jobUrl: `/api/projects/${ctx.pid()}/music/story/job`,
      done: async () => {
        await loadStory();
        reconciliar();
        ctx.toast("Sequência bruta pronta — assista inteira antes de escolher a trilha");
      },
    })
      .catch((err: unknown) => ctx.toast((err as Error).message))
      .finally(() => setStoryBusy(false));
  }

  async function saveStoryCheck(): Promise<void> {
    if (!musClosed) {
      ctx.toast("Responda se a história fecha ou se falta cena.");
      return;
    }
    try {
      await ctx.api(`/api/projects/${ctx.pid()}/music/story/check`, {
        method: "POST",
        body: JSON.stringify({ closed: musClosed === "1", note: "" }),
      });
      ctx.toast("Decisão registrada");
      await loadStory();
      reconciliar();
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }

  async function pick(id: string): Promise<void> {
    try {
      const r = (await ctx.api(`/api/projects/${ctx.pid()}/music/select`, {
        method: "POST",
        body: JSON.stringify({ id, license: "" }),
      })) as { beats?: BeatsData; warning?: string };
      const linha = r.beats
        ? `Trilha escolhida · ${r.beats.impacts.length} impactos`
        : "Trilha escolhida (sem detecção de batidas)";
      ctx.toast(`${r.warning ? r.warning + " · " : ""}${linha} — se você já montou, a etapa 7 precisa ser refeita`);
      await load();
      reconciliar();
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }

  const importar = useCallback(
    async (files: FileList): Promise<void> => {
      try {
        const r = (await ctx.apiUpload(`/api/projects/${ctx.pid()}/music/import/upload`, files)) as { added: number };
        ctx.toast(`${r.added} música(s) importada(s)`);
        await load();
        reconciliar();
      } catch (err) {
        ctx.toast((err as Error).message);
      }
    },
    // reconciliar/load estáveis o suficiente; ctx é estável (memoizado no shell)
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ctx, load],
  );

  const upload = useUpload(importar);

  // ---------- player por linha (imperativo, como o `<audio>` escondido do protótipo) ----------
  function pararOutros(exceto: string): void {
    audioRefs.current.forEach((a, id) => {
      if (id === exceto) return;
      if (!a.paused) a.pause();
      a.currentTime = 0;
      waveRefs.current.get(id)?.style.setProperty("--p", "0%");
    });
  }

  function onPlay(id: string): void {
    const audio = audioRefs.current.get(id);
    if (!audio) return;
    const tocar = audio.paused;
    pararOutros(id);
    if (tocar) {
      void audio.play();
      setPlayingId(id);
    } else {
      audio.pause();
      setPlayingId(null);
    }
  }

  function onWave(id: string, e: React.MouseEvent<HTMLDivElement>): void {
    const audio = audioRefs.current.get(id);
    const onda = waveRefs.current.get(id);
    if (!audio || !onda) return;
    const box = onda.getBoundingClientRect();
    const razao = Math.min(1, Math.max(0, (e.clientX - box.left) / (box.width || 1)));
    if (audio.duration) {
      audio.currentTime = razao * audio.duration;
      onda.style.setProperty("--p", `${(razao * 100).toFixed(1)}%`);
    }
  }

  function onTimeUpdate(id: string): void {
    const a = audioRefs.current.get(id);
    if (!a || !a.duration) return;
    waveRefs.current.get(id)?.style.setProperty("--p", `${((a.currentTime / a.duration) * 100).toFixed(1)}%`);
  }

  function onEnded(id: string): void {
    waveRefs.current.get(id)?.style.setProperty("--p", "0%");
    setPlayingId((p) => (p === id ? null : p));
  }

  const temSelecionada = cands.some((c) => c.selected);
  const beatsChip =
    !beats || !beats.duration
      ? {
          text: temSelecionada ? "trilha escolhida, sem batidas detectadas" : "nenhuma trilha escolhida",
          cls: temSelecionada ? "chip warn" : "chip mode",
        }
      : { text: `${beats.beats.length} batidas · ${beats.impacts.length} impactos`, cls: "chip ok" };
  const impactos = beats ? new Set(beats.impacts) : new Set<number>();

  return (
    <>
      <header className="stephead">
        <span className="eyebrow">Etapa 6 · aula 013</span>
        <h2>Trilha</h2>
        <p className="lede">
          Primeiro assista a história inteira, sem cortes. Depois ouça várias músicas e escolha{" "}
          <b>sentindo a energia</b> — a música define ritmo, emoção e impacto.
        </p>
      </header>

      <section id="guide" className="guide">
        <StepGuide key={guideNonce} stepId={STEP_ID} pid={pid} onGuide={ctx.onGuide} />
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">01</span>Assistir a história inteira
          </h3>
          <div className="row wrap">
            <span
              id="musStoryChip"
              className={
                story && (story.warning || !story.ffmpeg) ? "chip warn" : "chip warn hidden"
              }
            >
              {story ? story.warning || (story.ffmpeg ? "" : "ffmpeg ausente — a sequência bruta não pode ser montada aqui") : ""}
            </span>
            <button
              id="btnMusStory"
              className="primary"
              disabled={storyBusy || !(story?.ffmpeg && story?.clips)}
              onClick={renderStory}
            >
              Montar sequência bruta
            </button>
          </div>
        </div>
        <div className="grid2 even">
          <div className="player">
            <video
              id="musStoryVideo"
              className={story?.video ? "" : "hidden"}
              controls
              preload="metadata"
              {...(story?.video ? { src: `${ctx.files(story.video)}?t=${videoNonce}` } : {})}
            />
            <span id="musStoryPlay" className={story?.video ? "play-big hidden" : "play-big"}>
              ▶
            </span>
            <span className="term">audio/rough_sequence.mp4 · sem música, sem corte</span>
          </div>
          <div className="col g10">
            <p className="q">A história fecha, ou falta uma cena?</p>
            <label className="inline lg">
              <input
                type="radio"
                name="musClosed"
                value="1"
                checked={musClosed === "1"}
                onChange={() => setMusClosed("1")}
              />{" "}
              A história fecha
            </label>
            <label className="inline lg">
              <input
                type="radio"
                name="musClosed"
                value="0"
                checked={musClosed === "0"}
                onChange={() => setMusClosed("0")}
              />{" "}
              Falta cena / encerramento mais forte
            </label>
            <p className="note">Se faltar encerramento comercial, a saída é a cena do produto (etapas 5 e 6).</p>
            <button id="btnMusStoryCheck" className="ghost self-start" onClick={saveStoryCheck}>
              Salvar decisão
            </button>
          </div>
        </div>
      </section>

      <section className={upload.isOver ? "panel over" : "panel"} id="musPanel" {...upload.rootProps}>
        <div className="panel-head">
          <h3>
            <span className="pn">02</span>Ouvir e escolher
          </h3>
          <label id="musCounts" className="chip mode" htmlFor="musUpload" title="clique para importar mais músicas">
            {/* nó de texto único (como o vanilla) — o oráculo ADR-004 anda por text node */}
            {`${cands.length} ${cands.length === 1 ? "candidata" : "candidatas"}`}
          </label>
        </div>
        <input id="musUpload" accept="audio/*" {...upload.inputProps} />
        <div id="musList" className="rowlist">
          {cands.length ? (
            cands.map((c) => {
              const meta = [fmt(c.duration), c.bpm ? `${Math.round(c.bpm)} bpm` : ""].filter(Boolean).join(" · ");
              return (
                <div className={`rowcard track-row${c.selected ? " sel" : ""}`} data-id={c.id} key={c.id}>
                  <button className="play" data-id={c.id} title="ouvir / pausar" onClick={() => onPlay(c.id)}>
                    {playingId === c.id ? "❚❚" : "▶"}
                  </button>
                  <span className="meta">
                    <span className="nm">{c.name || c.file}</span>
                    <span className="mt">{meta}</span>
                  </span>
                  <div
                    className="wave"
                    title="clique para ir a um ponto da faixa"
                    ref={(el) => {
                      if (el) waveRefs.current.set(c.id, el);
                      else waveRefs.current.delete(c.id);
                    }}
                    onClick={(e) => onWave(c.id, e)}
                  />
                  <audio
                    hidden
                    preload="metadata"
                    src={ctx.files(`audio/candidates/${c.file}`)}
                    ref={(el) => {
                      if (el) audioRefs.current.set(c.id, el);
                      else audioRefs.current.delete(c.id);
                    }}
                    onTimeUpdate={() => onTimeUpdate(c.id)}
                    onEnded={() => onEnded(c.id)}
                  />
                  {c.selected ? (
                    <Chip kind="ok">escolhida</Chip>
                  ) : (
                    <button className="pick ghost sm" data-id={c.id} onClick={() => void pick(c.id)}>
                      Escolher
                    </button>
                  )}
                </div>
              );
            })
          ) : (
            <label className="drop" htmlFor="musUpload">
              Arraste músicas aqui ou <u>escolha arquivos</u>
            </label>
          )}
        </div>
        <p className="note">
          Ouça cada faixa inteira; escolha pelo sentimento, não pelo bpm. Ao escolher: audio/music.* + batidas em
          audio/beats.json.
        </p>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">03</span>Batidas da trilha escolhida
          </h3>
          <span id="musBeatsChip" className={beatsChip.cls}>
            {beatsChip.text}
          </span>
        </div>
        <div id="musRuler">
          {beats && beats.duration ? (
            <Beats
              lista={beats.beats.map((t, i) => ({
                h: impactos.has(t) ? 100 : 24 + ((i * 37) % 40),
                imp: impactos.has(t),
                title: `${t}s${impactos.has(t) ? " (impacto)" : ""}`,
              }))}
            />
          ) : null}
          <p className="note">Riscos altos são os impactos — é neles que a etapa 7 propõe os cortes.</p>
        </div>
      </section>

      {progressEl}
    </>
  );
}
