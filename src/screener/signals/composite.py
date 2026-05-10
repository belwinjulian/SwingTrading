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

import pandas as pd

# Pre-registered weights — CHANGING THESE WITHOUT UPDATING
# docs/strategy_v1_preregistration.md FAILS CI (FND-05, D-09).
# Sum is 1.00. Phase 6 keeps the same keys; Phase 4 zeros three of them
# via PHASE_4_ZEROED below.
DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "rs": 0.25,
    "trend": 0.20,
    "pattern": 0.20,    # zeroed in Phase 4 (D-01); active in Phase 6
    "volume": 0.10,
    "earnings": 0.15,   # zeroed in Phase 4 (D-01); active in Phase 6
    "catalyst": 0.10,   # zeroed in Phase 4 (D-01); active in Phase 6
}

# Components NOT computed in Phase 4 (D-01). The score function emits
# `<key>_component = 0.0` for each. The report renderer (Plan 04-04)
# iterates this set to render "—(Phase 6)" labels per D-04. When Phase 6
# implements pattern/earnings/catalyst, REMOVE keys from this set; the
# report placeholders disappear automatically.
PHASE_4_ZEROED: Final[frozenset[str]] = frozenset({"pattern", "earnings", "catalyst"})


def score(
    panel: pd.DataFrame,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
) -> pd.DataFrame:
    """Compute composite_score per ticker via weighted-sum of components.

    Live components (Phase 4): rs, trend, volume.
    Zeroed components (Phase 4 — D-01): pattern, earnings, catalyst.

    Args:
        panel: MultiIndex (ticker, date) DataFrame containing AT LEAST these
            columns: rs_rating (Int64Dtype, nullable), trend_template_score
            (Int64Dtype, 0-8, produced by passes_trend_template), dryup_ratio
            (float, produced by build_panel).
        weights: dict[str, float] with keys ⊆ DEFAULT_WEIGHTS.keys() and
            values summing to 1.0 ± 1e-6. Default is DEFAULT_WEIGHTS.

    Returns:
        The input panel with 7 new columns appended:
            rs_component       — rs_rating / 99.0, NaN -> 0.0
            trend_component    — trend_template_score / 8.0, NaN -> 0.0
            volume_component   — clip(1 - (dryup_ratio - 0.5)/1.5, 0, 1),
                                 NaN -> 0.0 (D-02 + Pitfall 4)
            pattern_component  — 0.0 (Phase 4 placeholder, D-01)
            earnings_component — 0.0 (Phase 4 placeholder, D-01)
            catalyst_component — 0.0 (Phase 4 placeholder, D-01)
            composite_score    — Σ weights[k] * <k>_component * 100,
                                 in [0, 100] when weights sum to 1.0.
                                 Phase 4 effective range: ~[0, 55] because
                                 three components are zeroed (sum of live
                                 weights is 0.55).

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
        raise ValueError(
            f"Weights must sum to 1.0; got {sum(weights.values())}"
        )

    out = panel.copy()

    # Live components (D-02 + D-13)
    out["rs_component"] = (
        panel["rs_rating"].astype("Float64") / 99.0
    ).fillna(0.0)
    out["trend_component"] = (
        panel["trend_template_score"].astype("Float64") / 8.0
    ).fillna(0.0)
    # D-02 volume formula: linear from 0.5->1.0, 2.0->0.0; NaN -> 0 (Pitfall 4)
    out["volume_component"] = (
        (1.0 - (panel["dryup_ratio"] - 0.5) / 1.5).clip(0.0, 1.0).fillna(0.0)
    )
    # Phase 4 placeholders (D-01) — Phase 6 swaps in real values.
    out["pattern_component"] = 0.0
    out["earnings_component"] = 0.0
    out["catalyst_component"] = 0.0

    # Weighted-sum scoring loop — iterates weights.items() per D-13.
    # M2 ML extension: adding `"ml_probability"` to DEFAULT_WEIGHTS plus an
    # `out["ml_probability_component"] = ...` line above is the ONLY change
    # needed — this loop iterates whatever keys `weights` contains.
    composite = pd.Series(0.0, index=panel.index)
    for key, w in weights.items():
        composite = composite + w * out[f"{key}_component"]
    out["composite_score"] = (composite * 100.0).astype(float)
    return out
