// Etapa 1 — Referências (aula 009). Registrada no core via Studio.register.
// Usa os componentes compartilhados (Studio.ui): escape de HTML, drag&drop, upload e polling.
// Wave 4: a tela é o protótipo — dois painéis. O upload manual (Explore do Midjourney) não tem
// painel próprio: o painel 02 inteiro é alvo de drop e o link "trazer imagens" abre o seletor.
Studio.register("refs", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  let cands = [], selected = new Set(), job = null, loginJob = null;
  // Filtros multiseleção da etapa 1: um conjunto por grupo. União dentro de cada grupo (qualquer
  // termo/fonte marcado), interseção entre grupos (termo marcado E fonte marcada). Vazio = tudo.
  const filterTerms = new Set(), filterSources = new Set();

  async function refreshLogin() {
    const el = $("#loginState"), btn = $("#btnLogin");
    if (!el) return;
    const s = await api("/api/pinterest/login");
    if (s.state === "running") {
      el.textContent = "sessão: aguardando login"; el.className = "chip warn";
      if (!loginJob) loginJob = ui.poll(async () => {
        const cur = await api("/api/pinterest/login");
        if (cur.state === "running") return;
        loginJob = null; refreshLogin(); return false;      // false encerra o poll
      }, 3000);
    } else if (s.state === "done") {
      setSession(s.ok);
    } else {
      el.textContent = "sessão: ?"; el.className = "chip mode";
      if (btn) btn.textContent = "Refazer login";
    }
  }

  // Estado desenhado pelo protótipo: chip `sessão ativa` (ok) + botão "Refazer login".
  // Sem sessão (estado que o protótipo não desenha) o chip vira `warn` e o botão, "Fazer login".
  function setSession(ok) {
    const el = $("#loginState"), btn = $("#btnLogin");
    if (el) { el.textContent = ok ? "sessão ativa" : "sessão: não logada"; el.className = "chip " + (ok ? "ok" : "warn"); }
    if (btn) btn.textContent = ok ? "Refazer login" : "Fazer login";
  }

  // Coluna de status do scrape: rótulo "baixadas/meta", barra e log.
  // `j.last_job` é o resumo persistido do último scrape (backend) — é o que faz a coluna
  // nascer preenchida ao abrir a tela, e não só enquanto o job roda.
  function renderJob(j) {
    const src = (j && (j.last_job || (j.meta !== undefined ? j : null))) || null;
    const bar = $("#progress .bar"), log = $("#log");
    if (!src) { scrapeLabel(); if (bar) bar.style.width = "0%"; if (log) log.innerHTML = ""; return; }
    const total = src.total || 0, meta = src.meta || 0;
    scrapeLabel(meta ? `${total}/${meta}` : (total ? `${total} candidatas` : ""));
    if (bar) bar.style.width = meta ? `${Math.min(100, Math.round((total / meta) * 100))}%` : "0%";
    if (log) {
      log.innerHTML = (src.log || []).map((l) => {
        const linha = `[${ui.esc(l.time || "")}] ${ui.esc(l.text || "")}`;
        return l.ok ? `<span class="ok">${linha}</span>` : linha;
      }).join("\n");
      log.scrollTop = log.scrollHeight;
    }
  }

  function startPoll() {
    if (job) job.stop();
    job = ui.poll(async () => {
      const j = await api(`/api/projects/${ctx.pid()}/refs/job`);
      renderJob(j);
      if (j.last && j.last.stage === "start") setSession(!!j.last.logged_in);
      if (j.state === "running") { if (j.total) load(true); return; }
      $("#btnSearch").disabled = false;
      if (j.state === "error") {
        $("#log").innerHTML += `\n<span class="warn">ERRO: ${ui.esc(j.error || "")}</span>`;
        toast("Falhou: " + j.error);
      }
      await load();
      ctx.guide();
      job = null;
      return false;
    }, 2000);
  }

  async function load(keepSel) {
    if (!ctx.pid()) { cands = []; renderFilters(); render(); return; }
    cands = await api(`/api/projects/${ctx.pid()}/refs/candidates`);
    if (!keepSel) selected = new Set(cands.filter(c => c.selected).map(c => c.id));
    // Marcações de filtro que já não existem nas candidatas atuais são descartadas.
    const terms = new Set(cands.map(c => c.term)), sources = new Set(cands.map(c => c.source || "pinterest"));
    [...filterTerms].forEach(t => { if (!terms.has(t)) filterTerms.delete(t); });
    [...filterSources].forEach(s => { if (!sources.has(s)) filterSources.delete(s); });
    renderFilters();
    render();
  }

  // Desenha os grupos de checkbox (termos e fontes presentes nas candidatas) + "limpar filtros".
  // Um grupo só aparece quando há mais de um valor — filtrar por um valor único não separa nada.
  function renderFilters() {
    const box = $("#refsFilters");
    if (!box) return;
    if (!cands.length) { box.innerHTML = ""; return; }
    const terms = [...new Set(cands.map(c => c.term))].sort();
    const sources = [...new Set(cands.map(c => c.source || "pinterest"))].sort();
    const chk = (kind, v, set) =>
      `<label class="rf-chk"><input type="checkbox" data-filter="${kind}" value="${ui.esc(v)}" ${set.has(v) ? "checked" : ""}> ${ui.esc(v)}</label>`;
    const groups = [];
    if (terms.length > 1)
      groups.push(`<div class="rf-fgroup"><span class="rf-flabel">termos</span>${terms.map(t => chk("term", t, filterTerms)).join("")}</div>`);
    if (sources.length > 1)
      groups.push(`<div class="rf-fgroup"><span class="rf-flabel">fontes</span>${sources.map(s => chk("source", s, filterSources)).join("")}</div>`);
    const active = filterTerms.size || filterSources.size;
    box.innerHTML = groups.join("") + (active ? `<button type="button" class="link rf-clear">limpar filtros</button>` : "");
  }

  // União dentro de cada grupo, interseção entre grupos. Sem marcação num grupo = grupo não filtra.
  function matchesFilters(c) {
    const okTerm = !filterTerms.size || filterTerms.has(c.term);
    const okSource = !filterSources.size || filterSources.has(c.source || "pinterest");
    return okTerm && okSource;
  }

  function counts() {
    $("#counts").textContent = `${cands.length} candidatas · ${selected.size} escolhidas`;
  }

  // Rótulo do "Último scrape" (`.progress-lbl` do protótipo): `baixadas/meta`, sempre derivado
  // do job real ou do resumo persistido — nunca dado de exemplo.
  function scrapeLabel(txt) {
    const el = $("#scrapeCount");
    if (el) el.textContent = txt || (cands.length ? `${cands.length} candidatas` : "—");
  }

  function render() {
    const g = $("#gallery");
    const list = cands.filter(matchesFilters);
    counts();
    if (!job) scrapeLabel();
    // Tile do catálogo do shell: `.card` > img + `span.src` (origem) + `span.term` (termo).
    g.innerHTML = list.length ? list.map(c =>
      `<div class="card ${selected.has(c.id) ? "sel" : ""}" data-id="${ui.esc(c.id)}" tabindex="0" title="${ui.esc(c.alt || "")}">
         <img loading="lazy" src="${ctx.files(`refs/candidates/${c.thumb}`)}" alt="">
         <span class="src">${ui.esc(c.source || "pinterest")}</span>
         <span class="term">${ui.esc(c.term)}</span>
       </div>`).join("")
      : `<div class="empty">${ctx.pid()
        ? `Nenhuma candidata ainda — rode uma busca ou <button type="button" class="link" data-bring>traga imagens</button>.`
        : "Crie ou selecione um projeto."}</div>`;
  }

  async function upload(files) {
    if (!files || !files.length) return;
    try {
      const r = await ui.upload(`/api/projects/${ctx.pid()}/refs/import/upload`, files);
      toast(`${r.added} referências adicionadas`);
      await load(true); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  return {
    init() {
      $("#btnLogin").onclick = async () => {
        await api("/api/pinterest/login", { method: "POST" });
        toast("Abrindo o Pinterest… faça login na janela"); refreshLogin();
      };
      $("#btnSuggest").onclick = async () => {
        const p = ctx.project(), brand = $("#brand").value.trim();
        if (!p || (!p.product && !brand)) return toast("Informe a marca validada ou o produto do projeto");
        // pid vai junto: com marca validada persistida (ADR-020) o backend sugere só a partir dela.
        const q = `product=${encodeURIComponent(p.product || "")}&vibe=${encodeURIComponent(p.vibe || "")}` +
                  `&brand=${encodeURIComponent(brand)}&pid=${encodeURIComponent(ctx.pid() || "")}`;
        $("#terms").value = (await api(`/api/suggest-terms?${q}`)).join("\n");
      };
      $("#btnSaveBrand").onclick = async () => {
        if (!ctx.pid()) return toast("Crie ou selecione um projeto");
        const brand = $("#brand").value.trim();
        try {
          await api(`/api/projects/${ctx.pid()}/refs/validated-brand`, { method: "PUT", body: JSON.stringify({ brand }) });
          const el = $("#brandSaved");
          if (el) { el.textContent = brand ? "marca validada salva" : "marca validada limpa"; setTimeout(() => { if (el.isConnected) el.textContent = ""; }, 3000); }
          toast(brand ? "Marca validada salva" : "Marca validada limpa");
        } catch (err) { toast(err.message); }
      };
      $("#btnSearch").onclick = async () => {
        const terms = $("#terms").value.split("\n").map(s => s.trim()).filter(Boolean);
        if (!terms.length) return toast("Informe ao menos um termo");
        // Scrape é um JOB: modal com o `log` REAL do backend progredindo (fonte única de polling).
        $("#btnSearch").disabled = true; $("#log").innerHTML = "";
        ui.progressJob({
          title: "Buscar referências",
          subtitle: `${terms.length} termo(s) no Pinterest`,
          start: () => api(`/api/projects/${ctx.pid()}/refs/search`, { method: "POST", body: JSON.stringify({
            terms, max_per_term: +$("#maxPer").value, headless: !$("#headed").checked }) }),
          jobUrl: `/api/projects/${ctx.pid()}/refs/job`,
          done: async () => { renderJob(await api(`/api/projects/${ctx.pid()}/refs/job`)); await load(); ctx.guide(); },
        }).catch((err) => toast("Falhou: " + err.message)).finally(() => { $("#btnSearch").disabled = false; });
      };
      // O protótipo não desenha painel de upload: o painel de escolha inteiro é o alvo do drop
      // (`.panel.over`) e o `input[type=file]` é aberto pelo link discreto do cabeçalho.
      ui.drop($("#refsPick"), upload);
      $("#btnBring").onclick = () => $("#refsUpload").click();
      $("#gallery").addEventListener("click", e => {
        if (e.target.closest("[data-bring]")) { $("#refsUpload").click(); return; }
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id;
        selected.has(id) ? selected.delete(id) : selected.add(id);
        card.classList.toggle("sel"); counts();
      });
      $("#gallery").addEventListener("dblclick", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const c = cands.find(x => x.id === card.dataset.id);
        window.open(ctx.files(`refs/candidates/${c.file}`), "_blank");
      });
      $("#gallery").addEventListener("keydown", e => {
        if (e.key === " " || e.key === "Enter") { e.preventDefault(); e.target.click(); }
      });
      // Filtros multiseleção: marcar/desmarcar um checkbox refiltra; "limpar filtros" reseta.
      $("#refsFilters").addEventListener("change", (e) => {
        const inp = e.target.closest("input[data-filter]"); if (!inp) return;
        const set = inp.dataset.filter === "term" ? filterTerms : filterSources;
        inp.checked ? set.add(inp.value) : set.delete(inp.value);
        renderFilters(); render();
      });
      $("#refsFilters").addEventListener("click", (e) => {
        if (!e.target.closest(".rf-clear")) return;
        filterTerms.clear(); filterSources.clear(); renderFilters(); render();
      });
      $("#btnSave").onclick = async () => {
        try {
          const r = await api(`/api/projects/${ctx.pid()}/refs/select`, { method: "POST",
            body: JSON.stringify({ ids: [...selected] }) });
          toast(`${r.selected} referências salvas em refs/brainstorming`);
          await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      refreshLogin();
      this.onProject();
    },
    async onProject() {
      $("#btnSearch").disabled = $("#btnSave").disabled = !ctx.pid();
      filterTerms.clear(); filterSources.clear();     // filtros são por projeto
      await load();
      if (ctx.pid()) {
        // Marca validada persistida (ADR-020): preenche o campo para editar/sugerir a partir dela.
        try { $("#brand").value = (await api(`/api/projects/${ctx.pid()}/refs/validated-brand`)).brand || ""; }
        catch { /* projeto sem marca validada: campo fica como está */ }
        const j = await api(`/api/projects/${ctx.pid()}/refs/job`);
        renderJob(j);
        // Retoma o feedback em tela se um scrape já estava rodando ao abrir a etapa.
        if (j.state === "running" && !job) { $("#btnSearch").disabled = true; startPoll(); }
      }
      ctx.guide();
    },
    destroy() {
      if (job) { job.stop(); job = null; }
      if (loginJob) { loginJob.stop(); loginJob = null; }
    },
  };
});
