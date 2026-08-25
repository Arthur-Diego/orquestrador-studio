# Ativacao do Trello MCP

Usar este guia quando o runtime atual nao expuser as tools do Trello.

## Regra principal

- Se as tools do Trello nao estiverem carregadas, nao fingir acesso.
- Explicar que a skill depende do MCP do Trello estar configurado e ativo no cliente atual.

## Claude Code

Orientar o usuario a registrar o servidor local com um comando no formato:

```bash
claude mcp add trello -- node C:\caminho\absoluto\para\trello-desktop-mcp\dist\index.js ^
  -e TRELLO_API_KEY=seu-api-key ^
  -e TRELLO_TOKEN=seu-token
```

Depois orientar:

1. reiniciar a sessao do Claude Code;
2. pedir uma verificacao simples, como listar boards;
3. confirmar que as tools ficaram disponiveis.

## Codex ou outro cliente MCP compativel

Orientar o usuario a configurar o runtime para:

1. executar `node <caminho-absoluto>/trello-desktop-mcp/dist/index.js`;
2. injetar `TRELLO_API_KEY` e `TRELLO_TOKEN`;
3. reiniciar o cliente;
4. validar com uma leitura simples de boards.

## Credenciais

Orientar a obtencao de credenciais em:

- `https://trello.com/app-key`

Permissoes esperadas:

- leitura para consultar boards, listas e cards;
- escrita para criar, mover, atualizar cards, listas e comentarios;
- token sem expiracao, quando o usuario quiser uso continuo.

## Verificacao minima

Depois da ativacao, o teste mais simples e:

- listar boards do usuario;
- abrir um board especifico;
- opcionalmente criar um card de teste.
