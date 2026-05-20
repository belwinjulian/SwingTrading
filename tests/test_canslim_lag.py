"""45-day fundamentals lag enforcement — DAT-05 / D-13b.

Plan 06-03 (Wave 1) fills the test body: write a fundamentals row with
``quarter_end = as_of_date - 30d``, call ``persistence.read_fundamentals(as_of_date)``,
assert the row is masked (lag not yet satisfied); advance to ``as_of_date + 16d``
(now 46d post-quarter), assert it appears (verbatim CONTEXT.md D-13b).
"""

# Wave: 1  (body filled by Plan 06-03 — see 06-VALIDATION.md "New test files")

import pandas as pd
import pytest


def test_lag_enforcement_30d_then_16d(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[type-arg]
    """D-13b verbatim: row with quarter_end = as_of - 30d is MASKED until as_of + 16d.

    Timeline:
    - fiscal_quarter_end = 2026-04-01 (as_of_date - 30d)
    - knowable_from      = 2026-04-01 + 45d = 2026-05-16
    - as_of_date         = 2026-05-01  ->  knowable_from (2026-05-16) > as_of -> MASKED
    - as_of_date + 16d   = 2026-05-17  ->  knowable_from (2026-05-16) <= as_of -> VISIBLE
    """
    monkeypatch.setenv("FUNDAMENTALS_CACHE_DIR", str(tmp_path))
    from screener.config import get_settings

    get_settings.cache_clear()

    from screener.persistence import read_fundamentals, write_fundamentals_atomic

    as_of = pd.Timestamp("2026-05-01")
    quarter_end = as_of - pd.Timedelta(days=30)  # 2026-04-01
    knowable_from = quarter_end + pd.Timedelta(days=45)  # 2026-05-16

    row = pd.DataFrame(
        {
            "ticker": ["AAPL"],
            "fiscal_quarter_end": [quarter_end],
            "eps_actual": [1.5],
            "eps_yoy_growth": [0.30],
            "knowable_from": [knowable_from],
            "next_earnings_date": [as_of + pd.Timedelta(days=80)],
            "next_earnings_hour": ["amc"],
            "source": ["yfinance"],
            "ingested_at": [pd.Timestamp.now()],
        }
    )
    write_fundamentals_atomic(row, "AAPL")

    # At as_of (2026-05-01): knowable_from (2026-05-16) > as_of -> MASKED
    df1 = read_fundamentals(as_of)
    assert "AAPL" not in set(df1["ticker"].tolist()), (
        f"Expected AAPL to be masked at {as_of} (knowable_from={knowable_from}), "
        f"but read_fundamentals returned {df1['ticker'].tolist()}"
    )

    # At as_of + 16d (2026-05-17): knowable_from (2026-05-16) <= as_of+16d -> VISIBLE
    df2 = read_fundamentals(as_of + pd.Timedelta(days=16))
    assert "AAPL" in set(df2["ticker"].tolist()), (
        f"Expected AAPL visible at {as_of + pd.Timedelta(days=16)} "
        f"(knowable_from={knowable_from}), but read_fundamentals returned {df2['ticker'].tolist()}"
    )
