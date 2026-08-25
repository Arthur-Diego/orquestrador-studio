---
name: cy-trello-mcp
description: Usa o MCP do Trello para consultar boards, listas, cards, membros, labels, checklists, anexos e comentarios, e para executar operacoes como criar card, atualizar card, mover card, comentar e criar lista. Use quando o usuario quiser ler informacoes de um board, localizar cards, acompanhar trabalho, organizar backlog ou operar o Trello a partir do Claude Code, Codex ou outro cliente MCP compativel. Nao use para implementar o servidor MCP do Trello nem para prometer acesso ao Trello quando as tools ainda nao estiverem carregadas no runtime.
---

# Trello MCP

Usar o MCP do Trello como camada de operacao e leitura do workspace Trello do usuario.

<HARD-GATE>
Antes de agir sobre o Trello:
1. verificar se as tools do Trello estao disponiveis no runtime atual;
2. se nao estiverem, orientar a ativacao do MCP em vez de fingir acesso;
3. para operacoes de escrita, confirmar alvo quando board, lista ou card nao forem inequivocos;
4. para boards grandes, evitar buscar "tudo" de uma vez sem necessidade.
</HARD-GATE>

## Resultado esperado

Permitir que o agente:

- leia boards, listas, cards e metadados do Trello;
- resuma boards de forma util e rastreavel;
- procure itens por nome, conteudo, membro ou contexto;
- execute acoes seguras de criacao, atualizacao, movimentacao e comentario;
- oriente a ativacao do MCP quando o runtime ainda nao tiver as tools carregadas.

## Fontes locais

Usar estes materiais do workspace quando precisar entender capacidades, limites ou ativacao:

1. `codebase/trello-desktop-mcp/README.md`
2. `codebase/trello-desktop-mcp/wiki/Available-Tools.md`
3. `codebase/trello-desktop-mcp/wiki/Best-Practices.md`
4. `codebase/trello-desktop-mcp/wiki/Installation-Guide.md`
5. `codebase/trello-desktop-mcp/wiki/Troubleshooting.md`, apenas quando houver falha

## Workflow

1. Descobrir disponibilidade.
   - Verificar se o runtime atual expoe tools do Trello.
   - Procurar nomes como:
     - `trello_search`
     - `trello_get_user_boards`
     - `get_board_details`
     - `get_card`
     - `create_card`
     - `update_card`
     - `move_card`
     - `trello_add_comment`
     - `trello_get_list_cards`
     - `trello_create_list`
     - `trello_get_board_cards`
     - `trello_get_card_actions`
     - `trello_get_card_attachments`
     - `trello_get_card_checklists`
     - `trello_get_board_members`
     - `trello_get_board_labels`
     - `trello_get_member`
   - Se as tools existirem, seguir para operacao.
   - Se nao existirem, seguir para ativacao guiada.

2. Ativacao guiada quando necessario.
   - Explicar com clareza que o agente ainda nao tem acesso ao Trello neste runtime.
   - Para Claude Code, orientar a configuracao do MCP usando o servidor local em `codebase/trello-desktop-mcp/dist/index.js`.
   - Para Codex ou outro cliente MCP compativel, orientar a configuracao do runtime para executar `node <caminho-absoluto>/dist/index.js` com `TRELLO_API_KEY` e `TRELLO_TOKEN`.
   - Nunca inventar que a conexao foi realizada se o runtime nao expuser as tools.
   - Se o usuario pedir ajuda de configuracao, usar `references/activation-template.md`.

3. Leitura e descoberta.
   - Para entender o workspace, comecar por `trello_get_user_boards`.
   - Quando o usuario mencionar um board por nome, usar busca ou listagem para resolver o board correto antes de detalhar.
   - Para overview de board, preferir:
     - identificar o board;
     - buscar detalhes do board;
     - complementar com membros, labels ou cards somente se isso responder a pergunta.
   - Para encontrar cards ou conteudo difuso, preferir `trello_search`.
   - Para cards especificos, usar `get_card` e depois ferramentas complementares como actions, attachments ou checklists quando fizer sentido.

4. Escrita segura.
   - Antes de criar card, confirmar lista destino se houver ambiguidade.
   - Antes de mover card, confirmar card e lista destino se houver mais de uma correspondencia plausivel.
   - Antes de atualizar card, deixar explicito o que sera alterado.
   - Antes de comentar, validar o card alvo.
   - Para multiplas acoes relacionadas, executar em ordem logica e relatar o resultado de cada uma.

5. Resposta ao usuario.
   - Para leitura de boards, devolver informacoes organizadas, por exemplo:
     - nome do board;
     - listas encontradas;
     - quantidade de cards, quando disponivel;
     - cards relevantes, quando pedidos;
     - membros, labels ou alertas, quando pedidos.
   - Para escrita, confirmar o resultado objetivo:
     - card criado;
     - card atualizado;
     - card movido;
     - comentario adicionado;
     - lista criada.
   - Se a operacao falhar, informar a causa conhecida e o proximo passo util.

## Padrões recomendados

- Para boards grandes, responder primeiro com resumo e depois oferecer aprofundamento.
- Para busca, usar consultas especificas em vez de "procure tudo".
- Para operacoes encadeadas, reaproveitar o contexto do board e do card ja resolvidos.
- Para analises, diferenciar fatos do board de inferencias do agente.
- Para cards e boards privados, lembrar que a visibilidade depende das permissoes do token configurado.

## Anti-padroes

Nao fazer:

- prometer acesso ao Trello sem tools carregadas;
- despejar todos os cards de boards grandes sem necessidade;
- executar escrita em alvo ambiguo;
- assumir que nome parcial identifica um unico board ou card;
- tratar guia de instalacao como se fosse execucao real da conexao.

Fazer:

- verificar disponibilidade das tools antes de qualquer promessa;
- usar a tool mais especifica para cada operacao;
- resumir boards grandes em vez de inundar a resposta;
- confirmar destino em alteracoes sensiveis;
- usar a documentacao local para ativacao e troubleshooting.

## Referencias

- Para ativacao: ler `references/activation-template.md`
- Para mapeamento rapido de ferramentas: ler `references/tool-playbook.md`
