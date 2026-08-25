// Etapa 9 — Export (aula 014): formato por rede a partir do master; thumb e QA são [extensão].
Studio.register("export", (ctx) => {
  const { $, api, toast } = ctx;
  const LABELS = { "16x9": "16:9 · YouTube", "9x16": "9:16 · Reels e TikTok", "1x1": "1:1 · feed [extensão]" };
  const FORMATS = Object.keys(LABELS);
  const ASPECT = { "16:9": "16x9", "9:16": "9x16", "1:1": "1x1" };
  let st = null, job = null;

  const url = (p) => `/api/projects/${ctx.pid()}/export/${p}`;
  const chip = (el, text, cls) => { const e = $(el); e.textContent = text; e.className = "chip " + cls; };
  // Formato da rede-alvo do projeto (project.aspect_ratio, [extensão] — default 16:9).
  const alvo = () => ASPECT[(ctx.project() || {}).aspect_ratio] || "16x9";

  function renderChips() {
    chip("#expFfmpeg", st.ffmpeg ? "ffmpeg: pronto" : "ffmpeg: ausente (~/.local/bin)", st.ffmpeg ? "ok" : "warn");
    const m = st.master;
    chip("#expMaster", m.exists ? "master: pronto" : "master: aguardando a etapa 8", m.exists ? "ok" : "warn");
    const hf = st.higgsfield || {};
    chip("#expHf", !hf.installed ? "CLI: não instalado" : hf.logged_in ? "CLI: logado" : "CLI: sem login", hf.logged_in ? "ok" : "warn");
    $("#expMasterInfo").textContent = m.exists && m.width
      ? `edit/master.mp4 · ${m.width}x${m.height} · ${(m.duration || 0).toFixed(1)}s · ${Math.round(m.fps || 0)} fps · ${m.vcodec || "?"}${m.has_audio ? " + " + (m.acodec || "áudio") : " · sem áudio (a trilha da etapa 7 é obrigatória)"}`
      : m.exists ? "edit/master.mp4 encontrado (sem ffmpeg para medir)." : "Nenhum edit/master.mp4: conclua a etapa 8 (montagem no ritmo).";
  }

  function ready() { return st && st.ffmpeg && st.master.exists; }

  function renderFormats() {
    const running = st.job && st.job.state === "running";
    const alvoFmt = alvo();
    $("#expFormats").innerHTML = FORMATS.map((f) => {
      const o = st.outputs[f], prev = st.previews[f];
      const destino = f === alvoFmt ? Studio.ui.chip("formato da rede-alvo", "ok") : "";
      return `<div class="panel" data-fmt="${f}" style="align-self:start">
        <div class="panel-head"><h3>${Studio.ui.esc(LABELS[f])}</h3><span class="chip ${o ? "ok" : "mode"}">${o ? "gerado" : "pendente"}</span>${destino}</div>
        ${prev ? `<img loading="lazy" src="${ctx.files(prev)}" alt="preview do enquadramento ${f}" style="max-width:150px;max-height:200px;border-radius:8px">` : ""}
        <p class="fine mono">${o && o.width ? `${o.width}x${o.height} · ${(o.duration || 0).toFixed(1)}s · ${o.has_audio ? "com áudio" : "sem áudio"}` : "ainda não renderizado"}</p>
        <div class="row wrap">
          <button class="ghost prev" data-fmt="${f}" ${ready() && !running ? "" : "disabled"}>Preview do corte</button>
          <button class="render" data-fmt="${f}" ${ready() && !running ? "" : "disabled"}>Renderizar</button>
          ${o ? `<a class="fine mono" href="${ctx.files(o.file)}" target="_blank" rel="noopener">abrir</a>` : ""}
        </div>
      </div>`;
    }).join("");
    $("#btnRenderAll").disabled = !ready() || running;
    $("#btnThumb").disabled = !ready() || running;
    $("#btnQa").disabled = !ready() || running;
    $("#btnReframe").disabled = !ready() || running || !(st.higgsfield || {}).logged_in;
  }

  function renderJob() {
    const j = st.job || { state: "idle" };
    const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
    $("#expBar").style.width = (j.state === "running" ? pct : j.state === "done" ? 100 : 0) + "%";
    $("#expJobLog").textContent = j.state === "running" ? `renderizando ${j.done}/${j.total}…`
      : j.state === "error" ? "erro: " + j.error : j.state === "done" ? `concluído · ${j.added} arquivo(s)` : "";
    $("#expLog").textContent = (j.log || []).join("\n");
    if (j.state === "running" && !job) startPoll();
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

  function renderThumb() {
    const t = st.outputs.thumb;
    $("#expThumbInfo").textContent = t ? `export/thumb.jpg${t.t != null ? ` · t = ${t.t}s` : ""}` : "nenhuma thumb ainda";
    $("#expThumb").innerHTML = t ? `<div class="card" style="max-width:320px"><img loading="lazy" src="${ctx.files(t.file)}?v=${Date.now()}" alt="thumb"></div>` : "";
    const qa = st.outputs.qa_report, a = $("#expQaFile");
    if (qa) { a.textContent = "export/qa_report.md"; a.href = ctx.files(qa.file); } else { a.textContent = ""; a.removeAttribute("href"); }
  }

  function renderQa(r) {
    const e = (s) => Studio.ui.esc(s);
    const kind = (v) => (v === "OK" ? "ok" : "warn");
    $("#expQa").innerHTML = (r.blocking
      ? `<p class="fine"><strong>Bloqueio:</strong> algum arquivo está sem áudio. A trilha da etapa 7 é obrigatória — o resto do checklist é atenção, não impedimento.</p>`
      : "")
      + `<table><thead><tr><th>Arquivo</th><th>Resolução</th><th>Duração</th><th>Áudio</th><th>Veredito</th></tr></thead><tbody>`
      + r.items.map((i) => `<tr><td class="mono">${e(i.file)}</td><td>${i.width ? `${i.width}x${i.height}` : "—"}</td>`
        + `<td>${i.duration ? i.duration.toFixed(2) + "s" : "—"}</td><td>${i.has_audio === undefined ? "—" : i.has_audio ? "sim" : "não"}</td>`
        + `<td><span class="chip ${kind(i.verdict)}">${e(i.verdict)}</span></td></tr>`).join("")
      + `</tbody></table>`;
  }

  async function load() {
    if (!ctx.pid()) return;
    st = await api(url("status"));
    renderChips(); renderFormats(); renderJob(); renderThumb();
  }

  async function render(formats) {
    const existing = formats.filter((f) => st.outputs[f]);
    if (existing.length && !confirm(`Já existe arquivo para ${existing.join(", ")}. Renderizar de novo substitui.`)) return;
    try { st.job = await api(url("render"), { method: "POST", body: JSON.stringify({ formats }) }); renderFormats(); renderJob(); }
    catch (e) { toast(e.message); }
  }

  return {
    init() {
      $("#btnRenderAll").onclick = () => render(FORMATS);
      $("#expFormats").addEventListener("click", async (e) => {
        const b = e.target.closest("button"); if (!b) return;
        const fmt = b.dataset.fmt;
        if (b.classList.contains("render")) return render([fmt]);
        if (!b.classList.contains("prev")) return;
        b.disabled = true;
        try { const r = await api(url("preview"), { method: "POST", body: JSON.stringify({ format: fmt, t: +$("#expThumbT").value }) }); toast(`Preview de ${fmt} em ${r.t}s`); await load(); ctx.guide(); }
        catch (err) { toast(err.message); b.disabled = false; }
      });
      $("#btnThumb").onclick = async () => {
        try { const r = await api(url("thumb"), { method: "POST", body: JSON.stringify({ t: +$("#expThumbT").value }) }); toast(`Thumb em ${r.t}s (${r.width}x${r.height})`); await load(); ctx.guide(); }
        catch (e) { toast(e.message); }
      };
      $("#btnQa").onclick = async () => {
        try {
          const r = await api(url("qa"), { method: "POST" });
          renderQa(r); await load(); ctx.guide();
          toast(r.blocking ? "QA gerado · BLOQUEIO: arquivo sem áudio"
            : `QA gerado · ${r.items.filter((i) => i.verdict !== "OK").length} atenção(ões)`);
        } catch (e) { toast(e.message); }
      };
      $("#btnReframe").onclick = async () => {
        const aspect = $("#expAspect").value;
        const ok = await Studio.ui.confirmCost(
          () => api(url("reframe/cost"), { method: "POST", body: JSON.stringify({ aspect_ratio: aspect }) }),
          `Reenquadrar o master para ${aspect} pelo CLI (o arquivo do formato será substituído)`);
        if (!ok) return;
        try { st.job = await api(url("reframe"), { method: "POST", body: JSON.stringify({ aspect_ratio: aspect }) }); $("#expReframeInfo").textContent = `reframe ${aspect} em andamento`; renderFormats(); renderJob(); }
        catch (e) { toast(e.message); }
      };
      this.onProject();
    },
    async onProject() {
      $("#expQa").innerHTML = "";
      await load();
      Studio.ui.renderGuide("export");
    },
    destroy() { if (job) { job.stop(); job = null; } },
  };
});
