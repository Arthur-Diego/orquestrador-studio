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
  Domínios: `studio` (app/web/plugins), `higgsfield` (ponte com o CLI) e um por etapa: `refs` (1), `mood` (2), `base` (3), `storyboard` (4), `shots` (5), `animate` (6), `music` (7), `edit` (8), `export` (9), `publish` (10), `prospect` (11). Contratos entre etapas: `docs/domains/studio/waves/wave-1.md`
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
- Frontend estático em `studio/web/` (HTML/CSS/JS sem build).
- **Etapas são plugins**: `studio/etapas/<id>/` com `META`, `router.py`, `view.html`, `view.js`
  (descoberta automática; ver `docs/domains/studio/hld.md`). Para implementar uma etapa nova,
  crie só essa pasta + `studio/<id>/service.py` + testes; **não edite** `app.py`, `index.html`,
  `app.js` nem `steps.py`. O `view.js` registra `Studio.register("<id>", ctx => ({init, onProject}))`.
- Ponte com a Higgsfield **somente** via CLI oficial (`studio/higgsfield.py`, subprocess +
  `--json`). Nunca chamar `api.higgsfield.ai` direto; nunca automatizar a UI da Higgsfield.
- Testes: `pytest` sem rede e sem navegador (fakes); `make verify` = ruff + pytest.
- Mudanças nessas decisões exigem ADR.

## Skills → ações

| Skill | Acionar para... |
| --- | --- |
| `ft-pr` | Gate obrigatório antes de push/PR |
| `ship-manual` | Encerrar entrega fora do SDD: commit com `ADH-OS-*` + PR para `develop` |
| `cy-trello-mcp` | Camada de acesso ao Trello usada pelo protocolo do `/dd` |
| `cy-create-prd`, `cy-create-tasks`, `cy-execute-task`, `cy-review-round`, `cy-fix-reviews`, `cy-final-verify`, `cy-workflow-memory` | Pipeline SDD (Compozy) — acionadas pelo `dd-feature` |
| `compozy` | Entender capacidades e fluxo do Compozy |
| `git-rebase` | Resolver conflitos de rebase/merge |

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

## Idioma

Documentação, PRs, prompts do fluxo e textos funcionais em português brasileiro;
identificadores de código em inglês; prompts de geração de imagem/vídeo em inglês (aula 007).

## Persistência do modo Plano

Ao aceitar um plano em modo Plano, gravar em `.claude/plans/[timestamp]-[slug].md`.
