// Etapa 5 — Animação (aula 012): prompt de movimento por shot, start/end frame gravado,
// importar da UI da Higgsfield, like no usável. Componentes compartilhados: Studio.ui.
//
// Wave 4 (fidelidade ao protótipo `06-animate`): a tela é header + guia + painel 01 (uma linha
// por shot: thumb + nome | input do prompt + faixa de tiles de take + nota) + painel 02 (drop +
// 2 botões + dica). Tudo que o protótipo não desenha saiu da tela; as ações que a aula exige
// foram INTEGRADAS sem elemento extra visível:
//   · opções de geração + "Gerar via CLI" + estado do CLI + galeria de candidatos +
//     "Atribuir selecionado"  →  modal "Gerar take N", aberto pelo slot dashed `+ gerar take N`;
//   · abrir o mp4 (▶) e rejeitar o take (✕)  →  ações só no hover, dentro do tile;
//   · "Salvar" o prompt  →  autosave no `blur`/Enter do input;
//   · chips de estado por shot  →  a nota única ao lado dos tiles (avisos em `--gate`);
//   · caminho da pasta Downloads e "via higgsfield generate list"  →  `title` dos botões.
Studio.register("animate", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const EMPTY = { shots: [], ready: 0, total: 0, model_order: [], mode_tips: {}, last_frames: [] };
  const TAKES_DA_AULA = 2;   // a aula 012 pede 2 takes por shot antes de escolher
  const DL_MINUTES = 120;    // janela fixa da importação da pasta Downloads (protótipo não desenha o campo)
  let plan = { ...EMPTY }, cands = [], picked = null, jobShot = null, job = null;
  let dl = { folder: "", exists: false }, avisos = "", mod = null;
  let cfgModel = null;   // modelo default de "animate.video" vindo da config (ADR-016)

  const esc = (s) => ui.esc(s);
  const key = (s) => `${s.scene}/${s.shot}`;
  const shotOf = (k) => plan.shots.find((s) => key(s) === k);
  const rowOf = (k) => document.querySelector(`.shot-row[data-k="${CSS.escape(k)}"]`);
  const base = () => `/api/projects/${ctx.pid()}/animate`;

  /** Chip do CLI: fora do modal só aparece quando é aviso (sem login / não instalado). */
  async function hfStatus(el) {
    const node = el || $("#anHfState");
    if (!node) return { installed: false, logged_in: false };
    const s = await ui.hfChip(node);
    if (!el) node.hidden = !!(s && s.installed && s.logged_in);
    return s;
  }

  async function loadPlan() {
    if (!ctx.pid()) { plan = { ...EMPTY }; return render(); }
    // Modelo default lido da config de "Créditos & Custos" (ADR-016), não fixo no código.
    if (cfgModel === null) { const d = await ui.defaultModel("animate.video", ctx.pid()); cfgModel = (d && d.model) || ""; }
    try { plan = await api(`${base()}/shots`); }
    catch (err) { $("#anShots").innerHTML = `<div class="empty">${esc(err.message)}</div>`; return; }
    // Avisos do plano não ocupam a tela (o protótipo não os desenha): viram toast na mudança.
    const novos = (plan.warnings || []).join(" · ");
    if (novos && novos !== avisos) toast(novos);
    avisos = novos;
    render();
  }

  async function loadCandidates() {
    if (!ctx.pid()) { cands = []; return renderGallery(); }
    cands = await api(`${base()}/candidates`);
    renderGallery();
  }

  /** "take1" → "take 1" (rótulo do protótipo); qualquer outro id passa inalterado. */
  const rotuloTake = (id, i) => String(id || `take${i + 1}`).replace(/^take(\d+)$/, "take $1");

  /**
   * Tile de um take (protótipo tpl 451/455): o próprio tile é o botão de **like** (clique),
   * com `▶` (abrir o mp4) e `✕` (rejeitar, `data-liked="false"`) visíveis só no hover.
   */
  function takeTile(s, t, i) {
    const liked = t.liked === true;
    const rejeitado = t.liked === false;
    const nome = (t.file || "").split("/").pop();
    const detalhe = [t.model || "", t.start_end ? "start/end" : "", nome].filter(Boolean).join(" · ");
    const k = esc(key(s));
    return `<div role="button" tabindex="0" class="take an-like${liked ? " like" : ""}"
        data-k="${k}" data-take="${esc(t.id)}" data-liked="true" data-file="${esc(t.file || "")}"
        title="${liked ? "take escolhido" : "dar like neste take"}${detalhe ? ` · ${esc(detalhe)}` : ""}"
      ><span>${esc(rotuloTake(t.id, i))} · ${t.duration || 5}s</span>${
      liked ? `<span class="like-lbl">♥ like</span>` : ""}${
      rejeitado ? `<span class="an-rej">✕ rejeitado</span>` : ""
      }<button type="button" class="act an-play" title="abrir ${esc(nome)}">▶</button
      ><button type="button" class="an-x" title="rejeitar este take">✕</button></div>`;
  }

  /** Slot vazio do protótipo (tpl 455 dashed): abre o modal "Gerar take N". Nunca desabilita. */
  function emptyTake(n) {
    return `<div role="button" tabindex="0" class="take empty an-gen" data-n="${n}"
      title="gerar mais um take (opções, CLI e vídeos importados)"><span>+ gerar take ${n}</span></div>`;
  }

  /**
   * Nota única ao lado da faixa de takes (protótipo tpl 457). Absorve o que a wave 3 mostrava
   * como chips de estado: aviso vence estado, e aviso pinta em `--gate`.
   */
  function noteFor(s) {
    const takes = s.takes || [];
    const alertas = [];
    if (!s.image) alertas.push("frame ausente");
    if (s.adapt_idea) alertas.push("adapte a ideia: novo frame na etapa 4 ou corte para preto");
    else if (s.suggested_model && s.failures >= 3) alertas.push(`Tente ${s.suggested_model}`);
    if (s.fallback_black) alertas.push("corte para preto");
    else if (s.suggest_fallback_black) alertas.push("sugestão: corte para preto");
    if (s.orphan) alertas.push("fora do storyboard");
    if (alertas.length) return { text: alertas.join(" · "), warn: true };
    const i = takes.findIndex((t) => t.liked === true);
    if (i >= 0) return { text: `♥ ${rotuloTake(takes[i].id, i)} escolhido`, warn: false };
    if (s.failures) {
      return { text: `${s.failures} ${s.failures === 1 ? "falha" : "falhas"} — na 3ª, troque de modelo`, warn: false };
    }
    if (!takes.length) return { text: "sem take ainda — gere 2 e dê like no usável", warn: false };
    return { text: `${takes.length} take(s) — dê like no usável`, warn: false };
  }

  /** Opções de end frame: o próximo shot da cena (padrão da aula) e os últimos frames da etapa 7. */
  function endOptions(s) {
    const atual = (s.start_end || {}).end || "";
    const auto = atual && atual === s.next_image;
    const opts = [`<option value=""${!atual || auto ? " selected" : ""}${s.next_image ? "" : " disabled"}>`
      + (s.next_image ? `próximo shot da cena (${esc(s.next_in_scene)})` : "sem próximo shot na cena")
      + `</option>`];
    const extras = (plan.last_frames || []).slice();
    if (atual && !auto && !extras.includes(atual)) extras.push(atual);
    extras.forEach((f) => {
      opts.push(`<option value="${esc(f)}"${f === atual ? " selected" : ""}>${esc(f.split("/").pop())}</option>`);
    });
    return opts.join("");
  }

  function tipsHtml(mode) {
    const tips = (plan.mode_tips || {})[mode] || [];
    return tips.map((t) => `<li>${esc(t)}</li>`).join("");
  }

  /** Linha do shot (protótipo tpl 444): thumb + nome | prompt + tiles de take + nota. */
  function shotRow(s) {
    const takes = s.takes || [];
    const tiles = takes.map((t, i) => takeTile(s, t, i)).join("");
    const vazio = takes.length < TAKES_DA_AULA ? emptyTake(takes.length + 1) : "";
    const nota = noteFor(s);
    return `<div class="shot-row" data-k="${esc(key(s))}">
      <div class="col an-left">
        <div class="thumb${s.image ? "" : " none"}">${s.image
          ? `<img src="${ctx.files(s.image)}" loading="lazy" alt="">`
          : `<span>sem frame</span>`}</div>
        <span class="nm">${esc(s.scene)} · ${esc(s.shot)}</span>
      </div>
      <div class="col g10">
        <input class="an-prompt prompt-inline" value="${esc(s.prompt)}"
          placeholder="prompt do movimento, em inglês" aria-label="prompt do movimento de ${esc(key(s))}">
        <div class="takes">${tiles}${vazio}<span class="note${nota.warn ? " warn" : ""}">${esc(nota.text)}</span></div>
      </div>
    </div>`;
  }

  function render() {
    $("#anShots").innerHTML = plan.shots.length
      ? plan.shots.map(shotRow).join("")
      : `<div class="empty">Nenhum shot — a etapa 4 precisa produzir <code>storyboard/storyboard.json</code> primeiro.</div>`;
    hfStatus();
  }

  /** O chip "N vídeos" fica sempre no painel 02; a galeria só existe com o modal aberto. */
  function renderGallery() {
    $("#anCandCount").textContent = `${cands.length} vídeos`;
    const g = document.getElementById("anGallery");
    if (mod && mod.actions[0]) mod.actions[0].disabled = !picked;
    if (!g) return;
    g.innerHTML = cands.length ? cands.map((c) => ui.tile({
      id: c.id,
      src: c.thumb ? ctx.files(`animate/candidates/${c.thumb}`) : "",
      badge: c.source,
      term: `${c.model || c.name || ""} · ${Math.round(c.duration || 0)}s`,
      sel: picked === c.id,
      wide: true,
      title: c.prompt || c.name || "",
    })).join("") : `<div class="empty">Nenhum vídeo ainda — gere na UI da Higgsfield e importe.</div>`;
  }

  function startPoll() {
    if (job) job.stop();
    job = ui.poll(async () => {
      const j = await api(`${base()}/job`);
      const row = jobShot && rowOf(jobShot);
      const slot = row && row.querySelector(".an-gen span");
      if (slot && j.state === "running") slot.textContent = `gerando ${j.done}/${j.total} · ${j.added} takes…`;
      if (j.state === "running") return;
      toast(j.state === "error" ? `erro: ${j.error}` : `job concluído · ${j.added} take(s)`);
      if ((j.log || []).length) console.log("[animate]", j.log.join("\n"));
      jobShot = null;
      await loadCandidates(); await loadPlan(); ctx.guide();
      return false;
    }, 3000);
  }

  // ---------- modal "Gerar take N" (INTEGRA todo o bloco de opções da wave 3) ----------
  /** Campos do modal aberto + o prompt, que vive na linha do shot (protótipo). */
  function fields(s) {
    const p = mod.el, row = rowOf(key(s));
    const end = p.querySelector(".an-end");
    return {
      mode: p.querySelector(".an-mode").value,
      camera: p.querySelector(".an-camera").value,
      action: p.querySelector(".an-action").value,
      slow: p.querySelector(".an-slow").checked,
      duration: +p.querySelector(".an-duration").value,
      model: p.querySelector(".an-model").value,
      count: +p.querySelector(".an-count").value,
      black: p.querySelector(".an-black").checked,
      end: end ? end.value : "",
      prompt: row ? row.querySelector(".an-prompt").value : (s.prompt || ""),
    };
  }

  function modalGerar(s, n) {
    const modes = [["simple", "simples"], ["elaborate", "elaborado (câmera + ação)"], ["start_end", "start/end frame"]];
    const se = s.mode === "start_end";
    const html = `<div class="row wrap">
        <div class="field grow-md"><span class="eyebrow lbl">modo</span>
          <select class="an-mode">${modes.map(([v, l]) =>
            `<option value="${v}"${s.mode === v ? " selected" : ""}>${l}</option>`).join("")}</select></div>
        <div class="field grow-md"><span class="eyebrow lbl">duração</span>
          <select class="an-duration">${[5, 10].map((d) =>
            `<option value="${d}"${s.duration === d ? " selected" : ""}>${d} s</option>`).join("")}</select></div>
      </div>
      <div class="field"><span class="eyebrow lbl">câmera</span>
        <input class="an-camera" placeholder="ex.: Dramatic dolly-in"></div>
      <div class="field"><span class="eyebrow lbl">ação</span>
        <input class="an-action" placeholder="ex.: walking through the blizzard"></div>
      <div class="row wrap">
        <label class="inline"><input type="checkbox" class="an-slow"> mudança lenta (10 s)</label>
        <label class="inline"><input type="checkbox" class="an-black"${s.fallback_black ? " checked" : ""}> corte para preto</label>
        <button type="button" class="ghost an-suggest">Sugerir prompt</button>
      </div>
      <div class="field an-endrow"${se ? "" : ` hidden style="display:none"`}>
        <span class="eyebrow lbl">end frame</span>
        <select class="an-end">${endOptions(s)}</select>
        <span class="hint">start = o frame deste shot; end = o frame de destino da transição (aula 012).</span>
      </div>
      <span class="fine an-example"></span>
      <ul class="fine an-tips">${tipsHtml(s.mode)}</ul>
      <div class="row wrap">
        <div class="field grow-md"><span class="eyebrow lbl">modelo</span>
          <select class="an-model" title="${esc(plan.model_note || "")}">${(plan.model_order || []).map((m) =>
            `<option value="${esc(m)}"${m === (s.suggested_model || cfgModel || (plan.model_order || [])[0] || "") ? " selected" : ""}>${esc(m)}</option>`).join("")}</select></div>
        <label class="inline">takes <input type="number" class="an-count" value="${TAKES_DA_AULA}" min="1" max="4"></label>
        <span class="chip mode an-cli">● CLI · ?</span>
      </div>
      <p class="fine">Na Higgsfield: Image to Video, start frame = este shot${
        s.next_in_scene ? `, end frame = ${esc(s.next_in_scene)} no modo start/end` : ""
      }, <strong>áudio do modelo OFF</strong>, gere 2, like no usável, download.</p>
      <div class="field"><span class="eyebrow lbl">ou atribua um vídeo que você já importou</span>
        <div id="anGallery" class="gallery sm"></div></div>`;
    mod = ui.modal({
      title: `Gerar take ${n} · ${s.scene} · ${s.shot}`,
      html,
      actions: [
        { label: "Atribuir selecionado", kind: "ghost", close: false, onClick: () => assign(s) },
        { label: "Gerar via CLI (gasta créditos)", kind: "primary", close: false, onClick: () => gerar(s) },
      ],
      onClose: () => { mod = null; },
    });
    mod.el.addEventListener("change", onModeChange);
    mod.el.addEventListener("click", (e) => {
      if (e.target.closest(".an-suggest")) return suggest(s);
      const card = e.target.closest("#anGallery .card");
      if (card) { picked = picked === card.dataset.id ? null : card.dataset.id; renderGallery(); }
    });
    mod.el.addEventListener("dblclick", (e) => {
      const card = e.target.closest("#anGallery .card"); if (!card) return;
      const c = cands.find((x) => x.id === card.dataset.id);
      if (c) window.open(ctx.files(`animate/candidates/${c.file}`), "_blank");
    });
    renderGallery();
    hfStatus(mod.el.querySelector(".an-cli"));
  }

  /** Trocar o modo revela o end frame e as dicas daquele modo — sem ida ao servidor. */
  function onModeChange(e) {
    const sel = e.target.closest(".an-mode"); if (!sel || !mod) return;
    const endrow = mod.el.querySelector(".an-endrow"), se = sel.value === "start_end";
    endrow.hidden = !se;
    endrow.style.display = se ? "" : "none";   // `.field {display:flex}` vence o atributo `hidden`
    mod.el.querySelector(".an-tips").innerHTML = tipsHtml(sel.value);
  }

  async function suggest(s) {
    const f = fields(s), row = rowOf(key(s));
    try {
      const q = new URLSearchParams({ scene: s.scene, shot: s.shot, mode: f.mode, camera: f.camera, action: f.action, slow: f.slow });
      const r = await api(`${base()}/prompt?${q}`);
      if (row) row.querySelector(".an-prompt").value = r.prompt;
      mod.el.querySelector(".an-duration").value = r.duration;
      mod.el.querySelector(".an-example").textContent = `Exemplo da aula: ${r.example_pt}`;
      mod.el.querySelector(".an-tips").innerHTML = (r.tips || []).map((t) => `<li>${esc(t)}</li>`).join("");
    } catch (err) { toast(err.message); }
  }

  /**
   * Grava o shot. `aspect_ratio`/`cli_mode` (o bloco "Avançado [extensão]" que saiu da tela) não
   * são enviados: campo ausente preserva o valor gravado — mandar `null` apagaria a configuração.
   */
  async function saveShot(s, patch) {
    await api(`${base()}/shots/${s.scene}/${s.shot}`, { method: "PUT", body: JSON.stringify(patch) });
  }

  async function gerar(s) {
    try {
      const f = fields(s);
      const body = { prompt: f.prompt, mode: f.mode, duration: f.duration, fallback_black: f.black };
      // start/end sem escolha manual = par automático no backend (este frame → próximo da cena).
      if (f.mode === "start_end" && f.end) body.start_end = { end: f.end };
      await saveShot(s, body);
      const ok = await ui.confirmCost(
        () => api(`${base()}/cost`, { method: "POST", body: JSON.stringify({ scene: s.scene, shot: s.shot, model: f.model, count: f.count }) }),
        `Gerar ${f.count} take(s) de ${key(s)} com ${f.model}`);
      if (!ok) { await loadPlan(); ctx.guide(); return; }
      // Geração paga é um JOB: fecha o modal "Gerar take" e abre o de progresso (um modal por vez),
      // com o `log` REAL progredindo (fonte única de polling).
      jobShot = key(s); mod.close();
      ui.progressJob({
        title: `Gerar ${f.count} take(s) · ${key(s)}`,
        subtitle: `modelo ${f.model} (Higgsfield)`,
        start: () => api(`${base()}/generate`, { method: "POST", body: JSON.stringify({ scene: s.scene, shot: s.shot, model: f.model, count: f.count, prompt: f.prompt, duration: f.duration }) }),
        jobUrl: `${base()}/job`,
        done: async (j) => { await loadCandidates(); await loadPlan(); ctx.guide(); toast(`job concluído · ${j.added} take(s)`); },
      }).catch((err) => toast(err.message)).finally(() => { jobShot = null; });
      await loadPlan(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  async function assign(s) {
    if (!picked) return toast("Selecione um vídeo importado");
    try {
      const f = fields(s);
      await api(`${base()}/shots/${s.scene}/${s.shot}/takes`,
                { method: "POST", body: JSON.stringify({ candidate_id: picked, model: f.model, prompt: f.prompt }) });
      picked = null; toast("Take atribuído"); mod.close();
      await loadCandidates(); await loadPlan(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  // ---------- linha do shot ----------
  async function onClick(e) {
    const el = e.target.closest(".an-x, .an-play, .an-gen, .an-like"); if (!el) return;
    const row = el.closest(".shot-row"); if (!row) return;
    const s = shotOf(row.dataset.k); if (!s) return;
    try {
      if (el.classList.contains("an-play")) {
        const f = el.closest(".take").dataset.file;
        if (f) window.open(ctx.files(f), "_blank");
      } else if (el.classList.contains("an-gen")) {
        modalGerar(s, +el.dataset.n || 1);
      } else {
        const tile = el.closest(".take");
        const liked = !el.classList.contains("an-x");
        await api(`${base()}/shots/${s.scene}/${s.shot}/takes/${tile.dataset.take}/like`,
                  { method: "POST", body: JSON.stringify({ liked }) });
        await loadPlan(); ctx.guide();
      }
    } catch (err) { toast(err.message); }
  }

  /** Tile e slot são `role="button"`: Enter/Espaço fazem o mesmo que o clique. */
  function onKeyDown(e) {
    if (e.key === "Enter" && e.target.classList.contains("an-prompt")) return e.target.blur();
    if (e.key !== "Enter" && e.key !== " ") return;
    if (!e.target.classList || !e.target.classList.contains("take")) return;
    e.preventDefault(); onClick(e);
  }

  /** Autosave do prompt (substitui o botão "Salvar" da wave 3): grava ao sair do campo. */
  async function onBlur(e) {
    const inp = e.target.closest && e.target.closest(".an-prompt"); if (!inp) return;
    const row = inp.closest(".shot-row"); const s = shotOf(row.dataset.k); if (!s) return;
    if (inp.value === (s.prompt || "")) return;
    try {
      await saveShot(s, { prompt: inp.value });
      toast("Prompt salvo"); await loadPlan(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  return {
    init() {
      $("#anReload").onclick = async () => { await loadPlan(); await loadCandidates(); ctx.guide(); };
      $("#anShots").addEventListener("click", onClick);
      $("#anShots").addEventListener("keydown", onKeyDown);
      $("#anShots").addEventListener("blur", onBlur, true);   // `blur` não borbulha
      ui.drop($("#anDrop"), async (files) => {
        try {
          const r = await ui.upload(`${base()}/import/upload`, files);
          toast(`${r.added} vídeos importados`); await loadCandidates(); ctx.guide();
        } catch (err) { toast(err.message); }
      });
      $("#anBtnHistory").title = "via `higgsfield generate list --video` (precisa de login no CLI)";
      $("#anBtnDownloads").onclick = async () => {
        if (dl.folder && !dl.exists) return toast(`Pasta não encontrada: ${dl.folder}`);
        try {
          const r = await api(`${base()}/import/downloads`,
                              { method: "POST", body: JSON.stringify({ since_minutes: DL_MINUTES }) });
          toast(`${r.added} novos de ${r.scanned} vídeos recentes`); await loadCandidates(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      $("#anBtnHistory").onclick = async () => {
        try {
          const r = await api(`${base()}/import/history`, { method: "POST", body: JSON.stringify({ size: 50 }) });
          toast(`${r.added} vídeos de ${r.jobs} jobs`); await loadCandidates(); ctx.guide();
        } catch (err) { toast(err.message); }
      };
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      picked = null; jobShot = null; avisos = "";
      await loadCandidates(); await loadPlan();
      dl = await api("/api/animate/downloads-folder");
      $("#anBtnDownloads").title =
        `Importar da pasta Downloads — ${dl.folder}${dl.exists ? "" : " (não encontrada)"} · últimos ${DL_MINUTES} min`;
      // Retoma o feedback em tela se uma geração já estava rodando ao abrir a etapa.
      api(`${base()}/job`).then((j) => { if (j.state === "running" && !job) startPoll(); }).catch(() => {});
      ui.renderGuide("animate");
    },
    destroy() { if (job) { job.stop(); job = null; } if (mod) mod.close(); },
  };
});
