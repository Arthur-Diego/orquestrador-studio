// Etapa 2 — Mood board (aula 009): UMA vibe encontrada, grid de 4, teto de 8 escolhidas.
// A aula NÃO proíbe produto/texto/logo no mood — só "sem pessoas", e como escolha da campanha.
Studio.register("mood", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  let cands = [], sel = new Set(), variation = 0, vibe = [], vibeSel = new Set(), job = null;
  // O rótulo da paleta é parte do markup da etapa (`.palette .lbl` do catálogo) e sobrevive
  // à reescrita dos swatches feita ao salvar o mood.
  const PALETTE_LBL = `<span class="lbl">palette.json · derivado técnico [extensão]</span>`;

  function showPrompt(r) {
    $("#moodHint").textContent = (r.ui_hint || "") + " Proporção " + (r.aspect_ratio || "16:9") +
      (r.source === "template" ? ` · template, variação ${(r.variation ?? variation) + 1}.`
                               : ` · gerado pelo bot (${r.source}) em ${r.seconds ?? "?"} s.`);
    const meta = [r.camera ? `Câmera: ${r.camera}` : "", r.negative ? `Evitar: ${r.negative}` : "",
                  r.notes_pt ? `Notas: ${r.notes_pt}` : ""].filter(Boolean).join("\n");
    // Card de prompt do catálogo do shell: eyebrow + `button.link` "Copiar" + `.ok` + textarea.
    $("#promptList").innerHTML =
      `<div class="prompt"><div class="row"><span class="eyebrow">Prompt gerado</span>` +
      `<button class="link copy" data-i="0">Copiar</button><span class="ok"></span></div>` +
      `<textarea data-i="0">${ui.esc(r.prompt)}</textarea>` +
      (meta ? `<p class="fine mono md-pre">${ui.esc(meta)}</p>` : "") + `</div>`;
  }

  async function genPrompts(next) {
    if (next) variation += 1;
    const q = `model=${encodeURIComponent($("#moodModel").value)}&variation=${variation}` +
              `&no_people=${$("#moodNoPeople").checked}` +
              `&explore_prompt=${encodeURIComponent($("#explorePrompt").value.trim())}`;
    const r = await api(`/api/projects/${ctx.pid()}/mood/prompts?${q}`);
    showPrompt({ prompt: r.prompts[0].text, ui_hint: r.ui_hint, aspect_ratio: r.aspect_ratio,
                 source: "template", variation: r.variation });
  }

  async function loadVibe() {
    const v = await api(`/api/projects/${ctx.pid()}/mood/vibe`);
    vibe = v.images; vibeSel = new Set([...vibeSel].filter(id => vibe.some(c => c.id === id)));
    const cs = $("#claudeState");
    cs.textContent = v.available_claude ? "bot: Claude CLI pronto" : "bot: Claude CLI ausente (só template)";
    cs.className = "chip " + (v.available_claude ? "ok" : "warn");
    [...$("#moodMode").options].forEach(o => { if (o.value !== "template") o.disabled = !v.available_claude; });
    if (!v.available_claude) $("#moodMode").value = "template";
    renderVibe();
  }

  function renderVibe() {
    $("#vibeCount").textContent = `${vibe.length} imagens · ${vibeSel.size} escolhidas (máx. 4)`;
    // Tiles do catálogo do shell: `.card` > img + `span.src` (origem) + `span.term` (legenda).
    $("#vibeGallery").innerHTML = vibe.length ? vibe.map(c =>
      `<div class="card ${vibeSel.has(c.id) ? "sel" : ""}" data-id="${ui.esc(c.id)}" tabindex="0" title="${ui.esc(c.name || "")}">
         <img loading="lazy" src="${ctx.files(`mood/vibe/candidates/${c.thumb}`)}" alt=""><span class="src">${ui.esc(c.source)}</span><span class="term">${ui.esc(c.name || "")}</span></div>`).join("")
      : `<div class="empty">Nenhuma imagem de vibe ainda — traga 1 a 4 imagens cujo sentimento você gosta.</div>`;
  }

  async function loadHistory() {
    const h = await api(`/api/projects/${ctx.pid()}/mood/prompts/history`);
    $("#promptHistory").textContent = h.length
      ? h.map(e => `${e.created} · ${e.mode}${e.instruction ? " · " + e.instruction : ""}\n${e.prompt}\n`).join("\n")
      : "(vazio)";
  }

  async function generatePrompt() {
    const mode = $("#moodMode").value, btn = $("#btnMoodGenPrompt");
    if (mode === "images" && !vibeSel.size) return toast("Marque de 1 a 4 imagens de vibe");
    btn.disabled = true;
    $("#promptStatus").textContent = mode === "template" ? "" : "gerando com o Claude (10–30 s)…";
    try {
      const r = await api(`/api/projects/${ctx.pid()}/mood/prompts/generate`, { method: "POST", body: JSON.stringify({
        mode, instruction: $("#moodInstruction").value, image_ids: [...vibeSel],
        purpose: $("#bfPurpose").value, tone: $("#bfTone").value, reference: $("#bfRef").value,
        model: $("#moodModel").value, variation,
        no_people: $("#moodNoPeople").checked, explore_prompt: $("#explorePrompt").value.trim() }) });
      showPrompt(r); loadHistory(); $("#promptStatus").textContent = ""; ctx.guide();
    } catch (err) { $("#promptStatus").textContent = ""; toast(err.message); }
    btn.disabled = false;
  }

  const prompts = () => [...document.querySelectorAll("#promptList textarea")].map(t => t.value.trim()).filter(Boolean);

  function startPoll() {
    if (job) job.stop();
    job = ui.poll(async () => {
      const j = await api(`/api/projects/${ctx.pid()}/mood/job`);
      $("#moodGenLog").textContent = j.state === "running" ? `gerando ${j.done}/${j.total} · ${j.added} imagens`
        : j.state === "error" ? "erro: " + j.error : `concluído · ${j.added} imagens`;
      if (j.state === "running") { load(true); return; }
      $("#btnMoodGen").disabled = false;
      await load(); ctx.guide(); job = null;
      return false;
    }, 3000);
  }

  async function uploadFiles(files) {
    if (!files || !files.length) return;
    try {
      const r = await ui.upload(`/api/projects/${ctx.pid()}/mood/import/upload`, files);
      toast(`${r.added} imagens importadas`); await load(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  async function vibeUpload(files) {
    if (!files || !files.length) return;
    try {
      const r = await ui.upload(`/api/projects/${ctx.pid()}/mood/vibe/import/upload`, files);
      toast(`${r.added} imagens de vibe importadas`); await loadVibe(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  async function load(keep) {
    if (!ctx.pid()) { cands = []; render(); return; }
    cands = await api(`/api/projects/${ctx.pid()}/mood/candidates`);
    if (!keep) sel = new Set(cands.filter(c => c.selected).map(c => c.id));
    render();
  }

  function render() {
    $("#moodCounts").textContent = `${cands.length} candidatas · ${sel.size} escolhidas`;
    const best = $("#moodBest"), cur = best.value;
    best.innerHTML = `<option value="">(nenhuma — 1ª rodada)</option>` + cands.map((c, i) =>
      `<option value="${ui.esc(c.id)}" ${c.id === cur ? "selected" : ""}>imagem ${i + 1} · ${ui.esc(c.source)}</option>`).join("");
    $("#moodGallery").innerHTML = cands.length ? cands.map(c =>
      `<div class="card ${sel.has(c.id) ? "sel" : ""}" data-id="${ui.esc(c.id)}" tabindex="0" title="${ui.esc(c.prompt || c.name || "")}">
         <img loading="lazy" src="${ctx.files(`mood/candidates/${c.thumb}`)}" alt=""><span class="src">${ui.esc(c.source)}</span><span class="term">${ui.esc(c.model || c.name || "")}</span></div>`).join("")
      : `<div class="empty">Nenhuma imagem ainda — gere na UI e importe, ou gere via CLI.</div>`;
  }

  return {
    init() {
      $("#btnMoodPrompts").onclick = () => genPrompts(true);
      $("#btnMoodGenPrompt").onclick = generatePrompt;
      $("#moodMode").onchange = () => {
        $("#briefFields").style.display = $("#moodMode").value === "template" ? "none" : "";
      };
      ui.drop($("#vibeDrop"), vibeUpload);
      ui.drop($("#drop"), uploadFiles);
      $("#btnVibeDownloads").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/mood/vibe/import/downloads`, { method: "POST",
            body: JSON.stringify({ since_minutes: +$("#vibeMinutes").value }) });
          toast(`${r.added} novas de ${r.scanned} imagens recentes`); await loadVibe(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#vibeGallery").addEventListener("click", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id;
        if (vibeSel.has(id)) vibeSel.delete(id);
        else { if (vibeSel.size >= 4) return toast("Máximo de 4 imagens de vibe"); vibeSel.add(id); }
        card.classList.toggle("sel");
        $("#vibeCount").textContent = `${vibe.length} imagens · ${vibeSel.size} escolhidas (máx. 4)`;
      });
      $("#promptList").addEventListener("click", async e => {
        const b = e.target.closest("button.copy"); if (!b) return;
        await navigator.clipboard.writeText($(`#promptList textarea[data-i="${b.dataset.i}"]`).value);
        const ok = b.parentElement.querySelector(".ok");
        ok.textContent = "copiado ✓"; setTimeout(() => { ok.textContent = ""; }, 1500);
      });
      $("#btnCopyAll").onclick = async () => {
        await navigator.clipboard.writeText(prompts().join("\n\n")); toast("Prompt copiado");
      };
      $("#btnMoodGen").onclick = async () => {
        const ps = prompts();
        const body = { model: $("#moodModel").value, prompts: ps, count: +$("#moodCount").value,
                       use_style_refs: $("#moodUseRefs").checked, vibe_ids: [...vibeSel],
                       best_id: $("#moodBest").value || null };
        const ok = await ui.confirmCost(
          () => api(`/api/projects/${ctx.pid()}/mood/cost`, { method: "POST", body: JSON.stringify(body) }),
          `Gerar ${ps.length} prompt(s) × ${$("#moodCount").value} variações via CLI`);
        if (!ok) return;
        try {
          await api(`/api/projects/${ctx.pid()}/mood/generate`, { method: "POST", body: JSON.stringify(body) });
          $("#btnMoodGen").disabled = true; startPoll();
        } catch (err) { toast(err.message); }
      };
      $("#btnDownloads").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/mood/import/downloads`, { method: "POST",
            body: JSON.stringify({ since_minutes: +$("#dlMinutes").value }) });
          toast(`${r.added} novas de ${r.scanned} imagens recentes`); await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#btnHistory").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/mood/import/history`, { method: "POST" });
          toast(`${r.added} imagens de ${r.jobs} jobs`); await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#moodGallery").addEventListener("click", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id;
        sel.has(id) ? sel.delete(id) : sel.add(id); card.classList.toggle("sel");
        $("#moodCounts").textContent = `${cands.length} candidatas · ${sel.size} escolhidas`;
      });
      $("#moodGallery").addEventListener("dblclick", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = cands.find(x => x.id === card.dataset.id);
        window.open(ctx.files(`mood/candidates/${c.file}`), "_blank");
      });
      $("#btnMoodSave").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/mood/select`, { method: "POST",
            body: JSON.stringify({ ids: [...sel], note: $("#moodNote").value }) });
          $("#palette").innerHTML = r.palette.map(c =>
            `<span style="background:${ui.esc(c)}" title="${ui.esc(c)}"></span>`).join("") + PALETTE_LBL;
          toast(r.vibe ? `${r.selected} imagens salvas · vibe do projeto: ${r.vibe}`
                       : `${r.selected} imagens salvas em mood/selected`);
          await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      variation = 0;
      ui.hfChip($("#hfState")).then(s => { $("#btnMoodGen").disabled = !s.logged_in; });
      const p = ctx.project();
      if (p && p.vibe && !$("#moodNote").value) $("#moodNote").value = p.vibe;
      await Promise.all([load(), loadVibe(), loadHistory(), genPrompts(false)]);
      ctx.guide();
      const d = await api("/api/mood/downloads-folder");
      $("#dlFolder").textContent = d.folder + (d.exists ? "" : " (não encontrada)");
    },
    destroy() { if (job) { job.stop(); job = null; } },
  };
});
