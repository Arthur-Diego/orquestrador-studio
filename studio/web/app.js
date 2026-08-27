// Núcleo do frontend (shell OS-013, redesenhado na wave 3 / ADH-OS-20260826-02): campanhas,
// roteamento, estado por etapa e visão geral.
//
// Redesign: o estado da campanha é comunicado por dois pipelines segmentados de 11 ticks
// (`#railPipe` na sidebar e `#tbPipe` no topo, mesmo mapa de cores, `title` por segmento) em vez
// das barras `.progress` da wave 2, e a visão geral vira um grid de cards sem `.panel` em volta.
//
// Cada etapa (studio/etapas/<id>/view.js) chama Studio.register(id, factory) e recebe um
// contexto com $, api, toast, pid(), project(), files(path), guide().
// `ui.js` roda antes deste arquivo e já criou window.Studio.ui — por isso aqui é Object.assign.
//
// Roteamento: o hash é a fonte de verdade (`#/<pid>/<step>` e `#/<pid>/overview`); o
// localStorage só serve de fallback quando o hash está vazio ou aponta para algo inexistente.
// O estado de cada etapa (a fazer / bloqueada / em andamento / concluída) vem SEMPRE do guia do
// backend (`GET /api/projects/{pid}/guide`), nunca de um cálculo daqui.
const $ = (s) => document.querySelector(s);
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const toast = (m) => { const t = $("#toast"); t.textContent = m; t.classList.remove("hidden"); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), 3200); };
const esc = (s) => window.Studio.ui.esc(s);

// ---------- estado ----------
let steps = [], projects = [], pid = null, project = null;
let guideAll = null;              // { steps: [Guide × 11], done, total, progress, current }
let guideById = {};               // id → Guide
let view = "overview";            // "overview" | <id da etapa>
// Áreas do shell: "campaign" (as 11 etapas + visão geral) e "moodboards" (biblioteca global
// [extensão] ADR-013, campanha-independente). `moodboards` é um prefixo de rota RESERVADO —
// um pid de projeto nunca pode ser "moodboards" (reservado em create_project).
const MB_ROUTE = "moodboards";
let area = "campaign";            // "campaign" | "moodboards"
let currentStep = null;           // etapa instanciada em #main
const factories = {}, instances = {}, loaded = new Set(), readySteps = new Set();
let refreshTimer = null;

const ASPECTS = [
  { id: "16:9", dest: "YouTube, tela cheia", w: 28, h: 16 },
  { id: "9:16", dest: "Reels, TikTok, Shorts", w: 11, h: 20 },
  { id: "1:1", dest: "Feed quadrado", w: 18, h: 18 },
];
const ASPECT_LABEL = { "16:9": "16:9 · YouTube", "9:16": "9:16 · Reels/TikTok", "1:1": "1:1 · feed" };
// Wave 4: o painel de fidelidade ao roteiro (aulas 005/007/008) saiu da UI — o protótipo não o
// desenha. O texto dele continua em CLAUDE.md e no ADR-004.

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* localStorage bloqueado */ } },
};

// ---------- contrato com os plugins de etapa ----------
window.Studio = Object.assign(window.Studio || {}, {
  register(id, factory) { factories[id] = factory; },
  /** Navegação entre telas: etapas e a visão geral (`Studio.go("overview")`). */
  go(target) {
    if (target === "overview" || factories[target] || readySteps.has(target)) navigate(target);
  },
  /** `Studio.ui.renderGuide` avisa aqui: o menu e a barra de progresso acompanham a etapa. */
  onGuide(stepId, g) {
    if (g) { guideById[stepId] = g; recomputeOverview(); renderMenu(); renderTopbar(); }
    scheduleGuideRefresh();
  },
  ctx: {
    $, api, toast,
    pid: () => pid,
    project: () => project || projects.find((p) => p.id === pid) || null,
    files: (path) => `/files/${pid}/${path}`,
    // Recarrega o painel #guide da etapa em exibição (após qualquer ação que muda artefatos).
    guide: () => window.Studio.ui.renderGuide(currentStep),
  },
});

// ---------- roteamento por hash ----------
function parseHash() {
  const m = (location.hash || "").match(/^#\/([^/]+)(?:\/([^/]+))?\/?$/);
  return m ? { pid: decodeURIComponent(m[1]), view: m[2] ? decodeURIComponent(m[2]) : "overview" } : null;
}
async function navigate(target, opts = {}) {
  const p = opts.pid || pid;
  if (!p) { await applyRoute(); return; }
  const h = `#/${encodeURIComponent(p)}/${encodeURIComponent(target)}`;
  if (location.hash === h) { await applyRoute(); return; }
  if (opts.replace) { history.replaceState(null, "", h); await applyRoute(); }
  else location.hash = h;                       // dispara hashchange → applyRoute()
}
async function applyRoute() {
  const hr = parseHash();
  // Área global da biblioteca de mood boards [extensão] (ADR-013): tratada ANTES do check de
  // campanhas — funciona mesmo sem nenhuma campanha criada. `#/moodboards` = lista;
  // `#/moodboards/<mbid>` = editor.
  if (hr && hr.pid === MB_ROUTE) {
    area = "moodboards";
    destroyCurrent();
    view = null;
    renderMenu(); renderTopbar();
    const mbid = (hr.view && hr.view !== "overview") ? hr.view : null;
    if (window.Studio.moodboards) window.Studio.moodboards.open(mbid);
    return;
  }
  area = "campaign";
  if (!projects.length) {
    pid = null; project = null; guideAll = null; guideById = {};
    renderMenu(); renderTopbar(); renderNoProject();
    return;
  }
  const r = parseHash();
  let wantPid = r && r.pid;
  let wantView = r && r.view;
  if (!wantPid || !projects.some((p) => p.id === wantPid)) {
    const saved = store.get("studio.pid");
    wantPid = projects.some((p) => p.id === saved) ? saved : projects[0].id;
    if (!r) wantView = store.get("studio.view") || "overview";
    return navigate(wantView || "overview", { pid: wantPid, replace: true });
  }
  if (wantView !== "overview" && !readySteps.has(wantView)) {
    return navigate("overview", { pid: wantPid, replace: true });
  }
  const trocouProjeto = wantPid !== pid;
  pid = wantPid;
  store.set("studio.pid", pid); store.set("studio.view", wantView);
  if ($("#projSel").value !== pid) $("#projSel").value = pid;
  if (trocouProjeto) {
    project = null; guideAll = null; guideById = {};
    renderTopbar(); renderMenu();
    await loadProjectState();
  }
  view = wantView;
  renderMenu(); renderTopbar();
  if (view === "overview") { destroyCurrent(); renderOverview(); }
  else await showView(view);
}
window.addEventListener("hashchange", () => { applyRoute(); });

// ---------- dados da campanha ----------
async function loadProjects(selectId) {
  projects = await api("/api/projects").catch(() => []);
  const sel = $("#projSel");
  sel.innerHTML = projects.length
    ? projects.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("")
    : `<option value="">— nenhuma campanha —</option>`;
  if (selectId) { pid = null; await navigate("overview", { pid: selectId, replace: true }); return; }
  await applyRoute();
}
async function loadProjectState() {
  const [p, g] = await Promise.allSettled([
    api(`/api/projects/${encodeURIComponent(pid)}`),
    api(`/api/projects/${encodeURIComponent(pid)}/guide`),
  ]);
  project = p.status === "fulfilled" ? p.value : (projects.find((x) => x.id === pid) || null);
  guideAll = g.status === "fulfilled" ? g.value : null;
  guideById = {};
  if (guideAll && guideAll.steps) guideAll.steps.forEach((s) => { guideById[s.id] = s; });
  renderTopbar(); renderMenu();
}
/** Recalcula `done`/`current` depois que uma etapa devolveu um guia novo (sem ir ao servidor). */
function recomputeOverview() {
  if (!guideAll) return;
  guideAll.steps = steps.map((s) => guideById[s.id]).filter(Boolean);
  guideAll.done = guideAll.steps.filter((g) => g.status === "done").length;
  guideAll.total = guideAll.steps.length;
  guideAll.progress = guideAll.total ? guideAll.done / guideAll.total : 0;
  const next = guideAll.steps.find((g) => g.status !== "done");
  guideAll.current = next ? next.id : null;
}
/** Recarrega o agregado do guia com debounce — uma etapa pode chamar `ctx.guide()` várias vezes. */
function scheduleGuideRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(async () => {
    if (!pid) return;
    try {
      guideAll = await api(`/api/projects/${encodeURIComponent(pid)}/guide`);
      guideById = {};
      guideAll.steps.forEach((s) => { guideById[s.id] = s; });
      renderMenu(); renderTopbar();
      if (view === "overview") renderOverview();
    } catch (e) { /* o guia é informativo: falhar aqui não pode atrapalhar a tela */ }
  }, 400);
}

// ---------- menu lateral ----------
function statusOf(stepId, stepStatus) {
  if (!pid) return "none";                    // sem campanha não existe estado de etapa
  const g = guideById[stepId];
  if (g) return g.status;
  return stepStatus === "ready" ? "unknown" : "todo";
}
/** Estado de cada uma das 11 etapas, na ordem do curso — alimenta os dois pipelines. */
function estadosDasEtapas() {
  return steps.map((s) => statusOf(s.id, s.status));
}
/** Pipeline segmentado (elemento-assinatura do redesign): 11 `i` com a cor do status. */
function pipeHtml(estados) {
  const ui = window.Studio.ui;
  return steps.map((s, i) => {
    const st = estados[i];
    const rotulo = st === "none" ? "sem campanha" : (ui.STATUS_LABEL[st] || st);
    return `<i class="${esc(st)}" title="${esc(`${s.n} · ${s.title} — ${rotulo}`)}"></i>`;
  }).join("");
}
function renderMenu() {
  const ui = window.Studio.ui;
  $("#btnOverview").classList.toggle("active", area === "campaign" && view === "overview");
  const mb = $("#btnMoodboards");
  if (mb) mb.classList.toggle("active", area === "moodboards");
  const estados = estadosDasEtapas();
  $("#railPipe").innerHTML = pipeHtml(estados);
  const feitas = estados.filter((st) => st === "done").length;
  $("#railCount").textContent = pid ? `${feitas}/${steps.length}` : "—";
  $("#steps").innerHTML = steps.map((s, i) => {
    const g = guideById[s.id];
    const st = estados[i];
    const falta = g && g.missing && g.missing.length ? `\nFaltando: ${g.missing.join(", ")}` : "";
    const rotulo = st === "none" ? "" : (ui.STATUS_LABEL[st] || st);
    const title = rotulo ? `${s.desc}\n${rotulo}${falta}` : s.desc;
    return `<li class="${s.status} st-${st}${view === s.id ? " active" : ""}" data-id="${esc(s.id)}" title="${esc(title)}"${s.status === "ready" ? ' tabindex="0" role="button"' : ""}>
      <span class="n">${String(s.n).padStart(2, "0")}</span>
      <span class="body"><span class="t">${esc(s.title)}</span><span class="a">aula ${esc(s.aula)}${s.status === "soon" ? " · em breve" : ""}</span></span>
      <span class="st" aria-label="${esc(rotulo)}"></span>
    </li>`;
  }).join("");
}

// ---------- topo da campanha ----------
function renderTopbar() {
  const ui = window.Studio.ui;
  const nome = project ? project.name : (projects.find((p) => p.id === pid) || {}).name;
  $("#tbName").textContent = nome || "Nenhuma campanha";
  $("#tbEyebrow").textContent = pid ? `Campanha · ${pid}` : "Campanha";
  const done = guideAll ? guideAll.done : 0;
  const total = guideAll ? guideAll.total : steps.length;
  $("#tbCount").textContent = pid ? `${done}/${total} etapas` : "—";
  $("#tbPipe").innerHTML = pipeHtml(estadosDasEtapas());

  const chips = [];
  if (project && project.product) chips.push(ui.chip(project.product, "mode"));
  chips.push(ui.chip(ASPECT_LABEL[(project && project.aspect_ratio) || "16:9"], "mode"));
  if (project && project.vibe) chips.push(ui.chip(`vibe: ${project.vibe}`, "info"));
  else if (pid) chips.push(ui.chip("vibe: definida na etapa 2", "info"));
  $("#tbMeta").innerHTML = pid ? chips.join("") : "";

  const cur = guideAll && guideAll.current;
  $("#btnContinue").disabled = !pid || !cur;
  $("#btnContinue").textContent = pid && guideAll && !cur ? "Campanha concluída" : "Continuar de onde parei →";
  $("#btnEditCamp").disabled = !pid;
  // Sem campanha o topo não tem o que mostrar: só a marca e o convite para criar a primeira.
  $("#topbar").classList.toggle("vazio", !pid);
}

// ---------- visão geral ----------
function cardHtml(s) {
  const ui = window.Studio.ui;
  const g = guideById[s.id];
  const st = statusOf(s.id, s.status);
  const pct = g ? Math.round((g.progress || 0) * 100) : 0;
  const atual = guideAll && guideAll.current === s.id;
  // O protótipo desenha a linha "→ …" só nos cards concluída/em andamento (e na bloqueada,
  // onde ela é o único aviso do que trava a etapa). O que falta continua no `title` do item do
  // rail e na linha de estado do guia da etapa — o card não repete "Faltando:".
  const mostraNext = st === "done" || st === "in_progress" || st === "blocked";
  const next = mostraNext && g && g.next_action ? `<p class="next">→ ${esc(g.next_action)}</p>` : "";
  // O card da etapa em andamento é o único destacado (bg elevado, borda accent, glow e CTA
  // primário); "etapa atual" vai no title/aria para não duplicar o chip de status do protótipo.
  const rotulo = atual ? ' title="etapa atual" aria-current="step"' : "";
  const acao = atual ? "Continuar aqui" : (st === "done" ? "Rever" : "Abrir");
  return `<article class="ovcard st-${st}${atual ? " is-current" : ""}"${rotulo}>
    <div class="ovcard-top">
      <span class="n">${String(s.n).padStart(2, "0")}</span>
      <span class="aula">aula ${esc(s.aula)}</span>
      ${ui.chip(ui.STATUS_LABEL[st] || st, ui.STATUS_KIND[st] || "mode")}
    </div>
    <h4>${esc(s.title)}</h4>
    <p class="desc">${esc(s.desc || "")}</p>
    <div class="progress${st === "done" ? " ok" : ""}"><div class="bar" style="width:${pct}%"></div></div>
    ${next}
    <div class="act">${s.status === "ready"
      ? `<button class="${atual ? "primary" : "ghost"}" data-go="${esc(s.id)}">${acao}</button>`
      : `<button class="ghost" disabled>Em breve</button>`}</div>
  </article>`;
}
function renderOverview() {
  const ui = window.Studio.ui;
  const cur = guideAll && guideAll.current && guideById[guideAll.current];
  const contagem = {};
  steps.forEach((s) => { const st = statusOf(s.id, s.status); contagem[st] = (contagem[st] || 0) + 1; });
  const resumo = ["done", "in_progress", "blocked", "todo", "unknown"]
    .filter((k) => contagem[k])
    .map((k) => ui.chip(`${contagem[k]} ${ui.STATUS_LABEL[k]}`, ui.STATUS_KIND[k])).join("");

  $("#main").innerHTML = `
  <header class="stephead ov">
    <span class="eyebrow">Etapas 1 a 11 · aulas 009 → 015 · 001</span>
    <h2>Visão geral da campanha</h2>
    <p class="lede">As 11 etapas do curso, na ordem das aulas, com o estado real dos artefatos. ${cur ? `Você está na <b>etapa ${esc(cur.n)} — ${esc(cur.title)}</b>.` : "Todas as etapas estão concluídas."}</p>
    <div class="ov-summary">${resumo}</div>
    <div class="ov-actions"><button type="button" class="shell-reset ghost" id="btnResetCamp"
      title="Apaga tudo o que as 11 etapas produziram; mantém nome, produto, vibe e formato">Resetar campanha [extensão]</button></div>
  </header>

  <div class="ovgrid">${steps.map(cardHtml).join("")}</div>`;

  const bReset = $("#btnResetCamp");
  if (bReset) bReset.onclick = confirmResetCampaign;
  $("#main").onclick = (ev) => {
    const b = ev.target.closest("[data-go]");
    if (b && !b.disabled) window.Studio.go(b.dataset.go);
  };
}
function renderNoProject() {
  $("#main").innerHTML = `
  <div class="empty-state">
    <span class="eyebrow">Orquestrador Studio</span>
    <h2>Nenhuma campanha ainda</h2>
    <p class="lede">Uma campanha guarda tudo o que as 11 etapas do curso produzem: referências, mood board, imagem base, storyboard, ângulos, takes, trilha, montagem, export, publicação e prospecção.</p>
    <button class="primary" id="btnFirst" type="button">Criar a primeira campanha</button>
  </div>`;
  $("#btnFirst").onclick = openWizard;
  $("#main").onclick = null;
}

// ---------- telas de etapa ----------
function loadScript(src) {
  return new Promise((resolve, reject) => { const s = document.createElement("script"); s.src = src; s.onload = resolve; s.onerror = () => reject(new Error("falha ao carregar " + src)); document.body.appendChild(s); });
}
/** Encerra a tela anterior: sem isso o polling dela sobrevive à troca e continua batendo na API. */
function destroyCurrent() {
  if (currentStep && instances[currentStep] && instances[currentStep].destroy) {
    try { instances[currentStep].destroy(); } catch (e) { /* uma tela quebrada não impede a troca */ }
  }
  currentStep = null;
  $("#main").onclick = null;
}
async function showView(id) {
  destroyCurrent();
  const main = $("#main");
  try {
    const r = await fetch(`/steps/${encodeURIComponent(id)}/view.html`);
    if (!r.ok) throw new Error(`etapa ${id}: tela indisponível (${r.status})`);
    main.innerHTML = await r.text();
    if (!loaded.has(id)) { await loadScript(`/steps/${encodeURIComponent(id)}/view.js`); loaded.add(id); }
    if (!factories[id]) throw new Error(`etapa ${id}: view.js não registrou a tela`);
    ensureGuideSlot(main);
    injectStepReset(main, id);
    currentStep = id;
    instances[id] = factories[id](window.Studio.ctx);
    instances[id].init();
    // A tela também chama `renderGuide` nas suas ações; aqui garantimos o painel no 1º render.
    window.Studio.ui.renderGuide(id);
  } catch (err) {
    currentStep = null;
    main.innerHTML = `<div class="empty">Não foi possível abrir esta etapa: ${esc(err.message)}</div>`;
    toast(err.message);
  }
}
/**
 * O contrato da wave 2 pede `<section id="guide" class="guide">` logo após o `header.stephead`.
 * Enquanto as frentes de etapa não migram os seus `view.html`, o shell cria o slot — quando o
 * `view.html` já traz o seu, nada muda (o elemento existente é reaproveitado).
 */
function ensureGuideSlot(main) {
  if (main.querySelector("#guide")) return;
  const sec = document.createElement("section");
  sec.id = "guide"; sec.className = "guide";
  const head = main.querySelector("header.stephead");
  if (head && head.parentNode) head.after(sec); else main.prepend(sec);
}

// ---------- reset [extensão] (não é passo do curso — ADR-004) ----------
// O SHELL desenha o controle de reset no `header.stephead` de qualquer etapa; os `view.html` das
// telas não o conhecem (ADR-010). O reset só acontece depois do modal de confirmação.
/** A etapa `stepId` + todas as seguintes (o que a cascata vai apagar). */
function stepsFromHere(stepId) {
  const i = steps.findIndex((s) => s.id === stepId);
  return i < 0 ? [] : steps.slice(i);
}
/** Injeta o botão "Resetar etapa [extensão]" no stephead da etapa em exibição. */
function injectStepReset(main, stepId) {
  const head = main.querySelector("header.stephead");
  if (!head || head.querySelector(".shell-reset")) return;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "shell-reset ghost";
  btn.textContent = "Resetar etapa [extensão]";
  btn.title = "Apaga o que esta etapa e as seguintes produziram; mantém nome, produto, vibe e formato";
  btn.onclick = () => confirmResetStep(stepId);
  head.appendChild(btn);
}
/** Modal de confirmação da cascata — lista a etapa + as seguintes, por nome. */
function confirmResetStep(stepId) {
  if (!pid) return;
  const s = steps.find((x) => x.id === stepId);
  const lista = stepsFromHere(stepId)
    .map((x) => `<li><b>${esc(x.n)}. ${esc(x.title)}</b></li>`).join("");
  const html = `<p>Isto apaga, em cascata, tudo o que estas etapas produziram:</p>
    <ul class="reset-list">${lista}</ul>
    <p>O <b>nome</b>, o <b>produto</b>, a <b>vibe</b> e o <b>formato</b> da campanha são mantidos.</p>
    <p class="reset-note">Reset é uma extensão do Studio, não um passo do curso.</p>`;
  const m = window.Studio.ui.modal({
    title: `Resetar etapa ${s ? `${s.n} — ${s.title}` : stepId} [extensão]`,
    subtitle: "Extensão do Studio",
    html,
    actions: [
      { label: "Cancelar", kind: "ghost", close: true },
      { label: "Resetar", kind: "primary", onClick: (mm) => doResetStep(stepId, mm) },
    ],
  });
  if (m.actions[1]) m.actions[1].classList.add("danger");
}
async function doResetStep(stepId, m) {
  try {
    await api(`/api/projects/${encodeURIComponent(pid)}/steps/${encodeURIComponent(stepId)}/reset`, { method: "POST" });
    if (m) m.close();
    toast("Etapa resetada");
    await loadProjectState();
    if (view === stepId) await showView(stepId);   // recarrega a tela (guia derivado volta ao inicial)
    renderMenu(); renderTopbar();
    if (view === "overview") renderOverview();
  } catch (err) {
    toast(err.message);
  }
}
/** Modal de confirmação do reset da campanha inteira (visão geral). */
function confirmResetCampaign() {
  if (!pid) return;
  const html = `<p>Isto apaga tudo o que as 11 etapas produziram — referências, mood board, imagem
    base, storyboard, ângulos, takes, trilha, montagem, export, publicação e prospecção.</p>
    <p>O <b>nome</b>, o <b>produto</b>, a <b>vibe</b> e o <b>formato</b> da campanha são mantidos.</p>
    <p class="reset-note">Reset é uma extensão do Studio, não um passo do curso.</p>`;
  const m = window.Studio.ui.modal({
    title: "Resetar campanha [extensão]",
    subtitle: "Extensão do Studio",
    html,
    actions: [
      { label: "Cancelar", kind: "ghost", close: true },
      { label: "Resetar campanha", kind: "primary", onClick: (mm) => doResetCampaign(mm) },
    ],
  });
  if (m.actions[1]) m.actions[1].classList.add("danger");
}
async function doResetCampaign(m) {
  try {
    await api(`/api/projects/${encodeURIComponent(pid)}/reset`, { method: "POST" });
    if (m) m.close();
    toast("Campanha resetada");
    await loadProjectState();
    renderMenu(); renderTopbar();
    if (view === "overview") renderOverview();
  } catch (err) {
    toast(err.message);
  }
}

// ---------- wizard e edição da campanha ----------
function campoFormato(atual) {
  return `<div class="field fmt-field">
    <span class="eyebrow">Formato — pela plataforma de destino</span>
    <div class="fmt">${ASPECTS.map((a) => `<label>
      <span class="box"><i style="width:${a.w}px;height:${a.h}px"></i></span>
      <input type="radio" name="aspect" value="${a.id}"${a.id === atual ? " checked" : ""}>
      <span class="ratio">${a.id}</span>
      <span class="dest">${esc(a.dest)}</span>
    </label>`).join("")}</div>
  </div>`;
}
function campanhaForm(p, submitLabel) {
  return `<form id="campForm" novalidate>
    <label class="field" for="cfName">
      <span class="eyebrow">Nome da campanha</span>
      <input id="cfName" name="name" required maxlength="80" placeholder="ex.: Gelo Zero" value="${esc(p.name || "")}">
    </label>
    <label class="field" for="cfProduct">
      <span class="eyebrow">Produto</span>
      <input id="cfProduct" name="product" placeholder="ex.: energy drink (vale em inglês — os prompts são em inglês)" value="${esc(p.product || "")}">
    </label>
    <label class="field" for="cfVibe">
      <span class="eyebrow">Vibe — opcional, encontrada na etapa 2</span>
      <input id="cfVibe" name="vibe" placeholder="(dá para começar sem nenhuma ideia)" value="${esc(p.vibe || "")}">
    </label>
    ${campoFormato(p.aspect_ratio || "16:9")}
    <div class="modal-actions">
      <button type="button" class="ghost lg" data-close>Cancelar</button>
      <button type="submit" class="primary lg">${esc(submitLabel)}</button>
    </div>
  </form>`;
}
function ligaForm(m, onSubmit) {
  const form = m.el.querySelector("#campForm");
  m.el.querySelector("[data-close]").onclick = m.close;
  form.onsubmit = async (e) => {
    e.preventDefault();
    const dados = {
      name: form.name.value.trim(),
      product: form.product.value.trim(),
      vibe: form.vibe.value.trim(),
      aspect_ratio: (form.querySelector('input[name="aspect"]:checked') || {}).value || "16:9",
    };
    if (!dados.name) { toast("Dê um nome à campanha"); form.name.focus(); return; }
    const btn = form.querySelector('button[type="submit"]');
    btn.classList.add("loading"); btn.disabled = true;
    try {
      await onSubmit(dados, m);
    } catch (err) {
      toast(err.message);
    } finally {
      btn.classList.remove("loading"); btn.disabled = false;
    }
  };
}
function openWizard() {
  const m = window.Studio.ui.modal({
    title: "Nova campanha",
    subtitle: "O básico para começar a etapa 1 — o resto o Studio descobre no caminho.",
    html: campanhaForm({}, "Criar campanha"),
  });
  ligaForm(m, async (dados, modal) => {
    const p = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name: dados.name, product: dados.product, vibe: dados.vibe }),
    });
    // O formato vive em `project.json` e é aplicado por PATCH (a criação não recebe o campo).
    await api(`/api/projects/${encodeURIComponent(p.id)}`, {
      method: "PATCH", body: JSON.stringify({ aspect_ratio: dados.aspect_ratio }),
    }).catch(() => null);
    modal.close();
    toast(`Campanha ${p.name} criada`);
    await loadProjects(p.id);
  });
}
function openEdit() {
  if (!pid) return;
  const atual = project || projects.find((p) => p.id === pid) || {};
  const m = window.Studio.ui.modal({
    title: "Editar campanha",
    subtitle: `Muda só os dados da campanha — os artefatos já produzidos ficam onde estão (${pid}).`,
    html: campanhaForm(atual, "Salvar alterações"),
  });
  ligaForm(m, async (dados, modal) => {
    project = await api(`/api/projects/${encodeURIComponent(pid)}`, { method: "PATCH", body: JSON.stringify(dados) });
    const na = projects.find((p) => p.id === pid);
    if (na) na.name = project.name;
    $("#projSel").innerHTML = projects.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
    $("#projSel").value = pid;
    modal.close();
    toast("Campanha atualizada");
    renderTopbar();
    if (view === "overview") renderOverview();
  });
}

// ---------- tema ----------
const TEMA_LABEL = { auto: "tema: sistema", light: "tema: claro", dark: "tema: escuro" };
function aplicaTema(t) {
  if (t === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = t;
  store.set("studio.theme", t);
  $("#themeLabel").textContent = TEMA_LABEL[t];
  $("#btnTheme").title = `Tema: ${TEMA_LABEL[t].replace("tema: ", "")} (clique para alternar)`;
}

// ---------- bootstrap ----------
$("#projSel").addEventListener("change", (e) => { if (e.target.value) navigate("overview", { pid: e.target.value }); });
$("#btnNewProj").onclick = openWizard;
$("#btnEditCamp").onclick = openEdit;
$("#btnOverview").onclick = () => navigate("overview");
$("#btnMoodboards").onclick = () => { if (location.hash === "#/moodboards") applyRoute(); else location.hash = "#/moodboards"; };
$("#btnContinue").onclick = () => { const c = guideAll && guideAll.current; if (c) navigate(c); };
$("#btnTheme").onclick = () => {
  const ordem = ["auto", "light", "dark"];
  aplicaTema(ordem[(ordem.indexOf(store.get("studio.theme") || "auto") + 1) % ordem.length]);
};
$("#steps").addEventListener("click", (e) => { const li = e.target.closest("li.ready"); if (li) navigate(li.dataset.id); });
$("#steps").addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const li = e.target.closest("li.ready");
  if (li) { e.preventDefault(); navigate(li.dataset.id); }
});

(async () => {
  aplicaTema(store.get("studio.theme") || "auto");
  // Chip do CLI da Higgsfield no rodapé da sidebar: o estado do plano vale para a sessão inteira.
  window.Studio.ui.hfChip("#hfChipSide");
  steps = await api("/api/steps").catch(() => []);
  // Catálogo em leitura para `Studio.ui` (o guia usa o número da etapa em "Ir para a etapa N").
  window.Studio.steps = steps;
  steps.filter((s) => s.status === "ready").forEach((s) => readySteps.add(s.id));
  renderMenu();
  await loadProjects();
})();
