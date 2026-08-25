// Etapa 3 — Imagem base (aula 009): produto na situação da referência → rótulo próprio → upscale 2x.
Studio.register("base", (ctx) => {
  const { $, api, toast } = ctx;
  const KINDS = { situation: "situação", label: "rótulo", upscale: "upscale" };
  let cands = [], sel = null, chain = { situation: null, label: null, upscale: null }, refs = [];

  const url = (p) => `/api/projects/${ctx.pid()}/base/${p}`;

  async function hfStatus() {
    const s = await api("/api/higgsfield/status"), el = $("#baseHfState");
    if (!s.installed) { el.textContent = "CLI: não instalado"; el.className = "chip warn"; }
    else if (!s.logged_in) { el.textContent = "CLI: instalado, sem login (higgsfield auth login)"; el.className = "chip warn"; }
    else { el.textContent = `CLI: ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`; el.className = "chip ok"; }
    $("#btnBaseGen").disabled = !s.logged_in;
  }

  function promptCard(label, text, key) {
    return `<div class="prompt"><div class="row"><span class="eyebrow">${label}</span>
      <button class="ghost copy" data-k="${key}">Copiar</button><span class="ok"></span></div>
      <textarea data-k="${key}" readonly>${text}</textarea></div>`;
  }

  async function loadPrompts() {
    refs = [];
    try {
      const r = await api(url(`prompts?model=${$("#baseModel").value}`));
      refs = r.refs;
      $("#baseHint").textContent = `${r.ui_hint} Proporção ${r.aspect_ratio}. Produto: ${r.product}.`;
      $("#basePalette").innerHTML = (r.palette.colors || []).map(c => `<span style="background:${c}" title="${c}"></span>`).join("");
      $("#baseMood").textContent = r.mood_files.length ? `mood anexado: ${r.mood_files.join(", ")}` : "sem imagens em mood/selected/ — anexe o mood na UI manualmente";
      $("#basePrompts").innerHTML = r.refs.map((f, i) =>
        promptCard(`referência ${f.ref_id}`, f.prompt, `r${i}`) + promptCard(`sem viés (aba nova) · ${f.ref_id}`, f.prompt_no_bias, `n${i}`)).join("");
      $("#labelPrompt").innerHTML = r.label_prompt_ready
        ? promptCard("troca de rótulo (uma instrução)", r.label_prompt, "label")
        : `<div class="empty">Informe a marca acima para liberar o prompt de troca de rótulo.</div>`;
      $("#impRef").innerHTML = `<option value="">—</option>` + r.refs.map(f => `<option value="${f.ref_id}">${f.ref_id}</option>`).join("");
      $("#upscaleHint").textContent = r.upscale_hint;
    } catch (err) {
      $("#basePrompts").innerHTML = `<div class="empty">${err.message}</div>`;
      $("#baseHint").textContent = "";
      $("#labelPrompt").innerHTML = "";
    }
  }

  async function loadBrand() {
    const b = await api(url("brand"));
    $("#brandName").value = b.name || ""; $("#brandDesc").value = b.description || "";
  }

  async function load() {
    if (!ctx.pid()) { cands = []; return render(); }
    const r = await api(url("candidates"));
    cands = r.candidates;
    chain = { situation: null, label: null, upscale: null };
    cands.filter(c => c.selected).forEach(c => { chain[c.kind] = c.id; });
    if (sel && !cands.some(c => c.id === sel)) sel = null;
    render(r.final);
  }

  function render(final) {
    const only = $("#galKind").value;
    const list = only ? cands.filter(c => c.kind === only) : cands;
    $("#baseCounts").textContent = `${cands.length} candidatas · ${list.length} exibidas`;
    $("#btnBaseSelect").disabled = !sel;
    $("#baseChain").textContent = "Cadeia: "
      + ["situation", "label", "upscale"].map(k => `${KINDS[k]}: ${chain[k] || "—"}`).join(" · ")
      + (final ? ` · final: ${final}` : " · sem imagem base ainda");
    $("#baseGallery").innerHTML = list.length ? list.map(c =>
      `<div class="card ${sel === c.id ? "sel" : ""}" data-id="${c.id}" tabindex="0" title="${(c.prompt || c.name || "").replace(/"/g, "'")}">
         <img loading="lazy" src="${ctx.files(c.thumb || c.file)}" alt="">
         <span class="src">${KINDS[c.kind] || c.kind}${c.selected ? " ✓" : ""}</span>
         <span class="term">${c.ref_id ? "ref " + c.ref_id + " · " : ""}${c.source}</span></div>`).join("")
      : `<div class="empty">Nenhuma imagem ainda — gere na UI da Higgsfield e importe acima.</div>`;
  }

  async function uploadFiles(files) {
    if (!files.length) return;
    const fd = new FormData();
    [...files].forEach(f => fd.append("files", f));
    fd.append("kind", $("#impKind").value);
    if ($("#impRef").value) fd.append("ref_id", $("#impRef").value);
    const r = await fetch(url("import/upload"), { method: "POST", body: fd });
    if (!r.ok) return toast((await r.json().catch(() => ({}))).detail || r.statusText);
    toast(`${(await r.json()).added} imagens importadas`); load();
  }

  async function pollJob() {
    const j = await api(url("job"));
    const pct = j.total ? Math.round(100 * j.done / j.total) : 0;
    $("#baseProgress").classList.toggle("hidden", j.state !== "running");
    $("#baseProgress").querySelector(".bar").style.width = pct + "%";
    $("#baseLog").textContent = (j.log || []).join("\n") + (j.state === "error" ? `\nerro: ${j.error}` : "");
    if (j.state === "running") { setTimeout(pollJob, 3000); load(); }
    else { $("#btnBaseGen").disabled = false; toast(`geração ${j.state === "error" ? "com erro" : "concluída"} · ${j.added || 0} imagens`); load(); }
  }

  return {
    init() {
      $("#btnBasePrompts").onclick = () => loadPrompts();
      $("#baseModel").onchange = () => loadPrompts();
      document.querySelectorAll("#basePrompts, #labelPrompt").forEach(el => el.addEventListener("click", async e => {
        const b = e.target.closest("button.copy"); if (!b) return;
        const ta = b.closest(".prompt").querySelector("textarea");
        await navigator.clipboard.writeText(ta.value);
        b.parentElement.querySelector(".ok").textContent = "copiado ✓";
        setTimeout(() => b.parentElement.querySelector(".ok").textContent = "", 1500);
      }));
      $("#btnBrand").onclick = async () => {
        try {
          await api(url("brand"), { method: "POST", body: JSON.stringify({ name: $("#brandName").value, description: $("#brandDesc").value }) });
          toast("Marca salva"); loadPrompts();
        } catch (err) { toast(err.message); }
      };
      const drop = $("#baseDrop");
      drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
      drop.addEventListener("dragleave", () => drop.classList.remove("over"));
      drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); uploadFiles(e.dataTransfer.files); });
      $("#baseUpload").addEventListener("change", e => uploadFiles(e.target.files));
      $("#btnBaseDownloads").onclick = async () => {
        try {
          const r = await api(url("import/downloads"), { method: "POST", body: JSON.stringify({ since_minutes: +$("#baseDlMinutes").value, kind: $("#impKind").value, ref_id: $("#impRef").value || null }) });
          toast(`${r.added} novas de ${r.scanned} imagens recentes`); load();
        } catch (err) { toast(err.message); }
      };
      $("#btnBaseHistory").onclick = async () => {
        try {
          const r = await api(url("import/history"), { method: "POST", body: JSON.stringify({ kind: $("#impKind").value, ref_id: $("#impRef").value || null }) });
          toast(`${r.added} imagens de ${r.jobs} jobs`); load();
        } catch (err) { toast(err.message); }
      };
      $("#galKind").onchange = () => render();
      $("#baseGallery").addEventListener("click", e => {
        const card = e.target.closest(".card"); if (!card) return;
        sel = sel === card.dataset.id ? null : card.dataset.id; render();
      });
      $("#baseGallery").addEventListener("dblclick", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = cands.find(x => x.id === card.dataset.id); window.open(ctx.files(c.file), "_blank");
      });
      $("#btnBaseSelect").onclick = async () => {
        if (!sel) return;
        try {
          const r = await api(url("select"), { method: "POST", body: JSON.stringify({ id: sel }) });
          toast(`Imagem base: ${r.final} (${KINDS[r.kind] || r.kind})`); loadPrompts(); load();
        } catch (err) { toast(err.message); }
      };
      $("#btnBaseGen").onclick = async () => {
        const kind = $("#genKind").value, count = +$("#genCount").value;
        const body = { kind, model: $("#baseModel").value, count };
        let est = "Estimativa indisponível.";
        try {
          const c = await api(url("cost"), { method: "POST", body: JSON.stringify(body) });
          if (c.total != null) est = `Estimativa: ${c.total} créditos (${c.count} imagens).`;
        } catch (err) { est = `Estimativa indisponível (${err.message}).`; }
        if (!confirm(`Gerar "${KINDS[kind]}" via CLI? ${est} Isso gasta créditos.`)) return;
        try {
          await api(url("generate"), { method: "POST", body: JSON.stringify(body) });
          $("#btnBaseGen").disabled = true; $("#baseLog").textContent = ""; pollJob();
        } catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      sel = null;
      hfStatus(); loadBrand(); loadPrompts(); load();
      const d = await api("/api/mood/downloads-folder");
      $("#baseDlFolder").textContent = d.folder + (d.exists ? "" : " (não encontrada)");
    },
  };
});
