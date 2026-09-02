#!/usr/bin/env bash
# Registra o servidor MCP do Trello no Claude Code (escopo user).
#
# Segredos NUNCA ficam neste arquivo nem no repositório: eles vivem em
#   ~/.config/orquestrador-studio/trello.env   (chmod 600, fora do git)
#
# Uso:
#   1. gere o token de API (o script mostra a URL se TRELLO_TOKEN estiver vazio)
#   2. cole o token no trello.env
#   3. ./scripts/trello-mcp-setup.sh
set -euo pipefail

ENV_FILE="${TRELLO_ENV_FILE:-$HOME/.config/orquestrador-studio/trello.env}"
SERVER_NAME="${TRELLO_MCP_NAME:-trello}"

[ -f "$ENV_FILE" ] || { echo "erro: $ENV_FILE não existe"; exit 1; }
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

: "${TRELLO_API_KEY:?TRELLO_API_KEY vazio em $ENV_FILE}"

if [ -z "${TRELLO_TOKEN:-}" ]; then
  cat <<MSG
TRELLO_TOKEN está vazio — sem ele a API não autentica (key sozinha devolve 400 "invalid token").

Abra esta URL no navegador, autorize, e cole o token em $ENV_FILE:

https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&name=orquestrador-studio&key=$TRELLO_API_KEY

Depois rode este script de novo.
MSG
  exit 2
fi

echo "==> validando credenciais na API do Trello"
code=$(curl -s -o /dev/null -w "%{http_code}" \
  "https://api.trello.com/1/members/me?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN")
[ "$code" = "200" ] || { echo "erro: Trello devolveu HTTP $code — key/token inválidos"; exit 1; }
echo "    ok (HTTP 200)"

echo "==> registrando o servidor MCP '$SERVER_NAME' (escopo user)"
claude mcp remove "$SERVER_NAME" --scope user >/dev/null 2>&1 || true
claude mcp add "$SERVER_NAME" --scope user \
  -e "TRELLO_API_KEY=$TRELLO_API_KEY" \
  -e "TRELLO_TOKEN=$TRELLO_TOKEN" \
  ${TRELLO_BOARD_ID:+-e "TRELLO_BOARD_ID=$TRELLO_BOARD_ID"} \
  -- npx -y @delorenj/mcp-server-trello

echo "==> pronto. Confira com: claude mcp list"
echo "    Reinicie a sessão do Claude Code para as tools aparecerem."
