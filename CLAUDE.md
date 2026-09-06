# orquestrador-studio

Ferramenta local (FastAPI + frontend estático) que executa, etapa por etapa, o método de
produção de vídeo com IA ensinado no curso **"O Orquestrador — Iniciante" (ABRAhub)**.
Este arquivo contém as instruções operacionais deste repositório para o Claude Code.

## Gates de fidelidade ao roteiro do curso (IRREVOGÁVEIS)

O produto deste repositório é **o método do curso, executável**. Ele não é um lugar para
inventar um método novo. Antes de implementar ou alterar qualquer etapa:

1. **A aula é a fonte de verdade.** Cada etapa em `studio/steps.py` aponta para a aula que a
   define. Implementação de etapa DEVE reproduzir o que o instrutor faz naquela aula
   (entradas, saídas, ordem, regras de qualidade que ele repete). O que a aula não ensina
   não entra na etapa. O mapa fiel aula-a-aula está em
   `docs/plano/plano-automacao-videos.md` (Fase 1) e a versão Higgsfield em
   `docs/plano/plano-higgsfield.md` — usar os dois como referência; as transcrições brutas
   ficam fora do repositório (locais).
2. **Sugerir é permitido; inventar não.** Melhorias que o curso não ensina (ex.: character
   sheet, color match, hook nos 3 s, seis tipos de prompt de mood) podem ser **sugeridas** ao
   usuário — no PR, no resumo ou como pergunta — mas **não implementadas** sem aprovação
   explícita dele. Quando implementadas, ficam marcadas como `[extensão]` no código e na
   documentação, separadas do que é do curso.
3. **Trocar ferramenta não é desvio; trocar processo é.** O próprio instrutor manda "ficar
   preso ao processo, não à plataforma" (aula 005). Substituir Midjourney/Higgsfield UI por
   Higgsfield CLI, CapCut por ffmpeg etc. é legítimo desde que a etapa produza o mesmo
   artefato que a aula produz.
4. **Toda decisão de desvio vira registro.** Se uma etapa precisar divergir da aula por
   limitação técnica ou de termos de uso, isso é ADR em `docs/adrs/` e nota na etapa — nunca
   um desvio silencioso.
5. **Antes de codar uma etapa nova, escrever em uma frase o que a aula faz e o que a etapa
   vai produzir**, e conferir com o usuário se houver qualquer dúvida de leitura. Em caso de
   ambiguidade entre duas leituras da aula, perguntar; não escolher sozinho.

Exemplo real desse gate: a etapa 2 (mood board) foi corrigida de "6 tipos de prompt" para
"1 prompt de vibe × grid de 4", porque é isso que a aula 009 ensina.

## Documentação

Todo o contexto deste repositório vive em `docs/`. Não há contexto em `contexts/`,
`.agents/contexts/` ou `rules/`.

- Gitflow: `docs/gitflow.md` (ler antes de qualquer commit)
- Configuração do fluxo DD (board e listas do Trello, IDs de task): `docs/dd.md`;
  modo paralelo: `docs/dd-parallel.md`
- Guidelines: `docs/guidelines/python-development-guidelines.md` (seguir sempre)
- Domínios (HLD): `docs/domains/<dominio>/hld.md` — ler antes de mexer no domínio.
  Domínios: `studio` (app/web/plugins), `higgsfield` (ponte com o CLI) e um por etapa: `refs` (1), `mood` (2), `base` (3), `storyboard` (4 — cenas **e** ângulos por cena; a documentação dos ângulos fica no domínio `shots`, que não é etapa própria), `animate` (5), `music` (6), `edit` (7), `export` (8), `publish` (9), `prospect` (10). Contratos entre etapas: `docs/domains/studio/waves/wave-1.md`
- FDDs: `docs/domains/<dominio>/features/` — fonte de verdade de comportamento por etapa;
  nascem sob demanda via `dd-feature`
- Diagramas: `docs/domains/<dominio>/diagrams/{mermaid,c4}/`
- ADRs: `docs/adrs/generated/` — não contrariar sem novo ADR; mapeamento em `docs/adrs/mapping.md`
- Relatórios de análise: `docs/agents/` (raio-X, auditoria de dependências, análises por
  componente; índice em `docs/agents/MANIFEST.md`)
- Planos de produto (método do curso e versão Higgsfield): `docs/plano/`
- Runbooks: `docs/operations/` (branch protection)

## Fluxo de trabalho

Use **`/dd`** como porta de entrada (feature, bug, refatoração, brownfield, docs, limpeza)
e **`/dd-parallel`** para waves de várias etapas ao mesmo tempo. Não existe fluxo paralelo
de orquestração. O card do Trello é o único registro de trabalho (`docs/dd.md`).

Cada etapa do curso é uma **feature** do domínio correspondente: `dd-feature` cria o FDD a
partir da aula, o Compozy (SDD) decompõe e executa quando a etapa for grande.

### Gate de PR profissional (IRREVOGÁVEL)

Antes de qualquer `git push`, abertura ou atualização de Pull Request, carregar
`.claude/skills/ft-pr/SKILL.md` e cumprir `.agents/gates/ft-pr.md`. Base padrão: `develop`.

## Stack e arquitetura

- Python 3.12 · FastAPI + Uvicorn · Playwright (Chromium) · Pillow. Sem banco: persistência
  em arquivos sob `projects/<id>/` (nunca versionado).
- Frontend em **React** (`frontend/`: Vite + React + TypeScript estrito + TanStack Query + Vitest),
  que constrói o bundle **versionado** `studio/web/dist/`, servido pelo mesmo processo em
  `/static/dist/` (ADR-031, ADR-032). A migração da Wave 10 terminou na E10: o vanilla
  `studio/web/{index.html,app.js,ui.js,ui.css,style.css}`, a flag `STUDIO_UI` e a ponte
  `window.Studio` foram removidos; React é sempre o default. `make verify` (Python) NÃO depende de
  Node — o job `frontend` do CI é paralelo.
- **Etapas são plugins**: `studio/etapas/<id>/` com `META`, `router.py` e a UI React `ui/index.tsx`
  (descoberta automática pelo backend via `discover()`; pelo shell via `import.meta.glob` — sem
  registry central). Para implementar uma etapa nova, crie só essa pasta + `studio/<id>/service.py`
  + testes; **não edite** `app.py`, `steps.py` nem o núcleo do frontend (`frontend/src/**`). A tela
  é o componente default-exportado de `ui/index.tsx`, montado pelo `PluginHost` do shell.
- Ponte com a Higgsfield **somente** via CLI oficial (`studio/higgsfield.py`, subprocess +
  `--json`). Nunca chamar `api.higgsfield.ai` direto; nunca automatizar a UI da Higgsfield.
- **Assistente de chat `[extensão]`** (ADR-036/037/038/040): `studio/chat/` (runtime `claude -p`
  stream-json + WebSocket `/ws/chat/{id}`) e `studio/mcp/` (servidor MCP stdio `python -m studio.mcp`,
  cliente HTTP da própria API). O agente age **só** pelas tools `mcp__studio__*` (tools nativas off,
  `--strict-mcp-config`); escolha visual e gasto são do usuário (`ui.*`, ADR-038). O MESMO MCP serve
  o chat embutido e o terminal (`.mcp.json` do repo). Biblioteca de **Personagens** em
  `studio/characters/` (ADR-039). Pontes de geração seguem sendo Higgsfield (paga) e motor local
  (grátis, ADR-033) — o chat não cria caminho alternativo.
- Testes: `pytest` sem rede e sem navegador (fakes); `make verify` = ruff + pytest.
- Mudanças nessas decisões exigem ADR.

## Skills → ações

| Skill | Acionar para... |
| --- | --- |
| `ft-pr` | Gate obrigatório antes de push/PR |
| `ship-manual` | Encerrar entrega fora do SDD: commit com `ADH-OS-*` + PR para `develop` |
| `qa-studio` | QA E2E da aplicação inteira (telas via Playwright + API + newman), cards no Trello, correção em `fix/qa-<data>` e revalidação incremental até zerar (`/qa-studio [telas]`; config em `docs/qa/config.md`) |
| `mood_orquestrador` | Cadeia de mood ponta a ponta: pergunta a foto escolhida → DNA → board (`/mood_orquestrador`) `[extensão]` |
| `mood_vibe_scout` | Descobrir a vibe do zero: entrevista de diretor de arte + coleta de N referências por vibe no Pinterest (`/mood_vibe_scout`) `[extensão]` |
| `mood_visual_dna` | Ler a foto escolhida e devolver DNA visual, paleta e consultas por função (também disponível como agente) `[extensão]` |
| `mood_board_builder` | A partir do DNA: busca, baixa, cura e monta a prancha `_moodboard.jpg` (`/mood_board_builder`) `[extensão]` |
| `cy-trello-mcp` | Camada de acesso ao Trello usada pelo protocolo do `/dd` |
| `cy-create-prd`, `cy-create-tasks`, `cy-execute-task`, `cy-review-round`, `cy-fix-reviews`, `cy-final-verify`, `cy-workflow-memory` | Pipeline SDD (Compozy) — acionadas pelo `dd-feature` |
| `compozy` | Entender capacidades e fluxo do Compozy |
| `git-rebase` | Resolver conflitos de rebase/merge |
| `studio-conduzir` `[extensão]` | Conduzir a campanha ponta a ponta no terminal pelas tools do MCP `studio` (ADR-036/037) |
| `studio-personagem` `[extensão]` | Criar/fixar personagem e aplicar identidade a uma campanha (ADR-039) |
| `studio-ajuda` `[extensão]` | Tirar dúvidas do método/aplicação pelo guia ao vivo e resources do MCP |

**Não acionar**: `cy-create-techspec` (o FDD é a techspec — ver `dd-feature`).

## Gitflow e rastreabilidade

Regra completa em `docs/gitflow.md`. Resumo:

- Todo commit recebe trailer `Task-Id:` — `OS-NNN` (SDD) ou `ADH-OS-<YYYYMMDD>-<seq>` (ad-hoc).
  Hook: `make hooks`. CI: `task-id-check`.
- Branch de trabalho nasce de `develop`, PR para `develop`; promoção `develop → main` por PR.
- Uma task só é concluída após promoção mergeada em `main`.

## Execução paralela

Várias sessões podem trabalhar em worktrees distintas (`/dd-parallel`): `.venv` próprio por
worktree, `PORT` a partir de `8766` (`8765` é da instância de referência), `projects/` local.
Um runner Compozy por worktree.

### Convenções da Wave 10 — migração do frontend para React

Valem enquanto a wave estiver aberta (E0…E10, `docs/domains/studio/waves/wave-10.md`):

1. **Rodada de QA usa `RUN=<nome-da-frente>`, nunca `RUN=local`.** Ex.: `make qa-up qa-seed qa-run
   RUN=react-e4`. Frentes paralelas compartilham a máquina; `RUN=local` faz duas frentes
   escreverem no mesmo `.qa/runs/`, e a segunda sobrescreve o resultado da primeira sem aviso.
   O `stack-up.sh` já resolve a primeira porta livre a partir de 8790, então o único conflito
   real é o diretório da rodada. Relatório commitado em
   `docs/qa/reports/<AAAA-MM-DD>-<run-id>/`.
2. **`studio/web/dist/` é versionado (desde a E10).** Durante a wave ficava no `.gitignore` para
   não conflitar entre as seis frentes paralelas; a **E10** commitou o bundle e **inverteu a guarda
   de CI** — o job `frontend` rebuilda e falha se o `dist/` commitado divergir do rebuild. Quem mexe
   no frontend roda `make frontend-build` e commita o `dist/`, senão o CI reprova (ADR-031;
   `wave-10.md` §6.1). O bundle é versionado de propósito: o usuário desta ferramenta local não tem
   Node.
3. **Tocar o núcleo exige declarar titularidade.** `tests/test_adr010_fronteira_nucleo.py` barra
   qualquer branch que mexa em `studio/web/`, `studio/app.py`, `steps.py`, `config.py`,
   `higgsfield.py`, `etapas/__init__.py` ou `frontend/` sem estar registrada em
   `TITULARES_DO_NUCLEO` com card e recorte mínimo. Frente de etapa continua barrada (ADR-010 b,
   ADR-032).
4. **Os cenários de `scripts/qa/cenarios/` não se editam.** Eles são o oráculo da migração: se um
   cenário precisou mudar para passar, o comportamento mudou — isso é bug da migração, não ajuste
   de teste. Mesma regra para o diff de `textContent` contra o baseline VIGENTE
   (`docs/qa/reports/2026-09-03-react-e0-v2/textcontent/`), que tem de ser vazio (ADR-004).
   O baseline original da E0 (`…-react-e0/`) foi **substituído** pelo `-v2`, regerado depois da
   correção do bug real que ele apontava (C-BASE-33, card [REACT-BUG-01], ADH-OS-20260903-01):
   o alvo agora é **375 PASSA · 5 FALHA · 2 BLOQUEADO** de 382.

### Frontend (a partir da Wave 10)

`frontend/` é um projeto npm (Vite + React + TypeScript estrito + Vitest + ESLint) que constrói
para `studio/web/dist/`. `make verify` **não** depende de Node — quem só mexe em Python nunca
precisa instalar npm. Os alvos são separados, espelhando os dois jobs paralelos do CI:
`make frontend-setup` (npm ci), `make frontend-verify` (typecheck + lint + vitest),
`make frontend-build`. A UI de cada etapa é `studio/etapas/<id>/ui/index.tsx`, descoberta por
`import.meta.glob` — **não existe registry central**, e criar etapa nova continua sendo criar só a
pasta dela (ADR-031, ADR-032).

O acesso à API sai todo de `frontend/src/api/` (Wave 10 · E1): `api()`/`apiUpload()` equivalentes
ao helper do vanilla, rotas e corpos tipados a partir de `schema.ts` e os hooks TanStack Query.
`schema.ts` é **gerado** do `/openapi.json` que o FastAPI publica — quem mexer em rota ou em modelo
Pydantic roda `make frontend-schema` e commita o arquivo, senão o job `frontend` reprova na guarda
de drift. Nenhum hook deriva prontidão de etapa: ela vem sempre do guia do backend (ADR-010 a).

O design system vive em `frontend/src/ui/` (Wave 10 · E2): componentes e hooks React que reproduzem
**100% da superfície de `window.Studio.ui`** do vanilla (28 membros — `Modal`, `ProgressModal`
+ `useProgress`/`progressJob`, `CostSheet` + `useCostConfirm`, `Guide`/`StepGuide`, `MoodMosaic`,
`Tile`, `Pipe`, `Beats`, `HfChip`, `CreditsChip`, `Chip`, `CopyButton`, `useUpload`, `usePoll`,
`useAutosize`, `esc`, `fmtPct`, os mapas `STATUS_LABEL/ITEM_LABEL/STATUS_KIND` etc.), com os MESMOS
ids/classes/atributos ARIA. As folhas `style.css`/`ui.css` são cópias **byte-a-byte** em
`frontend/src/styles/` — nenhuma classe é renomeada (contrato com os cenários de QA). Desde o corte
da E10 não há mais vanilla: todas as telas e o shell importam de `frontend/src/ui`; o único
resquício de `window.Studio` são os escape hatches imperativos que os cenários de QA dirigem
(`window.Studio.{moodboards,creditos}.open`, reinstalados pelas áreas React). O POST multipart
(`upload`) mora na camada de API e é reexportado pela `ui`, sem segunda cópia.

## Idioma

Documentação, PRs, prompts do fluxo e textos funcionais em português brasileiro;
identificadores de código em inglês; prompts de geração de imagem/vídeo em inglês (aula 007).

## Persistência do modo Plano

Ao aceitar um plano em modo Plano, gravar em `.claude/plans/[timestamp]-[slug].md`.
