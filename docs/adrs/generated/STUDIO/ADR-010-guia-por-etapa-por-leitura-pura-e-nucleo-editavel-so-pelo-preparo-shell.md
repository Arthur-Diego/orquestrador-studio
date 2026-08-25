# ADR-010: Guia por Etapa Calculado por Leitura Pura de Artefatos; Núcleo Editável Só pelo Preparo/Shell

**Status:** Aceito
**Data:** 25-08-2026
**ADRs relacionados:** [ADR-001](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md), [ADR-003](./ADR-003-persistencia-em-sistema-de-arquivos-sem-banco-de-dados.md), [ADR-004](./ADR-004-fidelidade-ao-roteiro-do-curso-como-restricao-arquitetural.md), [ADR-006](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-008](./ADR-008-estrategia-de-testes-sem-rede-ci-ruff-pytest-gitflow-task-id.md)

## Contexto e Problema

Com as 11 etapas implementadas (wave 1), o Studio passou a ter um problema que não era de código:
o usuário abre uma tela e não sabe o que a aula manda fazer ali, o que já está pronto, o que está
faltando nem para onde ir depois. O pedido do dono do produto foi explícito: *"criar campanhas o
mais rápido possível, com todos os passos claros e explicativos; nas telas, o que fazer, o que
está faltando e todas as validações possíveis"*. As auditorias de fidelidade das 11 etapas
(`docs/domains/studio/waves/wave-2-auditoria-*.md`) chegaram à mesma conclusão pelo outro lado:
vários textos de tela atribuem à aula regra que a transcrição não contém, e nenhuma tela mostra
pré-requisito, progresso ou próxima ação.

Cada etapa já sabia responder "o que está pronto", mas cada uma à sua maneira e sem contrato
comum: `sb.status()`, `GET .../shots/scenes`, `base.final_file()`, `publish.portfolio_status()`,
`prospect.gate()` — nove formatos diferentes, espalhados por nove serviços. Pior: duas dessas
leituras "de status" **gravam ao ler** (`edit.get_timeline` cria `edit/timeline.json` na primeira
chamada; `animate.load_plan` grava `animate/takes.json`), o que torna impossível usá-las para
apenas *perguntar* se a etapa está pronta. E `hf.status()` dispara um subprocess de até 30 s sem
cache, chamado por 7 telas a cada troca de projeto.

Ao mesmo tempo, o modo de trabalho do repositório é uma wave: 7 frentes em worktrees separadas,
em paralelo, mergeadas em sequência. A regra do HLD v1.1 ("etapa nova nunca edita `app.py`,
`index.html`, `app.js`, `steps.py`") existia justamente para isso, mas a wave 2 a rompe por
definição — ela *precisa* redesenhar o shell e criar rotas no núcleo. Sem uma regra nova, sete
frentes editariam os mesmos arquivos únicos ao mesmo tempo.

Havia ainda a alternativa óbvia e tentadora: gravar o progresso no `project.json` (`etapa_atual`,
`etapa_3_concluida`…) e ler esse campo. Isso resolveria a performance de imediato.

## Motivadores da Decisão

- O sistema de arquivos já é a fonte de verdade (ADR-003); um campo de progresso em
  `project.json` seria um **segundo** estado, capaz de divergir do disco — e diverge sempre que o
  usuário apaga, move ou traz um arquivo por fora do Studio, que é como a aula ensina a trabalhar.
- O guia é texto de aula (ADR-004): precisa ficar ao lado do código da etapa que ele descreve,
  não num arquivo central que ninguém consegue auditar contra a transcrição.
- O agregado das 11 etapas é uma requisição só (`GET /api/projects/{pid}/guide`), usada pelo menu,
  pela barra de progresso e pelo dashboard: os 11 hooks precisam ser baratos e sem efeito colateral.
- Um hook de plugin quebrado não pode derrubar a tela inteira nem o dashboard das outras 10 etapas.
- Sete frentes paralelas só não conflitam se a propriedade dos arquivos únicos for explícita.
- Teste de frontend com Node/Playwright contraria a ADR-008; a verificação do painel precisa
  caber em asserts HTTP e de string, com o smoke visual como ferramenta do orquestrador fora do CI.

## Opções Consideradas

1. **Guia calculado por leitura pura dos artefatos, num hook opcional por plugin, com contrato e
   derivação comuns em `studio/common/guide.py`** (escolhida)
2. **Estado de progresso persistido em `project.json`** — cada etapa marca "concluída" ao terminar
   e o guia lê o campo
3. **Guia centralizado no núcleo** — um único módulo com o `if` das 11 etapas, sem hook por plugin
4. **Guia no frontend** — cada `view.js` calcula localmente o que falta, a partir das rotas de
   status que a etapa já expõe

## Decisão

Opção escolhida: **o guia de cada etapa é calculado no backend por leitura pura dos artefatos do
projeto, exposto por um hook opcional `studio/etapas/<id>/guide.py::guide(pid)` descoberto por
`etapas.discover()`, com o contrato, os helpers e a derivação de estado centralizados em
`studio/common/guide.py`; e os arquivos únicos do núcleo (`studio/app.py`, `steps.py`,
`config.py`, `higgsfield.py`, `etapas/__init__.py` e `studio/web/*`) passam a ser editáveis
somente pelas frentes de preparo e shell de uma wave.**

O hook é **puro**: só lê arquivos, nunca cria nem regrava artefato, nunca chama CLI, `ffprobe` ou
rede. Isso exclui explicitamente `edit.get_timeline()` e `animate.load_plan()` como fonte de
prontidão — quem precisa desses dados lê `edit/timeline.json` e `animate/takes.json` direto.

A derivação de estado não é decidida por cada etapa: entrada `fail` → `blocked`; nenhuma saída
`ok` → `todo`; todas as saídas `ok` → `done`; senão `in_progress`; `progress` = saídas ok /
saídas. Validações (`ok|warn|fail|todo`) **nunca** bloqueiam — são itens de atenção. Etapa sem
`guide.py`, ou cujo hook levanta exceção, recebe `generic_guide(META)` com `status: "unknown"` e
`detail` do erro: o guia é informativo e jamais vira 500.

O único estado novo aceito em `project.json` é `aspect_ratio` (`[extensão]`, default `16:9`) — e
ele é *configuração*, não progresso. `vibe` deixa de ser pedido na criação do projeto porque a
aula 009 encontra a vibe na etapa 2.

Como consequência direta da regra de propriedade, `hf.status()` ganhou cache de 60 s no núcleo
(`?refresh=1` força) e `PROJECT_LAYOUT` passou a criar todas as pastas de etapa, para que o hook
de guia leia o projeto inteiro sem precisar criar nada.

## Prós e Contras das Opções

### Guia por leitura pura, hook por plugin, contrato comum (escolhida)

- Bom, porque não existe estado a divergir: o que o guia diz é o que está no disco, mesmo quando
  o usuário mexe nos arquivos por fora do Studio — que é o fluxo que a aula ensina.
- Bom, porque o texto da aula fica no plugin da etapa, auditável contra a transcrição
  (gate 1 do `CLAUDE.md`), e o núcleo não conhece nenhuma regra de etapa.
- Bom, porque a derivação de `status`/`progress` é única: 11 etapas não podem discordar sobre o
  que significa "concluída".
- Bom, porque o hook opcional preserva o contrato de plugin: uma etapa sem guia continua
  funcionando (`unknown`), e a wave pode ser mergeada frente a frente.
- Mau, porque o agregado faz I/O de disco por 11 etapas a cada request; é barato hoje (leitura
  local, sem probe), mas escala com o número de artefatos e não tem cache.
- Mau, porque a pureza do hook é uma disciplina, não uma barreira técnica: nada impede um hook
  de chamar o CLI — só a revisão pega.

### Estado de progresso persistido em `project.json`

- Bom, porque a leitura é O(1) e o agregado das 11 etapas sairia de um arquivo só.
- Mau, porque cria uma segunda fonte de verdade contra o sistema de arquivos (ADR-003) e passa a
  mentir assim que o usuário apaga ou traz arquivo por fora.
- Mau, porque exigiria toda etapa lembrar de marcar/desmarcar o campo em todo caminho de escrita
  — inclusive nos de erro e nos de desfazer.

### Guia centralizado no núcleo (sem hook por plugin)

- Bom, porque tudo ficaria num arquivo só, fácil de ler de uma vez.
- Mau, porque o núcleo voltaria a conhecer regra de etapa, revertendo a arquitetura de plugins da
  wave 1, e todo trabalho de etapa passaria a editar um arquivo único — inviável em wave paralela.
- Mau, porque o texto da aula ficaria longe do código que ele descreve.

### Guia no frontend

- Bom, porque não exigiria rota nova nem contrato novo no backend.
- Mau, porque duplicaria em JavaScript a leitura de prontidão que já existe em Python, com um
  segundo lugar para divergir da aula.
- Mau, porque é o tipo de lógica que a ADR-008 deixa sem cobertura de teste (não há teste de JS).

## Consequências

O guia passa a ser a superfície onde a fidelidade ao roteiro é cobrada: `what` e `checklist` vêm
da aula, e a revisão de fidelidade de cada etapa passa a ter um lugar concreto para viver. Em
compensação, todo texto novo do guia é território do gate 1 do `CLAUDE.md` — inventar regra ali é
tão grave quanto inventar comportamento no código.

A regra de propriedade do núcleo é rígida e assimétrica: uma frente de etapa que precise de uma
rota nova, de um componente compartilhado ou de uma pasta em `PROJECT_LAYOUT` **para**, registra a
pendência e pede à frente de preparo — mesmo que a mudança seja de uma linha. Isso custa uma
rodada de sincronização por wave e é o preço de sete worktrees em paralelo sem conflito nos
arquivos únicos.

`PROJECT_LAYOUT` passou a criar as pastas de todas as etapas na criação do projeto. Isso invalida
um padrão de teste que existia no repositório: "a pasta `publish/` não existe" deixou de provar
que um GET não escreve (`tests/test_publish_service.py` foi ajustado para verificar que a pasta
está **vazia**). Qualquer teste futuro que queira provar ausência de escrita deve olhar
artefatos, não pastas.

O cache de 60 s em `hf.status()` é estado de processo: some no reinício e pode mostrar créditos
defasados por até um minuto depois de uma geração. `?refresh=1` existe para a UI forçar quando o
número importa; em teste, `hf.reset_status_cache()` zera.

Enquanto os 11 `guide.py` não estiverem mergeados, `GET /api/projects/{pid}/guide` devolve as 11
etapas com `status: "unknown"` — estado intencional e válido, não regressão. O critério
cross-feature da wave 2 é justamente que, ao fim da integração, nenhuma etapa apareça como
`unknown`.

## Referências

- `studio/common/guide.py` — contrato `Guide`, helpers de leitura pura, derivação e `generic_guide`
- `studio/etapas/__init__.py` — `discover()` com a chave `guide` opcional
- `studio/app.py` — `GET|PATCH /api/projects/{pid}`, `GET /api/projects/{pid}/guide[/{step}]`,
  `_guide_of()` (hook protegido → `unknown`, nunca 500)
- `studio/higgsfield.py` — `STATUS_TTL`, `status(refresh=False)`, `reset_status_cache()`
- `studio/web/ui.js`, `studio/web/ui.css` — `Studio.ui` (inclui `guide`/`renderGuide`)
- `docs/domains/studio/hld.md` (v1.2) — componentes, interfaces públicas e regra de propriedade
- `docs/domains/studio/waves/wave-2.md` — contratos transversais e grafo de sub-waves
- `docs/domains/studio/waves/wave-2-api-transversal.md` — como as frentes usam o contrato
- `docs/domains/studio/recon-wave-2.md` — leituras de status com efeito colateral de escrita
- `tests/test_guide.py` — builder, derivação, fallback e rotas
