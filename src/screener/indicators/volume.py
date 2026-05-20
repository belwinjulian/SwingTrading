"""volume — OBV + dryup-ratio panel computations.

D-09: dryup_ratio = volume / SMA(volume, 50). Values < 0.5 indicate significant
volume contraction; the 50d window aligns with Phase 6 VCP breakout-volume
baseline (breakout volume >= 1.5 * SMA(volume, 50)).

Pure-function discipline (Phase 1 D-16).
"""

from __future__ import annotations

import pandas as pd
import pandas_ta_classic as ta


def _safe_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Wrap ta.obv; None on short input → NaN Series (Pitfall 2)."""
    result: pd.Series | None = ta.obv(close, volume)
    if result is None:
        return pd.Series(float("nan"), index=close.index, name="OBV")
    return result


def obv_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Append obv column, computed per-ticker.

    Uses explicit per-ticker concat instead of groupby.apply to avoid
    pandas returning a wide (ticker x date) DataFrame when the apply
    function returns a Series with the date as index.
    """
    out = panel.copy()
    parts: list[pd.Series] = []
    for _ticker, g in panel.groupby(level="ticker"):
        s = _safe_obv(g["close"], g["volume"])
        parts.append(s)
    combined = pd.concat(parts)
    combined.name = "obv"
    out["obv"] = combined
    return out


def dryup_ratio_panel(panel: pd.DataFrame, length: int = 50) -> pd.DataFrame:
    """D-09: dryup_ratio = volume / SMA(volume, length)."""
    out = panel.copy()
    sma_vol = panel.groupby(level="ticker")["volume"].rolling(length).mean().droplevel(0)
    out["dryup_ratio"] = panel["volume"] / sma_vol
    return out
