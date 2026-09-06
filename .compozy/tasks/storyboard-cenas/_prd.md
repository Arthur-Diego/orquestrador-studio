# PRD: storyboard-cenas (Wave 11 · frente F06 · sub-wave 1)

Task-Id: `ADH-OS-20260906-08` · Branch `feature/adh-os-20260906-08-storyboard-cenas`
Cards: [#95 leitura A](https://trello.com/c/QVr0fPRk) · [#97](https://trello.com/c/YroEvP9I) ·
[#98](https://trello.com/c/ouUqyCNu) · [#99](https://trello.com/c/v4CPkp6p) ·
card da wave <https://trello.com/c/OvSfo3D2>
Domínio: `storyboard` (etapa 4, aula 010) · Base: `develop` @ `0c4e823`

**Spec normativa completa: `_techspec.md`** (o FDD v1.0, aprovado no gate em lote W3 da
Wave 11). **Em qualquer divergência, `_techspec.md` vence.** Este PRD só resume o problema, o
objetivo e o recorte; nenhum detalhe de contrato, schema ou DOM nasce aqui.

---

## Problema

A metade "ideação e cenas" da etapa 4 acumulou quatro defeitos que o dono relatou em 2026-09-06:

1. **O roteiro fica invisível.** O botão `#sbScriptGen` nasce `disabled` quando
   `shutil.which("claude")` falha no processo do backend, e `prompter.BIN` é resolvido em import
   time — nem reabrir a aba resolve, só reiniciar o servidor. O usuário não vê o motivo nem o
   PATH que o processo enxerga. `run.sh` não normaliza o PATH, então subir o Studio fora de um
   shell interativo mata o botão.
2. **Não existe galeria de ideias na tela.** `#sbGallery` só vive dentro do `PickerModal`; o
   único ponto de entrada de uma foto na cena é um tile sem texto no DOM. O anexo **substitui**
   a galeria da cena em vez de somar e **não persiste** — anexar, remover e trocar a ★ ficam só
   no DOM até alguém clicar em "Salvar cenas". Não há drag-and-drop.
3. **O preset de realismo não tem escopo de campanha.** A configuração por ação existe inteira
   no servidor, mas nenhuma UI consome as rotas de escrita; o preset por foto não é persistido e
   `genVideoPrompt` manda `preset: null` **sempre**, o que anula o default da ação `motion`.
4. **Prompt de imagem e de vídeo não são campos.** `video_prompt` é `<p>` de leitura; o prompt
   de imagem por foto não existe no modelo — os `shot_prompts` do roteiro moram só em
   `script.json` e são copiados à mão.

## Objetivo

Fechar os quatro cards mantendo o caminho da aula 010 inteiro (escrever as cenas à mão e encaixar
as fotos), com tudo que se acrescenta ao redor marcado `[extensão]` e opt-in:

- o botão de roteiro está **sempre no DOM e sempre habilitado**, com diagnóstico do CLI e
  re-checagem sem reiniciar o servidor;
- **nenhum gesto de foto exige "Salvar cenas"** e anexar **soma** à galeria da cena;
- o **padrão visual da campanha** é escolhido uma vez e chega às gerações (o corpo omite `preset`
  quando a foto herda);
- prompt de imagem e de vídeo por foto são **texto do usuário**, editáveis, com gerador de IA
  opcional e origem (`ia`/`manual`/`template`) registrada;
- o agente age só pelas seis tools MCP novas.

## Fora de escopo

- Geração de imagem POR CENA (`angles/scenes/{scene}/{cost,generate,upscale}`, saída em
  `storyboard/cenaNN/`): é da frente **F07**. **Não tocar `studio/etapas/storyboard/ui/Angles.tsx`,
  `studio/storyboard/angles.py` nem `studio/storyboard/local.py`.**
- Reintroduzir o combo de fórmulas da aula (`#sbPreset`): proibido por ADR-035.
- Servidor escrever `scenes.json` a partir do roteiro: proibido por ADR-025.
- Fallback determinístico para o ROTEIRO (continua 409 sem CLI).
- `studio/common/settings.py` (é de F05), `pricing`/`ACTIONS`, `CostSheet`/`_paid` (F10).
- `studio/etapas/storyboard/ui/Ideation.tsx` é o arquivo central desta frente; nenhuma outra
  frente da wave mexe nele.

## Restrições duras (violação = defeito)

1. **`scripts/qa/cenarios/storyboard.py` NÃO se edita** — só se acrescentam casos novos. Ele é o
   oráculo congelado. Ver `_techspec.md` §8 ("Contrato de DOM com o oráculo de QA") para a lista
   vinculante: `.sb-pick` mantido no botão novo, ação primária do `PickerModal` continua sendo a
   de aplicar, "Sem imagem" continua com esse texto, `<p class="txt sbVidPromptText">` **permanece**
   dentro de `.sbVidPromptBox` como espelho `hidden` do campo editável, `genVideoPrompt` continua
   POSTando com descrição vazia.
2. **ADR-010:** a branch já precisa estar em `TITULARES_DO_NUCLEO`
   (`tests/test_adr010_fronteira_nucleo.py`) para tocar `frontend/` e `studio/web/`. Não tocar
   `studio/app.py`, `steps.py`, `config.py`, `higgsfield.py`, `etapas/__init__.py` nem
   `frontend/src/shell/`.
3. **Frontend:** mudança em `frontend/` ou em UI de etapa → `make frontend-build` e commit de
   `studio/web/dist/`. Rota ou modelo Pydantic novo/alterado → `make frontend-schema` e commit de
   `frontend/src/api/schema.ts` e `frontend/openapi.json`.
4. **Testes sem rede e sem navegador** (ADR-008): o binário `claude` é SEMPRE mockado
   (`monkeypatch` de `prompter.BIN`, `prompter.available`, `clibin.which` ou
   `prompter.subprocess.run`). Nada de subprocess real, nada de ComfyUI.
5. **Commits:** `<tipo>(storyboard): <descrição em pt-BR> [extensão]`, trailer
   `Task-Id: ADH-OS-20260906-08` na última linha. O hook `commit-msg` rejeita sem Task-Id.
6. **Fronteira com F07/F05:** acréscimos em `studio/etapas/storyboard/router.py` e
   `studio/storyboard/service.py` só em blocos próprios e no fim de cada bloco; as chaves novas
   de `PRESET_ACTIONS` entram por `setdefault` em `service.py`, nunca em `settings.py` nem em
   `angles.py`.

## Critérios de aceite

Os critérios são os da **seção 9 do `_techspec.md`** (A1–A6, B1–B11, C1–C7, D1–D10, T1–T4,
C8–C10). Cada task recebe o subconjunto declarado na tabela da **seção 11 (Build Order)** do
`_techspec.md`, que é a base da decomposição: 18 linhas, com as dependências já declaradas.

Os critérios **C8, C9 e C10** são `[cross-feature]`: só são verificáveis no estado integrado
(com F07, F04 e F03 respectivamente). Nenhuma task deve tentar fechá-los na worktree — apenas
registrar a fronteira.

## Itens explicitamente OPCIONAIS (últimos, podem sair do PR)

- **C5** — coluna de preset por ação no painel Créditos › Modelos default
  (`frontend/src/areas/creditos/CreditosArea.tsx`).
- **A1c** — `GET /api/chat/status` devolvendo o mesmo diagnóstico
  (`studio/chat/runtime.py`, `studio/chat/router.py`) — território de F02/F03/F09 nesta wave.
