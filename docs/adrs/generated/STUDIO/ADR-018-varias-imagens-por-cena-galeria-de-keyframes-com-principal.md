# ADR-018: Cada cena do storyboard carrega várias imagens (galeria de keyframes) com uma principal `[extensão]`

**Status:** Aceito
**Data:** 2026-08-28
**Módulo:** STUDIO
**ADRs relacionados:** [ADR-004](ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-015](ADR-015-fusao-da-etapa-5-angulos-na-etapa-4-storyboard.md), [ADR-017](ADR-017-componente-reutilizavel-de-multishot.md), [ADR-003](ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md)

## Contexto e Problema

A **aula 010** monta o storyboard com ~5 cenas, **uma imagem (keyframe) por cena**; os vários
ângulos de uma cena são assunto da **aula 011** (painel 03, "Ângulos por cena"). A implementação
refletia isso: `storyboard/scenes.json` guardava `{"scenes":[{id,n,text,image}]}` com `image`
**singular**, e o painel 02 anexava **uma** ideia por cena.

O dono do produto, usando o app (feedback da wave 5, ponto 3), pediu que **cada cena do painel 02
aceite várias fotos** — a cena "dura mais que uma foto". Isso **contraria a aula 010** (1 keyframe
por cena): é um **desvio de processo**, não uma troca de ferramenta. Pelo gate 2/4 do `CLAUDE.md`,
um desvio só entra **aprovado explicitamente** e **registrado em ADR**, marcado `[extensão]`. O dono
aprovou explicitamente este desvio nesta wave.

O problema de design: aceitar N imagens por cena não pode **colidir** com o painel 03 (ângulos por
cena da aula 011), que já dá a uma cena várias imagens/ângulos com outra finalidade (materializar
`storyboard/cenaNN/base.png`, escolher e ordenar `shotMM_final.png`). Precisávamos de um modelo em
que "várias imagens no painel 02" tivesse um papel claro e distinto do painel 03, e que **não
quebrasse** o `scenes.json` de projetos já existentes.

## Motivadores da Decisão

- **Fidelidade ao roteiro (ADR-004):** é `[extensão]` de decisão do dono, não uma reinvenção do
  método. Fica marcado `[extensão]` no código e nos docs; o painel 03 (aula 011) permanece
  inalterado.
- **Não colidir com o painel 03:** a cena do painel 02 precisa de **um** keyframe canônico — o que
  semeia a base dos ângulos (`angles.prepare_base`) e é o hero do `storyboard.md`. As demais imagens
  são alternativas de curadoria, não ângulos.
- **Retrocompatibilidade (ADR-003):** sem banco, `scenes.json` é lido de disco; projetos existentes
  (`projects/2026-08-wave-teste`, `projects/2026-08-gelo-zero`) não podem quebrar.
- **Consumidor a jusante contido:** o único leitor de `scenes[i].image` era `angles.prepare_base`
  (mesma etapa 4). O `animate` (etapa 5) lê `storyboard/storyboard.json`, **não** o keyframe da cena —
  o raio de impacto do desvio fica dentro da etapa 4.

## Opções Consideradas

1. **Galeria de keyframes por cena + 1 principal** (escolhida): a cena vira `{images:[…], primary}`;
   a principal semeia a base dos ângulos e é o hero do `.md`; as demais são alternativas.
2. **Lista de imagens sem principal** (todas iguais): simples, mas deixa `angles.prepare_base` e o
   hero do `.md` sem uma origem determinística — teria de inventar uma regra implícita (a 1ª?).
3. **Reaproveitar o painel 03** para "várias imagens no 02": funde dois conceitos com finalidades
   diferentes (curadoria de keyframe da cena × ângulos/frames para o vídeo) — exatamente a colisão
   que o design precisa evitar.

## Decisão

Opção escolhida: **galeria de keyframes por cena com uma principal.** Cada cena de
`storyboard/scenes.json` passa a ser `{id, n, text, images:[str,…], primary:str|null}`:

- **`images`**: lista de caminhos `storyboard/ideas/<file>` (0..N), deduplicada, na ordem de inclusão.
- **`primary`**: um item de `images` (ou `null`); default = **primeiro item** quando há imagens. É a
  única imagem que **semeia a base dos ângulos** (painel 03) e o **hero** do `storyboard.md`; as
  demais entram como **alternativas** no `.md`.
- **Migração retrocompatível:** ao ler, uma cena no formato antigo (`image` singular, sem `images`)
  vira `images:[image]`, `primary:image`; o formato novo é aceito como está. Nunca reescreve um
  `scenes.json` existente sem passar pela gravação normal.
- **Validação por item:** cada caminho de `images` é validado (dentro de `storyboard/ideas/`, sem
  path traversal, arquivo existente); a `primary` é forçada a ser um item de `images` (senão volta
  para o primeiro válido ou `null`).
- **Detach:** ao desmarcar ideias, os caminhos que caem saem das galerias; se a `primary` cai,
  promove-se o próximo item da cena (ou `null`).
- **Ângulos (`angles.py`):** `prepare_base(source != "base")` usa `primary` (fallback: 1º de
  `images`; retrocompat: `image` antigo). `list_scenes` expõe `primary` + `images` no lugar de
  `image`. Nada mais dos ângulos muda: o painel 03, `base_ready`, seleção/ordenação e
  `storyboard.json` ficam intactos.
- **Frontend (painel 02):** a cena vira mini-galeria (adicionar imagem via picker multi-seleção,
  marcar principal, remover imagem); "com imagem" conta cenas com ≥1 imagem.

**Escopo desta ADR (o que ela NÃO faz):** a ADR-017 antecipou que `angles.py` migraria para o
núcleo reutilizável de multishot "na reescrita do storyboard (ADR-018)". **Esta** reescrita é
restrita ao **modelo de keyframes da cena** (painel 02) e ao consumo da principal pela base dos
ângulos; a **migração de `angles.py` para `studio/common/multishot.py` continua pendente** — as duas
implementações seguem coexistindo até uma frente futura tratá-la.

## Consequências

- **Contrato `scenes.json` evolui** de `{id,n,text,image}` para `{id,n,text,images,primary}`, com
  migração de leitura retrocompatível. O contrato transversal publicado em
  `docs/domains/studio/waves/wave-1.md` (linha do schema de `scenes.json`) e o "Provides" do
  `storyboard-fdd.md` **precisam refletir o schema novo** — atualização de doc a ser consolidada na
  integração (W5), junto com a verificação da cadeia integrada `scenes.json → storyboard.json →
  animate`.
- O consumidor a jusante `angles.prepare_base` passa a semear a base pela **principal**; `animate`
  (que lê `storyboard/storyboard.json`) não muda.
- ADR-004 (fidelidade) continua vigente; esta ADR é a `[extensão]` que registra o desvio da aula 010.
- ADR-015 (fusão das aulas 010+011 na etapa 4) continua vigente: a mudança é só no **keyframe da
  cena** (painel 02) e em qual imagem semeia a base (painel 03), que permanece como está.
- ADR-003 (persistência em arquivos) continua vigente: só muda o **formato** de uma cena, não o
  modelo de persistência.

## Referências

- `docs/domains/storyboard/features/cena-multi-keyframe-fdd.md` — FDD desta frente (ADH-OS-20260828-15)
- `docs/domains/studio/recon-wave-5.md` — terreno da wave 5 (ponto 3)
- `studio/storyboard/service.py` — schema, migração, `_check_image` por item, `select()` detach, `_write_md`
- `studio/storyboard/angles.py` — `prepare_base`/`list_scenes` usando a principal
- `studio/etapas/storyboard/view.{js,html}` — mini-galeria de keyframes do painel 02
- `docs/adrs/generated/STUDIO/ADR-004-*.md` — fidelidade ao roteiro (estendida por esta `[extensão]`)
- `docs/adrs/generated/STUDIO/ADR-015-*.md` — fusão da etapa 5 (ângulos) na etapa 4
- `docs/adrs/generated/STUDIO/ADR-017-*.md` — componente de multishot (migração de `angles.py` segue pendente)
