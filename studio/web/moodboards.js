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
    const cards = boards.map((b) => {
      // Mosaico quadricular das selecionadas (wave 5 · ponto 4). Fallback à capa em respostas
      // antigas sem `thumbs`; sem imagem alguma, o próprio mosaico desenha "sem imagens ainda".
      const rels = (b.thumbs && b.thumbs.length) ? b.thumbs : (b.cover ? [b.cover] : []);
      const thumbs = rels.map((rel) => mb(b.id, rel));
      return `
      <article class="ovcard mb-card" data-mb="${esc(b.id)}" tabindex="0" role="button" title="${esc(b.name)}">
        ${ui.moodMosaic(thumbs, {})}
        <h4>${esc(b.name)}</h4>
        <p class="desc">${esc(b.vibe || b.note || "")}</p>
        <div class="mb-meta">${ui.chip(`${b.count} imagem(ns)`, "mode")}${b.vibe ? ui.chip(`vibe: ${b.vibe}`, "info") : ""}</div>
      </article>`;
    }).join("");
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
      <style>
        .msc-folder{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:.8rem;opacity:.8;margin:.3rem 0 0}
        .msc-folder code{font-family:ui-monospace,monospace;background:rgba(120,120,120,.16);padding:2px 6px;border-radius:6px;word-break:break-all}
        .msc-hint{font-size:.82rem;opacity:.72;margin:.2rem 0 .6rem}
        .msc-card .use-btn{position:absolute;bottom:6px;left:6px;font-size:.72rem;padding:2px 8px;border-radius:999px;
          border:none;cursor:pointer;background:rgba(60,150,90,.9);color:#fff;z-index:2}
        .msc-card .use-btn:hover{background:rgba(60,170,100,1)}
      </style>
      <header class="stephead">
        <span class="eyebrow"><button class="link" id="mbBack">← Biblioteca</button> · Mood board <span class="ext">[extensão]</span></span>
        <h2 id="mbTitle">${esc(data.name)}</h2>
        <p class="lede" id="mbSub">${esc(data.vibe || data.note || "Importe imagens que definem a vibe deste board, cure a galeria e gere um prompt de vibe.")}</p>
        <p class="msc-folder"><span>Pasta do board:</span> <code id="mbFolder">${esc(data.folder || "")}</code></p>
        <div class="ov-actions">
          <button type="button" class="ghost" id="btnMbOpenFolder" title="Abrir a pasta do board no explorador do SO — fácil de copiar as fotos">Abrir pasta</button>
          <button type="button" class="ghost" id="btnMbRename">Renomear</button>
          <button type="button" class="ghost danger" id="btnMbDelete">Apagar mood board</button>
        </div>
      </header>

      <section class="panel">
        <div class="panel-head">
          <h3><span class="pn">01</span>Importar imagens</h3>
          <span id="mbImpCount" class="chip mode"></span>
        </div>
        <div class="import-row">
          <label class="drop" id="mbDrop">Arraste imagens aqui ou <input id="mbUpload" type="file" accept="image/*" multiple hidden><u>escolha arquivos</u></label>
          <div class="col">
            <button id="btnMbDownloads" class="ghost" title="Imagens recentes da pasta Downloads">Importar da pasta Downloads</button>
            <button id="btnMbHistory" class="ghost" title="via higgsfield generate list --image (precisa de login no CLI)">Importar do histórico Higgsfield</button>
          </div>
        </div>
        <p class="msc-hint">Importadas ficam aqui até você mandá-las ao board. Cada uma pode gerar outros ângulos (<b>▨ ângulos</b>) e é promovida à curadoria com <b>usar no board</b>.</p>
        <div id="mbImported" class="gallery sm"></div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3><span class="pn">02</span>Curar a galeria</h3>
          <div class="row wrap">
            <span id="mbCounts" class="chip mode"></span>
            <button id="btnMbSave" class="primary">Salvar seleção</button>
          </div>
        </div>
        <p class="fine">Só as imagens escolhidas do painel 01 aparecem aqui (um board é uma vibe só — até 8). Clique numa imagem para tirá-la do board. O que você salvar é o que a etapa 2 puxa e a etapa 3 mostra.</p>
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
    document.querySelector("#btnMbOpenFolder").onclick = () => openBoardFolder(st);

    const mode = document.querySelector("#mbMode");
    const cs = document.querySelector("#mbClaude");
    cs.textContent = data.available_claude ? "bot: claude ok" : "bot: sem claude";
    cs.className = "chip " + (data.available_claude ? "ok" : "warn");
    [...mode.options].forEach((o) => { if (o.value !== "template") o.disabled = !data.available_claude; });
    if (!data.available_claude) mode.value = "template";

    // Painel 01 (importadas aguardando): "▨ ângulos" abre o multishot; "usar no board" promove
    // a candidata à seleção (vai ao painel 02). Rework ADR-019: a mesma lista `candidates` é
    // dividida por `st.sel` — não-selecionadas no 01, selecionadas no 02.
    // Bug fix (ADH-OS-20260827-05): mutar `st.sel` (não o `sel` do closure), pois `reload()`
    // reatribui `st.sel` a cada import.
    const imp = document.querySelector("#mbImported");
    imp.addEventListener("click", (e) => {
      const msb = e.target.closest(".ms-btn");
      if (msb) { e.stopPropagation(); openMultishot(st, msb.dataset.ms); return; }
      const use = e.target.closest(".use-btn");
      if (use) { e.stopPropagation(); st.sel.add(use.dataset.use); renderPanels(st); return; }
    });

    // Painel 02 (curar): "▨ ângulos" abre o multishot; clicar no card tira a imagem do board
    // (volta ao painel 01). A seleção só é persistida em "Salvar seleção".
    const gal = document.querySelector("#mbGallery");
    gal.addEventListener("click", (e) => {
      const msb = e.target.closest(".ms-btn");
      if (msb) { e.stopPropagation(); openMultishot(st, msb.dataset.ms); return; }
      const card = e.target.closest(".card"); if (!card) return;
      st.sel.delete(card.dataset.id); renderPanels(st);
    });

    renderPanels(st);
    paintPalette(data.palette.colors || []);
    if (data.prompt) showPrompt(data.prompt);
  }

  function cardHtml(mbid, c, promotable) {
    return `<div class="card msc-card ${promotable ? "" : "sel"}" data-id="${esc(c.id)}" tabindex="0" title="${esc(c.name || "")}">
       <img loading="lazy" src="${esc(mb(mbid, "candidates/" + c.thumb))}" alt="">
       ${c.role === "multishot" ? `<span class="src">multishot</span>` : ""}
       <button class="ms-btn" type="button" data-ms="${esc(c.id)}" title="Gerar multishot (outros ângulos) desta imagem [extensão]">▨ ângulos</button>
       ${promotable ? `<button class="use-btn" type="button" data-use="${esc(c.id)}" title="Adicionar esta imagem ao board (painel 02)">usar no board</button>` : ""}
       <span class="term">${esc(`${c.source || ""} · ${c.name || ""}`)}</span></div>`;
  }

  function renderPanels(st) {
    const { data, sel } = st;
    const waiting = data.candidates.filter((c) => !sel.has(c.id));
    const chosen = data.candidates.filter((c) => sel.has(c.id));
    const imp = document.querySelector("#mbImported");
    imp.innerHTML = waiting.length
      ? waiting.map((c) => cardHtml(data.id, c, true)).join("")
      : `<div class="empty">Nenhuma imagem aguardando — importe acima ou gere ângulos.</div>`;
    const gal = document.querySelector("#mbGallery");
    gal.innerHTML = chosen.length
      ? chosen.map((c) => cardHtml(data.id, c, false)).join("")
      : `<div class="empty">Nenhuma imagem no board ainda — use "usar no board" no painel 01.</div>`;
    counts(st);
  }

  function counts(st) {
    const waiting = st.data.candidates.length - st.sel.size;
    const ic = document.querySelector("#mbImpCount");
    if (ic) ic.textContent = `${waiting} aguardando`;
    document.querySelector("#mbCounts").textContent = `${st.data.candidates.length} candidatas · ${st.sel.size} escolhidas (máx. 8)`;
  }

  async function openBoardFolder(st) {
    try {
      const r = await api(`/api/moodboards/${encodeURIComponent(st.data.id)}/open-folder`, { method: "POST", body: JSON.stringify({ target: "board" }) });
      toast(r.opened ? "Pasta do board aberta no explorador" : `Pasta do board: ${r.path}`);
    } catch (err) { toast(err.message); }
  }

  /** Multishot [extensão] (ADR-017): gera outros ângulos da imagem de vibe escolhida e os
   * adiciona como candidatas do board (a galeria mostra os resultados para curar). */
  function openMultishot(st, id) {
    if (!window.Studio.multishot) { toast("Componente de multishot indisponível"); return; }
    const mbid = st.data.id;
    const cand = (st.data.candidates || []).find((c) => c.id === id);
    if (!cand) { toast("Imagem não encontrada"); return; }
    window.Studio.multishot.open({
      title: "Multishot da imagem de vibe",
      subtitle: `Mood board "${st.data.name}" · outros ângulos da mesma vibe (aula 011) [extensão]`,
      sourceUrl: mb(mbid, "candidates/" + cand.file),
      action: "mood.multishot",
      parentId: id,
      canRemove: true,
      endpoints: {
        generate: `/api/moodboards/${encodeURIComponent(mbid)}/multishot/generate`,
        job: `/api/moodboards/${encodeURIComponent(mbid)}/multishot/job`,
        candidates: `/api/moodboards/${encodeURIComponent(mbid)}/candidates`,
        upload: `/api/moodboards/${encodeURIComponent(mbid)}/import/upload`,
        importDownloads: `/api/moodboards/${encodeURIComponent(mbid)}/import/downloads`,
        downloadsFolder: `/api/moodboards/${encodeURIComponent(mbid)}/downloads-folder`,
        openFolder: `/api/moodboards/${encodeURIComponent(mbid)}/open-folder`,
      },
      fileUrl: (rel) => mb(mbid, "candidates/" + rel),
      onChanged: () => reload(st),
    });
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
    renderPanels(st);
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
    const gen = () => api(`/api/moodboards/${encodeURIComponent(st.data.id)}/prompt/generate`, { method: "POST", body: JSON.stringify({
      mode, instruction: document.querySelector("#mbInstruction").value,
      image_ids: [...st.sel], no_people: document.querySelector("#mbNoPeople").checked }) });
    const aplicar = (r) => {
      showPrompt(r.prompt);
      toast(`Prompt ${r.source === "claude" ? "escrito pelo bot" : "do template"} (${r.seconds || 0}s)`);
    };
    // Modo template é instantâneo (sem Claude): não pisca o modal.
    if (mode === "template") {
      btn.disabled = true;
      try { aplicar(await gen()); } catch (err) { toast(err.message); }
      btn.disabled = false;
      return;
    }
    // Chamada SÍNCRONA ao Claude: modal com as FASES reais + cronômetro (progresso honesto).
    const p = ui.progress({ title: "Gerar prompt de vibe", subtitle: "Bot de prompts (Claude) — mood board [extensão]" });
    p.step(mode === "images" ? `Preparando as imagens do board (${st.sel.size})` : "Preparando o brief");
    p.step("Consultando o Claude…");
    btn.disabled = true;
    try {
      const r = await gen();
      p.step("Formatando no padrão do bot");
      aplicar(r);
      p.ok("Pronto"); setTimeout(() => p.close(), 700);
    } catch (err) { p.fail(err.message); toast(err.message); }
    btn.disabled = false;
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
