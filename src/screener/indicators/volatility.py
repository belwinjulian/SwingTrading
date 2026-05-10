"""volatility — ATR(14) and ADR%(20) panel computations.

Pure-function discipline (Phase 1 D-16): NO I/O, NO global state.
"""

from __future__ import annotations

import pandas as pd
import pandas_ta_classic as ta


def _safe_atr(h: pd.Series, low: pd.Series, c: pd.Series, length: int) -> pd.Series:
    """Wrap ta.atr; default mamode='rma' is Wilder's smoothing per
    docs/methodology.md §6. None on short input → NaN Series (Pitfall 2).
    """
    result: pd.Series | None = ta.atr(h, low, c, length=length)
    if result is None:
        return pd.Series(float("nan"), index=c.index, name=f"ATRr_{length}")
    return result


def atr_panel(panel: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Append atr_<length> column. Per-ticker rolling (Pitfall 8).

    Uses explicit per-ticker concat instead of groupby.apply to avoid
    pandas returning a wide (ticker x date) DataFrame when the apply
    function returns a Series with the date as index.
    """
    out = panel.copy()
    parts: list[pd.Series] = []
    for _ticker, g in panel.groupby(level="ticker"):
        s = _safe_atr(g["high"], g["low"], g["close"], length)
        parts.append(s)
    combined = pd.concat(parts)
    combined.name = f"atr_{length}"
    out[f"atr_{length}"] = combined
    return out


def adr_pct_panel(panel: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """ADR%(length) per CLAUDE.md §"Signal Formulas — ADR%":
        ADR_pct = 100 * (mean(high/low over `length` days) - 1)

    Per-ticker rolling — groupby level='ticker' so the window doesn't span tickers.
    Verified live 2026-05-10: high=105/low=95 → 10.526%.
    """
    out = panel.copy()
    ratio = panel["high"] / panel["low"]
    out["adr_pct"] = (
        100.0
        * (
            ratio.groupby(level="ticker")
            .rolling(length)
            .mean()
            .droplevel(0)
            - 1.0
        )
    )
    return out
