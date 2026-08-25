# Auditoria de fidelidade — Etapas 4, 5 e 6 (aulas 010, 011, 012)

Wave 2 · 2026-08-25 · auditor read-only (subagente). Fontes: `texts/009…012` (descrição da página da aula, truncada em ~5,6 KB), `docs/plano/plano-automacao-videos.md` (§1.1, §1.3), `docs/plano/plano-higgsfield.md` (§2, §3), `CLAUDE.md`, ADR-004, `wave-1.md`, código/FDD/HLD das três etapas e `studio/higgsfield.py`.

**Ressalva sobre as fontes.** Regras como "gerar 2", "áudio OFF", "10 s", "3–4 falhas", "acertar cor/luz antes do multishot" e as fórmulas literais de prompt só existem no plano (extraído da transcrição completa). Citações vêm do `texts/` quando existem; quando a única evidência é o plano, está marcado **(plano)**.

---

## ETAPA 4 — Storyboard (aula 010 "Roteirização básica")

### 4.1 O que a aula ensina

1. **Entrada:** a *imagem base da campanha* da aula 009 — "transformar uma imagem base de campanha em uma sequência de cenas coerente".
2. **Roteirização assistida por IA**: "usar a própria tecnologia para sugerir ideias de cenas em vez de depender apenas da imaginação".
3. **Draw to Edit**: "desenhar referências visuais simples diretamente sobre a imagem base, indicando personagens, escala, posição, movimento e intenção da cena".
4. **Iteração econômica**: "ajustando proporções, refinando prompts, simplificando instruções quando necessário e tomando decisões estratégicas sobre quando gerar mais imagens ou economizar créditos". **(plano)** instruções *uma de cada vez*; gerar 4 quando incerto, 1 quando é tweak. Fórmulas **(plano)**: *"Faça com que o alpinista seja ainda menor e mais realista"*, *"Elimine o pequeno personagem da parte direita"*, Inpaint da corda.
5. **Aceitar imperfeição**: "alucinações da IA, bugs visuais e incoerências de escala… saber iterar, corrigir e avançar".
6. **Multi-Shot** já nesta aula: "gerar múltiplos ângulos da mesma cena para abrir possibilidades narrativas".
7. **Depois dos ângulos**: "selecionar, fazer **upscale**, corrigir elementos específicos da imagem… e preparar o material para uso real".
8. **Storyboard simples**: "organizando as imagens geradas em uma linha narrativa lógica… estruturando **começo, descoberta, ação e desfecho**"; **(plano)** 5 cenas em texto, documento no Google Docs.
9. **Saída:** storyboard com poucas cenas que "já é suficiente para destravar dezenas de novos takes, ângulos e ideias".

### 4.2 O que a implementação faz

- Exige `base/base_final.png` para montar instruções (`storyboard/service.py:101-105`); importar e escrever cenas funciona sem ela.
- Três `KINDS` (draw_to_edit / edit / multishot) com `ui_hint` e 4 presets literais da aula em inglês (`:45-63`).
- `build_instruction` (`:147-172`): valida "uma instrução por vez" (rejeita lista numerada ≥2 ou ≥2 frases, `:141-144`), `count ∈ {4,1}` (`:158-159`).
- Importa resultados (upload / Downloads / histórico CLI); `select_ideas` copia escolhidas para `storyboard/ideas/` (`:221-253`).
- Cenas: 5 vazias por padrão, 1–10 permitidas, texto ≤500, imagem só de `ideas/`; `PUT` regrava `scenes.json` + `storyboard.md` (`:303-333`).
- CLI para `edit`/`multishot` (`:355-415`), job serial.

### 4.3 Divergências — Etapa 4

| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção recomendada |
|---|---|---|---|---|---|
| 4.1 | falta | "selecionar, fazer **upscale**, corrigir elementos… preparar o material para uso real" (010) | Nenhum upscale na etapa 4; só em `shots/service.py:395` | baixa | Aceitar a transferência para a etapa 5, registrando nota na tela ("upscale das ideias acontece na etapa 5") e no FDD §3. |
| 4.2 | desvio de processo (caminho CLI) | Edições são iterativas sobre o último resultado ("Use a última imagem como referência", `ui_hint` `:49`) | `service.py:355-368` aceita `source_id`, mas `view.js:130` envia só `{model, kind, text, count}` → CLI sempre parte de `base_final.png` | média | Na galeria, botão "usar como origem" que preenche `source_id` no corpo de `/cost` e `/generate`. |
| 4.3 | texto da tela enganoso | "gerar mais imagens ou economizar créditos" — gerar é ato na Higgsfield | `view.html:30-31` botões **"Gerar 4 (estou incerto)" / "Gerar 1 (é só um tweak)"** apenas *montam a instrução* (`view.js:120-121`) | média | Renomear para "Montar instrução — gere 4 na Higgsfield (incerto)" / "… gere 1 (tweak)". |
| 4.4 | extensão não marcada | Aula/plano só citam Nano Banana | `view.html:42` oferece `gpt_image_2` | baixa | Manter `nano_banana_2` padrão e marcar a opção extra `[extensão]`. |
| 4.5 | falta (orientação) | "começo, descoberta, ação e desfecho" (010) | `view.js:103` placeholder genérico; `view.html:85` sem a estrutura | baixa | Estrutura nos placeholders das cenas e no painel de guia. |
| 4.6 | desvio de processo (rigidez) | "uma instrução por vez" **(plano)** é sobre *edições*, não pontuação | `_check_single_instruction` (`:141-144`) rejeita `"Make him smaller. Realistic."` → 422 | baixa | Rejeitar só listas numeradas ≥2 ou 2 imperativos; avisar no erro que é heurística. |
| 4.7–4.10 | ok | Draw to Edit é desenho na UI; 4/1; storyboard.md no lugar do Google Docs; 5 cenas | `KINDS`, `COUNTS`, `DEFAULT_SCENES=5` | — | — |

### 4.4 Texto sugerido para o painel de guia — Etapa 4

**O que fazer nesta etapa.** Pegue a imagem base da campanha (etapa 3) e use-a para ter ideias de cena na Higgsfield: desenhe por cima com Draw to Edit indicando personagem, escala, posição e movimento; peça edições **uma instrução por vez** ("faça o alpinista menor e mais realista", "elimine o personagem da direita"); e use Multi Shot para ver a mesma cena de outros ângulos. Gere 4 variações quando estiver incerto e 1 quando for só um ajuste — crédito é decisão estratégica. Aceite bugs, alucinações e erros de escala: corrija e avance. Importe o que gostou, escolha as ideias e escreva a história em ~5 cenas, com começo, descoberta, ação e desfecho.

**Checklist de qualidade da aula**
- Cada instrução pede **uma** coisa; a próxima parte do resultado anterior.
- Instruções simples, em inglês; simplifique quando a IA "alucinar".
- 4 imagens quando incerto, 1 quando é tweak.
- Personagens extras, objetos fora de posição e escala errada corrigidos antes de virar cena.
- Ideias em vários ângulos (Multi Shot).
- ~5 cenas em texto, em ordem: começo → descoberta → ação → desfecho.

**Entradas necessárias:** `base/base_final.png` (etapa 3); conta Higgsfield (UI).
**Saída esperada:** `storyboard/scenes.json` (~5 cenas com texto e ideia escolhida), `storyboard/ideas/`, `storyboard/storyboard.md`.

### 4.5 Validações automáticas — Etapa 4

| Regra | Fonte |
|---|---|
| V4.1 `scenes_with_text >= 5` (ou = total quando o usuário reduziu) antes de liberar a etapa 5 | "5 cenas" **(plano 010)** |
| V4.2 Toda cena tem `image` em `storyboard/ideas/`; alertar cenas sem imagem | "organizando as imagens geradas em uma linha narrativa" |
| V4.3 Ordem contígua `n=1..N` (já) | idem |
| V4.4 Nenhuma instrução importada contém lista numerada ≥2 | "uma instrução por vez" **(plano)** |
| V4.5 `count` CLI ∈ {1,4} (já) | idem |
| V4.6 `storyboard.md` mais novo que `scenes.json` | storyboard como documento (010) |

---

## ETAPA 5 — Ângulos por cena (aula 011)

### 5.1 O que a aula ensina

1. "planejar e organizar os takes principais do vídeo… close no rosto, plano mais aberto com cenário, foco nos pés, foco nas mãos, variações de enquadramento e ritmo. O objetivo é manter um tom mais cinemático".
2. Problema: "lentidão e instabilidade do Higgsfield" e o "'quase realista' que ainda cheira a inteligência artificial".
3. Realismo: Abrahub Realism/Cinema Studio — "linguagem de cinema (câmera, foco, abertura e estilos como documentário, wide, close-up etc.)".
4. **Imagem base da cena**: "Cena 1: o astronauta caminhando na nevasca, sem rosto visível…, sem a lata ao fundo e com sensação clara de movimento". **(plano)** edição numerada *"Quero as seguintes modificações. 1. … 2. … 3. …"*.
5. **Multishot**: "upload da imagem base no Multishot → gerar um grid de variações → selecionar os melhores takes → aplicar upscale e baixar → organizar tudo em pastas por cena (Cena 1… Cena 5)". **(plano)** *"Me traga um outro ponto de vista desta imagem. Quero um close no astronauta."*
6. **Ordenar no storyboard** "usando prints rápidos… ele andando, o plano abrindo, ele chegando à barreira, segurando na rocha e subindo".
7. Regra: "**padronizar cores e iluminação antes de gerar os multishots**".
8. Repetir para as próximas cenas.
9. Aula 013 (embutida): cena extra do produto — "troque a lata da imagem 1 pela da imagem 2" / "tudo ao redor congelado" **(plano)**, criada *depois* de escolher a trilha.

### 5.2 O que a implementação faz

- Lê `storyboard/scenes.json` (409 se ausente); lista cenas com paleta e `WARNING_COLORS` (`shots/service.py:41,105-126`).
- `prepare_base`: ideia da cena, `base_final.png` ou upload → `shots/cenaNN/base.png` (`:151-171`).
- `build_prompts` (`:205-232`): `angle` = "Bring me another point of view… close-up on {subject}. Same scene, same lighting and colors." + bloco de câmera opcional; `edit` = lista numerada.
- Importação por cena; CLI `generate` serial; `upscale` via `bytedance_image_upscale` (`:395-421`).
- `select_shots` (`:437-468`): ordem de clique → `shotMM_final.png`, `selection.json` (`upscaled` de **um** checkbox global, `view.js:204-205`), reconstrói `shots/storyboard.json`.
- Cena do produto: `ref.png` + duas instruções + `product_final.png`.

### 5.3 Divergências — Etapa 5

| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção recomendada |
|---|---|---|---|---|---|
| 5.1 | falta (regra de qualidade) | "selecionar os melhores takes → **aplicar upscale e baixar**" | `select_shots` aceita `upscaled: false` sem aviso (`:458`); checkbox global (`view.js:204`) | média | Mostrar por candidato "upscalado?" (`c.upscaled`/`role`), avisar no `select` quando algum frame não está upscalado, chip "N/M upscalados" por cena. |
| 5.2 | desvio de processo | Cinema Studio gera a **base da cena** → *depois* Multishot | O prompt `edit` gera **candidatos**, não há "promover candidato a base" (`:213-221`) | média | Botão "Usar como base da cena" (`POST …/base {source:"candidate", id}`); `ui_hint` do `edit`: "o resultado vira a nova base; depois faça o Multishot". |
| 5.3 | desvio (posição do bloco de câmera) | Linguagem de câmera é para a base realista | Bloco de câmera só no prompt de **ângulo** (`:227-228`) | baixa | Oferecer o bloco também em `kind=edit`. |
| 5.4 | falta | "monta a ordem dos frames dentro do **documento de storyboard**, usando prints" | Só `shots/storyboard.json` | média | Gerar `shots/storyboard.md` (grid por cena: base + shots na ordem + texto) a cada `select`. |
| 5.5 | texto da tela | "close no rosto… foco nos pés, foco nas mãos" | `view.html:37` campo "foco" livre sem exemplos | baixa | Placeholder com os exemplos da aula. |
| 5.6 | extensão não marcada | Aula não fixa proporção/resolução | `ASPECT_RATIO="16:9"` (`:38`), `resolution="2k"` (`router.py:36,44`) | baixa | Comentar `[extensão]`/decisão 5 no código e FDD. |
| 5.7 | extensão não marcada | "RED comercial" é da aula 013 | `"Shot on RED Komodo 6K"` fixo (`:197`) | baixa | Marcar como preset aprovado (decisão 9); presets editáveis. |
| 5.8 | desvio (ordem entre aulas) | Cena do produto nasce na aula 013, depois da trilha | Painel 3 na etapa 5 sem essa nota | baixa | Nota no painel: "Da aula 013: normalmente feita depois da trilha; volte aqui então". |
| 5.9–5.12 | ok | cores/luz antes do multishot; Cinema Studio → bloco de câmera; prompts literais; pastas por cena | `WARNING_COLORS`, `:224-226`, `shots/cenaNN/` | — | — |

### 5.4 Texto sugerido para o painel de guia — Etapa 5

**O que fazer nesta etapa.** Para cada cena do storyboard, primeiro acerte a imagem base da cena: realismo cinematográfico (câmera, lente, abertura, estilo), rosto oculto se for o caso, sem elementos que não pertencem à cena e com sensação de movimento — peça as modificações numeradas em uma rodada. Acerte cores e luz **antes** do Multishot, porque toda variação herda a base. Então suba a base no Multishot, gere o grid, escolha os melhores takes, faça upscale e baixe. Organize por pasta de cena e ordene os frames como a cena progride. Repita para todas as cenas.

**Checklist de qualidade da aula**
- Base da cena sem "cheiro de plástico": linguagem de cinema.
- Cores e iluminação padronizadas antes do Multishot.
- Vários enquadramentos por cena: close no rosto, plano aberto, foco nos pés/mãos, ritmo variado.
- Só os melhores takes; cada um **upscalado** antes de baixar.
- Uma pasta por cena; frames em ordem de progressão narrativa.
- Storyboard atualizado com os prints, na ordem.

**Entradas necessárias:** `storyboard/scenes.json` com cenas escritas; `base/base_final.png`; `mood/palette.json`; Higgsfield (Multishot, Upscale) e Cinema Studio.
**Saída esperada:** `shots/cenaNN/base.png` + `shotMM_final.png` (upscalados, em ordem) para todas as cenas; `shots/storyboard.json` (+ `shots/storyboard.md`).

### 5.5 Validações automáticas — Etapa 5

| Regra | Fonte |
|---|---|
| V5.1 Toda cena tem `base.png` antes de importar/gerar (já) | "upload da imagem base no Multishot" |
| V5.2 Toda cena tem ≥1 shot em `storyboard.json` antes da etapa 6 | "repetir nas próximas cenas" |
| V5.3 Todo `shots[].upscaled == true`; alerta se não | "aplicar upscale e baixar" |
| V5.4 `order` contíguo e `file` existe (já) | "monta a ordem dos frames" |
| V5.5 Cena com ≥2 shots — aviso | "grid de variações → melhores takes" |
| V5.6 Aviso quando candidatos foram importados antes de a base ser trocada | "cores/luz antes do multishot" |
| V5.7 Prompt de ângulo contém "another point of view" e um `subject` | fórmula **(plano)** |
| V5.8 `product_scene` presente antes da etapa 8 | aula 013 |

---

## ETAPA 6 — Animação (aula 012)

### 6.1 O que a aula ensina

1. Entrada: storyboard — "serve como guia, mas não é algo engessado".
2. "variações de ângulo para uma mesma cena; cortes cinematográficos (wide, POV, close); continuidade entre cenas; transições".
3. Modelos: "**Kling 2.6** — cenas mais simples; **Kling 2.5 Turbo** — transições com Start Frame e End Frame; **Seedance** — movimentos mais complexos… essencial testar diferentes opções".
4. Prompt de movimento: "descrever claramente o movimento desejado. Prompts simples para cenas básicas; Abrahub Creative Engine para prompts mais avançados… Quanto mais claro o comando, melhor". Fórmulas **(plano)**: *"Quero que ele esteja caminhando para frente em meio à nevasca…"*, *"Dolly dramático focando no reflexo de seu capacete"*, start/end: *"Esta é uma cena start frame e end frame. O clima rapidamente se modifica. A movimentação de câmera deve ser lenta e dramática."*
5. Iteração: "testar diferentes prompts; gerar múltiplas variações; selecionar o que é utilizável". **(plano)** gerar 2 → like → download → `videos/cena N/`.
6. "ajustar prompts; trocar modelos; resolver na edição com cortes". **(plano)** trocar após 3–4 falhas; fallback corte para preto.
7. "paciência; saber quando parar de iterar; adaptar a ideia".
8. "nomear e organizar cenas e takes; gerar cenas em **paralelo**". **(plano)** 10 s para transições lentas; áudio do modelo OFF.

### 6.2 O que a implementação faz

- Plano = `shots/storyboard.json` (+ `product_scene`) mesclado com `animate/takes.json` (`animate/service.py:55-140`).
- Por shot: `prompt`, `mode` (simple/elaborate/start_end), `duration ∈ {5,10}`, `start_end`, `fallback_black` (`update_shot :198-218`); `suggest_prompt` (`:238-275`).
- Importa mp4; `attach_take` → `videos/cenaNN/shotMM_takeK.mp4`; `set_like` → `_final.mp4`.
- `failures` a cada 3 sugere próximo de `MODEL_ORDER = kling3_0 → seedance_2_0 → veo3_1_lite`; esgotado → corte para preto (`:30-31, 159-168`).
- CLI: `sound: False`, `mode: pro`, `16:9`, `end_image` se `start_end` (`:381-398`); job serial (padrão 2, máx. 4).

### 6.3 Divergências — Etapa 6

| # | Tipo | Evidência na aula | Evidência no código | Grav. | Correção recomendada |
|---|---|---|---|---|---|
| 6.1 | falta / texto enganoso | "Kling 2.5 Turbo — transições com Start Frame e End Frame"; lede promete start/end | UI **nunca grava `start_end`**: `view.js:154` envia só `{prompt, mode, duration, fallback_black}`; `build_params` só manda `end_image` se `start_end` existe (`:389-395`). Modo `start_end` → CLI gera **sem end frame**; `takes.json.start_end` fica `null`. `next_in_scene` calculado mas não usado. | **alta** | Em `update_shot`, quando `mode == "start_end"` e `start_end` ausente, preencher `{start: image, end: next_in_scene.image}`; na UI, campo "end frame" (próximo shot por padrão; aceitar `edit/last_frames/*.png`). Testar: `generate` em start_end tem `end_image`. |
| 6.2 | extensão não marcada | Modelos da aula: Kling 2.6, 2.5 Turbo, Seedance | `veo3_1_lite` na ordem padrão (`:30`) + regra "duration 8" (`:396-397`) | média | Marcar `[extensão]` ou tirar da ordem padrão. |
| 6.3 | desvio parcialmente registrado | Kling 2.6 / 2.5 Turbo | Tudo em `kling3_0`; sem nota da substituição | baixa | Nota na etapa: "aula usa 2.6/2.5 Turbo; CLI oferece 3.0 para ambos". |
| 6.4 | falta (orientação) | "Abrahub Creative Engine para prompts avançados" | Só template local | baixa | Dica no modo "elaborado": "ou gere no Creative Engine e cole aqui". |
| 6.5 | falta (orientação) | "gerar cenas em paralelo" | Job serial; tela não fala em paralelismo | baixa | Guia: "na UI, dispare vários shots ao mesmo tempo e importe depois". |
| 6.6 | falta | "saber quando parar; adaptar a ideia" | Só `fallback_black` | baixa | Chip após 6 falhas: "adapte a ideia: novo frame na etapa 5 ou corte para preto". |
| 6.7 | extensão não marcada | Aula não fixa proporção/modo | `16:9`, `mode: pro` fixos (`:393`) | baixa | Marcar e permitir override. |
| 6.8 | texto da tela | "Seedance para movimentos complexos" | `MODEL_ORDER` só ordem de falha | baixa | No modo "elaborado", sugerir Seedance. |
| 6.9–6.11 | ok | áudio OFF, 10 s, 2 takes, like, nomenclatura; 3 falhas → modelo; storyboard não engessado | `:32-33, 383-393`, `FAIL_THRESHOLD=3`, `orphan` | — | — |

### 6.4 Texto sugerido para o painel de guia — Etapa 6

**O que fazer nesta etapa.** Anime cada frame do storyboard como um take de vídeo. Descreva o movimento com clareza: prompt simples para cena simples; movimento de câmera + ação (ou o Abrahub Creative Engine) quando a cena pede mais; quanto mais claro, menos a IA alucina. Use Kling para cenas simples, start frame + end frame (dois frames seguidos da mesma cena) para transições, Seedance para movimentos complexos; 10 s quando a mudança é lenta; áudio do modelo desligado. Gere 2 variações, dê like na usável, baixe e nomeie por cena e take. Depois de 3–4 tentativas ruins, troque o modelo ou adapte a ideia; o que não sair, resolve-se na montagem com cortes. Enquanto um take gera, dispare outros em paralelo.

**Checklist de qualidade da aula**
- Movimento pedido presente e coerente.
- Continuidade com a cena anterior/seguinte; variação de ângulo (wide, POV, close).
- Start/end frame quando dois frames se seguem na mesma cena.
- Áudio do modelo OFF; 5 s (10 s se a mudança for lenta).
- Pelo menos 2 takes por shot, 1 usável.
- Após 3–4 falhas: outro modelo, prompt reescrito ou corte para preto.
- Takes nomeados por cena (videos/cenaNN/).

**Entradas necessárias:** `shots/storyboard.json` com frames finais (e `product_scene`); Higgsfield Image-to-Video.
**Saída esperada:** `videos/cenaNN/shotMM_takeK.mp4` para todo shot, um `_final.mp4` por shot (ou `fallback_black`), `animate/takes.json` com prompt, modelo, duração e start/end.

### 6.5 Validações automáticas — Etapa 6

| Regra | Fonte |
|---|---|
| V6.1 Todo shot tem `image` existente | image-to-video |
| V6.2 Todo shot tem take `liked` **ou** `fallback_black` antes da etapa 8 (`ready == total`) | "selecionar o que é utilizável" |
| V6.3 Shot com ≥2 takes antes do like (aviso) | "gerar múltiplas variações" **(plano: 2)** |
| V6.4 `mode == start_end` ⇒ `start_end.end` preenchido e existe | Kling 2.5 Turbo start/end |
| V6.5 CLI com `sound: False` (já) | áudio OFF **(plano)** |
| V6.6 `duration ∈ {5,10}`; 10 só quando `slow` | "10 s para transições lentas" |
| V6.7 `failures >= 3` ⇒ `suggested_model` diferente (já) | "trocar modelos" |
| V6.8 `takes[].file` segue `videos/cenaNN/shotMM_takeK.ext` (já) | "nomear e organizar" |
| V6.9 Prompt não vazio e com verbo de movimento/câmera (aviso) | "descrever claramente o movimento" |
| V6.10 `product_scene` animada | aula 013 |

---

## Síntese (prioridades)

1. **Alta — Etapa 6:** `start_end` nunca gravado pela UI; CLI em modo start/end sai sem `end_image` (`animate/view.js:154`, `animate/service.py:213-214, 389-395`).
2. **Média — Etapa 5:** upscale não exigido/visível por frame; sem "promover resultado a base da cena"; sem `shots/storyboard.md`.
3. **Média — Etapa 4:** botões "Gerar 4/1" não geram; CLI não encadeia edições (`source_id`).
4. **Extensões sem marca:** `veo3_1_lite` (+ 8 s), `gpt_image_2`, `16:9`/`2k`/`mode: pro`, "RED Komodo 6K" — grep de `[extensão]` vazio em `studio/{storyboard,shots,animate}`.
5. Tudo o mais que a aula repete está implementado e coerente com o plano.
