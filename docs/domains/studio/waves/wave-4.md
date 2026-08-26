# Wave 4 — Fidelidade total ao protótipo (handoff `design_handoff_redesign_frontend`)

Data: 2026-08-26 · Orquestração: `/dd-parallel` (W0–W5) · Task-Ids: `ADH-OS-20260826-10` (shell-fidelity, sub-wave 0), `-11` … `-16` (frentes de tela, sub-wave 1), `-17` (fechamento)
Terreno: `docs/domains/studio/recon-wave-4.md` · Fonte de verdade visual: `Análise de codebase/design_handoff_redesign_frontend/` (README + `Redesign Orquestrador Studio.dc.html`) · Referência renderizada (fora do git): `../orquestrador-studio-worktrees/_wave4-ref/{proto/NN-<tela>.{html,png}, app-before/, audit/<frente>.md, AUDIT-PROTOCOL.md}`

## Objetivo

A wave 3 aplicou o redesign; esta wave **zera as divergências** entre o app e o protótipo. Pedido do dono do produto (26/08/2026): "implemente exatamente igual ao protótipo, mesmo que para isso tenha que remover coisas já feitas ou criar funcionalidades novas; identifique o que não está igual e deixe exatamente igual; não pare até terminar e deixar 100% igual".

Isso **substitui a regra 1 da wave 3** ("funcionalidade nunca some"). A nova regra de decisão está em `AUDIT-PROTOCOL.md` e resumida abaixo.

## Regras da wave (valem para todas as frentes)

1. **Protótipo manda em tudo que é visível.** Elemento, texto, ordem, cor, fonte, tamanho, raio, gap: o DOM renderizado do protótipo (`_wave4-ref/proto/NN-<tela>.html`, estilos inline) é a medida. Diferença de dado (nomes, contagens, quantidade de tiles) não é divergência.
2. **O que o app tem e o protótipo não desenha sai** (REMOVER), exceto quando é o único meio de executar uma ação que a aula exige — aí INTEGRA: a ação continua, sem elemento extra visível por padrão (texto estático editável ao clicar, ações só no hover/`focus-within`, modal aberto por um elemento que o protótipo já desenha). Marcações `[extensão]` que o protótipo não desenha saem.
3. **Controles reais com cara do protótipo**: `textarea` e `input` que o protótipo desenha como bloco/texto ficam sem altura fixa, sem barra interna (`field-sizing:content` + `Studio.ui.autosize` como fallback), com a mesma caixa, fonte e cor.
4. **`<details>` de aula só onde o protótipo tem** (apenas etapa 1, "O que a aula 009 manda fazer aqui"). Nas demais telas os `<details class="lesson">` saem. O texto de aula não é perdido: continua nos `guide.py`/FDDs/plano — a tela deixa de exibi-lo. Registro: decisão do lote #2.
5. **Backend muda só para expor dado que o protótipo mostra** (`guide.summary`/`summary_kind`, `bpm` por faixa, `segment` do lead, `checks[]` do QA, `reminders[]` do pitch, `last_job` do scrape, `batch` do mood, textos de `next_action`). Rotas existentes e regras de negócio não mudam; rota nova só se não houver rota que carregue o dado.
6. **Propriedade de arquivos (ADR-010)**: `studio/web/*`, `studio/common/guide.py`, `tests/test_api.py`, `tests/test_guide.py` = frente shell (sub-wave 0). `studio/etapas/<id>/*`, `studio/<id>/service.py` (só para o dado da regra 5), `tests/test_<id>_*` = frente da tela. Classe que a tela precisa e o shell não tem: `<style>` escopado com prefixo + registro no final report (promoção no fechamento).
7. **Testes acompanham**: a frente que remove/renomeia um painel reaponta os asserts de substring do seu `tests/test_<id>_*.py` na mesma PR. O baseline (667 testes) só cai por remoção justificada de teste que fixava o que foi removido.
8. **Verificação por frente**: `make verify` + smoke (`python scripts/smoke_ui.py http://127.0.0.1:<porta> 2026-08-wave-teste <pasta> dark`) + comparação lado a lado com `_wave4-ref/proto/NN-<tela>.png` + medição `scrollWidth − clientWidth == 0` em 1440 e 900 px. Print do antes/depois no PR.

## Contrato transversal: o que o shell entrega (sub-wave 0, `ADH-OS-20260826-10`)

Consolidado das seções (a) das 7 auditorias. Valores finais são os do DOM do protótipo — em conflito entre auditorias (ex.: `button.ghost` 6 × 7 px), o shell mede no DOM e registra o valor único.

### Guia (`ui.js` + `ui.css`) — transversal, bloqueia todas as telas
- `_guideOpen(id)`: **fechado por padrão** (sem chave em `localStorage` ⇒ faixa compacta). Etapa 1 do protótipo aparece expandida só porque o mock a abriu — não é exceção de código.
- Faixa compacta: `Guia` (eyebrow) + chip de status + chip `NN%` + `→ <next_action>`; chip extra `g.summary` quando existir, com classe `g.summary_kind || "mode"` (`warn` → cor `--gate`, ex.: "portfólio 1/4 vídeos"). Chips da faixa `padding:2px 8px`.
- Expandido: head clicável (caret ▾/▸, "Guia da etapa N", chips status/%, hint "recolher/abrir") + linha de estado (`tudo pronto` | `falta …` + `g.summary`) + **uma** grade `auto-fit minmax(240px,1fr)` de itens ✓/✕/! (união de inputs+outputs+validations, sem títulos de seção, sem `.det`, sem checkboxes, sem link por item) + `→ Próxima ação` + botão "Ir para a etapa N" (`6px 12px`). Apagar `.guide-sec>h4`, `.guide-what`, `.guide-check`, `.guide-fix`, `.guide-items .body`. Manter `_guideOpen`, `guide-toggle`, `guide-strip`, `aria-expanded` (asserts).
- `studio/common/guide.py`: `Guide.build(..., summary=None, summary_kind=None)` e `generic_guide` com os campos sempre presentes; `next_action` de etapa concluída = imperativo curto do estilo do protótipo (o texto por etapa vem do `guide.py` da tela).

### Tokens e controles (`style.css`)
- Tokens novos (escuro + par claro): `--glow-dot: 0 0 8px rgba(79,200,217,.7)`, `--accent-soft-1: rgba(79,200,217,.10)`, `--accent-line-3: rgba(79,200,217,.22)`, `--ok-line-2: rgba(80,207,158,.22)`, `--glow-cta` escuro `.18`; `--stripes` com passo 8 px na variante pequena (`.scene-row .thumb`, thumbs de linha) — manter 10 px nos tiles.
- `input, textarea{padding:8px 11px;font-size:13px}`, `select{padding:7px 26px 7px 11px}`, `textarea{padding:10px 12px;line-height:1.6}`; `input.sm` (panel-head, r8, 180 px), `input.bare` (número inline sem caixa, mono, borda só no focus), `input.mini{width:44px}`, `input.mini.lg` (52 px, `--surface-2`, borda `--ctl`, r7, 5px 8px, 11.5 px), `.w44`.
- Botões: `button, button.ghost` = valor do protótipo (medir `scp1`: `padding` 7px 12px, `font-weight:400`); `button.primary{padding:8px 14px}` mantém 600; `button.sm{font-size:12px;padding:6px 12px}`; `button.icon.mini` (↑ ↓ ✕); `button.link{font-size:12.5px}` (12 px dentro de `.prompt`); `button:disabled` ghost = `opacity:1;color:var(--ink-5);border-color:var(--ctl)`; modal usa `.ghost.lg`/`.primary.lg` (r9, 13 px, 8px 14/16, glow); `button.loading` é o único feedback de "gerando…".
- `.lede b{font-weight:700}`; `.stephead{margin-bottom:20px}`; `.stephead.ov .lede{max-width:68ch}`; `.eyebrow.lbl` (10 px, `.1em`, `--ink-3`, block, mb 8); `.note{font-size:11.5px;line-height:1.5}`; `.note code` sem fundo; `.panel>.fine,.panel-head+.fine{margin:0 0 14px}`; `main>.panel:last-child{margin-bottom:0}`; `.progress` em painel `margin-bottom:10px`.

### Shell, visão geral e modal
- Sidebar: `.brand .dot{box-shadow:var(--glow-dot)}`; `.navlink>span[aria-hidden]{font-size:12px}`; `.side-foot{position:static;padding:14px 0 0}`; chip do CLI `● CLI · <plano> · <N> créditos` (`hfChip`), `padding:4px 8px;gap:6px`, `.ok{border-color:var(--ok-line-2)}`.
- Topbar: `.tb-meta .chip.info{background:var(--accent-soft);border-color:var(--accent-line-3)}`; remover `.progress.hidden#tbBar` do `index.html` (manter o id `tbBar` só se um assert exigir — então `<span id="tbBar" hidden>`).
- Visão geral: lede sem "desta campanha", `.chip.in_progress{background:var(--accent-soft-1)}`, `.ov-summary .chip.todo{background:var(--bg-2)}`; ovcard: chips 10 px/`2px 8px`, barra r2, **sem** linha "Faltando:" (`.miss`), linha "→" só em done/in_progress; **remover** painel "Como o Studio segue o curso" (`courseHtml`, `COURSE_TEXT`, `.course*`) inclusive na tela sem campanha.
- Modal: sem as duas linhas `.hint` (aulas 009/007); campo formato `.field.fmt-field{gap:8px}`; ações `.ghost.lg` + `.primary.lg`. `Studio.ui.modal({title, html, actions})` aditivo, aceitando conteúdo arbitrário (galeria + botões) — usado pelas telas 4, 5 e 6.

### Galerias, prompts, linhas
- `.card .term{background:linear-gradient(transparent,rgba(0,0,0,.72));color:#C9CFD8}` (reverte a decisão de legibilidade da wave 3 — protótipo manda); idem `.player .term`. `.gallery.sm .card .term{white-space:normal}`.
- `.gallery.xs .card` r9, sem anel, check 20 px (`top/right:6px`, 11 px). `.card .card-act` hover-only (`opacity:0` → `:hover/:focus-within`). `.refpick{margin:0 0 14px}`.
- `.prompt{padding:12px 14px;gap:6px}`; `.prompt .fine{color:var(--ink-2)}`; `.prompt .txt` (mono 12/1.6, `--ink-2`, `pre-wrap`); `.prompt textarea{min-height:0;resize:none;overflow:hidden;field-sizing:content}`; `.prompts.one` (card único largura total). `Studio.ui.autosize(el)` novo helper (fallback do `field-sizing`).
- `.rowlist{gap:10px}`; `.rowcard.cur{background:var(--surface-3)}`; `.rowcard.col>.thumb{border-radius:8px}`; `.rowcard .upcount` (mono 9.5 px `--ink-5`; `.warn` → `--gate`; `.ok` → `--ok`); `.panel-head .palette{margin:0}`; `.palette.sm{gap:6px}`; `.palette.sm .lbl{margin-left:4px}`.
- `.scene-row{position:relative}`; `.scene-row textarea.txt` transparente, 13 px, `--ink-row`, auto-altura, `:focus` com anel; `.scene-row .acts` hover-only; `.thumb.pick` clicável; remover `.scene-row .media`.
- `.take.empty{color:var(--ink-5)}`; `.take .act,.take .an-x` hover-only; `.import-row` (flex, gap 14, `.col` min 220/gap 8, botões 8px 12px); `.panel-head button.ghost{padding:7px 12px}`.
- `.clip-row{grid-template-columns:26px 84px minmax(120px,1fr) auto}`; `.clip-row .thumb{border-radius:6px}`; `.clip-row .ctl label{gap:5px;font-size:12px}`; `.clip-row .acts,.clip-row .more` hover/`focus-within`; remover `.clip` órfã.
- `.track-row .wave{cursor:pointer}` + progresso `linear-gradient(90deg,var(--accent-soft-2) var(--p,0%),transparent 0)` sobre as barras; `.sfx-list`/`.sfx-line` (+ `.edit` hover); `.q`, `.col.g10`, `.inline.lg`, `.col>.note{margin-top:0}`, `.self-start`, `.row.loose`, `.row.media`, `.row.opts`, `.col>.cli{margin-top:0;padding-top:8px}`, `.cli .inline input[type=number]{width:52px}`.
- `.beats .cut{top:2px}`; `.beats-axis{margin-bottom:14px}`; `.beats+.note{margin-top:10px}`.
- `.fmt-card.on{border-color:rgba(80,207,158,.3)}`; `.checks{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}`; `.grow-md{flex:1;min-width:200px}`; `.grow-lg{min-width:220px}`; `.chip.info{background:var(--accent-soft)}`; `.pub-row .chip{padding:2px 8px}`; `.pub-row .url{white-space:nowrap;max-width:32ch}`; `.pub-row .act,.lead-row .body .act` hover-only; remover `.pub-row .fb`; `.strip .chip{padding:2px 8px}`; `.chip.xs`; `.lead-row{cursor:pointer}` + `.lead-row .body` (promovido de `.pr-body`); `.pitch-table .tr{border-bottom:1px dashed var(--line)}` + `input.v` transparente mono alinhado à direita; `.script{overflow:visible}`; `.drop{min-width:220px}`; `.panel.over` (alvo de drop = painel inteiro; `Studio.ui.drop()` aceita qualquer elemento).
- `tests/test_api.py`: atualizar asserts (classes novas, ausência de `courseHtml`/`miss`/`#tbBar` visível/hints do modal).

## Features e contratos

| Feature | Task-Id | Escopo | provides | consumes | sub-wave |
|---|---|---|---|---|---|
| shell-fidelity | ADH-OS-20260826-10 | `studio/web/*`, `studio/common/guide.py`, `tests/test_api.py`, `tests/test_guide.py`, docs desta wave | contrato acima (classes, helpers `autosize`/`modal`/`drop(el)`, guia compacto, `summary`/`summary_kind`) | — | 0 |
| views-refs-mood | -11 | etapas 1–2 (+ `studio/refs/service.py` `last_job`, `studio/mood/service.py` `batch`) | telas 1–2 iguais; `guide.summary` refs/mood | shell-fidelity | 1 |
| views-base | -12 | etapa 3 | tela 3 igual; `guide.summary` base | shell-fidelity | 1 |
| views-storyboard-shots | -13 | etapas 4–5 | telas 4–5 iguais; `next_action` do protótipo; `guide.summary` | shell-fidelity | 1 |
| views-animate | -14 | etapa 6 | tela 6 igual; `guide.summary` "n/m shots prontos" | shell-fidelity | 1 |
| views-music-edit | -15 | etapas 7–8 (+ `studio/music/service.py` `bpm`) | telas 7–8 iguais; `guide.summary` | shell-fidelity | 1 |
| views-export-publish-prospect | -16 | etapas 9–11 (+ `export.qa` `checks[]`, `prospect` `segment`/`reminders`/`gate.message`) | telas 9–11 iguais; `guide.summary`/`summary_kind` | shell-fidelity | 1 |
| fechamento | -17 | promoção de `<style>` escopados, smoke integrado, retro, HLD | — | todas | 2 |

Grafo: todas as frentes de tela dependem só de `shell-fidelity`; entre si são disjuntas em arquivos. Ordem de integração: shell → telas em qualquer ordem (PR pronta primeiro entra primeiro) → fechamento.

## Critérios cross-feature (cobrados na W5)

1. Zero erro/aviso de console nas 12 telas (smoke escuro e claro) e 11/11 sem timer órfão.
2. Zero scroll horizontal a 1440 e 900 px em todas as telas.
3. Faixa compacta do guia por padrão em todas as telas; expandido com uma grade só.
4. Comparação lado a lado `proto/NN-<tela>.png` × app: nenhum elemento a mais ou a menos; textos fixos (eyebrow, título, lede, títulos de painel, rótulos de botão, notas) idênticos ao protótipo.
5. `make verify` verde no estado integrado.

## Decisões do lote (auto-aceites do orquestrador — registradas no lugar do gate 1, porque o dono do produto pediu "não pare até terminar" e "tome as melhores decisões")

1. **Gate 1 (aprovação em lote das specs) e gate 3 (merge de cada PR) foram pré-autorizados** pelo pedido do dono do produto nesta wave; a lista completa do que foi removido fica no relatório final e na retro, para revisão a posteriori.
2. `<details>` de aula saem de todas as telas exceto a etapa 1 (regra 4). Os testes que exigiam `details.lesson` são reapontados.
3. Painéis e controles que o protótipo não desenha saem (CLI pago nas etapas 2–5 e 7, upload manual visível na 1, campos de brief/histórico na 2, painel 04 da 3, painéis extras da 4/5/7/8, Thumb e Reframe na 9, galeria de exports/resumo global na 10, lista de projetos do gate e `#guide` na 11 etc. — lista por tela em `_wave4-ref/audit/<frente>.md` §(c)). Ações exigidas pela aula que só existiam nesses painéis são INTEGRADAS (modal "Gerar take N", drop no painel, edição inline, ações no hover). Rotas do backend permanecem.
4. Backend só ganha campos (regra 5); nenhuma rota nova salvo `GET export/qa` se `status` não comportar o último QA.
5. Valores em conflito entre auditorias (paddings de botão/input) são resolvidos pelo shell medindo o DOM do protótipo; a tela não replica a regra localmente.
6. Fixtures: as frentes podem enriquecer `projects/2026-08-wave-teste` localmente (não versionado) para comparar telas cheias.
7. Trello indisponível (board inexistente): PR + final report são o registro.
