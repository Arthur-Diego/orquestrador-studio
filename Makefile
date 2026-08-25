.PHONY: help setup hooks run test lint verify

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
	. .venv/bin/activate && ruff check studio tests

verify: lint test ## Lint + testes (o que o CI roda)
