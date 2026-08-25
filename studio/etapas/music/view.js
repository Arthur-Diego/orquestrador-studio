// Etapa 7 — Trilha (aula 013): assistir a história inteira, decidir se ela fecha e só então
// escolher a música — "você não deve editar antes de escolher a trilha sonora".
Studio.register("music", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  let cands = [], beats = null, story = null, genJob = null, storyJob = null;

  const fmt = (s) => (s == null || !isFinite(s) || s <= 0) ? "" : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  const esc = (s) => ui.esc(s);

  async function loadPrompt() {
    const r = await api(`/api/projects/${ctx.pid()}/music/prompt`);
    $("#musPrompt").value = r.prompt;
    $("#musDuration").value = r.duration;
    $("#musInstructions").textContent = r.instructions;
  }

  // ---------- passo 0: a história inteira ----------
  async function loadStory() {
    if (!ctx.pid()) return;
    try { story = await api(`/api/projects/${ctx.pid()}/music/story`); }
    catch (e) { story = null; return; }
    const chip = $("#musStoryChip");
    if (story.warning) { chip.textContent = story.warning; chip.className = "chip warn"; }
    else if (story.video) { chip.textContent = `sequência pronta · ${story.clips} cena(s) · ${fmt(story.duration)}`; chip.className = "chip ok"; }
    else { chip.textContent = `${story.clips} cena(s) prontas para montar`; chip.className = "chip mode"; }
    $("#btnMusStory").disabled = !story.ffmpeg || !story.clips;
    if (!story.ffmpeg) $("#musStoryLog").textContent = "ffmpeg ausente — a sequência bruta não pode ser montada aqui";

    const v = $("#musStoryVideo");
    if (story.video) { v.src = `${ctx.files(story.video)}?t=${Date.now()}`; v.classList.remove("hidden"); }
    else { v.classList.add("hidden"); }

    $("#musStoryQuestion").textContent = story.question || "";
    const check = story.check;
    if (check) {
      const target = document.querySelector(`input[name="musClosed"][value="${check.closed ? 1 : 0}"]`);
      if (target) target.checked = true;
      $("#musStoryNote").value = check.note || "";
    }
    const pc = $("#musProductChip");
    pc.textContent = story.product_scene ? "cena do produto: existe (etapa 5)" : "cena do produto: não existe";
    pc.className = story.product_scene ? "chip ok" : "chip warn";
  }

  async function renderStory() {
    try {
      await api(`/api/projects/${ctx.pid()}/music/story/render`, { method: "POST", body: "{}" });
      $("#btnMusStory").disabled = true;
      if (storyJob) storyJob.stop();
      storyJob = ui.poll(async () => {
        const j = await api(`/api/projects/${ctx.pid()}/music/story/job`);
        $("#musStoryLog").textContent = j.state === "running" ? `montando ${j.done}/${j.total}…`
          : j.state === "error" ? `erro: ${j.error}` : (j.log || []).join(" | ");
        if (j.state === "running") return;
        $("#btnMusStory").disabled = false;
        await loadStory(); ctx.guide();
        if (j.state === "done") toast("Sequência bruta pronta — assista inteira antes de escolher a trilha");
        return false;
      }, 3000);
    } catch (err) { $("#btnMusStory").disabled = false; toast(err.message); }
  }

  async function saveStoryCheck() {
    const picked = document.querySelector('input[name="musClosed"]:checked');
    if (!picked) return toast("Responda se a história fecha ou se falta cena.");
    try {
      await api(`/api/projects/${ctx.pid()}/music/story/check`, {
        method: "POST",
        body: JSON.stringify({ closed: picked.value === "1", note: $("#musStoryNote").value.trim() }),
      });
      toast("Decisão registrada"); await loadStory(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  // ---------- candidatas e batidas ----------
  async function load() {
    if (!ctx.pid()) { cands = []; return render(); }
    cands = await api(`/api/projects/${ctx.pid()}/music/candidates`);
    render();
    try { beats = await api(`/api/projects/${ctx.pid()}/music/beats`); } catch (e) { beats = null; }
    renderBeats();
  }

  function render() {
    $("#musCounts").textContent = `${cands.length} candidata${cands.length === 1 ? "" : "s"}`;
    $("#musList").innerHTML = cands.length ? cands.map((c) => `
      <div class="prompt ${c.selected ? "sel" : ""}" data-id="${esc(c.id)}">
        <div class="row wrap">
          <span class="eyebrow">${esc(c.name || c.file)}</span>
          ${ui.chip(`${c.source}${c.duration ? " · " + fmt(c.duration) : ""}`)}
          ${c.selected ? ui.chip("escolhida", "ok") : ""}
          <button class="primary pick" data-id="${esc(c.id)}">Escolher esta</button>
        </div>
        <audio controls preload="none" style="width:100%" src="${ctx.files(`audio/candidates/${c.file}`)}"></audio>
      </div>`).join("")
      : `<div class="empty">Nenhuma candidata ainda — baixe várias músicas na biblioteca e importe acima.</div>`;
    const chosen = cands.find((c) => c.selected);
    $("#musPlayer").src = chosen ? ctx.files(`audio/candidates/${chosen.file}`) : "";
  }

  function renderBeats() {
    const chip = $("#musBeatsChip"), ruler = $("#musRuler");
    if (!beats || !beats.duration) {
      chip.textContent = cands.some((c) => c.selected) ? "trilha escolhida, sem batidas detectadas" : "nenhuma trilha escolhida";
      chip.className = "chip mode"; ruler.innerHTML = ""; return;
    }
    chip.textContent = `${beats.bpm ? beats.bpm + " bpm" : "bpm indefinido"} · ${beats.beats.length} batidas · ${beats.impacts.length} impactos · ${fmt(beats.duration)}`;
    chip.className = "chip ok";
    const impacts = new Set(beats.impacts);
    ruler.innerHTML = beats.beats.map((t) => {
      const strong = impacts.has(t);
      return `<span title="${t}s${strong ? " (impacto)" : ""}" style="position:absolute;left:${(t / beats.duration) * 100}%;bottom:0;width:${strong ? 2 : 1}px;height:${strong ? 100 : 45}%;background:${strong ? "currentColor" : "rgba(128,128,128,.6)"}"></span>`;
    }).join("");
  }

  async function pick(id) {
    try {
      const r = await api(`/api/projects/${ctx.pid()}/music/select`, {
        method: "POST",
        body: JSON.stringify({ id, license: $("#musOrigin").value.trim() }),
      });
      beats = r.beats;
      $("#musWarn").textContent = r.warning || "Trocou de trilha depois de montar? A montagem (etapa 8) precisa ser refeita.";
      toast(r.beats ? `Trilha escolhida · ${r.beats.impacts.length} impactos` : "Trilha escolhida (sem detecção de batidas)");
      await load(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  return {
    init() {
      $("#btnMusStory").onclick = renderStory;
      $("#btnMusStoryCheck").onclick = saveStoryCheck;
      $("#btnMusGoShots").onclick = () => Studio.go("shots");
      $("#btnMusGoAnimate").onclick = () => Studio.go("animate");
      $("#btnMusCopyPrompt").onclick = async () => {
        await navigator.clipboard.writeText($("#musPrompt").value);
        $("#musPromptOk").textContent = "copiado ✓"; setTimeout(() => ($("#musPromptOk").textContent = ""), 1500);
      };
      $("#btnMusGen").onclick = async () => {
        const body = { prompt: $("#musPrompt").value.trim(), duration: +$("#musDuration").value, count: +$("#musCount").value };
        const ok = await ui.confirmCost(
          () => api(`/api/projects/${ctx.pid()}/music/generate/cost`, { method: "POST", body: JSON.stringify(body) }),
          `Gerar ${body.count} faixa(s) de ${body.duration}s via CLI`);
        if (!ok) return;
        try {
          await api(`/api/projects/${ctx.pid()}/music/generate`, { method: "POST", body: JSON.stringify(body) });
          $("#btnMusGen").disabled = true;
          if (genJob) genJob.stop();
          genJob = ui.poll(async () => {
            const j = await api(`/api/projects/${ctx.pid()}/music/generate/job`);
            $("#musGenLog").textContent = j.state === "running" ? `gerando ${j.done}/${j.total} · ${j.added} faixas`
              : j.state === "error" ? "erro: " + j.error : `concluído · ${j.added} faixas` + (j.log && j.log.length ? " · " + j.log.join(" | ") : "");
            if (j.state === "running") return;
            $("#btnMusGen").disabled = false; await load(); ctx.guide();
            return false;
          }, 3000);
        } catch (err) { toast(err.message); }
      };
      ui.drop($("#musDrop"), async (files) => {
        try {
          const r = await ui.upload(`/api/projects/${ctx.pid()}/music/import/upload`, files);
          toast(`${r.added} música(s) importada(s)`); await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      });
      $("#btnMusDownloads").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/music/import/downloads`, { method: "POST", body: JSON.stringify({ since_minutes: +$("#musDlMinutes").value }) });
          toast(`${r.added} novas de ${r.scanned} músicas recentes`); await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#btnMusHistory").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/music/import/history`, { method: "POST", body: JSON.stringify({}) });
          toast(`${r.added} faixas de ${r.jobs} jobs`); await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#musList").addEventListener("click", (e) => { const b = e.target.closest("button.pick"); if (b) pick(b.dataset.id); });
      $("#btnMusBeats").onclick = async () => {
        try {
          beats = await api(`/api/projects/${ctx.pid()}/music/beats`, { method: "POST", body: JSON.stringify({}) });
          renderBeats(); ctx.guide(); toast(`${beats.impacts.length} impactos`);
        } catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      $("#musWarn").textContent = "";
      ui.hfChip($("#musHfState")).then((s) => { $("#btnMusGen").disabled = !s.logged_in; });
      await loadPrompt();
      await loadStory();
      await load();
      const d = await api("/api/music/downloads-folder");
      $("#musDlFolder").textContent = d.folder + (d.exists ? "" : " (não encontrada)");
      ctx.guide();
    },
    destroy() {
      if (genJob) genJob.stop();
      if (storyJob) storyJob.stop();
    },
  };
});
