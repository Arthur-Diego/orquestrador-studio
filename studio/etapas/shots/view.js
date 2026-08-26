// Etapa 5 — Ângulos por cena (aula 011) + cena do produto (aula 013).
// Ordem da aula: acertar a BASE da cena (edição numerada) → promover o resultado a base →
// Multi Shot → escolher → upscale → ordenar.
//
// Wave 4 (fidelidade ao protótipo): a tela tem DOIS painéis. A cena do produto é mais um card no
// grid do painel 01; preparar a base é ação de hover do card; importar candidatos abre pelo chip
// "N candidatos · N escolhidos" (ou arrastando arquivos sobre o painel 02); o prompt só aparece
// depois de "Gerar prompt". Não há geração/upscale pelo CLI nesta tela — as rotas `/generate`,
// `/upscale`, `/cost` e `/job` continuam no backend.
Studio.register("shots", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const esc = (s) => ui.esc(s);
  const base = () => `/api/projects/${ctx.pid()}/shots`;

  const PRODUCT = "__produto__";                 // cena virtual: o card "produto" do painel 01
  let scenes = [], scene = null, cands = [], order = [], prod = [];
  let prodState = { ref_ready: false, selected: false };
  let prodTick = 0;             // cache-buster: product_final.png é regravado no mesmo caminho

  const isProduct = () => scene === PRODUCT;
  // "cena01" → "cena 01" (rótulo mono do card, como no protótipo).
  const sceneLabel = (id) => String(id || "").replace(/^cena/, "cena ");
  const prodPick = () => prod.find((c) => c.selected) || null;

  // ---------- cenas ----------
  async function loadScenes() {
    if (!ctx.pid()) return;
    let r;
    try { r = await api(`${base()}/scenes`); }
    catch (err) { $("#sceneList").innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
    scenes = r.scenes;
    prodState = r.product_scene || { ref_ready: false, selected: false };
    const cores = (r.palette.colors || []).map((c) => `<span style="background:${esc(c)}" title="${esc(c)}"></span>`).join("");
    $("#shotsPalette").innerHTML = cores
      ? cores + `<span class="lbl">paleta do mood</span>`
      : `<span class="lbl">sem mood/palette.json ainda (etapa 2)</span>`;
    renderSceneList();
  }

  /** Card de cena do protótipo: thumb 16/9 + "cena NN" + contador de upscale (texto puro). */
  function card(id, label, thumb, up, total, dica, act) {
    const falta = total > 0 && up < total;
    const done = total > 0 && up === total;
    return `<div class="rowcard col pick ${scene === id ? "cur" : ""}" data-scene="${esc(id)}" tabindex="0" title="${esc(dica)}">
       <div class="thumb">${thumb ? `<img loading="lazy" src="${esc(thumb)}" alt="">` : ""}</div>
       <div class="row"><span class="mono sh-scene-id">${esc(label)}</span>
         <span class="upcount${falta ? " warn" : done ? " ok" : ""}">${up}/${total} upscalados</span></div>
       ${act || ""}</div>`;
  }

  function renderSceneList() {
    const cenas = scenes.map((s) => card(
      s.id, sceneLabel(s.id), s.base_ready ? ctx.files(s.base) : null, s.upscaled, s.selected,
      `${s.text ? s.text + " · " : ""}${s.candidates} candidatos · ${s.selected} shot(s) escolhidos`,
      `<button type="button" class="sh-act shBase" data-scene-base="${esc(s.id)}">base ▾</button>`));
    // Cena do produto (aula 013): mais um card no grid, com as mesmas peças visuais.
    const pick = prodPick();
    const produto = card(
      PRODUCT, "produto", prodState.selected ? `${ctx.files("shots/product/product_final.png")}?t=${prodTick}` : null,
      prodState.selected && pick && pick.upscaled ? 1 : 0, prodState.selected ? 1 : 0,
      prodState.selected ? "cena do produto salva (aula 013)"
        : prodState.ref_ready ? "imagem 1 enviada — rode as duas instruções e importe o resultado"
          : "cena do produto (aula 013): envie a imagem 1 e rode as duas instruções",
      prodState.selected ? `<button type="button" class="sh-act shProdClear">remover</button>` : "");
    $("#sceneList").innerHTML = (cenas.join("") + produto)
      || `<div class="empty">Nenhuma cena — escreva a história na etapa 4.</div>`;
  }

  async function openScene(id) {
    scene = id; order = [];
    clearPrompts();
    const produto = isProduct();
    $("#sceneTitle").textContent = produto ? "Produto — escolher e ordenar"
      : `${sceneLabel(id).replace("cena", "Cena")} — escolher e ordenar`;
    // No produto o builder some (aula 013 tem instruções fixas): sobra o "Gerar prompt".
    ["#promptKind", "#promptSubject", "#promptScale", "#promptAngle"]
      .forEach((sel) => $(sel).classList.toggle("hidden", produto));
    $("#editsBox").classList.toggle("hidden", produto || $("#promptKind").value !== "edit");
    if (produto) { await loadProd(); } else { await loadCands(); }
    renderSceneList();
  }

  // ---------- base da cena (ação de hover do card, aula 011 passo 1) ----------
  async function prepareBase(source, file, id) {
    if (!scene || isProduct()) return toast("Abra uma cena primeiro.");
    try {
      if (file) await ui.upload(`${base()}/scenes/${scene}/base/upload`, [file], "file");
      else await api(`${base()}/scenes/${scene}/base`, { method: "POST", body: JSON.stringify({ source, id: id || null }) });
      toast(source === "candidate" ? "Este resultado é a nova base da cena" : "Base da cena pronta");
      await loadScenes(); await openScene(scene); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  async function baseMenu(id) {
    if (scene !== id) await openScene(id);
    const m = ui.modal({
      title: `Base da ${sceneLabel(id)}`,
      subtitle: "A base define cor e luz de tudo: acerte-a antes do Multi Shot.",
      html: `<div class="col">
        <button type="button" id="shBaseScene" class="ghost">Imagem da cena (etapa 4)</button>
        <button type="button" id="shBaseCampaign" class="ghost">Imagem base da campanha</button>
        <label class="drop sm" id="shBaseDrop">Arraste uma imagem ou <input id="shBaseUpload" type="file" accept="image/*" hidden><u>envie um arquivo</u></label>
      </div>`,
    });
    m.el.querySelector("#shBaseScene").onclick = () => { m.close(); prepareBase("storyboard"); };
    m.el.querySelector("#shBaseCampaign").onclick = () => { m.close(); prepareBase("base"); };
    ui.drop(m.el.querySelector("#shBaseDrop"), (files) => { m.close(); prepareBase("upload", files[0]); });
  }

  // ---------- prompts (só depois de "Gerar prompt" — 5.31) ----------
  const editLines = () => $("#promptEdits").value.split("\n").map((t) => t.trim()).filter(Boolean);

  function clearPrompts() {
    $("#shotsPrompts").innerHTML = "";
    $("#shotsPrompts").classList.add("hidden");
  }
  function renderPrompts(list) {
    $("#shotsPrompts").innerHTML = list.map((p, i) =>
      `<div class="prompt sm"><div class="row"><span class="eyebrow">${esc(p.label)}</span><button type="button" class="link copy" data-i="${i}">Copiar</button><span class="ok"></span></div><p class="txt" data-i="${i}">${esc(p.text)}</p></div>`).join("");
    $("#shotsPrompts").classList.toggle("hidden", !list.length);
  }

  async function prompts() {
    if (!scene) return toast("Abra uma cena primeiro.");
    if (isProduct()) return prodPrompts();
    const kind = $("#promptKind").value;
    const q = new URLSearchParams({ kind, scale: $("#promptScale").value, angle: $("#promptAngle").value });
    if ($("#promptSubject").value.trim()) q.set("subject", $("#promptSubject").value.trim());
    if (kind === "edit") {
      const e = editLines();
      if (!e.length) return toast("Escreva ao menos uma modificação.");
      e.forEach((v) => q.append("edits", v));
    }
    try {
      const r = await api(`${base()}/scenes/${scene}/prompts?${q}`);
      renderPrompts(r.prompts);
    } catch (err) { toast(err.message); }
  }

  async function prodPrompts() {
    try {
      const r = await api(`${base()}/product/prompts`);
      renderPrompts(r.prompts);
    } catch (err) { toast(err.message); }
  }

  // ---------- candidatos ----------
  async function loadCands() {
    if (!scene || isProduct()) { cands = []; return renderCands(); }
    try { cands = (await api(`${base()}/scenes/${scene}/candidates`)).candidates; }
    catch (err) { cands = []; toast(err.message); }
    order = order.filter((id) => cands.some((c) => c.id === id));
    renderCands();
  }

  async function loadProd() {
    if (!ctx.pid()) return;
    try { prod = (await api(`${base()}/product/candidates`)).candidates; }
    catch { prod = []; }
    prodTick = Date.now();
    if (isProduct()) {
      const pick = prodPick();
      order = pick ? [pick.id] : [];
      renderCands();
    }
  }

  /** Tiles do protótipo: número da ordem (`data-ord`) e selo de upscale; sem selo de origem. */
  function renderCands() {
    const lista = isProduct() ? prod : cands;
    const escolhidos = order.length;
    $("#shotsCounts").textContent = `${lista.length} candidatos · ${escolhidos} escolhidos`;
    $("#shotsGallery").innerHTML = lista.length ? lista.map((c) => {
      const pos = order.indexOf(c.id);
      return `<div class="card ${pos >= 0 ? "sel" : ""}"${pos >= 0 ? ` data-ord="${pos + 1}"` : ""} data-id="${esc(c.id)}" tabindex="0" title="${esc(c.prompt || c.name || c.source || "")}">
         <img loading="lazy" src="${esc(ctx.files(c.thumb || c.file))}" alt="">
         <span class="up${c.upscaled ? " ok" : ""}">${c.upscaled ? "upscalado 2x" : "sem upscale"}</span>
         ${isProduct() ? "" : `<button type="button" class="link asBase card-act" data-base="${esc(c.id)}">Usar como base da cena</button>`}</div>`;
    }).join("") : `<div class="empty">Nenhum candidato — gere na UI da Higgsfield e importe.</div>`;
  }

  // ---------- importação (popover; o painel 02 inteiro também aceita arrastar) ----------
  async function importFiles(files) {
    if (!files.length || !scene) return;
    const url = isProduct() ? `${base()}/product/import/upload` : `${base()}/scenes/${scene}/import/upload`;
    try {
      const r = await ui.upload(url, files);
      toast(r.added ? `${r.added} imagem(ns) importada(s)` : "Nada novo: já estavam importadas");
      await reload(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  async function reload() {
    if (isProduct()) { await loadProd(); await loadScenes(); } else { await loadCands(); await loadScenes(); }
  }

  function importModal() {
    if (!scene) return toast("Abra uma cena primeiro.");
    const produto = isProduct();
    const m = ui.modal({
      title: produto ? "Cena do produto (aula 013)" : `Importar candidatos da ${sceneLabel(scene)}`,
      subtitle: produto
        ? "Imagem 1 é a cena (ex.: geladeira); a imagem 2 é sempre base/base_final.png."
        : "Gere na interface da Higgsfield (Multi Shot, Cinema Studio, Upscale 2x) e traga os resultados.",
      html: `<div class="import-row">
        <label class="drop" id="shImpDrop">Arraste imagens aqui ou <input id="shImpUpload" type="file" accept="image/*" multiple hidden><u>escolha arquivos</u></label>
        <div class="col">
          ${produto ? `<label class="drop sm" id="shProdRefDrop">imagem 1 (a cena)<input id="shProdRefUpload" type="file" accept="image/*" hidden></label>` : ""}
          <button type="button" id="shImpDownloads" class="ghost">Importar da pasta Downloads</button>
          <label class="inline">últimos <input id="shImpMinutes" class="mini wide" type="number" value="120" min="5"> min</label>
          ${produto ? "" : `<button type="button" id="shImpHistory" class="ghost">Importar do histórico Higgsfield</button>
          <span class="fine">precisa de login no CLI</span>`}
          <span id="shImpFolder" class="fine mono"></span>
        </div>
      </div>`,
    });
    ui.drop(m.el.querySelector("#shImpDrop"), (files) => { m.close(); importFiles(files); });
    if (produto) {
      ui.drop(m.el.querySelector("#shProdRefDrop"), async (files) => {
        m.close();
        try {
          await ui.upload(`${base()}/product/ref`, [files[0]], "file");
          toast("Imagem 1 salva"); await loadScenes(); ctx.guide();
        } catch (err) { toast(err.message); }
      });
    }
    m.el.querySelector("#shImpDownloads").onclick = async () => {
      const minutes = +m.el.querySelector("#shImpMinutes").value;
      const url = produto ? `${base()}/product/import/downloads` : `${base()}/scenes/${scene}/import/downloads`;
      m.close();
      try {
        const r = await api(url, { method: "POST", body: JSON.stringify({ since_minutes: minutes }) });
        toast(`${r.added} novas de ${r.scanned || 0} recentes`); await reload(); ctx.guide();
      } catch (err) { toast(err.message); }
    };
    const hist = m.el.querySelector("#shImpHistory");
    if (hist) hist.onclick = async () => {
      m.close();
      try {
        const r = await api(`${base()}/scenes/${scene}/import/history`, { method: "POST", body: JSON.stringify({}) });
        toast(`${r.added} imagens de ${r.jobs} jobs`); await reload(); ctx.guide();
      } catch (err) { toast(err.message); }
    };
    api("/api/shots/downloads-folder")
      .then((d) => { const el = m.el.querySelector("#shImpFolder"); if (el) el.textContent = d.folder + (d.exists ? "" : " (não encontrada)"); })
      .catch(() => {});
  }

  return {
    init() {
      $("#sceneList").addEventListener("click", (e) => {
        const b = e.target.closest("[data-scene-base]");
        if (b) { e.stopPropagation(); baseMenu(b.dataset.sceneBase); return; }
        if (e.target.closest(".shProdClear")) {
          e.stopPropagation();
          return api(`${base()}/product/select`, { method: "POST", body: JSON.stringify({ id: null }) })
            .then(async () => { toast("Cena do produto removida"); await loadProd(); await loadScenes(); ctx.guide(); })
            .catch((err) => toast(err.message));
        }
        const c = e.target.closest("[data-scene]");
        if (c) openScene(c.dataset.scene);
      });

      // Trocar um controle do builder invalida o prompt anterior: ele só volta com "Gerar prompt".
      ["#promptKind", "#promptScale", "#promptAngle", "#promptSubject"].forEach((sel) =>
        $(sel).addEventListener("change", () => {
          $("#editsBox").classList.toggle("hidden", isProduct() || $("#promptKind").value !== "edit");
          clearPrompts();
        }));
      $("#btnPrompts").onclick = prompts;
      $("#shotsPrompts").addEventListener("click", async (e) => {
        const b = e.target.closest("button.copy"); if (!b) return;
        await navigator.clipboard.writeText(b.closest(".prompt").querySelector(".txt").textContent);
        b.parentElement.querySelector(".ok").textContent = "copiado ✓";
        setTimeout(() => (b.parentElement.querySelector(".ok").textContent = ""), 1500);
      });

      ui.drop($("#scenePanel"), importFiles);
      $("#shotsCounts").onclick = importModal;

      $("#shotsGallery").addEventListener("click", (e) => {
        const asBase = e.target.closest("button.asBase");
        if (asBase) return prepareBase("candidate", null, asBase.dataset.base);
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id, i = order.indexOf(id);
        // A cena do produto tem escolha única (`data-ord="1"`); as cenas ordenam N frames.
        if (isProduct()) order = i >= 0 ? [] : [id];
        else if (i >= 0) order.splice(i, 1);
        else order.push(id);
        renderCands();
      });
      $("#shotsGallery").addEventListener("dblclick", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = (isProduct() ? prod : cands).find((x) => x.id === card.dataset.id);
        if (c) window.open(ctx.files(c.file), "_blank");
      });

      $("#btnShotsSave").onclick = async () => {
        if (!scene) return toast("Abra uma cena primeiro.");
        const up = $("#shotsUpscaled").checked;
        try {
          if (isProduct()) {
            const id = order[0] || null;
            const c = prod.find((x) => x.id === id);
            await api(`${base()}/product/select`, { method: "POST", body: JSON.stringify({ id, upscaled: !!(c && c.upscaled) || up }) });
            toast(id ? "Cena do produto salva · storyboard.md atualizado" : "Cena do produto removida");
            await loadProd(); await loadScenes(); ctx.guide();
            return;
          }
          // O upscale do CLI já marca o candidato; o checkbox cobre quem fez o upscale na UI.
          const shots = order.map((id) => {
            const c = cands.find((x) => x.id === id);
            return { id, upscaled: !!(c && c.upscaled) || up };
          });
          const r = await api(`${base()}/scenes/${scene}/select`, { method: "POST", body: JSON.stringify({ shots }) });
          toast(r.warning || `${r.shots.length} frame(s) salvos em ${scene} · storyboard.md atualizado`);
          await loadCands(); await loadScenes(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      scene = null; order = [];
      clearPrompts();
      await loadScenes();
      await loadProd();
      renderSceneList();
      await openScene(scenes.length ? scenes[0].id : PRODUCT);
      ui.renderGuide("shots");
    },
    destroy() {},
  };
});
