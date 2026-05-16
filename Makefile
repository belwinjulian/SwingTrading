# Makefile — Momentum Swing Screener
#
# Every target is .PHONY; recipes shell out to the `screener` typer CLI.
# Phase 1: every command logs a structured [stub] line and exits 0.
# Later phases fill in the bodies without changing this contract (FND-02).

.PHONY: help setup data macro rank report backtest backtest-audit backfill-snapshots journal lint typecheck test all clean

help:  ## List available targets with descriptions
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup:  ## Install dependencies (uv sync --extra dev) and pre-commit hooks
	uv sync --extra dev
	uvx pre-commit install

data:  ## Refresh universe, OHLCV, macro, and fundamentals (Phase 1: stub no-ops)
	uv run screener refresh-universe
	uv run screener refresh-ohlcv
	uv run screener refresh-macro
	uv run screener refresh-fundamentals

macro:  ## Refresh macro inputs only (SPY, QQQ, ^VIX, NYSE A/D, FRED yields)
	uv run screener refresh-macro

rank:  ## Compute composite scores + playbook tags over the universe (Phase 1: stub)
	uv run screener score

report:  ## Render the daily Markdown report (Phase 1: stub)
	uv run screener report

backtest:  ## Run vectorbt walk-forward backtest (Phase 1: stub)
	uv run screener backtest

backtest-audit:  ## Run the forensic checklist (no-look-ahead, weight-pre-reg hash, universe date)
	uv run screener backtest-audit

backfill-snapshots:  ## Backfill historical snapshots 2016-01-01..today (one-off; see D-01)
	uv run python scripts/backfill_snapshots.py

journal:  ## Append actionable picks to data/journal.sqlite (Phase 1: stub)
	uv run screener journal

lint:  ## Run ruff format --check and ruff check
	uv run ruff format --check .
	uv run ruff check .

typecheck:  ## Run mypy --strict on the math modules (signals/, indicators/, regime, sizing)
	uv run mypy

test:  ## Run pytest (with coverage gate from pyproject.toml)
	uv run pytest

all: data rank report  ## Run the daily DAG (data -> rank -> report)

clean:  ## Remove caches and build artifacts (does NOT remove uv.lock or data/)
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
