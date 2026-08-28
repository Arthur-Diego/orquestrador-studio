// Etapa 4 — Storyboard (aulas 010 + 011, ADR-015): o lugar único do storyboard.
//
// Duas metades na mesma tela, cada uma no seu próprio escopo (sem colisão de nomes):
//  - IDEAÇÃO + CENAS EM TEXTO (aula 010): ideias a partir da imagem base (uma instrução por vez,
//    4 gerações quando incerto / 1 quando tweak) e a história em ~5 cenas (começo → descoberta →
//    ação → desfecho). Rotas sob `/storyboard/...`.
//  - ÂNGULOS POR CENA (aula 011) + cena do produto (aula 013): por cena, várias imagens/ângulos
//    (upload + prompt de ângulo, escolher e ordenar) + a cena do produto. Rotas sob
//    `/storyboard/angles/...`. Escreve `storyboard/storyboard.json`, que o animate (etapa 5) lê.
//
// O guia é único ("storyboard"): as duas metades atualizam o mesmo painel.
Studio.register("storyboard", (ctx) => {
  const ideation = makeIdeation(ctx);
  const angles = makeAngles(ctx);

  return {
    init() {
      ideation.init();
      angles.init();
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      await ideation.onProject();
      await angles.onProject();
      Studio.ui.renderGuide("storyboard");
    },
    destroy() { ideation.destroy(); angles.destroy(); },
  };

  // ======================================================================================
  // METADE 1 — ideação + cenas em texto (aula 010)
  // ======================================================================================
  function makeIdeation(ctx) {
    const { $, api, toast } = ctx;
    const ui = Studio.ui;
    const esc = (s) => ui.esc(s);
    let meta = { kinds: [], presets: [], models: [], arc: [], counts: { uncertain: 4, tweak: 1 } };
    let ideas = [], scenes = [], hasBase = false;
    let instruction = "";      // instrução montada (o `.txt` mostra o texto de repouso quando vazia)
    let panelDrop = null;      // <input type="file"> criado por `ui.drop` no painel 01

    const EMPTY_INSTRUCTION = "a instrução montada aparece aqui — os botões não gastam crédito";
    const url = (p) => `/api/projects/${ctx.pid()}/storyboard${p || ""}`;

    const momOf = (label) => String(label || "").normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z]/g, "");

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
      $("#sbCounts").textContent = `${st.ideas} ideias · ${st.selected} escolhidas`;
      $("#sbBase").classList.toggle("hidden", !hasBase);
      if (hasBase) $("#sbBase").src = ctx.files(st.base_image);
      $("#sbGen4").disabled = $("#sbGen1").disabled = !hasBase;
    }

    async function loadPresets() {
      meta = await api(url("/instructions"));
      $("#sbKind").innerHTML = meta.kinds.map((k) => `<option value="${esc(k.kind)}">${esc(k.label)}</option>`).join("");
      $("#sbPreset").innerHTML = `<option value="">— fórmulas da aula —</option>` +
        meta.presets.map((p, i) => `<option value="${i}">${esc(p.label)}</option>`).join("");
      kindHint();
    }
    function kindHint() {
      const k = meta.kinds.find((x) => x.kind === $("#sbKind").value);
      $("#sbKind").title = k ? k.ui_hint : "";
    }

    function renderInstruction() {
      $("#sbInstruction").textContent = instruction || EMPTY_INSTRUCTION;
    }

    async function build(count) {
      try {
        const r = await api(url("/instructions"), { method: "POST", body: JSON.stringify({ kind: $("#sbKind").value, text: $("#sbText").value, count }) });
        instruction = r.instruction;
        renderInstruction();
        if (r.ui_hint) toast(r.ui_hint);
        return r;
      } catch (err) { toast(err.message); return null; }
    }

    async function importFiles(files) {
      if (!files.length) return;
      try {
        const fd = new FormData();
        [...files].forEach((f) => fd.append("files", f));
        fd.append("prompt", instruction);
        const r = await fetch(url("/import/upload"), { method: "POST", body: fd });
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.detail || r.statusText);
        toast(`${body.added} ideias importadas${body.skipped ? ` · ${body.skipped} ignoradas` : ""}`);
        await refresh();
      } catch (err) { toast(err.message); }
    }

    function importModal() {
      const m = ui.modal({
        title: "Importar ideias",
        subtitle: "Gere na interface da Higgsfield e traga os resultados para o storyboard.",
        html: `<div class="import-row">
          <label class="drop" id="sbDrop">Arraste imagens aqui ou <input id="sbUpload" type="file" accept="image/*" multiple hidden><u>escolha arquivos</u></label>
          <div class="col">
            <button type="button" id="sbBtnDownloads" class="ghost">Importar da pasta Downloads</button>
            <label class="inline">últimos <input id="sbMinutes" class="mini wide" type="number" value="120" min="5"> min</label>
            <button type="button" id="sbBtnHistory" class="ghost">Importar do histórico Higgsfield</button>
            <span class="fine">precisa de login no CLI</span>
          </div>
        </div>`,
      });
      ui.drop(m.el.querySelector("#sbDrop"), (files) => { m.close(); importFiles(files); });
      m.el.querySelector("#sbBtnDownloads").onclick = async () => {
        const minutes = +m.el.querySelector("#sbMinutes").value;
        m.close();
        try {
          const r = await api(url("/import/downloads"), { method: "POST", body: JSON.stringify({ since_minutes: minutes, prompt: instruction }) });
          toast(`${r.added} novas de ${r.scanned} imagens recentes`); await refresh();
        } catch (err) { toast(err.message); }
      };
      m.el.querySelector("#sbBtnHistory").onclick = async () => {
        m.close();
        try {
          const r = await api(url("/import/history"), { method: "POST", body: JSON.stringify({ size: 50 }) });
          toast(`${r.added} imagens de ${r.jobs} jobs`); await refresh();
        } catch (err) { toast(err.message); }
      };
    }

    async function loadIdeas() {
      if (!ctx.pid()) { ideas = []; return; }
      ideas = (await api(url("/candidates"))).ideas;
    }

    function pickerModal(i) {
      const atual = scenes[i] ? scenes[i].image : null;
      const gal = ideas.length ? ideas.map((c) =>
        `<div class="card ${c.file === atual ? "sel" : ""}" data-id="${esc(c.id)}" tabindex="0" title="${esc(c.prompt)}">
           <img loading="lazy" src="${esc(ctx.files(c.thumb || c.file))}" alt=""></div>`).join("")
        : `<div class="empty">Nenhuma ideia ainda — gere na Higgsfield com a instrução do painel 01 e importe.</div>`;
      const m = ui.modal({
        title: `Cena ${i + 1} — escolher a ideia`,
        subtitle: "Um clique anexa a ideia à cena (ela passa a viver em storyboard/ideas/).",
        html: `<div id="sbGallery" class="gallery sm">${gal}</div>`,
        actions: [
          { label: "Importar ideias…", onClick: () => setTimeout(importModal, 0) },
          { label: "Sem imagem", onClick: () => attach(i, null) },
        ],
      });
      m.el.querySelector("#sbGallery").addEventListener("click", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        m.close(); attach(i, card.dataset.id);
      });
      m.el.querySelector("#sbGallery").addEventListener("dblclick", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = ideas.find((x) => x.id === card.dataset.id);
        if (c) window.open(ctx.files(c.file), "_blank");
      });
    }

    async function attach(i, ideaId) {
      scenes = collect();
      if (!scenes[i]) return;
      if (!ideaId) { scenes[i].image = null; renderScenes(); return; }
      try {
        const alvo = ideas.find((c) => c.id === ideaId);
        if (alvo && !alvo.selected) {
          const ids = [...new Set(ideas.filter((c) => c.selected).map((c) => c.id).concat(ideaId))];
          await api(url("/candidates/select"), { method: "POST", body: JSON.stringify({ ids }) });
          await loadIdeas();
        }
        const escolhida = ideas.find((c) => c.id === ideaId);
        scenes[i].image = escolhida ? escolhida.file : null;
        renderScenes();
        await loadStatus(); ctx.guide();
      } catch (err) { toast(err.message); }
    }

    async function loadScenes() {
      scenes = (await api(url("/scenes"))).scenes;
      renderScenes();
    }
    function renderScenes() {
      const total = scenes.length;
      $("#sbScenes").innerHTML = scenes.map((s, i) => {
        const arc = arcOf(i + 1, total);
        return `<div class="scene-row" data-i="${i}" data-image="${esc(s.image || "")}">
           <span class="mom" data-mom="${esc(momOf(arc.label))}" title="Cena ${i + 1} · ${esc(arc.label)}">${esc(arc.label)}</span>
           <div class="thumb pick sb-pick" tabindex="0" role="button" title="escolher a imagem da cena">${s.image ? `<img loading="lazy" src="${esc(ctx.files(s.image))}" alt="">` : ""}</div>
           <textarea class="txt sbTxt" rows="1" placeholder="${esc(arc.label)}: ${esc(arc.hint)} (ex.: close no astronauta andando na nevasca)">${esc(s.text)}</textarea>
           <div class="acts">
             <button type="button" class="ghost mini sbUp" title="subir">↑</button><button type="button" class="ghost mini sbDown" title="descer">↓</button><button type="button" class="ghost mini sbDel" title="remover">✕</button>
           </div>
         </div>`;
      }).join("");
      ui.autosize("#sbScenes textarea.sbTxt");
    }
    function collect() {
      return [...document.querySelectorAll("#sbScenes .scene-row")].map((el) => ({
        text: el.querySelector(".sbTxt").value, image: el.dataset.image || null,
      }));
    }

    async function refresh() {
      await loadIdeas(); await loadStatus(); ctx.guide();
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
          if (!instruction) return toast("Monte a instrução primeiro.");
          await navigator.clipboard.writeText(instruction);
          $("#sbCopied").textContent = "copiado ✓"; setTimeout(() => ($("#sbCopied").textContent = ""), 1500);
        };

        panelDrop = ui.drop($("#sbIdeas"), importFiles);
        if (panelDrop) panelDrop.accept = "image/*";
        $("#sbCounts").onclick = importModal;

        $("#sbAdd").onclick = () => { scenes = collect().concat({ text: "", image: null }); renderScenes(); };
        $("#sbScenes").addEventListener("click", (e) => {
          const box = e.target.closest(".scene-row"); if (!box) return;
          const i = +box.dataset.i;
          if (e.target.closest(".thumb")) return pickerModal(i);
          scenes = collect();
          if (e.target.classList.contains("sbDel")) scenes.splice(i, 1);
          else if (e.target.classList.contains("sbUp") && i > 0) scenes.splice(i - 1, 0, scenes.splice(i, 1)[0]);
          else if (e.target.classList.contains("sbDown") && i < scenes.length - 1) scenes.splice(i + 1, 0, scenes.splice(i, 1)[0]);
          else return;
          renderScenes();
        });
        $("#sbScenes").addEventListener("keydown", (e) => {
          if (e.key !== "Enter" && e.key !== " ") return;
          const t = e.target.closest(".thumb"); if (!t) return;
          e.preventDefault(); pickerModal(+t.closest(".scene-row").dataset.i);
        });
        $("#sbSave").onclick = async () => {
          try {
            const r = await api(url("/scenes"), { method: "PUT", body: JSON.stringify({ scenes: collect() }) });
            scenes = r.scenes; renderScenes(); await loadStatus(); ctx.guide();
            toast(`${r.scenes.length} cenas salvas · storyboard.md atualizado`);
          } catch (err) { toast(err.message); }
        };
        $("#sbRender").onclick = async () => {
          try {
            const r = await api(url("/render"), { method: "POST" });
            await loadStatus(); ctx.guide(); toast("storyboard.md gerado");
            if (r && r.storyboard_md) window.open(ctx.files(r.storyboard_md), "_blank");
          } catch (err) { toast(err.message); }
        };
      },
      async onProject() {
        if (!ctx.pid()) return;
        instruction = ""; renderInstruction();
        await loadPresets();
        await loadStatus();
        await loadIdeas();
        await loadScenes();
      },
      destroy() {},
    };
  }

  // ======================================================================================
  // METADE 2 — ângulos por cena (aula 011) + cena do produto (aula 013)
  // ======================================================================================
  function makeAngles(ctx) {
    const { $, api, toast } = ctx;
    const ui = Studio.ui;
    const esc = (s) => ui.esc(s);
    const base = () => `/api/projects/${ctx.pid()}/storyboard/angles`;

    const PRODUCT = "__produto__";                 // cena virtual: o card "produto" do painel 03
    let scenes = [], scene = null, cands = [], order = [], prod = [];
    let prodState = { ref_ready: false, selected: false };
    let prodTick = 0;             // cache-buster: product_final.png é regravado no mesmo caminho

    const isProduct = () => scene === PRODUCT;
    const sceneLabel = (id) => String(id || "").replace(/^cena/, "cena ");
    const prodPick = () => prod.find((c) => c.selected) || null;

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
      const pick = prodPick();
      const produto = card(
        PRODUCT, "produto", prodState.selected ? `${ctx.files("storyboard/product/product_final.png")}?t=${prodTick}` : null,
        prodState.selected && pick && pick.upscaled ? 1 : 0, prodState.selected ? 1 : 0,
        prodState.selected ? "cena do produto salva (aula 013)"
          : prodState.ref_ready ? "imagem 1 enviada — rode as duas instruções e importe o resultado"
            : "cena do produto (aula 013): envie a imagem 1 e rode as duas instruções",
        prodState.selected ? `<button type="button" class="sh-act shProdClear">remover</button>` : "");
      $("#sceneList").innerHTML = (cenas.join("") + produto)
        || `<div class="empty">Nenhuma cena — escreva a história no painel 02.</div>`;
    }

    async function openScene(id) {
      scene = id; order = [];
      clearPrompts();
      const produto = isProduct();
      $("#sceneTitle").textContent = produto ? "Produto — escolher e ordenar"
        : `${sceneLabel(id).replace("cena", "Cena")} — escolher e ordenar`;
      ["#promptKind", "#promptSubject", "#promptScale", "#promptAngle"]
        .forEach((sel) => $(sel).classList.toggle("hidden", produto));
      $("#editsBox").classList.toggle("hidden", produto || $("#promptKind").value !== "edit");
      if (produto) { await loadProd(); } else { await loadCands(); }
      renderSceneList();
    }

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
          <button type="button" id="shBaseScene" class="ghost">Imagem da cena (ideia do painel 02)</button>
          <button type="button" id="shBaseCampaign" class="ghost">Imagem base da campanha</button>
          <label class="drop sm" id="shBaseDrop">Arraste uma imagem ou <input id="shBaseUpload" type="file" accept="image/*" hidden><u>envie um arquivo</u></label>
        </div>`,
      });
      m.el.querySelector("#shBaseScene").onclick = () => { m.close(); prepareBase("storyboard"); };
      m.el.querySelector("#shBaseCampaign").onclick = () => { m.close(); prepareBase("base"); };
      ui.drop(m.el.querySelector("#shBaseDrop"), (files) => { m.close(); prepareBase("upload", files[0]); });
    }

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

    async function importFiles(files) {
      if (!files.length || !scene) return;
      const uploadUrl = isProduct() ? `${base()}/product/import/upload` : `${base()}/scenes/${scene}/import/upload`;
      try {
        const r = await ui.upload(uploadUrl, files);
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
        const dlUrl = produto ? `${base()}/product/import/downloads` : `${base()}/scenes/${scene}/import/downloads`;
        m.close();
        try {
          const r = await api(dlUrl, { method: "POST", body: JSON.stringify({ since_minutes: minutes }) });
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
      api("/api/storyboard/angles/downloads-folder")
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
            const shots = order.map((id) => {
              const c = cands.find((x) => x.id === id);
              return { id, upscaled: !!(c && c.upscaled) || up };
            });
            const r = await api(`${base()}/scenes/${scene}/select`, { method: "POST", body: JSON.stringify({ shots }) });
            toast(r.warning || `${r.shots.length} frame(s) salvos em ${scene} · storyboard.md atualizado`);
            await loadCands(); await loadScenes(); ctx.guide();
          } catch (err) { toast(err.message); }
        };
      },
      async onProject() {
        if (!ctx.pid()) return;
        scene = null; order = [];
        clearPrompts();
        await loadScenes();
        await loadProd();
        renderSceneList();
        await openScene(scenes.length ? scenes[0].id : PRODUCT);
      },
      destroy() {},
    };
  }
});
