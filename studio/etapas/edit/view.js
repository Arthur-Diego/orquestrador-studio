// Etapa 8 — Montagem de vídeo: editor de vídeo completo [extensão] (estilo CapCut desktop).
//
// A montagem da aula 014 (backbone: clips + música + SFX + pretos + fade) continua sendo o que
// o ffmpeg renderiza. Este editor adiciona, de forma NÃO destrutiva, um preview WYSIWYG no
// browser, timeline multi-track, textos/legendas/overlays, transições, undo/redo e autosave —
// tudo persistido no bloco `editor` da mesma `edit/timeline.json`. O que ainda não entra no
// master.mp4 é rotulado na UI, nunca simulado.
//
// Organização (arquivo único do plugin): Store (estado + histórico) · model (deriva a visão de
// tracks do backbone) · Playback (engine de reprodução) · Preview · Timeline · Panels · Props ·
// Header · Shortcuts · ContextMenu · Persistence.
Studio.register("edit", (ctx) => {
  const { $, api, toast } = ctx;
  const ui = Studio.ui;
  const esc = (s) => ui.esc(s);
  const base = () => `/api/projects/${ctx.pid()}/edit`;
  const root = () => document.getElementById("ved");

  // ---------------------------------------------------------------- constantes
  const FPS_CHOICES = [24, 25, 30, 50, 60];
  const ASPECTS = { "16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1, "4:5": 4 / 5, "4:3": 4 / 3, "21:9": 21 / 9 };
  const RES = [["720p", 1280, 720], ["1080p", 1920, 1080], ["1440p", 2560, 1440], ["4K", 3840, 2160]];
  const SPEEDS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4];
  const PANELS = [
    ["media", "🎞", "Mídia"], ["text", "T", "Texto"], ["caption", "␣", "Legendas"],
    ["audio", "♪", "Áudio"], ["transitions", "⇄", "Transições"], ["effects", "✦", "Efeitos"],
    ["filters", "◐", "Filtros"], ["elements", "◆", "Elementos"], ["adjust", "🎚", "Ajustes"],
  ];
  const TRANSITIONS = [
    ["fade", "Fade"], ["dissolve", "Dissolve"], ["slide", "Slide"], ["zoom", "Zoom"],
    ["wipe", "Wipe"], ["blur", "Blur"], ["flash", "Flash"], ["glitch", "Glitch"],
    ["spin", "Spin"], ["push", "Push"], ["pull", "Pull"], ["directional", "Direcional"],
  ];
  const EFFECTS = [
    ["blur", "Blur"], ["glow", "Glow"], ["vignette", "Vinheta"], ["grain", "Grão"],
    ["shake", "Tremor"], ["glitch", "Glitch"], ["pixelate", "Pixelate"], ["rgbsplit", "RGB Split"],
    ["chromatic", "Aberração"], ["sharpen", "Nitidez"], ["mirror", "Espelho"], ["zoom", "Zoom"],
  ];
  const FILTER_PRESETS = [
    ["none", "Original", ""], ["warm", "Quente", "sepia(.25) saturate(1.2)"],
    ["cool", "Frio", "hue-rotate(-12deg) saturate(1.1) brightness(1.03)"],
    ["mono", "P&B", "grayscale(1) contrast(1.1)"], ["vivid", "Vívido", "saturate(1.5) contrast(1.08)"],
    ["fade", "Desbotado", "contrast(.9) brightness(1.08) saturate(.85)"],
    ["noir", "Noir", "grayscale(1) contrast(1.3) brightness(.9)"], ["dream", "Sonho", "blur(.4px) brightness(1.08) saturate(1.2)"],
  ];
  const ADJUSTS = [
    ["exposure", "Exposição"], ["brightness", "Brilho"], ["contrast", "Contraste"], ["saturation", "Saturação"],
    ["temperature", "Temperatura"], ["hue", "Matiz"], ["highlights", "Realces"], ["shadows", "Sombras"],
    ["whites", "Brancos"], ["blacks", "Pretos"], ["sharpen", "Nitidez"], ["fade", "Fade"],
    ["vignette", "Vinheta"], ["grain", "Grão"],
  ];
  const TEXT_PRESETS = [
    ["title", "Título", { size: 96, weight: 800 }], ["subtitle", "Subtítulo", { size: 54, weight: 600 }],
    ["body", "Texto", { size: 40, weight: 400 }], ["headline", "Headline", { size: 120, weight: 800, uppercase: true }],
    ["lower", "Lower third", { size: 44, weight: 700, align: "left" }], ["cta", "CTA", { size: 60, weight: 800, bg: "#0B7F93" }],
  ];
  const TRACK_LABEL = { video: "Vídeo", overlay: "Overlay", text: "Texto", caption: "Legendas",
    audio: "Áudio", music: "Música", sfx: "SFX" };

  // ---------------------------------------------------------------- utilidades
  const clamp = (v, a, b) => Math.min(Math.max(v, a), b);
  const num = (v, d = 0) => { const n = parseFloat(v); return isNaN(n) ? d : n; };
  const newId = (p) => `${p}_${Math.random().toString(36).slice(2, 10)}`;
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const fmtTC = (s) => {
    s = Math.max(0, s || 0); const m = Math.floor(s / 60), sec = Math.floor(s % 60), cs = Math.floor((s % 1) * 100);
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
  };
  const clipLen = (c) => (num(c.out) - num(c.in)) / Math.max(num(c.speed, 1), 0.05);
  const nameOf = (c) => (c.file ? c.file.split("/").pop() : `${c.scene}_${c.shot}_${c.take}`);

  // ---------------------------------------------------------------- STORE
  const St = {
    timeline: null,          // shape do backend (clips/blacks/music/sfx/fade_out/loudnorm/editor)
    beats: null,
    hasFfmpeg: true,
    // efêmeros (não entram no histórico)
    selection: [],           // uids de itens selecionados
    playhead: 0,
    isPlaying: false,
    loop: false,
    muted: false,
    volume: 1,
    zoom: 40,                // px por segundo
    snap: true,
    panel: "media",
    propsTab: "basic",
    saveStatus: "saved",
    // histórico (snapshots do backbone — JSON leve, nunca binário)
    history: [], future: [], hLabel: "",
    sfxLib: [],
  };
  let saveTimer = null, job = null, raf = null, playClock = 0;

  function ed() {
    // garante o bloco editor em memória (semeado no load); nunca null quando há timeline
    if (!St.timeline.editor) St.timeline.editor = { version: 1, project: { width: 1920, height: 1080, fps: 30, aspect: "16:9" }, tracks: [], clip_fx: {}, transitions: [], markers: [], ui: { zoom: 40, snap: true } };
    const e = St.timeline.editor;
    e.project = e.project || { width: 1920, height: 1080, fps: 30, aspect: "16:9" };
    e.tracks = e.tracks || []; e.clip_fx = e.clip_fx || {}; e.transitions = e.transitions || []; e.markers = e.markers || [];
    return e;
  }
  const proj = () => ed().project;

  /** commit(label, mutator): registra snapshot, aplica mutação estrutural, agenda autosave e re-renderiza. */
  function commit(label, mutator) {
    St.history.push(clone(St.timeline)); if (St.history.length > 80) St.history.shift();
    St.future = []; St.hLabel = label;
    mutator();
    setStatus("dirty"); scheduleSave(); renderAll();
  }
  function undo() {
    if (!St.history.length) return;
    St.future.push(clone(St.timeline)); St.timeline = St.history.pop();
    St.selection = []; setStatus("dirty"); scheduleSave(); renderAll(); toast("Desfeito");
  }
  function redo() {
    if (!St.future.length) return;
    St.history.push(clone(St.timeline)); St.timeline = St.future.pop();
    St.selection = []; setStatus("dirty"); scheduleSave(); renderAll(); toast("Refeito");
  }

  // ---------------------------------------------------------------- MODEL (backbone -> visão de tracks)
  /** Segmentos compostos do backbone: clipes na ordem + pretos que empurram (mesma regra do render). */
  function segments() {
    const tl = St.timeline, clips = tl.clips || [], blacks = tl.blacks || [];
    const segs = []; let pos = 0;
    clips.forEach((c, i) => {
      const len = clipLen(c);
      segs.push({ kind: "clip", clip: c, uid: c.id || (c.id = newId("c")), i, start: pos, dur: len });
      pos = +(pos + len).toFixed(3);
      const b = blacks.find((b) => Math.abs(num(b.at) - pos) <= 0.25 && num(b.dur) > 0);
      if (b) { segs.push({ kind: "black", black: b, start: pos, dur: num(b.dur) }); pos = +(pos + num(b.dur)).toFixed(3); }
    });
    return segs;
  }
  function duration() { const s = segments(); return s.length ? +(s[s.length - 1].start + s[s.length - 1].dur).toFixed(3) : 0; }
  function rawCutAt(i) { const clips = St.timeline.clips || []; let p = 0; for (let k = 0; k <= i; k++) p += clipLen(clips[k]); return +p.toFixed(3); }

  /** Visão unificada das faixas para a timeline: vídeo (backbone) + música + sfx + tracks do editor. */
  function tracks() {
    const tl = St.timeline, e = ed(), segs = segments();
    const out = [];
    // vídeo (backbone) — sequencial
    out.push({ id: "video", type: "video", name: "Vídeo", height: 62, locked: false, visible: true, muted: false, backbone: true,
      items: segs.filter((s) => s.kind === "clip").map((s) => ({ uid: s.clip.id, kind: "video", clip: s.clip, start: s.start, dur: s.dur, i: s.i })),
      blacks: segs.filter((s) => s.kind === "black").map((s) => ({ start: s.start, dur: s.dur, black: s.black })) });
    // tracks do editor de vídeo/overlay/texto/legenda que vêm de e.tracks
    (e.tracks || []).filter((t) => ["overlay", "text", "caption", "video"].includes(t.type)).forEach((t) => {
      out.push({ id: t.id, type: t.type, name: t.name || TRACK_LABEL[t.type], height: t.height || 40, locked: t.locked, visible: t.visible !== false, muted: t.muted,
        items: (t.items || []).map((it) => ({ uid: it.id, kind: t.type, item: it, track: t, start: num(it.start), dur: Math.max(num(it.end) - num(it.start), 0.3) })) });
    });
    // música (backbone) — 1 faixa cobrindo o vídeo
    const mf = (tl.music || {}).file;
    out.push({ id: "music", type: "music", name: "Música", height: 40, locked: false, visible: true, muted: false, backbone: true,
      items: mf ? [{ uid: "music", kind: "music", music: tl.music, start: 0, dur: duration() }] : [] });
    // faixas de áudio extra do editor
    (e.tracks || []).filter((t) => ["audio", "music"].includes(t.type)).forEach((t) => {
      out.push({ id: t.id, type: t.type, name: t.name || TRACK_LABEL[t.type], height: t.height || 38, locked: t.locked, visible: t.visible !== false, muted: t.muted,
        items: (t.items || []).map((it) => ({ uid: it.id, kind: t.type, item: it, track: t, start: num(it.start), dur: Math.max(num(it.end) - num(it.start), 1) })) });
    });
    // sfx (backbone)
    out.push({ id: "sfx", type: "sfx", name: "SFX", height: 34, locked: false, visible: true, muted: false, backbone: true,
      items: (tl.sfx || []).map((s, i) => ({ uid: `sfx_${i}`, kind: "sfx", sfx: s, i, start: num(s.at), dur: sfxDur(s) })) });
    return out;
  }
  function sfxDur(s) { const lib = St.sfxLib.find((x) => x.file === s.file); return lib && lib.duration ? lib.duration : 1.2; }

  function findItem(uid) {
    for (const t of tracks()) { const it = t.items.find((x) => x.uid === uid); if (it) return { ...it, track: t }; }
    return null;
  }
  const isSel = (uid) => St.selection.includes(uid);

  // fx por clipe (transform/effects/filters) — chaveado pelo id do clipe
  function clipFx(cid) { const m = ed().clip_fx; return (m[cid] = m[cid] || { transform: { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 }, effects: [], filters: {} }); }

  // ---------------------------------------------------------------- PLAYBACK
  const videoPool = new Map();
  function videoFor(file) {
    if (!file) return null;
    if (videoPool.has(file)) return videoPool.get(file);
    const v = document.createElement("video");
    v.preload = "metadata"; v.muted = true; v.playsInline = true; v.src = ctx.files(file);
    v.style.display = "none"; v.addEventListener("error", () => v.dataset.err = "1");
    videoPool.set(file, v); const stage = document.getElementById("edStage"); if (stage) stage.appendChild(v);
    return v;
  }
  function musicEl() {
    let a = document.getElementById("edMusic");
    const mf = (St.timeline.music || {}).file;
    if (!mf) { if (a) a.pause(); return null; }
    if (!a) { a = document.createElement("audio"); a.id = "edMusic"; a.preload = "auto"; document.getElementById("edStage").appendChild(a); }
    const want = ctx.files(mf); if (a.dataset.src !== want) { a.src = want; a.dataset.src = want; }
    return a;
  }

  function segAt(t) { const segs = segments(); for (const s of segs) if (t >= s.start - 1e-4 && t < s.start + s.dur - 1e-4) return s; return segs[segs.length - 1] || null; }

  function play() {
    if (St.isPlaying) return; if (duration() <= 0) return;
    St.isPlaying = true; if (St.playhead >= duration() - 0.02) St.playhead = 0;
    playClock = performance.now();
    const mu = musicEl(); if (mu) { mu.currentTime = clamp(num((St.timeline.music || {}).offset) + St.playhead, 0, 1e6); mu.volume = St.muted ? 0 : St.volume; mu.play().catch(() => {}); }
    setPlayIcon(); loopTick();
  }
  function pause() {
    St.isPlaying = false; if (raf) cancelAnimationFrame(raf), raf = null;
    videoPool.forEach((v) => v.pause()); const mu = document.getElementById("edMusic"); if (mu) mu.pause();
    setPlayIcon();
  }
  function togglePlay() { St.isPlaying ? pause() : play(); }

  function loopTick() {
    const now = performance.now(), dt = (now - playClock) / 1000; playClock = now;
    const seg = segAt(St.playhead);
    if (seg && seg.kind === "clip") {
      const v = videoFor(seg.clip.file);
      if (v && !v.dataset.err) {
        const want = num(seg.clip.in) + (St.playhead - seg.start) * num(seg.clip.speed, 1);
        if (v.paused) { try { v.currentTime = want; } catch (e) { /* metadata ainda não */ } v.playbackRate = clamp(num(seg.clip.speed, 1), 0.25, 4); v.play().catch(() => {}); }
        // deriva o playhead do vídeo real (movimento suave)
        St.playhead = seg.start + (v.currentTime - num(seg.clip.in)) / Math.max(num(seg.clip.speed, 1), 0.05);
        if (v.currentTime >= num(seg.clip.out) - 0.03 || v.ended) { v.pause(); St.playhead = seg.start + seg.dur + 0.001; }
      } else { St.playhead += dt; }
    } else { St.playhead += dt; }
    if (St.playhead >= duration() - 0.01) {
      if (St.loop) { seekTo(0); if (St.isPlaying) { playClock = performance.now(); } }
      else { St.playhead = duration(); pause(); }
    }
    syncMusic(); paintPlayhead(); renderPreview();
    if (St.isPlaying) raf = requestAnimationFrame(loopTick);
  }
  function syncMusic() {
    const mu = document.getElementById("edMusic"); if (!mu) return;
    const want = num((St.timeline.music || {}).offset) + St.playhead;
    if (St.isPlaying && Math.abs(mu.currentTime - want) > 0.3) mu.currentTime = clamp(want, 0, 1e6);
    mu.volume = St.muted ? 0 : St.volume;
  }
  function seekTo(t) {
    const wasPlaying = St.isPlaying; if (wasPlaying) pause();
    St.playhead = clamp(t, 0, duration());
    const seg = segAt(St.playhead);
    if (seg && seg.kind === "clip") { const v = videoFor(seg.clip.file); if (v) { try { v.currentTime = num(seg.clip.in) + (St.playhead - seg.start) * num(seg.clip.speed, 1); } catch (e) {} } }
    const mu = document.getElementById("edMusic"); if (mu) mu.currentTime = clamp(num((St.timeline.music || {}).offset) + St.playhead, 0, 1e6);
    paintPlayhead(); renderPreview();
    if (wasPlaying) play();
  }
  function step(frames) { const f = proj().fps || 30; seekTo(St.playhead + frames / f); }

  // ---------------------------------------------------------------- PREVIEW
  function stageBox() {
    const wrap = document.getElementById("edStageWrap"), stage = document.getElementById("edStage");
    if (!wrap || !stage) return;
    const p = proj(), ar = ASPECTS[p.aspect] || (p.width / p.height);
    const availW = wrap.clientWidth - 4, availH = wrap.clientHeight - 4;
    let w = availW, h = w / ar; if (h > availH) { h = availH; w = h * ar; }
    stage.style.width = Math.max(80, w) + "px"; stage.style.height = Math.max(80, h) + "px";
  }
  function cssFilterFor(fx) {
    const f = (fx && fx.filters) || {}; const parts = [];
    if (f.brightness) parts.push(`brightness(${1 + f.brightness / 100})`);
    if (f.exposure) parts.push(`brightness(${1 + f.exposure / 120})`);
    if (f.contrast) parts.push(`contrast(${1 + f.contrast / 100})`);
    if (f.saturation) parts.push(`saturate(${1 + f.saturation / 100})`);
    if (f.hue) parts.push(`hue-rotate(${f.hue * 1.8}deg)`);
    if (f.temperature) parts.push(`sepia(${clamp(Math.abs(f.temperature) / 100, 0, .6)}) hue-rotate(${f.temperature > 0 ? -10 : 10}deg)`);
    if (f.blacks) parts.push(`brightness(${1 - f.blacks / 300})`);
    if (fx && fx.effects) fx.effects.forEach((ef) => { if (!ef.enabled) return;
      if (ef.type === "blur") parts.push(`blur(${ef.intensity * 6}px)`);
      if (ef.type === "glow") parts.push(`brightness(${1 + ef.intensity * .3}) saturate(${1 + ef.intensity})`);
      if (ef.type === "sharpen") parts.push(`contrast(${1 + ef.intensity * .4})`); });
    if (fx && fx.filters && fx.filters.preset && fx.presetCss) parts.push(fx.presetCss);
    return parts.join(" ");
  }
  function renderPreview() {
    const stage = document.getElementById("edStage"); if (!stage) return;
    const seg = segAt(St.playhead);
    // vídeo/preto ativo
    videoPool.forEach((v) => { v.style.display = "none"; });
    let black = stage.querySelector(".ved-black"); if (!black) { black = document.createElement("div"); black.className = "ved-black"; black.style.display = "none"; stage.appendChild(black); }
    black.style.display = "none";
    if (seg && seg.kind === "clip") {
      const v = videoFor(seg.clip.file);
      if (v && !v.dataset.err) {
        v.style.display = "block";
        if (!St.isPlaying) { try { v.currentTime = num(seg.clip.in) + (St.playhead - seg.start) * num(seg.clip.speed, 1); } catch (e) {} }
        const fx = ed().clip_fx[seg.clip.id]; v.style.filter = fx ? cssFilterFor(fx) : "";
        const t = fx && fx.transform; v.style.transform = t ? `translate(${(t.x - .5) * 100}%,${(t.y - .5) * 100}%) scale(${(t.scaleX || 1) * (t.flipX ? -1 : 1)},${(t.scaleY || 1) * (t.flipY ? -1 : 1)}) rotate(${t.rotation || 0}deg)` : "";
        v.style.opacity = t ? (t.opacity != null ? t.opacity : 1) : 1;
      } else { black.style.display = "block"; }
    } else { black.style.display = "block"; }
    // camadas: overlays de imagem/vídeo + textos/legendas
    renderLayers(stage);
    // controles de tempo
    const tc = document.getElementById("pcTime"); if (tc) tc.textContent = `${fmtTC(St.playhead)} / ${fmtTC(duration())}`;
  }
  function renderLayers(stage) {
    stage.querySelectorAll(".ved-layer,.ved-bbox,.ved-guide").forEach((n) => n.remove());
    const e = ed(), t = St.playhead;
    (e.tracks || []).forEach((tr) => {
      if (tr.visible === false) return;
      if (!["text", "caption", "overlay"].includes(tr.type)) return;
      (tr.items || []).forEach((it) => {
        if (t < num(it.start) - 1e-3 || t > num(it.end) + 1e-3) return;
        const el = document.createElement("div"); el.className = "ved-layer " + tr.type; el.dataset.uid = it.id;
        const tf = it.transform || { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 };
        el.style.left = (tf.x * 100) + "%"; el.style.top = (tf.y * 100) + "%";
        el.style.transform = `translate(-50%,-50%) scale(${tf.scaleX || 1},${tf.scaleY || 1}) rotate(${tf.rotation || 0}deg)`;
        el.style.opacity = tf.opacity != null ? tf.opacity : 1;
        if (tr.type === "overlay") {
          if (it.src && /\.(png|jpe?g|webp|gif)$/i.test(it.src)) { const img = document.createElement("img"); img.src = ctx.files(it.src); img.style.position = "static"; img.style.width = "auto"; img.style.maxWidth = "60vw"; el.appendChild(img); }
          else { el.textContent = "▦ overlay"; el.style.color = "#fff"; el.style.background = "rgba(0,0,0,.3)"; }
        } else {
          const st = it.style || {}; const sz = (st.size || 48) / 1080; // relativo à altura do canvas
          el.textContent = st.uppercase ? (it.text || "").toUpperCase() : (it.text || "");
          el.style.fontFamily = `"${st.font || "Bricolage Grotesque"}",sans-serif`;
          el.style.fontSize = (sz * stage.clientHeight) + "px"; el.style.fontWeight = st.weight || 700;
          el.style.color = st.color || "#fff"; el.style.textAlign = st.align || "center"; el.style.lineHeight = st.lineHeight || 1.2;
          el.style.letterSpacing = (st.letterSpacing || 0) + "px";
          if (st.bg && st.bg !== "transparent") { el.style.background = st.bg; el.style.borderRadius = "4px"; }
          if (st.shadow) el.style.textShadow = "0 2px 12px rgba(0,0,0,.6)";
          if (st.border) el.style.webkitTextStroke = `${st.border}px ${st.borderColor || "#000"}`;
        }
        stage.appendChild(el);
        if (isSel(it.id)) drawBBox(stage, el);
      });
    });
  }
  function drawBBox(stage, el) {
    const bb = document.createElement("div"); bb.className = "ved-bbox";
    const r = el.getBoundingClientRect(), sr = stage.getBoundingClientRect();
    bb.style.left = (r.left - sr.left) + "px"; bb.style.top = (r.top - sr.top) + "px";
    bb.style.width = r.width + "px"; bb.style.height = r.height + "px";
    ["nw", "ne", "sw", "se"].forEach((c) => { const h = document.createElement("div"); h.className = "h " + c; h.dataset.h = c; bb.appendChild(h); });
    const rot = document.createElement("div"); rot.className = "h rot"; rot.dataset.h = "rot"; bb.appendChild(rot);
    stage.appendChild(bb);
  }
  function paintPlayhead() {
    const ph = document.getElementById("edPlayhead"); if (ph) ph.style.left = (St.playhead * St.zoom) + "px";
    const tc = document.getElementById("pcTime"); if (tc) tc.textContent = `${fmtTC(St.playhead)} / ${fmtTC(duration())}`;
  }
  function setPlayIcon() { const b = document.getElementById("pcPlay"); if (b) b.textContent = St.isPlaying ? "⏸" : "▶"; }

  // ---------------------------------------------------------------- persistence
  function setStatus(s) { St.saveStatus = s; const el = document.getElementById("edSave"); if (el) { el.dataset.s = s; el.textContent = { saved: "Salvo", saving: "Salvando…", dirty: "Alterações não salvas", error: "Erro ao salvar" }[s]; } }
  function scheduleSave() { if (saveTimer) clearTimeout(saveTimer); saveTimer = setTimeout(() => save(true), 900); }
  async function save(silent) {
    if (!St.timeline || !ctx.pid()) return;
    setStatus("saving");
    try {
      const r = await api(`${base()}/timeline`, { method: "PUT", body: JSON.stringify(serialize()) });
      // preserva o editor local (o backend faz round-trip; adotamos a versão normalizada dele)
      St.timeline = r.timeline; setStatus("saved"); if (!silent) toast(`Salvo · ${r.duration}s`); ctx.guide();
    } catch (err) { setStatus("error"); if (!silent) toast(err.message); }
  }
  function serialize() {
    const tl = St.timeline;
    return { clips: (tl.clips || []).map((c) => ({ id: c.id, scene: c.scene, shot: c.shot, take: c.take, file: c.file, in: num(c.in), out: num(c.out), speed: num(c.speed, 1), blend: c.blend !== false, zoom: num(c.zoom, 1) })),
      blacks: tl.blacks || [], music: tl.music || { file: null, offset: 0 }, sfx: tl.sfx || [], fade_out: num(tl.fade_out, 1.5), loudnorm: tl.loudnorm !== false, editor: ed() };
  }

  async function load() {
    if (!ctx.pid()) { St.timeline = null; renderAll(); return; }
    try { const r = await api(`${base()}/timeline`); St.timeline = r.timeline; }
    catch (err) { St.timeline = null; renderRoot(); toast(err.message); return; }
    if (!St.timeline.editor) ed();  // semeia em memória (persiste no 1º autosave)
    St.zoom = clamp(num(ed().ui.zoom, 40), 4, 300); St.snap = ed().ui.snap !== false;
    try { St.beats = await api(`/api/projects/${ctx.pid()}/music/beats`); } catch (e) { St.beats = null; }
    St.history = []; St.future = []; St.selection = []; St.playhead = 0;
    renderAll(); seekTo(0);
  }

  // (o restante — Header, Panels, Props, Timeline, Interações, Shortcuts, ContextMenu, Export —
  //  está definido abaixo em render* e bind*; renderAll orquestra tudo.)
  function renderAll() { renderRoot(); }

  // ============================================================ RENDER: ROOT
  function renderRoot() {
    const r = root(); if (!r) return;
    if (!ctx.pid()) { r.innerHTML = `<div class="ved-empty"><h3>Selecione uma campanha</h3><p>Abra um projeto para montar o vídeo.</p></div>`; return; }
    if (!St.timeline) { r.innerHTML = `<div class="ved-empty"><h3>Sem timeline</h3><p>A etapa 5 precisa de takes com like e a etapa 4 de um storyboard.</p></div>`; return; }
    if (!(St.timeline.clips || []).length && !ed().tracks.length) {
      r.innerHTML = `<div class="ved-empty"><h3>Timeline vazia</h3><p>Nenhum clipe na montagem.</p><button class="ghost" id="edReset">Recriar a partir dos takes com like</button></div>`;
      const b = document.getElementById("edReset"); if (b) b.onclick = resetTimeline; return;
    }
    r.innerHTML = headerHTML() + bodyHTML() + timelineHTML();
    bindHeader(); bindLeft(); bindPreview(); bindTimeline(); bindPointer();
    fit(); stageBox(); renderPanel(); renderProps(); renderTimeline(); renderPreview(); paintPlayhead();
    setStatus(St.saveStatus); setPlayIcon();
    document.getElementById("ffState").textContent = St.hasFfmpeg ? "ffmpeg ok" : "ffmpeg ausente";
    document.getElementById("ffState").className = "chip " + (St.hasFfmpeg ? "ok" : "warn");
  }

  // ============================================================ HEADER
  function headerHTML() {
    const p = proj();
    const opt = (arr, sel, fn) => arr.map((a) => { const [v, l] = fn(a); return `<option value="${v}"${v == sel ? " selected" : ""}>${l}</option>`; }).join("");
    return `<div class="ved-top">
      <div class="ved-top-l"><span class="ved-title">${esc(ctx.project() ? ctx.project().name || "Montagem" : "Montagem")}</span>
        <span class="ved-save" id="edSave" data-s="saved">Salvo</span></div>
      <div class="ved-top-c">
        <button class="ved-ib" id="edUndo" title="Desfazer (Ctrl+Z)">↶</button>
        <button class="ved-ib" id="edRedo" title="Refazer (Ctrl+Shift+Z)">↷</button>
        <span class="ved-sep"></span>
        <label class="ved-chip">Proporção <select id="edAspect">${opt(Object.keys(ASPECTS), p.aspect, (a) => [a, a])}</select></label>
        <label class="ved-chip">Resolução <select id="edRes">${opt(RES, p.width, (a) => [a[1], a[0]])}</select></label>
        <label class="ved-chip">FPS <select id="edFps">${opt(FPS_CHOICES, p.fps, (a) => [a, a])}</select></label>
        <button class="ved-ib${St.snap ? " on" : ""}" id="edSnap" title="Snapping">⌁</button>
        <span id="ffState" class="chip mode">ffmpeg: ?</span>
      </div>
      <div class="ved-top-r">
        <button class="ved-ib" id="edGuide" title="Guia da aula 014">?</button>
        <button class="ved-ib" id="edFull" title="Tela cheia">⛶</button>
        <button class="ghost" id="edSaveBtn">Salvar</button>
        <button class="primary" id="edExport">Exportar</button>
      </div></div>`;
  }
  function bindHeader() {
    document.getElementById("edUndo").onclick = undo;
    document.getElementById("edRedo").onclick = redo;
    document.getElementById("edSaveBtn").onclick = () => save(false);
    document.getElementById("edExport").onclick = openExport;
    document.getElementById("edFull").onclick = toggleFullscreen;
    document.getElementById("edGuide").onclick = openGuide;
    document.getElementById("edSnap").onclick = () => { St.snap = !St.snap; ed().ui.snap = St.snap; document.getElementById("edSnap").classList.toggle("on", St.snap); scheduleSave(); };
    document.getElementById("edAspect").onchange = (e) => commit("proporção", () => { proj().aspect = e.target.value; });
    document.getElementById("edAspect").addEventListener("change", () => stageBox());
    document.getElementById("edRes").onchange = (e) => commit("resolução", () => { const r = RES.find((x) => x[1] == e.target.value); if (r) { proj().width = r[1]; proj().height = r[2]; } });
    document.getElementById("edFps").onchange = (e) => commit("fps", () => { proj().fps = num(e.target.value, 30); });
  }
  function toggleFullscreen() { const r = root(); if (!document.fullscreenElement) r.requestFullscreen && r.requestFullscreen(); else document.exitFullscreen && document.exitFullscreen(); }
  /** Abre o guia da aula 014 (hook puro guide.py) num modal — fidelidade ao curso acessível no editor. */
  function openGuide() {
    const m = ui.modal({ title: "Montagem no ritmo — aula 014", subtitle: "O que a aula ensina", html: `<div id="edGuideBody" class="guide">Carregando…</div>` });
    const body = document.getElementById("edGuideBody");
    try { if (ui.renderGuide) { ui.renderGuide("edit", body); return; } } catch (e) { /* fallback abaixo */ }
    ctx.guide(); const g = document.getElementById("guide"); if (g && body) body.innerHTML = g.innerHTML || "Veja o guia na etapa.";
  }

  // ============================================================ BODY
  function bodyHTML() {
    return `<div class="ved-body">
      <div class="ved-left" id="edLeft">
        <nav class="ved-rail" id="edRail">${PANELS.map(([id, ic, lb]) => `<button data-panel="${id}"${id == St.panel ? " class=on" : ""}><span class="ic">${ic}</span>${lb}</button>`).join("")}</nav>
        <div class="ved-panel" id="edPanel"></div>
      </div>
      <div class="ved-resize" data-resize="left"></div>
      <div class="ved-center">
        <div class="ved-stage-wrap" id="edStageWrap"><div class="ved-stage" id="edStage"></div></div>
        <div class="ved-pctl" id="edPctl">
          <button class="ved-ib" id="pcStart" title="Início">⏮</button>
          <button class="ved-ib" id="pcPrev" title="Frame anterior (←)">◁</button>
          <button class="ved-ib" id="pcPlay" title="Play/Pause (Espaço)">▶</button>
          <button class="ved-ib" id="pcNext" title="Próximo frame (→)">▷</button>
          <button class="ved-ib" id="pcEnd" title="Fim">⏭</button>
          <span class="tc" id="pcTime">00:00.00 / 00:00.00</span>
          <span class="ved-sep"></span>
          <button class="ved-ib" id="pcMute" title="Mudo">🔊</button>
          <input type="range" id="pcVol" min="0" max="1" step="0.05" value="${St.volume}">
          <button class="ved-ib${St.loop ? " on" : ""}" id="pcLoop" title="Loop">↻</button>
        </div>
      </div>
      <div class="ved-resize" data-resize="right"></div>
      <div class="ved-right" id="edRight"><div class="ved-props" id="edProps"></div></div>
    </div>`;
  }
  function bindPreview() {
    document.getElementById("pcPlay").onclick = togglePlay;
    document.getElementById("pcStart").onclick = () => seekTo(0);
    document.getElementById("pcEnd").onclick = () => seekTo(duration());
    document.getElementById("pcPrev").onclick = () => step(-1);
    document.getElementById("pcNext").onclick = () => step(1);
    document.getElementById("pcLoop").onclick = () => { St.loop = !St.loop; document.getElementById("pcLoop").classList.toggle("on", St.loop); };
    document.getElementById("pcMute").onclick = () => { St.muted = !St.muted; document.getElementById("pcMute").textContent = St.muted ? "🔈" : "🔊"; syncMusic(); };
    document.getElementById("pcVol").oninput = (e) => { St.volume = num(e.target.value, 1); syncMusic(); };
    // clique numa camada de texto/overlay seleciona; clique no vazio limpa
    document.getElementById("edStage").addEventListener("pointerdown", (e) => {
      const layer = e.target.closest(".ved-layer"); const handle = e.target.closest(".h");
      if (handle) return startBBox(e, handle.dataset.h);
      if (layer) { selectOnly(layer.dataset.uid, e); startLayerDrag(e, layer.dataset.uid); }
      else if (!e.target.closest(".ved-bbox")) { St.selection = []; renderProps(); renderPreview(); renderTimeline(); }
    });
  }
  function bindLeft() {
    document.getElementById("edRail").addEventListener("click", (e) => { const b = e.target.closest("button[data-panel]"); if (!b) return; St.panel = b.dataset.panel; document.querySelectorAll("#edRail button").forEach((x) => x.classList.toggle("on", x.dataset.panel == St.panel)); renderPanel(); });
  }

  // ============================================================ PANELS (esquerda)
  function renderPanel() {
    const el = document.getElementById("edPanel"); if (!el) return;
    ({ media: panelMedia, text: panelText, caption: panelCaption, audio: panelAudio, transitions: panelTransitions,
       effects: panelEffects, filters: panelFilters, elements: panelElements, adjust: panelAdjust }[St.panel] || panelMedia)(el);
  }
  function panelMedia(el) {
    el.innerHTML = `<h4>Mídia</h4><p class="hint">Cenas e takes do projeto. Arraste para a timeline ou clique para adicionar.</p>
      <input class="ved-search" id="mSearch" placeholder="Buscar…">
      <label class="drop sm" id="mDrop" style="margin:6px 0">Arraste imagens/vídeos aqui<input id="mUp" type="file" accept="video/*,image/*" multiple hidden></label>
      <div class="ved-media" id="mList"></div>`;
    const list = document.getElementById("mList");
    const clips = (St.timeline.clips || []);
    list.innerHTML = clips.map((c) => `<div class="ved-mtile" draggable="true" data-file="${esc(c.file)}" data-cid="${c.id}" title="${esc(nameOf(c))}">
      <div class="mt-th">${/\.(mp4|webm|mov)$/i.test(c.file || "") ? `<video preload="metadata" muted src="${ctx.files(c.file)}#t=0.1"></video>` : `<img src="${ctx.files(c.file)}">`}</div>
      <div class="mt-meta"><span class="mt-name">${esc(nameOf(c))}</span></div></div>`).join("") || `<p class="hint">Sem mídia na timeline.</p>`;
    const search = document.getElementById("mSearch");
    search.oninput = () => { const q = search.value.toLowerCase(); list.querySelectorAll(".ved-mtile").forEach((t) => { t.style.display = t.dataset.file.toLowerCase().includes(q) ? "" : "none"; }); };
    ui.drop(document.getElementById("mDrop"), async (files) => { toast("Upload de mídia entra numa próxima fase; use os takes das etapas anteriores."); });
    list.querySelectorAll(".ved-mtile").forEach((t) => t.addEventListener("dragstart", (e) => { e.dataTransfer.setData("text/plain", "clip:" + t.dataset.cid); }));
  }
  function panelText(el) {
    el.innerHTML = `<h4>Texto</h4><p class="hint">Clique para inserir no playhead.</p><div class="ved-grid">${TEXT_PRESETS.map(([id, lb, st]) => `<button class="ved-pick" data-t="${id}"><span class="sw" style="font-weight:${st.weight};font-size:${Math.min(st.size / 4, 22)}px">Aa</span>${lb}</button>`).join("")}</div>`;
    el.querySelectorAll("[data-t]").forEach((b) => b.onclick = () => { const p = TEXT_PRESETS.find((x) => x[0] == b.dataset.t); addText(p[1], p[2]); });
  }
  function panelCaption(el) {
    el.innerHTML = `<h4>Legendas</h4><p class="hint">Adicione legendas manuais. Geração automática precisa de transcrição (pendente no projeto).</p>
      <button class="ghost" id="capAdd">+ Legenda no playhead</button>
      <div id="capList" style="margin-top:10px"></div>`;
    document.getElementById("capAdd").onclick = () => addText("Legenda", { size: 40, weight: 600 }, "caption");
    const t = capTrack(false); const items = t ? t.items : [];
    document.getElementById("capList").innerHTML = items.map((it) => `<div class="ved-field"><input type="text" value="${esc(it.text)}" data-cap="${it.id}" style="width:100%"><button class="ved-ib" data-capdel="${it.id}">✕</button></div>`).join("") || `<p class="hint">Nenhuma legenda.</p>`;
    el.querySelectorAll("[data-cap]").forEach((i) => i.onchange = () => editItem(i.dataset.cap, (it) => it.text = i.value));
    el.querySelectorAll("[data-capdel]").forEach((b) => b.onclick = () => deleteItems([b.dataset.capdel]));
  }
  function panelAudio(el) {
    el.innerHTML = `<h4>Áudio</h4><p class="hint">Trilha da etapa 6, SFX e faixas extra.</p>
      <div class="ved-field"><label>Música</label><span class="mt-name" style="font-size:11px">${esc((St.timeline.music || {}).file || "—")}</span></div>
      <div class="ved-slider"><label>Volume música</label><input type="range" min="0" max="1.5" step="0.05" id="aMusVol" value="${num((St.timeline.music || {}).volume, 1)}"><span class="val" id="aMusVolV"></span></div>
      <div class="ved-field"><label>Offset (s)</label><input type="number" step="0.1" min="0" id="aMusOff" value="${num((St.timeline.music || {}).offset)}"></div>
      <label class="drop sm" id="sfxDrop" style="margin:10px 0">Arraste SFX aqui<input id="sfxUp" type="file" accept="audio/*" multiple hidden></label>
      <div id="sfxList"></div>`;
    const vv = document.getElementById("aMusVolV"); const vol = document.getElementById("aMusVol"); vv.textContent = num(vol.value, 1).toFixed(2);
    vol.oninput = () => { vv.textContent = num(vol.value).toFixed(2); St.timeline.music = { ...(St.timeline.music || {}), volume: num(vol.value, 1) }; };
    vol.onchange = () => commit("volume música", () => { St.timeline.music = { ...(St.timeline.music || {}), volume: num(vol.value, 1) }; });
    document.getElementById("aMusOff").onchange = (e) => commit("offset música", () => { St.timeline.music = { ...(St.timeline.music || {}), offset: Math.max(num(e.target.value), 0) }; });
    ui.drop(document.getElementById("sfxDrop"), uploadSfx);
    document.getElementById("sfxList").innerHTML = (St.timeline.sfx || []).map((s, i) => `<div class="ved-field"><span class="mt-name" style="font-size:11px;flex:1">${esc(s.file.split("/").pop())}</span><input type="number" step="0.1" value="${num(s.at)}" data-sfxat="${i}" title="posição (s)"><button class="ved-ib" data-sfxdel="${i}">✕</button></div>`).join("") || `<p class="hint">Sem SFX.</p>`;
    el.querySelectorAll("[data-sfxat]").forEach((i) => i.onchange = () => commit("mover SFX", () => { St.timeline.sfx[+i.dataset.sfxat].at = Math.max(num(i.value), 0); }));
    el.querySelectorAll("[data-sfxdel]").forEach((b) => b.onclick = () => commit("remover SFX", () => { St.timeline.sfx.splice(+b.dataset.sfxdel, 1); }));
  }
  function panelTransitions(el) {
    const sel = St.selection[0]; const canApply = St.selection.length >= 1;
    el.innerHTML = `<h4>Transições</h4><p class="hint">Selecione um clipe de vídeo e escolha a transição para o próximo. <b>[extensão]</b> — aparece no preview; no master.mp4: fase seguinte.</p>
      <div class="ved-grid g3">${TRANSITIONS.map(([id, lb]) => `<button class="ved-pick" data-tr="${id}"><span class="sw">⇄</span>${lb}</button>`).join("")}</div>`;
    el.querySelectorAll("[data-tr]").forEach((b) => b.onclick = () => applyTransition(b.dataset.tr));
    if (!canApply) el.querySelectorAll("[data-tr]").forEach((b) => b.disabled = true);
  }
  function panelEffects(el) {
    el.innerHTML = `<h4>Efeitos</h4><p class="hint">Selecione um clipe. <b>[extensão]</b> preview no browser; no master.mp4: fase seguinte.</p>
      <div class="ved-grid g3">${EFFECTS.map(([id, lb]) => `<button class="ved-pick" data-ef="${id}"><span class="sw">✦</span>${lb}</button>`).join("")}</div>`;
    el.querySelectorAll("[data-ef]").forEach((b) => b.onclick = () => toggleEffect(b.dataset.ef));
    markActiveFx(el);
  }
  function panelFilters(el) {
    el.innerHTML = `<h4>Filtros</h4><p class="hint">Presets para o clipe selecionado.</p>
      <div class="ved-grid">${FILTER_PRESETS.map(([id, lb, css]) => `<button class="ved-pick" data-fl="${id}" data-css="${css}"><span class="sw" style="filter:${css || "none"};background:linear-gradient(45deg,#5661c8,#c85f8a)"></span>${lb}</button>`).join("")}</div>`;
    el.querySelectorAll("[data-fl]").forEach((b) => b.onclick = () => setFilterPreset(b.dataset.fl, b.dataset.css));
  }
  function panelElements(el) {
    el.innerHTML = `<h4>Elementos</h4><p class="hint">Formas e barras como overlay no playhead.</p>
      <div class="ved-grid g3">${[["rect", "▭"], ["circle", "●"], ["bar", "▬"], ["arrow", "➤"], ["star", "★"], ["dot", "•"]].map(([id, ic]) => `<button class="ved-pick" data-elx="${id}"><span class="sw">${ic}</span></button>`).join("")}</div>`;
    el.querySelectorAll("[data-elx]").forEach((b) => b.onclick = () => addText(b.textContent.trim(), { size: 120, weight: 400 }, "overlay-shape"));
  }
  function panelAdjust(el) {
    const fx = adjustTarget();
    el.innerHTML = `<h4>Ajustes</h4>` + (fx ? ADJUSTS.map(([k, lb]) => sliderHTML("adj-" + k, lb, num((fx.filters || {})[k]), -100, 100)).join("") + `<button class="ghost sm" id="adjReset" style="margin-top:8px">Resetar ajustes</button>` : `<p class="hint">Selecione um clipe ou overlay.</p>`);
    if (!fx) return;
    ADJUSTS.forEach(([k]) => bindSlider("adj-" + k, (v) => { fx.filters = fx.filters || {}; if (v) fx.filters[k] = v; else delete fx.filters[k]; }, "ajuste " + k, () => renderPreview()));
    document.getElementById("adjReset").onclick = () => commit("resetar ajustes", () => { fx.filters = {}; });
  }
  function markActiveFx(el) { const fx = adjustTarget(); const on = new Set((fx && fx.effects || []).filter((e) => e.enabled).map((e) => e.type)); el.querySelectorAll("[data-ef]").forEach((b) => b.classList.toggle("on", on.has(b.dataset.ef))); }

  function sliderHTML(id, lb, val, min, max) { return `<div class="ved-slider"><label>${lb}</label><input type="range" id="${id}" min="${min}" max="${max}" step="1" value="${val || 0}"><span class="val" id="${id}v">${val || 0}</span></div>`; }
  function bindSlider(id, apply, label, live) {
    const inp = document.getElementById(id), out = document.getElementById(id + "v"); if (!inp) return;
    inp.oninput = () => { out.textContent = inp.value; apply(num(inp.value)); if (live) live(); };
    inp.onchange = () => { St.history.push(clone(St.timeline)); St.future = []; St.hLabel = label; setStatus("dirty"); scheduleSave(); };
  }

  // ============================================================ PROPERTIES (direita)
  function renderProps() {
    const el = document.getElementById("edProps"); if (!el) return;
    const sel = St.selection;
    if (!sel.length) return propsProject(el);
    const it = findItem(sel[0]); if (!it) return propsProject(el);
    if (it.kind === "video") return propsClip(el, it);
    if (it.kind === "text" || it.kind === "caption") return propsText(el, it);
    if (["music", "audio", "sfx"].includes(it.kind)) return propsAudio(el, it);
    if (it.kind === "overlay") return propsClip(el, it);
    propsProject(el);
  }
  function propsProject(el) {
    const p = proj();
    el.innerHTML = `<h4>Projeto</h4>
      <div class="ved-field"><label>Proporção</label><span>${p.aspect}</span></div>
      <div class="ved-field"><label>Resolução</label><span>${p.width}×${p.height}</span></div>
      <div class="ved-field"><label>FPS</label><span>${p.fps}</span></div>
      <div class="ved-field"><label>Duração</label><span>${fmtTC(duration())}</span></div>
      <div class="ved-slider"><label>Fade final</label><input type="range" id="pFade" min="0" max="5" step="0.1" value="${num(St.timeline.fade_out, 1.5)}"><span class="val" id="pFadev">${num(St.timeline.fade_out, 1.5)}</span></div>
      <div class="ved-field"><label>Normalizar áudio [ext]</label><input type="checkbox" id="pLoud" ${St.timeline.loudnorm !== false ? "checked" : ""}></div>`;
    bindSlider("pFade", (v) => St.timeline.fade_out = v, "fade final", null);
    document.getElementById("pLoud").onchange = (e) => commit("loudnorm", () => St.timeline.loudnorm = e.target.checked);
  }
  function propsClip(el, it) {
    const isV = it.kind === "video"; const c = it.clip; const fx = isV ? clipFx(c.id) : (it.item.transform ? it.item : (it.item.transform = { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 }, it.item));
    const tf = isV ? fx.transform : it.item.transform;
    el.innerHTML = `<h4>${isV ? esc(nameOf(c)) : "Overlay"}</h4>
      <div class="ved-tabs">${["basic", "video", "audio", "speed", "adjust"].map((t) => `<button data-tab="${t}"${t == St.propsTab ? " class=on" : ""}>${{ basic: "Básico", video: "Vídeo", audio: "Áudio", speed: "Velocidade", adjust: "Ajustes" }[t]}</button>`).join("")}</div>
      <div id="tabBody"></div>`;
    el.querySelectorAll("[data-tab]").forEach((b) => b.onclick = () => { St.propsTab = b.dataset.tab; renderProps(); });
    const body = document.getElementById("tabBody");
    if (St.propsTab === "basic") {
      body.innerHTML = numField("bX", "Pos X", tf.x, .001) + numField("bY", "Pos Y", tf.y, .001) + numField("bSX", "Escala X", tf.scaleX, .01) + numField("bSY", "Escala Y", tf.scaleY, .01)
        + numField("bRot", "Rotação", tf.rotation, 1) + numField("bOp", "Opacidade", tf.opacity, .05)
        + `<div class="ved-field"><label>Flip</label><span><button class="ved-ib" id="bfx">↔</button><button class="ved-ib" id="bfy">↕</button></span></div>`;
      bindNum("bX", (v) => tf.x = v, "posição"); bindNum("bY", (v) => tf.y = v, "posição");
      bindNum("bSX", (v) => tf.scaleX = v, "escala"); bindNum("bSY", (v) => tf.scaleY = v, "escala");
      bindNum("bRot", (v) => tf.rotation = v, "rotação"); bindNum("bOp", (v) => tf.opacity = clamp(v, 0, 1), "opacidade");
      document.getElementById("bfx").onclick = () => commit("flip", () => tf.flipX = !tf.flipX);
      document.getElementById("bfy").onclick = () => commit("flip", () => tf.flipY = !tf.flipY);
    } else if (St.propsTab === "video" && isV) {
      body.innerHTML = numField("vIn", "In (s)", c.in, .05) + numField("vOut", "Out (s)", c.out, .05) + numField("vZoom", "Zoom", c.zoom, .01)
        + `<div class="ved-field"><label>Frame blend</label><input type="checkbox" id="vBlend" ${c.blend !== false ? "checked" : ""}></div>`
        + `<p class="hint">Trim é não destrutivo: só muda a janela sobre o arquivo original.</p>`;
      bindNum("vIn", (v) => c.in = clamp(v, 0, num(c.out) - .05), "trim"); bindNum("vOut", (v) => c.out = Math.max(v, num(c.in) + .05), "trim");
      bindNum("vZoom", (v) => c.zoom = clamp(v, 1, 1.3), "zoom");
      document.getElementById("vBlend").onchange = (e) => commit("blend", () => c.blend = e.target.checked);
    } else if (St.propsTab === "speed" && isV) {
      body.innerHTML = `<div class="ved-grid g3" style="margin-bottom:8px">${SPEEDS.map((s) => `<button class="ved-pick${num(c.speed, 1) == s ? " on" : ""}" data-sp="${s}">${s}×</button>`).join("")}</div>` + numField("vSpeed", "Custom", c.speed, .05);
      body.querySelectorAll("[data-sp]").forEach((b) => b.onclick = () => commit("velocidade", () => c.speed = num(b.dataset.sp, 1)));
      bindNum("vSpeed", (v) => c.speed = clamp(v, 0.25, 4), "velocidade");
    } else if (St.propsTab === "audio") {
      body.innerHTML = `<p class="hint">O áudio do modelo entra desligado (aula 014). A trilha vem da etapa 6; ajuste no painel Áudio.</p>`;
    } else if (St.propsTab === "adjust") {
      const t = isV ? fx : (it.item.filters ? it.item : (it.item.filters = {}, it.item));
      body.innerHTML = ADJUSTS.map(([k, lb]) => sliderHTML("cadj-" + k, lb, num((t.filters || {})[k]), -100, 100)).join("") + `<button class="ghost sm" id="cReset" style="margin-top:8px">Resetar</button>`;
      ADJUSTS.forEach(([k]) => bindSlider("cadj-" + k, (v) => { t.filters = t.filters || {}; if (v) t.filters[k] = v; else delete t.filters[k]; }, "ajuste", renderPreview));
      document.getElementById("cReset").onclick = () => commit("resetar", () => t.filters = {});
    } else { body.innerHTML = `<p class="hint">Sem controles nesta aba para este item.</p>`; }
  }
  function propsText(el, it) {
    const t = it.item, st = t.style = t.style || {}; const tf = t.transform = t.transform || { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 };
    el.innerHTML = `<h4>Texto</h4>
      <div class="ved-field"><label>Conteúdo</label></div><textarea id="txT" class="ved-search" rows="2">${esc(t.text || "")}</textarea>
      ${numField("txSize", "Tamanho", st.size || 48, 1)}${numField("txWeight", "Peso", st.weight || 700, 100)}
      <div class="ved-field"><label>Alinhar</label><select id="txAlign">${["left", "center", "right"].map((a) => `<option${a == (st.align || "center") ? " selected" : ""}>${a}</option>`).join("")}</select></div>
      <div class="ved-field"><label>Cor</label><input type="color" id="txColor" value="${st.color || "#ffffff"}"></div>
      <div class="ved-field"><label>Fundo</label><input type="text" id="txBg" value="${esc(st.bg || "transparent")}"></div>
      <div class="ved-field"><label>Sombra</label><input type="checkbox" id="txShadow" ${st.shadow !== false ? "checked" : ""}></div>
      <div class="ved-field"><label>Maiúsculas</label><input type="checkbox" id="txUpper" ${st.uppercase ? "checked" : ""}></div>
      ${numField("txOp", "Opacidade", tf.opacity, .05)}${numField("txRot", "Rotação", tf.rotation, 1)}
      ${numField("txStart", "Início (s)", t.start, .1)}${numField("txEnd", "Fim (s)", t.end, .1)}`;
    const upd = (label, fn) => { St.history.push(clone(St.timeline)); St.future = []; St.hLabel = label; fn(); setStatus("dirty"); scheduleSave(); renderPreview(); renderTimeline(); };
    document.getElementById("txT").oninput = (e) => { t.text = e.target.value; renderPreview(); scheduleSave(); };
    document.getElementById("txAlign").onchange = (e) => upd("alinhar", () => st.align = e.target.value);
    document.getElementById("txColor").oninput = (e) => { st.color = e.target.value; renderPreview(); scheduleSave(); };
    document.getElementById("txBg").onchange = (e) => upd("fundo", () => st.bg = e.target.value);
    document.getElementById("txShadow").onchange = (e) => upd("sombra", () => st.shadow = e.target.checked);
    document.getElementById("txUpper").onchange = (e) => upd("maiúsculas", () => st.uppercase = e.target.checked);
    bindNum("txSize", (v) => st.size = clamp(v, 4, 400), "tamanho", renderPreview); bindNum("txWeight", (v) => st.weight = clamp(v, 100, 900), "peso", renderPreview);
    bindNum("txOp", (v) => tf.opacity = clamp(v, 0, 1), "opacidade", renderPreview); bindNum("txRot", (v) => tf.rotation = v, "rotação", renderPreview);
    bindNum("txStart", (v) => t.start = Math.max(v, 0), "início", renderTimeline); bindNum("txEnd", (v) => t.end = Math.max(v, num(t.start) + .2), "fim", renderTimeline);
  }
  function propsAudio(el, it) {
    if (it.kind === "music") {
      const m = St.timeline.music || (St.timeline.music = {});
      el.innerHTML = `<h4>Música</h4>${numField("mOff", "Offset (s)", m.offset, .1)}<div class="ved-slider"><label>Volume</label><input type="range" id="mVol" min="0" max="1.5" step="0.05" value="${num(m.volume, 1)}"><span class="val" id="mVolv">${num(m.volume, 1).toFixed(2)}</span></div>`;
      bindNum("mOff", (v) => m.offset = Math.max(v, 0), "offset"); bindSlider("mVol", (v) => m.volume = v, "volume", syncMusic);
    } else if (it.kind === "sfx") {
      const s = it.sfx; el.innerHTML = `<h4>SFX</h4>${numField("sAt", "Em (s)", s.at, .1)}${numField("sGain", "Ganho (dB)", s.gain, 1)}`;
      bindNum("sAt", (v) => s.at = Math.max(v, 0), "posição SFX"); bindNum("sGain", (v) => s.gain = clamp(v, -40, 12), "ganho");
    } else { el.innerHTML = `<h4>Áudio</h4><p class="hint">Faixa de áudio.</p>`; }
  }
  function numField(id, lb, val, step) { return `<div class="ved-field"><label>${lb}</label><input type="number" id="${id}" step="${step}" value="${val != null ? (+val).toFixed(step < 1 ? 2 : 0) : 0}"></div>`; }
  function bindNum(id, apply, label, live) { const inp = document.getElementById(id); if (!inp) return; inp.onchange = () => { St.history.push(clone(St.timeline)); St.future = []; St.hLabel = label; apply(num(inp.value)); setStatus("dirty"); scheduleSave(); (live || renderPreview)(); renderTimeline(); }; }

  // ============================================================ TIMELINE
  function timelineHTML() {
    return `<div class="ved-resize-v" data-resize="timeline"></div>
      <div class="ved-timeline" id="edTimeline">
        <div class="ved-tl-toolbar" id="edTlbar">
          <button class="ved-ib" id="tSplit" title="Dividir (Ctrl+B)">✂</button>
          <button class="ved-ib" id="tDup" title="Duplicar (Ctrl+D)">⧉</button>
          <button class="ved-ib" id="tDel" title="Excluir (Del)">🗑</button>
          <span class="ved-sep"></span>
          <button class="ved-ib" id="tMark" title="Marcador">⚑</button>
          <span class="spacer"></span>
          <div class="ved-zoom"><button class="ved-ib" id="zOut">−</button><input type="range" id="zRange" min="6" max="240" value="${St.zoom}"><button class="ved-ib" id="zIn">+</button></div>
        </div>
        <div class="ved-tl-body">
          <div class="ved-tl-heads" id="edTlHeads"></div>
          <div class="ved-tl-main" id="edTlMain">
            <div class="ved-ruler" id="edRuler"></div>
            <div class="ved-tracks" id="edTracks"></div>
            <div class="ved-playhead" id="edPlayhead"><div class="grip"></div></div>
          </div>
        </div>
      </div>`;
  }
  function bindTimeline() {
    document.getElementById("tSplit").onclick = splitAtPlayhead;
    document.getElementById("tDup").onclick = duplicateSelection;
    document.getElementById("tDel").onclick = () => deleteItems(St.selection);
    document.getElementById("tMark").onclick = addMarker;
    document.getElementById("zIn").onclick = () => setZoom(St.zoom * 1.3);
    document.getElementById("zOut").onclick = () => setZoom(St.zoom / 1.3);
    document.getElementById("zRange").oninput = (e) => setZoom(num(e.target.value, 40));
    const main = document.getElementById("edTlMain");
    main.addEventListener("scroll", () => { document.getElementById("edTlHeads").scrollTop = main.scrollTop; });
    // clique na régua/vazio move o playhead
    main.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".ved-clip") || e.target.closest(".ved-trans")) return;
      const grip = e.target.closest(".grip") || e.target.closest(".ved-ruler");
      const r = main.getBoundingClientRect(); const t = (e.clientX - r.left + main.scrollLeft) / St.zoom;
      if (grip || e.target.closest(".ved-tracks") || e.target.closest(".ved-ruler")) { seekTo(t); if (grip) startPlayheadDrag(e); }
      if (!e.target.closest(".ved-clip")) { St.selection = []; renderProps(); renderTimeline(); }
    });
  }
  function setZoom(z) { St.zoom = clamp(z, 4, 300); ed().ui.zoom = St.zoom; const zr = document.getElementById("zRange"); if (zr) zr.value = St.zoom; renderTimeline(); paintPlayhead(); scheduleSave(); }

  function renderTimeline() {
    const heads = document.getElementById("edTlHeads"), lanes = document.getElementById("edTracks"); if (!heads || !lanes) return;
    const trs = tracks(), dur = duration(), W = Math.max(dur * St.zoom + 200, 400);
    // ruler
    const ruler = document.getElementById("edRuler"); ruler.style.width = W + "px"; ruler.innerHTML = "";
    const stepS = St.zoom > 80 ? 1 : St.zoom > 30 ? 2 : St.zoom > 12 ? 5 : 10;
    for (let s = 0; s <= dur + stepS; s += stepS) { const d = document.createElement("span"); d.className = "tick"; d.style.left = (s * St.zoom) + "px"; d.textContent = s + "s"; ruler.appendChild(d); }
    heads.innerHTML = `<div class="ruler-pad"></div>` + trs.map((t) => `<div class="ved-thead" style="height:${t.height}px" data-tid="${t.id}"><span class="tn" title="${esc(t.name)}">${esc(t.name)}</span>
      <button data-act="vis" class="${t.visible === false ? "" : "act"}" title="visível">${t.visible === false ? "◌" : "◉"}</button>
      <button data-act="mute" class="${t.muted ? "act" : ""}" title="mudo">${t.muted ? "🔇" : "🔉"}</button>
      <button data-act="lock" class="${t.locked ? "act" : ""}" title="travar">${t.locked ? "🔒" : "🔓"}</button></div>`).join("");
    lanes.style.width = W + "px"; lanes.innerHTML = trs.map((t) => laneHTML(t)).join("");
    document.getElementById("edPlayhead").style.height = lanes.offsetHeight + 26 + "px";
    // markers
    (ed().markers || []).forEach((m) => { const mk = document.createElement("div"); mk.className = "ved-marker"; mk.style.left = (num(m.at) * St.zoom) + "px"; mk.innerHTML = `<span class="lb">${esc(m.name || "•")}</span>`; lanes.appendChild(mk); });
    heads.querySelectorAll(".ved-thead").forEach((h) => h.querySelectorAll("button").forEach((b) => b.onclick = () => trackAction(h.dataset.tid, b.dataset.act)));
    paintPlayhead();
  }
  function laneHTML(t) {
    let inner = t.items.map((it) => clipHTML(t, it)).join("");
    if (t.type === "video" && t.blacks) inner += t.blacks.map((b) => `<div class="ved-clip" style="left:${b.start * St.zoom}px;width:${Math.max(b.dur * St.zoom, 3)}px;background:#000;border-color:#333" title="preto ${b.dur}s"></div>`).join("");
    // indicadores de transição entre clipes de vídeo
    if (t.type === "video") (ed().transitions || []).forEach((tr) => { const it = t.items.find((x) => x.uid === tr.from); if (it) inner += `<div class="ved-trans" data-tr="${tr.id}" style="left:${(it.start + it.dur) * St.zoom}px" title="${tr.type}">⇄</div>`; });
    return `<div class="ved-lane" data-tid="${t.id}" style="height:${t.height}px">${inner}</div>`;
  }
  function clipHTML(t, it) {
    const x = it.start * St.zoom, w = Math.max(it.dur * St.zoom, 6);
    const selc = isSel(it.uid) ? " sel" : "";
    let label = "", thumb = "", wave = "";
    if (it.kind === "video") { label = nameOf(it.clip); if (/\.(mp4|webm|mov)$/i.test(it.clip.file || "") && w > 40) thumb = `<div class="cl-th"><video preload="metadata" muted src="${ctx.files(it.clip.file)}#t=0.1"></video></div>`; }
    else if (it.kind === "text" || it.kind === "caption") label = it.item.text || "Texto";
    else if (it.kind === "overlay") label = "overlay";
    else if (it.kind === "music") label = (it.music.file || "música").split("/").pop();
    else if (it.kind === "sfx") label = it.sfx.file.split("/").pop();
    else label = it.item && it.item.file ? it.item.file.split("/").pop() : "áudio";
    if (["music", "audio", "sfx"].includes(it.kind)) wave = `<div class="ved-wave">${waveBars(w)}</div>`;
    const trim = it.kind === "video" || it.kind === "text" || it.kind === "caption" || it.kind === "overlay" ? `<div class="cl-trim l"></div><div class="cl-trim r"></div>` : "";
    return `<div class="ved-clip ${it.kind}${selc}" data-uid="${it.uid}" data-tid="${t.id}" style="left:${x}px;width:${w}px">${trim}<div class="cl-body">${thumb}${wave}<div class="cl-name">${esc(label)}</div></div></div>`;
  }
  function waveBars(w) { const n = Math.min(Math.floor(w / 3), 200); let s = ""; for (let i = 0; i < n; i++) { const h = 20 + Math.abs(Math.sin(i * 1.7) * 60); s += `<i style="left:${i * 3}px;height:${h}%"></i>`; } return s; }

  function trackAction(tid, act) {
    if (["video", "music", "sfx"].includes(tid)) { if (act === "vis" || act === "lock") return toast("Faixa do backbone da aula — sempre visível na montagem."); }
    const t = (ed().tracks || []).find((x) => x.id === tid); if (!t) return;
    commit("faixa " + act, () => { if (act === "vis") t.visible = t.visible === false; else if (act === "mute") t.muted = !t.muted; else if (act === "lock") t.locked = !t.locked; });
  }

  // ============================================================ INTERAÇÕES (pointer)
  let drag = null;
  function bindPointer() {
    const lanes = document.getElementById("edTracks");
    lanes.addEventListener("pointerdown", (e) => {
      const clip = e.target.closest(".ved-clip"); const trans = e.target.closest(".ved-trans"); const trim = e.target.closest(".cl-trim");
      if (trans) { openTransition(trans.dataset.tr); return; }
      if (!clip || !clip.dataset.uid) return;
      selectOnly(clip.dataset.uid, e);
      if (trim) startTrim(e, clip, trim.classList.contains("l") ? "l" : "r");
      else startClipDrag(e, clip);
    });
    lanes.addEventListener("dblclick", (e) => { const clip = e.target.closest(".ved-clip"); if (clip && clip.classList.contains("text")) { selectOnly(clip.dataset.uid, {}); St.panel = "text"; } });
    lanes.addEventListener("contextmenu", (e) => { const clip = e.target.closest(".ved-clip"); if (clip && clip.dataset.uid) { e.preventDefault(); if (!isSel(clip.dataset.uid)) selectOnly(clip.dataset.uid, {}); openMenu(e.clientX, e.clientY, clip.dataset.uid); } });
  }
  function selectOnly(uid, e) {
    if (e && (e.ctrlKey || e.metaKey)) { if (isSel(uid)) St.selection = St.selection.filter((x) => x !== uid); else St.selection.push(uid); }
    else if (!isSel(uid) || St.selection.length > 1) St.selection = [uid];
    renderProps(); renderTimeline(); renderPreview(); if (["text", "caption"].includes((findItem(uid) || {}).kind)) { }
  }

  function startClipDrag(e, clipEl) {
    const uid = clipEl.dataset.uid, it = findItem(uid); if (!it || it.track.backbone && it.kind !== "video" && it.kind !== "sfx") return;
    const startX = e.clientX, x0 = it.start; let moved = false;
    const move = (ev) => {
      const dx = (ev.clientX - startX) / St.zoom; if (Math.abs(dx * St.zoom) > 3) moved = true;
      if (it.kind === "video") { /* reorder por posição, aplicado no up */ clipEl.style.transform = `translateX(${(ev.clientX - startX)}px)`; }
      else { let ns = Math.max(x0 + dx, 0); ns = snapTime(ns, uid); clipEl.style.left = ns * St.zoom + "px"; clipEl.dataset.ns = ns; }
    };
    const up = (ev) => {
      document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up);
      if (!moved) return;
      if (it.kind === "video") { const dropX = (ev.clientX - document.getElementById("edTlMain").getBoundingClientRect().left + document.getElementById("edTlMain").scrollLeft) / St.zoom; reorderClip(uid, dropX); }
      else if (it.kind === "sfx") { const ns = num(clipEl.dataset.ns, x0); commit("mover SFX", () => { St.timeline.sfx[it.i].at = ns; }); }
      else { const ns = num(clipEl.dataset.ns, x0); const dur = it.dur; commit("mover", () => { editItemRaw(uid, (o) => { o.start = ns; o.end = ns + dur; }); }); }
    };
    document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
  }
  function reorderClip(uid, dropX) {
    const clips = St.timeline.clips; const from = clips.findIndex((c) => c.id === uid); if (from < 0) return;
    const segs = segments().filter((s) => s.kind === "clip");
    let to = segs.findIndex((s) => dropX < s.start + s.dur / 2); if (to < 0) to = clips.length - 1; else to = Math.max(0, Math.min(to, clips.length - 1));
    if (to === from) return renderTimeline();
    commit("reordenar clipe", () => { const [c] = clips.splice(from, 1); clips.splice(to, 0, c); });
  }
  function startTrim(e, clipEl, side) {
    const uid = clipEl.dataset.uid, it = findItem(uid); const startX = e.clientX;
    const base = it.kind === "video" ? { in: num(it.clip.in), out: num(it.clip.out) } : { start: num(it.item.start), end: num(it.item.end) };
    const move = (ev) => {
      const dx = (ev.clientX - startX) / St.zoom;
      if (it.kind === "video") { const sp = num(it.clip.speed, 1); if (side === "l") it.clip.in = clamp(base.in + dx * sp, 0, num(it.clip.out) - .05); else it.clip.out = Math.max(base.out + dx * sp, num(it.clip.in) + .05); }
      else { if (side === "l") it.item.start = clamp(base.start + dx, 0, num(it.item.end) - .2); else it.item.end = Math.max(base.end + dx, num(it.item.start) + .2); }
      renderTimeline(); renderPreview();
    };
    const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); commit("trim", () => {}); };
    document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
  }
  function startPlayheadDrag(e) {
    const main = document.getElementById("edTlMain");
    const move = (ev) => { const r = main.getBoundingClientRect(); seekTo((ev.clientX - r.left + main.scrollLeft) / St.zoom); };
    const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); };
    document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
  }
  function snapTime(t, skipUid) {
    if (!St.snap) return t; const px = 8 / St.zoom; const cands = [0, duration(), St.playhead];
    tracks().forEach((tr) => tr.items.forEach((it) => { if (it.uid === skipUid) return; cands.push(it.start, it.start + it.dur); }));
    (ed().markers || []).forEach((m) => cands.push(num(m.at)));
    for (const c of cands) if (Math.abs(c - t) < px) return c;
    return t;
  }
  // arraste de camada no canvas
  function startLayerDrag(e, uid) {
    const it = findItem(uid); if (!it || !["text", "caption", "overlay"].includes(it.kind)) return;
    const stage = document.getElementById("edStage"), sr = stage.getBoundingClientRect();
    const tf = it.item.transform = it.item.transform || { x: .5, y: .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 };
    const x0 = tf.x, y0 = tf.y, sx = e.clientX, sy = e.clientY; let moved = false;
    const move = (ev) => { moved = true; tf.x = clamp(x0 + (ev.clientX - sx) / sr.width, -1, 2); tf.y = clamp(y0 + (ev.clientY - sy) / sr.height, -1, 2); showGuides(tf); renderPreview(); };
    const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); stage.querySelectorAll(".ved-guide").forEach((g) => g.remove()); if (moved) commit("mover camada", () => {}); };
    document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
  }
  function showGuides(tf) {
    const stage = document.getElementById("edStage"); stage.querySelectorAll(".ved-guide").forEach((g) => g.remove());
    if (Math.abs(tf.x - .5) < .02) { tf.x = .5; const g = document.createElement("div"); g.className = "ved-guide v"; g.style.left = "50%"; stage.appendChild(g); }
    if (Math.abs(tf.y - .5) < .02) { tf.y = .5; const g = document.createElement("div"); g.className = "ved-guide h"; g.style.top = "50%"; stage.appendChild(g); }
  }
  function startBBox(e, handle) {
    const uid = St.selection[0], it = findItem(uid); if (!it) return; const tf = it.item.transform;
    const stage = document.getElementById("edStage"), sr = stage.getBoundingClientRect(); const cx = sr.left + tf.x * sr.width, cy = sr.top + tf.y * sr.height;
    const s0 = tf.scaleX || 1, r0 = tf.rotation || 0, d0 = Math.hypot(e.clientX - cx, e.clientY - cy), a0 = Math.atan2(e.clientY - cy, e.clientX - cx);
    const move = (ev) => {
      if (handle === "rot") { tf.rotation = Math.round(r0 + (Math.atan2(ev.clientY - cy, ev.clientX - cx) - a0) * 180 / Math.PI); }
      else { const d = Math.hypot(ev.clientX - cx, ev.clientY - cy); const k = clamp(s0 * d / (d0 || 1), .1, 8); tf.scaleX = tf.scaleY = +k.toFixed(3); }
      renderPreview();
    };
    const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); commit("transform", () => {}); };
    e.stopPropagation(); document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
  }

  // ============================================================ AÇÕES de edição
  function splitAtPlayhead() {
    const t = St.playhead, seg = segAt(t); if (!seg || seg.kind !== "clip") return toast("Posicione o playhead sobre um clipe de vídeo");
    const c = seg.clip, local = (t - seg.start) * num(c.speed, 1); if (local < .05 || local > clipLen(c) * num(c.speed, 1) - .05) return toast("Muito perto da borda do clipe");
    commit("dividir", () => {
      const i = St.timeline.clips.findIndex((x) => x.id === c.id); const a = clone(c), b = clone(c);
      a.out = +(num(c.in) + local).toFixed(3); b.in = a.out; b.id = newId("c");
      St.timeline.clips.splice(i, 1, a, b);
    });
    toast("Clipe dividido");
  }
  function duplicateSelection() {
    if (!St.selection.length) return;
    commit("duplicar", () => {
      St.selection.forEach((uid) => {
        const it = findItem(uid); if (!it) return;
        if (it.kind === "video") { const i = St.timeline.clips.findIndex((x) => x.id === uid); const d = clone(it.clip); d.id = newId("c"); St.timeline.clips.splice(i + 1, 0, d); }
        else if (it.kind === "sfx") { St.timeline.sfx.push({ ...clone(it.sfx), at: num(it.sfx.at) + .2 }); }
        else if (it.item) { const d = clone(it.item); d.id = newId(it.kind.slice(0, 2)); d.start = num(d.start) + .3; d.end = num(d.end) + .3; it.track.items.push(d); }
      });
    });
  }
  function deleteItems(uids) {
    if (!uids || !uids.length) return;
    commit("excluir", () => {
      uids.forEach((uid) => {
        const it = findItem(uid); if (!it) return;
        if (it.kind === "video") { if (St.timeline.clips.length <= 1) return toast("A montagem precisa de ao menos um clipe"); St.timeline.clips = St.timeline.clips.filter((x) => x.id !== uid); }
        else if (it.kind === "sfx") { St.timeline.sfx = St.timeline.sfx.filter((_, i) => `sfx_${i}` !== uid); }
        else if (it.track) it.track.items = it.track.items.filter((x) => x.id !== uid);
      });
    });
    St.selection = [];
  }
  function editItem(uid, fn) { commit("editar", () => editItemRaw(uid, fn)); }
  function editItemRaw(uid, fn) { for (const t of (ed().tracks || [])) { const it = (t.items || []).find((x) => x.id === uid); if (it) return fn(it); } }

  function addText(text, style, kind) {
    const type = kind === "caption" ? "caption" : (kind === "overlay-shape" ? "overlay" : "text");
    commit("adicionar " + type, () => {
      let t = (ed().tracks || []).find((x) => x.id === (type === "caption" ? "cap" : type + "1"));
      if (!t) { t = { id: type === "caption" ? "cap" : type + "1", type, name: TRACK_LABEL[type], items: [], visible: true, height: type === "overlay" ? 40 : 40 }; ed().tracks.push(t); }
      const it = { id: newId("tx"), start: +St.playhead.toFixed(2), end: +(St.playhead + 2.5).toFixed(2), text, style: { size: 48, weight: 700, align: "center", color: "#FFFFFF", shadow: true, ...style }, transform: { x: .5, y: type === "caption" ? .82 : .5, scaleX: 1, scaleY: 1, rotation: 0, opacity: 1 }, anim: { in: "fade", out: "fade" } };
      t.items.push(it); St.selection = [it.id];
    });
    St.panel = St.panel; renderPanel();
  }
  function capTrack(create) { let t = (ed().tracks || []).find((x) => x.type === "caption"); return t || null; }
  function applyTransition(type) {
    const uid = St.selection.find((u) => (findItem(u) || {}).kind === "video"); if (!uid) return toast("Selecione um clipe de vídeo");
    const clips = St.timeline.clips; const i = clips.findIndex((c) => c.id === uid); if (i < 0 || i >= clips.length - 1) return toast("Selecione um clipe que tenha um próximo");
    commit("transição", () => { ed().transitions = (ed().transitions || []).filter((t) => t.from !== uid); ed().transitions.push({ id: newId("tr"), from: uid, to: clips[i + 1].id, type, duration: .5, config: { direction: "left", intensity: .5, easing: "ease" } }); });
    toast("Transição " + type + " aplicada (preview)");
  }
  function openTransition(tid) {
    const tr = (ed().transitions || []).find((t) => t.id === tid); if (!tr) return;
    ui.modal({ title: "Transição", subtitle: tr.type, html: `<div class="ved-field"><label>Tipo</label><select id="trType">${TRANSITIONS.map(([id, lb]) => `<option value="${id}"${id == tr.type ? " selected" : ""}>${lb}</option>`).join("")}</select></div>
      <div class="ved-slider"><label>Duração</label><input type="range" id="trDur" min="0.1" max="3" step="0.1" value="${tr.duration}"><span class="val" id="trDurv">${tr.duration}</span></div>
      <div class="ved-field"><label>Direção</label><select id="trDir">${["left", "right", "up", "down"].map((d) => `<option${d == tr.config.direction ? " selected" : ""}>${d}</option>`).join("")}</select></div>
      <p class="hint">[extensão] — aparece no preview; no master.mp4 na próxima fase.</p>`,
      actions: [{ label: "Remover", onClick: (m) => { commit("remover transição", () => ed().transitions = ed().transitions.filter((x) => x.id !== tid)); m.close(); } }, { label: "OK", primary: true, onClick: (m) => {
        commit("editar transição", () => { tr.type = document.getElementById("trType").value; tr.duration = num(document.getElementById("trDur").value, .5); tr.config.direction = document.getElementById("trDir").value; }); m.close(); } }] });
    setTimeout(() => { const d = document.getElementById("trDur"); if (d) d.oninput = () => document.getElementById("trDurv").textContent = d.value; }, 0);
  }
  function toggleEffect(type) {
    const fx = adjustTarget(); if (!fx) return toast("Selecione um clipe");
    commit("efeito " + type, () => { fx.effects = fx.effects || []; const ex = fx.effects.find((e) => e.type === type); if (ex) fx.effects = fx.effects.filter((e) => e.type !== type); else fx.effects.push({ type, intensity: .5, enabled: true }); });
    renderPanel();
  }
  function setFilterPreset(id, css) { const fx = adjustTarget(); if (!fx) return toast("Selecione um clipe"); commit("filtro", () => { fx.filters = fx.filters || {}; fx.filters.preset = id; fx.presetCss = css; }); }
  function adjustTarget() {
    const uid = St.selection[0]; if (!uid) return null; const it = findItem(uid); if (!it) return null;
    if (it.kind === "video") return clipFx(it.clip.id);
    if (["overlay"].includes(it.kind)) { it.item.filters = it.item.filters || {}; it.item.effects = it.item.effects || []; return it.item; }
    return null;
  }
  function addMarker() { commit("marcador", () => { ed().markers.push({ id: newId("mk"), at: +St.playhead.toFixed(2), name: "Marcador" }); }); }
  async function uploadSfx(files) {
    try { const r = await ui.upload(`${base()}/sfx/upload`, files); St.sfxLib = await api(`${base()}/sfx`); const novos = St.sfxLib.slice(-r.added);
      commit("importar SFX", () => { novos.forEach((s) => St.timeline.sfx.push({ file: s.file, at: +St.playhead.toFixed(2), gain: -6 })); }); toast(`${r.added} SFX importados`); }
    catch (err) { toast(err.message); }
  }
  async function resetTimeline() { try { const r = await api(`${base()}/timeline/reset`, { method: "POST" }); St.timeline = r.timeline; ed(); load(); } catch (err) { toast(err.message); } }

  // ============================================================ CONTEXT MENU
  function openMenu(x, y, uid) {
    closeMenu(); const it = findItem(uid); const isV = it && it.kind === "video";
    const items = [["Dividir", splitAtPlayhead, "Ctrl+B", isV], ["Copiar", () => { St._clip = St.selection.slice(); toast("Copiado"); }, "Ctrl+C", true],
      ["Duplicar", duplicateSelection, "Ctrl+D", true], ["sep"], ["Velocidade", () => { St.panel = "media"; St.propsTab = "speed"; renderProps(); }, "", isV],
      ["Congelar quadro", () => toast("Freeze frame entra na próxima fase"), "", isV], ["sep"],
      ["Excluir", () => deleteItems(St.selection), "Del", true, "danger"]];
    const m = document.createElement("div"); m.className = "ved-menu"; m.id = "vedMenu";
    m.innerHTML = items.filter((i) => i[0] === "sep" || i[3] !== false).map((i) => i[0] === "sep" ? `<div class="sep"></div>` : `<button class="${i[4] || ""}" data-i="${i[0]}">${i[0]}<kbd>${i[2] || ""}</kbd></button>`).join("");
    document.body.appendChild(m); const r = m.getBoundingClientRect(); m.style.left = Math.min(x, innerWidth - r.width - 8) + "px"; m.style.top = Math.min(y, innerHeight - r.height - 8) + "px";
    m.querySelectorAll("button").forEach((b) => b.onclick = () => { const f = items.find((i) => i[0] === b.dataset.i); if (f && f[1]) f[1](); closeMenu(); });
    setTimeout(() => document.addEventListener("pointerdown", closeMenu, { once: true }), 0);
  }
  function closeMenu() { const m = document.getElementById("vedMenu"); if (m) m.remove(); }

  // ============================================================ EXPORT
  function openExport() {
    const p = proj();
    ui.modal({ title: "Exportar vídeo", subtitle: "Renderiza o master com ffmpeg",
      html: `<div class="ved-field"><label>Formato</label><select id="exFmt"><option>MP4 (H.264)</option></select></div>
        <div class="ved-field"><label>Resolução</label><select id="exRes">${RES.map((r) => `<option value="${r[1]},${r[2]}"${r[1] == p.width ? " selected" : ""}>${r[0]} (${r[1]}×${r[2]})</option>`).join("")}</select></div>
        <div class="ved-field"><label>FPS</label><select id="exFps">${FPS_CHOICES.map((f) => `<option${f == p.fps ? " selected" : ""}>${f}</option>`).join("")}</select></div>
        <div class="ved-field"><label>Qualidade</label><select id="exQ"><option value="low">Baixa</option><option value="medium">Média</option><option value="high" selected>Alta</option></select></div>
        <p class="hint">Duração ${fmtTC(duration())} · ${p.aspect}. O backbone da aula 014 entra no master; textos/transições/efeitos, no preview (fase seguinte).</p>`,
      actions: [{ label: "Rough cut", onClick: (m) => { m.close(); startRender("rough", null); } },
        { label: "Exportar master", primary: true, onClick: (m) => {
          const [w, h] = document.getElementById("exRes").value.split(",").map(Number);
          const opts = { width: w, height: h, fps: num(document.getElementById("exFps").value, 30), quality: document.getElementById("exQ").value };
          m.close(); startRender("master", opts); } }] });
  }
  function startRender(target, opts) {
    if (!St.hasFfmpeg) return toast("ffmpeg ausente — render bloqueado");
    save(true).then(() => {
      ui.progressJob({ title: target === "master" ? "Renderizar master" : "Prévia (rough)", subtitle: "Montagem no ritmo (ffmpeg)",
        start: () => api(`${base()}/render`, { method: "POST", body: JSON.stringify({ target, ...(opts || {}) }) }),
        jobUrl: `${base()}/render/job`, done: (j) => { if (j.output) toast(`${j.output} pronto — assista na etapa 9`); ctx.guide(); } })
        .catch((err) => toast(err.message));
    });
  }

  // ============================================================ SHORTCUTS
  function onKey(e) {
    const t = e.target; if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    if (!St.timeline) return; const meta = e.ctrlKey || e.metaKey;
    if (e.code === "Space") { e.preventDefault(); togglePlay(); }
    else if (meta && e.key.toLowerCase() === "z" && !e.shiftKey) { e.preventDefault(); undo(); }
    else if (meta && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) { e.preventDefault(); redo(); }
    else if (meta && e.key.toLowerCase() === "b") { e.preventDefault(); splitAtPlayhead(); }
    else if (meta && e.key.toLowerCase() === "d") { e.preventDefault(); duplicateSelection(); }
    else if (meta && e.key.toLowerCase() === "c") { St._clip = St.selection.slice(); }
    else if (meta && e.key.toLowerCase() === "v") { duplicateSelection(); }
    else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); deleteItems(St.selection); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); step(e.shiftKey ? -10 : -1); }
    else if (e.key === "ArrowRight") { e.preventDefault(); step(e.shiftKey ? 10 : 1); }
    else if (e.key === "Home") seekTo(0); else if (e.key === "End") seekTo(duration());
  }

  // ============================================================ LAYOUT (fit + resize de painéis)
  function fit() {
    const r = root(); if (!r) return;
    const side = document.querySelector(".side"), topbar = document.querySelector(".topbar");
    const l = side ? side.getBoundingClientRect().right : 0; const top = topbar ? topbar.getBoundingClientRect().height : 0;
    if (document.fullscreenElement === r) { r.style.top = "0"; r.style.left = "0"; } else { r.style.top = top + "px"; r.style.left = l + "px"; }
    stageBox();
  }
  function bindResizers() {
    document.addEventListener("pointerdown", (e) => {
      const h = e.target.closest("[data-resize]"); if (!h) return; e.preventDefault();
      const kind = h.dataset.resize; const left = document.getElementById("edLeft"), right = document.getElementById("edRight"), tl = document.getElementById("edTimeline");
      const sx = e.clientX, sy = e.clientY, lw = left ? left.offsetWidth : 0, rw = right ? right.offsetWidth : 0, th = tl ? tl.offsetHeight : 0;
      const move = (ev) => {
        if (kind === "left" && left) left.style.width = clamp(lw + (ev.clientX - sx), 180, 520) + "px";
        if (kind === "right" && right) right.style.width = clamp(rw - (ev.clientX - sx), 200, 520) + "px";
        if (kind === "timeline" && tl) tl.style.height = clamp(th - (ev.clientY - sy), 120, innerHeight * 0.7) + "px";
        stageBox(); renderTimeline();
      };
      const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); };
      document.addEventListener("pointermove", move); document.addEventListener("pointerup", up);
    });
  }

  // ---------------------------------------------------------------- ciclo de vida
  return {
    init() {
      window.addEventListener("keydown", onKey);
      window.addEventListener("resize", fit);
      document.addEventListener("fullscreenchange", fit);
      bindResizers();
      this.onProject();
    },
    async onProject() {
      if (!ctx.pid()) { St.timeline = null; renderRoot(); return; }
      try { const f = await api("/api/edit/ffmpeg"); St.hasFfmpeg = f.available; } catch (e) { St.hasFfmpeg = true; }
      try { St.sfxLib = await api(`${base()}/sfx`); } catch (e) { St.sfxLib = []; }
      await load();
    },
    destroy() {
      pause(); if (raf) cancelAnimationFrame(raf); if (saveTimer) clearTimeout(saveTimer); if (job && job.stop) job.stop();
      window.removeEventListener("keydown", onKey); window.removeEventListener("resize", fit); document.removeEventListener("fullscreenchange", fit);
      closeMenu(); videoPool.clear();
    },
  };
});
