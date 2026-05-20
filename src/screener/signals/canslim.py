"""canslim — CANSLIM C-only overlay (SIG-03, D-18).

D-18: only the C component (quarterly EPS YoY >= 25%) is scored here:
  - L (relative strength ≥ 80) is already captured in rs_component; this module
    does NOT reference that panel column — doing so would double-count it.
  - M (Confirmed Uptrend) is already captured in the regime soft gate
    (composite_score *= regime multiplier per Phase 4 D-03); this module
    does NOT reference the regime column — doing so would double-count it.
Scoring L or M here would inflate beyond the pre-registered 25% RS weight
and double-count the regime multiplier.

Pure-function discipline (Phase 1 D-16 architecture lock): no I/O, no global
state. Imports pandas + stdlib only. signals/ MUST NOT import from
screener.data — the 45-day lag (D-13b) lives at persistence.read_fundamentals;
the caller (publishers/pipeline.py — Plan 05) bridges the data layer to this
signal by passing the pre-filtered fundamentals frame in.
"""

from __future__ import annotations

import pandas as pd

CANSLIM_C_MIN_EPS_YOY: float = 0.25


def canslim_c_overlay(
    panel: pd.DataFrame,
    fundamentals: pd.DataFrame,
    as_of_date: pd.Timestamp,
) -> pd.DataFrame:
    """Append canslim_c_passes (bool) column. C-only per D-18.

    Args:
        panel: MultiIndex (ticker, date) DataFrame.
        fundamentals: DataFrame from persistence.read_fundamentals(as_of_date)
            — already lag-filtered (knowable_from <= as_of_date) per D-13b.
            Expected columns: ticker, fiscal_quarter_end, eps_yoy_growth,
            knowable_from (at minimum). No restriction on index shape.
        as_of_date: snapshot date (passed for clarity; lag already applied
            by the caller via persistence.read_fundamentals).

    Returns:
        The input panel with ``canslim_c_passes`` (bool) column appended.
        Tickers missing from fundamentals → False (honest-failure per D-13b).
        Tickers with eps_yoy_growth < CANSLIM_C_MIN_EPS_YOY → False.

    D-18 de-dup: this function references ONLY ``fundamentals["eps_yoy_growth"]``.
    It does NOT reference the relative-strength panel column (L — already in
    rs_component) or the regime panel columns (M — already in regime gate).
    """
    out = panel.copy()

    if fundamentals.empty:
        out["canslim_c_passes"] = False
        return out

    # Most-recent knowable EPS per ticker (fundamentals are already lag-filtered)
    latest = (
        fundamentals.sort_values("fiscal_quarter_end")
        .groupby("ticker", as_index=True)
        .tail(1)
        .set_index("ticker")
    )
    eps_yoy_by_ticker = latest["eps_yoy_growth"]

    tickers_in_panel = out.index.get_level_values("ticker")

    def _passes(t: str) -> bool:
        if t not in eps_yoy_by_ticker.index:
            return False
        val = eps_yoy_by_ticker[t]
        # NaN-safe: pd.isna(val) returns False condition
        if pd.isna(val):
            return False
        return bool(float(val) >= CANSLIM_C_MIN_EPS_YOY)

    passes_arr = [_passes(t) for t in tickers_in_panel]
    out["canslim_c_passes"] = pd.array(passes_arr, dtype=bool)
    return out
