"""FND-04 + BCK-02: CI-blocking no-look-ahead mutation test.

Wave 0 stub. Wave 1 (plan 05-02) replaces these skips with the parameterized
`_lookahead=True/False` calls to `screener.backtest.vbt_runner.run()`.

Assertion thresholds (per CONTEXT.md D-07 REVISED 2026-05-16):
  - _lookahead=False  ->  abs(total_return) < 0.50  (correct path; foresight negated)
  - _lookahead=True   ->  total_return > 1.00       (mutation; foresight wins)

Threshold rationale: 10-seed Monte Carlo, see 05-RESEARCH.md §B Q5.

Fixture span (C-1 fix, iter 3): test calls vbt_runner.run on the fixture's
~5.15-year date range (~2019-01-01..2024-01-XX), guaranteeing >=2 complete
3yr-IS / 1yr-OOS windows so the mutation test is non-trivial.
"""

from __future__ import annotations

import pytest


def test_no_lookahead_correct_path() -> None:
    """Wave 1 (plan 05-02) fills body — _lookahead=False asserts abs(total_return) < 0.50."""
    pytest.skip("Wave 1 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-02-PLAN.md")  # noqa: E501


def test_no_lookahead_mutation_detected() -> None:
    """Wave 1 (plan 05-02) fills body — _lookahead=True asserts total_return > 1.00."""
    pytest.skip("Wave 1 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-02-PLAN.md")  # noqa: E501
