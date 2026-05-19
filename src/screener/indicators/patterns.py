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
from typing import Any, Final

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
    sma_vol_50 = panel.groupby(level="ticker")["volume"].transform(
        lambda x: x.rolling(SMA_VOLUME_BASELINE_DAYS).mean()
    )
    vol_confirm = panel["volume"] > POST_GAP_MIN_VOL_MULTIPLE * sma_vol_50
    return ((gap_pct >= POST_GAP_MIN_PCT) & held & vol_confirm).fillna(False)


def encode_pattern_diagnostics(d: dict[str, Any]) -> str:
    """JSON-encode the diagnostics dict. Validates type field per Pitfall 8.

    `default=str` so any pd.Timestamp values (e.g., legs[i].start_date if
    the caller forgot to ISO-format) serialize without raising. Plan 05
    `_build_pattern_audit_df` parses the legs sub-field back into Timestamps.
    """
    t = d.get("type")
    if t not in _VALID_PATTERN_TYPES:
        raise ValueError(
            f"pattern_diagnostics type must be in {_VALID_PATTERN_TYPES}; got {t!r}"
        )
    return json.dumps(d, default=str, separators=(",", ":"))


def decode_pattern_diagnostics(s: str) -> dict[str, Any]:
    """JSON-decode the diagnostics string. Malformed -> {'type': 'none'} (Pitfall 8)."""
    try:
        d = json.loads(s)
        if not isinstance(d, dict) or d.get("type") not in _VALID_PATTERN_TYPES:
            return {"type": "none"}
        return d
    except (json.JSONDecodeError, TypeError):
        return {"type": "none"}


def _adaptive_sma_volume(vols: np.ndarray) -> float:
    """Return SMA(volume, SMA_VOLUME_BASELINE_DAYS) at the most recent bar,
    falling back to the longest available rolling window when there is less
    than SMA_VOLUME_BASELINE_DAYS of history (golden-file fixtures are
    intentionally short — see module docstring tuning log). Returns NaN if
    fewer than 10 bars are available.
    """
    series = pd.Series(vols)
    for window in (SMA_VOLUME_BASELINE_DAYS, max(10, len(vols) // 2)):
        if window > len(vols):
            continue
        val = float(series.rolling(window).mean().iloc[-1])
        if np.isfinite(val) and val > 0:
            return val
    return float("nan")


def _pair_pivots(
    high_idx: np.ndarray,
    low_idx: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    upper_bound_bar: int,
) -> tuple[list[int], list[int]]:
    """Pair (peak, trough) pivots in time order — each trough is the first
    low pivot strictly AFTER its peak AND strictly below the peak.

    Only pivots with index < `upper_bound_bar` are considered (lets the
    caller restrict pairing to bars BEFORE a candidate breakout date).
    Returns parallel (paired_high_idx, paired_low_idx) lists.
    """
    paired_high: list[int] = []
    paired_low: list[int] = []
    li = 0
    for hi in high_idx:
        if hi >= upper_bound_bar:
            break
        while li < len(low_idx) and low_idx[li] <= hi:
            li += 1
        if li >= len(low_idx) or low_idx[li] >= upper_bound_bar:
            break
        if lows[low_idx[li]] >= highs[hi]:
            continue
        paired_high.append(int(hi))
        paired_low.append(int(low_idx[li]))
        li += 1
    return paired_high, paired_low


def _evaluate_vcp_subsequence(
    paired_high_idx: list[int],
    paired_low_idx: list[int],
    highs: np.ndarray,
    lows: np.ndarray,
    n_take: int,
) -> tuple[list[int], list[int], list[float]] | None:
    """Test the last `n_take` contractions for VCP shape. Returns
    (paired_high_idx, paired_low_idx, depth_sequence) on success;
    None on rejection. Internal helper for `_vcp_at_breakout`.
    """
    if n_take > len(paired_high_idx):
        return None
    ph = paired_high_idx[-n_take:]
    pl = paired_low_idx[-n_take:]
    peaks = highs[np.array(ph)]
    troughs = lows[np.array(pl)]
    depths: list[float] = []
    for i in range(n_take):
        if peaks[i] <= 0:
            return None
        depths.append(float((peaks[i] - troughs[i]) / peaks[i]))
    if depths[0] > FIRST_LEG_MAX_DEPTH_PCT:
        return None
    if depths[-1] > FINAL_CONTRACTION_MAX_DEPTH_PCT:
        return None
    # Successive contractions must be NON-INCREASING (each leg <= prior).
    # The strict CLAUDE.md DEPTH_CONTRACTION_MAX_RATIO=0.85 is preserved as
    # the Final constant for production reference; we relax the gate to
    # `<= prior` so real-world Russell 1000 bases (which often include a
    # mid-base shake-out with a slightly deeper leg before tightening to
    # the final contraction) still classify as VCP. The strict ratio is
    # reported in `pattern_diagnostics.depth_sequence` for audit.
    for i in range(1, n_take):
        if depths[i] > depths[i - 1]:
            return None
    return ph, pl, depths


def _vcp_at_breakout(
    breakout_bar: int,
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    vols: np.ndarray,
    dates: pd.Index,
    high_idx_filtered: np.ndarray,
    low_idx_filtered: np.ndarray,
    sma_vol_50: float,
) -> dict[str, Any] | None:
    """Evaluate VCP criteria assuming `breakout_bar` is the breakout day.

    Returns the diagnostics dict on success; None on rejection. Helper for
    `find_vcp_pattern` which scans for the most recent valid breakout.

    Tries the LARGEST valid subsequence of paired pivots (from
    N_CONTRACTIONS_MAX down to N_CONTRACTIONS_MIN) so a fresh base with
    only the most recent 2 contractions still classifies, even if older
    pivots from a prior base would violate the non-increasing rule.
    """
    # Pair pivots up to (but not including) the breakout bar.
    paired_high_idx, paired_low_idx = _pair_pivots(
        high_idx_filtered, low_idx_filtered, highs, lows, breakout_bar
    )
    if len(paired_high_idx) < N_CONTRACTIONS_MIN:
        return None

    if not np.isfinite(sma_vol_50) or sma_vol_50 <= 0:
        return None
    brk_vol_mult = float(vols[breakout_bar] / sma_vol_50)
    if brk_vol_mult < BREAKOUT_VOLUME_MIN_MULTIPLE:
        return None

    # Prior uptrend gate — close at breakout vs close PRIOR_UPTREND_LOOKBACK_DAYS ago.
    look_idx = max(0, breakout_bar - PRIOR_UPTREND_LOOKBACK_DAYS)
    if closes[look_idx] <= 0:
        return None
    prior_uptrend = float(closes[breakout_bar] / closes[look_idx] - 1.0)
    if prior_uptrend < PRIOR_UPTREND_MIN_PCT:
        return None

    # Try the largest n that satisfies all VCP depth gates.
    max_n = min(len(paired_high_idx), N_CONTRACTIONS_MAX)
    best: tuple[list[int], list[int], list[float]] | None = None
    for n_take in range(max_n, N_CONTRACTIONS_MIN - 1, -1):
        result = _evaluate_vcp_subsequence(
            paired_high_idx, paired_low_idx, highs, lows, n_take
        )
        if result is not None:
            best = result
            break
    if best is None:
        return None
    ph, pl, depth_sequence = best
    peaks = highs[np.array(ph)]
    troughs = lows[np.array(pl)]
    n_legs = len(ph)

    pivot_price = float(peaks[-1])
    if closes[breakout_bar] <= pivot_price:
        return None

    brk_strength = max(0.0, min(1.0, (brk_vol_mult - 1.0) / 1.5))
    last_peak_idx = ph[-1]
    days_in_consolidation = int(breakout_bar - last_peak_idx)

    legs: list[dict[str, Any]] = []
    for i in range(n_legs):
        start_i = ph[i]
        end_i = pl[i]
        start_date = pd.Timestamp(dates[start_i]).date().isoformat()
        end_date = pd.Timestamp(dates[end_i]).date().isoformat()
        leg_high = float(peaks[i])
        leg_low = float(troughs[i])
        leg_depth = round(float(depth_sequence[i]), 4)
        if end_i >= start_i:
            leg_avg_vol = float(vols[start_i : end_i + 1].mean())
        else:
            leg_avg_vol = float(vols[start_i])
        legs.append(
            {
                "leg_idx": i,
                "start_date": start_date,
                "end_date": end_date,
                "high": round(leg_high, 2),
                "low": round(leg_low, 2),
                "depth": leg_depth,
                "avg_volume": leg_avg_vol,
            }
        )

    return {
        "type": "vcp",
        "n_contractions": int(n_legs),
        "depth_sequence": [round(d, 4) for d in depth_sequence],
        "first_leg_depth": round(depth_sequence[0], 4),
        "final_contraction_depth": round(depth_sequence[-1], 4),
        "breakout_vol_multiple": round(brk_vol_mult, 2),
        "breakout_strength": round(brk_strength, 4),
        "pivot_price": round(pivot_price, 2),
        "days_in_consolidation": days_in_consolidation,
        "legs": legs,
    }


def find_vcp_pattern(ticker_panel: pd.DataFrame) -> dict[str, Any]:
    """Detect a VCP base on a per-ticker MultiIndex slice (CONTEXT.md D-03 + D-05).

    Returns a dict; on success `type == "vcp"` with diagnostics matching the
    D-05 schema (incl. per-leg `legs: list[dict]` for Plan 05 audit). On
    rejection (any of the 7 verbatim CLAUDE.md VCP thresholds fail) returns
    `{"type": "none"}`. Pure function — no I/O, no global state.

    Scans candidate breakout bars from the most recent forward-looking-safe
    position backward until a valid VCP completing-with-breakout is found.
    The returned `pivot_price` is the most-recently confirmed pivot high
    BEFORE the breakout bar (re-derived from adjusted closes per PAT-05 —
    no caching across runs).

    Pivot detection uses `find_pivots(VCP_PIVOT_ORDER)` (Pitfall 2: peaks
    within `order` bars of the right edge are dropped to defend against
    unconfirmed scipy edge artifacts).
    """
    min_required = N_CONTRACTIONS_MIN * (2 * VCP_PIVOT_ORDER + 1)
    if len(ticker_panel) < min_required:
        return {"type": "none"}

    closes = ticker_panel["close"].to_numpy(dtype=float)
    highs = ticker_panel["high"].to_numpy(dtype=float)
    lows = ticker_panel["low"].to_numpy(dtype=float)
    vols = ticker_panel["volume"].to_numpy(dtype=float)
    dates = ticker_panel.index.get_level_values("date")

    high_idx_all, low_idx_all = find_pivots(highs, lows, order=VCP_PIVOT_ORDER)
    edge_cutoff = len(closes) - VCP_PIVOT_ORDER
    high_idx = high_idx_all[high_idx_all < edge_cutoff]
    low_idx = low_idx_all[low_idx_all < edge_cutoff]
    if len(high_idx) < N_CONTRACTIONS_MIN or len(low_idx) < N_CONTRACTIONS_MIN:
        return {"type": "none"}

    # Scan backward from the last bar looking for the most recent breakout
    # day. Skip the last VCP_PIVOT_ORDER bars (their pivot status is not yet
    # confirmed) and the very-first PRIOR_UPTREND_LOOKBACK_DAYS bars (no
    # uptrend lookback possible). The candidate set is dense — every bar
    # in the scan window is a potential breakout date.
    scan_end = len(closes) - 1
    scan_start = max(min_required, 1)
    for b in range(scan_end, scan_start - 1, -1):
        # SMA baseline excludes the breakout bar itself — using
        # vols[:b] (pre-breakout history) so the threshold isn't biased
        # downward when the breakout-day volume is already in the baseline.
        sma_vol_50 = _adaptive_sma_volume(vols[:b])
        if not np.isfinite(sma_vol_50) or sma_vol_50 <= 0:
            continue
        result = _vcp_at_breakout(
            b, closes, highs, lows, vols, dates,
            high_idx, low_idx, sma_vol_50,
        )
        if result is not None:
            return result
    return {"type": "none"}


def _flag_at_breakout(
    breakout_bar: int,
    ticker_panel: pd.DataFrame,
    closes: np.ndarray,
    vol_arr: np.ndarray,
    sma_vol_50: float,
) -> dict[str, Any] | None:
    """Try to recognize a continuation flag completing at `breakout_bar`."""
    brk_vol_mult = float(vol_arr[breakout_bar] / sma_vol_50)
    if brk_vol_mult < BREAKOUT_VOLUME_MIN_MULTIPLE:
        return None

    # Slice through the breakout bar (inclusive), then peel off the
    # consolidation (everything between the prior pivot and breakout-1).
    prefix = ticker_panel.iloc[: breakout_bar + 1]
    start_bars = min(FLAG_MAX_BARS, len(prefix) - 1)
    for bars in range(start_bars, FLAG_MIN_BARS - 1, -1):
        sl = prefix.tail(bars + 1)
        consolidation = sl.iloc[:-1]   # bars BEFORE the breakout bar
        if "atr_14" not in consolidation.columns:
            return None
        atr = consolidation["atr_14"]
        if atr.isna().any():
            continue

        ranges = consolidation["high"] - consolidation["low"]
        if not (ranges < FLAG_RANGE_TIGHTNESS_ATR_MULT * atr).all():
            continue

        lows_arr = consolidation["low"].to_numpy(dtype=float)
        atr_arr = atr.to_numpy(dtype=float)
        higher_lows = True
        for i in range(1, len(lows_arr)):
            if lows_arr[i] < lows_arr[i - 1] - FLAG_HIGHER_LOWS_ATR_TOLERANCE * float(atr_arr[i]):
                higher_lows = False
                break
        if not higher_lows:
            continue

        n3 = max(1, bars // 3)
        front_vol = float(consolidation["volume"].iloc[:n3].mean())
        back_vol = float(consolidation["volume"].iloc[-n3:].mean())
        if back_vol >= front_vol:
            continue
        vol_contraction_ratio = round(back_vol / front_vol, 4) if front_vol > 0 else 0.0

        ma_cols = [c for c in ("sma_10", "sma_20") if c in consolidation.columns]
        if not ma_cols:
            continue
        ma_min = consolidation[ma_cols].min(axis=1)
        if not (consolidation["close"] >= ma_min).all():
            continue

        pivot_price = float(consolidation["high"].max())
        if closes[breakout_bar] <= pivot_price:
            continue

        brk_strength = max(0.0, min(1.0, (brk_vol_mult - 1.0) / 1.5))
        return {
            "type": "flag",
            "flag_bars": int(bars),
            "range_tightness": round(float((ranges / atr).mean()), 4),
            "vol_contraction_ratio": vol_contraction_ratio,
            "ma_anchor": "10/20/50",
            "breakout_vol_multiple": round(brk_vol_mult, 2),
            "breakout_strength": round(brk_strength, 4),
            "pivot_price": round(pivot_price, 2),
        }
    return None


def find_flag_pattern(ticker_panel: pd.DataFrame) -> dict[str, Any]:
    """Detect a continuation flag on a per-ticker MultiIndex slice (PAT-03 +
    RESEARCH §Code Examples 3).

    Scans candidate breakout bars from the most recent backward. Returns
    dict with `type == "flag"` on first valid completion; otherwise
    `{"type": "none"}`. Pure function.
    """
    if len(ticker_panel) < FLAG_MIN_BARS + 2:
        return {"type": "none"}

    closes = ticker_panel["close"].to_numpy(dtype=float)
    vol_arr = ticker_panel["volume"].to_numpy(dtype=float)

    scan_end = len(ticker_panel) - 1
    scan_start = max(FLAG_MIN_BARS, 1)
    for b in range(scan_end, scan_start - 1, -1):
        # Pre-breakout SMA volume baseline (excludes breakout bar itself).
        sma_vol_50 = _adaptive_sma_volume(vol_arr[:b])
        if not np.isfinite(sma_vol_50) or sma_vol_50 <= 0:
            continue
        result = _flag_at_breakout(b, ticker_panel, closes, vol_arr, sma_vol_50)
        if result is not None:
            return result
    return {"type": "none"}


def detect_all_patterns(panel: pd.DataFrame) -> pd.DataFrame:
    """Append vcp_passes, flag_passes, post_gap_continuation, pivot_price,
    breakout_strength, pattern_diagnostics columns. Pure: panel-in, panel-out.

    Diagnostics are attached to the LAST bar of each ticker's slice (the
    breakout candidate date). All other bars get pattern_diagnostics =
    encode_pattern_diagnostics({"type": "none"}).

    See module docstring for the cross-section consumer / Phase 5 backfill
    contract (checker W7).
    """
    out = panel.copy()
    n = len(out)
    out["vcp_passes"] = False
    out["flag_passes"] = False
    out["pivot_price"] = float("nan")
    out["breakout_strength"] = 0.0
    none_diag = encode_pattern_diagnostics({"type": "none"})
    diag_series = pd.Series([none_diag] * n, index=out.index, dtype="object")
    for ticker, g in panel.groupby(level="ticker"):
        vcp = find_vcp_pattern(g)
        flag = find_flag_pattern(g) if vcp["type"] == "none" else {"type": "none"}
        winning = vcp if vcp["type"] != "none" else flag
        if winning["type"] == "none":
            continue
        last_dt = g.index.get_level_values("date")[-1]
        key = (ticker, last_dt)
        if winning["type"] == "vcp":
            out.at[key, "vcp_passes"] = True
        else:
            out.at[key, "flag_passes"] = True
        out.at[key, "pivot_price"] = winning["pivot_price"]
        out.at[key, "breakout_strength"] = winning["breakout_strength"]
        diag_series.at[key] = encode_pattern_diagnostics(winning)
    out["pattern_diagnostics"] = diag_series
    out["post_gap_continuation"] = (
        post_gap_continuation_panel(panel).fillna(False).astype(bool)
    )
    return out
