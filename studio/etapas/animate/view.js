// Etapa 6 — Animação (aula 012): prompt de movimento por take, importar da UI, like no usável.
Studio.register("animate", (ctx) => {
  const { $, api, toast } = ctx;
  let plan = { shots: [], ready: 0, total: 0, model_order: [] }, cands = [], picked = null, jobShot = null;

  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  const key = (s) => `${s.scene}/${s.shot}`;
  const shotOf = (k) => plan.shots.find(s => key(s) === k);

  async function hfStatus() {
    const s = await api("/api/higgsfield/status"), el = $("#anHfState");
    if (!s.installed) { el.textContent = "CLI: não instalado"; el.className = "chip warn"; }
    else if (!s.logged_in) { el.textContent = "CLI: sem login (higgsfield auth login)"; el.className = "chip warn"; }
    else { el.textContent = `CLI: ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`; el.className = "chip ok"; }
    document.querySelectorAll("button.an-gen").forEach(b => { b.disabled = !s.logged_in; });
  }

  async function loadPlan() {
    if (!ctx.pid()) { plan = { shots: [], ready: 0, total: 0, model_order: [] }; return render(); }
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
      <span class="chip mode">${esc(t.id)}</span>
      <a href="${ctx.files(t.file)}" target="_blank" class="mono fine">${esc(t.file)}</a>
      <span class="chip">${esc(t.model || "")} · ${t.duration || 5}s</span>
      <button class="ghost an-like" data-k="${key(s)}" data-take="${esc(t.id)}" data-liked="true">${t.liked === true ? "★ usável" : "like"}</button>
      <button class="ghost an-like" data-k="${key(s)}" data-take="${esc(t.id)}" data-liked="false">${t.liked === false ? "✕ rejeitado" : "rejeitar"}</button>
    </div>`;
  }

  function shotPanel(s) {
    const modes = [["simple", "simples"], ["elaborate", "elaborado (câmera + ação)"], ["start_end", "start/end frame"]];
    const chips = [
      s.ready ? `<span class="chip ok">pronto</span>` : `<span class="chip mode">sem take escolhido</span>`,
      s.failures ? `<span class="chip warn">${s.failures} falha(s)</span>` : "",
      s.suggested_model && s.failures >= 3 ? `<span class="chip warn">Tente ${esc(s.suggested_model)}</span>` : "",
      s.suggest_fallback_black ? `<span class="chip warn">sugestão: corte para preto</span>` : "",
      s.fallback_black ? `<span class="chip warn">corte para preto</span>` : "",
      s.orphan ? `<span class="chip warn">fora do storyboard</span>` : "",
    ].join("");
    return `<section class="panel" data-k="${key(s)}">
      <div class="panel-head">
        <h3>${esc(s.scene)} · ${esc(s.shot)}</h3>
        <div class="row wrap">${chips}</div>
      </div>
      <div class="row wrap">
        ${s.image ? `<img src="${ctx.files(s.image)}" alt="" style="width:180px;border-radius:8px">` : `<span class="chip warn">frame ausente</span>`}
        <div class="col" style="flex:1">
          <div class="row wrap">
            <select class="an-mode" style="min-width:210px">${modes.map(([v, l]) => `<option value="${v}"${s.mode === v ? " selected" : ""}${v === "start_end" && !s.next_in_scene && !s.start_end ? " disabled" : ""}>${l}</option>`).join("")}</select>
            <input class="an-camera" placeholder="câmera (ex.: Dramatic dolly-in)">
            <input class="an-action" placeholder="ação (ex.: walking through the blizzard)">
            <label class="inline"><input type="checkbox" class="an-slow"> mudança lenta (10 s)</label>
            <button class="ghost an-suggest">Sugerir prompt</button>
          </div>
          <textarea class="an-prompt" rows="3" placeholder="prompt do movimento, em inglês">${esc(s.prompt)}</textarea>
          <span class="fine an-example"></span>
          <div class="row wrap">
            <select class="an-duration" style="min-width:90px">${[5, 10].map(d => `<option value="${d}"${s.duration === d ? " selected" : ""}>${d} s</option>`).join("")}</select>
            <button class="an-save">Salvar</button>
            <label class="inline"><input type="checkbox" class="an-black"${s.fallback_black ? " checked" : ""}> corte para preto</label>
            <button class="an-assign" ${picked ? "" : "disabled"}>Atribuir selecionado</button>
            <select class="an-model" style="min-width:150px" title="modelo usado na geração pelo CLI">${(plan.model_order || []).map(m => `<option value="${m}"${m === (s.suggested_model || "") ? " selected" : ""}>${m}</option>`).join("")}</select>
            <label class="inline">takes <input type="number" class="an-count" value="2" min="1" max="4"></label>
            <button class="primary an-gen" disabled>Gerar via CLI (gasta créditos)</button>
          </div>
          <p class="fine">Na Higgsfield: Image to Video, start frame = este shot${s.next_in_scene ? `, end frame = ${esc(s.next_in_scene)} no modo start/end` : ""}, <strong>áudio do modelo OFF</strong>, gere 2, like no usável, download.</p>
          <div class="col an-takes">${(s.takes || []).map(t => takeRow(s, t)).join("") || `<span class="fine">nenhum take ainda</span>`}</div>
        </div>
      </div>
    </section>`;
  }

  function render() {
    $("#anReady").textContent = `${plan.ready}/${plan.total} shots prontos`;
    $("#anWarnings").textContent = (plan.warnings || []).join(" · ");
    $("#anShots").innerHTML = plan.shots.length
      ? plan.shots.map(shotPanel).join("")
      : `<div class="empty">Nenhum shot — a etapa 5 precisa produzir <code>shots/storyboard.json</code> primeiro.</div>`;
    hfStatus();
  }

  function renderGallery() {
    $("#anCandCount").textContent = `${cands.length} vídeos`;
    $("#anGallery").innerHTML = cands.length ? cands.map(c => `
      <div class="card ${picked === c.id ? "sel" : ""}" data-id="${esc(c.id)}" tabindex="0" title="${esc(c.prompt || c.name || "")}">
        ${c.thumb ? `<img loading="lazy" src="${ctx.files(`animate/candidates/${c.thumb}`)}" alt="">` : ""}
        <span class="src">${esc(c.source)}</span>
        <span class="term">${esc(c.model || c.name || "")} · ${Math.round(c.duration || 0)}s</span>
      </div>`).join("") : `<div class="empty">Nenhum vídeo ainda — gere na UI da Higgsfield e importe.</div>`;
    document.querySelectorAll("button.an-assign").forEach(b => { b.disabled = !picked; });
  }

  async function uploadFiles(files) {
    if (!files.length) return;
    const fd = new FormData(); [...files].forEach(f => fd.append("files", f));
    const r = await fetch(`/api/projects/${ctx.pid()}/animate/import/upload`, { method: "POST", body: fd });
    if (!r.ok) return toast((await r.json().catch(() => ({}))).detail || r.statusText);
    toast(`${(await r.json()).added} vídeos importados`); loadCandidates();
  }

  async function pollJob() {
    const j = await api(`/api/projects/${ctx.pid()}/animate/job`);
    const el = document.querySelector(`section.panel[data-k="${jobShot}"] .an-takes`);
    if (el && j.state === "running") el.innerHTML = `<span class="fine mono">gerando ${j.done}/${j.total} · ${j.added} takes…</span>`;
    if (j.state === "running") return setTimeout(pollJob, 3000);
    toast(j.state === "error" ? `erro: ${j.error}` : `job concluído · ${j.added} take(s)`);
    if ((j.log || []).length) console.log("[animate]", j.log.join("\n"));
    jobShot = null; await loadCandidates(); loadPlan();
  }

  function fields(el) {
    const p = el.closest("section.panel");
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
    };
  }

  return {
    init() {
      $("#anReload").onclick = () => { loadPlan(); loadCandidates(); };
      $("#anShots").addEventListener("click", async (e) => {
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
          } else if (btn.classList.contains("an-save")) {
            await api(`${base}/shots/${s.scene}/${s.shot}`, { method: "PUT", body: JSON.stringify({ prompt: f.prompt, mode: f.mode, duration: f.duration, fallback_black: f.black }) });
            toast("Shot salvo"); loadPlan();
          } else if (btn.classList.contains("an-assign")) {
            if (!picked) return toast("Selecione um vídeo na galeria");
            await api(`${base}/shots/${s.scene}/${s.shot}/takes`, { method: "POST", body: JSON.stringify({ candidate_id: picked, model: f.model, prompt: f.prompt }) });
            picked = null; toast("Take atribuído"); await loadCandidates(); loadPlan();
          } else if (btn.classList.contains("an-like")) {
            const liked = btn.dataset.liked === "true";
            await api(`${base}/shots/${s.scene}/${s.shot}/takes/${btn.dataset.take}/like`, { method: "POST", body: JSON.stringify({ liked }) });
            loadPlan();
          } else if (btn.classList.contains("an-gen")) {
            let est = "Estimativa indisponível.";
            try {
              const c = await api(`${base}/cost`, { method: "POST", body: JSON.stringify({ scene: s.scene, shot: s.shot, model: f.model, count: f.count }) });
              if (!c.credits_unknown) est = `Estimativa: ${c.total} créditos.`;
            } catch (err) { /* mantém indisponível */ }
            if (!confirm(`Gerar ${f.count} take(s) de ${f.k} com ${f.model}? ${est} Isso gasta créditos.`)) return;
            await api(`${base}/generate`, { method: "POST", body: JSON.stringify({ scene: s.scene, shot: s.shot, model: f.model, count: f.count, prompt: f.prompt, duration: f.duration }) });
            jobShot = f.k; pollJob();
          }
        } catch (err) { toast(err.message); }
      });
      const drop = $("#anDrop");
      drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
      drop.addEventListener("dragleave", () => drop.classList.remove("over"));
      drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); uploadFiles(e.dataTransfer.files); });
      $("#anUpload").addEventListener("change", e => uploadFiles(e.target.files));
      $("#anBtnDownloads").onclick = async () => {
        try { const r = await api(`/api/projects/${ctx.pid()}/animate/import/downloads`, { method: "POST", body: JSON.stringify({ since_minutes: +$("#anDlMinutes").value }) }); toast(`${r.added} novos de ${r.scanned} vídeos recentes`); loadCandidates(); }
        catch (err) { toast(err.message); }
      };
      $("#anBtnHistory").onclick = async () => {
        try { const r = await api(`/api/projects/${ctx.pid()}/animate/import/history`, { method: "POST", body: JSON.stringify({ size: 50 }) }); toast(`${r.added} vídeos de ${r.jobs} jobs`); loadCandidates(); }
        catch (err) { toast(err.message); }
      };
      $("#anGallery").addEventListener("click", e => {
        const card = e.target.closest(".card"); if (!card) return;
        picked = picked === card.dataset.id ? null : card.dataset.id; renderGallery();
      });
      $("#anGallery").addEventListener("dblclick", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = cands.find(x => x.id === card.dataset.id);
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
    },
  };
});
