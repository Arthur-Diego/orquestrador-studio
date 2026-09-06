---
status: completed
title: Frontend — galeria de ideias, botão real, persistência imediata e drag-and-drop
type: frontend
complexity: critical
---

# Task 5: Frontend — galeria de ideias, botão real, persistência imediata e drag-and-drop

## Overview

Fecha o card #97, o defeito mais visível da frente: hoje a galeria de ideias só existe dentro do
modal, o único ponto de entrada de uma foto na cena é um tile sem texto no DOM, anexar
**substitui** a galeria da cena em vez de somar, e nenhum gesto de foto persiste sem clicar em
"Salvar cenas". Esta task põe a galeria na tela, dá um botão de verdade, faz `attachImages` somar,
persiste todo gesto na hora e implementa arrastar-e-soltar com alternativa por teclado. É a task
10 (frontend), 11 e 12 da Build Order (§11).

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- **CONTRATO DE DOM CONGELADO (restrição dura).** `scripts/qa/cenarios/storyboard.py` NÃO pode ser
  editado. Consequências vinculantes, de `_techspec.md` §8:
  - o botão novo MUST manter a classe `sb-pick`
    (`<button class="thumb pick sb-pick sbAddPhoto">`), ganhando **texto no DOM** e `aria-label`
    (C-STORYBOARD-22/23);
  - a **ação primária** do `PickerModal` (`.modal-actions button.primary`) MUST continuar sendo a
    de aplicar/adicionar;
  - o botão com o texto **"Sem imagem"** MUST continuar existindo em `.modal-actions`;
  - `#sbGallery .card` MUST continuar existindo dentro do modal.
- O painel 01 MUST renderizar `#sbIdeasGallery` a partir de `GET .../storyboard/candidates`, com
  `data-id`, `data-file`, `data-source` e um **badge legível de origem** por card:
  `cli` = "Higgsfield (CLI)", `local` = "Motor local (grátis)", `local_kind: "inpaint"` =
  "Inpaint local", `upload` = "Enviada", `downloads` = "Downloads", `history` = "Histórico HF";
  mais a marca "escolhida" quando `selected`.
- O filtro por origem `#sbIdeasFilter` MUST se aplicar **à galeria do painel 01 e ao
  `PickerModal`**.
- `attachImages(i, ids, mode)` MUST, com `mode="add"` (**default**), montar
  `images: dedup([...atual, ...novas])` preservando a ordem e mantendo a `primary` atual; com
  `mode="replace"`, substituir. "Substituir tudo" MUST ser ação **explícita e confirmada**
  (`window.confirm`), fantasma no modal.
- Anexar, remover (`.sb-rm`), estrelar (`.sb-star`), reordenar (`↑`/`↓`) e todo `drop` MUST chamar
  `persist` (`PUT /scenes`) **na mesma interação** — nenhum gesto pode exigir "Salvar cenas".
- **Risco 3 (perda de escrita por payload obsoleto)** — mitigação obrigatória: a persistência MUST
  ser centralizada numa função que recebe o estado **NOVO** explicitamente, sempre calculado
  **dentro** do atualizador funcional; o último payload MUST ficar numa `ref` e os `PUT` MUST ser
  serializados (fila de um), descartando respostas fora de ordem. O `reorderPhoto` atual, que lê
  `photos` de fora do `setScenes`, é exatamente o antipadrão a eliminar.
- O botão "Salvar cenas" (`#sbSave`) MUST continuar existindo, como rede de segurança.
- Arrastar: o card da galeria e o `.sb-key` MUST ser `draggable`. `dragstart` grava
  `application/x-studio-idea` (id da ideia) ou `application/x-studio-photo` (`{"sid","img"}`);
  `.sb-phototable` e `.sb-key` aplicam `.dragover` no `dragover`. Ideia solta em uma cena vira
  anexo (`mode="add"`); foto solta em **outra** cena **move** (some da origem, aparece no destino);
  foto solta sobre outra `.sb-key` da mesma cena reordena. As classes `.dragging`/`.dragover`
  (que já existem no CSS e nunca são aplicadas) MUST passar a ser aplicadas durante o gesto.
- Drop de arquivo do sistema operacional MUST ser **ignorado**: só os dois MIME internos são
  aceitos.
- Alternativa por teclado: cada linha de foto MUST ter `select.sbPhotoMove` ("Mover para…")
  listando as demais cenas, com o mesmo efeito do arrasto entre cenas.
- **Política de desanexo (invariante 4, §12 auto-aceito 7)**: quando uma foto deixa de estar em
  qualquer cena, ela **continua** `selected` e **continua** em `storyboard/ideas/`. Desmarcar é
  gesto exclusivo da galeria (`POST /candidates/select`). Não implementar limpeza automática.
- A mensagem de vazio do `PickerModal` MUST citar o motor local do painel 01b.
- A galeria MUST se atualizar no `done` dos jobs da própria tela (a fronteira `state_changed` de
  F03 é **opcional e mockada**: não implementar dependência dela).
- Drop de uma ideia ainda não `selected` MUST rodar `POST /candidates/select` **antes** do anexo;
  se ele falhar, nada é anexado e a tela mostra o erro.
- `studio/etapas/storyboard/ui/Angles.tsx` MUST permanecer **intocado**.
</requirements>

## Subtasks

- [x] 5.1 Renderizar `#sbIdeasGallery` no painel 01 com badge de origem e os `data-*`.
- [x] 5.2 Implementar `#sbIdeasFilter` compartilhado entre a galeria e o `PickerModal`.
- [x] 5.3 Trocar o tile mudo por `button.thumb.pick.sb-pick.sbAddPhoto` com texto no DOM e
      `aria-label="Adicionar foto à cena N"`.
- [x] 5.4 Reescrever `attachImages` para somar (dedup, ordem preservada) e acrescentar
      "Substituir tudo" confirmado.
- [x] 5.5 Centralizar a persistência numa função que recebe o estado novo, com `ref` do último
      payload e fila de um `PUT`.
- [x] 5.6 Ligar `persist` a anexo, remoção, ★ e reordenação.
- [x] 5.7 Implementar `dragstart`/`dragover`/`drop` na galeria, no `.sb-phototable` e no `.sb-key`,
      com os dois MIME internos e as classes `.dragging`/`.dragover`.
- [x] 5.8 Implementar `select.sbPhotoMove` como alternativa por teclado.
- [x] 5.9 Atualizar a mensagem de vazio do picker citando o motor local.
- [x] 5.10 Refrescar a galeria no `done` dos jobs da própria tela.
- [x] 5.11 Escrever `studio/etapas/storyboard/ui/ideation-fotos.test.tsx` com os casos abaixo.

## Implementation Details

Arquivos a modificar: `studio/etapas/storyboard/ui/Ideation.tsx` (inclui o bloco `STYLE`);
criar `studio/etapas/storyboard/ui/ideation-fotos.test.tsx`.

Fluxo completo em `_techspec.md` §4 (fluxo principal 2, passos 1 a 8), contrato de DOM em §8,
mitigação do Risco 3 em §10.

`make frontend-build` e o commit de `studio/web/dist/` ficam para a task_07.

Pontos exatos do código (levantados nesta worktree):

- `studio/etapas/storyboard/ui/Ideation.tsx` (2162 linhas): `pkey` :42 · `seedPhotos` :98-113 ·
  `buildPayload` :116-134 · `putScenes` :369-372 · `saveScenesAndReseed` :374-384 ·
  **`persist` :386-391** (`(sc, ph) => void putScenes(buildPayload(sc, ph)).catch(() => {})` —
  recebe o estado por parâmetro, mas os chamadores passam estado **de fora** do atualizador) ·
  `refresh` :424 · `pm` :433 · `updatePhoto` :436 · **`setPrimary` :459-462** (não persiste) ·
  **`removeImage` :463-470** (não persiste) · **`reorderPhoto` :471-486** (persiste, mas lê
  `photos` de fora do `setScenes` — o antipadrão do Risco 3) ·
  **`attachImages` :488-512** (`POST /candidates/select` com a união :492-493, depois
  `images: files` **substituindo** a galeria :500-505, **sem** `persist`) ·
  `saveScenesBtn` :561 · painel 01 …–1060 · painel 03 :1206-1305 (`#sbScenes` :1227,
  `.scene-row` :1232, `PhotoRow` :1263-1285) · **o tile mudo `.thumb.pick.sb-pick` :1287-1299**
  (é um `<div role="button">` sem texto; vira `<button class="thumb pick sb-pick sbAddPhoto">`
  com texto) · `ImportIdeasModal` :1674-1715 · **`PickerModal` :1769-1832** (grade `#sbGallery`
  :1810, mensagem de vazio :1827 que não cita o motor local) · `ReorderModal` :1972-2052
  (tem `onDragStart/End` de CENAS — o padrão a espelhar para fotos) ·
  **`STYLE` :2070-2162**, com `.sb-pick` :2082-2085 (inclui o `::after{content:"+ foto"}` de 9 px
  que precisa sair, já que o texto passa a existir no DOM) e as classes
  `.sb-photorow.dragging` / `.sb-key.dagover` já definidas e nunca aplicadas.
- `studio/etapas/storyboard/ui/types.ts`: `Idea` :40-46 (`id, file, thumb?, prompt?, selected?`) —
  **ganha `source` e `local_kind` vindos da task_02**; `Scene` :54-61; `PhotoEntry` :48-52.
- `studio/storyboard/service.py` (**somente leitura**): `select_ideas` :424-465 já desanexa das
  cenas e apaga de `ideas/` ao **desmarcar** — por isso a política de desanexo desta task é não
  fazer nada; `_check_image` :571-579 rejeita caminho fora de `storyboard/ideas/`.
- Oráculo de QA (**somente leitura**): C-STORYBOARD-22 `scripts/qa/cenarios/storyboard.py`
  :536-567 (clica `.sb-pick`, lê `#sbGallery .card`, clica `.modal-actions button.primary`) ·
  C-STORYBOARD-23 :570-584 (`.modal-actions button` com texto "Sem imagem") ·
  C-STORYBOARD-24 :587-603 (`.sb-star`, `.sb-rm`, `.sb-key.primary`, `data-img`).
  **Atenção ao C-STORYBOARD-22**: ele clica no card, clica em "Aplicar" e só DEPOIS clica em
  `#sbSave` esperando o toast "cenas salvas" — a persistência imediata **não pode** quebrar esse
  fluxo, e `#sbSave` tem de continuar emitindo o mesmo toast.

### Relevant Files

- `studio/etapas/storyboard/ui/Ideation.tsx` — `attachImages`, `persist`, `buildPayload`,
  `removeImage`, `setPrimary`, `reorderPhoto`, `PickerModal`, `ImportIdeasModal`, `PhotoRow`,
  `#sbCounts`, o bloco `STYLE` (onde `.dragging`/`.dragover` já existem e o `::after` "+ foto" do
  tile mudo precisa sair).
- `scripts/qa/cenarios/storyboard.py` — **somente leitura, NUNCA editar**: C-STORYBOARD-22/23/24
  definem o contrato de DOM que esta task tem de preservar.
- `studio/storyboard/service.py` — **somente leitura**: `select_ideas` já desanexa das cenas e
  apaga de `ideas/` ao desmarcar; `_check_image` rejeita caminho fora de `storyboard/ideas/`.
- `frontend/src/ui/` — `Modal`, `Tile`, `useProgress`/`progressJob`; os mesmos ids/classes/ARIA do
  design system.

### Dependent Files

- `studio/etapas/storyboard/ui/Ideation.tsx` — a task_06 continua no **mesmo** arquivo.
- `studio/web/dist/` — rebuildado na task_07.
- `scripts/qa/cenarios/storyboard.py` — a task_07 **acrescenta** (nunca edita) o cenário novo de
  persistência com `page.reload()`.

### Related ADRs

- ADR-018 — cena = `images[]` + `primary`; `primary` é sempre item de `images` ou `null`.
- ADR-038 — a escolha visual é do usuário; nada aqui escolhe foto sozinho.
- ADR-042 (a criar na task_07) — item 4 da Decisão (desanexar não desmarca nem apaga).
- ADR-031/032 — o bundle é versionado; nenhuma classe do design system é renomeada.

## Deliverables

- `#sbIdeasGallery` no painel 01 com badge de origem e filtro compartilhado.
- `button.sb-pick.sbAddPhoto` com texto no DOM e `aria-label`.
- `attachImages` somando, com "Substituir tudo" confirmado.
- Persistência imediata de anexo, remoção, ★, reordenação e drop, com fila de um `PUT`.
- Drag-and-drop galeria→cena, cena→cena e reordenação, com alternativa por teclado.
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Não há `_tests.md` — casos completos abaixo. Vitest com jsdom, sem rede.

- [x] O painel 01 mostra `#sbIdeasGallery` com um card por ideia, cada um com badge de origem
      legível; uma ideia `local` com `local_kind: "inpaint"` mostra "Inpaint local" (critério B1).
- [x] O filtro por origem reduz a grade do painel 01 **e** a do `PickerModal` (critério B1).
- [x] Existe um `button` com o texto "Adicionar foto à cena" **no DOM** (não só em CSS), com
      `aria-label`, e ele mantém a classe `sb-pick` (critério B2, C-STORYBOARD-22).
- [x] O `PickerModal` continua tendo `.modal-actions button.primary` como ação de aplicar e um
      botão com o texto "Sem imagem" (C-STORYBOARD-23/24).
- [x] Anexar duas fotos a uma cena que já tem uma resulta em **três** imagens, na ordem, sem
      duplicar, e dispara `PUT /scenes` **sem** clicar em "Salvar cenas" (critério B3).
- [x] Anexar uma foto que já está na cena **não** duplica.
- [x] "Substituir tudo" pede `window.confirm`; recusar mantém a galeria da cena, aceitar troca
      (critério B5).
- [x] Remover uma foto dispara `PUT /scenes` na mesma interação, e o corpo já reflete a remoção
      (critério B4).
- [x] Trocar a ★ dispara `PUT /scenes` e o corpo traz a `primary` nova (critério B4).
- [x] Reordenar por `↑`/`↓` dispara `PUT /scenes` com a ordem nova.
- [x] **Sequência anexar → remover → estrelar em rajada**: o corpo do **último** `PUT` reflete os
      três gestos; nenhum é perdido por payload obsoleto (Risco 3).
- [x] `dragstart` no card da galeria grava `application/x-studio-idea`; soltar em uma cena anexa e
      persiste (critério B6).
- [x] `dragstart` num `.sb-key` grava `application/x-studio-photo`; soltar em **outra** cena remove
      da origem e acrescenta no destino, com um único `PUT` consistente (critério B6).
- [x] Soltar um `.sb-key` sobre outro `.sb-key` da mesma cena reordena.
- [x] As classes `.dragging` e `.dragover` são aplicadas durante o gesto e removidas no fim
      (critério B6).
- [x] Um `drop` com `dataTransfer` de arquivo do sistema operacional (nenhum dos dois MIME
      internos) é **ignorado**: nenhum `PUT` é disparado.
- [x] `select.sbPhotoMove` move a foto entre cenas apenas com teclado, com o mesmo efeito do
      arrasto (critério B7).
- [x] A mensagem de vazio do picker cita o motor local do painel 01b (critério B8).
- [x] Soltar uma ideia ainda não `selected` chama `POST /candidates/select` **antes** do
      `PUT /scenes`; com o `select` falhando, **nenhum** `PUT /scenes` acontece e o erro aparece.
- [x] Remover uma foto de todas as cenas **não** dispara `POST /candidates/select` nem nenhuma
      chamada de desmarcação (critério B9 no cliente).
- [x] O `done` de um job da própria tela dispara o refetch de `GET .../storyboard/candidates`.

## Success Criteria

- Every assigned test case implemented and passing.
- `make frontend-verify` verde.
- `git diff --name-only` **não** contém `scripts/qa/cenarios/storyboard.py` nem
  `studio/etapas/storyboard/ui/Angles.tsx`.
- Nenhuma classe do design system foi renomeada; `sb-pick`, `#sbGallery`, `.modal-actions
  button.primary` e "Sem imagem" continuam presentes.
- Nenhuma rota nova; `frontend/src/api/schema.ts` não muda nesta task.
