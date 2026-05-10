---
phase: 03-indicator-panel-regime
plan: 03
type: execute
wave: 2
depends_on:
  - 03-01
files_modified:
  - src/screener/indicators/__init__.py
  - src/screener/indicators/trend.py
  - src/screener/indicators/volatility.py
  - src/screener/indicators/volume.py
  - src/screener/indicators/relative_strength.py
  - tests/test_indicators_panel.py
  - tests/test_indicators_trend.py
  - tests/test_indicators_volatility.py
  - tests/test_indicators_volume.py
  - tests/test_indicators_rs.py
  - tests/test_indicators_purity.py
  - tests/conftest.py
autonomous: true
requirements:
  - IND-01
  - IND-03
  - IND-04
  - IND-05
tags:
  - indicators
  - pure-functions
  - panel

must_haves:
  truths:
    - "indicators.build_panel(snapshot_date) reads via persistence.read_panel and returns the panel with 10 new columns: sma_10, sma_20, sma_50, sma_150, sma_200, atr_14, adr_pct, obv, dryup_ratio, rs_raw, rs_rating (rs_raw + rs_rating = 2 cols, plus 8 others — 10 total per IND-01)."
    - "Every indicator function is a pure DataFrame transform — no I/O, no global state; consumes Phase 2 OhlcvPanelSchema (ticker, date) MultiIndex panel and returns the same MultiIndex with appended columns. tests/test_architecture.py::test_indicators_signals_pure_no_io_imports passes."
    - "Every pandas-ta-classic call is wrapped in `_safe_*` helpers that return a NaN-filled Series when input is shorter than the lookback (RESEARCH Pitfall 2: ta.sma/atr/obv return None on short inputs)."
    - "RS rating is cross-sectional per date: rs_raw is per-ticker time-series; pct rank is `groupby(level='date').rank(pct=True)`; rs_rating is `pd.Int64Dtype` (NaN preserved for tickers with < 252d history per Pitfall 9)."
    - "indicators/trend.py contains NO `ema` reference (case-insensitive) — neither code nor comments — so the IND-02 grep gate (added in Plan 03-05) does not trip on this file."
    - "All per-ticker time-series transforms use `groupby(level='ticker')` to prevent cross-ticker bleed (Pitfall 8)."
  artifacts:
    - path: "src/screener/indicators/trend.py"
      provides: "_safe_sma + sma_panel; SMA(10/20/50/150/200) per IND-01"
      contains: "def _safe_sma, def sma_panel, import pandas_ta_classic as ta"
    - path: "src/screener/indicators/volatility.py"
      provides: "_safe_atr + atr_panel + adr_pct_panel; ATR(14) per IND-01, ADR%(20) per IND-04"
      contains: "def _safe_atr, def atr_panel, def adr_pct_panel"
    - path: "src/screener/indicators/volume.py"
      provides: "_safe_obv + obv_panel + dryup_ratio_panel; OBV + dryup-ratio per IND-01 / D-09"
      contains: "def _safe_obv, def obv_panel, def dryup_ratio_panel"
    - path: "src/screener/indicators/relative_strength.py"
      provides: "rs_panel — IBD-style cross-sectional RS per IND-03"
      contains: "def rs_panel, groupby(level=\"date\").rank(pct=True)"
    - path: "src/screener/indicators/__init__.py"
      provides: "build_panel(snapshot_date) — panel-in / panel-out orchestrator per D-07"
      contains: "def build_panel, from screener.persistence import read_panel"
    - path: "tests/test_indicators_panel.py"
      provides: "build_panel integration tests — 10 new cols, MultiIndex preservation, NaN warmup"
      exports: ["test_build_panel_returns_10_new_cols", "test_build_panel_preserves_multiindex", "test_short_history_nan_warmup"]
    - path: "tests/test_indicators_rs.py"
      provides: "RS cross-sectional + per-ticker shift isolation + Int64 dtype tests"
      exports: ["test_rs_rating_in_range", "test_rs_nan_for_short_history", "test_rs_per_ticker_shift_isolation"]
  key_links:
    - from: "src/screener/indicators/__init__.py build_panel"
      to: "src/screener/persistence.py read_panel"
      via: "Phase 2 read entrypoint"
      pattern: "read_panel\\(snapshot_date\\)"
    - from: "src/screener/indicators/trend.py sma_panel"
      to: "pandas_ta_classic.sma"
      via: "_safe_sma wrapper (Pitfall 2 — None-on-short-series defense)"
      pattern: "ta\\.sma\\(close, length=length\\)"
    - from: "src/screener/indicators/relative_strength.py rs_panel"
      to: "pandas.DataFrame.groupby(level='date').rank"
      via: "cross-sectional percentile rank per date (Pitfall 8 — never per-ticker rank)"
      pattern: "groupby\\(level=.date.\\)\\.rank\\(pct=True\\)"
---

<objective>
Build the pure-function indicator panel — 5 new modules under `src/screener/indicators/` plus the orchestrator in `__init__.py`. Output: `indicators.build_panel(snapshot_date)` returns the Phase 2 OHLCV panel + 10 new columns: SMA(10/20/50/150/200), ATR(14), ADR%(20), OBV, dryup_ratio, rs_raw, rs_rating.

Purpose: Provide the indicator surface that Phase 4's Trend Template (Minervini 8 conditions), Phase 6's pattern detection, and Plan 03-04's regime breadth_pct will consume. Pure functions only — every external I/O is rejected by the architecture test (Phase 1 D-16). All pandas-ta-classic calls are defended against the `None`-on-short-input bug (RESEARCH Pitfall 2).

Output:
- `indicators/trend.py` (new) — _safe_sma + sma_panel
- `indicators/volatility.py` (new) — _safe_atr + atr_panel + adr_pct_panel
- `indicators/volume.py` (new) — _safe_obv + obv_panel + dryup_ratio_panel
- `indicators/relative_strength.py` (new) — rs_panel
- `indicators/__init__.py` (modified — keep current docstring; add build_panel())
- 6 test files (test_indicators_panel + per-domain unit tests + purity test)
- `tests/conftest.py` extended with synthetic_short_history_panel + synthetic_multi_ticker_panel fixtures
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

@src/screener/indicators/__init__.py
@src/screener/persistence.py
@tests/test_architecture.py
@tests/test_persistence.py
@tests/conftest.py
@CLAUDE.md

<interfaces>
<!-- pandas-ta-classic 0.4.47 — verified live 2026-05-10, returns None on short series. -->
import pandas_ta_classic as ta
ta.sma(close: pd.Series, length: int) -> pd.Series | None  # column name "SMA_<length>"; None when len(close) < length
ta.atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14, mamode: str = "rma") -> pd.Series | None  # "ATRr_14"; default mamode="rma" (Wilder's)
ta.obv(close: pd.Series, volume: pd.Series) -> pd.Series | None  # column name "OBV"

<!-- From src/screener/persistence.py (existing Phase 2): -->
def read_panel(snapshot_date: str | pd.Timestamp) -> pd.DataFrame:
    """Returns OhlcvPanelSchema-validated MultiIndex (ticker, date) DataFrame
    with columns {open, high, low, close, volume}."""

<!-- From tests/test_architecture.py (line 32): -->
ALLOWED["indicators"] = {"persistence", "config", "obs"}  # NO data, NO regime
forbidden_external = {
    "requests", "yfinance", "finnhub", "edgar", "edgartools", "fredapi",
    "sqlite3", "urllib", "urllib3", "httpx", "requests_cache",
}  # forbidden in indicators/ AND signals/

<!-- IBD RS formula (CLAUDE.md §"Signal Formulas — Quick-Reference"): -->
RS_raw    = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)
RS_rating = (rs_raw.rank(pct=True) * 99).round().clip(1, 99).astype(int)

<!-- ADR% formula (CLAUDE.md): -->
ADR_pct = 100 * ((high/low).rolling(20).mean() - 1)
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| persistence → indicators | Indicator panel consumes Phase 2 schema-validated panel; pandera schema is the trust boundary. Indicators are pure functions; if a malformed panel sneaks past the schema (impossible by Phase 2 D-16), indicator output is corrupt. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-01 | Tampering | indicators/build_panel | mitigate | Input panel is already validated by persistence.read_panel via validate_at_read(OhlcvPanelSchema, df) lazy-mode; no additional validation needed in indicators/. _safe_* wrappers protect against ta.sma/atr/obv None returns on short series (Pitfall 2) — defensive return preserves panel shape so downstream signals see NaN warmup, not an attribute error. |
</threat_model>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create indicators/{trend,volatility,volume,relative_strength}.py with pure functions + _safe_* wrappers</name>
  <files>src/screener/indicators/trend.py, src/screener/indicators/volatility.py, src/screener/indicators/volume.py, src/screener/indicators/relative_strength.py</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/indicators/__init__.py (current 7-line docstring; the comment "SMAs (NOT EMAs in the Trend Template — see CLAUDE.md §13.6 pitfall #4)" stays — it is intentionally NOT in the IND-02 grep gate scope)
    - /Users/belwinjulian/Desktop/SwingTrading/CLAUDE.md (§"Signal Formulas — Quick-Reference" — IBD RS, ADR%, SMA-not-EMA rule)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-RESEARCH.md (Pattern 1 lines 213-237 — _safe wrapper; Pattern 2 lines 250-279 — RS cross-sectional; Pattern 3 lines 286-296 — ADR%; Pitfalls 2/3/6/8/9; Examples 2/3 lines 596-667 — verbatim file bodies)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 370-542 — per-file analog + verbatim function bodies for trend.py / volatility.py / volume.py / relative_strength.py)
    - /Users/belwinjulian/Desktop/SwingTrading/tests/test_architecture.py (lines 30-44 — ALLOWED["indicators"] = {persistence, config, obs}; lines 164-196 — forbidden_external set; ANY import of yfinance/requests/sqlite3/etc. fails CI)
  </read_first>
  <behavior>
    - Test: `from screener.indicators.trend import sma_panel, _safe_sma` — both importable.
    - Test: `_safe_sma(pd.Series([1,2,3]), length=200)` returns `pd.Series` with NaN, NOT `None` (RESEARCH Pitfall 2).
    - Test: `sma_panel(panel, lengths=(10, 20, 50, 150, 200))` adds 5 new columns to the panel (named `sma_10` through `sma_200`); preserves (ticker, date) MultiIndex.
    - Test: `from screener.indicators.volatility import atr_panel, adr_pct_panel, _safe_atr` — importable.
    - Test: ADR%(20) for high=105/low=95 returns ≈10.526% (formula verification, RESEARCH Pattern 3).
    - Test: `atr_panel(panel, length=14)` adds `atr_14` column.
    - Test: `from screener.indicators.volume import obv_panel, dryup_ratio_panel, _safe_obv` — importable.
    - Test: `dryup_ratio_panel(panel, length=50)` adds `dryup_ratio` column = `volume / SMA(volume, 50)` per D-09.
    - Test: `from screener.indicators.relative_strength import rs_panel` — importable.
    - Test: `rs_panel(panel)` adds `rs_raw` (float) + `rs_rating` (Int64Dtype) columns.
    - Test: `rs_rating` values fall in [1, 99] for tickers with full history; NaN for tickers with < 252d history.
    - Test: per-ticker shift isolation — for two tickers with different lengths, the AAPL row at date X is NOT shifted from MSFT's row 63 days ago (Pitfall 8 verification).
    - Test: NO `ema` (case-insensitive) appears in `src/screener/indicators/trend.py` — `grep -i "ema" src/screener/indicators/trend.py` exits with status 1 (no matches).
    - Test: Architecture test still passes — `tests/test_architecture.py::test_indicators_signals_pure_no_io_imports` exits 0 (no forbidden imports).
  </behavior>
  <action>
**CRITICAL — IND-02 SCOPE LOCK:** The string `ema` (case-insensitive) MUST NOT appear ANYWHERE in `src/screener/indicators/trend.py` — not in code, not in comments, not in docstrings, not in variable names. The CI grep gate (added in Plan 03-05) is scoped to this exact file. Use phrases like "simple rolling means" / "non-exponential" / "must not be exponentially-weighted" if you need to describe the contrast in docstrings.

**Step A — Create `src/screener/indicators/trend.py`:**

```python
"""trend — SMA panel computations.

This module computes simple rolling means (NOT exponentially-weighted) per
CLAUDE.md §13.6 pitfall #4. The CI grep gate (IND-02) is scoped to this file
specifically — do not introduce the substring 'ema' (case-insensitive) here.

Pure-function discipline (Phase 1 D-16): NO I/O, NO global state. Imports only
pandas, pandas_ta_classic (third-party math), and stdlib.
"""

from __future__ import annotations

import pandas as pd
import pandas_ta_classic as ta


def _safe_sma(close: pd.Series, length: int) -> pd.Series:
    """Wrap ta.sma to return a NaN-filled Series when input is shorter than `length`.

    pandas-ta-classic returns None in that case (verified live 2026-05-10
    against pandas-ta-classic==0.4.47), which crashes downstream `.rename()`
    and DataFrame assembly (RESEARCH Pitfall 2).
    """
    result = ta.sma(close, length=length)
    if result is None:
        return pd.Series(float("nan"), index=close.index, name=f"SMA_{length}")
    return result


def sma_panel(
    panel: pd.DataFrame,
    lengths: tuple[int, ...] = (10, 20, 50, 150, 200),
) -> pd.DataFrame:
    """Append sma_<length> columns to the panel, computed per-ticker.

    Pitfall 8: groupby(level='ticker') is required to prevent rolling-window
    bleed across tickers in the (ticker, date) MultiIndex.
    """
    out = panel.copy()
    for L in lengths:
        col = f"sma_{L}"
        out[col] = (
            panel.groupby(level="ticker")["close"]
            .apply(lambda c: _safe_sma(c, L).reset_index(level=0, drop=True))
        )
    return out
```

**Step B — Create `src/screener/indicators/volatility.py`:**

```python
"""volatility — ATR(14) and ADR%(20) panel computations.

Pure-function discipline (Phase 1 D-16): NO I/O, NO global state.
"""

from __future__ import annotations

import pandas as pd
import pandas_ta_classic as ta


def _safe_atr(h: pd.Series, low: pd.Series, c: pd.Series, length: int) -> pd.Series:
    """Wrap ta.atr; default mamode='rma' is Wilder's smoothing per
    docs/methodology.md §6. None on short input → NaN Series (Pitfall 2).
    """
    result = ta.atr(h, low, c, length=length)
    if result is None:
        return pd.Series(float("nan"), index=c.index, name=f"ATRr_{length}")
    return result


def atr_panel(panel: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Append atr_<length> column. Per-ticker rolling (Pitfall 8)."""
    out = panel.copy()

    def _per_ticker(g: pd.DataFrame) -> pd.Series:
        return _safe_atr(g["high"], g["low"], g["close"], length).reset_index(
            level=0, drop=True
        )

    out[f"atr_{length}"] = panel.groupby(level="ticker").apply(_per_ticker)
    return out


def adr_pct_panel(panel: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """ADR%(length) per CLAUDE.md §"Signal Formulas — ADR%":
        ADR_pct = 100 * (mean(high/low over `length` days) - 1)

    Per-ticker rolling — groupby level='ticker' so the window doesn't span tickers.
    Verified live 2026-05-10: high=105/low=95 → 10.526%.
    """
    out = panel.copy()
    ratio = panel["high"] / panel["low"]
    out["adr_pct"] = (
        100.0
        * (
            ratio.groupby(level="ticker")
            .rolling(length)
            .mean()
            .droplevel(0)
            - 1.0
        )
    )
    return out
```

**Step C — Create `src/screener/indicators/volume.py`:**

```python
"""volume — OBV + dryup-ratio panel computations.

D-09: dryup_ratio = volume / SMA(volume, 50). Values < 0.5 indicate significant
volume contraction; the 50d window aligns with Phase 6 VCP breakout-volume
baseline (breakout volume >= 1.5 * SMA(volume, 50)).

Pure-function discipline (Phase 1 D-16).
"""

from __future__ import annotations

import pandas as pd
import pandas_ta_classic as ta


def _safe_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Wrap ta.obv; None on short input → NaN Series (Pitfall 2)."""
    result = ta.obv(close, volume)
    if result is None:
        return pd.Series(float("nan"), index=close.index, name="OBV")
    return result


def obv_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Append obv column, computed per-ticker."""
    out = panel.copy()

    def _per_ticker(g: pd.DataFrame) -> pd.Series:
        return _safe_obv(g["close"], g["volume"]).reset_index(level=0, drop=True)

    out["obv"] = panel.groupby(level="ticker").apply(_per_ticker)
    return out


def dryup_ratio_panel(panel: pd.DataFrame, length: int = 50) -> pd.DataFrame:
    """D-09: dryup_ratio = volume / SMA(volume, length)."""
    out = panel.copy()
    sma_vol = (
        panel.groupby(level="ticker")["volume"]
        .rolling(length)
        .mean()
        .droplevel(0)
    )
    out["dryup_ratio"] = panel["volume"] / sma_vol
    return out
```

**Step D — Create `src/screener/indicators/relative_strength.py`:**

```python
"""relative_strength — IBD-style RS computation (cross-sectional, per-date).

Formula (CLAUDE.md §"Signal Formulas — IBD-style RS"):
    rs_raw    = 2*(C/C_63) + (C/C_126) + (C/C_189) + (C/C_252)
    rs_rating = (rs_raw.rank(pct=True) * 99).round().clip(1, 99).astype(Int64)

Cross-sectional rank per date — groupby(level='date'). NaN tickers
(insufficient history) are excluded from the ranking and receive NaN
rs_rating per CONTEXT.md "RS percentile ranking excludes NaN tickers".

Pitfalls handled:
- 8: per-ticker shifts use groupby(level='ticker').shift() — never naked .shift()
- 9: rs_rating is pd.Int64Dtype (nullable Int64), NOT int — int can't hold NaN
"""

from __future__ import annotations

import pandas as pd


def rs_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Compute rs_raw and rs_rating for the (ticker, date) MultiIndex panel.

    Returns the panel with two new columns:
    - rs_raw: float (NaN where any of C_63 / C_126 / C_189 / C_252 is missing)
    - rs_rating: pd.Int64Dtype in [1, 99] (NaN where rs_raw is NaN)
    """
    by_ticker = panel.groupby(level="ticker")["close"]
    c_63 = by_ticker.shift(63)
    c_126 = by_ticker.shift(126)
    c_189 = by_ticker.shift(189)
    c_252 = by_ticker.shift(252)
    rs_raw = (
        2.0 * (panel["close"] / c_63)
        + (panel["close"] / c_126)
        + (panel["close"] / c_189)
        + (panel["close"] / c_252)
    )
    pct = rs_raw.groupby(level="date").rank(pct=True)
    rs_rating = (pct * 99).round().clip(1, 99)
    rs_rating = rs_rating.astype("Int64")  # nullable Int64 (Pitfall 9)
    out = panel.copy()
    out["rs_raw"] = rs_raw
    out["rs_rating"] = rs_rating
    return out
```

DO NOT add any I/O imports (yfinance, requests, sqlite3, fredapi, urllib, etc.) — the architecture test will fail. Only `pandas`, `pandas_ta_classic`, and stdlib are permitted.
  </action>
  <verify>
    <automated>uv run pytest tests/test_architecture.py -x -q && uv run python -c "from screener.indicators.trend import sma_panel, _safe_sma; from screener.indicators.volatility import atr_panel, adr_pct_panel, _safe_atr; from screener.indicators.volume import obv_panel, dryup_ratio_panel, _safe_obv; from screener.indicators.relative_strength import rs_panel; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - All 4 files exist: `src/screener/indicators/{trend,volatility,volume,relative_strength}.py`.
    - `grep -ic "ema" src/screener/indicators/trend.py` returns 0 (NO matches anywhere — IND-02 prep).
    - `grep -c "^def sma_panel" src/screener/indicators/trend.py` returns 1.
    - `grep -c "^def _safe_sma" src/screener/indicators/trend.py` returns 1.
    - `grep -c "^def atr_panel" src/screener/indicators/volatility.py` returns 1.
    - `grep -c "^def adr_pct_panel" src/screener/indicators/volatility.py` returns 1.
    - `grep -c "^def obv_panel" src/screener/indicators/volume.py` returns 1.
    - `grep -c "^def dryup_ratio_panel" src/screener/indicators/volume.py` returns 1.
    - `grep -c "^def rs_panel" src/screener/indicators/relative_strength.py` returns 1.
    - `grep -c "groupby(level=.ticker.)" src/screener/indicators/relative_strength.py` returns at least 1 (per-ticker shift isolation — Pitfall 8).
    - `grep -c 'groupby(level="date")\\.rank' src/screener/indicators/relative_strength.py` returns 1.
    - `grep -c '\\.astype("Int64")' src/screener/indicators/relative_strength.py` returns 1 (nullable Int64 — Pitfall 9).
    - No `import yfinance|import requests|import fredapi|import sqlite3|import urllib|import httpx|import requests_cache|from yfinance|from requests|from fredapi|from sqlite3|from urllib|from httpx|from requests_cache` in any of the 4 files (`grep -lE "^(import|from) (yfinance|requests|fredapi|sqlite3|urllib|httpx|requests_cache)" src/screener/indicators/*.py` exits with status 1 — no matches).
    - `uv run pytest tests/test_architecture.py -x -q` exits 0 (purity invariant preserved).
    - `uv run mypy --config-file pyproject.toml src/screener/indicators/trend.py src/screener/indicators/volatility.py src/screener/indicators/volume.py src/screener/indicators/relative_strength.py` exits 0 (mypy strict on indicators/).
    - `uv run ruff check src/screener/indicators/` exits 0.
    - The import smoke test in `<automated>` exits 0 with `OK`.
  </acceptance_criteria>
  <done>4 pure-function indicator modules created; all _safe_* wrappers handle None-on-short; per-ticker groupby applied throughout; rs_rating is Int64Dtype; trend.py contains zero `ema` references; architecture test, mypy, ruff all clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire build_panel orchestrator + create 6 unit test files + extend conftest with synthetic panel fixtures</name>
  <files>src/screener/indicators/__init__.py, tests/test_indicators_panel.py, tests/test_indicators_trend.py, tests/test_indicators_volatility.py, tests/test_indicators_volume.py, tests/test_indicators_rs.py, tests/test_indicators_purity.py, tests/conftest.py</files>
  <read_first>
    - /Users/belwinjulian/Desktop/SwingTrading/src/screener/indicators/__init__.py (current 7-line docstring — keep verbatim; ONLY append imports + build_panel function)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-RESEARCH.md (Example 1 lines 562-591 — build_panel orchestrator body; Validation Architecture lines 887-918 — required test functions)
    - /Users/belwinjulian/Desktop/SwingTrading/.planning/phases/03-indicator-panel-regime/03-PATTERNS.md (lines 326-366 — indicators/__init__.py orchestration; lines 886-995 — test_indicators_panel.py + test_indicators_purity.py analogs; lines 1141-1182 — conftest.py extension)
    - /Users/belwinjulian/Desktop/SwingTrading/tests/test_persistence.py (lines 23-38 — _make_panel helper template; lines 161-192 — monkeypatch _ohlcv_dir round-trip pattern)
    - /Users/belwinjulian/Desktop/SwingTrading/tests/conftest.py (Phase 3 section header from Plan 03-01 — append fixtures here)
  </read_first>
  <behavior>
    - Test: `from screener.indicators import build_panel` — importable.
    - Test: `build_panel("2026-04-30")` (with monkeypatched persistence dirs and a synthetic 252-bar 5-ticker panel) returns a DataFrame with all 5 original columns plus 10 new columns: sma_10/20/50/150/200, atr_14, adr_pct, obv, dryup_ratio, rs_raw, rs_rating.
    - Test: `build_panel(...)` preserves the (ticker, date) MultiIndex (no reindex, no level loss).
    - Test: A ticker with only 50 bars has valid sma_10/sma_20/sma_50, NaN sma_150/sma_200, NaN rs_rating (D-08 + Pitfall 3).
    - Test: `_safe_sma(pd.Series([1.0, 2.0, 3.0]), length=200)` returns a `pd.Series` (NOT None), all NaN, length 3.
    - Test: `adr_pct_panel` for high=105/low=95 returns 10.526 (rounded) for warmup-complete bars.
    - Test: `rs_panel` rs_rating values for full-history tickers are integers in [1, 99]; for short-history tickers, rs_rating is NaN.
    - Test: per-ticker shift isolation — given a panel with two tickers AAA (252 bars all close=100) and BBB (252 bars all close=200), AAA's rs_raw at the last date does NOT depend on BBB's history (computed via groupby(level='ticker').shift, never naked .shift).
    - Test: `test_indicators_purity` — calling `build_panel` twice with the same input returns identical output (no global state); input panel is not mutated.
    - Test: tests/test_architecture.py::test_indicators_signals_pure_no_io_imports still passes after the new modules exist.
  </behavior>
  <action>
**Step A — Modify `src/screener/indicators/__init__.py`** to add the `build_panel` orchestrator. KEEP the existing docstring verbatim (it contains "EMAs" in a comment — outside the IND-02 grep gate scope per RESEARCH Pitfall 6).

The current file is:
```python
"""indicators — pure-function indicator panel; no I/O, no global state.

Functions take pandas DataFrames in, return DataFrames with identical index.
SMAs (NOT EMAs in the Trend Template — see CLAUDE.md §13.6 pitfall #4),
ATR(14), ADR%(20), OBV, RS percentile (universe-relative). May import only
`persistence` and `config` from inside the package.
"""
```

Replace its body with (preserving the docstring verbatim):

```python
"""indicators — pure-function indicator panel; no I/O, no global state.

Functions take pandas DataFrames in, return DataFrames with identical index.
SMAs (NOT EMAs in the Trend Template — see CLAUDE.md §13.6 pitfall #4),
ATR(14), ADR%(20), OBV, RS percentile (universe-relative). May import only
`persistence` and `config` from inside the package.
"""

from __future__ import annotations

import pandas as pd

from screener.indicators.relative_strength import rs_panel
from screener.indicators.trend import sma_panel
from screener.indicators.volatility import adr_pct_panel, atr_panel
from screener.indicators.volume import dryup_ratio_panel, obv_panel
from screener.persistence import read_panel

__all__ = ["build_panel"]


def build_panel(snapshot_date: str | pd.Timestamp) -> pd.DataFrame:
    """Returns the OHLCV panel + 10 indicator columns. Pure function — reads
    from persistence.read_panel(); emits no I/O.

    Columns added (in order):
        sma_10, sma_20, sma_50, sma_150, sma_200, atr_14, adr_pct, obv,
        dryup_ratio, rs_raw, rs_rating
    """
    panel = read_panel(snapshot_date)  # MultiIndex (ticker, date), validated lazily
    panel = sma_panel(panel, lengths=(10, 20, 50, 150, 200))
    panel = atr_panel(panel, length=14)
    panel = adr_pct_panel(panel, length=20)
    panel = obv_panel(panel)
    panel = dryup_ratio_panel(panel, length=50)
    panel = rs_panel(panel)
    return panel
```

NOTE: rs_panel adds 2 columns (rs_raw + rs_rating); other functions add 1 each except sma_panel (5). Total = 5+1+1+1+1+2 = 11 — but IND-01 lists 10 distinct indicator categories. The ten "categories" are: SMA(10), SMA(20), SMA(50), SMA(150), SMA(200), ATR(14), ADR%(20), OBV, dryup_ratio, RS_rating. rs_raw is the auxiliary input to rs_rating — count it as an internal computation column. The test below counts 11 NEW columns total but verifies all 10 IND-01 categories are present.

**Step B — Append synthetic-panel fixtures to `tests/conftest.py`** (under the `# --- Phase 3 indicator + regime fixtures ---` header from Plan 03-01):

```python
@pytest.fixture(scope="session")
def synthetic_short_history_panel() -> pd.DataFrame:
    """50-bar single-ticker panel — exercises SMA200 NaN warmup path (D-08).
    Ticker = SHORT; close starts at 100, drifts up by 0.1/day."""
    n = 50
    idx = pd.MultiIndex.from_product(
        [["SHORT"], pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)],
        names=["ticker", "date"],
    )
    close = np.linspace(100.0, 100.0 + 0.1 * (n - 1), n)
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 1_000_000, dtype="int64"),
        },
        index=idx,
    )


@pytest.fixture(scope="session")
def synthetic_multi_ticker_panel() -> pd.DataFrame:
    """5 tickers × 260 business days (>252d so RS rating is defined for all).
    Tickers: AAA, BBB, CCC, DDD, EEE — distinct returns trajectories."""
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    n = 260
    dates = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)
    frames = []
    for i, t in enumerate(tickers):
        # Each ticker has a different drift — produces distinguishable RS values.
        drift = 0.001 * (i + 1)
        close = 100.0 * np.cumprod(1.0 + np.full(n, drift))
        idx = pd.MultiIndex.from_product([[t], dates], names=["ticker", "date"])
        frames.append(pd.DataFrame(
            {
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": np.full(n, 1_000_000, dtype="int64"),
            },
            index=idx,
        ))
    return pd.concat(frames).sort_index()
```

(Add `import numpy as np` to conftest.py if not already present; check existing imports.)

**Step C — Create `tests/test_indicators_panel.py`** (build_panel integration tests):

```python
"""build_panel integration tests (IND-01, D-07, D-08)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from screener.indicators import build_panel
from screener.persistence import write_ohlcv_atomic, write_universe_atomic


REQUIRED_NEW_COLS = {
    "sma_10", "sma_20", "sma_50", "sma_150", "sma_200",
    "atr_14", "adr_pct", "obv", "dryup_ratio", "rs_raw", "rs_rating",
}


def _setup_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("screener.persistence._ohlcv_dir", lambda: tmp_path / "ohlcv")
    monkeypatch.setattr("screener.persistence._universe_dir", lambda: tmp_path / "universe")


def test_build_panel_returns_10_new_cols(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_multi_ticker_panel: pd.DataFrame,
) -> None:
    _setup_persistence(tmp_path, monkeypatch)
    # Write per-ticker prices.parquet + universe snapshot, then build_panel.
    for ticker in synthetic_multi_ticker_panel.index.get_level_values("ticker").unique():
        ticker_df = synthetic_multi_ticker_panel.xs(ticker, level="ticker", drop_level=False)
        write_ohlcv_atomic(ticker, ticker_df.droplevel("ticker"))
    universe = pd.DataFrame({
        "ticker": ["AAA", "BBB", "CCC", "DDD", "EEE"],
        "name": ["A Co", "B Co", "C Co", "D Co", "E Co"],
        "sector": ["Tech"] * 5,
    })
    write_universe_atomic(universe, "2026-04-27")
    panel = build_panel("2026-04-27")
    new = set(panel.columns) - {"open", "high", "low", "close", "volume"}
    missing = REQUIRED_NEW_COLS - new
    assert not missing, f"build_panel missing IND-01 columns: {missing}"


def test_build_panel_preserves_multiindex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_multi_ticker_panel: pd.DataFrame,
) -> None:
    _setup_persistence(tmp_path, monkeypatch)
    for ticker in synthetic_multi_ticker_panel.index.get_level_values("ticker").unique():
        ticker_df = synthetic_multi_ticker_panel.xs(ticker, level="ticker", drop_level=False)
        write_ohlcv_atomic(ticker, ticker_df.droplevel("ticker"))
    universe = pd.DataFrame({
        "ticker": ["AAA", "BBB", "CCC", "DDD", "EEE"],
        "name": ["A"] * 5, "sector": ["X"] * 5,
    })
    write_universe_atomic(universe, "2026-04-27")
    panel = build_panel("2026-04-27")
    assert panel.index.names == ["ticker", "date"]


def test_short_history_nan_warmup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_short_history_panel: pd.DataFrame,
) -> None:
    """D-08: 50-bar ticker has valid sma_10..50 but NaN sma_150/200/rs_rating."""
    _setup_persistence(tmp_path, monkeypatch)
    short = synthetic_short_history_panel
    write_ohlcv_atomic("SHORT", short.droplevel("ticker"))
    universe = pd.DataFrame({"ticker": ["SHORT"], "name": ["s"], "sector": ["x"]})
    write_universe_atomic(universe, "2026-04-27")
    panel = build_panel("2026-04-27")
    last = panel.iloc[-1]
    assert pd.notna(last["sma_50"])
    assert pd.isna(last["sma_150"])
    assert pd.isna(last["sma_200"])
    assert pd.isna(last["rs_rating"]) or last["rs_rating"] is pd.NA
```

**Step D — Create `tests/test_indicators_trend.py`:**

```python
"""SMA + _safe_sma tests (IND-01, RESEARCH Pitfall 2)."""

from __future__ import annotations

import pandas as pd
import pytest

from screener.indicators.trend import _safe_sma, sma_panel


def test_safe_sma_short_series_returns_nan_series() -> None:
    """Pitfall 2: ta.sma returns None on input shorter than length; the wrapper
    must return a NaN-filled Series of the same index, never None."""
    short = pd.Series([1.0, 2.0, 3.0], name="close")
    result = _safe_sma(short, length=200)
    assert result is not None
    assert isinstance(result, pd.Series)
    assert len(result) == 3
    assert result.isna().all()


def test_sma_panel_adds_5_columns() -> None:
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=300)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [100.0] * 300,
            "high": [101.0] * 300,
            "low": [99.0] * 300,
            "close": [100.0] * 300,
            "volume": [1_000_000] * 300,
        },
        index=idx,
    )
    out = sma_panel(panel)
    for L in (10, 20, 50, 150, 200):
        assert f"sma_{L}" in out.columns
```

**Step E — Create `tests/test_indicators_volatility.py`:**

```python
"""ATR + ADR% tests (IND-01, IND-04)."""

from __future__ import annotations

import pandas as pd

from screener.indicators.volatility import adr_pct_panel, atr_panel


def test_adr_pct_canonical_value() -> None:
    """RESEARCH Pattern 3: ADR%(20) for high=105/low=95 = 100*(1.10526-1) ≈ 10.526."""
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=30)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [100.0] * 30, "high": [105.0] * 30, "low": [95.0] * 30,
            "close": [100.0] * 30, "volume": [1] * 30,
        },
        index=idx,
    )
    out = adr_pct_panel(panel, length=20)
    assert "adr_pct" in out.columns
    last_adr = out["adr_pct"].iloc[-1]
    assert abs(last_adr - 10.526) < 0.01, f"expected ~10.526; got {last_adr}"


def test_atr_panel_adds_atr_14() -> None:
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=30)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [100.0] * 30, "high": [101.0] * 30, "low": [99.0] * 30,
            "close": [100.0] * 30, "volume": [1] * 30,
        },
        index=idx,
    )
    out = atr_panel(panel, length=14)
    assert "atr_14" in out.columns
```

**Step F — Create `tests/test_indicators_volume.py`:**

```python
"""OBV + dryup_ratio tests (IND-01, D-09)."""

from __future__ import annotations

import pandas as pd

from screener.indicators.volume import dryup_ratio_panel, obv_panel


def test_obv_panel_adds_obv_col() -> None:
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=30)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [100.0] * 30, "high": [101.0] * 30, "low": [99.0] * 30,
            "close": [100.0] * 30, "volume": [1_000_000] * 30,
        },
        index=idx,
    )
    out = obv_panel(panel)
    assert "obv" in out.columns


def test_dryup_ratio_definition() -> None:
    """D-09: dryup_ratio = volume / SMA(volume, 50). For constant volume,
    dryup_ratio == 1.0 after the SMA has warmed up."""
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=100)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {
            "open": [100.0] * 100, "high": [101.0] * 100, "low": [99.0] * 100,
            "close": [100.0] * 100, "volume": [2_000_000] * 100,
        },
        index=idx,
    )
    out = dryup_ratio_panel(panel, length=50)
    assert "dryup_ratio" in out.columns
    # After warmup, ratio should equal 1.0 (constant volume / its own 50d SMA = 1.0)
    last = out["dryup_ratio"].iloc[-1]
    assert abs(last - 1.0) < 1e-6
```

**Step G — Create `tests/test_indicators_rs.py`:**

```python
"""RS panel tests (IND-03, RESEARCH Pitfalls 8, 9)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from screener.indicators.relative_strength import rs_panel


def _multi_ticker_panel(tickers: list[str], n: int = 260) -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp("2026-04-30"), periods=n)
    frames = []
    for i, t in enumerate(tickers):
        drift = 0.001 * (i + 1)
        close = 100.0 * np.cumprod(1.0 + np.full(n, drift))
        idx = pd.MultiIndex.from_product([[t], dates], names=["ticker", "date"])
        frames.append(pd.DataFrame(
            {
                "open": close, "high": close * 1.01, "low": close * 0.99,
                "close": close, "volume": np.full(n, 1_000_000, dtype="int64"),
            },
            index=idx,
        ))
    return pd.concat(frames).sort_index()


def test_rs_rating_in_range() -> None:
    panel = _multi_ticker_panel(["AAA", "BBB", "CCC", "DDD", "EEE"], n=260)
    out = rs_panel(panel)
    last_date = out.index.get_level_values("date").max()
    snapshot = out.xs(last_date, level="date")
    valid = snapshot["rs_rating"].dropna()
    assert (valid >= 1).all()
    assert (valid <= 99).all()
    # Pitfall 9: nullable Int64
    assert out["rs_rating"].dtype == pd.Int64Dtype()


def test_rs_nan_for_short_history() -> None:
    """A ticker with only 100 bars has NaN rs_raw (needs 252d) → NaN rs_rating."""
    panel = _multi_ticker_panel(["AAA", "BBB"], n=100)
    out = rs_panel(panel)
    assert out["rs_raw"].isna().all()
    assert out["rs_rating"].isna().all()


def test_rs_per_ticker_shift_isolation() -> None:
    """Pitfall 8: each ticker's shift is independent; verified by checking
    that the rs_raw at row N for ticker AAA only depends on AAA's prior bars,
    not on the trailing rows of any other ticker."""
    panel = _multi_ticker_panel(["AAA", "BBB"], n=260)
    # If naked .shift(63) were used, AAA's first 63 rows would mix with BBB's
    # last 63 rows. Compute via groupby and assert AAA's first 63 rs_raw rows
    # are all NaN (no prior history available within ticker AAA).
    out = rs_panel(panel)
    aaa = out.xs("AAA", level="ticker")
    assert aaa["rs_raw"].iloc[:63].isna().all(), \
        "first 63 rows of AAA must be NaN — shift bled across tickers"
```

**Step H — Create `tests/test_indicators_purity.py`:**

```python
"""Indicator purity invariant (IND-05).

Complements tests/test_architecture.py (forbidden-import AST check) with a
behavioral purity check: build_panel called twice on equivalent inputs returns
identical output, and never mutates its input panel.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from screener.indicators.relative_strength import rs_panel
from screener.indicators.trend import sma_panel


def test_rs_panel_does_not_mutate_input() -> None:
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=300)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {"open": [1.0] * 300, "high": [1.0] * 300, "low": [1.0] * 300,
         "close": [1.0] * 300, "volume": [1] * 300},
        index=idx,
    )
    cols_before = list(panel.columns)
    _ = rs_panel(panel)
    assert list(panel.columns) == cols_before, "rs_panel mutated input columns"


def test_sma_panel_idempotent() -> None:
    """Calling sma_panel twice on identical input returns identical output."""
    idx = pd.MultiIndex.from_product(
        [["AAA"], pd.bdate_range(end="2026-04-30", periods=300)],
        names=["ticker", "date"],
    )
    panel = pd.DataFrame(
        {"open": [1.0] * 300, "high": [1.0] * 300, "low": [1.0] * 300,
         "close": [100.0] * 300, "volume": [1] * 300},
        index=idx,
    )
    a = sma_panel(panel)
    b = sma_panel(panel)
    pd.testing.assert_frame_equal(a, b)
```
  </action>
  <verify>
    <automated>uv run pytest tests/test_indicators_panel.py tests/test_indicators_trend.py tests/test_indicators_volatility.py tests/test_indicators_volume.py tests/test_indicators_rs.py tests/test_indicators_purity.py tests/test_architecture.py -m "not slow and not integration" -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^def build_panel" src/screener/indicators/__init__.py` returns 1.
    - `grep -c "from screener.persistence import read_panel" src/screener/indicators/__init__.py` returns 1.
    - `grep -c "from screener.indicators.relative_strength import rs_panel" src/screener/indicators/__init__.py` returns 1.
    - `grep -c "from screener.indicators.trend import sma_panel" src/screener/indicators/__init__.py` returns 1.
    - All 6 test files exist: tests/test_indicators_{panel,trend,volatility,volume,rs,purity}.py.
    - `grep -c "synthetic_short_history_panel" tests/conftest.py` returns 1.
    - `grep -c "synthetic_multi_ticker_panel" tests/conftest.py` returns 1.
    - `uv run pytest tests/test_indicators_panel.py -x -q` exits 0.
    - `uv run pytest tests/test_indicators_trend.py -x -q` exits 0.
    - `uv run pytest tests/test_indicators_volatility.py -x -q` exits 0.
    - `uv run pytest tests/test_indicators_volume.py -x -q` exits 0.
    - `uv run pytest tests/test_indicators_rs.py -x -q` exits 0.
    - `uv run pytest tests/test_indicators_purity.py -x -q` exits 0.
    - `uv run pytest tests/test_architecture.py -x -q` exits 0 (no I/O imports leaked into indicators/).
    - `uv run mypy --config-file pyproject.toml src/screener/indicators/__init__.py` exits 0.
    - `uv run ruff check src/screener/indicators/__init__.py tests/test_indicators_*.py tests/conftest.py` exits 0.
  </acceptance_criteria>
  <done>build_panel orchestrator wired; 6 test files created; conftest.py extended with 2 synthetic-panel fixtures; all indicator + architecture tests green; mypy + ruff clean.</done>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_indicators_panel.py tests/test_indicators_trend.py tests/test_indicators_volatility.py tests/test_indicators_volume.py tests/test_indicators_rs.py tests/test_indicators_purity.py tests/test_architecture.py -x -q` exits 0
- `uv run mypy --config-file pyproject.toml src/screener/indicators/` exits 0
- `uv run ruff check src/screener/indicators/ tests/test_indicators_*.py tests/conftest.py` exits 0
- `grep -ic "ema" src/screener/indicators/trend.py` returns 0 (zero matches; IND-02 grep gate prep)
- `uv run python -c "from screener.indicators import build_panel; print('OK')"` exits 0
- All Phase 1 + 2 tests still green: `uv run pytest -m "not slow and not integration" -x -q` exits 0
</verification>

<success_criteria>
- `indicators/{trend,volatility,volume,relative_strength}.py` modules created with pure-function _safe_*-wrapped pandas-ta calls + per-ticker groupby idiom
- `indicators/__init__.py` exports `build_panel(snapshot_date)` that adds 11 columns (sma_10/20/50/150/200, atr_14, adr_pct, obv, dryup_ratio, rs_raw, rs_rating) — covers all 10 IND-01 indicator categories
- `trend.py` contains zero `ema` references (IND-02 prep — Plan 03-05 adds the CI gate)
- rs_rating uses `pd.Int64Dtype` for nullable integers (Pitfall 9); per-ticker shifts use `groupby(level='ticker').shift()` (Pitfall 8); cross-sectional rank uses `groupby(level='date').rank(pct=True)`
- Architecture invariant preserved: `tests/test_architecture.py::test_indicators_signals_pure_no_io_imports` still passes (no yfinance/requests/sqlite3/etc. imports in indicators/)
- 6 unit test files cover IND-01/03/04/05: build_panel integration, _safe_sma None defense, ADR% canonical value (10.526), RS range + per-ticker shift isolation, dryup_ratio definition, purity (idempotence + no input mutation)
- 2 new synthetic fixtures in conftest.py support indicator tests + downstream regime tests
- ruff + mypy clean; all Phase 1+2+3 tests green
</success_criteria>

<output>
After completion, create `.planning/phases/03-indicator-panel-regime/03-03-SUMMARY.md` documenting the indicator surface (column names, formula references, _safe_* wrapper pattern, Pitfalls 2/8/9 mitigations). Note any deviations.
</output>
