// Etapa 4 — Storyboard (aula 010): ideias a partir da imagem base (uma instrução por vez,
// 4 gerações quando incerto / 1 quando é tweak) e a história em ~5 cenas de texto, na estrutura
// começo → descoberta → ação → desfecho. Componentes compartilhados vêm de `Studio.ui` (wave 2).
Studio.register("storyboard", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const esc = (s) => ui.esc(s);
  let meta = { kinds: [], presets: [], models: [], arc: [], counts: { uncertain: 4, tweak: 1 } };
  let ideas = [], sel = new Set(), scenes = [], hasBase = false, lastCount = 4;
  let sourceId = null;   // ideia usada como origem da próxima geração pelo CLI (auditoria 4.2)
  let job = null;        // handle do poll: parado em destroy()

  const url = (p) => `/api/projects/${ctx.pid()}/storyboard${p || ""}`;

  // O rótulo do arco vira o `data-mom` que o shell colore (`.mom[data-mom="comeco|…"]`):
  // "começo" → comeco, "ação" → acao. Sem acento, minúsculo, só letras.
  const momOf = (label) => String(label || "").normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z]/g, "");

  // Mesma regra do backend (`storyboard.service.scene_arc`): a aula 010 organiza a história em
  // começo → descoberta → ação → desfecho; com ~5 cenas a ação ocupa o miolo.
  function arcOf(n, total) {
    const [comeco, descoberta, acao, desfecho] = meta.arc.length === 4 ? meta.arc
      : [{ label: "começo", hint: "" }, { label: "descoberta", hint: "" }, { label: "ação", hint: "" }, { label: "desfecho", hint: "" }];
    if (n <= 1) return comeco;
    if (n >= total) return desfecho;
    return n === 2 ? descoberta : acao;
  }

  async function loadStatus() {
    const st = await api(url());
    hasBase = st.has_base;
    $("#sbBaseChip").textContent = hasBase ? "base: pronta (etapa 3)" : "base: ausente";
    $("#sbBaseChip").className = "chip " + (hasBase ? "ok" : "warn");
    $("#sbCounts").textContent = `${st.ideas} ideias · ${st.selected} escolhidas · ${st.scenes_with_text}/${st.scenes} cenas escritas`;
    $("#sbBase").classList.toggle("hidden", !hasBase);
    if (hasBase) $("#sbBase").src = ctx.files(st.base_image);
    $("#sbBaseWarn").classList.toggle("hidden", hasBase);
    $("#sbGen4").disabled = $("#sbGen1").disabled = !hasBase;
    const md = $("#sbMd");
    md.classList.toggle("hidden", !st.storyboard_md);
    if (st.storyboard_md) md.href = ctx.files(st.storyboard_md);
  }

  async function loadPresets() {
    meta = await api(url("/instructions"));
    $("#sbKind").innerHTML = meta.kinds.map((k) => `<option value="${esc(k.kind)}">${esc(k.label)}</option>`).join("");
    $("#sbPreset").innerHTML = `<option value="">— fórmulas da aula —</option>` +
      meta.presets.map((p, i) => `<option value="${i}">${esc(p.label)}</option>`).join("");
    // O modelo padrão é o da aula; o extra vem marcado `[extensão]` pelo backend (auditoria 4.4).
    $("#sbModel").innerHTML = (meta.models || []).map((m) =>
      `<option value="${esc(m.id)}" ${m.default ? "selected" : ""}>${esc(m.label)}</option>`).join("");
    if (meta.upscale_note) $("#sbUpscaleNote").textContent = meta.upscale_note;
    kindHint();
  }
  function kindHint() {
    const k = meta.kinds.find((x) => x.kind === $("#sbKind").value);
    $("#sbKindHint").textContent = k ? k.ui_hint : "";
    $("#sbCliGen").title = $("#sbKind").value === "draw_to_edit" ? "Draw to Edit não existe no CLI: o desenho é feito na interface." : "";
  }

  function renderSource() {
    const c = ideas.find((i) => i.id === sourceId);
    $("#sbSourceChip").textContent = c ? `origem: ${c.id}` : "origem: imagem base";
    $("#sbSourceChip").className = "chip " + (c ? "ok" : "mode");
    $("#sbSourceClear").classList.toggle("hidden", !c);
  }

  async function build(count) {
    try {
      const r = await api(url("/instructions"), { method: "POST", body: JSON.stringify({ kind: $("#sbKind").value, text: $("#sbText").value, count }) });
      $("#sbInstruction").value = r.instruction;
      $("#sbHint").textContent = r.ui_hint;
      lastCount = r.count;
      return r;
    } catch (err) { toast(err.message); return null; }
  }

  async function importFiles(files) {
    if (!files.length) return;
    try {
      const fd = new FormData();
      [...files].forEach((f) => fd.append("files", f));
      fd.append("prompt", $("#sbInstruction").value || "");
      const r = await fetch(url("/import/upload"), { method: "POST", body: fd });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.detail || r.statusText);
      toast(`${body.added} ideias importadas${body.skipped ? ` · ${body.skipped} ignoradas` : ""}`);
      await loadIdeas(); await loadStatus(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  async function loadIdeas() {
    if (!ctx.pid()) { ideas = []; return renderIdeas(); }
    ideas = (await api(url("/candidates"))).ideas;
    sel = new Set(ideas.filter((i) => i.selected).map((i) => i.id));
    if (sourceId && !ideas.some((i) => i.id === sourceId)) sourceId = null;
    renderIdeas(); renderScenes();
  }
  function renderIdeas() {
    $("#sbGallery").innerHTML = ideas.length ? ideas.map((i) =>
      `<div class="card ${sel.has(i.id) ? "sel" : ""} ${i.id === sourceId ? "src-of" : ""}" data-id="${esc(i.id)}" tabindex="0" title="${esc(i.prompt)}">
         <img loading="lazy" src="${esc(ctx.files(i.thumb || i.file))}" alt=""><span class="src">${esc(i.source)}</span>
         <button type="button" class="link sbSrc sb-tilebtn" data-src="${esc(i.id)}">${i.id === sourceId ? "origem ✓" : "usar como origem"}</button></div>`).join("")
      : `<div class="empty">Nenhuma ideia ainda — gere na Higgsfield com a instrução acima e importe.</div>`;
    renderSource();
  }

  const selectedIdeas = () => ideas.filter((i) => i.selected);
  async function loadScenes() {
    scenes = (await api(url("/scenes"))).scenes;
    renderScenes();
  }
  function renderScenes() {
    const opts = (cur) => `<option value="">— sem imagem —</option>` + selectedIdeas().map((i) =>
      `<option value="${esc(i.file)}" ${i.file === cur ? "selected" : ""}>${esc(i.id)}</option>`).join("");
    const total = scenes.length;
    // `.scene-row` do shell: momento narrativo | thumb + select da imagem | texto e ações.
    // Os botões ↑ ↓ ✕ NUNCA recebem filhos: o handler usa `e.target.classList.contains`.
    $("#sbScenes").innerHTML = scenes.map((s, i) => {
      const arc = arcOf(i + 1, total);
      return `<div class="scene-row" data-i="${i}">
         <span class="mom" data-mom="${esc(momOf(arc.label))}" title="Cena ${i + 1} · ${esc(arc.label)}">${esc(arc.label)}</span>
         <div class="sb-scene-media">
           <div class="thumb">${s.image ? `<img loading="lazy" src="${esc(ctx.files(s.image))}" alt="">` : ""}</div>
           <select class="sbImg" title="imagem da cena">${opts(s.image)}</select>
         </div>
         <div class="sb-scene-body">
           <textarea class="sbTxt" rows="2" placeholder="${esc(arc.label)}: ${esc(arc.hint)} (ex.: close no astronauta andando na nevasca)">${esc(s.text)}</textarea>
           <div class="sb-scene-acts">
             <button type="button" class="ghost sbUp" title="subir">↑</button><button type="button" class="ghost sbDown" title="descer">↓</button><button type="button" class="ghost sbDel" title="remover">✕</button>
           </div>
         </div>
       </div>`;
    }).join("");
  }
  function collect() {
    return [...document.querySelectorAll("#sbScenes .scene-row")].map((el) => ({
      text: el.querySelector(".sbTxt").value, image: el.querySelector(".sbImg").value || null,
    }));
  }

  function cliBody(built) {
    // `source_id` encadeia a edição na ideia escolhida; sem ele o CLI parte de base/base_final.png.
    const body = { model: $("#sbModel").value, kind: built.kind, text: $("#sbText").value, count: built.count };
    if (sourceId) body.source_id = sourceId;
    return body;
  }

  return {
    init() {
      $("#sbKind").onchange = kindHint;
      $("#sbPreset").onchange = (e) => {
        const p = meta.presets[+e.target.value];
        if (!p) return;
        $("#sbKind").value = p.kind; $("#sbText").value = p.text; kindHint();
      };
      $("#sbGen4").onclick = () => build(meta.counts.uncertain);
      $("#sbGen1").onclick = () => build(meta.counts.tweak);
      $("#sbCopy").onclick = async () => {
        if (!$("#sbInstruction").value) return toast("Monte a instrução primeiro.");
        await navigator.clipboard.writeText($("#sbInstruction").value);
        $("#sbCopied").textContent = "copiado ✓"; setTimeout(() => ($("#sbCopied").textContent = ""), 1500);
      };
      $("#sbSourceClear").onclick = () => { sourceId = null; renderIdeas(); };
      $("#sbCliGen").onclick = async () => {
        const built = await build(lastCount);
        if (!built) return;
        const body = cliBody(built);
        const ok = await ui.confirmCost(
          () => api(url("/cost"), { method: "POST", body: JSON.stringify(body) }),
          `Gerar ${body.count} imagem(ns) via CLI${sourceId ? ` a partir de ${sourceId}` : ""}`);
        if (!ok) return;
        try {
          await api(url("/generate"), { method: "POST", body: JSON.stringify(body) });
          $("#sbCliGen").disabled = true;
          job = ui.poll(async () => {
            const j = await api(url("/job"));
            $("#sbJobLog").textContent = j.state === "running" ? `gerando ${j.done}/${j.total} · ${j.added} imagens`
              : j.state === "error" ? "erro: " + j.error : j.state === "done" ? `concluído · ${j.added} imagens` : "";
            if (j.state === "running") return;
            $("#sbCliGen").disabled = false;
            await loadIdeas(); await loadStatus(); ctx.guide();
            return false;
          }, 3000);
        } catch (err) { toast(err.message); }
      };

      ui.drop($("#sbDrop"), importFiles);
      $("#sbBtnDownloads").onclick = async () => {
        try {
          const r = await api(url("/import/downloads"), { method: "POST", body: JSON.stringify({ since_minutes: +$("#sbMinutes").value, prompt: $("#sbInstruction").value || "" }) });
          toast(`${r.added} novas de ${r.scanned} imagens recentes`); await loadIdeas(); await loadStatus(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#sbBtnHistory").onclick = async () => {
        try {
          const r = await api(url("/import/history"), { method: "POST", body: JSON.stringify({ size: 50 }) });
          toast(`${r.added} imagens de ${r.jobs} jobs`); await loadIdeas(); await loadStatus(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#sbGallery").addEventListener("click", (e) => {
        const src = e.target.closest("button.sbSrc");
        if (src) { sourceId = sourceId === src.dataset.src ? null : src.dataset.src; return renderIdeas(); }
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id;
        sel.has(id) ? sel.delete(id) : sel.add(id);
        card.classList.toggle("sel");
      });
      $("#sbGallery").addEventListener("dblclick", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        window.open(ctx.files(ideas.find((i) => i.id === card.dataset.id).file), "_blank");
      });
      $("#sbUse").onclick = async () => {
        try {
          const r = await api(url("/candidates/select"), { method: "POST", body: JSON.stringify({ ids: [...sel] }) });
          toast(r.detached.length ? `${r.selected} ideias no storyboard · imagem removida de ${r.detached.join(", ")}` : `${r.selected} ideias no storyboard`);
          await loadIdeas(); await loadScenes(); await loadStatus(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#sbAdd").onclick = () => { scenes = collect().concat({ text: "", image: null }); renderScenes(); };
      $("#sbScenes").addEventListener("click", (e) => {
        const box = e.target.closest(".scene-row"); if (!box) return;
        const i = +box.dataset.i;
        scenes = collect();
        if (e.target.classList.contains("sbDel")) scenes.splice(i, 1);
        else if (e.target.classList.contains("sbUp") && i > 0) scenes.splice(i - 1, 0, scenes.splice(i, 1)[0]);
        else if (e.target.classList.contains("sbDown") && i < scenes.length - 1) scenes.splice(i + 1, 0, scenes.splice(i, 1)[0]);
        else return;
        renderScenes();
      });
      // A miniatura da cena acompanha o select sem esperar o próximo render.
      $("#sbScenes").addEventListener("change", (e) => {
        if (!e.target.classList.contains("sbImg")) return;
        const box = e.target.closest(".scene-row"); if (!box) return;
        const t = box.querySelector(".thumb"); if (!t) return;
        t.innerHTML = e.target.value ? `<img loading="lazy" src="${esc(ctx.files(e.target.value))}" alt="">` : "";
      });
      $("#sbSave").onclick = async () => {
        try {
          const r = await api(url("/scenes"), { method: "PUT", body: JSON.stringify({ scenes: collect() }) });
          scenes = r.scenes; renderScenes(); await loadStatus(); ctx.guide();
          toast(`${r.scenes.length} cenas salvas · storyboard.md atualizado`);
        } catch (err) { toast(err.message); }
      };
      $("#sbRender").onclick = async () => {
        try { await api(url("/render"), { method: "POST" }); await loadStatus(); ctx.guide(); toast("storyboard.md gerado"); }
        catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      sourceId = null;
      ui.hfChip($("#sbHfState")).then((s) => { $("#sbCliGen").disabled = !s.logged_in; });
      await loadPresets();
      await loadStatus();
      await loadIdeas();
      await loadScenes();
      ui.renderGuide("storyboard");
    },
    destroy() { if (job) { job.stop(); job = null; } },
  };
});
