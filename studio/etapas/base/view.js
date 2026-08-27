// Etapa 3 — Imagem base (aula 009): o bot escreve o prompt olhando a referência e o mood,
// você gera na Higgsfield, escolhe, troca o rótulo e faz upscale 2x.
//
// Wave 4 (ADH-OS-20260826-12): a tela é a do protótipo — 3 painéis, um único card de prompt
// (o da referência selecionada) e o stepper como SELETOR do passo da importação. O que era
// controle visível virou default fixo: modo `images`, `no_people:false`, `since_minutes:120`
// e o modelo default do backend (o `?model=` saiu junto com o seletor).
Studio.register("base", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const KINDS = { situation: "situação", label: "rótulo", upscale: "upscale" };
  const CHAIN = [["situation", "situação"], ["label", "rótulo"], ["upscale", "upscale 2x"]];
  const SINCE_MINUTES = 120;

  let cands = [], sel = null, chain = { situation: null, label: null, upscale: null };
  let refs = [], labelPrompt = null, claudeOk = false;
  // base-prompt-provenance: insumos visuais da junção mood × referência (cabeçalho + chips).
  let palette = { colors: [], note: "" }, moodFiles = [], boardImgUrls = [];
  // Rótulo descritivo por linha (FDD §1) e o texto/cor de cada proveniência.
  const PART_LABEL = { Composition: "referência (situação/enquadramento)", Lighting: "mood (luz)",
    "Color grading": "mood (cor/paleta)", Style: "mood (estética/atmosfera)", Camera: "técnico" };
  const FROM_LABEL = { reference: "referência", mood: "mood", technical: "técnico" };
  const edits = {};        // texto editado na tela, por chave: sobrevive à troca de passo (B4)
  let refId = "";          // referência escolhida no painel 01: vale para o prompt E para o import
  let step = "situation";  // passo ativo do stepper = passo da importação (auditoria #36)
  let stepTouched = false; // depois do primeiro clique o recarregamento não muda mais o passo
  // [extensão] (ADR-013): fonte do mood usada como referência de estilo — null = mood da
  // campanha (atual), ou o mbid de um mood board da biblioteca.
  let moodSources = null, boardSel = null;

  const url = (p) => `/api/projects/${ctx.pid()}/base/${p}`;

  // ---------- prompts (painel 01) ----------
  // O texto EDITADO na tela é o que vale: o import o herda (B4).
  function promptText(key) {
    const ta = document.querySelector(`#basePrompts textarea[data-k="${key}"]`);
    return ta ? ta.value : "";
  }

  function importPrompt() {
    if (step === "upscale") return "";
    return promptText(step === "label" ? "label" : `p:${refId}`);
  }

  function promptCard(label, text, key) {
    return `<div class="prompt"><div class="row"><span class="eyebrow">${ui.esc(label)}</span>
      <button type="button" class="link copy" data-k="${ui.esc(key)}">Copiar</button><span class="ok"></span></div>
      <textarea data-k="${ui.esc(key)}">${ui.esc(text)}</textarea></div>`;
  }

  // Um card só, de largura total: o da referência selecionada. Quando o passo ativo é "rótulo"
  // e há marca salva, o MESMO card passa a mostrar a instrução de troca de rótulo (auditoria #29).
  function renderPrompt() {
    const el = $("#basePrompts");
    // O card é um só: guarde o que estava editado antes de trocar de referência ou de passo.
    const atual = el.querySelector("textarea");
    if (atual) edits[atual.dataset.k] = atual.value;
    const f = refs.find((r) => r.ref_id === refId) || refs[0];
    const card = (label, texto, key) => promptCard(label, key in edits ? edits[key] : texto, key);
    if (step === "label" && labelPrompt !== null) {
      el.innerHTML = card("Prompt · rótulo · editável", labelPrompt, "label");
    } else if (f) {
      el.innerHTML = card("Prompt · situação · editável", f.prompt, `p:${f.ref_id}`);
    } else {
      el.innerHTML = "";
    }
    ui.autosize(el.querySelectorAll("textarea"));
    renderJunction();
    renderProvenance();
  }

  // base-prompt-provenance: as thumbs do mood que vão ao bot (board escolhido ou mood da campanha).
  function currentMoodThumbs() {
    if (boardSel) return boardImgUrls;
    return (moodFiles || []).map((f) => ctx.files(f));
  }

  // Cabeçalho de junção (FDD §3): 🖼️ referência (situação) + 🎨 mood (vibe/luz/cor) + paleta, com
  // o texto que deixa claro que o prompt abaixo é a JUNÇÃO dos dois. Só aparece com uma referência
  // escolhida e no passo "situação" (o passo "rótulo" é outra tarefa da aula).
  function renderJunction() {
    const el = $("#baseJunction");
    if (!el) return;
    const f = refs.find((r) => r.ref_id === refId) || refs[0];
    if (!f || step === "label") { el.innerHTML = ""; el.style.display = "none"; return; }
    el.style.display = "";
    const moods = currentMoodThumbs();
    const moodThumbs = moods.length
      ? moods.slice(0, 4).map((u) => `<img src="${u}" alt="imagem do mood" loading="lazy">`).join("")
      : `<span class="fine">sem imagens do mood ainda (etapa 2 ou um board)</span>`;
    const swatches = (palette.colors || []).length
      ? `<div class="swatches">${palette.colors.slice(0, 8).map((c) =>
          `<span class="sw" style="background:${ui.esc(c)}" title="${ui.esc(c)}"></span>`).join("")}</div>`
      : "";
    el.innerHTML = `
      <div class="side">
        <span class="eyebrow lbl">🖼️ Referência (situação)</span>
        <div class="thumbs"><img src="${ctx.files(f.file)}" alt="referência ${ui.esc(f.ref_id)}" loading="lazy"></div>
      </div>
      <div class="side">
        <span class="eyebrow lbl">🎨 Mood (vibe/luz/cor)</span>
        <div class="thumbs">${moodThumbs}</div>${swatches}
      </div>
      <p class="join-note">O prompt abaixo funde a <b>situação da referência</b> com a <b>vibe do mood</b>.</p>`;
  }

  // Visão anotada [extensão] (FDD §3): read-only, cada linha do prompt com um chip de proveniência
  // (referência / mood / técnico) e o parágrafo rotulado "junção". A fonte é o `provenance` que o
  // backend devolve (split_sections + mapa determinístico). Nunca substitui o textarea copiável.
  function renderProvenance() {
    const el = $("#baseProvenance");
    if (!el) return;
    const f = refs.find((r) => r.ref_id === refId) || refs[0];
    const prov = f && step !== "label" ? f.provenance : null;
    if (!prov) { el.innerHTML = ""; el.style.display = "none"; return; }
    el.style.display = "";
    const lines = [];
    if (prov.paragraph) {
      lines.push(`<div class="prov-line"><span class="bs-chip from-join">junção</span>
        <span class="prov-text"><b>produto da referência na vibe do mood.</b> ${ui.esc(prov.paragraph)}</span></div>`);
    }
    (prov.parts || []).forEach((p) => {
      const desc = PART_LABEL[p.label] || FROM_LABEL[p.from] || p.from;
      lines.push(`<div class="prov-line"><span class="bs-chip from-${ui.esc(p.from)}">${ui.esc(FROM_LABEL[p.from] || p.from)}</span>
        <span class="prov-text"><b>${ui.esc(p.label)}</b> <span class="fine">(${ui.esc(desc)})</span> — ${ui.esc(p.text)}</span></div>`);
    });
    el.innerHTML = `<div class="row"><span class="eyebrow lbl">De onde vem cada parte</span>
      <span class="ext">[extensão]</span></div>${lines.join("") ||
      `<p class="fine">Prompt fora do formato de 5 linhas — copie o texto completo acima.</p>`}`;
  }

  // Galeria das referências da etapa 1: a escolha vale para "Gerar prompt" e para "Importar".
  function renderRefGallery() {
    $("#refGallery").innerHTML = refs.map((f) =>
      `<div class="card${f.ref_id === refId ? " sel" : ""}" data-ref="${ui.esc(f.ref_id)}" tabindex="0" title="referência ${ui.esc(f.ref_id)}">
         <img src="${ctx.files(f.file)}" alt="referência ${ui.esc(f.ref_id)}" loading="lazy"></div>`).join("");
  }

  function selectRef(id) {
    refId = id || "";
    $("#refGallery").querySelectorAll(".card").forEach((c) => c.classList.toggle("sel", c.dataset.ref === refId));
    renderPrompt();
  }

  async function loadPrompts() {
    refs = []; labelPrompt = null;
    try {
      const r = await api(url("prompts"));
      refs = r.refs;
      labelPrompt = r.label_prompt_ready ? r.label_prompt : null;
      claudeOk = !!r.claude;
      palette = r.palette || { colors: [], note: "" };
      moodFiles = r.mood_files || [];
      const claude = $("#baseClaude");
      claude.textContent = claudeOk ? "bot: claude ok" : "bot: sem claude";
      claude.className = claudeOk ? "chip ok" : "chip warn";
      renderRefGallery();
      selectRef(refs.some((f) => f.ref_id === refId) ? refId : (refs[0] ? refs[0].ref_id : ""));
    } catch (err) {
      $("#refGallery").innerHTML = "";
      $("#basePrompts").innerHTML = `<div class="empty">${ui.esc(err.message)}</div>`;
    }
  }

  async function gerarPrompt(noBias) {
    const btn = noBias ? $("#btnPromptNoBias") : $("#btnPrompt");
    // O protótipo não desenha o seletor de modo: o app sempre pede com as imagens (referência +
    // mood). Sem Claude, "Gerar prompt" cai no template — o `bot: sem claude` já avisa por que o
    // texto não veio do bot. "Gerar sem viés" é ação do bot: sem ele, erra. Só o modo `images`
    // chama o Claude (síncrono, lento) e merece o modal de fases; o template é instantâneo.
    const usaBot = noBias || claudeOk;
    const body = {
      ref_id: refId || null,
      mode: usaBot ? "images" : "template",
      instruction: $("#promptInstruction").value,
      no_bias: !!noBias,
      no_people: false,
      board: boardSel,   // [extensão] ADR-013: usa as imagens do board como referência
    };
    const gen = () => api(url("prompts/generate"), { method: "POST", body: JSON.stringify(body) });
    const aplicar = (e) => {
      toast(`Prompt ${e.source === "claude" ? "escrito pelo bot" : "do template"} (${e.seconds || 0}s)`);
      Object.keys(edits).forEach((k) => delete edits[k]);   // o texto novo do bot manda
      return loadPrompts().then(() => ctx.guide());
    };
    if (!usaBot) {
      try { await aplicar(await gen()); } catch (err) { toast(err.message); }
      return;
    }
    const p = ui.progress({
      title: noBias ? "Gerar prompt sem viés" : "Gerar prompt da base",
      subtitle: "Bot de prompts (Claude) — aula 009",
    });
    p.step(noBias ? "Preparando referência + mood (sessão nova, sem o prompt anterior)"
                  : "Preparando referência + mood");
    p.step("Consultando o Claude…");
    btn.disabled = true;
    btn.textContent = noBias ? "Perguntando ao bot (sessão nova)…" : "Perguntando ao bot…";
    try {
      const e = await gen();
      p.step("Formatando no padrão do bot");
      await aplicar(e);
      p.ok("Pronto"); setTimeout(() => p.close(), 700);
    } catch (err) { p.fail(err.message); toast(err.message); }
    btn.disabled = false;
    btn.textContent = noBias ? "Gerar sem viés" : "Gerar prompt";
  }

  async function loadBrand() {
    const b = await api(url("brand"));
    $("#brandName").value = b.name || ""; $("#brandDesc").value = b.description || "";
  }

  // ---------- mood de referência [extensão] (ADR-013): campanha OU board da biblioteca ----------
  async function loadMoodSources() {
    try { moodSources = await api(url("mood-sources")); }
    catch (e) { moodSources = { campaign: { files: [], count: 0 }, boards: [] }; }
    const sel = $("#moodSource");
    const opts = [`<option value="">Mood da campanha (${moodSources.campaign.count} img)</option>`]
      .concat(moodSources.boards.map((b) =>
        `<option value="${ui.esc(b.id)}">Board: ${ui.esc(b.name)} (${b.count} img) [extensão]</option>`));
    sel.innerHTML = opts.join("");
    if (boardSel && !moodSources.boards.some((b) => b.id === boardSel)) boardSel = null;
    sel.value = boardSel || "";
    await renderMoodSourceGallery();
  }

  async function renderMoodSourceGallery() {
    const g = $("#moodSourceGallery");
    if (!boardSel) {
      const files = (moodSources && moodSources.campaign.files) || [];
      boardImgUrls = [];
      g.innerHTML = files.length
        ? files.map((f) => `<div class="card"><img loading="lazy" src="${ctx.files(f)}" alt=""></div>`).join("")
        : `<div class="empty">Sem mood da campanha ainda — salve o mood na etapa 2, ou puxe/escolha um mood board.</div>`;
      renderJunction();
      return;
    }
    try {
      const d = await api(`/api/moodboards/${encodeURIComponent(boardSel)}`);
      boardImgUrls = d.images.map((rel) => `/mbfiles/${encodeURIComponent(boardSel)}/${rel}`);
      g.innerHTML = d.images.length
        ? d.images.map((rel) => `<div class="card"><img loading="lazy" src="/mbfiles/${encodeURIComponent(boardSel)}/${ui.esc(rel)}" alt=""></div>`).join("")
        : `<div class="empty">Este mood board não tem imagens curadas.</div>`;
    } catch (e) { boardImgUrls = []; g.innerHTML = `<div class="empty">${ui.esc(e.message)}</div>`; }
    renderJunction();
  }

  // ---------- candidatas (painel 03) ----------
  async function load() {
    if (!ctx.pid()) { cands = []; return render(); }
    const r = await api(url("candidates"));
    cands = r.candidates;
    chain = { situation: null, label: null, upscale: null };
    cands.filter((c) => c.selected).forEach((c) => { chain[c.kind] = c.id; });
    if (sel && !cands.some((c) => c.id === sel)) sel = null;
    if (!stepTouched) {
      const proximo = CHAIN.find(([k]) => !chain[k]);
      step = proximo ? proximo[0] : "upscale";
    }
    render();
  }

  function render() {
    $("#btnBaseSelect").disabled = !sel;
    renderChain();
    // Sem filtro e sem contador (auditoria #31): a galeria mostra tudo; vazia, não desenha nada.
    $("#baseGallery").innerHTML = cands.map((c) => ui.tile({
      id: c.id,
      src: ctx.files(c.thumb || c.file),
      badge: `${KINDS[c.kind] || c.kind}${c.selected ? " ✓" : ""}`,
      term: `${c.ref_id ? "ref " + c.ref_id + " · " : ""}${c.source}`,
      sel: sel === c.id,
      title: c.prompt || c.name || "",
    })).join("");
  }

  // Cadeia da aula como `.stepper` do catálogo. O passo com candidata escolhida fica `done`
  // (estado que o protótipo não desenha, regra 6) e o passo ATIVO — o que recebe a importação —
  // fica `on`. Clicar troca o passo ativo: é o seletor da importação, sem controle extra.
  function stepClass(k) {
    if (k === step) return chain[k] ? "st on done" : "st on";
    return chain[k] ? "st done" : "st";
  }

  function renderChain() {
    $("#baseChain").innerHTML = CHAIN.map(([k, rotulo], i) => {
      const escolhida = chain[k] ? `${rotulo}: ${chain[k]}` : `${rotulo}: ainda não escolhido`;
      const t = `${escolhida} — clique para importar neste passo`;
      return `<span class="${stepClass(k)}" data-step="${ui.esc(k)}" role="button" tabindex="0" title="${ui.esc(t)}"><i>${i + 1}</i>${ui.esc(rotulo)}</span>`;
    }).join(`<span class="sep"></span>`);
  }

  function setStep(k) {
    if (!k || k === step) return;
    step = k; stepTouched = true;
    renderChain();
    renderPrompt();   // no passo "rótulo" o card do painel 01 vira a instrução de rótulo
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
    fd.append("kind", step);
    if (refId) fd.append("ref_id", refId);
    fd.append("prompt", importPrompt());
    const res = await fetch(url("import/upload"), { method: "POST", body: fd });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) return toast(body.detail || res.statusText);
    afterImport(body);
  }

  return {
    init() {
      $("#refGallery").addEventListener("click", (e) => { const c = e.target.closest(".card"); if (c) selectRef(c.dataset.ref); });
      $("#refGallery").addEventListener("keydown", (e) => { const c = e.target.closest(".card"); if (c && e.key === "Enter") selectRef(c.dataset.ref); });
      $("#btnPrompt").onclick = () => gerarPrompt(false);
      $("#btnPromptNoBias").onclick = () => gerarPrompt(true);
      $("#moodSource").onchange = () => { boardSel = $("#moodSource").value || null; renderMoodSourceGallery(); };
      $("#basePrompts").addEventListener("click", async (e) => {
        const b = e.target.closest("button.copy"); if (!b) return;
        const ta = b.closest(".prompt").querySelector("textarea");
        await navigator.clipboard.writeText(ta.value);
        b.parentElement.querySelector(".ok").textContent = "copiado ✓";
        setTimeout(() => { b.parentElement.querySelector(".ok").textContent = ""; }, 1500);
      });
      $("#btnBrand").onclick = async () => {
        try {
          await api(url("brand"), { method: "POST", body: JSON.stringify({ name: $("#brandName").value, description: $("#brandDesc").value }) });
          delete edits.label;   // a instrução de rótulo é reescrita a partir da marca nova
          toast("Marca salva"); await loadPrompts(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#baseChain").addEventListener("click", (e) => { const s = e.target.closest("[data-step]"); if (s) setStep(s.dataset.step); });
      $("#baseChain").addEventListener("keydown", (e) => {
        const s = e.target.closest("[data-step]");
        if (s && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setStep(s.dataset.step); }
      });
      ui.drop($("#baseDrop"), importar);
      $("#btnBaseDownloads").onclick = async () => {
        try {
          afterImport(await api(url("import/downloads"), { method: "POST", body: JSON.stringify({
            since_minutes: SINCE_MINUTES, kind: step, ref_id: refId || null, prompt: importPrompt() }) }));
        } catch (err) { toast(err.message); }
      };
      $("#btnBaseHistory").onclick = async () => {
        try {
          afterImport(await api(url("import/history"), { method: "POST", body: JSON.stringify({
            kind: step, ref_id: refId || null }) }));
        } catch (err) { toast(err.message); }
      };
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
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      sel = null; stepTouched = false; boardSel = null;
      loadBrand();
      loadMoodSources();
      await loadPrompts();
      load();
      ui.renderGuide("base");
      // O caminho da pasta some da tela e vira tooltip do botão (auditoria #39).
      const d = await api("/api/mood/downloads-folder");
      $("#btnBaseDownloads").title = `Últimos ${SINCE_MINUTES} min de ${d.folder}${d.exists ? "" : " (não encontrada)"}`;
    },
  };
});
