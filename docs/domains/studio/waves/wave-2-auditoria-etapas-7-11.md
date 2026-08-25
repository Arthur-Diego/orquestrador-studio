# Auditoria de fidelidade — Etapas 7 a 11 (aulas 013, 014, 015, 001/016)

Wave 2 · 2026-08-25 · auditor read-only (subagente)

**Escopo lido inteiro:** transcrições 013, 014, 015, 001, 016, 017 (+ 018–020, que são páginas vazias de download); `docs/plano/plano-automacao-videos.md` (Fase 1, 3.0, 4.2) e `plano-higgsfield.md` (§2, §3, §7–§10); `docs/domains/studio/waves/wave-1.md` (contratos e decisões do lote); código e FDD das cinco etapas; `studio/common/ffmpeg.py` e `jobs.py`; `CLAUDE.md`; `docs/adrs/generated/`.

**Ressalva de fonte:** os arquivos em `texts/` são o texto da página da aula (resumo escrito pelo instrutor), não a fala transcrita do vídeo. Frases como "3 a 5 candidatas", "licença", "cena extra da geladeira", "speed ramp", "marcadores", "afiliação 35%" e o script literal da DM vêm do `plano-automacao-videos.md` (que diz ter sido extraído das transcrições), não do texto local. Onde a implementação cita "a aula" para algo que só existe no plano ou em lugar nenhum, aponto abaixo.

**Nota sobre 016–020:** 016 é a mesma aula 14 (monetização) com a parte final que 001 perde: *"R$100 a R$500 por um vídeo de 30 segundos a 1 minuto"* e o resumo *"portfólio visível, DM diária, curiosidade, prova rápida (5–10s), c[all]"* — já coberto pela etapa 11. 017 é o encerramento (curso avançado, "participação ativa na comunidade", "aplicar imediatamente"): nada operacional para o pipeline além do que a etapa 10 deveria absorver (comunidade). 018–020 são páginas vazias (`{{downloadurl}}`). Nenhuma etapa nova é necessária.

---

## Etapa 7 — Trilha (aula 013)

### 1. O que a aula ensina
1. **Antes de qualquer edição**, colocar **todas as cenas em ordem na timeline, sem cortar nada**: *"o objetivo não é editar, é enxergar a história como um todo e sentir se a narrativa faz sentido."*
2. Assistir a sequência completa e decidir se *"a história está fechada ou se falta alguma cena"*; *"fica claro quando é necessário criar um encerramento mais forte ou mais comercial, para deixar evidente o objetivo da peça"* (→ cena extra do produto, ex. do plano: geladeira congelada).
3. **Só depois** ir para a trilha — *"não para editar ainda, mas para sentir a energia"*. Regra repetida: *"Você não deve editar antes de escolher a trilha sonora. A música é o que define ritmo, emoção e impacto. Quando o vídeo é montado primeiro e a trilha vem depois, o resultado quase sempre soa amador."*
4. Ouvir várias músicas (plano: bibliotecas CapCut, Artlist, Envato, Musicbed, Epidemic, YouTube Audio Library) e escolher "sentindo".
5. Regra de qualidade: *"As batidas mais fortes da música indicam exatamente onde algo precisa acontecer visualmente."*
6. (Plano) Criar e animar a cena extra do produto: *"Troque a lata da imagem 1 pela da imagem 2"* → *"…tudo ao redor dela esteja congelado"* → *"Câmera se aproxima da lata enquanto a mulher pega em câmera lenta."*
- **Entradas:** todos os takes da etapa 6. **Saídas:** sequência bruta assistida, decisão sobre cena faltante, uma trilha escolhida. **Quantidades:** nenhuma numérica na aula.

### 2. O que a implementação faz
`studio/music/service.py` + `studio/etapas/music/`: prompt derivado do mood para `sonilo_music` (CLI, com `cost` antes); importar candidatas (upload / Downloads / histórico CLI); ouvir na UI; `select` copia para `audio/music.<ext>`, **exige** texto de origem/licença (`license.txt`) e roda `beats.py` (numpy+ffmpeg, ADR-009) gerando `audio/beats.json` `{bpm, beats, impacts, duration}`; régua de batidas/impactos; recalcular batidas. A cena extra do produto está na etapa 5 (`studio/shots/service.py:1`, `product_scene`), e a "timeline com tudo em ordem" só nasce na etapa 8 (`studio/edit/service.py:131-151`).

### 3. Divergências
| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção recomendada |
|---|---|---|---|---|---|
| 7.1 | falta | *"colocar todas as cenas em ordem na timeline, sem cortar nada… enxergar a história como um todo… se falta alguma cena"* | Nenhuma rota/tela da etapa 7 produz ou exibe a sequência bruta; só a etapa 8 monta (`edit/service.py:131`) | alta | Adicionar em `music` um passo "0. Assistir a história inteira": render de `audio/rough_sequence.mp4` (concat simples dos takes *liked* na ordem do storyboard, sem música, ffmpeg) + pergunta "a história fecha? precisa de encerramento mais forte/comercial?" com link para a cena do produto (etapa 5) e para gerar o take dela (etapa 6). Reutilizar `edit.initial_timeline` + `render.build_filtergraph(target="rough")`. |
| 7.2 | desvio de ordem (registrado só no FDD) | Cena extra do produto é decidida **depois** de assistir a sequência (013) | `music-fdd.md:28` "ficou em `shots` por decisão da wave"; sem ADR em `docs/adrs/` | média | Manter em `shots` (mesmo artefato), mas registrar ADR (gate 4 do CLAUDE.md) e, na etapa 7, mostrar "cena do produto: existe/não existe" com atalho. |
| 7.3 | texto da tela enganoso | Aula não dá número | `service.py:39` "Baixe de 3 a 5 músicas"; `view.html:4` "reúna de 3 a 5 candidatas"; `view.js:44` | baixa | Trocar por "várias músicas (a aula não fixa número)". |
| 7.4 | extensão não marcada + texto enganoso | Nenhuma transcrição menciona licença | `service.py:184-186` `raise ValueError("…a aula 013 exige saber de onde veio a música")`; `view.js:83` "(aula 013)"; obrigatório em `router.py:43` | média | Tornar opcional (campo "origem" sugerido, não bloqueante) ou manter obrigatório marcado `[extensão]` no código, FDD e tela, sem atribuir à aula. |
| 7.5 | ok (ferramenta trocada) | Bibliotecas de música (013) | `sonilo_music` via CLI + upload/Downloads | — | Já rotulado "gasta créditos"; ok. |
| 7.6 | ok (materialização) | *"batidas mais fortes… onde algo precisa acontecer"* | `beats.py` (ADR-009) | — | — |
| 7.7 | texto da tela | *"não para editar ainda, mas para sentir a energia"* | `view.html:4` explica; não diz "não edite antes" como regra proibitiva | baixa | Incluir a frase literal da aula no guia (ver §4). |

### 4. Texto sugerido para a tela
**O que fazer nesta etapa.** Antes de editar qualquer coisa, coloque todas as cenas em ordem e assista tudo de uma vez, sem cortar nada — o objetivo é enxergar a história como um todo. Pergunte-se se a história fecha ou se falta uma cena; se faltar um encerramento mais forte ou mais comercial (mostrar o produto), volte e crie essa cena. Só então ouça várias músicas e escolha a trilha sentindo a energia dela. Não edite antes de escolher a trilha: é a música que define ritmo, emoção e impacto. As batidas mais fortes indicam onde algo precisa acontecer no vídeo.

**Checklist de qualidade da aula**
- Assisti a sequência completa, na ordem, sem cortes.
- Decidi se falta cena ou encerramento (produto em evidência no fim).
- Ouvi várias músicas e escolhi uma "sentindo", não só pelo número de bpm.
- A trilha foi escolhida **antes** de qualquer corte.
- Sei onde estão as batidas fortes (é ali que algo acontece).

**Entradas necessárias:** takes escolhidos na etapa 6 (todas as cenas); storyboard da etapa 5 (ordem); opcional: cena do produto.
**Saída esperada:** uma trilha escolhida (`audio/music.*`), a marcação das batidas fortes (`audio/beats.json`) e a decisão "história fechada / precisa de cena extra".

### 5. Validações automáticas possíveis
- Existe pelo menos um take *liked* por cena do storyboard antes de liberar a trilha (013: "todas as cenas em ordem").
- `audio/music.*` existe e `beats.json` corresponde a ele (invariante já implementada) — "trilha escolhida e batidas detectadas".
- Se `product_scene` é nulo, aviso "a aula manda que o comercial termine mostrando o produto" (013 + plano 1.3 item 8).
- Etapa 8 bloqueada/avisada enquanto `audio/music.*` não existir (013: "não deve editar antes").
- Duração da trilha ≥ soma dos takes *liked* (senão aviso de que a música será loopada/cortada).

---

## Etapa 8 — Montagem no ritmo (aula 014)

### 1. O que a aula ensina
1. Base pronta; *"o foco agora não é criar novas cenas, mas colar tudo no ritmo da música e resolver transições de forma inteligente."*
2. **Frames finais como pontes:** *"extraindo o último frame de uma cena e usando ele como início da próxima"* (start frame na etapa de animação; plano: *"A lente da câmera está totalmente congelada e vai descongelando…"*).
3. **Montagem guiada pelo som:** *"Você acelera, desacelera, corta e reposiciona cenas para que cada impacto visual aconteça exatamente nas batidas da música, sem se preocupar ainda com detalhes finos. O ritmo vem primeiro, o refinamento vem depois."*
4. Quando a mudança de movimento quebra a fluidez, **recursos simples**: *"mistura de quadros, pequenos zooms, cortes estratégicos ou até telas pretas para criar impacto e respiração narrativa."* (plano: speed ramp com frame blending, marcadores, cortar a música para o ápice, fade de opacidade no fim).
5. *"nem tudo precisa ser resolvido com IA. Algumas transições simplesmente funcionam melhor na edição."*
6. **Camadas sonoras por último:** *"SFX, ambiência, respiração, gelo, impacto… trabalho de detalhe, mas é o que transforma o vídeo em algo vivo."*
7. Dever de casa: *"publique o seu trabalho, mesmo imperfeito. O primeiro projeto sempre será o pior."*
- **Entradas:** takes + trilha. **Saída:** vídeo montado no ritmo, com SFX. Ferramenta: CapCut (troca por ffmpeg é legítima).

### 2. O que a implementação faz
Timeline única (`edit/timeline.json`): clipes *liked* na ordem do storyboard (cena do produto por último), `in/out/speed/blend`, reordenar/remover; `propose-cuts` alinha o fim de cada clipe a um impacto de `beats.json` (com `music.offset`) e **põe um quadro preto em cada corte usado** (`black_dur` padrão 0,2 s); música com offset, `fade_out` (vídeo + áudio); SFX por upload com `at/gain`; `last-frame` exporta PNG para a etapa 6; render `rough` (só música) e `master` (SFX, `loudnorm=-14`, fade) em 1920×1080/30 fps via ffmpeg (`minterpolate=blend` quando `speed≠1` e `blend`). Render segue mesmo sem trilha (aviso).

### 3. Divergências
| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção recomendada |
|---|---|---|---|---|---|
| 8.1 | desvio de processo | Telas pretas são **um dos recursos** para quando "a mudança de movimento entre cenas quebra a fluidez", não regra em todo corte | `edit/service.py:311-314` adiciona `black` em **todo** corte usado; `view.html:25` padrão 0,2 s; `render.py:24` | média | Padrão `black_dur=0` na proposta (cortes secos nos impactos); quadro preto vira ação por corte ("adicionar preto aqui") ou checkbox desmarcada "preto nos impactos". |
| 8.2 | desvio de processo (regra central) | *"Você não deve editar antes de escolher a trilha sonora"* (013); *"totalmente guiada pelo som"* (014) | `render.py:232-233` renderiza sem música só com aviso; `view.js:50` "o master sai sem música"; `propose_cuts` exige beats, mas timeline/render não exigem trilha | média | `POST /edit/render` com `target=master` sem `audio/music.*` → 409 "escolha a trilha na etapa 7 antes de montar"; `rough` pode continuar liberado com aviso. |
| 8.3 | falta | *"pequenos zooms"* | Não há zoom por clipe (`validate_timeline` só aceita in/out/speed/blend) | baixa | Campo opcional `zoom` (1.0–1.3) por clipe → `scale=iw*z:ih*z,crop=W:H` ou `zoompan` lento; marcar como recurso da aula. |
| 8.4 | extensão não marcada | Aula não fala de loudness | `render.py:153` `loudnorm=I=-14:TP=-1.5`; `view.html:77` só diz "sem loudnorm" no rough | baixa | Manter, mas marcar `[extensão]` no código/FDD ou tornar opcional ("normalizar volume"). |
| 8.5 | falta (UX) | *"cada impacto visual aconteça exatamente nas batidas"*; plano: "marcadores" | A etapa 8 não mostra os impactos sobre a timeline; a régua só existe na etapa 7 (`music/view.js:58`) | baixa | Reaproveitar a régua de `beats.json` (com offset) acima da lista de clipes, marcando onde cada `out` cai. |
| 8.6 | ok (ferramenta) | CapCut → ffmpeg | `render.py` inteiro; docstring cita regra 3 | — | — |
| 8.7 | ok | Último frame → start frame da próxima | `service.py:351-360`, `INSTRUCTION` com a frase da aula | — | — |
| 8.8 | ok | *"ritmo vem primeiro, refinamento depois"* | `rough` (sem SFX/fade) vs `master` | — | Explicitar no guia. |
| 8.9 | ok | SFX "respiração, gelo, impacto" | `import_sfx`, `view.html:57` | — | Acrescentar "gelo" e "ambiência" ao texto (lista literal da aula). |
| 8.10 | texto da tela | Dever de casa "publique mesmo imperfeito" | Não aparece na etapa 8 (só na 9/10) | baixa | Frase no rodapé do render. |

### 4. Texto sugerido para a tela
**O que fazer nesta etapa.** A base já está pronta: agora é colar tudo no ritmo da música. Acelere, desacelere, corte e reposicione as cenas para que cada impacto visual caia exatamente numa batida forte da trilha — sem se preocupar ainda com detalhes finos: o ritmo vem primeiro, o refinamento depois. Quando a mudança de movimento entre duas cenas quebrar a fluidez, resolva com recursos simples de edição: mistura de quadros, um pequeno zoom, um corte estratégico ou uma tela preta para dar impacto e respiração. Se uma transição pede continuidade, exporte o último frame da cena e use como start frame da próxima (etapa 6); nem tudo precisa ser resolvido com IA. Por último, as camadas de som: SFX, ambiência, respiração, gelo, impacto.

**Checklist de qualidade da aula**
- A trilha foi escolhida antes de qualquer corte (etapa 7).
- Cada impacto visual cai numa batida forte da música.
- Velocidade/ordem ajustadas pelo som, não pela duração original dos takes.
- Transições que quebravam a fluidez foram resolvidas (mistura de quadros, zoom, corte, tela preta) ou coladas por último frame → start frame.
- Ritmo fechado antes de mexer em detalhe fino.
- Camadas sonoras adicionadas por último (SFX, ambiência, respiração, impacto).
- Vou publicar mesmo imperfeito — o primeiro sempre será o pior.

**Entradas necessárias:** takes *liked* (etapa 6) na ordem do storyboard (etapa 5), trilha escolhida e batidas (etapa 7), SFX (upload).
**Saída esperada:** `edit/rough_cut.mp4` (ritmo) e `edit/master.mp4` (com SFX e fade); `edit/last_frames/*.png` quando houver transição colada.

### 5. Validações automáticas possíveis
- "Cortes caem em batidas": cada `out` de clipe (em tempo de timeline + offset) a ≤ 2 frames (0,067 s) de um `impacts[]` ou `beats[]`; relatório N/M cortes no ritmo.
- Master só renderiza com `audio/music.*` presente (013).
- Duração do master ≤ duração da trilha − offset (senão aviso de música cortada antes do fim).
- Ao menos um SFX na timeline do master (014: "camadas sonoras… é o que transforma o vídeo em algo vivo") — aviso, não bloqueio.
- Cena do produto é o último clipe (013: encerramento comercial) — aviso.
- Se um `last_frames/*.png` foi exportado, verificar que existe take start/end correspondente na etapa 6 (transição colada concluída).

---

## Etapa 9 — Export e QA (aula 014; formatos citados na 007)

### 1. O que a aula ensina
1. Aula 014 termina em *"publique o seu trabalho, mesmo imperfeito"*. Não existe aula de QA nem de export; a 007 cita, para imagens no Midjourney, *"Ajustes de formato (vertical, quadrado, widescreen)"*; o plano (1.4) registra "vertical para Reels/TikTok, 16:9 para YouTube".
2. Nenhuma regra de qualidade técnica é ensinada; a regra é **não** travar na perfeição.
- **Entrada:** vídeo montado. **Saída:** arquivo publicável no formato da rede.

### 2. O que a implementação faz
Deriva `export/16x9|9x16|1x1.mp4` do master (crop central com preview; 16:9 por `-c copy`), thumb em `t`, `qa_report.md` (existência, resolução, duração ±0,5 s, h264, áudio, tamanho), reframe pago opcional via CLI (com custo e confirm). Não lê POI do storyboard (extensão não aprovada, corretamente excluída).

### 3. Divergências
| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção recomendada |
|---|---|---|---|---|---|
| 9.1 | extensão não marcada | Aula não ensina QA/thumb; só "publique mesmo imperfeito" | `export/service.py:338-425` QA; `make_thumb`; `view.html:4` atribui os formatos à "aula 007" | baixa | Manter (é ferramenta de entrega), mas rotular painéis "Thumb" e "QA técnico" como `[extensão]` na tela e no FDD §3; no lede, dizer "formato por rede (plano) — a aula só manda publicar". |
| 9.2 | texto da tela enganoso | 007 fala de formato **de imagem** no Midjourney ("vertical, quadrado, widescreen"), não de export de vídeo | `service.py:27` "Formatos por rede (aula 007)"; `view.html:4`; FDD "Pendências: confirmar leitura da aula 007 para 1:1" (ainda aberta) | baixa | Reescrever: "16:9 e 9:16 pelo destino (YouTube / Reels-TikTok, plano 1.4); 1:1 é opcional [extensão]". Fechar a pendência do FDD. |
| 9.3 | ok (ferramenta) | — | reframe CLI opcional, pago, com `cost` | — | — |
| 9.4 | ok | "publique mesmo que o primeiro fique ruim" | `_qa_markdown` e lede repetem | — | — |
| 9.5 | falta (coerência com 8.2) | Trilha obrigatória (013) | QA marca "áudio ausente" só como ATENCAO | baixa | Se 8.2 for adotado, o caso deixa de existir; senão, tornar "sem áudio" bloqueante. |

### 4. Texto sugerido para a tela
**O que fazer nesta etapa.** Gere o arquivo no formato da rede onde você vai publicar: vertical (9:16) para Reels e TikTok, 16:9 para YouTube. Confira o enquadramento do corte central antes de renderizar. O checklist abaixo é técnico (duração, resolução, codec, áudio) e não julga gosto — a aula manda publicar mesmo que o primeiro fique ruim; o primeiro projeto sempre será o pior, e isso faz parte do processo.

**Checklist de qualidade da aula**
- O vídeo tem trilha (etapa 7) e foi montado no ritmo (etapa 8).
- Existe o formato da rede-alvo (9:16 e/ou 16:9).
- Nada importante ficou fora do corte central.
- Não fiquei preso na perfeição: está bom para publicar.

**Entradas necessárias:** `edit/master.mp4`.
**Saída esperada:** `export/9x16.mp4` e/ou `export/16x9.mp4` (1:1 opcional), thumb e relatório técnico `[extensão]`.

### 5. Validações automáticas possíveis
- "Master 9:16 e 16:9 existem" (ou pelo menos o da rede escolhida no projeto).
- Duração do export = duração do master ±0,5 s; resolução exata; h264; áudio presente (já implementado).
- Duração total entre 30 s e 60 s quando o projeto é comercial (001: "vídeo de 30 segundos a 1 minuto") — aviso.
- Teaser/portfólio: arquivo ≤ limite de upload da rede (aviso informativo).

---

## Etapa 10 — Publicar (aula 015, dever de casa da 014)

### 1. O que a aula ensina
1. *"Antes de sair procurando clientes, você precisa consolidar a base… evoluir com consistência."*
2. **Comunidade é estratégica:** *"Interagir, postar, comentar e dar feedback é como você aprende padrões, melhora mais rápido e… passa a ser notado."* *"a própria comunidade já pode gerar oportunidades."*
3. **Dever de casa:** *"criar pelo menos quatro vídeos e publicá-los, seja em um perfil novo ou nas redes que você já tem. Esses vídeos não são para perfeição, são para prática, exposição e validação."*
4. *"o primeiro trabalho tende a ser o pior… Evolução vem da repetição, não da espera."*
5. Cumprido isso, *"você atinge o nível necessário para destravar a estratégia de monetização."*
6. (014) *"Compartilhar é o que permite feedback, evolução e, mais à frente, monetização."*
- **Saída:** 4 vídeos (obras) publicados; presença ativa na comunidade.

### 2. O que a implementação faz
Lista `export/*.mp4` do projeto, registra manualmente posts (`video, network, url, posted_at, note, feedback`), regrava `publish/portfolio.md`, conta `distinct_videos` = arquivos distintos de `export/` **dentro do projeto** e diz "pronto" quando ≥ 4. Sem publicação automática (correto).

### 3. Divergências
| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção recomendada |
|---|---|---|---|---|---|
| 10.1 | desvio de processo | *"pelo menos quatro vídeos"* = quatro obras diferentes (prática, repetição) | `publish/service.py:206-216` `distinct = len({p["video"]})` por projeto; `16x9.mp4`, `9x16.mp4`, `1x1.mp4` do **mesmo** comercial contam 3; um projeto (= um vídeo) nunca chega a 4 honestamente; `prospect/service.py:95-126` lê o mesmo arquivo | alta | Portfólio **global**: `distinct_videos` = número de projetos em `PROJECTS_DIR` com ≥ 1 post em `publish/log.json` (ou log global `projects/portfolio.json` com `project_id`). Expor `GET /api/portfolio`; `prospect.gate` consome isso. Dentro do projeto, a UI mostra "este vídeo já está publicado" (booleano). |
| 10.2 | falta | *"Interagir, postar, comentar e dar feedback… é como você passa a ser notado"*; *"a própria comunidade já pode gerar oportunidades"* | Nada sobre comunidade; datalist só instagram/tiktok/youtube (`view.html:26-29`) | média | Adicionar "comunidade ABRAhub" às redes sugeridas e um checklist não bloqueante "postei na comunidade / comentei / dei feedback" persistido em `publish/log.json` ou `portfolio.md`. |
| 10.3 | texto da tela enganoso | 015 fala em **dar** feedback na comunidade e "validação"; "receber feedback" vem da 014 ("Compartilhar é o que permite feedback") | `view.html:4` "A aula 015 manda… pedir feedback"; `view.html:45`; `service.py:175` | baixa | Reescrever: "Compartilhar é o que permite feedback (aula 014); na comunidade, interaja e dê feedback (aula 015)". |
| 10.4 | falta (texto) | *"seja em um perfil novo ou nas redes que você já tem"*; *"não são para perfeição, são para prática, exposição e validação"* | Ausente | baixa | Incluir no guia. |
| 10.5 | ok | Publicar é ato humano; sem API | `service.py:3-4` | — | — |

### 4. Texto sugerido para a tela
**O que fazer nesta etapa.** Publique o vídeo — num perfil novo ou nas redes que você já tem — e registre aqui o link. O dever de casa da aula é ter pelo menos quatro vídeos publicados antes de procurar clientes: eles não são para perfeição, são para prática, exposição e validação. Compartilhar é o que permite feedback e evolução; o primeiro trabalho tende a ser o pior, e isso é normal. Participe da comunidade ABRAhub: interagir, postar, comentar e dar feedback é como você passa a ser notado — e a própria comunidade já pode gerar oportunidades.

**Checklist de qualidade da aula**
- Publiquei mesmo imperfeito.
- Postei também na comunidade e interagi (comentei, dei feedback).
- Registrei o link e o que aprendi com este vídeo.
- Portfólio: N/4 vídeos **diferentes** publicados.

**Entradas necessárias:** `export/*.mp4` deste projeto; links dos posts.
**Saída esperada:** `publish/log.json` do projeto e portfólio global com ≥ 4 obras publicadas (destrava a etapa 11).

### 5. Validações automáticas possíveis
- "4 vídeos de portfólio" = ≥ 4 **projetos distintos** com post registrado (não 4 arquivos).
- URL válida e única; arquivo registrado existe em `export/`.
- Aviso quando o mesmo projeto registra 2+ formatos: "conta como 1 vídeo do portfólio".
- Checklist de comunidade preenchido (não bloqueante).
- Cada post tem ao menos uma nota/feedback antes de contar (opcional, "validação").

---

## Etapa 11 — Prospecção (aula 001 = 016)

### 1. O que a aula ensina
1. Caminho mais rápido: *"pequenos comerciais para pequenos negócios"* (clínicas, academias, advogados, estética, dentistas, comércios). *"É isso que você oferece: criativos melhores."*
2. *"Todo dia, você encontra 10 empresas no Instagram e envia uma DM."*
3. *"Não é spam, porque você personaliza: mostra que olhou o perfil e menciona um post específico."*
4. Script curto com três ideias: acompanha/gosta da marca; um post "ressoou"; cria anúncios criativos e o portfólio está no perfil. Sem links (plano).
5. Pulo do gato: *"Tive uma inspiração e criei algo para o seu negócio. Quer ver como ficou?"*
6. **"Você só cria de verdade se a empresa responder."** Aí *"produz apenas 5 a 10 segundos, com música e impacto"*, envia e *"chama para uma call de 15 minutos"*.
7. Na call: *"Você não vende 'IA'. Você vende resultado."* Mostrar *"lista de etapas (conceito, roteiro, direção criativa, etc.)"*; *"ancoragem: revela valores por etapa até chegar no total que você quer cobrar."*
8. Urgência: *"Condição especial na hora, ou válida por 24h."* *"Não trabalhe sem entrada: 50% antes e 50% na entrega."* *"50% off no primeiro trabalho, deixando claro o valor cheio para os próximos."*
9. Preço inicial (016): *"R$100 a R$500 por um vídeo de 30 segundos a 1 minuto."*
- **Entrada:** portfólio visível. **Saídas:** 10 DMs/dia, teaser 5–10 s para quem responde, call, proposta ancorada.

### 2. O que a implementação faz
Gate `≥ 4 vídeos` lendo `publish/log.json` **do projeto**; CRUD de leads; DM com template literal (fã/consumidor, `post_ref` opcional); "marquei como enviada" + contador N/10 (aviso, sem trava); "respondeu"; teaser = um take do projeto + `audio/music.*` com fade (5–10 s) — disponível para **qualquer** lead; follow-up literal; registro da call; `pitch.md` com tabela de etapas **sem valores** e lembretes.

### 3. Divergências
| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção recomendada |
|---|---|---|---|---|---|
| 11.1 | desvio de processo | *"Você só cria de verdade se a empresa responder."* | `prospect/service.py:378-399` `start_teaser` não checa `replied`; `view.js:40` botão "Gerar teaser" sempre visível; status `teaser_ready` pode vir antes de `replied` | alta | `start_teaser`: `if not lead["replied"]: raise ValueError("a aula manda criar só depois que a empresa responder")` → 422; UI esconde o botão até `replied`. Ajustar máquina de estados (`new → dm_sent → replied → teaser_ready → call_*`). |
| 11.2 | desvio estrutural (ligado a 10.1) | Gate = 4 vídeos de portfólio (obras anteriores); teaser = *"criei algo para o seu negócio"* (do lead) | Gate lê `publish/log.json` do **mesmo** projeto de onde sai o take do teaser (`service.py:100`, `:334`). Um projeto criado para o negócio do lead nunca terá 4 vídeos publicados → a etapa fica inutilizável no uso real | alta | Gate global (10.1). Guia explícito: "crie um projeto para o negócio do lead (etapas 1–6 em versão curta: 1 cena) e gere o teaser aqui". Opcional `[extensão]`: leads em arquivo global com `project_id` por lead. |
| 11.3 | desvio de processo | *"mostra que olhou o perfil e menciona um post específico"* (é o que torna "não spam") | `service.py:189` `post_ref` opcional → DM "O seu post a respeito de  realmente ressoou" | média | `post_ref` obrigatório em `create_lead` e no PUT; `dm_text` recusa vazio. |
| 11.4 | desvio de processo | *"revela valores por etapa até chegar no total que você quer cobrar"* | `PITCH_ROWS` sem coluna de valor (`service.py:453-470`); FDD §3 exclui "valores na tabela" | média | Coluna "Valor (R$)" editável por etapa + linha "Total" (o que você quer cobrar) e "Total com 50% off no 1º trabalho"; manter lembrete "valor cheio para os próximos". |
| 11.5 | falta (texto) | *"Condição especial na hora, ou válida por 24h"*; *"deixando claro o valor cheio para os próximos"* | `service.py:474-478` só "válida só nesta conversa"; sem "valor cheio" | baixa | Ajustar lembretes literalmente. |
| 11.6 | ok (auto-aceite registrado) | 10/dia | contador + aviso | — | — |
| 11.7 | ok | Sem links; três ideias-chave + gancho; call de 15 min; vender resultado; 50/50; R$100–500 | `DM_TEMPLATE`, `FOLLOWUP_TEXT`, lembretes | — | — |
| 11.8 | sugestão `[extensão]` | *"com música e impacto"* | Teaser não usa `beats.json` | baixa | `music_offset` padrão = primeiro `impact` − 0,5 s (impacto no início) — sugerir, não impor. |
| 11.9 | texto da tela | Mar azul: clínicas, academias, advogados, estética, dentistas, comércios | `view.html` genérico "pequenos negócios" | baixa | Listar os segmentos da aula no guia. |

### 4. Texto sugerido para a tela
**O que fazer nesta etapa.** Com quatro vídeos publicados no perfil, todo dia encontre 10 pequenos negócios no Instagram (clínicas, academias, advogados, estética, dentistas, comércios) e mande uma DM personalizada: mostre que olhou o perfil e cite um post específico — é isso que faz não ser spam. O script tem três ideias (você acompanha a marca, um post ressoou, você cria anúncios criativos e o portfólio está no perfil) e o gancho: "Tive uma inspiração e criei algo para o seu negócio. Quer ver como ficou?". Você só cria de verdade se a empresa responder: aí produz 5 a 10 segundos com música e impacto, envia e chama para uma call de 15 minutos. Na call você não vende IA, vende resultado: mostre as etapas de produção, ancore valor por etapa até o total, ofereça condição especial na hora (ou por 24h), 50% na entrada e 50% na entrega. No começo, cobre R$100–500 por vídeo de 30 s a 1 min para girar volume e construir portfólio real.

**Checklist de qualidade da aula**
- Portfólio de 4 vídeos publicado antes da primeira DM.
- 10 DMs hoje, cada uma citando um post específico do negócio; sem links.
- Teaser só para quem respondeu; 5–10 s, com música e impacto.
- Call de 15 min marcada; na call: lista de etapas, valores por etapa → total, urgência, 50/50, 50% off no 1º com valor cheio explícito.
- Vendi resultado (mais clientes para o negócio), não "IA".

**Entradas necessárias:** portfólio ≥ 4 vídeos publicados (global); perfil e post do lead; um take + trilha do projeto criado para o negócio do lead.
**Saída esperada:** `prospect/leads.json` (DMs enviadas/respostas/calls), `prospect/teasers/<lead>.mp4` (5–10 s com música), `prospect/pitch.md` com etapas, valores e total.

### 5. Validações automáticas possíveis
- "10 DMs/dia": contador diário; aviso abaixo de 10 no fim do dia e acima de 10 (já parcial).
- DM não contém `http`, `www.` ou `@` externo (sem links) e contém o `post_ref` não vazio.
- Teaser só com `replied=true`; duração 5–10 s; faixa de áudio presente (já parcial).
- Gate `≥ 4` obras publicadas **em projetos distintos**.
- `pitch.md`: soma dos valores por etapa = total; total dentro de R$100–500 quando marcado "iniciante" (aviso, não trava).
- Call registrada em ≤ 7 dias após `replied` (aviso de follow-up pendente) `[extensão]`.

---

## Resumo transversal

**Gravidade alta (3):** 7.1 (falta o passo "assistir tudo em ordem antes da trilha"), 10.1/11.2 (portfólio contado por arquivos do mesmo projeto; gate e teaser estruturalmente incompatíveis com o uso real), 11.1 (teaser antes da resposta contraria "só cria se responder").

**Gravidade média (7):** 7.2 (cena do produto movida para a etapa 5 sem ADR), 7.4 (licença obrigatória atribuída à aula), 8.1 (quadro preto em todo corte), 8.2 (master sem trilha permitido), 10.2 (comunidade ausente), 11.3 (post específico opcional), 11.4 (tabela sem valores por etapa).

**Extensões sem marca `[extensão]`:** licença obrigatória (7.4), `loudnorm` (8.4), QA/thumb (9.1), formato 1:1 (9.2). ADR existente só para batidas (ADR-009); faltam registros para 7.2, 7.4, 8.1/8.4 e para a regra de contagem do portfólio (gate 4 do CLAUDE.md).

**Textos de tela a corrigir:** `studio/music/service.py:39-43`, `studio/etapas/music/view.html:4`, `studio/etapas/music/view.js:44,81-83`, `studio/export/service.py:27`, `studio/etapas/export/view.html:4`, `studio/etapas/publish/view.html:4,45`, `studio/prospect/service.py:474-478`, `studio/etapas/prospect/view.html:50`.

Arquivos auditados (absolutos): `/home/arthu/code/senhortecnologia/orquestrador-studio/studio/{music,edit,export,publish,prospect}/service.py`, `.../studio/music/beats.py`, `.../studio/edit/render.py`, `.../studio/etapas/{music,edit,export,publish,prospect}/{__init__.py,router.py,view.html,view.js}`, `.../studio/common/{ffmpeg,jobs}.py`, `.../docs/domains/{music,edit,export,publish,prospect}/features/*-fdd.md`, `.../docs/domains/studio/waves/wave-1.md`, `.../docs/plano/{plano-automacao-videos,plano-higgsfield}.md`, `.../CLAUDE.md`; transcrições em `/home/arthu/code/senhortecnologia/aprendizado/20260824-162323/01-curso-iniciante-o-orquestrador/texts/{001,013,014,015,016,017,018,019,020}-*.txt`.
