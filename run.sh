#!/usr/bin/env bash
# Sobe o Orquestrador Studio em http://127.0.0.1:8765
cd "$(dirname "$0")"
. .venv/bin/activate
exec uvicorn studio.app:app --host 127.0.0.1 --port "${PORT:-8765}" "$@"
