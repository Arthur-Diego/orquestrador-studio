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
//
// Wave 3 (redesign, ADH-OS-20260826-02) — helpers ADITIVOS de marcação, para que as telas não
// recopiem o HTML das classes do shell (nada foi removido ou renomeado):
//   Studio.ui.tile({src, badge, term, up, upOk, sel, ord, wide, sq, id, title, cls})
//       → `div.card` da galeria. `src` = URL da imagem, `badge` = `span.src` (origem),
//         `term` = legenda mono da base, `up`/`upOk` = selo "upscalado 2x"/"sem upscale",
//         `ord` = número da ordem (o check do tile selecionado vira o número, etapa 5).
//   Studio.ui.pipe(estados, {lg, titles})
//       → `div.pipe` segmentado (um `i` por etapa; classes done/in_progress/blocked/todo).
//   Studio.ui.beats(lista, {sm, cuts})
//       → `div.beats` (barras de batida; `{h, imp, title}` ou número 0..1;
//         `cuts` = `[{at, off, title}]` com o marcador ▾ dos cortes).
//   Studio.ui.copyBtn(alvo, label)
//       → `button.link` "Copiar". `alvo` = texto literal ou seletor CSS do campo a copiar;
//         o clique é tratado por um listener único (toast "copiado" + `.ok` irmão).
//
// Wave 4 (fidelidade ao protótipo, ADH-OS-20260826-10) — também ADITIVO:
//   Studio.ui.autosize(el)
//       → `textarea` de altura automática (fallback de `field-sizing:content`): mede o
//         `scrollHeight` no 1º render e a cada `input`. Aceita elemento, seletor ou lista.
//   Studio.ui.modal({title, subtitle, html, actions})
//       → o `actions` novo monta a linha `.modal-actions` (ghost/primary `.lg`) e devolve os
//         botões em `m.actions`; sem `actions` o modal continua exatamente como era.
//   Studio.ui.drop(el, onFiles)
//       → já aceitava qualquer elemento; a wave 4 documenta o uso com o PAINEL inteiro como
//         alvo (`.panel.over`), que é o que o protótipo desenha (sem dropzone visível).
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
      if (node) { node.textContent = "● CLI · indisponível"; node.className = "chip warn"; }
      return s;
    }
    if (!node) return s;
    // Texto do protótipo: `● CLI · <plano> · <N> créditos` (bolinha e `·`, sem dois-pontos).
    // Os estados de erro, que o protótipo não desenha, mantêm o mesmo prefixo.
    if (!s.installed) { node.textContent = "● CLI · não instalado"; node.className = "chip warn"; }
    else if (!s.logged_in) { node.textContent = "● CLI · sem login (higgsfield auth login)"; node.className = "chip warn"; }
    else { node.textContent = `● CLI · ${s.plan || "logado"} · ${s.credits ?? "?"} créditos`; node.className = "chip ok"; }
    return s;
  },

  // ---------- importação de arquivos ----------
  /**
   * Liga drag&drop + "escolha arquivos" em QUALQUER elemento (`label.drop`, `.panel`, `.card`…):
   * a classe `over` marca o arraste por cima — `.drop.over` e `.panel.over` têm regra no CSS.
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

  /**
   * Altura automática de `textarea` (fallback de `field-sizing:content`, que ainda não existe
   * em todos os navegadores). Chame depois de preencher o valor; o listener de `input` mantém
   * a altura enquanto o usuário digita. `alvo` = elemento, seletor CSS ou lista de elementos.
   */
  autosize(alvo) {
    const nodes = typeof alvo === "string"
      ? [...document.querySelectorAll(alvo)]
      : (alvo && alvo.length !== undefined && !alvo.tagName ? [...alvo] : [alvo]);
    nodes.filter(Boolean).forEach((el) => {
      const ajusta = () => { el.style.height = "auto"; el.style.height = `${el.scrollHeight}px`; };
      if (!el.dataset.autosize) { el.dataset.autosize = "1"; el.addEventListener("input", ajusta); }
      ajusta();
    });
    return nodes[0] || null;
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
   * para quem abriu. `opts = {title, subtitle, html, actions, onClose}`; `html` aceita conteúdo
   * arbitrário (galeria, formulário, lista). `actions` (wave 4) é a lista de botões do rodapé:
   * `[{label, kind: "ghost"|"primary", close: true, onClick(m)}]` — vira `.modal-actions` com
   * `.ghost.lg`/`.primary.lg`. Devolve `{el, close(), actions}` (os nós dos botões criados).
   */
  modal({ title, subtitle = "", html = "", actions = null, onClose } = {}) {
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
      <div class="modal-body">${html}${(actions && actions.length)
        ? `<div class="modal-actions">${actions.map((a, i) =>
          `<button type="button" class="${a.kind === "primary" ? "primary" : "ghost"} lg" data-act="${i}">${this.esc(a.label)}</button>`).join("")}</div>`
        : ""}</div>
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
    const ref = { el: back, close, actions: [] };
    (actions || []).forEach((a, i) => {
      const b = back.querySelector(`.modal-actions [data-act="${i}"]`);
      if (!b) return;
      ref.actions.push(b);
      b.onclick = () => {
        if (a.onClick) a.onClick(ref);
        if (a.close !== false) close();
      };
    });
    return ref;
  },

  // ---------- painel do guia ----------
  /** Rótulo pt-BR de cada status de etapa. */
  STATUS_LABEL: { todo: "a fazer", blocked: "bloqueada", in_progress: "em andamento", done: "concluída", unknown: "sem guia" },
  /** Rótulo pt-BR de cada status de item (entrada, saída, validação). */
  ITEM_LABEL: { ok: "ok", fail: "falta", todo: "a fazer", warn: "atenção" },
  /** Status da etapa → `kind` do chip (menu, visão geral e painel usam o mesmo mapa). */
  STATUS_KIND: { done: "done", in_progress: "in_progress", blocked: "blocked", todo: "todo", unknown: "unknown" },

  /**
   * Renderiza o guia da etapa dentro de `el`, em um dos dois estados:
   * - colapsado (PADRÃO, wave 4) → faixa compacta `.guide-strip`: "GUIA", chip de status, chip
   *   de %, chip extra opcional (`g.summary`, com a cor de `g.summary_kind`) e a próxima ação.
   *   A faixa inteira é clicável e expande;
   * - expandido → `.guide-body[data-open="1"]`: cabeçalho clicável (`.guide-toggle`, caret,
   *   chips, "recolher"), a linha de estado (`.guide-missing`), UMA grade `.guide-items.checks`
   *   com a união de entradas + saídas + validações, e a linha de ações.
   * O estado é guardado por etapa em `studio.guide.<id>` (fechado por padrão — o protótipo
   * desenha a faixa compacta em 10 das 11 telas; ver shell-redesign-fdd §10.5).
   */
  guide(el, g) {
    const node = typeof el === "string" ? document.querySelector(el) : el;
    if (!node) return;
    if (!g) { node.innerHTML = `<div class="empty">Guia indisponível para esta etapa.</div>`; return; }
    const e = (s) => this.esc(s);
    const pct = Math.round((g.progress || 0) * 100);
    const open = this._guideOpen(g.id);
    const chipStatus = this.chip(this.STATUS_LABEL[g.status] || g.status, this.STATUS_KIND[g.status] || "mode");
    const chipPct = (g.status === "in_progress" || g.status === "done") ? this.chip(`${pct}%`, "mode") : "";
    // O chip extra ("1/6 shots prontos", "portfólio 1/4 vídeos") pode pedir cor de atenção.
    const chipExtra = g.summary ? this.chip(g.summary, g.summary_kind || "mode") : "";
    const proxima = g.next_action ? `<span class="guide-next">→ ${e(g.next_action)}</span>` : "";
    const ligar = () => {
      node.onclick = (ev) => {
        const b = ev.target.closest("[data-go]");
        if (b && window.Studio.go) window.Studio.go(b.dataset.go);
      };
    };

    if (!open) {
      node.innerHTML = `<button class="guide-strip" type="button" aria-expanded="false">
        <span class="eyebrow sm">Guia</span>
        ${chipStatus}${chipPct}${chipExtra}${proxima}
      </button>`;
      node.querySelector(".guide-strip").onclick = () => { this._guideOpen(g.id, true); this.guide(node, g); };
      ligar();
      return;
    }

    // Linha de estado: "falta …" ou "tudo pronto", com o resumo da etapa quando ele existir.
    const resumo = g.summary ? ` · ${e(g.summary)}` : "";
    const missing = g.missing && g.missing.length
      ? `<span class="k">faltando</span><span class="v">${e(g.missing.join(" · "))}${resumo}</span>`
      : `<span class="k">tudo pronto</span><span class="v">nenhuma entrada ou saída pendente nesta etapa${resumo}</span>`;

    // Uma grade só, na ordem do protótipo: entradas, saídas e validações no mesmo `ul.checks`.
    // `what`, `detail`, o checklist e os títulos de seção não são desenhados (o texto de aula
    // continua no `guide.py` e nos `details.lesson` das telas que o protótipo tem).
    const itens = [...(g.inputs || []), ...(g.outputs || []), ...(g.validations || [])];
    const grade = itens.length ? this._items(itens) : "";
    const alvo = (window.Studio.steps || []).find((s) => s.id === g.next_step);
    const acoes = g.next_action
      ? `<div class="guide-actions"><p class="guide-next">→ Próxima ação: ${e(g.next_action)}</p>${
        g.next_step ? `<button class="ghost" data-go="${e(g.next_step)}">Ir para a etapa ${e(alvo ? alvo.n : "seguinte")}</button>` : ""}</div>`
      : "";

    node.innerHTML = `<div class="guide-body" data-open="1">
      <button class="guide-toggle" type="button" aria-expanded="true">
        <span class="caret">▾</span>
        <span class="ttl">Guia da etapa ${e(g.n)}</span>
        ${chipStatus}${chipPct}${chipExtra}
        <span class="hint">recolher</span>
      </button>
      <div class="guide-sections">
        <div class="guide-missing${g.missing && g.missing.length ? "" : " all-ok"}">${missing}</div>
        ${grade}${acoes}
      </div>
    </div>`;

    node.querySelector(".guide-toggle").onclick = () => { this._guideOpen(g.id, false); this.guide(node, g); };
    ligar();
  },

  // ---------- helpers de marcação (aditivos, wave 3) ----------
  /** HTML de um tile `.card` da galeria — ver o cabeçalho deste arquivo para os campos. */
  tile(o = {}) {
    const e = (s) => this.esc(s);
    const cls = ["card"];
    if (o.sel) cls.push("sel");
    if (o.wide) cls.push("wide");
    if (o.sq) cls.push("sq");
    if (o.cls) cls.push(o.cls);
    const attrs = `${o.id !== undefined ? ` data-id="${e(o.id)}"` : ""}${o.ord ? ` data-ord="${e(o.ord)}"` : ""}` +
      `${o.title ? ` title="${e(o.title)}"` : ""} tabindex="0"`;
    return `<div class="${cls.join(" ")}"${attrs}>` +
      `${o.src ? `<img src="${e(o.src)}" loading="lazy" alt="">` : ""}` +
      `${o.badge ? `<span class="src">${e(o.badge)}</span>` : ""}` +
      `${o.term ? `<span class="term">${e(o.term)}</span>` : ""}` +
      `${o.up ? `<span class="up${o.upOk ? " ok" : ""}">${e(o.up)}</span>` : ""}</div>`;
  },

  /** HTML do pipeline segmentado (`.pipe`): um `i` por etapa, com a classe do status. */
  pipe(estados, o = {}) {
    const t = o.titles || [];
    return `<div class="pipe${o.lg ? " lg" : ""}">${(estados || []).map((s, i) =>
      `<i class="${this.esc(s || "todo")}"${t[i] ? ` title="${this.esc(t[i])}"` : ""}></i>`).join("")}</div>`;
  },

  /** HTML da régua de batidas (`.beats`): `{h, imp, title}` ou número 0..1; `cuts` = marcadores ▾. */
  beats(lista, o = {}) {
    const barras = (lista || []).map((b) => {
      const v = typeof b === "number" ? { h: b } : (b || {});
      const bruto = v.h == null ? 40 : (v.h <= 1 ? v.h * 100 : v.h);
      const alt = v.imp ? 100 : Math.max(8, Math.min(100, Math.round(bruto)));
      return `<i class="${v.imp ? "imp" : ""}" style="height:${alt}%"${v.title ? ` title="${this.esc(v.title)}"` : ""}></i>`;
    }).join("");
    const cortes = (o.cuts || []).map((c) => {
      const v = typeof c === "number" ? { at: c } : (c || {});
      return `<span class="cut${v.off ? " off" : ""}" style="left:${Number(v.at) || 0}%"${
        v.title ? ` title="${this.esc(v.title)}"` : ""}>▾</span>`;
    }).join("");
    return `<div class="beats${o.sm ? " sm" : ""}">${barras}${cortes}</div>`;
  },

  /**
   * HTML de um `button.link` "Copiar". `alvo` = texto literal ou seletor CSS do campo cujo
   * conteúdo será copiado. O clique é tratado pelo listener único do fim deste arquivo.
   */
  copyBtn(alvo, label = "Copiar") {
    const seletor = typeof alvo === "string" && /^[#.[]/.test(alvo.trim());
    const attr = seletor ? `data-copy-from="${this.esc(alvo)}"` : `data-copy="${this.esc(alvo == null ? "" : alvo)}"`;
    return `<button type="button" class="link copy" ${attr}>${this.esc(label)}</button>`;
  },

  /** Copia `texto` para a área de transferência (com fallback para navegadores sem permissão). */
  async copy(texto) {
    const t = String(texto == null ? "" : texto);
    try {
      await navigator.clipboard.writeText(t);
      return true;
    } catch (e) {
      const ta = document.createElement("textarea");
      ta.value = t; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
      ta.remove();
      return ok;
    }
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
  /**
   * Lê (ou grava, quando `set` vem) o estado do painel de guia da etapa.
   * Wave 4: sem chave salva o guia nasce FECHADO (faixa compacta) — é o que o protótipo
   * desenha em 10 das 11 telas. O estado continua lembrado por etapa.
   */
  _guideOpen(stepId, set) {
    const key = `studio.guide.${stepId}`;
    try {
      if (set === undefined) return localStorage.getItem(key) === "1";
      localStorage.setItem(key, set ? "1" : "0");
    } catch (e) { /* localStorage bloqueado: o painel só não lembra do estado */ }
    return set === true;
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
  /**
   * Grade de itens do guia: só marca + rótulo, como no protótipo. O detalhe e a dica de
   * correção viram `title` (tooltip) — nada de sublinha nem de link por item.
   */
  _items(items) {
    const e = (s) => this.esc(s);
    return `<ul class="guide-items checks">${items.map((it) => {
      const mark = it.status === "ok" ? "✓" : it.status === "fail" ? "✕" : it.status === "warn" ? "!" : "·";
      const dica = [it.detail, it.fix].filter(Boolean).join(" — ");
      return `<li class="it ${e(it.status)}"${dica ? ` title="${e(dica)}"` : ""}>` +
        `<span class="mark" title="${e(this.ITEM_LABEL[it.status] || it.status)}">${mark}</span>` +
        `<span class="lbl">${e(it.label)}</span></li>`;
    }).join("")}</ul>`;
  },
};

// Listener único do `Studio.ui.copyBtn`: qualquer botão com `data-copy` (texto literal) ou
// `data-copy-from` (seletor do campo) copia e dá o retorno visual — toast "copiado" e, quando o
// botão tem um `.ok` irmão, o "copiado ✓" por 1,5 s (mesmo padrão das telas da wave 2).
document.addEventListener("click", (ev) => {
  const alvo = ev.target && ev.target.closest ? ev.target.closest("[data-copy],[data-copy-from]") : null;
  if (!alvo) return;
  let texto = alvo.dataset.copy || "";
  if (alvo.dataset.copyFrom) {
    const n = document.querySelector(alvo.dataset.copyFrom);
    texto = n ? (n.value !== undefined ? n.value : n.textContent) : "";
  }
  window.Studio.ui.copy(texto).then((ok) => {
    const eco = alvo.parentElement && alvo.parentElement.querySelector(".ok");
    if (eco) { eco.textContent = ok ? "copiado ✓" : "copie à mão"; setTimeout(() => { eco.textContent = ""; }, 1500); }
    if (window.Studio.ctx && window.Studio.ctx.toast) window.Studio.ctx.toast(ok ? "copiado" : "não foi possível copiar");
  });
});
