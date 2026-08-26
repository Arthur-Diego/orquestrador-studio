// Etapa 4 — Storyboard (aula 010): ideias a partir da imagem base (uma instrução por vez,
// 4 gerações quando incerto / 1 quando é tweak) e a história em ~5 cenas de texto, na estrutura
// começo → descoberta → ação → desfecho.
//
// Wave 4 (fidelidade ao protótipo): a tela tem DOIS painéis. A importação das ideias e a escolha
// da imagem de cada cena não têm painel próprio — a importação abre pelo chip "N ideias · N
// escolhidas" (ou por arrastar arquivos sobre o painel 01) e o picker de ideias abre pela thumb
// da cena. Não há geração pelo CLI nesta etapa (a aula 010 gera na UI da Higgsfield); as rotas
// `/cost`, `/generate` e `/job` continuam no backend.
Studio.register("storyboard", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const esc = (s) => ui.esc(s);
  let meta = { kinds: [], presets: [], models: [], arc: [], counts: { uncertain: 4, tweak: 1 } };
  let ideas = [], scenes = [], hasBase = false;
  let instruction = "";      // instrução montada (o `.txt` mostra o texto de repouso quando vazia)
  let panelDrop = null;      // <input type="file"> criado por `ui.drop` no painel 01

  const EMPTY_INSTRUCTION = "a instrução montada aparece aqui — os botões não gastam crédito";
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
  // A dica do tipo de instrução não é desenhada pelo protótipo: vira `title` do select.
  function kindHint() {
    const k = meta.kinds.find((x) => x.kind === $("#sbKind").value);
    $("#sbKind").title = k ? k.ui_hint : "";
  }

  function renderInstruction() {
    const el = $("#sbInstruction");
    el.textContent = instruction || EMPTY_INSTRUCTION;
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

  // ---------- importação (popover; o painel 01 inteiro também aceita arrastar) ----------
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

  // ---------- ideias ----------
  async function loadIdeas() {
    if (!ctx.pid()) { ideas = []; return; }
    ideas = (await api(url("/candidates"))).ideas;
  }

  /** Picker de ideias da cena `i` — a galeria do protótipo mora aqui, não num painel. */
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

  /**
   * Anexa (ou desanexa) uma ideia à cena. Escolher deixou de ser um botão: anexar já promove a
   * ideia para `storyboard/ideas/` (`/candidates/select`), que é onde `save_scenes` aceita a
   * imagem. Por isso a seleção é reenviada como união do que já estava escolhido.
   */
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

  // ---------- cenas ----------
  async function loadScenes() {
    scenes = (await api(url("/scenes"))).scenes;
    renderScenes();
  }
  function renderScenes() {
    const total = scenes.length;
    // `.scene-row` do shell: momento narrativo | thumb clicável | texto editável com cara estática.
    // Os botões ↑ ↓ ✕ NUNCA recebem filhos: o handler usa `e.target.classList.contains`.
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

      // O painel 01 inteiro é alvo de drop (`.panel.over` só enquanto arrasta) e o chip de
      // contagem abre o popover de importação — nada visível a mais que o protótipo desenha.
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
      // Sem link permanente na tela: "Gerar storyboard.md" abre o documento ao terminar (4.27).
      $("#sbRender").onclick = async () => {
        try {
          const r = await api(url("/render"), { method: "POST" });
          await loadStatus(); ctx.guide(); toast("storyboard.md gerado");
          if (r && r.storyboard_md) window.open(ctx.files(r.storyboard_md), "_blank");
        } catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      instruction = ""; renderInstruction();
      await loadPresets();
      await loadStatus();
      await loadIdeas();
      await loadScenes();
      ui.renderGuide("storyboard");
    },
    destroy() {},
  };
});
