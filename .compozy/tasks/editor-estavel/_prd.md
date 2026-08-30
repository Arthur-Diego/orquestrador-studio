# PRD — Studio de vídeo: editor estável (etapa 7, rodada 3) `[extensão]`

Task-Id: `ADH-OS-20260829-38` · Card: <https://trello.com/c/uDU7Hyfh> · Wave 8, frente **A · editor-estavel**
TechSpec normativa: `_techspec.md` (FDD aprovado em lote, gate W3 do dd-parallel).
Fonte de produto: `.claude/plans/2026-08-29-studio-de-video-estavel.md`, itens **1 a 8** (o item 9 é das frentes B e C).

## 1. Problema

A etapa 7 (editor de vídeo `[extensão]` da aula 014) entregou a arquitetura (store + undo/redo,
playback, timeline de 6 faixas, painéis), mas o caminho de renderização é destrutivo: cada ação de
edição refaz o `innerHTML` do editor inteiro. Na prática o usuário perde o layout a cada clique
(timeline volta a 262 px e corta MÚSICA/SFX, larguras de painel e scroll se perdem, thumbnails
recarregam), além de quatro defeitos funcionais e duas lacunas relatadas em uso real.

## 2. Usuário e valor

Usuário: o próprio dono do projeto montando o vídeo da campanha na etapa 7, local, single-user.
Valor: o editor deixa de "pular" a cada ação e passa a permitir a montagem completa sem recarregar
a etapa — que é o que o CapCut da aula 014 entrega, com as camadas extras já aprovadas na ADR-030.

## 3. Requisitos de produto (itens 1 a 8 do plano)

1. **Render incremental** — nenhuma ação de edição pode recriar o editor. Layout (altura da
   timeline, larguras dos painéis, `scrollLeft`) idêntico antes e depois de qualquer ação.
2. **Timeline sempre completa** — as 6 faixas cabem por padrão; MÚSICA e SFX nunca ficam cortadas;
   a altura escolhida pelo usuário sobrevive ao F5.
3. **Exclusão total** — dá para excluir a música e todos os clipes; a guarda de "precisa de clipe"
   passa a valer só na exportação.
4. **MP4 na VÍDEO 2 toca no preview** — overlay de vídeo aparece com tamanho visível, toca em Play
   e segue o playhead.
5. **Escolha e movimento V1 ↔ V2 explícitos** — ao adicionar um vídeo o usuário escolhe a faixa;
   pelo menu de contexto e pelas Propriedades ele move (não copia) entre VÍDEO 1 e VÍDEO 2.
6. **Efeitos em qualquer camada** — os 14 efeitos e os 10 ajustes se aplicam também a texto,
   legenda e overlay no preview, e sobrevivem ao salvamento.
7. **Esconder o menu lateral** — botão no header do editor, preferência lembrada.
8. **Renomear a etapa 7 para "Studio de vídeo"** — catálogo, META do plugin, rótulos da UI e README.

## 4. Fora de escopo

- Efeitos em texto/legenda/overlay e MP4 na VÍDEO 2 **no `master.mp4`**: continuam preview-only e
  rotulados na UI (ADR-030 — nunca simular).
- Legendas (geração, karaokê, burn-in por palavra): item 9 do plano, frentes B e C.
- Transições no encode, áudio extra no mix, freeze frame: fase seguinte, já registradas.
- Qualquer edição de `render.py`, `burnin.py`, `router.py`, `ui.js`, `ui.css`, `style.css`,
  `app.py`, `index.html`, `app.js`.

## 5. Critérios de aceite

Os critérios normativos, numerados de 1 a 22, estão na **seção 9 do `_techspec.md`** (backend em
pytest, frontend em smoke Playwright, e os `[cross-feature]` cobrados na integração da wave).
Fecha também: `make verify` (ruff + pytest) verde.

## 6. Restrições

- Python 3.12 / FastAPI + SPA vanilla sem build (ADR-008): o front não tem teste unitário; o que é
  verificável por string vive em `tests/test_edit_api.py`.
- Nenhuma rota HTTP nova; `PUT /timeline` evolui de forma aditiva e retrocompatível.
- Strings de contrato de UI fixadas por `tests/test_edit_api.py:316-350` não podem mudar
  (lista completa na seção 8 do `_techspec.md`).
- Regra de arquivos da Wave 8 para esta frente: `studio/etapas/edit/view.js`, `view.html`,
  `studio/etapas/edit/__init__.py`, `studio/steps.py`, `README.md`, `studio/edit/editor.py`
  (só `normalize_item` no ramo text/caption + o bloco `ui`), e os testes correspondentes.
  O nome `normalize_caption_extra` é **reservado para a frente B** — não criar.
