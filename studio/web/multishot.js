// Componente reutilizável de MULTISHOT [extensão] (ADR-017): "gerar vários ângulos a partir de
// uma imagem". Um modal único, usado pelo mood board (gerar ângulos da imagem de vibe) e, depois,
// pela etapa 4 (fotos-semente e frames da cena). Carregado depois de ui.js/app.js — reusa
// Studio.ui (confirmCost/progressJob/tile/modal) e o gate de custo global (ADR-016).
//
// Uso:
//   Studio.multishot.open({
//     title, subtitle, sourceUrl,
//     action,                 // ação do gate de custo (ex.: "mood.multishot")
//     pid,                    // opcional — habilita override de modelo por projeto no custo
//     count,                  // default 4
//     endpoints: { cost, generate, job, candidates },  // URLs do dono (board/cena)
//     fileUrl(rel),           // como transformar o `file` de uma candidata em URL servível
//     parentId,               // id da imagem de origem — filtra a galeria de resultados
//     onChanged,              // callback após gerar (recarregar a galeria do dono)
//   })
(function () {
  const ui = window.Studio.ui;
  const esc = (s) => ui.esc(s);
  const ctx = () => window.Studio.ctx;
  const toast = (m) => ctx().toast(m);
  const api = (p, o) => ctx().api(p, o);

  async function fetchResults(o) {
    if (!o.endpoints.candidates) return [];
    try {
      const r = await api(o.endpoints.candidates);
      const list = Array.isArray(r) ? r : (r.candidates || []);
      return list.filter((c) => c && c.role === "multishot" && (!o.parentId || c.parent === o.parentId));
    } catch (e) { return []; }
  }

  function galleryHtml(o, results) {
    if (!results.length) {
      return `<p class="ms-empty">Nenhum ângulo gerado ainda a partir desta imagem. Gere pelo CLI (custo abaixo) ou pela UI da Higgsfield e importe.</p>`;
    }
    const tiles = results.map((c) => ui.tile({
      src: o.fileUrl ? o.fileUrl(c.file) : c.file,
      badge: "multishot", id: c.id, title: c.prompt || "",
    })).join("");
    return `<p class="ms-count">${results.length} ângulo(s) gerado(s) desta imagem:</p>
      <div class="grid ms-grid">${tiles}</div>`;
  }

  function bodyHtml(o, results) {
    return `<div class="ms-wrap">
      <div class="ms-source">
        <span class="eyebrow">Imagem de origem</span>
        <img src="${esc(o.sourceUrl)}" alt="" loading="lazy">
      </div>
      <div class="ms-controls">
        <label class="inline">ângulos <input type="number" id="msCount" value="${Number(o.count) || 4}" min="1" max="8"></label>
        <button class="primary" id="msGen" type="button">Gerar ângulos via CLI</button>
        <span class="fine ms-hint">O custo aparece antes de gastar. Sem CLI, gere na UI da Higgsfield (ilimitado) e importe.</span>
      </div>
      <div class="ms-results">${galleryHtml(o, results)}</div>
    </div>`;
  }

  async function open(o) {
    const results = await fetchResults(o);
    const m = ui.modal({
      title: o.title || "Multishot — outro ponto de vista",
      subtitle: o.subtitle || "Aula 011 · vários ângulos a partir de uma imagem [extensão]",
      html: bodyHtml(o, results),
    });

    const refreshGallery = async () => {
      const rs = await fetchResults(o);
      const box = m.el.querySelector(".ms-results");
      if (box) box.innerHTML = galleryHtml(o, rs);
    };

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
          done: async () => { await refreshGallery(); if (o.onChanged) await o.onChanged(); },
          label: "Ângulos gerados",
        });
      } catch (e) { toast((e && e.message) || String(e)); }
    };

    return m;
  }

  window.Studio.multishot = { open };
})();
