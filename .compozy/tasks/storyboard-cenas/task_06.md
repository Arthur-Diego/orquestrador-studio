---
status: completed
title: Frontend — campos abertos de prompt por foto e roteiro visível na tela
type: frontend
complexity: critical
---

# Task 6: Frontend — campos abertos de prompt por foto e roteiro visível na tela

## Overview

Fecha o card #99 na tela e a leitura A do card #95: o prompt de vídeo deixa de ser texto de
leitura e vira campo editável, nasce o campo "Prompt de imagem (keyframe)" por foto, ambos com
gerador de IA opcional, chip de origem e persistência com debounce; e o botão do roteiro passa a
estar **sempre habilitado**, com bloco de diagnóstico e "Verificar de novo". É a task 13 e 14 da
Build Order (§11) e a última da cadeia de frontend.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **CONTRATO DE DOM CONGELADO (restrição dura).** `scripts/qa/cenarios/storyboard.py` NÃO pode ser
  editado. Consequências vinculantes desta task, de `_techspec.md` §8 e §12 auto-aceito 8:
  - o campo editável de prompt de vídeo é um `textarea.sbVidPromptField` **NOVO**, e o
    `<p class="txt sbVidPromptText">` **PERMANECE** dentro de `.sbVidPromptBox` como **espelho de
    leitura com o atributo `hidden`** — invisível ao usuário, legível por `text_content()`
    (C-STORYBOARD-27 e C-STORYBOARD-33). Use `el.hidden`, e mantenha o texto do espelho sempre
    igual ao do campo;
  - `.sbVidPrompt` MUST continuar sendo o **BOTÃO** "Gerar com IA" do prompt de vídeo, e
    `.sbVidPromptBox` MUST continuar visível;
  - `genVideoPrompt` MUST continuar **POSTando mesmo com descrição vazia** — o 422 do servidor é
    o que o cenário C-STORYBOARD-28 verifica; a confirmação "Substituir?" acontece **DEPOIS** da
    resposta.
- Cada `PhotoRow` MUST mostrar, além do `video_desc` já existente, dois campos:
  `textarea.sbImgPromptField` ("Prompt de imagem (keyframe)") e `textarea.sbVidPromptField`
  ("Prompt de vídeo"), cada um com botão "Gerar com IA" (`button.sbImgPrompt` e o já existente
  `button.sbVidPrompt`), botão "Copiar" e um chip de origem `.sbPromptOrigin`.
- "Gerar com IA" do prompt de imagem MUST chamar `POST .../storyboard/image-prompt` com
  `scene_id`, `photo`, `description` (o `video_desc` da foto vale como contexto quando a instrução
  está vazia) e o `preset` conforme a herança da task_04.
- A confirmação "Substituir o texto que você escreveu?" MUST disparar **só** sobre texto de origem
  `manual` e **só DEPOIS** de a geração voltar. Recusar MUST manter o texto e oferecer "Copiar" da
  sugestão. Texto de origem `ia`/`template` MUST ser sobrescrito sem perguntar (é regeneração).
- Toda escrita nos campos MUST chamar `persist` com **debounce de 400 ms** para digitação e
  **imediatamente** para o resultado da IA, gravando também
  `origin.<campo> = {source, preset, at}`.
- O chip de origem MUST mostrar `ia` (com o preset), `manual` ou `template`.
- O botão `#sbScriptGen` MUST ter o rótulo **"Gerar cenas (roteiro por Claude) [extensão]"** e MUST
  estar **sempre no DOM e sempre habilitado**.
- Quando `script_cli_diag.available` é falso, o bloco `#sbScriptCliDiag` com `role="status"` e
  `aria-live="polite"` MUST mostrar "Claude CLI não encontrado. PATH do processo:
  `<searched_path>`" mais a `hint`.
- Clique no botão com `available` falso MUST chamar `GET .../storyboard/script/cli?refresh=true`
  (uma requisição, sem job). Se voltar `true`, o fluxo segue para o job **na mesma interação**; se
  voltar falso, a tela atualiza o diagnóstico e **NÃO** dispara `POST /script/generate` (evita 409
  inútil), mantendo o foco no bloco de diagnóstico.
- O botão `#sbScriptCliRecheck` ("Verificar de novo") MUST chamar a mesma rota com `refresh=true` a
  qualquer momento.
- O painel 02 (roteiro) MUST continuar **antes** do painel 03 no DOM — isso já é verdade; a
  entrega aqui é a blindagem por teste, não mudança de layout (§12 auto-aceito 1).
- `applyScript(all, withPrompts)` MUST ganhar a caixa "trazer também os prompts de imagem": com
  ela marcada, a cena `i` recebe `text` como hoje e, para cada foto `k` **já anexada** à cena,
  recebe `photos[img].image_prompt = script.scenes[i].shot_prompts[k]` quando existir, com
  `origin.image_prompt = {source: "ia", preset: <preset do script>}`. Prompts sobrando **NÃO
  criam foto nenhuma** e continuam visíveis no painel 02 com o botão "usar este".
- "usar este" MUST gravar o texto no `image_prompt` da foto `k` da cena correspondente; sem foto
  `k`, a tela avisa quantas fotos a cena tem.
- "Gerar animação" MUST usar o valor do **campo** `video_prompt` (estado da tela), não o valor
  salvo, e só bloquear quando o campo está vazio.
- "Usar no motor local" MUST copiar o `image_prompt` da foto para `#sbLocalPrompt` do painel 01b e
  mover o foco para lá. A geração por cena com saída em `cenaNN/` **continua sendo de F07** — não
  implementar.
- `studio/etapas/storyboard/ui/Angles.tsx` MUST permanecer **intocado**.
</requirements>

## Subtasks

- [x] 6.1 Transformar o prompt de vídeo em `textarea.sbVidPromptField`, mantendo
      `<p class="txt sbVidPromptText" hidden>` como espelho sincronizado dentro de
      `.sbVidPromptBox`.
- [x] 6.2 Acrescentar `textarea.sbImgPromptField` com "Gerar com IA", "Copiar" e chip de origem.
- [x] 6.3 Ligar `button.sbImgPrompt` a `POST .../storyboard/image-prompt`.
- [x] 6.4 Implementar a confirmação "Substituir?" pós-resposta, só sobre origem `manual`.
- [x] 6.5 Implementar o `persist` com debounce de 400 ms na digitação e imediato no resultado da
      IA, gravando `origin.<campo>`.
- [x] 6.6 Renomear o botão do roteiro e torná-lo sempre habilitado.
- [x] 6.7 Criar o bloco `#sbScriptCliDiag` (`role="status"`, `aria-live="polite"`) e o botão
      `#sbScriptCliRecheck`.
- [x] 6.8 Implementar o clique com `available` falso: `refresh=true` e, se virar verdadeiro,
      seguir para o job na mesma interação.
- [x] 6.9 Acrescentar a caixa "trazer também os prompts de imagem" a `applyScript`.
- [x] 6.10 Acrescentar o botão "usar este" por `shot_prompt` no painel 02.
- [x] 6.11 Fazer "Gerar animação" usar o campo e "Usar no motor local" preencher `#sbLocalPrompt`.
- [x] 6.12 Escrever `studio/etapas/storyboard/ui/ideation-prompts.test.tsx` e estender
      `storyboard.test.tsx` com o rótulo novo e a ordem dos painéis.

## Implementation Details

Arquivos a modificar: `studio/etapas/storyboard/ui/Ideation.tsx`,
`studio/etapas/storyboard/ui/types.ts`, `studio/etapas/storyboard/ui/storyboard.test.tsx`;
criar `studio/etapas/storyboard/ui/ideation-prompts.test.tsx`.

Fluxos completos em `_techspec.md` §4 (fluxo principal 1 e fluxo principal 4). Contrato de DOM em
§8. O espelho `hidden` é a mitigação do Risco 1 (§10) e não é negociável.

`make frontend-build` e o commit de `studio/web/dist/` ficam para a task_07.

Pontos exatos do código (levantados nesta worktree):

- `studio/etapas/storyboard/ui/Ideation.tsx`: `SCRIPT_NO_CLI` :32 · `SCRIPT_TARGET` :34 ·
  **`genVideoPrompt` :515-543** (grava `prompt` e `preset` no `PhotoState` e chama `persist` :539)
  · `runScript` :594-617 · **`applyScript(all)` :619-656** (copia **só** `text` em :643; a
  confirmação de "Substituir tudo" está em :633-638) · painel 02 :1062-1204, com
  `#sbScriptPreset`/`RealismField` :1081, `#sbScriptGen` :1127-1129 (**`disabled={!scriptCli}`** —
  é o que sai), `#sbScriptMeta` :1141-1145, "Aplicar às cenas vazias" :1146 e "Substituir tudo"
  :1149, a lista de cenas do roteiro :1156-1202 com os `shot_prompts` **só de leitura** :1193 e os
  botões Copiar :1178-1188, mais o aviso de "encaixe manual" :1167-1169 · painel 03 :1206-1305 ·
  `#sbLocalPrompt` :999-1008 · `AutoTextarea` :1495-1531 · `PhotoRow` :1582-1671 (`.sbVidDesc`
  :1608-1614, `.sbVidPrompt` botão "Gerar prompt" :1651, `↑`/`↓` :1660-1667) ·
  `AnimateModal` :1851-1970 (bloqueio por prompt vazio :1410-1411 no chamador, valor salvo
  enviado :1427).
- **`.sbVidPromptBox` :1616-1633** — o bloco exato a transformar:
  `<div className={"prompt sm sbVidPromptBox" + (has ? "" : " hidden")}>` com `const has =
  !!p.meta.prompt;` em :1583, o botão `.sbVidCopy` e, na última linha,
  `<p className="txt sbVidPromptText">{p.meta.prompt}</p>`. **O `<p>` fica, com `hidden`**, e o
  `textarea.sbVidPromptField` nasce ao lado. **Atenção**: a `.sbVidPromptBox` hoje ganha a classe
  `hidden` quando não há prompt, mas o C-STORYBOARD-27 verifica
  `linha.locator(".sbVidPromptBox").is_visible()` **depois** de gerar — a caixa tem de ficar
  visível com o campo, e o `<p>` espelho é que carrega o atributo `hidden`. Um bloco **idêntico**
  está duplicado no `AnimateModal` :1894-1911 e precisa do mesmo tratamento.
- `studio/etapas/storyboard/ui/types.ts`: `ScriptScene` :78-83 (`arc?, text?, image_prompt?,
  shot_prompts?: string[]`) · `Script` :84-90 (`scenes?, generated_at?, preset?, aspect_ratio?,
  notes_pt?`) · `PhotoEntry` :48-52 (**ganha `image_prompt?` e `origin?`**) · `SbStatus` :28-38
  (**ganha `script_cli_diag?`**).
- Oráculo de QA (**somente leitura**): C-STORYBOARD-27 `scripts/qa/cenarios/storyboard.py`
  :642-668 — preenche `.sbVidDesc`, clica `.sbVidPrompt`, e no fim exige
  `linha.locator(".sbVidPromptText").text_content()` **não vazio**,
  `.sbVidPromptBox.is_visible()` verdadeiro e o valor **igual** ao `video_prompt` gravado em
  disco. C-STORYBOARD-28 :671-688 — `.sbVidDesc` **vazio**, clica `.sbVidPrompt`, espera
  `.prog-err` com a palavra "descrição": **o POST tem de acontecer**. C-STORYBOARD-33 :793-808 —
  após `page.reload()`, `.sbVidDesc` com valor e `.sbVidPromptText` igual ao prompt salvo.
- `studio/common/prompter.py` (**somente leitura aqui**): `SHOTS_MIN = 3` :488 e `SHOTS_MAX = 6`
  :489 delimitam quantos `shot_prompts` uma cena do roteiro pode ter — o "usar este" e o
  `applyScript(withPrompts)` trabalham sobre essa lista.

### Relevant Files

- `studio/etapas/storyboard/ui/Ideation.tsx` — `PhotoRow`, `AnimateModal`, `genVideoPrompt`,
  `applyScript`, `runScript`, `#sbScriptGen`, `#sbScriptPreset`, `#sbScriptMeta`, `#sbLocalPrompt`,
  o painel 02 com os `shot_prompts` copiáveis, o bloco `STYLE`.
- `studio/etapas/storyboard/ui/types.ts` — `PhotoEntry`, `ScriptScene.shot_prompts`, `PhotoMeta`.
- `scripts/qa/cenarios/storyboard.py` — **somente leitura, NUNCA editar**: C-STORYBOARD-27/28/33
  definem o contrato que o espelho `hidden` preserva.
- `studio/etapas/storyboard/ui/storyboard.test.tsx` — asserções de ordem dos painéis, de
  `.sbVidPromptText` e de "Gerar prompt" → `/video-prompt`. **Pode** ser ajustado (não é oráculo
  congelado), mas o comportamento que ele afirma tem de continuar valendo.
- `frontend/src/ui/` — `useAutosize`, `CopyButton`, `useProgress`/`progressJob`.

### Dependent Files

- `studio/web/dist/` — rebuildado na task_07.
- `scripts/qa/cenarios/storyboard.py` — a task_07 **acrescenta** o cenário novo.
- `docs/qa/reports/2026-09-03-react-e0-v2/textcontent/` — o rename do botão e os textos novos
  produzem diff contra esse baseline. **Decisão já tomada pelo gate da wave**: o baseline é
  artefato compartilhado e será **regerado na integração (W5)**. Não regerar aqui, não editar.

### Related ADRs

- ADR-025 — sem CLI, o roteiro continua 409; o fallback por template vale só para prompt por foto.
- ADR-028 — os `shot_prompts` continuam morando só em `script.json`; a cena guarda apenas o prompt
  que o usuário aceitou (invariante 9).
- ADR-022 — o bloco de vídeo por foto é preservado.
- ADR-042 (a criar na task_07) — item 1 da Decisão (`image_prompt` e `origin` por foto).

## Deliverables

- Campos editáveis de prompt de imagem e de vídeo por foto, com IA opcional, chip de origem e
  persistência com debounce.
- Espelho `hidden` de `.sbVidPromptText` preservando os oráculos de QA.
- Botão do roteiro renomeado, sempre habilitado, com diagnóstico e "Verificar de novo".
- `applyScript` com prompts de imagem e botão "usar este" por `shot_prompt`.
- "Gerar animação" pelo campo e "Usar no motor local".
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Não há `_tests.md` — casos completos abaixo. Vitest com jsdom, sem rede.

- [x] `.sbVidPromptBox` contém **os dois**: o `textarea.sbVidPromptField` visível e o
      `<p class="txt sbVidPromptText">` com `hidden`, e o `textContent` do `<p>` acompanha o valor
      do campo depois de digitar e depois de gerar (C-STORYBOARD-27/33).
- [x] `.sbVidPrompt` continua sendo um `button` (não um campo).
- [x] `genVideoPrompt` com `video_desc` **vazio** ainda faz o POST (C-STORYBOARD-28) e a mensagem
      de erro da API aparece.
- [x] `button.sbImgPrompt` chama `POST .../storyboard/image-prompt` com `scene_id`, `photo` e o
      `description` vindo do `video_desc` quando a instrução está vazia.
- [x] A resposta com `source: "claude"` preenche o campo e o chip de origem mostra `ia` com o
      preset; com `source: "template"`, o chip mostra `template` (critérios D1 e D4).
- [x] Gerar com IA sobre um campo de origem `manual` pede confirmação **depois** da resposta;
      recusar mantém o texto do usuário intacto e oferece "Copiar" (critério D3).
- [x] Gerar com IA sobre um campo de origem `ia` **não** pergunta nada.
- [x] Digitar no campo dispara **um** `PUT /scenes` após o debounce de 400 ms (timers falsos), não
      um por tecla; o corpo traz `origin.<campo>.source == "manual"` (critério D2).
- [x] O resultado da IA persiste **imediatamente**, sem esperar o debounce.
- [x] O botão `#sbScriptGen` está no DOM, **habilitado**, com o texto "Gerar cenas (roteiro por
      Claude) [extensão]" mesmo com `script_cli: false` (critérios A1 e A5).
- [x] Com `script_cli_diag.available: false`, `#sbScriptCliDiag` existe com `role="status"`,
      `aria-live="polite"` e mostra o `searched_path` e a `hint` (critério A1).
- [x] Clicar no botão com `available: false` chama `.../script/cli?refresh=true` e, quando a
      resposta volta `false`, **não** dispara `POST /script/generate`.
- [x] Clicar no botão com `available: false` e a re-checagem voltando `true` segue para o
      `POST /script/generate` **na mesma interação** (critério A2 no cliente).
- [x] `#sbScriptCliRecheck` chama a rota com `refresh=true` e atualiza o bloco.
- [x] O painel 02 precede o painel 03 no DOM (asserção mantida e estendida, critério A5).
- [x] "Aplicar às cenas vazias" com "trazer também os prompts de imagem" preenche o `image_prompt`
      da k-ésima foto de cada cena a partir de `shot_prompts[k]`, **sem tocar** em cenas com texto,
      e marca `origin.image_prompt.source == "ia"` (critério D5).
- [x] `shot_prompts` sobrando **não** criam foto nenhuma e continuam listados no painel 02.
- [x] "usar este" grava o texto no `image_prompt` da foto correspondente (critério D6); numa cena
      sem a foto `k`, a tela avisa quantas fotos a cena tem.
- [x] "Gerar animação" com `video_prompt` **escrito à mão e nunca gerado** inicia o fluxo de custo
      sem bloquear; com o campo vazio, avisa (critério D7).
- [x] "Usar no motor local" preenche `#sbLocalPrompt` com o `image_prompt` da foto e move o foco
      (critério D8).

## Success Criteria

- Every assigned test case implemented and passing.
- `make frontend-verify` verde.
- `git diff --name-only` **não** contém `scripts/qa/cenarios/storyboard.py`,
  `docs/qa/reports/**` nem `studio/etapas/storyboard/ui/Angles.tsx`.
- `.sbVidPromptText` continua existindo dentro de `.sbVidPromptBox` (grep no arquivo).
- Nenhuma rota nova; `frontend/src/api/schema.ts` não muda nesta task.
