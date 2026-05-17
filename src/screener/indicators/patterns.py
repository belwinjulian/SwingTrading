"""patterns — VCP, continuation flag, post-gap-continuation pattern detection.

Pure-function discipline (Phase 1 D-16): NO I/O, NO global state. Imports only
pandas, scipy.signal, numpy, and stdlib.

VCP thresholds locked as Final module-level constants per CONTEXT.md D-03 —
not Settings fields, not env-overridable. Tuned via golden-file tests
(test_patterns_golden.py), never against backtest results (Critical Pitfall 5).

detect_all_patterns annotates ONLY the last bar of each ticker's slice with
vcp_passes/flag_passes/pivot_price/pattern_diagnostics. The cross-section
consumer (publishers/pipeline.py at as_of_date) sees one annotated row per
ticker. For Phase 5 BCK-04 backfill: re-run build_panel() per snapshot_date —
each snapshot independently runs pattern detection on its own trailing slice,
so historical attribution gets non-NaN tags for each backfilled date.
(See Plan 05 verification step W7 — re-run make backfill-snapshots after
Phase 6 ships.)

Tuning Log (D-03 / Open Question 1):
- VCP_PIVOT_ORDER = 5 — starting value per RESEARCH §Specifics. Reviewed
  against the 4 D-02 golden fixtures; retained.
- FLAG_PIVOT_ORDER = 3 — starting value per RESEARCH §Specifics. Reviewed
  against the NVDA 2023 flag fixture; retained.
"""
from __future__ import annotations

import json
from typing import Final

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

# Phase 6 D-03 — VCP detection thresholds (CLAUDE.md Signal Formulas — VCP)
PRIOR_UPTREND_MIN_PCT: Final[float] = 0.30
PRIOR_UPTREND_LOOKBACK_DAYS: Final[int] = 126
N_CONTRACTIONS_MIN: Final[int] = 2
N_CONTRACTIONS_MAX: Final[int] = 6
DEPTH_CONTRACTION_MAX_RATIO: Final[float] = 0.85
FIRST_LEG_MAX_DEPTH_PCT: Final[float] = 0.35
FINAL_CONTRACTION_MAX_DEPTH_PCT: Final[float] = 0.12
BREAKOUT_VOLUME_MIN_MULTIPLE: Final[float] = 1.5
SMA_VOLUME_BASELINE_DAYS: Final[int] = 50

# Phase 6 D-01/D-03 — flag detector constants (PAT-03 + Code Examples 3)
FLAG_MIN_BARS: Final[int] = 5
FLAG_MAX_BARS: Final[int] = 25
FLAG_HIGHER_LOWS_ATR_TOLERANCE: Final[float] = 0.5
FLAG_RANGE_TIGHTNESS_ATR_MULT: Final[float] = 1.0

# Phase 6 D-04 — post-gap-continuation thresholds (boolean only)
POST_GAP_MIN_PCT: Final[float] = 0.08
POST_GAP_MIN_VOL_MULTIPLE: Final[float] = 1.5
POST_GAP_UPPER_THIRD_THRESHOLD: Final[float] = 2.0 / 3.0

# Pivot detection (Open Question 1 / Pitfall 2) — tune via 4 golden files
VCP_PIVOT_ORDER: Final[int] = 5
FLAG_PIVOT_ORDER: Final[int] = 3

_VALID_PATTERN_TYPES: Final[frozenset[str]] = frozenset({"vcp", "flag", "none"})


def breakout_strength(vol: pd.Series, sma_vol_50: pd.Series) -> pd.Series:
    """D-06: graded volume-confirmation score.

    breakout_strength = clip((vol / sma_vol_50 - 1.0) / 1.5, 0, 1).
    1.5x SMA -> 0.33, 3x SMA -> 1.0. NaN/0 inputs -> 0 (Pitfall 10).
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = vol / sma_vol_50
    # Pitfall 10: a zero baseline yields +inf -> clipped to 1.0, which is a
    # false-positive signal (we observed no real volume vs nothing). Force
    # non-finite ratios to NaN so the final fillna(0.0) catches them.
    ratio = ratio.where(np.isfinite(ratio), other=np.nan)
    strength = ((ratio - 1.0) / 1.5).clip(0.0, 1.0)
    return strength.fillna(0.0)


def find_pivots(
    highs: np.ndarray, lows: np.ndarray, order: int
) -> tuple[np.ndarray, np.ndarray]:
    """argrelextrema wrapper. Edge-effect: peaks within `order` bars of
    start/end are NOT detected (Pitfall 2).
    """
    highs_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
    lows_idx = argrelextrema(lows, np.less_equal, order=order)[0]
    return highs_idx, lows_idx


def post_gap_continuation_panel(panel: pd.DataFrame) -> pd.Series:
    """D-04: boolean per row.

    gap_pct = open / prev_close - 1
    held = close >= low + (2/3)*(high-low)
    vol_confirm = volume > POST_GAP_MIN_VOL_MULTIPLE * sma_vol_50
    """
    prev_close = panel.groupby(level="ticker")["close"].shift(1)
    gap_pct = panel["open"] / prev_close - 1.0
    high_low = panel["high"] - panel["low"]
    held = panel["close"] >= panel["low"] + POST_GAP_UPPER_THIRD_THRESHOLD * high_low
    sma_vol_50 = (
        panel.groupby(level="ticker")["volume"]
        .rolling(SMA_VOLUME_BASELINE_DAYS)
        .mean()
        .droplevel(0)
    )
    vol_confirm = panel["volume"] > POST_GAP_MIN_VOL_MULTIPLE * sma_vol_50
    return ((gap_pct >= POST_GAP_MIN_PCT) & held & vol_confirm).fillna(False)
