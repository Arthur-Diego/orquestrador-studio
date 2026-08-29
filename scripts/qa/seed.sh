#!/usr/bin/env bash
# Popula o ambiente isolado de uma rodada de QA (skill qa-studio).
#
#   bash scripts/qa/seed.sh <repo-dir> <run-id>
#
# Cria, no STUDIO_PROJECTS/STUDIO_MOODBOARDS da rodada:
#   - pid_cheio: campanha com as 10 etapas populadas (scripts/e2e_pipeline.py --populate-only,
#     fixtures sintéticas, sem rede);
#   - pid_vazio: campanha recém-criada (estados vazios, wizard, gate da prospecção);
#   - mbid: um mood board na biblioteca global com 3 imagens candidatas.
# Grava .qa/runs/<run-id>/seed.json com os ids. Idempotente (recria o que já existir).
set -euo pipefail
REPO="$(cd "${1:?uso: seed.sh <repo-dir> <run-id>}" && pwd)"
RUN="$REPO/.qa/runs/${2:?uso: seed.sh <repo-dir> <run-id>}"
[[ -f "$RUN/env.sh" ]] || { echo "FAIL: $RUN/env.sh não existe — rode stack-up.sh primeiro" >&2; exit 1; }
# shellcheck disable=SC1090
source "$RUN/env.sh"
PY="$REPO/.venv/bin/python"

# 0) estado limpo — os diretórios são da rodada (isolados), então apagar tudo é seguro. Sem isto,
#    campanhas criadas por casos anteriores contaminam agregados globais (portfólio, gate da
#    prospecção) e o seed cheio deixa de ser determinístico.
find "$STUDIO_PROJECTS" "$STUDIO_MOODBOARDS" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true

# 1) campanha cheia — o e2e_pipeline usa TestClient em processo, escrevendo no mesmo
#    STUDIO_PROJECTS que o servidor lê do disco.
( cd "$REPO" && "$PY" scripts/e2e_pipeline.py --populate-only ) > "$RUN/seed-e2e.log" 2>&1 \
  || { echo "FAIL: e2e_pipeline --populate-only falhou — veja $RUN/seed-e2e.log" >&2; tail -20 "$RUN/seed-e2e.log" >&2; exit 1; }
PID_CHEIO="$(cd "$REPO" && "$PY" - <<'PY'
from datetime import date
from studio.refs.service import slugify
print(f"{date.today():%Y-%m}-{slugify('E2E Mock')}")
PY
)"

# 2) campanha vazia
rm -rf "$STUDIO_PROJECTS"/*-qa-vazia
PID_VAZIO="$(curl -sf -X POST "$QA_BASE_URL/api/projects" -H 'content-type: application/json' \
  -d '{"name":"QA Vazia","product":"produto de teste","vibe":""}' | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["id"])')"

# 3) mood board na biblioteca com 3 candidatas
rm -rf "$STUDIO_MOODBOARDS"/qa-board
MBID="$(curl -sf -X POST "$QA_BASE_URL/api/moodboards" -H 'content-type: application/json' \
  -d '{"name":"QA Board","note":"seed do qa-studio"}' | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
"$PY" - "$RUN" <<'PY'
import sys
from pathlib import Path
from PIL import Image
out = Path(sys.argv[1]) / "seed-imgs"; out.mkdir(exist_ok=True)
for i, c in enumerate([(200, 60, 60), (60, 200, 120), (60, 90, 200)]):
    Image.new("RGB", (640, 400), c).save(out / f"vibe{i + 1}.png", "PNG")
PY
curl -sf -X POST "$QA_BASE_URL/api/moodboards/$MBID/import/upload" \
  -F "files=@$RUN/seed-imgs/vibe1.png" -F "files=@$RUN/seed-imgs/vibe2.png" -F "files=@$RUN/seed-imgs/vibe3.png" >/dev/null

cat > "$RUN/seed.json" <<EOF
{"pid_cheio": "$PID_CHEIO", "pid_vazio": "$PID_VAZIO", "mbid": "$MBID"}
EOF
echo "seed ok: pid_cheio=$PID_CHEIO pid_vazio=$PID_VAZIO mbid=$MBID → $RUN/seed.json"
