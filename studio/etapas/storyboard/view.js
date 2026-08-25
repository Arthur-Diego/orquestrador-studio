// Etapa 4 — Storyboard (aula 010): ideias a partir da imagem base (uma instrução por vez,
// 4 gerações quando incerto / 1 quando é tweak) e a história em ~5 cenas de texto.
Studio.register("storyboard", (ctx) => {
  const { $, api, toast } = ctx;
  let meta = { kinds: [], presets: [], counts: { uncertain: 4, tweak: 1 } };
  let ideas = [], sel = new Set(), scenes = [], hasBase = false;

  const url = (p) => `/api/projects/${ctx.pid()}/storyboard${p || ""}`;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

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
    $("#sbKind").innerHTML = meta.kinds.map((k) => `<option value="${k.kind}">${esc(k.label)}</option>`).join("");
    $("#sbPreset").innerHTML = `<option value="">— fórmulas da aula —</option>` +
      meta.presets.map((p, i) => `<option value="${i}">${esc(p.label)}</option>`).join("");
    kindHint();
  }
  function kindHint() {
    const k = meta.kinds.find((x) => x.kind === $("#sbKind").value);
    $("#sbKindHint").textContent = k ? k.ui_hint : "";
    $("#sbCliGen").title = $("#sbKind").value === "draw_to_edit" ? "Draw to Edit não existe no CLI: o desenho é feito na interface." : "";
  }

  async function build(count) {
    try {
      const r = await api(url("/instructions"), { method: "POST", body: JSON.stringify({ kind: $("#sbKind").value, text: $("#sbText").value, count }) });
      $("#sbInstruction").value = r.instruction;
      $("#sbHint").textContent = r.ui_hint;
      return r;
    } catch (err) { toast(err.message); return null; }
  }

  async function hfStatus() {
    const s = await api("/api/higgsfield/status"), el = $("#sbHfState");
    if (!s.installed) { el.textContent = "CLI: não instalado"; el.className = "chip warn"; }
    else if (!s.logged_in) { el.textContent = "CLI: sem login"; el.className = "chip warn"; }
    else { el.textContent = `CLI: ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`; el.className = "chip ok"; }
    $("#sbCliGen").disabled = !s.logged_in;
  }
  async function pollJob() {
    const j = await api(url("/job"));
    $("#sbJobLog").textContent = j.state === "running" ? `gerando ${j.done}/${j.total} · ${j.added} imagens`
      : j.state === "error" ? "erro: " + j.error : j.state === "done" ? `concluído · ${j.added} imagens` : "";
    if (j.state === "running") setTimeout(pollJob, 3000);
    else { $("#sbCliGen").disabled = false; loadIdeas(); loadStatus(); }
  }

  async function upload(files) {
    if (!files.length) return;
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    fd.append("prompt", $("#sbInstruction").value || "");
    const r = await fetch(url("/import/upload"), { method: "POST", body: fd });
    if (!r.ok) return toast((await r.json().catch(() => ({}))).detail || r.statusText);
    const j = await r.json();
    toast(`${j.added} ideias importadas${j.skipped ? ` · ${j.skipped} ignoradas` : ""}`);
    loadIdeas(); loadStatus();
  }

  async function loadIdeas() {
    if (!ctx.pid()) { ideas = []; return renderIdeas(); }
    ideas = (await api(url("/candidates"))).ideas;
    sel = new Set(ideas.filter((i) => i.selected).map((i) => i.id));
    renderIdeas(); renderScenes();
  }
  function renderIdeas() {
    $("#sbGallery").innerHTML = ideas.length ? ideas.map((i) =>
      `<div class="card ${sel.has(i.id) ? "sel" : ""}" data-id="${i.id}" tabindex="0" title="${esc(i.prompt)}">
         <img loading="lazy" src="${ctx.files(i.thumb || i.file)}" alt=""><span class="src">${esc(i.source)}</span></div>`).join("")
      : `<div class="empty">Nenhuma ideia ainda — gere na Higgsfield com a instrução acima e importe.</div>`;
  }

  const selectedIdeas = () => ideas.filter((i) => i.selected);
  async function loadScenes() {
    scenes = (await api(url("/scenes"))).scenes;
    renderScenes();
  }
  function renderScenes() {
    const opts = (cur) => `<option value="">— sem imagem —</option>` + selectedIdeas().map((i) =>
      `<option value="${esc(i.file)}" ${i.file === cur ? "selected" : ""}>${esc(i.id)}</option>`).join("");
    $("#sbScenes").innerHTML = scenes.map((s, i) =>
      `<div class="prompt" data-i="${i}">
         <div class="row"><span class="eyebrow">Cena ${i + 1}</span>
           <select class="sbImg">${opts(s.image)}</select>
           <button class="ghost sbUp" title="subir">↑</button><button class="ghost sbDown" title="descer">↓</button>
           <button class="ghost sbDel" title="remover">remover</button></div>
         <textarea class="sbTxt" rows="2" placeholder="ex.: close no astronauta andando na nevasca">${esc(s.text)}</textarea>
       </div>`).join("");
  }
  function collect() {
    return [...document.querySelectorAll("#sbScenes .prompt")].map((el) => ({
      text: el.querySelector(".sbTxt").value, image: el.querySelector(".sbImg").value || null,
    }));
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
      $("#sbCliGen").onclick = async () => {
        const built = await build(+($("#sbGen1").dataset.last || meta.counts.uncertain));
        if (!built) return;
        const body = { model: $("#sbModel").value, kind: built.kind, text: $("#sbText").value, count: built.count };
        let est = "Estimativa indisponível.";
        try { const c = await api(url("/cost"), { method: "POST", body: JSON.stringify(body) }); if (c.total != null) est = `Estimativa: ${c.total} créditos.`; } catch (e) { /* segue sem estimativa */ }
        if (!confirm(`Gerar ${body.count} imagem(ns) via CLI? ${est} Isso gasta créditos.`)) return;
        try { await api(url("/generate"), { method: "POST", body: JSON.stringify(body) }); $("#sbCliGen").disabled = true; pollJob(); }
        catch (err) { toast(err.message); }
      };
      const drop = $("#sbDrop");
      drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
      drop.addEventListener("dragleave", () => drop.classList.remove("over"));
      drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files); });
      $("#sbUpload").addEventListener("change", (e) => upload(e.target.files));
      $("#sbBtnDownloads").onclick = async () => {
        try {
          const r = await api(url("/import/downloads"), { method: "POST", body: JSON.stringify({ since_minutes: +$("#sbMinutes").value, prompt: $("#sbInstruction").value || "" }) });
          toast(`${r.added} novas de ${r.scanned} imagens recentes`); loadIdeas(); loadStatus();
        } catch (err) { toast(err.message); }
      };
      $("#sbBtnHistory").onclick = async () => {
        try { const r = await api(url("/import/history"), { method: "POST", body: JSON.stringify({ size: 50 }) }); toast(`${r.added} imagens de ${r.jobs} jobs`); loadIdeas(); loadStatus(); }
        catch (err) { toast(err.message); }
      };
      $("#sbGallery").addEventListener("click", (e) => {
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
          await loadIdeas(); await loadScenes(); loadStatus();
        } catch (err) { toast(err.message); }
      };
      $("#sbAdd").onclick = () => { scenes = collect().concat({ text: "", image: null }); renderScenes(); };
      $("#sbScenes").addEventListener("click", (e) => {
        const box = e.target.closest(".prompt"); if (!box) return;
        const i = +box.dataset.i;
        scenes = collect();
        if (e.target.classList.contains("sbDel")) scenes.splice(i, 1);
        else if (e.target.classList.contains("sbUp") && i > 0) scenes.splice(i - 1, 0, scenes.splice(i, 1)[0]);
        else if (e.target.classList.contains("sbDown") && i < scenes.length - 1) scenes.splice(i + 1, 0, scenes.splice(i, 1)[0]);
        else return;
        renderScenes();
      });
      $("#sbSave").onclick = async () => {
        try {
          const r = await api(url("/scenes"), { method: "PUT", body: JSON.stringify({ scenes: collect() }) });
          scenes = r.scenes; renderScenes(); loadStatus(); toast(`${r.scenes.length} cenas salvas · storyboard.md atualizado`);
        } catch (err) { toast(err.message); }
      };
      $("#sbRender").onclick = async () => {
        try { await api(url("/render"), { method: "POST" }); loadStatus(); toast("storyboard.md gerado"); }
        catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      hfStatus();
      await loadPresets();
      await loadStatus();
      await loadIdeas();
      await loadScenes();
    },
  };
});
