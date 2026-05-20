---
phase: 04-trend-template-composite-skeleton-first-report
reviewed: 2026-05-10T20:35:00Z
depth: standard
iteration: 3
files_reviewed: 25
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
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 4: Code Review Report (Iteration 3)

**Reviewed:** 2026-05-10T20:35:00Z
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Iteration 3 verification of the 5 fixes applied in iteration 2 (WR-01, WR-02, WR-03, IN-01, IN-02). All five fixes are intact and behaviourally correct:

- **WR-01 (`test_condition_7_isolated_fail`)** — Verified the new isolation construction holds. The spike at `close.iloc[60] = 400.0` is INSIDE the 252-bar `high_52w` window at the last bar (window [48, 299]) but OUTSIDE every SMA footprint that touches the final bar: `SMA_50` uses [250, 299]; `SMA_150` uses [150, 299]; `SMA_200` uses [100, 299]; cond 3's `SMA_200.shift(22)` uses [78, 277]. `low_52w[-1]` uses [48, 299] which DOES include index 60, but the spike is upward so the rolling-min is unaffected (`low_52w[-1] = close[48] ≈ 110`). All conds 1–6 and 8 reflect the unperturbed uptrend; only cond 7 fails because `0.75 * high_52w[-1] = 300 > close[-1] ≈ 182`. The strong-form assertion `score == 7` is met (verified by `pytest tests/test_signals_minervini.py::test_condition_7_isolated_fail` — passes).
- **WR-02 (preregistration partial bidirectional)** — Comment downgrade applied with explicit SCOPE block documenting the unknown-friendly-name blind spot. Three preregistration tests pass.
- **WR-03 (`_write_text_atomic` consolidation)** — Restructured correctly: the write is now inside the same `with NamedTemporaryFile()` block as the `os.replace`, with a single outer `try/except`. `tmp_path: Path | None = None` is pre-declared so the except branch correctly distinguishes the never-created case. The `test_report_atomic_write_crash_no_residue` test continues to pass.
- **IN-01 (lru_cache caveat)** — Docstring block added to `read_panel` naming the staleness hazard. Documentation-only; no behaviour change.
- **IN-02 (`StaleOrEmptyError` consistency)** — `read_panel` low-coverage gate now raises `StaleOrEmptyError`, restoring log-grep consistency with `data/ohlcv.py` and `data/stooq.py`. CLI's broad `except Exception` continues to catch it; structured log now reports `error_type=StaleOrEmptyError`.

Cross-cutting health checks performed end-to-end on this iteration:
- `pytest -m "not slow" --no-cov` — 132 passed, 2 skipped (same as iter 2 — no regressions)
- `mypy` (strict math modules) — Success: no issues found in 11 source files
- `ruff check` on all 23 in-scope Python files — All checks passed
- SMA-not-EMA grep gate (IND-02 in `ci.yml`) — `minervini.py` and `indicators/trend.py` both clean

**No critical or warning issues found at standard depth.** Two info-level items document quality drift introduced by (or left unaddressed during) iteration 2; neither is a behaviour bug and neither blocks shipping.

---

## Info

### IN-01: `_write_text_atomic` docstring claim that the function "matches the parquet variant's pattern" is no longer accurate after the WR-03 fix

**File:** `src/screener/publishers/report.py:141`

**Issue:** The iter-2 WR-03 fix consolidated `tmp.write(content)` and `os.replace(tmp_path, target)` inside a single `try/except` block, with the write happening INSIDE the `with NamedTemporaryFile(...) as tmp:` block. The docstring at line 141 says: "The consolidated structure below matches the parquet variant's pattern." This is no longer correct. `persistence._write_parquet_atomic` at lines 282-295 still has the OLD structure:

```python
with tempfile.NamedTemporaryFile(
    dir=target.parent,
    prefix=f".{target.name}.",
    suffix=".tmp",
    delete=False,
) as tmp:
    tmp_path = Path(tmp.name)        # tempfile closed here (empty)
try:
    df.to_parquet(tmp_path, ...)     # write happens OUTSIDE the with-block
    os.replace(tmp_path, target)
except Exception:
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)
    raise
```

This is precisely the pattern the WR-03 review flagged as having a narrow "empty `.tmp` orphan window" — and the iter-2 fix only addressed it in the text variant. The two atomic-write helpers have now diverged: the text variant uses the consolidated `write-inside-with` pattern (no empty-tempfile window); the parquet variant uses the older split pattern (small empty-tempfile orphan window between `with` exit and `to_parquet` start). The docstring's claim is incorrect.

**Fix:** Either (a) update the docstring to acknowledge that the text variant is now MORE atomic than the parquet variant, with an explicit note that the parquet variant should be brought to the same standard in a follow-up; or (b) refactor `_write_parquet_atomic` to use the same consolidated pattern so the docstring's claim becomes true:

```python
def _write_parquet_atomic(df: pd.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            # to_parquet opens its own file handle, so calling it while the
            # NamedTemporaryFile fd is also open is safe on POSIX.
            ...
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
```

Option (a) is the lower-risk patch (documentation-only). Option (b) requires verifying that `to_parquet` can be called on a path whose file descriptor is currently open in the `NamedTemporaryFile` context (it can; pandas opens its own handle).

---

### IN-02: `test_publishers_pipeline.py` tests `validate_run` with identical warn_threshold and fail_threshold_with_correction (0.25/0.25) — never exercises the independent two-tier semantics that CR-01's flattening enabled

**File:** `tests/test_publishers_pipeline.py:37-92`

**Issue:** Iter-1's CR-01 fix flattened `validate_run` so the warn and hard-fail thresholds are independent control surfaces; iter-1's WR-01 fix then set distinct defaults (`WARN=0.15`, `HARD_FAIL=0.25`). However, every test call to `validate_run` in `test_publishers_pipeline.py` passes `warn_threshold=0.25, fail_threshold_with_correction=0.25`:

```python
def test_pass_rate_warns_d07() -> None:
    validate_run(pass_rate=0.30, regime_state="Confirmed Uptrend",
                warn_threshold=0.25, fail_threshold_with_correction=0.25)
# ... and 3 more tests with the same two-equal-values pattern.
```

The integration test in `test_cli_smoke.py:217` also uses `validate_run(0.30, "Correction", 0.25, 0.25)`. So no test in the suite exercises the case `warn_threshold < fail_threshold_with_correction` (the documented healthy configuration with distinct two-tier semantics). A regression that re-nests the inner `if` block (re-introducing CR-01's bug) would NOT be caught by the existing tests because both gates fire at identical thresholds in every test case.

The behaviour is functionally correct in production with the distinct defaults (`0.15` warn, `0.25` hard-fail), but the test suite does not verify it. A follow-up test like:

```python
def test_validate_run_distinct_thresholds_warn_only() -> None:
    """With warn=0.10 < fail=0.30, a pass_rate of 0.20 emits a warn but
    does NOT raise — regression test for CR-01's flattening."""
    # pass_rate (0.20) > warn (0.10) -> warning fires
    # pass_rate (0.20) <= fail (0.30) AND not in Correction -> no exit
    validate_run(0.20, "Confirmed Uptrend", warn_threshold=0.10,
                fail_threshold_with_correction=0.30)
    # In Correction with same numbers: still NO exit (under fail_threshold).
    validate_run(0.20, "Correction", warn_threshold=0.10,
                fail_threshold_with_correction=0.30)

def test_validate_run_distinct_thresholds_hard_fail_only() -> None:
    """With warn=0.30 > fail=0.20, pass_rate=0.25 in Correction must
    HARD-FAIL even though it is BELOW the warn threshold — proves the
    two checks are truly independent."""
    with pytest.raises(typer.Exit):
        validate_run(0.25, "Correction", warn_threshold=0.30,
                    fail_threshold_with_correction=0.20)
```

would lock the independent-control-surface semantic in place. Without it, CR-01's flattening is a behavioural change that the test suite cannot detect a regression of.

**Fix:** Add the two tests above (or similar) to `test_publishers_pipeline.py`. Lowest-effort patch; pure additive — does not modify existing tests.

---

_Reviewed: 2026-05-10T20:35:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Iteration: 3_
