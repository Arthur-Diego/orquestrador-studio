"""`[extensão]` Servidor MCP do Studio (ADR-037).

Um único servidor MCP **stdio** (`python -m studio.mcp`) que expõe as ações do Studio como
tools de um agente do Claude. Ele NÃO importa os serviços das etapas: fala com o Studio pela
**API HTTP em loopback** (`studio/mcp/client.py`), a mesma que o frontend usa. Assim há uma
única fonte de estado (o processo do servidor, com seu `JobRegistry` em memória — ADR-006), o
guia se reconcilia e o gate de custo (ADR-016) vale por construção.

O mesmo binário serve os dois consumidores da ADR-037:
- o **chat embutido** (`studio/chat/runtime.py`), que lança `claude -p ... --mcp-config`;
- um **terminal** `claude` comum, via `.mcp.json` do repositório.

As tools puras vivem em `studio/mcp/tools.py` (testáveis com um cliente fake); `server.py` as
registra num `FastMCP`. Config por env, lida no processo do MCP (nunca em `config.py`, núcleo):
  STUDIO_URL        base da API do Studio (default http://127.0.0.1:8765)
  STUDIO_CHAT_ID    id da aba de chat que lançou o MCP (habilita as tools `ui.*`; ausente no
                    terminal, onde `ui.*` degrada para "pergunte em texto")
"""
