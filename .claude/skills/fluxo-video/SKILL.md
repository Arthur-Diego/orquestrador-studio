---
name: fluxo-video
description: >
  [extensão] Orquestra, de ponta a ponta e com gates humanos, um fluxo LOCAL e independente de
  criação de vídeo: roteiro → cenas → planos (JSON congruente) → imagens → vídeo. Usa os
  subagents `roteirista-cenas-planos` e `revisor-continuidade` para o julgamento e o CLI
  `python -m fluxo_video` (validar/imagens/video/tudo) para a geração. É autossuficiente: gera as
  imagens pelo `local_ai_engine` (ComfyUI local, no lugar) e monta o vídeo com ffmpeg — NÃO
  depende de ContentFlow nem de nenhum serviço externo. Use quando o usuário quiser criar um vídeo
  a partir de uma ideia/tese, ou digitar /fluxo-video. Não use para descobrir a vibe (é
  `mood_orquestrador`) nem para uma etapa isolada do curso (é o núcleo do studio).
---

Você conduz um fluxo de produção de vídeo **local e autossuficiente**. É uma **extensão**
independente do método do curso — não confunda com as etapas do `studio/`. O código vive em
`fluxo_video/` (raiz do orquestrador-studio).

## Pré-requisitos (confira e avise se faltar)
- **ComfyUI no ar** em `http://127.0.0.1:8188` (o `local_ai_engine` gera a imagem por ele).
- **`local_ai_engine` acessível**: o binário `engine` (default `~/local_ai_engine/.venv/bin/engine`,
  ou aponte `FLUXO_ENGINE_BIN`). Teste: `<bin> doctor`.
- **ffmpeg** no PATH.

## Fluxo (um gate humano entre cada etapa — nunca pule a aprovação)

1. **Roteiro** — invoque o subagent `roteirista-cenas-planos` com a ideia/tese, a identidade
   visual (estilo, paleta, personagem, âncora) e a duração alvo. Ele grava `roteiro.json` e se
   autovalida. Saída: caminho do JSON.

2. **Validar (gate determinístico)** — `python -m fluxo_video validar roteiro.json`.
   Se sair erro, devolva ao subagent para corrigir. Não avance com incongruência.

3. **Revisar coerência (gate de julgamento)** — invoque `revisor-continuidade` no `roteiro.json`.
   Só siga com `PRONTO PARA PRODUÇÃO` ou aprovação explícita do usuário.

4. **Imagens (gate visual)** — `python -m fluxo_video imagens roteiro.json`.
   Gera a imagem de cada plano (a 1ª vira âncora de identidade → personagem consistente entre
   planos). As imagens ficam em `projects/<slug>/fontes/`. Mostre-as; regenere planos ruins
   (ajustando o `image_prompt` e rodando de novo) antes de montar.

5. **Vídeo** — `python -m fluxo_video video roteiro.json` (ou `tudo` para imagens+vídeo de uma vez).
   Cada imagem vira um clipe com movimento (Ken Burns) na duração do plano; concatena no
   `projects/<slug>/final.mp4`. Este é o baseline local grátis; i2v real é o próximo ponto de
   extensão (trocar o `render` do plano por um provider de i2v via ComfyUI), sem mudar o fluxo.

## Regras
- **Congruência é inegociável**: `imagens`/`video`/`tudo` já rodam o `validar` como gate — um
  roteiro incongruente nem começa a gerar.
- **Gates são do humano**: apresente o resultado de cada etapa e espere o ok antes da próxima.
- **Independência**: nada aqui fala com o ContentFlow/making-money. A única dependência externa é o
  `local_ai_engine` (no lugar) + ComfyUI + ffmpeg.
- Antes de qualquer commit/PR desta extensão: skill `ft-pr`, trailer `Task-Id: ADH-OS-*`, base `develop`.
