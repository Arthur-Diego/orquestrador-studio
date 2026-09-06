---
status: completed
title: Seis tools MCP do storyboard (roteiro, aplicação, anexo e prompt por foto)
type: backend
complexity: medium
---

# Task 3: Seis tools MCP do storyboard (roteiro, aplicação, anexo e prompt por foto)

## Overview

Dá ao agente as mesmas capacidades que a tela ganha nesta frente, sempre atrás de autorização
humana: `storyboard_script` e `storyboard_script_wait` (pedir e acompanhar o roteiro),
`storyboard_apply_script` (aplicar às cenas depois de `ui_confirm`), `storyboard_scene_attach`
(anexar fotos depois de `ui_choose_images`), `storyboard_keyframe_prompt` e
`storyboard_keyframe_set` (gerar e escrever os prompts por foto). É a task 15 da Build Order (§11).
Não toca frontend nenhum, então roda em paralelo com as tasks de UI.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- As seis tools MUST ter exatamente as assinaturas de `_techspec.md` §5.13 a §5.18 e MUST ser
  registradas em `studio/mcp/server.py` **ao final do bloco "ações: 4 Storyboard"**.
- Nenhuma tool pode importar serviço de etapa: todas MUST agir como cliente HTTP da própria API
  (ADR-037), pelo `StudioClient`.
- **`StudioClient` NÃO tem `put` nem `delete` hoje** (`studio/mcp/client.py`: só `get` :65,
  `post` :68, `post_form` :71, `patch` :74). Quatro das seis tools escrevem por
  `PUT .../storyboard/scenes`, então esta task MUST acrescentar `put(path, json=None)` ao
  `StudioClient`, seguindo exatamente o formato de `post` (mesmo `_call`, mesmo tratamento de
  `StudioApiError` e de 204/corpo vazio). Acrescentar `delete` **apenas se** alguma tool precisar
  — nenhuma das seis precisa.
- **Nenhuma tool escreve em `scenes.json` sem autorização humana** (invariante 8, ADR-038):
  `storyboard_apply_script` MUST pedir `ui.confirm(...)` quando há `ui.chat_id()`, e exigir
  `confirm=true` explícito quando não há chat (mesmo padrão de `_paid`);
  `storyboard_scene_attach` MUST usar `ui.choose_images(...)` quando `ids` vem vazio.
- `storyboard_script_wait` MUST fazer polling de `GET .../storyboard/script/job` a cada 2 s (mesmo
  padrão de `tools.job_wait`) até o `state` sair de `running` ou estourar o `timeout`, e então ler
  `GET .../storyboard/script` para resumir.
- `storyboard_scene_attach` MUST filtrar as ideias às **escolhidas** (`selected: true`) e MUST
  montar as imagens do widget com o `thumb` **já relativo à raiz do projeto**
  (`/files/{pid}/{thumb}`), **sem passar por `_images_for`**. `studio/mcp/actions.py::_pick` e
  `_images_for` MUST permanecer **intocados** — o conserto deles é entrega de F04 (§12 auto-aceito
  10). Isso é uma restrição de fronteira, não uma preferência.
- `storyboard_scene_attach` MUST **somar** à galeria da cena (dedup, ordem preservada) e definir a
  `primary` **só** quando a cena não tinha nenhuma.
- `storyboard_keyframe_prompt` MUST aceitar `kind ∈ {"image", "video"}` e chamar a rota
  correspondente; MUST aceitar `image` como caminho relativo completo **ou** só o nome do arquivo,
  resolvido contra as imagens da cena. Se o campo alvo já tem texto de origem `manual`, MUST pedir
  `ui.confirm` antes de sobrescrever — e, sem chat, **não sobrescrever**, devolvendo o texto
  sugerido.
- `storyboard_keyframe_set` MUST aceitar `field ∈ {"image_prompt", "video_prompt", "video_desc"}`
  e marcar `origin.<campo> = {"source": "manual", "preset": null}`.
- Toda tool MUST devolver **texto**, nunca levantar exceção crua: `mode`/`field`/`kind` inválido
  devolve texto de erro **sem escrever nada** (§6).
- Os textos de retorno MUST seguir os exemplos de §5.13–§5.18, inclusive a **próxima ação
  sugerida** ao final de cada um.
- O 409 sem CLI de `POST /script/generate` MUST voltar ao usuário com a mensagem **literal** do
  servidor.
- Nenhum teste pode tocar rede: o `StudioClient` é fingido, e o binário `claude` é sempre mockado.
</requirements>

## Subtasks

- [x] 3.0 Acrescentar `put(path, json=None)` ao `StudioClient` (`studio/mcp/client.py`), espelhando
      `post`; sem ele nenhuma das quatro tools de escrita funciona.
- [x] 3.1 Implementar `storyboard_script(pid, count, arc, preset)` chamando `POST /script/generate`.
- [x] 3.2 Implementar `storyboard_script_wait(pid, timeout)` com o polling de 2 s e o resumo final.
- [x] 3.3 Implementar `storyboard_apply_script(pid, mode, with_prompts, confirm)` montando o
      payload em memória e escrevendo **só** depois de `ui.confirm`/`confirm=true`.
- [x] 3.4 Implementar `storyboard_scene_attach(pid, scene, ids)` com lista de imagens própria
      (sem `_images_for`) e soma à galeria da cena.
- [x] 3.5 Implementar `storyboard_keyframe_prompt(pid, scene, image, kind, description)` com a
      confirmação sobre texto `manual`.
- [x] 3.6 Implementar `storyboard_keyframe_set(pid, scene, image, field, text)`.
- [x] 3.7 Registrar as seis em `studio/mcp/server.py`, no fim do bloco de storyboard, com as
      descrições de §5.13–§5.18.
- [x] 3.8 Anunciar as tools novas em `studio/chat/prompts/sistema.md` (acréscimo mínimo, sem
      reescrever o arquivo).
- [x] 3.9 Escrever os testes inline listados em `## Tests`.

## Implementation Details

Arquivos a modificar: `studio/mcp/actions.py`, `studio/mcp/client.py` (método `put`),
`studio/mcp/server.py`, `studio/chat/prompts/sistema.md`, `tests/test_mcp_actions.py`.

Pontos exatos do código (levantados nesta worktree):

- `studio/mcp/client.py`: `_call` :46-63 (levanta `StudioApiError` em `>=400`, devolve `None` em
  204/corpo vazio), `get` :65, `post` :68, `patch` :74. **Não existe `put`.**
- `studio/mcp/server.py`: bloco "ações: 4 Storyboard" em :103-114, com
  `storyboard_local_generate`, `storyboard_pick` e `storyboard_scenes`. As seis tools novas entram
  **depois da linha 114**, antes do bloco "5–9" (:116).
- `studio/mcp/actions.py`: `_images_for` :20-28 e `_pick` :61-83 — **NÃO EDITAR**. `_paid` :39-58
  é o padrão de autorização a reusar. `storyboard_pick` :194-198, `storyboard_scenes` :201-207.
- `studio/mcp/ui.py`: `chat_id()` :16, `choose_images(client, title, images, minimum=1,
  maximum=None)` :46-50 (imagens no formato `{id, thumb, label}`), `confirm(client, title,
  detail="")` :58-59.
- `studio/mcp/tools.py`: `job_wait(client, pid, step, timeout=600, poll=2.0, _sleep=time.sleep)`
  :140-162 — o `_sleep` injetável é o que torna o polling testável sem dormir de verdade; o
  `storyboard_script_wait` MUST seguir o mesmo padrão (o job do roteiro tem URL própria,
  `GET .../storyboard/script/job`, não `/{step}/job`).
- `studio/etapas/storyboard/router.py`: `PUT .../storyboard/scenes` :246-248 (corpo
  `{"scenes": [...]}`), `GET .../storyboard/scenes` :241, `GET .../storyboard/script` :333,
  `GET .../storyboard/script/job` :327, `GET .../storyboard/candidates` :230.

Contratos exatos, incluindo os textos de retorno, em `_techspec.md` §5.13 a §5.18. O padrão de
autorização humana (`ui.confirm`, `ui.choose_images`, o fallback `confirm=true` sem chat) já existe
em `studio/mcp/actions.py` no helper `_paid` — reusar, não reinventar.

`storyboard_apply_script` implementa o item 3 da Decisão da ADR-042: o **servidor** continua nunca
escrevendo `scenes.json` a partir de `script.json`; quem escreve é um cliente (a tool) agindo por
gesto humano.

### Relevant Files

- `studio/mcp/actions.py` — `_paid` (padrão de autorização), `_pick` e `_images_for`
  (**não editar**), as tools de storyboard já existentes (`storyboard_local_generate`,
  `storyboard_pick`, `storyboard_scenes`).
- `studio/mcp/server.py` — bloco "ações: 4 Storyboard" onde as seis tools são registradas.
- `studio/mcp/tools.py` — `job_wait` é o molde do polling de `storyboard_script_wait`.
- `studio/mcp/uibridge.py` / `studio/chat/uibridge.py` — `ui.confirm`, `ui.choose_images`,
  `ui.chat_id`.
- `tests/test_mcp_actions.py` — convenção de `StudioClient` fingido.

### Dependent Files

- `studio/chat/prompts/sistema.md` — o agente precisa saber que as tools existem.
- `studio/chat/mudancas.py` (`TOOL_STEPS`) e `frontend/src/areas/chat/toolLabels.ts` —
  **não existem** em `develop` @ `0c4e823`; são entregas de F03/F02. **Não criar.** Se aparecerem
  no rebase, a etapa e o rótulo das seis tools entram lá; senão, é item de integração.

### Related ADRs

- ADR-037 — o MCP é cliente HTTP da própria API; nenhuma tool importa serviço de etapa.
- ADR-038 — protocolo humano no laço: escolha visual e escrita passam por `ui.*`.
- ADR-025 — o servidor nunca escreve `scenes.json` a partir do roteiro; a tool escreve por gesto
  humano.
- ADR-040 — o agente não lê nem escreve bytes diretamente.

## Deliverables

- Seis tools implementadas, registradas e documentadas no prompt de sistema.
- `studio/mcp/actions.py::_pick` e `_images_for` **inalterados**.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Não há `_tests.md` — os casos abaixo são as definições completas. Todos com `StudioClient` fingido.

- [x] `storyboard_script` com o servidor devolvendo 202 retorna o texto de sucesso citando o número
      de cenas e o preset, e sugerindo `storyboard_script_wait`.
- [x] `storyboard_script` com o servidor devolvendo 409 sem CLI retorna a mensagem **literal** do
      servidor.
- [x] `storyboard_script_wait` com o job indo de `running` para `done` retorna o resumo do roteiro
      (número de cenas, momentos do arco, faixa de fotos por cena, preset) e sugere
      `storyboard_apply_script`.
- [x] `storyboard_script_wait` com o job em `error` retorna a última linha do log e diz que nada
      foi gravado.
- [x] `storyboard_script_wait` com o job ainda `running` no fim do `timeout` retorna a mensagem de
      timeout pedindo nova chamada.
- [x] `storyboard_apply_script` **sem** `ui.chat_id()` e **sem** `confirm=true` **não** chama
      `PUT /scenes` e devolve texto explicando como confirmar.
- [x] `storyboard_apply_script` com `ui.confirm` recusando **não** chama `PUT /scenes` e devolve
      "Aplicação cancelada pelo usuário. Nada foi escrito em scenes.json."
- [x] `storyboard_apply_script(mode="empty")` com `ui.confirm` aceitando escreve **apenas** nas
      cenas sem texto e devolve a contagem; cenas com texto ficam intactas.
- [x] `storyboard_apply_script(mode="replace")` sobrescreve todas.
- [x] `storyboard_apply_script(mode="lixo")` devolve erro **sem** chamar `PUT /scenes`.
- [x] `storyboard_apply_script(with_prompts=True)` leva `shot_prompts[k]` para o `image_prompt` da
      k-ésima foto **já anexada** da cena, com `origin.image_prompt.source == "ia"`; prompts
      sobrando **não** criam foto nenhuma.
- [x] `storyboard_scene_attach` sem `ids` chama `ui.choose_images` com as imagens montadas a partir
      de `/files/{pid}/{thumb}` — asserção sobre a URL, que **não** pode conter
      `candidates/candidates/` nem passar por `_images_for`.
- [x] `storyboard_scene_attach` anexa duas fotos a uma cena que já tinha uma, resultando em três
      na ordem e sem duplicar, e devolve a contagem e a próxima ação (critério B10).
- [x] `storyboard_scene_attach` define `primary` só quando a cena não tinha nenhuma; com `primary`
      já definida, ela é preservada.
- [x] `storyboard_scene_attach` sem nenhuma ideia `selected` devolve a orientação citando
      `storyboard_pick` e `storyboard_local_generate`, sem chamar `PUT /scenes` (critério B10).
- [x] `storyboard_scene_attach` ignora ideias com `selected: false` mesmo quando o id é passado
      explicitamente.
- [x] `storyboard_keyframe_prompt(kind="image")` chama `POST /image-prompt`, grava por
      `PUT /scenes` e marca `origin.image_prompt` com o `source` e o `preset` da resposta
      (critério D9).
- [x] `storyboard_keyframe_prompt(kind="video")` chama `POST /video-prompt`.
- [x] `storyboard_keyframe_prompt(kind="lixo")` devolve erro sem chamar rota nenhuma.
- [x] `storyboard_keyframe_prompt` sobre campo de origem `manual`, **sem** chat, **não**
      sobrescreve e devolve o texto sugerido.
- [x] `storyboard_keyframe_prompt` aceita `image` como só o nome do arquivo e resolve contra as
      imagens da cena.
- [x] `storyboard_keyframe_set(field="video_prompt")` escreve o texto e marca
      `origin.video_prompt = {"source": "manual", "preset": null}` (critério D9).
- [x] `storyboard_keyframe_set(field="lixo")` devolve erro sem escrever.
- [x] `storyboard_keyframe_set` com texto acima do teto recebe o 422 do servidor e o devolve como
      texto, sem levantar exceção.
- [x] As seis tools aparecem registradas em `studio/mcp/server.py` (teste de registro, como o já
      existente para as tools de storyboard).
- [x] `StudioClient.put` existe, faz `PUT` pelo mesmo `_call` de `post`, levanta `StudioApiError`
      em `>=400` e devolve `None` em 204/corpo vazio.

## Success Criteria

- Every assigned test case implemented and passing.
- `make verify` verde (menos as 2 falhas pré-existentes de `tests/test_edit_captions.py`).
- `git diff` de `studio/mcp/actions.py` **não** toca `_pick` nem `_images_for`.
- Nenhuma tool importa `studio.storyboard.service` (asserção por leitura dos imports).
- Nenhum arquivo de `frontend/` é tocado por esta task.
