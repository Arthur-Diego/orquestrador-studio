// Etapa 4 — Storyboard guiado por PRÉ-ROTEIRO (ADR-018). Fluxo: base → fotos-semente + pré-roteiro
// → por cena (semente → prompt realista → foto → frames → ordenar). Reusa Studio.ui (confirmCost,
// progressJob, progress, tile, modal, drop) e o gate de custo/saldo global (ADR-016). Os frames e o
// contrato de saída (storyboard/storyboard.json) vêm do motor de ângulos (angles.py) por baixo.
Studio.register("storyboard", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = window.Studio.ui;
  const esc = (s) => ui.esc(s);
  const pid = () => ctx.pid();
  const files = (p) => ctx.files(p);
  const base = () => `/api/projects/${encodeURIComponent(pid())}/storyboard`;

  let overview = null, seeds = [], prescript = null, claudeOk = false;
  const expanded = new Set();          // cenas com o card aberto
  const order = {};                    // scene -> [cand ids] ordenados
  const candCache = {};                // scene -> candidates
  let poller = null;

  const ARC_LABEL = { comeco: "Começo", descoberta: "Descoberta", acao: "Ação", desfecho: "Desfecho" };

  // ---------- carga ----------
  async function load() {
    if (!pid()) return;
    const [ov, sd, pre] = await Promise.allSettled([
      api(`${base()}/overview`), api(`${base()}/seeds`), api(`${base()}/prescript`),
    ]);
    overview = ov.status === "fulfilled" ? ov.value : null;
    seeds = sd.status === "fulfilled" ? (sd.value.seeds || []) : [];
    prescript = pre.status === "fulfilled" ? pre.value : null;
    claudeOk = !!(prescript && prescript.available_claude);
    render();
  }

  function render() {
    const hasBase = overview && overview.base_final;
    // `.empty-state` tem display:flex no CSS, que vence o atributo [hidden] — por isso togglamos
    // o display direto (o #sbFlow é um div comum e o [hidden] basta, mas mantemos os dois iguais).
    $("#sbNoBase").style.display = hasBase ? "none" : "";
    $("#sbFlow").style.display = hasBase ? "" : "none";
    const goBase = $("#sbNoBase [data-go]");
    if (goBase) goBase.onclick = () => window.Studio.go("base");
    if (!hasBase) return;
    renderSeeds();
    renderPrescript();
    renderScenes();
    ctx.guide();
  }

  // ---------- 01 · sementes + pré-roteiro ----------
  function renderSeeds() {
    $("#sbSeedsChip").textContent = `${seeds.length} foto(s)-semente`;
    const cl = $("#sbClaude");
    cl.textContent = claudeOk ? "bot: claude ok" : "bot: sem claude (usa template)";
    cl.className = "chip " + (claudeOk ? "ok" : "warn");
    $("#sbSeedGallery").innerHTML = seeds.map((s) =>
      `<div class="card" title="foto-semente"><img loading="lazy" src="${esc(files(s.url))}" alt="">
        <span class="src">semente</span></div>`).join("")
      || `<div class="empty">Ainda não há fotos-semente. Gere o 1º multishot da base.</div>`;

    $("#sbBtnSeeds").onclick = async () => {
      const count = clamp($("#sbSeedCount").value, 1, 8, 4);
      const ok = await ui.confirmCost({ action: "storyboard.multishot", pid: pid(), count, label: `Gerar ${count} foto(s)-semente` });
      if (!ok) return;
      await runJob(`${base()}/seeds/generate`, { count }, "Gerar fotos-semente");
      await load();
    };
    $("#sbBtnPrescript").onclick = async () => {
      const n = clamp($("#sbSceneCount").value, 3, 10, 4);
      const p = ui.progress({ title: "Gerar pré-roteiro", subtitle: "O bot lê a base + as sementes e propõe as cenas" });
      p.step("Escrevendo o pré-roteiro…");
      try {
        const r = await api(`${base()}/prescript/generate`, { method: "POST", body: JSON.stringify({ n_scenes: n }) });
        p.ok(`${r.scenes.length} cenas (${r.source === "claude" ? "Claude" : "template"})`);
        setTimeout(() => p.close(), 800);
        await load();
      } catch (e) { p.fail((e && e.message) || String(e)); }
    };
  }

  // ---------- 02 · pré-roteiro editável (drag para reordenar) ----------
  function renderPrescript() {
    const scenes = (prescript && prescript.scenes) || [];
    $("#sbPrescript").hidden = scenes.length === 0;
    if (!scenes.length) return;
    $("#sbPreSource").textContent = prescript.source ? `fonte: ${prescript.source === "claude" ? "Claude" : "template"}` : "editado";
    const list = $("#sbSceneList");
    list.innerHTML = scenes.map((s, i) => `
      <li class="sb-scene-edit" draggable="true" data-i="${i}">
        <span class="sb-drag" title="Arraste para reordenar" aria-hidden="true">⠿</span>
        <span class="n">${i + 1}</span>
        <div class="col grow">
          <div class="row wrap g6">
            <input class="sb-title" value="${esc(s.title || "")}" placeholder="título curto">
            <span class="chip info">${esc(ARC_LABEL[s.arc] || s.arc || "")}</span>
          </div>
          <textarea class="sb-text" rows="2" placeholder="descrição do plano">${esc(s.text || "")}</textarea>
        </div>
      </li>`).join("");
    ui.autosize(list.querySelectorAll(".sb-text"));
    wireDrag(list, ".sb-scene-edit", (from, to) => {
      const arr = collectPrescript();
      const [m] = arr.splice(from, 1); arr.splice(to, 0, m);
      prescript.scenes = arr.map((x, i) => ({ ...x, arc: x.arc }));
      renderPrescript();
    });
    $("#sbBtnPreSave").onclick = async () => {
      try {
        const r = await api(`${base()}/prescript`, { method: "PUT", body: JSON.stringify({ scenes: collectPrescript() }) });
        prescript.scenes = r.scenes; toast("Pré-roteiro salvo");
        await load();
      } catch (e) { toast(e.message); }
    };
  }
  function collectPrescript() {
    return [...$("#sbSceneList").querySelectorAll(".sb-scene-edit")].map((li, i) => {
      const s = (prescript.scenes || [])[+li.dataset.i] || {};
      return { title: li.querySelector(".sb-title").value.trim(), text: li.querySelector(".sb-text").value.trim(), arc: s.arc };
    });
  }

  // ---------- 03 · cenas ----------
  function renderScenes() {
    const scenes = (overview && overview.scenes) || [];
    $("#sbScenes").hidden = scenes.length === 0;
    const withFrames = scenes.filter((s) => s.frames > 0).length;
    $("#sbScenesChip").textContent = `${withFrames}/${scenes.length} cenas com frames`;
    $("#sbSceneCards").innerHTML = scenes.map(sceneCard).join("");
    scenes.forEach(wireScene);
  }

  function statusPills(s) {
    const p = (ok, label) => `<span class="chip ${ok ? "ok" : "todo"}">${ok ? "✓" : "○"} ${label}</span>`;
    return p(s.seed_ready, "semente") + p(s.prompt_ready, "prompt") + p(s.photo_ready, "foto") + p(s.frames > 0, `frames ${s.frames || 0}`);
  }

  function sceneCard(s) {
    const open = expanded.has(s.id);
    return `<article class="sb-card${open ? " open" : ""}" data-scene="${esc(s.id)}">
      <button class="sb-card-head" type="button" data-toggle="${esc(s.id)}">
        <span class="n">${String(s.n).padStart(2, "0")}</span>
        <span class="col grow"><b>${esc(s.title || s.id)}</b><span class="fine">${esc(ARC_LABEL[s.arc] || "")} · ${esc((s.text || "").slice(0, 90))}</span></span>
        <span class="row g6 pills">${statusPills(s)}</span>
        <span class="caret">${open ? "▾" : "▸"}</span>
      </button>
      ${open ? `<div class="sb-card-body" id="sbBody-${esc(s.id)}"></div>` : ""}
    </article>`;
  }

  function wireScene(s) {
    const head = $(`[data-toggle="${cssq(s.id)}"]`);
    if (head) head.onclick = () => { if (expanded.has(s.id)) expanded.delete(s.id); else expanded.add(s.id); renderScenes(); if (expanded.has(s.id)) fillScene(s.id); };
    if (expanded.has(s.id)) fillScene(s.id);
  }

  async function fillScene(scene) {
    const body = $(`#sbBody-${cssq(scene)}`);
    if (!body) return;
    const s = (overview.scenes || []).find((x) => x.id === scene) || {};
    const seedImg = s.seed_ready ? `<img class="sb-thumb" src="${esc(files(`storyboard/${scene}/seed.png`))}" alt="">` : `<span class="sb-none">sem semente</span>`;
    const photoImg = s.photo_ready ? `<img class="sb-thumb" src="${esc(files(`storyboard/${scene}/base.png`))}" alt="">` : `<span class="sb-none">sem foto</span>`;
    body.innerHTML = `
      <div class="sb-step">
        <div class="sb-step-h"><b>c. Semente</b><button class="ghost sm" data-seed="${esc(scene)}">Escolher semente</button></div>
        <div class="sb-seed">${seedImg}</div>
      </div>
      <div class="sb-step">
        <div class="sb-step-h"><b>d. Prompt realista</b><button class="ghost sm" data-prompt="${esc(scene)}"${s.seed_ready ? "" : " disabled"}>${s.prompt_ready ? "Refazer prompt" : "Gerar prompt"}</button></div>
        <div class="sb-prompt" id="sbPrompt-${esc(scene)}"></div>
      </div>
      <div class="sb-step">
        <div class="sb-step-h"><b>e. Foto da cena</b><button class="primary sm" data-photo="${esc(scene)}"${s.prompt_ready ? "" : " disabled"}>${s.photo_ready ? "Refazer foto" : "Gerar foto (≈2 cr)"}</button></div>
        <div class="sb-photo">${photoImg}</div>
      </div>
      <div class="sb-step">
        <div class="sb-step-h"><b>f/g. Frames (multishot) e ordem</b>
          <span class="row g6"><label class="inline">nº <input type="number" class="sb-fcount" value="4" min="1" max="8"></label>
          <button class="primary sm" data-frames="${esc(scene)}"${s.photo_ready ? "" : " disabled"}>Gerar frames</button>
          <button class="ghost sm" data-saveorder="${esc(scene)}">Salvar ordem</button></span>
        </div>
        <div class="sb-order" id="sbOrder-${esc(scene)}"></div>
        <div class="sb-frames gallery sm" id="sbFrames-${esc(scene)}"></div>
      </div>`;
    // prompt atual
    loadPrompt(scene);
    // frames
    await loadCandidates(scene);
    // wire buttons
    body.querySelector(`[data-seed]`).onclick = () => seedModal(scene);
    body.querySelector(`[data-prompt]`).onclick = () => genPrompt(scene);
    body.querySelector(`[data-photo]`).onclick = () => genPhoto(scene);
    body.querySelector(`[data-frames]`).onclick = () => genFrames(scene, body);
    body.querySelector(`[data-saveorder]`).onclick = () => saveOrder(scene);
  }

  // -- semente --
  function seedModal(scene) {
    if (!seeds.length) { toast("Gere as fotos-semente primeiro (painel 01)"); return; }
    const tiles = seeds.map((sd) => `<div class="card" data-pick="${esc(sd.id)}" tabindex="0" title="usar esta semente">
      <img loading="lazy" src="${esc(files(sd.url))}" alt=""></div>`).join("");
    const m = ui.modal({ title: "Escolher a semente da cena", subtitle: "Sugerida pelo pré-roteiro ou escolha manual",
      html: `<p class="fine">Clique numa foto-semente para usá-la como base desta cena.</p><div class="grid ms-grid">${tiles}</div>` });
    m.el.querySelectorAll("[data-pick]").forEach((c) => { c.onclick = async () => {
      try { await api(`${base()}/scenes/${encodeURIComponent(scene)}/seed`, { method: "POST", body: JSON.stringify({ seed_id: c.dataset.pick }) });
        m.close(); toast("Semente escolhida"); await load(); }
      catch (e) { toast(e.message); }
    }; });
  }

  // -- prompt --
  async function loadPrompt(scene) {
    const box = $(`#sbPrompt-${cssq(scene)}`);
    if (!box) return;
    const s = (overview.scenes || []).find((x) => x.id === scene) || {};
    if (!s.prompt_ready) { box.innerHTML = `<span class="sb-none">gere o prompt realista (grátis, via Claude)</span>`; return; }
    try {
      const r = await api(`${base()}/scenes/${encodeURIComponent(scene)}/prompt`);
      box.innerHTML = `<textarea class="sb-prompt-t" rows="4">${esc(r.prompt || "")}</textarea>
        <div class="row g6"><span class="chip mode">fonte: ${esc(r.source || "")}</span>
        <button class="ghost sm" data-savep="${esc(scene)}">Salvar prompt</button></div>`;
      ui.autosize(box.querySelector("textarea"));
      box.querySelector("[data-savep]").onclick = async () => {
        try { await api(`${base()}/scenes/${encodeURIComponent(scene)}/prompt`, { method: "PUT", body: JSON.stringify({ prompt: box.querySelector("textarea").value.trim() }) }); toast("Prompt salvo"); }
        catch (e) { toast(e.message); }
      };
    } catch (e) { box.innerHTML = `<span class="sb-none">${esc(e.message)}</span>`; }
  }
  function genPrompt(scene) {
    const p = ui.progress({ title: "Gerar prompt realista", subtitle: "Skill /generate_realistic_prompt_images (Claude, grátis)" });
    p.step("Escrevendo o prompt…");
    api(`${base()}/scenes/${encodeURIComponent(scene)}/prompt`, { method: "POST" })
      .then((r) => { p.ok(`prompt pronto (${r.source})`); setTimeout(() => p.close(), 700); load(); })
      .catch((e) => p.fail((e && e.message) || String(e)));
  }

  // -- foto --
  async function genPhoto(scene) {
    const ok = await ui.confirmCost({ action: "storyboard.scene", pid: pid(), count: 1, label: "Gerar a foto da cena" });
    if (!ok) return;
    await runJob(`${base()}/scenes/${encodeURIComponent(scene)}/photo/generate`, {}, "Gerar a foto da cena");
    await load();
  }

  // -- frames + ordem --
  async function loadCandidates(scene) {
    const gal = $(`#sbFrames-${cssq(scene)}`);
    if (!gal) return;
    let cands = [];
    try { const r = await api(`${base()}/scenes/${encodeURIComponent(scene)}/candidates`); cands = r.candidates || [];
      if (!order[scene]) order[scene] = (r.selected || []).map((sh) => sh.candidate).filter(Boolean);
    } catch (e) { /* cena sem base ainda */ }
    candCache[scene] = cands;
    gal.innerHTML = cands.map((c) => {
      const ord = (order[scene] || []).indexOf(c.id);
      return `<div class="card${ord >= 0 ? " sel" : ""}" data-cand="${esc(c.id)}" tabindex="0" title="clique para ${ord >= 0 ? "tirar da" : "pôr na"} ordem">
        <img loading="lazy" src="${esc(files(c.url))}" alt="">
        ${ord >= 0 ? `<span class="ord">${ord + 1}</span>` : ""}
        ${c.upscaled ? `<span class="up ok">upscalado</span>` : `<button class="up-btn" data-up="${esc(c.id)}" title="Upscale 2x (aula 011)">upscale</button>`}</div>`;
    }).join("") || `<div class="empty">Sem frames ainda. Gere o multishot da foto da cena.</div>`;
    gal.querySelectorAll("[data-cand]").forEach((card) => {
      card.onclick = (e) => {
        if (e.target.closest("[data-up]")) return;
        const id = card.dataset.cand;
        order[scene] = order[scene] || [];
        const i = order[scene].indexOf(id);
        if (i >= 0) order[scene].splice(i, 1); else order[scene].push(id);
        loadCandidates(scene); renderOrderStrip(scene);
      };
    });
    gal.querySelectorAll("[data-up]").forEach((b) => { b.onclick = (e) => { e.stopPropagation(); upscale(scene, b.dataset.up); }; });
    renderOrderStrip(scene);
  }

  function renderOrderStrip(scene) {
    const strip = $(`#sbOrder-${cssq(scene)}`);
    if (!strip) return;
    const ids = order[scene] || [];
    const byId = Object.fromEntries((candCache[scene] || []).map((c) => [c.id, c]));
    strip.innerHTML = ids.length
      ? `<span class="eyebrow sm">ordem dos frames (arraste)</span><div class="sb-order-row">` + ids.map((id, i) => {
          const c = byId[id]; if (!c) return "";
          return `<div class="sb-ord-item" draggable="true" data-i="${i}"><span class="ord">${i + 1}</span><img src="${esc(files(c.url))}" alt=""></div>`;
        }).join("") + `</div>`
      : `<span class="fine">Clique nos frames abaixo para montar a ordem da cena.</span>`;
    const row = strip.querySelector(".sb-order-row");
    if (row) wireDrag(row, ".sb-ord-item", (from, to) => {
      const [m] = ids.splice(from, 1); ids.splice(to, 0, m); order[scene] = ids; loadCandidates(scene);
    });
  }

  async function genFrames(scene, body) {
    const count = clamp(body.querySelector(".sb-fcount").value, 1, 8, 4);
    const ok = await ui.confirmCost({ action: "storyboard.multishot", pid: pid(), count, label: `Gerar ${count} frame(s)` });
    if (!ok) return;
    await runJob(`${base()}/scenes/${encodeURIComponent(scene)}/frames/generate`, { count }, "Gerar frames (multishot)");
    await loadCandidates(scene); ctx.guide();
  }

  async function upscale(scene, cid) {
    const ok = await ui.confirmCost({ action: "base.upscale", pid: pid(), count: 1, label: "Upscale 2x do frame" });
    if (!ok) return;
    // reusa o endpoint de upscale dos ângulos (mesmo motor)
    await runJob(`${base()}/angles/scenes/${encodeURIComponent(scene)}/upscale`, { id: cid }, "Upscale do frame", `${base()}/job`);
    await loadCandidates(scene);
  }

  async function saveOrder(scene) {
    const ids = order[scene] || [];
    if (!ids.length) { toast("Monte a ordem clicando nos frames"); return; }
    const byId = Object.fromEntries((candCache[scene] || []).map((c) => [c.id, c]));
    const shots = ids.map((id) => ({ id, upscaled: !!(byId[id] && byId[id].upscaled) }));
    try {
      const r = await api(`${base()}/scenes/${encodeURIComponent(scene)}/order`, { method: "POST", body: JSON.stringify({ shots }) });
      toast(r.warning ? r.warning : "Ordem salva"); await load();
    } catch (e) { toast(e.message); }
  }

  // ---------- utilidades ----------
  function clamp(v, min, max, def) { const n = Number(v); return Number.isFinite(n) ? Math.max(min, Math.min(max, n)) : def; }
  function cssq(s) { return (window.CSS && CSS.escape) ? CSS.escape(s) : s; }

  async function runJob(url, body, title, jobUrl) {
    return ui.progressJob({
      title, subtitle: "Geração no Higgsfield (aula 011)",
      start: () => api(url, { method: "POST", body: JSON.stringify(body || {}) }),
      jobUrl: jobUrl || `${base()}/job`, label: "Pronto",
    }).catch((e) => { toast((e && e.message) || String(e)); });
  }

  // Drag-and-drop simples e reutilizável: `sel` são itens irmãos com data-i; `onMove(from,to)`.
  function wireDrag(container, sel, onMove) {
    let dragI = null;
    container.querySelectorAll(sel).forEach((el) => {
      el.addEventListener("dragstart", () => { dragI = +el.dataset.i; el.classList.add("dragging"); });
      el.addEventListener("dragend", () => { el.classList.remove("dragging"); dragI = null; });
      el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("dragover"); });
      el.addEventListener("dragleave", () => el.classList.remove("dragover"));
      el.addEventListener("drop", (e) => { e.preventDefault(); el.classList.remove("dragover");
        const to = +el.dataset.i; if (dragI !== null && dragI !== to) onMove(dragI, to); });
    });
  }

  return {
    init() { load(); },
    onProject() { overview = null; seeds = []; prescript = null; expanded.clear(); load(); },
    destroy() { if (poller) poller.stop(); },
  };
});
