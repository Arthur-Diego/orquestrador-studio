// Etapa 2 — Mood board (aula 009): UMA vibe encontrada, grid de 4, teto de 8 escolhidas.
// A aula NÃO proíbe produto/texto/logo no mood — só "sem pessoas", e como escolha da campanha.
// Wave 4: a tela é o protótipo (4 painéis, sem `details.lesson`, sem brief/histórico visíveis).
// O texto de aula continua no `guide.py`; as ações que só existiam nos controles removidos
// foram integradas: "melhor do grid" virou ação de hover no tile, "usar as imagens de vibe como
// referência de estilo" passou a ser sempre verdadeiro e o progresso virou `button.loading`.
Studio.register("mood", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  let cands = [], sel = new Set(), variation = 0, vibe = [], vibeSel = new Set(), bestId = "", job = null;
  // O rótulo da paleta é parte do markup da etapa (`.palette .lbl` do catálogo) e sobrevive
  // à reescrita dos swatches feita ao salvar o mood.
  const PALETTE_LBL = `<span class="lbl">palette.json · derivado técnico [extensão]</span>`;

  // Card de prompt do protótipo: eyebrow "Prompt gerado" + "Copiar" + o prompt em altura
  // automática. O negativo entra no próprio texto (o protótipo não desenha bloco de meta).
  function showPrompt(r) {
    const texto = r.negative ? `${r.prompt} Negative: ${r.negative}` : r.prompt;
    $("#promptList").innerHTML =
      `<div class="prompt"><div class="row"><span class="eyebrow">Prompt gerado</span>` +
      ui.copyBtn("#promptList textarea") + `</div>` +
      `<textarea data-i="0">${ui.esc(texto)}</textarea></div>`;
    ui.autosize($("#promptList textarea"));
  }

  async function genPrompts(next) {
    if (next) variation += 1;
    const q = `model=${encodeURIComponent($("#moodModel").value)}&variation=${variation}` +
              `&no_people=${$("#moodNoPeople").checked}` +
              `&explore_prompt=${encodeURIComponent($("#explorePrompt").value.trim())}`;
    const r = await api(`/api/projects/${ctx.pid()}/mood/prompts?${q}`);
    showPrompt({ prompt: r.prompts[0].text });
  }

  async function loadVibe() {
    const v = await api(`/api/projects/${ctx.pid()}/mood/vibe`);
    vibe = v.images; vibeSel = new Set([...vibeSel].filter(id => vibe.some(c => c.id === id)));
    const cs = $("#claudeState");
    // Estado desenhado pelo protótipo: "bot: claude ok". O ausente (que ele não desenha) é `warn`.
    cs.textContent = v.available_claude ? "bot: claude ok" : "bot: claude ausente";
    cs.className = "chip " + (v.available_claude ? "ok" : "warn");
    [...$("#moodMode").options].forEach(o => { if (o.value !== "template") o.disabled = !v.available_claude; });
    if (!v.available_claude) { $("#moodMode").value = "template"; syncMode(); }
    renderVibe();
  }

  function vibeCount() {
    $("#vibeCount").textContent = `${vibe.length} imagens · ${vibeSel.size} escolhidas (máx. 4)`;
  }

  function renderVibe() {
    vibeCount();
    // Tile do protótipo: sem badge de origem; legenda = "<origem> · <nome>".
    $("#vibeGallery").innerHTML = vibe.length ? vibe.map(c =>
      `<div class="card ${vibeSel.has(c.id) ? "sel" : ""}" data-id="${ui.esc(c.id)}" tabindex="0" title="${ui.esc(c.name || "")}">
         <img loading="lazy" src="${ctx.files(`mood/vibe/candidates/${c.thumb}`)}" alt=""><span class="term">${ui.esc(`${c.source || ""} · ${c.name || ""}`)}</span></div>`).join("")
      : `<div class="empty">Nenhuma imagem de vibe ainda — traga 1 a 4 imagens cujo sentimento você gosta.</div>`;
  }

  function syncMode() {
    // Os campos de brief só existem no modo "brief profissional" (o protótipo não os desenha).
    $("#briefFields").hidden = $("#moodMode").value !== "brief";
  }

  async function generatePrompt() {
    const mode = $("#moodMode").value, btn = $("#btnMoodGenPrompt");
    if (mode === "images" && !vibeSel.size) return toast("Marque de 1 a 4 imagens de vibe");
    btn.disabled = true;
    // `button.loading` é o único feedback de "gerando…" (10–30 s com o Claude).
    if (mode !== "template") btn.classList.add("loading");
    try {
      const r = await api(`/api/projects/${ctx.pid()}/mood/prompts/generate`, { method: "POST", body: JSON.stringify({
        mode, instruction: $("#moodInstruction").value, image_ids: [...vibeSel],
        purpose: $("#bfPurpose").value, tone: $("#bfTone").value, reference: $("#bfRef").value,
        model: $("#moodModel").value, variation,
        no_people: $("#moodNoPeople").checked, explore_prompt: $("#explorePrompt").value.trim() }) });
      showPrompt(r); ctx.guide();
    } catch (err) { toast(err.message); }
    btn.classList.remove("loading");
    btn.disabled = false;
  }

  const prompts = () => [...document.querySelectorAll("#promptList textarea")].map(t => t.value.trim()).filter(Boolean);

  function startPoll() {
    if (job) job.stop();
    job = ui.poll(async () => {
      const j = await api(`/api/projects/${ctx.pid()}/mood/job`);
      if (j.state === "running") { load(true); return; }
      $("#btnMoodGen").classList.remove("loading");
      $("#btnMoodGen").disabled = false;
      toast(j.state === "error" ? "erro: " + j.error : `concluído · ${j.added} imagens`);
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
    await loadPalette();
  }

  // `mood/palette.json` só existe depois do primeiro "Salvar mood": buscar antes disso daria
  // um 404 no console. Por isso a leitura é condicionada a haver escolhida salva.
  async function loadPalette() {
    if (!cands.some(c => c.selected)) return;
    try {
      const r = await fetch(ctx.files("mood/palette.json"));
      if (!r.ok) return;
      paintPalette((await r.json()).colors || []);
    } catch (err) { /* derivado técnico: nunca quebra a tela */ }
  }

  function paintPalette(colors) {
    $("#palette").innerHTML = colors.map(c =>
      `<span style="background:${ui.esc(c)}" title="${ui.esc(c)}"></span>`).join("") + PALETTE_LBL;
  }

  function moodCounts() {
    $("#moodCounts").textContent = `${cands.length} candidatas · ${sel.size} escolhidas`;
  }

  function render() {
    moodCounts();
    // Tile do protótipo: sem badge de origem; legenda = "<lote> · img <n>". A ação "melhor do
    // grid" (aula 009: gerar de novo com a melhor imagem como referência) é o `.card-act`,
    // visível só no hover — o protótipo não desenha controle para ela.
    $("#moodGallery").innerHTML = cands.length ? cands.map(c =>
      `<div class="card ${sel.has(c.id) ? "sel" : ""}" data-id="${ui.esc(c.id)}" tabindex="0" title="${ui.esc(c.prompt || c.name || "")}">
         <img loading="lazy" src="${ctx.files(`mood/candidates/${c.thumb}`)}" alt=""><span class="term">${ui.esc(`${c.batch || "grid"} · img ${c.batch_index || 1}`)}</span>` +
      `<button type="button" class="card-act" data-best="${ui.esc(c.id)}">${c.id === bestId ? "referência de estilo ✓" : "usar como referência"}</button></div>`).join("")
      : `<div class="empty">Nenhuma imagem ainda — gere na UI e importe, ou gere via CLI.</div>`;
  }

  return {
    init() {
      $("#btnMoodPrompts").onclick = () => genPrompts(true);
      $("#btnMoodGenPrompt").onclick = generatePrompt;
      $("#moodMode").onchange = syncMode;
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
        vibeCount();
      });
      $("#btnMoodGen").onclick = async () => {
        const ps = prompts();
        // `use_style_refs` é sempre verdadeiro: a aula manda usar a vibe como referência de estilo.
        const body = { model: $("#moodModel").value, prompts: ps, count: +$("#moodCount").value,
                       use_style_refs: true, vibe_ids: [...vibeSel], best_id: bestId || null };
        const ok = await ui.confirmCost(
          () => api(`/api/projects/${ctx.pid()}/mood/cost`, { method: "POST", body: JSON.stringify(body) }),
          `Gerar ${ps.length} prompt(s) × ${$("#moodCount").value} variações via CLI`);
        if (!ok) return;
        try {
          await api(`/api/projects/${ctx.pid()}/mood/generate`, { method: "POST", body: JSON.stringify(body) });
          $("#btnMoodGen").disabled = true; $("#btnMoodGen").classList.add("loading"); startPoll();
        } catch (err) { toast(err.message); }
      };
      $("#btnDownloads").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/mood/import/downloads`, { method: "POST",
            body: JSON.stringify({ since_minutes: +$("#vibeMinutes").value }) });
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
        const act = e.target.closest("[data-best]");
        if (act) {
          bestId = bestId === act.dataset.best ? "" : act.dataset.best;
          render();
          toast(bestId ? "melhor do grid: será a referência de estilo da próxima geração"
                       : "referência de estilo desmarcada");
          return;
        }
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id;
        sel.has(id) ? sel.delete(id) : sel.add(id); card.classList.toggle("sel");
        moodCounts();
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
          paintPalette(r.palette);
          toast(r.vibe ? `${r.selected} imagens salvas · vibe do projeto: ${r.vibe}`
                       : `${r.selected} imagens salvas em mood/selected`);
          await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      variation = 0; bestId = "";
      syncMode();
      ui.hfChip($("#hfState")).then(s => {
        $("#btnMoodGen").disabled = !s.logged_in;
        // O protótipo desta tela escreve `CLI: <plano> · <N> créditos` (a barra lateral usa `● CLI · …`).
        $("#hfState").textContent = s.logged_in
          ? `CLI: ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`
          : $("#hfState").textContent.replace(/^●\s*CLI\s*·\s*/, "CLI: ");
      });
      const p = ctx.project();
      if (p && p.vibe && !$("#moodNote").value) $("#moodNote").value = p.vibe;
      await Promise.all([load(), loadVibe(), genPrompts(false)]);
      ctx.guide();
    },
    destroy() { if (job) { job.stop(); job = null; } },
  };
});
