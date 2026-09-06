### FDD: storyboard-cenas

Versão: 1.0
Data: 2026-09-06
Responsável: Arthur Diego (modo autônomo /dd-parallel, Wave 11)
Task-Id: ADH-OS-20260906-08
Cards: [#95 leitura A](https://trello.com/c/QVr0fPRk) · [#97](https://trello.com/c/YroEvP9I) · [#98](https://trello.com/c/ouUqyCNu) · [#99](https://trello.com/c/v4CPkp6p)
Domínio: storyboard (etapa 4) · Frente F06 da `docs/domains/studio/waves/wave-11.md`
Recon: `docs/domains/studio/recon-wave-11.md` §6 e §6.1 · Base: `develop` @ `0c4e823`

> **Gate de fidelidade (CLAUDE.md gate 2, ADR-004).** A aula 010 manda o ALUNO escrever a
> história em ~5 cenas e encaixar as fotos à mão. Tudo que esta frente acrescenta ao redor
> disso é `[extensão]` opt-in, já coberto por decisões vigentes (ADR-018 galeria por cena,
> ADR-022 vídeo por foto, ADR-025 roteiro por LLM, ADR-028 fotos inferidas e ordem dos painéis,
> ADR-033 motor local, ADR-035 preset de realismo no lugar do combo de fórmulas). O caminho da
> aula continua inteiro: escrever à mão, importar as fotos geradas na interface da Higgsfield e
> salvar. Nenhum campo novo é obrigatório e nenhum caminho novo escreve cena sozinho.

---

### 1. Contexto e motivação técnica

#### 1.1 Provides / Consumes (contrato da wave 11)

Bloco copiado de `docs/domains/studio/waves/wave-11.md` (seção "Feature: storyboard-cenas (F06)").

**Provides**

- Painel 02 (roteiro) antes do 03, botão "Gerar cenas (roteiro por Claude) [extensão]" sempre
  visível com diagnóstico do PATH quando o CLI falta; correção do PATH em `run.sh`/`Makefile` se
  for a causa.
- Galeria de ideias visível, botão real "Adicionar foto à cena", drag-and-drop, anexo/remoção/★
  persistidos imediatamente e somando à galeria da cena (#97).
- Preset global por projeto: seletor "Padrão visual da campanha" gravando as ações
  `storyboard.script`, `motion`, `base` pelas rotas `preset-config` existentes; herança por foto
  com override persistido em `scenes.json` (`photos[img].preset`); chave `storyboard.angles`
  registrada em `PRESET_ACTIONS` (default `None`), **contrato consumido por F07** (#98).
- Campos abertos por foto `image_prompt` (novo) e `video_prompt` (editável) persistidos em
  `scenes.json`; `POST …/storyboard/image-prompt` (papel `keyframe` do prompter `[extensão]`);
  `applyScript` traz prompts; indicador de origem ia/manual/template (#99).
- Tools MCP `storyboard_script`, `script_wait`, `storyboard_apply_script`,
  `storyboard_scene_attach`, `storyboard_keyframe_prompt`, `storyboard_keyframe_set`.

**Consumes**

- (opcional, mesma sub-wave) `state_changed` de **chat-sync** (F03), para a galeria atualizar
  após geração vinda do chat; sem ele, refresh no `done` dos jobs da própria tela (fronteira
  mockada).
- `_images_for` robusto e sufixo `{"selected": [...], "next_step": "<id>"}` nos `*_pick` de
  **mcp-pick-shape** (F04, mesma sub-wave). F06 **não** edita `_pick`/`_images_for`: as tools
  novas montam a própria lista de imagens, e o critério "`storyboard_pick` devolve ids e próxima
  ação" é validado no estado integrado. Ver critério `[cross-feature]` 9.C4.

#### 1.2 Problema técnico

A metade "ideação e cenas" da etapa 4 (`Ideation.tsx`, `studio/storyboard/service.py`,
`studio/etapas/storyboard/router.py`) acumulou quatro defeitos que o dono relatou em 2026-09-06:

1. **O roteiro fica invisível.** O botão `#sbScriptGen` nasce `disabled` quando
   `shutil.which("claude")` falha **no processo do backend** (`studio/common/prompter.py:19,290`).
   `BIN` é resolvido em import time, então nem reiniciar a aba resolve: só reiniciar o servidor.
   O usuário não vê o motivo nem o PATH que o processo enxerga, e a mesma checagem existe
   duplicada em `studio/chat/runtime.py:23,36` (`GET /api/chat/status {available}`), sem
   diagnóstico nenhum. `run.sh` executa `. .venv/bin/activate` e não normaliza o PATH: subindo o
   Studio fora de um shell interativo (IDE, Finder, `sh -c`), `$HOME/.local/bin` (onde o `claude`
   mora nesta máquina) some do PATH herdado e o botão morre.
2. **Não existe galeria de ideias na tela.** `#sbGallery` só vive dentro do `PickerModal`
   (`Ideation.tsx:1810`); o painel 01 tem apenas o chip textual `#sbCounts` "N ideias · M
   escolhidas". O único ponto de entrada de uma foto na cena é um tile `.thumb.pick.sb-pick` sem
   texto no DOM (rótulo "+ foto" só por `::after` de 9 px, `Ideation.tsx:2084`). O anexo
   **substitui** a galeria da cena em vez de somar (`attachImages`, `:500-505`) e **não
   persiste**: só `reorderPhoto` chama `persist`; anexar, remover e trocar a ★ ficam no DOM até
   alguém clicar em "Salvar cenas". Não há drag-and-drop (as classes `.dragging`/`.dragover`
   existem no CSS e nunca são aplicadas).
3. **O preset de realismo não tem escopo de campanha.** A configuração por ação já existe inteira
   no servidor (`settings.PRESET_ACTIONS`, `preset_default_for`, `resolve_preset`, rotas
   `studio/creditos/router.py:154-194`, tipadas em `schema.ts:678-745`), mas **nenhuma UI consome
   as rotas de escrita**. Pior: o `RealismField` por foto guarda a escolha em `PhotoMeta.preset`,
   que não é persistido (`buildPayload` não o envia, `seedPhotos` devolve `null`), e
   `genVideoPrompt` manda `preset: null` **sempre** (`:519,:525`), o que na semântica de três
   estados do `VideoPromptReq` significa "sem preset explícito" e **anula** o default da ação
   `motion`. O default configurado nunca chega à geração.
4. **Prompt de imagem e de vídeo não são campos.** `video_prompt` é `<p class="txt
   sbVidPromptText">` (leitura); o prompt de imagem por foto **não existe no modelo**: os
   `shot_prompts` do roteiro moram só em `script.json`, são copiáveis à mão e o `applyScript`
   leva apenas `text` para a cena (`:643`). O backend já aceita prompt livre em
   `POST /video/generate` (`VideoGenerateReq.prompt`), mas a tela bloqueia quando o campo salvo
   está vazio (`:1410-1411`).

#### 1.3 Encaixe na arquitetura

A etapa 4 é plugin (`studio/etapas/storyboard/` + `studio/storyboard/service.py`), então esta
frente vive quase toda fora do núcleo. O núcleo tocado é `frontend/` (apenas o `schema.ts`
gerado, mais `frontend/src/areas/creditos/CreditosArea.tsx` no item opcional C5) e
`studio/web/dist/` (bundle regenerado), ambos declarados em `TITULARES_DO_NUCLEO` (seção 11).
Nada em `studio/common/settings.py` é editado: as ações novas de preset entram pelo mapa ABERTO
`PRESET_ACTIONS` por `setdefault` em import time, o precedente que a própria
`storyboard-roteiro-llm` criou (`service.py:1166`).

#### 1.4 Atores e limites

- **Usuário (dono da campanha)**: escreve cenas, escolhe fotos, escolhe o padrão visual, edita os
  prompts. Toda escrita em `scenes.json` nasce de um gesto dele (ADR-025, ADR-038).
- **Servidor (etapa 4)**: valida, resolve preset, chama o Claude CLI, persiste o que o cliente
  mandou. **Nunca** escreve `scenes.json` a partir do roteiro (ADR-025).
- **Agente (MCP)**: cliente HTTP da própria API (ADR-037). Aplica roteiro e anexa fotos apenas
  depois de `ui_confirm`/`ui_choose_images` (ADR-038), nunca lê nem escreve bytes (ADR-040).
- **Fora do limite**: a metade ângulos/local por cena (`Angles.tsx`, `studio/storyboard/angles.py`,
  `studio/storyboard/local.py`) é da frente F07. F06 toca `angles` apenas pelo registro
  idempotente da chave de preset, e sequer no arquivo dela (ver 5.11).

---

### 2. Objetivos técnicos

- **O roteiro nunca fica escondido.** O botão de roteiro está sempre no DOM e sempre habilitado;
  quando o CLI falta, a tela mostra o caminho procurado e o PATH do processo, e o botão
  "Verificar de novo" re-resolve `shutil.which` **sem reiniciar o servidor**. Invariante: com
  `claude` no PATH do processo, uma checagem com `refresh=true` devolve `available: true` e o job
  parte.
- **O PATH do processo passa a ser determinístico.** `run.sh` prefixa os diretórios de binário do
  usuário antes de executar o uvicorn; medida: subir o app por `sh -c ./run.sh` com um PATH
  mínimo e ainda assim ver `available: true` quando o `claude` existe em `$HOME/.local/bin`.
- **Nenhum gesto de foto exige "Salvar cenas".** Anexar, remover, trocar a ★, reordenar e arrastar
  disparam `PUT /scenes` imediatamente; medida: após cada gesto, `scenes.json` no disco já reflete
  o estado, verificado por vitest e por cenário de QA com reload.
- **Anexar SOMA.** `attachImages` acrescenta à galeria da cena preservando a ordem e sem
  duplicar; substituir é uma ação explícita e confirmada.
- **O default da campanha chega à geração.** Sem override por foto, o corpo enviado a
  `/video-prompt` e a `/image-prompt` **omite** o campo `preset`, e a resposta devolve o preset
  resolvido pela cadeia projeto → global → código. Medida: com `storyboard.script`/`motion`/`base`
  gravados no projeto, a resposta de `/video-prompt` traz o id configurado (hoje traz `null`).
- **Três estados de preset preservados de ponta a ponta.** Ausente = herda, `null` = sem preset,
  `"<id>"` = esse; em memória, no corpo HTTP e em `scenes.json` (chave ausente vs `null` vs id).
- **Prompt de imagem e de vídeo são texto do usuário.** Ambos persistem em
  `photos[img]`, são editáveis, têm gerador de IA opcional e carregam a origem
  (`ia`/`manual`/`template`) e o preset usado. "Gerar animação" usa o texto do campo, inclusive
  escrito à mão.
- **Schema de `scenes.json` só cresce.** Toda chave nova é opcional; `scenes.json` de campanhas
  antigas continua carregando sem migração (ADR-018/022/025).
- **O agente age só pelas tools.** Seis tools novas cobrem roteiro, aplicação, anexo de foto e
  edição de prompt; nenhuma importa serviço de etapa (ADR-037).

---

### 3. Escopo e exclusões

**Incluído**

*A. Roteiro visível (#95 leitura A)*
- A1: diagnóstico do CLI `claude` (caminho, PATH do processo, hora da checagem, dica), rota de
  re-checagem com `refresh`, botão sempre habilitado, painel de diagnóstico com "Verificar de
  novo"; correção do PATH em `run.sh`; unificação da checagem com `GET /api/chat/status`.
- A2: rótulo do botão vira "Gerar cenas (roteiro por Claude) [extensão]"; confirmação e blindagem
  por teste da ordem painel 02 antes do 03 (já verdadeira no código, ADR-028); N prompts de imagem
  por cena expostos como sugestões acionáveis (o dado `shot_prompts` já existe).
- A3: tools MCP `storyboard_script`, `storyboard_script_wait`, `storyboard_apply_script`.

*B. Fotos nas cenas (#97)*
- B1: galeria de ideias visível no painel 01 com badge de origem e filtro, atualizada no `done`
  dos jobs da própria tela (e por `state_changed` quando F03 integrar).
- B2: botão real "Adicionar foto à cena" com texto no DOM e `aria-label`.
- B3: picker com filtro por origem e mensagem de vazio citando o motor local.
- B4: drag-and-drop galeria → cena e entre cenas, com alternativa por teclado ("Mover para…").
- B5: persistência imediata de anexo, remoção, ★ e reordenação.
- B6: `attachImages` soma à galeria da cena; "Substituir tudo" é ação explícita e confirmada.
- B7: política registrada de `selected`/`ideas/` quando a foto sai de todas as cenas.
- B8: tools MCP `storyboard_scene_attach`; validação do contrato de `storyboard_pick` com F04.
- B9: vitest de picker, galeria, anexo, remoção e ★; cenário novo de QA (só acréscimo).

*C. Preset global da campanha (#98)*
- C1: seletor "Padrão visual da campanha" no topo da etapa 4, espelhado na etapa 3.
- C2: escrita pelas rotas `preset-config` existentes, sem rota nova, cobrindo
  `storyboard.script`, `storyboard.keyframe`, `storyboard.angles`, `motion`, `base` e, opcional,
  `mood`.
- C3: `RealismField` mostra "(padrão da campanha: X)" como opção de herança; `genVideoPrompt`
  **omite** `preset` sem override; override por foto persistido em `photos[img].preset`.
- C4: registro idempotente de `storyboard.angles` e `storyboard.keyframe` em `PRESET_ACTIONS`.
- C5 (último, opcional): coluna de preset no painel Créditos › Modelos default por ação.

*D. Keyframe e motion em campos abertos (#99)*
- D1: `photos[img].image_prompt` (novo) e `photos[img].video_prompt` (editável) persistidos;
  `video_desc` mantido; `photos[img].origin` com fonte e preset por campo.
- D2: `POST /api/projects/{pid}/storyboard/image-prompt` com o papel `keyframe` do prompter.
- D3: botões "Gerar com IA" por campo, com confirmação "Substituir?" sobre texto manual.
- D4: `applyScript` com a opção "trazer também os prompts de imagem"; `shot_prompts` viram
  sugestões com "usar este".
- D5: "Gerar animação" usa o texto do campo `video_prompt`, inclusive escrito à mão.
- D6: "Gerar local (grátis)" do painel 01b pode ser pré-preenchido pelo `image_prompt` de uma foto.
- D7: tools MCP `storyboard_keyframe_prompt` e `storyboard_keyframe_set`.

**Excluído**

- Geração de imagem POR CENA com saída em `storyboard/cenaNN/` e os endpoints
  `angles/scenes/{scene}/{cost,generate,upscale}`: são da frente F07 (`storyboard-geracao-por-cena`).
  F06 não toca `Angles.tsx` nem `studio/storyboard/angles.py`.
- Reintroduzir o combo de fórmulas da aula `#sbPreset`: proibido por ADR-035. "Preset global"
  nesta feature é exclusivamente o preset de REALISMO.
- Servidor escrever `scenes.json` a partir do roteiro: proibido por ADR-025. A aplicação continua
  sendo gesto do usuário (tela) ou do agente após `ui_confirm` (tool).
- Fallback determinístico para o ROTEIRO: sem CLI o `POST /script/generate` continua 409
  (ADR-025). O fallback por template vale só para prompt por foto (`/video-prompt` hoje,
  `/image-prompt` agora), que não escreve arquivo por conta própria.
- Anunciar o roteiro no guia da etapa (`studio/etapas/storyboard/guide.py`): sugestão registrada
  em `storyboard-roteiro-llm-fdd` §13.5, fora do escopo destes quatro cards.
- Migrar `angles.py` para o multishot do núcleo (ADR-017), mexer em `pricing`/`ACTIONS` (F05) ou
  no `CostSheet`/`_paid` (F10).
- STT, markdown do chat, navegação automática e demais frentes da wave.

---

### 4. Fluxos detalhados e diagramas

#### Fluxo principal 1: diagnóstico e uso do roteiro (A)

1. A tela monta e lê `GET /api/projects/{pid}/storyboard`. O status traz `script_cli` (booleano,
   compatível) e o campo aditivo `script_cli_diag` com `{name, available, path, searched_path,
   checked_at, hint}`.
2. O botão `#sbScriptGen` (rótulo "Gerar cenas (roteiro por Claude) [extensão]") é renderizado
   **sempre habilitado**. Quando `available` é falso, um bloco `#sbScriptCliDiag` com
   `role="status"` e `aria-live="polite"` mostra: "Claude CLI não encontrado. PATH do processo:
   `<searched_path>`" mais a dica.
3. Clique no botão com `available` falso: a tela chama
   `GET …/storyboard/script/cli?refresh=true` (uma requisição, sem job). Se voltar
   `available: true`, o fluxo segue para o passo 4 na mesma interação. Se voltar falso, a tela
   atualiza o diagnóstico e não dispara `POST /script/generate` (evita 409 inútil), mantendo o
   foco no bloco de diagnóstico.
4. Clique com `available` verdadeiro: `progressJob` sobre `POST /script/generate` +
   `GET /script/job`, exatamente como hoje; no `done`, `GET /script` popula o painel 02.
5. Botão "Verificar de novo" (`#sbScriptCliRecheck`) chama a mesma rota com `refresh=true` a
   qualquer momento, independentemente do botão principal.
6. Aplicar: "Aplicar às cenas vazias" ou "Substituir tudo", com a caixa nova "trazer também os
   prompts de imagem" (fluxo 4).

#### Fluxo principal 2: foto entra, sai e se move entre cenas (B)

1. Painel 01 renderiza `#sbIdeasGallery` a partir de `GET …/storyboard/candidates`. Cada card
   traz `data-id`, `data-file`, `data-source` e um badge legível de origem
   (`cli` = "Higgsfield (CLI)", `local` = "Motor local (grátis)", `local_kind: "inpaint"` =
   "Inpaint local", `upload` = "Enviada", `downloads` = "Downloads", `history` = "Histórico HF")
   mais a marca "escolhida" quando `selected`.
2. Filtro por origem (`#sbIdeasFilter`) aplica-se à galeria do painel 01 e ao `PickerModal`.
3. Anexar por botão: `button.sb-pick.sbAddPhoto` com o texto "+ Adicionar foto à cena" no DOM e
   `aria-label="Adicionar foto à cena N"` abre o `PickerModal`. As ações do modal são
   "Adicionar à cena" (primária), "Substituir tudo" (fantasma, com `window.confirm`),
   "Sem imagem" e "Importar ideias…".
4. `attachImages(i, ids, mode)`: marca as ideias novas como `selected`
   (`POST /candidates/select` com a união, comportamento atual), resolve os `file` e, com
   `mode="add"` (default), monta `images: dedup([...atual, ...novas])`, mantendo a `primary`
   atual; com `mode="replace"`, substitui. Em seguida chama `persist` (PUT /scenes) e recarrega
   status e guia.
5. Remover (`.sb-rm`), estrelar (`.sb-star`) e reordenar (`↑`/`↓`) chamam `persist` na mesma
   interação, com o estado já atualizado (atualizações funcionais para evitar payload obsoleto).
6. Arrastar: o card da galeria e o `.sb-key` são `draggable`. `dragstart` grava
   `application/x-studio-idea` (id da ideia) ou `application/x-studio-photo`
   (`{"sid","img"}`); `.sb-phototable` e `.sb-key` aplicam `.dragover` no `dragover` e tratam o
   `drop`: ideia solta em uma cena vira anexo (passo 4, `mode="add"`); foto solta em outra cena
   move (remove da origem, acrescenta no destino); foto solta sobre outra `.sb-key` da mesma cena
   reordena. Todo `drop` termina em `persist`.
7. Alternativa por teclado: cada linha de foto tem `select.sbPhotoMove` ("Mover para…") listando
   as demais cenas; escolher executa o mesmo movimento do `drop` entre cenas.
8. Quando uma foto deixa de estar em qualquer cena, ela **continua** `selected` e **continua** em
   `storyboard/ideas/`. Desmarcar é gesto exclusivo da galeria (`POST /candidates/select`), que já
   desanexa das cenas e apaga de `ideas/` (`select_ideas`, `service.py:424-465`).

#### Fluxo principal 3: padrão visual da campanha (C)

1. No topo da etapa 4, o bloco `#sbCampaignPreset` ("Padrão visual da campanha") lê
   `GET /api/prompter/presets?pid=<pid>` e mostra o valor resolvido. Quando as ações do conjunto
   resolvem para presets diferentes, o seletor exibe "(misto)" e a mudança nivela todas.
2. Escolher um preset dispara, em série,
   `PUT /api/projects/{pid}/prompter/preset-config {kind, preset}` para cada `kind` do conjunto
   `["storyboard.script", "storyboard.keyframe", "storyboard.angles", "motion", "base"]`
   (mais `"mood"` quando a caixa "aplicar também ao mood board" está marcada). Escolher "(herdar
   do global)" dispara `DELETE /api/projects/{pid}/prompter/preset-config/{kind}` para os mesmos
   `kind`. Falha parcial: a tela reporta quais `kind` falharam e recarrega o estado real.
3. O `RealismField` por foto e o do roteiro passam a ter três opções distintas: "(padrão da
   campanha: X)" com valor vazio (herda), "(sem preset)" com valor `off`, e cada preset do
   catálogo. O valor vazio é o default.
4. Ao gerar prompt de vídeo ou de imagem, o corpo **omite** `preset` quando a foto herda, manda
   `preset: null` quando o usuário escolheu "(sem preset)" e manda o id quando ele escolheu um.
5. O servidor resolve por `settings.resolve_preset(<ação>, pid, preset_arg)` e devolve `preset`
   na resposta; a tela grava o preset resolvido em `photos[img].origin.<campo>.preset`.

#### Fluxo principal 4: campos abertos de keyframe e motion (D)

1. Cada `PhotoRow` mostra, além do `video_desc` já existente, dois campos: "Prompt de imagem
   (keyframe)" (`textarea.sbImgPromptField`) e "Prompt de vídeo" (`textarea.sbVidPromptField`),
   ambos com botão "Gerar com IA" ao lado (`button.sbImgPrompt` e o já existente
   `button.sbVidPrompt`), botão "Copiar" e um chip de origem `.sbPromptOrigin`.
2. "Gerar com IA" do prompt de imagem: `POST …/storyboard/image-prompt` com `scene_id`, `photo`,
   `description` (o `video_desc` da foto vale como contexto quando o campo de instrução está
   vazio) e o `preset` conforme o fluxo 3. A resposta preenche o campo.
3. "Gerar com IA" do prompt de vídeo: `POST …/storyboard/video-prompt`, como hoje, com a correção
   de omissão do `preset`.
4. Se o campo alvo já tem texto **de origem `manual`**, a tela pergunta "Substituir o texto que
   você escreveu?" **depois** de a geração voltar; recusar mantém o texto e oferece "Copiar" da
   sugestão. Texto de origem `ia`/`template` é sobrescrito sem perguntar (é regeneração).
5. Toda escrita nos campos (manual ou por IA) chama `persist` com debounce de 400 ms para digitação
   e imediatamente para o resultado da IA, gravando também `origin.<campo> = {source, preset, at}`.
6. `applyScript(all, withPrompts)`: com a caixa "trazer também os prompts de imagem" marcada, a
   cena `i` recebe `text` como hoje e, para cada foto `k` já anexada à cena, recebe
   `photos[img].image_prompt = script.scenes[i].shot_prompts[k]` (quando existir), com
   `origin.image_prompt = {source: "ia", preset: script.preset}`. Prompts sobrando continuam
   visíveis no painel 02 com o botão "usar este".
7. "usar este" em um `shot_prompt` do painel 02 grava o texto no `image_prompt` da foto `k` da
   cena correspondente; sem foto `k`, a tela avisa quantas fotos a cena tem.
8. "Gerar animação": o modal usa o valor do campo `video_prompt` (estado da tela), não o valor
   salvo, e só bloqueia quando o campo está vazio.
9. "Usar no motor local": copia o `image_prompt` da foto para `#sbLocalPrompt` do painel 01b e
   move o foco para lá. A geração por cena com saída em `cenaNN/` continua sendo de F07.

**Fluxos alternativos e exceções**

- CLI ausente no `POST /script/generate`: 409 com a mensagem de sempre (ADR-025); o
  `progressJob` mostra o erro e o bloco de diagnóstico aparece.
- CLI ausente no `POST /image-prompt`: **não** é 409. Igual a `/video-prompt`, cai no template
  determinístico e devolve `source: "template"`; o chip de origem mostra "template".
- Job de roteiro concorrente: 409 antes da checagem de CLI (precedência já implementada,
  `service.py:1370`).
- `PUT /scenes` com imagem fora de `storyboard/ideas/`: 422 de `_check_image`, comportamento atual.
- Drop de uma ideia ainda não `selected`: o passo de `POST /candidates/select` roda antes do
  anexo; se ele falhar, nada é anexado e a tela mostra o erro.
- Preset gravado que saiu do catálogo: `preset_default_for` já ignora id morto e cai para o nível
  seguinte; a tela nunca fica presa.
- Agente sem UI (terminal, sem `STUDIO_CHAT_ID`): `storyboard_apply_script` e
  `storyboard_scene_attach` exigem `confirm=true`/`ids` explícitos, mesmo padrão de `_paid`.

**Diagramas**

- Sequência sugerida (fechamento): `docs/domains/storyboard/diagrams/mermaid/storyboard-cenas-fotos.mmd`
  (galeria → picker/drop → `attachImages` → `PUT /scenes` → disco) e
  `storyboard-cenas-preset.mmd` (seletor da campanha → `preset-config` → `resolve_preset` →
  prompt gerado). Não bloqueiam a implementação.

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Convenção do repositório: sem `response_model` declarado; o contrato tipado do cliente é
`frontend/src/api/schema.ts`, regenerado por `make frontend-schema` sempre que uma rota ou um
modelo Pydantic muda. Todos os campos novos são ADITIVOS; nenhum campo existente muda de nome,
tipo ou semântica.

#### 5.1 `GET /api/projects/{pid}/storyboard/script/cli` (novo)

- Tipo: endpoint HTTP
- Método: GET
- Query: `refresh` (booleano, default `false`). Com `true`, re-resolve `shutil.which("claude")` e
  atualiza `prompter.BIN` no processo.
- Status: `200` sempre que o projeto existe; `404` para projeto inexistente (via
  `refs.project_dir`). Nunca 409: a ausência do CLI é **dado**, não erro.

**Exemplo de requisição**

```
GET /api/projects/campanha-01/storyboard/script/cli?refresh=true
```

**Exemplo de resposta**

```json
{
  "name": "claude",
  "available": false,
  "path": null,
  "searched_path": "/usr/bin:/bin:/usr/sbin:/sbin",
  "checked_at": "2026-09-06T14:03:11",
  "hint": "Claude CLI não encontrado no PATH deste processo. Instale o Claude Code ou suba o Studio por ./run.sh (que acrescenta ~/.local/bin ao PATH) e clique em Verificar de novo."
}
```

#### 5.2 `GET /api/projects/{pid}/storyboard` (campo aditivo)

- Tipo: endpoint HTTP existente (`sb.status`)
- Acréscimo: `script_cli_diag`, o mesmo objeto de 5.1 **sem** `refresh` (leitura barata, sem
  re-resolver o PATH). `script_cli` (booleano) permanece com a semântica atual.

**Exemplo de resposta (trecho)**

```json
{
  "script_cli": false,
  "script_cli_diag": {
    "name": "claude", "available": false, "path": null,
    "searched_path": "/usr/bin:/bin", "checked_at": "2026-09-06T14:03:11",
    "hint": "Claude CLI não encontrado no PATH deste processo. …"
  }
}
```

#### 5.3 `GET /api/chat/status` (campo aditivo, item opcional A1c)

- Tipo: endpoint HTTP existente (`studio/chat/router.py:75-78`)
- Acréscimo: as mesmas chaves de 5.1 ao lado de `available`, produzidas pelo mesmo helper
  (`studio/common/clibin.py`), de modo que a tela do chat e a do storyboard nunca discordem sobre
  o mesmo binário. `available` continua no mesmo lugar e com o mesmo tipo.

**Exemplo de resposta**

```json
{"available": true, "name": "claude", "path": "/Users/x/.local/bin/claude",
 "searched_path": "/Users/x/.local/bin:/usr/bin", "checked_at": "2026-09-06T14:03:11", "hint": ""}
```

#### 5.4 `POST /api/projects/{pid}/storyboard/image-prompt` (novo)

- Tipo: endpoint HTTP
- Método: POST
- Corpo (`ImagePromptReq`): `scene_id` (obrigatório, `cenaNN`), `photo` (obrigatório, caminho
  relativo sob `storyboard/ideas/`), `description` (opcional, teto 500, o contexto do que a foto
  precisa mostrar), `preset` (opcional, três estados como em `VideoPromptReq`: ausente resolve o
  default da ação `storyboard.keyframe`; `null` desliga; `"<id>"` usa esse; id fora do catálogo
  vira 422 no validador, antes de qualquer chamada ao CLI).
- Status: `200` prompt pronto; `404` projeto inexistente; `422` `scene_id`/`photo`/`description`/
  `preset` inválidos (inclusive foto fora de `storyboard/ideas/`); **não existe 409**: sem CLI o
  serviço cai no template determinístico.
- Limites: sem custo de crédito (Claude CLI é assinatura local, ADR-025), timeout do prompter
  (`TIMEOUT_S` = 180 s), 1 imagem enviada ao bot.
- Não persiste nada: quem grava é o cliente, pelo `PUT /scenes` (mesma política de
  `/video-prompt`).

**Exemplo de requisição**

```json
{
  "scene_id": "cena02",
  "photo": "storyboard/ideas/a1b2c3d4e5f6.png",
  "description": "o produto na mão do personagem, chuva forte ao fundo",
  "preset": "documentary-street"
}
```

**Exemplo de resposta**

```json
{
  "prompt": "A lone courier holds the can at chest height … Camera: Blackmagic Pocket 6K Pro, Cooke S4, Super 35, 24-35mm, T2.8 …",
  "negative": "plastic skin, airbrushed look, oversaturation, HDR glow, CGI look",
  "source": "claude",
  "seconds": 12.4,
  "preset": "documentary-street"
}
```

#### 5.5 `PUT /api/projects/{pid}/storyboard/scenes` (schema aditivo por foto)

- Tipo: endpoint HTTP existente (`SceneIn` em `router.py:50-59`, `sb.save_scenes`)
- `SceneIn.photos` já é `dict` livre, então **nenhum modelo Pydantic muda**. O que muda é a
  normalização e a poda em `_scene_photos`/`save_scenes`, que passam a preservar por foto:
  - `image_prompt` (string, default `""`, teto `MAX_PHOTO_PROMPT` = 4000);
  - `video_prompt` (string, já existente, mesmo teto novo);
  - `video_desc` (string, já existente, teto `MAX_VIDEO_DESC` = 500);
  - `videos` (lista, já existente);
  - `preset` (**opcional**: chave AUSENTE = herda o default da ação; `null` = sem preset;
    `"<id>"` = esse id, validado por `prompter.valid_preset`, id desconhecido vira 422);
  - `origin` (mapa opcional `{campo: {source, preset, at}}`, com `campo ∈ {image_prompt,
    video_prompt}`, `source ∈ {ia, manual, template}`, `preset` string ou `null`, `at` ISO 8601;
    valores fora do enum são descartados, não derrubam o save).
- Retrocompatibilidade: `photos` antigo (só `video_desc`/`video_prompt`/`videos`) carrega igual;
  a migração do par por cena para a foto principal (ADR-022) continua idêntica.

**Exemplo de requisição (trecho de uma cena)**

```json
{
  "scenes": [
    {
      "text": "O entregador cruza a avenida sob chuva.",
      "images": ["storyboard/ideas/a1.png", "storyboard/ideas/b2.png"],
      "primary": "storyboard/ideas/a1.png",
      "photos": {
        "storyboard/ideas/a1.png": {
          "video_desc": "he steps off the curb",
          "video_prompt": "A photorealistic cinematic animation of …",
          "image_prompt": "A lone courier steps off the curb …",
          "videos": [],
          "preset": null,
          "origin": {
            "image_prompt": {"source": "ia", "preset": "documentary-street", "at": "2026-09-06T14:20:00"},
            "video_prompt": {"source": "manual", "preset": null, "at": "2026-09-06T14:31:02"}
          }
        },
        "storyboard/ideas/b2.png": {"video_desc": "", "video_prompt": "", "image_prompt": "", "videos": []}
      }
    }
  ]
}
```

**Exemplo de resposta (trecho)**

```json
{"scenes": [{"id": "cena01", "n": 1, "text": "O entregador cruza a avenida sob chuva.",
             "images": ["storyboard/ideas/a1.png", "storyboard/ideas/b2.png"],
             "primary": "storyboard/ideas/a1.png",
             "photos": {"storyboard/ideas/a1.png": {"video_desc": "he steps off the curb",
                                                     "video_prompt": "A photorealistic …",
                                                     "image_prompt": "A lone courier …",
                                                     "videos": [], "preset": null,
                                                     "origin": {"image_prompt": {"source": "ia", "preset": "documentary-street", "at": "2026-09-06T14:20:00"}}}}}],
 "storyboard_md": "storyboard/storyboard.md"}
```

#### 5.6 `GET /api/projects/{pid}/storyboard/candidates` (campo aditivo)

- Tipo: endpoint HTTP existente (`sb.list_ideas` → `_idea_row`)
- Acréscimo por ideia: `local_kind` (string ou `null`), lido do `meta` do candidato
  (`local.py:70,127` grava `local_kind: "keyframe_local"` e o do inpaint). Serve só para o badge
  de origem distinguir "Motor local (grátis)" de "Inpaint local". `source`, `file`, `thumb`,
  `prompt`, `selected` e `imported` seguem intocados.

**Exemplo de resposta (trecho)**

```json
{"ideas": [{"id": "a1b2c3", "file": "storyboard/ideas/a1b2c3.png",
            "thumb": "storyboard/candidates/thumbs/a1b2c3.jpg", "prompt": "…",
            "selected": true, "source": "local", "local_kind": "keyframe_local", "imported": ""}]}
```

#### 5.7 `POST /api/projects/{pid}/storyboard/video-prompt` (semântica corrigida no cliente)

- Tipo: endpoint HTTP existente. **O contrato do servidor não muda.** O que muda é o cliente: a
  tela deixa de mandar `preset: null` sempre e passa a **omitir** o campo quando a foto herda o
  default da campanha. Registrado aqui porque é o ponto exato onde o default hoje é anulado
  (`Ideation.tsx:519,525`).

**Exemplo de requisição (herdando o padrão da campanha)**

```json
{"scene_id": "cena01", "description": "he steps off the curb",
 "frames": {"mode": "single", "image": "storyboard/ideas/a1.png"}}
```

**Exemplo de resposta**

```json
{"prompt": "A photorealistic cinematic animation of …", "source": "claude",
 "seconds": 5, "preset": "documentary-street"}
```

#### 5.8 Rotas de preset já existentes (consumo, sem alteração)

- `GET /api/prompter/presets?pid=<pid>` → `{presets, defaults}`; `defaults` passa a listar
  também `storyboard.angles` e `storyboard.keyframe` (efeito colateral aditivo do registro em
  `PRESET_ACTIONS`, mesmo mecanismo que já acrescentou `storyboard.script`).
- `PUT /api/projects/{pid}/prompter/preset-config` com `{kind, preset}`.
- `DELETE /api/projects/{pid}/prompter/preset-config/{kind}`.
- `PUT /api/prompter/preset-config` (global) para o painel de Créditos (item C5).

**Exemplo de requisição (uma das cinco chamadas do seletor da campanha)**

```json
{"kind": "storyboard.keyframe", "preset": "arri-natural-narrative"}
```

**Exemplo de resposta**

```json
{"kind": "storyboard.keyframe", "preset": "arri-natural-narrative", "source": "project"}
```

#### 5.9 `studio/common/clibin.py` (módulo novo, contrato interno)

```python
def which(name: str = "claude") -> str | None:
    """`shutil.which` isolado, para o teste substituir sem tocar em `os.environ`."""

def describe(name: str, path: str | None, hint: str = "") -> dict:
    """Diagnóstico serializável: {name, available, path, searched_path, checked_at, hint}.
    `searched_path` é `os.environ.get("PATH", "")`; `hint` só aparece quando `path` é None."""
```

Consumidores: `prompter.cli_status` (5.10) e, no item opcional A1c, `studio/chat/runtime.py`.
Função pura o bastante para teste sem rede e sem subprocess (ADR-008).

#### 5.10 `prompter.cli_status(refresh: bool = False) -> dict` (contrato interno, aditivo)

```python
def cli_status(refresh: bool = False) -> dict:
    """Diagnóstico do binário `claude` VISTO POR ESTE PROCESSO.

    `refresh=True` re-resolve `shutil.which` e reatribui o módulo-global `BIN` (é o que faz o
    botão "Verificar de novo" funcionar sem reiniciar o servidor). `refresh=False` apenas
    descreve o `BIN` atual, então `monkeypatch.setattr(prompter, "BIN", …)` continua sendo o
    jeito de fingir o CLI nos testes (ADR-008).
    """
```

`available()` continua sendo `BIN is not None` e continua patchável; nenhuma chamada existente
muda de comportamento.

#### 5.11 `settings.PRESET_ACTIONS`: chaves novas (registro aditivo em import time)

```python
# studio/storyboard/service.py, ao lado do registro já existente de SCRIPT_ACTION
ANGLES_ACTION = "storyboard.angles"        # contrato consumido por F07
KEYFRAME_ACTION = "storyboard.keyframe"    # papel `keyframe` do prompter
settings.PRESET_ACTIONS.setdefault(ANGLES_ACTION, None)
settings.PRESET_ACTIONS.setdefault(KEYFRAME_ACTION, None)
```

`studio/common/settings.py` **não é editado** (evita conflito com F05, que mexe em `ACTIONS`).
`setdefault` torna o registro idempotente: se F07 registrar a mesma chave em
`studio/storyboard/angles.py`, as duas convivem e o rebase é trivial. Default de código `None`
nas duas, coerente com o opt-in do gate W3 da provedora (ADR-004).

#### 5.12 `prompter.keyframe(...)` (contrato interno, novo, `[extensão]`)

```python
def keyframe(images: list[Path], brief: dict, preset: str | None = None,
             model_target: str = "nano_banana_2") -> dict:
    """UM prompt de imagem (briefing de diretor de fotografia) para UMA foto do storyboard.

    Reusa a ordem de briefing e o hint de modelo do roteiro (`ROLES["script"]`,
    `SCRIPT_MODEL_HINTS`) por meio das constantes compartilhadas, o `script_preset_block` para o
    rig e o `_parse` do prompt único para a resposta. Devolve
    `{prompt, negative, source, seconds, preset}`. Sem CLI, `_run` levanta `RuntimeError` e quem
    chama (o serviço) cai no template determinístico.
    """
```

Papel novo `ROLES["keyframe"]` (`[extensão]`, ADR-004): mesma ordem sujeito → ação → ambiente →
câmera/lente/abertura do rig → luz com UMA fonte dominante → texturas → grade → composição e
proporção → bloco de fidelidade → negativos, para UMA foto, em inglês.

#### 5.13 Tool MCP `storyboard_script`

```python
def storyboard_script(client: StudioClient, pid: str, count: int = 5, arc: str = "",
                      preset: str | None = None) -> str
```

- Registro em `studio/mcp/server.py`, ao final do bloco "ações: 4 Storyboard", nome
  `storyboard_script`, descrição "Pede ao Claude um roteiro de N cenas para a campanha
  (`[extensão]`, sem crédito). Acompanhe com `storyboard_script_wait`.".
- `arc` é uma instrução livre em pt-BR sobre a narrativa (vai como `instruction`, teto 300). O
  arco POR CENA continua sendo decidido pelo servidor (`scene_arc`), nunca pelo modelo (ADR-028).
- `preset` ausente deixa o servidor resolver o default da ação `storyboard.script`.
- Retorno (sucesso): `"Roteiro em geração: 5 cenas (preset documentary-street). Acompanhe com \`storyboard_script_wait\`."`
- Retorno (409 sem CLI): a mensagem do servidor, literal:
  `"Claude CLI não encontrado no PATH: escreva as cenas manualmente (aula 010) ou instale o Claude Code"`.

#### 5.14 Tool MCP `storyboard_script_wait`

```python
def storyboard_script_wait(client: StudioClient, pid: str, timeout: int = 600) -> str
```

- Faz polling de `GET …/storyboard/script/job` a cada 2 s (mesmo padrão de `tools.job_wait`,
  `studio/mcp/tools.py:140`), até `state` sair de `running` ou estourar o `timeout`.
- No fim, lê `GET …/storyboard/script` e resume.
- Retorno (sucesso):
  `"Roteiro pronto: 5 cenas (comeco, descoberta, acao, acao, desfecho), 3 a 5 fotos por cena, preset documentary-street. Aplique com \`storyboard_apply_script\` (mode=empty não sobrescreve o que você escreveu)."`
- Retorno (erro do job): `"O roteiro falhou: <última linha do log>. Nada foi gravado; peça de novo."`
- Retorno (timeout): `"O roteiro ainda está rodando depois de 600 s. Chame \`storyboard_script_wait\` de novo."`

#### 5.15 Tool MCP `storyboard_apply_script`

```python
def storyboard_apply_script(client: StudioClient, pid: str, mode: str = "empty",
                            with_prompts: bool = False, confirm: bool = False) -> str
```

- `mode`: `empty` (só cenas sem texto) ou `replace` (todas). Outro valor devolve texto de erro
  sem tocar em nada.
- Lê `GET …/storyboard/script` e `GET …/storyboard/scenes`, monta o payload em memória e, **antes
  de escrever**, pede autorização humana: com `ui.chat_id()`, `ui.confirm(client, título,
  detalhe)` listando quantas cenas serão escritas e quais têm texto; sem chat, exige
  `confirm=true` (mesmo padrão de `_paid`, `actions.py:34-59`). Só então faz `PUT …/scenes`.
- Isso mantém a ADR-025 intacta: quem escreve `scenes.json` é sempre um cliente agindo por gesto
  humano, nunca o servidor a partir do `script.json`.
- `with_prompts=True` leva também `shot_prompts[k]` para o `image_prompt` da k-ésima foto já
  anexada de cada cena, com `origin.image_prompt = {"source": "ia", "preset": <preset do script>}`.
- Retorno: `"3 cena(s) preenchida(s) pelo roteiro (mode=empty, prompts de imagem: sim). 2 sugestão(ões) sobraram: use \`storyboard_scenes\` para conferir."`
- Retorno (recusa): `"Aplicação cancelada pelo usuário. Nada foi escrito em scenes.json."`

#### 5.16 Tool MCP `storyboard_scene_attach`

```python
def storyboard_scene_attach(client: StudioClient, pid: str, scene: str,
                            ids: list[str] = []) -> str  # noqa: B006
```

- Lê `GET …/storyboard/candidates` e filtra às ideias **escolhidas** (`selected: true`), que são
  as únicas que existem em `storyboard/ideas/` e portanto as únicas que `_check_image` aceita.
- Monta as imagens do widget com o `thumb` **já relativo à raiz do projeto**
  (`/files/{pid}/{thumb}`), sem passar por `_images_for` (que prefixa `candidates/` e duplicaria o
  caminho). Isso deixa F06 fora do arquivo que F04 conserta.
- Sem `ids`, chama `ui.choose_images(client, "Escolha as fotos da cena N", imgs, minimum=1)`;
  com `ids`, usa a lista dada (caminho de terminal).
- Lê `GET …/storyboard/scenes`, SOMA à galeria da cena (dedup, ordem preservada), define a
  `primary` só quando a cena não tinha nenhuma, e faz `PUT …/scenes`.
- Retorno: `"2 foto(s) anexada(s) à cena02 (agora com 3). Próxima ação: \`storyboard_keyframe_prompt\` para escrever o prompt de imagem de cada foto, ou \`storyboard_scenes\` para revisar."`
- Retorno (sem ideias escolhidas): `"Nenhuma ideia escolhida ainda. Use \`storyboard_pick\` para o usuário escolher, ou \`storyboard_local_generate\` para gerar de graça no motor local."`

#### 5.17 Tool MCP `storyboard_keyframe_prompt`

```python
def storyboard_keyframe_prompt(client: StudioClient, pid: str, scene: str, image: str,
                               kind: str = "image", description: str = "") -> str
```

- `kind="image"` → `POST …/storyboard/image-prompt`; `kind="video"` → `POST …/storyboard/video-prompt`.
- `image` aceita o caminho relativo completo (`storyboard/ideas/x.png`) ou só o nome do arquivo,
  resolvido contra as imagens da cena lidas de `GET …/scenes`.
- Grava o resultado por `PUT …/scenes` com `origin.<campo> = {"source": <source da resposta>,
  "preset": <preset da resposta>}`. Se o campo alvo já tem texto de origem `manual`, pede
  `ui.confirm` antes de sobrescrever (sem chat, não sobrescreve e devolve o texto sugerido).
- Retorno: `"Prompt de imagem escrito para cena02/a1.png (fonte: claude, preset documentary-street): \"A lone courier steps off the curb …\" (312 chars). Ajuste com \`storyboard_keyframe_set\`."`

#### 5.18 Tool MCP `storyboard_keyframe_set`

```python
def storyboard_keyframe_set(client: StudioClient, pid: str, scene: str, image: str,
                            field: str, text: str) -> str
```

- `field ∈ {"image_prompt", "video_prompt", "video_desc"}`; qualquer outro valor devolve erro sem
  escrever.
- Lê `GET …/scenes`, aplica o texto na foto, marca `origin.<campo> = {"source": "manual",
  "preset": null}` e faz `PUT …/scenes`. Respeita os tetos do servidor (o 422 volta como texto).
- Retorno: `"video_prompt de cena02/a1.png atualizado (manual, 240 chars). Gere a animação pela tela (\`ui_open\` storyboard) ou peça \`storyboard_keyframe_prompt\` para reescrever com IA."`

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Tratamento | Observações |
| --- | --- | --- |
| Projeto inexistente em qualquer rota nova | 404 via `refs.project_dir` | Padrão da etapa |
| `scene_id` fora de `cenaNN` em `/image-prompt` | 422 (`_valid_scene_id`) | Antes de qualquer CLI |
| `photo` fora de `storyboard/ideas/` ou inexistente | 422 (`_check_image`) | Bloqueia path traversal |
| `description` acima de 500 chars em `/image-prompt` | 422 | Mesmo teto de `MAX_VIDEO_DESC` |
| `preset` fora do catálogo em `/image-prompt` | 422 no `field_validator` | Antes de chamar o CLI |
| Claude ausente em `/image-prompt` | 200 com `source: "template"` | Simetria com `/video-prompt`; nunca 409 |
| Claude falha ou estoura timeout em `/image-prompt` | 200 com `source: "template"` e `log.warning` | Igual a `video_prompt` (`service.py:938-940`) |
| Claude ausente em `/script/generate` | 409, mensagem atual | ADR-025, inalterado |
| Job de roteiro já rodando | 409 antes do 409 de CLI | Precedência atual preservada |
| `image_prompt`/`video_prompt` acima de 4000 chars no `PUT /scenes` | 422 citando a cena e a foto | Teto novo `MAX_PHOTO_PROMPT` |
| `photos[img].preset` com id fora do catálogo no `PUT /scenes` | 422 | `prompter.valid_preset` |
| `photos[img].origin` malformado | Descartado silenciosamente | Metadado, nunca derruba o save (mesma leniência dos `videos`) |
| `PUT /scenes` com foto que saiu de `ideas/` | 422 de `_check_image` | Comportamento atual |
| `preset-config` com `kind` desconhecido | 422 citando ações e presets válidos | `_preset_422`, existente |
| Falha parcial nas N chamadas do seletor da campanha | Toast citando os `kind` que falharam e recarga do estado real | Sem retry automático |
| `GET …/script/cli?refresh=true` com PATH inacessível | 200 com `available: false` e `hint` | Diagnóstico nunca é erro |
| Drop de arquivo do sistema operacional na cena | Ignorado (só os dois MIME internos são aceitos) | O upload continua sendo pelo painel 01 |
| Tool MCP sem UI e sem `confirm` | Texto explicando como confirmar | Padrão `_paid` |
| Tool MCP com `mode`/`field`/`kind` inválido | Texto de erro, nenhuma escrita | Tools nunca levantam exceção crua |

**Estratégias de resiliência**

- Timeouts: prompter 180 s (`TIMEOUT_S`) para `/image-prompt`; roteiro 300 s (`SCRIPT_TIMEOUT_S`),
  inalterado; `storyboard_script_wait` 600 s de polling, como `job_wait`.
- Sem retry automático em nenhum caminho: regenerar é gesto do usuário (o Claude CLI é assinatura
  local, custo zero, mas tempo do usuário não é).
- `persist` (PUT /scenes) é idempotente e sempre manda a cena inteira; falha mostra toast e
  mantém o estado da tela, que continua consistente porque o próximo gesto reenvia tudo.
- Debounce de 400 ms na digitação dos campos de prompt, alinhado ao `DEBOUNCE_GUIA_MS` do
  `guide-sync.ts`.

**Política de fallback**

- Prompt por foto (imagem e vídeo): Claude → template determinístico, com `source` explícito na
  resposta e no chip de origem.
- Roteiro: sem fallback (ADR-025), 409.
- Galeria: sem `state_changed` (F03 ainda não integrada), a atualização acontece no `done` dos
  jobs da própria tela e no `refresh()` já existente.

**Invariantes**

1. O servidor nunca escreve `scenes.json` a partir de `script.json` (ADR-025).
2. `primary` é sempre item de `images` ou `null` (ADR-018).
3. `images` só aponta para arquivos existentes sob `storyboard/ideas/` (`_check_image`).
4. Desanexar uma foto de todas as cenas **não** a desmarca nem a remove de `storyboard/ideas/`.
   Desmarcar é gesto exclusivo de `POST /candidates/select`, que já desanexa e apaga.
5. `photos` só contém chaves que estão em `images` (poda de `save_scenes`, mantida).
6. Três estados de preset preservados: chave ausente ≠ `null` ≠ id, em memória, no corpo HTTP e no
   arquivo.
7. Sem preset resolvido, o texto enviado ao CLI fica byte-idêntico ao de antes da extensão de
   presets (invariante do gate W3 da provedora).
8. Nenhuma tool MCP escreve em `scenes.json` sem `ui_confirm`/`ui_choose_images` ou `confirm=true`.
9. `script.json` continua sendo o único lugar dos `shot_prompts` do roteiro; a cena guarda apenas
   o prompt que o usuário aceitou.
10. `scripts/qa/cenarios/storyboard.py` só recebe casos NOVOS; os existentes continuam passando sem
    edição (ver seção 8, contrato de DOM).

---

### 7. Observabilidade

**Métricas** (contagem por linha de log estruturado, o padrão da etapa)

- `cli_probe`: quantas re-checagens de PATH aconteceram e quantas viraram `available: true`.
- `image_prompt`: total por `source` (`claude` × `template`) e por `preset`.
- `scenes_saved`: já existe; ganha `with_image_prompt` e `with_photo_preset`.
- `scene_attach`: fotos anexadas por gesto (`picker`, `drop`, `keyboard`, `mcp`).
- `preset_campaign`: quantas ações foram gravadas em um clique do seletor da campanha.

**Logs**

Formato atual `log.info("<evento> %s", {campos})` em `studio.storyboard`:

- `log.info("cli_probe %s", {"name": "claude", "available": bool, "path": str|None, "refresh": bool})`
- `log.info("image_prompt %s", {"pid", "scene", "photo", "source", "preset", "seconds"})`
- `log.info("scenes_saved %s", {"pid", "scenes", "with_image", "with_image_prompt", "with_photo_preset"})`
  (extensão do log existente em `service.py:625`)
- `log.warning("image_prompt claude falhou, usando template: %s", e)`
- Nunca logar o texto do prompt inteiro: apenas o tamanho em caracteres. `searched_path` é logado
  porque é diagnóstico do ambiente local (ferramenta local, loopback, sem multiusuário, ADR-001).

**Tracing**

Não há tracing distribuído no produto (monólito single-process, ADR-001). O rastro é o par
`progressJob` na tela mais as linhas de log acima; para o roteiro, o `log` do job já viaja para a
UI dentro de `GET /script/job`.

**Dashboards e alertas**

Não se aplica (ferramenta local). O painel mínimo é a própria tela: chip de estado do CLI no painel
02, chip de origem por campo de prompt e o bloco "Padrão visual da campanha" mostrando a origem da
resolução (`project`/`global`/`code`).

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Python | 3.12 | Stack do repositório |
| FastAPI + Pydantic v2 | atual do `requirements.txt` | `field_validator` já usado em `VideoPromptReq` |
| Claude Code CLI (`claude`) | qualquer com `-p` e `--output-format text` | Opcional: sem ele, roteiro dá 409 e prompt por foto cai no template |
| `studio/common/prompter.py` | atual | Ganha `ROLES["keyframe"]`, `keyframe()` e `cli_status()` |
| `studio/common/settings.py` | atual | **Não é editado**; só recebe chaves por `setdefault` |
| `studio/creditos/router.py` | atual | Consumido, não alterado (exceto item opcional C5, que é frontend) |
| React 18 + TanStack Query + Vitest | atual do `frontend/` | Sem dependência nova de npm |
| `frontend/src/api/schema.ts` | gerado | `make frontend-schema` obrigatório (rotas novas) |
| `studio/web/dist/` | gerado | `make frontend-build` obrigatório, commitado |

**Garantias de compatibilidade**

- **Contrato de DOM com o oráculo de QA.** `scripts/qa/cenarios/storyboard.py` não pode ser
  editado e depende de: `.sb-pick` clicável (C-STORYBOARD-22/23), `#sbGallery .card` dentro do
  modal, `.modal-actions button.primary` sendo a ação de aplicar, `.modal-actions button` com
  texto "Sem imagem", `.sbVidPrompt` sendo o BOTÃO "Gerar com IA" do prompt de vídeo,
  `.sbVidPromptBox` visível e `.sbVidPromptText.text_content()` devolvendo o prompt salvo
  (C-STORYBOARD-27 e C-STORYBOARD-33), e `.sbVidPrompt` com descrição vazia ainda abrindo o modal
  de progresso e falhando com a mensagem da API (C-STORYBOARD-28). Consequências vinculantes para
  a implementação:
  - o botão novo mantém a classe `sb-pick` (`<button class="thumb pick sb-pick sbAddPhoto">`),
    ganhando texto no DOM e `aria-label`;
  - a ação primária do `PickerModal` continua sendo a de aplicar/adicionar, e "Sem imagem"
    continua existindo com esse texto;
  - o campo editável de prompt de vídeo é um `textarea.sbVidPromptField` NOVO, e o
    `<p class="txt sbVidPromptText">` **permanece** dentro de `.sbVidPromptBox` como espelho de
    leitura com o atributo `hidden` (invisível ao usuário, legível por `text_content()`). Isso
    preserva os dois oráculos ao mesmo tempo: o cenário de QA e o dump de `textContent` do
    baseline vigente;
  - `genVideoPrompt` continua POSTando mesmo com descrição vazia (o 422 do servidor é o que o
    cenário 28 verifica); a confirmação "Substituir?" acontece **depois** da resposta e só sobre
    texto de origem `manual`.
- **Vitest existente** (`studio/etapas/storyboard/ui/storyboard.test.tsx`) pode ser ajustado: ele
  não é oráculo congelado. As asserções de ordem dos painéis, `.sbVidPromptText` e `.sbRealismPreset`
  continuam válidas; a de `.sbRealismPreset` ganha a opção nova "(padrão da campanha: X)".
- **Retrocompatibilidade de arquivo**: `scenes.json` sem `image_prompt`/`preset`/`origin` carrega
  igual; `script.json` não muda de schema.
- **Retrocompatibilidade de API**: nenhum campo existente muda; todo acréscimo é opcional. Testes
  com asserção de conjunto fechado sobre o `status` da etapa e sobre `defaults` de
  `GET /api/prompter/presets` já foram afrouxados na Wave 9 (`storyboard-roteiro-llm-fdd` §13.4) e
  seguem tolerantes.
- **Fronteira com F07**: F06 acrescenta apenas em blocos próprios de
  `studio/etapas/storyboard/router.py` (bloco de ideação e bloco `script`) e de
  `studio/storyboard/service.py` (blocos de cenas, de roteiro e o novo bloco de prompt por foto).
  Não toca `Angles.tsx`, `angles.py` nem `local.py`.

---

### 9. Critérios de aceite técnicos

**A. Roteiro visível**

- A1. Com `claude` fora do PATH do processo, `GET …/storyboard/script/cli` responde 200 com
  `available: false`, `path: null` e `searched_path` igual ao `PATH` do processo; o botão
  `#sbScriptGen` está no DOM, **habilitado**, e o bloco `#sbScriptCliDiag` mostra o PATH.
- A2. Com o binário disponibilizado depois de o servidor subir, `?refresh=true` devolve
  `available: true` e um `POST /script/generate` subsequente inicia o job, **sem reiniciar o
  processo** (teste com `monkeypatch` de `clibin.which`).
- A3. `GET /api/projects/{pid}/storyboard` traz `script_cli_diag` com as mesmas seis chaves e
  `script_cli` continua booleano.
- A4. `run.sh` executado com `env -i PATH=/usr/bin:/bin sh ./run.sh` produz um processo cujo
  `PATH` contém `$HOME/.local/bin` (verificação por inspeção do script, sem subir servidor no CI).
- A5. O botão principal exibe o texto "Gerar cenas (roteiro por Claude) [extensão]" e o painel 02
  precede o painel 03 no DOM (vitest de ordem mantido e estendido para o rótulo novo).
- A6. `storyboard_script` + `storyboard_script_wait` levam um roteiro de 5 cenas do início ao fim
  com o `claude` fingido, e `storyboard_apply_script` só escreve depois de confirmação.

**B. Fotos nas cenas**

- B1. O painel 01 mostra `#sbIdeasGallery` com um card por ideia, cada um com badge de origem
  legível; o filtro por origem reduz a grade e o `PickerModal`.
- B2. Existe um `button` com o texto "Adicionar foto à cena" no DOM (não apenas em CSS) e com
  `aria-label`; ele mantém a classe `sb-pick` (compatibilidade C-STORYBOARD-22).
- B3. Anexar duas fotos a uma cena que já tem uma resulta em três imagens, na ordem, sem duplicar,
  e `scenes.json` no disco já reflete isso **sem** clicar em "Salvar cenas".
- B4. Remover uma foto e trocar a ★ também persistem imediatamente; após reload, o estado é o
  mesmo (cenário novo de QA com `page.reload()`).
- B5. "Substituir tudo" pede confirmação e só então troca a galeria da cena.
- B6. Arrastar um card da galeria para uma cena anexa; arrastar um `.sb-key` para outra cena move
  (some da origem, aparece no destino) e as classes `.dragging`/`.dragover` são aplicadas durante o
  gesto.
- B7. O `select.sbPhotoMove` move a foto entre cenas apenas com teclado, com o mesmo efeito do
  arrasto.
- B8. A mensagem de vazio do picker cita o motor local do painel 01b.
- B9. Uma foto retirada de todas as cenas continua `selected: true` em
  `GET …/storyboard/candidates` e o arquivo continua em `storyboard/ideas/`.
- B10. `storyboard_scene_attach` anexa duas fotos escolhidas e devolve a contagem e a próxima ação;
  sem ideias escolhidas devolve a orientação de `storyboard_pick`/`storyboard_local_generate`.
- B11. Vitest cobre picker, galeria, anexo, remoção e ★.

**C. Preset global**

- C1. O seletor "Padrão visual da campanha" grava, em um clique, os cinco `kind`
  (`storyboard.script`, `storyboard.keyframe`, `storyboard.angles`, `motion`, `base`) via
  `PUT /api/projects/{pid}/prompter/preset-config`, e `GET /api/prompter/presets?pid=` passa a
  devolver `source: "project"` para todos eles.
- C2. Com o padrão configurado e nenhum override na foto, o corpo enviado a `/video-prompt`
  **não contém** a chave `preset` e a resposta traz o preset da campanha (hoje traz `null`).
- C3. Escolher "(sem preset)" na foto envia `preset: null` e a resposta traz `preset: null`.
- C4. `photos[img].preset` sobrevive a um round-trip `PUT /scenes` → `GET /scenes` nos três
  estados (chave ausente, `null`, id).
- C5. `settings.PRESET_ACTIONS` contém `storyboard.angles` e `storyboard.keyframe` com default
  `None`, e um segundo `setdefault` da mesma chave não altera o valor já registrado.
- C6. `GET /api/prompter/presets` lista as chaves novas em `defaults` sem quebrar nenhum teste
  existente.
- C7 (opcional). O painel Créditos › Modelos default mostra uma coluna "preset" por ação e permite
  gravar o default global pela rota existente.

**D. Campos abertos**

- D1. `POST …/storyboard/image-prompt` devolve `{prompt, negative, source, seconds, preset}`;
  com o `claude` fingido, `source: "claude"`; sem CLI, `source: "template"` e prompt não vazio.
- D2. `image_prompt` e `video_prompt` editados à mão sobrevivem a `PUT /scenes` → reload, com
  `origin.<campo>.source == "manual"`.
- D3. Gerar com IA sobre um campo de origem `manual` pede confirmação; recusar mantém o texto do
  usuário intacto.
- D4. O chip de origem mostra `ia` (com o preset), `manual` ou `template` conforme o caso.
- D5. "Aplicar às cenas vazias" com "trazer também os prompts de imagem" preenche o `image_prompt`
  da k-ésima foto de cada cena a partir de `shot_prompts[k]`, sem tocar em cenas com texto.
- D6. "usar este" em um `shot_prompt` grava o texto na foto correspondente.
- D7. "Gerar animação" com `video_prompt` escrito à mão (nunca gerado) inicia o fluxo de custo sem
  bloquear; com o campo vazio, avisa.
- D8. "Usar no motor local" preenche `#sbLocalPrompt` com o `image_prompt` da foto.
- D9. `storyboard_keyframe_prompt` e `storyboard_keyframe_set` escrevem em `scenes.json` pelo
  `PUT /scenes` e marcam a origem correta.
- D10. `PUT /scenes` com `image_prompt` de 4001 caracteres devolve 422 citando cena e foto.

**Transversais e `[cross-feature]`**

- T1. `make verify` e `make frontend-verify` verdes; `studio/web/dist/` e
  `frontend/src/api/schema.ts` regenerados e commitados.
- T2. Todos os testes Python novos mockam o binário `claude` (`monkeypatch` de `prompter.BIN`,
  `prompter.available`, `clibin.which` ou `prompter.subprocess.run`); nenhum toca rede.
- T3. Nenhum caso existente de `scripts/qa/cenarios/storyboard.py` foi editado; o cenário novo
  passa.
- T4. `tests/test_adr010_fronteira_nucleo.py` passa com a branch registrada em
  `TITULARES_DO_NUCLEO` e o recorte mínimo declarado.
- C8. `[cross-feature]` (com F07, validado no estado integrado): com o padrão visual da campanha
  configurado por F06, os prompts de ângulos gerados por F07 carregam o `preset_block`
  correspondente, porque `settings.preset_default_for("storyboard.angles", pid)` resolve para o
  preset da campanha.
- C9. `[cross-feature]` (com F04, validado no estado integrado): `storyboard_pick` devolve os ids
  selecionados e a próxima ação no formato `{"selected": [...], "next_step": "..."}`, e
  `storyboard_scene_attach` consome esses ids sem passar por `_images_for`.
- C10. `[cross-feature]` (com F03, opcional): quando `chat-sync` integrar, um `state_changed` de
  escopo `storyboard` recarrega a galeria de ideias sem clique.

---

### 10. Riscos e mitigação

### Risco 1: quebrar os cenários de QA congelados ao transformar leitura em campo

- **Probabilidade:** alta
- **Impacto:** a rodada de QA da wave reprova sem que haja bug real, e os cenários não podem ser
  editados para acomodar.
- **Mitigação:**
  - manter o `<p class="txt sbVidPromptText">` como espelho `hidden` dentro de
    `.sbVidPromptBox`, com o mesmo texto do campo (seção 8);
  - manter a classe `sb-pick` no botão novo e a ação primária do `PickerModal` como a de aplicar;
  - manter `genVideoPrompt` POSTando com descrição vazia;
  - rodar `make qa-up qa-seed qa-run RUN=w11-f06 TELAS=storyboard` antes do PR e anexar o
    relatório.
- **Plano de contingência:** se algum cenário ainda reprovar por texto, reverter só o trecho de DOM
  envolvido e registrar a divergência como pendência para o dono decidir sobre o baseline.

### Risco 2: conflito de rebase com F07 em `router.py` e `service.py`

- **Probabilidade:** média
- **Impacto:** integração da sub-wave 1 atrasa; risco de resolver conflito à mão em arquivo grande.
- **Mitigação:**
  - F06 acrescenta apenas em blocos próprios e no fim de cada bloco (roteiro, cenas, prompt por
    foto), nunca no meio do bloco de ângulos;
  - registro de `storyboard.angles` feito em `service.py` por `setdefault`, e não em `angles.py`,
    para que F07 possa registrar a mesma chave sem colidir;
  - a ordem de integração da wave já coloca F07 antes de F06.
- **Plano de contingência:** rebase com `git-rebase` e regeneração de `dist/`/`schema.ts` em vez de
  resolução manual.

### Risco 3: perda de escrita por payload obsoleto na persistência imediata

- **Probabilidade:** média
- **Impacto:** o usuário anexa, remove e estrela em sequência rápida e uma das operações some,
  porque `persist(scenes, photos)` foi chamado com estado antigo (o `reorderPhoto` atual já faz
  isso dentro de um `setScenes`, lendo `photos` de fora).
- **Mitigação:**
  - centralizar a persistência em uma função que recebe o estado NOVO explicitamente, sempre
    calculado dentro do atualizador funcional;
  - guardar o último payload em uma `ref` e serializar os `PUT` (fila de um), descartando
    respostas fora de ordem;
  - vitest cobrindo a sequência anexar → remover → estrelar com asserção sobre o corpo do último
    `PUT`.
- **Plano de contingência:** manter o botão "Salvar cenas" como rede de segurança (ele continua
  existindo e enviando o estado completo).

### Risco 4: o preset da campanha ficar inconsistente entre as cinco ações

- **Probabilidade:** média
- **Impacto:** o usuário acha que configurou o padrão visual e uma das pontas (ângulos, keyframe)
  continua sem preset, quebrando o critério `[cross-feature]` com F07.
- **Mitigação:**
  - o seletor sempre relê `GET /api/prompter/presets?pid=` depois de gravar e mostra "(misto)"
    quando as ações divergem;
  - falha parcial é reportada por `kind`;
  - teste de API que grava pelo seletor e confere os cinco `kind` com `source: "project"`.
- **Plano de contingência:** botão "nivelar tudo" que regrava o conjunto inteiro.

### Risco 5: papel `keyframe` do prompter divergir do formato do roteiro

- **Probabilidade:** média
- **Impacto:** o prompt de imagem por foto sai com estrutura diferente da dos `shot_prompts`, e as
  fotos de uma mesma cena deixam de ser visualmente coesas.
- **Mitigação:**
  - extrair a ordem de briefing e o `SCRIPT_MODEL_HINTS` para constantes compartilhadas, usadas
    pelos dois papéis;
  - reusar `script_preset_block` para o rig, garantindo corpo/lente/formato idênticos;
  - teste que confere que, com preset, o rig aparece literalmente no prompt devolvido.
- **Plano de contingência:** o campo é editável e o `shot_prompt` do roteiro continua disponível
  pelo botão "usar este".

### Risco 6: a correção de PATH em `run.sh` mascarar um binário errado

- **Probabilidade:** baixa
- **Impacto:** o Studio passa a usar um `claude` diferente do que o usuário espera.
- **Mitigação:**
  - o PATH do usuário é **preservado na frente** e os diretórios conhecidos são acrescentados
    depois dele, nunca antes;
  - o diagnóstico mostra o `path` resolvido, então a escolha fica visível.
- **Plano de contingência:** `STUDIO_CLAUDE_BIN` não entra nesta frente; se for preciso, vira
  pendência para o dono.

### Risco 7: escopo grande demais para uma frente só

- **Probabilidade:** alta
- **Impacto:** a frente atrasa a sub-wave 1 inteira.
- **Mitigação:**
  - a seção 11 quebra em 16 tarefas independentes, com A, B, C e D acopladas apenas por
    `Ideation.tsx` e pelo schema de foto;
  - a ordem coloca o schema (D1) e o helper de CLI (A1a) primeiro, porque tudo depende deles;
  - C5 (Créditos) e A1c (`/api/chat/status`) são explicitamente opcionais e podem sair do PR.
- **Plano de contingência:** entregar A, B e C, deixando D5 a D8 (usar este, motor local,
  animação com prompt manual) para um segundo PR da mesma frente.

---

### 11. Sequenciamento de implementação (Build Order)

Decomposição pensada para o SDD (Compozy): cada linha é uma task independente, com arquivos e
critérios próprios. As dependências são só as declaradas.

| Ordem | Etapa (task) | Depende de | Componentes/arquivos prováveis | Critérios que fecha (seção 9) |
| --- | --- | --- | --- | --- |
| 1 | **D1 schema de foto**: `image_prompt`, `preset` (3 estados), `origin`, `MAX_PHOTO_PROMPT` em `_scene_photos`/`save_scenes`/`_blank_scenes`; validação e poda | - | `studio/storyboard/service.py`, `tests/test_storyboard_service.py`, `tests/test_storyboard_api.py` | C4, D2, D10, invariantes 5 e 6 |
| 2 | **A1a probe do CLI**: módulo `clibin` + `prompter.cli_status`; `status()` ganha `script_cli_diag` | - | `studio/common/clibin.py` (novo), `studio/common/prompter.py`, `studio/storyboard/service.py`, `tests/test_prompter.py`, `tests/test_storyboard_api.py` | A2, A3 |
| 3 | **A1b rota de diagnóstico**: `GET …/storyboard/script/cli?refresh=` | 2 | `studio/etapas/storyboard/router.py`, `tests/test_storyboard_api.py` | A1, A2 |
| 4 | **A1d PATH do run.sh**: prefixo de diretórios de binário preservando o PATH herdado, com comentário explicando a causa | - | `run.sh` (e nota no `Makefile` se necessário) | A4 |
| 5 | **C4 chaves de preset**: `ANGLES_ACTION`/`KEYFRAME_ACTION` por `setdefault` em import time | 1 | `studio/storyboard/service.py`, `tests/test_storyboard_service.py`, `tests/test_creditos_api.py` (leitura) | C5, C6, C8 |
| 6 | **D2 papel `keyframe` + `prompter.keyframe()`**: constantes de briefing compartilhadas com o roteiro, output spec própria, reuso de `_parse` e `script_preset_block` | 5 | `studio/common/prompter.py`, `tests/test_prompter.py` | D1, Risco 5 |
| 7 | **D2b rota `/image-prompt`**: `ImagePromptReq` com `preset_arg()`, serviço `image_prompt(...)` com fallback de template, log estruturado | 1, 6 | `studio/etapas/storyboard/router.py`, `studio/storyboard/service.py`, `tests/test_storyboard_api.py`, `tests/test_storyboard_service.py` | D1, matriz da seção 6 |
| 8 | **C1 seletor da campanha (backend nenhum, frontend)**: bloco `#sbCampaignPreset` no topo da etapa 4, leitura e escrita pelas rotas existentes, estado "(misto)", falha parcial | 5 | `studio/etapas/storyboard/ui/Ideation.tsx`, `studio/etapas/storyboard/ui/types.ts`, vitest novo | C1, C6 |
| 9 | **C2 herança por foto**: `RealismField` com "(padrão da campanha: X)"/"(sem preset)", `PhotoMeta.preset` de 3 estados, `buildPayload`/`seedPhotos` persistindo, `genVideoPrompt` omitindo o campo | 1, 8 | `studio/etapas/storyboard/ui/Ideation.tsx`, `types.ts`, `storyboard.test.tsx` | C2, C3, C4 |
| 10 | **B1 galeria + filtro**: `#sbIdeasGallery` no painel 01, badge de origem, `local_kind` no `_idea_row`, filtro compartilhado com o picker, refresh no `done` dos jobs | - | `studio/storyboard/service.py`, `studio/etapas/storyboard/ui/Ideation.tsx`, `tests/test_storyboard_service.py`, vitest novo | B1, B8 |
| 11 | **B2 botão real e persistência imediata**: `button.sb-pick.sbAddPhoto` com texto e `aria-label`; `attachImages` somando; `persist` em anexo, remoção, ★ e reordenação; fila de um `PUT` | 1, 10 | `studio/etapas/storyboard/ui/Ideation.tsx`, vitest novo | B2, B3, B4, B5, B11 |
| 12 | **B3 drag-and-drop e teclado**: `dragstart`/`dragover`/`drop` na galeria, no `.sb-phototable` e no `.sb-key`; `select.sbPhotoMove`; classes `.dragging`/`.dragover` | 11 | `studio/etapas/storyboard/ui/Ideation.tsx` (inclui o bloco `STYLE`), vitest novo | B6, B7 |
| 13 | **D3 campos abertos na UI**: `textarea.sbImgPromptField` e `textarea.sbVidPromptField` (com o espelho `hidden` `.sbVidPromptText`), botões "Gerar com IA", chip de origem, "Substituir?", debounce, "Gerar animação" com prompt manual, "Usar no motor local" | 7, 9, 11 | `studio/etapas/storyboard/ui/Ideation.tsx`, `types.ts`, `storyboard.test.tsx`, vitest novo | D2, D3, D4, D7, D8 |
| 14 | **A2 + D4 roteiro na tela**: rótulo "Gerar cenas (roteiro por Claude) [extensão]", botão sempre habilitado, bloco de diagnóstico com "Verificar de novo", `applyScript(all, withPrompts)`, botão "usar este" por `shot_prompt` | 3, 13 | `studio/etapas/storyboard/ui/Ideation.tsx`, `storyboard.test.tsx` | A1, A5, D5, D6 |
| 15 | **A3 + B8 + D7 tools MCP**: `storyboard_script`, `storyboard_script_wait`, `storyboard_apply_script`, `storyboard_scene_attach`, `storyboard_keyframe_prompt`, `storyboard_keyframe_set`, registradas ao final do bloco de storyboard | 1, 7 | `studio/mcp/actions.py`, `studio/mcp/server.py`, `tests/test_mcp_actions.py`, `studio/chat/prompts/sistema.md` (opcional) | A6, B10, D9, C9 |
| 16 | **Fechamento**: cenário novo de QA (só acréscimo), `make frontend-schema`, `make frontend-build`, `TITULARES_DO_NUCLEO`, ADR-042, coleção Postman | 1 a 15 | `scripts/qa/cenarios/storyboard.py`, `frontend/src/api/schema.ts`, `studio/web/dist/`, `tests/test_adr010_fronteira_nucleo.py`, `docs/adrs/generated/STUDIO/ADR-042-*.md`, `docs/domains/storyboard/postman/` | B4, T1, T3, T4 |
| 17 | **C5 (OPCIONAL, último)**: coluna de preset por ação no painel Créditos › Modelos default | 5 | `frontend/src/areas/creditos/CreditosArea.tsx`, `frontend/src/areas/creditos/CreditosArea.test.tsx` | C7 |
| 18 | **A1c (OPCIONAL)**: `GET /api/chat/status` devolvendo o mesmo diagnóstico | 2 | `studio/chat/runtime.py`, `studio/chat/router.py`, `tests/test_chat_api.py` | A3 (unificação) |

**Titularidade de núcleo a declarar** (`tests/test_adr010_fronteira_nucleo.py`,
`TITULARES_DO_NUCLEO`, entrada nova no topo do dict):

- branch: `feature/adh-os-20260906-08-storyboard-cenas`
- prefixos: `("frontend/", "studio/web/")`
- motivo: rota nova (`/storyboard/script/cli`, `/storyboard/image-prompt`) obriga a regenerar
  `frontend/src/api/schema.ts`; mudanças na UI da etapa 4 (fora do núcleo) obrigam a regenerar o
  bundle versionado `studio/web/dist/`; o item opcional C5 toca
  `frontend/src/areas/creditos/CreditosArea.tsx`. Nenhum arquivo de `frontend/src/shell/`,
  `studio/app.py`, `steps.py`, `config.py`, `higgsfield.py` ou `etapas/__init__.py` é tocado.

**Contagens finais**

Contratos (seção 5): 18
Fluxos principais (seção 4): 4
Arquivos previstos: 29

Lista dos 29 arquivos: `studio/common/clibin.py`, `studio/common/prompter.py`,
`studio/storyboard/service.py`, `studio/etapas/storyboard/router.py`, `studio/mcp/actions.py`,
`studio/mcp/server.py`, `studio/chat/prompts/sistema.md`, `studio/chat/runtime.py`,
`studio/chat/router.py`, `run.sh`, `studio/etapas/storyboard/ui/Ideation.tsx`,
`studio/etapas/storyboard/ui/types.ts`, `studio/etapas/storyboard/ui/storyboard.test.tsx`,
`studio/etapas/storyboard/ui/ideation-fotos.test.tsx`,
`studio/etapas/storyboard/ui/ideation-prompts.test.tsx`,
`studio/etapas/storyboard/ui/ideation-preset.test.tsx`, `studio/etapas/base/ui/index.tsx`,
`frontend/src/areas/creditos/CreditosArea.tsx`, `frontend/src/areas/creditos/CreditosArea.test.tsx`,
`frontend/src/api/schema.ts` (gerado), `studio/web/dist/` (gerado),
`tests/test_prompter.py`, `tests/test_storyboard_api.py`, `tests/test_storyboard_service.py`,
`tests/test_mcp_actions.py`, `tests/test_adr010_fronteira_nucleo.py`,
`scripts/qa/cenarios/storyboard.py`, `docs/adrs/generated/STUDIO/ADR-042-*.md`,
`docs/domains/storyboard/postman/storyboard.postman_collection.json`.

**Decisão direta × SDD:** 18 contratos, 4 fluxos e 29 arquivos. O limiar de implementação direta
(≤3 contratos E 1 fluxo E ≤8 arquivos) é ultrapassado nos três eixos. **Esta frente vai por
SDD/Compozy**, com as 18 tasks da tabela acima como base da decomposição.

---

### 12. Decisões auto-aceitas e pendências

**Decisões auto-aceitas** (todas com o rótulo `[auto-aceito]` no ponto em que aparecem no
documento; repetidas aqui para auditoria da retro)

1. `[auto-aceito: o painel 02 JÁ precede o 03 no DOM (`Ideation.tsx:1062` antes de `:1201`) e há
   vitest guardando isso (`storyboard.test.tsx:98-112`), conforme ADR-028 §4; a parte A2 do card
   vira confirmação por teste, não mudança de layout]`
2. `[auto-aceito: a rota de diagnóstico do CLI nasce no namespace da etapa
   (`/api/projects/{pid}/storyboard/script/cli`) porque etapa é plugin e o roteiro é o consumidor;
   a alternativa (rota global em `studio/creditos/router.py`) invadiria arquivo de outras frentes]`
3. `[auto-aceito: `/image-prompt` NÃO devolve 409 sem CLI; cai no template determinístico por
   simetria com `/video-prompt` (`service.py:938-942`). O 409 do ADR-025 é do ROTEIRO, que escreve
   arquivo; prompt por foto não escreve nada por conta própria]`
4. `[auto-aceito: a ação de preset do prompt de imagem é uma chave NOVA `storyboard.keyframe`
   (default `None`), em vez de reusar `base` (que é a imagem base da etapa 3) ou
   `storyboard.script` (que é o roteiro); o seletor da campanha grava as cinco chaves de uma vez]`
5. `[auto-aceito: o seletor da campanha grava também `storyboard.angles`, além das três do card,
   porque o critério `[cross-feature]` da wave com F07 exige que o preset da campanha chegue aos
   prompts de ângulos]`
6. `[auto-aceito: as chaves novas de `PRESET_ACTIONS` são registradas por `setdefault` em
   `studio/storyboard/service.py`, e não em `studio/common/settings.py` (conflito com F05) nem em
   `studio/storyboard/angles.py` (arquivo de F07)]`
7. `[auto-aceito: desanexar uma foto de todas as cenas NÃO a desmarca nem a remove de
   `storyboard/ideas/`; desmarcar continua sendo gesto exclusivo de `POST /candidates/select`,
   que já desanexa e apaga (`service.py:441-465`). A política inversa apagaria arquivo que outra
   cena ou o roteiro (`_selected_idea_paths`) ainda usa]`
8. `[auto-aceito: o `<p class="txt sbVidPromptText">` permanece no DOM como espelho `hidden` do
   campo editável, porque `scripts/qa/cenarios/storyboard.py` não pode ser editado e lê esse
   elemento por `text_content()` (C-STORYBOARD-27 e C-STORYBOARD-33)]`
9. `[auto-aceito: "persistir o preset usado por geração" é implementado como
   `photos[img].origin.<campo>.preset`, o mesmo lugar do indicador de origem ia/manual/template;
   evita uma segunda estrutura para o mesmo fato]`
10. `[auto-aceito: `storyboard_pick` NÃO é alterado por esta frente; o retorno estruturado com ids
    e próxima ação é entrega de F04 (mcp-pick-shape), e F06 apenas o consome e valida no estado
    integrado. `storyboard_scene_attach` monta a própria lista de imagens para não depender do
    `_images_for` em conserto]`
11. `[auto-aceito: `run.sh` acrescenta os diretórios conhecidos DEPOIS do PATH herdado, nunca
    antes, para não trocar silenciosamente o binário que o usuário já tem]`
12. `[auto-aceito: o teto de `image_prompt`/`video_prompt` por foto é 4000 caracteres, valor novo
    `MAX_PHOTO_PROMPT`; não havia teto para `video_prompt` e um prompt de briefing completo fica
    bem abaixo disso]`
13. `[auto-aceito: `applyScript` com prompts preenche a k-ésima foto JÁ anexada; prompts sobrando
    não criam foto nenhuma (o servidor nunca inventa conteúdo, §6 do FDD do roteiro) e ficam
    disponíveis pelo botão "usar este"]`
14. `[auto-aceito: a confirmação "Substituir?" dispara só sobre texto de origem `manual` e só
    DEPOIS de a geração voltar, para não quebrar C-STORYBOARD-27/28, que geram prompt sem
    interação extra]`
15. `[auto-aceito: `GET /api/chat/status` ganha o diagnóstico como item OPCIONAL no fim da build
    order (A1c), porque `studio/chat/router.py` é território de F02/F03/F09 nesta wave; a
    unificação real acontece pelo helper compartilhado `studio/common/clibin.py`]`
16. `[auto-aceito: `local_kind` é exposto em `_idea_row` só para o badge distinguir motor local de
    inpaint local; nenhum consumidor existente lê o objeto por chaves fechadas]`

**Pendências para o gate em lote**

1. **ADR-042 proposta (schema de foto e papel novo do prompter).** A mudança em `scenes.json` é
   aditiva, e ADR-018/022/025 já autorizam acréscimos. Ainda assim a frente propõe uma ADR, porque
   três decisões novas passam a valer para além dela: (a) a foto do storyboard passa a carregar
   **conteúdo autoral do usuário** (prompt de imagem), e não só metadado de vídeo; (b) o preset por
   foto vira contrato persistido de TRÊS estados; (c) as tools MCP podem aplicar o roteiro às
   cenas depois de `ui_confirm`, o que precisa ficar explicitamente compatível com a ADR-025
   ("o servidor nunca escreve"). Esqueleto:

   ```markdown
   # ADR-042: campos abertos de prompt por foto no storyboard e papel `keyframe` do prompter

   **Status:** proposta
   **Data:** 2026-09-06
   **Task-Id:** ADH-OS-20260906-08
   **ADRs relacionados:** ADR-004, ADR-018, ADR-022, ADR-025, ADR-028, ADR-035, ADR-037, ADR-038

   ## Contexto e Problema
   A cena do storyboard já guarda, por foto, a descrição e o prompt de vídeo (ADR-022). O prompt
   de IMAGEM só existe em `script.json` (ADR-025/028) e é copiado à mão. O preset de realismo
   escolhido por foto nunca é persistido e o cliente anula o default da ação ao mandar `null`.

   ## Decisão
   1. `scenes.json` ganha, por foto e de forma ADITIVA: `image_prompt`, `preset` com três estados
      (chave ausente herda, `null` desliga, id usa) e `origin` com a fonte (`ia`/`manual`/
      `template`), o preset usado e o horário, por campo.
   2. O prompter ganha o papel `[extensão]` `keyframe` e a função `keyframe()`, que reusa a ordem
      de briefing e o bloco de rig do roteiro para UMA foto, exposto por
      `POST /api/projects/{pid}/storyboard/image-prompt`. Sem o Claude CLI, o endpoint cai em
      template determinístico (o 409 da ADR-025 continua valendo só para o ROTEIRO).
   3. O servidor continua **nunca** escrevendo `scenes.json` a partir do roteiro. As tools MCP
      podem aplicar o roteiro e anexar fotos, sempre depois de `ui_confirm`/`ui_choose_images`
      (ADR-038) ou de `confirm=true` explícito no terminal.
   4. Desanexar uma foto de todas as cenas não a desmarca nem a remove de `storyboard/ideas/`.

   ## Consequências
   Positivas: o prompt de imagem passa a ser editável e reaproveitável pela geração local e pela
   por cena (F07); o default visual da campanha finalmente chega às gerações. Negativas: o schema
   por foto cresce e passa a exigir poda e validação próprias; a distinção "chave ausente ≠ null"
   precisa ser preservada em quatro camadas (UI, corpo HTTP, serviço, arquivo).
   ```

2. **Baseline de `textContent` da Wave 10.** Renomear o botão para "Gerar cenas (roteiro por
   Claude) [extensão]" e acrescentar textos novos (galeria, botão de foto, campos, chips de
   origem) produz diff contra `docs/qa/reports/2026-09-03-react-e0-v2/textcontent/`. A regra de
   diff vazio nasceu como oráculo da MIGRAÇÃO React (Wave 10, convenção 4 do CLAUDE.md), não como
   proibição de evoluir a tela; ainda assim a decisão de regerar o baseline é do dono da wave.
   **Pendência:** confirmar se o baseline é regerado no fechamento da Wave 11 ou se o rename fica
   para depois.

3. **`storyboard_pick` e `_images_for`.** O shape real de `GET …/storyboard/candidates` é
   `{"ideas": [...]}` (dict), e o `thumb` já vem prefixado com `storyboard/candidates/`. O
   `_images_for` atual itera lista e prefixa de novo, então `storyboard_pick` está quebrado do
   mesmo jeito que `base_pick`. F04 declarou cobrir `{candidates, final}`; o shape `{"ideas": …}`
   precisa entrar no escopo dela. **Pendência:** confirmar com F04 na integração; F06 não toca o
   arquivo.

4. **`studio/chat/` como núcleo.** O recon §0.6 registra que `studio/chat/` e `studio/mcp/` não
   estão em `NUCLEO_PREFIXOS` e que a wave precisa decidir. F06 escreve em `studio/mcp/` (tools) e,
   no item opcional A1c, em `studio/chat/`. **Pendência:** decisão da wave; se virar núcleo, a
   entrada de `TITULARES_DO_NUCLEO` desta frente ganha os dois prefixos.

5. **Custo do `/image-prompt` no livro-caixa.** O Claude CLI é assinatura local e não gera crédito
   Higgsfield (ADR-025), então nada é gravado no ledger. Se o dono quiser medir o uso do CLI, isso
   é uma ação nova no catálogo de F05, fora desta frente. **Pendência:** apenas registro.

6. **Diagramas do domínio.** O storyboard não tem HLD (recon §0.2) e os dois diagramas sugeridos na
   seção 4 ficam para o fechamento (`dd-parallel-doc-sync`), não bloqueiam a implementação.
