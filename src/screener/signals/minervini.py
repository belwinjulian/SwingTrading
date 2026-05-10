"""minervini — Trend Template gate (8 SMA-based conditions; pass/fail + 0-8 score).

Per CLAUDE.md "Signal Formulas — Quick-Reference" — simple moving averages
only. The CI grep gate (IND-02) is scoped to this file specifically — must
NOT import or reference exponential variants of moving averages anywhere.

Pure-function discipline (Phase 1 D-16 architecture lock): no I/O, no global
state, panel-in / panel-out. Imports only pandas + stdlib.

Pitfalls handled:
- Per-ticker shift via groupby(level='ticker').shift(22) for cond 3
  (Pitfall 2: naked .shift on MultiIndex bleeds across tickers)
- Nullable Int64 NaN propagation: rs_rating >= 70 returns pd.NA on NaN
  input; .fillna(False).astype(bool) is required BEFORE AND-ing conditions
  (Pitfall 3: pd.NA in boolean context raises 'ambiguous')
- Tickers with insufficient history (< 252 bars) get NaN -> False -> score 0
  and do NOT pass the gate (Phase 3 D-08 NaN policy carry-forward)
"""

from __future__ import annotations

import pandas as pd


def passes_trend_template(panel: pd.DataFrame) -> pd.DataFrame:
    """Add `passes_trend_template` (bool) and `trend_template_score` (Int64 0-8).

    Implements the 8 Minervini Trend Template conditions verbatim from
    CLAUDE.md "Signal Formulas — Quick-Reference":

        1. Close > SMA150 AND Close > SMA200
        2. SMA150 > SMA200
        3. SMA200 > SMA200[t-22]                  (per-ticker shift)
        4. SMA50 > SMA150 AND SMA50 > SMA200
        5. Close > SMA50
        6. Close >= 1.30 * MIN(Low, 252)          (low_52w)
        7. Close >= 0.75 * MAX(High, 252)         (high_52w)
        8. RS_Rating >= 70

    Args:
        panel: MultiIndex (ticker, date) DataFrame containing AT LEAST these
            columns: close, sma_50, sma_150, sma_200, high_52w, low_52w,
            rs_rating. Produced by indicators.build_panel() after Plan 04-01
            wires high_52w / low_52w into the chain.

    Returns:
        The input panel with two new columns appended:
            trend_template_score: pd.Int64Dtype, 0-8 inclusive
            passes_trend_template: bool, True iff score == 8

    Tickers missing any input get NaN -> False / 0 (NaN-safe per Pitfall 3
    and Phase 3 D-08).
    """
    out = panel.copy()

    close = panel["close"]
    sma_50 = panel["sma_50"]
    sma_150 = panel["sma_150"]
    sma_200 = panel["sma_200"]
    high_52w = panel["high_52w"]
    low_52w = panel["low_52w"]
    rs_rating = panel["rs_rating"]

    # Cond 3: per-ticker shift to avoid index bleed across tickers (Pitfall 2).
    sma_200_22d_ago = sma_200.groupby(level="ticker").shift(22)

    cond1 = (close > sma_150) & (close > sma_200)
    cond2 = sma_150 > sma_200
    cond3 = sma_200 > sma_200_22d_ago
    cond4 = (sma_50 > sma_150) & (sma_50 > sma_200)
    cond5 = close > sma_50
    cond6 = close >= 1.30 * low_52w
    cond7 = close >= 0.75 * high_52w
    cond8 = rs_rating >= 70  # nullable Int64 -> pd.NA on NaN; handled below

    # NaN-safe boolean coercion (Pitfall 3): pd.NA in `&` raises ambiguous;
    # any NaN input must propagate to False (ticker fails the condition).
    conds = [cond1, cond2, cond3, cond4, cond5, cond6, cond7, cond8]
    bool_conds: list[pd.Series] = [c.fillna(False).astype(bool) for c in conds]

    # Sum bool conditions as Int64 -> 0-8 score.
    # Use pd.concat + sum to keep mypy happy with the Series[Int64] type.
    score: pd.Series = pd.concat(
        [bc.astype("Int64") for bc in bool_conds], axis=1
    ).sum(axis=1).astype("Int64")

    out["trend_template_score"] = score
    # passes iff all 8 are True; NaN-safe via the prior fillna chain.
    out["passes_trend_template"] = (score == 8).fillna(False).astype(bool)
    return out
