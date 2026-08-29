#!/usr/bin/env bash
# Pré-voo de uma rodada de QA (skill qa-studio): toolchain, servidor isolado, fakes e git.
#
#   bash scripts/qa/check-env.sh <repo-dir> <run-id>
#
# Imprime PASS:/FAIL:/AVISO: por item e termina com "PRE-VOO OK" (exit 0) ou
# "PRE-VOO com N falha(s)" (exit 1). AVISO não conta como falha. A saída integral vai para a
# seção "Ambiente" do relatório.
set -uo pipefail
REPO="$(cd "${1:?uso: check-env.sh <repo-dir> <run-id>}" && pwd)"
RUN="$REPO/.qa/runs/${2:?uso: check-env.sh <repo-dir> <run-id>}"
fails=0
chk() { local n="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS: $n"; else echo "FAIL: $n"; fails=$((fails + 1)); fi; }
warn() { local n="$1"; shift; if "$@" >/dev/null 2>&1; then echo "PASS: $n"; else echo "AVISO: $n"; fi; }

PY="$REPO/.venv/bin/python"
chk "venv em $REPO/.venv" test -x "$PY"
chk "fastapi/uvicorn importáveis" "$PY" -c "import fastapi, uvicorn"
chk "playwright (python) importável" "$PY" -c "from playwright.sync_api import sync_playwright"
chk "Chromium do Playwright instalado" bash -c "ls -d \"\$HOME\"/.cache/ms-playwright/chromium-* >/dev/null"
chk "PIL importável (fakes/seed)" "$PY" -c "import PIL"
chk "ffmpeg no PATH" command -v ffmpeg
chk "ffprobe no PATH" command -v ffprobe
warn "newman no PATH (coleções Postman)" command -v newman
warn "gh autenticado (higiene de cards por PR)" gh auth status

if [[ -f "$RUN/env.sh" ]]; then
  # shellcheck disable=SC1090
  source "$RUN/env.sh"
  echo "INFO: run=$QA_RUN_ID modo=$QA_MODE base=$QA_BASE_URL"
  chk "servidor responde em $QA_BASE_URL/api/steps" curl -sf "$QA_BASE_URL/api/steps"
  chk "servidor serve o frontend (/)" bash -c "curl -sf '$QA_BASE_URL/' | grep -q '<html'"
  chk "STUDIO_PROJECTS isolado (fora de $REPO/projects)" test "$STUDIO_PROJECTS" != "$REPO/projects"
  if [[ "$QA_MODE" == offline ]]; then
    chk "fake higgsfield ativo no PATH" bash -c "command -v higgsfield | grep -q scripts/qa/fakes"
    chk "fake claude ativo no PATH" bash -c "command -v claude | grep -q scripts/qa/fakes"
    chk "fake higgsfield responde (account status)" bash -c "higgsfield account status --json | grep -q qa-fake"
    chk "servidor de mídia fake em $QA_FAKE_MEDIA_URL" curl -sf "$QA_FAKE_MEDIA_URL/"
    chk "API vê o CLI fake como logado" bash -c "curl -sf '$QA_BASE_URL/api/higgsfield/status?refresh=1' | grep -q '\"logged_in\": *true'"
  else
    echo "AVISO: modo REAL — gerações gastam crédito Higgsfield (HARD-GATE 2 da skill)"
    warn "higgsfield real logado" bash -c "higgsfield account status --json | grep -qv 'Not logged'"
  fi
else
  echo "FAIL: $RUN/env.sh não existe — rode stack-up.sh primeiro"; fails=$((fails + 1))
fi

if git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "INFO: git $(git -C "$REPO" branch --show-current) @ $(git -C "$REPO" rev-parse --short HEAD)"
  warn "árvore git limpa (alterações locais aparecem no diff da rodada)" bash -c "test -z \"\$(git -C '$REPO' status --porcelain --untracked-files=no)\""
fi

if [[ $fails -eq 0 ]]; then echo "PRE-VOO OK"; else echo "PRE-VOO com $fails falha(s)"; exit 1; fi
