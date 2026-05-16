"""BCK-03: ADV-tiered slippage panel construction unit tests.

Wave 0 stub. Wave 1 (plan 05-01) replaces these skips with assertions against
`screener.backtest.vbt_runner._build_slippage_panel()`. Tier mapping (D-11 verbatim):

  - ADV > $50M           ->  0.0005 (5 bps)
  - $5M <= ADV <= $50M   ->  0.0015 (15 bps)
  - ADV < $5M            ->  0.0030 (30 bps)
  - Warmup NaN (first 19 bars) -> filled with 0.0030 (worst tier; RESEARCH §E L1)
"""

from __future__ import annotations

import pytest


def test_adv_above_50m_gets_5bps() -> None:
    """Wave 1 (plan 05-01) fills body — verifies 5 bps for ADV > $50M post-warmup."""
    pytest.skip("Wave 1 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-01-PLAN.md")  # noqa: E501


def test_adv_below_5m_gets_30bps() -> None:
    """Wave 1 (plan 05-01) fills body — verifies 30 bps for ADV < $5M post-warmup."""
    pytest.skip("Wave 1 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-01-PLAN.md")  # noqa: E501


def test_warmup_nan_filled_with_worst_tier() -> None:
    """Wave 1 (plan 05-01) fills body — verifies first 19 bars get 30 bps default."""
    pytest.skip("Wave 1 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-01-PLAN.md")  # noqa: E501
