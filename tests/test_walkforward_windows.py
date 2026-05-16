"""BCK-01: Walk-forward window construction unit tests.

Wave 0 stub. Wave 1 (plan 05-01) replaces these skips with assertions against
`screener.backtest.walkforward.walk_forward_windows()`:

  - 7 complete windows for start=2016-01-01, end=2025-12-31 (IS=3yr, OOS=1yr, slide=1yr)
  - First window: IS 2016-01-01..2018-12-31 | OOS 2019-01-01..2019-12-31
  - Last window:  IS 2022-01-01..2024-12-31 | OOS 2025-01-01..2025-12-31
  - All windows: is_end < oos_start (no overlap)
  - Empty list if (end - start) < (is_years + oos_years)
"""

from __future__ import annotations

import pytest


def test_walkforward_window_count_2016_to_2025() -> None:
    """Wave 1 (plan 05-01) fills body — asserts exactly 7 windows."""
    pytest.skip("Wave 1 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-01-PLAN.md")  # noqa: E501


def test_walkforward_first_and_last_window_boundaries() -> None:
    """Wave 1 (plan 05-01) fills body — asserts first/last window exact dates."""
    pytest.skip("Wave 1 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-01-PLAN.md")  # noqa: E501


def test_walkforward_empty_when_range_too_short() -> None:
    """Wave 1 (plan 05-01) fills body — asserts [] when end-start < is_years+oos_years."""
    pytest.skip("Wave 1 fills body — see .planning/phases/05-backtest-harness-no-lookahead-gate/05-01-PLAN.md")  # noqa: E501
