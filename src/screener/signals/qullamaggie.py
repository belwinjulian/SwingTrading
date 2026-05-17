"""qullamaggie — Setup A scan (SIG-02). Pure: panel-in, panel-out.

SIG-02 verbatim: top 1-2% performers over 1m/3m/6m AND avg dollar volume > $1.5M
AND ADR%(20) >= 4.

Top 1-2% interpreted as percentile rank (CONTEXT.md Discretion default;
matches IBD RS pattern already in codebase). The 1m/3m/6m windows form an
OR-gate so a ticker that explodes in any one of the three windows qualifies.

Pure-function discipline (Phase 1 D-16 architecture lock): no I/O, no global
state, panel-in / panel-out. Imports only pandas + stdlib.
"""

from __future__ import annotations

import pandas as pd

# SIG-02 constants: scan-time gates (NOT the D-13 tie-break thresholds in composite.py)
QULL_TOP_PCT_THRESHOLD: float = 0.98
QULL_MIN_DOLLAR_VOLUME: float = 1_500_000.0
QULL_MIN_ADR_PCT_SCAN: float = 4.0  # Setup A scan gate (NOT the D-13 tie-break threshold)


def passes_qullamaggie_setup_a(panel: pd.DataFrame) -> pd.DataFrame:
    """Append qullamaggie_score (Int64 0/1) per SIG-02.

    SIG-02 verbatim: top 1-2% performers over 1m/3m/6m AND avg dollar volume
    > $1.5M AND ADR%(20) >= 4. The 1m/3m/6m windows form an OR-gate (any one
    of the three windows qualifying is sufficient). Percentile rank computed
    cross-sectionally per date.

    Args:
        panel: MultiIndex (ticker, date) with AT LEAST: close, volume, adr_pct.
            rs_rating is available for future extension but not used in the
            scan (the scan uses cross-sectional return ranks directly per
            SIG-02 verbatim).

    Returns:
        The input panel with ``qullamaggie_score`` (Int64 0/1) column appended.
        1 = passes all three SIG-02 gates; 0 = fails at least one gate.

    Pitfalls handled:
    - NaN propagation: fillna(False) before AND-gating nullable series.
    - Dollar-volume rolling mean: grouped by ticker before rolling to avoid
      cross-ticker contamination.
    - droplevel(0) removes the extra ticker level added by groupby().rolling().
    """
    out = panel.copy()

    # --- Gate 1: cross-sectional percentile rank of trailing returns ---
    # pct_change(n) per ticker, then rank(pct=True) per date
    grouped_close = panel["close"].groupby(level="ticker")
    ret_1m = grouped_close.pct_change(21)
    ret_3m = grouped_close.pct_change(63)
    ret_6m = grouped_close.pct_change(126)

    pct_1m = ret_1m.groupby(level="date").rank(pct=True)
    pct_3m = ret_3m.groupby(level="date").rank(pct=True)
    pct_6m = ret_6m.groupby(level="date").rank(pct=True)

    # OR-gate: qualifies if in top 1-2% on any of the three windows
    top_2pct = (
        (pct_1m >= QULL_TOP_PCT_THRESHOLD)
        | (pct_3m >= QULL_TOP_PCT_THRESHOLD)
        | (pct_6m >= QULL_TOP_PCT_THRESHOLD)
    )

    # --- Gate 2: average dollar volume (20-day) > $1.5M ---
    dollar_vol = panel["close"] * panel["volume"]
    # Group by ticker before rolling to avoid cross-ticker contamination
    avg_dv = (
        dollar_vol.groupby(level="ticker")
        .rolling(20)
        .mean()
        .droplevel(0)
    )
    liquid = avg_dv > QULL_MIN_DOLLAR_VOLUME

    # --- Gate 3: ADR%(20) >= 4.0 ---
    high_adr = panel["adr_pct"] >= QULL_MIN_ADR_PCT_SCAN

    # AND-gate with NaN-safe coercion (Pitfall 3 analogue from minervini.py)
    combined = (
        top_2pct.fillna(False).astype(bool)
        & liquid.fillna(False).astype(bool)
        & high_adr.fillna(False).astype(bool)
    )

    out["qullamaggie_score"] = combined.astype("Int64")
    return out
