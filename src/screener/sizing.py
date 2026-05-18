"""sizing — per-playbook entry / stop / shares dispatch (SIZ-01..05).

Pure-function discipline (Phase 1 D-16): no I/O, no global state, panel-in /
panel-out. Imports pandas + numpy + structlog + indicators.patterns helpers.

Dispatch model (CONTEXT D-07): three private `_stop_*` helpers registered in
the module-level `STOP_HELPERS: Final[dict[str, Callable]]` registry. SC-2 is
satisfied trivially via `assert STOP_HELPERS["qullamaggie_continuation"] is
_stop_qullamaggie` (RESEARCH §Pattern 1).

Per-row reject classes (Pitfalls 5 + 6): adr_exceeded, invalid_stop,
missing_diagnostics. Rejected rows carry adr_rejected=True with rejection_reason
populated; their shares = 0.

ATR-zone classifier (D-09): 3 buckets via classify_atr_zone(); boundary
semantics ≤0.66 → in-zone, ≤1.0 → extended, >1.0 → chase, skip.

Trail labels (D-08): _trail_rule_label() returns a display STRING (sizing
does NOT compute trail values; the report renders the label per pick).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Final

import numpy as np
import pandas as pd
import structlog

from screener.indicators.patterns import (
    FLAG_PIVOT_ORDER,
    decode_pattern_diagnostics,
    find_pivots,
)

log = structlog.get_logger(__name__)

# --- D-09 ATR-zone thresholds (locked, not Settings-overridable per Pitfall 5)
IN_ZONE_ATR: Final[float] = 0.66
EXTENDED_ATR: Final[float] = 1.00

# --- D-07 leader_hold swing-low lookback (reuses indicators.patterns conventions)
LEADER_SWING_LOOKBACK_BARS: Final[int] = 20      # same as FLAG_MAX_BARS
LEADER_SWING_PIVOT_ORDER: Final[int] = FLAG_PIVOT_ORDER  # reuse Phase 6 constant

# --- D-08 Qullamaggie trail tier boundaries (ADR%)
QULL_TRAIL_FAST_ADR: Final[float] = 6.0    # >= 6.0 → 10d SMA
QULL_TRAIL_MEDIUM_ADR: Final[float] = 4.0  # 4.0..6.0 → 20d SMA; else → 50d SMA

# --- D-07 leader_hold stop bounds
LEADER_STOP_FLOOR_ATR_MULTIPLE: Final[float] = 1.5
LEADER_STOP_CAP_ATR_MULTIPLE: Final[float] = 2.0

# --- D-05 per-position cap
MAX_POSITION_FRACTION: Final[float] = 0.25


# --- ATR zone classifier (SIZ-05 / D-09) ---------------------------------

def classify_atr_zone(pivot_distance_atr: float) -> str:
    """D-09 3-bucket classifier.

    Boundary semantics (per RESEARCH §Code Examples Pattern 3 verbatim):
      exactly 0.66 → in-zone; exactly 1.00 → extended; anything > 1.00 → chase, skip.
    """
    if pivot_distance_atr <= IN_ZONE_ATR:
        return "in-zone"
    if pivot_distance_atr <= EXTENDED_ATR:
        return "extended"
    return "chase, skip"


# --- Trail-rule label dispatch (SIZ-04 / D-08) ---------------------------

def _trail_rule_label(row: "pd.Series") -> str:
    """Return D-08 trail rule as a display string for the report.

    Sizing emits the LABEL ONLY (RESEARCH §Pattern 3); the report renders it
    under `Trail:` per CONTEXT specifics. Qullamaggie tier boundaries
    inclusive at the QULL_TRAIL_MEDIUM_ADR and QULL_TRAIL_FAST_ADR values
    (4.0 and 6.0 are INSIDE their respective tiers).
    """
    tag = str(row["playbook_tag"])
    if tag == "qullamaggie_continuation":
        adr = float(row.get("adr_pct", 0.0))
        if adr >= QULL_TRAIL_FAST_ADR:
            return "10d SMA"
        if adr >= QULL_TRAIL_MEDIUM_ADR:
            return "20d SMA"
        return "50d SMA"
    if tag == "minervini_vcp":
        return "21d EMA (then 50d SMA after 15 bars)"
    if tag == "leader_hold":
        return "50d SMA close"
    return ""


# --- Per-playbook stop helpers (SIZ-03 / D-07) ---------------------------

def _stop_qullamaggie(row: "pd.Series", ticker_history: "pd.DataFrame") -> float:
    """D-07: entry-day low = the D-0 'low' bar (same bar that triggered breakout).

    The cross-section row is the snapshot-day OHLC by construction (the caller
    extracts it via `panel.xs(snapshot_date, level='date')`); RESEARCH A2.
    """
    return float(row["low"])


def _stop_minervini_vcp(row: "pd.Series", ticker_history: "pd.DataFrame") -> float:
    """D-07: final_contraction_low = pivot_price × (1 − final_contraction_depth).

    Pitfall 5 guard: assert diag['type'] == 'vcp' AND required keys present.
    If diagnostics are malformed (corrupt blob with type='none' on a vcp-tagged
    row), raise ValueError so compute_sizing's outer try/except marks the
    pick adr_rejected with rejection_reason='missing_diagnostics'.
    """
    diag = decode_pattern_diagnostics(str(row["pattern_diagnostics"]))
    if (
        diag.get("type") != "vcp"
        or "pivot_price" not in diag
        or "final_contraction_depth" not in diag
    ):
        raise ValueError("missing_diagnostics")
    pivot = float(diag["pivot_price"])
    final_depth = float(diag["final_contraction_depth"])
    return pivot * (1.0 - final_depth)


def _recent_swing_low_distance(
    ticker_history: "pd.DataFrame",
    entry_price: float,
    atr: float,
) -> float:
    """Return (entry_price − most_recent_swing_low) over the last 20 bars.

    Reuses screener.indicators.patterns.find_pivots with order=3 (same as
    FLAG_PIVOT_ORDER). RESEARCH §Pattern 2.

    Fallback when no trough is found in the window OR history is too short
    (< 2 × order + 1 bars): return 2.0 × atr — net effect with the outer
    `max(1.5×atr, ...)` and `min(..., 2×atr)` clamps in `_stop_leader_hold`
    is a stop at `entry_price − 2×atr`.
    """
    if "low" not in ticker_history.columns or "high" not in ticker_history.columns:
        return 2.0 * atr
    tail = ticker_history.tail(LEADER_SWING_LOOKBACK_BARS)
    if len(tail) < (2 * LEADER_SWING_PIVOT_ORDER + 1):
        return 2.0 * atr
    highs = tail["high"].to_numpy(dtype=float)
    lows = tail["low"].to_numpy(dtype=float)
    _, low_idx = find_pivots(highs, lows, order=LEADER_SWING_PIVOT_ORDER)
    if len(low_idx) == 0:
        return 2.0 * atr
    last_trough_low = float(lows[int(low_idx[-1])])
    return max(0.0, entry_price - last_trough_low)


def _stop_leader_hold(row: "pd.Series", ticker_history: "pd.DataFrame") -> float:
    """D-07: entry_price − clamp(max(1.5×ATR, recent_swing_low_distance), max=2×ATR)."""
    entry = float(row["close"])
    atr = float(row["atr_14"])
    swing_dist = _recent_swing_low_distance(ticker_history, entry, atr)
    raw_distance = max(LEADER_STOP_FLOOR_ATR_MULTIPLE * atr, swing_dist)
    capped = min(raw_distance, LEADER_STOP_CAP_ATR_MULTIPLE * atr)
    return entry - capped


# --- Dispatch registry (SC-2 satisfaction) -------------------------------

STOP_HELPERS: Final[dict[str, Callable[["pd.Series", "pd.DataFrame"], float]]] = {
    "qullamaggie_continuation": _stop_qullamaggie,
    "minervini_vcp": _stop_minervini_vcp,
    "leader_hold": _stop_leader_hold,
}


# --- Internal helpers for compute_sizing ---------------------------------

def _compute_pivot_distance_atr_breakout(
    close: float, atr: float, pattern_diagnostics: str
) -> float:
    """Distance ABOVE breakout pivot in ATR units: (close − pivot_price) / atr.

    Phase 7 NEW column (RESEARCH Open Question 3 / Assumption A3) — distinct
    from Phase 4's `pivot_distance_atr` which is (high_52w − close) / atr
    (distance BELOW the 52w high). The new column feeds the D-09 atr_zone
    3-bucket classifier; the Phase 4 column feeds Phase 4's 2-state pivot_zone.

    Returns NaN when atr is 0 or pivot_price is missing from diagnostics
    (e.g. type='none' for leader_hold picks — they have no breakout pivot).
    """
    if atr <= 0:
        return float("nan")
    diag = decode_pattern_diagnostics(str(pattern_diagnostics))
    if "pivot_price" not in diag:
        return float("nan")
    pivot = float(diag["pivot_price"])
    return (close - pivot) / atr


def compute_sizing(
    cross: pd.DataFrame,
    panel: pd.DataFrame,
    account_equity: float,
    risk_pct: float,
    regime_score: float,
) -> pd.DataFrame:
    """SIZ-01..05 per-playbook dispatch. Pure: returns NEW DataFrame.

    Args:
        cross: snapshot-day cross-section (one row per ticker, indexed by 'ticker'
            or with 'ticker' column). MUST carry: close, low, high, atr_14,
            adr_pct, playbook_tag, pattern_diagnostics. (Pitfall 7: tests
            without these columns will KeyError loudly — fix the fixture, not
            this function.)
        panel: full MultiIndex(ticker, date) history needed for the leader_hold
            swing-low lookback (D-07 / RESEARCH §Pattern 2).
        account_equity: from Settings.ACCOUNT_EQUITY (D-05). Caller responsibility.
        risk_pct: from Settings.RISK_PCT (D-05). Caller responsibility.
        regime_score: continuous regime score from regime.compute_for_date (D-12).
            Multiplies the shares numerator; regime_score=0 → shares=0 by design.

    Returns:
        out: cross.copy() with 9 new columns appended:
            stop_price (float >0 or 0 for rejected),
            entry_price (float = close),
            shares (Int64 ≥0),
            risk_per_share (float ≥0),
            atr_zone (str ∈ {'in-zone','extended','chase, skip'}),
            pivot_distance_atr_breakout (float or NaN),
            trail_rule_label (str),
            adr_rejected (bool),
            rejection_reason (str — '', 'adr_exceeded', 'invalid_stop', 'missing_diagnostics').
    """
    out = cross.copy()
    n = len(out)
    if n == 0:
        # Pre-allocate empty columns for downstream schema validation.
        out["stop_price"] = pd.Series(dtype=float)
        out["entry_price"] = pd.Series(dtype=float)
        out["shares"] = pd.array([], dtype=pd.Int64Dtype())
        out["risk_per_share"] = pd.Series(dtype=float)
        out["atr_zone"] = pd.Series(dtype=str)
        out["pivot_distance_atr_breakout"] = pd.Series(dtype=float)
        out["trail_rule_label"] = pd.Series(dtype=str)
        out["adr_rejected"] = pd.Series(dtype=bool)
        out["rejection_reason"] = pd.Series(dtype=str)
        return out

    # Per-row computation (one pass — readable over vectorization for n≤R1000).
    stop_prices: list[float] = []
    entry_prices: list[float] = []
    risk_per_shares: list[float] = []
    atr_zones: list[str] = []
    pdists_breakout: list[float] = []
    trail_labels: list[str] = []
    adr_rejs: list[bool] = []
    reasons: list[str] = []
    shares_list: list[int] = []

    # Per-ticker history slice cache for leader_hold swing-low lookback.
    panel_has_ticker_index = isinstance(panel.index, pd.MultiIndex) and (
        "ticker" in (panel.index.names or [])
    )

    def _ticker_history(t: str) -> pd.DataFrame:
        if not panel_has_ticker_index:
            return pd.DataFrame(columns=["high", "low"])
        try:
            return panel.xs(t, level="ticker", drop_level=True)
        except KeyError:
            return pd.DataFrame(columns=["high", "low"])

    tickers = out.index if out.index.name == "ticker" else out["ticker"]
    for i, ticker in enumerate(tickers):
        ticker = str(ticker)
        row = out.iloc[i]
        tag = str(row["playbook_tag"])
        close_price = float(row["close"])
        atr = float(row["atr_14"])
        adr_pct = float(row["adr_pct"])
        diag_str = str(row["pattern_diagnostics"])

        # --- Stop dispatch (D-07) -------------------------------------
        helper = STOP_HELPERS.get(tag)
        rejection = ""
        try:
            stop_price = helper(row, _ticker_history(ticker)) if helper else close_price
        except ValueError as e:
            # Pitfall 5: missing_diagnostics — reject the pick.
            stop_price = close_price
            rejection = "missing_diagnostics" if str(e) == "missing_diagnostics" else "invalid_stop"

        # --- Risk per share + invalid-stop guard (Pitfall 6) ----------
        risk_per_share = close_price - stop_price
        if rejection == "" and risk_per_share <= 0.0:
            rejection = "invalid_stop"
            risk_per_share = max(0.0, risk_per_share)

        # --- 1×ADR auto-reject (D-06 / SIZ-02) ------------------------
        adr_dollars = (adr_pct / 100.0) * close_price
        if rejection == "" and risk_per_share > adr_dollars and adr_dollars > 0:
            rejection = "adr_exceeded"

        # --- Shares (D-05 / SIZ-01) -----------------------------------
        if rejection != "" or risk_per_share <= 0:
            shares = 0
        else:
            raw_shares = int(np.floor(
                (account_equity * risk_pct * regime_score) / risk_per_share
            ))
            cap_shares = int(np.floor(
                account_equity * MAX_POSITION_FRACTION / close_price
            ))
            shares = max(0, min(raw_shares, cap_shares))

        # --- pivot_distance_atr_breakout + ATR zone (D-09 / SIZ-05) ---
        pdist = _compute_pivot_distance_atr_breakout(close_price, atr, diag_str)
        # Use the existing Phase 4 column if breakout pivot is missing (leader_hold).
        zone_input = pdist if not np.isnan(pdist) else 0.0  # leader_hold defaults to in-zone
        atr_zone = classify_atr_zone(zone_input)

        # --- Trail label (D-08 / SIZ-04) ------------------------------
        trail = _trail_rule_label(row)

        stop_prices.append(float(stop_price))
        entry_prices.append(close_price)
        risk_per_shares.append(float(risk_per_share))
        atr_zones.append(atr_zone)
        pdists_breakout.append(float(pdist))
        trail_labels.append(trail)
        adr_rejs.append(rejection != "")
        reasons.append(rejection)
        shares_list.append(shares)

    out["stop_price"] = stop_prices
    out["entry_price"] = entry_prices
    out["shares"] = pd.array(shares_list, dtype=pd.Int64Dtype())
    out["risk_per_share"] = risk_per_shares
    out["atr_zone"] = atr_zones
    out["pivot_distance_atr_breakout"] = pdists_breakout
    out["trail_rule_label"] = trail_labels
    out["adr_rejected"] = adr_rejs
    out["rejection_reason"] = reasons

    log.info(
        "sizing_applied",
        n_input=n,
        n_actionable=int(sum(1 for r in adr_rejs if not r)),
        n_rejected_adr=int(sum(1 for r in reasons if r == "adr_exceeded")),
        n_rejected_stop=int(sum(1 for r in reasons if r == "invalid_stop")),
        n_rejected_missing_diag=int(sum(1 for r in reasons if r == "missing_diagnostics")),
    )

    return out
