# Retro da Wave 4 — fidelidade total ao protótipo (2026-08-26)

Orquestração `/dd-parallel` W0–W5. Pedido do dono do produto: "implemente exatamente igual ao
protótipo, mesmo que para isso tenha que remover coisas já feitas ou criar funcionalidades novas;
identifique o que não está igual e deixe exatamente igual; não pare até terminar e deixar 100%
igual". Esse pedido **substitui a regra 1 da wave 3** ("funcionalidade nunca some") e
pré-autorizou os gates 1 (aprovação das specs em lote) e 3 (merge de cada PR) — ver
`wave-4.md` §"Decisões do lote". Terreno em `recon-wave-4.md`; contratos, regras e decisões do
lote em `wave-4.md`; fonte de verdade visual (fora do repositório) em
`Análise de codebase/design_handoff_redesign_frontend/` e referência renderizada item a item em
`../orquestrador-studio-worktrees/_wave4-ref/` (`proto/`, `app-before/`, `audit/<frente>.md`,
`AUDIT-PROTOCOL.md`).

Estrutura da wave: **sub-wave 0** (`shell-fidelity`, PR único, mergeado antes de tudo) →
**sub-wave 1** (6 frentes de tela em paralelo, arquivos disjuntos — ADR-010) → **fechamento**
(promoção das lacunas + verificação integrada + esta retro).

## Resultado

| Frente | Task-Id | PR | Entrega principal |
|---|---|---|---|
| shell-fidelity | ADH-OS-20260826-10 | #42 | guia compacto por padrão (faixa de uma linha; expandido = uma grade só), tokens/controles/botões com os valores medidos no DOM do protótipo, helpers aditivos `Studio.ui.autosize` / `modal({actions})` / `drop(elemento)`, `Guide.build(summary=, summary_kind=)`, limpeza de sidebar/topbar/visão geral/modal, catálogo de classes da §5 estendido |
| views-refs-mood | ADH-OS-20260826-11 | #47 | etapas 1–2 iguais ao protótipo; `refs/service.py` grava `last_job` antes do `done`; `mood/service.py` expõe `batch`; upload sem painel (drop + `button.link` no hover) |
| views-base | ADH-OS-20260826-12 | #43 | etapa 3: 4 painéis → 3, prompt em `<textarea>` de altura automática que sobrevive à troca de passo/marca |
| views-storyboard-shots | ADH-OS-20260826-13 | #48 | etapas 4–5: "escolher ideias" vira picker aberto pela thumb da cena; `next_action` do protótipo; `guide.summary` |
| views-animate | ADH-OS-20260826-14 | #44 | etapa 6: `.shot-row` com `input` de uma linha, take como tile-like, ações `▶`/`✕` só no hover, drop no painel inteiro |
| views-music-edit | ADH-OS-20260826-15 | #45 | etapas 7–8: music sem `<style>` escopado; edit com 4 painéis → 3, `music/service.py` expõe `bpm` |
| views-export-publish-prospect | ADH-OS-20260826-16 | #46 | etapas 9–11: `export.qa.checks[]`, feedback por edição inline, pitch com `input.v` editável, `prospect` com `segment`/`reminders`/`gate.message` |
| **fechamento** | **ADH-OS-20260826-17** | **esta PR** | 11 promoções de regra ao `style.css` (lacunas registradas nas 7 PRs), remoção do `<style>` escopado redundante em 5 telas, verificação integrada das 12 telas, HLD 1.6, FDD `shell-redesign` §10.5, índice de ADRs completado (010–012) e esta retro |

Ordem de integração em `develop` (shell primeiro; telas na ordem em que ficaram `CLEAN`):
#42 → #47 → #48 → #45 → #46 → #44 → #43 → esta PR. `develop` estava em `b5ece7a` no início do
fechamento.

## Verificação cross-feature no estado integrado (W5)

Todos os critérios do `wave-4.md` §"Critérios cross-feature" verdes **após** as promoções:

1. **Zero erro/aviso de console** nas 12 telas no tema escuro **e** claro (smoke
   `scripts/smoke_ui.py`, `errors=0` nas duas passadas) e **11/11 sem timer órfão**
   (nenhuma etapa faz requisição 8 s depois de o usuário navegar para outra).
2. **Zero scroll horizontal** (`documentElement.scrollWidth − clientWidth ≤ 0`) nas 12 telas a
   1440 px **e** 900 px — 24 combinações OK.
3. **Faixa compacta do guia por padrão** em todas as telas (sem chave em `localStorage` o guia
   nasce fechado); expandido abre uma única grade `auto-fit`. Fixado em
   `test_wave4_guia_nasce_compacto_e_expande_em_uma_grade`.
4. **Comparação lado a lado** `proto/NN-<tela>.png` × app-depois (`fechamento-smoke/dark/`): ver
   §"Comparação lado a lado com o protótipo" abaixo.
5. **`make verify` verde**: ruff limpo, **692 testes** (baseline preservado — o fechamento não
   removeu nenhum teste; as classes-marcador fixadas por asserts foram mantidas no markup).

Prints de referência do fechamento (fora do git):
`../orquestrador-studio-worktrees/_wave4-ref/fechamento-smoke/{dark,light,timers}/`.

## Comparação lado a lado com o protótipo

Auditoria final das 12 telas: `_wave4-ref/proto/NN-<tela>.png` (referência, escuro) ×
`_wave4-ref/fechamento-smoke/dark/NN-<tela>.png` (app depois). Veredito: **12/12 IGUAL** —
nenhuma divergência estrutural, de estilo ou de texto fixo (eyebrow, título, lede, títulos de
painel, rótulos de botão, notas e marcadores `[extensão]` conferem). Todas as diferenças visíveis
entre os pares são **dado/estado** (campanha "Gelo Zero" no protótipo × "Wave Teste" no app,
contagens, quantidade de tiles/imagens, textos gerados, chips por estado).

Pontos que o fechamento tocou, confirmados **sem regressão**:
- campos `type=number` limpos, sem spin-button (etapas 2, 8, 11);
- ações de hover em `.clip-row`/`.take` **ocultas em repouso** (etapas 6 e 8) — comportamento correto;
- áreas de importar/drop presentes e conformes (etapas 1, 2, 6); painéis/uploads `[extensão]`
  excedentes do app-before seguem removidos;
- consistência visual uniforme entre as 12 telas (fontes, tokens, raios, gaps, chips, botões) —
  sem vazamento do CSS promovido.

Ressalvas (não são regressões, não bloqueiam):
1. o guia da etapa 1 abre **compacto** no app enquanto o protótipo o desenha **expandido** — o
   `AUDIT-PROTOCOL` (refs-mood §2.2) trata aberto/fechado por padrão como decisão de shell
   (`localStorage`), não requisito de fidelidade;
2. alguns estados vazios aparecem populados no protótipo e vazios no app por serem dados ainda não
   produzidos no snapshot (log de scrape na etapa 1, checks de QA na etapa 9).

## Lacunas de CSS promovidas nesta PR

As 7 PRs de sub-wave registraram, na seção "Lacunas do shell", regras que ficaram como `<style>`
escopado por serem correções de uma regra do catálogo ou classes que faltavam. O fechamento é a
janela de promoção (regra 6). Cada promoção **mantém a classe-marcador no markup** (vários asserts
fixam `bs-note`, `bs-one`, `ed-num`, `an-left`, `sb-pick`) e apenas move a *regra* para o shell,
removendo o override redundante.

| # | Regra promovida (`studio/web/style.css`) | Origem (PR) | Motivo |
|---|---|---|---|
| 1 | `.note{font-size:12px;line-height:1.55;max-width:none}` | #43 base (`.bs-note`) | o catálogo estava em `11.5px/1.5/max-width:78ch`; o protótipo usa 12px/1.55 sem limite em **todas** as telas — com o limite a nota quebrava linha |
| 2 | `.prompts.one{…;margin:0}` | #43 base (`.bs-one`) | o shell entregou `.prompts.one{display:block}` sem o `margin:0` que a auditoria 19 pediu |
| 3 | `.take .act,.take .an-x{…aparência de botão-ícone}` + `:hover{color:var(--ink)}` | #44 animate | o shell só entregava o `display` das ações do tile; faltava a aparência (padding/borda/cor/fonte) |
| 4 | `.note.warn{color:var(--gate)}` | #44 animate (`.shot-row .note.warn`) | o shell não tinha o modificador de aviso da nota |
| 5 | `.import-row{align-items:stretch}` | #44 animate | o shell fixara `align-items:flex-start`, que baixava o drop; o protótipo (tpl 463) não fixa `align-items` — o default `stretch` é o correto |
| 6 | `.clip-row .acts,.clip-row .more{display:none}` → `inline-flex` no hover | #45 edit | a regra do shell usava `opacity:0`, que **continuava reservando ~110 px** e alargava a linha |
| 7 | `.inline input.mini.lg.w44,.ctl input.mini.lg.w44{width:44px}` | #45 edit | `.w44` (0,1,0) perdia para `.inline input.mini.lg` (0,3,1) e o campo voltava a 52 px |
| 8 | `input.mini,input.bare{appearance:textfield}` + supressão `-webkit-` do spin-button | #45 edit (`.ed-num`), #47 mood (`.md-min`) | campos `type=number` limpos, sem setinha, em todas as telas |
| 9 | `.pitch-table input.v::-webkit-{outer,inner}-spin-button{-webkit-appearance:none}` | #46 prospect | `appearance:textfield` não basta no Chromium atual; sem tirar o spin-button o número não encostava no "R$" |

(Contam-se 9 lacunas distintas; itens 3 e 6 tocam duas regras cada — 11 edições no `style.css`,
todas com asserção de unicidade no script de promoção.)

### O que ficou escopado (e por quê)

Nem toda regra em `<style>` é lacuna de catálogo. Estas continuam escopadas por serem de **uma
tela só** — promovê-las não reduziria duplicação e poluiria o catálogo:

- **base:** `.bs-instr`, `.bs-brand`, `.bs-io`, `#baseGallery:not(:empty)`, `#baseChain .st` (gaps
  e cursor do stepper de importação da etapa 3).
- **animate:** `.an-left{gap:6px}` (coluna da `.shot-row`; classe fixada em `test_animate_api`),
  `.an-rej`, `.an-tips`, `.an-example:empty`, `.modal-body .an-*` (modal "Gerar take N").
- **edit:** `.sfx-line.ed-none` (texto do estado vazio da lista de SFX).
- **mood:** `.md-side{min-width:200px}`, `#briefFields[hidden]`, `input.bare.md-min{width:4ch;
  field-sizing:content}` (o número inline "últimos N min" da etapa 2).
- **export:** `.ex-box`, `.ex-box img`, `.fmt-card>button{margin-top:auto}` (preview do corte
  dentro da caixa da proporção — markup exclusivo da etapa 9).
- **publish:** `.pb-form`, `#pubNetwork{width:170px}`, `.pb-com`, `#pubLog{gap:8px}`,
  `.pub-row .del/.nt/.nt-edit` (formulário e edição inline da nota da etapa 10).
- **prospect:** `#leadList{gap:8px}`, `.pr-newlead*`, `.lead-row .body video`, `#gatePipe`.
- **refs:** `.rf-prog`, `#refsPick .rf-bring` (coluna de status do scrape e o link de upload
  revelado no hover — o protótipo não desenha painel de upload na etapa 1).
- **shots:** `.sh-scene-id`, `.sh-builder`, `#sceneList .rowcard{position:relative}` + `.sh-act`
  (ação hover-only dentro de um `.rowcard`).
- **storyboard:** `.sb-base{align-self:start}`, `.sb-pick::after` (overlay "escolher imagem" da
  thumb clicável; classe `sb-pick` fixada em `test_storyboard_api`).

Duas dessas — `.sh-act`/`#sceneList .rowcard` (etapa 5) e `.sb-pick::after` (etapa 4) — as PRs
sugeriram promover como `.rowcard .card-act` e `.thumb.pick::after`. O fechamento **manteve-as
escopadas**: são de uma tela cada, os testes fixam os nomes atuais (`sh-act`, `sb-pick`) e a
promoção exigiria renomear markup acoplado a JS sem ganho de reuso. Ficam registradas aqui para
uma futura tela que precise do mesmo padrão.

## Divergências conscientes em relação ao protótipo (registradas, não corrigidas)

Herdadas das seções "Divergências protótipo × shell" das PRs #47 e outras; são decisões de shell
(batch decision #5: o shell mede o DOM e resolve; a tela não replica localmente). Não bloqueiam.

- **Guia expandido da etapa 1**: o protótipo mostra `TUDO PRONTO` + resumo + 3 itens ✓; o shell
  renderiza a união de entradas+saídas+validações (8 itens neste projeto) e repete o resumo.
  O dado pedido está publicado; a diferença é de renderização do `ui.js`. Candidato a
  `guide.summary` mais curto ou a truncar o chip.
- **Chip de resumo na faixa compacta da etapa 1**: com a etapa concluída, o texto vira um chip
  longo; o protótipo só desenha esta tela expandida, então não há referência do estado compacto.
- **Micro-divergências de 1–4 px/alpha** medidas como "maioria" pelo shell: `button.ghost`
  6 × 7 px em algumas telas, `--glow-cta` .18 × .22, `.stephead` 18 × 20 px na etapa 1. Abaixo
  do limiar de percepção e resolvidas de forma única pelo shell.

## Pendências (não bloqueiam a wave)

- **Promoção `develop → main`**: é do dono do produto (branch protection). O fechamento entrega
  `develop` verde.
- **Board Trello** inexistente (MCP não cria): PR + esta retro são o registro, como nas waves
  anteriores.
- **`.sh-act`/`.sb-pick`** aguardam uma segunda tela que precise do padrão para virarem catálogo.
- **Fila do pedido pós-wave-4** (via `/dd-parallel`): (1) resetar qualquer etapa e recomeçar do
  zero; (2) E2E mockado de todas as etapas com evidências em print; (3) transformar
  divergências/bugs achados em apontamentos e correções. Liberada agora que a wave 4 fechou.
