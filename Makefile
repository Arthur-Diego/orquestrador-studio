.PHONY: help setup hooks run test lint verify frontend-setup frontend-verify frontend-build frontend-schema frontend-schema-check qa-up qa-seed qa-run qa-api qa-down

help: ## Lista os alvos
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n", $$1, $$2}'

setup: ## Cria o venv e instala dependências (dev incluído)
	python3 -m venv .venv
	. .venv/bin/activate && pip install -q --upgrade pip && pip install -q -r requirements-dev.txt
	@echo "Se não houver Chromium em ~/.cache/ms-playwright: . .venv/bin/activate && playwright install chromium"

hooks: ## Instala os git hooks do repositório (.githooks)
	git config core.hooksPath .githooks
	@echo "Hooks instalados (core.hooksPath=.githooks)"

run: ## Sobe o Studio em http://127.0.0.1:8765
	./run.sh

test: ## Roda a suíte de testes
	. .venv/bin/activate && pytest

lint: ## Lint com ruff
	. .venv/bin/activate && ruff check studio tests scripts

verify: lint test ## Lint + testes Python (o job `build-and-test` do CI)

# ---- frontend React (Wave 10, ADR-031). Paralelo ao Python: `verify` NÃO depende de Node ----
# Node não é pré-requisito para rodar a ferramenta (o `dist/` é versionado a partir da E10), então
# o alvo é separado de propósito — quem só mexe em Python nunca precisa instalar npm.
frontend-setup: ## Instala as dependências do frontend (npm ci)
	cd frontend && npm ci
frontend-verify: ## Typecheck + lint + testes do frontend (o job `frontend` do CI)
	cd frontend && npm run typecheck && npm run lint && npm test
frontend-build: ## Constrói o bundle em studio/web/dist/
	cd frontend && npm run build

# Contrato tipado da API (Wave 10, E1 — card [REACT-02]). O `schema.ts` é GERADO do `/openapi.json`
# que o FastAPI publica; regenerar exige Python (para despejar o contrato) e Node (para tipá-lo).
frontend-schema: ## Regenera frontend/src/api/schema.ts a partir do /openapi.json do app
	. .venv/bin/activate && python scripts/gen_openapi.py
	cd frontend && npm run schema:gen
frontend-schema-check: ## Falha se o schema.ts versionado divergir do /openapi.json (guarda de drift)
	. .venv/bin/activate && python scripts/gen_openapi.py
	cd frontend && npm run schema:check

# ---- QA E2E fora do CI (skill qa-studio, ADR-008). RUN=<run-id> (padrão: local) ----
RUN ?= local
qa-up: ## Sobe o Studio isolado com fakes em .qa/runs/$(RUN) e faz o pré-voo
	bash scripts/qa/stack-up.sh . $(RUN) && bash scripts/qa/check-env.sh . $(RUN)
qa-seed: ## Popula campanha cheia + vazia + mood board na rodada $(RUN)
	bash scripts/qa/seed.sh . $(RUN)
qa-run: ## Roda os cenários Playwright (TELAS="refs mood" para filtrar)
	. .qa/runs/$(RUN)/env.sh && .venv/bin/python scripts/qa/run.py --run $(RUN) $(if $(TELAS),--telas $(TELAS),)
qa-api: ## Auditoria de API (OpenAPI + contratos + newman) da rodada $(RUN)
	. .qa/runs/$(RUN)/env.sh && .venv/bin/python scripts/qa/api_audit.py --run $(RUN)
qa-down: ## Derruba o servidor da rodada $(RUN) (PURGE=1 apaga os artefatos)
	bash scripts/qa/stack-down.sh . $(RUN) $(if $(PURGE),--purge,)
