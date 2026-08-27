// Etapa 7 — Trilha (aula 013): assistir a história inteira, decidir se ela fecha e só então
// escolher a música — "você não deve editar antes de escolher a trilha sonora".
Studio.register("music", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  let cands = [], beats = null, story = null;

  const fmt = (s) => (s == null || !isFinite(s) || s <= 0) ? "" : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  const esc = (s) => ui.esc(s);

  // ---------- passo 0: a história inteira ----------
  async function loadStory() {
    if (!ctx.pid()) return;
    try { story = await api(`/api/projects/${ctx.pid()}/music/story`); }
    catch (e) { story = null; return; }
    // O protótipo desenha só o botão: o chip aparece apenas nos estados de atenção (regra 6).
    const chip = $("#musStoryChip");
    const aviso = story.warning || (story.ffmpeg ? "" : "ffmpeg ausente — a sequência bruta não pode ser montada aqui");
    chip.textContent = aviso;
    chip.className = aviso ? "chip warn" : "chip warn hidden";
    $("#btnMusStory").disabled = !story.ffmpeg || !story.clips;

    const v = $("#musStoryVideo"), ph = $("#musStoryPlay");
    if (story.video) { v.src = `${ctx.files(story.video)}?t=${Date.now()}`; v.classList.remove("hidden"); ph.classList.add("hidden"); }
    else { v.classList.add("hidden"); ph.classList.remove("hidden"); }

    const check = story.check;
    if (check) {
      const target = document.querySelector(`input[name="musClosed"][value="${check.closed ? 1 : 0}"]`);
      if (target) target.checked = true;
    }
  }

  async function renderStory() {
    const btn = $("#btnMusStory");
    // "Assistir a história" monta a sequência bruta dos takes com like (ffmpeg) — é um JOB:
    // modal com o `log` REAL progredindo (fonte única de polling).
    btn.disabled = true;
    ui.progressJob({
      title: "Montar a história inteira",
      subtitle: "Sequência bruta dos takes com like (ffmpeg)",
      start: () => api(`/api/projects/${ctx.pid()}/music/story/render`, { method: "POST", body: "{}" }),
      jobUrl: `/api/projects/${ctx.pid()}/music/story/job`,
      done: async () => { await loadStory(); ctx.guide(); toast("Sequência bruta pronta — assista inteira antes de escolher a trilha"); },
    }).catch((err) => toast(err.message)).finally(() => { btn.disabled = false; });
  }

  async function saveStoryCheck() {
    const picked = document.querySelector('input[name="musClosed"]:checked');
    if (!picked) return toast("Responda se a história fecha ou se falta cena.");
    try {
      await api(`/api/projects/${ctx.pid()}/music/story/check`, {
        method: "POST",
        body: JSON.stringify({ closed: picked.value === "1", note: "" }),
      });
      toast("Decisão registrada"); await loadStory(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  // ---------- candidatas e batidas ----------
  async function load() {
    if (!ctx.pid()) { cands = []; return render(); }
    cands = await api(`/api/projects/${ctx.pid()}/music/candidates`);
    try { beats = await api(`/api/projects/${ctx.pid()}/music/beats`); } catch (e) { beats = null; }
    render();
    renderBeats();
  }

  /** Linha de faixa candidata (`.track-row` do catálogo): play + nome/meta + onda + ação. */
  function trackRow(c) {
    const meta = [fmt(c.duration), c.bpm ? `${Math.round(c.bpm)} bpm` : ""].filter(Boolean).join(" · ");
    return `
      <div class="rowcard track-row${c.selected ? " sel" : ""}" data-id="${esc(c.id)}">
        <button class="play" data-id="${esc(c.id)}" title="ouvir / pausar">▶</button>
        <span class="meta">
          <span class="nm">${esc(c.name || c.file)}</span>
          <span class="mt">${esc(meta)}</span>
        </span>
        <div class="wave" title="clique para ir a um ponto da faixa"></div>
        <audio hidden preload="metadata" src="${ctx.files(`audio/candidates/${c.file}`)}"></audio>
        ${c.selected ? ui.chip("escolhida", "ok")
                     : `<button class="pick ghost sm" data-id="${esc(c.id)}">Escolher</button>`}
      </div>`;
  }

  function render() {
    $("#musCounts").textContent = `${cands.length} candidata${cands.length === 1 ? "" : "s"}`;
    // Sem candidatas, o próprio estado vazio é a zona de importação (o painel inteiro também aceita
    // arraste); com candidatas, o chip do cabeçalho abre o seletor de arquivos.
    $("#musList").innerHTML = cands.length ? cands.map(trackRow).join("")
      : `<label class="drop" for="musUpload">Arraste músicas aqui ou <u>escolha arquivos</u></label>`;
  }

  function renderBeats() {
    const chip = $("#musBeatsChip"), ruler = $("#musRuler");
    const antiga = ruler.querySelector(".beats");
    if (antiga) antiga.remove();
    if (!beats || !beats.duration) {
      chip.textContent = cands.some((c) => c.selected) ? "trilha escolhida, sem batidas detectadas" : "nenhuma trilha escolhida";
      chip.className = cands.some((c) => c.selected) ? "chip warn" : "chip mode";
      return;
    }
    chip.textContent = `${beats.beats.length} batidas · ${beats.impacts.length} impactos`;
    chip.className = "chip ok";
    const impacts = new Set(beats.impacts);
    // `.beats` do catálogo: uma barra por batida, impacto em 100% (accent); as demais variam
    // 24–64% só como textura (a API devolve o instante da batida, não a energia dela).
    ruler.insertAdjacentHTML("afterbegin", ui.beats(beats.beats.map((t, i) => ({
      h: impacts.has(t) ? 100 : 24 + ((i * 37) % 40),
      imp: impacts.has(t),
      title: `${t}s${impacts.has(t) ? " (impacto)" : ""}`,
    }))));
  }

  // ---------- áudio da linha (o `<audio>` fica escondido atrás da onda do protótipo) ----------
  function pararTudo(exceto) {
    $("#musList").querySelectorAll(".track-row").forEach((r) => {
      const a = r.querySelector("audio");
      if (!a || a === exceto) return;
      if (!a.paused) a.pause();
      a.currentTime = 0;
      const b = r.querySelector("button.play"), w = r.querySelector(".wave");
      if (b) b.textContent = "▶";
      if (w) w.style.setProperty("--p", "0%");
    });
  }

  async function pick(id) {
    try {
      const r = await api(`/api/projects/${ctx.pid()}/music/select`, {
        method: "POST",
        body: JSON.stringify({ id, license: "" }),
      });
      beats = r.beats;
      const base = r.beats ? `Trilha escolhida · ${r.beats.impacts.length} impactos`
                           : "Trilha escolhida (sem detecção de batidas)";
      toast(`${r.warning ? r.warning + " · " : ""}${base} — se você já montou, a etapa 8 precisa ser refeita`);
      await load(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  async function importar(files) {
    try {
      const r = await ui.upload(`/api/projects/${ctx.pid()}/music/import/upload`, files);
      toast(`${r.added} música(s) importada(s)`); await load(); ctx.guide();
    } catch (err) { toast(err.message); }
  }

  return {
    init() {
      $("#btnMusStory").onclick = renderStory;
      $("#btnMusStoryCheck").onclick = saveStoryCheck;
      // O painel inteiro é alvo de arraste (`.panel.over`); o `input` é o mesmo do chip e do vazio.
      ui.drop($("#musPanel"), importar);
      $("#musList").addEventListener("click", (e) => {
        const p = e.target.closest("button.pick");
        if (p) return pick(p.dataset.id);
        const row = e.target.closest(".track-row");
        const audio = row && row.querySelector("audio");
        if (!audio) return;
        const onda = e.target.closest(".wave");
        if (onda) {
          const box = onda.getBoundingClientRect();
          const razao = Math.min(1, Math.max(0, (e.clientX - box.left) / (box.width || 1)));
          if (audio.duration) {
            audio.currentTime = razao * audio.duration;
            onda.style.setProperty("--p", `${(razao * 100).toFixed(1)}%`);
          }
          return;
        }
        const play = e.target.closest("button.play");
        if (!play) return;
        const tocar = audio.paused;
        pararTudo(audio);
        if (tocar) { audio.play(); play.textContent = "❚❚"; }
        else { audio.pause(); play.textContent = "▶"; }
      });
      // `timeupdate`/`ended` não sobem na árvore: o listener é de captura no container.
      $("#musList").addEventListener("timeupdate", (e) => {
        const a = e.target;
        if (!a || a.tagName !== "AUDIO" || !a.duration) return;
        const w = a.closest(".track-row").querySelector(".wave");
        if (w) w.style.setProperty("--p", `${((a.currentTime / a.duration) * 100).toFixed(1)}%`);
      }, true);
      $("#musList").addEventListener("ended", (e) => {
        const a = e.target;
        if (!a || a.tagName !== "AUDIO") return;
        const row = a.closest(".track-row");
        const b = row.querySelector("button.play"), w = row.querySelector(".wave");
        if (b) b.textContent = "▶";
        if (w) w.style.setProperty("--p", "0%");
      }, true);
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      await loadStory();
      await load();
      ctx.guide();
    },
    destroy() { /* o modal de progresso (progressJob) para o próprio poll ao terminar/fechar */ },
  };
});
