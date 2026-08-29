#!/usr/bin/env bash
# Derruba o servidor de uma rodada de QA (skill qa-studio).
#
#   bash scripts/qa/stack-down.sh <repo-dir> <run-id> [--purge]
#
# --purge apaga .qa/runs/<run-id>/ inteiro (prints, logs, projetos sintéticos). Sem --purge os
# artefatos ficam para o relatório e para a revalidação.
set -uo pipefail
REPO="$(cd "${1:?uso: stack-down.sh <repo-dir> <run-id> [--purge]}" && pwd)"
RUN="$REPO/.qa/runs/${2:?uso: stack-down.sh <repo-dir> <run-id> [--purge]}"

for name in server media; do
  pidfile="$RUN/$name.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    kill "$(cat "$pidfile")" 2>/dev/null && echo "$name parado (pid $(cat "$pidfile"))"
  fi
  rm -f "$pidfile"
done
if [[ "${3:-}" == "--purge" ]]; then
  rm -rf "$RUN" && echo "removido: $RUN"
fi
