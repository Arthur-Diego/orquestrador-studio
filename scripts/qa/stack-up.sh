#!/usr/bin/env bash
# Sobe o Orquestrador Studio num ambiente ISOLADO para uma rodada de QA (skill qa-studio).
#
#   bash scripts/qa/stack-up.sh <repo-dir> <run-id> [--real] [--restart]
#
# - Cria .qa/runs/<run-id>/ com projects/, moodboards/, state/, downloads/, fakes/, evidencias/
#   (nunca toca o projects/ real do repositório).
# - Modo offline (padrão): põe scripts/qa/fakes/ na frente do PATH → `higgsfield` e `claude`
#   viram fakes; sobe um servidor estático (python -m http.server) para servir a mídia fake.
# - --real: sem fakes (gasta crédito Higgsfield — HARD-GATE da skill).
# - Idempotente: se o servidor da rodada já responde, reaproveita; --restart derruba e sobe de novo
#   (usado na revalidação, para servir o código corrigido da worktree).
# - Escreve .qa/runs/<run-id>/env.sh (source para reproduzir o ambiente) e imprime o resumo.
set -uo pipefail

REPO="$(cd "${1:?uso: stack-up.sh <repo-dir> <run-id> [--real] [--restart]}" && pwd)"
RUN_ID="${2:?uso: stack-up.sh <repo-dir> <run-id> [--real] [--restart]}"
shift 2
MODE=offline; RESTART=0
for a in "$@"; do
  case "$a" in
    --real) MODE=real ;;
    --restart) RESTART=1 ;;
    *) echo "argumento desconhecido: $a" >&2; exit 2 ;;
  esac
done

RUN="$REPO/.qa/runs/$RUN_ID"
mkdir -p "$RUN"/{projects,moodboards,state,downloads,fakes,evidencias}
VENV="$REPO/.venv"
[[ -x "$VENV/bin/python" ]] || { echo "FAIL: $VENV não existe — rode 'make setup' em $REPO" >&2; exit 1; }

alive() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }
free_port() {  # primeira porta livre a partir de $1
  local p="$1"
  while "$VENV/bin/python" - "$p" <<'PY'; do p=$((p + 1)); done
import socket, sys
s = socket.socket(); s.settimeout(0.2)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PY
  echo "$p"
}

# ---- reaproveitar ou derrubar ----
if [[ -f "$RUN/env.sh" ]] && alive "$RUN/server.pid"; then
  # shellcheck disable=SC1090
  source "$RUN/env.sh"
  if [[ $RESTART -eq 0 ]] && curl -sf "$QA_BASE_URL/api/steps" >/dev/null; then
    echo "server já no ar: $QA_BASE_URL (pid $(cat "$RUN/server.pid"), modo $QA_MODE) — reaproveitando"
    exit 0
  fi
  echo "derrubando servidor anterior (pid $(cat "$RUN/server.pid"))"
  kill "$(cat "$RUN/server.pid")" 2>/dev/null; sleep 1
fi
alive "$RUN/media.pid" && { kill "$(cat "$RUN/media.pid")" 2>/dev/null; sleep 0.5; }

# ---- portas e ambiente ----
PORT="${QA_PORT:-$(free_port 8790)}"
MPORT="$(free_port $((PORT + 1)))"
FAKES="$REPO/scripts/qa/fakes"
chmod +x "$FAKES"/* 2>/dev/null
if [[ $MODE == offline ]]; then
  QA_PATH="$VENV/bin:$FAKES:$PATH"
else
  QA_PATH="$VENV/bin:$PATH"
fi

cat > "$RUN/env.sh" <<EOF
# gerado por stack-up.sh — source este arquivo para reproduzir o ambiente da rodada $RUN_ID
export QA_RUN_ID="$RUN_ID"
export QA_RUN_DIR="$RUN"
export QA_REPO="$REPO"
export QA_MODE="$MODE"
export QA_BASE_URL="http://127.0.0.1:$PORT"
export QA_FAKE_DIR="$RUN/fakes"
export QA_FAKE_MEDIA_URL="http://127.0.0.1:$MPORT"
export PORT="$PORT"
export STUDIO_PROJECTS="$RUN/projects"
export STUDIO_MOODBOARDS="$RUN/moodboards"
export STUDIO_STATE="$RUN/state"
export STUDIO_DOWNLOADS="$RUN/downloads"
export PATH="$QA_PATH"
EOF
# shellcheck disable=SC1090
source "$RUN/env.sh"

# ---- servidor de mídia fake (offline) ----
# Espera de readiness no MESMO padrão do Studio (abaixo). Sem ela o script seguia direto para o
# pré-voo e o `check-env.sh` batia num socket que ainda não escutava: FAIL a frio, PASS a quente —
# corrida clássica, e o único item do pré-voo que dependia da ordem de agendamento do SO.
if [[ $MODE == offline ]]; then
  ( cd "$RUN/fakes" && exec "$VENV/bin/python" -m http.server "$MPORT" --bind 127.0.0.1 ) \
    >"$RUN/media.log" 2>&1 &
  echo $! > "$RUN/media.pid"
  media_ok=0
  for _ in $(seq 1 30); do
    if curl -sf "$QA_FAKE_MEDIA_URL/" >/dev/null; then media_ok=1; break; fi
    alive "$RUN/media.pid" || { echo "FAIL: servidor de mídia fake morreu — veja $RUN/media.log" >&2; tail -20 "$RUN/media.log" >&2; exit 1; }
    sleep 1
  done
  [[ $media_ok -eq 1 ]] || { echo "FAIL: servidor de mídia fake não respondeu em 30 s — veja $RUN/media.log" >&2; exit 1; }
  echo "mídia fake no ar: $QA_FAKE_MEDIA_URL (pid $(cat "$RUN/media.pid"))"
fi

# ---- Studio ----
( cd "$REPO" && exec "$VENV/bin/uvicorn" studio.app:app --host 127.0.0.1 --port "$PORT" ) \
  >"$RUN/server.log" 2>&1 &
echo $! > "$RUN/server.pid"

for _ in $(seq 1 60); do
  if curl -sf "$QA_BASE_URL/api/steps" >/dev/null; then
    echo "server no ar: $QA_BASE_URL (pid $(cat "$RUN/server.pid"), modo $MODE, repo $REPO)"
    echo "env: source $RUN/env.sh"
    exit 0
  fi
  alive "$RUN/server.pid" || { echo "FAIL: uvicorn morreu — veja $RUN/server.log" >&2; tail -20 "$RUN/server.log" >&2; exit 1; }
  sleep 1
done
echo "FAIL: servidor não respondeu em 60 s — veja $RUN/server.log" >&2
exit 1
