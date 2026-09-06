// Etapa 1 — Referências (aula 009) · Wave 10 · E5 (card [REACT-06]).
//
// Porte React da tela vanilla `studio/etapas/refs/view.{html,js}` — mesma tela, mesmo
// comportamento (refatoração pura). Dois painéis: buscar no Pinterest (marca validada, sugestão de
// termos, import por URL `[extensão]`) e escolher o que você gosta (grade de candidatas, multi-
// seleção, upload por drop/link, filtros por termo e por fonte). O upload manual (Explore do
// Midjourney) não tem painel próprio: o painel 02 inteiro é alvo de drop (`.panel.over`).
//
// O `<style>` de escopo `.rf-` vai como nó no JSX (desmonta com a tela — sem import global, recon
// §6.4). Guia via `<StepGuide>` da E2; polling via `poll`/`progressJob`; upload/drop via `useUpload`.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { StepGuide, progressJob, useProgress, useUpload, poll } from "../../../../frontend/src/ui";
import { useStudio } from "../../../../frontend/src/shell/plugin";
import { useStudioChange } from "../../../../frontend/src/shell/events";

interface Candidate {
  id: string;
  term: string;
  source?: string;
  thumb: string;
  file: string;
  alt?: string;
  selected?: boolean;
}
interface LogLine {
  time?: string;
  text?: string;
  ok?: boolean;
}
interface JobSrc {
  total?: number;
  meta?: number;
  log?: LogLine[];
}
interface Job {
  state?: string;
  total?: number;
  error?: string;
  last_job?: JobSrc;
  meta?: number;
  last?: { stage?: string; logged_in?: boolean };
}

const ESTILO = `
  .rf-prog{display:flex;flex-direction:column;gap:5px}
  #refsPick .panel-head{position:relative}
  #refsPick .rf-bring{position:absolute;right:0;top:calc(100% + 2px);opacity:0;transition:opacity .15s}
  #refsPick .panel-head:hover .rf-bring,#refsPick .rf-bring:focus-visible{opacity:1}
  .rf-brandsave{display:flex;align-items:center;gap:10px;margin-top:2px}
  .rf-filters{display:flex;flex-wrap:wrap;gap:14px 18px;align-items:flex-start;margin:2px 0 12px}
  .rf-filters:empty{display:none}
  .rf-fgroup{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center}
  .rf-flabel{font-size:.72rem;letter-spacing:.05em;text-transform:uppercase;opacity:.6;margin-right:2px}
  .rf-chk{display:inline-flex;align-items:center;gap:5px;font-size:.85rem;cursor:pointer;white-space:nowrap}
  .rf-chk input{margin:0}
  .rf-clear{align-self:center}
  .rf-import{display:flex;flex-direction:column;gap:6px;margin-top:12px}
`;

export default function RefsScreen() {
  const ctx = useStudio();
  const [cands, setCands] = useState<Candidate[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filterTerms, setFilterTerms] = useState<Set<string>>(new Set());
  const [filterSources, setFilterSources] = useState<Set<string>>(new Set());
  const [brand, setBrand] = useState("");
  const [brandSaved, setBrandSaved] = useState("");
  const [terms, setTerms] = useState("");
  const [maxPer, setMaxPer] = useState("30");
  const [maxPins, setMaxPins] = useState("30");
  const [headed, setHeaded] = useState(false);
  const [refsUrl, setRefsUrl] = useState("");
  const [loginChip, setLoginChip] = useState<{ text: string; kind: string }>({ text: "sessão: ?", kind: "mode" });
  const [loginBtn, setLoginBtn] = useState("Refazer login");
  const [scrapeOverride, setScrapeOverride] = useState<string | null>(null);
  const [barWidth, setBarWidth] = useState("0%");
  const [logLines, setLogLines] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [guideNonce, setGuideNonce] = useState(0);

  const [progHandle, progEl] = useProgress();
  const pollRef = useRef<ReturnType<typeof poll> | null>(null);
  const loginPollRef = useRef<ReturnType<typeof poll> | null>(null);
  const brandTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pickRef = useRef<HTMLElement>(null);

  const pid = ctx.pid();
  const refreshGuide = useCallback(() => setGuideNonce((n) => n + 1), []);

  // ---------- login do Pinterest ----------
  const setSession = useCallback((ok: boolean) => {
    setLoginChip({ text: ok ? "sessão ativa" : "sessão: não logada", kind: ok ? "ok" : "warn" });
    setLoginBtn(ok ? "Refazer login" : "Fazer login");
  }, []);

  const refreshLogin = useCallback(async () => {
    const s = (await ctx.api("/api/pinterest/login")) as { state?: string; ok?: boolean };
    if (s.state === "running") {
      setLoginChip({ text: "sessão: aguardando login", kind: "warn" });
      if (!loginPollRef.current) {
        loginPollRef.current = poll(async () => {
          const cur = (await ctx.api("/api/pinterest/login")) as { state?: string };
          if (cur.state === "running") return undefined;
          loginPollRef.current = null;
          void refreshLogin();
          return false;
        }, 3000);
      }
    } else if (s.state === "done") {
      setSession(!!s.ok);
    } else {
      setLoginChip({ text: "sessão: ?", kind: "mode" });
      setLoginBtn("Refazer login");
    }
  }, [ctx, setSession]);

  // ---------- scrape / job ----------
  const renderJob = useCallback((j: Job | null) => {
    const src: JobSrc | null = (j && (j.last_job || (j.meta !== undefined ? j : null))) || null;
    if (!src) {
      setScrapeOverride(null);
      setBarWidth("0%");
      setLogLines([]);
      return;
    }
    const total = src.total || 0;
    const meta = src.meta || 0;
    const txt = meta ? `${total}/${meta}` : total ? `${total} candidatas` : "";
    setScrapeOverride(txt || null);
    setBarWidth(meta ? `${Math.min(100, Math.round((total / meta) * 100))}%` : "0%");
    setLogLines((src.log || []).map((l) => `[${l.time || ""}] ${l.text || ""}`));
  }, []);

  const load = useCallback(
    async (keepSel = false) => {
      if (!ctx.pid()) {
        setCands([]);
        return;
      }
      const cs = (await ctx.api(`/api/projects/${ctx.pid()}/refs/candidates`)) as Candidate[];
      setCands(cs);
      if (!keepSel) setSelected(new Set(cs.filter((c) => c.selected).map((c) => c.id)));
      const termsSet = new Set(cs.map((c) => c.term));
      const sourcesSet = new Set(cs.map((c) => c.source || "pinterest"));
      setFilterTerms((prev) => new Set([...prev].filter((t) => termsSet.has(t))));
      setFilterSources((prev) => new Set([...prev].filter((s) => sourcesSet.has(s))));
    },
    [ctx],
  );

  const startPoll = useCallback(() => {
    if (pollRef.current) pollRef.current.stop();
    pollRef.current = poll(async () => {
      const j = (await ctx.api(`/api/projects/${ctx.pid()}/refs/job`)) as Job;
      renderJob(j);
      if (j.last && j.last.stage === "start") setSession(!!j.last.logged_in);
      if (j.state === "running") {
        if (j.total) void load(true);
        return undefined;
      }
      setBusy(false);
      if (j.state === "error") {
        setLogLines((ls) => [...ls, `ERRO: ${j.error || ""}`]);
        ctx.toast("Falhou: " + j.error);
      }
      await load();
      refreshGuide();
      pollRef.current = null;
      return false;
    }, 2000);
  }, [ctx, renderJob, setSession, load, refreshGuide]);

  // ---------- ciclo de vida ----------
  useEffect(() => {
    let vivo = true;
    setFilterTerms(new Set());
    setFilterSources(new Set());
    void (async () => {
      void refreshLogin();
      await load();
      if (ctx.pid()) {
        try {
          const b = (await ctx.api(`/api/projects/${ctx.pid()}/refs/validated-brand`)) as { brand?: string };
          if (vivo) setBrand(b.brand || "");
        } catch {
          /* projeto sem marca validada */
        }
        try {
          const j = (await ctx.api(`/api/projects/${ctx.pid()}/refs/job`)) as Job;
          if (!vivo) return;
          renderJob(j);
          if (j.state === "running" && !pollRef.current) {
            setBusy(true);
            startPoll();
          }
        } catch {
          /* sem job de coleta em andamento */
        }
      }
    })().catch(() => {
      /* efeito de carga defensivo: uma falha de rede não derruba a montagem da tela */
    });
    return () => {
      vivo = false;
      if (pollRef.current) pollRef.current.stop();
      if (loginPollRef.current) loginPollRef.current.stop();
      if (brandTimer.current) clearTimeout(brandTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  // ---------- sincronização com o chat `[extensão]` (Wave 11 · F03) ----------
  // O assistente age pelas tools `mcp__studio__*` e escreve nos MESMOS artefatos desta tela
  // (`refs_search` dispara o job, `refs_pick` grava a escolha). O `ChatDock` avisa pelo barramento
  // do shell e a tela reusa o que ela já tem: nada de segunda carga, nada de segundo poll.
  //
  // `load(true)` e não `load()`: `keepSel` preserva a marcação em curso do usuário, que ainda não
  // foi salva no disco (§10 Risco 5 do FDD). Reler o job em seguida é o passo 9 do fluxo principal
  // — o evento de `refs_search` sai quando o POST volta, não quando o scrape termina, então o que a
  // tela precisa mostrar é o progresso, e quem faz isso é o `startPoll()` que já existe.
  useStudioChange(
    "refs",
    () => {
      void (async () => {
        await load(true);
        if (!ctx.pid()) return;
        const j = (await ctx.api(`/api/projects/${ctx.pid()}/refs/job`)) as Job;
        renderJob(j);
        if (j.state === "running" && !pollRef.current) {
          setBusy(true);
          startPoll();
        }
      })().catch(() => {
        /* aviso do chat é best-effort: falha de rede aqui não pode derrubar a tela */
      });
    },
    { pid },
  );

  // ---------- upload / drop ----------
  const doUpload = useCallback(
    async (files: FileList) => {
      if (!files || !files.length) return;
      try {
        const r = (await ctx.apiUpload(`/api/projects/${ctx.pid()}/refs/import/upload`, files)) as { added: number };
        ctx.toast(`${r.added} referências adicionadas`);
        await load(true);
        refreshGuide();
      } catch (err) {
        ctx.toast((err as Error).message);
      }
    },
    [ctx, load, refreshGuide],
  );
  const dz = useUpload(doUpload);

  // ---------- ações do painel 01 ----------
  const onLogin = useCallback(async () => {
    await ctx.api("/api/pinterest/login", { method: "POST" });
    ctx.toast("Abrindo o Pinterest… faça login na janela");
    void refreshLogin();
  }, [ctx, refreshLogin]);

  const onSuggest = useCallback(async () => {
    const p = ctx.project() as { product?: string; vibe?: string } | null;
    const b = brand.trim();
    if (!p || (!p.product && !b)) {
      ctx.toast("Informe a marca validada ou o produto do projeto");
      return;
    }
    const q =
      `product=${encodeURIComponent(p.product || "")}&vibe=${encodeURIComponent(p.vibe || "")}` +
      `&brand=${encodeURIComponent(b)}&pid=${encodeURIComponent(ctx.pid() || "")}`;
    const arr = (await ctx.api(`/api/suggest-terms?${q}`)) as string[];
    setTerms(arr.join("\n"));
  }, [ctx, brand]);

  const onSaveBrand = useCallback(async () => {
    if (!ctx.pid()) {
      ctx.toast("Crie ou selecione um projeto");
      return;
    }
    const b = brand.trim();
    try {
      await ctx.api(`/api/projects/${ctx.pid()}/refs/validated-brand`, {
        method: "PUT",
        body: JSON.stringify({ brand: b }),
      });
      setBrandSaved(b ? "marca validada salva" : "marca validada limpa");
      if (brandTimer.current) clearTimeout(brandTimer.current);
      brandTimer.current = setTimeout(() => setBrandSaved(""), 3000);
      ctx.toast(b ? "Marca validada salva" : "Marca validada limpa");
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }, [ctx, brand]);

  const onSearch = useCallback(() => {
    const lista = terms
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!lista.length) {
      ctx.toast("Informe ao menos um termo");
      return;
    }
    setBusy(true);
    setLogLines([]);
    progressJob(progHandle, {
      title: "Buscar referências",
      subtitle: `${lista.length} termo(s) no Pinterest`,
      start: () =>
        ctx.api(`/api/projects/${ctx.pid()}/refs/search`, {
          method: "POST",
          body: JSON.stringify({ terms: lista, max_per_term: +maxPer, headless: !headed }),
        }),
      jobUrl: `/api/projects/${ctx.pid()}/refs/job`,
      done: async () => {
        renderJob((await ctx.api(`/api/projects/${ctx.pid()}/refs/job`)) as Job);
        await load();
        refreshGuide();
      },
    })
      .catch((err: unknown) => ctx.toast("Falhou: " + (err as Error).message))
      .finally(() => setBusy(false));
  }, [ctx, terms, maxPer, headed, progHandle, renderJob, load, refreshGuide]);

  const onImportUrl = useCallback(() => {
    const url = refsUrl.trim();
    if (!url) {
      ctx.toast("Cole a URL de um pin ou de um board do Pinterest");
      return;
    }
    setBusy(true);
    setLogLines([]);
    progressJob(progHandle, {
      title: "Importar por URL",
      subtitle: "[extensão] pin ou board do Pinterest",
      start: () =>
        ctx.api(`/api/projects/${ctx.pid()}/refs/import/url`, {
          method: "POST",
          body: JSON.stringify({ url, max_pins: +maxPins, headless: !headed }),
        }),
      jobUrl: `/api/projects/${ctx.pid()}/refs/job`,
      done: async () => {
        renderJob((await ctx.api(`/api/projects/${ctx.pid()}/refs/job`)) as Job);
        await load();
        refreshGuide();
      },
    })
      .catch((err: unknown) => ctx.toast("Falhou: " + (err as Error).message))
      .finally(() => setBusy(false));
  }, [ctx, refsUrl, maxPins, headed, progHandle, renderJob, load, refreshGuide]);

  // ---------- painel 02: seleção, filtros, salvar ----------
  const toggleCard = useCallback((id: string) => {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }, []);

  const openFile = useCallback(
    (c: Candidate) => {
      window.open(ctx.files(`refs/candidates/${c.file}`), "_blank");
    },
    [ctx],
  );

  const onSave = useCallback(async () => {
    try {
      const r = (await ctx.api(`/api/projects/${ctx.pid()}/refs/select`, {
        method: "POST",
        body: JSON.stringify({ ids: [...selected] }),
      })) as { selected: number };
      ctx.toast(`${r.selected} referências salvas em refs/brainstorming`);
      await load();
      refreshGuide();
    } catch (err) {
      ctx.toast((err as Error).message);
    }
  }, [ctx, selected, load, refreshGuide]);

  const toggleFilter = useCallback((kind: string, value: string, checked: boolean) => {
    const setter = kind === "term" ? setFilterTerms : setFilterSources;
    setter((prev) => {
      const n = new Set(prev);
      if (checked) n.add(value);
      else n.delete(value);
      return n;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setFilterTerms(new Set());
    setFilterSources(new Set());
  }, []);

  // ---------- derivados de render ----------
  const scrapeText = scrapeOverride ?? (cands.length ? `${cands.length} candidatas` : "—");
  const matchesFilters = useCallback(
    (c: Candidate) => {
      const okTerm = !filterTerms.size || filterTerms.has(c.term);
      const okSource = !filterSources.size || filterSources.has(c.source || "pinterest");
      return okTerm && okSource;
    },
    [filterTerms, filterSources],
  );
  const visiveis = useMemo(() => cands.filter(matchesFilters), [cands, matchesFilters]);

  const grupos = useMemo(() => {
    if (!cands.length) return { terms: [] as string[], sources: [] as string[] };
    const t = [...new Set(cands.map((c) => c.term))].sort();
    const s = [...new Set(cands.map((c) => c.source || "pinterest"))].sort();
    return { terms: t, sources: s };
  }, [cands]);
  const filtroAtivo = filterTerms.size || filterSources.size;

  const disabled = !pid || busy;

  return (
    <>
      <style>{ESTILO}</style>

      <header className="stephead">
        <span className="eyebrow">Etapa 1 · aula 009</span>
        <h2>Referências</h2>
        <p className="lede">
          Comece sem ideia nenhuma: pesquise uma marca já validada, role o Pinterest e marque só o que
          você gosta. As escolhidas viram referência para os prompts das próximas etapas.
        </p>
      </header>

      <section id="guide" className="guide">
        <StepGuide key={guideNonce} stepId="refs" pid={pid} onGuide={ctx.onGuide} />
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>
            <span className="pn">01</span>Buscar no Pinterest
          </h3>
          <div className="row">
            <span id="loginState" className={"chip " + loginChip.kind}>
              {loginChip.text}
            </span>
            <button id="btnLogin" className="ghost" onClick={onLogin}>
              {loginBtn}
            </button>
          </div>
        </div>
        <details className="lesson">
          <summary>O que a aula 009 manda fazer aqui</summary>
          <p>
            Comece por uma <b>marca já validada</b> ("Red Bull, que já tem anúncios validados") e só
            depois refine pela situação ("Red Bull snow ads"). Os termos pelo seu produto entram como
            complemento. A vibe ainda não precisa existir — ela é encontrada na etapa 2.
          </p>
        </details>
        <div className="grid2">
          <div className="col">
            <label className="field">
              <span className="eyebrow">marca validada para se inspirar</span>
              <input
                id="brand"
                className="lg"
                placeholder="ex.: Red Bull"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
              />
            </label>
            <div className="row rf-brandsave">
              <button
                id="btnSaveBrand"
                className="link"
                type="button"
                title="Guarda esta marca como a marca validada do projeto — vira a fonte das sugestões de termos"
                onClick={onSaveBrand}
              >
                Salvar marca validada
              </button>
              <span id="brandSaved" className="note">
                {brandSaved}
              </span>
            </div>
            <label className="field">
              <span className="eyebrow">termos de busca — um por linha, em inglês</span>
              <textarea
                id="terms"
                rows={6}
                placeholder={"Red Bull ads\nRed Bull snow ads\nenergy drink ad campaign"}
                value={terms}
                onChange={(e) => setTerms(e.target.value)}
              />
            </label>
            <div className="row opts wrap">
              <label className="inline">
                máx. por termo{" "}
                <input
                  id="maxPer"
                  type="number"
                  value={maxPer}
                  min={5}
                  max={100}
                  onChange={(e) => setMaxPer(e.target.value)}
                />
              </label>
              <label className="inline">
                <input id="headed" type="checkbox" checked={headed} onChange={(e) => setHeaded(e.target.checked)} /> ver
                o navegador
              </label>
              <button id="btnSuggest" className="link" onClick={onSuggest}>
                Sugerir termos a partir do projeto
              </button>
            </div>
            <div className="rf-import">
              <label className="field">
                <span className="eyebrow">ou traga um pin/board que você já tem, pela URL</span>
                <input
                  id="refsUrl"
                  placeholder="https://www.pinterest.com/usuario/campanhas-energetico/"
                  value={refsUrl}
                  onChange={(e) => setRefsUrl(e.target.value)}
                />
              </label>
              <div className="row opts wrap">
                <label className="inline">
                  máx. do board{" "}
                  <input
                    id="maxPins"
                    type="number"
                    value={maxPins}
                    min={1}
                    max={100}
                    onChange={(e) => setMaxPins(e.target.value)}
                  />
                </label>
                <button id="btnImportUrl" className="ghost" disabled={disabled} onClick={onImportUrl}>
                  Importar URL
                </button>
              </div>
              <span className="note">
                Extensão do Studio — a aula 009 busca por termos; importar um link pronto é atalho nosso.
                Roda com a sua sessão e contraria os termos do Pinterest: prefira uma conta secundária.
              </span>
            </div>
          </div>
          <div className="status">
            <button id="btnSearch" className="primary cta" disabled={disabled} onClick={onSearch}>
              Buscar e baixar
            </button>
            <div className="rf-prog">
              <div className="progress-lbl">
                <span>Último scrape</span>
                <span id="scrapeCount" className="mono">
                  {scrapeText}
                </span>
              </div>
              <div id="progress" className="progress">
                <div className="bar" style={{ width: barWidth }} />
              </div>
            </div>
            <div id="log" className="log mono">
              {logLines.join("\n")}
            </div>
            <span className="note">
              Roda em ritmo humano com a sua sessão. Contraria os termos do Pinterest — prefira uma conta
              secundária.
            </span>
          </div>
        </div>
      </section>

      <section
        className={"panel" + (dz.isOver ? " over" : "")}
        id="refsPick"
        ref={pickRef}
        // A classe `.over` é aplicada TAMBÉM de forma imperativa (não só pelo estado) para aparecer
        // no MESMO tick do `dragover` — o cenário C-REFS-22 lê `classList.contains('over')` de forma
        // síncrona logo após despachar o evento, antes de o React re-renderizar pelo `setState`.
        onDragOver={(e) => {
          dz.rootProps.onDragOver(e);
          pickRef.current?.classList.add("over");
        }}
        onDragLeave={(e) => {
          dz.rootProps.onDragLeave(e);
          pickRef.current?.classList.remove("over");
        }}
        onDrop={(e) => {
          dz.rootProps.onDrop(e);
          pickRef.current?.classList.remove("over");
        }}
      >
        <div className="panel-head">
          <h3>
            <span className="pn">02</span>Escolher o que você gosta
          </h3>
          <div className="row wrap">
            <span id="counts" className="chip mode">
              {/* nó de texto ÚNICO (template string): o vanilla setava `textContent` de uma vez;
                  em React, `{a} candidatas · {b}` criaria vários text nodes e o oráculo de
                  `textContent` (ADR-004) acusaria diferença. */}
              {`${cands.length} candidatas · ${selected.size} escolhidas`}
            </span>
            <button id="btnSave" className="primary" disabled={!pid} onClick={onSave}>
              Salvar seleção
            </button>
          </div>
          <button
            id="btnBring"
            className="link rf-bring"
            type="button"
            title="Imagens salvas à mão (Explore do Midjourney, print, download avulso) — ou arraste-as sobre este painel"
            onClick={dz.open}
          >
            trazer imagens
          </button>
        </div>
        <p className="fine">
          Marque o que <b>você</b> gosta e o que foge do clichê. Clique para marcar; a aula manda voltar
          no fim e desmarcar o que já não agrada.
        </p>
        <div id="refsFilters" className="rf-filters">
          {grupos.terms.length > 1 ? (
            <div className="rf-fgroup">
              <span className="rf-flabel">termos</span>
              {grupos.terms.map((t) => (
                <label className="rf-chk" key={t}>
                  <input
                    type="checkbox"
                    data-filter="term"
                    value={t}
                    checked={filterTerms.has(t)}
                    onChange={(e) => toggleFilter("term", t, e.target.checked)}
                  />{" "}
                  {t}
                </label>
              ))}
            </div>
          ) : null}
          {grupos.sources.length > 1 ? (
            <div className="rf-fgroup">
              <span className="rf-flabel">fontes</span>
              {grupos.sources.map((s) => (
                <label className="rf-chk" key={s}>
                  <input
                    type="checkbox"
                    data-filter="source"
                    value={s}
                    checked={filterSources.has(s)}
                    onChange={(e) => toggleFilter("source", s, e.target.checked)}
                  />{" "}
                  {s}
                </label>
              ))}
            </div>
          ) : null}
          {filtroAtivo ? (
            <button type="button" className="link rf-clear" onClick={clearFilters}>
              limpar filtros
            </button>
          ) : null}
        </div>
        <div id="gallery" className="gallery">
          {visiveis.length ? (
            visiveis.map((c) => (
              <div
                key={c.id}
                className={"card" + (selected.has(c.id) ? " sel" : "")}
                data-id={c.id}
                tabIndex={0}
                title={c.alt || ""}
                onClick={() => toggleCard(c.id)}
                onDoubleClick={() => openFile(c)}
                onKeyDown={(e) => {
                  if (e.key === " " || e.key === "Enter") {
                    e.preventDefault();
                    toggleCard(c.id);
                  }
                }}
              >
                <img loading="lazy" src={ctx.files(`refs/candidates/${c.thumb}`)} alt="" />
                <span className="src">{c.source || "pinterest"}</span>
                <span className="term">{c.term}</span>
              </div>
            ))
          ) : (
            <div className="empty">
              {pid ? (
                <>
                  Nenhuma candidata ainda — rode uma busca ou{" "}
                  <button type="button" className="link" data-bring onClick={dz.open}>
                    traga imagens
                  </button>
                  .
                </>
              ) : (
                "Crie ou selecione um projeto."
              )}
            </div>
          )}
        </div>
        <input {...dz.inputProps} id="refsUpload" accept="image/*" />
      </section>

      {progEl}
    </>
  );
}
