# Recon — Wave 10 · migração integral do frontend para React

> Estado compartilhado das 11 frentes (E0…E10). Fontes lidas listadas no fim.
> Base: `develop` @ `7b6f3b7`. `docs/plano/plano-migracao-react.md` está **não commitado** no working tree; `docs/domains/studio/waves/wave-10.md` e `docs/domains/studio/diagrams/mermaid/wave-10-dependencias.md` **já estão commitados**.

---

## 0. Correções ao que já está escrito (ler antes de tudo)

1. **`wave-10.md` §E2 erra a superfície de `Studio.ui`.** A lista `… pipe · beats · snap · zoom · tlHeight · js` inclui quatro nomes que **não existem** em `window.Studio.ui`:
   - `snap`, `zoom`, `tlHeight` são campos do objeto **persistido** `editor.ui` dentro de `projects/<pid>/edit/timeline.json`, acessados no `edit/view.js` como `ed().ui.zoom`, `ed().ui.snap`, `ed().ui.tlHeight` (`studio/etapas/edit/view.js:759, 1526, 1549, 1918, 1934`; `UI_SIZES = { tlHeight:[345,150,700], leftW:[236,180,420], rightW:[280,220,460] }` na linha 864). São **estado de domínio da etapa 8**, não biblioteca de UI. E9 os porta; E2 **não**.
   - `js` é ruído de match sobre a string `"ui.js"`.
   A lista da E2 também **omite** `fmtPct`, `guide`, `STATUS_LABEL`, `ITEM_LABEL`, `STATUS_KIND` e o listener global de `data-copy`. A superfície real e completa está na §2 deste recon.
2. **A correção de dependência E6→E8 do `wave-10.md` está certa**: `studio/etapas/storyboard/view.js` tem zero ocorrências de `multishot`; o único consumidor de `window.Studio.multishot` é `studio/web/moodboards.js:252,256`.
3. **Existem duas guardas de diff em pytest que reprovam qualquer branch que toque `studio/web/*`** — elas quebram E2, E3, E6 e E10 por construção. Detalhe na §7.3. Isso não está registrado em nenhum documento da wave.
4. Numeração ambígua: o comentário do `ci.yml:17-20` já usa "wave 10" para se referir à wave de features anterior (as frentes 03/04 que estouraram o timeout). Ao escrever ADR/retro, qualificar sempre como "Wave 10 — migração React".

---

## 1. Arquitetura vigente do frontend (contrato shell ↔ plugin de etapa)

Fonte: `docs/domains/studio/hld.md` §Componentes (linhas 55, 59-61, 63-73), `studio/web/app.js`, `studio/web/index.html`, `studio/etapas/__init__.py`, `studio/app.py:205-226`.

### 1.1 Como o HTML nasce

`studio/app.py` monta três coisas:
- `app.mount("/static", StaticFiles(directory=WEB_DIR))` → serve `index.html`, `app.js`, `ui.js`, `style.css`, `ui.css`, `multishot.js`, `moodboards.js`, `creditos.js`, `annotate.js`.
- `GET /` → `FileResponse(WEB_DIR/"index.html")` (`studio/app.py:226`).
- `GET /steps/{step_id}/{asset}` com `asset ∈ {"view.html","view.js"}` (`studio/app.py:205-216`) → o par de arquivos do plugin. **Esta é a única rota de backend que a E10 remove.**

`index.html` (88 linhas) é casca estática: `.app > aside.side + .workspace(header.topbar + main#main)` + `#toast` fora do `.app`. Os scripts vêm nesta ordem fixa, **e a ordem é contrato testado**:

```html
<script src="/static/ui.js"></script>       <!-- cria window.Studio = {}; Studio.ui = {...} -->
<script src="/static/app.js"></script>      <!-- Object.assign(window.Studio, {register, go, onGuide, ctx}) -->
<script src="/static/multishot.js"></script><!-- IIFE: const ui = window.Studio.ui  (linha 27) -->
<script src="/static/moodboards.js"></script><!-- IIFE: const ui = window.Studio.ui (linha 9)  -->
<script src="/static/creditos.js"></script> <!-- IIFE: const ui = window.Studio.ui  (linha 10) -->
```

`tests/test_api.py:129-131` e `tests/test_steps_and_config.py:45-46` afirmam a ordem `style.css < ui.css` e `ui.js < app.js`.

### 1.2 O objeto `window.Studio` — superfície exata

Montado em duas etapas (`ui.js:50-52` cria; `app.js:57-76` faz `Object.assign`):

| Membro | Onde nasce | Assinatura | Semântica |
| --- | --- | --- | --- |
| `Studio.ui` | `ui.js:52` | objeto | biblioteca de UI (§2) |
| `Studio.register(id, factory)` | `app.js:58` | `(string, (ctx) => instance) => void` | o `view.js` da etapa se registra. Guarda em `factories[id]`. **Chamado no load do script, uma vez por sessão.** |
| `Studio.go(target)` | `app.js:60-62` | `(string) => void` | navega para etapa ou `"overview"`. Só navega se `target === "overview" || factories[target] || readySteps.has(target)`. |
| `Studio.onGuide(stepId, g)` | `app.js:64-67` | `(string, Guide) => void` | callback que `Studio.ui.renderGuide` invoca. Grava `guideById[stepId]`, chama `recomputeOverview()`, `renderMenu()`, `renderTopbar()` e agenda `scheduleGuideRefresh()` (debounce 400 ms). |
| `Studio.steps` | `app.js:606` | `Step[]` de `/api/steps` | catálogo publicado em leitura para o `ui.guide` montar "Ir para a etapa N". |
| `Studio.ctx` | `app.js:68-75` | objeto | contexto do plugin (abaixo) |
| `Studio.multishot` | `multishot.js:221` | `{open(opts)}` | componente ADR-017 |
| `Studio.moodboards` | `moodboards.js:400` | `{open(mbid), goList(), goEditor(mbid)}` | área global ADR-013 |
| `Studio.creditos` | `creditos.js:230` | `{open(pid)}` | área global ADR-016 |
| `Studio.annotate` | `annotate.js:189` | `{open(opts)}` | canvas de marcação; **injetado sob demanda** (§6.4) |

`Studio.ctx` (`app.js:68-75`) — é isto que cada tela recebe:

```js
ctx = {
  $,                                     // (sel) => document.querySelector(sel)
  api,                                   // (path, opts) => Promise<json>; !r.ok → throw Error(body.detail || statusText)
  toast,                                 // (msg) => escreve em #toast, remove .hidden, re-esconde em 3200 ms
  pid:     () => pid,                    // string | null
  project: () => project || projects.find(p => p.id === pid) || null,
  files:   (path) => `/files/${pid}/${path}`,
  guide:   () => window.Studio.ui.renderGuide(currentStep),
}
```

`api` (`app.js:17-21`) manda **sempre** `Content-Type: application/json`, inclusive em GET. O client tipado da E1 tem de reproduzir isso e o mapeamento de erro `detail → Error.message`.

### 1.3 Ciclo de vida `init / onProject / destroy`

`showView(id)` em `app.js:349-370` é a sequência inteira:

1. `destroyCurrent()` — chama `instances[currentStep].destroy()` dentro de `try/catch` (tela quebrada não impede a troca), zera `currentStep`, zera `$("#main").onclick`.
2. `fetch('/steps/<id>/view.html')` → `main.innerHTML = await r.text()`. **O HTML entra antes do JS.**
3. Se `!loaded.has(id)`: injeta `<script src="/steps/<id>/view.js">` em `document.body`, aguarda `onload`, marca `loaded`. Nas visitas seguintes **o script não é recarregado** — o módulo do plugin executa uma única vez por sessão.
4. `ensureGuideSlot(main)` — se não há `#guide`, cria `<section id="guide" class="guide">` logo após `header.stephead` (ou como primeiro filho de `#main`).
5. `injectStepReset(main, id)` — **o shell** injeta `<button class="shell-reset ghost">Resetar etapa [extensão]</button>` no `header.stephead`. Nenhum `view.html` conhece esse botão (ADR-010).
6. `currentStep = id; instances[id] = factories[id](ctx); instances[id].init();`
7. `Studio.ui.renderGuide(id)` — primeiro render do painel de guia.

Erro em qualquer passo → `main.innerHTML = '<div class="empty">Não foi possível abrir esta etapa: …</div>'` + `toast(err.message)` + `currentStep = null`.

**`onProject` não é chamado por `showView`.** A interface real devolvida pelas fábricas é `{init, onProject?, destroy?}`; `onProject` é convenção documentada no `ui.js:8-10` e no HLD, mas o único disparo de re-render por troca de projeto hoje é a remontagem completa via `applyRoute` → `showView`. **A E3 precisa decidir explicitamente se mantém `onProject` no contrato do host React** (o `wave-10.md` §E3 promete `init/onProject/destroy`) — hoje ele é vestigial.

### 1.4 Roteamento

`parseHash()` (`app.js:79-82`): regex `^#\/([^/]+)(?:\/([^/]+))?\/?$` → `{pid, view}` (view default `"overview"`).

Gramática completa e ordem de resolução em `applyRoute()` (`app.js:91-146`):
1. `#/moodboards` / `#/moodboards/<mbid>` → `area="moodboards"`, `destroyCurrent()`, `view=null`, `Studio.moodboards.open(mbid)`. **Tratado ANTES do check de campanhas** — funciona sem nenhuma campanha.
2. `#/creditos` → `area="creditos"`, `Studio.creditos.open(pid)`. Idem.
3. `projects.length === 0` → `renderNoProject()` (empty-state com `#btnFirst`).
4. `pid` inválido/ausente → fallback `localStorage["studio.pid"]` → `projects[0].id`; se o hash era vazio, `view` cai em `localStorage["studio.view"] || "overview"`; `navigate(..., {replace:true})`.
5. `view !== "overview" && !readySteps.has(view)` → redireciona para `overview` com `replace`.
6. Troca de projeto → limpa `project/guideAll/guideById`, `await loadProjectState()`.
7. `view === "overview"` → `destroyCurrent(); renderOverview()`; senão `await showView(view)`.

`MB_ROUTE="moodboards"` e `CR_ROUTE="creditos"` são **prefixos reservados** — `create_project` no backend recusa esses ids.

**Chaves de `localStorage` (contrato de usuário, inventário completo):**

| Chave | Onde | Valores |
| --- | --- | --- |
| `studio.theme` | `index.html:13` (pré-paint) + `app.js:568-573` | `auto` \| `light` \| `dark` |
| `studio.pid` | `app.js:126,135` | id do projeto |
| `studio.view` | `app.js:127,135` | `overview` \| id de etapa |
| `studio.guide.<stepId>` | `ui.js:719-726` | `"1"` \| `"0"` (default **fechado**) |
| `studio.edit.sideHidden` | `edit/view.js:842-848` | `"1"` \| `"0"` |

Tema: `index.html` aplica `document.documentElement.dataset.theme` **antes do primeiro paint**, dentro de `try/catch`. A E3 tem de manter isso como script inline no `index.html` do Vite — um `useEffect` pisca.

### 1.5 Regra de extensão (HLD §63-73 + ADR-010)

Etapa nova cria **só** `studio/etapas/<id>/` (+ `studio/<id>/service.py`). Nunca edita `app.py`, `steps.py`, `config.py`, `higgsfield.py`, `etapas/__init__.py`, `studio/web/*`. Precedente vivo: `annotate.js` foi **criado** (não editado) por uma frente de etapa na wave 9 (HLD linhas 88-91). A E0 tem de reafirmar essa invariante para `etapas/<id>/ui/index.tsx` + `import.meta.glob`.

---

## 2. Superfície completa de `studio/web/ui.js` (E2 — nada pode faltar)

768 linhas. Tudo o que é público está em `window.Studio.ui`. **28 membros + 1 listener global.**

### 2.1 Membros públicos

| # | Membro | Assinatura | O que faz | Telas que consomem |
| --- | --- | --- | --- | --- |
| 1 | `esc(s)` | `(any) => string` | escapa `&<>"'` para HTML | **15/15** — animate, base, edit, export, mood, music, prospect, publish, refs, storyboard, moodboards, creditos, multishot, annotate, app |
| 2 | `fmtPct(x)` | `(number) => string` | `0.42→"42%"`; aceita 42 | **nenhuma** — dead code, mas `tests/test_api.py:210` exige `fmtPct(` no fonte |
| 3 | `chip(text, kind="mode")` | `(string, string) => string` | `<span class="chip {kind}">`; kinds `ok/done/warn/fail/blocked/todo/info/in_progress/unknown/mode` | music, moodboards, creditos, app (+ uso interno em `guide`) |
| 4 | `hfChip(el)` | `(el\|sel) => Promise<status>` | preenche o chip de status do CLI Higgsfield a partir de `/api/higgsfield/status`; textos exatos: `● CLI · não instalado`, `● CLI · sem login (higgsfield auth login)`, `● CLI · <plan> · <credits> créditos`, `● CLI · indisponível` | animate, storyboard, app (`#hfChipSide`) |
| 5 | `drop(el, onFiles)` | `(el\|sel, (FileList)=>void) => HTMLInputElement\|null` | liga drag&drop + input file em **qualquer** elemento; adiciona/remove classe `over`; reusa `input[type=file]` existente ou cria um oculto; zera `e.target.value` após change | animate, base, edit, music, refs, storyboard, moodboards, multishot |
| 6 | `upload(url, files, field="files", extra={})` | `(…) => Promise<json>` | POST multipart; `throw new Error(body.detail \|\| r.statusText)` | animate, edit, music, refs, storyboard, moodboards, multishot |
| 7 | `autosize(alvo)` | `(el\|sel\|list) => el\|null` | altura automática de `<textarea>` via `scrollHeight`; marca `dataset.autosize="1"` e liga listener de `input` uma vez | base, storyboard, moodboards |
| 8 | `confirmCost(costFnOrOpts, label="Gerar via CLI")` | `=> Promise<boolean>` | **dois modos**: função → modal simples; objeto `{action,pid,count,label,step}` → cost sheet rica (modelo, custo unitário, quantidade, total, saldo atual, saldo depois, aviso de CLI deslogado/não instalado) | animate, base, storyboard, multishot |
| 9 | `_confirmCostSimple(costFn, label)` | privado | modo legado do 8 | — |
| 10 | `_confirmGeneration({action,pid,count,label,step})` | privado | modo ADR-016 do 8; consulta `/api/projects/{pid}/creditos/cost?action=` ou `/api/creditos/cost?action=` | — |
| 11 | `_confirmModal({title,label,bodyHtml})` | privado | `Promise<boolean>` sobre `modal()`, subtítulo fixo `"Custo antes de gerar (aula 008)"`, ações `Cancelar`(ghost)/`<label>`(primary), `onClose → false` | — |
| 12 | `defaultModel(action, pid)` | `=> Promise<{model?,variant?}>` | resolve modelo default da ação (projeto › global › código, ADR-016) | animate, creditos |
| 13 | `refreshCredits(refresh=true)` | `=> Promise<status>` | atualiza **todo** `[data-credits-chip]` do documento a partir de `/api/creditos/balance`; textos `● CLI · não instalado`, `● CLI · sem login`, `● <n> créditos`; escreve `title` | creditos, app (+ chamado automaticamente por `progressJob`) |
| 14 | `poll(fn, ms=3000)` | `=> {stop()}` | loop até `stop()`, até `fn()` devolver `false`, ou 3 erros seguidos | animate, export, prospect, refs (+ interno em `progressJob`) |
| 15 | `modal({title,subtitle,html,actions,onClose})` | `=> {el, close, actions[]}` | modal acessível: `.modal-backdrop > .modal[role=dialog][aria-modal=true][aria-label=title]`, `.modal-head>h3 + p.sub`, `.modal-close`, `.modal-body`, `.modal-actions > button.(ghost\|primary).lg[data-act=i]`. **Focus trap** com Tab/Shift+Tab, `Escape` fecha, `mousedown` no backdrop fecha, foco volta ao `activeElement` anterior, autofoco no primeiro `input/select/textarea/button:not(.modal-close)`. `a.close !== false` fecha após `onClick` | animate, edit, storyboard, moodboards, multishot, annotate, app |
| 16 | `progress({title,subtitle})` | `=> handle` | modal `.modal.progress-modal` com cronômetro `mm:ss` (`.prog-timer`), `<ol class="prog-steps" aria-live="polite">`, `.prog-note[hidden]`, e `.modal-close` **`disabled` até `ok()`/`fail()`**. Handle: `.step(label)` `.ok(label?)` `.fail(msg)` `.note(html)` `.count(d,t)` `.close()` `.el`. Estados por `li.prog-step[data-state=active\|done\|error]` com `.prog-ico` `✓`/`✗` e `.prog-count` | base, storyboard, moodboards |
| 17 | `progressJob({title,subtitle,start,jobUrl,done,label,ms=2000})` | `=> Promise<job>` | `progress` + `poll` sobre `{state,done,total,log[]}`; cada linha nova do `log` vira `.step()`; `done/total` vira `.count()`; resolve em `state==="done"`, rejeita em `"error"`; 5 falhas de fetch → `fail("Sem resposta do servidor.")`; ao terminar chama `refreshCredits()` e fecha em 900 ms | animate, base, edit, export, music, prospect, refs, storyboard, multishot (**9 consumidores — o mais crítico**) |
| 18 | `STATUS_LABEL` | mapa | `{todo:"a fazer", blocked:"bloqueada", in_progress:"em andamento", done:"concluída", unknown:"sem guia"}` | app (+ interno) |
| 19 | `ITEM_LABEL` | mapa | `{ok:"ok", fail:"falta", todo:"a fazer", warn:"atenção"}` | interno (`_items`) |
| 20 | `STATUS_KIND` | mapa | `{done:"done", in_progress:"in_progress", blocked:"blocked", todo:"todo", unknown:"unknown"}` | app (+ interno) |
| 21 | `guide(el, g)` | `(el\|sel, Guide) => void` | dois estados: compacto `button.guide-strip[aria-expanded=false]` (eyebrow "Guia", chip de status, chip de %, chip extra `g.summary`, `span.guide-next`) × expandido `div.guide-body[data-open="1"]` com `button.guide-toggle[aria-expanded=true]` (`.caret ▾`, `.ttl`, chips, `.hint "recolher"`), `.guide-sections > .guide-missing[.all-ok] (.k/.v)`, `ul.guide-items.checks`, `.guide-actions`. Estado por etapa em `studio.guide.<id>`. Delegação: clique em `[data-go]` → `Studio.go` | interno de `renderGuide` |
| 22 | `tile(o)` | `({src,badge,term,up,upOk,sel,ord,wide,sq,id,title,cls}) => string` | `div.card[data-id][data-ord][title][tabindex=0]` + `img[loading=lazy]` + `span.src` + `span.term` + `span.up[.ok]` | animate, base, moodboards |
| 23 | `moodMosaic(urls, {max=4,title})` | `=> string` | grade 2×2 `div.mood-mosaic[data-n]` de `span.mm-cell > img`, selo `.mm-more +N` na última; vazio → `.mood-mosaic.empty[role=img] > .mm-empty "sem imagens ainda"`; título opcional `span.mm-title.eyebrow` | base, mood, moodboards |
| 24 | `pipe(estados, {lg,titles})` | `=> string` | `div.pipe[.lg] > i.<status>[title]` | prospect (+ app usa `pipeHtml` próprio, **não** este helper) |
| 25 | `beats(lista, {sm,cuts})` | `=> string` | `div.beats[.sm] > i[.imp][style=height:N%]` + `span.cut[.off][style=left:N%] ▾` | music |
| 26 | `copyBtn(alvo, label="Copiar")` | `=> string` | `button.link.copy` com `data-copy` (literal) ou `data-copy-from` (seletor CSS, detectado por `/^[#.[]/`) | moodboards |
| 27 | `copy(texto)` | `=> Promise<boolean>` | `navigator.clipboard.writeText` com fallback `<textarea>` + `execCommand("copy")` | storyboard |
| 28 | `renderGuide(stepId, el?)` | `=> Promise<Guide\|null>` | busca `/api/projects/{pid}/guide/{stepId}`, renderiza em `el` ou `#guide`, e **avisa `window.Studio.onGuide(stepId, g)`**. Sem pid → `div.empty "Sem campanha selecionada…"`. Erro → `div.empty "Não foi possível carregar o guia: …"` | animate, base, edit, export, prospect, publish, storyboard, app |

Privados restantes: `_guideOpen(stepId, set?)`, `_statusKind(status)` (**dead code**), `_section(title, html)` (**dead code**), `_items(items)` (grade `ul.guide-items.checks > li.it.<status>[title] > span.mark + span.lbl`, marcas `✓ ✕ ! ·`).

### 2.2 Listener global (`ui.js:755-768`) — fácil de esquecer

`document.addEventListener("click", …)` em nível de módulo: qualquer `[data-copy]`/`[data-copy-from]` no documento inteiro copia, escreve `"copiado ✓"`/`"copie à mão"` num `.ok` **irmão** por 1500 ms e dispara `ctx.toast("copiado")`. Em React isto vira um handler no root do app ou um `<CopyButton>`; se virar componente, **todo** markup que hoje emite `data-copy` cru precisa ser convertido junto.

### 2.3 Contrato de tela imposto pelo `ui.js` (cabeçalho, linhas 7-10)

Todo `view.html` começa com `<header class="stephead">` seguido de `<section id="guide" class="guide"></section>`; o `view.js` chama `Studio.ui.renderGuide("<id>")` em `onProject()` e após cada ação que muda artefatos; e devolve `destroy()` parando os polls.

---

## 3. Contrato DOM por tela (o oráculo)

382 casos Playwright em 14 telas (`scripts/qa/cenarios/*.py`, 8.256 LOC). **A regra da wave: os cenários passam sem uma linha editada.** Abaixo, os seletores que cada cenário usa — é exatamente o que o DOM React precisa emitir.

### 3.0 Contrato global (vale nas 14 telas — `scripts/qa/harness.py`)

| Seletor / condição | Onde no harness | Exigência |
| --- | --- | --- |
| `#main` | `esperar_tela` (l.241) | precisa sair do texto `Carregando…` — `wait_for_function` sobre `textContent` |
| `.modal[role=dialog]` (`.last`) | `modal()` (l.271) | todo modal, inclusive o de progresso |
| `.modal-close` | `fechar_modal` (l.277), `esperar_progresso` (l.340) | `disabled` enquanto o job corre; habilita ao terminar |
| `.modal-backdrop` | `fechar_modal` (l.287) | removível pelo DOM como último recurso |
| `.modal[role=dialog] .prog-steps` / `.prog-steps li` / `.prog-note` | `esperar_progresso` (l.336-351), `observar_progresso` (l.675) | lista de passos observável por `MutationObserver` |
| `.cost-sheet`, `.modal-actions button` | `modal_com`/`confirmar_custo` (l.623-631) | folha de custo e botões do rodapé |
| `#toast` | `toast()` (l.299), `esperar_toast` (l.301) | precisa ficar **visível** (`is_visible`) e ter `textContent`; limpado por `evaluate` (l.642) |
| `#main header.stephead` | `shell.py` C-SHELL-02/10 | toda tela de etapa |
| `#main header.stephead .shell-reset` | `shell.py` C-SHELL-10 | injetado pelo shell |
| `#main #guide` | `export.py`, `prospect.py` | slot do guia |
| `button/a[href]/[role=button]` sem nome acessível | `AUDIT_JS` (l.474-477) | **zero** botões sem `aria-label`/`title`/texto |
| `input:not([hidden]):not([type=file])`, `select`, `textarea` sem label | `AUDIT_JS` (l.479-483) | precisa `label[for]`, ancestral `<label>`, `aria-label`, `aria-labelledby`, `placeholder` ou `title` |
| overflow horizontal, imagem quebrada, controle coberto por overlay, texto cortado | `AUDIT_JS` | zero, em **claro e escuro**, a 1440 e 900 px |
| console/pageerror/HTTP 4xx-5xx | `sonda.snapshot()` | zero em toda auditoria e todo caso |
| requests da tela anterior 6 s após trocar de etapa | `timer_orfao` (l.547-557) | **zero timers órfãos** — o `destroy()` do React tem de parar polls |
| `set_input_files(seletor)` | `H.upload` (l.573) | precisa existir `input[type=file]` alcançável pelo seletor |
| `DataTransfer` + `dragenter/dragover/drop` em `querySelector(sel)` | `soltar_arquivos` (l.694-712) | os handlers têm de estar no **elemento**, não só via React synthetic em ancestral |
| `page.mouse` down/move×12/up | `arrastar` (l.750-760) | drag por ponteiro real (timeline, resizers) |
| rota | `Ctx.rota` (l.94-103) | `shell`/`overview` → `#/<pid>/overview`; `moodboards` → `#/moodboards[/<sub>]`; `creditos` → `#/creditos`; demais → `#/<pid>/<tela>` |

### 3.1 `shell` — 15 casos (E3)

`#steps li` · `#steps li.ready` · `#steps li.ready[data-id='<id>']` (com `dataset.id`, `tabindex`, focável, Enter/Espaço navegam) · `#main header.stephead` · `#main header.stephead .shell-reset` · `#btnNewProj` · `#btnEditCamp` · `#btnTheme` · `#themeLabel` · `#btnContinue` · `#btnResetCamp` · `#tbName` · `#tbCount` · `#projSel` · `#projSel option[value='<pid>']` · `#hfChipSide` · `#cfName` · `#cfProduct` · `label:has(input[name=aspect][value='9:16'])` (o radio é oculto por CSS — o clique é no `<label>`) · `button[type=submit]` · `.modal-actions button.primary, .modal-actions button[data-act]` · `#main`.
Invariantes extras: `localStorage['studio.theme']` e `document.documentElement.dataset.theme` ciclam `auto→light→dark`; `#tbCount` contém `"<done>/<total>"`; `#/nao-existe/overview` cai na 1ª campanha; `#/<pid>/etapa-que-nao-existe` cai em `overview`.

### 3.2 `overview` — 5 casos (E3)

`#main .ovgrid > *` (contagem == nº de etapas do guia) · `#main .ovgrid [data-go]` · `#main .ovgrid [data-go]:not([disabled])` · `#main .ov-summary .chip` (texto começa com número; somam o total de etapas) · `#main` (inner_text contém `"etapa 1"`) · `#projSel` (`select_option`) · `#tbName`.

### 3.3 `mood` — 18 casos (E4)

`#btnApplyBoard` · `#mbCount` · `#mbGrid .card` · `#mbGrid .card[data-mb='<mbid>']` · `#mbGrid .card.sel` · `#mbGrid .card .term` · `#mbGrid .empty` · `#moodVibe` · `#moodGallery img` · `#moodGallery .empty` · `#moodGallery .mood-mosaic .mm-cell` · `#palette span[title]` · `#palette .lbl` · `#btnSwap` · `#btnManageBoards` · `#btnGoLibEmpty` · `#main h2` · `#main .panel .panel-head h3` · `#main input[type=file]` · ausência de `#btnMbOpenFolder, #btnMoodGen, #btnMoodPrompt`.

### 3.4 `publish` — 21 casos (E4)

`#pubVideo` + `#pubVideo option` · `#pubNetwork` · `#pubNetworks option` · `#pubUrl` · `#pubDate` · `#pubNote` · `#btnPubAdd` · `#pubLog .pub-row` · `#pubLog .pub-row[data-id='<id>'] .nt` · `… input.nt-edit` · `… button.del` · `#pubLog .empty` · `#pubComChip` · `#pubCommunity input[data-com='posted'\|'commented']` + `label:has(...)` · `#main input:not([type=hidden]), #main select`.

### 3.5 `export` — 21 casos (E4)

`#btnRenderAll` · `#expMaster` · `#expFormats .fmt-card` · `#expFormats .fmt-card[data-fmt='<f>'] button.open` · `… button.render` · `… .chip.sm` · `… .ex-box img` · `#expFormats .ex-box[data-fmt='<f>']` · `#expFormats .ex-box[data-fmt='9x16']` · `#expFormats button.render` · `#expFfmpeg` · `#expLog` · `#expProgress` · `#btnQa` · `#expQa .checks.qa .it` · `#expQa .it .mark` · `#expQa .it .lbl` · `#guide` · `.modal[role=dialog] .prog-steps` · `.modal-head h3` · `.modal-close` · `#main [data-act='reframe'], #main button:has-text('reframe'), #main button:has-text('Reenquadrar')`.

### 3.6 `music` — 19 casos (E4)

`#btnMusStory` · `#musStoryVideo` · `#musStoryChip` · `#musStoryPlay` · `#btnMusStoryCheck` · `#musBeatsChip` · `#musCounts` · `#musRuler .beats i` · `#musRuler .beats i.imp` · `#musList .track-row` · `.track-row[data-id='<cid>']` · `#musList label.drop` · `#musList audio` (via `querySelectorAll`) · `#musUpload` · `button.play` · `button.pick` · `.nm` · `.mt` · `.wave` · `.chip.ok` · `input[name=musClosed][value='0'|'1']` + `label:has(...)` + `:checked` · `.modal.progress-modal` + `.modal-close` · `#main button`.

### 3.7 `prospect` — 28 casos (E5)

`#btnNewLead` · `#newLeadPanel` · `#leadForm button[type=submit]` · `#leadForm input:invalid` · `#lfBusiness` · `#lfHandle` · `#lfWhy` · `#lfSegment` · `#lfRole` · `#lfPostRef` · `#gateChip` · `#gatePanel` · `#gateMsg` · `#gatePipe .seg, #gatePipe > *` · `#todayChip` · `#leadList .lead-row[data-id='<lid>']` · `#leadList .empty` · `.lead-biz` · `.lead-biz .nm` · `.chip.xs` · `.body` · `.body button[data-act]` · `.body video` · `button[data-open='<lid>']` · `button[data-act='teaser'|'call'|'replied'|'copy'|'sent'|'copyfollow'|'del']` · `input[data-call='<lid>']` · `input[data-note='<lid>']` · `label:has(input[data-done='<lid>'])` · `pre.script` · `#pitchBox` · `#pitchBox .end` · `#pitchValues input[data-pitch='<etapa>']` · `#pitchValues [data-pitch-total]` · `#pitchValues .pitch-table .tr` · `#pitchValues .total .v` · `#btnPitchSave` · `#btnPitchCopy` · `#main #guide` · `#main #gatePanel`.

### 3.8 `refs` — 27 casos (E5)

`#terms` · `#brand` · `#brandSaved` · `#btnSaveBrand` · `#btnSuggest` · `#btnSearch` · `#btnSave` · `#btnBring` · `#btnLogin` · `#loginState` · `#counts` · `#maxPer` · `#headed` + `label.inline:has(#headed)` · `#scrapeCount` · `#gallery .card` · `#gallery .card.sel` · `#gallery .card .src` · `#gallery .card .term` · `#gallery .empty` · `#refsPick` · `[data-bring]` · `#refsFilters` · `#refsFilters .rf-fgroup` · `#refsFilters .rf-flabel` · `#refsFilters .rf-clear` · `#refsFilters input[data-filter]` · `#refsFilters input[data-filter]:checked` · `#refsFilters input[data-filter=term][value='qa termo a']` · `#refsFilters input[data-filter=source][value='upload']` · `.modal[role=dialog]`.

### 3.9 `animate` — 37 casos (E5)

`#anReload` · `#anShots .shot-row` · `#anShots .empty` · `.shot-row[data-k='<k>']` · `.nm` · `.thumb` + `.thumb img` · `.takes .note` · `.take.an-like` + `.take.an-like span` · `.take.empty.an-gen` · `.take .an-rej` · `.an-gen` · `.an-prompt` · `.an-model` + `.an-model option` · `.an-mode` · `.an-endrow` · `.an-end option` · `.an-suggest` · `.an-duration` · `.an-count` · `.an-camera` · `.an-action` · `.an-example` · `.an-tips li` · `.an-play` · `.an-x` · `label:has(.an-slow)` · `label:has(.an-black)` · `#anCandCount` · `#anGallery .card` · `#anHfState` · `#anBtnDownloads` · `#anBtnHistory` · `#anDrop` · `.modal.progress-modal` + `.modal-close` + `.prog-err` + `.prog-steps li` · `.modal-actions button.primary`/`.ghost` · `.modal-head h3` · `.modal-body span.chip` · `.modal .sub` (via `querySelector`).

### 3.10 `moodboards` — 31 casos (E6)

`#btnNewBoard` · `#main .mb-grid .mb-card` · `#main .mb-card[data-mb='<mbid>']` · `#main .mb-grid, #main .empty-state` · `#main .stephead, #main .empty-state` · `#main section.panel` · `#mbBack` · `#mbTitle` · `#mbName` · `#mbNote` · `#mbFolder` · `#mbCounts` · `#mbPalette span[title]` · `#mbGallery` + `#mbGallery .msc-card` + `#mbGallery .empty` · `#mbImported .msc-card` + `.use-btn` + `.ms-btn` · `#mbImpCount` · `#btnMbSave` · `#btnMbRename` · `#btnMbDelete` · `#btnMbDownloads` · `#btnMbHistory` · `#btnMbOpenFolder` · `#btnMbGenPrompt` · `#mbPromptList textarea` · `#mbMode` + `#mbMode option` · `#mbInstruction` · `#mbClaude` · `#mbNoPeople` + `label:has(#mbNoPeople)` · `#msGen` · `#msCount` · `#msImport` · `#msImpDrop` · `#msImpDl` · `#msImpPath` · `.ms-source img` · `.msc-count` · `.msc-remove` · `input[name=name]` · `input[name=vibe]` · `button[type=submit]` · `.modal[role=dialog] .cost-sheet` · `.modal-actions [data-act='0'\|'1']`.

### 3.11 `creditos` — 20 casos (E6)

`#main h2` · `#main .cr-saldo b` · `#main .cr-balance .chip` · `#main .cr-card-head .chip` · `#main .cr-note` · `#main .cr-kind` · `#main .cr-card:has(.cr-kind) .cr-table` · `#main .cr-table.admin tbody tr` · `#main .cr-table.admin select` · `#main .cr-table.admin .cr-model` · `#main .cr-table.admin .cr-cost` · `#main tr[data-action='<acao>']` · `.cr-model` + `.cr-model option` · `.cr-variant` · `.cr-cost` · `.cr-src .chip` · `.cr-clear` / `#main .cr-clear` · `#main .cr-scope` + `[data-scope='<nome>']` + `.seg-btn` + `#main .seg-btn[data-scope='global'\|'project']` · `#main .cr-hist-grid table` · `#main .cr-hist-scroll` + `tbody tr` · `#crRefresh` + `#crRefresh:not(.loading)` · `[data-credits-chip]` · `#topbar` · `#btnCredits` · `#btnCreditos`.

### 3.12 `base` — 33 casos (E7)

`#basePrompts textarea` · `#basePrompts .eyebrow` · `#basePrompts .prompt` · `#basePrompts .prompt .ok` · `#basePrompts button.copy` · `#basePrompts .empty` · `#btnPrompt` · `#btnPromptNoBias` · `#promptInstruction` · `#baseClaude` · `#btnBaseSelect` · `#btnBaseCli` · `#baseCliCost` · `#btnBasePanel01Cli` · `#basePanel01CliCost` · `#btnBaseDownloads` · `#btnBaseHistory` · `#baseChain [data-step]` + `[data-step=situation]` + `[data-step=label]` + `[data-step=upscale]` + `#baseChain .st.on` · `#refGallery .card` + `.card.sel` + `#refGallery img` · `#baseRefHero img` · `#baseGallery .card` + `.card .src` · `#baseFinalCard .bs-final` + `.chip` · `#baseGenResult .pair` · `#baseJunction` + `.bs-fuse .bs-fuse-thumb` + `.bs-fuse-out` + `.bs-fuse-mood .mm-cell` + `.mm-cell img` + `.swatches .sw` · `#baseProvenance details.bs-prov-det` + `summary` + `.prov-line` + `.bs-chip` · `#brandName` · `#brandDesc` · `#btnBrand` · `#moodSource` + `option` · `.modal.progress-modal .prog-steps` (+ `.prog-step` via `querySelectorAll`) · `.modal-actions button` · `.modal[role=dialog]` · `#main`.

### 3.13 `storyboard` — 51 casos (E8) — a maior superfície

Ideação/cenas: `#sbKind` + `option` · `#sbText` · `#sbBase` · `#sbInstruction` · `#sbPreset` · `#sbMinutes` · `#sbCounts` · `#sbCopy` + `#sbCopied` · `#sbGen1` · `#sbGen4` · `#sbSave` · `#sbAdd` · `#sbRender` · `#sbDrop` · `#sbIdeas > input[type=file]` + `#sbIdeas button` · `#sbGallery .card` · `#sbReorder` + `.sb-reorder .sb-ro-item` + `.sb-ro-up` · `#sbBtnDownloads` · `#sbBtnHistory` · `#btnPrompts` · `#sceneTitle`.
Cenas: `#sbScenes .scene-row` · `#sbScenes .scene-row[data-sid='<sid>']` · `… .sb-photorow` · `… textarea.sbTxt` · `.scene-row .mom` · `.sbDel`.
Fotos por cena: `.sb-photorow` · `.sb-pick` · `.sb-key.primary` + `.sb-photorow .sb-key.primary` + `.sb-key img` · `.sb-star` · `.sb-rm` · `.sbPhotoUp` / `.sbPhotoDown` · `.sb-lightbox-media`.
Vídeo por cena: `.sbAnim` · `.sbVidDesc` · `.sbVidPrompt` + `.sbVidPromptText` + `.sbVidPromptBox` · `.sbVidModel` · `.sbVidDur` + `option` · `.sbVidMode` · `.sbVidPair` · `.sbVidEnd option` · `video.sbVidPlayer` · `.sb-anim-preview img`.
Ângulos/shots: `#sceneList [data-scene]` + `[data-scene='cena01']` + `[data-scene='cena01'].cur` + `[data-scene-base='cena02']` + `.upcount` + `#sceneList [data-scene='cena01'] .upcount` + `#sceneList .shProdClear` · `#shotsCounts` · `#shotsGallery .card` + `.card.sel` + `button.asBase` · `#shotsPrompts` + `.txt` + `.prompt` + `.eyebrow` + `button.copy` + `.ok` · `#shotsPalette span` · `#shotsUpscaled` · `#btnShotsSave` · `#promptKind` · `#promptSubject` · `#promptScale` · `#promptAngle` · `#promptEdits` · `#editsBox` · `#shBaseCampaign` · `#shBaseScene` · `#shBaseDrop` · `#scenePanel button, #shotsGallery button`.
Modais: `.modal.progress-modal` · `.modal-head h3` · `.modal-close` · `.prog-note` · `.prog-err` · `.modal-actions button.primary`/`.ghost` · `.modal[role=dialog] .modal-actions button.primary`.

### 3.14 `edit` — 56 casos (E9) — a mais imperativa

Header/global: `#edBack` · `#edSave` · `#edSaveBtn` · `#edAuto` · `#edUndo` · `#edRedo` · `#edFull` · `#edGuide` · `#edAspect` · `#edRes` · `#edFps` · `#edExport` · `#edProps` + `#edProps h4` · `#edStage` · `#edTimeline` · `#edPanel` · `#edRail`.
Rail/painéis: `#edRail button` + `#edRail button[data-panel='<p>']` + `.on` · `#edPanel .ved-phead h4` · `#edPanel .ved-row[data-uid]` + `.rn` + `[data-del]` · `#edPanel .ved-row[data-t='title'\|'subtitle'\|'cta']` · `#edPanel .ved-row[data-el='circle']` · `#edPanel [data-tr='Fade'\|'Glitch'\|'Zoom']` · `#edPanel [data-ef='Blur']` + `.on` · `#edPanel [data-fl='mono']` · `#edPanel [data-el='rect']` · `#edPanel [data-aud^='lib:']` · `#edPanel .ved-row` (via `querySelectorAll`).
Mídia: `#mSearch` · `#mList .ved-mcard[data-cid]` + `:visible` + `[data-mid]` + `.mv2` · `#mUpload` · `#mReset` · `#mMute` + `.on`.
Legendas: `#capGen` · `#capScript` · `#capPreset option` · `#capHi` · `button:not(#capGen):not([data-del])`.
Timeline: `#edRuler .mk` · `#edTlHeads .ved-thead .tn` · `#edTlHeads .ved-thead[data-tid='v1'] button[data-act='vis']` · `#edTlHeads .ved-thead[data-tid='t_txt'] button[data-act='lock']` · `.ved-lane[data-tid='v1'\|'v2'\|'t_txt'\|'t_cap'\|'t_sfx'\|'t_mus'] .ved-clip[data-uid]` · `.ved-lane[data-tid='v1'] .ved-trans` · `.ved-clip[data-uid='<uid>']` + `.sel` + `.cl-name` + `.cl-trim.r` · `#edTimeline .zoom .zp` · `#zOut` · `#tSel` · `#tMark` · `#tRipple` · `#tSplit` · `#tDup` · `#tDel` · `#tSnap`.
Player: `#pcPlay` · `#pcPrev` · `#pcNext` · `#pcStart` · `#pcEnd` · `#pcLoop` + `.on` · `#pcMute` · `#pcVol` · `#pcTime`.
Stage: `#edStage .ved-layer.text` / `.overlay` / `.caption` · `#edStage .ved-layer.overlay video` · `#edStage .ved-cliplabel` · `#edStage audio[data-sfx]` (via `querySelectorAll`) · `video` (via `querySelectorAll`).
Props: `#edProps [data-tab='basico'\|'video'\|'audio'\|'speed'\|'ajustes']` · `#edProps .ved-tabs button` · `#edProps [data-at='muted']` + `.on` · `#edProps [data-sp='2']` + `.on` · `#bFx` · `#cReset` · `#txSh` · `#txUp` · `#trT option` · `#pLoud` · `#sfxUp`.
Export/menu: `#exRes button` + `[data-res='720p']` + `[data-on]` · `#exFps button` + `[data-fps='24 fps']` · `#exQ button` + `[data-q='baixa']` · `#vedMenu` + `#vedMenu button` · `.modal .prog-steps` · `.modal-actions button[data-act='0'\|'1']` · `.modal-head h3` · `.modal-body`.

---

## 4. ADRs vigentes — o que a migração toca

Todos os 30 ADRs em `docs/adrs/generated/` estão com status **Aceito/Aceita**; nenhum superseded ainda. Mapeamento por impacto:

| ADR | Status | O que impõe | Ação da wave |
| --- | --- | --- | --- |
| **ADR-001** monolito single-process, loopback, sem auth | Aceito | "o frontend é **SPA estática vanilla (HTML/CSS/JS, sem framework, sem bundler, sem etapa de build)**", servido pelo mesmo processo; driver explícito "iteração rápida no frontend **sem pipeline de build**" | **EMENDA obrigatória na E0.** A decisão de arquitetura de rede (single-process/loopback) **permanece** e a migração não a contraria: nada de segundo runtime servindo a UI, o `dist/` é servido pelo mesmo `/static`. Mas a caracterização "sem bundler, sem build" e o driver de iteração deixam de valer — o ADR novo cita ADR-001 e emenda esse trecho. **Não** é supersede integral. |
| **ADR-004** fidelidade ao roteiro do curso | Aceito | todo texto visível é conteúdo de aula; desvio silencioso é proibido | **Citação + gate.** Diff de `textContent` == vazio é o critério 5. Nenhum ADR novo. É o ADR que proíbe "aproveitar a migração para melhorar a tela". |
| **ADR-006** jobs em thread + estado em memória + polling | Aceita | driver escrito: "**Frontend vanilla JS sem framework**: polling HTTP simples evita gerenciar conexões persistentes… sem uma camada de estado de UI para suportá-las" | **Emenda de nota na E0 ou E1.** O driver cai (agora há camada de estado: TanStack Query), mas a **decisão** (polling, sem WS/SSE) fica intacta. `usePoll`/`progressJob` continuam polling. Registrar que o driver mudou sem mudar a decisão — senão o próximo leitor acha que WS virou opção. |
| **ADR-008** testes sem rede/navegador, CI ruff+pytest | Aceito | CI sem navegador; timeout apertado; fakes | **Emenda na E0.** Ganha o job `frontend` (npm ci, `tsc --noEmit`, vitest, build, guarda de dist). Vitest+Testing Library rodam em jsdom → **continuam sem navegador real**, então a decisão não é contrariada; o que muda é "só ruff+pytest". Cuidado com o teto de 20 min do `ci.yml` (já elevado de 10). |
| **ADR-010** guia por leitura pura + núcleo editável só por preparo/shell | Aceito | (a) prontidão vem **sempre** de `GET /api/projects/{pid}/guide`; frontend nunca calcula. (b) tela **nunca** edita `studio/web/*`. (c) etapa nova cria só a sua pasta. Motivador escrito: "**Teste de frontend com Node/Playwright contraria a ADR-008**" | **ADR novo ou emenda formal na E0** — é o ADR mais tocado. Reafirmar (a) e (c) para `etapas/<id>/ui/index.tsx` + `import.meta.glob`; reescrever (b) para o novo endereço do núcleo (`frontend/src/**`); revogar o motivador sobre teste de frontend com Node (Vitest passa a existir). **E as duas guardas de diff em pytest que materializam (b) precisam ser reescritas — ver §7.3.** |
| **ADR-017** componente reutilizável de multishot | Aceito | ponto 2: "**Componente de frontend reutilizável (`studio/web/multishot.js`, `Studio.multishot.open`)**" — um modal único | **Emenda de endereço na E6.** O componente continua existindo e reutilizável; muda de `studio/web/multishot.js` + global `Studio.multishot` para componente React compartilhado. Nota no ADR (não supersede — a decisão é "existe um componente único", não "ele é um IIFE global"). |
| ADR-013 biblioteca global de mood boards | Aceito | rota `#/moodboards[/<mbid>]` reservada, campanha-independente | Citação (E3 roteador, E6). |
| ADR-016 créditos/custos/modelo default por ação | Aceito | `confirmCost` rico, `[data-credits-chip]`, rota `#/creditos` reservada | Citação (E2 `confirmCost`/`refreshCredits`/`defaultModel`, E6). |
| ADR-025, ADR-027, ADR-028 (×2), ADR-029, ADR-030 | Aceito | comportamento das telas 4 e 8 | Citação; E8/E9 não podem alterar comportamento. **Atenção: existem dois ADR-028 distintos** no mesmo diretório (`…-roteiro-do-storyboard-le-as-fotos-escolhidas…` e `…-roteiro-por-cena-fotos-inferidas…`) — colisão de numeração preexistente; a E0 não deve reusar o número 028 nem "consertar" isso dentro da wave. |
| ADR-002, 003, 005, 007, 009, 011, 012, 014, 015, 018-024, 026 | Aceito | backend / método do curso | Nenhum impacto (a wave não toca `service.py`/`router.py`/`guide.py`). |

**Nenhum ADR precisa de supersede integral.** O padrão correto é: 2 ADRs novos (React+Vite com build & `dist/` versionado; plugin de UI = `ui/index.tsx`) que **emendam** ADR-001 (§stack), ADR-006 (driver), ADR-008 (job Node) e ADR-010 (endereço do núcleo + revogação do motivador anti-Node), e **citam** ADR-004 como gate.

---

## 5. Catálogo de classes CSS — o contrato com as telas

Fonte normativa: `docs/domains/studio/features/shell-redesign-fdd.md` §5 (linhas 139-226), espelhado no HLD linhas 206-225. Asserts em `tests/test_api.py::test_shell_preserva_as_classes_que_as_telas_de_etapa_usam` (l.192) e `::test_shell_redesign_traz_o_pipeline_segmentado_e_o_catalogo_de_classes` (l.217) e `::test_wave4_tokens_e_catalogo_de_classes_do_shell` (l.249).

### 5.1 O que o contrato diz

Três contratos formais:
1. **Tokens de tema** — custom properties em `:root` (claro), `@media (prefers-color-scheme:dark) :root:not([data-theme="light"])` e `:root[data-theme="dark"]`. Superfícies `--bg/-2/--surface/-2/-3`, tinta `--ink..--ink-5`, `--ink-row`, linhas `--line/-2/--ctl/--ctl-hover`, accent `--accent/-hover/-ink/-soft/-soft-2/-line/-line-2`, semânticas `--ok/--gate/--fail/--info` (+`-soft`, `-line`), efeitos `--glow-cta/--glow-card/--ring/--ring-sel/--stripes/--topbar-bg/--scrim/--shadow-modal/--caret`, escala `--s1..--s10`, raios `--r-chip/--r-sm/--r/--r-tile/--r-panel/--r-modal`, e **aliases da wave 2 que não podem sumir**: `--code-bg`, `--sel`, `--shadow-1/2`, `--r1..--r4`, `--fs-*`, `--side-w`. O FDD é explícito: "as três strings testadas existem literalmente e sem espaços" — reformatar o CSS quebra assert (é o Risco 2 do próprio FDD, §10 l.328).
2. **Catálogo de classes** — 11 grupos: Texto, Controles, Shell, Guia, Visão geral, Painéis, Mídia, Prompt, Linhas, Específicos, Chips/avisos, Modal. Regra: **o shell pode acrescentar, nunca renomear**.
3. **`Studio.ui` (JS)** — "só estender"; lista preservada + aditivos + `window.Studio.steps`.

### 5.2 Está completo e atualizado?

**Sim para o shell; parcialmente para as telas — e isso é declarado.**

- O FDD registra a lição da wave 3 (l.147-156): o catálogo nasceu antes das telas, **8 lacunas** apareceram, foram contornadas com `<style>` escopado e depois **promovidas** ao `style.css`. A wave 4 promoveu mais **11 regras** (HLD l.150). Duas eram bugs de especificidade (`.palette .lbl` perdendo para `.palette.sm>span`; `input.mini` perdendo para `.inline input[type=number]`) — a solução foi regra extra `.inline input.mini`/`.ctl input.mini`. **Se a E2 "limpar" o CSS ao portar, essas duas regras somem e dois bugs visuais voltam.**
- O que **sobra escopado por design** e não está no catálogo (FDD l.154-156): `.rf-why`, `.md-side`, `.md-path`, `.bs-io`, `.bs-imp`, `.bs-chain-state`, `.sb-base`, `.sh-wrapchip`, `.sh-scene-id`, `.sh-basethumb`, `.sh-scene-text`, `.sh-subhead`, `.an-*`, `.mu-*`, `.ed-*`, `.ex-*`, `.pb-*`, `.pr-*`. Hoje isso vive em `<style>` dentro do `view.html` de cada tela — **9 dos 10 `view.html` têm um bloco `<style>`** (`music` é o único sem):

  | tela | linhas de `<style>` |
  | --- | --- |
  | edit | **315** |
  | base | 113 |
  | storyboard | 110 |
  | refs | 21 |
  | publish | 16 |
  | animate | 13 |
  | prospect | 10 |
  | export | 9 |
  | mood | 8 |

  Esses blocos **não são realmente escopados** — hoje são "descartados" só porque `main.innerHTML = ...` remove o `<style>` junto ao trocar de tela. **Em React, CSS importado é global e permanente: sem CSS Modules / `:where(.escopo)` haverá vazamento entre telas.** É a lacuna mais concreta do catálogo para esta wave.
- O catálogo **não** documenta as classes do modal de progresso (`.progress-modal`, `.prog-timer`, `.prog-steps`, `.prog-step[data-state]`, `.prog-ico`, `.prog-lbl`, `.prog-count`, `.prog-note`, `.prog-err`) — elas nasceram depois (ADH-OS-20260827-06) e só aparecem no `ui.css` e nos asserts de `test_progress_modal.py`. Nem as do mosaico (`.mood-mosaic`, `.mm-cell`, `.mm-more`, `.mm-empty`, `.mm-title`) além de uma menção no HLD. **A E2 deve promovê-las ao catálogo ao portar.**
- `.course`/`.course-body` aparecem na tabela do HLD (linha 218) mas `tests/test_api.py:190` **exige que `.course` NÃO exista no CSS** (a wave 4 removeu o painel). O HLD está desatualizado nesse ponto.

---

## 6. Lacunas e riscos não documentados (o que vai morder)

### 6.1 Ordem de carregamento de `<script>` e estado global mutável

- `ui.js` → `app.js` → `multishot.js` → `moodboards.js` → `creditos.js`. Os três últimos capturam `const ui = window.Studio.ui;` e `const ctx = () => window.Studio.ctx;` **no topo do IIFE** (`multishot.js:27,29`, `moodboards.js:9,11`, `creditos.js:10,12`). Qualquer inversão explode em `undefined`. Em React isso vira import estático — a ordem some, mas **o teste `test_api.py:130-131` que afirma a ordem no `index.html` some junto e precisa de substituto**.
- `app.js` tem **12 variáveis de módulo mutáveis** compartilhadas por todas as funções: `steps`, `projects`, `pid`, `project`, `guideAll`, `guideById`, `view`, `area`, `currentStep`, `factories`, `instances`, `loaded`, `readySteps`, `refreshTimer`. `recomputeOverview()` **muta `guideAll` in-place** (l.171-179) a partir de `guideById` — é um cache derivado escrito por fora do fetch. O equivalente TanStack Query é `setQueryData` no `onGuide` + `invalidateQueries` debounced; **`scheduleGuideRefresh` (debounce 400 ms) tem de ser reproduzido**, senão o rail pisca ou faz N requests.
- `loaded: Set` faz o `view.js` de cada etapa executar **uma única vez por sessão**. Módulos de tela com estado de topo de arquivo sobrevivem à navegação. Ao virar componente React, esse estado passa a ser recriado a cada mount (ou precisa subir para contexto). **Comportamento observável pode mudar sem ninguém notar** — o cenário QA que troca de tela e volta é o detector.
- Cada tela hoje sobrescreve `$("#main").onclick` (delegação por tela). `destroyCurrent()` zera. Em React, delegação some — mas o cenário `edit.py` e `storyboard.py` clicam em elementos gerados por `innerHTML` dentro de handlers delegados; os testes só olham o efeito, não o mecanismo.

### 6.2 `edit` (E9) — o pior caso

- `view.html` tem **2 ids** (`#guide`, `#ved`) e **315 linhas de CSS**. **Todo o DOM do editor é gerado por JS**: `r.innerHTML = headerHTML() + bodyHTML() + timelineHTML()` (`view.js:783`), e depois re-renderizado por região (`renderTimeline`, `renderPreview`, `renderProps`, painéis).
- `.ved` é `position:fixed; top:0; left:var(--side-w); right:0; bottom:0; z-index:20` — **a tela escapa do fluxo do `main`** e depende do token `--side-w` do shell. A E3 tem de manter esse token; a E9 tem de manter o `position:fixed`.
- Paleta **própria** (`--v*`) escopada em `.ved`, com dark derivado de `prefers-color-scheme` **e** `[data-theme=dark]` — duplicação do mecanismo de tema do shell dentro da tela.
- 6 `pointerdown` + 6 `pointermove` + 6 `pointerup`, `wheel`, `scroll`, `resize`, `dragstart`×2, `dblclick`×2, `keydown`, `loadedmetadata`, `error`×2, 1 `requestAnimationFrame`, 3 timers.
- Drag manipula `el.style.left` e `el.dataset.ns` **diretamente durante o arrasto** (`view.js:1632`) — imperativo puro; em React isso é `ref` + estilo direto, não estado.
- `snapTime(t, skip)` (`view.js:1652`) varre todos os clipes de todas as tracks + markers + playhead a cada movimento de ponteiro, com tolerância `8/pps()`.
- `fit()` mede o container e recalcula `tlHeight` (`view.js:1910-1918`) — layout medido em JS, com `UI_SIZES` clampando e `ed().ui.tlHeight` persistido no `timeline.json`.
- Existe **handler inline no HTML gerado**: `oninput="const q=this.value.toLowerCase();this.parentNode.querySelectorAll('[data-tr]').forEach(...)"` (`view.js:1166`). React não avalia `oninput` string em `dangerouslySetInnerHTML` **nem** como atributo JSX — isso quebra silenciosamente e nenhum teste pytest pega; só o cenário QA de transições pega.
- Histórico próprio (`snapshot()`, `St.history` com teto de 40, `St.future`) + autosave (`scheduleSave`) + `setStatus("dirty")`. Undo/redo é estado de domínio; não misturar com o cache de query.

### 6.3 `storyboard` (E8)

- 2 referências a `canvas`, `dragstart`/`dragover`/`dragend` ×2 (reorder de cenas por HTML5 DnD nativo — **não** `pointer`), `dblclick`, lightbox (`.sb-lightbox-media`), 5 timers, 9 `click`.
- `annotate.js` é **injetado dinamicamente**: `ANNOTATE_SRC = "/static/annotate.js"` (`view.js:901`), com uma `Promise` memoizada `annotateLoad` (l.907-924), resolvendo `window.Studio.annotate`. O `annotate.js` usa `pointerdown/move/up/cancel` + `getContext` (8 referências a canvas) e faz upload via `ui.upload(annotateUrl(), [f], "file", {source_id})`, com a URL passada pelo chamador (o canvas não conhece a rota — ADR-017 style). **Encapsular em componente com `ref`, não reescrever a lógica de desenho.**
- `test_storyboard_view.py` roda `node --check` sobre `view.js` **e** sobre `annotate.js` (l.168, 234) — some com o vanilla, precisa virar `tsc --noEmit`.

### 6.4 Coisas que só aparecem no runtime

- `progressJob` chama `window.Studio.ui.refreshCredits()` no sucesso (`ui.js:482`) → **toda geração paga atualiza `[data-credits-chip]` na topbar**. Se o chip virar componente React lendo de query, o `progressJob` precisa invalidar a query, não mexer no DOM.
- `hfChip` e `refreshCredits` escrevem `node.className`/`classList` diretamente sobre elementos do shell. `refreshCredits` faz `classList.remove("ok","warn","mode")` **preservando** `tb-credits` — comportamento sutil que o cenário `creditos.py` observa via `[data-credits-chip]`.
- `modal()` faz `prev.focus()` na hora de fechar (retorno de foco) e autofoco no primeiro controle. `progress()` faz `closeBtn.focus()` ao terminar. Os cenários não testam foco explicitamente, mas `AUDIT_JS` testa `controles_cobertos` via `elementFromPoint` — um portal React mal posicionado acusa.
- Radios ocultos por CSS: `shell.py` C-SHELL-05 clica em `label:has(input[name=aspect][value='9:16'])`, `music.py` em `label:has(input[name=musClosed][value='1'])`, `moodboards.py` em `label:has(#mbNoPeople)`, `prospect.py` em `label:has(input[data-done='<lid>'])`. O `<label>` **tem** de envolver o input.
- `#tbBar` existe `hidden` e vazio **só porque o contrato de teste exige** (`index.html:69-71`, `test_api.py:141`). Manter.
- `toast` é único, global, `role="status" aria-live="polite"`, com timer de 3200 ms compartilhado (`clearTimeout(toast._t)`). Fila não existe: o último toast vence. `esperar_toast` do harness faz polling de 150 ms — se o React trocar por um toaster com animação de saída, `is_visible()` pode dar falso negativo.
- **`onProject` é vestigial** (§1.3) — decidir na E3.

### 6.5 Riscos de processo

- **`studio/web/dist/` como artefato compartilhado** entre 6 frentes paralelas: já resolvido no `wave-10.md` §6.1 (dist gitignored durante a wave, commit único na E10). Manter.
- Rodadas de QA em paralelo: `RUN=<nome-da-frente>`, nunca `RUN=local` (`wave-10.md` §6.2). `stack-up.sh` acha a primeira porta livre a partir de 8790.
- `ci.yml` já está em 20 min com a suíte Python. Somar `npm ci` + `tsc` + `vitest` + `build` **no mesmo job** estoura. O `wave-10.md` §E0 já pede job `frontend` **paralelo** — respeitar.
- `docs/qa/config.md` mapeia o label "purple = dono frontend" para `studio/web/` + `studio/etapas/*/view.*`. A E10 atualiza para `frontend/` + `etapas/*/ui/`.

---

## 7. Testes que quebram por construção

### 7.1 Testes que leem o fonte das telas (caixa-branca sobre o vanilla)

| Arquivo | Testes que tocam fonte de frontend | Fontes lidas | Frente que o substitui |
| --- | --- | --- | --- |
| `tests/test_api.py` | ~12 de 21 | `style.css`(7) `ui.css`(8) `ui.js`(7) `app.js`(7) `moodboards.js`(3) `mood/view.*`(2) `base/view.*`(2) | **E2** (catálogo de classes + `Studio.ui`), **E3** (shell/wizard/rota), **E10** (limpeza final). É o arquivo mais transversal. |
| `tests/test_steps_and_config.py` | 3 de 8 | `ui.js`(3) `ui.css`(2) `app.js`(2) — inclui a **ordem** dos `<script>` e `destroy()`/`go` | **E3** |
| `tests/test_reset_shell.py` | **4 de 4** | `WEB_DIR/app.js`, `WEB_DIR/ui.js`, `view.html` das etapas | **E3** (`wave-10.md` já mapeia) |
| `tests/test_progress_modal.py` | **6 de 6** | `/static/ui.js`, `/static/ui.css`, `view.js` de várias etapas | **E2** |
| `tests/test_mood_view.py` | 6 de 7 | `mood/view.{html,js}` | **E4** |
| `tests/test_refs_view.py` | 7 de 9 | `refs/view.{html,js}` | **E5** |
| `tests/test_prompter_presets_view.py` | 7 de 8 | `base/view.{html,js}` + `node --check` + **guarda de diff** | **E7** |
| `tests/test_storyboard_view.py` | **46 de 48** | `storyboard/view.{html,js}`, `WEB_DIR/annotate.js`, `node --check` ×3, **guarda de diff** ×2 | **E8** — o maior bloco isolado |
| `tests/test_base_api.py` | ~15 de 47 | `base/view.*` (26 refs), inclui `test_contrato_dom_da_etapa` (l.178) | **E7** |
| `tests/test_storyboard_api.py` | ~10 de 65 | `storyboard/view.*` (15 refs) | **E8** |
| `tests/test_storyboard_angles_api.py` | ~9 de 29 | `storyboard/view.*` (16 refs) | **E8** |
| `tests/test_edit_api.py` | ~6 de 52 | `edit/view.*` (11 refs) | **E9** |
| `tests/test_edit_captions.py` | 1 de 43 | espelho de valores no `view.js` | **E9** |
| `tests/test_animate_api.py` | ~5 de 20 | `animate/view.*` (10 refs), inclui guardas "removido pela wave 4, não pode voltar" | **E5** |
| `tests/test_music_api.py` | ~3 de 22 | `music/view.*` (6 refs) | **E4** |
| `tests/test_publish_api.py` | ~3 de 20 | `publish/view.*` (6 refs) | **E4** |
| `tests/test_export_api.py` + `test_export_guide.py` | 1 + 2 | `export/view.*` (6 refs) | **E4** |
| `tests/test_prospect_api.py` | ~3 de 15 | `prospect/view.*` (6 refs) | **E5** |
| `tests/test_refs_import_url.py` | 1 de 18 | `refs/view.*` (2 refs) | **E5** |
| `tests/test_vibes_api.py` | 1 de 19 | `mood/view.*` (2 refs) | **E4** |
| `tests/test_multishot.py` | **0 de 6** | — só núcleo Python + rotas HTTP | ⚠ **não quebra.** O `wave-10.md` §E6 promete "substituto Vitest de `tests/test_multishot.py`" — **isso está errado**: esse arquivo é backend puro (`studio/common/multishot.py` + rotas) e **deve continuar em pytest, intocado**. O que a E6 precisa é de um teste Vitest **novo** para o componente `Multishot`, não de substituição. |

**Correções ao mapeamento de substituição do `wave-10.md`:** além do item `test_multishot.py` acima, o §E4 cita só `test_mood_view.py`, mas `test_music_api.py`, `test_publish_api.py`, `test_export_api.py`, `test_export_guide.py` e `test_vibes_api.py` também têm asserts sobre os `view.*` do lote A. O §E5 cita só `test_refs_view.py`, mas `test_animate_api.py`, `test_prospect_api.py` e `test_refs_import_url.py` idem. O §E7 cita `test_prompter_presets_view.py` mas omite os ~15 testes de `test_base_api.py`. O §E8 omite `test_storyboard_api.py` e `test_storyboard_angles_api.py`.

### 7.2 Regra de ouro para os substitutos

Nenhum desses testes é apagado sem substituto. Mas note a **natureza**: quase todos são asserts de **substring sobre o fonte** ("o texto da aula X está no view.html", "o botão Y aponta para a rota Z"). O substituto Vitest não deve copiar essa técnica — deve renderizar o componente e asseverar **DOM + comportamento**. Os asserts que são de **fidelidade ao curso** (ADR-004: um texto de aula específico está na tela) continuam valendo e são os que mais importam preservar.

### 7.3 ⚠ Guardas de diff que reprovam a wave por construção

Duas, e nenhuma está documentada em `wave-10.md`:

1. `tests/test_prompter_presets_view.py::test_diff_da_feature_nao_toca_o_nucleo` (l.90-113) — faz `git merge-base develop HEAD`, junta `git diff --name-only` + `git status --porcelain`, e **falha** se qualquer caminho começar com `studio/web/`, `studio/app.py`, `studio/steps.py`, `studio/index.html` ou `studio/etapas/mood/view.`.
2. `tests/test_storyboard_view.py::test_t3_13_nucleo_do_shell_intocado[studio/web/ui.js]` e `[studio/web/style.css]` (l.521-535) — **falham** se esses dois arquivos mudarem em relação ao `merge-base develop`.

Impacto: **E2** (porta `ui.js`/`style.css`), **E3** (reescreve `app.js`/`index.html`), **E6** (remove `moodboards.js`/`creditos.js`/`multishot.js`) e **E10** (remove tudo + edita `studio/app.py`) reprovam em `make verify` sem tocar em nada errado. Estas guardas foram escritas para proteger frentes de *etapa* e a wave 10 é frente de *núcleo*.
**Ação para E0:** decidir e registrar o tratamento — reescrever as guardas para excluir a branch da wave, ou movê-las para um marcador pytest desligado durante a wave, ou substituí-las por uma guarda de "frente de etapa não toca `frontend/src/`". Sem isso, a E2 trava no primeiro `make verify`.

---

## 8. Perguntas que a entrevista de FDD pode pular (o recon já respondeu)

- **Qual é o contrato de plugin?** §1.2/§1.3, incluindo o detalhe de que `view.js` carrega uma vez só e que `onProject` é vestigial.
- **Quais rotas e chaves de `localStorage` são contrato?** §1.4 — 5 chaves, gramática completa, ordem de fallback.
- **Qual é a superfície da `Studio.ui`?** §2 — 28 membros + listener global, com consumidores mapeados.
- **Quais seletores cada tela precisa emitir?** §3 — tabela por tela + contrato global do harness.
- **O CSS pode ser renomeado/reformatado?** Não. §5.1 e Risco 2 do FDD (l.328): as strings são testadas literalmente.
- **A ordem E6→E8 existe?** Não. §0.2.
- **Precisa supersede de ADR?** Não integral; 2 ADRs novos que emendam 001/006/008/010. §4.

## 9. O que NÃO pode ser quebrado (checklist de merge por frente)

1. Os 382 cenários em `scripts/qa/cenarios/` passam **sem uma linha editada**.
2. `make qa-api` sem diferença de contrato; nenhum `service.py`/`router.py`/`guide.py` no diff (exceto a remoção de `/steps/{step}/{asset}` de `studio/app.py` na E10).
3. Diff de `textContent` contra o baseline da E0 == vazio (ADR-004).
4. Zero timers órfãos após trocar de etapa (`H.timer_orfao`, janela de 6 s) — o `destroy()`/cleanup React tem de parar todo `poll`.
5. Zero erro de console/pageerror/HTTP 4xx-5xx nas auditorias, em **claro e escuro**, a 1440 e 900 px; zero scroll horizontal; zero botão sem nome acessível; zero input sem label.
6. Prontidão de etapa **sempre** de `GET /api/projects/{pid}/guide` (ADR-010) — o React nunca deriva status.
7. Nomes de classe e tokens CSS preservados **literalmente** (catálogo §5).
8. `#tbBar` hidden, ordem `style.css < ui.css`, tema aplicado antes do primeiro paint.
9. Gramática de hash e as 5 chaves de `localStorage` intactas.
10. Etapa nova continua criando **só a sua pasta** (`etapas/<id>/ui/index.tsx` descoberto por `import.meta.glob`).

---

## 10. Arquivos-fonte lidos

**Documentação**
- `docs/plano/plano-migracao-react.md` (162 l., não commitado)
- `docs/domains/studio/hld.md` (v1.7, 289 l.)
- `docs/domains/studio/waves/wave-10.md`
- `docs/domains/studio/diagrams/mermaid/wave-10-dependencias.md`
- `docs/domains/studio/features/shell-redesign-fdd.md` §5 (l.139-238)
- `docs/adrs/generated/STUDIO/ADR-001, ADR-004, ADR-006, ADR-008, ADR-010, ADR-017` (+ listagem de todos os 30 em `STUDIO/`, `MOOD/`, `MUSIC/`, `REFS/`, `HIGGSFIELD/`, `PUBLISH/`, `STORYBOARD/`)
- `docs/adrs/mapping.md`
- `docs/qa/config.md`
- `CLAUDE.md`
- `Makefile`, `.github/workflows/ci.yml`

**Código de frontend**
- `studio/web/index.html` (88), `app.js` (610), `ui.js` (768, integral), `style.css` (692), `ui.css` (226), `multishot.js` (222), `moodboards.js` (401), `creditos.js` (231), `annotate.js` (190)
- `studio/etapas/{animate,base,edit,export,mood,music,prospect,publish,refs,storyboard}/view.{html,js}` (6.958 LOC — leitura de estrutura, ids, blocos `<style>`, listeners e hotspots imperativos; `edit/view.js` e `storyboard/view.js` em detalhe)

**Backend tocado pelo frontend**
- `studio/app.py` (l.205-226), `studio/etapas/__init__.py`

**Oráculo QA**
- `scripts/qa/harness.py` (integral nas seções de navegação, modal, toast, progresso, auditoria, timers, drag/drop)
- `scripts/qa/run.py` (l.95-215)
- `scripts/qa/cenarios/{shell,overview,mood,publish,export,music,prospect,refs,animate,moodboards,creditos,base,storyboard,edit}.py` (8.256 LOC — extração completa de seletores)

**Testes**
- `tests/` (63 arquivos; análise de acoplamento a fonte de frontend em todos; leitura detalhada de `test_api.py`, `test_steps_and_config.py`, `test_reset_shell.py`, `test_progress_modal.py`, `test_multishot.py`, `test_mood_view.py`, `test_refs_view.py`, `test_storyboard_view.py`, `test_prompter_presets_view.py`)
