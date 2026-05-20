---
phase: 04-trend-template-composite-skeleton-first-report
reviewed: 2026-05-11T01:02:51Z
depth: standard
iteration: 2
files_reviewed: 26
files_reviewed_list:
  - .github/workflows/ci.yml
  - .gitignore
  - docs/strategy_v1_preregistration.md
  - scripts/check_preregistration.py
  - src/screener/cli.py
  - src/screener/config.py
  - src/screener/indicators/__init__.py
  - src/screener/indicators/trend.py
  - src/screener/persistence.py
  - src/screener/publishers/pipeline.py
  - src/screener/publishers/report.py
  - src/screener/publishers/snapshot.py
  - src/screener/signals/__init__.py
  - src/screener/signals/composite.py
  - src/screener/signals/minervini.py
  - tests/conftest.py
  - tests/test_cli_smoke.py
  - tests/test_indicators_panel.py
  - tests/test_persistence.py
  - tests/test_preregistration_check.py
  - tests/test_publishers_pipeline.py
  - tests/test_publishers_report.py
  - tests/test_publishers_snapshot.py
  - tests/test_rs_snapshot.py
  - tests/test_signals_composite.py
  - tests/test_signals_minervini.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 4: Code Review Report (Iteration 2)

**Reviewed:** 2026-05-11T01:02:51Z
**Depth:** standard
**Files Reviewed:** 26
**Status:** issues_found

## Summary

Iteration 1 applied 12 of 14 findings; the 2 skips (CR-04 Communication sector, WR-02 first sma_panel closure) were independently verified and remain sound: the live `data/universe/2026-04-27.parquet` snapshot's `df['sector'].unique()` contains literal `'Communication'` (not `'Communication Services'`), so changing the allowlist would break the production pipeline; the SMA closure pattern is correct as the original reviewer self-downgraded.

The applied fixes themselves are largely correct and verified end-to-end:
- The `validate_run` flattening (CR-01) is now genuinely two-tier with `WARN=0.15` / `HARD_FAIL=0.25` defaults and the test suite covers both independent paths.
- The `RankingSnapshotSchema.composite_score` bound is tightened to `[0, 100]` (CR-03); existing test data (max 50.0) still passes.
- The `_classify_pivot_zone` sign convention is flipped (CR-05); `test_pivot_zone_labels` now exercises laggard and breakout paths.
- `read_panel` now hard-fails on `< 95%` coverage (WR-02-second); all three call-sites in tests write 100% so no regression.
- `synthetic_scored_panel` is now driven by `_add_publisher_columns` (WR-06).
- `check_preregistration.py` is uniformly int-returning (IN-02); typed `PreregistrationDocError` is a clean abstraction.

No new bugs of behavioral severity were introduced — there are 0 BLOCKER findings. Three remaining quality issues warrant attention:
1. **WR-05's `test_condition_7_isolated_fail`** claims to stress condition 7 in isolation but pins `sma_200[-1]` to a value far below `sma_200[-23]`, which also fails condition 3 (`SMA200 > SMA200[t-22]`). The assertion `score < 8` is satisfied by ANY failing condition, not specifically cond 7 — the test does not achieve the isolation its docstring advertises.
2. **CR-02's bidirectional preregistration check** has a hidden blind spot: `extra_in_doc` can only detect doc keys that already pass through `NAME_TO_KEY`; a doc row with an unknown friendly name is silently dropped during parsing and never reaches the bidirectional gate.
3. **WR-04's `_write_text_atomic` restructure** creates an empty temp file via `NamedTemporaryFile(delete=False)`, closes it, then re-opens it for the actual write. The pattern is functionally correct but introduces a narrow window where an empty `.tmp` exists on disk before being filled; if the fix's stated goal was to eliminate orphan `.tmp` files on every failure path, the empty-file-then-reopen pattern reintroduces a (smaller) orphan window.

---

## Warnings

### WR-01: `test_condition_7_isolated_fail` does not isolate condition 7 — also fails condition 3 by construction

**File:** `tests/test_signals_minervini.py:144-193`

**Issue:** The fix added to address review WR-05 sets up a uniform 1.002^n monotonic uptrend, then performs three pin operations at the last bar:
```python
close.iloc[-1] = float(high_52w.iloc[-1]) * 0.70    # forces cond 7 to fail
sma_50.iloc[-1]  = forced_sma          # ≈ 0.9 * close[-1]
sma_150.iloc[-1] = forced_sma * 0.95
sma_200.iloc[-1] = forced_sma * 0.90   # ≈ 0.81 * close[-1] ≈ 0.57 * pre-drop close
```

Before the pin, `sma_200` was a rising rolling mean of a 1.002^n series. `sma_200.iloc[-23]` is roughly `0.93 * close[-1-22]` ≈ near the un-dropped `close[-1]` level (~`(1/1.002)^22 * close[-1]_pre_drop`), which is much higher than the pinned `sma_200.iloc[-1] = 0.57 * close[-1]_pre_drop`. The result is that condition 3 (`SMA200 > SMA200[t-22]`) ALSO fails because the pinned sma_200 is now far below its 22-bar-prior value.

The test docstring says: "REVIEW WR-05: stress condition 7 (Close >= 0.75 * MAX(High, 252)) in isolation. ... constructs a panel where ALL other conditions pass but close is BELOW 0.75 * high_52w, and assert the score drops below 8 (i.e., condition 7 is the failing one)." The actual assertion `last["trend_template_score"] < 8` is satisfied by both cond 3 and cond 7 failing simultaneously. The test does not demonstrate that condition 7 is specifically the failing condition — it merely demonstrates that the score is sub-8 when at least one condition fails.

This is a quality regression versus the fix's stated goal. The original WR-05 said: "The downtrend panel partially covers this but does not isolate condition 7 from the other failing conditions." The new test has the same defect: multiple conditions co-fail.

**Fix:** Either (a) add a second assertion that explicitly checks `trend_template_score == 7` (proves exactly one condition failed) AND verify which one — but the current minervini.py output does not surface per-condition booleans, so this requires either exposing them or computing them inline; or (b) restructure the pin operations so only cond 7 fails. Option (b) requires keeping `sma_200.iloc[-1]` strictly greater than `sma_200.iloc[-1-22]` while still below the pre-pin close, which is geometrically constrained but possible:
```python
# Make sma_200 still RISING at t-22 -> t so cond 3 passes.
pre_pin_sma_200_at_minus_23 = sma_200.iloc[-23]
sma_200.iloc[-1] = pre_pin_sma_200_at_minus_23 + 1e-3  # barely rising
# Then pin sma_50 / sma_150 below close[-1] so conds 1/4/5 pass.
```
A cleaner alternative: build a 300-bar uptrend, then on the last bar set `close` low enough to fail cond 7 (close < 0.75 * high_52w) but leave SMAs untouched (so all SMA-based conds reflect the gentle uptrend); then assert `score == 7` (proves exactly one cond failed) plus check `trend_template_score == 7`.

---

### WR-02: Bidirectional preregistration check (CR-02 fix) has a blind spot — doc rows outside `NAME_TO_KEY` never reach the gate

**File:** `scripts/check_preregistration.py:109-113`

**Issue:** The fix added:
```python
extra_in_doc = set(doc_weights) - set(DEFAULT_WEIGHTS)
if extra_in_doc:
    diffs.append(f"doc has extra keys not in composite.py: {sorted(extra_in_doc)}")
```

However, `doc_weights` is constructed inside `parse_doc_weights()` by iterating `NAME_TO_KEY.items()` — meaning `doc_weights.keys()` is structurally bounded by the `NAME_TO_KEY` value set. The original review CR-02 was concerned that "a new key is added to the doc table without adding it to `DEFAULT_WEIGHTS`" would be silently ignored. The implemented fix only catches this case if the new doc row's friendly name happens to be in `NAME_TO_KEY` and the corresponding internal key is missing from `DEFAULT_WEIGHTS` — a narrow slice of the original concern. A doc row whose friendly name is NOT in `NAME_TO_KEY` is silently dropped during parsing; `parse_doc_weights` does not iterate the doc to find rows it does not recognize.

This was not a regression from iter 1 — the original review CR-02 specified the exact fix that was applied — but the gate name "bidirectional" overstates the protection it provides. A truly bidirectional check would:
```python
# After parse_doc_weights(), scan the raw doc text for any "| <foo> ... | <pct>% | <pct>% |"
# rows whose <foo> is not in NAME_TO_KEY, and report them as unknown rows.
```

**Fix:** Either (a) downgrade the inline comment to clarify the scope of the check ("partial bidirectional — detects keys in `NAME_TO_KEY` not in `DEFAULT_WEIGHTS`, not doc rows outside `NAME_TO_KEY`"), or (b) add a pass that scans the doc table for unrecognized rows. Option (a) is the lower-risk patch for v1.

---

### WR-03: `_write_text_atomic` creates and re-opens the temp file — narrow empty-`.tmp` orphan window

**File:** `src/screener/publishers/report.py:138-155`

**Issue:** The WR-04 fix changed the structure to:
```python
with tempfile.NamedTemporaryFile(
    dir=target.parent, prefix=..., suffix=".tmp",
    delete=False, mode="w", encoding="utf-8",
) as tmp:
    tmp_path = Path(tmp.name)
# tmp is now CLOSED and EMPTY (no write happened inside the with-block).
try:
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, target)
except Exception:
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)
    raise
```

The fix correctly wraps both the write AND `os.replace` in a single `try/except`, so a disk-full failure during the `f.write(content)` call is now caught and the empty `.tmp` is cleaned up. This is an improvement.

However, the new structure introduces a narrow window between the outer `with` block exit (which closes the empty tempfile but does NOT delete it because `delete=False`) and the inner `with open(tmp_path, "w") ...` call. If the process receives `SIGKILL` precisely in this window — e.g., during `Path(tmp.name)` or any intermediate Python bytecode — an empty `.tmp` file is orphaned. The pre-fix code had the same vulnerability (the original was a single `tmp.write(content)` followed by an external `os.replace`); the fix narrows the failure window but does not eliminate it.

The simpler, more idiomatic pattern is to do the write inside the original `with` block and rely on `try/finally` for cleanup:
```python
try:
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=..., suffix=".tmp",
        delete=False, mode="w", encoding="utf-8",
    ) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(content)
    os.replace(tmp_path, target)
except Exception:
    if 'tmp_path' in locals() and tmp_path.exists():
        tmp_path.unlink(missing_ok=True)
    raise
```
This eliminates the empty-`.tmp` window and matches the pattern in `persistence._write_parquet_atomic` line 282-295 (which keeps the write inside the same `try` block as the `os.replace`).

**Fix:** Restructure as above to consolidate write + replace under a single `with` + `try/except`, eliminating the empty-tempfile orphan window. The existing `test_report_atomic_write_crash_no_residue` test continues to pass under either pattern.

---

## Info

### IN-01: `read_panel` low-coverage gate uses `lru_cache`'d `get_settings()` — settings staleness hazard in tests

**File:** `src/screener/persistence.py:633`

**Issue:** The WR-02-second fix added `threshold = get_settings().UNIVERSE_HEALTH_THRESHOLD`. `get_settings` is decorated with `@lru_cache(maxsize=1)` in `config.py:73-74`. If any test monkeypatches the `UNIVERSE_HEALTH_THRESHOLD` env var without calling `get_settings.cache_clear()`, the gate sees the stale cached value. Existing tests do not exercise this path (they write 100% of the universe), so there is no current regression — but Phase 5 tests that vary universe coverage will need to be aware of the lru_cache pattern. The persistence module already uses `getattr(get_settings(), ...)` elsewhere with the same hazard, so this is not introduced by the fix; it's a propagation of an existing pattern.

**Fix:** No code change required. Add a note in the persistence docstring documenting the `lru_cache` constraint for future test authors, or consolidate to a single `_settings_for_read_panel()` accessor that calls `get_settings.cache_clear()` first if a test marker indicates fresh-settings mode. Lowest-cost option: document in the test author's reference.

---

### IN-02: `read_panel` raises `RuntimeError` directly — inconsistent with `StaleOrEmptyError` and `typer.Exit` patterns elsewhere

**File:** `src/screener/persistence.py:642-645`

**Issue:** The new gate raises a bare `RuntimeError("read_panel: only X/Y tickers loaded — re-run refresh-ohlcv to fix coverage")`. The persistence module defines `StaleOrEmptyError(RuntimeError)` (line 46) as the standard fail-loud exception for data-quality issues at the data/ boundary, and the CLI layer uses `typer.Exit(code=1)` for health-gate failures (cli.py:135-144). The new `RuntimeError` is technically caught by the broad `except Exception` in `cli.score` (line 210-214) and `cli.report` (line 227-229), which logs `error_type=type(e).__name__` and re-raises via `typer.Exit(code=1)` — so the behavior is correct (process exits non-zero with a structured log), but the log will say `error_type=RuntimeError`, not `error_type=StaleOrEmptyError`, breaking the log-grep convention.

**Fix:** Either (a) raise `StaleOrEmptyError(...)` instead of `RuntimeError(...)` to match the existing data-quality fail-loud convention, or (b) leave as-is and document that `read_panel` is a different class of failure (read-time coverage check, not write-time staleness). Option (a) is one-line and improves log consistency:
```python
raise StaleOrEmptyError(
    f"read_panel: only {n_loaded}/{n_universe} tickers loaded — "
    "re-run refresh-ohlcv to fix coverage"
)
```

---

_Reviewed: 2026-05-11T01:02:51Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Iteration: 2_
