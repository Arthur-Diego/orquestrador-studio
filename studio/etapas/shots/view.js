// Etapa 5 — Ângulos por cena (aula 011) + cena do produto (aula 013).
// Caminho principal: gerar na UI da Higgsfield e importar; o CLI é opcional e gasta créditos.
Studio.register("shots", (ctx) => {
  const { $, api, toast } = ctx;
  const base = () => `/api/projects/${ctx.pid()}/shots`;
  let scenes = [], scene = null, cands = [], order = [], prod = [], loggedIn = false;

  // ---------- CLI ----------
  async function hfStatus() {
    const s = await api("/api/higgsfield/status"), el = $("#shotsHf");
    loggedIn = !!s.logged_in;
    if (!s.installed) { el.textContent = "CLI: não instalado — gere na UI e importe"; el.className = "chip warn"; }
    else if (!s.logged_in) { el.textContent = "CLI: sem login (higgsfield auth login)"; el.className = "chip warn"; }
    else { el.textContent = `CLI: ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`; el.className = "chip ok"; }
    $("#btnShotsGen").disabled = !loggedIn;
  }

  // ---------- cenas ----------
  async function loadScenes() {
    if (!ctx.pid()) return;
    let r;
    try { r = await api(`${base()}/scenes`); }
    catch (err) { $("#sceneList").innerHTML = `<div class="empty">${err.message}</div>`; return; }
    scenes = r.scenes;
    $("#shotsWarn").textContent = r.warning;
    $("#shotsPalette").innerHTML = (r.palette.colors || []).map(c => `<span style="background:${c}" title="${c}"></span>`).join("")
      || `<span class="fine">sem mood/palette.json ainda (etapa 2)</span>`;
    $("#prodStatus").textContent = r.product_scene.selected ? "cena do produto salva"
      : r.product_scene.ref_ready ? "imagem 1 enviada" : "sem imagem de referência";
    $("#prodStatus").className = "chip " + (r.product_scene.selected ? "ok" : "mode");
    $("#sceneList").innerHTML = scenes.map(s =>
      `<div class="card ${scene === s.id ? "sel" : ""}" data-scene="${s.id}" tabindex="0" title="${(s.text || "").replace(/"/g, "'")}">
         ${s.base_ready ? `<img loading="lazy" src="${ctx.files(s.base)}" alt="">` : `<div class="empty">sem base</div>`}
         <span class="src">${s.id}</span>
         <span class="term">${s.candidates} cand. · ${s.selected} shot(s)</span></div>`).join("");
  }

  function sceneMeta() { return scenes.find(s => s.id === scene) || null; }

  async function openScene(id) {
    scene = id; order = [];
    const s = sceneMeta();
    $("#sceneTitle").textContent = `2. ${id}${s && s.text ? " — " + s.text : ""}`;
    $("#sceneStatus").textContent = s && s.base_ready ? "base pronta" : "prepare a base da cena";
    $("#sceneStatus").className = "chip " + (s && s.base_ready ? "ok" : "warn");
    const thumb = $("#baseThumb");
    if (s && s.base_ready) { thumb.src = ctx.files(s.base) + `?t=${Date.now()}`; thumb.classList.remove("hidden"); }
    else thumb.classList.add("hidden");
    await loadCands();
    await prompts();
  }

  async function prepareBase(source, file) {
    if (!scene) return toast("Abra uma cena primeiro.");
    try {
      if (file) {
        const fd = new FormData(); fd.append("file", file);
        const r = await fetch(`${base()}/scenes/${scene}/base/upload`, { method: "POST", body: fd });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
      } else {
        await api(`${base()}/scenes/${scene}/base`, { method: "POST", body: JSON.stringify({ source }) });
      }
      toast("Base da cena pronta"); await loadScenes(); await openScene(scene);
    } catch (err) { toast(err.message); }
  }

  // ---------- prompts ----------
  const editLines = () => $("#promptEdits").value.split("\n").map(t => t.trim()).filter(Boolean);

  async function prompts() {
    if (!scene) return;
    const kind = $("#promptKind").value;
    $("#editsBox").classList.toggle("hidden", kind !== "edit");
    const q = new URLSearchParams({
      kind, scale: $("#promptScale").value, angle: $("#promptAngle").value,
      realism: $("#promptRealism").checked, lens: $("#promptLens").value, aperture: $("#promptAperture").value,
      count: $("#shotsCount").value,
    });
    if ($("#promptSubject").value.trim()) q.set("subject", $("#promptSubject").value.trim());
    if (kind === "edit") { const e = editLines(); if (!e.length) { $("#shotsPrompts").innerHTML = `<div class="empty">Escreva ao menos uma modificação.</div>`; return; } e.forEach(v => q.append("edits", v)); }
    try {
      const r = await api(`${base()}/scenes/${scene}/prompts?${q}`);
      $("#shotsHint").textContent = `${r.ui_hint} Proporção ${r.aspect_ratio}. ${r.warning}`;
      $("#shotsPrompts").innerHTML = r.prompts.map((p, i) =>
        `<div class="prompt"><div class="row"><span class="eyebrow">${p.label}</span><button class="ghost copy" data-i="${i}">Copiar</button><span class="ok"></span></div><textarea data-i="${i}">${p.text}</textarea></div>`).join("");
    } catch (err) { toast(err.message); }
  }
  const promptTexts = () => [...document.querySelectorAll("#shotsPrompts textarea")].map(t => t.value.trim()).filter(Boolean);

  // ---------- candidatos ----------
  async function loadCands() {
    if (!scene) { cands = []; return renderCands(); }
    try { cands = (await api(`${base()}/scenes/${scene}/candidates`)).candidates; }
    catch (err) { cands = []; toast(err.message); }
    order = order.filter(id => cands.some(c => c.id === id));
    renderCands();
  }
  function renderCands() {
    $("#shotsCounts").textContent = `${cands.length} candidatos · ${order.length} escolhidos`;
    $("#btnShotsUpscale").disabled = !loggedIn || !order.length;
    $("#shotsGallery").innerHTML = cands.length ? cands.map(c => {
      const pos = order.indexOf(c.id);
      return `<div class="card ${pos >= 0 ? "sel" : ""}" data-id="${c.id}" tabindex="0" title="${(c.prompt || c.name || "").replace(/"/g, "'")}">
         <img loading="lazy" src="${ctx.files(c.thumb || c.file)}" alt="">
         <span class="src">${pos >= 0 ? "ordem " + (pos + 1) : c.source}</span>
         <span class="term">${c.role === "upscale" ? "upscale" : (c.upscaled ? "upscalado" : (c.model || c.name || ""))}</span></div>`;
    }).join("") : `<div class="empty">Nenhum candidato — gere na UI da Higgsfield e importe.</div>`;
  }

  async function upload(url, files, reload) {
    if (!files.length) return;
    const fd = new FormData(); [...files].forEach(f => fd.append("files", f));
    const r = await fetch(url, { method: "POST", body: fd });
    if (!r.ok) return toast((await r.json().catch(() => ({}))).detail || r.statusText);
    const added = (await r.json()).added;
    toast(added ? `${added} imagem(ns) importada(s)` : "Nada novo: já estavam importadas");
    await reload();
  }

  // ---------- job do CLI ----------
  async function pollJob() {
    const j = await api(`${base()}/job`);
    const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
    $("#shotsProgress").querySelector(".bar").style.width = pct + "%";
    $("#shotsLog").textContent = (j.log || []).join("\n");
    $("#shotsGenLog").textContent = j.state === "running" ? `${j.op || "job"} ${j.done}/${j.total} · ${j.added} imagens`
      : j.state === "error" ? "erro: " + j.error : j.state === "done" ? `concluído · ${j.added} imagens` : "";
    if (j.state === "running") setTimeout(pollJob, 3000);
    else { $("#btnShotsGen").disabled = !loggedIn; await loadCands(); await loadScenes(); }
  }

  // ---------- cena do produto ----------
  async function loadProd() {
    if (!ctx.pid()) return;
    try { prod = (await api(`${base()}/product/candidates`)).candidates; }
    catch { prod = []; }
    $("#prodGallery").innerHTML = prod.length ? prod.map(c =>
      `<div class="card ${c.selected ? "sel" : ""}" data-id="${c.id}" tabindex="0" title="${(c.prompt || "").replace(/"/g, "'")}">
         <img loading="lazy" src="${ctx.files(c.thumb || c.file)}" alt=""><span class="src">${c.source}</span>
         <span class="term">clique para salvar como cena do produto</span></div>`).join("")
      : `<div class="empty">Envie a imagem 1, rode as duas instruções na Higgsfield e importe o resultado.</div>`;
  }

  return {
    init() {
      $("#btnShotsReload").onclick = () => { loadScenes(); loadProd(); };
      $("#sceneList").addEventListener("click", e => { const c = e.target.closest(".card"); if (c) { openScene(c.dataset.scene); loadScenes(); } });
      $("#btnPrepBase").onclick = () => prepareBase("storyboard");
      $("#btnPrepBaseCampaign").onclick = () => prepareBase("base");
      $("#baseUpload").addEventListener("change", e => prepareBase("upload", e.target.files[0]));

      ["#promptKind", "#promptScale", "#promptAngle", "#promptRealism", "#promptLens", "#promptAperture"]
        .forEach(sel => $(sel).addEventListener("change", prompts));
      $("#btnPrompts").onclick = prompts;
      $("#shotsPrompts").addEventListener("click", async e => {
        const b = e.target.closest("button.copy"); if (!b) return;
        await navigator.clipboard.writeText($(`#shotsPrompts textarea[data-i="${b.dataset.i}"]`).value);
        b.parentElement.querySelector(".ok").textContent = "copiado ✓";
        setTimeout(() => b.parentElement.querySelector(".ok").textContent = "", 1500);
      });

      const drop = $("#shotsDrop");
      drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
      drop.addEventListener("dragleave", () => drop.classList.remove("over"));
      drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); upload(`${base()}/scenes/${scene}/import/upload`, e.dataTransfer.files, loadCands); });
      $("#shotsUpload").addEventListener("change", e => upload(`${base()}/scenes/${scene}/import/upload`, e.target.files, loadCands));
      $("#btnShotsDownloads").onclick = async () => {
        try { const r = await api(`${base()}/scenes/${scene}/import/downloads`, { method: "POST", body: JSON.stringify({ since_minutes: +$("#shotsDlMinutes").value }) }); toast(`${r.added} novas de ${r.scanned} recentes`); loadCands(); }
        catch (err) { toast(err.message); }
      };
      $("#btnShotsHistory").onclick = async () => {
        try { const r = await api(`${base()}/scenes/${scene}/import/history`, { method: "POST", body: JSON.stringify({}) }); toast(`${r.added} imagens de ${r.jobs} jobs`); loadCands(); }
        catch (err) { toast(err.message); }
      };

      $("#btnShotsGen").onclick = async () => {
        const ps = promptTexts(); if (!ps.length) return toast("Gere o prompt antes.");
        const count = +$("#shotsCount").value;
        let est = "Estimativa indisponível.";
        try { const c = await api(`${base()}/scenes/${scene}/cost`, { method: "POST", body: JSON.stringify({ prompts: ps, count }) }); if (c.total != null) est = `Estimativa: ${c.total} créditos.`; } catch { /* mantém indisponível */ }
        if (!confirm(`Gerar ${ps.length} prompt(s) × ${count} imagens via CLI? ${est} Isso gasta créditos. Na interface da Higgsfield é ilimitado.`)) return;
        try { await api(`${base()}/scenes/${scene}/generate`, { method: "POST", body: JSON.stringify({ prompts: ps, count }) }); $("#btnShotsGen").disabled = true; pollJob(); }
        catch (err) { toast(err.message); }
      };
      $("#btnShotsUpscale").onclick = async () => {
        const id = order[order.length - 1]; if (!id) return;
        try { await api(`${base()}/scenes/${scene}/upscale`, { method: "POST", body: JSON.stringify({ id }) }); pollJob(); }
        catch (err) { toast(err.message); }
      };

      $("#shotsGallery").addEventListener("click", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id, i = order.indexOf(id);
        i >= 0 ? order.splice(i, 1) : order.push(id);
        renderCands();
      });
      $("#shotsGallery").addEventListener("dblclick", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = cands.find(x => x.id === card.dataset.id); window.open(ctx.files(c.file), "_blank");
      });
      $("#btnShotsSave").onclick = async () => {
        if (!scene) return toast("Abra uma cena primeiro.");
        try {
          const up = $("#shotsUpscaled").checked;
          const r = await api(`${base()}/scenes/${scene}/select`, { method: "POST", body: JSON.stringify({ shots: order.map(id => ({ id, upscaled: up })) }) });
          toast(`${r.shots.length} frame(s) salvos em ${scene}`); loadCands(); loadScenes();
        } catch (err) { toast(err.message); }
      };

      $("#prodRefUpload").addEventListener("change", async e => {
        const f = e.target.files[0]; if (!f) return;
        const fd = new FormData(); fd.append("file", f);
        const r = await fetch(`${base()}/product/ref`, { method: "POST", body: fd });
        if (!r.ok) return toast((await r.json().catch(() => ({}))).detail || r.statusText);
        toast("Imagem 1 salva"); loadScenes(); prodPrompts();
      });
      const prodPrompts = async () => {
        try {
          const r = await api(`${base()}/product/prompts`);
          $("#prodPrompts").innerHTML = `<p class="fine">${r.ui_hint}</p>` + r.prompts.map((p, i) =>
            `<div class="prompt"><div class="row"><span class="eyebrow">${p.label}</span></div><textarea data-i="${i}">${p.text}</textarea></div>`).join("");
        } catch (err) { $("#prodPrompts").innerHTML = `<div class="empty">${err.message}</div>`; }
      };
      $("#btnProdPrompts").onclick = prodPrompts;
      const pdrop = $("#prodDrop");
      pdrop.addEventListener("dragover", e => { e.preventDefault(); pdrop.classList.add("over"); });
      pdrop.addEventListener("drop", e => { e.preventDefault(); pdrop.classList.remove("over"); upload(`${base()}/product/import/upload`, e.dataTransfer.files, loadProd); });
      $("#prodUpload").addEventListener("change", e => upload(`${base()}/product/import/upload`, e.target.files, loadProd));
      $("#btnProdDownloads").onclick = async () => {
        try { const r = await api(`${base()}/product/import/downloads`, { method: "POST", body: JSON.stringify({}) }); toast(`${r.added} novas`); loadProd(); }
        catch (err) { toast(err.message); }
      };
      $("#prodGallery").addEventListener("click", async e => {
        const card = e.target.closest(".card"); if (!card) return;
        try { await api(`${base()}/product/select`, { method: "POST", body: JSON.stringify({ id: card.dataset.id }) }); toast("Cena do produto salva"); loadProd(); loadScenes(); }
        catch (err) { toast(err.message); }
      });
      $("#btnProdClear").onclick = async () => {
        try { await api(`${base()}/product/select`, { method: "POST", body: JSON.stringify({ id: null }) }); toast("Cena do produto removida"); loadProd(); loadScenes(); }
        catch (err) { toast(err.message); }
      };

      $("#btnBoard").onclick = async () => {
        try { $("#boardOut").textContent = JSON.stringify(await api(`${base()}/storyboard`), null, 1); }
        catch (err) { $("#boardOut").textContent = err.message; }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      scene = null; order = [];
      hfStatus(); await loadScenes(); loadProd();
      const d = await api("/api/shots/downloads-folder");
      $("#shotsDlFolder").textContent = d.folder + (d.exists ? "" : " (não encontrada)");
      if (scenes.length) openScene(scenes[0].id);
    },
  };
});
