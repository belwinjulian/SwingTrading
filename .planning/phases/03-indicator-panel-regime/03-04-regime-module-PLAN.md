---
phase: 03-indicator-panel-regime
plan: 04
type: execute
wave: 3
depends_on:
  - 03-02
  - 03-03
files_modified:
  - src/screener/regime.py
  - tests/test_regime.py
  - tests/test_regime_score.py
  - tests/conftest.py
autonomous: true
requirements:
  - REG-01
  - REG-02
  - REG-03
tags:
  - regime
  - market-state
  - sizing-seam

must_haves:
  truths:
    - "regime.compute_for_date(date, panel) returns a pd.Series with 6 fields per REG-01: spy_above_200d (bool), breadth_pct (float), distribution_days (int), vix_level (float), regime_state (str), regime_score (float)."
    - "regime_state ∈ {'Confirmed Uptrend', 'Uptrend Under Pressure', 'Correction'} with D-01 priority chain: Correction overrides everything if SPY < 200d SMA OR distribution_days ≥ 9 OR VIX ≥ 30."
    - "regime_score is the D-03 weighted blend (SPY 30 / Breadth 40 / Dist 20 / VIX 10), naturally in [0, 1]; it is the seam Phase 7 sizing will multiply into base risk (REG-03)."
    - "Distribution-day counter follows strict IBD definition (D-02): SPY close < prev_close by > 0.2% AND SPY volume > prev_volume; rolling 25-session window."
    - "Breadth_pct denominator is 'tickers with valid sma_200' not 'all universe tickers' (RESEARCH Pitfall 11) — prevents biased breadth during post-IPO clusters."
    - "regime.build_history(start, end) returns a DataFrame across a date range using the same 6-column schema; vectorized regime_score per RESEARCH Pattern 5."
    - "regime.py is in the architecture-test ALLOWED set for imports {data, indicators, persistence, config, obs} — no yfinance/requests/etc."
  artifacts:
    - path: "src/screener/regime.py"
      provides: "Replaces the 7-line stub with: _classify_state, _compute_distribution_days, _regime_score, compute_for_date, build_history; structured-log event 'regime_computed'"
      contains: "def _classify_state, def _compute_distribution_days, def _regime_score, def compute_for_date, def build_history, RegimeState = Literal, from screener.persistence import read_macro_spy, read_macro_vix, from screener.indicators import build_panel"
    - path: "tests/test_regime.py"
      provides: "REG-01..03 unit tests + REG-01 distribution-day idiom test + Pitfall-11 breadth_pct test"
      exports: ["test_compute_for_date_columns", "test_distribution_day_idiom", "test_regime_state_enum", "test_correction_overrides_pressure", "test_regime_score_seam_exists", "test_breadth_pct_denominator_uses_valid_sma"]
    - path: "tests/test_regime_score.py"
      provides: "REG-02 hypothesis property test — regime_score ∈ [0, 1] over random inputs"
      exports: ["test_regime_score_in_unit_interval"]
  key_links:
    - from: "src/screener/regime.py compute_for_date"
      to: "src/screener/persistence.py read_macro_spy"
      via: "macro Parquet read for SPY OHLCV (data flow: data/macro.py wrote it; regime reads it)"
      pattern: "read_macro_spy\\(\\)"
    - from: "src/screener/regime.py compute_for_date"
      to: "src/screener/persistence.py read_macro_vix"
      via: "macro Parquet read for ^VIX close-only"
      pattern: "read_macro_vix\\(\\)"
    - from: "src/screener/regime.py compute_for_date breadth_pct"
      to: "src/screener/indicators.build_panel sma_200"
      via: "indicator panel sma_200 column drives breadth denominator (Pitfall 11)"
      pattern: "sma_200"
    - from: "src/screener/regime.py _classify_state"
      to: "src/screener/config.Settings REGIME_*"
      via: "8 regime threshold fields read from Settings (D-01, D-12)"
      pattern: "settings\\.REGIME_"
---

<objective>
Replace the 7-line `regime.py` stub with the full Phase 3 regime module: distribution-day counter (D-02), three-state classifier (D-01 with Correction priority), continuous regime_score (D-03), `compute_for_date()` per-date row, and `build_history()` for backtest history.

Purpose: Provide the regime gate consumed by Phase 4's report banner, Phase 5's per-regime backtest breakdown (BCK-05), and Phase 7's `regime_score`-into-sizing wiring (REG-03 seam). Phase 3 only computes and exposes `regime_score` — Phase 7 wires it into `sizing.py`.

Output:
- `src/screener/regime.py` (modify — currently 7-line stub) with full body
- `tests/test_regime.py` (new) — REG-01/02/03 unit tests including D-01 priority and Pitfall-11 breadth denominator
- `tests/test_regime_score.py` (new) — first hypothesis property test in the project (REG-02 score-in-unit-interval invariant)
- Conftest extension with synthetic SPY/VIX fixtures (full golden-file fixtures land in Plan 03-05; this plan adds the core distribution-day fixture)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-indicator-panel-regime/03-CONTEXT.md
@.planning/phases/03-indicator-panel-regime/03-RESEARCH.md
@.planning/phases/03-indicator-panel-regime/03-PATTERNS.md
@.planning/phases/03-indicator-panel-regime/03-VALIDATION.md
@.planning/phases/03-indicator-panel-regime/03-01-SUMMARY.md
@.planning/phases/03-indicator-panel-regime/03-02-SUMMARY.md
@.planning/phases/03-indicator-panel-regime/03-03-SUMMARY.md

@src/screener/regime.py
@src/screener/persistence.py
@src/screener/config.py
@src/screener/indicators/__init__.py
@tests/test_architecture.py
@tests/conftest.py

<interfaces>
<!-- From src/screener/persistence.py (Plan 03-01 added): -->
def read_macro_spy() -> pd.DataFrame:
    """Returns single-index (date) MacroOhlcvSchema-validated SPY OHLCV
    (lowercase columns: open, high, low, close, volume)."""

def read_macro_vix() -> pd.DataFrame:
    """Returns single-index (date) VixSchema-validated frame with `close` only."""

def read_macro_nyad() -> pd.DataFrame:
    """Returns NyadMacroSchema-validated DataFrame with advances/declines/ad_line."""

<!-- From src/screener/indicators/__init__.py (Plan 03-03 added): -->
def build_panel(snapshot_date: str | pd.Timestamp) -> pd.DataFrame:
    """Returns OHLCV panel + 10 indicator columns including sma_200."""

<!-- From src/screener/config.py (Plan 03-01 added — D-12 fields): -->
class Settings(BaseSettings):
    REGIME_BREADTH_THRESHOLD: float = 0.60      # Confirmed Uptrend cutoff
    REGIME_DIST_DAYS_PRESSURE: int = 5          # Pressure lower bound
    REGIME_DIST_DAYS_CORRECTION: int = 9        # Correction trigger
    REGIME_VIX_CORRECTION: float = 30.0         # Correction trigger
    REGIME_VIX_CONFIRMED: float = 20.0          # Confirmed Uptrend ceiling

<!-- D-01 priority chain: Correction > Pressure > Uptrend (verbatim CONTEXT.md): -->
# Confirmed Uptrend: SPY > SMA200 AND breadth >= 60% AND dist <= 4 AND VIX < 20
# Uptrend Under Pressure: any single condition fails OR dist in [5, 8]
# Correction: SPY < SMA200 OR dist >= 9 OR VIX >= 30
# Priority: Correction overrides Pressure regardless of other inputs

<!-- D-03 score formula (verbatim CONTEXT.md): -->
spy_component    = 1.0 if spy_above_200d else 0.0
breadth_norm     = clip(breadth_pct / 100, 0, 1)
dist_norm        = clip(1 - (distribution_days / 9), 0, 1)
vix_norm         = clip(1 - ((vix_level - 15) / 25), 0, 1)
regime_score     = 0.30*spy_component + 0.40*breadth_norm + 0.20*dist_norm + 0.10*vix_norm

<!-- D-02 distribution-day rule: -->
# is_dist_day = (SPY close < prev_close by > 0.2%) AND (SPY volume > prev_volume)
# Count via .rolling(25).sum()

<!-- From tests/test_architecture.py: -->
ALLOWED["regime"] = {"data", "indicators", "persistence", "config", "obs"}
# regime → indicators → persistence is permitted; data → persistence + config is permitted.
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| persistence → regime | regime.py reads schema-validated macro Parquets via persistence.read_macro_spy/vix; pandera lazy validation is the trust boundary. |
| indicators → regime | Indicator panel is computed by Plan 03-03; regime consumes sma_200 column for breadth denominator. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-01 | Tampering | regime.compute_for_date | mitigate | All inputs flow through pandera-validated readers (read_macro_spy, read_macro_vix); breadth_pct denominator uses (close.notna() & sma_200.notna()) mask per Pitfall 11 — guards against biased breadth when many tickers lack 200d history. |
</threat_model>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Replace regime.py stub with full body — _classify_state + _compute_distribution_days + _regime_score + compute_for_date + build_history</name>
  <files>src/screener/regime.py</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/regime.py (current 7-line stub — replace; DO NOT preserve placeholder logic)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-RESEARCH.md (Example 4 lines 671-763 — verbatim regime body; Pattern 4 lines 302-312 — distribution-day idiom; Pattern 5 lines 318-328 — vectorized _regime_score; Pitfall 11 — breadth denominator)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 546-630 — regime.py module template + structured-log event `regime_computed`)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-CONTEXT.md (D-01, D-02, D-03 — exact thresholds and formula constants)
    - /Users/belwinjulian/Desktop/SwingTrading/tests/test_architecture.py (lines 30-44 — confirm `regime` is in ALLOWED with {data, indicators, persistence, config, obs})
  </read_first>
  <behavior>
    - Test: `from screener.regime import compute_for_date, build_history, _classify_state, _compute_distribution_days, _regime_score, RegimeState` — all importable.
    - Test: `_classify_state(spy_above_200d=True, breadth_pct=70.0, distribution_days=2, vix_level=15.0, settings=...)` returns `"Confirmed Uptrend"`.
    - Test: `_classify_state(spy_above_200d=False, breadth_pct=70.0, distribution_days=2, vix_level=15.0, settings=...)` returns `"Correction"` (SPY-below-200d triggers Correction).
    - Test: `_classify_state(spy_above_200d=True, breadth_pct=70.0, distribution_days=10, vix_level=15.0, settings=...)` returns `"Correction"` (dist ≥ 9 triggers Correction).
    - Test: `_classify_state(spy_above_200d=True, breadth_pct=70.0, distribution_days=2, vix_level=35.0, settings=...)` returns `"Correction"` (VIX ≥ 30 triggers Correction — D-01 priority).
    - Test: `_classify_state(spy_above_200d=True, breadth_pct=50.0, distribution_days=2, vix_level=15.0, settings=...)` returns `"Uptrend Under Pressure"` (breadth < 60% but no Correction trigger).
    - Test: `_compute_distribution_days(spy_df_with_4_dist_days_in_last_25)` returns rolling-25 sum where the last value is 4.
    - Test: `_regime_score(df_all_good)` returns ~1.0; `_regime_score(df_all_bad)` returns ~0.0; intermediate cases stay in [0, 1].
    - Test: `compute_for_date(date, panel)` returns pd.Series with exactly the 6 fields: spy_above_200d, breadth_pct, distribution_days, vix_level, regime_state, regime_score.
    - Test: `build_history(start, end)` returns DataFrame with the same 6 columns indexed by date.
    - Test: structlog event `regime_computed` with kwargs date, state, score is emitted on every compute_for_date call.
  </behavior>
  <action>
Replace the entire content of `src/screener/regime.py` (currently 7 lines) with the following body. Do NOT preserve the existing stub.

```python
"""regime — universe-wide market-regime gate (one row per date).

Emits a discrete state in {Confirmed Uptrend, Uptrend Under Pressure,
Correction} plus a continuous regime_score in [0, 1]. Imports `data/`,
`indicators/`, and `persistence/`; consumed by `sizing` (Phase 7) and
`publishers/` (Phase 4).

Rules (CONTEXT.md D-01, D-02, D-03):
- Confirmed Uptrend: SPY > 200d SMA AND breadth_pct >= 60 AND dist <= 4 AND VIX < 20
- Uptrend Under Pressure: any single condition fails, OR dist in [5, 8]
- Correction (priority — overrides everything):
    SPY < 200d SMA OR dist >= 9 OR VIX >= 30

Distribution day (strict IBD): SPY close < prev_close by > 0.2% AND SPY volume
> prev_volume; counted in a rolling 25-session window.

regime_score (vectorized, naturally in [0, 1]):
    0.30 * spy_component + 0.40 * breadth_norm + 0.20 * dist_norm + 0.10 * vix_norm

The breadth_pct denominator is "tickers with valid sma_200" not "all universe
tickers" (RESEARCH Pitfall 11) — prevents biased breadth during periods when
many tickers lack 200d history.
"""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd
import structlog

from screener.config import get_settings
from screener.indicators import build_panel
from screener.persistence import read_macro_spy, read_macro_vix

log = structlog.get_logger(__name__)

RegimeState = Literal["Confirmed Uptrend", "Uptrend Under Pressure", "Correction"]


# ---------------------------------------------------------------------------
# Distribution-day counter (D-02)
# ---------------------------------------------------------------------------


def _compute_distribution_days(spy: pd.DataFrame, window: int = 25) -> pd.Series:
    """Strict IBD: SPY close down > 0.2% AND volume > prev_volume; rolling 25.
    Returns int Series indexed by date.
    """
    prev_close = spy["close"].shift(1)
    prev_vol = spy["volume"].shift(1)
    is_dist_day = (
        (spy["close"] / prev_close - 1.0 < -0.002)
        & (spy["volume"] > prev_vol)
    )
    return is_dist_day.rolling(window).sum().fillna(0).astype(int)


# ---------------------------------------------------------------------------
# Three-state classifier (D-01 priority: Correction > Pressure > Uptrend)
# ---------------------------------------------------------------------------


def _classify_state(
    spy_above_200d: bool,
    breadth_pct: float,
    distribution_days: int,
    vix_level: float,
    settings: Any,
) -> RegimeState:
    """D-01 priority: Correction overrides any other state."""
    # Correction triggers — any one fires returns Correction immediately.
    if (
        not spy_above_200d
        or distribution_days >= settings.REGIME_DIST_DAYS_CORRECTION
        or vix_level >= settings.REGIME_VIX_CORRECTION
    ):
        return "Correction"
    # Confirmed Uptrend: ALL four conditions
    if (
        spy_above_200d
        and breadth_pct >= settings.REGIME_BREADTH_THRESHOLD * 100
        and distribution_days <= settings.REGIME_DIST_DAYS_PRESSURE - 1  # ≤ 4
        and vix_level < settings.REGIME_VIX_CONFIRMED
    ):
        return "Confirmed Uptrend"
    # Default — any single Confirmed condition fails OR dist in [5, 8]
    return "Uptrend Under Pressure"


# ---------------------------------------------------------------------------
# Vectorized regime_score (D-03; RESEARCH Pattern 5)
# ---------------------------------------------------------------------------


def _regime_score(df: pd.DataFrame) -> pd.Series:
    """Vectorized D-03 formula. df must have columns:
    spy_above_200d (bool), breadth_pct, distribution_days, vix_level.
    Returns Series in [0, 1].
    """
    spy_component = df["spy_above_200d"].astype(float)
    breadth_norm = (df["breadth_pct"] / 100.0).clip(0.0, 1.0)
    dist_norm = (1.0 - df["distribution_days"] / 9.0).clip(0.0, 1.0)
    vix_norm = (1.0 - (df["vix_level"] - 15.0) / 25.0).clip(0.0, 1.0)
    return (
        0.30 * spy_component
        + 0.40 * breadth_norm
        + 0.20 * dist_norm
        + 0.10 * vix_norm
    )


# ---------------------------------------------------------------------------
# Single-date row API
# ---------------------------------------------------------------------------


def compute_for_date(
    date: pd.Timestamp,
    panel: pd.DataFrame,
) -> pd.Series:
    """Single-date regime row. `panel` is the indicator panel with sma_200.

    Returns Series with 6 fields named per REG-01/02:
        spy_above_200d (bool), breadth_pct (float),
        distribution_days (int), vix_level (float),
        regime_state (RegimeState), regime_score (float in [0, 1])
    """
    spy = read_macro_spy()
    vix = read_macro_vix()
    settings = get_settings()

    # SPY 200d trend pass
    spy_sma200 = spy["close"].rolling(200).mean()
    spy_above_200d = bool(spy.loc[date, "close"] > spy_sma200.loc[date])

    # Breadth: % of universe above 200d SMA on this date.
    # Pitfall 11: denominator is "tickers with valid sma_200" — prevents
    # biased breadth during post-IPO clusters.
    snapshot = panel.xs(date, level="date")  # ticker × columns at this date
    has_data = snapshot["close"].notna() & snapshot["sma_200"].notna()
    if has_data.sum() == 0:
        breadth_pct = 0.0
    else:
        breadth_pct = float(
            (snapshot.loc[has_data, "close"] > snapshot.loc[has_data, "sma_200"]).mean()
            * 100
        )

    # Distribution days
    dist_days = int(_compute_distribution_days(spy).loc[date])

    # VIX (close-only — Pitfall 4)
    vix_level = float(vix.loc[date, "close"])

    # State
    state = _classify_state(
        spy_above_200d, breadth_pct, dist_days, vix_level, settings
    )

    # Score (call vectorized _regime_score on a 1-row frame)
    one_row = pd.DataFrame({
        "spy_above_200d": [spy_above_200d],
        "breadth_pct": [breadth_pct],
        "distribution_days": [dist_days],
        "vix_level": [vix_level],
    })
    regime_score = float(_regime_score(one_row).iloc[0])

    log.info(
        "regime_computed",
        date=str(date),
        state=state,
        score=regime_score,
    )

    return pd.Series(
        {
            "spy_above_200d": spy_above_200d,
            "breadth_pct": breadth_pct,
            "distribution_days": dist_days,
            "vix_level": vix_level,
            "regime_state": state,
            "regime_score": regime_score,
        },
        name=date,
    )


# ---------------------------------------------------------------------------
# Multi-date history API (Phase 5 backtest harness will consume this)
# ---------------------------------------------------------------------------


def build_history(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> pd.DataFrame:
    """Vectorized regime history across [start, end]. Used by the Phase 5
    backtest harness to read regime state without per-date Python loops.

    Reads SPY + VIX from the macro Parquet cache and the indicator panel for
    breadth_pct. Returns DataFrame indexed by date with the same 6 columns
    as compute_for_date.
    """
    spy = read_macro_spy()
    vix = read_macro_vix()
    settings = get_settings()

    spy_sma200 = spy["close"].rolling(200).mean()
    spy_above = (spy["close"] > spy_sma200).rename("spy_above_200d")
    dist_days = _compute_distribution_days(spy).rename("distribution_days")
    vix_close = vix["close"].rename("vix_level")

    # For build_history breadth_pct, we read panel once at the most-recent
    # snapshot and use it as a static breadth baseline within the date range.
    # Backtests should call compute_for_date per-date for point-in-time accuracy.
    panel = build_panel(str(end))
    breadth_series = (
        panel
        .reset_index()
        .groupby("date")
        .apply(lambda g: float(
            (g["close"][g["sma_200"].notna()] > g["sma_200"][g["sma_200"].notna()]).mean() * 100
        ) if g["sma_200"].notna().any() else 0.0)
        .rename("breadth_pct")
    )

    df = pd.concat(
        [spy_above, breadth_series, dist_days, vix_close],
        axis=1,
        join="inner",
    )
    df = df.loc[str(start):str(end)]

    # Apply classification per row
    df["regime_state"] = df.apply(
        lambda r: _classify_state(
            bool(r["spy_above_200d"]),
            float(r["breadth_pct"]),
            int(r["distribution_days"]),
            float(r["vix_level"]),
            settings,
        ),
        axis=1,
    )
    df["regime_score"] = _regime_score(df)
    df.index.name = "date"
    return df[
        [
            "spy_above_200d",
            "breadth_pct",
            "distribution_days",
            "vix_level",
            "regime_state",
            "regime_score",
        ]
    ]
```

DO NOT add imports of `yfinance`, `requests`, `fredapi`, `sqlite3`, etc. — the architecture test will fail.
  </action>
  <verify>
    <automated>uv run pytest tests/test_architecture.py -x -q && uv run python -c "from screener.regime import compute_for_date, build_history, _classify_state, _compute_distribution_days, _regime_score, RegimeState; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^def _classify_state" src/screener/regime.py` returns 1.
    - `grep -c "^def _compute_distribution_days" src/screener/regime.py` returns 1.
    - `grep -c "^def _regime_score" src/screener/regime.py` returns 1.
    - `grep -c "^def compute_for_date" src/screener/regime.py` returns 1.
    - `grep -c "^def build_history" src/screener/regime.py` returns 1.
    - `grep -c "RegimeState = Literal" src/screener/regime.py` returns 1.
    - `grep -c "from screener.persistence import read_macro_spy, read_macro_vix" src/screener/regime.py` returns 1.
    - `grep -c "from screener.indicators import build_panel" src/screener/regime.py` returns 1.
    - `grep -c "settings.REGIME_DIST_DAYS_CORRECTION" src/screener/regime.py` returns 1.
    - `grep -c "settings.REGIME_VIX_CORRECTION" src/screener/regime.py` returns 1.
    - `grep -c "regime_computed" src/screener/regime.py` returns 1 (structured-log event).
    - `grep -c "0.30 \\* spy_component" src/screener/regime.py` returns 1 (D-03 weight verbatim).
    - `grep -c "0.40 \\* breadth_norm" src/screener/regime.py` returns 1.
    - `grep -c "0.20 \\* dist_norm" src/screener/regime.py` returns 1.
    - `grep -c "0.10 \\* vix_norm" src/screener/regime.py` returns 1.
    - No imports of yfinance/requests/fredapi/sqlite3/urllib/httpx/requests_cache (`grep -lE "^(import|from) (yfinance|requests|fredapi|sqlite3|urllib|httpx|requests_cache)" src/screener/regime.py` exits 1).
    - `uv run pytest tests/test_architecture.py -x -q` exits 0 (regime in ALLOWED).
    - `uv run mypy --config-file pyproject.toml src/screener/regime.py` exits 0 (mypy strict on regime.py per existing config).
    - `uv run ruff check src/screener/regime.py` exits 0.
    - The import smoke test in `<automated>` exits 0 with `OK`.
  </acceptance_criteria>
  <done>regime.py replaced with full body; 5 helper functions + RegimeState type + compute_for_date + build_history; D-01 priority chain encoded with Correction first; D-02 dist-day formula verbatim; D-03 score weights verbatim; structlog regime_computed emitted; architecture, mypy, ruff all clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Write tests/test_regime.py + tests/test_regime_score.py + extend conftest with synthetic SPY/VIX fixtures</name>
  <files>tests/test_regime.py, tests/test_regime_score.py, tests/conftest.py</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 1050-1107 — test_regime.py + test_regime_score.py templates with synthetic SPY/VIX fixtures and hypothesis pattern)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-RESEARCH.md (Validation Architecture lines 887-918 — full required test list including REG-01/02/03 unit tests; Pitfall 11 — breadth_pct denominator)
    - /Users/belwinjulian/Desktop/SwingTrading/tests/conftest.py (existing Phase 3 section header from Plan 03-01; existing _REF_DATE constant pattern from Phase 2)
    - /Users/belwinjulian/Desktop/SwingTrading/pyproject.toml (confirm hypothesis>=6,<7 in dev extras for property tests)
  </read_first>
  <behavior>
    - Test: `test_compute_for_date_columns` — output Series has exactly 6 fields named spy_above_200d / breadth_pct / distribution_days / vix_level / regime_state / regime_score.
    - Test: `test_distribution_day_idiom` — synthetic SPY where 4 days satisfy strict-IBD criteria; `_compute_distribution_days(spy).iloc[-1]` == 4 (rolling 25 captures all 4).
    - Test: `test_regime_state_enum` — output regime_state ∈ {Confirmed Uptrend, Uptrend Under Pressure, Correction}.
    - Test: `test_correction_overrides_pressure` — D-01 priority: when dist=10 and breadth=70%, state is Correction (not Pressure).
    - Test: `test_correction_overrides_on_spy_below_200d` — when SPY < SMA200 even with low dist + low VIX, state is Correction.
    - Test: `test_correction_overrides_on_vix_30` — when VIX ≥ 30 even with high breadth + low dist + SPY > SMA200, state is Correction.
    - Test: `test_regime_score_seam_exists` — output Series has `regime_score` field with float type (REG-03 seam present).
    - Test: `test_breadth_pct_denominator_uses_valid_sma` — Pitfall 11: a panel where 50% of tickers lack sma_200 still computes correct breadth using the valid-sma-only denominator.
    - Test: `test_regime_score_in_unit_interval` (hypothesis) — over 100 random inputs (spy_above ∈ {True,False}, breadth ∈ [0, 100], dist ∈ [0, 20], vix ∈ [10, 80]), regime_score ∈ [0, 1].
  </behavior>
  <action>
**Step A — Append synthetic SPY/VIX fixtures to `tests/conftest.py`** (under the Phase 3 section header from Plan 03-01):

```python
@pytest.fixture(scope="session")
def synthetic_spy_with_dist_days() -> pd.DataFrame:
    """SPY OHLCV with exactly 4 strict-IBD distribution days in the last 25
    sessions — used by test_distribution_day_idiom.

    Distribution day = close down >0.2% AND volume > prev_volume.
    """
    n = 50
    idx = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)
    close = np.full(n, 100.0)
    volume = np.full(n, 1_000_000, dtype="int64")

    # Inject 4 distribution days at indices 30, 35, 40, 45 (within last 25 sessions
    # of index n-1=49; window covers indices 25..49).
    for i in (30, 35, 40, 45):
        close[i] = close[i - 1] * 0.99   # 1% drop > 0.2%
        volume[i] = int(volume[i - 1] * 1.5)  # higher volume
    return pd.DataFrame(
        {
            "open": close, "high": close * 1.01, "low": close * 0.98,
            "close": close, "volume": volume,
        },
        index=pd.DatetimeIndex(idx, name="date"),
    )


@pytest.fixture(scope="session")
def synthetic_vix_calm() -> pd.DataFrame:
    """VIX series with close always at 15 (calm market — Confirmed Uptrend territory)."""
    idx = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=50)
    return pd.DataFrame(
        {"close": [15.0] * 50},
        index=pd.DatetimeIndex(idx, name="date"),
    )
```

**Step B — Create `tests/test_regime.py`:**

```python
"""Regime module unit tests (REG-01, REG-02, REG-03; D-01, D-02, D-03; Pitfall 11)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from screener.regime import (
    _classify_state,
    _compute_distribution_days,
    _regime_score,
    compute_for_date,
)


class _StubSettings:
    REGIME_BREADTH_THRESHOLD = 0.60
    REGIME_DIST_DAYS_PRESSURE = 5
    REGIME_DIST_DAYS_CORRECTION = 9
    REGIME_VIX_CORRECTION = 30.0
    REGIME_VIX_CONFIRMED = 20.0


SETTINGS = _StubSettings()


# --- _classify_state — D-01 priority chain ---------------------------------


def test_classify_state_confirmed_uptrend() -> None:
    s = _classify_state(spy_above_200d=True, breadth_pct=70.0,
                        distribution_days=2, vix_level=15.0, settings=SETTINGS)
    assert s == "Confirmed Uptrend"


def test_classify_state_uptrend_under_pressure_breadth() -> None:
    """Breadth < 60% — not Correction; falls back to Pressure."""
    s = _classify_state(spy_above_200d=True, breadth_pct=50.0,
                        distribution_days=2, vix_level=15.0, settings=SETTINGS)
    assert s == "Uptrend Under Pressure"


def test_correction_overrides_on_spy_below_200d() -> None:
    s = _classify_state(spy_above_200d=False, breadth_pct=70.0,
                        distribution_days=2, vix_level=15.0, settings=SETTINGS)
    assert s == "Correction"


def test_correction_overrides_pressure() -> None:
    """D-01: dist >= 9 forces Correction even if breadth and VIX are healthy."""
    s = _classify_state(spy_above_200d=True, breadth_pct=70.0,
                        distribution_days=10, vix_level=15.0, settings=SETTINGS)
    assert s == "Correction"


def test_correction_overrides_on_vix_30() -> None:
    s = _classify_state(spy_above_200d=True, breadth_pct=70.0,
                        distribution_days=2, vix_level=35.0, settings=SETTINGS)
    assert s == "Correction"


# --- _compute_distribution_days — strict IBD definition (D-02) -------------


def test_distribution_day_idiom(synthetic_spy_with_dist_days: pd.DataFrame) -> None:
    """4 injected dist days within the last 25 sessions → rolling sum at last day == 4."""
    out = _compute_distribution_days(synthetic_spy_with_dist_days, window=25)
    assert out.iloc[-1] == 4


def test_distribution_day_volume_filter() -> None:
    """A close-down day with NOT-higher volume must NOT count as a distribution day."""
    n = 30
    idx = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)
    close = np.full(n, 100.0)
    close[15] = 99.0  # 1% drop
    vol = np.full(n, 1_000_000, dtype="int64")
    vol[15] = vol[14] - 1  # LOWER volume — must NOT count
    spy = pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.98,
         "close": close, "volume": vol},
        index=pd.DatetimeIndex(idx, name="date"),
    )
    out = _compute_distribution_days(spy, window=25)
    assert out.iloc[-1] == 0


# --- _regime_score boundary cases ------------------------------------------


def test_regime_score_all_good() -> None:
    df = pd.DataFrame({
        "spy_above_200d": [True],
        "breadth_pct": [100.0],
        "distribution_days": [0],
        "vix_level": [10.0],
    })
    score = _regime_score(df).iloc[0]
    assert score == pytest.approx(1.0)


def test_regime_score_all_bad() -> None:
    df = pd.DataFrame({
        "spy_above_200d": [False],
        "breadth_pct": [0.0],
        "distribution_days": [10],
        "vix_level": [50.0],
    })
    score = _regime_score(df).iloc[0]
    assert score == pytest.approx(0.0)


# --- compute_for_date — REG-01/02/03 integration ---------------------------


def _setup_macro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                 spy_df: pd.DataFrame, vix_df: pd.DataFrame) -> None:
    """Write macro parquets to tmp_path/macro and monkeypatch the dir."""
    macro_dir = tmp_path / "macro"
    macro_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("screener.persistence._macro_dir", lambda: macro_dir)
    spy_df.to_parquet(macro_dir / "spy.parquet", engine="pyarrow", index=True)
    vix_df.to_parquet(macro_dir / "vix.parquet", engine="pyarrow", index=True)


def _make_indicator_panel(n_tickers: int = 5, n_days: int = 260) -> pd.DataFrame:
    """Build a minimal indicator-panel-shaped frame with sma_200 and close."""
    tickers = [f"TKR{i}" for i in range(n_tickers)]
    dates = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n_days)
    rows = []
    idx_pairs = []
    for t in tickers:
        for d in dates:
            idx_pairs.append((t, d))
            rows.append({"close": 110.0, "sma_200": 100.0})  # close > sma_200
    idx = pd.MultiIndex.from_tuples(idx_pairs, names=["ticker", "date"])
    return pd.DataFrame(rows, index=idx)


def test_compute_for_date_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_with_dist_days: pd.DataFrame,
    synthetic_vix_calm: pd.DataFrame,
) -> None:
    _setup_macro(tmp_path, monkeypatch, synthetic_spy_with_dist_days, synthetic_vix_calm)
    panel = _make_indicator_panel()
    target = synthetic_spy_with_dist_days.index[-1]  # use last shared date
    out = compute_for_date(target, panel)
    expected = {"spy_above_200d", "breadth_pct", "distribution_days",
                "vix_level", "regime_state", "regime_score"}
    assert set(out.index) == expected


def test_regime_state_enum(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_with_dist_days: pd.DataFrame,
    synthetic_vix_calm: pd.DataFrame,
) -> None:
    _setup_macro(tmp_path, monkeypatch, synthetic_spy_with_dist_days, synthetic_vix_calm)
    panel = _make_indicator_panel()
    target = synthetic_spy_with_dist_days.index[-1]
    out = compute_for_date(target, panel)
    assert out["regime_state"] in {"Confirmed Uptrend", "Uptrend Under Pressure", "Correction"}


def test_regime_score_seam_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_with_dist_days: pd.DataFrame,
    synthetic_vix_calm: pd.DataFrame,
) -> None:
    """REG-03: regime_score column is present and is a float in [0, 1]."""
    _setup_macro(tmp_path, monkeypatch, synthetic_spy_with_dist_days, synthetic_vix_calm)
    panel = _make_indicator_panel()
    target = synthetic_spy_with_dist_days.index[-1]
    out = compute_for_date(target, panel)
    assert "regime_score" in out.index
    assert 0.0 <= float(out["regime_score"]) <= 1.0


def test_breadth_pct_denominator_uses_valid_sma(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_spy_with_dist_days: pd.DataFrame,
    synthetic_vix_calm: pd.DataFrame,
) -> None:
    """Pitfall 11: tickers without sma_200 are excluded from breadth denominator.
    Build a panel where half the tickers have NaN sma_200; the other half
    all have close > sma_200. Breadth should be 100% (only the valid half counts)."""
    _setup_macro(tmp_path, monkeypatch, synthetic_spy_with_dist_days, synthetic_vix_calm)
    target = synthetic_spy_with_dist_days.index[-1]
    tickers = [f"TKR{i}" for i in range(10)]
    rows = []
    idx_pairs = []
    for i, t in enumerate(tickers):
        idx_pairs.append((t, target))
        if i < 5:
            rows.append({"close": 110.0, "sma_200": 100.0})  # valid + above
        else:
            rows.append({"close": 110.0, "sma_200": float("nan")})  # ineligible
    panel = pd.DataFrame(
        rows,
        index=pd.MultiIndex.from_tuples(idx_pairs, names=["ticker", "date"]),
    )
    out = compute_for_date(target, panel)
    assert float(out["breadth_pct"]) == pytest.approx(100.0)
```

**Step C — Create `tests/test_regime_score.py`** (first hypothesis property test):

```python
"""regime_score property test (REG-02): regime_score ∈ [0, 1] for any input."""

from __future__ import annotations

import pandas as pd
from hypothesis import given
from hypothesis import strategies as st

from screener.regime import _regime_score


@given(
    spy_above=st.booleans(),
    breadth=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    dist=st.integers(min_value=0, max_value=20),
    vix=st.floats(min_value=10.0, max_value=80.0, allow_nan=False, allow_infinity=False),
)
def test_regime_score_in_unit_interval(
    spy_above: bool, breadth: float, dist: int, vix: float
) -> None:
    df = pd.DataFrame({
        "spy_above_200d": [spy_above],
        "breadth_pct": [breadth],
        "distribution_days": [dist],
        "vix_level": [vix],
    })
    score = _regime_score(df).iloc[0]
    assert 0.0 <= float(score) <= 1.0
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_regime.py tests/test_regime_score.py -m "not slow and not integration" -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_regime.py` exists.
    - `tests/test_regime_score.py` exists.
    - `grep -c "^def test_" tests/test_regime.py` returns at least 11 (5 classify_state + 2 distribution_day + 2 score boundary + 4 compute_for_date integration tests).
    - `grep -c "test_correction_overrides_pressure" tests/test_regime.py` returns 1.
    - `grep -c "test_correction_overrides_on_spy_below_200d" tests/test_regime.py` returns 1.
    - `grep -c "test_correction_overrides_on_vix_30" tests/test_regime.py` returns 1.
    - `grep -c "test_breadth_pct_denominator_uses_valid_sma" tests/test_regime.py` returns 1.
    - `grep -c "test_regime_score_in_unit_interval" tests/test_regime_score.py` returns 1.
    - `grep -c "from hypothesis import given" tests/test_regime_score.py` returns 1.
    - `grep -c "synthetic_spy_with_dist_days" tests/conftest.py` returns 1.
    - `grep -c "synthetic_vix_calm" tests/conftest.py` returns 1.
    - `uv run pytest tests/test_regime.py -x -q` exits 0.
    - `uv run pytest tests/test_regime_score.py -x -q` exits 0.
    - `uv run ruff check tests/test_regime.py tests/test_regime_score.py tests/conftest.py` exits 0.
  </acceptance_criteria>
  <done>tests/test_regime.py with 11+ tests covering D-01 priority chain (5 cases), D-02 distribution day (2 cases), D-03 score boundary (2 cases), and 4 compute_for_date integration tests including Pitfall 11; tests/test_regime_score.py with hypothesis property test; conftest.py extended; all green.</done>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_regime.py tests/test_regime_score.py tests/test_architecture.py -x -q` exits 0
- `uv run mypy --config-file pyproject.toml src/screener/regime.py` exits 0
- `uv run ruff check src/screener/regime.py tests/test_regime.py tests/test_regime_score.py tests/conftest.py` exits 0
- `uv run python -c "from screener.regime import compute_for_date, build_history; print('OK')"` exits 0
- All Phase 1 + 2 + 3 prior-plan tests still green: `uv run pytest -m "not slow and not integration" -x -q` exits 0
</verification>

<success_criteria>
- regime.py replaced (was 7-line stub) with full body: 3 helpers + RegimeState type + compute_for_date + build_history
- D-01 priority chain encoded with Correction overriding Pressure regardless of breadth/VIX/dist as long as any Correction trigger fires
- D-02 distribution-day formula verbatim: close < prev_close by > 0.2% AND volume > prev_volume; rolling 25 window
- D-03 score weights verbatim: 0.30 spy + 0.40 breadth + 0.20 dist + 0.10 vix; result clipped to [0, 1]
- Breadth_pct denominator uses (close.notna() & sma_200.notna()) mask per Pitfall 11; verified by `test_breadth_pct_denominator_uses_valid_sma`
- structlog `regime_computed` event emitted with date, state, score on every compute_for_date call
- 11+ unit tests in test_regime.py + 1 hypothesis property test in test_regime_score.py covering REG-01/02/03 + all D-01 Correction-priority paths + Pitfall 11
- Architecture test still green: regime.py imports only allowed peers (data, indicators, persistence, config, obs)
- mypy strict + ruff clean on regime.py
</success_criteria>

<output>
After completion, create `.planning/phases/03-indicator-panel-regime/03-04-SUMMARY.md` documenting the regime module API (compute_for_date / build_history), the D-01 priority chain implementation, the structlog event names emitted, and the Pitfall 11 mitigation. Note any deviations.
</output>
