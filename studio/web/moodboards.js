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
        <div class="ov-actions"><button type="button" class="primary" id="btnNewBoard">Novo mood board</button><button type="button" class="ghost" id="btnVibes" title="As fotos que o /mood_vibe_scout pesquisou no Pinterest [extensão]">Fotos de vibe</button></div>
      </header>
      ${boards.length
        ? `<div class="ovgrid mb-grid">${cards}</div>`
        : `<div class="empty-state"><span class="eyebrow">Biblioteca vazia</span><h2>Nenhum mood board ainda</h2><p class="lede">Crie um mood board reutilizável — importe imagens que definem uma vibe e use-o quando quiser.</p><button class="primary" id="btnNewBoard2" type="button">Criar o primeiro mood board</button></div>`}`;
    const openNew = () => newBoardModal();
    const b1 = document.querySelector("#btnNewBoard"); if (b1) b1.onclick = openNew;
    const b2 = document.querySelector("#btnNewBoard2"); if (b2) b2.onclick = openNew;
    const bv = document.querySelector("#btnVibes"); if (bv) bv.onclick = goVibes;
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

  // ---------- painel das fotos de vibe do Pinterest [extensão] (ADH-OS-20260902-03) ----------
  // A peneira: o que o `/mood_vibe_scout` baixou do Pinterest vira uma grade paginada (máx. 20
  // por página, teto do servidor) onde se marcam as boas. Marcar COPIA para `_escolhidas/` — a
  // pesquisa nunca é destruída (D3) — e é dessa pasta que a cadeia de mood parte.
  //
  // Pseudo-rota `#/moodboards/_vibes`: `_vibes` jamais é um mbid válido (`MBID_RE` rejeita `_`
  // inicial), então `open()` intercepta esse valor antes do editor. Isso dá uma tela nova SEM
  // tocar `studio/web/app.js` nem `index.html`.
  //
  // Contrato completo: docs/domains/mood/features/painel-vibes-fdd.md
  const VIBES_ROUTE = "_vibes";
  //: prefixo do arquivo -> badge (references/saida.md do mood_vibe_scout)
  const ORIGEM_BADGE = {
    catalogo: { rotulo: "catálogo", kind: "mode" },
    usuario: { rotulo: "pedida", kind: "ok" },
    sugestao: { rotulo: "sugerida", kind: "info" },
  };
  //: último total conhecido de escolhidas — a feature 01 lê por `Studio.vibes.count()`.
  let escolhidasTotal = 0;

  function goVibes() { location.hash = `#/moodboards/${VIBES_ROUTE}`; }

  /** Publica o contador. Só é chamado DEPOIS de o estado já estar no disco, e só quando o valor
   *  muda de fato — salvar dispara duas leituras (a resposta do select e o repinte da peneira) e
   *  quem escuta não deve ver o mesmo total duas vezes. */
  function setEscolhidasTotal(total) {
    const novo = Number(total) || 0;
    if (novo === escolhidasTotal) return;
    escolhidasTotal = novo;
    document.dispatchEvent(new CustomEvent("studio:escolhidas", { detail: { total: escolhidasTotal } }));
  }

  /** Só http(s) vira href — `origem_url` é dado de terceiro e nunca deve virar `javascript:`. */
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? String(u) : "");

  function pinHtml(url) {
    const href = safeUrl(url);
    return href
      ? `<a class="vbp-pin" href="${esc(href)}" target="_blank" rel="noopener noreferrer">pin de origem ↗</a>`
      : `<span class="vbp-pin off">sem origem_url</span>`;
  }

  function metaHtml(it, nome) {
    const badge = ORIGEM_BADGE[it.origem] || ORIGEM_BADGE.catalogo;
    return `<div class="vbp-meta">
      <span class="vbp-name">${esc(nome)}</span>
      <span class="row wrap">${ui.chip(it.vibe_nome || it.vibe || "sem vibe", "info")}${ui.chip(badge.rotulo, badge.kind)}</span>
      ${pinHtml(it.origem_url)}</div>`;
  }

  function vibeCardHtml(it) {
    return `<div class="vbp-card" data-vid="${esc(it.id)}" tabindex="0" role="checkbox" aria-checked="false" title="${esc(it.arquivo)}">
      <img loading="lazy" src="${esc(it.url)}" alt="">
      <span class="vbp-check" aria-hidden="true">✓</span>
      ${it.escolhida ? `<span class="vbp-tag">já escolhida</span>` : ""}
      ${metaHtml(it, it.arquivo)}</div>`;
  }

  function chosenCardHtml(it) {
    return `<div class="vbp-card" data-cid="${esc(it.id)}" title="${esc(it.origem_arquivo || it.arquivo)}">
      <img loading="lazy" src="${esc(it.url)}" alt="">
      <button class="vbp-rm" type="button" data-rm="${esc(it.id)}" title="Tirar da peneira — o original da pesquisa não é apagado">remover</button>
      ${metaHtml(it, it.origem_arquivo || it.arquivo)}</div>`;
  }

  const gridIds = () => [...document.querySelectorAll("#vbGrid [data-vid]")].map((el) => el.dataset.vid);
  const pageAllMarked = (st) => { const ids = gridIds(); return ids.length > 0 && ids.every((id) => st.sel.has(id)); };

  function markSelected(st) {
    document.querySelectorAll("#vbGrid [data-vid]").forEach((el) => {
      const on = st.sel.has(el.dataset.vid);
      el.classList.toggle("vbp-on", on);
      el.setAttribute("aria-checked", on ? "true" : "false");
    });
  }

  function paintSelCount(st) {
    const c = document.querySelector("#vbSelCount");
    if (c) c.textContent = `${st.sel.size} marcada(s)`;
    const save = document.querySelector("#vbSave");
    if (save) {
      save.disabled = !st.sel.size;
      save.textContent = st.sel.size ? `Salvar ${st.sel.size} em escolhidas` : "Salvar em escolhidas";
    }
    const all = document.querySelector("#vbAllPage");
    if (all) all.textContent = pageAllMarked(st) ? "desmarcar todas da página" : "marcar todas da página";
  }

  function paintIndice(indice) {
    const el = document.querySelector("#vbIndice");
    if (!el) return;
    el.innerHTML = (indice && indice.ok)
      ? ui.chip(indice.campanha ? `_indice.json ok · ${indice.campanha}` : "_indice.json ok", "ok")
      : ui.chip(`_indice.json ${(indice && indice.erro) || "indisponível"} — vibe e pin vêm do nome do arquivo`, "warn");
  }

  function pagerHtml(page, pages, perPage, total, rotulo) {
    if (!total) return "";
    const primeiro = (page - 1) * perPage + 1;
    const ultimo = Math.min(page * perPage, total);
    const btn = (alvo, texto, off) =>
      `<button type="button" class="ghost" data-pg="${alvo}"${off ? " disabled" : ""}>${texto}</button>`;
    return btn(1, "« primeira", page <= 1) + btn(page - 1, "‹ anterior", page <= 1) +
      `<span class="vbp-pg">página <b>${page}</b> de ${pages} · ${primeiro}–${ultimo} de ${total} ${esc(rotulo)}</span>` +
      btn(page + 1, "próxima ›", page >= pages) + btn(pages, "última »", page >= pages);
  }

  function emptyVibesHtml(st, body) {
    if (body.total === 0 && (st.vibe || st.origem)) {
      return `<div class="empty">Nenhuma foto com esse filtro. <button class="link" data-vbclear>limpar filtros</button></div>`;
    }
    if (body.total === 0) {
      return `<div class="empty-state"><span class="eyebrow">Nenhuma pesquisa ainda</span>
        <h2>A pasta de fotos de vibe está vazia</h2>
        <p class="lede">Rode a pesquisa de vibe apontando a saída para esta pasta:</p>
        <pre class="vbp-cmd">/mood_vibe_scout --saida ${esc(body.pasta || "")}</pre>
        <p class="fine">A skill entrevista você como um diretor de arte, cruza o catálogo de 30 vibes com sugestões e baixa N referências por vibe no Pinterest. Depois volte aqui para peneirar.</p></div>`;
    }
    return `<div class="empty">Esta página está além do fim (${body.pages} páginas ao todo).
      <button class="link" data-vblast>ir para a última página</button></div>`;
  }

  async function paintGrid(st) {
    const grid = document.querySelector("#vbGrid");
    if (!grid) return;
    const qs = new URLSearchParams({ page: String(st.page), per_page: String(st.perPage) });
    if (st.vibe) qs.set("vibe", st.vibe);
    if (st.origem) qs.set("origem", st.origem);
    let body;
    try { body = await api(`/api/vibes?${qs.toString()}`); }
    catch (e) { grid.innerHTML = `<div class="empty">Não foi possível listar as fotos: ${esc(e.message)}</div>`; return; }

    st.page = body.page; st.perPage = body.per_page; st.pages = body.pages; st.total = body.total;
    const folder = document.querySelector("#vbFolder");
    if (folder) folder.textContent = body.pasta || "";
    paintIndice(body.indice);
    grid.innerHTML = body.items.length ? body.items.map(vibeCardHtml).join("") : emptyVibesHtml(st, body);
    const limpar = grid.querySelector("[data-vbclear]");
    if (limpar) limpar.onclick = () => { st.vibe = ""; st.origem = ""; st.page = 1; syncFilters(st); paintGrid(st); };
    const ultima = grid.querySelector("[data-vblast]");
    if (ultima) ultima.onclick = () => { st.page = st.pages; paintGrid(st); };
    const pager = document.querySelector("#vbPager");
    if (pager) pager.innerHTML = pagerHtml(st.page, st.pages, st.perPage, st.total, "fotos");
    markSelected(st);
    paintSelCount(st);
  }

  async function paintChosen(st) {
    const grid = document.querySelector("#vbChosen");
    if (!grid) return;
    let body;
    try { body = await api(`/api/escolhidas?page=${st.chosenPage}&per_page=${st.perPage}`); }
    catch (e) { grid.innerHTML = `<div class="empty">Não foi possível listar as escolhidas: ${esc(e.message)}</div>`; return; }
    if (body.page > body.pages) { st.chosenPage = body.pages; return paintChosen(st); }

    st.chosenPage = body.page;
    setEscolhidasTotal(body.total);
    const c = document.querySelector("#vbChosenCount");
    if (c) c.textContent = `${body.total} escolhida(s)`;
    grid.innerHTML = body.items.length
      ? body.items.map(chosenCardHtml).join("")
      : `<div class="empty">Nenhuma foto escolhida ainda — marque acima e salve.</div>`;
    const pager = document.querySelector("#vbChosenPager");
    if (pager) pager.innerHTML = pagerHtml(body.page, body.pages, body.per_page, body.total, "escolhidas");
  }

  async function paintFacets(st) {
    const sel = document.querySelector("#vbVibe");
    if (!sel) return;
    let facets;
    try { facets = await api("/api/vibes/facets"); }
    catch (e) { toast(e.message); return; }
    sel.innerHTML = `<option value="">todas as vibes (${facets.total})</option>` +
      facets.vibes.map((v) => `<option value="${esc(v.slug)}">${esc(v.nome || v.slug)} (${v.total})</option>`).join("");
    sel.value = st.vibe;
  }

  function syncFilters(st) {
    const v = document.querySelector("#vbVibe"); if (v) v.value = st.vibe;
    const o = document.querySelector("#vbOrigem"); if (o) o.value = st.origem;
  }

  async function saveVibes(st) {
    const ids = [...st.sel];
    if (!ids.length) { toast("Marque ao menos uma foto"); return; }
    const btn = document.querySelector("#vbSave");
    if (btn) btn.disabled = true;
    try {
      const r = await api("/api/vibes/select", { method: "POST", body: JSON.stringify({ ids }) });
      st.sel.clear();
      const partes = [`${r.copiadas.length} copiada(s)`];
      if (r.duplicadas.length) partes.push(`${r.duplicadas.length} já estava(m) na peneira`);
      if (r.ausentes.length) partes.push(`${r.ausentes.length} sumiu(ram) do disco`);
      toast(partes.join(" · "));
      setEscolhidasTotal(r.total_escolhidas);
      st.chosenPage = 1;
      await paintGrid(st);
      await paintChosen(st);
      await paintFacets(st);
    } catch (err) { toast(err.message); }
    paintSelCount(st);   // devolve o botão ao estado certo, inclusive depois de erro
  }

  async function removeChosen(st, id) {
    try {
      const r = await api(`/api/escolhidas/${encodeURIComponent(id)}`, { method: "DELETE" });
      setEscolhidasTotal(r.total_escolhidas);
      toast("Foto tirada da peneira — o original da pesquisa continua lá");
      await paintChosen(st);
      await paintGrid(st);
      await paintFacets(st);
    } catch (err) { toast(err.message); }
  }

  async function renderVibes() {
    const main = $main();
    main.onclick = null; main.onkeydown = null;
    //: A marcação vive AQUI, fora do ciclo de repintura da grade — por isso sobrevive a trocar
    //: de página, a filtrar e a recarregar.
    const st = { page: 1, perPage: 20, vibe: "", origem: "", sel: new Set(), pages: 1, total: 0, chosenPage: 1 };

    main.innerHTML = `
      <style>
        .vbp-folder{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:.8rem;opacity:.85;margin:.3rem 0 0}
        .vbp-folder code{font-family:"IBM Plex Mono",ui-monospace,monospace;background:rgba(120,120,120,.16);padding:2px 6px;border-radius:6px;word-break:break-all}
        .vbp-cmd{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.82rem;background:rgba(120,120,120,.16);padding:9px 11px;border-radius:8px;overflow-x:auto;max-width:100%}
        .vbp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:14px}
        .vbp-card{position:relative;display:flex;flex-direction:column;border-radius:10px;overflow:hidden;
          border:2px solid transparent;background:rgba(120,120,120,.12);cursor:pointer;transition:border-color .15s,transform .15s}
        .vbp-card:hover{transform:translateY(-2px)}
        .vbp-card>img{width:100%;aspect-ratio:3/4;object-fit:cover;display:block}
        .vbp-card.vbp-on{border-color:var(--accent);box-shadow:var(--ring-sel)}
        .vbp-check{position:absolute;top:7px;left:7px;width:22px;height:22px;border-radius:999px;display:grid;place-items:center;
          background:rgba(0,0,0,.55);color:#fff;font-size:.72rem;z-index:2;opacity:.4}
        .vbp-card.vbp-on .vbp-check{background:var(--accent);opacity:1}
        .vbp-tag{position:absolute;top:7px;right:7px;font-size:.66rem;padding:2px 7px;border-radius:999px;background:rgba(60,150,90,.92);color:#fff;z-index:2}
        .vbp-rm{position:absolute;top:7px;right:7px;font-size:.68rem;padding:3px 9px;border-radius:999px;border:none;
          cursor:pointer;background:rgba(170,60,60,.92);color:#fff;z-index:2}
        .vbp-rm:hover{background:rgba(195,70,70,1)}
        .vbp-meta{display:flex;flex-direction:column;gap:4px;padding:6px 7px 8px;font-size:.72rem}
        .vbp-name{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.66rem;opacity:.78;word-break:break-all}
        .vbp-pin{font-size:.68rem;opacity:.85}
        .vbp-pin.off{opacity:.42;font-style:italic}
        .vbp-chosen .vbp-card{cursor:default}
        .vbp-chosen .vbp-card:hover{transform:none}
        .vbp-pager{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:.8rem}
        .vbp-pg{font-size:.8rem;opacity:.85}
      </style>
      <header class="stephead">
        <span class="eyebrow"><button class="link" id="vbBack">← Biblioteca</button> · Fotos de vibe <span class="ext">[extensão]</span></span>
        <h2>Fotos de vibe do Pinterest</h2>
        <p class="lede">O resultado da pesquisa do <b>/mood_vibe_scout</b>. Marque as que valem: marcar <b>copia</b> para as escolhidas e nunca destrói a pesquisa. É da pasta de escolhidas que a cadeia de mood parte.</p>
        <p class="vbp-folder"><span>Pasta pesquisada:</span> <code id="vbFolder"></code> <span id="vbIndice"></span></p>
      </header>

      <section class="panel">
        <div class="panel-head">
          <h3><span class="pn">01</span>Escolher as fotos</h3>
          <div class="row wrap">
            <select id="vbVibe" title="Filtrar por vibe (lido do _indice.json)"><option value="">todas as vibes</option></select>
            <select id="vbOrigem" title="Filtrar por origem">
              <option value="">toda origem</option>
              <option value="catalogo">catálogo</option>
              <option value="usuario">pedida</option>
              <option value="sugestao">sugerida</option>
            </select>
            <button type="button" class="ghost" id="vbAllPage">marcar todas da página</button>
            <span id="vbSelCount" class="chip mode">0 marcada(s)</span>
            <button type="button" class="primary" id="vbSave" disabled>Salvar em escolhidas</button>
          </div>
        </div>
        <p class="fine">No máximo 20 por página (teto do servidor). A marcação <b>sobrevive à troca de página e ao filtro</b> — pode marcar em várias páginas e salvar tudo de uma vez.</p>
        <div id="vbGrid" class="vbp-grid"></div>
        <div id="vbPager" class="vbp-pager"></div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3><span class="pn">02</span>Fotos escolhidas</h3>
          <span id="vbChosenCount" class="chip mode">0 escolhida(s)</span>
        </div>
        <p class="fine">A peneira não tem teto — o limite de 8 é do mood board (ADR-007), não daqui. Remover uma foto aqui apaga só a cópia: o original da pesquisa continua na pasta.</p>
        <div id="vbChosen" class="vbp-grid vbp-chosen"></div>
        <div id="vbChosenPager" class="vbp-pager"></div>
      </section>`;

    document.querySelector("#vbBack").onclick = goList;
    document.querySelector("#vbVibe").onchange = (e) => { st.vibe = e.target.value; st.page = 1; paintGrid(st); };
    document.querySelector("#vbOrigem").onchange = (e) => { st.origem = e.target.value; st.page = 1; paintGrid(st); };
    document.querySelector("#vbSave").onclick = () => saveVibes(st);
    document.querySelector("#vbAllPage").onclick = () => {
      const ids = gridIds();
      const desmarcar = pageAllMarked(st);
      ids.forEach((id) => (desmarcar ? st.sel.delete(id) : st.sel.add(id)));
      markSelected(st); paintSelCount(st);
    };

    const grid = document.querySelector("#vbGrid");
    const toggle = (card) => {
      const id = card.dataset.vid;
      if (st.sel.has(id)) st.sel.delete(id); else st.sel.add(id);
      markSelected(st); paintSelCount(st);
    };
    grid.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;                 // o link do pin abre o Pinterest, não marca
      const card = e.target.closest("[data-vid]");
      if (card) toggle(card);
    });
    grid.addEventListener("keydown", (e) => {
      const card = e.target.closest("[data-vid]");
      if (card && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); toggle(card); }
    });

    document.querySelector("#vbPager").addEventListener("click", (e) => {
      const b = e.target.closest("[data-pg]");
      if (!b || b.disabled) return;
      st.page = Number(b.dataset.pg); paintGrid(st);
    });
    document.querySelector("#vbChosenPager").addEventListener("click", (e) => {
      const b = e.target.closest("[data-pg]");
      if (!b || b.disabled) return;
      st.chosenPage = Number(b.dataset.pg); paintChosen(st);
    });
    document.querySelector("#vbChosen").addEventListener("click", (e) => {
      const b = e.target.closest("[data-rm]");
      if (b) removeChosen(st, b.dataset.rm);
    });

    await paintFacets(st);
    await paintGrid(st);
    await paintChosen(st);
  }

  /** Contador autoritativo das escolhidas (uma chamada barata: `per_page=1`). */
  async function refreshEscolhidasCount() {
    const r = await api("/api/escolhidas?page=1&per_page=1");
    setEscolhidasTotal(r.total);
    return escolhidasTotal;
  }

  // ---------- entrada da área (chamada por app.js applyRoute) ----------
  function open(mbid) {
    if (mbid === VIBES_ROUTE) { renderVibes(); return; }   // pseudo-rota, ver o bloco acima
    if (mbid) renderEditor(mbid); else renderList();
  }

  window.Studio.moodboards = { open, goList, goEditor, goVibes };

  //: Contrato consumido pela feature 01 (mood-run) — seção 12 "Provides" do FDD do painel.
  //: A fonte de verdade é `GET /api/escolhidas` (`total`); isto aqui é só o açúcar da mesma tela.
  window.Studio.vibes = {
    route: VIBES_ROUTE,
    open: renderVibes,
    count: () => escolhidasTotal,
    refreshCount: refreshEscolhidasCount,
    onChange(cb) {
      const h = (ev) => cb(ev.detail.total);
      document.addEventListener("studio:escolhidas", h);
      return () => document.removeEventListener("studio:escolhidas", h);
    },
  };
})();
