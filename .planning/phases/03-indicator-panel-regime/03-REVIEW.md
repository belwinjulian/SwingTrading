---
phase: 03-indicator-panel-regime
reviewed: 2026-05-10T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - .github/workflows/ci.yml
  - src/screener/regime.py
  - src/screener/config.py
  - src/screener/persistence.py
  - src/screener/indicators/__init__.py
  - src/screener/indicators/trend.py
  - src/screener/indicators/relative_strength.py
  - src/screener/indicators/volatility.py
  - src/screener/indicators/volume.py
  - src/screener/data/macro.py
  - src/screener/cli.py
  - tests/test_regime.py
  - tests/test_regime_score.py
  - tests/test_regime_golden.py
  - tests/test_ci_ema_grep_gate.py
  - tests/conftest.py
findings:
  critical: 3
  warning: 7
  info: 5
  total: 15
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-10T00:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 03 delivers the indicator panel, regime classifier, and supporting CI gate. The D-01
priority chain and D-02 distribution-day formula are correctly implemented; boundary math
for `_classify_state` is sound, and the Hypothesis-based regime score property test is
comprehensive. However, three blockers require attention before this code ships: a semantic
data-corruption bug in `_stooq_to_breadth`, a look-ahead bias baked into `build_history`
that will silently corrupt walk-forward backtests, and a zero-price division path in
`rs_panel` that produces silent `inf` values bypassing schema validation. Seven warnings
cover missing error guards, hardcoded magic numbers that diverge from settings, and a
test-coverage gap for the `build_history` public API.

---

## Critical Issues

### CR-01: `_stooq_to_breadth` produces semantically corrupt `advances`/`declines` columns

**File:** `src/screener/data/macro.py:395-405`

**Issue:** `_stooq_to_breadth` derives `advances` and `declines` by binary-flagging
whether `close.diff()` is positive or negative on a single price series (the NYAD cumulative
A-D line). This produces `advances ∈ {0, 1}` and `declines ∈ {0, 1}`, not actual counts of
advancing/declining NYSE stocks (which are typically in the hundreds to thousands on any
trading day). `NyadMacroSchema` only enforces `ge=0`, so corrupt values pass validation
silently. If Stooq service recovers and the Stooq code path becomes operative, every NYAD
row written after that point will contain wrong counts — poisoning any downstream consumer
that interprets the columns as stock counts.

**Fix:**
```python
def _stooq_to_breadth(stooq_df: pd.DataFrame) -> pd.DataFrame:
    """Stooq $NYAD 'close' is the cumulative A-D line value.
    daily_ad = close.diff() is the net (advances - declines) for each day,
    but individual advance/decline counts are NOT recoverable from the cumulative line.
    Raise here to force the fallback rather than silently storing garbage counts.
    """
    raise StaleOrEmptyError(
        "$NYAD Stooq data provides only the cumulative A-D line; "
        "individual advances/declines counts are not recoverable. "
        "Falling back to R1000 breadth proxy."
    )
```
Alternatively, if storing a synthetic NYAD shape is intentional, add a schema comment and
schema-level range check, and document that advances/declines are binary flags not counts.

---

### CR-02: `build_history` has baked-in look-ahead bias for `breadth_pct`

**File:** `src/screener/regime.py:218-227`

**Issue:** `build_history` calls `build_panel(str(end))` — the single universe snapshot at
the *end* of the requested window — and derives `breadth_pct` for all historical dates from
this future-dated snapshot. Any ticker added to the Russell 1000 between `start` and `end`
is included in breadth counts for dates prior to its entry, inflating or deflating historical
breadth numbers. The module docstring acknowledges this ("Backtests should call
`compute_for_date` per-date for point-in-time accuracy") but `build_history` is explicitly
documented as the "Phase 5 backtest harness" entry point, meaning look-ahead-biased regime
states will be fed directly to walk-forward backtest evaluation.

**Fix:** Either remove `build_history` until a proper point-in-time panel is available, or
add a runtime guard that raises when the date range exceeds a safe threshold where universe
churn is material:

```python
def build_history(start: str | pd.Timestamp, end: str | pd.Timestamp) -> pd.DataFrame:
    """..."""
    # Refuse long historical ranges because breadth_pct uses a single end-date
    # snapshot, introducing look-ahead bias for universe additions.
    span_days = (pd.Timestamp(end) - pd.Timestamp(start)).days
    if span_days > 90:
        raise NotImplementedError(
            "build_history uses a single panel snapshot for breadth_pct — "
            "look-ahead bias over spans > 90d is unacceptable for backtests. "
            "Call compute_for_date per date for point-in-time accuracy."
        )
    ...
```

---

### CR-03: Zero-price division in `rs_panel` produces silent `inf` values

**File:** `src/screener/indicators/relative_strength.py:33-38`

**Issue:** The RS formula divides `panel["close"]` by lagged closes (`c_63`, `c_126`, etc.).
`OhlcvPanelSchema` constrains `close: ge=0.0` — allowing `close == 0`. If a lagged close is
zero (e.g., data error or delisted-at-zero artifact), the division produces `inf`, not `NaN`.
`inf` propagates through `rank(pct=True)` (pandas excludes `NaN` but not `inf` from ranking)
and through `.clip(1, 99)` unchecked — `inf > 99` clips to `99`, assigning the maximum RS
rating to a broken data point. Neither `OhlcvPanelSchema` nor `RsSnapshotSchema` has an
upper-bound check that would catch this.

**Fix:** Add a non-zero guard on the schema, or guard in `rs_panel`:

```python
# In rs_panel, replace zeros with NaN before computing ratios:
close = panel["close"].replace(0.0, float("nan"))
c_63  = panel.groupby(level="ticker")["close"].shift(63).replace(0.0, float("nan"))
# ... same for c_126, c_189, c_252
rs_raw = 2.0 * (close / c_63) + (close / c_126) + (close / c_189) + (close / c_252)
```

Or tighten the schema:
```python
# In OhlcvPanelSchema:
close: Series[float] = pa.Field(gt=0.0, nullable=False)  # changed ge -> gt
```

---

## Warnings

### WR-01: `compute_for_date` crashes with `KeyError` when macro cache is empty or date is missing

**File:** `src/screener/regime.py:129-154`

**Issue:** `read_macro_spy()` and `read_macro_vix()` return empty DataFrames when the
Parquet cache does not exist. `compute_for_date` then attempts `spy.loc[date, "close"]` and
`vix.loc[date, "close"]` on empty DataFrames, raising `KeyError` with no informative message.
The same crash occurs when `date` is a holiday or weekend not present in the SPY/VIX index.

**Fix:**
```python
if spy.empty:
    raise RuntimeError(
        "SPY macro cache is empty — run `screener refresh-macro` first."
    )
if date not in spy.index:
    raise KeyError(
        f"Date {date} not found in SPY index. "
        "Ensure the date is a valid trading day and the macro cache is current."
    )
```

---

### WR-02: `_regime_score` VIX normalization uses hardcoded constants that diverge from `Settings`

**File:** `src/screener/regime.py:103-104`

**Issue:** The formula `(1.0 - (vix_level - 15.0) / 25.0)` uses two magic numbers (baseline
`15.0`, range `25.0`) that are not derived from `Settings.REGIME_VIX_CONFIRMED` (20.0) or
`Settings.REGIME_VIX_CORRECTION` (30.0). The VIX score reaches zero at VIX=40, not at the
correction threshold of VIX=30. This means the score does not track the classification
thresholds: at VIX=30 (correction boundary) the VIX component is still 0.4, not 0. If the
thresholds in `Settings` are ever tuned, the score weights will silently diverge further.

**Fix:** Derive the normalization from settings constants:
```python
# vix_norm goes from 1.0 at REGIME_VIX_CONFIRMED (or below) to 0.0 at REGIME_VIX_CORRECTION
def _regime_score(df: pd.DataFrame, settings: Any = None) -> pd.Series:
    if settings is None:
        settings = get_settings()
    vix_floor = settings.REGIME_VIX_CONFIRMED   # 20.0
    vix_ceil  = settings.REGIME_VIX_CORRECTION  # 30.0
    vix_norm  = (1.0 - (df["vix_level"] - vix_floor) / (vix_ceil - vix_floor)).clip(0.0, 1.0)
    dist_ceil = float(settings.REGIME_DIST_DAYS_CORRECTION)  # 9.0
    dist_norm = (1.0 - df["distribution_days"] / dist_ceil).clip(0.0, 1.0)
    ...
```

---

### WR-03: `read_splits` crashes with `FileNotFoundError` when the splits Parquet is absent

**File:** `src/screener/persistence.py:515-524`

**Issue:** `read_splits` calls `pd.read_parquet(path)` without first checking `path.exists()`.
All `read_macro_*` functions return an empty schema-shaped DataFrame for missing files, but
`read_splits` is inconsistent: if the splits Parquet was never written (ticker never had
`write_splits_atomic` called), the caller gets an unhandled `FileNotFoundError`. The docstring
implies empty-but-valid is returned for tickers with no corporate actions, but that contract
only holds if the zero-row file was previously written by `make_empty_splits()`.

**Fix:**
```python
def read_splits(ticker: str) -> pd.DataFrame:
    _assert_safe_ticker(ticker)
    path = _ohlcv_dir() / ticker / "splits.parquet"
    if not path.exists():
        return make_empty_splits()
    df = pd.read_parquet(path)
    return validate_at_read(SplitsSchema, df)
```

---

### WR-04: `dryup_ratio_panel` produces silent `inf` when volume SMA is zero

**File:** `src/screener/indicators/volume.py:51`

**Issue:** `out["dryup_ratio"] = panel["volume"] / sma_vol`. `OhlcvPanelSchema` allows
`volume >= 0`, so a ticker with zero volume across the entire 50-day window produces
`sma_vol = 0.0`, which causes `dryup_ratio = inf` (for any non-zero volume day following)
or `NaN` (for `0 / 0`). These silently pass through since there is no indicator schema
validation after the panel is built. `inf` values in `dryup_ratio` will silently corrupt
downstream signal comparisons.

**Fix:**
```python
out["dryup_ratio"] = (panel["volume"] / sma_vol).replace([float("inf"), float("-inf")], float("nan"))
```

---

### WR-05: `test_ema_grep_passes_when_clean` passes even if `trend.py` is missing or renamed

**File:** `tests/test_ci_ema_grep_gate.py:37-49`

**Issue:** The test asserts `proc.returncode != 0` after running grep on the TARGETS paths.
When a file in TARGETS does not exist, grep exits with code 2 (on Linux/macOS). Code 2 also
satisfies `!= 0`, so the test passes even if `trend.py` is deleted or moved. The test cannot
distinguish "file found but no EMA match" (rc=1, expected clean state) from "file not found"
(rc=2, broken gate). A rename of `trend.py` would pass this test while the CI gate silently
stopped guarding anything.

**Fix:**
```python
def test_ema_grep_passes_when_clean() -> None:
    for target in TARGETS:
        if target.exists():  # only assert on files that should exist
            assert target.exists(), f"Expected gate target {target} to exist"
    proc = subprocess.run(...)
    assert proc.returncode != 0, ...
```

More robustly, assert each present file was actually scanned:
```python
assert (REPO_ROOT / "src" / "screener" / "indicators" / "trend.py").exists(), \
    "trend.py must exist for the EMA grep gate to be meaningful"
```

---

### WR-06: `build_history` is entirely untested

**File:** `src/screener/regime.py:195-258`

**Issue:** `build_history` is the documented entry point for the Phase 5 backtest harness
and is a non-trivial function (inner join, vectorized classification, breadth derivation).
None of the three regime test files (`test_regime.py`, `test_regime_score.py`,
`test_regime_golden.py`) test `build_history`. The function contains the look-ahead bias
noted in CR-02 and the silent inner-join date-dropping noted in WR-07 — both of which would
only be caught by tests.

**Fix:** Add at minimum a smoke test verifying column presence, index continuity, and that
all returned `regime_state` values are valid `RegimeState` literals.

---

### WR-07: `build_history` inner join silently drops trading dates absent from the panel

**File:** `src/screener/regime.py:229-233`

**Issue:** `pd.concat([spy_above, breadth_series, dist_days, vix_close], axis=1, join="inner")`
drops any date present in SPY/VIX but absent from `breadth_series`. SPY and VIX are fetched
from yfinance and may include dates where the universe panel has no breadth data (e.g., the
first 252 days of the panel before any ticker has SMA200 computed, or when the panel was
built with an older universe snapshot that has no OHLCV for some dates). The resulting
DataFrame is silently shorter than the requested `[start, end]` range with no warning.

**Fix:**
```python
df = pd.concat([spy_above, breadth_series, dist_days, vix_close], axis=1, join="outer")
df["breadth_pct"] = df["breadth_pct"].fillna(0.0)  # treat missing breadth as 0 (conservative)
df = df.dropna(subset=["spy_above_200d", "vix_level"])  # require macro data to exist
```

---

## Info

### IN-01: Wrong CLAUDE.md pitfall number cited in `ci.yml` EMA gate comment

**File:** `.github/workflows/ci.yml:45`

**Issue:** The comment says `"See IND-02 / CLAUDE.md §13.6 pitfall #4"`. Pitfall #4 in
CLAUDE.md is "Free EOD + intraday entries." The EMA substitution risk is Pitfall #1:
"EMA substitution for SMA in the Trend Template." A developer following the link to debug
or understand the gate would land on the wrong pitfall.

**Fix:** Change to `"See IND-02 / CLAUDE.md Critical Pitfall #1 (EMA substitution for SMA)."`

---

### IN-02: `GICS_SECTORS` uses `"Communication"` instead of `"Communication Services"`

**File:** `src/screener/persistence.py:67`

**Issue:** The standard GICS sector name (post-2018 reclassification) is
`"Communication Services"`, not `"Communication"`. The iShares IWB CSV feed uses the full
`"Communication Services"` name. The current allowlist will reject real iShares rows with
sector `"Communication Services"` and accept rows with the truncated `"Communication"`, which
is the sector name used only in the project's synthetic test fixtures. If real IWB data is
loaded, `UniverseSchema` validation will fail for every Communication Services ticker in the
universe (roughly 7-9% of Russell 1000 as of 2026).

**Fix:**
```python
GICS_SECTORS: frozenset[str] = frozenset({
    ...
    "Communication Services",  # was "Communication"
    ...
})
```
Update `conftest.py` `_make_ishares_csv_bytes` sectors list to match.

---

### IN-03: Late `from screener import persistence` imports inside `refresh_*` are redundant

**File:** `src/screener/data/macro.py:152-153, 160-161, 192-194, 224-227, 261-263, 314-315`

**Issue:** Each `refresh_*` function and `_macro_dir_for_log` performs a late
`from screener import persistence` import. The module already imports
`StaleOrEmptyError, read_panel, write_macro_atomic` from `screener.persistence` at the top
level (line 44). The late imports are necessary only for `read_macro_spy`,
`read_macro_qqq`, etc., which are not in the top-level import list. The pattern is confusing
because it looks like a circular-import workaround but the actual issue is an incomplete
top-level import.

**Fix:** Add `read_macro_spy, read_macro_qqq, read_macro_vix, read_macro_yields,
read_macro_nyad` to the module-level `from screener.persistence import (...)` block and
remove all late imports.

---

### IN-04: `_macro_dir_for_log` calls a private function (`persistence._macro_dir`) across module boundaries

**File:** `src/screener/data/macro.py:150-153`

**Issue:** `_macro_dir_for_log` imports `persistence` and calls `persistence._macro_dir()` —
a private function (underscore-prefixed) of another module. This creates a hidden coupling
that will silently break if `persistence._macro_dir` is renamed or refactored.

**Fix:** Add a public `macro_dir() -> Path` accessor to `persistence.py` or simply inline
the path construction using `get_settings().MACRO_CACHE_DIR` directly in the return
statement:
```python
def _macro_dir_for_log() -> Path:
    return Path(get_settings().MACRO_CACHE_DIR)
```

---

### IN-05: `build_history` and `_compute_breadth_fallback` share the same look-ahead bias but the fallback has no comment

**File:** `src/screener/data/macro.py:408-433`

**Issue:** `_compute_breadth_fallback` reads the latest universe snapshot and uses
`read_panel(snapshot_date)` to derive the R1000 breadth for a historical window. Tickers
added to the Russell 1000 after `start` contribute to advance/decline counts for dates before
their addition. Unlike `build_history` (which has an explicit acknowledgment comment),
`_compute_breadth_fallback` has no comment warning about this pitfall. It is consumed by
`refresh_nyad` which writes the NYAD Parquet — persisting the look-ahead bias to disk.

**Fix:** Add a warning comment and `log.warning` event when computing over spans > 90 days,
similar to the recommendation in CR-02.

---

_Reviewed: 2026-05-10T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
