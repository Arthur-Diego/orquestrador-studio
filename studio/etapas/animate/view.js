// Etapa 6 — Animação (aula 012): prompt de movimento por take, start/end frame gravado,
// importar da UI da Higgsfield, like no usável. Componentes compartilhados: Studio.ui.
Studio.register("animate", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const EMPTY = { shots: [], ready: 0, total: 0, model_order: [], mode_tips: {}, last_frames: [] };
  let plan = { ...EMPTY }, cands = [], picked = null, jobShot = null, job = null, loggedIn = false;

  const esc = (s) => ui.esc(s);
  const key = (s) => `${s.scene}/${s.shot}`;
  const shotOf = (k) => plan.shots.find((s) => key(s) === k);
  const panelOf = (k) => document.querySelector(`section.panel[data-k="${CSS.escape(k)}"]`);

  async function hfStatus() {
    const s = await ui.hfChip($("#anHfState"));
    loggedIn = !!(s && s.logged_in);
    document.querySelectorAll("button.an-gen").forEach((b) => { b.disabled = !loggedIn; });
  }

  async function loadPlan() {
    if (!ctx.pid()) { plan = { ...EMPTY }; return render(); }
    try { plan = await api(`/api/projects/${ctx.pid()}/animate/shots`); }
    catch (err) { $("#anShots").innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
    render();
  }

  async function loadCandidates() {
    if (!ctx.pid()) { cands = []; return renderGallery(); }
    cands = await api(`/api/projects/${ctx.pid()}/animate/candidates`);
    renderGallery();
  }

  function takeRow(s, t) {
    const liked = t.liked === true ? " sel" : "";
    return `<div class="row wrap${liked}" data-take="${esc(t.id)}">
      ${ui.chip(t.id)}
      <a href="${ctx.files(t.file)}" target="_blank" class="mono fine">${esc(t.file)}</a>
      ${ui.chip(`${t.model || ""} · ${t.duration || 5}s${t.start_end ? " · start/end" : ""}`)}
      <button class="ghost an-like" data-k="${esc(key(s))}" data-take="${esc(t.id)}" data-liked="true">${t.liked === true ? "★ usável" : "like"}</button>
      <button class="ghost an-like" data-k="${esc(key(s))}" data-take="${esc(t.id)}" data-liked="false">${t.liked === false ? "✕ rejeitado" : "rejeitar"}</button>
    </div>`;
  }

  /** Opções de end frame: o próximo shot da cena (padrão da aula) e os últimos frames da etapa 8. */
  function endOptions(s) {
    const atual = (s.start_end || {}).end || "";
    const auto = atual && atual === s.next_image;
    const opts = [`<option value=""${!atual || auto ? " selected" : ""}${s.next_image ? "" : " disabled"}>`
      + (s.next_image ? `próximo shot da cena (${esc(s.next_in_scene)})` : "sem próximo shot na cena")
      + `</option>`];
    const extras = (plan.last_frames || []).slice();
    if (atual && !auto && !extras.includes(atual)) extras.push(atual);
    extras.forEach((f) => {
      opts.push(`<option value="${esc(f)}"${f === atual ? " selected" : ""}>${esc(f.split("/").pop())}</option>`);
    });
    return opts.join("");
  }

  function tipsHtml(mode) {
    const tips = (plan.mode_tips || {})[mode] || [];
    return tips.map((t) => `<li>${esc(t)}</li>`).join("");
  }

  function shotPanel(s) {
    const modes = [["simple", "simples"], ["elaborate", "elaborado (câmera + ação)"], ["start_end", "start/end frame"]];
    const chips = [
      s.ready ? ui.chip("pronto", "ok") : ui.chip("sem take escolhido"),
      s.failures ? ui.chip(`${s.failures} falha(s)`, "warn") : "",
      s.suggested_model && s.failures >= 3 ? ui.chip(`Tente ${s.suggested_model}`, "warn") : "",
      s.adapt_idea ? ui.chip("adapte a ideia: novo frame na etapa 5 ou corte para preto", "warn") : "",
      s.suggest_fallback_black && !s.adapt_idea ? ui.chip("sugestão: corte para preto", "warn") : "",
      s.fallback_black ? ui.chip("corte para preto", "warn") : "",
      s.orphan ? ui.chip("fora do storyboard", "warn") : "",
    ].join("");
    const se = s.mode === "start_end";
    const aspects = (plan.aspect_ratios || []).map((a) =>
      `<option value="${esc(a)}"${s.aspect_ratio === a ? " selected" : ""}>${esc(a)}</option>`).join("");
    const cliModes = (plan.cli_modes || []).map((m) =>
      `<option value="${esc(m)}"${s.cli_mode === m ? " selected" : ""}>${esc(m)}</option>`).join("");
    return `<section class="panel" data-k="${esc(key(s))}">
      <div class="panel-head">
        <h3>${esc(s.scene)} · ${esc(s.shot)}</h3>
        <div class="row wrap">${chips}</div>
      </div>
      <div class="row wrap">
        ${s.image ? `<img src="${ctx.files(s.image)}" alt="" style="width:180px;border-radius:8px">` : ui.chip("frame ausente", "warn")}
        <div class="col" style="flex:1">
          <div class="row wrap">
            <select class="an-mode" style="min-width:210px">${modes.map(([v, l]) => `<option value="${v}"${s.mode === v ? " selected" : ""}>${l}</option>`).join("")}</select>
            <input class="an-camera" placeholder="câmera (ex.: Dramatic dolly-in)">
            <input class="an-action" placeholder="ação (ex.: walking through the blizzard)">
            <label class="inline"><input type="checkbox" class="an-slow"> mudança lenta (10 s)</label>
            <button class="ghost an-suggest">Sugerir prompt</button>
          </div>
          <div class="row wrap an-endrow"${se ? "" : ` hidden style="display:none"`}>
            <label class="inline">end frame <select class="an-end" style="min-width:240px">${endOptions(s)}</select></label>
            <span class="fine">start = o frame deste shot; end = o frame de destino da transição (aula 012).</span>
          </div>
          <textarea class="an-prompt" rows="3" placeholder="prompt do movimento, em inglês">${esc(s.prompt)}</textarea>
          <span class="fine an-example"></span>
          <ul class="fine an-tips">${tipsHtml(s.mode)}</ul>
          <div class="row wrap">
            <select class="an-duration" style="min-width:90px">${[5, 10].map((d) => `<option value="${d}"${s.duration === d ? " selected" : ""}>${d} s</option>`).join("")}</select>
            <button class="an-save">Salvar</button>
            <label class="inline"><input type="checkbox" class="an-black"${s.fallback_black ? " checked" : ""}> corte para preto</label>
            <button class="an-assign" ${picked ? "" : "disabled"}>Atribuir selecionado</button>
            <select class="an-model" style="min-width:150px" title="modelo usado na geração pelo CLI">${(plan.model_order || []).map((m) => `<option value="${esc(m)}"${m === (s.suggested_model || "") ? " selected" : ""}>${esc(m)}</option>`).join("")}</select>
            <label class="inline">takes <input type="number" class="an-count" value="2" min="1" max="4"></label>
            <button class="primary an-gen" ${loggedIn ? "" : "disabled"}>Gerar via CLI (gasta créditos)</button>
          </div>
          <details class="fine">
            <summary>Avançado <code>[extensão]</code> — a aula 012 não fixa proporção nem modo do CLI</summary>
            <div class="row wrap">
              <label class="inline">proporção <select class="an-aspect"><option value="">projeto (${esc(plan.aspect_ratio || "16:9")})</option>${aspects}</select></label>
              <label class="inline">modo do CLI <select class="an-climode"><option value="">padrão (${esc(plan.cli_mode || "pro")})</option>${cliModes}</select></label>
            </div>
          </details>
          <p class="fine">Na Higgsfield: Image to Video, start frame = este shot${s.next_in_scene ? `, end frame = ${esc(s.next_in_scene)} no modo start/end` : ""}, <strong>áudio do modelo OFF</strong>, gere 2, like no usável, download.</p>
          <div class="col an-takes">${(s.takes || []).map((t) => takeRow(s, t)).join("") || `<span class="fine">nenhum take ainda</span>`}</div>
        </div>
      </div>
    </section>`;
  }

  function render() {
    $("#anReady").textContent = `${plan.ready}/${plan.total} shots prontos`;
    $("#anWarnings").textContent = (plan.warnings || []).join(" · ");
    $("#anModelNote").textContent = plan.model_note || "";
    if (plan.parallel_hint) $("#anParallel").textContent = plan.parallel_hint;
    $("#anShots").innerHTML = plan.shots.length
      ? plan.shots.map(shotPanel).join("")
      : `<div class="empty">Nenhum shot — a etapa 5 precisa produzir <code>shots/storyboard.json</code> primeiro.</div>`;
    hfStatus();
  }

  function renderGallery() {
    $("#anCandCount").textContent = `${cands.length} vídeos`;
    $("#anGallery").innerHTML = cands.length ? cands.map((c) => `
      <div class="card ${picked === c.id ? "sel" : ""}" data-id="${esc(c.id)}" tabindex="0" title="${esc(c.prompt || c.name || "")}">
        ${c.thumb ? `<img loading="lazy" src="${ctx.files(`animate/candidates/${c.thumb}`)}" alt="">` : ""}
        <span class="src">${esc(c.source)}</span>
        <span class="term">${esc(c.model || c.name || "")} · ${Math.round(c.duration || 0)}s</span>
      </div>`).join("") : `<div class="empty">Nenhum vídeo ainda — gere na UI da Higgsfield e importe.</div>`;
    document.querySelectorAll("button.an-assign").forEach((b) => { b.disabled = !picked; });
  }

  function startPoll() {
    if (job) job.stop();
    job = ui.poll(async () => {
      const j = await api(`/api/projects/${ctx.pid()}/animate/job`);
      const panel = jobShot && panelOf(jobShot);
      const el = panel && panel.querySelector(".an-takes");
      if (el && j.state === "running") el.innerHTML = `<span class="fine mono">gerando ${j.done}/${j.total} · ${j.added} takes…</span>`;
      if (j.state === "running") return;
      toast(j.state === "error" ? `erro: ${j.error}` : `job concluído · ${j.added} take(s)`);
      if ((j.log || []).length) console.log("[animate]", j.log.join("\n"));
      jobShot = null;
      await loadCandidates(); await loadPlan(); ctx.guide();
      return false;
    }, 3000);
  }

  function fields(el) {
    const p = el.closest("section.panel");
    const end = p.querySelector(".an-end");
    return {
      k: p.dataset.k, panel: p,
      mode: p.querySelector(".an-mode").value,
      camera: p.querySelector(".an-camera").value,
      action: p.querySelector(".an-action").value,
      slow: p.querySelector(".an-slow").checked,
      prompt: p.querySelector(".an-prompt").value,
      duration: +p.querySelector(".an-duration").value,
      model: p.querySelector(".an-model").value,
      count: +p.querySelector(".an-count").value,
      black: p.querySelector(".an-black").checked,
      end: end ? end.value : "",
      aspect: p.querySelector(".an-aspect").value,
      cliMode: p.querySelector(".an-climode").value,
    };
  }

  async function onClick(e) {
    const btn = e.target.closest("button"); if (!btn) return;
    const f = fields(btn), s = shotOf(f.k); if (!s) return;
    const base = `/api/projects/${ctx.pid()}/animate`;
    try {
      if (btn.classList.contains("an-suggest")) {
        const q = new URLSearchParams({ scene: s.scene, shot: s.shot, mode: f.mode, camera: f.camera, action: f.action, slow: f.slow });
        const r = await api(`${base}/prompt?${q}`);
        f.panel.querySelector(".an-prompt").value = r.prompt;
        f.panel.querySelector(".an-duration").value = r.duration;
        f.panel.querySelector(".an-example").textContent = `Exemplo da aula: ${r.example_pt}`;
        f.panel.querySelector(".an-tips").innerHTML = (r.tips || []).map((t) => `<li>${esc(t)}</li>`).join("");
      } else if (btn.classList.contains("an-save")) {
        const body = { prompt: f.prompt, mode: f.mode, duration: f.duration, fallback_black: f.black,
                       aspect_ratio: f.aspect || null, cli_mode: f.cliMode || null };
        // start/end sem escolha manual = par automático no backend (este frame → próximo da cena).
        if (f.mode === "start_end" && f.end) body.start_end = { end: f.end };
        await api(`${base}/shots/${s.scene}/${s.shot}`, { method: "PUT", body: JSON.stringify(body) });
        toast("Shot salvo"); await loadPlan(); ctx.guide();
      } else if (btn.classList.contains("an-assign")) {
        if (!picked) return toast("Selecione um vídeo na galeria");
        await api(`${base}/shots/${s.scene}/${s.shot}/takes`, { method: "POST", body: JSON.stringify({ candidate_id: picked, model: f.model, prompt: f.prompt }) });
        picked = null; toast("Take atribuído"); await loadCandidates(); await loadPlan(); ctx.guide();
      } else if (btn.classList.contains("an-like")) {
        const liked = btn.dataset.liked === "true";
        await api(`${base}/shots/${s.scene}/${s.shot}/takes/${btn.dataset.take}/like`, { method: "POST", body: JSON.stringify({ liked }) });
        await loadPlan(); ctx.guide();
      } else if (btn.classList.contains("an-gen")) {
        const ok = await ui.confirmCost(
          () => api(`${base}/cost`, { method: "POST", body: JSON.stringify({ scene: s.scene, shot: s.shot, model: f.model, count: f.count }) }),
          `Gerar ${f.count} take(s) de ${f.k} com ${f.model}`);
        if (!ok) return;
        await api(`${base}/generate`, { method: "POST", body: JSON.stringify({ scene: s.scene, shot: s.shot, model: f.model, count: f.count, prompt: f.prompt, duration: f.duration }) });
        jobShot = f.k; startPoll();
      }
    } catch (err) { toast(err.message); }
  }

  /** Trocar o modo revela o end frame e as dicas daquele modo — sem ida ao servidor. */
  function onModeChange(e) {
    const sel = e.target.closest(".an-mode"); if (!sel) return;
    const p = sel.closest("section.panel");
    const endrow = p.querySelector(".an-endrow"), se = sel.value === "start_end";
    endrow.hidden = !se;
    endrow.style.display = se ? "" : "none";   // `.row {display:flex}` vence o atributo `hidden`
    p.querySelector(".an-tips").innerHTML = tipsHtml(sel.value);
  }

  return {
    init() {
      $("#anReload").onclick = async () => { await loadPlan(); await loadCandidates(); ctx.guide(); };
      $("#anShots").addEventListener("click", onClick);
      $("#anShots").addEventListener("change", onModeChange);
      ui.drop($("#anDrop"), async (files) => {
        try {
          const r = await ui.upload(`/api/projects/${ctx.pid()}/animate/import/upload`, files);
          toast(`${r.added} vídeos importados`); await loadCandidates(); ctx.guide();
        } catch (err) { toast(err.message); }
      });
      $("#anBtnDownloads").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/animate/import/downloads`, { method: "POST", body: JSON.stringify({ since_minutes: +$("#anDlMinutes").value }) });
          toast(`${r.added} novos de ${r.scanned} vídeos recentes`); await loadCandidates(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#anBtnHistory").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/animate/import/history`, { method: "POST", body: JSON.stringify({ size: 50 }) });
          toast(`${r.added} vídeos de ${r.jobs} jobs`); await loadCandidates(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#anGallery").addEventListener("click", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        picked = picked === card.dataset.id ? null : card.dataset.id; renderGallery();
      });
      $("#anGallery").addEventListener("dblclick", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = cands.find((x) => x.id === card.dataset.id);
        window.open(ctx.files(`animate/candidates/${c.file}`), "_blank");
      });
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      picked = null; jobShot = null;
      await loadCandidates(); await loadPlan();
      const d = await api("/api/animate/downloads-folder");
      $("#anDlFolder").textContent = d.folder + (d.exists ? "" : " (não encontrada)");
      ui.renderGuide("animate");
    },
    destroy() { if (job) { job.stop(); job = null; } },
  };
});
