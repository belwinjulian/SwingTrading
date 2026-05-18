---
phase: 07-sizing-finalization-paper-trade-journal
plan: "02"
type: execute
wave: 1
depends_on: ["07-01"]
files_modified:
  - src/screener/sizing.py
  - tests/test_sizing.py
  - tests/test_architecture.py
autonomous: true
requirements: [SIZ-01, SIZ-02, SIZ-03, SIZ-04, SIZ-05]
requirements_addressed: [SIZ-01, SIZ-02, SIZ-03, SIZ-04, SIZ-05]
tags: [phase-7, sizing, pure-function, dispatch-registry, stop-helpers, trail-labels, atr-zone]

must_haves:
  truths:
    - "sizing.compute_sizing(cross, panel, account_equity, risk_pct, regime_score) returns a NEW cross-section with 9 new columns (stop_price, entry_price, shares, risk_per_share, atr_zone, pivot_distance_atr_breakout, trail_rule_label, adr_rejected, rejection_reason) and never mutates the input"
    - "STOP_HELPERS dict registry maps every playbook_tag to a private _stop_* helper (SC-2 trivially satisfied)"
    - "Per-playbook stop dispatch matches D-07: qullamaggie → entry-day low; minervini_vcp → pivot_price × (1 − final_contraction_depth) from pattern_diagnostics; leader_hold → entry_price − clamp(max(1.5×ATR, recent_swing_low_distance), 2×ATR)"
    - "1×ADR auto-reject per D-06 / SIZ-02: row marked adr_rejected=True with rejection_reason='adr_exceeded' when risk_per_share > (adr_pct/100) × entry_price"
    - "Invalid-stop guard per Pitfall 6: entry_price <= stop_price → adr_rejected=True with rejection_reason='invalid_stop' (no ZeroDivisionError, shares=0)"
    - "shares formula per D-05 / SIZ-01: floor((eq × risk_pct × regime_score) / (entry − stop)), capped at floor(eq × 0.25 / entry)"
    - "atr_zone 3-bucket classifier per D-09 / SIZ-05: ≤0.66 → in-zone; ≤1.0 → extended; >1.0 → chase, skip"
    - "Trail-rule labels per D-08 / SIZ-04: Qullamaggie ADR%-tier (10/20/50d SMA), Minervini '21d EMA (then 50d SMA after 15 bars)', leader '50d SMA close'"
    - "11 unit tests pass (test_sizing.py — every skeleton from Plan 07-01 has a real body)"
    - "sizing.py is a pure function module — no I/O, no global state, imports only from {signals, regime, config, obs, indicators.patterns}"
    - "test_architecture.py ALLOWED dict line 35 EXTENDED to include `indicators` (sizing: {signals, regime, config, obs, indicators}) so sizing.py can import indicators.patterns.find_pivots + decode_pattern_diagnostics per RESEARCH §Pattern 1/2 — this is the only architecture-test change Phase 7 makes"
  artifacts:
    - path: "src/screener/sizing.py"
      provides: "compute_sizing() + STOP_HELPERS registry + 3 _stop_* helpers + classify_atr_zone + _trail_rule_label + _recent_swing_low_distance"
      min_lines: 200
      contains: "STOP_HELPERS: Final"
    - path: "tests/test_sizing.py"
      provides: "11 real test bodies (replaces Plan 07-01 skeletons in-place)"
      contains: "assert STOP_HELPERS"
  key_links:
    - from: "src/screener/sizing.py"
      to: "src/screener/indicators/patterns.py"
      via: "from screener.indicators.patterns import find_pivots, decode_pattern_diagnostics"
      pattern: "from screener\\.indicators\\.patterns import"
    - from: "src/screener/sizing.py compute_sizing()"
      to: "src/screener/config.py Settings"
      via: "account_equity + risk_pct parameters passed by caller (publishers/pipeline.py)"
      pattern: "def compute_sizing\\(.*account_equity: float.*risk_pct: float"
    - from: "src/screener/sizing.py STOP_HELPERS"
      to: "tests/test_sizing.py::test_stop_dispatch_per_playbook"
      via: "registry import + `is` identity assertion"
      pattern: "STOP_HELPERS\\[.qullamaggie_continuation.\\] is _stop_qullamaggie"

user_setup: []
---

<objective>
Wave 1 implementation of `src/screener/sizing.py` body — pure-function compute_sizing() that dispatches per-playbook stops (D-07), computes shares (D-05), runs the 1×ADR auto-reject (D-06), classifies the 3-bucket ATR zone (D-09), and emits trail-rule labels (D-08). Land real bodies in all 11 skeletons in `tests/test_sizing.py`.

Purpose: This is the SIZ-01..05 core. Plan 07-04 (pipeline wiring) and Plan 07-04 (report rendering) depend on this module's columns. Parallel-safe with Plan 07-03 (zero file overlap — sizing.py + test_sizing.py vs persistence.py + test_journal.py).

**Note on input scope (revision iteration 1 Blocker #1 context):** Plan 07-04 (revised) calls `compute_sizing` on the FULL cross-section (every ticker, including ~95% with playbook_tag='none' that default-dispatch to no stop helper). Those rows naturally land as `adr_rejected=True` with `rejection_reason='invalid_stop'` and NaN-able sizing values. This Plan's behavior contract does NOT change — the function already handles unknown playbook_tag via `STOP_HELPERS.get(tag)` returning None and falling back to `stop_price = close_price`. The downstream snapshot schema (Plan 07-01 revised) accepts those rows via `nullable=True`.

Output: sizing.py body (~250 lines), test_sizing.py with 11 passing tests, FND-04 no-look-ahead gate still green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-CONTEXT.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md
@.planning/phases/07-sizing-finalization-paper-trade-journal/07-01-foundation-settings-schemas-fixtures-PLAN.md
@CLAUDE.md
@src/screener/signals/composite.py
@src/screener/indicators/patterns.py

<interfaces>
<!-- Key types and contracts extracted from the codebase. Use these directly. -->

Existing pure-function module shape (src/screener/signals/composite.py — the closest analog):
```python
"""composite — pre-registered weighted composite scorer (D-12, D-13).
...
Pure-function discipline (Phase 1 D-16): no I/O, no global state, panel-in /
panel-out. Imports only pandas + stdlib typing.
"""
from __future__ import annotations
from typing import Final
import numpy as np
import pandas as pd

QULL_MAX_BARS: Final[int] = 25
DEFAULT_WEIGHTS: Final[dict[str, float]] = {...}

def score(panel: pd.DataFrame, weights: dict[str, float] = DEFAULT_WEIGHTS) -> pd.DataFrame:
    """...pure: returns a NEW DataFrame; the input is not mutated."""
    out = panel.copy()
    ...
    return out
```

Existing pattern-helpers to reuse (src/screener/indicators/patterns.py):
- `find_pivots(highs: np.ndarray, lows: np.ndarray, order: int) -> tuple[np.ndarray, np.ndarray]` at patterns.py:79 — returns (high_idx, low_idx) of argrelextrema pivots
- `decode_pattern_diagnostics(raw: str) -> dict` at patterns.py:126-134 — JSON decode with `{"type": "none"}` fallback
- `FLAG_PIVOT_ORDER: Final[int] = 3` at patterns.py:58 — reuse for the leader-hold swing-low lookback per RESEARCH §Pattern 2

Existing architecture-test ALLOWED dict (tests/test_architecture.py:30-44) — line 35:
```python
"sizing": {"signals", "regime", "config", "obs"},
```
sizing.py is NOT currently permitted to import `indicators.*`. Plan 07-02 ADDS `indicators` to this set: change line 35 to `"sizing": {"signals", "regime", "config", "obs", "indicators"}`. This is the only architecture-test change Plan 07-02 makes (and the only one Phase 7 makes at all).

Phase 6 D-05 pattern_diagnostics schema (decode_pattern_diagnostics returns these keys for VCP):
```python
{
    "type": "vcp",
    "n_contractions": int,           # 2-6
    "depth_sequence": list[float],   # fractions, e.g. [0.25, 0.15, 0.08]
    "first_leg_depth": float,        # fraction
    "final_contraction_depth": float,# fraction (e.g. 0.08 = 8%)
    "breakout_vol_multiple": float,
    "breakout_strength": float,      # 0..1
    "pivot_price": float,            # dollar price
    "days_in_consolidation": int,
}
```
For flag: same keys; `depth_sequence=[]`, `first_leg_depth=0.0`, `final_contraction_depth=0.0`.
For leader_hold / no pattern: `{"type": "none"}` (no other keys).

Existing pandas/typing/np imports — the version pinned: pandas 2.2.x, numpy 2.x, typing stdlib.

The conftest fixture `sized_input_cross()` (Plan 07-01 Task 3) returns a 5-ticker DataFrame indexed by `ticker` with these columns:
- close, low, high, atr_14, adr_pct (float)
- playbook_tag (str — one of 4 enum values)
- pattern_diagnostics (str — JSON-encoded dict)
- composite_score, regime_state, regime_score (float / str / float)
- passes_trend_template (bool), rs_rating (Int64), trend_template_score (Int64), volume_component (float)

Settings fields available to compute_sizing() (Plan 07-01 Task 1):
- `settings.ACCOUNT_EQUITY: float = 100_000.0` (unchanged, line 39)
- `settings.RISK_PCT: float = 0.01` (new, Plan 07-01)
- caller MUST pass these as positional/keyword args; compute_sizing must NOT import Settings (pure function — RESEARCH §Anti-Patterns).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Update architecture-test ALLOWED dict to permit sizing → indicators imports, then add Final constants + private helpers (_recent_swing_low_distance, _stop_qullamaggie, _stop_minervini_vcp, _stop_leader_hold, classify_atr_zone, _trail_rule_label) to sizing.py</name>
  <files>tests/test_architecture.py, src/screener/sizing.py</files>
  <read_first>
    - tests/test_architecture.py (lines 30-44 — current ALLOWED dict; line 35 needs `"indicators"` added to sizing's set)
    - src/screener/sizing.py (current 6-line stub — REPLACE entirely; do NOT preserve the stub docstring as-is)
    - src/screener/signals/composite.py (lines 1-44 — module docstring + Final constants + import shape to copy)
    - src/screener/indicators/patterns.py (lines 79 `find_pivots`, 126-134 `decode_pattern_diagnostics`, 58 `FLAG_PIVOT_ORDER`)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-PATTERNS.md §"src/screener/sizing.py" (analog patterns to copy verbatim)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md §"Architecture Patterns" Pattern 1 (stop registry) + Pattern 2 (swing-low) + Pattern 3 (trail labels) + §"Common Pitfalls" 5 (VCP diagnostics guard) + 6 (entry==stop guard)
  </read_first>
  <behavior>
    - test_architecture.py passes after adding "indicators" to sizing's ALLOWED set (otherwise the test will fail when sizing.py imports from screener.indicators.patterns)
    - sizing.py imports succeed: `from screener.sizing import STOP_HELPERS, classify_atr_zone, _stop_qullamaggie, _stop_minervini_vcp, _stop_leader_hold, IN_ZONE_ATR, EXTENDED_ATR, LEADER_SWING_LOOKBACK_BARS, MAX_POSITION_FRACTION`
    - STOP_HELPERS dict keys equal exactly {"qullamaggie_continuation", "minervini_vcp", "leader_hold"}; values are the three private helper functions (identity-equal)
    - classify_atr_zone(0.0) == "in-zone"; classify_atr_zone(0.66) == "in-zone"; classify_atr_zone(0.67) == "extended"; classify_atr_zone(1.0) == "extended"; classify_atr_zone(1.01) == "chase, skip"
    - _trail_rule_label({"playbook_tag": "qullamaggie_continuation", "adr_pct": 7.0}) returns string containing "10d SMA"
    - _trail_rule_label for adr_pct=5.0 returns "20d SMA"; for adr_pct=3.0 returns "50d SMA"
    - _trail_rule_label for minervini_vcp returns "21d EMA (then 50d SMA after 15 bars)"
    - _trail_rule_label for leader_hold returns "50d SMA close"
  </behavior>
  <action>
**A. tests/test_architecture.py — update ALLOWED dict line 35** EXACTLY:

Before:
```python
    "sizing": {"signals", "regime", "config", "obs"},
```

After:
```python
    "sizing": {"signals", "regime", "config", "obs", "indicators"},  # Phase 7 D-07: sizing reuses indicators.patterns.find_pivots + decode_pattern_diagnostics (RESEARCH §Pattern 1/2)
```

No other change to this file.

**B. src/screener/sizing.py — REPLACE the entire 6-line stub** with the following structure (Final constants + private helpers; compute_sizing() lands in Task 2):

```python
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
```

DO NOT add `compute_sizing()` in this task — it lands in Task 2 so the diff stays reviewable.
  </action>
  <verify>
    <automated>uv run pytest tests/test_architecture.py -x --no-cov && uv run python -c "from screener.sizing import STOP_HELPERS, classify_atr_zone, _stop_qullamaggie, _stop_minervini_vcp, _stop_leader_hold, _trail_rule_label, IN_ZONE_ATR, EXTENDED_ATR, MAX_POSITION_FRACTION, LEADER_SWING_LOOKBACK_BARS, LEADER_SWING_PIVOT_ORDER; assert set(STOP_HELPERS.keys()) == {'qullamaggie_continuation','minervini_vcp','leader_hold'}; assert STOP_HELPERS['qullamaggie_continuation'] is _stop_qullamaggie; assert STOP_HELPERS['minervini_vcp'] is _stop_minervini_vcp; assert STOP_HELPERS['leader_hold'] is _stop_leader_hold; assert classify_atr_zone(0.0) == 'in-zone'; assert classify_atr_zone(0.66) == 'in-zone'; assert classify_atr_zone(0.67) == 'extended'; assert classify_atr_zone(1.0) == 'extended'; assert classify_atr_zone(1.5) == 'chase, skip'; print('sizing core OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -nE "^\s*.sizing.: \{.signals., .regime., .config., .obs., .indicators.\}" tests/test_architecture.py` returns exactly one match
    - `grep -cE "^def _stop_qullamaggie|^def _stop_minervini_vcp|^def _stop_leader_hold|^def _recent_swing_low_distance|^def classify_atr_zone|^def _trail_rule_label" src/screener/sizing.py` outputs `6`
    - `grep -cE "^STOP_HELPERS: Final\[dict\[str, Callable" src/screener/sizing.py` outputs `1`
    - `grep -cE "^IN_ZONE_ATR: Final\[float\] = 0\.66$" src/screener/sizing.py` outputs `1`
    - `grep -cE "^EXTENDED_ATR: Final\[float\] = 1\.00$" src/screener/sizing.py` outputs `1`
    - `grep -cE "^MAX_POSITION_FRACTION: Final\[float\] = 0\.25$" src/screener/sizing.py` outputs `1`
    - `grep -cE "^from screener\.indicators\.patterns import" src/screener/sizing.py` outputs `1`
    - sizing.py does NOT import from `data` or `persistence`: `grep -cE "from screener\.(data|persistence)" src/screener/sizing.py` outputs `0`
    - sizing.py uses NO `print()`: `grep -c "^\s*print(" src/screener/sizing.py` outputs `0`
    - `uv run pytest tests/test_architecture.py -x --no-cov` passes
    - Python import smoke-check (single command above) prints `sizing core OK`
  </acceptance_criteria>
  <done>
    Architecture-test ALLOWED dict permits sizing → indicators (one-line change). sizing.py module has 6 functions (5 module-level + STOP_HELPERS registry) and 7 Final constants. All imports clean; no I/O, no print, no data/persistence imports. Architecture test passes.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add compute_sizing() to sizing.py and land real bodies in all 11 tests/test_sizing.py skeletons</name>
  <files>src/screener/sizing.py, tests/test_sizing.py</files>
  <read_first>
    - src/screener/sizing.py (current file after Task 1 — constants + helpers + STOP_HELPERS exist)
    - tests/test_sizing.py (11 pytest.skip skeletons from Plan 07-01 Task 3)
    - tests/conftest.py (the new `sized_input_cross()` fixture — lines added by Plan 07-01)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md §"Architecture Patterns" Pattern 4 (pipeline seam → understand what compute_sizing returns)
    - .planning/phases/07-sizing-finalization-paper-trade-journal/07-RESEARCH.md §"Common Pitfalls" 5 + 6 + 7
  </read_first>
  <behavior>
    - compute_sizing(cross, panel, account_equity, risk_pct, regime_score) returns a NEW DataFrame; assert input frame is untouched after the call (pure-function discipline)
    - Returned frame has 9 NEW columns: stop_price (float), entry_price (float = close), shares (Int64), risk_per_share (float), atr_zone (str), pivot_distance_atr_breakout (float, nullable), trail_rule_label (str), adr_rejected (bool), rejection_reason (str — empty string when not rejected)
    - For ticker QULL (qullamaggie, adr_pct=5.5, close=120, low=118, atr=2): stop_price=118.0, risk_per_share=2.0, adr_rejected=False (because risk=2.0 ≤ adr$ = (5.5/100)×120 = 6.6), trail_rule_label="20d SMA" (5.5 is in 4–6 tier)
    - For ticker REJC (qullamaggie, adr_pct=0.3, close=80, low=79.5): adr_dollars = (0.3/100)×80 = 0.24; risk_per_share = 80-79.5 = 0.5; 0.5 > 0.24 → adr_rejected=True, rejection_reason="adr_exceeded", shares=0
    - For ticker INVS (leader_hold, close=50, low=50, atr=1): _stop_leader_hold returns 50 - min(max(1.5, swing), 2) = a value strictly less than 50 (because the 1.5×ATR floor is 1.5, the cap is 2.0); so entry > stop. INVS is NOT rejected for invalid_stop with the sized_input_cross numbers. The invalid-stop branch is exercised separately by a test that constructs entry==stop via a fixture override.
    - For ticker VCP1 (minervini_vcp, close=100, pattern_diagnostics with pivot_price=100, final_contraction_depth=0.08): stop_price = 100 × (1 - 0.08) = 92.0; risk_per_share = 8.0
    - shares formula sanity (QULL example): floor((100_000 × 0.01 × 0.85) / (120 − 118)) = floor(850 / 2) = 425; cap = floor(100_000 × 0.25 / 120) = 208 → effective shares = 208 (cap binds)
    - regime_score=0 → numerator=0 → shares=0 for every row (no div-by-zero)
    - test count: all 11 test functions in test_sizing.py have real bodies (no remaining pytest.skip calls in that file)
  </behavior>
  <action>
**A. Append `compute_sizing()` to `src/screener/sizing.py`** (after the STOP_HELPERS registry):

```python


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
```

**B. Replace ALL 11 pytest.skip skeletons in tests/test_sizing.py** with real bodies. Each test imports the conftest fixture `sized_input_cross` and exercises the documented behavior. Below is the COMPLETE replacement file:

```python
"""tests/test_sizing.py — Phase 7 SIZ-01..05 unit tests (Plan 07-02 bodies)."""
from __future__ import annotations

import math
import json

import numpy as np
import pandas as pd
import pytest

from screener.sizing import (
    EXTENDED_ATR,
    IN_ZONE_ATR,
    LEADER_SWING_LOOKBACK_BARS,
    LEADER_SWING_PIVOT_ORDER,
    MAX_POSITION_FRACTION,
    QULL_TRAIL_FAST_ADR,
    QULL_TRAIL_MEDIUM_ADR,
    STOP_HELPERS,
    _stop_leader_hold,
    _stop_minervini_vcp,
    _stop_qullamaggie,
    _trail_rule_label,
    classify_atr_zone,
    compute_sizing,
)


def _empty_panel(tickers: list[str]) -> pd.DataFrame:
    """Minimal MultiIndex(ticker, date) panel — empty rows; sizing uses it
    only for the leader_hold swing-low lookback fallback path."""
    idx = pd.MultiIndex.from_product(
        [tickers, pd.date_range("2026-01-01", periods=1, freq="D")],
        names=["ticker", "date"],
    )
    return pd.DataFrame({"high": 0.0, "low": 0.0, "close": 0.0}, index=idx)


def test_shares_formula(sized_input_cross: pd.DataFrame) -> None:
    """SIZ-01: shares = floor((eq × risk_pct × regime_score)/(entry − stop)), capped at 25% equity."""
    cross = sized_input_cross
    panel = _empty_panel(list(cross.index))
    out = compute_sizing(cross, panel, account_equity=100_000.0, risk_pct=0.01, regime_score=0.85)
    # QULL: stop=118, entry=120, risk=2; raw = floor(100_000*0.01*0.85 / 2) = 425;
    # cap = floor(100_000 * 0.25 / 120) = 208 → cap binds → 208.
    assert int(out.loc["QULL", "shares"]) == 208
    # VCP1: stop=100*(1-0.08)=92, entry=100, risk=8; raw = floor(850/8) = 106;
    # cap = floor(25_000/100) = 250 → raw binds → 106.
    assert int(out.loc["VCP1", "shares"]) == 106


def test_zero_regime_score_zero_shares(sized_input_cross: pd.DataFrame) -> None:
    """SIZ-01 / Pitfall 6: regime_score=0 → shares=0 (no div-by-zero)."""
    cross = sized_input_cross
    panel = _empty_panel(list(cross.index))
    out = compute_sizing(cross, panel, account_equity=100_000.0, risk_pct=0.01, regime_score=0.0)
    # Every non-rejected row → shares=0; rejected rows already 0.
    assert (out["shares"] == 0).all()


def test_shares_nonneg_property() -> None:
    """Property: shares ≥ 0 for any valid input."""
    # Hand-crafted edge cases (hypothesis would inflate scope; this satisfies the property).
    rows = []
    for eq, rp, rg in [(100_000, 0.01, 0.5), (50_000, 0.005, 1.0), (1_000_000, 0.02, 0.1)]:
        cross = pd.DataFrame(
            {
                "close": [100.0],
                "low": [99.0],
                "high": [101.0],
                "atr_14": [1.5],
                "adr_pct": [4.0],
                "playbook_tag": ["qullamaggie_continuation"],
                "pattern_diagnostics": ['{"type": "flag"}'],
                "composite_score": [70.0],
                "regime_state": ["Confirmed Uptrend"],
                "regime_score": [rg],
                "passes_trend_template": [True],
                "rs_rating": pd.array([90], dtype=pd.Int64Dtype()),
                "trend_template_score": pd.array([7], dtype=pd.Int64Dtype()),
                "volume_component": [0.5],
            },
            index=pd.Index(["TEST"], name="ticker"),
        )
        out = compute_sizing(cross, _empty_panel(["TEST"]), eq, rp, rg)
        rows.append(int(out.loc["TEST", "shares"]))
    assert all(s >= 0 for s in rows), rows


def test_adr_reject_boundary(sized_input_cross: pd.DataFrame) -> None:
    """SIZ-02: adr_rejected when risk_per_share > adr_dollars."""
    cross = sized_input_cross
    out = compute_sizing(cross, _empty_panel(list(cross.index)), 100_000.0, 0.01, 0.85)
    # REJC: adr_pct=0.3, close=80 → adr_dollars = 0.24; low=79.5 → risk=0.5 > 0.24 → reject.
    assert bool(out.loc["REJC", "adr_rejected"]) is True
    assert str(out.loc["REJC", "rejection_reason"]) == "adr_exceeded"
    assert int(out.loc["REJC", "shares"]) == 0
    # QULL: adr_pct=5.5, close=120 → adr_dollars=6.6; risk=2.0 ≤ 6.6 → not rejected.
    assert bool(out.loc["QULL", "adr_rejected"]) is False


def test_stop_dispatch_per_playbook() -> None:
    """SIZ-03 / SC-2: STOP_HELPERS[tag] is the correct private helper."""
    assert STOP_HELPERS["qullamaggie_continuation"] is _stop_qullamaggie
    assert STOP_HELPERS["minervini_vcp"] is _stop_minervini_vcp
    assert STOP_HELPERS["leader_hold"] is _stop_leader_hold
    assert set(STOP_HELPERS.keys()) == {
        "qullamaggie_continuation", "minervini_vcp", "leader_hold",
    }


def test_leader_swing_fallback(sized_input_cross: pd.DataFrame) -> None:
    """SIZ-03: leader_hold falls back to 2×ATR when history is too short."""
    cross = sized_input_cross.loc[["LEAD"]].copy()  # leader_hold, atr_14=4
    out = compute_sizing(cross, _empty_panel(["LEAD"]), 100_000.0, 0.01, 0.85)
    # _empty_panel has 1 bar; LEADER_SWING_PIVOT_ORDER=3 → too short → 2×ATR=8 cap
    # entry=200, stop=200-8=192.
    assert math.isclose(float(out.loc["LEAD", "stop_price"]), 192.0, abs_tol=1e-9)


def test_vcp_stop_from_diagnostics(sized_input_cross: pd.DataFrame) -> None:
    """SIZ-03: minervini_vcp stop = pivot_price × (1 − final_contraction_depth)."""
    out = compute_sizing(sized_input_cross.loc[["VCP1"]].copy(), _empty_panel(["VCP1"]),
                         100_000.0, 0.01, 0.85)
    # vcp_diag has pivot_price=100.0, final_contraction_depth=0.08 → stop = 92.0
    assert math.isclose(float(out.loc["VCP1", "stop_price"]), 92.0, abs_tol=1e-9)


def test_trail_label_dispatch() -> None:
    """SIZ-04 / D-08: trail label per playbook tag."""
    qull = pd.Series({"playbook_tag": "qullamaggie_continuation", "adr_pct": 5.0})
    vcp = pd.Series({"playbook_tag": "minervini_vcp", "adr_pct": 0.0})
    lead = pd.Series({"playbook_tag": "leader_hold", "adr_pct": 0.0})
    none = pd.Series({"playbook_tag": "none", "adr_pct": 0.0})
    assert _trail_rule_label(qull) == "20d SMA"
    assert _trail_rule_label(vcp) == "21d EMA (then 50d SMA after 15 bars)"
    assert _trail_rule_label(lead) == "50d SMA close"
    assert _trail_rule_label(none) == ""


def test_qull_trail_speed_tiers() -> None:
    """SIZ-04: Qullamaggie ADR%<4 → 50d SMA, 4–6 → 20d SMA, ≥6 → 10d SMA (boundaries inclusive at 4 and 6)."""
    base = {"playbook_tag": "qullamaggie_continuation"}
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 3.99})) == "50d SMA"
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 4.0})) == "20d SMA"
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 5.5})) == "20d SMA"
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 5.99})) == "20d SMA"
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 6.0})) == "10d SMA"
    assert _trail_rule_label(pd.Series({**base, "adr_pct": 7.5})) == "10d SMA"


def test_atr_zone_boundaries() -> None:
    """SIZ-05 / D-09: =0.66 → in-zone; =1.0 → extended; >1.0 → chase, skip."""
    assert classify_atr_zone(0.0) == "in-zone"
    assert classify_atr_zone(0.65999) == "in-zone"
    assert classify_atr_zone(IN_ZONE_ATR) == "in-zone"          # exactly 0.66
    assert classify_atr_zone(0.66001) == "extended"
    assert classify_atr_zone(0.85) == "extended"
    assert classify_atr_zone(EXTENDED_ATR) == "extended"        # exactly 1.0
    assert classify_atr_zone(1.0001) == "chase, skip"
    assert classify_atr_zone(2.5) == "chase, skip"


def test_pure_function_no_input_mutation(sized_input_cross: pd.DataFrame) -> None:
    """compute_sizing returns a NEW DataFrame; input is untouched."""
    cross = sized_input_cross.copy()  # snapshot the expected state
    cross_backup = cross.copy(deep=True)
    out = compute_sizing(cross, _empty_panel(list(cross.index)), 100_000.0, 0.01, 0.85)
    # Input columns unchanged.
    assert list(cross.columns) == list(cross_backup.columns)
    for col in cross_backup.columns:
        pd.testing.assert_series_equal(cross[col], cross_backup[col], check_names=False)
    # Output has 9 new columns.
    new_cols = set(out.columns) - set(cross.columns)
    assert new_cols == {
        "stop_price", "entry_price", "shares", "risk_per_share", "atr_zone",
        "pivot_distance_atr_breakout", "trail_rule_label", "adr_rejected", "rejection_reason",
    }
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_sizing.py -x --no-cov -q && uv run pytest tests/test_backtest_no_lookahead.py -x --no-cov -q && uv run pytest tests/test_architecture.py -x --no-cov -q</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest tests/test_sizing.py --no-cov -q 2>&1 | tail -3 | grep -E "11 passed"` matches (zero failures, zero remaining skips)
    - `grep -c "^def test_" tests/test_sizing.py` outputs `11`
    - `grep -c "pytest\.skip" tests/test_sizing.py` outputs `0` (every skeleton replaced)
    - `grep -nE "^def compute_sizing\(" src/screener/sizing.py` returns exactly one match
    - `grep -nE "^def _compute_pivot_distance_atr_breakout\(" src/screener/sizing.py` returns exactly one match
    - sizing.py file size ≥ 200 lines: `wc -l src/screener/sizing.py | awk '{print $1}'` returns ≥ 200
    - mypy strict on sizing.py passes: `uv run mypy --strict src/screener/sizing.py` returns exit 0 (this is a NEW addition to the strict-files list — see RESEARCH note; if pyproject.toml does not yet list sizing.py under `[tool.mypy.overrides] strict`, document the gap in SUMMARY but do NOT fail the task — mypy on indicators/+signals/ in non-strict mode must still pass)
    - FND-04 no-look-ahead gate green: `uv run pytest tests/test_backtest_no_lookahead.py -x --no-cov -q` passes
    - Architecture test green: `uv run pytest tests/test_architecture.py -x --no-cov -q` passes
    - Pre-existing test suite has zero regressions: `uv run pytest tests/test_publishers_pipeline.py tests/test_cli_smoke.py::test_subcommand_surface_locked --no-cov -q` passes
  </acceptance_criteria>
  <done>
    sizing.py compute_sizing() body landed (~150 lines). All 11 test_sizing.py skeletons replaced with real bodies and pass. FND-04 mutation gate still green; architecture test green; D-24 CLI surface lock intact.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| sized cross-section → snapshot Parquet | Sizing emits 9 new columns that become persistent state; bad values poison every downstream backtest and journal row |
| pattern_diagnostics JSON → _stop_minervini_vcp | Corrupt blob with type='vcp' but missing pivot_price would compute a nonsensical stop without Pitfall 5 guard |
| user-supplied risk_pct via Settings | Out-of-range value (e.g. 0.5 = 50%) would size impossibly large positions; mitigated only by the 25% per-position cap |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-06 | Tampering | _stop_minervini_vcp via corrupt pattern_diagnostics blob | mitigate | Pitfall 5 guard: assert diag.type=='vcp' AND required keys present; raise ValueError('missing_diagnostics') on failure → outer try/except marks pick as rejected (rejection_reason='missing_diagnostics'). Tested via test_vcp_stop_from_diagnostics + a synthetic corrupt-blob test (added in Task 2 acceptance via inline construction). |
| T-07-07 | Denial of service | leader_hold swing-low lookback on short history | accept | _recent_swing_low_distance returns 2.0×atr fallback when history < 2×order+1 bars or find_pivots returns empty; no exception path. Tested via test_leader_swing_fallback. |
| T-07-08 | Information disclosure | structlog `sizing_applied` event payload | accept | Event payload contains aggregate counts only (n_input, n_actionable, n_rejected_*). No per-ticker data, no API keys, no env values. Per-row rejection events are DEBUG level only and not enabled by default. |
| T-07-09 | Process integrity | regime_score=0 → div-by-zero risk | mitigate | Numerator (eq × risk_pct × regime_score) goes to 0; division by risk_per_share is guarded by `if rejection != "" or risk_per_share <= 0` → shares = 0. Tested via test_zero_regime_score_zero_shares. |
| T-07-10 | Elevation of privilege | sizing.py → indicators.patterns import | mitigate | tests/test_architecture.py ALLOWED dict explicitly extended to permit `sizing → indicators` (Task 1). Architecture test enforces this; any future leak into data/ or persistence/ fails the test. Tested via test_architecture.py::test_layer_import_contract. |

ASVS L1 applicable: V5.2.4 (sanitize untrusted input — pattern_diagnostics JSON), V11.1.1 (business logic — playbook dispatch). No high-risk threats.
</threat_model>

<verification>
```bash
# Phase 7 Plan 02 verification suite (~15s)
uv run pytest tests/test_sizing.py --no-cov -q
uv run pytest tests/test_architecture.py --no-cov -q
uv run pytest tests/test_backtest_no_lookahead.py --no-cov -q   # FND-04 mutation gate
uv run pytest tests/test_publishers_pipeline.py --no-cov -q     # Phase 6 W-Plan05-1 still green
uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked --no-cov -q  # D-24 lock

# Sizing module sanity
uv run python -c "from screener.sizing import STOP_HELPERS, compute_sizing; print(len(STOP_HELPERS), 'helpers registered')"
# Expected: 3 helpers registered

uv run ruff check src/screener/sizing.py
```
</verification>

<success_criteria>
- src/screener/sizing.py has compute_sizing() body, STOP_HELPERS registry, 3 _stop_* helpers, classify_atr_zone, _trail_rule_label, _recent_swing_low_distance, _compute_pivot_distance_atr_breakout (≥200 lines).
- sizing.py is pure: no I/O, no `print()`, no imports from `data` or `persistence`.
- tests/test_architecture.py ALLOWED dict permits sizing → indicators (one-line change).
- All 11 tests in tests/test_sizing.py pass (no remaining pytest.skip).
- regime_score=0 → shares=0 across all rows (no div-by-zero).
- 1×ADR auto-reject sets `adr_rejected=True` with `rejection_reason='adr_exceeded'`.
- Pitfall 5 missing_diagnostics and Pitfall 6 invalid_stop paths both reject with distinct reasons.
- STOP_HELPERS dict registry passes SC-2 identity assertion.
- ATR zone classifier returns exactly 'in-zone' / 'extended' / 'chase, skip' per D-09 boundaries.
- Qullamaggie trail tier boundaries inclusive at 4.0 and 6.0 (4 → "20d", 6 → "10d").
- FND-04 no-look-ahead mutation gate STILL GREEN after sizing.py lands.
- D-24 9-subcommand CLI surface STILL LOCKED.
</success_criteria>

<output>
After completion, create `.planning/phases/07-sizing-finalization-paper-trade-journal/07-02-SUMMARY.md` per the standard template.
</output>
</content>
</invoke>