// Etapa 8 — Montagem no ritmo (aula 014): cortes nos impactos, speed ramp, pretos, música, SFX, fade.
Studio.register("edit", (ctx) => {
  const { $, api, toast } = ctx;
  const base = () => `/api/projects/${ctx.pid()}/edit`;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const num = (v, d) => { const n = parseFloat(v); return isNaN(n) ? d : n; };
  let tl = null, sfxLib = [], polling = false, hasFfmpeg = true;

  function collect() {
    if (!tl) return null;
    tl.clips = [...document.querySelectorAll("#clips .clip")].map((row) => {
      const c = tl.clips[+row.dataset.i];
      return { ...c, in: num(row.querySelector(".cin").value, c.in), out: num(row.querySelector(".cout").value, c.out),
               speed: num(row.querySelector(".cspeed").value, c.speed), blend: row.querySelector(".cblend").checked };
    });
    tl.sfx = [...document.querySelectorAll("#sfxTimeline .sfxrow")].map((row) => {
      const s = tl.sfx[+row.dataset.i];
      return { ...s, at: num(row.querySelector(".sat").value, s.at), gain: num(row.querySelector(".sgain").value, s.gain) };
    });
    tl.music = { ...(tl.music || {}), offset: num($("#musicOffset").value, 0) };
    tl.fade_out = num($("#fadeOut").value, 1.5);
    return tl;
  }

  function duration() {
    const clips = (tl.clips || []).reduce((a, c) => a + (c.out - c.in) / Math.max(c.speed || 1, 0.01), 0);
    return clips + (tl.blacks || []).reduce((a, b) => a + (b.dur || 0), 0);
  }

  function render() {
    if (!tl) { $("#clips").innerHTML = `<div class="empty">Sem timeline — a etapa 6 precisa ter takes com like e a etapa 5 um storyboard.</div>`; return; }
    $("#clips").innerHTML = tl.clips.length ? tl.clips.map((c, i) => `
      <div class="row wrap clip" data-i="${i}">
        <span class="eyebrow">${i + 1} · ${esc(c.scene)}/${esc(c.shot)} ${esc(c.take)}</span>
        <label class="inline">in <input class="cin" type="number" step="0.05" min="0" value="${c.in}"></label>
        <label class="inline">out <input class="cout" type="number" step="0.05" min="0" value="${c.out}"></label>
        <label class="inline">speed <input class="cspeed" type="number" step="0.1" min="0.25" max="4" value="${c.speed}"></label>
        <label class="inline"><input class="cblend" type="checkbox" ${c.blend ? "checked" : ""}> mistura de quadros</label>
        <button class="ghost mv" data-d="-1" title="subir">↑</button>
        <button class="ghost mv" data-d="1" title="descer">↓</button>
        <button class="ghost del" title="remover da montagem">remover</button>
        <span class="fine mono">take ${c.duration ?? "?"} s</span>
      </div>`).join("") : `<div class="empty">Nenhum clipe na timeline.</div>`;
    $("#blacks").innerHTML = (tl.blacks || []).length
      ? tl.blacks.map((b) => `<span class="chip ok">preto em ${b.at} s · ${b.dur} s</span>`).join("")
      : `<span class="chip mode">sem quadros pretos</span>`;
    $("#musicOffset").value = (tl.music || {}).offset || 0;
    $("#fadeOut").value = tl.fade_out;
    const mf = (tl.music || {}).file;
    $("#musicInfo").textContent = mf || "sem trilha escolhida na etapa 7 — o master sai sem música";
    const player = $("#musicPlay");
    if (mf) { player.src = ctx.files(mf); player.classList.remove("hidden"); } else { player.classList.add("hidden"); }
    $("#sfxTimeline").innerHTML = (tl.sfx || []).map((s, i) => `
      <div class="row wrap sfxrow" data-i="${i}">
        <span class="eyebrow mono">${esc(s.file.split("/").pop())}</span>
        <label class="inline">em <input class="sat" type="number" step="0.1" min="0" value="${s.at}"> s</label>
        <label class="inline">ganho <input class="sgain" type="number" step="1" min="-40" max="12" value="${s.gain}"> dB</label>
        <button class="ghost sdel">remover</button>
      </div>`).join("");
    $("#lfClip").innerHTML = tl.clips.map((c, i) => `<option value="${i}">${esc(c.scene)}/${esc(c.shot)} ${esc(c.take)}</option>`).join("");
    $("#durInfo").textContent = `duração ${duration().toFixed(2)} s`;
  }

  async function load() {
    if (!ctx.pid()) { tl = null; render(); return; }
    try {
      const r = await api(`${base()}/timeline`);
      tl = r.timeline;
      $("#editState").textContent = r.created ? "timeline criada a partir dos takes com like" : `${tl.clips.length} clipes`;
      $("#editState").className = "chip ok";
    } catch (err) {
      tl = null;
      $("#editState").textContent = err.message;
      $("#editState").className = "chip warn";
    }
    render();
  }

  async function save(silent) {
    const body = collect();
    if (!body) return;
    try {
      const r = await api(`${base()}/timeline`, { method: "PUT", body: JSON.stringify(body) });
      tl = r.timeline; render();
      if (!silent) toast(`Timeline salva · ${r.duration} s`);
    } catch (err) { toast(err.message); }
  }

  async function propose(apply) {
    try {
      await save(true);
      const r = await api(`${base()}/propose-cuts`, { method: "POST", body: JSON.stringify({ offset: num($("#musicOffset").value, 0), black_dur: num($("#blackDur").value, 0.2), apply: !!apply }) });
      tl = r.timeline; render();
      $("#cutsInfo").textContent = `${r.impacts_used.length} impactos usados (${r.impacts_used.map((t) => t.toFixed(2)).join(", ")}) · ${r.duration} s${apply ? " · aplicado" : " — confira e aplique"}`;
    } catch (err) { $("#cutsInfo").textContent = err.message; toast(err.message); }
  }

  async function loadSfx() {
    if (!ctx.pid()) return;
    sfxLib = await api(`${base()}/sfx`);
    $("#sfxCount").textContent = `${sfxLib.length} SFX`;
    $("#sfxLib").innerHTML = sfxLib.length ? sfxLib.map((s) => `
      <div class="row wrap">
        <span class="mono fine">${esc(s.name)} · ${(s.duration || 0).toFixed(1)} s</span>
        <audio controls preload="none" src="${ctx.files(s.file)}"></audio>
        <button class="ghost use" data-file="${esc(s.file)}">usar na timeline</button>
      </div>`).join("") : `<div class="empty">Nenhum SFX importado ainda.</div>`;
  }

  async function upload(files) {
    if (!files.length) return;
    const fd = new FormData(); [...files].forEach((f) => fd.append("files", f));
    const r = await fetch(`${base()}/sfx/upload`, { method: "POST", body: fd });
    if (!r.ok) return toast((await r.json().catch(() => ({}))).detail || r.statusText);
    toast(`${(await r.json()).added} SFX importados`); loadSfx();
  }

  async function poll() {
    const j = await api(`${base()}/render/job`);
    const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
    $("#renderBar").style.width = `${j.state === "done" ? 100 : pct}%`;
    $("#renderLog").innerHTML = (j.log || []).map((l) => `<div>${esc(l)}</div>`).join("") + (j.error ? `<div class="warn">${esc(j.error)}</div>` : "");
    if (j.state === "running") { setTimeout(poll, 3000); return; }
    polling = false;
    $("#btnRough").disabled = $("#btnMaster").disabled = false;
    if (j.state === "done" && j.output) {
      const v = $("#preview"); v.src = `${ctx.files(j.output)}?t=${Date.now()}`; v.classList.remove("hidden");
      toast(`${j.output} pronto`);
    } else if (j.state === "error") { toast(j.error); }
  }

  async function startRender(target) {
    try {
      await save(true);
      await api(`${base()}/render`, { method: "POST", body: JSON.stringify({ target }) });
      $("#btnRough").disabled = $("#btnMaster").disabled = true;
      if (!polling) { polling = true; poll(); }
    } catch (err) { toast(err.message); }
  }

  return {
    init() {
      $("#btnSave").onclick = () => save(false);
      $("#btnReset").onclick = async () => {
        if (!confirm("Recriar a timeline a partir dos takes com like? As edições atuais são perdidas.")) return;
        try { const r = await api(`${base()}/timeline/reset`, { method: "POST" }); tl = r.timeline; render(); toast("Timeline recriada"); }
        catch (err) { toast(err.message); }
      };
      $("#btnPropose").onclick = () => propose(false);
      $("#btnApply").onclick = () => propose(true);
      $("#clips").addEventListener("click", (e) => {
        const row = e.target.closest(".clip"); if (!row) return;
        const i = +row.dataset.i; collect();
        if (e.target.closest(".del")) tl.clips.splice(i, 1);
        else if (e.target.closest(".mv")) {
          const d = +e.target.closest(".mv").dataset.d, j = i + d;
          if (j < 0 || j >= tl.clips.length) return;
          [tl.clips[i], tl.clips[j]] = [tl.clips[j], tl.clips[i]];
        } else return;
        render();
      });
      $("#sfxTimeline").addEventListener("click", (e) => {
        const row = e.target.closest(".sfxrow"); if (!row || !e.target.closest(".sdel")) return;
        collect(); tl.sfx.splice(+row.dataset.i, 1); render();
      });
      $("#sfxLib").addEventListener("click", (e) => {
        const b = e.target.closest(".use"); if (!b || !tl) return;
        collect(); tl.sfx.push({ file: b.dataset.file, at: 0, gain: -6 }); render();
      });
      const drop = $("#sfxDrop");
      drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
      drop.addEventListener("dragleave", () => drop.classList.remove("over"));
      drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files); });
      $("#sfxUpload").addEventListener("change", (e) => upload(e.target.files));
      $("#btnLastFrame").onclick = async () => {
        if (!tl || !tl.clips.length) return toast("Sem clipes na timeline");
        const c = tl.clips[+$("#lfClip").value];
        try {
          const r = await api(`${base()}/last-frame`, { method: "POST", body: JSON.stringify({ scene: c.scene, shot: c.shot, take: c.take }) });
          $("#lfInfo").textContent = `${r.file} — ${r.instruction}`;
          const img = $("#lfImg"); img.src = `${ctx.files(r.file)}?t=${Date.now()}`; img.classList.remove("hidden");
        } catch (err) { $("#lfInfo").textContent = err.message; toast(err.message); }
      };
      $("#btnRough").onclick = () => startRender("rough");
      $("#btnMaster").onclick = () => startRender("master");
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) return;
      try {
        const f = await api("/api/edit/ffmpeg");
        hasFfmpeg = f.available;
        $("#ffState").textContent = hasFfmpeg ? "ffmpeg pronto" : "ffmpeg ausente — render e último frame bloqueados";
        $("#ffState").className = hasFfmpeg ? "chip ok" : "chip warn";
        $("#btnRough").disabled = $("#btnMaster").disabled = $("#btnLastFrame").disabled = !hasFfmpeg;
      } catch (e) { /* chip fica neutro */ }
      await load(); await loadSfx();
      if (!polling) { polling = true; poll(); }
    },
  };
});
