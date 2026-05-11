---
phase: 04-trend-template-composite-skeleton-first-report
reviewed: 2026-05-10T00:00:00Z
depth: standard
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
  critical: 5
  warning: 6
  info: 3
  total: 14
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-05-10T00:00:00Z
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Summary

This phase delivers the Trend Template gate (`passes_trend_template`), the pre-registered composite scorer, the full daily pipeline (`run_pipeline`), the Markdown report writer, and the preregistration CI gate. The core signal math is correct: per-ticker groupby shifts for cond 3, NaN propagation through Int64 → bool coercion, and SMA-not-EMA discipline are all handled properly. The atomic-write plumbing is solid.

Five blockers require fixes before this code ships. Three involve logic errors with real behavioral consequences: (1) the data-quality gate's hard-fail condition is structurally unreachable for any `pass_rate <= fail_threshold` value due to threshold identity; (2) the preregistration check only iterates `DEFAULT_WEIGHTS` keys, so a doc weight key not in `DEFAULT_WEIGHTS` is silently ignored; (3) the `validate_run` hard-fail fires only when `pass_rate > warn_threshold` (outer if) AND `pass_rate > fail_threshold_with_correction` (inner if), but because both thresholds are identical and both comparisons are strict-greater-than, the gate and the warn fire identically — in Correction the exit fires correctly, but the outer gate means there is no independent control surface between "warn" and "hard fail" threshold levels. Two further blockers are schema correctness issues: `RankingSnapshotSchema.composite_score` allows up to 110.0 but the codebase documents 0–100, and the GICS sector allowlist spells "Communication" but the actual iShares feed uses "Communication Services."

---

## Critical Issues

### CR-01: `validate_run` D-08 hard-fail is nested inside the D-07 warn block — identical thresholds make the gates non-independent

**File:** `src/screener/publishers/pipeline.py:82-102`

**Issue:** The D-08 `typer.Exit` is reachable only when `pass_rate > warn_threshold` (the outer `if`). With `TREND_TEMPLATE_PASS_RATE_WARN == TREND_TEMPLATE_PASS_RATE_HARD_FAIL == 0.25` (both defaulting to 0.25 in `config.py:65-66`), the two strict-greater-than comparisons are identical. This is not a bug in the current default configuration — the exit does fire when `pass_rate > 0.25 AND regime_state == 'Correction'` — but it means the `fail_threshold_with_correction` parameter has no independent effect. Any future operator who sets `TREND_TEMPLATE_PASS_RATE_WARN = 0.20` and `TREND_TEMPLATE_PASS_RATE_HARD_FAIL = 0.30` expecting a stricter hard-fail threshold will silently get no hard-fail because `pass_rate > warn_threshold` (0.20) gates entry, but the inner check `pass_rate > fail_threshold_with_correction` (0.30) is never independently evaluated when `pass_rate` is between 0.20 and 0.30. The design intent (separate warn vs. hard-fail thresholds) is violated by the nesting.

**Fix:** Flatten the two checks so each operates independently:
```python
def validate_run(
    pass_rate: float,
    regime_state: str,
    warn_threshold: float,
    fail_threshold_with_correction: float,
) -> None:
    if pass_rate > warn_threshold:
        log.warning(
            "trend_template_pass_rate_high",
            pass_rate=pass_rate,
            expected_range="0.05-0.15",
            warn_threshold=warn_threshold,
        )
    # Independent check — does NOT require pass_rate > warn_threshold first.
    if (
        regime_state == "Correction"
        and pass_rate > fail_threshold_with_correction
    ):
        log.error(
            "data_quality_gate_failed",
            pass_rate=pass_rate,
            regime_state=regime_state,
            message=(
                f"Pass rate {pass_rate * 100:.1f}% in Correction regime — "
                f"data quality gate failed"
            ),
        )
        raise typer.Exit(code=1)
```

---

### CR-02: Preregistration check only iterates `DEFAULT_WEIGHTS` keys — doc-only extra keys are silently ignored

**File:** `scripts/check_preregistration.py:79-84`

**Issue:** The comparison loop is `for k, w in DEFAULT_WEIGHTS.items()`. If a doc weight row is renamed or a new key is added to the doc table without adding it to `DEFAULT_WEIGHTS`, the check passes without detecting the discrepancy. The check is unidirectional (code → doc) rather than bidirectional. In the inverse direction — doc has key X, code does not — the `doc_weights.get(k)` call never executes for that key, so the mismatch is invisible.

**Fix:** After the main loop, add a check for keys in `doc_weights` not present in `DEFAULT_WEIGHTS`:
```python
extra_in_doc = set(doc_weights) - set(DEFAULT_WEIGHTS)
if extra_in_doc:
    diffs.append(
        f"doc has extra keys not in composite.py: {sorted(extra_in_doc)}"
    )
```

---

### CR-03: `RankingSnapshotSchema.composite_score` allows up to 110.0 — inconsistent with documented 0–100 range

**File:** `src/screener/persistence.py:231`

**Issue:** `composite_score: Series[float] = pa.Field(ge=0.0, le=110.0, nullable=True)`. Every other piece of documentation, the `score()` docstring (`in [0, 100] when weights sum to 1.0`), and the composite scorer formula confine the score to 0–100. The regime gate (`apply_regime_gate`) multiplies by `regime_score ∈ [0, 1]`, which can only lower the score, never raise it above the pre-gate value. The `le=110.0` upper bound has no semantic justification and would pass corrupted rows (e.g., a bug that emits 105.0) that should be rejected.

**Fix:** Tighten the upper bound to 100.0:
```python
composite_score: Series[float] = pa.Field(ge=0.0, le=100.0, nullable=True)
```

---

### CR-04: GICS sector allowlist uses "Communication" — iShares feed uses "Communication Services"

**File:** `src/screener/persistence.py:63`

**Issue:** `GICS_SECTORS` contains `"Communication"`. The comment on line 55 says "verified live in iShares feed 2026-05-02". The GICS standard sector name — and what iShares IWB reports — is "Communication Services", not "Communication". If the live feed ever emits "Communication Services" (the standard name), `UniverseSchema` will reject all Communication Services tickers with a `SchemaError` at the write boundary, silently dropping a large sector (~8% of the index) from the universe Parquet. The conftest fixture `_make_ishares_csv_bytes` hard-codes the 11-sector list including "Communication", matching the current persistence code — both the production and test data may be wrong together.

**Fix:** Verify against the live iShares IWB CSV header. If the live feed says "Communication Services", update `GICS_SECTORS`:
```python
"Communication Services",   # was "Communication" — verify live
```
and update the conftest fixture accordingly.

---

### CR-05: `_classify_pivot_zone` classifies `close < high_52w` (close BELOW the 52-week high) as "in-zone" — semantically inverted

**File:** `src/screener/publishers/report.py:46-57`

**Issue:** The formula is `distance = (close - high_52w) / atr`. When `close < high_52w`, the distance is negative, and `distance <= 1.0` is trivially true, so any stock below its 52-week high is classified as "in-zone". This is documented as a "proxy" that "Phase 6 will tighten", but the current behavior is counter-productive: a stock at 50% below its 52-week high would be "in-zone", while a stock 1.5 ATR above its 52-week high (a breakout) would be "chase, skip". A stock trading significantly below its 52-week high is categorically NOT in a valid pivot zone. This produces materially misleading output in the report.

The correct intent (from the comment) is to classify stocks that are *near* the 52-week high — the distance should use `abs()` or the comparison should check that distance is a small *positive* number (close is slightly below or at the 52w high):
```python
def _classify_pivot_zone(close: float, high_52w: float, atr: float) -> PivotZone:
    if pd.isna(high_52w) or pd.isna(atr) or atr == 0:
        return "unknown"
    distance = (high_52w - close) / atr  # positive when close is BELOW high_52w
    return "in-zone" if 0.0 <= distance <= 1.0 else "chase, skip"
```
This treats stocks within 1 ATR *below* the 52-week high as in-zone, and stocks above (breakout) or more than 1 ATR below (laggard) as chase/skip. The `conftest.synthetic_scored_panel` fixture and `test_pivot_zone_labels` test both pass through the same helper and would need updating.

---

## Warnings

### WR-01: `config.py` sets `TREND_TEMPLATE_PASS_RATE_WARN` and `TREND_TEMPLATE_PASS_RATE_HARD_FAIL` to the same value (0.25) — dead configuration knob

**File:** `src/screener/config.py:65-66`

**Issue:** Both thresholds default to 0.25, making `TREND_TEMPLATE_PASS_RATE_HARD_FAIL` a redundant duplicate of `TREND_TEMPLATE_PASS_RATE_WARN`. Given the nesting bug in CR-01, even if these were different values, the hard-fail threshold would still be inoperative. At minimum the defaults should be distinct to make the two-tier semantics testable.

**Fix:** Set a clearly lower warn threshold: `TREND_TEMPLATE_PASS_RATE_WARN: float = 0.15` (expected healthy range is 5–15% per the log message) and keep `TREND_TEMPLATE_PASS_RATE_HARD_FAIL: float = 0.25`. After fixing CR-01, this produces distinct behavior.

---

### WR-02: `sma_panel` closure captures `length` incorrectly — all SMA columns may compute `length=200`

**File:** `src/screener/indicators/trend.py:41-47`

**Issue:** The inner function `_apply_sma` is defined inside a `for length in lengths` loop and uses `n: int = length` as a default argument. Default-argument capture at definition time is correct Python. However, the `groupby.apply` call on line 47 passes `_apply_sma` directly. Depending on the pandas version and groupby internals, `apply` may or may not pass the series — it calls `_apply_sma(group)` with a positional argument for the group, which binds to `c`. The default `n=length` is captured at loop iteration time, so it should be correct. This is fine as written.

**Correction:** On closer inspection, the default-argument pattern `n: int = length` correctly captures the loop variable at definition time. No bug here — but the pattern is subtle enough to warrant a comment, and the `apply` call shape (no explicit `n=` being passed) relies on the default being set correctly. **This finding is downgraded; the code is correct.**

---

### WR-02: `read_panel` silently skips missing tickers with no count logged — 95% gate may be bypassed at read time

**File:** `src/screener/persistence.py:615-620`

**Issue:** `read_panel` logs a warning per-missing ticker and continues. There is no aggregate count of how many tickers were skipped, and no threshold check inside `read_panel` itself. If `refresh-ohlcv` fails before the 95% gate is checked, a subsequent `score`/`report` invocation on a partial dataset could proceed with, say, 400 out of 1000 tickers without any gate rejecting the run. The 95% gate only executes during `refresh-ohlcv`; it does not re-validate at scoring time.

**Fix:** After the loop, add a coverage check:
```python
n_universe = len(universe)
n_loaded = len(frames)
if n_universe > 0 and n_loaded / n_universe < get_settings().UNIVERSE_HEALTH_THRESHOLD:
    log.error(
        "read_panel_low_coverage",
        n_universe=n_universe,
        n_loaded=n_loaded,
        ratio=n_loaded / n_universe,
    )
    raise RuntimeError(
        f"read_panel: only {n_loaded}/{n_universe} tickers loaded — "
        "re-run refresh-ohlcv to fix coverage"
    )
```

---

### WR-03: `run_pipeline` cross-sections `today_panel` from the full panel before calling `compute_for_date` — but passes the full panel to regime, not the cross-section

**File:** `src/screener/publishers/pipeline.py:132-138`

**Issue:** Step 4 does `today_panel = panel.xs(snap_ts, level="date")` to get the cross-section. Step 5 calls `compute_for_date(snap_ts, panel)` — passing the full multi-date panel (correct). Then `apply_regime_gate(today_panel, ...)` multiplies the cross-section's `composite_score` by `regime_score`. This is correct sequencing. However, `_add_publisher_columns` (step 7) is called on `today_panel` *after* the regime gate has already modified `composite_score`. The rank computed in `_add_publisher_columns` will rank by the regime-gated score (regime_score * composite_score), which is the intended behavior. This is actually correct but worth flagging as a sequencing dependency that is easy to break if steps are reordered.

No code change required; add a comment at step 7 noting the regime gate must precede ranking.

---

### WR-04: `_write_text_atomic` writes the full content to the tempfile *inside* the `with` block, then calls `os.replace` *outside* it — a crash between `__exit__` and `os.replace` leaves a committed .tmp

**File:** `src/screener/publishers/report.py:118-141`

**Issue:** The file is written and flushed when the `with tempfile.NamedTemporaryFile(...)` context exits (line 136 `tmp.write(content)` + `__exit__` flushes). Then `os.replace` is called in a bare `try` block outside the `with`. If the process crashes between context exit and `os.replace`, the data is in the `.tmp` file but `target` is never written — no data loss, just a stranded `.tmp`. More importantly, the `except` block calls `tmp_path.unlink` on the `.tmp`, but since the write already completed, this is the right behavior. However, the `try/except` block on line 137 only wraps `os.replace`, not `tmp.write`. A write failure (e.g., disk full) would raise inside the `with` block, and `delete=False` means the partial `.tmp` would not be cleaned up by the context manager. This is a latent `.tmp` leak on disk-full write failures.

**Fix:** Wrap the `write` call too, or add cleanup in the outer `except`:
```python
try:
    os.replace(tmp_path, target)
except Exception:
    tmp_path.unlink(missing_ok=True)
    raise
```
The current code already does this — but for `write` failures the `with` block exits without cleanup because `delete=False`. Consider adding a `try/finally` around the `with` block to ensure cleanup on write error. The `persistence._write_parquet_atomic` has the same structure; that version is fine because `to_parquet` failure happens inside `try`, but the text writer separates the write from the try.

---

### WR-05: `test_signals_minervini.py` — condition 7 test direction is inverted relative to spec

**File:** `tests/test_signals_minervini.py:_make_uptrend_panel`

**Issue:** Condition 7 per CLAUDE.md is `Close >= 0.75 * MAX(High, 252)` — close must be *within 25% of the 52-week high*. In `_make_uptrend_panel`, `high_52w = close.rolling(252).max()`. Since close is always rising (0.2% daily drift), the 52-week high at bar t is the current `close[t]`, and `0.75 * close[t] <= close[t]` is always trivially true. This means condition 7 is never actually stress-tested — a stock that is 40% below its 52-week high would also pass this fixture's condition 7 logic. The test validates the overall score is 8 without independently verifying that condition 7 is non-trivially satisfied.

**Fix:** Add a dedicated test that constructs a panel where close is below `0.75 * high_52w` and asserts condition 7 fails (score < 8). The downtrend panel partially covers this but does not isolate condition 7 from the other failing conditions.

---

### WR-06: `conftest.py` `synthetic_scored_panel` does not call `_add_publisher_columns` — it reimplements the formula inline, introducing drift risk

**File:** `tests/conftest.py:415-432`

**Issue:** The fixture manually computes `pivot_distance_atr`, `pivot_zone`, `regime_state`, `regime_score`, and `rank` using inline logic rather than calling `publishers.report._add_publisher_columns`. The inline `_zone` lambda (line 419-421) differs subtly from `_classify_pivot_zone`: it does not check for `atr == 0` (only checks `pd.isna`). If `_add_publisher_columns` changes (e.g., to fix CR-05), the fixture will diverge silently and the publisher tests will test against stale fixture data.

**Fix:** Replace the inline computation with a call to `_add_publisher_columns`:
```python
from screener.publishers.report import _add_publisher_columns
regime_row = pd.Series({"regime_state": "Confirmed Uptrend", "regime_score": 0.82})
cross = _add_publisher_columns(cross, regime_row)
```
This ensures the fixture always reflects the real publisher behavior.

---

## Info

### IN-01: `TREND_TEMPLATE_PASS_RATE_WARN` docstring says "default 0.25" — the expected healthy range is 5–15%

**File:** `src/screener/publishers/pipeline.py:71`

**Issue:** The docstring inside `validate_run` says `expected_range="0.05-0.15"` in the log event, but the threshold is 0.25. A 25% pass rate is already 10x the expected maximum (15%). The warn threshold should align with the documented healthy range — setting it at 0.25 means the warning fires only when data quality is severely degraded, not when it first begins to drift. This is a configuration philosophy issue, not a code bug, but it dilutes the usefulness of the D-07 warning signal.

---

### IN-02: `check_preregistration.py` uses `sys.exit()` for the missing-weight case but `return 1` for the mismatch case — inconsistent error-reporting convention

**File:** `scripts/check_preregistration.py:51, 90`

**Issue:** `parse_doc_weights()` calls `sys.exit(f"Preregistration doc missing ...")` directly, which terminates the process with an exit code of 1 and the message as the exit value. The `main()` function returns `1` for mismatches. Callers that import `main()` (as the tests do) can catch the `SystemExit` from the parse path but not from the mismatch path (it returns an int). This inconsistency makes the script harder to test uniformly. The test `test_missing_weight_in_doc_fail` correctly uses `pytest.raises(SystemExit)`, but `test_mismatched_weights_fail` checks `main() == 1` — two different exception models for two error paths.

**Fix:** Standardize: raise `SystemExit` for both, or return a non-zero int from both. Returning an int from `main()` and calling `sys.exit(main())` at the `__main__` entry point is the conventional pattern.

---

### IN-03: `.gitignore` line 45 `data/snapshots/*.parquet` is not anchored — may match paths in subdirectories unintentionally

**File:** `.gitignore:45`

**Issue:** The pattern `data/snapshots/*.parquet` is not anchored with a leading `/`. Git interprets unanchored patterns as matching in any directory, so `foo/data/snapshots/bar.parquet` would also be excluded if such a path existed. The neighboring patterns (`/data/*`, `/data/ohlcv/**/prices.parquet`) are anchored. This is a minor inconsistency. Given the flat repo structure it is unlikely to cause an actual problem, but for consistency with the other anchored patterns in the file:

**Fix:** Change to `/data/snapshots/*.parquet`.

---

_Reviewed: 2026-05-10T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
