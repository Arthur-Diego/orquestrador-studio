# ADR-040: Agente do chat sem tools nativas e isolado das configurações do usuário

**Status:** Aceito
**Data:** 2026-09-05
**Task-Id:** ADH-OS-20260905-04
**ADRs relacionados:** [ADR-001 (loopback, sem auth)](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md), [ADR-034 (execução de skill do Claude CLI)](./ADR-034-execucao-de-skill-do-claude-cli-com-escrita-em-disco.md), [ADR-036](./ADR-036-runtime-de-chat-via-claude-cli-em-processo-terceiro-modo.md), [ADR-037](./ADR-037-servidor-mcp-do-studio-como-cliente-http-da-propria-api.md)

## Contexto e Problema

O `skill_runner` (ADR-034) já registrou que um `claude` com `Bash`/`Write` solto na máquina é
superfície nova que precisa de fronteira. O assistente é um chat **contínuo** e mais exposto: o
usuário conversa com ele o tempo todo. Se o agente tivesse as tools nativas do Claude Code
(`Bash`, `Edit`, `Write`, `Skill`, `WebFetch`…) e herdasse os MCP e skills globais do usuário
(Trello, Context7, os 40+ skills do repo), ele poderia rodar comandos arbitrários, editar arquivos
e invocar workflows pesados (até o próprio `dd-parallel`) a partir de uma frase casual — muito além
de "conduzir a criação de vídeo".

## Decisão

**O que o agente pode fazer é exatamente o catálogo do MCP do Studio — nada mais.**

1. **Tools nativas desligadas.** O turno passa `--tools ""` (nenhuma tool do conjunto interno:
   sem `Bash`, `Edit`, `Write`, `Skill`, `WebFetch`).
2. **Só o MCP do Studio, e só ele.** `--allowedTools mcp__studio__*` (auto-aprova as tools do
   Studio, sem prompt) e `--strict-mcp-config` (ignora todos os MCP configurados do usuário —
   Trello, Context7). O `--mcp-config` da aba declara apenas o servidor `studio`.
3. **Blast radius = catálogo.** Como as tools do MCP são clientes HTTP da API em loopback
   (ADR-037), o pior que o agente faz é o que qualquer tela faz — com os mesmos gates (login,
   custo, um job por projeto). `api_get` é somente-GET, com allowlist de prefixo `/api/`.
4. **Escrita confinada onde precisa.** A geração real acontece no servidor (não no agente); o
   agente nunca lê nem escreve bytes de arquivo — uploads entram pela tela/REST e o agente recebe
   só ids (Onda B).

## Consequências

**Positivas**
- Superfície do agente é enumerável e auditável: é a lista de tools do `studio/mcp/`.
- O agente não pode ser induzido (por texto do usuário ou de terceiros) a rodar comando de shell,
  editar arquivo ou disparar um workflow pesado.
- Isolado dos MCP/skills do usuário: mudanças na config global do Claude não afetam o assistente.

**Negativas / custos**
- O agente não pode fazer nada que não tenha virado tool — de propósito. Capacidade nova exige
  uma tool nova no catálogo (com seu gate), não uma permissão ampla.
- `--strict-mcp-config` significa que, no uso pelo terminal (Onda E), o usuário precisa apontar o
  `.mcp.json` do repo explicitamente; é o comportamento desejado (o Studio traz o próprio MCP).
