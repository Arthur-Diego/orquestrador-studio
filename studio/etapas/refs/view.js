// Etapa 1 — Referências (aula 009). Registrada no core via Studio.register.
Studio.register("refs", (ctx) => {
  const { $, api, toast } = ctx;
  let cands = [], selected = new Set(), pollTimer = null;

  async function refreshLogin() {
    const s = await api("/api/pinterest/login"), el = $("#loginState");
    if (!el) return;
    if (s.state === "running") { el.textContent = "login: aguardando no navegador…"; el.className = "chip warn"; setTimeout(refreshLogin, 3000); }
    else if (s.state === "done") { el.textContent = s.ok ? "sessão: logada" : "sessão: não logada"; el.className = "chip " + (s.ok ? "ok" : "warn"); }
    else { el.textContent = "sessão: desconhecida (a busca informa)"; el.className = "chip mode"; }
  }

  async function poll() {
    clearTimeout(pollTimer);
    const j = await api(`/api/projects/${ctx.pid()}/refs/job`);
    const log = $("#log"), bar = $("#progress .bar");
    if (j.last && j.last.stage) {
      const l = j.last, line = { start: `sessão logada: ${l.logged_in ? "sim" : "não"}`, term: `buscando "${l.term}" (${l.index + 1}/${l.n_terms})`, download: `baixando ${l.count} imagens de "${l.term}"`, saved: `${l.total} salvas`, done: `concluído: ${l.total} candidatas` }[l.stage] || JSON.stringify(l);
      if (!log.textContent.endsWith(line + "\n")) log.textContent += line + "\n"; log.scrollTop = log.scrollHeight;
      if (l.stage === "term") bar.style.width = `${Math.round((l.index / l.n_terms) * 100)}%`;
      if (l.stage === "done") bar.style.width = "100%";
      if (l.stage === "start") { $("#loginState").textContent = `sessão: ${l.logged_in ? "logada" : "não logada"}`; $("#loginState").className = "chip " + (l.logged_in ? "ok" : "warn"); }
    }
    if (j.state === "running") { pollTimer = setTimeout(poll, 2000); if (j.total) load(true); }
    else { $("#btnSearch").disabled = false; if (j.state === "error") { log.textContent += "ERRO: " + j.error + "\n"; toast("Falhou: " + j.error); } load(); }
  }

  async function load(keepSel) {
    if (!ctx.pid()) { cands = []; render(); return; }
    cands = await api(`/api/projects/${ctx.pid()}/refs/candidates`);
    if (!keepSel) selected = new Set(cands.filter(c => c.selected).map(c => c.id));
    const terms = [...new Set(cands.map(c => c.term))], f = $("#filterTerm"), cur = f.value;
    f.innerHTML = `<option value="">todos os termos</option>` + terms.map(t => `<option ${t === cur ? "selected" : ""}>${t}</option>`).join("");
    render();
  }
  function render() {
    const g = $("#gallery"), term = $("#filterTerm").value, only = $("#onlySel").checked;
    const list = cands.filter(c => (!term || c.term === term) && (!only || selected.has(c.id)));
    $("#counts").textContent = `${cands.length} candidatas · ${selected.size} escolhidas`;
    g.innerHTML = list.length ? list.map(c =>
      `<div class="card ${selected.has(c.id) ? "sel" : ""}" data-id="${c.id}" tabindex="0" title="${(c.alt || "").replace(/"/g, "'")}">
         <img loading="lazy" src="${ctx.files(`refs/candidates/${c.thumb}`)}" alt=""><span class="term">${c.term}</span></div>`).join("")
      : `<div class="empty">${ctx.pid() ? "Nenhuma candidata ainda — rode uma busca." : "Crie ou selecione um projeto."}</div>`;
  }

  return {
    init() {
      $("#btnLogin").onclick = async () => { await api("/api/pinterest/login", { method: "POST" }); toast("Abrindo o Pinterest… faça login na janela"); refreshLogin(); };
      $("#btnSuggest").onclick = async () => {
        const p = ctx.project();
        if (!p || !p.product) return toast("Defina o produto do projeto para sugerir termos");
        $("#terms").value = (await api(`/api/suggest-terms?product=${encodeURIComponent(p.product)}&vibe=${encodeURIComponent(p.vibe || "")}`)).join("\n");
      };
      $("#btnSearch").onclick = async () => {
        const terms = $("#terms").value.split("\n").map(s => s.trim()).filter(Boolean);
        if (!terms.length) return toast("Informe ao menos um termo");
        try {
          await api(`/api/projects/${ctx.pid()}/refs/search`, { method: "POST", body: JSON.stringify({ terms, max_per_term: +$("#maxPer").value, headless: !$("#headed").checked }) });
          $("#btnSearch").disabled = true; $("#log").textContent = ""; poll();
        } catch (err) { toast(err.message); }
      };
      $("#gallery").addEventListener("click", e => {
        const card = e.target.closest(".card"); if (!card) return;
        const id = card.dataset.id; selected.has(id) ? selected.delete(id) : selected.add(id);
        card.classList.toggle("sel"); $("#counts").textContent = `${cands.length} candidatas · ${selected.size} escolhidas`;
      });
      $("#gallery").addEventListener("dblclick", e => { const card = e.target.closest(".card"); if (!card) return; const c = cands.find(x => x.id === card.dataset.id); window.open(ctx.files(`refs/candidates/${c.file}`), "_blank"); });
      $("#gallery").addEventListener("keydown", e => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); e.target.click(); } });
      $("#filterTerm").onchange = $("#onlySel").onchange = render;
      $("#btnSave").onclick = async () => {
        try { const r = await api(`/api/projects/${ctx.pid()}/refs/select`, { method: "POST", body: JSON.stringify({ ids: [...selected] }) }); toast(`${r.selected} referências salvas em refs/brainstorming`); load(); }
        catch (err) { toast(err.message); }
      };
      refreshLogin(); load();
    },
    onProject() { $("#btnSearch").disabled = $("#btnSave").disabled = !ctx.pid(); load(); },
  };
});
