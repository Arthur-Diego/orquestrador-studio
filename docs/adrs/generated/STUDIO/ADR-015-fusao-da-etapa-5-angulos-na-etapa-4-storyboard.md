# ADR-015: A etapa 5 (Ângulos por cena) é fundida na etapa 4 (Storyboard) e sai do pipeline

**Status:** Aceito
**Data:** 2026-08-27
**Módulo:** STUDIO
**ADRs relacionados:** [ADR-004](ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-011](../MUSIC/ADR-011-cena-do-produto-permanece-na-etapa-5.md), [ADR-003](ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-010](ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md)

## Contexto e Problema

O curso separa a **aula 010** (storyboard: ideação a partir da base + as cenas em texto) da **aula
011** (ângulos por cena: gerar/importar várias imagens da mesma cena a partir da imagem-base). A
implementação da wave 1 seguiu essa separação ao pé da letra: a etapa 4 (storyboard) só guardava o
texto das cenas (`scenes.json` = `[{id, n, text, image}]`, **uma** imagem por cena) e a etapa 5
(shots) era uma tela separada com todo o pipeline de imagem por cena — base da cena, candidatos
importados, `_final.png` escolhidos e ordenados, upscale — mais a cena extra do produto (aula 013).

O dono do produto pediu (27/08/2026): *"o storyboard precisa ser mais flexível: as cenas podem
conter mais de uma foto (duram mais que uma foto); poder upar imagens com diferentes ângulos geradas
a partir da imagem-base."* Ou seja, o modelo de **uma imagem por cena** da etapa 4 não serve mais —
uma cena precisa carregar **várias** imagens/ângulos, exatamente o que a etapa 5 já fazia.

Isso deixou o pipeline com **duas telas fazendo o mesmo trabalho de imagem por cena**: a etapa 4
começava a ideação a partir da base e a etapa 5 continuava a produção de ângulos por cena, com o
aluno saltando entre elas. A decisão (em lote, pré-autorizada pelo dono) foi unir tudo num lugar só:
o Storyboard vira **a** casa da cena — texto + várias imagens/ângulos por cena + a cena do produto —
e a etapa 5 é absorvida e **removida** do pipeline (uma etapa a menos).

## Motivadores da Decisão

- Fidelidade ao roteiro (ADR-004): unir as aulas 010 e 011 numa etapa só é `[extensão]` (decisão do
  dono do produto), não uma regressão do conteúdo — a etapa 4 passa a **cobrir as duas aulas** e o
  texto de ambas continua no guia da etapa como contexto. O gate 4 do `CLAUDE.md` exige registrar em
  ADR todo desvio do roteiro; é o que esta ADR faz.
- Uma cena, um lugar: o aluno deixa de saltar entre a etapa 4 e a etapa 5 para montar a mesma cena.
  Cada cena = texto + base + vários ângulos (upload/importar + ordenar) + a cena do produto, tudo na
  etapa 4.
- Sem quebrar o consumidor a jusante: o `animate` (etapa seguinte) depende do **arquivo de saída**,
  não das telas nem das rotas. Preservar o schema `{scenes:[{id, base, shots:[{scene, shot, order,
  image, scene_prompt, ...}]}], product_scene}` mantém o `animate` funcionando com o mínimo de
  mudança.
- Reuso, não reescrita: o serviço de shots já faz exatamente o trabalho pedido; movê-lo para o
  domínio do storyboard preserva a capacidade sem reimplementar o pipeline de imagem.
- Adicionar ângulos = upload + ajuda de prompt: o Studio sugere "outro ponto de vista desta cena a
  partir da base" para o aluno gerar na Higgsfield (via CLI, ADR-002/ADR-004) e importar — sem forçar
  geração paga.

## Opções Consideradas

1. **Fundir a etapa 5 na etapa 4 e removê-la do pipeline; mover o serviço de shots para o domínio do
   storyboard, preservando o schema de saída** (escolhida)
2. **Manter as duas etapas** e só permitir várias imagens por cena na etapa 4 (duplicando o pipeline
   de imagem entre as telas)
3. **Reescrever o pipeline de imagem por cena do zero dentro do storyboard**, aposentando o código de
   shots
4. **Mover o texto das cenas para a etapa 5**, fazendo dela a casa única (o inverso da escolha)

## Decisão

Opção escolhida: **a etapa 5 (Ângulos por cena) é absorvida pela etapa 4 (Storyboard) e sai do
pipeline.** A etapa 4 passa a cobrir as aulas **010 + 011** (e a cena do produto da aula 013). Esta
ADR estende a ADR-004 (`[extensão]` do pipeline) e **complementa/amenda** a ADR-011 (ver
"Consequências").

- **Modelo da cena (etapa 4):** cada cena deixa de ter uma imagem e passa a carregar **várias**
  imagens/ângulos, escolhidas e ordenadas, além do texto. Por cena: base da cena (imagem de ideação
  ou `base/base_final.png`), importar (upload/Downloads/histórico), **prompt de ângulo** sugerido
  ("another point of view … from the base") para gerar na Higgsfield e importar, gerar via CLI
  (opcional, pago), escolher/ordenar os frames, upscale, e a **cena do produto** (aula 013).
- **Serviço:** o serviço de shots move para o domínio do storyboard (`studio/storyboard/angles.py`),
  preservando o **schema de saída** que o `animate` lê:
  `{scenes:[{id, base, shots:[{scene, shot, order, image, scene_prompt, ...}]}], product_scene}`.
- **Arquivo de saída:** move de `shots/storyboard.json` para **`storyboard/storyboard.json`**; o
  `animate` passa a lê-lo desse caminho (ajuste em `animate._storyboard_file()`). A saída de ângulos
  por cena passa a viver sob a pasta `storyboard/` do projeto: `storyboard/cenaNN/`,
  `storyboard/product/`, `storyboard/storyboard.json`, mais `storyboard/frames.md` (a grade de
  ângulos). O `storyboard/storyboard.md` continua sendo o documento de texto das cenas.
- **Pipeline (`studio/steps.py`) — uma etapa a menos:** a entrada `shots` sai; a numeração passa a
  storyboard `n=4` (aulas 010+011), `animate=5` (aula 012), `music=6`, `edit=7`, `export=8`,
  `publish=9`, `prospect=10`. O plugin `studio/etapas/shots/` é absorvido por
  `studio/etapas/storyboard/`.
- **Frontend (etapa 4):** tela única — ideação a partir da base + as cenas (texto) + por cena a base
  e as várias imagens/ângulos (upload + prompt de ângulo + gerar/importar + escolher/ordenar) + a
  cena do produto. Os componentes visuais da antiga etapa 5 (galerias, cards de cena, ordenação)
  migram para a etapa 4.
- **Guia (`guide.py`, ADR-010):** o guia da etapa 4 passa a refletir as duas aulas e a exigência de
  frames por cena; a leitura continua pura (ADR-010).

Projetos antigos que gravaram em `shots/storyboard.json` seguem o caminho de migração/leitura que o
código de saída define; o schema é o mesmo, muda o lugar do arquivo.

## Prós e Contras das Opções

### Fundir na etapa 4 e remover a etapa 5 (escolhida)

- Bom, porque a cena passa a ter **uma casa única** (texto + ângulos + cena do produto), sem o aluno
  saltar entre duas telas para montar a mesma cena.
- Bom, porque reusa o serviço de shots (movido, não reescrito): nenhuma capacidade se perde e o risco
  de regressão do pipeline de imagem é mínimo.
- Bom, porque preserva o schema de saída — o `animate` só muda **o caminho** do arquivo
  (`shots/` → `storyboard/`), não o contrato.
- Bom, porque o pipeline encolhe de 11 para 10 etapas, alinhado ao pedido do dono.
- Mau, porque a etapa 4 fica mais densa (ideação + texto + ângulos + produto numa tela só) e a
  numeração das etapas 5–10 muda, exigindo atualizar catálogo, guias, E2E e a nota de status das
  telas.

### Manter as duas etapas com várias imagens na etapa 4

- Bom, porque não mexe na numeração.
- Mau, porque é justamente a duplicação de pipeline de imagem entre telas que o pedido veio eliminar.

### Reescrever o pipeline de imagem dentro do storyboard

- Bom, porque deixaria o código "nativo" do storyboard.
- Mau, porque jogaria fora um serviço que já faz o trabalho, com alto risco de regressão e fora do
  pedido — a regra de segurança do FDD manda **reusar** o serviço de shots.

### Mover o texto das cenas para a etapa 5

- Mau, porque é o inverso da escolha: a aula 010 (ideação + cenas em texto) é o começo natural da
  etapa; a casa única é o Storyboard, não os ângulos.

## Consequências

- **Relação com a ADR-011:** a ADR-011 se chama literalmente *"A cena do produto permanece na etapa
  5"* — esse enquadramento **muda**. A cena do produto continua existindo e sendo **criada** onde
  vivia o pipeline de imagem por cena (aula 013), mas esse pipeline agora é a **etapa 4**
  (storyboard), não mais uma "etapa 5". Esta ADR **amenda a moldura de numeração** da ADR-011: onde a
  ADR-011 diz "etapa 5 / `shots/`", leia-se **etapa 4 / `storyboard/`** (`storyboard/storyboard.json
  → product_scene`, imagens em `storyboard/product/`). O que a ADR-011 decidiu no mérito continua
  valendo: a **decisão** sobre a cena do produto acontece na etapa de edição/story-check (assistir →
  decidir → escolher a trilha), que apenas renumera (era 7, seguindo o mesmo deslocamento das demais
  etapas). Os atalhos "criar a cena do produto / animá-la" da ADR-011 passam a apontar para a etapa 4
  e a etapa de animação (5), não mais 5 e 6.
- A ADR-004 (fidelidade ao roteiro) continua vigente; esta ADR é a `[extensão]` que registra a fusão
  das aulas 010 e 011 numa etapa só — o conhecimento das duas aulas fica no guia da etapa 4.
- A ADR-003 (persistência em arquivos) continua vigente: só muda **onde** o artefato mora
  (`shots/` → `storyboard/`), não o modelo de persistência.
- O serviço de shots passa a viver em `studio/storyboard/angles.py`; o plugin `studio/etapas/shots/`
  é absorvido por `studio/etapas/storyboard/`.
- `studio/steps.py` remove a etapa `shots` e renumera 5–10; catálogo passa a ter 10 etapas.
- `studio/animate` lê a storyboard de `storyboard/storyboard.json` (antes `shots/storyboard.json`),
  mesmo schema.
- Saída por cena passa a viver sob `storyboard/` do projeto (`storyboard/cenaNN/`,
  `storyboard/product/`, `storyboard/storyboard.json`, `storyboard/frames.md`); `storyboard/
  storyboard.md` segue como o documento de texto das cenas.
- Testes, `scripts/e2e_pipeline.py` e demais scripts são reagrupados para o novo desenho (10 etapas,
  sem `shots`; animate lendo o novo caminho) — sem perder cobertura.
- Documentação: o índice `docs/adrs/README.md` ganha esta ADR; a nota de status das telas registra
  que a tela `05-shots` deixa de existir e as telas seguintes renumeram (o status canônico das telas
  vive no protótipo anotado em `sociedade-codebase`).

## Referências

- `docs/domains/studio/features/storyboard-merge-fdd.md` — FDD (ADH-OS-20260827-10)
- `studio/storyboard/angles.py` — serviço de ângulos por cena (movido do antigo `studio/shots/`)
- `studio/etapas/storyboard/` — plugin da etapa 4 que absorveu `studio/etapas/shots/`
- `studio/steps.py` — pipeline com 10 etapas (storyboard `n=4` cobre aulas 010+011; sem `shots`)
- `studio/animate` — lê `storyboard/storyboard.json` (mesmo schema, novo caminho)
- `docs/adrs/generated/MUSIC/ADR-011-cena-do-produto-permanece-na-etapa-5.md` — moldura de
  numeração amendada por esta ADR (a cena do produto é preservada, dentro da etapa 4)
- `docs/adrs/generated/STUDIO/ADR-004-*.md` — fidelidade ao roteiro (estendida por esta `[extensão]`)
- `docs/adrs/generated/STUDIO/ADR-010-*.md` — guia por leitura pura (o guia da etapa 4 passa a
  cobrir as aulas 010+011)
