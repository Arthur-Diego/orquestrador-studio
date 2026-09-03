# QA E2E — BASELINE DE REFERÊNCIA da Wave 10 (migração React) — 2026-09-03 — react-e0

> **Esta rodada não é uma rodada de QA comum: é o ORÁCULO da Wave 10.**
> As dez frentes seguintes (E1…E10) comparam contra os números aqui. Rodada **completa**:
> 14 telas, 382 casos, 56 auditorias (2 temas × 2 viewports), auditoria de API e newman.
> Nenhum código de aplicação foi tocado pela E0 — só ferramental de teste, scaffold e docs.

## 1. Identificação

| Campo | Valor |
| --- | --- |
| Card-pai (Trello) | https://trello.com/c/vIRHoJ81 — [REACT-01] · agregador https://trello.com/c/Bngd5Vwi |
| Task-Id | ADH-OS-20260902-08 |
| Branch / worktree | `refactor/adh-os-20260902-08-react-fundacao` · `orquestrador-studio-worktrees/refactor/adh-os-20260902-08-react-fundacao` |
| Commit base (develop) | `7b6f3b7` |
| Modo | offline |
| Base URL | http://127.0.0.1:8790 |
| Telas pedidas / executadas | shell, overview, refs, mood, base, storyboard, animate, music, edit, export, publish, prospect, moodboards, creditos |
| Rodadas executadas | 1 (rodada completa, sem revalidação) |
| Executado por | Wave 10 · E0 (frente de fundação) |
| Máquina | macOS 25.6 (Darwin), Python 3.12.14, Chromium 151.0.7922.34 |

## 2. Ambiente (saída real do check-env.sh)

```text
PASS: venv em <WORKTREE>/.venv
PASS: fastapi/uvicorn importáveis
PASS: playwright (python) importável
PASS: Chromium do Playwright sobe (v151.0.7922.34)
PASS: PIL importável (fakes/seed)
PASS: ffmpeg no PATH
PASS: ffprobe no PATH
PASS: newman disponível (PATH ou frontend/node_modules)
PASS: gh autenticado (higiene de cards por PR)
INFO: run=react-e0 modo=offline base=http://127.0.0.1:8790
PASS: servidor responde em http://127.0.0.1:8790/api/steps
PASS: servidor serve o frontend (/)
PASS: STUDIO_PROJECTS isolado (fora de <WORKTREE>/projects)
PASS: fake higgsfield ativo no PATH
PASS: fake claude ativo no PATH
PASS: fake higgsfield responde (account status)
PASS: servidor de mídia fake em http://127.0.0.1:8791
PASS: API vê o CLI fake como logado
INFO: git refactor/adh-os-20260902-08-react-fundacao @ 64a8bcb
PASS: árvore git limpa (alterações locais aparecem no diff da rodada)
PRE-VOO OK
```

## 3. Casos executados

| # | Tela | Cenário | Resultado | Evidência |
| --- | --- | --- | --- | --- |
| C-SHELL-01 | shell | sidebar lista as etapas de /api/steps na ordem e marca as 'ready' | PASSA | evidencias/light-1440x900-shell-sidebar.png |
| C-SHELL-02 | shell | clique numa etapa da sidebar navega para #/<pid>/<id> e monta a tela | PASSA | abriu refs |
| C-SHELL-03 | shell | Enter/Espaço numa etapa focada navega (acessibilidade por teclado) | PASSA | Enter abriu mood |
| C-SHELL-04 | shell | wizard: nome vazio bloqueia com toast e não cria campanha | PASSA | evidencias/light-1440x900-shell-wizard-vazio.png |
| C-SHELL-05 | shell | wizard cria campanha com formato 9:16 e seleciona no select | PASSA | evidencias/light-1440x900-shell-wizard-criada.png |
| C-SHELL-06 | shell | editar campanha altera nome/produto e reflete na topbar e no select | PASSA | nome refletido na topbar e no select |
| C-SHELL-07 | shell | botão de tema cicla sistema → claro → escuro e persiste em localStorage | PASSA | evidencias/light-1440x900-shell-tema.png |
| C-SHELL-08 | shell | 'Continuar de onde parei' abre a etapa `current` do guia | PASSA | abriu base |
| C-SHELL-09 | shell | progresso da topbar bate com /api/projects/<pid>.progress | PASSA | topbar '5/10 etapas' |
| C-SHELL-10 | shell | botão 'Resetar etapa' injetado na etapa abre modal listando a cascata | PASSA | evidencias/light-1440x900-shell-reset-modal.png |
| C-SHELL-11 | shell | reset de campanha (overview) apaga artefatos e mantém project.json | PASSA | evidencias/light-1440x900-shell-reset-campanha-modal.png |
| C-SHELL-12 | shell | estado sem campanha: /#/ com projects vazio mostra empty-state com botão de criar | PASSA | pid inexistente cai na 1ª campanha |
| C-SHELL-13 | shell | rota de etapa inexistente cai no overview | PASSA | redirecionou para overview |
| C-SHELL-14 | shell | chip do CLI Higgsfield na sidebar reflete /api/higgsfield/status | PASSA | ● CLI · qa-fake · 9999 créditos |
| C-SHELL-15 | shell | texto do overview consistente com o número real de etapas (/api/steps) | PASSA | evidencias/light-1440x900-shell-texto-etapas.png |
| C-OVERVIEW-01 | overview | um card por etapa, com status igual ao do guia | PASSA | evidencias/light-1440x900-overview-cards.png |
| C-OVERVIEW-02 | overview | botão do card abre a etapa correspondente | PASSA | abriu refs |
| C-OVERVIEW-03 | overview | resumo de status (chips) soma o total de etapas | PASSA | chips=['5 concluída', '4 em andamento', '1 bloqueada'] |
| C-OVERVIEW-04 | overview | campanha vazia: 'Você está na etapa 1' e todas as etapas 'a fazer' | PASSA | evidencias/light-1440x900-overview-vazia.png |
| C-OVERVIEW-05 | overview | trocar campanha no select recarrega o overview da outra campanha | PASSA | topbar='QA Vazia' |
| C-REFS-01 | refs | chip de sessão e rótulo do botão de login refletem /api/pinterest/login | PASSA | evidencias/light-1440x900-refs-sessao.png |
| C-REFS-02 | refs | 'Salvar marca validada' persiste a marca e mostra a nota + toast | PASSA | evidencias/light-1440x900-refs-marca-salva.png |
| C-REFS-03 | refs | a marca validada volta preenchida no campo ao reabrir a etapa | PASSA | campo preenchido com a marca persistida |
| C-REFS-04 | refs | salvar com o campo vazio limpa a marca validada | PASSA | marca limpa (toast='Marca validada limpa') |
| C-REFS-05 | refs | 'Sugerir termos' preenche o textarea com os termos da marca validada | PASSA | evidencias/light-1440x900-refs-sugerir.png |
| C-REFS-06 | refs | 'Sugerir termos' sem marca e sem produto avisa em vez de chamar a API | PASSA | evidencias/light-1440x900-refs-sugerir-sem-insumo.png |
| C-REFS-07 | refs | 'máx. por termo' declara faixa 5–100 e marca valor fora dela como inválido | PASSA | faixa 5–100 (default 30) |
| C-REFS-08 | refs | 'ver o navegador' é um checkbox desmarcado por padrão e alterna pelo rótulo | PASSA | desmarcado por padrão e alterna pelo rótulo |
| C-REFS-09 | refs | 'Buscar e baixar' sem termo avisa e não dispara job nem modal | PASSA | evidencias/light-1440x900-refs-busca-sem-termo.png |
| C-REFS-10 | refs | caminho feliz de 'Buscar e baixar' (scrape real do Pinterest) | BLOQUEADO | o scrape usa rede externa (i.pinimg.com/pinterest.com) e a sessão real do usuário — proibido na rodada offline; só o caminho de erro client-side é coberto (C-RE |
| C-REFS-11 | refs | coluna 'Último scrape' nasce derivada das candidatas, sem dado de exemplo | PASSA | evidencias/light-1440x900-refs-ultimo-scrape.png |
| C-REFS-12 | refs | contador do painel 02 bate com /refs/candidates (candidatas × escolhidas) | PASSA | 2 candidatas · 2 escolhidas |
| C-REFS-13 | refs | cada candidata vira um tile com selo de fonte e legenda do termo | PASSA | evidencias/light-1440x900-refs-tiles.png |
| C-REFS-14 | refs | clicar num tile alterna a marcação e atualiza o contador (sem salvar) | PASSA | '2 candidatas · 2 escolhidas' → '2 candidatas · 1 escolhidas' |
| C-REFS-15 | refs | Espaço num tile focado alterna a marcação (acessibilidade por teclado) | PASSA | Espaço alterna a marcação |
| C-REFS-16 | refs | 'Salvar seleção' copia as escolhidas para refs/brainstorming e avisa | PASSA | evidencias/light-1440x900-refs-salvar-selecao.png |
| C-REFS-17 | refs | desmarcar tudo e salvar remove os arquivos de refs/brainstorming | PASSA | brainstorming esvaziado |
| C-REFS-18 | refs | 'trazer imagens' + upload adiciona candidatas em refs/candidates | PASSA | evidencias/light-1440x900-refs-upload.png |
| C-REFS-19 | refs | upload de arquivo que não é imagem é ignorado sem quebrar a tela | PASSA | evidencias/light-1440x900-refs-upload-invalido.png |
| C-REFS-20 | refs | 'trazer imagens' abre o seletor de arquivos do painel 02 | PASSA | abre #refsUpload (múltiplo) |
| C-REFS-21 | refs | campanha sem candidatas mostra o vazio com o atalho 'traga imagens' | PASSA | evidencias/light-1440x900-refs-vazio.png |
| C-REFS-22 | refs | arrastar imagem sobre o painel 02 marca `.over` e importa como candidata | PASSA | evidencias/light-1440x900-refs-drop.png |
| C-REFS-23 | refs | filtros por termo e por fonte só aparecem quando há mais de um valor | PASSA | evidencias/light-1440x900-refs-filtros.png |
| C-REFS-24 | refs | marcar um termo filtra a grade; somar uma fonte é interseção entre grupos | PASSA | evidencias/light-1440x900-refs-filtros-interseccao.png |
| C-REFS-25 | refs | 'limpar filtros' desmarca tudo, some do DOM e devolve a grade inteira | PASSA | filtros limpos e grade completa |
| C-REFS-26 | refs | filtros são por campanha: trocar de projeto zera as marcações | PASSA | marcações zeradas ao trocar de campanha |
| C-REFS-27 | refs | a seleção salva volta marcada ao reabrir a etapa (persistência) | PASSA | 2 tiles marcados como no disco |
| C-MOOD-01 | mood | a grade lista um card por board de /api/moodboards, com 'nome · N img' | PASSA | evidencias/light-1440x900-mood-lista-boards.png |
| C-MOOD-02 | mood | board sem imagens curadas nasce inativo e não pode ser escolhido | PASSA | evidencias/light-1440x900-mood-board-vazio.png |
| C-MOOD-03 | mood | clicar num board curado marca a escolha e habilita 'Aplicar a esta campanha' | PASSA | evidencias/light-1440x900-mood-escolher-board.png |
| C-MOOD-04 | mood | clicar no board já escolhido desfaz a escolha e desabilita o botão | PASSA | escolha desfeita |
| C-MOOD-05 | mood | Enter num board focado escolhe (acessibilidade por teclado) | PASSA | Enter escolheu o board |
| C-MOOD-06 | mood | 'Aplicar a esta campanha' copia as imagens do board para mood/selected | PASSA | evidencias/light-1440x900-mood-aplicar.png |
| C-MOOD-07 | mood | aplicar grava mood.md, palette.json e a vibe do board na campanha | PASSA | mood.md + palette (6 cores) + vibe='qa vibe gelo neon' |
| C-MOOD-08 | mood | depois de aplicar, a escolha é limpa e o painel 02 mostra o mood novo | PASSA | evidencias/light-1440x900-mood-apos-aplicar.png |
| C-MOOD-09 | mood | reaplicar o mesmo board é idempotente (mood/selected não acumula) | PASSA | 2 imagens após aplicar 2× |
| C-MOOD-10 | mood | aplicar não altera o board na biblioteca (a cópia é da campanha) | PASSA | board segue com 2 imagens |
| C-MOOD-11 | mood | mosaico do mood atual tem uma célula por imagem de GET /mood | PASSA | evidencias/light-1440x900-mood-atual.png |
| C-MOOD-12 | mood | chip de vibe do painel 02 reflete a vibe da campanha | PASSA | vibe: gelo neon ciano, alto contraste |
| C-MOOD-13 | mood | paleta desenha um swatch por cor de palette.json e mantém o rótulo | PASSA | evidencias/light-1440x900-mood-paleta.png |
| C-MOOD-14 | mood | campanha sem mood mostra o vazio apontando para o painel 01 | PASSA | evidencias/light-1440x900-mood-vazio.png |
| C-MOOD-15 | mood | 'Trocar' devolve o usuário ao painel de escolha | PASSA | painel 01 trazido para a viewport |
| C-MOOD-16 | mood | 'Criar / gerenciar mood boards' abre a biblioteca global | PASSA | evidencias/light-1440x900-mood-biblioteca.png |
| C-MOOD-17 | mood | biblioteca vazia: empty-state com 'Ir para a biblioteca' que navega | PASSA | evidencias/light-1440x900-mood-biblioteca-vazia.png |
| C-MOOD-18 | mood | ADR-014: a etapa não oferece importar, curar nem gerar prompt de mood | PASSA | evidencias/light-1440x900-mood-sem-criacao.png |
| C-BASE-01 | base | chip do bot reflete a disponibilidade do Claude em /base/prompts | PASSA | evidencias/light-1440x900-base-chip-bot.png |
| C-BASE-02 | base | tira de referências e preview grande mostram as escolhidas na etapa 1 | PASSA | evidencias/light-1440x900-base-referencias.png |
| C-BASE-03 | base | clicar noutra referência troca a seleção, o preview e o prompt exibido | PASSA | evidencias/light-1440x900-base-troca-referencia.png |
| C-BASE-04 | base | card único de prompt mostra o prompt da referência selecionada | PASSA | evidencias/light-1440x900-base-card-prompt.png |
| C-BASE-05 | base | junção mostra a equação referência + mood → prompt com a paleta da campanha | PASSA | evidencias/light-1440x900-base-juncao.png |
| C-BASE-06 | base | seletor de fonte do mood lista a campanha e os boards da biblioteca | PASSA | evidencias/light-1440x900-base-mood-source.png |
| C-BASE-07 | base | escolher um board como fonte de mood repinta o mosaico com as imagens dele | PASSA | evidencias/light-1440x900-base-mood-source-board.png |
| C-BASE-08 | base | 'De onde vem cada parte' nasce recolhido e abre com a proveniência do prompt | PASSA | evidencias/light-1440x900-base-proveniencia.png |
| C-BASE-09 | base | 'Gerar prompt' abre o modal de fases e traz o texto escrito pelo bot | PASSA | evidencias/light-1440x900-base-gerar-prompt.png |
| C-BASE-10 | base | 'Gerar sem viés' usa sessão nova e registra no_bias no histórico | PASSA | evidencias/light-1440x900-base-gerar-sem-vies.png |
| C-BASE-11 | base | a instrução digitada vai junto ao bot e fica registrada no histórico | PASSA | instrução gravada no histórico |
| C-BASE-12 | base | botão 'Copiar' do card de prompt confirma a cópia na própria linha | PASSA | evidencias/light-1440x900-base-copiar-prompt.png |
| C-BASE-13 | base | histórico de prompts guarda referência, modo e proveniência de cada geração | PASSA | 3 entradas; topo={'ref_id': 'c864a2ed2313', 'mode': 'images', 'source': 'claude', 'created': '2026-09-03T00:09:54'} |
| C-BASE-14 | base | 'Salvar marca' persiste nome e descrição da marca do rótulo | FALHA | evidencias/light-1440x900-C-BASE-14-excecao.png — exceção no caso: TimeoutError: Locator.fill: Timeout 15000ms exceeded. Call log:   - waiting for locator("#brandName")  Traceback (most recent call last):   Fil |
| C-BASE-15 | base | 'Salvar marca' sem nome mostra o erro da aula e não grava nada | FALHA | evidencias/light-1440x900-C-BASE-15-excecao.png — exceção no caso: TimeoutError: Locator.fill: Timeout 15000ms exceeded. Call log:   - waiting for locator("#brandName")  Traceback (most recent call last):   Fil |
| C-BASE-16 | base | no passo 'rótulo' o card de prompt vira a instrução de troca de rótulo | FALHA | evidencias/light-1440x900-C-BASE-16-excecao.png — exceção no caso: KeyError: 'label_prompt_ready' Traceback (most recent call last):   File "<WORKTREE>/orquestrador-studio-worktre |
| C-BASE-17 | base | stepper tem os 3 passos da aula, com 'done' no escolhido e 'on' no ativo | FALHA | evidencias/light-1440x900-base-stepper.png — passos=[{'k': 'situation', 'c': 'st done'}, {'k': 'clean', 'c': 'st'}, {'k': 'label', 'c': 'st on'}, {'k': 'upscale', 'c': 'st'}] escolhidos_api=['situation'] a |
| C-BASE-18 | base | clicar num passo do stepper troca o passo ativo e o rótulo do botão do CLI | PASSA | 'Gerar upscale via CLI' → 'Gerar situação via CLI' |
| C-BASE-19 | base | Enter num passo focado do stepper também troca o passo ativo (teclado) | PASSA | Enter trocou o passo ativo |
| C-BASE-20 | base | upload no painel 03 importa a imagem no passo ativo do stepper | PASSA | evidencias/light-1440x900-base-upload.png |
| C-BASE-21 | base | arrastar sobre a área de drop do painel 03 importa igual ao upload | PASSA | evidencias/light-1440x900-base-drop.png |
| C-BASE-22 | base | 'Importar da pasta Downloads' traz a mídia recente da pasta da rodada | PASSA | evidencias/light-1440x900-base-downloads.png |
| C-BASE-23 | base | 'Importar do histórico Higgsfield' traz os itens que o CLI devolve | PASSA | evidencias/light-1440x900-base-historico-hf.png |
| C-BASE-24 | base | 'Usar como imagem base' só habilita depois de marcar uma candidata | PASSA | gate do botão respeita a marcação |
| C-BASE-25 | base | 'Usar como imagem base' grava base_final.png + base.md e mostra o card final | PASSA | evidencias/light-1440x900-base-fechar.png |
| C-BASE-26 | base | cada candidata vira um tile com o selo do passo e ✓ na escolhida | PASSA | evidencias/light-1440x900-base-galeria.png |
| C-BASE-27 | base | duplo clique numa candidata abre a imagem em tamanho real | PASSA | evidencias/light-1440x900-base-abrir-imagem.png |
| C-BASE-28 | base | 'Gerar via CLI' mostra o custo antes de gastar e cancelar não gera nada | PASSA | evidencias/light-1440x900-base-custo-cancelar.png |
| C-BASE-29 | base | 'Gerar via CLI' do painel 01 gera a situação e mostra o antes → depois | PASSA | evidencias/light-1440x900-base-gerar-cli.png |
| C-BASE-30 | base | sem referência da etapa 1, o CLI avisa em vez de estourar erro cru | PASSA | evidencias/light-1440x900-base-cli-sem-insumo.png |
| C-BASE-31 | base | campanha sem referência mostra o gate da etapa 1 no painel do prompt | PASSA | evidencias/light-1440x900-base-gate-etapa1.png |
| C-BASE-32 | base | o botão de Downloads informa a pasta e a janela de tempo no tooltip | PASSA | tooltip='Últimos 120 min de <WORKTREE>/adh-os-2026 |
| C-BASE-33 | base | ao abrir a etapa, o card de prompt e o passo ativo do stepper concordam | FALHA | evidencias/light-1440x900-base-card-x-stepper.png — o stepper abre em 'label' (load() avança para o 1º passo sem escolha) mas o card do painel 01 continua no prompt de situação: rótulo='Prompt · situação · editáv |
| C-STORYBOARD-01 | storyboard | painel 01 mostra a imagem base e o chip de contagem bate com a API | PASSA | evidencias/light-1440x900-sb-painel01.png |
| C-STORYBOARD-02 | storyboard | #sbKind lista os modos de ideação de /instructions e o title segue o modo | PASSA | 4 modos, title do multishot ok |
| C-STORYBOARD-03 | storyboard | #sbPreset preenche modo e texto com a fórmula da aula | PASSA | preset 'Inpaint: corda proporcional' aplicado |
| C-STORYBOARD-04 | storyboard | #sbGen4 e #sbGen1 montam a instrução com o sufixo da aula e a dica de quantas gerar | PASSA | evidencias/light-1440x900-sb-instrucao.png |
| C-STORYBOARD-05 | storyboard | #sbGen4 com texto vazio: erro amigável e instrução em repouso | PASSA | toast='Escreva a instrução (em inglês, aula 007).' |
| C-STORYBOARD-06 | storyboard | heurística 'uma instrução por vez': dois pedidos são recusados com sugestão | PASSA | evidencias/light-1440x900-sb-uma-instrucao.png |
| C-STORYBOARD-07 | storyboard | #sbCopy: sem instrução avisa; com instrução copia e ecoa 'copiado ✓' | PASSA | toast sem instrução='Monte a instrução primeiro.' eco='copiado ✓' clipboard='Make the climber even smaller and more r' |
| C-STORYBOARD-08 | storyboard | #sbCounts abre o modal 'Importar ideias' com os três caminhos | PASSA | evidencias/light-1440x900-sb-modal-importar.png |
| C-STORYBOARD-09 | storyboard | importar ideias por upload (modal) grava candidato em storyboard/candidates/ | PASSA | evidencias/light-1440x900-sb-import-upload.png |
| C-STORYBOARD-10 | storyboard | importar da pasta Downloads traz as imagens recentes | PASSA | evidencias/light-1440x900-sb-import-downloads.png |
| C-STORYBOARD-11 | storyboard | importar do histórico do CLI traz os jobs (fake higgsfield) | FALHA | evidencias/light-1440x900-sb-import-historico.png — 4→4 ideias; toast=''; fakes.log tem 'generate list'? True |
| C-STORYBOARD-12 | storyboard | arrastar imagem no painel 01 importa sem abrir o modal | PASSA | 4→5 ideias (toast='1 ideias importadas') |
| C-STORYBOARD-13 | storyboard | geração paga de ideias: rota só por API (decisão AP-21), sem comando no painel 01 | PASSA | painel 01 sem comando pago e /storyboard/cost vivo: {'per_image': 7, 'total': 7} |
| C-STORYBOARD-14 | storyboard | painel 02 desenha uma cena por linha, com o momento do arco da aula | PASSA | evidencias/light-1440x900-sb-painel02.png |
| C-STORYBOARD-15 | storyboard | #sbAdd acrescenta a cena só no DOM (scenes.json só muda ao salvar) | PASSA | DOM 5→6, disco estável em 5 |
| C-STORYBOARD-16 | storyboard | #sbSave grava o texto da cena em scenes.json e regrava storyboard.md | PASSA | evidencias/light-1440x900-sb-salvar-cenas.png |
| C-STORYBOARD-17 | storyboard | #sbRender regera o storyboard.md e abre o arquivo | PASSA | md regravado e aberto em storyboard.md |
| C-STORYBOARD-18 | storyboard | #sbRender sem nenhuma cena escrita recusa com mensagem da aula | PASSA | evidencias/light-1440x900-sb-render-vazio.png |
| C-STORYBOARD-19 | storyboard | campanha sem imagem base: #sbGen4/#sbGen1 desabilitados e base escondida | PASSA | evidencias/light-1440x900-sb-sem-base.png |
| C-STORYBOARD-20 | storyboard | #sbReorder: ↑ no modal reordena as cenas e 'Salvar ordem' regrava scenes.json | PASSA | evidencias/light-1440x900-sb-reordenar.png |
| C-STORYBOARD-21 | storyboard | + cena → salvar → ✕ → salvar volta ao número original de cenas | PASSA | 5 → 6 → 5 cenas |
| C-STORYBOARD-22 | storyboard | '+ foto' abre o picker; marcar e Aplicar anexa as ideias como keyframes | PASSA | evidencias/light-1440x900-sb-picker.png |
| C-STORYBOARD-23 | storyboard | 'Sem imagem' no picker limpa a galeria de keyframes da cena | PASSA | 1 → 0 keyframes |
| C-STORYBOARD-24 | storyboard | ★ troca a foto principal e ✕ remove a foto da cena | PASSA | evidencias/light-1440x900-sb-star.png |
| C-STORYBOARD-25 | storyboard | ↑/↓ da foto reordena e persiste a ordem em scenes.json | PASSA | ordem invertida no DOM e no disco |
| C-STORYBOARD-26 | storyboard | clique na foto abre o lightbox em tamanho real | PASSA | evidencias/light-1440x900-sb-lightbox.png |
| C-STORYBOARD-27 | storyboard | 'Gerar prompt' da foto chama o Claude (fake) e mostra a fonte no progresso | PASSA | evidencias/light-1440x900-sb-prompt-video.png |
| C-STORYBOARD-28 | storyboard | 'Gerar prompt' sem descrição falha no modal de progresso com a mensagem da API | PASSA | evidencias/light-1440x900-sb-prompt-video-vazio.png |
| C-STORYBOARD-29 | storyboard | modal 'Gerar animação' traz preview, duração, modelo default e start→end | PASSA | evidencias/light-1440x900-sb-modal-animacao.png |
| C-STORYBOARD-30 | storyboard | 'Gerar animação' sem prompt de vídeo avisa e não abre o modal de custo | PASSA | evidencias/light-1440x900-sb-animar-sem-prompt.png |
| C-STORYBOARD-31 | storyboard | gerar animação: modal de custo → job → mp4 no disco e player na linha-foto | PASSA | evidencias/light-1440x900-sb-modal-custo.png |
| C-STORYBOARD-32 | storyboard | cancelar no modal de custo não gera vídeo nem chama o CLI | PASSA | nenhum mp4 novo (1) |
| C-STORYBOARD-33 | storyboard | recarregar a tela mantém fotos, prompt e vídeo da cena | PASSA | evidencias/light-1440x900-sb-persistencia.png |
| C-STORYBOARD-34 | storyboard | painel 03 lista um card por cena + o card do produto, com N/M upscalados | PASSA | evidencias/light-1440x900-sb-painel03.png |
| C-STORYBOARD-35 | storyboard | abrir uma cena no painel 03 carrega candidatos e título no painel 04 | PASSA | evidencias/light-1440x900-sb-painel04.png |
| C-STORYBOARD-36 | storyboard | reabrir uma cena já salva deveria remarcar os frames escolhidos | PASSA | evidencias/light-1440x900-sb-ordem-persistida.png |
| C-STORYBOARD-37 | storyboard | 'base ▾' abre o menu de base e 'Imagem base da campanha' regrava base.png | PASSA | evidencias/light-1440x900-sb-menu-base.png |
| C-STORYBOARD-38 | storyboard | #btnPrompts monta o prompt de ângulo com foco, escala e ângulo escolhidos | PASSA | evidencias/light-1440x900-sb-prompt-angulo.png |
| C-STORYBOARD-39 | storyboard | modo 'Edição numerada': sem linhas avisa; com linhas numera as modificações | PASSA | evidencias/light-1440x900-sb-prompt-edicao.png |
| C-STORYBOARD-40 | storyboard | copiar o prompt de ângulo ecoa 'copiado ✓' | PASSA | eco='copiado ✓' |
| C-STORYBOARD-41 | storyboard | #shotsCounts abre 'Importar candidatos' e o upload entra na cena | PASSA | evidencias/light-1440x900-sb-modal-import-cena.png |
| C-STORYBOARD-42 | storyboard | escolher frames numera a ordem e #btnShotsSave grava shots + storyboard.json | PASSA | evidencias/light-1440x900-sb-ordem-frames.png |
| C-STORYBOARD-43 | storyboard | #shotsUpscaled marca os frames como upscalados e some o aviso da aula 011 | PASSA | evidencias/light-1440x900-sb-upscaled.png |
| C-STORYBOARD-44 | storyboard | 'Usar como base da cena' promove o candidato a nova base da cena | PASSA | evidencias/light-1440x900-sb-usar-como-base.png |
| C-STORYBOARD-45 | storyboard | cena do produto: sem a imagem 1 os prompts da aula 013 são recusados | PASSA | evidencias/light-1440x900-sb-produto-sem-ref.png |
| C-STORYBOARD-46 | storyboard | cena do produto: enviar a imagem 1 grava storyboard/product/ref.png | PASSA | evidencias/light-1440x900-sb-modal-produto.png |
| C-STORYBOARD-47 | storyboard | cena do produto: #btnPrompts traz as duas instruções da aula 013 | PASSA | evidencias/light-1440x900-sb-produto-prompts.png |
| C-STORYBOARD-48 | storyboard | cena do produto: importar, escolher e salvar grava product_final.png | PASSA | evidencias/light-1440x900-sb-produto-salvo.png |
| C-STORYBOARD-49 | storyboard | cena do produto: 'remover' apaga a escolha e volta o card ao estado inicial | PASSA | evidencias/light-1440x900-sb-produto-removido.png |
| C-STORYBOARD-51 | storyboard | depois de remover, a cena do produto reabre sem candidata marcada | PASSA | evidencias/light-1440x900-sb-produto-estado-apos-remover.png |
| C-STORYBOARD-50 | storyboard | upscale e geração paga dos ângulos: rotas só por API (decisão AP-21) | PASSA | painel 04 sem comando de upscale/geração e /angles/.../cost vivo: total=7 |
| C-ANIMATE-01 | animate | painel 01 lista uma linha por shot do storyboard, na ordem do plano | PASSA | evidencias/light-1440x900-animate-plano.png |
| C-ANIMATE-02 | animate | shot com take escolhido mostra thumb, tile com ♥ e nota 'take 1 escolhido' | PASSA | evidencias/light-1440x900-animate-shot-like.png |
| C-ANIMATE-03 | animate | shot sem take mostra o slot '+ gerar take 1' e a nota da aula (gere 2 e dê like) | PASSA | slot='+ gerar take 1' nota='sem take ainda — gere 2 e dê like no usável' |
| C-ANIMATE-04 | animate | 'Recarregar plano' traz o que mudou no backend para a tela | PASSA | input recarregado com 'QA reload dolly-in' |
| C-ANIMATE-05 | animate | prompt do movimento tem autosave no blur (toast + takes.json) | PASSA | toast='Prompt salvo' e takes.json gravado |
| C-ANIMATE-06 | animate | Enter no campo do prompt tira o foco e grava (sem botão Salvar) | PASSA | toast='Prompt salvo' e prompt gravado por Enter |
| C-ANIMATE-07 | animate | prompt gravado sobrevive ao reload da tela | PASSA | prompt reaparece depois do reload |
| C-ANIMATE-08 | animate | slot '+ gerar take N' abre o modal com modo, duração, câmera, ação, modelo e takes | PASSA | evidencias/light-1440x900-animate-modal-gerar.png |
| C-ANIMATE-09 | animate | modal traz o chip do CLI e o select de modelo com a ordem viva de modelos | PASSA | modelos=['kling2_6', 'seedance_2_0'] selecionado=kling2_6 chip='● CLI · qa-fake · 9999 créditos' |
| C-ANIMATE-10 | animate | modo start/end revela o end frame com o próximo shot da cena e as dicas do modo | PASSA | evidencias/light-1440x900-animate-modal-start-end.png |
| C-ANIMATE-11 | animate | 'Sugerir prompt' preenche o prompt do shot e mostra o exemplo da aula | PASSA | evidencias/light-1440x900-animate-sugerir.png |
| C-ANIMATE-12 | animate | 'mudança lenta' + sugestão leva a duração para 10 s (aula 012) | PASSA | duração 5s → 10s |
| C-ANIMATE-13 | animate | 'Atribuir selecionado' só habilita depois de marcar um vídeo na galeria do modal | PASSA | botão travado sem seleção, liberado com o vídeo marcado |
| C-ANIMATE-14 | animate | atribuir um vídeo importado vira take em takes.json e videos/<cena>/ | PASSA | evidencias/light-1440x900-animate-take-atribuido.png |
| C-ANIMATE-15 | animate | ✕ rejeita o take: conta falha e apaga o shotMM_final.mp4 da etapa 7 | PASSA | evidencias/light-1440x900-animate-take-rejeitado.png |
| C-ANIMATE-16 | animate | clique no tile dá like e recria o shotMM_final.mp4 | PASSA | liked=true e shot01_final.mp4 recriado (nota '♥ take 1 escolhido') |
| C-ANIMATE-17 | animate | Enter no tile focado dá like (o tile é role=button) | PASSA | Enter no tile deu like |
| C-ANIMATE-18 | animate | ▶ do tile abre o mp4 do take em nova aba | PASSA | abriu http://127.0.0.1:8790/files/2026-09-e2e-mock/videos/cena01/shot01_take1.mp4 |
| C-ANIMATE-19 | animate | chip do CLI fica oculto com o CLI logado e o contador reflete /candidates | PASSA | contador='1 vídeos' chip oculto=True |
| C-ANIMATE-20 | animate | upload de mp4 pelo #anUpload importa o vídeo e atualiza o contador | PASSA | evidencias/light-1440x900-animate-upload.png |
| C-ANIMATE-21 | animate | 'Importar da pasta Downloads' varre a pasta configurada e importa os mp4 recentes | PASSA | toast='1 novos de 1 vídeos recentes' · candidato importado da pasta <WORKTREE>/orquestrad |
| C-ANIMATE-22 | animate | 'Importar do histórico Higgsfield' lê o histórico do CLI e reporta jobs e vídeos | PASSA | toast='1 vídeos de 3 jobs' · 1→2 candidatos |
| C-ANIMATE-23 | animate | 'Gerar via CLI' mostra o custo antes; Cancelar não gera nem gasta | PASSA | evidencias/light-1440x900-animate-custo.png |
| C-ANIMATE-24 | animate | gerar 1 take via CLI: modal de progresso, take em takes.json e mp4 em videos/ | PASSA | evidencias/light-1440x900-animate-gerado.png |
| C-ANIMATE-25 | animate | gerar sem prompt falha com mensagem amigável dentro do modal de progresso | PASSA | evidencias/light-1440x900-animate-gerar-sem-prompt.png |
| C-ANIMATE-26 | animate | 'corte para preto' fica gravado no shot e vira aviso na nota da linha | PASSA | fallback_black gravado · nota 'corte para preto' |
| C-ANIMATE-27 | animate | Escape fecha o modal 'Gerar take N' sem gravar nada | PASSA | modal fechou por Escape sem alterar o shot |
| C-ANIMATE-29 | animate | arrastar um mp4 sobre a dropzone importa igual ao seletor de arquivos | PASSA | toast='1 vídeos importados' · mp4 arrastado virou candidato |
| C-ANIMATE-30 | animate | arquivo que não é vídeo é recusado pelo import sem quebrar a tela | PASSA | toast='1 vídeos importados' e nenhum candidato criado |
| C-ANIMATE-31 | animate | 3 falhas no shot: a nota sugere o próximo modelo da ordem (aula 012) | PASSA | evidencias/light-1440x900-animate-3-falhas.png |
| C-ANIMATE-32 | animate | 6 falhas no shot: a nota manda adaptar a ideia ou cortar para preto | PASSA | evidencias/light-1440x900-animate-6-falhas.png |
| C-ANIMATE-33 | animate | shot que saiu do storyboard continua no plano marcado como 'fora do storyboard' | PASSA | linha órfã com nota 'frame ausente · fora do storyboard' |
| C-ANIMATE-34 | animate | pedir mais de 4 takes: o erro do backend chega legível ao usuário | PASSA | evidencias/light-1440x900-animate-takes-invalido.png |
| C-ANIMATE-35 | animate | modo start/end usa o modelo de transição do plano (ADR-023: cena Kling 2.6 / transição Kling 3.0) | PASSA | evidencias/light-1440x900-animate-modelo-transicao.png |
| C-ANIMATE-36 | animate | com 3 falhas, o modal já abre com o modelo sugerido pelo serviço | PASSA | modal abriu em seedance_2_0 (sugerido pelo serviço) |
| C-ANIMATE-37 | animate | salvar o prompt e recarregar o plano ao mesmo tempo não pode devolver erro | PASSA | evidencias/light-1440x900-animate-concorrencia.png |
| C-ANIMATE-28 | animate | campanha sem storyboard: estado vazio aponta a etapa 4 e a importação segue disponível | PASSA | evidencias/light-1440x900-animate-vazio.png |
| C-MUSIC-01 | music | painel 01 reflete /music/story: botão habilitado com clipes e ffmpeg, chip só no aviso | PASSA | evidencias/light-1440x900-music-painel01.png |
| C-MUSIC-02 | music | 'Montar sequência bruta' roda o job com ffmpeg e produz audio/rough_sequence.mp4 | PASSA | evidencias/light-1440x900-music-progresso.png |
| C-MUSIC-03 | music | 'Salvar decisão' sem responder avisa e não grava story_check.json | PASSA | toast='Responda se a história fecha ou se falta cena.' e nada gravado |
| C-MUSIC-04 | music | 'A história fecha' grava story_check.json e volta marcado depois do reload | PASSA | toast='Decisão registrada' · closed=true · radio marcado após reload |
| C-MUSIC-05 | music | 'Falta cena / encerramento mais forte' grava closed=false | PASSA | closed=false gravado e devolvido por /music/story |
| C-MUSIC-06 | music | chip do painel 02 conta as candidatas de /music/candidates e abre o seletor de arquivos | PASSA | chip='1 candidata' for=musUpload |
| C-MUSIC-07 | music | linha da candidata mostra nome, duração e bpm vindos da API | PASSA | evidencias/light-1440x900-music-candidata.png |
| C-MUSIC-08 | music | upload pelo painel 02 importa a música e cria a linha na lista | PASSA | evidencias/light-1440x900-music-upload.png |
| C-MUSIC-09 | music | arrastar um arquivo sobre o painel 02 importa igual ao seletor | PASSA | toast='1 música(s) importada(s)' · arquivo arrastado virou candidata |
| C-MUSIC-10 | music | ▶ toca a faixa da linha e tocar outra pausa a primeira | PASSA | faixa 1 tocou (botão '❚❚') e pausou quando a 2ª começou |
| C-MUSIC-11 | music | clique na onda posiciona a faixa (currentTime e marcador --p) | PASSA | currentTime em 75% da faixa (--p=74.9%) |
| C-MUSIC-12 | music | 'Escolher' grava audio/music.*, detecta as batidas e marca a linha como escolhida | PASSA | evidencias/light-1440x900-music-escolhida.png |
| C-MUSIC-13 | music | painel 03 mostra 'N batidas · M impactos' e uma barra por batida de /music/beats | PASSA | evidencias/light-1440x900-music-batidas.png |
| C-MUSIC-14 | music | redetectar batidas com outro limiar (POST /music/beats) muda a régua da tela | PASSA | impactos 23 → 0, régua e chip acompanham |
| C-MUSIC-18 | music | trilha escolhida sem beats.json: o chip avisa em vez de fingir que há batidas | PASSA | evidencias/light-1440x900-music-sem-beats.png |
| C-MUSIC-19 | music | arquivo que não é áudio é recusado pelo import sem quebrar a tela | PASSA | toast='0 música(s) importada(s)' e nenhuma candidata criada |
| C-MUSIC-15 | music | campanha sem trilha: chip 'nenhuma trilha escolhida', régua vazia e dropzone no painel 02 | PASSA | evidencias/light-1440x900-music-vazio.png |
| C-MUSIC-16 | music | campanha sem takes: painel 01 avisa e não deixa montar a sequência bruta | PASSA | botão desabilitado e chip 'a etapa 5 (animação) ainda não gerou animate/takes.json' |
| C-MUSIC-17 | music | geração de trilha por CLI: rota só por API (decisão AP-21), sem comando na tela | PASSA | tela sem comando de geração paga e /music/generate/cost vivo: {'per_track': 7, 'total': 7, 'raw': {'model': 'sonilo_musi |
| C-EDIT-01 | edit | editor monta as 5 regiões e as 6 faixas da timeline | PASSA | evidencias/light-1440x900-C-EDIT-01-layout.png |
| C-EDIT-02 | edit | #edBack volta para a etapa 6 (música) | PASSA | voltou para music |
| C-EDIT-03 | edit | #edSaveBtn salva: toast, chip 'Salvo' e bloco editor no timeline.json | PASSA | evidencias/light-1440x900-C-EDIT-03-salvar.png |
| C-EDIT-04 | edit | #edAuto desligado segura a gravação; religar dispara o autosave | PASSA | evidencias/light-1440x900-C-EDIT-04-autosave.png |
| C-EDIT-05 | edit | #edAspect/#edRes/#edFps mudam o projeto e persistem em editor.project | PASSA | evidencias/light-1440x900-C-EDIT-05-projeto.png |
| C-EDIT-06 | edit | #edUndo/#edRedo e Ctrl+Z / Ctrl+Shift+Z desfazem e refazem | PASSA | evidencias/light-1440x900-C-EDIT-06-undo.png |
| C-EDIT-07 | edit | #edGuide abre o guia da aula 014 em modal | PASSA | evidencias/light-1440x900-C-EDIT-07-guia.png |
| C-EDIT-08 | edit | #edFull entra e sai de tela cheia | PASSA | entrou e saiu de tela cheia |
| C-EDIT-09 | edit | modal de exportação: pílulas e botões respondem ao clique do mouse | PASSA | evidencias/light-1440x900-C-EDIT-09-modal-export.png |
| C-EDIT-10 | edit | exportar 'Rough cut' roda o ffmpeg e grava edit/rough_cut.mp4 | PASSA | evidencias/light-1440x900-C-EDIT-10-rough.png |
| C-EDIT-11 | edit | exportar master 720p/24fps/baixa grava edit/master.mp4 e registra os parâmetros no job | PASSA | evidencias/light-1440x900-C-EDIT-11-master.png |
| C-EDIT-12 | edit | #edRail alterna os 10 painéis e marca o ativo | PASSA | evidencias/light-1440x900-C-EDIT-12-rail.png |
| C-EDIT-13 | edit | painel Mídia lista os clipes do backbone e a busca filtra | PASSA | evidencias/light-1440x900-C-EDIT-13-midia.png |
| C-EDIT-14 | edit | #mUpload/#mUp importa mídia nova para o editor (disco + card) | PASSA | evidencias/light-1440x900-C-EDIT-14-upload.png |
| C-EDIT-15 | edit | campanha sem takes abre o editor vazio com 'Montar a partir dos takes com like' | PASSA | evidencias/light-1440x900-C-EDIT-15-vazio.png |
| C-EDIT-16 | edit | #mReset numa campanha sem takes mantém a timeline vazia sem erro | PASSA | evidencias/light-1440x900-C-EDIT-16-reset-vazio.png |
| C-EDIT-17 | edit | painel Texto: preset 'Título' cria item na faixa TEXTO (preview, timeline e disco) | PASSA | evidencias/light-1440x900-C-EDIT-17-texto.png |
| C-EDIT-18 | edit | #capGen abre o modal 'Gerar legendas' (roteiro \| áudio, preset, cor) [extensão] | PASSA | evidencias/light-1440x900-C-EDIT-18-capgen.png |
| C-EDIT-19 | edit | painel Legendas oferece adicionar legenda manual (#capAdd) | PASSA | evidencias/light-1440x900-C-EDIT-19-legenda-add.png |
| C-EDIT-20 | edit | painel Legendas lista o item da faixa e o ✕ apaga | PASSA | evidencias/light-1440x900-C-EDIT-20-legenda-del.png |
| C-EDIT-21 | edit | #sfxUp importa SFX, joga na faixa SFX e grava em edit/candidates | PASSA | evidencias/light-1440x900-C-EDIT-21-sfx.png |
| C-EDIT-22 | edit | '+' da biblioteca de SFX insere o efeito no playhead | PASSA | evidencias/light-1440x900-C-EDIT-22-sfx-lib.png |
| C-EDIT-23 | edit | Transições: sem clipe selecionado avisa; com clipe grava a transição escolhida | PASSA | evidencias/light-1440x900-C-EDIT-23-transicao.png |
| C-EDIT-24 | edit | indicador de transição abre o modal e o botão Remover apaga | PASSA | evidencias/light-1440x900-C-EDIT-24-transicao-modal.png |
| C-EDIT-25 | edit | painel Efeitos aplica Blur no clipe selecionado (marca o botão e persiste) | PASSA | evidencias/light-1440x900-C-EDIT-25-efeito.png |
| C-EDIT-26 | edit | painel Filtros: preset aplicado ao clipe é gravado na timeline | PASSA | evidencias/light-1440x900-C-EDIT-26-filtro.png |
| C-EDIT-27 | edit | painel Elementos adiciona forma na faixa VÍDEO 2 (overlay) | PASSA | evidencias/light-1440x900-C-EDIT-27-elemento.png |
| C-EDIT-28 | edit | #pcPlay e a tecla Espaço tocam e pausam | PASSA | evidencias/light-1440x900-C-EDIT-28-play.png |
| C-EDIT-29 | edit | transporte: #pcStart/#pcPrev/#pcNext/#pcEnd e setas ←/→ movem o playhead | PASSA | evidencias/light-1440x900-C-EDIT-29-transporte.png |
| C-EDIT-30 | edit | #pcLoop, #pcMute e #pcVol alternam o estado do player | PASSA | evidencias/light-1440x900-C-EDIT-30-loop-mute.png |
| C-EDIT-31 | edit | painel Projeto (sem seleção): #pFade e #pLoud gravam fade_out e loudnorm | PASSA | evidencias/light-1440x900-C-EDIT-31-projeto.png |
| C-EDIT-32 | edit | aba Básico: X/Y/escala/rotação/opacidade/flip gravam clip_fx.transform | PASSA | evidencias/light-1440x900-C-EDIT-32-basico.png |
| C-EDIT-33 | edit | aba Vídeo: in/out/zoom gravam o trim não destrutivo em clips[] | PASSA | evidencias/light-1440x900-C-EDIT-33-video.png |
| C-EDIT-34 | edit | aba Áudio do clipe: volume/mudo ficam guardados em clip_fx.audio (FDD rodada 2 §4) | PASSA | evidencias/light-1440x900-C-EDIT-34-audio-clipe.png |
| C-EDIT-35 | edit | aba Velocidade: preset 2x muda speed no disco e rotula o clipe na timeline | PASSA | evidencias/light-1440x900-C-EDIT-35-velocidade.png |
| C-EDIT-36 | edit | aba Ajustes: sliders gravam clip_fx.filters e #cReset zera | PASSA | evidencias/light-1440x900-C-EDIT-36-ajustes.png |
| C-EDIT-37 | edit | props de texto: #txSh e #txUp gravam sombra/maiúsculas no estilo do item | PASSA | evidencias/light-1440x900-C-EDIT-37-texto-props.png |
| C-EDIT-38 | edit | props da música: #mMute deixa a trilha muda e o estado persiste | PASSA | evidencias/light-1440x900-C-EDIT-38-musica.png |
| C-EDIT-39 | edit | clicar num clipe seleciona (borda, contador e painel de propriedades) | PASSA | evidencias/light-1440x900-C-EDIT-39-selecao.png |
| C-EDIT-40 | edit | #tSplit e Ctrl+B dividem o clipe sob o playhead | PASSA | evidencias/light-1440x900-C-EDIT-40-split.png |
| C-EDIT-41 | edit | #tDup e Ctrl+D duplicam o clipe selecionado | PASSA | evidencias/light-1440x900-C-EDIT-41-dup.png |
| C-EDIT-42 | edit | #tDel/Delete excluem o clipe — inclusive o último (montagem vazia é editável) [wave 8] | PASSA | evidencias/light-1440x900-C-EDIT-42-excluir.png |
| C-EDIT-43 | edit | #tRipple remove o clipe e pode esvaziar a montagem (quem exige clipe é a exportação) [wave 8] | PASSA | evidencias/light-1440x900-C-EDIT-43-ripple.png |
| C-EDIT-44 | edit | arrastar um clipe na timeline solta-o na posição livre (modo posicional) | PASSA | evidencias/light-1440x900-C-EDIT-44-drag.png |
| C-EDIT-45 | edit | arrastar a borda direita do clipe faz o trim (in/out) na timeline | PASSA | evidencias/light-1440x900-C-EDIT-45-trim.png |
| C-EDIT-46 | edit | zoom da timeline (#zIn/#zOut/#zR) muda a escala e o nível sobrevive ao reload | PASSA | evidencias/light-1440x900-C-EDIT-46-zoom.png |
| C-EDIT-47 | edit | #tMark crava um marcador no playhead (régua + editor.markers) | PASSA | evidencias/light-1440x900-C-EDIT-47-marcador.png |
| C-EDIT-48 | edit | cabeçalhos das faixas: VÍDEO 1 é do backbone e as faixas do editor escondem/travam | PASSA | evidencias/light-1440x900-C-EDIT-48-heads.png |
| C-EDIT-49 | edit | botão direito num clipe abre o menu de contexto com as ações do clipe | PASSA | evidencias/light-1440x900-C-EDIT-49-menu.png |
| C-EDIT-50 | edit | preview continua mostrando o vídeo do clipe depois de uma edição | PASSA | evidencias/light-1440x900-C-EDIT-50-preview.png |
| C-EDIT-51 | edit | edições sobrevivem ao reload da tela (GET timeline + DOM) | PASSA | evidencias/light-1440x900-C-EDIT-51-persistencia.png |
| C-EDIT-52 | edit | trilha do projeto toca no preview (<audio> no palco, sai do pausado e anda) | PASSA | evidencias/light-1440x900-C-EDIT-52-musica-toca.png |
| C-EDIT-53 | edit | SFX ganha <audio> próprio e dispara quando o playhead cruza o seu `at` | PASSA | evidencias/light-1440x900-C-EDIT-53-sfx-toca.png |
| C-EDIT-54 | edit | elemento do painel guarda o id da forma e o preview desenha a forma (não um caractere) | PASSA | evidencias/light-1440x900-C-EDIT-54-elemento-forma.png |
| C-EDIT-55 | edit | vídeo do painel Mídia vai para a faixa VÍDEO 2 (overlay com src de vídeo) | PASSA | evidencias/light-1440x900-C-EDIT-55-video-v2.png |
| C-EDIT-56 | edit | botão de ação das linhas dos painéis cabe o rótulo e fica alinhado à direita | PASSA | evidencias/light-1440x900-C-EDIT-56-radd.png |
| C-EXPORT-01 | export | um card por formato, com proporção, destino e chip igual ao /export/status | PASSA | evidencias/light-1440x900-export-cards.png |
| C-EXPORT-02 | export | formato já renderizado mostra 'Ver arquivo' com medidas no title | PASSA | title='export/16x9.mp4 · 1920x1080 · 1.0s' |
| C-EXPORT-03 | export | 'Ver arquivo' abre /files/<pid>/export/<fmt>.mp4 em nova aba | PASSA | abriu /files/2026-09-e2e-mock/export/16x9.mp4 |
| C-EXPORT-04 | export | 'Renderizar todos' habilitado e com as medidas do master no title | PASSA | habilitado, title='edit/master.mp4 · 1280x720 · 1.0s' |
| C-EXPORT-05 | export | chips de bloqueio ficam ocultos quando há ffmpeg e master | PASSA | nenhum chip de falta visível |
| C-EXPORT-06 | export | clique na caixa da proporção gera o preview do corte central em disco | PASSA | evidencias/light-1440x900-export-preview.png |
| C-EXPORT-07 | export | renderizar um formato faltante: modal de progresso, log real e arquivo em disco | PASSA | evidencias/light-1440x900-export-render-modal.png |
| C-EXPORT-08 | export | 'Renderizar todos' com arquivos existentes pede confirmação; cancelar não mexe no disco | PASSA | confirm='Já existe arquivo para 16x9, 9x16, 1x1. Renderizar de novo s' e nada foi regravado |
| C-EXPORT-09 | export | 'Renderizar todos' confirmado regrava os três formatos com um passo por formato | PASSA | evidencias/light-1440x900-export-render-all.png |
| C-EXPORT-10 | export | #expLog e a barra de progresso ficam escondidos quando não há job em erro | PASSA | job=done, log e barra ocultos |
| C-EXPORT-11 | export | 'Gerar QA' grava export/qa_report.md e desenha o grid de checks | PASSA | evidencias/light-1440x900-export-qa.png |
| C-EXPORT-12 | export | grid do QA persiste depois de recarregar a tela (vem do status, não do POST) | PASSA | 5 checks após reload |
| C-EXPORT-13 | export | cada check do grid usa a marca do seu tipo (✓ ok · ! atenção · ✕ falha) | PASSA | marcas=['✓', '✓', '✓', '✓', '✓'] |
| C-EXPORT-14 | export | sem master: chip explica a etapa 7 e todos os comandos ficam desabilitados | PASSA | evidencias/light-1440x900-export-vazio.png |
| C-EXPORT-15 | export | sem master: clicar na caixa da proporção não gera preview nem erro na tela | PASSA | clique ignorado (ready() falso), sem toast de erro |
| C-EXPORT-16 | export | sem master: title do 'Renderizar todos' aponta a etapa 7 | PASSA | title='conclua a etapa 7 para gerar edit/master.mp4' |
| C-EXPORT-17 | export | reframe: rota só por API (decisão AP-21) — custo responde em créditos, tela sem comando | PASSA | custo=7 créditos; tela não expõe o comando |
| C-EXPORT-18 | export | reframe: proporção inválida responde 422 com mensagem amigável | PASSA | 422 'proporção inválida: use 9:16 ou 1:1' |
| C-EXPORT-19 | export | reframe sem master responde 404 apontando a etapa 7 | PASSA | 404 'edit/master.mp4 não encontrado; conclua a etapa 7' |
| C-EXPORT-20 | export | guia da etapa reflete o estado do export depois de gerar o QA | PASSA | evidencias/light-1440x900-export-guia.png |
| C-EXPORT-21 | export | os formatos renderizados aparecem para a etapa 9 em /publish/exports | PASSA | etapa 9 enxerga ['16x9.mp4', '1x1.mp4', '9x16.mp4'] |
| C-PUBLISH-01 | publish | select de vídeo lista os exports de /publish/exports | PASSA | evidencias/light-1440x900-publish-select.png |
| C-PUBLISH-02 | publish | campo de data já vem com a data de hoje | PASSA | data=2026-09-03 |
| C-PUBLISH-03 | publish | datalist de redes sugere as redes da aula, inclusive a comunidade ABRAhub | PASSA | sugestões=['instagram', 'tiktok', 'youtube', 'comunidade ABRAhub', 'outro'] |
| C-PUBLISH-04 | publish | sem rede: toast pedindo a rede e nada gravado no log | PASSA | evidencias/light-1440x900-publish-sem-rede.png |
| C-PUBLISH-05 | publish | URL sem http/https: toast explicando o formato e nada gravado | PASSA | toast='a URL da publicação precisa começar com http:// ou https://' |
| C-PUBLISH-06 | publish | URL já registrada: toast de duplicidade e log intacto | PASSA | toast='URL já registrada' |
| C-PUBLISH-07 | publish | registrar publicação: linha na lista, entrada em publish/log.json e portfolio.md regravado | PASSA | evidencias/light-1440x900-publish-registrado.png |
| C-PUBLISH-08 | publish | cada linha traz chip da rede, URL encurtada e data/arquivo no title | PASSA | evidencias/light-1440x900-publish-lista.png |
| C-PUBLISH-09 | publish | anotar feedback: Enter grava em log.json e a linha passa a mostrar a nota | PASSA | evidencias/light-1440x900-publish-nota.png |
| C-PUBLISH-10 | publish | anotar feedback: Escape descarta a edição sem gravar | PASSA | edição descartada |
| C-PUBLISH-11 | publish | 'Remover' com a confirmação recusada mantém o registro | PASSA | confirm='Remover este registro de publicação? O post continua no ar n' e o post continua |
| C-PUBLISH-12 | publish | 'Remover' confirmado faz DELETE, tira a linha da lista e do log.json | PASSA | evidencias/light-1440x900-publish-removido.png |
| C-PUBLISH-13 | publish | chip do painel 02 conta publicações e o checklist de comunidade | PASSA | chip='4 publicações · comunidade 0/3' |
| C-PUBLISH-14 | publish | marcar 'postei na comunidade' grava publish/community.json e atualiza o chip | PASSA | evidencias/light-1440x900-publish-comunidade.png |
| C-PUBLISH-15 | publish | desmarcar um item da comunidade volta o arquivo para false | PASSA | item desmarcado e persistido |
| C-PUBLISH-16 | publish | os três checkboxes data-com refletem o arquivo depois de recarregar a tela | PASSA | checkboxes={'posted': True, 'commented': False, 'feedback': True} chip='4 publicações · comunidade 2/3' |
| C-PUBLISH-17 | publish | portfólio global conta PROJETOS distintos com post (ADR-012), não arquivos | PASSA | evidencias/light-1440x900-publish-portfolio.png |
| C-PUBLISH-18 | publish | campanha sem export: select avisa e a lista mostra o empty-state | PASSA | evidencias/light-1440x900-publish-vazio.png |
| C-PUBLISH-19 | publish | campanha sem export: registrar mostra o erro amigável do backend | PASSA | evidencias/light-1440x900-publish-vazio-erro.png |
| C-PUBLISH-21 | publish | todo campo do formulário tem rótulo acessível (label, aria-label ou placeholder) | PASSA | evidencias/light-1440x900-publish-rotulos.png |
| C-PUBLISH-20 | publish | arquivo que saiu de export/ vira aviso no title da linha | PASSA | evidencias/light-1440x900-publish-orfao.png |
| C-PROSPECT-01 | prospect | gate aberto: chip N/4, pipe com um segmento por obra e '+ Novo lead' habilitado | PASSA | evidencias/light-1440x900-prospect-gate.png |
| C-PROSPECT-02 | prospect | gate é GLOBAL (ADR-012): campanha sem publicação mostra o mesmo estado | PASSA | evidencias/light-1440x900-prospect-gate-vazio.png |
| C-PROSPECT-03 | prospect | portfólio abaixo de 4 obras fecha o gate: '+ Novo lead' desabilitado e formulário escondido | PASSA | evidencias/light-1440x900-prospect-gate-fechado.png |
| C-PROSPECT-04 | prospect | gate fechado recusa a criação de lead no backend (409 com a frase da aula) | PASSA | 409 'A aula pede quatro obras diferentes antes de prospectar — falta 1 campanha.' |
| C-PROSPECT-05 | prospect | '+ Novo lead' revela o formulário inline e põe o foco no negócio | PASSA | evidencias/light-1440x900-prospect-form.png |
| C-PROSPECT-06 | prospect | campos obrigatórios: submit vazio é barrado e nenhum lead é criado | PASSA | evidencias/light-1440x900-prospect-obrigatorios.png |
| C-PROSPECT-07 | prospect | sem o post citado, a API recusa com a frase da aula ('cite um post específico') | PASSA | 422 'cite um post específico do perfil: é isso que a aula manda mostrar ("olhou o per' e #lfPostRef required |
| C-PROSPECT-08 | prospect | cadastrar lead: linha na lista, DM com o script literal e prospect/leads.json em disco | PASSA | evidencias/light-1440x900-prospect-lead-criado.png |
| C-PROSPECT-09 | prospect | handle repetido: toast de duplicidade e nenhum lead novo | PASSA | toast='handle já cadastrado: @qaleadteste' |
| C-PROSPECT-10 | prospect | 'Gerar DM (script da aula)' abre o corpo do lead com o script e as ações | PASSA | evidencias/light-1440x900-prospect-dm.png |
| C-PROSPECT-11 | prospect | 'Copiar DM' põe o script na área de transferência | PASSA | botão='copiado ✓' e clipboard com 291 caracteres |
| C-PROSPECT-12 | prospect | 'Marquei como enviada' muda o status para 'DM enviada' e sobe o contador do dia | PASSA | evidencias/light-1440x900-prospect-enviada.png |
| C-PROSPECT-13 | prospect | 'Marcar respondeu' muda o estado e a ação principal vira 'Gerar teaser 5–10s' | PASSA | evidencias/light-1440x900-prospect-respondeu.png |
| C-PROSPECT-14 | prospect | responder antes de enviar a DM é recusado (422) — a tela nem oferece o caminho | PASSA | 422 'marque a DM como enviada antes de registrar a resposta' |
| C-PROSPECT-15 | prospect | 'Gerar teaser 5–10s': modal de progresso e prospect/teasers/<lead>.mp4 com música | PASSA | evidencias/light-1440x900-prospect-teaser-modal.png |
| C-PROSPECT-16 | prospect | 'Refazer teaser' pede confirmação; recusar não regrava o arquivo | PASSA | confirm='Isso substitui o teaser atual deste lead. Continuar?' e o teaser não foi refeito |
| C-PROSPECT-17 | prospect | 'Copiar follow-up' copia o texto literal da aula (convite para a call de 15 min) | PASSA | follow-up copiado ('Aqui está o início. Se quiser, podemos agendar uma…') |
| C-PROSPECT-18 | prospect | 'Registrar call' sem data mostra toast pedindo a data e não grava nada | PASSA | toast='escolha a data da call' |
| C-PROSPECT-19 | prospect | 'Registrar call' com data e nota grava call_at e muda o estado para 'call agendada' | PASSA | evidencias/light-1440x900-prospect-call.png |
| C-PROSPECT-20 | prospect | marcar 'feita' junto com a data registra a call como concluída | PASSA | status=call_done |
| C-PROSPECT-21 | prospect | 'Remover' apaga o lead e o teaser dele do disco | PASSA | evidencias/light-1440x900-prospect-removido.png |
| C-PROSPECT-22 | prospect | campanha sem leads: empty-state cita os segmentos do mar azul da aula | PASSA | evidencias/light-1440x900-prospect-vazio.png |
| C-PROSPECT-23 | prospect | caixa do pitch traz os lembretes da aula e aponta prospect/pitch.md | PASSA | evidencias/light-1440x900-prospect-pitch.png |
| C-PROSPECT-24 | prospect | 'Copiar' do pitch põe o markdown (tabela de etapas) na área de transferência | PASSA | markdown copiado (1249 caracteres) |
| C-PROSPECT-25 | prospect | 'Salvar valores e regerar' grava prospect/pitch.json e regrava prospect/pitch.md | PASSA | evidencias/light-1440x900-prospect-pitch-salvo.png |
| C-PROSPECT-26 | prospect | total diferente da soma das etapas avisa no toast e no title do total | PASSA | toast='pitch.md salvo — a soma das etapas (R$ 210) é diferente do total' e title='soma das etapas: R$ 210 — diferente do |
| C-PROSPECT-27 | prospect | total fora da faixa de R$ 100 a R$ 500 avisa a ancoragem inicial da aula | PASSA | toast='pitch.md salvo — a aula manda começar entre R$ 100 e R$ 500' |
| C-PROSPECT-28 | prospect | a tela não desenha o painel do guia: a faixa do gate ocupa o lugar dele | PASSA | #guide removido, #gatePanel presente |
| C-MOODBOARDS-01 | moodboards | biblioteca lista um card por board de /api/moodboards, com contagem e mosaico | PASSA | evidencias/light-1440x900-mb-lista.png |
| C-MOODBOARDS-02 | moodboards | clique no card abre o editor #/moodboards/<mbid> | PASSA | editor de 'QA Board' |
| C-MOODBOARDS-03 | moodboards | Enter no card focado abre o editor (acessibilidade por teclado) | PASSA | Enter abriu o editor |
| C-MOODBOARDS-04 | moodboards | 'Novo mood board' abre modal com nome e nota | PASSA | evidencias/light-1440x900-mb-modal-novo.png |
| C-MOODBOARDS-05 | moodboards | nome vazio bloqueia a criação com toast e mantém o modal aberto | PASSA | evidencias/light-1440x900-mb-nome-vazio.png |
| C-MOODBOARDS-06 | moodboards | nome duplicado devolve 409 com mensagem amigável no toast | PASSA | evidencias/light-1440x900-mb-nome-duplicado.png |
| C-MOODBOARDS-07 | moodboards | criar board pelo modal grava no disco e abre o editor do board novo | PASSA | evidencias/light-1440x900-mb-board-criado.png |
| C-MOODBOARDS-08 | moodboards | editor mostra nome, pasta real do board e os três painéis | PASSA | evidencias/light-1440x900-mb-editor.png |
| C-MOODBOARDS-09 | moodboards | '← Biblioteca' volta para a lista | PASSA | voltou para a biblioteca |
| C-MOODBOARDS-10 | moodboards | renomear altera nome e vibe (PATCH) e reflete no título | PASSA | evidencias/light-1440x900-mb-renomear.png |
| C-MOODBOARDS-11 | moodboards | upload de imagem importa a candidata (toast, painel 01 e candidates/ no disco) | PASSA | evidencias/light-1440x900-mb-upload.png |
| C-MOODBOARDS-12 | moodboards | 'Importar da pasta Downloads' traz o PNG recente de STUDIO_DOWNLOADS | PASSA | evidencias/light-1440x900-mb-downloads.png |
| C-MOODBOARDS-13 | moodboards | 'Importar do histórico Higgsfield' traz as 3 imagens do CLI | PASSA | evidencias/light-1440x900-mb-historico.png |
| C-MOODBOARDS-14 | moodboards | 'usar no board' move a candidata do painel 01 para o 02 e atualiza as contagens | PASSA | evidencias/light-1440x900-mb-usar-no-board.png |
| C-MOODBOARDS-15 | moodboards | 'Salvar seleção' copia para images/, deriva a paleta e pinta os swatches | PASSA | evidencias/light-1440x900-mb-salvar-selecao.png |
| C-MOODBOARDS-16 | moodboards | clicar na imagem do painel 02 tira do board e salvar remove de images/ | PASSA | evidencias/light-1440x900-mb-tirar-do-board.png |
| C-MOODBOARDS-17 | moodboards | teto de 8 imagens: salvar 9 escolhidas devolve erro amigável (ADR-007) | PASSA | evidencias/light-1440x900-mb-teto-8.png |
| C-MOODBOARDS-18 | moodboards | '▨ ângulos' abre o modal de multishot com a imagem de origem | PASSA | evidencias/light-1440x900-mb-multishot-modal.png |
| C-MOODBOARDS-19 | moodboards | multishot: 'Gerar' abre o modal de custo e cancelar não gera nada | PASSA | evidencias/light-1440x900-mb-multishot-custo.png |
| C-MOODBOARDS-20 | moodboards | multishot: confirmar gera o ângulo (fake), mostra o carrossel e 'remover' apaga | PASSA | evidencias/light-1440x900-mb-multishot-gerado.png |
| C-MOODBOARDS-21 | moodboards | multishot: 'Importar fotos' abre o modal de importação com a pasta Downloads | PASSA | evidencias/light-1440x900-mb-multishot-importar.png |
| C-MOODBOARDS-22 | moodboards | painel 03 reflete o bot disponível e habilita os três modos | PASSA | chip='bot: claude ok', modos=[['images', False], ['brief', False], ['template', False]] |
| C-MOODBOARDS-23 | moodboards | modo template gera o prompt sem modal e grava prompt.txt | PASSA | evidencias/light-1440x900-mb-prompt-template.png |
| C-MOODBOARDS-24 | moodboards | modo imagens abre o modal de progresso e grava o prompt do bot em prompts.json | PASSA | evidencias/light-1440x900-mb-prompt-imagens.png |
| C-MOODBOARDS-25 | moodboards | modo imagens sem imagem escolhida avisa e não chama a API | PASSA | evidencias/light-1440x900-mb-prompt-sem-imagem.png |
| C-MOODBOARDS-26 | moodboards | desmarcar 'sem pessoas' é registrado no histórico do prompt | PASSA | evidencias/light-1440x900-mb-prompt-no-people.png |
| C-MOODBOARDS-27 | moodboards | board inexistente mostra mensagem amigável com volta para a biblioteca | PASSA | evidencias/light-1440x900-mb-inexistente.png |
| C-MOODBOARDS-28 | moodboards | apagar board: o modal avisa o efeito e cancelar não apaga | PASSA | evidencias/light-1440x900-mb-apagar-modal.png |
| C-MOODBOARDS-29 | moodboards | apagar board: confirmar apaga a pasta e volta para a biblioteca | PASSA | evidencias/light-1440x900-mb-apagado.png |
| C-MOODBOARDS-30 | moodboards | 'Abrir pasta' do board não é testável offline (abre o explorador do SO) | BLOQUEADO | clicar #btnMbOpenFolder abre o explorador do SO (proibido na rodada headless); o endpoint POST /open-folder é best-effort e não tem efeito verificável na UI |
| C-MOODBOARDS-31 | moodboards | seleção e prompt sobrevivem ao reload do editor | PASSA | evidencias/light-1440x900-mb-persistencia.png |
| C-CREDITOS-01 | creditos | card de saldo mostra os créditos e o plano de /api/creditos/balance | PASSA | evidencias/light-1440x900-cr-saldo.png |
| C-CREDITOS-02 | creditos | 'Atualizar saldo' consulta o CLI com refresh=1 e repinta o card | PASSA | evidencias/light-1440x900-cr-refresh.png |
| C-CREDITOS-03 | creditos | chip global de créditos (topbar/sidebar) reflete o mesmo saldo | PASSA | chips=['● 9999 créditos'] |
| C-CREDITOS-04 | creditos | tabela admin tem uma linha por ação, com custo e origem de /api/creditos | PASSA | evidencias/light-1440x900-cr-admin.png |
| C-CREDITOS-05 | creditos | o select de modelo de uma ação só oferece modelos do mesmo tipo | PASSA | 12 ações com opções do próprio tipo |
| C-CREDITOS-06 | creditos | trocar o modelo no escopo Global grava em STUDIO_STATE/config.json | PASSA | evidencias/light-1440x900-cr-admin-global.png |
| C-CREDITOS-07 | creditos | trocar a variação recalcula o custo da linha e persiste a resolução | PASSA | evidencias/light-1440x900-cr-admin-variacao.png |
| C-CREDITOS-08 | creditos | com campanha aberta, o seletor de escopo Global/Esta campanha aparece | PASSA | evidencias/light-1440x900-cr-escopo.png |
| C-CREDITOS-09 | creditos | override por campanha grava em projects/<pid>/config.json e marca a origem 'projeto' | PASSA | evidencias/light-1440x900-cr-admin-projeto.png |
| C-CREDITOS-10 | creditos | 'usar global' remove o override do projeto (DELETE) e a origem volta a código | PASSA | evidencias/light-1440x900-cr-usar-global.png |
| C-CREDITOS-11 | creditos | default global sobrevive ao reload e continua marcado como 'global' | PASSA | evidencias/light-1440x900-cr-persistencia.png |
| C-CREDITOS-12 | creditos | tabela de custo agrupa por tipo na ordem de kind_order | PASSA | grupos=['Imagem', 'Upscale', 'Vídeo', 'Áudio'] |
| C-CREDITOS-13 | creditos | tabela de custo lista uma linha por variação de cada modelo | PASSA | evidencias/light-1440x900-cr-custos.png |
| C-CREDITOS-14 | creditos | custo da tabela admin é o medido; o gate de geração usa o custo ao vivo do CLI | PASSA | tabela=2 cr; gate usa 7 cr (source=cli) |
| C-CREDITOS-15 | creditos | gasto registrado aparece em 'Gerações recentes', por etapa e por projeto | PASSA | evidencias/light-1440x900-cr-historico.png |
| C-CREDITOS-16 | creditos | com campanha aberta o histórico é o da campanha (nota + só os gastos do pid) | PASSA | evidencias/light-1440x900-cr-historico-campanha.png |
| C-CREDITOS-17 | creditos | sem campanha (deep link) a tela mostra o total geral e só defaults globais | PASSA | evidencias/light-1440x900-cr-deep-link.png |
| C-CREDITOS-18 | creditos | chip de créditos da topbar abre a área de Créditos & Custos | PASSA | evidencias/light-1440x900-cr-abrir-topbar.png |
| C-CREDITOS-19 | creditos | trocar de escopo não perde o override do projeto nem o mostra no global | PASSA | evidencias/light-1440x900-cr-escopo-isolado.png |
| C-CREDITOS-20 | creditos | cada select do painel admin tem nome acessível (rótulo/aria-label) | PASSA | evidencias/light-1440x900-cr-a11y-selects.png |

## 4. Auditoria automática por tela (tema × viewport)

| Tela | Tema | Viewport | Problemas | Console/pageerror | HTTP ≥ 400 | Print |
| --- | --- | --- | --- | --- | --- | --- |
| shell | light | 1440x900 | — | — | — | evidencias/light-1440x900-shell.png |
| overview | light | 1440x900 | — | — | — | evidencias/light-1440x900-overview.png |
| refs | light | 1440x900 | — | — | — | evidencias/light-1440x900-refs.png |
| mood | light | 1440x900 | — | — | — | evidencias/light-1440x900-mood.png |
| base | light | 1440x900 | — | — | — | evidencias/light-1440x900-base.png |
| storyboard | light | 1440x900 | — | — | — | evidencias/light-1440x900-storyboard.png |
| animate | light | 1440x900 | — | — | — | evidencias/light-1440x900-animate.png |
| music | light | 1440x900 | — | — | — | evidencias/light-1440x900-music.png |
| edit | light | 1440x900 | — | — | — | evidencias/light-1440x900-edit.png |
| export | light | 1440x900 | — | — | — | evidencias/light-1440x900-export.png |
| publish | light | 1440x900 | — | — | — | evidencias/light-1440x900-publish.png |
| prospect | light | 1440x900 | — | — | — | evidencias/light-1440x900-prospect.png |
| moodboards | light | 1440x900 | — | — | — | evidencias/light-1440x900-moodboards.png |
| creditos | light | 1440x900 | — | — | — | evidencias/light-1440x900-creditos.png |
| shell | light | 1024x768 | — | — | — | evidencias/light-1024x768-shell.png |
| overview | light | 1024x768 | — | — | — | evidencias/light-1024x768-overview.png |
| refs | light | 1024x768 | — | — | — | evidencias/light-1024x768-refs.png |
| mood | light | 1024x768 | — | — | — | evidencias/light-1024x768-mood.png |
| base | light | 1024x768 | — | — | — | evidencias/light-1024x768-base.png |
| storyboard | light | 1024x768 | — | — | — | evidencias/light-1024x768-storyboard.png |
| animate | light | 1024x768 | — | — | — | evidencias/light-1024x768-animate.png |
| music | light | 1024x768 | — | — | — | evidencias/light-1024x768-music.png |
| edit | light | 1024x768 | — | — | — | evidencias/light-1024x768-edit.png |
| export | light | 1024x768 | — | — | — | evidencias/light-1024x768-export.png |
| publish | light | 1024x768 | — | — | — | evidencias/light-1024x768-publish.png |
| prospect | light | 1024x768 | — | — | — | evidencias/light-1024x768-prospect.png |
| moodboards | light | 1024x768 | — | — | — | evidencias/light-1024x768-moodboards.png |
| creditos | light | 1024x768 | — | — | — | evidencias/light-1024x768-creditos.png |
| shell | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-shell.png |
| overview | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-overview.png |
| refs | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-refs.png |
| mood | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-mood.png |
| base | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-base.png |
| storyboard | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-storyboard.png |
| animate | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-animate.png |
| music | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-music.png |
| edit | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-edit.png |
| export | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-export.png |
| publish | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-publish.png |
| prospect | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-prospect.png |
| moodboards | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-moodboards.png |
| creditos | dark | 1440x900 | — | — | — | evidencias/dark-1440x900-creditos.png |
| shell | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-shell.png |
| overview | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-overview.png |
| refs | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-refs.png |
| mood | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-mood.png |
| base | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-base.png |
| storyboard | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-storyboard.png |
| animate | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-animate.png |
| music | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-music.png |
| edit | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-edit.png |
| export | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-export.png |
| publish | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-publish.png |
| prospect | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-prospect.png |
| moodboards | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-moodboards.png |
| creditos | dark | 1024x768 | — | — | — | evidencias/dark-1024x768-creditos.png |

Timers órfãos: —.

## 5. Inspeção visual (feita pelo agente sobre os prints)

**56 auditorias, 0 com problema** — claro e escuro, 1440×900 e 1024×768, nas 14 telas. Zero
overflow horizontal, zero imagem quebrada, zero botão sem nome acessível, zero input sem rótulo,
zero controle coberto por overlay, zero texto cortado, zero erro de console/pageerror/HTTP 4xx-5xx.

| Tela | Tema | Observação | Severidade | Print |
| --- | --- | --- | --- | --- |
| todas (14) | claro e escuro | nenhum problema visual detectado nas 56 combinações | — | `.qa/runs/react-e0/evidencias/` |

Os prints ficam fora do git (`.qa/` é gitignored). Para regerá-los:
`make qa-up qa-seed qa-run RUN=react-e0`.


## 6. Backend

### 6.1 Auditoria de API (api_audit.py)

| Grupo | Item | Resultado | Detalhe |
| --- | --- | --- | --- |
| openapi | 219 operações descobertas | PASSA | 219 (esperado > 50) |
| openapi | nenhum GET responde 5xx | PASSA | — |
| openapi | nenhum GET acima de 5s | PASSA | — |
| contratos | pid inexistente devolve 404 (GET) e nunca 5xx | PASSA | — |
| contratos | corpo inválido em POST/PUT/PATCH nunca devolve 5xx | PASSA | — |
| contratos | todo GET …/job devolve {state} | PASSA | — |
| catalogo | /api/steps tem 10 etapas com n=1..10 | PASSA | [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] |
| catalogo | guia.total == etapas ready | PASSA | total=10 ready=10 |
| contratos | POST /api/projects duplicado → 409 | PASSA | → 409 |
| contratos | PATCH aspect_ratio inválido → 422 | PASSA | → 422 |
| contratos | reset de etapa desconhecida → 404 | PASSA | → 404 |
| contratos | guia de etapa desconhecida → 404 | PASSA | → 404 |
| contratos | /api/higgsfield/status tem installed/logged_in | PASSA | {"installed":true,"logged_in":true,"email":"qa-fake@studio.local","plan":"qa-fake","credits":9999,"raw":{"email":"qa-fak |
| contratos | pid reservado ('moodboards') é recusado | PASSA | → 409 |
| disco | project.json do seed cheio continua íntegro após a auditoria | PASSA | {'id': '2026-09-e2e-mock', 'name': 'E2E Mock', 'product': 'energético', 'vibe': 'gelo neon ciano, alto contraste', 'crea |
| offline | fakes foram chamados (higgsfield/claude passam pelos fakes) | PASSA | fakes.log sem chamadas de higgsfield — o servidor pode estar usando o binário real |
| server.log | sem Traceback no log do servidor | PASSA | 0 traceback(s) em <WORKTREE>/.qa/run |
| server.log | sem respostas 500 / linhas ERROR | PASSA | — |

### 6.2 Newman

| Coleção | Requests | Falhas | Classificação | Observação |
| --- | --- | --- | --- | --- |
| docs/domains/animate/postman/animate.postman_collection.json | 25 | 8 | coleção defasada — ADR-015 (numeração das etapas) e ADR-023 (modelo default) | GET /api/steps — etapa 6 pronta: expected 5 to deeply equal 6; GET animate/shots — plano na ordem do storyboard: expected 'kling2_6' to deep |
| docs/domains/base/postman/base-etapa3-imagem-base.postman_collection.json | 45 | 6 | coleção defasada — ADR-026 (marca por imagem, `label_prompt_ready` fora do contrato) | GET prompts da aula (contrato 1): expected { model: 'nano_banana_2', …(15) } to have property 'label_prompt_ready'; GET brand (contrato 2):  |
| docs/domains/edit/postman/edit.postman_collection.json | 30 | 0 | — | — |
| docs/domains/export/postman/export.postman_collection.json | 42 | 2 | coleção defasada — mensagem de 404 mudou (`Not Found` sem citar `master.mp4`) | POST render — projeto sem edit/master.mp4 (404): expected 'Not Found' to include 'master.mp4'; POST qa — projeto sem edit/master.mp4 (404):  |
| docs/domains/mood/postman/mood-vibes.postman_collection.json | 20 | 0 | — | — |
| docs/domains/music/postman/music.postman_collection.json | 40 | 23 | coleção defasada + fixture — assume `candidates` vazio, mas o seed já traz candidatas | GET candidates — lista vazia antes de importar: expected [ { id: '7bd90956856a', …(12) } ] to be empty; POST import/upload — 2 wav (added 2) |
| docs/domains/prospect/postman/prospect.postman_collection.json | 26 | 10 | coleção defasada — rota de DM devolve 404; leve sensibilidade a ordem (12↔10) | Lead: obter: expected undefined to deeply equal ''; DM: ver o texto para copiar: expected response to have status code 200 but got 404 |
| docs/domains/publish/postman/publish.postman_collection.json | 22 | 0 | — | — |
| docs/domains/refs/postman/refs-import-url.postman_collection.json | 59 | 4 | fixture — o polling do job dá mais voltas que o teto assumido pela coleção | GET job — polling do import de seção: expected 20 to be at most 1; GET job — polling do import de pin: expected 20 to be at most 1 |
| docs/domains/storyboard/postman/storyboard.postman_collection.json | 80 | 10 | coleção defasada — o payload de estado da etapa ganhou/perdeu chaves | GET storyboard - estado da etapa: expected { …(13) } to have keys 'base_image', 'has_base', 'ideas', 'selected', 'scenes', 'scenes_wit; POST |
| docs/domains/studio/postman/prompter-presets-realismo.postman_collection.json | 18 | 0 | — | — |
| docs/domains/shots/postman/shots.postman_collection.json | — | — | legado | shots: domínio legado sem plugin — coleção não executada |

## 7. Apontamentos

> **Nenhum apontamento é da E0.** Esta frente não tocou comportamento de aplicação. Tudo abaixo já
> existia em `develop` @ `7b6f3b7` e está registrado aqui porque **muda o plano das frentes
> seguintes**.

### 7.1 ⚠ O baseline NÃO é 382/382 — e a regra da wave assume que era

A regra que governa a Wave 10 é *"os cenários passam sem uma linha editada"*. Ela nasceu da
premissa de que os 382 cenários estavam verdes. **Não estão: 6 falham em `develop` antes de existir
uma linha de React.** Cinco deles falham porque o **cenário ficou para trás de um ADR mergeado** —
não porque a aplicação esteja errada.

| # | Caso | Causa raiz | Classe | Dono |
| --- | --- | --- | --- | --- |
| AP-01 | `C-BASE-14` · 'Salvar marca' persiste nome e descrição | `#brandName`/`#brandDesc`/`#btnBrand` **não existem mais**: a marca do rótulo virou IMAGEM anexada (**ADR-026**, supersede da marca-texto). O `view.html` só tem `#btnBrandClear`/`#brandPreview`/`#brandDrop`. | cenário defasado | E7 |
| AP-02 | `C-BASE-15` · 'Salvar marca' sem nome mostra o erro da aula | idem AP-01 | cenário defasado | E7 |
| AP-03 | `C-BASE-16` · card de prompt vira a instrução de rótulo | a chave `label_prompt_ready` **saiu do contrato** da etapa 3 (ADR-026). Zero ocorrências em `studio/`. | cenário defasado | E7 |
| AP-04 | `C-BASE-17` · stepper tem os 3 passos da aula | o stepper tem **4** passos (`situation`, `clean`, `label`, `upscale`); `clean` é `[extensão]` e o cenário só conhece a `COURSE_CHAIN` de 3. | cenário defasado | E7 |
| AP-05 | `C-BASE-33` · card de prompt e passo ativo do stepper concordam | **bug real da aplicação, e o cenário está certo**: `load()` avança `step` para o 1º passo sem escolha, mas não chama `renderPrompt()`. O stepper abre em `label` e o card do painel 01 continua no prompt de `situação`. | **bug de produto** | decisão do dono |
| AP-06 | `C-STORYBOARD-11` · importar do histórico do CLI traz os jobs | `#sbBtnHistory` deixou de importar direto e passou a abrir o **seletor de histórico** (`historyModal()`, **ADR-029**). O cenário ainda espera o import direto e o toast `jobs`. Confirmado em isolamento, em estado recém-semeado: `1→1 ideias`, `toast=''`, mas `generate list` **foi** chamado. | cenário defasado | E8 |

Os 2 BLOQUEADO são **por desenho**, documentados nos próprios cenários, e não são falha:
`C-REFS-10` (scrape real do Pinterest usa rede externa e sessão do usuário) e `C-MOODBOARDS-30`
(`Abrir pasta` abre o explorador do SO).

### 7.2 ⚠ O recon §3 herdou a defasagem — E7 e E8 leiam com cuidado

O contrato DOM por tela do `recon-wave-10.md` §3 foi extraído **dos cenários**. Onde o cenário está
defasado, o recon também está. Concretamente: **§3.12 lista `#brandName`, `#brandDesc` e `#btnBrand`
como parte do contrato da tela `base`, e esses ids não existem no `view.html` atual.** Uma E7 que
seguisse o recon ao pé da letra reconstruiria fielmente um DOM que não está lá — e passaria a
falhar um cenário que já falha, agora por um motivo novo.

**Regra prática para E7 e E8:** onde cenário e código divergirem, **o código em `develop` é a
verdade** (a wave é refatoração pura: o alvo é reproduzir o que existe, não o que o cenário
esperava). Portar o comportamento atual, deixar o cenário falhando exatamente como falha hoje, e
não editar o cenário.

### 7.3 ⚠ `make qa-api`: contratos verdes, 7 coleções Postman defasadas

`newman` não estava instalado nesta máquina, então `make qa-api` **não rodava** — e por isso a
defasagem passou despercebida. Com o newman resolvido pela E0, o quadro real aparece:

- **As 18 checagens de contrato/OpenAPI passam** (219 operações, nenhum GET 5xx, nenhum acima de
  5 s, `{pid}` inexistente sempre 404, corpo inválido nunca 5xx, catálogo coerente com o guia,
  zero Traceback e zero 500 no `server.log`). O backend está saudável.
- **7 de 12 coleções Postman falham**, somando **63 asserções**: `animate` 8, `base` 6, `export` 2,
  `music` 23, `prospect` 10, `refs` 4, `storyboard` 10. Verdes: `edit`, `mood`, `publish`, `studio`.
  `shots` não roda (domínio legado sem plugin).
- Amostras que mostram a natureza do problema — é a mesma defasagem da §7.1, não regressão:
  `animate` afirma *"etapa 6 pronta: expected 5 to deeply equal 6"* (numeração anterior à **ADR-015**,
  que fundiu a etapa 5 na 4) e *"expected 'kling2_6' to deeply equal 'kling3_0'"* (**ADR-023**
  mudou o default); `base` cobra `label_prompt_ready` (**ADR-026**), a mesma chave do AP-03.
- Reproduzido **duas vezes**, em estado usado e em estado recém-semeado: mesmo resultado
  (23 ok / 7 falhas). Não é poluição de estado. Duas coleções têm leve sensibilidade a ordem
  (`prospect` 12↔10, `refs` polling 21↔20), então **a comparação estável é a contagem de falhas por
  coleção, não o total de asserções.**
- Evidência das duas execuções: `api.json` (estado limpo, é o baseline) e `api-apos-cenarios.json`
  (depois dos 382 cenários).

**Consequência para a definição de pronto.** O critério 2 (*"`make qa-api` sem diferença de
contrato"*) não pode significar "verde": significa **idêntico a este baseline**. E a wave dá uma
garantia forte aqui — ela **não toca `service.py`, `router.py` nem `guide.py`** —, então qualquer
mudança nestes números é regressão real, e o sinal é limpo apesar do vermelho de partida.


## 8. Veredito

- **Casos: 374 PASSA, 6 FALHA, 2 BLOQUEADO de 382.**
- **Auditorias: 0 com problema de 56** (14 telas × claro/escuro × 1440×900/1024×768).
- **Timers órfãos: 0** em todas as etapas (janela de 6 s após trocar de tela).
- **Auditoria de API: 18 checagens de contrato verdes**; 7 de 12 coleções Postman com 63 asserções
  falhando, todas por defasagem preexistente (§7.3).
- **Pré-voo: 20 PASS, 0 FAIL, 0 AVISO** — a frio, na primeira execução.
- **Apontamentos:** 6, **nenhum causado pela E0**. 5 são cenário defasado de ADR mergeado
  (ADR-026, ADR-029) e 1 é bug real de produto (AP-05).
- **Situação: APROVADA COM RESSALVAS** — aprovada como baseline (é o retrato fiel de `develop`
  @ `7b6f3b7`); as ressalvas são as §7.1, §7.2 e §7.3, que mudam o plano de E7, E8 e da integração.

### Como as frentes E1…E10 comparam contra este baseline

```bash
# 1) cenários — o alvo é 374 PASSA / 6 FALHA / 2 BLOQUEADO, com os MESMOS 6 casos falhando
make qa-up qa-seed qa-run RUN=<nome-da-frente>          # nunca RUN=local

# 2) contrato de backend — o alvo é 23 ok / 7 falhas, com as MESMAS coleções vermelhas
make qa-api RUN=<nome-da-frente>

# 3) texto visível (ADR-004) — o alvo é diff VAZIO
. .qa/runs/<nome-da-frente>/env.sh
python scripts/qa/textcontent.py --run <nome-da-frente> --saida /tmp/tc-<frente>
diff -ru docs/qa/reports/2026-09-03-react-e0/textcontent /tmp/tc-<frente>
```

O item 3 é o critério 5 da definição de pronto. O dump foi **provado determinístico**: gerado duas
vezes, com `stack-down --purge` + `stack-up` + `seed` completos entre as duas, e `diff -ru` vazio.
São 25 arquivos (14 telas; cada tela de etapa capturada com a campanha cheia **e** com a vazia,
porque empty-state também é texto de aula), 3.212 nós de texto no total, um por linha, em ordem de
documento e com espaço em branco normalizado. `MANIFEST.txt` traz sha256 e contagem por arquivo.


## 9. Histórico de rodadas

### Rodada 1 — 2026-09-03, baseline de referência da Wave 10

- **Pré-voo:** 20 PASS, 0 FAIL, 0 AVISO, a frio. Foi preciso consertar três bugs de portabilidade
  do harness antes (o harness nasceu em Linux/WSL2 e nunca havia rodado em macOS): detecção do
  Chromium por caminho do Linux, servidor de mídia fake sem readiness wait, e o CLI inerte fixado
  em `/bin/true` — que não existe no macOS. Sem eles o baseline nasceria contaminado.
- **Executado:** 14 telas, 382 casos, 56 auditorias, timers órfãos, auditoria de API e newman.
- **Resultado:** 374 PASSA, 6 FALHA, 2 BLOQUEADO; 0 auditoria com problema; 0 timer órfão.
- **Artefatos:** `resultados.json` (cenários), `api.json` (auditoria de API em estado limpo),
  `api-apos-cenarios.json` (a mesma auditoria depois dos cenários, para mostrar o que é
  sensibilidade a ordem), `check-env.txt` (pré-voo) e `textcontent/` (o oráculo do ADR-004).
- **Apontamentos abertos:** AP-01…AP-06, todos preexistentes, nenhum da E0.
