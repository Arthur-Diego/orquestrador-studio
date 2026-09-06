"""`[extensão]` Assistente de chat do Orquestrador Studio (ADR-036).

Terceiro modo de falar com o Claude no Studio, irmão do `common/prompter.py` (bot de prompts) e
do `common/skill_runner.py` (corrida de skill): um **chat multi-turno** que conduz a criação de
conteúdo do início ao fim e executa as ações das etapas pelas tools do MCP (`studio/mcp/`).

Como os dois irmãos, usa o **CLI `claude` com a assinatura do usuário** — nunca chave de API. Cada
turno é um `claude -p <msg> --resume <sid> --output-format stream-json --mcp-config <studio>.json`;
os eventos do stream (texto, tool_use, tool_result, resultado) são transmitidos ao browser por
WebSocket e persistidos em `STATE_DIR/chats/<id>/events.jsonl`.

Módulos:
- `sessions.py`  — store das abas de chat (meta + transcript), persistência em arquivo (ADR-003).
- `runtime.py`   — monta o argv, roda o turno como subprocess e normaliza o stream-json.
- `uibridge.py`  — ponte humano-no-laço (`ui.*`): Futures resolvidas pela resposta do browser.
- `router.py`    — REST das abas + WebSocket `/ws/chat/{id}` + endpoints internos do MCP.
"""
