# PRD: chat-sync — sincronização chat → telas

Task-Id: ADH-OS-20260906-05
Card: #87 https://trello.com/c/CvcqIxB5
Wave: 11 (frente F03, sub-wave 1, sem dependências)
TechSpec normativa: `_techspec.md` (cópia do FDD aprovado em lote,
`docs/domains/chat/features/chat-sync-fdd.md`)

> Este `_prd.md` existe apenas como adaptação de interface do pipeline SDD. **A fonte de verdade
> normativa é o `_techspec.md`.** Em qualquer divergência, o `_techspec.md` vence.

## Problema

O assistente de chat age pelas tools `mcp__studio__*` e escreve de verdade nos artefatos da
campanha, mas a tela aberta ao lado não sabe disso. O usuário pede "pesquisa referências de café"
no chat, a tool `refs_search` roda, o job termina, os arquivos aparecem em `refs/candidates/`, e a
grade da etapa 1 continua vazia até o usuário sair da etapa e voltar. O mesmo defeito vale para
base, mood, storyboard, personagens e para o rail de progresso do guia.

## Requisitos funcionais

- **RF1.** Após uma tool de ação do chat concluir com sucesso, a tela da etapa correspondente, se
  estiver montada, recarrega seus dados sem intervenção do usuário.
- **RF2.** Todo evento de mudança com `pid` invalida o guia do backend (`invalidarGuia`). Nenhuma
  linha nova calcula status ou prontidão de etapa no cliente (ADR-010 item a).
- **RF3.** Toda tool registrada em `studio/mcp/server.py` tem classificação explícita (etapa+escopo,
  ou `None` para leitura), e um teste de guarda reprova se uma tool nova ficar de fora.
- **RF4.** Tools de leitura nunca produzem evento de mudança.
- **RF5.** Tool que falhou (`is_error: true`) nunca produz evento de mudança.
- **RF6.** Eventos repetidos do mesmo `(pid, step)` dentro de 400 ms viram um único recarregamento;
  eventos de outro `pid` são ignorados pela tela.
- **RF7.** O protocolo do WebSocket cresce de forma estritamente aditiva: nenhum kind existente muda
  de forma e um cliente antigo que receba o kind novo o ignora.

## Não-objetivos

- `refetchInterval` global no `QueryClient`.
- Sincronização para o MCP usado no terminal sem browser (sem aba não há WebSocket).
- Migração das telas de etapa para TanStack Query.
- Navegação automática para a etapa alvo (é a frente F08, que consome este contrato).
- Eventos de mudança originados fora do chat.

## Restrições do repositório (não negociáveis)

- ADR-004: o que o curso não ensina é `[extensão]` e fica marcado como tal no código.
- ADR-006: o polling das telas permanece; o push é canal aditivo.
- ADR-008: testes sem rede e sem navegador.
- ADR-010 item a: prontidão de etapa vem sempre do guia do backend.
- ADR-010 item b / ADR-031 / ADR-032: tocar `frontend/` ou `studio/web/` exige declarar a branch em
  `TITULARES_DO_NUCLEO` (`tests/test_adr010_fronteira_nucleo.py`).
- Cenários de `scripts/qa/cenarios/` **não** se editam.
- Commits: `fix(chat): <descrição em pt-BR> [extensão]` com trailer `Task-Id: ADH-OS-20260906-05`.

## Critérios de aceite

Os 23 critérios da seção 9 do `_techspec.md`. O catálogo executável está em `_tests.md`.
