// Etapa 1 — Referências (aula 009). Registrada no core via Studio.register.
// Usa os componentes compartilhados (Studio.ui): escape de HTML, drag&drop, upload e polling.
// Wave 4: a tela é o protótipo — dois painéis. O upload manual (Explore do Midjourney) não tem
// painel próprio: o painel 02 inteiro é alvo de drop e o link "trazer imagens" abre o seletor.
Studio.register("refs", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  let cands = [], selected = new Set(), job = null, loginJob = null;

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
    if (!ctx.pid()) { cands = []; render(); return; }
    cands = await api(`/api/projects/${ctx.pid()}/refs/candidates`);
    if (!keepSel) selected = new Set(cands.filter(c => c.selected).map(c => c.id));
    const terms = [...new Set(cands.map(c => c.term))], f = $("#filterTerm"), cur = f.value;
    f.innerHTML = `<option value="">todos os termos</option>` +
      terms.map(t => `<option ${t === cur ? "selected" : ""}>${ui.esc(t)}</option>`).join("");
    render();
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
    const g = $("#gallery"), term = $("#filterTerm").value;
    const list = cands.filter(c => !term || c.term === term);
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
          $("#btnSearch").disabled = true; $("#log").innerHTML = ""; startPoll();
        } catch (err) { toast(err.message); }
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
      $("#filterTerm").onchange = render;
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
      await load();
      if (ctx.pid()) renderJob(await api(`/api/projects/${ctx.pid()}/refs/job`));
      ctx.guide();
    },
    destroy() {
      if (job) { job.stop(); job = null; }
      if (loginJob) { loginJob.stop(); loginJob = null; }
    },
  };
});
