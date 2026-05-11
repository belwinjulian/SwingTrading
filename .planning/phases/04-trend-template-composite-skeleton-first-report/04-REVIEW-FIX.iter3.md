---
phase: 04-trend-template-composite-skeleton-first-report
fixed_at: 2026-05-11T01:13:42Z
review_path: .planning/phases/04-trend-template-composite-skeleton-first-report/04-REVIEW.md
iteration: 2
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report (Iteration 2)

**Fixed at:** 2026-05-11T01:13:42Z
**Source review:** `.planning/phases/04-trend-template-composite-skeleton-first-report/04-REVIEW.md`
**Iteration:** 2

**Summary:**
- Findings in scope: 5 (0 Critical + 3 Warning + 2 Info)
- Fixed: 5
- Skipped: 0
- Full pytest run after all fixes: 132 passed, 2 skipped (no regressions)
- mypy `indicators/` + `signals/` clean
- ruff clean on all modified files (pre-existing project-wide ruff errors untouched)

Iteration-1 history (preserved for context): 14 findings in scope, 12 fixed, 2 skipped (CR-04 Communication sector — sector allowlist matches live parquet; WR-02 first sma_panel closure — reviewer self-downgraded).

## Fixed Issues

### WR-01: `test_condition_7_isolated_fail` does not isolate condition 7

**Files modified:** `tests/test_signals_minervini.py`
**Commit:** `d1e2911`
**Applied fix:** Restructured the test to inject a single price spike at index 60 — a position that is INSIDE the 252-bar `high_52w` rolling window at the final bar (window 48..299) but OUTSIDE every SMA window footprint at the final bar (SMA50: 250..299, SMA150: 150..299, SMA200: 100..299, cond-3's `sma_200[-23]` window: 77..276). The spike inflates `high_52w[-1]` to 400 (≈ 2.2× the un-spiked last-bar close of ~182), forcing `close[-1] < 0.75 * high_52w[-1]` while every SMA-based condition reflects the unperturbed uptrend. Replaced the weak `score < 8` assertion with the strong-form `score == 7` (exactly one condition failed), and added a setup invariant check that `0.75 * high_52w[-1] > close[-1]`.

Verified: `pytest tests/test_signals_minervini.py` passes 6/6 with the new isolation guarantee. The new assertion would FAIL if any other condition co-failed — which is the regression-protection the iter-1 test lacked.

### WR-02: Bidirectional preregistration check blind spot

**Files modified:** `scripts/check_preregistration.py`
**Commit:** `6ac4028`
**Applied fix:** Per reviewer's recommended low-risk patch (option a), downgraded the inline comment on the `extra_in_doc` gate from "Bidirectional check" to "Partial bidirectional check" with an explicit SCOPE block stating that the gate only catches doc rows whose friendly name is in `NAME_TO_KEY` but whose internal key is missing from `DEFAULT_WEIGHTS`. Doc rows whose friendly name is NOT in `NAME_TO_KEY` are silently dropped during `parse_doc_weights` and do NOT reach this gate. A full bidirectional doc-table scan is deferred since v1 has a fixed 6-component composite.

Verified: `pytest tests/test_preregistration_check.py` passes 3/3 (no behavior change).

### WR-03: `_write_text_atomic` empty-`.tmp` orphan window

**Files modified:** `src/screener/publishers/report.py`
**Commit:** `4be5499`
**Applied fix:** Consolidated `tmp.write(content)` INSIDE the same `with tempfile.NamedTemporaryFile(...) as tmp:` block as the tempfile creation, then run `os.replace` after the `with` exits, all wrapped in a single `try/except`. Pre-declared `tmp_path: Path | None = None` so the except branch can distinguish "tempfile never created" from "tempfile created and needs unlinking". The new structure matches `persistence._write_parquet_atomic` and closes the narrow window (between outer `with` exit and inner `open()` call) where an empty `.tmp` could be orphaned by a SIGKILL.

Verified: `pytest tests/test_publishers_report.py` passes 7/7, including `test_report_atomic_write_crash_no_residue`. `mypy src/screener/publishers/report.py` clean.

### IN-01: `read_panel` low-coverage gate uses `lru_cache`'d `get_settings()`

**Files modified:** `src/screener/persistence.py`
**Commit:** `b689306`
**Applied fix:** Per reviewer's recommended lowest-cost option, added a "Test-author note (REVIEW IN-01, iter 2)" block to `read_panel`'s docstring explaining that `UNIVERSE_HEALTH_THRESHOLD` is read via `get_settings()` which is `@lru_cache(maxsize=1)`-decorated. Tests that monkeypatch the env var after any prior `get_settings()` call will see the stale value; the fix is to call `get_settings.cache_clear()` in the test fixture. Documents the caveat as a propagated constraint across every settings read in the module. No code change; documentation-only.

### IN-02: `read_panel` raises bare `RuntimeError` — inconsistent with `StaleOrEmptyError`

**Files modified:** `src/screener/persistence.py`
**Commit:** `8e46b17`
**Applied fix:** Per reviewer's option (a), replaced `raise RuntimeError(...)` with `raise StaleOrEmptyError(...)` in the low-coverage gate. `StaleOrEmptyError` inherits from `RuntimeError` so the CLI's broad `except Exception` continues to work, and `data/` adapters that catch `StaleOrEmptyError` via tenacity's `retry_if_exception_type` continue to function. The CLI structured log now reads `error_type=StaleOrEmptyError`, matching the convention used by `data/ohlcv.py` and `data/stooq.py` and restoring log-grep consistency for data-quality failures. Added an inline comment naming the IN-02 fix.

Verified: `pytest tests/test_persistence.py tests/test_cli_smoke.py` passes 22/22.

---

_Fixed: 2026-05-11T01:13:42Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
