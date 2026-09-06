#!/usr/bin/env bash
# Sobe o Orquestrador Studio em http://127.0.0.1:8765
cd "$(dirname "$0")"

# `[extensão]` Wave 11 · F06 — PATH determinístico para o Claude CLI.
# Causa: subir o Studio fora de um shell interativo (Finder, um atalho, launchd) chega aqui com o
# PATH curto do sistema, sem `~/.local/bin`. Aí `shutil.which("claude")` falha no import do
# `studio.common.prompter`, o roteiro nasce sem CLI e nem reabrir a aba resolve.
# Os diretórios de binário do usuário são ACRESCENTADOS DEPOIS do PATH herdado, nunca antes: um
# `claude` que o usuário já tem no PATH continua ganhando, e o Studio não troca silenciosamente o
# binário dele (FDD §10, Risco 6). O diagnóstico da tela mostra o `path` que venceu.
for _d in "$HOME/.local/bin" "$HOME/bin" "$HOME/.bun/bin" "/opt/homebrew/bin" "/usr/local/bin"; do
  case ":$PATH:" in
    *":$_d:"*) ;;             # já está no PATH (na posição que o usuário escolheu): não mexe
    # `${PATH:+...}` evita o dois-pontos INICIAL quando o PATH herdado vem vazio (o caso do
    # `env -i`, justamente o que este bloco existe para cobrir): elemento vazio de PATH é o
    # DIRETÓRIO ATUAL no POSIX, e a linha 3 já fez `cd` para a raiz do repositório.
    *) PATH="${PATH:+$PATH:}$_d" ;;
  esac
done
export PATH

. .venv/bin/activate
exec uvicorn studio.app:app --host 127.0.0.1 --port "${PORT:-8765}" "$@"
