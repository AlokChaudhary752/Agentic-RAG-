.PHONY: help install lint format typecheck test test-unit test-integration test-security up down clean eval demo

PYTHON := python
VENV_BIN := .venv/Scripts
RUFF := $(VENV_BIN)/ruff
MYPY := $(VENV_BIN)/mypy
PYTEST := $(VENV_BIN)/pytest

help:
	@echo "Enterprise Knowledge Agent - Management Commands"
	@echo "================================================"
	@echo "make install          Install Python dependencies"
	@echo "make lint             Run code linter (Ruff)"
	@echo "make format           Run code formatter (Ruff)"
	@echo "make typecheck        Run static type checker (Mypy)"
	@echo "make test             Run full test suite with coverage"
	@echo "make test-unit        Run unit tests only"
	@echo "make test-security    Run permission leak and security tests"
	@echo "make up               Start services with Docker Compose"
	@echo "make down             Stop Docker Compose services"
	@echo "make eval             Run RAGAS and golden set evaluation"
	@echo "make demo             Run the 5-minute interactive demo"

install:
	uv --no-config pip install --python $(VENV_BIN)/python.exe -e ".[dev]"

lint:
	$(RUFF) check backend evaluation mcp_servers scripts

format:
	$(RUFF) format backend evaluation mcp_servers scripts

typecheck:
	$(MYPY) backend/app

test:
	$(PYTEST) backend/tests --cov=backend/app --cov-report=term-missing --cov-report=html

test-unit:
	$(PYTEST) backend/tests/unit

test-integration:
	$(PYTEST) backend/tests/integration

test-security:
	$(PYTEST) backend/tests/security

up:
	docker compose up -d

down:
	docker compose down -v

clean:
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

eval:
	$(PYTHON) evaluation/run_eval.py

demo:
	$(PYTHON) scripts/demo.py

