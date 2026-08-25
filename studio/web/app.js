// Núcleo do frontend: projetos, navegação e carregamento dos plugins de etapa.
// Cada etapa (studio/etapas/<id>/view.js) chama Studio.register(id, factory) e recebe um
// contexto com $, api, toast, pid(), project(), files(path), guide().
// `ui.js` roda antes deste arquivo e já criou window.Studio.ui — por isso aqui é Object.assign.
const $ = (s) => document.querySelector(s);
const api = async (path, opts = {}) => {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const toast = (m) => { const t = $("#toast"); t.textContent = m; t.classList.remove("hidden"); setTimeout(() => t.classList.add("hidden"), 2600); };

let projects = [], pid = null, current = null;
const factories = {}, instances = {}, loaded = new Set(), readySteps = new Set();

window.Studio = Object.assign(window.Studio || {}, {
  register(id, factory) { factories[id] = factory; },
  // Navegação entre etapas: usada pelos links "ir para a etapa" do painel de guia.
  go(stepId) { if (factories[stepId] || readySteps.has(stepId)) showView(stepId); },
  ctx: {
    $, api, toast,
    pid: () => pid,
    project: () => projects.find(p => p.id === pid) || null,
    files: (path) => `/files/${pid}/${path}`,
    // Recarrega o painel #guide da etapa em exibição (após qualquer ação que muda artefatos).
    guide: () => window.Studio.ui.renderGuide(current),
  },
});

// ---------- projetos ----------
async function loadProjects(selectId) {
  projects = await api("/api/projects");
  const sel = $("#projSel");
  sel.innerHTML = projects.length ? projects.map(p => `<option value="${p.id}">${p.name}</option>`).join("") : `<option value="">— crie um projeto —</option>`;
  pid = selectId || localStorage.getItem("studio.pid") || (projects[0] && projects[0].id) || null;
  if (pid && !projects.some(p => p.id === pid)) pid = projects[0] ? projects[0].id : null;
  if (pid) sel.value = pid;
  onProjectChange();
}
function onProjectChange() {
  pid = $("#projSel").value || null;
  if (pid) localStorage.setItem("studio.pid", pid);
  if (current && instances[current] && instances[current].onProject) instances[current].onProject();
}
$("#projSel").addEventListener("change", onProjectChange);
$("#btnNewProj").onclick = () => $("#newProj").classList.toggle("hidden");
$("#npCancel").onclick = () => $("#newProj").classList.add("hidden");
$("#newProj").onsubmit = async (e) => {
  e.preventDefault();
  try {
    const p = await api("/api/projects", { method: "POST", body: JSON.stringify({ name: $("#npName").value, product: $("#npProduct").value, vibe: $("#npVibe").value }) });
    $("#newProj").classList.add("hidden"); $("#newProj").reset();
    await loadProjects(p.id); toast(`Projeto ${p.name} criado`);
  } catch (err) { toast(err.message); }
};

// ---------- etapas ----------
function loadScript(src) {
  return new Promise((resolve, reject) => { const s = document.createElement("script"); s.src = src; s.onload = resolve; s.onerror = () => reject(new Error("falha ao carregar " + src)); document.body.appendChild(s); });
}
async function showView(id) {
  // Encerra a tela anterior: sem isso o polling dela sobrevive à troca e continua batendo na API.
  if (current && instances[current] && instances[current].destroy) {
    try { instances[current].destroy(); } catch (e) { /* uma tela quebrada não impede a troca */ }
  }
  document.querySelectorAll("#steps li").forEach(li => li.classList.toggle("active", li.dataset.id === id));
  localStorage.setItem("studio.view", id);
  const main = $("#main");
  try {
    const r = await fetch(`/steps/${id}/view.html`);
    if (!r.ok) throw new Error(`etapa ${id}: tela indisponível (${r.status})`);
    main.innerHTML = await r.text();
    if (!loaded.has(id)) { await loadScript(`/steps/${id}/view.js`); loaded.add(id); }
    if (!factories[id]) throw new Error(`etapa ${id}: view.js não registrou a tela`);
    current = id;
    instances[id] = factories[id](window.Studio.ctx);
    instances[id].init();
  } catch (err) {
    current = null;
    main.innerHTML = `<div class="empty">Não foi possível abrir esta etapa: ${window.Studio.ui.esc(err.message)}</div>`;
    toast(err.message);
  }
}
(async () => {
  const steps = await api("/api/steps");
  steps.filter(s => s.status === "ready").forEach(s => readySteps.add(s.id));
  const ol = $("#steps");
  ol.innerHTML = steps.map(s =>
    `<li class="${s.status}" data-id="${s.id}" title="${s.desc}" ${s.status === "ready" ? 'tabindex="0"' : ""}><span class="n">${String(s.n).padStart(2, "0")}</span><span><span class="t">${s.title}</span><span class="a">aula ${s.aula}${s.status === "soon" ? " · em breve" : ""}</span></span></li>`).join("");
  ol.addEventListener("click", e => { const li = e.target.closest("li.ready"); if (li) showView(li.dataset.id); });
  ol.addEventListener("keydown", e => { if (e.key === "Enter") { const li = e.target.closest("li.ready"); if (li) showView(li.dataset.id); } });
  await loadProjects();
  const want = localStorage.getItem("studio.view");
  showView(readySteps.has(want) ? want : steps.find(s => s.status === "ready").id);
})();
