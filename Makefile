.PHONY: help lint format type-check test install dev-install clean

help:
	@echo "Available commands:"
	@echo "  make install       - Install migsafe"
	@echo "  make dev-install   - Install migsafe with dev dependencies"
	@echo "  make lint          - Run all linters (ruff, mypy, bandit)"
	@echo "  make format        - Format code with ruff"
	@echo "  make type-check    - Run type checks with mypy"
	@echo "  make test          - Run tests"
	@echo "  make clean         - Clean temporary files"

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

lint: lint-ruff lint-mypy lint-bandit

lint-ruff:
	@echo "🔍 Checking code with ruff..."
	ruff check migsafe tests
	ruff format --check migsafe tests

lint-mypy:
	@echo "🔍 Type checking with mypy..."
	mypy migsafe --ignore-missing-imports --no-strict-optional || true

lint-bandit:
	@echo "🔍 Security checking with bandit..."
	bandit -r migsafe -c .bandit || true

format:
	@echo "✨ Formatting code with ruff..."
	ruff format migsafe tests
	ruff check --fix migsafe tests

type-check:
	@echo "🔍 Type checking..."
	mypy migsafe --ignore-missing-imports

test:
	@echo "🧪 Running tests..."
	pytest tests/ -v --cov=migsafe --cov-report=term --cov-report=html

test-fast:
	@echo "🧪 Running tests (fast)..."
	pytest tests/ -v

clean:
	@echo "🧹 Cleaning temporary files..."
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -r {} + 2>/dev/null || true
	rm -rf build dist .coverage coverage.xml
