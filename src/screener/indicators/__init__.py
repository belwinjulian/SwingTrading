"""indicators — pure-function indicator panel; no I/O, no global state.

Functions take pandas DataFrames in, return DataFrames with identical index.
SMAs (NOT EMAs in the Trend Template — see CLAUDE.md §13.6 pitfall #4),
ATR(14), ADR%(20), OBV, RS percentile (universe-relative). May import only
`persistence` and `config` from inside the package.
"""

from __future__ import annotations

import pandas as pd

from screener.indicators.relative_strength import rs_panel
from screener.indicators.trend import sma_panel
from screener.indicators.volatility import adr_pct_panel, atr_panel
from screener.indicators.volume import dryup_ratio_panel, obv_panel
from screener.persistence import read_panel

__all__ = ["build_panel"]


def build_panel(snapshot_date: str | pd.Timestamp) -> pd.DataFrame:
    """Returns the OHLCV panel + 10 indicator columns. Pure function — reads
    from persistence.read_panel(); emits no I/O.

    Columns added (in order):
        sma_10, sma_20, sma_50, sma_150, sma_200, atr_14, adr_pct, obv,
        dryup_ratio, rs_raw, rs_rating
    """
    panel = read_panel(snapshot_date)  # MultiIndex (ticker, date), validated lazily
    panel = sma_panel(panel, lengths=(10, 20, 50, 150, 200))
    panel = atr_panel(panel, length=14)
    panel = adr_pct_panel(panel, length=20)
    panel = obv_panel(panel)
    panel = dryup_ratio_panel(panel, length=50)
    panel = rs_panel(panel)
    return panel
