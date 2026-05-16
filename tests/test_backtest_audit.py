"""BCK-07: Forensic audit CLI tests (4-check checklist).

Wave 0 stub. Wave 3 (plan 05-05) replaces these skips with CliRunner-based
assertions against `screener.cli.backtest_audit()`. Checks (CONTEXT.md D-16,
REVISED 2026-05-16):

  1. pytest tests/test_backtest_no_lookahead.py exits 0
  2. subprocess scripts/check_preregistration.py exits 0
  3. REVISED: earliest available data/universe/*.parquet stem <= earliest IS window start
     (emits WARN with gap detail; the original wording was "latest snapshot <= start"
      which would never pass until a backdated 2016 snapshot exists)
  4. >= 2 complete OOS windows exist in data/snapshots/
"""

from __future__ import annotations

import pytest


def test_audit_all_checks_pass_returns_exit_zero() -> None:
    """Wave 3 (plan 05-05) fills body — happy-path: 4/4 PASS -> exit 0."""
    pytest.skip("Wave 3 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-05-PLAN.md")  # noqa: E501


def test_audit_empty_snapshots_dir_exits_nonzero() -> None:
    """Wave 3 (plan 05-05) fills body — empty data/snapshots/ -> FAIL on check #4."""
    pytest.skip("Wave 3 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-05-PLAN.md")  # noqa: E501


def test_audit_empty_universe_dir_exits_nonzero() -> None:
    """Wave 3 (plan 05-05) fills body — empty data/universe/ -> FAIL on REVISED check #3."""
    pytest.skip("Wave 3 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-05-PLAN.md")  # noqa: E501
