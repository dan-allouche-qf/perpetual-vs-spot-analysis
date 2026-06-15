# Reproducible workflow for the perp-spot research repo.
# Usage: `make setup`, `make test`, `make all`.

PY ?= python3
PIP ?= $(PY) -m pip

.DEFAULT_GOAL := help
.PHONY: help setup data test lint typecheck figures notebooks app report all clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install the package + dev/app extras (editable)
	$(PIP) install -e ".[dev,app]"

data: ## (Re)build the committed parquet snapshot from data.binance.vision
	$(PY) -m scripts.fetch_data

test: ## Run the pytest suite
	$(PY) -m pytest

lint: ## Lint with ruff
	$(PY) -m ruff check src tests scripts

typecheck: ## Static type check with mypy
	$(PY) -m mypy

figures: ## Regenerate the committed hero figures into docs/figures/
	$(PY) -m scripts.make_figures

notebooks: ## Execute all notebooks in place (offline, from the snapshot)
	$(PY) -m jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb

app: ## Launch the Dash explorer (non-blocking server)
	$(PY) -m scripts.app

report: ## Recompute report/numbers.tex and compile report/report.pdf
	$(PY) -m scripts.report_numbers
	latexmk -pdf -cd -interaction=nonstopmode report/report.tex

all: lint typecheck test figures ## Lint, type-check, test, and regenerate figures

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist src/*.egg-info
	find . -type d -name __pycache__ -not -path './venv/*' -exec rm -rf {} +
