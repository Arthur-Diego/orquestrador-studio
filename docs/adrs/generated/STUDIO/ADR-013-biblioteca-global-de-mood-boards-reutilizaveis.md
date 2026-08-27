# ADR-013: Biblioteca Global de Mood Boards Reutilizáveis

**Status:** Aceito
**Data:** 27-08-2026
**ADRs relacionados:** [ADR-007](../MOOD/ADR-007-mood-board-vibe-unica-teto-de-8-grid-de-4-como-orientacao-de-ui.md), [ADR-003](ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004](ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-010](ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md)

## Contexto e Problema

A aula 009 do curso (etapa 2) ensina **um** mood board de **vibe única por campanha**: o aluno
encontra uma vibe, o bot escreve um prompt, ele gera na UI, importa e escolhe as imagens no mesmo
mood. A ADR-007 registrou essa decisão — vibe única, teto de 8 imagens, grid de 4 como orientação
de UI — e ela continua valendo.

O dono do produto pediu (27/08/2026) algo que a aula não cobre: *"quero uma tela de moodboard para
gerar meus mood boards e usá-los quando quiser; na tela de imagem base poder puxar o mood board que
eu quiser e trazê-los visualmente além do prompt que já existe."*

O mood da etapa 2 é **preso a uma campanha** (`projects/<pid>/mood/`): ele nasce e morre com o
projeto, não pode ser reaproveitado em outra campanha e não é uma coleção que o aluno cultiva ao
longo do tempo. Além disso, a etapa 3 (imagem base) só conhece o mood da própria campanha
(`mood_paths()` = `mood/selected/`) e o expõe como texto/paleta — nunca como galeria visual das
imagens que o bot vê. Faltavam, portanto: (1) mood boards **reutilizáveis entre campanhas**;
(2) a etapa 2 e a etapa 3 poderem **puxar/referenciar** um desses boards; (3) mostrar o mood
**visualmente** na etapa 3.

## Motivadores da Decisão

- Fidelidade ao roteiro (ADR-004): a aula ensina vibe única por campanha e o produto **não** pode
  regredir nisso. A biblioteca é um **acréscimo** (`[extensão]`), não uma troca do modelo da aula.
- Reuso real: um aluno que produz várias campanhas quer montar um mood board de "neon frio" uma vez
  e semeá-lo em quantas campanhas quiser, sem recolher e recurar as mesmas imagens.
- Persistência já é sistema de arquivos (ADR-003): não faz sentido introduzir banco para isto.
- Isolamento por domínio: a biblioteca é campanha-independente, então não é uma das 11 etapas nem
  um plugin de etapa — precisa de área e armazenamento próprios.
- Segurança de caminho: como nos projetos (`PID_RE`), um identificador cru nunca pode virar caminho
  de arquivo.

## Opções Consideradas

1. **Biblioteca global separada, com área própria na sidebar; etapa 2 puxa e etapa 3 referencia**
   (escolhida)
2. **Estender a etapa 2 para guardar N moods por campanha** (multi-mood por campanha)
3. **Mood boards globais, mas sem área própria** — só um seletor dentro das etapas 2 e 3
4. **Copiar o mood de uma campanha para outra** (sem biblioteca; "duplicar mood de outro projeto")

## Decisão

Opção escolhida: **uma biblioteca GLOBAL de mood boards reutilizáveis, independente de campanha,
com área própria na sidebar, que estende (não substitui) a ADR-007.**

- **Armazenamento** (`studio/config.py`): `MOODBOARDS_DIR =
  Path(os.environ.get("STUDIO_MOODBOARDS", ROOT / "moodboards"))`, criado no boot junto de
  `PROJECTS_DIR`/`STATE_DIR` e gitignorado (`/moodboards/`). Cada board vive em
  `MOODBOARDS_DIR/<mbid>/` com `moodboard.json` (`{id,name,note,vibe,created}`), `candidates/`
  (importadas), `images/` (curadas), `palette.json` (derivado técnico) e `prompt.txt`/`prompts.json`
  (prompt de vibe). `mbid` é o slug do nome, validado pelo mesmo formato do `PID_RE`.
- **Novo domínio** `studio/moodboards/` (`service.py` + `router.py`), reusando `common/ingest.py`
  (importação/dedupe), `common/prompter.py` (o mesmo bot da etapa 2) e `common/palette.py` — este
  último **fatorado** de `studio/mood/service._palette` para ser a fonte única da derivação de
  paleta entre a etapa 2 e a biblioteca, sem alterar o comportamento da etapa 2.
- **API global** (sem pid), registrada diretamente em `studio/app.py` (não é plugin de etapa):
  `GET/POST /api/moodboards`, `GET/PATCH/DELETE /api/moodboards/{mbid}`,
  `POST /api/moodboards/{mbid}/import/{upload,downloads,history}`,
  `GET /api/moodboards/{mbid}/candidates`, `POST /api/moodboards/{mbid}/select`,
  `GET /api/moodboards/{mbid}/prompt` e `POST /api/moodboards/{mbid}/prompt/generate`. As imagens
  são servidas em `/mbfiles`. `board_dir()` levanta `KeyError` para mbid inválido/inexistente — o
  mesmo handler do núcleo o transforma em 404 (409 para nome duplicado, 422 para curadoria > 8).
- **Área própria no shell** (`studio/web/*`, ADR-010): item "Mood boards `[extensão]`" numa
  `.side-sec` acima da nav de etapas; roteamento por hash **global** reservado — `#/moodboards`
  (lista) e `#/moodboards/<mbid>` (editor) — reconhecido no `parseRoute`/`applyRoute`. O nome
  `moodboards` é **reservado**: um pid de projeto nunca pode assumi-lo (`RESERVED_PIDS` em
  `create_project`).
- **Puxar na etapa 2**: ação "Puxar de um mood board `[extensão]`" — copia as imagens do board
  para `mood/selected/` da campanha e semeia `mood.md`/`palette.json`/`project.vibe`. Mantém-se o
  modelo de **vibe única por campanha** (ADR-007): o board é a **semente**, não um segundo mood. O
  fluxo original (achar a vibe + bot) permanece intacto como origem alternativa.
- **Referenciar na etapa 3**: um seletor de qual mood usar como referência (o da campanha **ou**
  um board da biblioteca) e uma **galeria visual** das imagens escolhidas, além do prompt/paleta
  que já existiam. Quando um board é escolhido, o bot recebe as imagens dele (por caminho absoluto,
  como `mood_paths` faz hoje) no lugar das do mood da campanha.

A biblioteca é **global e a cópia para a campanha é independente**: apagar um board depois **não**
afeta campanhas que já o puxaram — as imagens foram copiadas para `mood/selected/`.

## Prós e Contras das Opções

### Biblioteca global separada, com área própria (escolhida)

- Bom, porque separa claramente o que é da campanha (vibe única, ADR-007) do que é reutilizável, sem
  regredir a fidelidade à aula: a etapa 2 continua com um mood só por campanha.
- Bom, porque reusa a infraestrutura existente (ingest, prompter, paleta) e não introduz banco
  (ADR-003).
- Bom, porque o roteamento reservado deixa a área campanha-independente coexistir com o shell de
  campanha sem ambiguidade de pid.
- Mau, porque cria um segundo espaço de armazenamento (`MOODBOARDS_DIR`) e um domínio novo fora do
  mecanismo de plugins de etapa — o `app.py` passa a registrar um router global explicitamente.
- Mau, porque "puxar" copia bytes: um board grande copiado para muitas campanhas duplica imagens em
  disco (é o lado seguro — a campanha fica autossuficiente).

### Multi-mood por campanha

- Bom, porque não sairia do domínio da etapa 2.
- Mau, porque contraria diretamente a ADR-007 (vibe única) e a aula, e não resolve o reuso **entre**
  campanhas — que era o pedido.

### Mood boards globais sem área própria

- Bom, porque evita mexer no roteamento do shell.
- Mau, porque o usuário pediu explicitamente "uma tela de moodboard"; sem área própria não há onde
  montar/curar a biblioteca fora do contexto de uma campanha.

### Copiar o mood de outra campanha

- Bom, porque seria a menor mudança.
- Mau, porque não cria uma coleção cultivável nem desacopla o mood da campanha: continuaria preso a
  um projeto de origem, que pode ser apagado.

## Consequências

- A ADR-007 continua vigente e a etapa 2 continua com **vibe única por campanha**; a biblioteca é
  `[extensão]` marcada na UI e nos docstrings. Esta ADR **estende** a ADR-007.
- `studio/mood/service.py` passou a importar `studio/common/palette.py` (fonte única da paleta);
  o `_palette` local virou alias importado — sem mudança de comportamento na etapa 2.
- `studio/base/service.py` passou a importar `studio/moodboards/service.py` (referência de estilo
  vinda de um board). A direção não cria ciclo: `moodboards` não importa `base`/`mood`; quem importa
  `moodboards` é `base` (etapa 3) e `mood` (etapa 2, para "puxar").
- `studio/app.py` foi editado para registrar o router global e montar `/mbfiles` — decisão de
  arquitetura, coerente com o fato de a biblioteca não ser um plugin de etapa.
- Os testes usam um `STUDIO_MOODBOARDS` isolado (monkeypatch no `conftest`, como já é feito com
  `STUDIO_PROJECTS`). A geração de imagens por IA dentro da biblioteca fica como `[extensão]`
  opcional fora deste escopo — o caminho primário é importar.

## Referências

- `studio/config.py` — `MOODBOARDS_DIR`
- `studio/moodboards/service.py`, `studio/moodboards/router.py` — CRUD, curadoria, paleta, prompt
- `studio/common/palette.py` — derivação de paleta (fonte única)
- `studio/mood/service.py` — `pull_board()` (puxar da biblioteca para a campanha)
- `studio/base/service.py` — `mood_sources()`, `_ref_mood_paths()` (referência por board na etapa 3)
- `studio/app.py` — registro do router global e mount `/mbfiles`
- `studio/web/moodboards.js`, `studio/web/app.js`, `studio/web/index.html` — área e rota global
- `docs/domains/moodboards/features/moodboard-library-fdd.md` — FDD (ADH-OS-20260827-04)
- `docs/adrs/generated/MOOD/ADR-007-*.md` — vibe única por campanha (estendida por esta ADR)
