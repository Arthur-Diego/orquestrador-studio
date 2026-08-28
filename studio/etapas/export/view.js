// Etapa 8 — Export (aula 014): formato por rede a partir do master; o QA técnico é [extensão].
// Wave 4: a tela é o protótipo — card de formato com UM botão, preview no clique da caixa e o
// QA como grid de checks por critério. Thumb e reframe saíram da tela (as rotas continuam).
Studio.register("export", (ctx) => {
  const { $, api, toast } = ctx;
  // Cartão de formato do protótipo: proporção, destino da rede e o retângulo desenhado.
  const FMT = {
    "16x9": { ratio: "16:9", dest: "YouTube", w: 46, h: 26 },
    "9x16": { ratio: "9:16", dest: "Reels · TikTok", w: 15, h: 27 },
    "1x1": { ratio: "1:1", dest: "feed · opcional", w: 24, h: 24 },
  };
  const FORMATS = Object.keys(FMT);
  const ASPECT = { "16:9": "16x9", "9:16": "9x16", "1:1": "1x1" };
  //: O painel Thumb saiu da tela (o campo "tempo" com ele): o preview do corte usa sempre o
  //: mesmo instante — 3 s, ou o meio do vídeo quando o master é mais curto que isso.
  const PREVIEW_T = 3;
  let st = null, job = null;

  const esc = (s) => Studio.ui.esc(s);
  const url = (p) => `/api/projects/${ctx.pid()}/export/${p}`;
  // Formato da rede-alvo do projeto (project.aspect_ratio, [extensão] — default 16:9).
  const alvo = () => ASPECT[(ctx.project() || {}).aspect_ratio] || "16x9";

  // O protótipo não desenha chip de estado bom: eles só aparecem quando algo falta (regra 6).
  function chipFalha(sel, mostrar, texto) {
    const e = $(sel);
    e.textContent = texto;
    e.classList.toggle("hidden", !mostrar);
  }

  function renderChips() {
    chipFalha("#expFfmpeg", !st.ffmpeg, "ffmpeg: ausente (~/.local/bin)");
    chipFalha("#expMaster", !st.master.exists, "master: aguardando a etapa 7");
  }

  function ready() { return st && st.ffmpeg && st.master.exists; }

  // Medidas do master viram `title` do botão "Renderizar todos" (o protótipo não desenha a linha).
  function tituloMaster() {
    const m = st.master;
    if (!m.exists) return "conclua a etapa 7 para gerar edit/master.mp4";
    if (!m.width) return "edit/master.mp4 encontrado (sem ffmpeg para medir)";
    return `edit/master.mp4 · ${m.width}x${m.height} · ${(m.duration || 0).toFixed(1)}s`
      + `${m.has_audio ? "" : " · sem áudio (a trilha da etapa 6 é obrigatória)"}`;
  }

  function renderFormats() {
    const running = st.job && st.job.state === "running";
    const alvoFmt = alvo();
    $("#expFormats").innerHTML = FORMATS.map((f) => {
      const o = st.outputs[f], prev = st.previews[f], m = FMT[f];
      const off = ready() && !running ? "" : "disabled";
      const medidas = o && o.width ? ` · ${o.width}x${o.height} · ${(o.duration || 0).toFixed(1)}s` : "";
      const caixa = prev
        ? `<img loading="lazy" src="${ctx.files(prev)}?v=${Date.now()}" alt="preview do corte central em ${m.ratio}">`
        : `<i class="${o ? "on" : ""}" style="width:${m.w}px;height:${m.h}px"></i>`;
      return `<div class="fmt-card${o ? " on" : ""}" data-fmt="${f}">
        <div class="top">
          <span class="ratio"${f === alvoFmt ? ' title="formato da rede-alvo do projeto"' : ""}>${m.ratio}</span>
          <span class="dest">${esc(m.dest)}</span>
          <span class="chip sm ${o ? "ok" : "todo"}">${o ? "renderizado" : "a renderizar"}</span>
        </div>
        <div class="box ex-box" data-fmt="${f}" title="conferir o corte central">${caixa}</div>
        ${o
          ? `<button class="ghost open" data-fmt="${f}" title="export/${f}.mp4${medidas}">Ver arquivo</button>`
          : `<button class="primary render" data-fmt="${f}" ${off}>Renderizar</button>`}
      </div>`;
    }).join("");
    const btn = $("#btnRenderAll");
    btn.disabled = !ready() || running;
    btn.title = tituloMaster();
    $("#btnQa").disabled = !ready() || running;
  }

  function renderJob() {
    const j = st.job || { state: "idle" };
    const rodando = j.state === "running";
    const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
    // Barra e log só existem enquanto o render acontece (ou quando ele falha).
    $("#expProgress").classList.toggle("hidden", !rodando);
    $("#expBar").style.width = (rodando ? pct : 0) + "%";
    $("#expJobLog").textContent = rodando ? `renderizando ${j.done}/${j.total}…`
      : j.state === "error" ? "erro: " + j.error : "";
    const erro = j.state === "error";
    $("#expLog").textContent = erro ? (j.log || []).join("\n") : "";
    $("#expLog").classList.toggle("hidden", !erro);
    if (rodando && !job) startPoll();
  }

  function startPoll() {
    job = Studio.ui.poll(async () => {
      if (!ctx.pid()) return false;
      st.job = await api(url("job"));
      renderJob();
      if (st.job.state === "running") return;
      job = null;
      await load(); ctx.guide();
      return false;
    }, 3000);
  }

  // Grid de checks POR CRITÉRIO (duração, resolução, áudio, formatos que faltam) — é o que o
  // protótipo desenha; o relatório por arquivo continua em `export/qa_report.md`.
  function renderQa(checks) {
    $("#expQa").innerHTML = (checks || []).length
      ? `<div class="checks qa">${checks.map((c) => {
        const kind = c.kind === "ok" ? "ok" : c.kind === "fail" ? "fail" : "warn";
        const marca = kind === "ok" ? "✓" : kind === "fail" ? "✕" : "!";
        return `<div class="it ${kind}"><span class="mark">${marca}</span><span class="lbl">${esc(c.text)}</span></div>`;
      }).join("")}</div>`
      : "";
  }

  async function load() {
    if (!ctx.pid()) return;
    st = await api(url("status"));
    renderChips(); renderFormats(); renderJob();
    renderQa((st.outputs.qa_report || {}).checks);
  }

  async function render(formats) {
    const existing = formats.filter((f) => st.outputs[f]);
    if (existing.length && !confirm(`Já existe arquivo para ${existing.join(", ")}. Renderizar de novo substitui.`)) return;
    // Render por formato é um JOB (ffmpeg): modal com o `log` REAL progredindo (fonte única).
    Studio.ui.progressJob({
      title: formats.length > 1 ? "Renderizar todos os formatos" : `Renderizar ${FMT[formats[0]].ratio}`,
      subtitle: "Export por rede (ffmpeg)",
      start: async () => { st.job = await api(url("render"), { method: "POST", body: JSON.stringify({ formats }) }); renderFormats(); },
      jobUrl: url("job"),
      done: async () => { await load(); ctx.guide(); },
    }).catch((e) => toast(e.message));
  }

  return {
    init() {
      $("#btnRenderAll").onclick = () => render(FORMATS);
      $("#expFormats").addEventListener("click", async (e) => {
        const b = e.target.closest("button");
        if (b && b.classList.contains("render")) return render([b.dataset.fmt]);
        if (b && b.classList.contains("open")) return window.open(ctx.files(st.outputs[b.dataset.fmt].file), "_blank", "noopener");
        // "Confira o enquadramento antes de renderizar": a caixa da proporção é o preview.
        const box = e.target.closest(".ex-box");
        if (!box || !ready()) return;
        const d = st.master.duration || 0;
        const t = d && d < PREVIEW_T ? +(d / 2).toFixed(2) : PREVIEW_T;
        try { await api(url("preview"), { method: "POST", body: JSON.stringify({ format: box.dataset.fmt, t }) }); await load(); ctx.guide(); }
        catch (err) { toast(err.message); }
      });
      $("#btnQa").onclick = async () => {
        try {
          const r = await api(url("qa"), { method: "POST" });
          renderQa(r.checks); await load(); ctx.guide();
          toast(r.blocking ? "QA gerado · BLOQUEIO: arquivo sem áudio"
            : `QA gerado · ${(r.checks || []).filter((c) => c.kind !== "ok").length} atenção(ões)`);
        } catch (e) { toast(e.message); }
      };
      this.onProject();
    },
    async onProject() {
      await load();
      Studio.ui.renderGuide("export");
    },
    destroy() { if (job) { job.stop(); job = null; } },
  };
});
