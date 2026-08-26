// Etapa 5 — Ângulos por cena (aula 011) + cena do produto (aula 013).
// Caminho principal: gerar na UI da Higgsfield e importar; o CLI é opcional e gasta créditos.
// Ordem da aula: acertar a BASE da cena (edição numerada) → promover o resultado a base →
// Multi Shot → escolher → upscale → ordenar. Componentes compartilhados vêm de `Studio.ui`.
Studio.register("shots", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const esc = (s) => ui.esc(s);
  const base = () => `/api/projects/${ctx.pid()}/shots`;
  let scenes = [], scene = null, cands = [], order = [], prod = [], loggedIn = false;
  let cameras = [], job = null;

  // "cena01" → "cena 01" (rótulo mono do card da cena, como no protótipo).
  const sceneLabel = (id) => String(id || "").replace(/^cena/, "cena ");

  // ---------- cenas ----------
  async function loadScenes() {
    if (!ctx.pid()) return;
    let r;
    try { r = await api(`${base()}/scenes`); }
    catch (err) { $("#sceneList").innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
    scenes = r.scenes;
    $("#shotsWarn").textContent = r.warning;
    $("#shotsRatio").textContent = `proporção: ${r.aspect_ratio || "16:9"}`;
    if (r.product_note) $("#prodNote").textContent = r.product_note;
    const cores = (r.palette.colors || []).map(c => `<span style="background:${esc(c)}" title="${esc(c)}"></span>`).join("");
    $("#shotsPalette").innerHTML = cores
      ? cores + `<span class="lbl">paleta do mood</span>`
      : `<span class="lbl">sem mood/palette.json ainda (etapa 2)</span>`;
    $("#prodStatus").textContent = r.product_scene.selected ? "cena do produto salva"
      : r.product_scene.ref_ready ? "imagem 1 enviada" : "sem imagem de referência";
    $("#prodStatus").className = "chip " + (r.product_scene.selected ? "ok" : "mode");
    // Card de cena do protótipo: `.rowcard` em coluna (thumb 16/9 + "cena NN" + chip de upscale).
    // `.cur` = cena aberta; `.sel` = cena que já tem frames salvos; o resto vai no `title`.
    $("#sceneList").innerHTML = scenes.map(s => {
      const falta = s.selected > 0 && s.upscaled < s.selected;
      const dica = `${s.text ? s.text + " · " : ""}${s.candidates} candidatos · ${s.selected} shot(s) escolhidos`;
      return `<div class="rowcard sh-scene ${s.selected ? "sel" : ""} ${scene === s.id ? "cur" : ""}" data-scene="${esc(s.id)}" tabindex="0" title="${esc(dica)}">
         <div class="thumb">${s.base_ready ? `<img loading="lazy" src="${esc(ctx.files(s.base))}" alt="">` : `<div class="empty">sem base</div>`}</div>
         <div class="row"><span class="mono sh-scene-id">${esc(sceneLabel(s.id))}</span>
           <span class="chip sm ${falta ? "warn" : ""}">${s.upscaled}/${s.selected} upscalados</span></div></div>`;
    }).join("") || `<div class="empty">Nenhuma cena — escreva a história na etapa 4.</div>`;
    const md = $("#shotsMd");
    const anySel = scenes.some(s => s.selected);
    md.classList.toggle("hidden", !anySel);
    if (anySel) md.href = ctx.files("shots/storyboard.md");
  }

  function sceneMeta() { return scenes.find(s => s.id === scene) || null; }

  async function openScene(id) {
    scene = id; order = [];
    const s = sceneMeta();
    $("#sceneTitle").textContent = `${sceneLabel(id).replace("cena", "Cena")} — escolher e ordenar`;
    $("#sceneText").textContent = s && s.text ? s.text : "";
    $("#sceneStatus").textContent = s && s.base_ready ? "base pronta" : "prepare a base da cena";
    $("#sceneStatus").className = "chip " + (s && s.base_ready ? "ok" : "warn");
    const thumb = $("#baseThumb");
    if (s && s.base_ready) { thumb.src = ctx.files(s.base) + `?t=${Date.now()}`; thumb.classList.remove("hidden"); }
    else thumb.classList.add("hidden");
    await loadCands();
    await prompts();
  }

  async function prepareBase(source, file, id) {
    if (!scene) return toast("Abra uma cena primeiro.");
    try {
      if (file) {
        await ui.upload(`${base()}/scenes/${scene}/base/upload`, [file], "file");
      } else {
        await api(`${base()}/scenes/${scene}/base`, { method: "POST", body: JSON.stringify({ source, id: id || null }) });
      }
      toast(source === "candidate" ? "Este resultado é a nova base da cena" : "Base da cena pronta");
      await loadScenes(); await openScene(scene); ctx.guide();
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
    // O bloco de câmera é padrão no ângulo e opt-in na edição (aula 011 · auditoria 5.3):
    // mandamos `camera` só quando ele está ligado, e o backend decide onde entra.
    if ($("#promptRealism").checked && $("#promptCamera").value) q.set("camera", $("#promptCamera").value);
    if ($("#promptSubject").value.trim()) q.set("subject", $("#promptSubject").value.trim());
    if (kind === "edit") { const e = editLines(); if (!e.length) { $("#shotsPrompts").innerHTML = `<div class="empty">Escreva ao menos uma modificação.</div>`; return; } e.forEach(v => q.append("edits", v)); }
    try {
      const r = await api(`${base()}/scenes/${scene}/prompts?${q}`);
      renderCameras(r.cameras, r.camera);
      if (r.focus_examples) $("#focusExamples").textContent = "Enquadramentos da aula: " + r.focus_examples.join(" · ");
      $("#shotsHint").textContent = `${r.ui_hint} Proporção ${r.aspect_ratio}. ${r.warning}`;
      $("#shotsPrompts").innerHTML = r.prompts.map((p, i) =>
        `<div class="prompt"><div class="row"><span class="eyebrow">${esc(p.label)}</span><button type="button" class="link copy" data-i="${i}">Copiar</button><span class="ok"></span></div><textarea data-i="${i}">${esc(p.text)}</textarea></div>`).join("");
    } catch (err) { toast(err.message); }
  }
  function renderCameras(list, current) {
    if (!list || !list.length) return;
    if (cameras.length === list.length && $("#promptCamera").options.length) return;   // não recria a cada prompt
    cameras = list;
    $("#promptCamera").innerHTML = list.map(c =>
      `<option value="${esc(c.id)}" ${c.id === current ? "selected" : ""}>${esc(c.label)}</option>`).join("");
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
    const faltam = order.filter(id => { const c = cands.find(x => x.id === id); return c && !c.upscaled; }).length;
    $("#shotsCounts").textContent = `${cands.length} candidatos · ${order.length} escolhidos`
      + (order.length ? ` · ${order.length - faltam}/${order.length} upscalados` : "");
    $("#btnShotsUpscale").disabled = !loggedIn || !order.length;
    $("#shotsGallery").innerHTML = cands.length ? cands.map(c => {
      const pos = order.indexOf(c.id);
      // `data-ord` faz o check do tile virar o número da ordem (`.card.sel[data-ord]::after` do shell).
      return `<div class="card ${pos >= 0 ? "sel" : ""}"${pos >= 0 ? ` data-ord="${pos + 1}"` : ""} data-id="${esc(c.id)}" tabindex="0" title="${esc(c.prompt || c.name || "")}">
         <img loading="lazy" src="${esc(ctx.files(c.thumb || c.file))}" alt="">
         <span class="src">${esc(c.source)}</span>
         <span class="up${c.upscaled ? " ok" : ""}">${c.upscaled ? "upscalado 2x" : "sem upscale"}</span>
         <button type="button" class="link asBase sh-tilebtn" data-base="${esc(c.id)}">Usar como base da cena</button></div>`;
    }).join("") : `<div class="empty">Nenhum candidato — gere na UI da Higgsfield e importe.</div>`;
  }

  async function importFiles(url, files, reload) {
    if (!files.length) return;
    try {
      const r = await ui.upload(url, files);
      toast(r.added ? `${r.added} imagem(ns) importada(s)` : "Nada novo: já estavam importadas");
      await reload(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  // ---------- job do CLI ----------
  function watchJob() {
    if (job) job.stop();
    job = ui.poll(async () => {
      const j = await api(`${base()}/job`);
      const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
      $("#shotsProgress").querySelector(".bar").style.width = pct + "%";
      $("#shotsLog").textContent = (j.log || []).join("\n");
      $("#shotsGenLog").textContent = j.state === "running" ? `${j.op || "job"} ${j.done}/${j.total} · ${j.added} imagens`
        : j.state === "error" ? "erro: " + j.error : j.state === "done" ? `concluído · ${j.added} imagens` : "";
      if (j.state === "running") return;
      $("#btnShotsGen").disabled = !loggedIn;
      await loadCands(); await loadScenes(); ctx.guide();
      return false;
    }, 3000);
  }

  // ---------- cena do produto ----------
  async function loadProd() {
    if (!ctx.pid()) return;
    try { prod = (await api(`${base()}/product/candidates`)).candidates; }
    catch { prod = []; }
    $("#prodGallery").innerHTML = prod.length ? prod.map(c =>
      `<div class="card ${c.selected ? "sel" : ""}" data-id="${esc(c.id)}" tabindex="0" title="${esc(c.prompt || "")}">
         <img loading="lazy" src="${esc(ctx.files(c.thumb || c.file))}" alt=""><span class="src">${esc(c.source)}</span>
         <span class="term">clique para salvar como cena do produto</span>
         <span class="up${c.upscaled ? " ok" : ""}">${c.upscaled ? "upscalado 2x" : "sem upscale"}</span></div>`).join("")
      : `<div class="empty">Envie a imagem 1, rode as duas instruções na Higgsfield e importe o resultado.</div>`;
  }

  return {
    init() {
      $("#btnShotsReload").onclick = () => { loadScenes(); loadProd(); ctx.guide(); };
      $("#sceneList").addEventListener("click", e => { const c = e.target.closest("[data-scene]"); if (c) { openScene(c.dataset.scene); loadScenes(); } });
      $("#btnPrepBase").onclick = () => prepareBase("storyboard");
      $("#btnPrepBaseCampaign").onclick = () => prepareBase("base");
      $("#baseUpload").addEventListener("change", e => { if (e.target.files[0]) prepareBase("upload", e.target.files[0]); });

      ["#promptKind", "#promptScale", "#promptAngle", "#promptRealism", "#promptLens", "#promptAperture", "#promptCamera"]
        .forEach(sel => $(sel).addEventListener("change", prompts));
      $("#btnPrompts").onclick = prompts;
      $("#shotsPrompts").addEventListener("click", async e => {
        const b = e.target.closest("button.copy"); if (!b) return;
        await navigator.clipboard.writeText($(`#shotsPrompts textarea[data-i="${b.dataset.i}"]`).value);
        b.parentElement.querySelector(".ok").textContent = "copiado ✓";
        setTimeout(() => b.parentElement.querySelector(".ok").textContent = "", 1500);
      });

      ui.drop($("#shotsDrop"), files => importFiles(`${base()}/scenes/${scene}/import/upload`, files, loadCands));
      $("#btnShotsDownloads").onclick = async () => {
        try { const r = await api(`${base()}/scenes/${scene}/import/downloads`, { method: "POST", body: JSON.stringify({ since_minutes: +$("#shotsDlMinutes").value }) }); toast(`${r.added} novas de ${r.scanned} recentes`); await loadCands(); ctx.guide(); }
        catch (err) { toast(err.message); }
      };
      $("#btnShotsHistory").onclick = async () => {
        try { const r = await api(`${base()}/scenes/${scene}/import/history`, { method: "POST", body: JSON.stringify({}) }); toast(`${r.added} imagens de ${r.jobs} jobs`); await loadCands(); ctx.guide(); }
        catch (err) { toast(err.message); }
      };

      $("#btnShotsGen").onclick = async () => {
        const ps = promptTexts(); if (!ps.length) return toast("Gere o prompt antes.");
        const count = +$("#shotsCount").value;
        const ok = await ui.confirmCost(
          () => api(`${base()}/scenes/${scene}/cost`, { method: "POST", body: JSON.stringify({ prompts: ps, count }) }),
          `Gerar ${ps.length} prompt(s) × ${count} imagens via CLI`);
        if (!ok) return;
        try { await api(`${base()}/scenes/${scene}/generate`, { method: "POST", body: JSON.stringify({ prompts: ps, count }) }); $("#btnShotsGen").disabled = true; watchJob(); }
        catch (err) { toast(err.message); }
      };
      $("#btnShotsUpscale").onclick = async () => {
        const id = order[order.length - 1]; if (!id) return;
        try { await api(`${base()}/scenes/${scene}/upscale`, { method: "POST", body: JSON.stringify({ id }) }); watchJob(); }
        catch (err) { toast(err.message); }
      };

      $("#shotsGallery").addEventListener("click", e => {
        const asBase = e.target.closest("button.asBase");
        if (asBase) return prepareBase("candidate", null, asBase.dataset.base);
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
          // O upscale do CLI já marca o candidato; o checkbox cobre quem fez o upscale na UI.
          const up = $("#shotsUpscaled").checked;
          const shots = order.map(id => {
            const c = cands.find(x => x.id === id);
            return { id, upscaled: !!(c && c.upscaled) || up };
          });
          const r = await api(`${base()}/scenes/${scene}/select`, { method: "POST", body: JSON.stringify({ shots }) });
          toast(r.warning || `${r.shots.length} frame(s) salvos em ${scene} · storyboard.md atualizado`);
          await loadCands(); await loadScenes(); ctx.guide();
        } catch (err) { toast(err.message); }
      };

      $("#prodRefUpload").addEventListener("change", async e => {
        const f = e.target.files[0]; if (!f) return;
        try {
          await ui.upload(`${base()}/product/ref`, [f], "file");
          toast("Imagem 1 salva"); await loadScenes(); prodPrompts(); ctx.guide();
        } catch (err) { toast(err.message); }
      });
      const prodPrompts = async () => {
        try {
          const r = await api(`${base()}/product/prompts`);
          $("#prodPrompts").innerHTML = `<p class="fine">${esc(r.note || "")}</p><p class="fine">${esc(r.ui_hint)}</p>` + r.prompts.map((p, i) =>
            `<div class="prompt"><div class="row"><span class="eyebrow">${esc(p.label)}</span></div><textarea data-i="${i}">${esc(p.text)}</textarea></div>`).join("");
        } catch (err) { $("#prodPrompts").innerHTML = `<div class="empty">${esc(err.message)}</div>`; }
      };
      $("#btnProdPrompts").onclick = prodPrompts;
      ui.drop($("#prodDrop"), files => importFiles(`${base()}/product/import/upload`, files, loadProd));
      $("#btnProdDownloads").onclick = async () => {
        try { const r = await api(`${base()}/product/import/downloads`, { method: "POST", body: JSON.stringify({}) }); toast(`${r.added} novas`); await loadProd(); ctx.guide(); }
        catch (err) { toast(err.message); }
      };
      $("#prodGallery").addEventListener("click", async e => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = prod.find(x => x.id === card.dataset.id);
        try {
          await api(`${base()}/product/select`, { method: "POST", body: JSON.stringify({ id: card.dataset.id, upscaled: !!(c && c.upscaled) }) });
          toast("Cena do produto salva"); await loadProd(); await loadScenes(); ctx.guide();
        } catch (err) { toast(err.message); }
      });
      $("#btnProdClear").onclick = async () => {
        try { await api(`${base()}/product/select`, { method: "POST", body: JSON.stringify({ id: null }) }); toast("Cena do produto removida"); await loadProd(); await loadScenes(); ctx.guide(); }
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
      scene = null; order = []; cameras = [];
      $("#sceneText").textContent = "";
      ui.hfChip($("#shotsHf")).then(s => { loggedIn = !!s.logged_in; $("#btnShotsGen").disabled = !loggedIn; });
      await loadScenes(); loadProd();
      const d = await api("/api/shots/downloads-folder");
      $("#shotsDlFolder").textContent = d.folder + (d.exists ? "" : " (não encontrada)");
      if (scenes.length) await openScene(scenes[0].id);
      ui.renderGuide("shots");
    },
    destroy() { if (job) { job.stop(); job = null; } },
  };
});
