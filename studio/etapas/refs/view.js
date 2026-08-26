// Etapa 1 — Referências (aula 009). Registrada no core via Studio.register.
// Usa os componentes compartilhados (Studio.ui): escape de HTML, drag&drop, upload e polling.
Studio.register("refs", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  let cands = [], selected = new Set(), notes = {}, job = null, loginJob = null;

  async function refreshLogin() {
    const el = $("#loginState");
    if (!el) return;
    const s = await api("/api/pinterest/login");
    if (s.state === "running") {
      el.textContent = "login: aguardando no navegador…"; el.className = "chip warn";
      if (!loginJob) loginJob = ui.poll(async () => {
        const cur = await api("/api/pinterest/login");
        if (cur.state === "running") return;
        loginJob = null; refreshLogin(); return false;      // false encerra o poll
      }, 3000);
    } else if (s.state === "done") {
      el.textContent = s.ok ? "sessão: logada" : "sessão: não logada";
      el.className = "chip " + (s.ok ? "ok" : "warn");
    } else {
      el.textContent = "sessão: desconhecida (a busca informa)"; el.className = "chip mode";
    }
  }

  function logLine(l) {
    return { start: `sessão logada: ${l.logged_in ? "sim" : "não"}`,
             term: `buscando "${l.term}" (${l.index + 1}/${l.n_terms})`,
             download: `baixando ${l.count} imagens de "${l.term}"`,
             saved: `${l.total} salvas`,
             done: `concluído: ${l.total} candidatas` }[l.stage] || JSON.stringify(l);
  }

  function startPoll() {
    if (job) job.stop();
    job = ui.poll(async () => {
      const j = await api(`/api/projects/${ctx.pid()}/refs/job`);
      const log = $("#log"), bar = $("#progress .bar");
      if (j.last && j.last.stage) {
        const l = j.last, line = logLine(l);
        if (!log.textContent.endsWith(line + "\n")) log.textContent += line + "\n";
        log.scrollTop = log.scrollHeight;
        if (l.stage === "term") {
          bar.style.width = `${Math.round((l.index / l.n_terms) * 100)}%`;
          scrapeLabel(`${l.index + 1}/${l.n_terms} termos`);
        }
        if (l.stage === "done") { bar.style.width = "100%"; scrapeLabel(`${l.total} candidatas`); }
        if (l.stage === "start") {
          $("#loginState").textContent = `sessão: ${l.logged_in ? "logada" : "não logada"}`;
          $("#loginState").className = "chip " + (l.logged_in ? "ok" : "warn");
        }
      }
      if (j.state === "running") { if (j.total) load(true); return; }
      $("#btnSearch").disabled = false;
      if (j.state === "error") { log.textContent += "ERRO: " + j.error + "\n"; toast("Falhou: " + j.error); }
      await load();
      ctx.guide();
      job = null;
      return false;
    }, 2000);
  }

  async function load(keepSel) {
    if (!ctx.pid()) { cands = []; render(); return; }
    cands = await api(`/api/projects/${ctx.pid()}/refs/candidates`);
    if (!keepSel) selected = new Set(cands.filter(c => c.selected).map(c => c.id));
    cands.forEach(c => { const w = (c.extra || {}).why; if (w && !notes[c.id]) notes[c.id] = w; });
    const terms = [...new Set(cands.map(c => c.term))], f = $("#filterTerm"), cur = f.value;
    f.innerHTML = `<option value="">todos os termos</option>` +
      terms.map(t => `<option ${t === cur ? "selected" : ""}>${ui.esc(t)}</option>`).join("");
    render();
  }

  function counts() {
    $("#counts").textContent = `${cands.length} candidatas · ${selected.size} escolhidas`;
  }

  // Rótulo do "Último scrape" (`.progress-lbl` do redesign): sempre derivado do job real
  // ou da lista de candidatas — nunca dado de exemplo.
  function scrapeLabel(txt) {
    const el = $("#scrapeCount");
    if (el) el.textContent = txt || (cands.length ? `${cands.length} candidatas` : "—");
  }

  function render() {
    const g = $("#gallery"), term = $("#filterTerm").value, only = $("#onlySel").checked;
    const list = cands.filter(c => (!term || c.term === term) && (!only || selected.has(c.id)));
    counts();
    if (!job) scrapeLabel();
    // Tile do catálogo do shell: `.card` > img + `span.src` (origem) + `span.term` (termo).
    // O `input.why` é [extensão] do Studio e usa a classe local `.rf-why` (view.html).
    g.innerHTML = list.length ? list.map(c =>
      `<div class="card ${selected.has(c.id) ? "sel" : ""}" data-id="${ui.esc(c.id)}" tabindex="0" title="${ui.esc(c.alt || "")}">
         <img loading="lazy" src="${ctx.files(`refs/candidates/${c.thumb}`)}" alt="">
         <span class="src">${ui.esc(c.source || "pinterest")}</span>
         <span class="term">${ui.esc(c.term)}</span>
         <input class="why rf-why" data-id="${ui.esc(c.id)}" placeholder="por quê? (opcional)" value="${ui.esc(notes[c.id] || "")}">
       </div>`).join("")
      : `<div class="empty">${ctx.pid() ? "Nenhuma candidata ainda — rode uma busca ou traga imagens por upload." : "Crie ou selecione um projeto."}</div>`;
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
        const q = `product=${encodeURIComponent(p.product || "")}&vibe=${encodeURIComponent(p.vibe || "")}` +
                  `&brand=${encodeURIComponent(brand)}`;
        $("#terms").value = (await api(`/api/suggest-terms?${q}`)).join("\n");
      };
      $("#btnSearch").onclick = async () => {
        const terms = $("#terms").value.split("\n").map(s => s.trim()).filter(Boolean);
        if (!terms.length) return toast("Informe ao menos um termo");
        try {
          await api(`/api/projects/${ctx.pid()}/refs/search`, { method: "POST", body: JSON.stringify({
            terms, max_per_term: +$("#maxPer").value, headless: !$("#headed").checked }) });
          $("#btnSearch").disabled = true; $("#log").textContent = ""; startPoll();
        } catch (err) { toast(err.message); }
      };
      ui.drop($("#refsDrop"), upload);
      $("#gallery").addEventListener("click", e => {
        if (e.target.closest("input.why")) return;                 // escrever o "por quê" não marca o card
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id;
        selected.has(id) ? selected.delete(id) : selected.add(id);
        card.classList.toggle("sel"); counts();
      });
      $("#gallery").addEventListener("input", e => {
        const inp = e.target.closest("input.why"); if (!inp) return;
        notes[inp.dataset.id] = inp.value;
      });
      $("#gallery").addEventListener("dblclick", e => {
        const card = e.target.closest(".card"); if (!card || e.target.closest("input.why")) return;
        const c = cands.find(x => x.id === card.dataset.id);
        window.open(ctx.files(`refs/candidates/${c.file}`), "_blank");
      });
      $("#gallery").addEventListener("keydown", e => {
        if (e.target.closest("input.why")) return;
        if (e.key === " " || e.key === "Enter") { e.preventDefault(); e.target.click(); }
      });
      $("#filterTerm").onchange = $("#onlySel").onchange = render;
      $("#btnSave").onclick = async () => {
        try {
          const why = {};
          [...selected].forEach(id => { if ((notes[id] || "").trim()) why[id] = notes[id].trim(); });
          const r = await api(`/api/projects/${ctx.pid()}/refs/select`, { method: "POST",
            body: JSON.stringify({ ids: [...selected], notes: why }) });
          toast(`${r.selected} referências salvas em refs/brainstorming`);
          await load(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      refreshLogin();
      this.onProject();
    },
    async onProject() {
      $("#btnSearch").disabled = $("#btnSave").disabled = !ctx.pid();
      notes = {};
      await load();
      ctx.guide();
    },
    destroy() {
      if (job) { job.stop(); job = null; }
      if (loginJob) { loginJob.stop(); loginJob = null; }
    },
  };
});
