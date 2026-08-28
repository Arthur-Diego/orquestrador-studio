### FDD: cena-multi-keyframe — várias imagens por cena no painel 02 (galeria + principal) [extensão]

**Wave:** 5 · **Frente B** · **Branch:** `feature/adh-os-20260828-15-cena-multi-keyframe`
**Recon:** `docs/domains/studio/recon-wave-5.md` · **Ponto 3 do feedback.**

> **Gate de fidelidade (CLAUDE.md):** a aula 010 monta ~5 cenas com **1 keyframe cada**; os
> vários ângulos vêm no painel 03 (aula 011). Aceitar N keyframes por cena é **desvio** →
> marcado `[extensão]` no código/docs **e registrado em ADR-018** (relacionado a ADR-004
> fidelidade e ADR-015 fusão). Aprovado explicitamente pelo dono do produto nesta wave.
> Design escolhido para não colidir com o painel 03: **galeria de keyframes por cena com 1
> marcado como principal** — a principal é a única que semeia a base dos ângulos e é o hero do
> `storyboard.md`; as demais são alternativas.

### 0. Estado atual (verificado)

`scenes.json` = `{scenes:[{id,n,text,image}]}` (`image` singular). `studio/storyboard/service.py`:
`_blank_scenes`, `_normalize`, `_read_scenes`, `_write_scenes`, `save_scenes`, `_check_image`
(aponta para `storyboard/ideas/`), `_write_md`, `select()` (detach). Front `makeIdeation`
(`studio/etapas/storyboard/view.js`): `renderScenes` (1 `.thumb.pick`/cena), `pickerModal`
(anexa 1 ideia), `attach`, `collect`. Downstream: `angles.py::prepare_base(source!="base")` lê
`s.get("image")`. Projetos com `scenes.json`: `2026-08-wave-teste`, `2026-08-gelo-zero`.

### 1. Backend (`studio/storyboard/service.py`)

- **Schema** por cena passa a `{id, n, text, images:[str,…], primary:str|null}`.
  - `images`: lista de caminhos `storyboard/ideas/<file>` (0..N).
  - `primary`: um item de `images` (ou `null`); default = primeiro item quando há imagens.
- **Migração retrocompatível** em `_normalize`/`_read_scenes`: se a cena vier com `image`
  (formato antigo) e sem `images`, converter para `images:[image]`, `primary:image`. Aceitar
  também `images` já no formato novo. Nunca quebrar `scenes.json` existente.
- `_check_image`: validar **cada** item de `images` (mesma regra de path/existência); `primary`
  precisa estar em `images` (senão, ajusta para o primeiro ou `null`).
- `save_scenes`: normaliza, valida a lista, recalcula `primary`, grava, regrava `storyboard.md`.
  Manter o limite de cenas (1..MAX_SCENES) e MAX_SCENE_TEXT.
- `select()` (detach de ideias removidas): remover das listas `images` os caminhos que caíram;
  se a `primary` caiu, promover o próximo item (ou `null`).
- `_write_md`: por cena, renderiza a **principal** como imagem hero e as demais como
  "alternativas" (lista de `![]()`), preservando a estrutura começo→descoberta→ação→desfecho.
- [auto-aceito: `primary` default = primeiro item da lista; quando o usuário não escolhe
  principal explicitamente, a ordem de inclusão manda.]

### 2. Backend ângulos (`studio/storyboard/angles.py`)

- `prepare_base(source != "base")`: em vez de `s.get("image")`, usar `s.get("primary")` (com
  fallback para o primeiro de `images`; se vazio, mensagem atual "Cena sem imagem…").
- `_scene_view`/`load` que expõem `image` da cena passam a expor `primary` (+ `images` se útil
  ao front dos ângulos). Manter `base_ready` etc. intactos.

### 3. Frontend painel 02 (`studio/etapas/storyboard/view.js` `makeIdeation` + `view.html`)

- `renderScenes`: a `.thumb.pick` única vira uma **mini-galeria** por cena (as `images`), com a
  principal destacada (anel/estrela) e um "+ imagem" para abrir o picker. Clique numa thumb da
  cena permite marcar principal; um "✕" remove aquela imagem da cena.
- `pickerModal(i)`: passa a **multi-seleção** (marca/desmarca várias ideias); ao confirmar,
  seta `scenes[i].images` e mantém/define `primary`.
- `attach`/`collect`: operar sobre `images`+`primary` (não `image`). `data-image` do row →
  `data-images`/`data-primary`.
- Guia/counts: "com imagem" continua contando cenas com ≥1 imagem.
- [auto-aceito: primeira imagem adicionada a uma cena vira automaticamente a principal; o usuário
  troca com um clique. Sem limite rígido de imagens por cena além do bom senso (as ideias
  disponíveis).]

### 4. ADR-018 (`docs/adrs/generated/STUDIO/ADR-018-*.md`)

Registrar o desvio: contexto (pedido do dono, aula 010 é 1 keyframe), decisão (N keyframes por
cena com principal; principal semeia base dos ângulos e é hero do md), consequências (schema
`scenes.json` evolui com migração retrocompatível; painel 03 inalterado), `[extensão]` marcado.
Relacionar ADR-004, ADR-015. Atualizar `docs/adrs/mapping.md` e o `storyboard-fdd.md` (nota).

### 5. Testes (`tests/…storyboard…`)

- Migração: `scenes.json` antigo (`image`) lido vira `images:[image]`,`primary`.
- `save_scenes` com múltiplas imagens: persistência, `primary` default e explícita, validação de
  path por item, recálculo de `primary` quando some.
- `select()` detach: remover imagem que era principal promove a próxima.
- `angles.prepare_base` usa a principal.
- `storyboard.md` mostra principal + alternativas.

### 6. Verificação

- `make verify` verde (incluindo os projetos-fixture, se os testes os usam).
- Manual: `make run`, painel 02 → adicionar 3 ideias a uma cena, trocar principal, salvar,
  conferir `storyboard.md`; painel 03 → base da cena vem da principal.

### 7. Fora de escopo

- Pontos 1, 2, 4 → Frente A. Painel 03 (ângulos) permanece como está — a mudança é só no
  keyframe da cena (painel 02) e em qual imagem semeia a base.
