---
name: ft-pr
description: Gera e valida Pull Requests profissionais com corpo tecnico detalhado, evidencias de verificacao, riscos, rastreabilidade e checklist de review. Use obrigatoriamente antes de qualquer push, abertura ou atualizacao de PR, ao encerrar entregas SDD/Compozy ou manuais, ou quando o usuario pedir para criar uma PR.
---

# FT PR

## Objetivo

Produzir PRs revisaveis sem depender de leitura completa do diff. A PR deve explicar o que
mudou, por que mudou, como foi implementado, como foi validado, riscos e pontos de atencao
para code review.

<HARD-GATE>
Antes de qualquer `git push`, `gh pr create`, `gh pr edit` ou declaracao de PR pronta,
carregue esta skill e cumpra `.agents/gates/ft-pr.md`.

E proibido criar ou atualizar PR quando:
- o corpo nao segue `references/pr-description-template.md`;
- ha placeholders sem preencher;
- nao ha evidencia de validacao ou explicacao objetiva do que nao foi executado;
- o diff contem arquivos fora do escopo sem mencao explicita;
- a base do PR nao e `develop`, salvo regra escrita do repositorio;
- ha risco de segredo, token, senha, email completo sensivel ou dado pessoal exposto.
</HARD-GATE>

## Sequencia obrigatoria

1. **Identificar contexto**
   - Confirmar repositorio, branch atual, base esperada e se a entrega e SDD/Compozy ou manual.
   - Ler PRD, TechSpec, task files, ADRs, prompt de origem ou issue quando existirem.
   - Preservar `Task-Id` no titulo/corpo quando existir.

2. **Inventariar o diff**
   - Coletar `git status`, `git diff --stat`, `git diff --name-only` e commits locais.
   - Separar alteracoes de produto, contrato, testes, docs, infra, contexto e gerados.
   - Nao incluir arquivos nao relacionados no commit/PR.

3. **Construir narrativa tecnica**
   - Explicar motivacao e comportamento antes/depois.
   - Descrever decisoes tecnicas, contratos, persistencia, seguranca, compatibilidade e rollback quando aplicavel.
   - Chamar atencao para pontos que o reviewer deve olhar primeiro.

4. **Registrar validacao**
   - Listar comandos executados e resultado.
   - Se algo nao foi executado, registrar motivo concreto e risco residual.
   - Nunca escrever "testes ok" sem comandos e evidencia.

5. **Gerar corpo da PR**
   - Usar `references/pr-description-template.md`.
   - Remover secoes que nao se aplicam apenas quando isso melhorar clareza.
   - Preencher riscos, mitigacoes, rollout e checklist mesmo em PR pequena.

6. **Criar ou atualizar PR**
   - Base padrao: `develop`.
   - Titulo: claro, revisavel e consistente com o tipo da mudanca.
   - Corpo: em portugues brasileiro; identificadores, comandos e APIs preservam idioma tecnico.
   - Apos criar, revisar a URL da PR e confirmar que o corpo renderizou corretamente.

## Qualidade minima do corpo

- Um reviewer deve entender o escopo sem abrir o diff.
- Toda mudanca relevante deve aparecer em pelo menos uma secao.
- Riscos conhecidos nao podem ficar escondidos.
- Validacao deve ser reproduzivel.
- Breaking changes, migracoes, contratos e seguranca devem ter secoes explicitas quando existirem.
- Nada de placeholders, checklist vazio ou texto generico.

## Recurso obrigatorio

Leia `references/pr-description-template.md` antes de redigir qualquer PR.
