# Playbook de tools do Trello MCP

Usar este playbook para escolher a tool certa sem reler toda a documentacao.

## Descoberta

- `trello_get_user_boards`: listar boards acessiveis
- `trello_search`: procurar boards, cards, membros e conteudos

## Boards

- `get_board_details`: obter detalhes de um board
- `get_lists`: obter listas do board
- `trello_get_board_cards`: obter cards de um board
- `trello_get_board_members`: obter membros do board
- `trello_get_board_labels`: obter labels do board

## Cards

- `get_card`: obter detalhes completos de um card
- `create_card`: criar card
- `update_card`: atualizar card
- `move_card`: mover card entre listas
- `trello_get_card_actions`: historico de acoes
- `trello_get_card_attachments`: anexos
- `trello_get_card_checklists`: checklists

## Listas e comentarios

- `trello_get_list_cards`: cards de uma lista
- `trello_create_list`: criar lista
- `trello_add_comment`: comentar em card

## Membros

- `trello_get_member`: detalhes de membro

## Sequencias comuns

### Ler um board

1. listar ou buscar boards;
2. resolver o board correto;
3. usar `get_board_details`;
4. complementar com cards, membros ou labels apenas se necessario.

### Encontrar um card e agir nele

1. buscar card ou board;
2. resolver o card correto;
3. usar `get_card`;
4. atualizar, mover ou comentar.

### Criar trabalho novo

1. resolver board e lista destino;
2. criar card com titulo e descricao claros;
3. se pedido, atribuir membros, labels e data;
4. se pedido, comentar contexto inicial.
