### FDD: views-export-publish-prospect — etapas 9, 10 e 11 no redesign dark-first

Versão: 1.0
Data: 2026-08-26
Responsável: Arthur Diego (implementação: frente `views-export-publish-prospect` da wave 3, `ADH-OS-20260826-08`)

Modo: **batch** — Gate 1 (spec) pré-aprovado em lote pelo dono do produto
(`waves/wave-3.md` §"Decisões do lote" #1). Todo ponto que exigiria entrevista foi decidido
aqui e está rotulado `[auto-aceito: …]`.
Spec normativa: `docs/domains/studio/waves/wave-3.md` (§"Contrato transversal" e
§"Feature: views-export-publish-prospect"). Terreno: `docs/domains/studio/recon-wave-3.md`
(§1 contrato DOM de export/publish/prospect, §2 strings fixadas por teste).
Catálogo consumido: `docs/domains/studio/features/shell-redesign-fdd.md` §5.
FDDs anteriores dos mesmos módulos (continuam válidos para backend e regra de negócio):
`docs/domains/export/features/export-fdd.md`, `docs/domains/publish/features/publish-fdd.md`,
`docs/domains/prospect/features/prospect-fdd.md`. Este documento **só** substitui a descrição
de tela (markup/ids) daqueles três.
Fonte de verdade visual (fora do repositório): `Análise de codebase/
design_handoff_redesign_frontend/Redesign Orquestrador Studio.dc.html`, linhas 719–763
(export), 765–815 (publish), 817–876 (prospect) e 1043–1070 (estados dos formatos e leads).

---

### 1. Contexto e motivação técnica

A wave 2 entregou as três telas funcionais, mas com o visual antigo: painéis numerados "1.",
"2.", tabelas HTML no QA técnico e no pitch, cartões de formato feitos de `.panel` aninhado,
posts e leads renderizados como `.prompt`, e o gate do portfólio como painel inteiro. O
handoff de redesign dark-first fixa outra linguagem para exatamente esses objetos: `.fmt-card`
com a proporção desenhada, `.checks` (✓/!) no lugar da tabela de QA, `.pub-row` e `.lead-row`
como linhas de lista, `.strip.warn` como faixa de gate e `.pitch`/`.pitch-table`/`.script`
para a ancoragem de preço.

A frente `shell-redesign` (`ADH-OS-20260826-02`, sub-wave 0, já em `develop` @ `a8795bb`)
publicou todas essas classes em `studio/web/style.css` e os helpers `Studio.ui.tile/pipe/
beats/copyBtn/copy` em `studio/web/ui.js`. Esta frente **consome** o catálogo e não toca em
nada de `studio/web/`, backend, rotas ou serviços: é uma troca de markup nas três telas.

Encaixe no HLD `studio`: os plugins `studio/etapas/{export,publish,prospect}/` continuam
descobertos por `discover()`, servidos como `view.html` + `view.js` e registrados por
`Studio.register(<id>, ctx)`. Nenhuma rota muda; nenhum arquivo de `studio/<dominio>/service.py`
é lido ou escrito por esta entrega.

Atores: usuário do Studio (renderiza formatos, gera QA/thumb, registra publicações, cadastra
e evolui leads, edita o pitch); shell (`app.js`/`ui.js`, dono do CSS e dos helpers).

Suposições e restrições:
- O catálogo do shell é imutável para esta frente. Classe que faltar vira `<style>` escopado
  no topo do `view.html` da própria etapa, com prefixo `.ex-`/`.pb-`/`.pr-`, e é registrada
  como lacuna para a integração (W5) decidir se promove.
- `publish/view.html` não pode ganhar nenhum `<input|select|textarea id=…>` novo: o conjunto
  `{pubVideo, pubNetwork, pubDate, pubUrl, pubNote}` é fixado por regex em
  `tests/test_publish_api.py::test_view_html_segue_a_aula_sem_copy_automatica`.
- Sem rede e sem emulador; a validação visual é `scripts/smoke_ui.py` mais um roteiro
  Playwright de fluxo (fora do CI, ADR-008).

---

### 2. Objetivos técnicos

1. As três telas renderizam no padrão do protótipo: painéis numerados com `<span class="pn">`,
   texto longo de aula dentro de `<details class="lesson">`, rótulo `[extensão]` como
   `<span class="ext">` em vez de `chip mode`.
2. `#expFormats` passa a ser `.fmt-grid` de `.fmt-card`; `#expQa` passa a ser `.checks`;
   `#pubLog` passa a ser `.rowlist` de `.pub-row`; `#gatePanel` passa a ser `.strip.warn` com
   `.pipe` de 4 segmentos; `#leadList` passa a ser `.rowlist` de `.lead-row`; `#pitchValues`
   passa a ser `.pitch-table` e `#pitchBox` passa a ser `.script`.
3. Nenhum id do inventário do recon §1 desaparece; nenhum `data-*` de hook muda; toda ação
   existente continua alcançável.
4. `make verify` verde; smoke claro/escuro/`--timers` com zero erro de console e 11/11 etapas
   sem timer vazado; nenhuma das três telas gera scroll horizontal a 1440 nem a 900 px.

---

### 3. Escopo e exclusões

**Incluído:** `studio/etapas/export/{view.html,view.js}`,
`studio/etapas/publish/{view.html,view.js}`, `studio/etapas/prospect/{view.html,view.js}`,
os testes `tests/test_export_guide.py`, `tests/test_publish_api.py`,
`tests/test_prospect_api.py` (asserts novos do contrato visual) e este FDD.

**Excluído:** `studio/web/*` (propriedade da frente `shell-redesign`); qualquer backend
(`studio/export/`, `studio/publish/`, `studio/prospect/`, `studio/common/`, `studio/guide/`);
rotas; `steps.py`; coleção Postman (a entrega não cria nem altera contrato HTTP — §5 abaixo
não tem endpoint novo); chips extras do guia por `g.summary` (decisão do lote #5: nenhum
`guide.py` muda nesta wave); dados de exemplo do protótipo (decisão do lote #6).

---

### 4. Fluxos detalhados

Um fluxo principal por tela, todos já existentes — o que muda é a marcação renderizada.

**9 · export.** `onProject()` → `load()` → `GET /export/status` → `renderChips()` (chips no
`.panel-head` do painel 01) + `renderFormats()` (um `.fmt-card` por formato) + `renderJob()`
(`.progress`/`#expBar`, `#expJobLog`, `#expLog`) + `renderThumb()`. Clique em `.render` →
`POST /export/render` → job → `Studio.ui.poll` a cada 3 s até `done`. Clique em `.prev` →
`POST /export/preview` → imagem `.ex-prev` no cartão. "Gerar QA" → `POST /export/qa` →
`renderQa()` desenha `.checks`.

**10 · publish.** `load()` → `GET /publish/{exports,log,portfolio}` em paralelo →
`renderExports()` (select `#pubVideo` + galeria `.gallery.sm`), `renderLog()` (`.pub-row` por
post), `renderGlobal()`, `renderCommunity()` (chip combinado). "Registrar publicação" →
`POST /publish/log` → recarrega. Clique num tile → preenche `#pubVideo` e foca `#pubUrl`.
`button.link.del` → `DELETE /publish/log/{id}`; `button.link.save` → `POST
/publish/log/{id}/feedback`.

**11 · prospect.** `load()` → `GET /prospect/leads` → `renderGate()` (faixa `.strip[.warn]`,
chip, `.pipe` de `gate.required` segmentos com `done` por obra publicada, `#gateMsg`,
`#gateProjects`) + `render()` (`.lead-row` por lead). O gate fechado esconde `#leadsPanel`
inteiro, como antes. "+ Novo lead" alterna `#newLeadPanel` (formulário inline). Cadastro →
`POST /prospect/leads`. Ação principal por estado, na ordem da aula: sem `sent_at` → abre a
linha ("Gerar DM (script da aula)"); com `sent_at` e sem `replied` → `data-act="replied"`;
com `replied` e sem teaser → `primary` `data-act="teaser"`; com teaser →
`data-act="copyfollow"`. `loadPitch()` → `GET /prospect/pitch` → `.pitch-table` + `.script`;
"Salvar valores e regerar" → `POST /prospect/pitch`.

`destroy()` continua parando o poll de export e o de teaser do prospect (publish não faz
polling).

---

### 5. Contratos públicos — mapa painel → markup/ids

Não há endpoint novo. O contrato público desta entrega é o **DOM** que o `view.js` de cada
etapa consulta e o shell estiliza. `→` marca o que mudou de forma em relação à wave 2.

#### 9 · export (`studio/etapas/export/`)

| Painel | Markup | ids / hooks |
| --- | --- | --- |
| `header.stephead` | eyebrow "Etapa 9 · aula 014", `h2`, `p.lede` com "plano 1.4", "1:1 é opcional", `span.ext` e a frase "publique o seu trabalho, mesmo imperfeito" | — |
| guia | `<section id="guide" class="guide"></section>` | `#guide` |
| **01 Formatos** (funde o antigo painel "Estado") | `.panel` > `.panel-head` (`h3` > `span.pn` `01`) + `.row.wrap` com os 3 chips e o CTA → `p#expMasterInfo.fine.mono` → `details.lesson` → `.progress > span#expBar.bar` → `div#expFormats.fmt-grid` → `pre#expLog.log` (nasce `.hidden`) | `#expFfmpeg` `#expMaster` `#expHf` `#btnRenderAll.primary` `#expJobLog` `#expMasterInfo` `#expBar` `#expFormats` `#expLog` |
| cartão de formato (gerado) | → `div.fmt-card[.on][data-fmt]` > `.top` (`span.ratio`, `span.dest`, chip "rede-alvo" opcional, `span.chip.ok\|mode` "renderizado"/"a renderizar") + `.box > i[.on]` (46×26 / 15×27 / 24×24) + `img.ex-prev`? + `p.fine.mono` + `.ex-acts` (`button.ghost.prev[data-fmt]` "Preview", `button.render[.primary][data-fmt]` "Renderizar", `a.fine.mono.ver` "Ver arquivo"?) | `data-fmt`, `.render`, `.prev` |
| **02 QA técnico `span.ext`** | `.panel-head` (`span.pn` `02`) + `button#btnQa.ghost` + `a#expQaFile` → `div#expQa` → `p.note` → `details.lesson` | `#btnQa` `#expQaFile` `#expQa` |
| QA renderizado | → `p.fine` de bloqueio? + `div.checks > div.it.ok\|warn > span.mark` (`✓`/`!`) + `span.lbl` (arquivo) `> span.det` (resolução · duração · áudio · veredito) | — |
| **03 Thumb `span.ext`** | igual à wave 2, com `.pn` e `.lesson`; → `div#expThumb.gallery.xs` recebendo `div.card.wide > img` (sem `style="max-width:320px"`) | `#expThumbT` `#btnThumb` `#expThumbInfo` `#expThumb` |
| **04 Reframe pelo CLI `span.ext`** | igual à wave 2, com `.pn` e `.lesson`; `.row.wrap.cli` preservado | `#expAspect` `#btnReframe` `#expReframeInfo` |

#### 10 · publish (`studio/etapas/publish/`)

| Painel | Markup | ids / hooks |
| --- | --- | --- |
| `header.stephead` | lede com "perfil novo ou nas redes que você já tem", "4 vídeos", "prática, exposição e validação" | — |
| guia | `<section id="guide" class="guide"></section>` | `#guide` |
| **01 Registrar uma publicação** | `.panel-head` (`span.pn` `01`) + chips `#pubCounter`/`#pubPosts` + `a#pubPortfolio` → `.pb-form` linha 1 (`select#pubVideo`, `input#pubNetwork[list=pubNetworks]`, `input#pubDate[type=date]`) → `.pb-form` linha 2 (`input#pubUrl.u`, `input#pubNote.n`, `button#btnPubAdd.primary`) → `details.lesson` → `.pb-exports` (`span.eyebrow` "Vídeos prontos em export/", `div#pubExports.gallery.sm`, `div#pubGlobal.fine`) → `p.note` | conjunto de ids de campo **exatamente** `{pubVideo, pubNetwork, pubDate, pubUrl, pubNote}` |
| **02 Publicações e comunidade** | `.panel-head` (`span.pn` `02`) + `span#pubComChip` ("N publicações · comunidade n/3") + `span#pubReady` → `div#pubLog.rowlist` → `#pubCommunity` (3 `input[type=checkbox][data-com]`, sem id) → `details.lesson` com "comunidade ABRAhub" e "feedback" | `#pubComChip` `#pubReady` `#pubLog` `#pubCommunity` |
| post (gerado) | → `div.pub-row[data-id]` > `span.chip.info` (rede) + `a.url` + `span.nt` (nota)? + `span.fine.mono` (data · arquivo) + `.pb-fb` (`input.fb[data-id]`, `button.link.save[data-id]`, `button.link.del[data-id]`) | `.fb`, `.save`, `.del` |
| tile de export (gerado) | inalterado: `div.card[.sel][data-file][tabindex][title]` > `img`? + `span.src` + `span.term` | `data-file` |

#### 11 · prospect (`studio/etapas/prospect/`)

| Bloco | Markup | ids / hooks |
| --- | --- | --- |
| `header.stephead` | lede do protótipo ("O Studio redige e registra; enviar é com você") | — |
| guia | `<section id="guide" class="guide"></section>` | `#guide` |
| **gate** | → `section#gatePanel.strip.warn` > `span.eyebrow` "Gate do portfólio" + `span#gateChip.chip` "n/4 obras publicadas" + `div#gatePipe` (recebe `Studio.ui.pipe`, 4 segmentos `done`/`todo`) + `span#gateMsg`; abaixo `div#gateProjects.fine` e um `details.lesson` | `#gatePanel` `#gateChip` `#gatePipe` `#gateMsg` `#gateProjects` |
| **01 Leads** (funde `#newLeadPanel` em `#leadsPanel`) | `section#leadsPanel.panel[.hidden]` > `.panel-head` (`span.pn` `01` + `#statusChip` + `#todayChip` "n/10 hoje" + `#jobChip` + `button#btnNewLead.primary` "+ Novo lead") → `div#newLeadPanel.pr-newlead[.hidden]` (`form#leadForm.row.wrap` com `#lfBusiness #lfHandle #lfPostRef #lfWhy #lfRole` + submit) → `div#leadList.rowlist` → `p.note` da ordem da aula → `details.lesson` com os 6 segmentos | `#leadsPanel` `#newLeadPanel` `#btnNewLead` `#leadForm` `#lf*` `#leadList` `#todayChip` `#statusChip` `#jobChip` |
| lead (gerado) | → `div.lead-row[data-id]` > `.lead-biz` (`span.nm`, `span.h` "@handle · papel") + `span.lead-post` + `span.chip` (`mode`/`info`/`ok`) + ação principal + `button.link.toggle[data-id]`; aberto: `.pr-body` com `textarea[data-dm]`, `button.act[data-act=copy\|sent\|replied\|teaser\|del\|copyfollow]`, `video`?, `input[data-call]`, `input[data-note]`, `input[data-done]` | `.toggle`, `.act[data-act]`, `[data-call]`, `[data-note]`, `[data-done]` |
| **02 Pitch da call — 15 minutos** | `.panel-head` (`span.pn` `02`) + `#btnPitchCopy.ghost` + `#btnPitchSave.primary` → `div.pitch` (`div#pitchValues`, `pre#pitchBox.script`) → `details.lesson` | `#pitchPanel` `#btnPitchCopy` `#btnPitchSave` `#pitchValues` `#pitchBox` |
| pitch (gerado) | → `div.pitch-table` > `div.tr` (`span` rótulo + `span.v > input.mini[data-pitch]`) × N + `div.total` (`span` "Total" + `span.v` com `input.mini[data-pitch-total]` e o "· 50% off no 1º") ; `p.note` da soma; `#pitchBox` = markdown + `span.end` "→ prospect/pitch.md" | `[data-pitch]`, `[data-pitch-total]` |

**Decisões de contrato deste FDD**

- `[auto-aceito: o cartão de formato mantém DOIS botões (`.prev` "Preview" e `.render`
  "Renderizar") e ganha um `a.ver` "Ver arquivo" quando o formato já existe.]` O protótipo
  desenha um único botão que alterna "Ver arquivo"/"Renderizar", mas o app tem duas ações
  distintas (gerar o quadro de conferência do corte × renderizar o mp4) e a wave proíbe
  remover funcionalidade (regra 1). As duas strings do protótipo aparecem no cartão; a
  hierarquia visual do protótipo é preservada por `.render.primary` só enquanto o formato
  não existe.
- `[auto-aceito: os chips de estado (ffmpeg/master/CLI) vão para o `.panel-head` do painel 01,
  e `#expMasterInfo` vira a primeira linha do corpo do painel.]` É o que a spec da wave manda
  ("estado ffmpeg/master/CLI como chips no `.panel-head`"), e elimina um painel que o
  protótipo não tem.
- `[auto-aceito: em publish, "Registrar uma publicação" é o painel 01 e a galeria de exports
  fica dentro dele, sob a `eyebrow` "Vídeos prontos em export/".]` O protótipo abre pelo
  registro; separar a galeria em um terceiro painel afastaria a tela do protótipo, e a
  galeria só existe para preencher o `select` do formulário logo acima.
- `[auto-aceito: `#pubComChip` passa a carregar o texto combinado "N publicações · comunidade
  n/3" (era só "n/3").]` É o chip único do painel 02 no protótipo. `#pubPosts` continua
  existindo, no painel 01.
- `[auto-aceito: a coluna "@handle · segmento" do protótipo usa o campo `role` do lead
  (fã/consumidor).]` O modelo de lead não tem segmento por lead — os 6 segmentos da aula são
  uma lista global (`GET /prospect/leads` → `segments`), exibida na `.lesson` e no estado
  vazio.
- `[auto-aceito: `#pitchBox` passa a receber `innerHTML` (markdown escapado + `span.end`) e
  "Copiar" passa a copiar `pitch.markdown`.]` Assim o rodapé "→ prospect/pitch.md" é rótulo
  de tela e não entra no texto copiado.
- `[auto-aceito: `#expLog` nasce `.hidden` e só aparece quando o job tem log.]` Sem isso a
  caixa vazia fica visível no painel 01 em todo carregamento.

---

### 6. Erros, exceções e fallback

Inalterados — todos os `try/catch` das três telas continuam chamando `toast(err.message)`.
Especificamente:

| Situação | Comportamento |
| --- | --- |
| Sem `edit/master.mp4` | `ready()` falso → `#btnRenderAll`, `.render`, `.prev`, `#btnThumb`, `#btnQa`, `#btnReframe` desabilitados; `#expMasterInfo` explica o que falta |
| Job de render em `error` | `#expJobLog` mostra "erro: …"; `#expBar` volta a 0 |
| QA com áudio ausente | `p.fine` de bloqueio antes do `.checks`; o item entra como `.it.warn` com `!` |
| `publish/log.json` corrompido | rotas devolvem lista vazia (já coberto por teste); a tela mostra o `.empty` |
| Export removido de `export/` mas ainda no log | a `.pub-row` acrescenta "— arquivo não está mais em export/" |
| Gate do portfólio fechado | `#leadsPanel` recebe `.hidden` e `#newLeadPanel` é forçado a `.hidden`; a faixa fica `.strip.warn` |
| Lead sem resposta | nenhum `data-act="teaser"` é renderizado (nem na linha, nem no corpo aberto) |
| Teaser em `error` | `#jobChip` vira `.chip.warn` com a mensagem; `toast` |
| Clipboard indisponível | `Studio.ui.copy` cai no fallback `execCommand` |

---

### 7. Observabilidade

Frontend puro, sem métricas de servidor. Os sinais verificáveis são:
- `errors.txt` do `scripts/smoke_ui.py` (claro e escuro) — deve ser vazio;
- saída de `scripts/smoke_ui.py --timers` — 11/11 `OK`, prova de que `destroy()` para o poll;
- `#expJobLog` + `#expLog` (render), `#jobChip` (teaser) e os toasts continuam sendo o
  feedback de progresso ao usuário;
- os chips `#expFfmpeg`/`#expMaster`/`#expHf`, `#pubCounter`/`#pubPosts`/`#pubComChip`/
  `#pubReady`, `#gateChip`/`#todayChip`/`#statusChip` continuam sendo o estado legível da tela.

---

### 8. Dependências e compatibilidade

- **Depende de** `shell-redesign` (`ADH-OS-20260826-02`), já integrada em `develop` @ `a8795bb`:
  `.pn`, `.ext`, `.note`, `details.lesson`, `.fmt-grid`/`.fmt-card`, `.checks`, `.strip[.warn]`,
  `.pipe`, `.rowlist`/`.rowcard`, `.pub-row`, `.lead-row`/`.lead-biz`/`.lead-post`,
  `.pitch`/`.pitch-table`/`.script`, `.gallery.sm`/`.xs`, `.card.wide`, `input.mini`,
  `Studio.ui.pipe`.
- **Não depende de** nenhuma outra frente da sub-wave 1 (arquivos disjuntos).
- Backend, rotas, `steps.py` e `guide.py` inalterados → compatibilidade de API total.
- Nenhuma dependência nova (nem npm, nem pip).
- `docs/domains/{export,publish,prospect}/postman/` intocados: a entrega não muda contrato HTTP.

---

### 9. Critérios de aceite técnicos

1. `make verify` verde (ruff + pytest) na worktree.
2. Testes novos (um por tela) fixam o contrato visual: `.pn` nos painéis, `details.lesson`,
   `#expFormats.fmt-grid` + `fmt-card` + `.checks` no JS de export, `#pubLog.rowlist` +
   `.pub-row`, `#gatePanel.strip.warn` + `#gatePipe` + `.lead-row` + `.pitch-table` +
   `Studio.ui.pipe`.
3. Todas as strings do recon §2 continuam presentes: export ("Etapa 9 · aula 014", sem
   "aulas 007 e 014", "publique o seu trabalho, mesmo imperfeito", "plano 1.4",
   "1:1 é opcional", `[extensão]` ≥ 3×, `id="guide"`, `destroy()`, `Studio.ui.poll`);
   publish ("Etapa 10 · aula 015", "4 vídeos", "feedback", conjunto exato de ids de campo,
   `id="guide"`, "comunidade ABRAhub", "prática, exposição e validação", "perfil novo ou nas
   redes que você já tem", `distinct_videos`, `destroy()`); prospect ("Etapa 11 · aula 001",
   `id="guide"`, os 6 segmentos, `l.replied`, `data-act="teaser"`, `destroy()`).
4. Smoke `scripts/smoke_ui.py` claro, escuro e `--timers`: 0 erro de console, 11/11 etapas.
5. `[cross-feature]` Todo id do recon §1 das três telas existe no DOM renderizado; com o gate
   aberto, o roteiro Playwright registra e apaga uma publicação, cadastra um lead, marca DM
   enviada (o botão do teaser **não** aparece), marca respondeu (o botão do teaser aparece) e
   salva os valores do pitch, tudo sem erro de console.
6. Nenhuma das três telas gera scroll horizontal a 1440 nem a 900 px.
7. Nenhuma funcionalidade removida: preview do corte, render por formato e todos, thumb, QA,
   reframe pelo CLI, seleção de export por tile, feedback por post, checklist da comunidade,
   DM/copiar/enviada/respondeu/teaser/follow-up/call/remover do lead e edição do pitch
   continuam alcançáveis.

---

### 10. Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Um `<input>` novo em publish quebrar o regex do teste | Nenhum campo novo foi criado; o teste roda em cada `make verify` e o FDD registra a restrição em §1 e §5 |
| `.lead-row` ficar apertada com a linha expandida | Corpo expandido em `.pr-body` com `flex:1 0 100%` — quebra para a linha de baixo dentro do mesmo cartão; validado a 1440 e 900 px |
| `input.mini` (48 px do shell) não caber um valor em reais | `<style>` escopado `#pitchValues .pitch-table input.mini{width:76px}`; registrado como lacuna do catálogo |
| Perder o preview do corte ao adotar o botão único do protótipo | Decisão explícita de manter dois botões (§5); as duas strings do protótipo continuam na tela |
| Chip duplo no `.top` do `.fmt-card` (rede-alvo + estado) receber `margin-left:auto` duas vezes | Ambos ficam à direita, na ordem do protótipo; conferido nos prints claro e escuro |
| Painel 01 (Leads) ficar oculto e a numeração visível começar em "02" | Comportamento herdado e correto: o gate esconde o painel de leads como na wave 2; a numeração é a da tela completa |

---

### 11. Sequenciamento de implementação (Build Order)

1. Ler o catálogo (`shell-redesign-fdd.md` §5) e confirmar cada classe em `style.css`. ✔
2. export: `view.html` (4 painéis, `.pn`, `.ext`, `.lesson`) e `view.js`
   (`.fmt-card`, `.checks`, `.card.wide`). ✔
3. publish: `view.html` (2 painéis, registro primeiro) e `view.js`
   (`.pub-row`, chip combinado). ✔
4. prospect: `view.html` (`.strip.warn`, painéis 01/02 fundidos) e `view.js`
   (`.lead-row`, ação por estado, `.pitch-table`/`.script`, `+ Novo lead`). ✔
5. Testes: um assert-set do contrato visual por tela. ✔
6. `make verify` + smoke claro/escuro/`--timers` + roteiro Playwright cross-feature. ✔
7. Commits com `Task-Id: ADH-OS-20260826-08`, push, PR para `develop`. ✔

Arquivos tocados: 6 de código + 3 de teste + este FDD = **10**.
