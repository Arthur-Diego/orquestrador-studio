# ADR-037: Servidor MCP do Studio como cliente HTTP da própria API

**Status:** Aceito
**Data:** 2026-09-05
**Task-Id:** ADH-OS-20260905-04
**ADRs relacionados:** [ADR-001](./ADR-001-monolito-single-process-sem-autenticacao-bind-loopback.md), [ADR-006 (jobs em memória + polling)](./ADR-006-jobs-assincronos-em-threads-com-estado-em-memoria-e-polling.md), [ADR-010 (guia por leitura pura)](./ADR-010-guia-por-etapa-por-leitura-pura-e-nucleo-editavel-so-pelo-preparo-shell.md), [ADR-016 (créditos e custos)](./ADR-016-gestao-de-creditos-custos-e-modelo-default-por-acao.md), [ADR-036](./ADR-036-runtime-de-chat-via-claude-cli-em-processo-terceiro-modo.md), [ADR-038](./ADR-038-protocolo-humano-no-laco-do-chat.md)

## Contexto e Problema

O assistente (ADR-036) precisa **agir** no Studio: buscar referências, gerar mood, ler o guia,
disparar o motor local, etc. O padrão para expor ações a um agente do Claude é um **servidor MCP**.
A pergunta é *como* o MCP toca o Studio: importando os serviços das etapas (`studio.<etapa>.service`)
ou falando com a API HTTP que já existe?

Importar os serviços tem um defeito fatal: o estado dos jobs vive **em memória do processo do
servidor** (ADR-006, um `JobRegistry` por processo). Um MCP que importasse os serviços rodaria num
processo separado (o subprocess que o `claude` lança), com um `JobRegistry` próprio: a tela nunca
veria o job que o agente iniciou, o guia (ADR-010) não reconciliaria, e o gate de custo da UI
(ADR-016) seria contornado por um caminho paralelo.

## Decisão

**O servidor MCP do Studio (`studio/mcp/`, `python -m studio.mcp`) é um cliente HTTP da própria
API, em loopback.** Nunca importa os serviços das etapas.

1. **Um servidor stdio, dois consumidores.** O MESMO `python -m studio.mcp` serve (a) o chat
   embutido — o runtime o passa em `--mcp-config` — e (b) um terminal `claude` comum, via
   `.mcp.json` do repositório (Onda E). Não há "dois adaptadores": há um servidor e dois jeitos de
   lançá-lo.
2. **Cliente HTTP fino (`client.py`).** `StudioClient` fala `http://127.0.0.1:<PORT>` (env
   `STUDIO_URL`/`PORT`). Erros HTTP viram mensagem acionável (o 409 do gate de login vira o próprio
   texto da instrução), nunca stack. `runner` injetável para teste sem rede.
3. **Fonte única de estado.** Como o agente age pelas MESMAS rotas das telas, ele herda por
   construção: gate de login 409, `cost` antes de `generate`, um job por projeto, prontidão do guia.
   Não existe caminho alternativo para "inventar método" (ADR-004).
4. **Catálogo curado, não 1:1 com as rotas.** As 216 rotas não viram 216 tools (contexto de tool é
   caro). Tools de alto nível por domínio + transversais (`guide`, `job`, `doctor`, `api_get`
   somente-GET). Respostas compactas (ids, thumbs, `next_action`), nunca JSON bruto.
5. **Tools puras testáveis (`tools.py`).** Cada tool é uma função `(client, …) -> str|dict`; o
   `server.py` (FastMCP) só as registra. Os testes chamam as funções com um cliente fake (ADR-008).
6. **Guarda de drift (Onda A→E).** O catálogo declara as rotas que consome; um teste cruza o
   manifesto com o `/openapi.json` publicado e falha se a rota sumiu ou mudou de método.

Onda A entrega as tools de **leitura** (`projects`, `project`, `guide`, `guide_step`, `steps`,
`doctor`, `job`, `api_get`). As de ação e `ui.*` somam a este mesmo servidor na Onda B.

## Consequências

**Positivas**
- Uma fonte de estado: o que o agente faz aparece nas telas e no livro-caixa.
- O mesmo servidor serve chat e terminal — sem código duplicado.
- Isolamento de teste trivial (cliente fake), sem Studio no ar.

**Negativas / custos**
- Um salto HTTP a mais por tool (loopback, custo desprezível).
- O MCP depende de o Studio estar no ar; ausente, a tool devolve uma mensagem "suba o Studio".
- `mcp` (FastMCP) fixado em `<2` — a 2.x renomeou `FastMCP` para `MCPServer`; a 1.x é a API usada
  e comprovada no ecossistema local (`local_ai_engine`).
