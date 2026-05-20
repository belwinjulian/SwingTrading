"""composite — pre-registered weighted composite scorer (D-12, D-13).

DEFAULT_WEIGHTS is a Final dict importable by scripts/check_preregistration.py
without instantiating any pandas frame. M2 extension seam (D-13): adding a
new key (e.g., "ml_probability") is a one-line append; downstream iterators
over weights.items() need no changes.

Pure-function discipline (Phase 1 D-16): no I/O, no global state, panel-in /
panel-out. Imports only pandas + stdlib typing.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

# Phase 6 D-13 — playbook tie-breaker thresholds. Final (not Settings-overridable)
# to defend Critical Pitfall 5 (in-sample tuning). Tuned via paper trading
# in v1.x, never against backtest results.
QULL_MAX_BARS: Final[int] = 25
QULL_MIN_ADR_PCT: Final[float] = 5.0
MINERVINI_MIN_BARS: Final[int] = 25
MINERVINI_MAX_FINAL_CONTRACTION_PCT: Final[float] = 8.0
LEADER_MIN_RS: Final[int] = 90

# Pre-registered weights — CHANGING THESE WITHOUT UPDATING
# docs/strategy_v1_preregistration.md FAILS CI (FND-05, D-09).
# Sum is 1.00. Phase 6 keeps the same keys; Phase 4 zeros three of them
# via PHASE_4_ZEROED below.
DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "rs": 0.25,
    "trend": 0.20,
    "pattern": 0.20,  # zeroed in Phase 4 (D-01); active in Phase 6
    "volume": 0.10,
    "earnings": 0.15,  # zeroed in Phase 4 (D-01); active in Phase 6
    "catalyst": 0.10,  # zeroed in Phase 4 (D-01); active in Phase 6
}

# Phase 6 D-16: empty frozenset — pattern/earnings/catalyst components are now LIVE.
# Phase 4 had frozenset({"pattern", "earnings", "catalyst"}) — all three zeroed.
# Phase 6 removes them from this set so the report placeholders auto-disappear.
PHASE_4_ZEROED: Final[frozenset[str]] = frozenset()


def score_pattern_component(panel: pd.DataFrame) -> pd.Series:
    """D-17: breakout_strength for VCP/flag picks; 0.0 for leader_hold/no-pattern.

    The columns vcp_passes / flag_passes / breakout_strength are added
    upstream by indicators/patterns.detect_all_patterns (Plan 02).

    Columns missing from panel (e.g., pre-Phase-6 minimal test panels) default
    to 0.0 so the function degrades gracefully when called on legacy panels.
    """
    zero = pd.Series(0.0, index=panel.index)
    if "vcp_passes" not in panel.columns or "flag_passes" not in panel.columns:
        return zero
    has_pattern = panel["vcp_passes"].fillna(False) | panel["flag_passes"].fillna(False)
    if "breakout_strength" not in panel.columns:
        return zero
    comp = panel["breakout_strength"].where(has_pattern, 0.0).fillna(0.0)
    return comp.clip(0.0, 1.0).astype(float)


def score_earnings_component(panel: pd.DataFrame) -> pd.Series:
    """D-18: 1.0 if canslim_c_passes else 0.0. C-only — no L/M double-count.

    canslim_c_passes is added upstream by signals/canslim.canslim_c_overlay
    (Plan 04 Task 2). signals/canslim does not import data/ — Plan 05's
    pipeline.py bridges persistence.read_fundamentals -> canslim.

    Column missing from panel defaults to 0.0 for graceful degradation on
    legacy panels.
    """
    if "canslim_c_passes" not in panel.columns:
        return pd.Series(0.0, index=panel.index)
    return panel["canslim_c_passes"].fillna(False).astype(float)


def score_catalyst_component(panel: pd.DataFrame) -> pd.Series:
    """D-11: equal-weighted mean of three booleans in [0,1].

    (earnings_proximity + crossed_52w_high_within_60d + insider_cluster_buy) / 3

    earnings_proximity = 1 if 0 <= days_to_next_earnings <= 14 else 0
    (D-11; checker W5: the >=0 guard rejects stale next_earnings_date rows
     where the calendared event has already passed without ingestion refresh)
    The three input columns are added upstream by publishers/pipeline.py
    (Plan 05).

    All three columns missing from panel defaults to 0.0 for graceful degradation
    on legacy panels.
    """
    zero = pd.Series(0.0, index=panel.index)
    if (
        "days_to_next_earnings" not in panel.columns
        and "crossed_52w_high_within_60d" not in panel.columns
        and "insider_cluster_buy" not in panel.columns
    ):
        return zero
    # Checker W5: negative days_to_next_earnings means a STALE next_earnings_date
    # (the calendared event already passed without ingestion refresh). Treat as
    # 0, not 1 — the catalyst fires only on a real-and-upcoming event in [0, 14].
    days = panel.get("days_to_next_earnings", pd.Series(999, index=panel.index)).fillna(999)
    earnings_prox = ((days >= 0) & (days <= 14)).astype(float)
    crossed_52w_col = panel.get("crossed_52w_high_within_60d", pd.Series(False, index=panel.index))
    crossed_52w = crossed_52w_col.fillna(False).astype(float)
    cluster_col = panel.get("insider_cluster_buy", pd.Series(False, index=panel.index))
    cluster = cluster_col.fillna(False).astype(float)
    return ((earnings_prox + crossed_52w + cluster) / 3.0).clip(0.0, 1.0)


def score(
    panel: pd.DataFrame,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
) -> pd.DataFrame:
    """Compute composite_score per ticker via weighted-sum of components.

    Live components (Phase 6): rs, trend, volume, pattern, earnings, catalyst.

    Args:
        panel: MultiIndex (ticker, date) DataFrame containing AT LEAST these
            columns: rs_rating (Int64Dtype, nullable), trend_template_score
            (Int64Dtype, 0-8, produced by passes_trend_template), dryup_ratio
            (float, produced by build_panel), vcp_passes (bool), flag_passes
            (bool), breakout_strength (float), canslim_c_passes (bool),
            days_to_next_earnings (int/float), crossed_52w_high_within_60d
            (bool), insider_cluster_buy (bool).
        weights: dict[str, float] with keys ⊆ DEFAULT_WEIGHTS.keys() and
            values summing to 1.0 ± 1e-6. Default is DEFAULT_WEIGHTS.

    Returns:
        The input panel with 7 new columns appended:
            rs_component       — rs_rating / 99.0, NaN -> 0.0
            trend_component    — trend_template_score / 8.0, NaN -> 0.0
            volume_component   — clip(1 - (dryup_ratio - 0.5)/1.5, 0, 1),
                                 NaN -> 0.0 (D-02 + Pitfall 4)
            pattern_component  — breakout_strength if vcp/flag, else 0.0 (D-17)
            earnings_component — 1.0 if canslim_c_passes else 0.0 (D-18)
            catalyst_component — (earnings_prox + 52w_cross + insider) / 3 (D-11)
            composite_score    — Σ weights[k] * <k>_component * 100,
                                 in [0, 100] when weights sum to 1.0.

    Raises:
        ValueError: if `weights` contains keys not in DEFAULT_WEIGHTS.
        ValueError: if `weights.values()` does not sum to 1.0 within 1e-6.

    D-13 contract: this function MUST iterate `weights.items()` and look up
    component columns via the f"{key}_component" pattern. Hardcoded column
    references (e.g., panel["rs_rating"] inside the scoring loop) defeat
    the M2 extension seam — adding `"ml_probability"` to DEFAULT_WEIGHTS
    must require ZERO refactor in this function.
    """
    # Validate weights dict contract (D-13 + Pitfall 11)
    unknown = set(weights) - set(DEFAULT_WEIGHTS)
    if unknown:
        raise ValueError(f"Unknown weight keys: {sorted(unknown)}")
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError(f"Weights must sum to 1.0; got {sum(weights.values())}")

    out = panel.copy()

    # Live components (D-02 + D-13)
    out["rs_component"] = (panel["rs_rating"].astype("Float64") / 99.0).fillna(0.0)
    out["trend_component"] = (panel["trend_template_score"].astype("Float64") / 8.0).fillna(0.0)
    # D-02 volume formula: linear from 0.5->1.0, 2.0->0.0; NaN -> 0 (Pitfall 4)
    out["volume_component"] = (1.0 - (panel["dryup_ratio"] - 0.5) / 1.5).clip(0.0, 1.0).fillna(0.0)
    # Phase 6 D-16: full activation — three helpers replace the Phase 4 zero placeholders.
    out["pattern_component"] = score_pattern_component(panel)
    out["earnings_component"] = score_earnings_component(panel)
    out["catalyst_component"] = score_catalyst_component(panel)

    # Weighted-sum scoring loop — iterates weights.items() per D-13.
    # M2 ML extension: adding `"ml_probability"` to DEFAULT_WEIGHTS plus an
    # `out["ml_probability_component"] = ...` line above is the ONLY change
    # needed — this loop iterates whatever keys `weights` contains.
    composite = pd.Series(0.0, index=panel.index)
    for key, w in weights.items():
        composite = composite + w * out[f"{key}_component"]
    out["composite_score"] = (composite * 100.0).astype(float)
    return out


def tag_playbook(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute playbook_tag + 3 binary diagnostic scores per pick (CMP-02..04).

    D-14 tie-break: Qullamaggie wins over Minervini when both fire (encoded
    via np.select with qull_mask FIRST in the conditions list — earlier
    conditions take precedence over later ones; checker W8).
    D-15: leader_hold = passes_trend_template AND rs_rating >= LEADER_MIN_RS
          AND pattern_diagnostics["type"] == "none". Picks failing all three
          scores get playbook_tag = "none" (Plan 05 filters from report).

    Args:
        panel: MultiIndex (ticker, date) DataFrame with AT LEAST: adr_pct,
            rs_rating, passes_trend_template, pattern_diagnostics (JSON str),
            vcp_passes, flag_passes, breakout_strength.

    Returns:
        The input panel with 4 new columns appended:
            qullamaggie_score (Int64 0/1)
            minervini_score (Int64 0/1)
            leader_hold_score (Int64 0/1)
            playbook_tag (str — one of: qullamaggie_continuation, minervini_vcp,
                          leader_hold, none)
    """
    from screener.indicators.patterns import decode_pattern_diagnostics

    out = panel.copy()
    diag = panel["pattern_diagnostics"].apply(decode_pattern_diagnostics)
    pattern_type = diag.apply(lambda d: d.get("type", "none"))
    # pattern_bars: prefer VCP days_in_consolidation, else flag flag_bars, else 0
    pattern_bars = diag.apply(
        lambda d: int(d.get("days_in_consolidation", d.get("flag_bars", 0)) or 0)
    )
    final_contraction_pct = diag.apply(
        lambda d: float(d.get("final_contraction_depth", 1.0) or 1.0) * 100.0
    )

    adr_pct = panel["adr_pct"].fillna(0.0)
    rs_rating = panel["rs_rating"].fillna(0).astype(int)
    ptt = panel["passes_trend_template"].fillna(False)

    qull_mask = (
        pattern_type.isin(["vcp", "flag"])
        & (pattern_bars < QULL_MAX_BARS)
        & (adr_pct >= QULL_MIN_ADR_PCT)
    )
    mvp_mask = (pattern_type == "vcp") & (
        (pattern_bars >= MINERVINI_MIN_BARS)
        | (final_contraction_pct <= MINERVINI_MAX_FINAL_CONTRACTION_PCT)
    )
    leader_mask = ptt & (rs_rating >= LEADER_MIN_RS) & (pattern_type == "none")

    out["qullamaggie_score"] = qull_mask.astype("Int64")
    out["minervini_score"] = mvp_mask.astype("Int64")
    out["leader_hold_score"] = leader_mask.astype("Int64")

    # D-14 precedence via np.select — Qullamaggie wins (checker W8): condition
    # order in the list IS the precedence. Earlier conditions take precedence
    # over later ones; default fires when no condition matches.
    ldr_only = leader_mask & ~qull_mask & ~mvp_mask
    conditions = [qull_mask, mvp_mask, ldr_only]
    choices = ["qullamaggie_continuation", "minervini_vcp", "leader_hold"]
    out["playbook_tag"] = np.select(conditions, choices, default="none")
    return out
