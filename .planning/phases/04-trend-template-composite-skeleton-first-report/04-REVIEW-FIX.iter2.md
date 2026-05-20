---
phase: 04-trend-template-composite-skeleton-first-report
fixed_at: 2026-05-10T00:48:00Z
review_path: .planning/phases/04-trend-template-composite-skeleton-first-report/04-REVIEW.md
iteration: 1
findings_in_scope: 14
fixed: 12
skipped: 2
status: partial
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-05-10T00:48:00Z
**Source review:** `.planning/phases/04-trend-template-composite-skeleton-first-report/04-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 14 (5 Critical + 6 Warning + 3 Info)
- Fixed: 12
- Skipped: 2

## Fixed Issues

### CR-01: `validate_run` D-08 hard-fail is nested inside the D-07 warn block

**Files modified:** `src/screener/publishers/pipeline.py`
**Commit:** `deec4e6`
**Applied fix:** Flattened the inner `if regime_state == 'Correction' and pass_rate > fail_threshold_with_correction` block out of the outer `if pass_rate > warn_threshold` block so the two thresholds are independent control surfaces. Added an inline comment naming the bug class.

### CR-02: Preregistration check only iterates `DEFAULT_WEIGHTS` keys

**Files modified:** `scripts/check_preregistration.py`
**Commit:** `e644a3d`
**Applied fix:** Added a bidirectional check `extra_in_doc = set(doc_weights) - set(DEFAULT_WEIGHTS)` after the forward loop so an unknown doc key surfaces as a CI failure with a clear message.

### CR-03: `RankingSnapshotSchema.composite_score` allows up to 110.0

**Files modified:** `src/screener/persistence.py`
**Commit:** `140ca29`
**Applied fix:** Tightened the pandera `Field(le=110.0)` to `Field(le=100.0)` to match the documented composite range. Existing snapshot test data (max 50.0) is unaffected.

### CR-05: `_classify_pivot_zone` semantic inversion

**Files modified:** `src/screener/publishers/report.py`, `tests/test_publishers_report.py`
**Commit:** `01a1cde`
**Applied fix:** Flipped the sign convention in both `_classify_pivot_zone` and `_add_publisher_columns` to `(high_52w - close) / atr`, and required `0.0 <= distance <= 1.0` for `'in-zone'`. Refreshed the direct helper assertions in `test_pivot_zone_labels` to exercise both laggard (10 ATR below) and breakout (above 52w high) paths.

### WR-01: Both `TREND_TEMPLATE_PASS_RATE_*` defaults are 0.25

**Files modified:** `src/screener/config.py`
**Commit:** `f705afc`
**Applied fix:** Lowered `TREND_TEMPLATE_PASS_RATE_WARN` to 0.15 (top of the documented healthy 5-15% range); kept `TREND_TEMPLATE_PASS_RATE_HARD_FAIL` at 0.25. Combined with CR-01's flattening, the two-tier semantics are now testable end-to-end.

### WR-02 (second, on `read_panel`): silent low-coverage at read time

**Files modified:** `src/screener/persistence.py`
**Commit:** `27fcd8e`
**Applied fix:** Added an aggregate `n_loaded / n_universe < UNIVERSE_HEALTH_THRESHOLD` check after the per-ticker loop in `read_panel`. Raises `RuntimeError` with a remediation hint pointing to `refresh-ohlcv`. The existing round-trip test writes 100% of the universe so the gate does not regress.

### WR-03: `run_pipeline` step-ordering dependency is implicit

**Files modified:** `src/screener/publishers/pipeline.py`
**Commit:** `ff3d8d6`
**Applied fix:** Added a comment at step 7 documenting that `_add_publisher_columns` ranks by `composite_score` AFTER the regime gate has multiplied it, so step 5 (`apply_regime_gate`) and step 7 must NOT be reordered. The reviewer explicitly said no code change required.

### WR-04: `_write_text_atomic` leaks `.tmp` on `tmp.write` failure

**Files modified:** `src/screener/publishers/report.py`
**Commit:** `9cb655a`
**Applied fix:** Restructured `_write_text_atomic` so the file is created with `delete=False` inside the context manager, but the actual content write happens inside the same `try/except` block as `os.replace`. Now a disk-full failure during the write unlinks the `.tmp` and re-raises. The existing crash-no-residue test continues to pass.

### WR-05: Condition 7 never independently stressed

**Files modified:** `tests/test_signals_minervini.py`
**Commit:** `eddd5b6`
**Applied fix:** Added `test_condition_7_isolated_fail` which constructs a panel with a monotonic uptrend, then forces `close[-1]` to 0.70 × `high_52w[-1]` while pinning the SMAs below the dropped close so conditions 1-6 and 8 still pass. Asserts `trend_template_score < 8` and `passes_trend_template is False`. This change is in `tests/`, not `signals/`, so the no-lookahead test obligation does not apply. (The `tests/test_backtest_no_lookahead.py` file does not yet exist — Phase 5 deliverable.)

### WR-06: `synthetic_scored_panel` reimplements pivot/regime logic inline

**Files modified:** `tests/conftest.py`
**Commit:** `61b0a3f`
**Applied fix:** Replaced the inline `pivot_distance_atr` / `pivot_zone` / `rank` / regime-column derivation with a call to `screener.publishers.report._add_publisher_columns`. The fixture is now driven by production code so it cannot silently diverge from CR-05's sign-convention fix or any future tweak.

### IN-01: `validate_run` docstring out of sync with new defaults

**Files modified:** `src/screener/publishers/pipeline.py`
**Commit:** `f5c5b63`
**Applied fix:** Updated the docstring to say `warn_threshold (default 0.15, top of the documented healthy 5-15% range)` and added a pointer to WR-01 explaining the distinct two-tier defaults.

### IN-02: `check_preregistration.py` uses `sys.exit` vs `return 1` inconsistently

**Files modified:** `scripts/check_preregistration.py`, `tests/test_preregistration_check.py`
**Commit:** `c6e4400`
**Applied fix:** Introduced a `PreregistrationDocError` typed exception, made `parse_doc_weights` raise it (instead of calling `sys.exit`), and made `main()` catch it and return 1 — so every error path now returns a uniform non-zero int. The `__main__` entry point still calls `sys.exit(main())`. Updated `test_missing_weight_in_doc_fail` to assert `main() == 1` + stderr message instead of `pytest.raises(SystemExit)`.

### IN-03: `.gitignore` `data/snapshots/*.parquet` unanchored

**Files modified:** `.gitignore`
**Commit:** `9580e46`
**Applied fix:** Anchored the pattern to `/data/snapshots/*.parquet` for consistency with the surrounding patterns.

## Skipped Issues

### CR-04: GICS sector allowlist uses "Communication"

**File:** `src/screener/persistence.py:63`
**Reason:** Verified the live iShares feed at `data/universe/2026-04-27.parquet` (the currently-committed snapshot): `df['sector'].unique()` contains `'Communication'`, NOT `'Communication Services'`. The current `GICS_SECTORS` allowlist matches the live data byte-for-byte. The review's fix is *conditional* ("Verify against the live iShares IWB CSV header. If the live feed says 'Communication Services', update..."); since the live feed does not, applying the fix would break the running pipeline by rejecting every Communication-sector ticker.
**Original issue:** Reviewer asserted GICS standard spelling is "Communication Services" and that iShares would silently reject the existing allowlist. This is contradicted by the actual live parquet.

### WR-02 (first, on `sma_panel` closure capture)

**File:** `src/screener/indicators/trend.py:41-47`
**Reason:** Reviewer explicitly self-downgraded this finding: "**This finding is downgraded; the code is correct.**" — the default-argument `n: int = length` correctly captures the loop variable at definition time and the `groupby.apply` call shape is fine. No fix is required by the review itself.
**Original issue:** Initial concern that the closure may compute `length=200` for all SMA columns; reviewer's correction notes the default-argument capture pattern is correct as written.

---

_Fixed: 2026-05-10T00:48:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
