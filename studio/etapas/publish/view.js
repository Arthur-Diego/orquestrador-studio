// Etapa 10 — Publicar (aula 015): registro manual dos posts, portfólio global e comunidade.
// ADR-012: o portfólio conta PROJETOS distintos com post (distinct_videos), não arquivos nem posts.
Studio.register("publish", (ctx) => {
  const { $, api, toast } = ctx;
  let exports_ = [], thumb = null, posts = [],
    status = { count: 0, videos: 0, published: false, distinct_videos: 0, goal: 4, ready: false, missing: 4, projects: [], community: { done: 0, total: 3 } };

  const esc = (s) => Studio.ui.esc(s);
  const today = () => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10); };
  const mb = (n) => (n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : n >= 1024 ? Math.round(n / 1024) + " KB" : n + " B");
  const base = () => `/api/projects/${ctx.pid()}/publish`;

  async function load() {
    if (!ctx.pid()) { exports_ = []; posts = []; render(); return; }
    const [ex, lg, st] = await Promise.all([api(`${base()}/exports`), api(`${base()}/log`), api(`${base()}/portfolio`)]);
    exports_ = ex.files; thumb = ex.thumb; posts = lg.posts; status = st;
    render();
  }

  function renderExports() {
    const sel = $("#pubVideo");
    const current = sel.value;
    sel.innerHTML = exports_.map((f) => `<option value="${esc(f.file)}">${esc(f.name)}</option>`).join("")
      || `<option value="">nenhum export disponível</option>`;
    if (exports_.some((f) => f.file === current)) sel.value = current;
    $("#pubExports").innerHTML = exports_.length ? exports_.map((f) => `
      <div class="card ${f.published ? "sel" : ""}" data-file="${esc(f.file)}" tabindex="0" title="${esc(f.file)} · ${mb(f.size)}">
        ${thumb ? `<img loading="lazy" src="${ctx.files(thumb)}" alt="">` : ""}
        <span class="src">${f.published ? "publicado" : "a publicar"}</span>
        <span class="term">${esc(f.name)} · ${mb(f.size)}</span>
      </div>`).join("")
      : `<div class="empty">Nenhum export ainda. Volte à etapa 9 e gere os formatos do vídeo.</div>`;
  }

  function renderGlobal() {
    const p = status.projects || [];
    const este = status.published
      ? `<strong>Este vídeo já está publicado</strong> (${status.videos} arquivo(s) registrado(s) neste projeto).`
      : `Este vídeo ainda não está publicado.`;
    const lista = p.length
      ? `<ul>${p.map((x) => `<li>${esc(x.name)} — ${x.posts} publicação(ões)${x.first_posted ? ` · desde ${esc(x.first_posted)}` : ""}</li>`).join("")}</ul>`
      : `<p>Nenhum projeto com post registrado ainda.</p>`;
    $("#pubGlobal").innerHTML = `<p>${este} Portfólio <strong>${status.distinct_videos}/${status.goal} (global)</strong>:</p>${lista}`;
  }

  function renderCommunity() {
    const c = status.community || { done: 0, total: 3 };
    document.querySelectorAll("#pubCommunity input[data-com]").forEach((el) => { el.checked = !!c[el.dataset.com]; });
    const chip = $("#pubComChip");
    // Chip único do painel 02 no redesign: "N publicações · comunidade n/3".
    chip.textContent = `${status.count} ${status.count === 1 ? "publicação" : "publicações"} · comunidade ${c.done}/${c.total}`;
    chip.className = "chip " + (c.done === c.total ? "ok" : c.done ? "warn" : "mode");
  }

  function renderLog() {
    $("#pubLog").innerHTML = posts.length ? posts.map((p) => {
      const orfao = exports_.length && !exports_.some((f) => f.file === p.video);
      // `.pub-row` do redesign: chip da rede, url mono, nota — e os controles de sempre.
      return `<div class="pub-row" data-id="${esc(p.id)}">
        <span class="chip info">${esc(p.network)}</span>
        <a class="url" href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.url)}</a>
        ${p.note ? `<span class="nt">${esc(p.note)}</span>` : ""}
        <span class="fine mono">${esc(p.posted_at)} · ${esc(p.video)}${orfao ? " — arquivo não está mais em export/" : ""}</span>
        <div class="fb">
          <input class="fb" data-id="${esc(p.id)}" placeholder="Feedback recebido (aula 014: compartilhar é o que permite feedback)" value="${esc(p.feedback)}">
          <button class="link save" data-id="${esc(p.id)}">Salvar</button>
          <button class="link del" data-id="${esc(p.id)}">Remover</button>
        </div>
      </div>`;
    }).join("") : `<div class="empty">Nenhuma publicação registrada. Poste na rede e cole o link aqui.</div>`;
  }

  function render() {
    renderExports(); renderLog(); renderGlobal(); renderCommunity();
    $("#pubCounter").textContent = `${status.distinct_videos}/${status.goal} vídeos`;
    $("#pubPosts").textContent = `${status.count} ${status.count === 1 ? "publicação" : "publicações"}`;
    const ready = $("#pubReady");
    ready.textContent = status.ready ? "portfólio pronto — pode prospectar (etapa 11)"
      : `portfólio: ${status.missing === 1 ? "falta 1 vídeo" : `faltam ${status.missing} vídeos`}`;
    ready.className = status.ready ? "chip ok" : "chip warn";
    const link = $("#pubPortfolio");
    if (status.portfolio_md) { link.href = ctx.files(status.portfolio_md); link.classList.remove("hidden"); }
    else link.classList.add("hidden");
  }

  return {
    init() {
      $("#pubDate").value = today();
      $("#pubExports").addEventListener("click", (e) => {
        const card = e.target.closest(".card"); if (!card) return;
        $("#pubVideo").value = card.dataset.file; $("#pubUrl").focus();
      });
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
        const del = e.target.closest("button.del"), save = e.target.closest("button.save");
        if (del) {
          if (!confirm("Remover este registro de publicação? O post continua no ar na rede.")) return;
          try { await api(`${base()}/log/${del.dataset.id}`, { method: "DELETE" }); toast("Registro removido"); await load(); ctx.guide(); }
          catch (err) { toast(err.message); }
        } else if (save) {
          const input = $(`#pubLog input.fb[data-id="${save.dataset.id}"]`);
          try { await api(`${base()}/log/${save.dataset.id}/feedback`, { method: "POST", body: JSON.stringify({ feedback: input.value }) }); toast("Feedback salvo"); await load(); ctx.guide(); }
          catch (err) { toast(err.message); }
        }
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
