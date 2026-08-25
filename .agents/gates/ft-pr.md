# Gate FT PR

Este gate e obrigatorio antes de qualquer push, abertura ou atualizacao de Pull Request.

## Regra irrevogavel

Carregar `.agents/skills/ft-pr/SKILL.md` e cumprir o template
`.agents/skills/ft-pr/references/pr-description-template.md` antes de criar ou atualizar PR.

## Bloqueios

Bloquear a PR se qualquer item abaixo for verdadeiro:

- corpo da PR ausente, generico ou com placeholders;
- sem resumo tecnico do que mudou;
- sem contexto/motivacao;
- sem lista de arquivos ou componentes relevantes;
- sem comandos de validacao ou justificativa objetiva para validacao nao executada;
- sem riscos e mitigacoes;
- sem base `develop`, salvo regra explicita do repositorio;
- inclui arquivos nao relacionados ao escopo;
- contem segredo, token, senha, codigo, email completo sensivel ou dado pessoal desnecessario;
- SDD/Compozy aplicavel sem rastreabilidade de PRD, TechSpec, ADR/task ou justificativa.

## Evidencia minima

Antes de abrir PR, o agente deve ter coletado:

- `git status`;
- `git diff --stat`;
- `git diff --name-only`;
- comandos de teste/lint/build executados ou justificativa de nao execucao;
- branch head e base da PR.

## Saida esperada

O corpo da PR deve permitir code review detalhado diretamente no GitHub, sem depender de
perguntas adicionais para entender escopo, motivacao, validacao e riscos.
