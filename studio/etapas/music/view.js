// Etapa 7 — Trilha (aula 013): reunir candidatas, ouvir até "sentir", escolher uma e marcar as batidas.
Studio.register("music", (ctx) => {
  const { $, api, toast } = ctx;
  let cands = [], beats = null;

  const fmt = (s) => (s == null || !isFinite(s) || s <= 0) ? "" : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  const esc = (s) => String(s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  async function hfStatus() {
    const s = await api("/api/higgsfield/status"), el = $("#musHfState");
    if (!s.installed) { el.textContent = "CLI: não instalado"; el.className = "chip warn"; }
    else if (!s.logged_in) { el.textContent = "CLI: instalado, sem login (higgsfield auth login)"; el.className = "chip warn"; }
    else { el.textContent = `CLI: ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`; el.className = "chip ok"; }
    $("#btnMusGen").disabled = !s.logged_in;
  }

  async function loadPrompt() {
    const r = await api(`/api/projects/${ctx.pid()}/music/prompt`);
    $("#musPrompt").value = r.prompt;
    $("#musDuration").value = r.duration;
    $("#musInstructions").textContent = r.instructions;
  }

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
      <div class="prompt ${c.selected ? "sel" : ""}" data-id="${c.id}">
        <div class="row wrap">
          <span class="eyebrow">${esc(c.name || c.file)}</span>
          <span class="chip mode">${esc(c.source)}${c.duration ? " · " + fmt(c.duration) : ""}</span>
          ${c.selected ? '<span class="chip ok">escolhida</span>' : ""}
          <button class="primary pick" data-id="${c.id}">Escolher esta</button>
        </div>
        <audio controls preload="none" style="width:100%" src="${ctx.files(`audio/candidates/${c.file}`)}"></audio>
      </div>`).join("")
      : `<div class="empty">Nenhuma candidata ainda — baixe 3 a 5 músicas na biblioteca e importe acima.</div>`;
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

  async function uploadFiles(files) {
    if (!files.length) return;
    const fd = new FormData(); [...files].forEach((f) => fd.append("files", f));
    const r = await fetch(`/api/projects/${ctx.pid()}/music/import/upload`, { method: "POST", body: fd });
    if (!r.ok) return toast((await r.json().catch(() => ({}))).detail || r.statusText);
    toast(`${(await r.json()).added} música(s) importada(s)`); load();
  }

  async function pollGen() {
    const j = await api(`/api/projects/${ctx.pid()}/music/generate/job`);
    $("#musGenLog").textContent = j.state === "running" ? `gerando ${j.done}/${j.total} · ${j.added} faixas`
      : j.state === "error" ? "erro: " + j.error : `concluído · ${j.added} faixas` + (j.log && j.log.length ? " · " + j.log.join(" | ") : "");
    if (j.state === "running") setTimeout(pollGen, 3000); else { $("#btnMusGen").disabled = false; load(); }
  }

  async function pick(id) {
    const c = cands.find((x) => x.id === id);
    const declared = prompt(`Origem e licença de "${c.name || c.file}"\n(ex.: YouTube Audio Library, "Frost Rider", uso livre com atribuição)`, "");
    if (declared === null) return;
    if (!declared.trim()) return toast("Sem a origem declarada não dá para escolher (aula 013).");
    try {
      const r = await api(`/api/projects/${ctx.pid()}/music/select`, { method: "POST", body: JSON.stringify({ id, license: declared }) });
      beats = r.beats;
      $("#musWarn").textContent = r.warning || "Trocou de trilha depois de montar? A montagem (etapa 8) precisa ser refeita.";
      toast(r.beats ? `Trilha escolhida · ${r.beats.impacts.length} impactos` : "Trilha escolhida (sem detecção de batidas)");
      await load();
    } catch (err) { toast(err.message); }
  }

  return {
    init() {
      $("#btnMusCopyPrompt").onclick = async () => {
        await navigator.clipboard.writeText($("#musPrompt").value);
        $("#musPromptOk").textContent = "copiado ✓"; setTimeout(() => ($("#musPromptOk").textContent = ""), 1500);
      };
      $("#btnMusGen").onclick = async () => {
        const body = { prompt: $("#musPrompt").value.trim(), duration: +$("#musDuration").value, count: +$("#musCount").value };
        let est = "Estimativa indisponível.";
        try { const c = await api(`/api/projects/${ctx.pid()}/music/generate/cost`, { method: "POST", body: JSON.stringify(body) }); if (c.total != null) est = `Estimativa: ${c.total} créditos.`; else if (c.error) est = `Estimativa indisponível (${c.error.slice(0, 120)}).`; } catch (e) { /* mantém indisponível */ }
        if (!confirm(`Gerar ${body.count} faixa(s) de ${body.duration}s via CLI? ${est} Isso gasta créditos.`)) return;
        try { await api(`/api/projects/${ctx.pid()}/music/generate`, { method: "POST", body: JSON.stringify(body) }); $("#btnMusGen").disabled = true; pollGen(); }
        catch (err) { toast(err.message); }
      };
      const drop = $("#musDrop");
      drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
      drop.addEventListener("dragleave", () => drop.classList.remove("over"));
      drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); uploadFiles(e.dataTransfer.files); });
      $("#musUpload").addEventListener("change", (e) => uploadFiles(e.target.files));
      $("#btnMusDownloads").onclick = async () => {
        try { const r = await api(`/api/projects/${ctx.pid()}/music/import/downloads`, { method: "POST", body: JSON.stringify({ since_minutes: +$("#musDlMinutes").value }) }); toast(`${r.added} novas de ${r.scanned} músicas recentes`); load(); }
        catch (err) { toast(err.message); }
      };
      $("#btnMusHistory").onclick = async () => {
        try { const r = await api(`/api/projects/${ctx.pid()}/music/import/history`, { method: "POST", body: JSON.stringify({}) }); toast(`${r.added} faixas de ${r.jobs} jobs`); load(); }
        catch (err) { toast(err.message); }
      };
      $("#musList").addEventListener("click", (e) => { const b = e.target.closest("button.pick"); if (b) pick(b.dataset.id); });
      $("#btnMusBeats").onclick = async () => {
        try { beats = await api(`/api/projects/${ctx.pid()}/music/beats`, { method: "POST", body: JSON.stringify({}) }); renderBeats(); toast(`${beats.impacts.length} impactos`); }
        catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      $("#musWarn").textContent = "";
      hfStatus(); loadPrompt(); load();
      const d = await api("/api/music/downloads-folder");
      $("#musDlFolder").textContent = d.folder + (d.exists ? "" : " (não encontrada)");
    },
  };
});
