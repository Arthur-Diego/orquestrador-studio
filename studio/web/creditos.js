// Área global "Créditos & Custos [extensão]" (ADR-016): saldo do CLI, tabela de custo por
// modelo/resolução, histórico de gasto por etapa/projeto e o PAINEL ADMIN dos modelos default
// por ação (config global e por projeto). Rota reservada `#/creditos`. Carregado depois de
// app.js e ui.js — reusa Studio.ui (chip/modal) e Studio.ctx (api, toast, pid).
//
// A aula 008 coloca o custo como critério principal de cada geração. Esta tela é a extensão que
// torna esse critério visível e configurável: as telas de etapa leem o modelo default daqui
// (Studio.ui.defaultModel) em vez de fixá-lo no código.
(function () {
  const ui = window.Studio.ui;
  const esc = (s) => ui.esc(s);
  const ctx = () => window.Studio.ctx;
  const api = (p, o) => ctx().api(p, o);
  const toast = (m) => ctx().toast(m);
  const $main = () => document.querySelector("#main");

  let data = null;          // último dashboard carregado
  let pid = null;           // campanha atual (para override por projeto)
  let scope = "global";     // "global" | "project"

  function base() { return (scope === "project" && pid) ? `/api/projects/${encodeURIComponent(pid)}/creditos` : "/api/creditos"; }

  async function load() {
    const url = pid ? `/api/projects/${encodeURIComponent(pid)}/creditos` : "/api/creditos";
    data = await api(url);
    return data;
  }

  async function open(currentPid) {
    pid = currentPid || null;
    if (!pid) scope = "global";
    const main = $main();
    main.onclick = null;
    main.innerHTML = `<div class="empty">Carregando créditos…</div>`;
    try { await load(); }
    catch (e) { main.innerHTML = `<div class="empty">Não foi possível carregar: ${esc(e.message)}</div>`; return; }
    render();
  }

  // ---------- saldo ----------
  function balanceCard() {
    const b = data.balance || {};
    let chip, msg;
    if (!b.installed) {
      chip = ui.chip("CLI não instalado", "warn");
      msg = `O CLI da Higgsfield não está instalado. Gere pela <b>UI da Higgsfield</b> (ilimitado no plano) e importe o resultado nas etapas.`;
    } else if (!b.logged_in) {
      chip = ui.chip("sem login", "warn");
      msg = `CLI sem login (<code>higgsfield auth login</code>). Sem login o CLI não gera — use a <b>UI da Higgsfield</b> (ilimitado) e importe; o custo em créditos vale só para o caminho CLI.`;
    } else {
      chip = ui.chip(b.plan || "logado", "ok");
      msg = `Saldo do CLI da Higgsfield. O ilimitado do plano vale só na UI — cada geração pelo CLI gasta os créditos abaixo.`;
    }
    const saldo = b.logged_in ? (b.credits ?? "?") : "—";
    return `<section class="cr-card cr-balance">
      <div class="cr-balance-main">
        <span class="eyebrow">Saldo restante</span>
        <div class="cr-saldo"><b>${esc(saldo)}</b><span>créditos</span></div>
        ${chip}
      </div>
      <p class="cr-balance-msg">${msg}</p>
      <button class="ghost" id="crRefresh" type="button">Atualizar saldo</button>
    </section>`;
  }

  // ---------- painel admin: modelos default por ação ----------
  function optionsFor(kind, selected) {
    return (data.models || []).filter((m) => m.kind === kind)
      .map((m) => `<option value="${esc(m.id)}"${m.id === selected ? " selected" : ""}>${esc(m.label)}</option>`).join("");
  }
  // `acao` = rótulo da ação da linha: entra no aria-label porque a tabela repete estes selects
  // por linha e o cabeçalho "Modelo" sozinho não identifica qual ação está sendo editada.
  function variantOptions(modelId, selected, acao) {
    const m = (data.models || []).find((x) => x.id === modelId);
    if (!m || !m.variant_options || !m.variant_options.length) return "";
    const opts = m.variant_options.map((v) => `<option value="${esc(v)}"${v === selected ? " selected" : ""}>${esc(v)}</option>`).join("");
    return `<select class="cr-variant" data-vk="${esc(m.variant_key || "")}" aria-label="Variação de ${esc(acao || "")}">${opts}</select>`;
  }
  const SRC_LABEL = { code: "código", global: "global", project: "projeto" };

  function adminSection() {
    const scopeToggle = pid
      ? `<div class="cr-scope">
          <span class="eyebrow">Editar defaults de</span>
          <div class="seg">
            <button type="button" class="seg-btn${scope === "global" ? " on" : ""}" data-scope="global">Global</button>
            <button type="button" class="seg-btn${scope === "project" ? " on" : ""}" data-scope="project">Esta campanha</button>
          </div>
        </div>`
      : `<p class="cr-note">Defaults <b>globais</b> — abra uma campanha para definir override por projeto.</p>`;
    const rows = (data.actions || []).map((a) => {
      const isOverride = scope === "project" && a.source === "project";
      const srcChip = ui.chip(SRC_LABEL[a.source] || a.source, a.source === "project" ? "info" : a.source === "global" ? "mode" : "todo");
      const clearBtn = (scope === "project")
        ? `<button class="link cr-clear" type="button" data-action="${esc(a.key)}"${isOverride ? "" : " disabled"} title="Voltar ao default global/código">usar global</button>`
        : "";
      return `<tr data-action="${esc(a.key)}" data-kind="${esc(a.kind)}" data-label="${esc(a.label)}">
        <td><div class="cr-act"><b>${esc(a.label)}</b><span>${esc(a.screen)}</span></div></td>
        <td class="cr-modelcell">
          <select class="cr-model" aria-label="Modelo de ${esc(a.label)}">${optionsFor(a.kind, a.model)}</select>
          ${variantOptions(a.model, a.variant, a.label)}
        </td>
        <td class="cr-cost">${a.credits != null ? `${esc(a.credits)} cr` : "—"}</td>
        <td class="cr-src">${srcChip}${clearBtn}</td>
      </tr>`;
    }).join("");
    return `<section class="cr-card">
      <div class="cr-card-head"><h3>Modelos default por ação</h3>${scopeToggle}</div>
      <p class="cr-note">As telas de etapa preselecionam o modelo escolhido aqui (config do projeto › global › código). Trocar aqui não gera nada.</p>
      <table class="cr-table admin">
        <thead><tr><th>Ação</th><th>Modelo</th><th>Custo</th><th>Origem</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </section>`;
  }

  // ---------- tabela de custo por modelo/resolução ----------
  function costTable() {
    const order = data.kind_order || ["image", "upscale", "video", "audio"];
    const label = data.kind_label || {};
    const groups = order.map((k) => {
      const models = (data.models || []).filter((m) => m.kind === k);
      if (!models.length) return "";
      const rows = models.map((m) => m.rows.map((r, i) => `
        <tr>
          ${i === 0 ? `<td rowspan="${m.rows.length}"><b>${esc(m.label)}</b><span class="cr-mid">${esc(m.id)}</span></td>` : ""}
          <td>${r.variant ? esc(r.variant) : "—"}</td>
          <td class="cr-cost">${esc(r.credits)} cr</td>
          ${i === 0 ? `<td rowspan="${m.rows.length}" class="cr-mnote">${esc(m.note || "")}</td>` : ""}
        </tr>`).join("")).join("");
      return `<h4 class="cr-kind">${esc(label[k] || k)}</h4>
        <table class="cr-table"><thead><tr><th>Modelo</th><th>Variação</th><th>Custo</th><th>Nota</th></tr></thead>
        <tbody>${rows}</tbody></table>`;
    }).join("");
    return `<section class="cr-card"><h3>Custo por modelo e resolução</h3>
      <p class="cr-note">Custo medido em gerações reais (créditos Higgsfield). Consultar custo não gasta crédito — só a geração real gasta.</p>
      ${groups}</section>`;
  }

  // ---------- histórico de gasto ----------
  function historySection() {
    const s = data.summary || { total_credits: 0, count: 0, by_step: [], by_project: [] };
    const byStep = (s.by_step || []).map((r) => `<tr><td>${esc(stepLabel(r.step))}</td><td class="cr-cost">${esc(r.credits)} cr</td><td>${esc(r.count)}×</td></tr>`).join("")
      || `<tr><td colspan="3" class="cr-empty">Nenhum gasto registrado ainda.</td></tr>`;
    const byProj = (s.by_project || []).map((r) => `<tr><td>${esc(r.name || r.pid || "—")}</td><td class="cr-cost">${esc(r.credits)} cr</td><td>${esc(r.count)}×</td></tr>`).join("")
      || `<tr><td colspan="3" class="cr-empty">—</td></tr>`;
    const recent = (data.history || []).slice(0, 30).map((h) => `<tr>
      <td>${esc((h.at || "").replace("T", " ").replace(/(\+00:00|Z)$/, ""))}</td>
      <td>${esc(h.project_name || h.pid || "—")}</td>
      <td>${esc(stepLabel(h.step || h.action))}</td>
      <td>${esc(h.model || "")}${h.variant ? ` · ${esc(h.variant)}` : ""}</td>
      <td class="cr-cost">${h.credits != null ? `${esc(h.credits)} cr` : "—"}</td>
    </tr>`).join("") || `<tr><td colspan="5" class="cr-empty">Sem gerações registradas.</td></tr>`;
    return `<section class="cr-card"><div class="cr-card-head"><h3>Histórico de gasto</h3>
      ${ui.chip(`total ${s.total_credits} cr`, "info")}${ui.chip(`${s.count} gerações`, "mode")}</div>
      ${pid ? `<p class="cr-note">Mostrando o gasto da campanha atual. Abra "Créditos & Custos" sem campanha para o total geral.</p>` : ""}
      <div class="cr-hist-grid">
        <div><h4>Por etapa</h4><table class="cr-table"><thead><tr><th>Etapa</th><th>Créditos</th><th>Ger.</th></tr></thead><tbody>${byStep}</tbody></table></div>
        <div><h4>Por projeto</h4><table class="cr-table"><thead><tr><th>Projeto</th><th>Créditos</th><th>Ger.</th></tr></thead><tbody>${byProj}</tbody></table></div>
      </div>
      <h4>Gerações recentes</h4>
      <div class="cr-hist-scroll"><table class="cr-table"><thead><tr><th>Quando (UTC)</th><th>Projeto</th><th>Etapa</th><th>Modelo</th><th>Custo</th></tr></thead><tbody>${recent}</tbody></table></div>
    </section>`;
  }

  const STEP_LABEL = { base: "Imagem base", mood: "Mood board", storyboard: "Storyboard",
    animate: "Animação", music: "Trilha" };
  function stepLabel(s) { return STEP_LABEL[s] || s || "—"; }

  // ---------- render + eventos ----------
  function render() {
    const main = $main();
    main.innerHTML = `
      <header class="stephead ov">
        <span class="eyebrow">Extensão do Studio · aula 008 (o custo em primeiro lugar)</span>
        <h2>Créditos &amp; Custos <span class="ext">[extensão]</span></h2>
        <p class="lede">Saldo do CLI, quanto cada modelo custa, para onde os créditos foram e qual modelo cada etapa usa por padrão.${pid ? ` Campanha atual: <b>${esc(pid)}</b>.` : ""}</p>
      </header>
      <div class="cr-grid">
        ${balanceCard()}
        ${adminSection()}
        ${costTable()}
        ${historySection()}
      </div>`;

    const refresh = document.querySelector("#crRefresh");
    if (refresh) refresh.onclick = async () => {
      refresh.classList.add("loading"); refresh.disabled = true;
      try { data.balance = await api("/api/creditos/balance?refresh=1"); ui.refreshCredits(false); render(); }
      catch (e) { toast(e.message); refresh.classList.remove("loading"); refresh.disabled = false; }
    };

    main.querySelectorAll("[data-scope]").forEach((b) => { b.onclick = () => { scope = b.dataset.scope; render(); }; });

    // troca de modelo/variação → persiste no escopo atual
    main.querySelectorAll("tr[data-action]").forEach((tr) => {
      const action = tr.dataset.action;
      const kind = tr.dataset.kind;
      const modelSel = tr.querySelector(".cr-model");
      const save = async () => {
        const model = modelSel.value;
        const variantSel = tr.querySelector(".cr-variant");
        const variant = variantSel ? variantSel.value : null;
        try {
          await api(`${base()}/config`, { method: "PUT", body: JSON.stringify({ action, model, variant }) });
          await load(); render();
          toast(`Default de "${action}" salvo (${scope === "project" ? "campanha" : "global"})`);
        } catch (e) { toast(e.message); }
      };
      if (modelSel) modelSel.onchange = () => {
        // se o modelo mudou de família de variação, re-render a célula antes de salvar
        const m = (data.models || []).find((x) => x.id === modelSel.value);
        const cell = modelSel.parentElement;
        const old = cell.querySelector(".cr-variant");
        if (old) old.remove();
        if (m && m.variant_options && m.variant_options.length) cell.insertAdjacentHTML("beforeend", variantOptions(m.id, m.default_variant, tr.dataset.label));
        cell.querySelectorAll(".cr-variant").forEach((v) => { v.onchange = save; });
        save();
      };
      const variantSel = tr.querySelector(".cr-variant");
      if (variantSel) variantSel.onchange = save;
      const clear = tr.querySelector(".cr-clear");
      if (clear && !clear.disabled) clear.onclick = async () => {
        try { await api(`/api/projects/${encodeURIComponent(pid)}/creditos/config/${encodeURIComponent(action)}`, { method: "DELETE" }); await load(); render(); toast("Override do projeto removido"); }
        catch (e) { toast(e.message); }
      };
    });
  }

  window.Studio.creditos = { open };
})();
