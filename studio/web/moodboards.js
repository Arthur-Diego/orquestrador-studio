// Área global "Mood boards [extensão]" (ADR-013): biblioteca de mood boards reutilizáveis,
// independente de campanha. Roteamento por hash reservado: `#/moodboards` (lista) e
// `#/moodboards/<mbid>` (editor). Carregado depois de app.js e ui.js — reusa os componentes do
// catálogo do shell (Studio.ui.tile/modal/drop/upload/copyBtn/chip) e o contexto (api, toast).
//
// Nada aqui muda o modelo de vibe única por campanha (ADR-007): o board é uma semente que a
// etapa 2 pode PUXAR e a etapa 3 pode referenciar visualmente.
(function () {
  const ui = window.Studio.ui;
  const esc = (s) => ui.esc(s);
  const ctx = () => window.Studio.ctx;
  const api = (p, o) => ctx().api(p, o);
  const toast = (m) => ctx().toast(m);
  const $main = () => document.querySelector("#main");
  const mb = (mbid, rel) => `/mbfiles/${encodeURIComponent(mbid)}/${rel}`;

  function goList() { if (location.hash === "#/moodboards") open(null); else location.hash = "#/moodboards"; }
  function goEditor(mbid) { location.hash = `#/moodboards/${encodeURIComponent(mbid)}`; }

  // ---------- lista ----------
  async function renderList() {
    const main = $main();
    main.onclick = null;
    let boards = [];
    try { boards = await api("/api/moodboards"); }
    catch (e) { main.innerHTML = `<div class="empty">Não foi possível carregar a biblioteca: ${esc(e.message)}</div>`; return; }
    const cards = boards.map((b) => `
      <article class="ovcard mb-card" data-mb="${esc(b.id)}" tabindex="0" role="button" title="${esc(b.name)}">
        <div class="mb-cover">${b.cover
          ? `<img src="${esc(mb(b.id, b.cover))}" loading="lazy" alt="">`
          : `<span class="mb-nocover">sem imagens ainda</span>`}</div>
        <h4>${esc(b.name)}</h4>
        <p class="desc">${esc(b.vibe || b.note || "")}</p>
        <div class="mb-meta">${ui.chip(`${b.count} imagem(ns)`, "mode")}${b.vibe ? ui.chip(`vibe: ${b.vibe}`, "info") : ""}</div>
      </article>`).join("");
    main.innerHTML = `
      <header class="stephead ov">
        <span class="eyebrow">Biblioteca · independente de campanha</span>
        <h2>Mood boards <span class="ext">[extensão]</span></h2>
        <p class="lede">Mood boards reutilizáveis: monte uma vez e use em qualquer campanha. A etapa 2 pode <b>puxar</b> um board e a etapa 3 pode referenciá-lo visualmente. Estende a vibe única do curso (ADR-007).</p>
        <div class="ov-actions"><button type="button" class="primary" id="btnNewBoard">Novo mood board</button></div>
      </header>
      ${boards.length
        ? `<div class="ovgrid mb-grid">${cards}</div>`
        : `<div class="empty-state"><span class="eyebrow">Biblioteca vazia</span><h2>Nenhum mood board ainda</h2><p class="lede">Crie um mood board reutilizável — importe imagens que definem uma vibe e use-o quando quiser.</p><button class="primary" id="btnNewBoard2" type="button">Criar o primeiro mood board</button></div>`}`;
    const openNew = () => newBoardModal();
    const b1 = document.querySelector("#btnNewBoard"); if (b1) b1.onclick = openNew;
    const b2 = document.querySelector("#btnNewBoard2"); if (b2) b2.onclick = openNew;
    main.onclick = (ev) => { const c = ev.target.closest("[data-mb]"); if (c) goEditor(c.dataset.mb); };
    main.onkeydown = (ev) => { const c = ev.target.closest("[data-mb]"); if (c && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); goEditor(c.dataset.mb); } };
  }

  function newBoardModal() {
    const m = ui.modal({
      title: "Novo mood board",
      subtitle: "Um mood board reutilizável — independente de campanha.",
      html: `<form id="mbForm" novalidate>
        <label class="field" for="mbName"><span class="eyebrow">Nome do mood board</span>
          <input id="mbName" name="name" required maxlength="80" placeholder="ex.: Neon Snow"></label>
        <label class="field" for="mbNote"><span class="eyebrow">Nota — opcional</span>
          <input id="mbNote" name="note" placeholder="do que se trata este mood"></label>
        <div class="modal-actions"><button type="button" class="ghost lg" data-close>Cancelar</button>
          <button type="submit" class="primary lg">Criar mood board</button></div></form>`,
    });
    const form = m.el.querySelector("#mbForm");
    m.el.querySelector("[data-close]").onclick = m.close;
    form.onsubmit = async (e) => {
      e.preventDefault();
      const name = form.name.value.trim();
      if (!name) { toast("Dê um nome ao mood board"); form.name.focus(); return; }
      try {
        const board = await api("/api/moodboards", { method: "POST", body: JSON.stringify({ name, note: form.note.value.trim() }) });
        m.close(); toast(`Mood board ${board.name} criado`); goEditor(board.id);
      } catch (err) { toast(err.message); }
    };
  }

  // ---------- editor ----------
  async function renderEditor(mbid) {
    const main = $main();
    main.onclick = null; main.onkeydown = null;
    let data;
    try { data = await api(`/api/moodboards/${encodeURIComponent(mbid)}`); }
    catch (e) { main.innerHTML = `<div class="empty">Mood board não encontrado: ${esc(e.message)} <button class="link" id="mbBack">← voltar à biblioteca</button></div>`; const bk = document.querySelector("#mbBack"); if (bk) bk.onclick = goList; return; }

    const sel = new Set(data.candidates.filter((c) => c.selected).map((c) => c.id));
    const st = { data, sel };

    main.innerHTML = `
      <header class="stephead">
        <span class="eyebrow"><button class="link" id="mbBack">← Biblioteca</button> · Mood board <span class="ext">[extensão]</span></span>
        <h2 id="mbTitle">${esc(data.name)}</h2>
        <p class="lede" id="mbSub">${esc(data.vibe || data.note || "Importe imagens que definem a vibe deste board, cure a galeria e gere um prompt de vibe.")}</p>
        <div class="ov-actions">
          <button type="button" class="ghost" id="btnMbRename">Renomear</button>
          <button type="button" class="ghost danger" id="btnMbDelete">Apagar mood board</button>
        </div>
      </header>

      <section class="panel">
        <div class="panel-head"><h3><span class="pn">01</span>Importar imagens</h3></div>
        <div class="import-row">
          <label class="drop" id="mbDrop">Arraste imagens aqui ou <input id="mbUpload" type="file" accept="image/*" multiple hidden><u>escolha arquivos</u></label>
          <div class="col">
            <button id="btnMbDownloads" class="ghost" title="Imagens recentes da pasta Downloads">Importar da pasta Downloads</button>
            <button id="btnMbHistory" class="ghost" title="via higgsfield generate list --image (precisa de login no CLI)">Importar do histórico Higgsfield</button>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3><span class="pn">02</span>Curar a galeria</h3>
          <div class="row wrap">
            <span id="mbCounts" class="chip mode"></span>
            <button id="btnMbSave" class="primary">Salvar seleção</button>
          </div>
        </div>
        <p class="fine">Escolha as imagens que ficam no board (um board é uma vibe só — até 8). O que você salvar é o que a etapa 2 puxa e a etapa 3 mostra.</p>
        <div id="mbPalette" class="palette"><span class="lbl">palette.json · derivado técnico [extensão]</span></div>
        <div id="mbGallery" class="gallery sm"></div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3><span class="pn">03</span>Prompt de vibe do board</h3>
          <div class="row wrap">
            <select id="mbMode">
              <option value="images">imagens do board + instrução</option>
              <option value="brief">brief profissional</option>
              <option value="template">template fixo</option>
            </select>
            <span id="mbClaude" class="chip mode">bot: ?</span>
          </div>
        </div>
        <div class="col g10">
          <input id="mbInstruction" class="lg" placeholder="sua instrução para o bot (ex.: mais neon e neve)">
          <div class="row opts wrap">
            <label class="inline"><input id="mbNoPeople" type="checkbox" checked> sem pessoas</label>
            <button id="btnMbGenPrompt" class="primary">Gerar prompt</button>
          </div>
          <div id="mbPromptList"></div>
        </div>
      </section>`;

    document.querySelector("#mbBack").onclick = goList;
    document.querySelector("#btnMbRename").onclick = () => renameModal(st);
    document.querySelector("#btnMbDelete").onclick = () => deleteModal(st);

    ui.drop(document.querySelector("#mbDrop"), (files) => uploadFiles(st, files));
    document.querySelector("#btnMbDownloads").onclick = () => importDownloads(st);
    document.querySelector("#btnMbHistory").onclick = () => importHistory(st);
    document.querySelector("#btnMbSave").onclick = () => saveSelection(st);
    document.querySelector("#btnMbGenPrompt").onclick = () => genPrompt(st);

    const mode = document.querySelector("#mbMode");
    const cs = document.querySelector("#mbClaude");
    cs.textContent = data.available_claude ? "bot: claude ok" : "bot: sem claude";
    cs.className = "chip " + (data.available_claude ? "ok" : "warn");
    [...mode.options].forEach((o) => { if (o.value !== "template") o.disabled = !data.available_claude; });
    if (!data.available_claude) mode.value = "template";

    const gal = document.querySelector("#mbGallery");
    gal.addEventListener("click", (e) => {
      const card = e.target.closest(".card"); if (!card) return;
      const id = card.dataset.id;
      if (sel.has(id)) sel.delete(id); else sel.add(id);
      card.classList.toggle("sel"); counts(st);
    });

    renderGallery(st);
    paintPalette(data.palette.colors || []);
    if (data.prompt) showPrompt(data.prompt);
  }

  function renderGallery(st) {
    const { data, sel } = st;
    const gal = document.querySelector("#mbGallery");
    gal.innerHTML = data.candidates.length
      ? data.candidates.map((c) =>
        `<div class="card ${sel.has(c.id) ? "sel" : ""}" data-id="${esc(c.id)}" tabindex="0" title="${esc(c.name || "")}">
           <img loading="lazy" src="${esc(mb(data.id, "candidates/" + c.thumb))}" alt="">
           <span class="term">${esc(`${c.source || ""} · ${c.name || ""}`)}</span></div>`).join("")
      : `<div class="empty">Nenhuma imagem ainda — importe no painel 01.</div>`;
    counts(st);
  }

  function counts(st) {
    document.querySelector("#mbCounts").textContent = `${st.data.candidates.length} candidatas · ${st.sel.size} escolhidas (máx. 8)`;
  }

  function paintPalette(colors) {
    document.querySelector("#mbPalette").innerHTML = colors.map((c) =>
      `<span style="background:${esc(c)}" title="${esc(c)}"></span>`).join("") +
      `<span class="lbl">palette.json · derivado técnico [extensão]</span>`;
  }

  function showPrompt(text) {
    document.querySelector("#mbPromptList").innerHTML =
      `<div class="prompt"><div class="row"><span class="eyebrow">Prompt de vibe</span>` +
      ui.copyBtn("#mbPromptList textarea") + `<span class="ok"></span></div>` +
      `<textarea data-i="0">${esc(text)}</textarea></div>`;
    ui.autosize(document.querySelector("#mbPromptList textarea"));
  }

  async function reload(st) {
    const data = await api(`/api/moodboards/${encodeURIComponent(st.data.id)}`);
    st.data = data;
    st.sel = new Set(data.candidates.filter((c) => c.selected).map((c) => c.id));
    renderGallery(st);
    paintPalette(data.palette.colors || []);
  }

  async function uploadFiles(st, files) {
    if (!files || !files.length) return;
    try {
      const r = await ui.upload(`/api/moodboards/${encodeURIComponent(st.data.id)}/import/upload`, files);
      toast(`${r.added} imagem(ns) importada(s)`); await reload(st);
    } catch (err) { toast(err.message); }
  }

  async function importDownloads(st) {
    try {
      const r = await api(`/api/moodboards/${encodeURIComponent(st.data.id)}/import/downloads`, { method: "POST", body: JSON.stringify({ since_minutes: 120 }) });
      toast(`${r.added} novas de ${r.scanned} imagens recentes`); await reload(st);
    } catch (err) { toast(err.message); }
  }

  async function importHistory(st) {
    try {
      const r = await api(`/api/moodboards/${encodeURIComponent(st.data.id)}/import/history`, { method: "POST" });
      toast(`${r.added} imagens de ${r.jobs} jobs`); await reload(st);
    } catch (err) { toast(err.message); }
  }

  async function saveSelection(st) {
    try {
      const r = await api(`/api/moodboards/${encodeURIComponent(st.data.id)}/select`, { method: "POST", body: JSON.stringify({ ids: [...st.sel] }) });
      paintPalette(r.palette || []); toast(`${r.selected} imagem(ns) no board`); await reload(st);
    } catch (err) { toast(err.message); }
  }

  async function genPrompt(st) {
    const mode = document.querySelector("#mbMode").value;
    const btn = document.querySelector("#btnMbGenPrompt");
    if (mode === "images" && !st.sel.size) return toast("Salve/escolha ao menos uma imagem para o bot olhar");
    btn.disabled = true; if (mode !== "template") btn.classList.add("loading");
    try {
      const r = await api(`/api/moodboards/${encodeURIComponent(st.data.id)}/prompt/generate`, { method: "POST", body: JSON.stringify({
        mode, instruction: document.querySelector("#mbInstruction").value,
        image_ids: [...st.sel], no_people: document.querySelector("#mbNoPeople").checked }) });
      showPrompt(r.prompt);
      toast(`Prompt ${r.source === "claude" ? "escrito pelo bot" : "do template"} (${r.seconds || 0}s)`);
    } catch (err) { toast(err.message); }
    btn.classList.remove("loading"); btn.disabled = false;
  }

  function renameModal(st) {
    const m = ui.modal({
      title: "Renomear mood board", subtitle: `O id (${st.data.id}) permanece o mesmo.`,
      html: `<form id="mbRen" novalidate>
        <label class="field"><span class="eyebrow">Nome</span><input name="name" maxlength="80" value="${esc(st.data.name)}"></label>
        <label class="field"><span class="eyebrow">Vibe em palavras — opcional</span><input name="vibe" value="${esc(st.data.vibe || "")}"></label>
        <div class="modal-actions"><button type="button" class="ghost lg" data-close>Cancelar</button><button type="submit" class="primary lg">Salvar</button></div></form>`,
    });
    const form = m.el.querySelector("#mbRen");
    m.el.querySelector("[data-close]").onclick = m.close;
    form.onsubmit = async (e) => {
      e.preventDefault();
      try {
        const r = await api(`/api/moodboards/${encodeURIComponent(st.data.id)}`, { method: "PATCH", body: JSON.stringify({ name: form.name.value.trim(), vibe: form.vibe.value.trim() }) });
        st.data.name = r.name; st.data.vibe = r.vibe;
        document.querySelector("#mbTitle").textContent = r.name;
        m.close(); toast("Mood board atualizado");
      } catch (err) { toast(err.message); }
    };
  }

  function deleteModal(st) {
    const m = ui.modal({
      title: "Apagar mood board [extensão]", subtitle: "Ação destrutiva",
      html: `<p>Isto apaga o mood board <b>${esc(st.data.name)}</b> e todas as suas imagens.</p>
        <p>A biblioteca é global: campanhas que já <b>puxaram</b> este board <b>não</b> são afetadas — a cópia para a campanha é independente.</p>`,
      actions: [
        { label: "Cancelar", kind: "ghost", close: true },
        { label: "Apagar", kind: "primary", onClick: async () => {
          try { await api(`/api/moodboards/${encodeURIComponent(st.data.id)}`, { method: "DELETE" }); toast("Mood board apagado"); goList(); }
          catch (err) { toast(err.message); }
        } },
      ],
    });
    if (m.actions[1]) m.actions[1].classList.add("danger");
  }

  // ---------- entrada da área (chamada por app.js applyRoute) ----------
  function open(mbid) { if (mbid) renderEditor(mbid); else renderList(); }

  window.Studio.moodboards = { open, goList, goEditor };
})();
