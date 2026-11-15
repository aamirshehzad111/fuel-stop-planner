PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help install data run test lint format

help: ## Show the available commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install: ## Create the virtualenv, install dependencies and migrate the database
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements-dev.txt
	$(BIN)/python manage.py migrate

data: ## Load the reference data into the database
	$(BIN)/python manage.py import_places

run: ## Start the development server on http://127.0.0.1:8000
	$(BIN)/python manage.py runserver

test: ## Run the test suite with coverage
	$(BIN)/pytest --cov --cov-report=term-missing:skip-covered

lint: ## Lint, check formatting and type-check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	$(BIN)/mypy .

format: ## Auto-fix lint issues and format the code
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .
