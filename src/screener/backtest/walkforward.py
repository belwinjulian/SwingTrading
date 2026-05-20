"""backtest/walkforward — pure window-construction utility for the walk-forward harness.

BCK-01: 3-year IS / 1-year OOS rolling windows, sliding by 1 year. Returns
exactly 7 windows for start=2016-01-01..end=2025-12-31 (calendar-year arithmetic
via pd.DateOffset(years=...)).

Architectural contract (D-17): pure function, no I/O, no global state, no
``screener.*`` imports beyond what is in this file (none). Allowed: stdlib +
pandas only.

Pitfall (RESEARCH §E L11): ``pd.Timestamp('2020-02-29') + pd.DateOffset(years=1)``
yields ``Timestamp('2021-02-28')`` (Feb 29 bumps backward on non-leap years).
The canonical 2016-01-01 start is unaffected; documented for awareness.
"""

from __future__ import annotations

import pandas as pd


def walk_forward_windows(
    start: pd.Timestamp,
    end: pd.Timestamp,
    is_years: int = 3,
    oos_years: int = 1,
    slide_years: int = 1,
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    """Yield (is_start, is_end, oos_start, oos_end) tuples for walk-forward.

    Window placement example (start=2016-01-01, end=2025-12-31, IS=3y, OOS=1y, slide=1y)::

        Win 1: IS 2016-01-01..2018-12-31 | OOS 2019-01-01..2019-12-31
        Win 2: IS 2017-01-01..2019-12-31 | OOS 2020-01-01..2020-12-31
        ...
        Win 7: IS 2022-01-01..2024-12-31 | OOS 2025-01-01..2025-12-31

    Args:
        start: First IS-window start date.
        end:   Last date inclusive that an OOS window may close on.
        is_years:    In-sample window length in calendar years (default 3).
        oos_years:   Out-of-sample window length in calendar years (default 1).
        slide_years: Step between successive window starts in calendar years (default 1).

    Returns:
        List of (is_start, is_end, oos_start, oos_end) pd.Timestamp tuples.
        Empty list if no complete window fits within [start, end].
    """
    windows: list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]] = []
    window_start = start
    while True:
        is_end = window_start + pd.DateOffset(years=is_years) - pd.Timedelta(days=1)
        oos_start = is_end + pd.Timedelta(days=1)
        oos_end = oos_start + pd.DateOffset(years=oos_years) - pd.Timedelta(days=1)
        if oos_end > end:
            break
        windows.append((window_start, is_end, oos_start, oos_end))
        window_start = window_start + pd.DateOffset(years=slide_years)
    return windows
