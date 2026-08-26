// Etapa 10 — Publicar (aula 015): registro manual dos posts, portfólio global e comunidade.
// ADR-012: o portfólio conta PROJETOS distintos com post (distinct_videos), não arquivos nem posts.
// Wave 4: a tela é o protótipo — form de duas linhas e lista de publicações (chip · url · "nota").
// A contagem do portfólio vive no chip do guia; a galeria de exports e o resumo global saíram.
Studio.register("publish", (ctx) => {
  const { $, api, toast } = ctx;
  // A contagem do portfólio (`distinct_videos`) virou o chip-resumo do guia (`publish/guide.py`):
  // a tela só usa o total de publicações e o checklist da comunidade.
  let exports_ = [], posts = [], status = { count: 0, community: { done: 0, total: 3 } };

  const esc = (s) => Studio.ui.esc(s);
  const today = () => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10); };
  const base = () => `/api/projects/${ctx.pid()}/publish`;

  // URL como o protótipo a desenha: sem o protocolo/www e cortada — a íntegra fica no `title`.
  function urlCurta(u) {
    const limpa = String(u || "").replace(/^https?:\/\/(www\.)?/, "");
    return limpa.length > 28 ? limpa.slice(0, 28) + "…" : limpa;
  }

  async function load() {
    if (!ctx.pid()) { exports_ = []; posts = []; render(); return; }
    const [ex, lg, st] = await Promise.all([api(`${base()}/exports`), api(`${base()}/log`), api(`${base()}/portfolio`)]);
    exports_ = ex.files; posts = lg.posts; status = st;
    render();
  }

  // O `<select>` é o único meio de escolher o arquivo (a galeria de tiles saiu da tela).
  function renderExports() {
    const sel = $("#pubVideo");
    const current = sel.value;
    sel.innerHTML = exports_.map((f) => `<option value="${esc(f.file)}">${esc(f.file)}</option>`).join("")
      || `<option value="">nenhum export disponível</option>`;
    if (exports_.some((f) => f.file === current)) sel.value = current;
  }

  function renderCommunity() {
    const c = status.community || { done: 0, total: 3 };
    document.querySelectorAll("#pubCommunity input[data-com]").forEach((el) => { el.checked = !!c[el.dataset.com]; });
    // Chip único do painel 02: "N publicações · comunidade n/3" — neutro em todos os estados.
    $("#pubComChip").textContent =
      `${status.count} ${status.count === 1 ? "publicação" : "publicações"} · comunidade ${c.done}/${c.total}`;
  }

  function renderLog() {
    $("#pubLog").innerHTML = posts.length ? posts.map((p) => {
      const orfao = exports_.length && !exports_.some((f) => f.file === p.video);
      const texto = p.feedback || p.note || "";
      // A data, o arquivo e o aviso de arquivo órfão viram `title` da linha (protótipo: 3 elementos).
      const dica = `${esc(p.posted_at)} · ${esc(p.video)}${orfao ? " — arquivo não está mais em export/" : ""}`;
      return `<div class="pub-row" data-id="${esc(p.id)}" title="${dica}">
        <span class="chip info">${esc(p.network)}</span>
        <a class="url" href="${esc(p.url)}" target="_blank" rel="noopener" title="${esc(p.url)}">${esc(urlCurta(p.url))}</a>
        <span class="nt" data-note="${esc(p.id)}" tabindex="0" role="button"
          title="clique para anotar o feedback recebido">${texto ? `“${esc(texto)}”` : "“nota”"}</span>
        <button class="link del act" data-id="${esc(p.id)}" title="remover este registro">Remover</button>
      </div>`;
    }).join("") : `<div class="empty">Nenhuma publicação registrada. Poste na rede e cole o link aqui.</div>`;
  }

  // "Anotar o feedback recebido" é ação da aula 014: a nota vira campo ao ser clicada e some ao salvar.
  function editarNota(span) {
    const id = span.dataset.note, p = posts.find((x) => x.id === id);
    if (!p || span.querySelector("input")) return;
    const input = document.createElement("input");
    input.className = "nt-edit";
    input.value = p.feedback || p.note || "";
    input.placeholder = "feedback recebido";
    span.textContent = "";
    span.style.flex = "1 1 240px";   // enquanto edita, a nota usa a largura que sobra na linha
    span.appendChild(input);
    input.focus();
    let salvando = false;
    const salvar = async (gravar) => {
      if (salvando) return;
      salvando = true;
      if (!gravar) return renderLog();
      try { await api(`${base()}/log/${id}/feedback`, { method: "POST", body: JSON.stringify({ feedback: input.value }) }); toast("Feedback salvo"); await load(); ctx.guide(); }
      catch (err) { toast(err.message); renderLog(); }
    };
    input.onblur = () => salvar(true);
    input.onkeydown = (e) => {
      if (e.key === "Enter") { e.preventDefault(); input.blur(); }
      else if (e.key === "Escape") { salvando = true; renderLog(); }
    };
  }

  function render() { renderExports(); renderLog(); renderCommunity(); }

  return {
    init() {
      $("#pubDate").value = today();
      $("#btnPubAdd").onclick = async () => {
        const body = {
          video: $("#pubVideo").value, network: $("#pubNetwork").value,
          url: $("#pubUrl").value, posted_at: $("#pubDate").value || null, note: $("#pubNote").value,
        };
        try {
          await api(`${base()}/log`, { method: "POST", body: JSON.stringify(body) });
          $("#pubUrl").value = ""; $("#pubNote").value = "";
          toast("Publicação registrada"); await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#pubCommunity").addEventListener("change", async (e) => {
        const el = e.target.closest("input[data-com]"); if (!el) return;
        try {
          await api(`${base()}/community`, { method: "POST", body: JSON.stringify({ [el.dataset.com]: el.checked }) });
          await load(); ctx.guide();
        } catch (err) { toast(err.message); el.checked = !el.checked; }
      });
      $("#pubLog").addEventListener("click", async (e) => {
        const del = e.target.closest("button.del");
        if (del) {
          if (!confirm("Remover este registro de publicação? O post continua no ar na rede.")) return;
          try { await api(`${base()}/log/${del.dataset.id}`, { method: "DELETE" }); toast("Registro removido"); await load(); ctx.guide(); }
          catch (err) { toast(err.message); }
          return;
        }
        const nota = e.target.closest(".nt[data-note]");
        if (nota) editarNota(nota);
      });
      this.onProject();
    },
    async onProject() {
      $("#pubDate").value = today();
      await load();
      Studio.ui.renderGuide("publish");
    },
    destroy() { /* esta tela não usa polling: nada a parar */ },
  };
});
