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
# O Chromium é provado por LAUNCH, não por caminho: o diretório de instalação do Playwright muda
# por SO (`~/.cache/ms-playwright` no Linux, `~/Library/Caches/ms-playwright` no macOS) e ainda pode
# ser redirecionado por `PLAYWRIGHT_BROWSERS_PATH`. Checar caminho dava falso negativo 100% das
# vezes no macOS com o browser instalado e funcional. Quem sobe o navegador é o próprio Playwright:
# se ele abre, o pré-voo está provado; se não abre, o motivo real aparece no stderr.
CHROMIUM_VER="$("$PY" - <<'PY' 2>/dev/null
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    print(b.version)
    b.close()
PY
)"
if [[ -n "$CHROMIUM_VER" ]]; then
  echo "PASS: Chromium do Playwright sobe (v$CHROMIUM_VER)"
else
  echo "FAIL: Chromium do Playwright sobe (rode: $PY -m playwright install chromium)"; fails=$((fails + 1))
fi
chk "PIL importável (fakes/seed)" "$PY" -c "import PIL"
chk "ffmpeg no PATH" command -v ffmpeg
chk "ffprobe no PATH" command -v ffprobe
# `newman` é devDependency de `frontend/` (ADR-031): sem Node global ele vem do node_modules local.
warn "newman disponível (PATH ou frontend/node_modules)" bash -c \
  "command -v newman >/dev/null || test -x '$REPO/frontend/node_modules/.bin/newman'"
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
