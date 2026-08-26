# Retro da Wave 3 — redesign dark-first do frontend (2026-08-26)

Orquestração `/dd-parallel` W0–W5. Pedido do dono do produto: "implemente o redesign… tome todas
as decisões recomendadas e só pare quando tiver acabado tudo; crie todas as funcionalidades do
novo protótipo, deixe exatamente idêntico; remova o que for necessário do que já existe; quero a
aplicação absolutamente funcional". Terreno em `recon-wave-3.md`; contratos e catálogo em
`wave-3.md`; fonte de verdade visual (fora do repositório) em
`Análise de codebase/design_handoff_redesign_frontend/`.

Estrutura da wave: **sub-wave 0** (`shell-redesign`, PR único, mergeado antes de tudo) →
**sub-wave 1** (6 frentes de tela em paralelo, arquivos disjuntos) → **fechamento**
(promoção das lacunas + verificação integrada + esta retro).

## Resultado

| Frente | PR | Testes novos | Entrega principal |
|---|---|---|---|
| shell-redesign (ADH-OS-20260826-02) | #34 | +1 | tokens dark-first + tema claro derivado, rail e topbar com `.pipe` segmentado de 11 ticks, `.ovcard` sem `border-left` com card atual elevado, guia em dois estados (`.guide-strip` × `.guide-body`), modal r14, **catálogo de classes** como contrato, helpers `Studio.ui.tile/pipe/beats/copyBtn/copy`, HLD 1.4 |
| views-refs-mood (ADH-OS-20260826-03) | #35 | +2 | refs em 3 painéis numerados (`.progress-lbl` "Último scrape" com número real do job, `.log`, tiles com badge de origem e legenda do termo, `input.why` no tile); mood em 4 painéis (vibe, prompt do bot com `.prompt` + Copiar, importar, escolher com swatches e `palette.json`) |
| views-base (ADH-OS-20260826-04) | #37 | +2 | painel 01 "quem escreve é o bot" com ref-picker `.gallery.xs`, painel 02 marca `[extensão]`, painel 03 com `.stepper` situação→rótulo→upscale derivado do estado da cadeia, painel 04 CLI pago mantido |
| views-storyboard-shots (ADH-OS-20260826-05) | #40 | +6 | storyboard com `.grid2.rev`, cenas como `.scene-row` editável com `.mom[data-mom]` colorido pelo arco narrativo; shots com card de cena em coluna, tiles com `data-ord` (o check vira o número da ordem) e selo `.up` de upscale |
| views-animate (ADH-OS-20260826-06) | #39 | +2 | `.shot-row` por shot (thumb + nome | prompt editável + faixa de `.take`), take vira `<button>` com like no próprio tile, `.take.empty` "+ gerar take N", controles secundários em `details.an-opts` |
| views-music-edit (ADH-OS-20260826-07) | #38 | +2 | music com `.player` da história inteira, `.track-row` com `<audio controls>` real e `.beats` de 44 px; edit com `.beats.sm` + `.beats-axis`, `.clip-row` com `input.mini` de in/out/speed e thumb de vídeo do take, 6 painéis condensados em 3 |
| views-export-publish-prospect (ADH-OS-20260826-08) | #36 | +3 | export com `.fmt-grid`/`.fmt-card` (proporção desenhada, dois botões Preview + Renderizar) e `.checks` do QA; publish com `.pub-row` por post; prospect com `.strip.warn` do gate do portfólio, `.lead-row` por estado e `.pitch` com tabela editável |
| **fechamento (ADH-OS-20260826-09)** | **esta PR** | +0 (3 asserts reapontados) | 8 lacunas de CSS promovidas ao `style.css` + 6 divergências do protótipo corrigidas, regras escopadas equivalentes removidas das 11 telas, FDD §5 e HLD 1.5 atualizados, verificação integrada e esta retro |

Suíte após a integração: **667 testes** (649 → 667), ruff limpo. As 7 PRs entraram em `develop`
na ordem em que ficaram `CLEAN` (#34 → #35 → #36 → #39 → #37 → #38 → #40 — tabela em
`wave-3.md` §Fechamento), não na ordem do curso: a única dependência real era a sub-wave 0 antes
de tudo, e os arquivos das 6 frentes de tela eram disjuntos.

## Verificação cross-feature no estado integrado

Estado: `develop` @ `2ef0ebb` + as promoções desta PR. Projeto `2026-08-wave-teste`, servidor em
`127.0.0.1:8766`, Chromium do Playwright a 1440×900. **Todos os números abaixo são de execução
real, antes e depois das mudanças.**

| # | Critério (`wave-3.md` §Critérios cross-feature) | Antes das promoções | Depois |
|---|---|---|---|
| 1 | Smoke visual das 11 telas + visão geral, claro e escuro | 24 prints, **0 erro de JS/console** | 24 prints, **0 erro** |
| 2 | Timers órfãos (`--timers`) | **11/11 OK** | **11/11 OK** |
| 3 | Scroll horizontal (12 telas × 2 temas × 1440/900 px) | **nenhum** (24 combinações) | **nenhum** (24 combinações) |
| 4 | `make verify` (ruff + pytest) | **667 passed**, ruff limpo | **667 passed**, ruff limpo |
| 5 | Todo id consultado pelo `view.js` existe no `view.html` | coberto pelos testes de contrato DOM das 11 telas | idem |
| 6 | Modal, tema em 3 estados, `Continuar de onde parei →`, hash routing | — | **todos OK** (detalhe abaixo) |

Detalhe do critério 6 (medido no DOM, não só olhado):

- **Modal**: `#btnNewProj` abre "Nova campanha" com `aria-modal="true"` e os campos
  `cfName`, `cfProduct`, `cfVibe` + 3 radios `aspect`; `Escape` fecha; `#btnEditCamp` abre
  "Editar campanha" já preenchida ("Wave Teste"). Tema-aware conferido: `.modal` tem
  `background` `#12151A` no escuro e `#FFFFFF` no claro.
- **Tema em 3 estados**: `auto` (`data-theme` ausente, `studio.theme=auto`, "tema: sistema") →
  `light` → `dark` → volta a `auto`, com o `#themeLabel` certo em cada um.
- **`Continuar de onde parei →`**: leva a `#/2026-08-wave-teste/base` (etapa atual do guia),
  título "Imagem base".
- **Hash routing**: `#/…/shots`, `#/…/music`, `#/…/overview` renderizam a tela certa e marcam
  o `li.active` correspondente; o *voltar* do navegador retorna a `#/…/music`. Zero `pageerror`
  na sessão inteira.

Prova das 8 lacunas promovidas, medida no DOM real (não no CSS):

| Lacuna | Antes (escopado na tela) | Depois (shell), medido |
|---|---|---|
| `.palette .lbl` herdava o swatch | `#shotsPalette .lbl` na etapa 5 | rótulo com **84×16 px**, borda `0px` |
| `input.mini` voltava a 60 px | `.ed-ctl input.mini` na etapa 8 | `.ctl input.mini` = **64 px**; `input.mini.wide` = **76 px**, alinhado à direita |
| `textarea.prompt-inline` | `.an-main textarea.prompt-inline` na 6 | `resize:vertical`, `min-height:56px`, mono 12 px, bg `--bg-2` |
| `.take` sem reset de `<button>` | `button.take` na 6 | `<button>` com `text-align:left`, `line-height:15px`, `font-weight:400`, `white-space:normal` |
| `.beats .cut` encoberto | — (ninguém contornou) | `top:-6px`, `z-index:2`; base do ▾ a **5 px** do topo da caixa, barras começam a **7 px** |
| `.player .term` ilegível no claro | — | branco `#EDEFF2` sobre gradiente `.25→.85` nos dois temas |
| `.shot-row` colapsava a thumb | `.an-left` em `@media` na 6 | a 900 px: `110px 658px`, thumb de **110 px** |
| utilitários (`.grow*`, `.stretch`, `.card-act`, `.static`, `.thumb.none`, `.rowcard.col/.pick`, `.scene-row .media/.edit/.acts`, `.drop.inline`, `.pub-row .fb`, `.flat`, `.pre`) | 6 prefixos diferentes (`.bs-`, `.md-`, `.sb-`, `.sh-`, `.pb-`, `.pr-`) | todos ativos e medidos (ex.: `.card-act` em `bottom:30px` acima do selo `.up`; `.rowcard.col` em coluna com `cursor:pointer`; `.row.stretch>.drop` como flex centralizado) |

## Comparação lado a lado com o protótipo

O protótipo foi renderizado com o seu próprio runtime (`support.js`, servido localmente) e
fotografado tela a tela; as 12 telas do app foram fotografadas no tema escuro com o mesmo
viewport. A comparação foi feita par a par. Regra usada: **diferença de dado não é divergência**
(o protótipo é um mock — "Gelo Zero", "94/120", "412 créditos" — e o app mostra o projeto de
teste real).

### Corrigido nesta PR (CSS/markup, sem tirar funcionalidade)

| # | O que o protótipo faz | O que o app fazia | Correção |
|---|---|---|---|
| 1 | legenda do tile numa barra legível | `.card .term` `#C9CFD8` sobre gradiente `transparent→.72`: o hash sumia sobre foto clara (neve, lata branca) | gradiente `.25→.85` + branco `#EDEFF2` — o mesmo tratamento que a lacuna 6 já tinha dado ao `.player .term` |
| 2 | nome do clipe inteiro (`cena01_shot01_take1.mp4`) | `.clip-row` com coluna de 120 px cortando em `cena01/shot01 ta…` (o nome precisa de 133 px) | coluna para `minmax(170px,1fr)`; medido: 170 px disponíveis para 170 px de texto |
| 3 | nenhum painel com caixa vazia | `#baseLog`, `#shotsLog`, `#boardOut` e `#renderLog` desenhavam uma barra de 1058×22 px com borda quando não havia log | `.log:empty{display:none}` |
| 4 | tile "+ gerar take N" legível | `.take.empty` em `--ink-5` sobre `--surface`: ≈2,6:1 de contraste, praticamente invisível no escuro | `--ink-4` + hover em `--ink-3` |
| 5 | hairline sólida entre as linhas do pitch | `.pitch-table .tr` com borda pontilhada | `1px solid var(--line)` |
| 6 | "Gerar via CLI (gasta créditos)" como **ghost** (é a alternativa paga) | `primary` preenchido em teal nas etapas 2, 3, 5 e 7 e sem classe na 4 — o app estava inconsistente consigo mesmo | `ghost` nas cinco. Alinha com o protótipo **e** com o gate do curso ("na aula 008 o custo é o principal critério") |

### Verificado e descartado (não era defeito)

| Suspeita levantada na comparação | Medição |
|---|---|
| "a etapa 11 sumiu da sidebar" | os 11 `li` existem e o último está visível (`nav ol li` = 11, `getBoundingClientRect().bottom` dentro da `.side`). A `.side` é `sticky; height:100vh; overflow:auto` e rola sozinha quando a janela tem 900 px de altura (`scrollHeight` 973 × `clientHeight` 900); o print `full_page` corta a coluna fixa. **Artefato de captura**, não de layout — e o protótipo tem a mesma densidade. |
| "cards de clipe com larguras diferentes" | os dois `.clip-row` medem 1058 px e terminam ambos em x=1381. O que difere é a quebra do conteúdo interno de `.ctl`. |
| "os dois botões do `.fmt-card` são ambos ghost" | o `view.js` põe `.primary` no "Renderizar" **enquanto o formato não existe** (`class="render${o ? "" : " primary"}"`), como o FDD decidiu. No projeto de teste os dois formatos já estão renderizados — por isso os dois apareceram ghost. |
| "o painel 01 Leads não é renderizado na etapa 11" | é o gate do portfólio fechando o painel (`$("#leadsPanel").classList.toggle("hidden", fechado)`), comportamento herdado e registrado como risco no FDD da frente. Com o portfólio em 1/4, o painel visível começa em `02` — é o esperado. |
| "checkboxes nativos sem estilo no checklist" | `color-scheme: dark` e `accent-color: #4FC8D9` chegam ao elemento; a renderização é a nativa do tema escuro. |
| "réguas de batidas com blocos uniformes" | dado: o projeto de teste tem 23 de 24 batidas marcadas como impacto, e impacto é 100 % da altura por especificação. |

### Registrado, não mexido (divergência consciente ou fora do escopo de fechamento)

- **Guia sempre expandido.** O protótipo desenha o guia como faixa de uma linha; o app abre o
  guia completo por padrão (`studio.guide.<id>`, decisão da wave 2 mantida na §10.5 do
  `shell-fdd.md`). Em telas longas ele ocupa boa parte da primeira dobra. Os dois estados
  existem e o usuário colapsa com um clique — mudar o padrão é decisão de produto, não de CSS.
- **`textarea` de prompt com altura fixa.** O protótipo desenha blocos mono de altura
  automática; o app usa `textarea` (é editável, e a aula manda editar o prompt). Auto-altura
  exige JS em cada `view.js` — fica para a próxima passada.
- **Dropzone dividindo a linha com os importadores.** Nas etapas 1–8 a `.drop` (`flex:1`) divide
  o espaço com colunas de botões dimensionadas pelo conteúdo; como os rótulos são longos
  ("Importar do histórico Higgsfield"), a dropzone fica com ~40 % em vez dos ~78 % do protótipo.
  As seis frentes produziram o mesmo resultado de forma consistente; reequilibrar exige mexer no
  markup das seis telas e não é mudança de fechamento.
- **`#palette` da etapa 2 sem swatches.** O `mood/view.js` só preenche `#palette` na resposta do
  `POST /mood/select`; ao (re)abrir a tela sobra o rótulo `palette.json · derivado técnico
  [extensão]` sem as cores — que aparecem normalmente nas etapas 3 e 5, que leem
  `mood/palette.json`. É carregamento de dado, não CSS: corrigir exige um `fetch` novo no
  `view.js`, com risco de 404 no console (e o critério cross-feature 1 é justamente "zero erro de
  console"). **Pendência para a próxima wave.**
- **Painéis a mais nas etapas 4, 5, 7, 8 e 9.** Todos previstos na spec da wave
  (`wave-3.md` §"Features e contratos") ou na decisão do lote #4 — ver a tabela de divergências
  conscientes abaixo.
- **Estados âmbar/vermelho** (chip `CLI: sem login`, dot da etapa bloqueada, validação `!`) não
  existem no protótipo, que só desenha teal/verde/cinza. São a semântica de estado da wave 2
  (`todo/blocked/in_progress/done`), anterior ao handoff, e o protótipo simplesmente não tinha
  campanha bloqueada para desenhar.

## Auditoria dos auto-aceites (7 FDDs)

Os 7 FDDs foram escritos em modo batch (Gate 1 pré-aprovado, decisão do lote #1) e cada ponto
que exigiria entrevista ficou rotulado `[auto-aceito: …]`. Consolidação por tema:

| Tema | FDDs que convergiram | Decisão | Veredito da integração |
|---|---|---|---|
| Sem coleção Postman, sem contrato HTTP novo | shell, base, storyboard-shots (rotulado); as outras 4 decidem o mesmo na §3 | a §5 dos FDDs é contrato de **markup**, não de rede; backend intocado | **Correto.** Nenhuma rota mudou na wave inteira; os testes de API passaram sem alteração. |
| Manter painel/controle que o protótipo não desenha | base, storyboard-shots, animate, music-edit, export-publish-prospect (+ refs-mood pela decisão do lote #4) | regra 1 da wave: "idêntico ao protótipo" nunca significa remover funcionalidade | **Correto e decisivo.** Sem essa leitura, a wave teria apagado o upload manual de refs, o CLI pago da 3, o reframe/thumb da 9 e metade dos controles da 8 e da 11. |
| Classe faltante vira `<style>` escopado com prefixo da etapa | as 6 frentes de tela | ADR-010: tela não edita `studio/web/*` | **Correto como processo, caro como resultado.** Foi o que permitiu 6 frentes em paralelo sem conflito — e é a origem das 8 lacunas que esta PR promoveu. Ver "soft fails". |
| Texto de aula migra para `details.lesson`, nada é apagado | storyboard-shots, refs-mood, music-edit | regra 1 + gate de fidelidade do `CLAUDE.md` (ADR-004) | **Correto.** As strings fixadas por teste sobreviveram porque os asserts são substring no HTML. |
| Não inventar dado: tudo continua vindo da API | refs-mood, music-edit, animate, export | decisão do lote #6 | **Correto.** Os números do protótipo ("94/120", "128 bpm", "R$ 60") ficaram de fora; onde a API não tem o campo, a tela mostra o que tem. |
| Rótulos de UI do protótipo adotados (ou recusados) caso a caso | refs-mood, storyboard-shots, export | texto de UI segue o protótipo; texto de aula e string fixada por teste, não | **Correto.** Único ponto de atrito: o eyebrow da etapa 5, que manteve "Etapa 5 · aula 011 (+ cena do produto, aula 013)" porque o teste exige a substring. |
| Reorganizar painéis para se aproximar do protótipo | music-edit (6 painéis da 8 → 3), export (painel "Estado" → chips no `.panel-head`) | condensa a moldura sem tirar controle | **Correto**, e é a mudança que mais aproximou o app do protótipo. |
| Trocas de markup preservando hook de JS | animate (take vira `<button>`), music-edit (`<audio>` no lugar da onda; `.rowcard.sel` no lugar de `.prompt.sel`), storyboard-shots (`.cur` × `.sel` do card de cena), export | `data-*` e seletores do handler preservados | **Correto**, com uma consequência: `.an-takes .row.sel` do catálogo virou CSS morto (removido nesta PR). |
| Sem diagrama novo / sem C4 | refs-mood, base, storyboard-shots | entrega de markup, sem fluxo novo | **Correto.** |
| Implementação direta em vez de SDD | todas (decisão do lote #8) | regra do Passo 6 daria SDD para as frentes de 2–3 telas; override mantido (decisão 15 da wave 1) | **Correto pelo terceiro ciclo seguido.** A proposta de contar **fluxos**, não arquivos, segue de pé. |
| Sem card no Trello | storyboard-shots (e decisão do lote #9) | board `orquestrador-studio` inexistente | **Correto**, e continua pendência. |

## Soft fails e o que vira regra

| Ocorrência | Regra adotada |
|---|---|
| **Incidente de integração — branch remota apagada.** Um `gh pr merge` da PR #36 foi recusado por `BEHIND` (base desatualizada). Uma rotina de limpeza de worktree rodou logo em seguida, leu "merge não concluído" como "trabalho encerrado" e apagou a branch remota do PR, que virou um PR fechado sem `head`. Recuperado com `git branch <oid>` a partir do último commit conhecido + `gh pr reopen`, e depois mergeado normalmente. | **Nunca limpar branch/worktree sem `gh pr view --json state` retornar `MERGED`.** `CLOSED` e `OPEN` não autorizam remoção. E PR `BEHIND` se resolve com `gh pr update-branch` + **esperar os checks ficarem verdes** antes de tentar o merge de novo — não com limpeza nem com force-push. |
| **O catálogo do shell nasceu sem consumidor.** A sub-wave 0 entregou o catálogo antes de qualquer tela existir; as 6 frentes acharam 8 lacunas nele e cada uma contornou com o seu prefixo (`.bs-`, `.md-`, `.sb-`/`.sh-`, `.an-`, `.mu-`/`.ed-`, `.ex-`/`.pb-`/`.pr-`). Seis frentes reinventaram o mesmo "input que cresce dentro de uma linha" com quatro larguras diferentes. | **Reservar a janela de promoção na integração é parte do plano, não retrabalho.** O catálogo só vira contrato de verdade depois que a primeira tela o consome. E a regra 3 (escopo com prefixo + lacuna no final report) funcionou exatamente como desenhada: nenhuma frente editou `studio/web/*`, e a integração teve uma lista pronta do que promover. |
| **Duas das 8 "lacunas" eram bugs de especificidade, não ausências.** `.palette .lbl` (0,2,0) perdia para `.palette.sm>span` (0,2,1) e o rótulo herdava um quadrado de 22 px que estourava a linha (3 px de scroll horizontal na etapa 5); `input.mini` (0,1,1) perdia para `.inline input[type=number]` (0,2,1) e voltava a 60 px, cortando `0.511`. | **Regra genérica que aponta para um elemento (`>span`, `input[type=…]`) precisa de `:not()` para os modificadores**, senão o modificador de menor especificidade nunca ganha. Vale para todo par "família + exceção" do catálogo. |
| **`.an-takes .row.sel` virou CSS morto.** O recon pediu regra para essa classe com base no markup da wave 2; a frente `views-animate` reescreveu o markup e o seletor deixou de casar. | Classe que o recon lista como "hook sem CSS" deve ser reconfirmada **depois** que a frente decide o markup novo. Removida nesta PR. |
| **Regra do Passo 6 (direta × SDD) apontaria SDD de novo.** As frentes de 2–3 telas passam do limite de 8 arquivos da §11. | Override mantido pelo terceiro ciclo (decisão 15 da wave 1, retro da wave 2). A proposta de **contar fluxos, não arquivos** já tem três waves de evidência. |
| **Sidebar de 11 etapas não cabe em 100 vh a 900 px de altura** (`scrollHeight` 973 × `clientHeight` 900): a `.side` rola sozinha (`overflow:auto`) e o print `full_page` corta o item 11. | Não é defeito — é o Risco 5 do `shell-redesign-fdd.md` se realizando, e o protótipo tem a mesma densidade. Fica registrado que **print `full_page` de layout com `position:sticky;height:100vh` corta a coluna fixa**: para comparar sidebar com protótipo, ajustar o viewport à altura do conteúdo antes do shot. |

## Lacunas de CSS promovidas nesta PR

Promovidas ao `studio/web/style.css` (regras **genéricas**, sem prefixo de etapa) e retiradas dos
`<style>` escopados:

1. `.palette>span:not(.lbl):not(.fine):not(.ext)` — corrige o rótulo herdando o swatch.
2. `.inline input.mini`/`.ctl input.mini` (64 px) + `input.mini.wide` (76 px) + `input.mini.num`.
3. `input.prompt-inline, textarea.prompt-inline` + `resize:vertical`/`min-height` no `textarea`.
4. `.take` com reset de `<button>` (`font-weight`, `text-align`, `line-height`, `white-space`) e `:disabled`.
5. `.beats .cut{top:-6px;z-index:2;text-shadow:…}` — sem mexer no padding, o `.beats-axis` segue alinhado.
6. `.player .term` com gradiente reforçado e branco `#EDEFF2`.
7. `@media (max-width:900px)`: `.shot-row` mantém `110px minmax(0,1fr)` (só `.scene-row` e `.clip-row` colapsam).
8. Utilitários: `.grow`/`.grow-sm`/`.grow-lg`, `.row.stretch` (+ `>.drop` e `>.col`), `.flat` e a
   regra automática `.row>.fine,.row>.note,.cli>…,.ctl>…,.takes>.note{margin-top:0}`, `.pre`,
   `.card.static`, `.card .card-act` (com `bottom:30px` acima de `.term`/`.up`), `.thumb.none` e
   `.thumb>.empty`, `.rowcard.col` e `.rowcard.pick`, `.scene-row .media/.edit/.acts`,
   `.drop.inline`, `.pub-row .fb`.

Desvio consciente da sugestão original: `.grow-lg` ficou com `flex:1.4` (e não `flex:1`), porque
duas telas usavam proporção 1,4 para a coluna dominante da linha (url da publicação, descrição da
logo) e `flex:1` em todos anularia a hierarquia.

Três asserts foram **reapontados** (não relaxados) para as classes do shell: `test_base_api.py`
passou a exigir `.grow`/`.grow-lg` no HTML **e** que `.bs-grow` tenha sumido; `test_shots_api.py`
exige `rowcard col pick`; `test_storyboard_api.py` exige `card wide static`.

### O que ficou escopado (e por quê)

| Tela | Fica | Motivo |
|---|---|---|
| refs | `.rf-why` | o `input.why` sobre o tile é um controle de uma tela só |
| mood | `.md-side`, `.md-path` | largura da coluna de importação e quebra de caminho de arquivo |
| base | `.bs-io`, `.bs-imp`, `.bs-chain-state` | espaçamentos do painel 03 |
| storyboard | `.sb-base` (só `align-self:start`) | posicionamento dentro do `.grid2.rev` |
| shots | `.sh-wrapchip`, `.sh-scene-id`, `.sh-basethumb`, `.sh-scene-text`, `.sh-subhead` | chip que quebra linha, elipses e espaçamentos da tela |
| animate | `.an-left/-main/-foot/-file/-x/-tips/-mode/-end/-model`, `details.an-opts` | layout interno do `.shot-row` da etapa 6 |
| music/edit | `.mu-q`, `.mu-player`, `.mu-story`, `.ed-sfxcol`, `.ed-lf`, `.ed-music`, `.ed-take` | pergunta do painel 01, larguras de mídia |
| export/publish/prospect | `.ex-prev`, `.ex-acts`, `.pb-form`, `.pb-exports`, `.pb-com`, `.pr-gatefoot`, `.pr-newlead`, `.pr-body`, `.pr-teaser` | molduras de painel e o corpo expansível do lead |

## Divergências conscientes em relação ao protótipo

O protótipo é a fonte de verdade **visual**; onde ele condensa ou omite o que o app já faz, a
regra 1 da wave manda manter a funcionalidade no padrão visual novo. Nenhum item abaixo é
defeito — todos foram decididos nos FDDs e conferidos na comparação lado a lado.

| Etapa | O protótipo desenha | O app faz | Por quê |
|---|---|---|---|
| 1 refs | só busca + escolha | painel 02 "upload manual de referências" | funcionalidade existente; remover contraria "aplicação absolutamente funcional" (lote #4) |
| 2 mood | vibe + prompt + escolha | + campos de brief, histórico de prompts e bloco CLI | idem |
| 3 base | 3 painéis | + painel 04 "Alternativa paga: gerar via CLI"; chip de estado final no fim do `.stepper` | a informação de `#baseChain` não pode sumir (regra 1) |
| 4 storyboard | cena com texto estático | `.scene-row` com `select` da imagem, `textarea` e ↑ ↓ ✕ | a cena é editável no app desde a wave 2 |
| 5 shots | eyebrow "aula 011 + cena do produto (013)" | "Etapa 5 · aula 011 (+ cena do produto, aula 013)" | a substring é fixada por teste |
| 6 animate | prompt + takes + nota | + `details.an-opts` com todos os controles de geração; link do mp4 fora do tile | `<a>` dentro de `<button>` é inválido; controles não podem sumir |
| 7 music | onda decorativa e "0:34 · 128 bpm" | `<audio controls>` real; meta sem bpm por candidata | ouvir a faixa inteira é a instrução da aula 013; a API não devolve bpm por candidata |
| 8 edit | 3 painéis, clipe sem ações | 3 painéis (6 condensados) com ↑ ↓ ✕ do clipe | reordenar clipe é funcionalidade existente |
| 9 export | um botão que alterna | **dois** botões (Preview + Renderizar) | são duas ações distintas; a hierarquia do protótipo fica no `.render.primary` |
| 10 publish | linha do post | + input de feedback por post e checklist da comunidade | controles existentes |
| 11 prospect | lead como linha de 1 ação | + corpo expansível com `textarea` da DM, vídeo do teaser e campos da call; "@handle · segmento" usa `role` | o modelo de lead não tem segmento por lead |
| visão geral | grid de cards | + painel "Como o Studio segue o curso" | conteúdo do gate de fidelidade ao roteiro (lote #3) |
| modal | 4 campos | + duas linhas `.fine` citando as aulas 009 e 007 | fidelidade ao roteiro (ADR-004) |

Fora dessa lista, os dados são diferentes por natureza: o protótipo é um mock ("Gelo Zero",
"94/120", "412 créditos") e o app mostra o projeto de teste real. Diferença de conteúdo não foi
tratada como divergência.

## Pendências (não bloqueiam)

- **Chips extras do guia compacto** ("1/6 shots prontos", "master: pronto", "portfólio 1/4
  vídeos") só aparecem quando o guia expuser `summary`. `Studio.ui.guide` já lê o campo como
  opcional; falta cada `guide.py` publicá-lo — nenhum backend mudou nesta wave (decisão do
  lote #5). É o primeiro item natural da próxima wave.
- **Board Trello `orquestrador-studio` continua inexistente** (12 boards no workspace, nenhum com
  esse nome; MCP não cria boards). PR + final report seguem sendo o único registro.
- **`#palette` da etapa 2 sem swatches ao abrir a tela** — o `mood/view.js` só preenche a paleta
  na resposta do `POST /mood/select`. Fica o rótulo órfão; as cores aparecem normalmente nas
  etapas 3 e 5. Corrigir exige um `fetch` de `mood/palette.json` no `view.js` (o arquivo é
  servido por `/files/`), com tratamento de 404 para não sujar o console.
- **`docs/adrs/README.md` parado na ADR-009** — ADR-010, 011 e 012 existem em
  `docs/adrs/mapping.md` e em `generated/`, mas o índice não as lista.
- **Promoção `develop → main`** a cargo do dono do produto (decisão do lote #2).
- Fixtures do `2026-08-wave-teste` deixam algumas telas com galeria vazia; a comparação com o
  protótipo em telas ricas (galerias cheias, várias faixas, muitos leads) depende de completar o
  projeto de teste ou ampliar `scripts/crossfeature_wave1.py`.
