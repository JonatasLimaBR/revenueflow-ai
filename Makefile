PYTHON ?= python
COMPOSE ?= docker compose
DB_URL ?= postgresql://revenueflow:revenueflow@localhost:5432/revenueflow

.PHONY: help up down logs shell migrate seed run lint format typecheck test test-unit test-int test-sec test-ai check

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

up: ## Start the local stack (postgres, pubsub emulator, langfuse, app)
	$(COMPOSE) up -d --build

down: ## Stop the local stack and remove volumes
	$(COMPOSE) down -v

logs: ## Tail the app logs
	$(COMPOSE) logs -f app

shell: ## Open a shell in the app container
	$(COMPOSE) exec app sh

db-up: ## Start only postgres (for running tests locally)
	$(COMPOSE) up -d postgres

migrate: db-up ## Apply SQL migrations and LangGraph checkpoint setup
	DATABASE_URL=$(DB_URL) $(PYTHON) scripts/migrate.py

seed: migrate ## Load the simulated catalog / inventory / customer sales
	DATABASE_URL=$(DB_URL) $(PYTHON) scripts/seed.py

run: ## Run the API locally with autoreload
	DATABASE_URL=$(DB_URL) $(PYTHON) -m uvicorn revenueflow.main:app --reload

lint: ## Ruff lint + format check
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format: ## Apply ruff formatting and autofixes
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

typecheck: ## mypy (strict) on src
	$(PYTHON) -m mypy src

test: seed ## Full test suite against a local postgres
	DATABASE_URL=$(DB_URL) $(PYTHON) -m pytest -q

test-unit: seed ## Unit tests only
	DATABASE_URL=$(DB_URL) $(PYTHON) -m pytest -q tests/unit

test-int: seed ## Integration tests only
	DATABASE_URL=$(DB_URL) $(PYTHON) -m pytest -q tests/integration

test-sec: seed ## Security tests only
	DATABASE_URL=$(DB_URL) $(PYTHON) -m pytest -q tests/security

test-ai: seed ## AI eval tests only
	DATABASE_URL=$(DB_URL) $(PYTHON) -m pytest -q tests/ai_eval

check: lint typecheck test ## Everything the CI runs
	$(PYTHON) scripts/validate_docs.py
