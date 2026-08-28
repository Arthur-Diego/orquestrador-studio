// Componente reutilizável de MULTISHOT [extensão] (ADR-017): "gerar vários ângulos a partir de
// uma imagem". Um modal único, usado pelo mood board (gerar ângulos da imagem de vibe) e, depois,
// pela etapa 4 (fotos-semente e frames da cena). Carregado depois de ui.js/app.js — reusa
// Studio.ui (confirmCost/progressJob/tile/modal/drop/upload) e o gate de custo global (ADR-016).
//
// Os resultados são exibidos em CARROSSEL (rework ADR-019): um ângulo por vez, com prev/‹ ›/next,
// contador "n/total", e — quando o dono habilita — ações "remover" (DELETE da candidata) e
// "importar" (novas fotos ao board). O CSS do carrossel é 100% escopado em `.msc-` via `<style>`
// inline (não toca ui.css/style.css).
//
// Uso:
//   Studio.multishot.open({
//     title, subtitle, sourceUrl,
//     action,                 // ação do gate de custo (ex.: "mood.multishot")
//     pid,                    // opcional — habilita override de modelo por projeto no custo
//     count,                  // default 4
//     endpoints: {
//       cost, generate, job, candidates,   // URLs do dono (board/cena)
//       upload, importDownloads, downloadsFolder, openFolder,  // opcionais — habilitam "importar"
//     },
//     canRemove,              // true habilita "remover" no item ativo do carrossel
//     fileUrl(rel),           // como transformar o `file` de uma candidata em URL servível
//     parentId,               // id da imagem de origem — filtra a galeria de resultados
//     onChanged,              // callback após gerar/remover/importar (recarregar o dono)
//   })
(function () {
  const ui = window.Studio.ui;
  const esc = (s) => ui.esc(s);
  const ctx = () => window.Studio.ctx;
  const toast = (m) => ctx().toast(m);
  const api = (p, o) => ctx().api(p, o);

  const STYLE = `<style>
    .msc-wrap{display:flex;flex-direction:column;gap:12px}
    .msc-empty{opacity:.7;font-size:.9rem;padding:18px 8px;text-align:center}
    .msc-count{font-size:.85rem;opacity:.8}
    .msc-stage{display:flex;align-items:center;gap:10px;justify-content:center}
    .msc-frame{position:relative;flex:1;min-width:0;display:flex;align-items:center;justify-content:center;
      background:rgba(0,0,0,.18);border-radius:12px;overflow:hidden;min-height:220px;max-height:52vh}
    .msc-frame img{max-width:100%;max-height:52vh;object-fit:contain;display:block}
    .msc-tag{position:absolute;top:8px;left:8px;font-size:.7rem;padding:2px 8px;border-radius:999px;
      background:rgba(0,0,0,.55);color:#fff;letter-spacing:.04em;text-transform:uppercase}
    .msc-nav{flex:0 0 auto;width:40px;height:40px;border-radius:50%;border:none;cursor:pointer;
      font-size:1.3rem;line-height:1;background:rgba(120,120,120,.22);color:inherit}
    .msc-nav:hover{background:rgba(120,120,120,.4)}
    .msc-nav:disabled{opacity:.3;cursor:default}
    .msc-bar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
    .msc-bar-actions{display:flex;gap:8px;flex-wrap:wrap}
    .msc-prompt{font-size:.78rem;opacity:.65;margin:0}
  </style>`;

  async function fetchResults(o) {
    if (!o.endpoints.candidates) return [];
    try {
      const r = await api(o.endpoints.candidates);
      const list = Array.isArray(r) ? r : (r.candidates || []);
      return list.filter((c) => c && c.role === "multishot" && (!o.parentId || c.parent === o.parentId));
    } catch (e) { return []; }
  }

  function carouselHtml(o, results, idx) {
    if (!results.length) {
      return `<p class="msc-empty">Nenhum ângulo gerado ainda a partir desta imagem. Gere pelo CLI (custo abaixo) ou pela UI da Higgsfield e importe.</p>`;
    }
    const c = results[idx];
    const src = o.fileUrl ? o.fileUrl(c.file) : c.file;
    const single = results.length <= 1;
    return `
      <div class="msc-stage">
        <button class="msc-nav msc-prev" type="button" title="Anterior" ${single ? "disabled" : ""}>‹</button>
        <div class="msc-frame">
          <span class="msc-tag">multishot</span>
          <img src="${esc(src)}" alt="" loading="lazy">
        </div>
        <button class="msc-nav msc-next" type="button" title="Próximo" ${single ? "disabled" : ""}>›</button>
      </div>
      <div class="msc-bar">
        <span class="msc-count">${idx + 1}/${results.length} ângulo(s) gerado(s) desta imagem</span>
        <div class="msc-bar-actions">
          ${o.canRemove ? `<button class="ghost danger msc-remove" type="button">remover</button>` : ""}
        </div>
      </div>
      ${c.prompt ? `<p class="msc-prompt">${esc(c.prompt)}</p>` : ""}`;
  }

  function bodyHtml(o) {
    const canImport = !!(o.endpoints && o.endpoints.upload);
    return `${STYLE}<div class="msc-wrap">
      <div class="ms-source">
        <span class="eyebrow">Imagem de origem</span>
        <img src="${esc(o.sourceUrl)}" alt="" loading="lazy">
      </div>
      <div class="ms-controls">
        <label class="inline">ângulos <input type="number" id="msCount" value="${Number(o.count) || 4}" min="1" max="8"></label>
        <button class="primary" id="msGen" type="button">Gerar ângulos via CLI</button>
        ${canImport ? `<button class="ghost" id="msImport" type="button" title="Importar novas fotos ao board">Importar fotos</button>` : ""}
        <span class="fine ms-hint">O custo aparece antes de gastar. Sem CLI, gere na UI da Higgsfield (ilimitado) e importe.</span>
      </div>
      <div class="ms-results"></div>
    </div>`;
  }

  async function open(o) {
    let results = await fetchResults(o);
    const state = { idx: 0 };
    const m = ui.modal({
      title: o.title || "Multishot — outro ponto de vista",
      subtitle: o.subtitle || "Aula 011 · vários ângulos a partir de uma imagem [extensão]",
      html: bodyHtml(o),
    });

    const resultsBox = () => m.el.querySelector(".ms-results");

    function mount() {
      if (state.idx >= results.length) state.idx = Math.max(0, results.length - 1);
      if (state.idx < 0) state.idx = 0;
      const box = resultsBox();
      if (box) box.innerHTML = carouselHtml(o, results, state.idx);
      bindCarousel();
    }

    function bindCarousel() {
      const box = resultsBox();
      if (!box) return;
      const step = (delta) => { state.idx = (state.idx + delta + results.length) % results.length; mount(); };
      const prev = box.querySelector(".msc-prev");
      const next = box.querySelector(".msc-next");
      if (prev) prev.onclick = () => step(-1);
      if (next) next.onclick = () => step(1);
      const rm = box.querySelector(".msc-remove");
      if (rm) rm.onclick = () => removeCurrent();
    }

    async function refresh() {
      results = await fetchResults(o);
      mount();
    }

    async function removeCurrent() {
      const cur = results[state.idx];
      if (!cur) return;
      try {
        await api(`${o.endpoints.candidates}/${encodeURIComponent(cur.id)}`, { method: "DELETE" });
        toast("Ângulo removido");
        await refresh();
        if (o.onChanged) await o.onChanged();
      } catch (e) { toast((e && e.message) || String(e)); }
    }

    const gen = m.el.querySelector("#msGen");
    if (gen) gen.onclick = async () => {
      const count = Math.max(1, Math.min(8, Number(m.el.querySelector("#msCount").value) || 4));
      const ok = await ui.confirmCost({ action: o.action, pid: o.pid, count, label: `Gerar ${count} ângulo(s)` });
      if (!ok) return;
      try {
        await ui.progressJob({
          title: "Gerar multishot", subtitle: "Outro ponto de vista (aula 011)",
          start: () => api(o.endpoints.generate, { method: "POST", body: JSON.stringify({ source_id: o.parentId, count }) }),
          jobUrl: o.endpoints.job,
          done: async () => { await refresh(); if (o.onChanged) await o.onChanged(); },
          label: "Ângulos gerados",
        });
      } catch (e) { toast((e && e.message) || String(e)); }
    };

    const imp = m.el.querySelector("#msImport");
    if (imp) imp.onclick = () => openImport(o, async () => { await refresh(); if (o.onChanged) await o.onChanged(); });

    mount();
    return m;
  }

  // ---------- importar novas fotos ao board (reusa import/upload + import/downloads) ----------
  function openImport(o, onDone) {
    const ep = o.endpoints;
    const im = ui.modal({
      title: "Importar novas fotos",
      subtitle: "Adicione imagens ao board — por upload ou da pasta Downloads",
      html: `<div class="msc-wrap">
        <label class="drop" id="msImpDrop">Arraste imagens aqui ou <input id="msImpFile" type="file" accept="image/*" multiple hidden><u>escolha arquivos</u></label>
        <div class="msc-bar-actions">
          <button class="ghost" id="msImpDl" type="button">Importar da pasta Downloads</button>
          <button class="ghost" id="msImpOpen" type="button" title="Abrir a pasta de Downloads no explorador">Abrir pasta de Downloads</button>
        </div>
        <p class="msc-prompt" id="msImpPath"></p>
      </div>`,
    });

    if (ep.downloadsFolder) {
      api(ep.downloadsFolder).then((d) => {
        const el = im.el.querySelector("#msImpPath");
        if (el) el.textContent = `pasta Downloads: ${d.folder}${d.exists ? "" : " (não encontrada)"}`;
      }).catch(() => {});
    }

    ui.drop(im.el.querySelector("#msImpDrop"), async (files) => {
      if (!files || !files.length) return;
      try {
        const r = await ui.upload(ep.upload, files);
        toast(`${r.added} imagem(ns) importada(s)`); im.close(); await onDone();
      } catch (e) { toast((e && e.message) || String(e)); }
    });

    const dl = im.el.querySelector("#msImpDl");
    if (dl) dl.onclick = async () => {
      try {
        const r = await api(ep.importDownloads, { method: "POST", body: JSON.stringify({ since_minutes: 120 }) });
        toast(`${r.added} novas de ${r.scanned} imagens recentes`); im.close(); await onDone();
      } catch (e) { toast((e && e.message) || String(e)); }
    };

    const opn = im.el.querySelector("#msImpOpen");
    if (opn) opn.onclick = async () => {
      try {
        const r = await api(ep.openFolder, { method: "POST", body: JSON.stringify({ target: "downloads" }) });
        toast(r.opened ? "Pasta de Downloads aberta" : `Pasta: ${r.path}`);
      } catch (e) { toast((e && e.message) || String(e)); }
    };
  }

  window.Studio.multishot = { open };
})();
