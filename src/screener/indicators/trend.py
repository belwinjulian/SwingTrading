"""trend — SMA panel computations.

This module computes simple rolling means (NOT exponentially-weighted) per
CLAUDE.md §13.6 pitfall #4. The CI grep gate (IND-02) is scoped to this file
specifically — all moving averages must be simple (non-exponential) rolling
means; do not add exponentially-weighted variants here.

Pure-function discipline (Phase 1 D-16): NO I/O, NO global state. Imports only
pandas, pandas_ta_classic (third-party math), and stdlib.
"""

from __future__ import annotations

import pandas as pd
import pandas_ta_classic as ta


def _safe_sma(close: pd.Series, length: int) -> pd.Series:
    """Wrap ta.sma to return a NaN-filled Series when input is shorter than `length`.

    pandas-ta-classic returns None in that case (verified live 2026-05-10
    against pandas-ta-classic==0.4.47), which crashes downstream `.rename()`
    and DataFrame assembly (RESEARCH Pitfall 2).
    """
    result: pd.Series | None = ta.sma(close, length=length)
    if result is None:
        return pd.Series(float("nan"), index=close.index, name=f"SMA_{length}")
    return result


def sma_panel(
    panel: pd.DataFrame,
    lengths: tuple[int, ...] = (10, 20, 50, 150, 200),
) -> pd.DataFrame:
    """Append sma_<length> columns to the panel, computed per-ticker.

    Pitfall 8: groupby(level='ticker') is required to prevent rolling-window
    bleed across tickers in the (ticker, date) MultiIndex.
    """
    out = panel.copy()
    for length in lengths:
        col = f"sma_{length}"

        def _apply_sma(c: pd.Series, n: int = length) -> pd.Series:
            return _safe_sma(c, n).reset_index(level=0, drop=True)

        out[col] = panel.groupby(level="ticker")["close"].apply(_apply_sma)
    return out


def high_52w_panel(panel: pd.DataFrame, length: int = 252) -> pd.DataFrame:
    """Append high_52w column — per-ticker rolling max of `high` over `length` bars.

    NaN warmup for the first `length-1` bars per ticker (Phase 3 D-08 NaN policy).
    Pitfall 2: groupby(level="ticker") prevents rolling-window bleed across
    tickers in the (ticker, date) MultiIndex.

    Required by signals/minervini.passes_trend_template condition 7
    (Close >= 0.75 * MAX(High, 252)) per CLAUDE.md "Signal Formulas".
    """
    out = panel.copy()
    out["high_52w"] = (
        panel.groupby(level="ticker")["high"]
        .rolling(length)
        .max()
        .droplevel(0)
    )
    return out


def low_52w_panel(panel: pd.DataFrame, length: int = 252) -> pd.DataFrame:
    """Append low_52w column — per-ticker rolling min of `low` over `length` bars.

    Required by signals/minervini.passes_trend_template condition 6
    (Close >= 1.30 * MIN(Low, 252)) per CLAUDE.md "Signal Formulas".
    """
    out = panel.copy()
    out["low_52w"] = (
        panel.groupby(level="ticker")["low"]
        .rolling(length)
        .min()
        .droplevel(0)
    )
    return out
