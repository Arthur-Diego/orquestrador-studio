// Etapa 2 — Mood board (aula 009): UMA vibe, grid de 4 na UI, teto de 8 escolhidas.
Studio.register("mood", (ctx) => {
  const { $, api, toast } = ctx;
  let cands = [], sel = new Set(), variation = 0, vibe = [], vibeSel = new Set();

  async function hfStatus() {
    const s = await api("/api/higgsfield/status"), el = $("#hfState");
    if (!s.installed) { el.textContent = "CLI: não instalado"; el.className = "chip warn"; }
    else if (!s.logged_in) { el.textContent = "CLI: instalado, sem login (higgsfield auth login)"; el.className = "chip warn"; }
    else { el.textContent = `CLI: ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`; el.className = "chip ok"; }
    $("#btnMoodGen").disabled = !s.logged_in;
  }
  function showPrompt(r) {
    $("#moodHint").textContent = (r.ui_hint || "") + " Proporção " + (r.aspect_ratio || "16:9") + (r.source === "template" ? ` · template, variação ${(r.variation ?? variation) + 1}.` : ` · gerado pelo bot (${r.source}) em ${r.seconds ?? "?"} s.`);
    const meta = [r.camera ? `Câmera: ${r.camera}` : "", r.negative ? `Evitar: ${r.negative}` : "", r.notes_pt ? `Notas: ${r.notes_pt}` : ""].filter(Boolean).join("\n");
    $("#promptList").innerHTML = `<div class="prompt"><div class="row"><span class="eyebrow">Vibe da campanha</span><button class="ghost copy" data-i="0">Copiar</button><span class="ok"></span></div><textarea data-i="0">${r.prompt}</textarea>${meta ? `<div class="fine mono" style="white-space:pre-wrap">${meta}</div>` : ""}</div>`;
  }
  async function genPrompts(next) {
    if (next) variation += 1;
    const r = await api(`/api/projects/${ctx.pid()}/mood/prompts?model=${$("#moodModel").value}&variation=${variation}`);
    showPrompt({ prompt: r.prompts[0].text, ui_hint: r.ui_hint, aspect_ratio: r.aspect_ratio, source: "template", variation: r.variation });
  }
  async function loadVibe() {
    const v = await api(`/api/projects/${ctx.pid()}/mood/vibe`);
    vibe = v.images; vibeSel = new Set([...vibeSel].filter(id => vibe.some(c => c.id === id)));
    const cs = $("#claudeState"); cs.textContent = v.available_claude ? "bot: Claude CLI pronto" : "bot: Claude CLI ausente (só template)"; cs.className = "chip " + (v.available_claude ? "ok" : "warn");
    [...$("#moodMode").options].forEach(o => { if (o.value !== "template") o.disabled = !v.available_claude; });
    if (!v.available_claude) $("#moodMode").value = "template";
    renderVibe();
  }
  function renderVibe() {
    $("#vibeCount").textContent = `${vibe.length} imagens · ${vibeSel.size} escolhidas (máx. 4)`;
    $("#vibeGallery").innerHTML = vibe.length ? vibe.map(c =>
      `<div class="card ${vibeSel.has(c.id) ? "sel" : ""}" data-id="${c.id}" tabindex="0" title="${c.name || ""}"><img loading="lazy" src="${ctx.files(`mood/vibe/candidates/${c.thumb}`)}" alt=""><span class="src">${c.source}</span></div>`).join("")
      : `<div class="empty">Nenhuma imagem de vibe ainda — traga 1 a 4 imagens cujo sentimento você gosta.</div>`;
  }
  async function vibeUpload(files) {
    if (!files.length) return;
    const fd = new FormData(); [...files].forEach(f => fd.append("files", f));
    const r = await fetch(`/api/projects/${ctx.pid()}/mood/vibe/import/upload`, { method: "POST", body: fd });
    if (!r.ok) return toast((await r.json().catch(() => ({}))).detail || r.statusText);
    toast(`${(await r.json()).added} imagens de vibe importadas`); loadVibe();
  }
  async function loadHistory() {
    const h = await api(`/api/projects/${ctx.pid()}/mood/prompts/history`);
    $("#promptHistory").textContent = h.length ? h.map(e => `${e.created} · ${e.mode}${e.instruction ? " · " + e.instruction : ""}\n${e.prompt}\n`).join("\n") : "(vazio)";
  }
  async function generatePrompt() {
    const mode = $("#moodMode").value, btn = $("#btnMoodGenPrompt");
    if (mode === "images" && !vibeSel.size) return toast("Marque de 1 a 4 imagens de vibe");
    btn.disabled = true; $("#promptStatus").textContent = mode === "template" ? "" : "gerando com o Claude (10–30 s)…";
    try {
      const r = await api(`/api/projects/${ctx.pid()}/mood/prompts/generate`, { method: "POST", body: JSON.stringify({ mode, instruction: $("#moodInstruction").value, image_ids: [...vibeSel], purpose: $("#bfPurpose").value, tone: $("#bfTone").value, reference: $("#bfRef").value, model: $("#moodModel").value, variation }) });
      showPrompt(r); loadHistory(); $("#promptStatus").textContent = "";
    } catch (err) { $("#promptStatus").textContent = ""; toast(err.message); }
    btn.disabled = false;
  }
  const prompts = () => [...document.querySelectorAll("#promptList textarea")].map(t => t.value.trim()).filter(Boolean);
  async function pollGen() {
    const j = await api(`/api/projects/${ctx.pid()}/mood/job`);
    $("#moodGenLog").textContent = j.state === "running" ? `gerando ${j.done}/${j.total} · ${j.added} imagens` : j.state === "error" ? "erro: " + j.error : `concluído · ${j.added} imagens`;
    if (j.state === "running") { setTimeout(pollGen, 3000); load(true); } else { $("#btnMoodGen").disabled = false; load(); }
  }
  async function uploadFiles(files) {
    if (!files.length) return;
    const fd = new FormData(); [...files].forEach(f => fd.append("files", f));
    const r = await fetch(`/api/projects/${ctx.pid()}/mood/import/upload`, { method: "POST", body: fd });
    if (!r.ok) return toast((await r.json().catch(() => ({}))).detail || r.statusText);
    toast(`${(await r.json()).added} imagens importadas`); load();
  }
  async function load(keep) {
    if (!ctx.pid()) { cands = []; render(); return; }
    cands = await api(`/api/projects/${ctx.pid()}/mood/candidates`);
    if (!keep) sel = new Set(cands.filter(c => c.selected).map(c => c.id));
    render();
  }
  function render() {
    $("#moodCounts").textContent = `${cands.length} candidatas · ${sel.size} escolhidas`;
    $("#moodGallery").innerHTML = cands.length ? cands.map(c =>
      `<div class="card ${sel.has(c.id) ? "sel" : ""}" data-id="${c.id}" tabindex="0" title="${(c.prompt || c.name || "").replace(/"/g, "'")}">
         <img loading="lazy" src="${ctx.files(`mood/candidates/${c.thumb}`)}" alt=""><span class="src">${c.source}</span><span class="term">${c.model || c.name || ""}</span></div>`).join("")
      : `<div class="empty">Nenhuma imagem ainda — gere na UI e importe, ou gere via CLI.</div>`;
  }

  return {
    init() {
      $("#btnMoodPrompts").onclick = () => genPrompts(true);
      $("#btnMoodGenPrompt").onclick = generatePrompt;
      $("#moodMode").onchange = () => { $("#briefFields").style.display = $("#moodMode").value === "template" ? "none" : ""; };
      const vd = $("#vibeDrop");
      vd.addEventListener("dragover", e => { e.preventDefault(); vd.classList.add("over"); });
      vd.addEventListener("dragleave", () => vd.classList.remove("over"));
      vd.addEventListener("drop", e => { e.preventDefault(); vd.classList.remove("over"); vibeUpload(e.dataTransfer.files); });
      $("#vibeUpload").addEventListener("change", e => vibeUpload(e.target.files));
      $("#btnVibeDownloads").onclick = async () => {
        try { const r = await api(`/api/projects/${ctx.pid()}/mood/vibe/import/downloads`, { method: "POST", body: JSON.stringify({ since_minutes: +$("#vibeMinutes").value }) }); toast(`${r.added} novas de ${r.scanned} imagens recentes`); loadVibe(); }
        catch (err) { toast(err.message); }
      };
      $("#vibeGallery").addEventListener("click", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id;
        if (vibeSel.has(id)) vibeSel.delete(id); else { if (vibeSel.size >= 4) return toast("Máximo de 4 imagens de vibe"); vibeSel.add(id); }
        card.classList.toggle("sel"); $("#vibeCount").textContent = `${vibe.length} imagens · ${vibeSel.size} escolhidas (máx. 4)`;
      });
      $("#promptList").addEventListener("click", async e => {
        const b = e.target.closest("button.copy"); if (!b) return;
        await navigator.clipboard.writeText($(`#promptList textarea[data-i="${b.dataset.i}"]`).value);
        b.parentElement.querySelector(".ok").textContent = "copiado ✓"; setTimeout(() => b.parentElement.querySelector(".ok").textContent = "", 1500);
      });
      $("#btnCopyAll").onclick = async () => { await navigator.clipboard.writeText(prompts().join("\n\n")); toast("Prompt copiado"); };
      $("#btnMoodGen").onclick = async () => {
        const ps = prompts(); let est = "Estimativa indisponível.";
        try { const c = await api(`/api/projects/${ctx.pid()}/mood/cost`, { method: "POST", body: JSON.stringify({ model: $("#moodModel").value, prompts: ps, count: +$("#moodCount").value }) }); if (c.total != null) est = `Estimativa: ${c.total} créditos.`; } catch (e) { /* mantém indisponível */ }
        if (!confirm(`Gerar ${ps.length} prompt(s) × ${$("#moodCount").value} variações via CLI? ${est} Isso gasta créditos.`)) return;
        try {
          await api(`/api/projects/${ctx.pid()}/mood/generate`, { method: "POST", body: JSON.stringify({ model: $("#moodModel").value, prompts: ps, count: +$("#moodCount").value, use_refs: $("#moodUseRefs").checked }) });
          $("#btnMoodGen").disabled = true; pollGen();
        } catch (err) { toast(err.message); }
      };
      const drop = $("#drop");
      drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
      drop.addEventListener("dragleave", () => drop.classList.remove("over"));
      drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); uploadFiles(e.dataTransfer.files); });
      $("#upload").addEventListener("change", e => uploadFiles(e.target.files));
      $("#btnDownloads").onclick = async () => {
        try { const r = await api(`/api/projects/${ctx.pid()}/mood/import/downloads`, { method: "POST", body: JSON.stringify({ since_minutes: +$("#dlMinutes").value }) }); toast(`${r.added} novas de ${r.scanned} imagens recentes`); load(); }
        catch (err) { toast(err.message); }
      };
      $("#btnHistory").onclick = async () => {
        try { const r = await api(`/api/projects/${ctx.pid()}/mood/import/history`, { method: "POST" }); toast(`${r.added} imagens de ${r.jobs} jobs`); load(); }
        catch (err) { toast(err.message); }
      };
      $("#moodGallery").addEventListener("click", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id; sel.has(id) ? sel.delete(id) : sel.add(id); card.classList.toggle("sel");
        $("#moodCounts").textContent = `${cands.length} candidatas · ${sel.size} escolhidas`;
      });
      $("#moodGallery").addEventListener("dblclick", e => { const card = e.target.closest(".card"); if (!card) return; const c = cands.find(x => x.id === card.dataset.id); window.open(ctx.files(`mood/candidates/${c.file}`), "_blank"); });
      $("#btnMoodSave").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/mood/select`, { method: "POST", body: JSON.stringify({ ids: [...sel], note: $("#moodNote").value }) });
          $("#palette").innerHTML = r.palette.map(c => `<span style="background:${c}" title="${c}"></span>`).join("");
          toast(`${r.selected} imagens salvas em mood/selected`); load();
        } catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      variation = 0; hfStatus(); load(); loadVibe(); loadHistory(); genPrompts(false);
      const d = await api("/api/mood/downloads-folder"); $("#dlFolder").textContent = d.folder + (d.exists ? "" : " (não encontrada)");
    },
  };
});
