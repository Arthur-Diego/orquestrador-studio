// Studio.ui — componentes compartilhados das telas de etapa (wave 2: preparo + shell OS-013).
//
// Carregado ANTES do app.js: cria `window.Studio` se ainda não existir e pendura `ui` nele.
// Cada plugin usa estas funções em vez de recopiar `esc`, chip do CLI, drag&drop, upload,
// confirmação de custo e polling — que antes viviam duplicados em 7 views.
//
// Contrato de tela (wave 2): todo `view.html` começa com `<header class="stephead">` seguido de
// `<section id="guide" class="guide"></section>`; o `view.js` chama `Studio.ui.renderGuide("<id>")`
// em `onProject()` e depois de cada ação que muda artefatos, e devolve `destroy()` parando os
// polls (`app.js` chama `destroy()` ao trocar de tela).
//
// Regra de compatibilidade (OS-013): esta API é consumida pelos 11 plugins — dá para ESTENDER,
// nunca remover nem renomear função existente.
window.Studio = window.Studio || {};

window.Studio.ui = {
  // ---------- texto ----------
  /** Escapa texto para interpolar em HTML. Todo dado vindo da API passa por aqui. */
  esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  },

  /** `0.42 → "42%"` (aceita também 42 quando o valor já vem em porcentagem). */
  fmtPct(x) {
    const v = Number(x) || 0;
    return `${Math.round(v <= 1 ? v * 100 : v)}%`;
  },

  /**
   * HTML de um chip. `kind`: "ok" | "done" | "warn" | "fail" | "blocked" | "todo" | "info" |
   * "in_progress" | "unknown" | "mode" (default). Todos existem em style.css.
   */
  chip(text, kind = "mode") {
    return `<span class="chip ${this.esc(kind)}">${this.esc(text)}</span>`;
  },

  // ---------- CLI da Higgsfield ----------
  /**
   * Preenche `el` com o chip de status do CLI (`/api/higgsfield/status`, cacheado 60 s no
   * backend) e devolve o status — a tela usa `s.logged_in` para habilitar o botão de gerar.
   */
  async hfChip(el) {
    const node = typeof el === "string" ? document.querySelector(el) : el;
    let s = { installed: false, logged_in: false };
    try {
      s = await (await fetch("/api/higgsfield/status")).json();
    } catch (e) {
      if (node) { node.textContent = "CLI: indisponível"; node.className = "chip warn"; }
      return s;
    }
    if (!node) return s;
    if (!s.installed) { node.textContent = "CLI: não instalado"; node.className = "chip warn"; }
    else if (!s.logged_in) { node.textContent = "CLI: sem login (higgsfield auth login)"; node.className = "chip warn"; }
    else { node.textContent = `CLI: ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`; node.className = "chip ok"; }
    return s;
  },

  // ---------- importação de arquivos ----------
  /**
   * Liga drag&drop + "escolha arquivos" em `el` (a classe `over` marca o arraste por cima).
   * Usa o `<input type="file">` que já estiver dentro de `el`; se não houver, cria um oculto.
   */
  drop(el, onFiles) {
    const node = typeof el === "string" ? document.querySelector(el) : el;
    if (!node) return null;
    let input = node.querySelector('input[type="file"]');
    if (!input) {
      input = document.createElement("input");
      input.type = "file"; input.multiple = true; input.hidden = true;
      node.appendChild(input);
    }
    node.addEventListener("dragover", (e) => { e.preventDefault(); node.classList.add("over"); });
    node.addEventListener("dragleave", () => node.classList.remove("over"));
    node.addEventListener("drop", (e) => {
      e.preventDefault(); node.classList.remove("over");
      if (e.dataTransfer && e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
    });
    input.addEventListener("change", (e) => { if (e.target.files.length) onFiles(e.target.files); e.target.value = ""; });
    return input;
  },

  /**
   * POST multipart de arquivos. `extra` = campos adicionais do formulário (ex.: `{kind, ref_id}`).
   * Devolve o JSON da resposta; lança Error com o `detail` da API.
   */
  async upload(url, files, field = "files", extra = {}) {
    const fd = new FormData();
    [...files].forEach((f) => fd.append(field, f));
    Object.entries(extra || {}).forEach(([k, v]) => { if (v !== undefined && v !== null) fd.append(k, v); });
    const r = await fetch(url, { method: "POST", body: fd });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || r.statusText);
    return body;
  },

  // ---------- custo ----------
  /**
   * Mostra o custo estimado antes de gastar créditos (aula 008: custo é o critério principal).
   * `costFn()` devolve `{credits}` / `{total}` / número / null; falha vira "estimativa
   * indisponível" — nunca impede o usuário de decidir. Retorna true se ele confirmou.
   */
  async confirmCost(costFn, label = "Gerar via CLI") {
    let est = "Estimativa de custo indisponível.";
    try {
      const c = await costFn();
      const credits = typeof c === "number" ? c : (c && (c.total ?? c.credits));
      if (credits != null) est = `Estimativa: ${credits} créditos.`;
    } catch (e) { /* mantém indisponível */ }
    return window.confirm(`${label}? ${est} Isso gasta créditos (o ilimitado do plano vale só na UI da Higgsfield).`);
  },

  // ---------- polling ----------
  /**
   * Chama `fn` a cada `ms` até `stop()`, até `fn` devolver `false`, ou até 3 erros seguidos.
   * Sempre guarde o retorno e chame `stop()` no `destroy()` da tela — senão o timer sobrevive
   * à troca de etapa e a tela antiga continua batendo na API.
   */
  poll(fn, ms = 3000) {
    let live = true, fails = 0, timer = null;
    const tick = async () => {
      if (!live) return;
      try {
        const r = await fn();
        fails = 0;
        if (r === false) { live = false; return; }
      } catch (e) {
        if (++fails >= 3) { live = false; return; }
      }
      if (live) timer = setTimeout(tick, ms);
    };
    tick();
    return { stop() { live = false; clearTimeout(timer); } };
  },

  // ---------- modal ----------
  /**
   * Modal acessível: foco preso dentro do diálogo, `Esc` e clique no fundo fecham, o foco volta
   * para quem abriu. `opts = {title, subtitle, html, wide}`. Devolve `{el, close()}` — quem
   * chama liga os botões pelo `el.querySelector(...)`.
   */
  modal({ title, subtitle = "", html = "", onClose } = {}) {
    const prev = document.activeElement;
    const back = document.createElement("div");
    back.className = "modal-backdrop";
    back.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${this.esc(title)}">
      <div class="modal-head">
        <div>
          <h3>${this.esc(title)}</h3>
          ${subtitle ? `<p class="sub">${this.esc(subtitle)}</p>` : ""}
        </div>
        <button class="modal-close" type="button" title="Fechar" aria-label="Fechar">✕</button>
      </div>
      <div class="modal-body">${html}</div>
    </div>`;
    const close = () => {
      if (!back.isConnected) return;
      document.removeEventListener("keydown", onKey, true);
      back.remove();
      if (prev && prev.focus) prev.focus();
      if (onClose) onClose();
    };
    const focusables = () => [...back.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')].filter((n) => !n.disabled && n.offsetParent !== null);
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); close(); return; }
      if (e.key !== "Tab") return;
      const f = focusables();
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    back.addEventListener("mousedown", (e) => { if (e.target === back) close(); });
    back.querySelector(".modal-close").onclick = close;
    document.addEventListener("keydown", onKey, true);
    document.body.appendChild(back);
    const auto = back.querySelector("input, select, textarea, button:not(.modal-close)");
    if (auto) auto.focus();
    return { el: back, close };
  },

  // ---------- painel do guia ----------
  /** Rótulo pt-BR de cada status de etapa. */
  STATUS_LABEL: { todo: "a fazer", blocked: "bloqueada", in_progress: "em andamento", done: "concluída", unknown: "sem guia" },
  /** Rótulo pt-BR de cada status de item (entrada, saída, validação). */
  ITEM_LABEL: { ok: "ok", fail: "falta", todo: "a fazer", warn: "atenção" },
  /** Status da etapa → `kind` do chip (menu, visão geral e painel usam o mesmo mapa). */
  STATUS_KIND: { done: "done", in_progress: "in_progress", blocked: "blocked", todo: "todo", unknown: "unknown" },

  /**
   * Renderiza o painel do guia (`GET /api/projects/{pid}/guide/{step}`) dentro de `el`.
   * O painel é colapsável: o resumo (status, progresso, o que falta e a próxima ação) fica
   * sempre visível; as seções detalhadas abrem e fecham, com o estado guardado por etapa.
   */
  guide(el, g) {
    const node = typeof el === "string" ? document.querySelector(el) : el;
    if (!node) return;
    if (!g) { node.innerHTML = `<div class="empty">Guia indisponível para esta etapa.</div>`; return; }
    const e = (s) => this.esc(s);
    const pct = Math.round((g.progress || 0) * 100);
    const open = this._guideOpen(g.id);
    const missing = g.missing && g.missing.length
      ? `<span class="k">faltando</span><span class="v">${e(g.missing.join(" · "))}</span>`
      : `<span class="k">tudo pronto</span><span class="v">nenhuma entrada ou saída pendente nesta etapa</span>`;

    const secs = [];
    if (g.what) secs.push(this._section("O que fazer nesta etapa", `<p class="guide-what">${e(g.what)}</p>`));
    if (g.detail) secs.push(this._section("Aviso", `<p class="fine mono">${e(g.detail)}</p>`));
    if (g.inputs && g.inputs.length) secs.push(this._section("Entradas (vêm de outras etapas)", this._items(g.inputs)));
    if (g.outputs && g.outputs.length) secs.push(this._section("Saídas (o que esta etapa produz)", this._items(g.outputs)));
    if (g.validations && g.validations.length) secs.push(this._section("Validações da aula", this._items(g.validations)));
    if (g.checklist && g.checklist.length) {
      secs.push(this._section("Checklist da aula", `<ul class="guide-check">${g.checklist.map((c) =>
        `<li><label><input type="checkbox"> <span>${e(c)}</span></label></li>`).join("")}</ul>`));
    }
    if (g.next_action) {
      const btn = g.next_step ? `<button class="ghost" data-go="${e(g.next_step)}">Ir para a etapa seguinte</button>` : "";
      secs.push(this._section("Próxima ação", `<div class="row wrap"><p class="guide-next">${e(g.next_action)}</p>${btn}</div>`));
    }

    node.innerHTML = `<div class="guide-body" data-open="${open ? 1 : 0}">
      <div class="guide-head">
        <button class="guide-toggle" type="button" aria-expanded="${open}">
          <span class="caret">▾</span>
          <span class="ttl">Guia da etapa ${e(g.n)}</span>
          ${this.chip(`aula ${g.aula}`, "mode")}
          ${this.chip(this.STATUS_LABEL[g.status] || g.status, this.STATUS_KIND[g.status] || "mode")}
          ${this.chip(`${pct}%`, "mode")}
          <span class="hint">${open ? "recolher" : "abrir"}</span>
        </button>
        <div class="progress${g.status === "done" ? " ok" : ""}"><div class="bar" style="width:${pct}%"></div></div>
        <div class="guide-missing${g.missing && g.missing.length ? "" : " all-ok"}">${missing}</div>
        ${g.next_action ? `<p class="guide-pin">→ ${e(g.next_action)}</p>` : ""}
      </div>
      <div class="guide-sections">${secs.join("")}</div>
    </div>`;

    const body = node.querySelector(".guide-body");
    const toggle = node.querySelector(".guide-toggle");
    toggle.onclick = () => {
      const now = body.dataset.open !== "1";
      body.dataset.open = now ? "1" : "0";
      toggle.setAttribute("aria-expanded", String(now));
      toggle.querySelector(".hint").textContent = now ? "recolher" : "abrir";
      this._guideOpen(g.id, now);
    };
    node.onclick = (ev) => {
      const b = ev.target.closest("[data-go]");
      if (b && window.Studio.go) window.Studio.go(b.dataset.go);
    };
  },

  /** Busca e renderiza o guia da etapa `stepId` no `#guide` da tela (ou em `el`). */
  async renderGuide(stepId, el) {
    const node = (typeof el === "string" ? document.querySelector(el) : el) || document.querySelector("#guide");
    const pid = window.Studio.ctx && window.Studio.ctx.pid();
    if (!pid) {
      if (node) node.innerHTML = `<div class="empty">Sem campanha selecionada — crie uma campanha para ver o guia desta etapa.</div>`;
      return null;
    }
    try {
      const r = await fetch(`/api/projects/${encodeURIComponent(pid)}/guide/${encodeURIComponent(stepId)}`);
      if (!r.ok) throw new Error(((await r.json().catch(() => ({}))).detail) || r.statusText);
      const g = await r.json();
      if (node) this.guide(node, g);
      // Avisa o shell: o menu, a barra de progresso e a visão geral refletem a mudança.
      if (window.Studio.onGuide) window.Studio.onGuide(stepId, g);
      return g;
    } catch (err) {
      if (node) node.innerHTML = `<div class="empty">Não foi possível carregar o guia: ${this.esc(err.message)}</div>`;
      return null;
    }
  },

  // ---------- internos ----------
  /** Lê (ou grava, quando `set` vem) o estado colapsado do painel de guia da etapa. */
  _guideOpen(stepId, set) {
    const key = `studio.guide.${stepId}`;
    try {
      if (set === undefined) return localStorage.getItem(key) !== "0";
      localStorage.setItem(key, set ? "1" : "0");
    } catch (e) { /* localStorage bloqueado: o painel só não lembra do estado */ }
    return set !== false;
  },
  _statusKind(status) {
    if (status === "done" || status === "ok") return "ok";
    if (status === "blocked" || status === "fail") return "fail";
    if (status === "warn") return "warn";
    return "mode";
  },
  _section(title, html) {
    return `<section class="guide-sec"><h4>${this.esc(title)}</h4>${html}</section>`;
  },
  _items(items) {
    const e = (s) => this.esc(s);
    return `<ul class="guide-items">${items.map((it) => {
      const mark = it.status === "ok" ? "✓" : it.status === "fail" ? "✕" : it.status === "warn" ? "!" : "·";
      const fix = it.fix
        ? `<span class="guide-fix">${e(it.fix)}${it.step ? ` <button class="link" data-go="${e(it.step)}">ir para a etapa</button>` : ""}</span>`
        : (it.step ? `<span class="guide-fix"><button class="link" data-go="${e(it.step)}">ir para a etapa</button></span>` : "");
      return `<li class="it ${e(it.status)}"><span class="mark" title="${e(this.ITEM_LABEL[it.status] || it.status)}">${mark}</span>
        <span class="body"><span class="lbl">${e(it.label)}</span>${it.detail ? `<span class="det">${e(it.detail)}</span>` : ""}${fix}</span></li>`;
    }).join("")}</ul>`;
  },
};
