// Etapa 3 — Imagem base (aula 009): o bot escreve o prompt olhando a referência e o mood,
// você gera na Higgsfield, escolhe, troca o rótulo e faz upscale 2x.
Studio.register("base", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const KINDS = { situation: "situação", label: "rótulo", upscale: "upscale" };
  let cands = [], sel = null, chain = { situation: null, label: null, upscale: null };
  let refs = [], labelCount = 3, job = null;

  const url = (p) => `/api/projects/${ctx.pid()}/base/${p}`;

  // ---------- prompts (painéis 1 e 2) ----------
  // O texto EDITADO na tela é o que vale: o import o herda e o CLI o recebe (B4).
  function promptText(key) {
    const ta = document.querySelector(`#basePrompts textarea[data-k="${key}"], #labelPrompt textarea[data-k="${key}"]`);
    return ta ? ta.value : "";
  }

  function importPrompt() {
    const k = $("#impKind").value;
    if (k === "label") return promptText("label");
    if (k === "upscale") return "";
    const rid = $("#impRef").value || (refs[0] && refs[0].ref_id);
    return promptText(`p:${rid}`);
  }

  function promptCard(label, text, key, editable, note) {
    return `<div class="prompt"><div class="row wrap"><span class="eyebrow">${ui.esc(label)}</span>
      ${note ? `<span class="fine">${ui.esc(note)}</span>` : ""}
      <button class="ghost copy" data-k="${ui.esc(key)}">Copiar</button><span class="ok"></span></div>
      <textarea data-k="${ui.esc(key)}"${editable ? "" : " readonly"}>${ui.esc(text)}</textarea></div>`;
  }

  // Galeria das referências da etapa 1: a escolha vale para "Gerar prompt" e para "Importar".
  function renderRefGallery() {
    $("#refGallery").innerHTML = refs.length ? refs.map((f) =>
      `<div class="card" data-ref="${ui.esc(f.ref_id)}" tabindex="0" title="${ui.esc(f.ref_id)}">
         <img src="${ctx.files(f.file)}" alt="referência ${ui.esc(f.ref_id)}" loading="lazy">
         <span class="term">${ui.esc(f.ref_id)}</span></div>`).join("")
      : `<div class="empty">Nenhuma referência escolhida — volte à etapa 1 e salve a seleção.</div>`;
  }
  function selectRef(id) {
    $("#promptRef").value = id || ""; $("#impRef").value = id || "";
    $("#refGallery").querySelectorAll(".card").forEach((c) => c.classList.toggle("sel", c.dataset.ref === id));
    $("#refPickState").textContent = id ? `ref ${id}` : "nenhuma";
    $("#refPickState").className = id ? "chip ok" : "chip warn";
    $("#impRefChip").textContent = id ? `ref ${id}` : "—";
    $("#basePrompts").querySelectorAll(".prompt-group").forEach((g) => g.classList.toggle("sel", g.dataset.ref === id));
  }

  function refCard(f) {
    const fonte = f.prompt_source === "claude" ? `escrito pelo bot (modo ${f.prompt_mode || "images"})`
                                               : "template fixo — gere pelo bot para ficar como na aula";
    return `<div class="prompt-group" data-ref="${ui.esc(f.ref_id)}">
      <div class="prompt-ref"><img src="${ctx.files(f.file)}" alt="referência ${ui.esc(f.ref_id)}" loading="lazy">
        <span class="fine">referência ${ui.esc(f.ref_id)}</span></div>
      ${promptCard(`instrução para o bot · sessão nova, sem viés · ref ${f.ref_id}`, f.bot_instruction,
                   `b:${f.ref_id}`, false, "cole isto numa aba nova do BOT, junto com a imagem da referência")}
      ${promptCard(`prompt para gerar · ref ${f.ref_id}`, f.prompt, `p:${f.ref_id}`, true, fonte)}
    </div>`;
  }

  async function loadPrompts() {
    refs = [];
    try {
      const r = await api(url(`prompts?model=${$("#baseModel").value}`));
      refs = r.refs; labelCount = r.label_count || 3;
      const claude = $("#baseClaude");
      claude.textContent = r.claude ? "bot: Claude CLI disponível" : "bot: sem Claude CLI (só template)";
      claude.className = r.claude ? "chip ok" : "chip warn";
      $("#promptMode").querySelectorAll("option").forEach((o) => {
        o.disabled = !r.claude && o.value !== "template";
      });
      if (!r.claude) $("#promptMode").value = "template";
      $("#botHint").textContent = r.bot_hint;
      $("#baseHint").textContent = `${r.ui_hint} Formato ${r.aspect_ratio} (vem da campanha). Produto: ${r.product}.`;
      $("#basePalette").innerHTML = (r.palette.colors || []).map((c) =>
        `<span style="background:${ui.esc(c)}" title="${ui.esc(c)}"></span>`).join("");
      $("#baseMood").textContent = `mood anexado (o bot vê estas imagens): ${r.mood_files.join(", ")}`;
      $("#basePrompts").innerHTML = r.refs.map(refCard).join("");
      $("#labelPrompt").innerHTML = r.label_prompt_ready
        ? promptCard("troca de rótulo (uma instrução só)", r.label_prompt, "label", true,
                     `edite se ficar simples demais · ${labelCount} variações por vez no CLI`)
        : `<div class="empty">Informe a marca acima para liberar a instrução de troca de rótulo.</div>`;
      renderRefGallery();
      selectRef(refs.some((f) => f.ref_id === $("#promptRef").value) ? $("#promptRef").value
                                                                     : (refs[0] ? refs[0].ref_id : ""));
      $("#upscaleHint").textContent = r.upscale_hint;
    } catch (err) {
      $("#basePrompts").innerHTML = `<div class="empty">${ui.esc(err.message)}</div>`;
      $("#baseHint").textContent = ""; $("#botHint").textContent = "";
      $("#labelPrompt").innerHTML = "";
    }
  }

  async function gerarPrompt(noBias) {
    const btn = noBias ? $("#btnPromptNoBias") : $("#btnPrompt");
    btn.disabled = true;
    btn.textContent = noBias ? "Perguntando ao bot (sem viés)…" : "Perguntando ao bot…";
    try {
      const body = {
        ref_id: $("#promptRef").value || null,
        mode: noBias ? "images" : $("#promptMode").value,
        instruction: $("#promptInstruction").value,
        no_bias: !!noBias,
        no_people: $("#promptNoPeople").checked,
      };
      const e = await api(url("prompts/generate"), { method: "POST", body: JSON.stringify(body) });
      toast(`Prompt ${e.source === "claude" ? "escrito pelo bot" : "do template"} (${e.seconds || 0}s)`);
      await loadPrompts();
      ctx.guide();
    } catch (err) { toast(err.message); }
    btn.disabled = false;
    btn.textContent = noBias ? "Gerar sem viés (sessão nova)" : "Gerar prompt";
  }

  async function loadBrand() {
    const b = await api(url("brand"));
    $("#brandName").value = b.name || ""; $("#brandDesc").value = b.description || "";
  }

  // ---------- candidatas ----------
  async function load() {
    if (!ctx.pid()) { cands = []; return render(); }
    const r = await api(url("candidates"));
    cands = r.candidates;
    chain = { situation: null, label: null, upscale: null };
    cands.filter((c) => c.selected).forEach((c) => { chain[c.kind] = c.id; });
    if (sel && !cands.some((c) => c.id === sel)) sel = null;
    render(r.final);
  }

  function render(final) {
    const only = $("#galKind").value;
    const list = only ? cands.filter((c) => c.kind === only) : cands;
    $("#baseCounts").textContent = `${cands.length} candidatas · ${list.length} exibidas`;
    $("#btnBaseSelect").disabled = !sel;
    $("#baseChain").textContent = "Cadeia: "
      + ["situation", "label", "upscale"].map((k) => `${KINDS[k]}: ${chain[k] || "—"}`).join(" · ")
      + (final ? ` · final: ${final}` : " · sem imagem base ainda");
    $("#baseGallery").innerHTML = list.length ? list.map((c) =>
      `<div class="card ${sel === c.id ? "sel" : ""}" data-id="${ui.esc(c.id)}" tabindex="0" title="${ui.esc(c.prompt || c.name || "")}">
         <img loading="lazy" src="${ui.esc(ctx.files(c.thumb || c.file))}" alt="">
         <span class="src">${ui.esc(KINDS[c.kind] || c.kind)}${c.selected ? " ✓" : ""}</span>
         <span class="term">${c.ref_id ? "ref " + ui.esc(c.ref_id) + " · " : ""}${ui.esc(c.source)}</span></div>`).join("")
      : `<div class="empty">Nenhuma imagem ainda — gere na UI da Higgsfield com o mood anexado e importe acima.</div>`;
  }

  function afterImport(r) {
    (r.warnings || []).forEach((w) => toast(w));
    toast(`${r.added} imagem(ns) importada(s)`);
    load(); ctx.guide();
  }

  async function importar(files) {
    if (!files.length) return;
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    fd.append("kind", $("#impKind").value);
    if ($("#impRef").value) fd.append("ref_id", $("#impRef").value);
    fd.append("prompt", importPrompt());
    const res = await fetch(url("import/upload"), { method: "POST", body: fd });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) return toast(body.detail || res.statusText);
    afterImport(body);
  }

  // ---------- geração paga ----------
  function genBody() {
    const kind = $("#genKind").value;
    const body = { kind, count: +$("#genCount").value || null };
    // Em `situation` o serviço usa o prompt que o bot escreveu para CADA referência — mandar um
    // texto só sobrescreveria todas. No rótulo há uma instrução única: vale a editada na tela (B4).
    if (kind === "label") body.prompt = promptText("label");
    // O seletor de modelo é o dos prompts de situação: em rótulo/upscale o serviço usa o default
    // do passo (mandar o modelo daqui gastaria créditos no modelo errado).
    if (kind === "situation") body.model = $("#baseModel").value;
    return body;
  }

  async function gerarCli() {
    const body = genBody();
    const ok = await ui.confirmCost(
      () => api(url("cost"), { method: "POST", body: JSON.stringify(body) }),
      `Gerar "${KINDS[body.kind]}" via CLI`);
    if (!ok) return;
    try {
      await api(url("generate"), { method: "POST", body: JSON.stringify(body) });
      $("#btnBaseGen").disabled = true; $("#baseLog").textContent = "";
      if (job) job.stop();
      job = ui.poll(async () => {
        const j = await api(url("job"));
        const pct = j.total ? Math.round(100 * j.done / j.total) : 0;
        $("#baseProgress").classList.toggle("hidden", j.state !== "running");
        $("#baseProgress").querySelector(".bar").style.width = pct + "%";
        $("#baseLog").textContent = (j.log || []).join("\n") + (j.state === "error" ? `\nerro: ${j.error}` : "");
        if (j.state === "running") { load(); return; }
        $("#btnBaseGen").disabled = false;
        toast(`geração ${j.state === "error" ? "com erro" : "concluída"} · ${j.added || 0} imagens`);
        load(); ctx.guide();
        return false;      // encerra o poll
      }, 3000);
    } catch (err) { toast(err.message); }
  }

  return {
    init() {
      $("#btnBasePrompts").onclick = () => loadPrompts();
      $("#refGallery").addEventListener("click", (e) => { const c = e.target.closest(".card"); if (c) selectRef(c.dataset.ref); });
      $("#refGallery").addEventListener("keydown", (e) => { const c = e.target.closest(".card"); if (c && e.key === "Enter") selectRef(c.dataset.ref); });
      $("#baseModel").onchange = () => loadPrompts();
      $("#btnPrompt").onclick = () => gerarPrompt(false);
      $("#btnPromptNoBias").onclick = () => gerarPrompt(true);
      $("#genKind").onchange = () => { $("#genCount").value = $("#genKind").value === "label" ? labelCount : 1; };
      document.querySelectorAll("#basePrompts, #labelPrompt").forEach((el) => el.addEventListener("click", async (e) => {
        const b = e.target.closest("button.copy"); if (!b) return;
        const ta = b.closest(".prompt").querySelector("textarea");
        await navigator.clipboard.writeText(ta.value);
        b.parentElement.querySelector(".ok").textContent = "copiado ✓";
        setTimeout(() => { b.parentElement.querySelector(".ok").textContent = ""; }, 1500);
      }));
      $("#btnBrand").onclick = async () => {
        try {
          await api(url("brand"), { method: "POST", body: JSON.stringify({ name: $("#brandName").value, description: $("#brandDesc").value }) });
          toast("Marca salva"); await loadPrompts(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      ui.drop($("#baseDrop"), importar);
      $("#btnBaseDownloads").onclick = async () => {
        try {
          afterImport(await api(url("import/downloads"), { method: "POST", body: JSON.stringify({
            since_minutes: +$("#baseDlMinutes").value, kind: $("#impKind").value,
            ref_id: $("#impRef").value || null, prompt: importPrompt() }) }));
        } catch (err) { toast(err.message); }
      };
      $("#btnBaseHistory").onclick = async () => {
        try {
          afterImport(await api(url("import/history"), { method: "POST", body: JSON.stringify({
            kind: $("#impKind").value, ref_id: $("#impRef").value || null }) }));
        } catch (err) { toast(err.message); }
      };
      $("#galKind").onchange = () => render();
      $("#baseGallery").addEventListener("click", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        sel = sel === card.dataset.id ? null : card.dataset.id; render();
      });
      $("#baseGallery").addEventListener("dblclick", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = cands.find((x) => x.id === card.dataset.id); window.open(ctx.files(c.file), "_blank");
      });
      $("#btnBaseSelect").onclick = async () => {
        if (!sel) return;
        try {
          const r = await api(url("select"), { method: "POST", body: JSON.stringify({ id: sel }) });
          toast(`Imagem base: ${r.final} (${KINDS[r.kind] || r.kind})`);
          await loadPrompts(); load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#btnBaseGen").onclick = gerarCli;
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      sel = null;
      ui.hfChip($("#baseHf")).then((s) => { $("#btnBaseGen").disabled = !s.logged_in; });
      loadBrand();
      await loadPrompts();
      load();
      ui.renderGuide("base");
      const d = await api("/api/mood/downloads-folder");
      $("#baseDlFolder").textContent = d.folder + (d.exists ? "" : " (não encontrada)");
    },
    destroy() { if (job) { job.stop(); job = null; } },
  };
});
