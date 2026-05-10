"""relative_strength — IBD-style RS computation (cross-sectional, per-date).

Formula (CLAUDE.md §"Signal Formulas — IBD-style RS"):
    rs_raw    = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)
    rs_rating = (rs_raw.rank(pct=True) * 99).round().clip(1, 99).astype(Int64)

Cross-sectional rank per date — groupby(level='date'). NaN tickers
(insufficient history) are excluded from the ranking and receive NaN
rs_rating per CONTEXT.md "RS percentile ranking excludes NaN tickers".

Pitfalls handled:
- 8: per-ticker shifts use groupby(level='ticker').shift() — never naked .shift()
- 9: rs_rating is pd.Int64Dtype (nullable Int64), NOT int — int can't hold NaN
"""

from __future__ import annotations

import pandas as pd


def rs_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute rs_raw and rs_rating for the (ticker, date) MultiIndex panel.

    Returns the panel with two new columns:
    - rs_raw: float (NaN where any of C_63 / C_126 / C_189 / C_252 is missing)
    - rs_rating: pd.Int64Dtype in [1, 99] (NaN where rs_raw is NaN)
    """
    by_ticker = panel.groupby(level="ticker")["close"]
    c_63 = by_ticker.shift(63)
    c_126 = by_ticker.shift(126)
    c_189 = by_ticker.shift(189)
    c_252 = by_ticker.shift(252)
    rs_raw = (
        2.0 * (panel["close"] / c_63)
        + (panel["close"] / c_126)
        + (panel["close"] / c_189)
        + (panel["close"] / c_252)
    )
    pct = rs_raw.groupby(level="date").rank(pct=True)
    rs_rating = (pct * 99).round().clip(1, 99)
    rs_rating = rs_rating.astype("Int64")  # nullable Int64 (Pitfall 9)
    out = panel.copy()
    out["rs_raw"] = rs_raw
    out["rs_rating"] = rs_rating
    return out
