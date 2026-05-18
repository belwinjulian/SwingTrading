---
phase: 07-sizing-finalization-paper-trade-journal
plan: "02"
subsystem: sizing-pure-function
tags: [phase-7, sizing, pure-function, dispatch-registry, stop-helpers, trail-labels, atr-zone, SIZ-01, SIZ-02, SIZ-03, SIZ-04, SIZ-05]
dependency_graph:
  requires:
    - 07-01-SUMMARY.md (sized_input_cross() fixture + RankingSnapshotSchema 10 nullable cols + RISK_PCT Setting)
    - 06-05-SUMMARY.md (playbook_tag, pattern_diagnostics columns in snapshot; indicators/patterns.find_pivots + decode_pattern_diagnostics)
  provides:
    - sizing.compute_sizing(cross, panel, account_equity, risk_pct, regime_score) -> DataFrame with 9 new columns
    - STOP_HELPERS Final dict registry (3 entries) satisfying SC-2 identity assertion
    - classify_atr_zone() 3-bucket classifier (in-zone/extended/chase, skip)
    - _trail_rule_label() display-string dispatch (Qull ADR%-tier / VCP / leader_hold)
    - _recent_swing_low_distance() leader_hold fallback helper
    - 11 passing unit tests in tests/test_sizing.py (zero remaining pytest.skip)
  affects:
    - 07-04-PLAN.md (pipeline wiring calls compute_sizing; depends on 9-column contract)
    - 07-05-PLAN.md (report rendering uses trail_rule_label, atr_zone columns)
tech_stack:
  added: []
  patterns:
    - Final-dict-dispatch-registry (STOP_HELPERS: SC-2 identity assertion via dict key lookup)
    - per-row-iteration-over-vectorization (n <= R1000, readability favored)
    - ValueError-as-rejection-signal (Pitfall 5: corrupt VCP diagnostics -> missing_diagnostics reason)
    - isinstance-guard-for-mypy-strict (panel.xs() returns DataFrame|Series; guarded for strict mode)
key_files:
  created: []
  modified:
    - src/screener/sizing.py (6-line stub -> 360-line body; 8 top-level functions + STOP_HELPERS registry)
    - tests/test_sizing.py (11 pytest.skip skeletons -> 11 real test bodies, all passing)
    - tests/test_architecture.py (ALLOWED["sizing"] set extended with "indicators")
decisions:
  - "test_shares_formula VCP1 assertion corrected: fixture adr_pct=4.2 with risk=8 triggers adr_exceeded rejection (8 > 4.2); test now uses custom single-row cross with adr_pct=10.0 to exercise the shares formula path cleanly"
  - "mypy strict panel.xs() cast: pandas stubs declare xs() return as DataFrame|Series[Any]; added isinstance guard rather than cast() to keep runtime safety + satisfy strict mode; sizing.py already in pyproject.toml strict files list"
  - "Unicode math symbols stripped from docstrings/comments: ruff RUF002/003 flagged × and − (Unicode) in docstrings; replaced with x and - (ASCII) throughout to keep ruff clean"
  - "compute_sizing() included in Task 1 write (not deferred to Task 2 as plan suggested) since the file was fully replaced; effectively Task 1 and 2 land in two commits (first commit: constants+helpers+STOP_HELPERS; second commit: compute_sizing+test bodies)"
metrics:
  duration: 6m
  completed_date: "2026-05-18"
  tasks: 2
  files: 3
---

# Phase 07 Plan 02: Sizing Module — Pure-Function compute_sizing() Body Summary

Wave 1 implementation of `src/screener/sizing.py`: pure-function `compute_sizing()` that dispatches per-playbook stops (D-07), computes shares (D-05), runs the 1xADR auto-reject (D-06), classifies the 3-bucket ATR zone (D-09), and emits trail-rule labels (D-08). All 11 pytest.skip skeletons in `tests/test_sizing.py` replaced with real passing bodies. Architecture test extended to permit `sizing -> indicators` imports.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Architecture-test ALLOWED dict + sizing.py constants + private helpers + STOP_HELPERS | a276de2 | tests/test_architecture.py, src/screener/sizing.py |
| 2 | compute_sizing() body + 11 real test bodies | fa77474 | src/screener/sizing.py, tests/test_sizing.py |
| 2a | mypy strict panel.xs return type cast | a99137a | src/screener/sizing.py |

## Verification Results

All acceptance criteria passed:

- `11 passed` — tests/test_sizing.py (zero skips, zero failures)
- `4 passed` — tests/test_architecture.py (ALLOWED dict with indicators extension)
- `2 passed` — tests/test_backtest_no_lookahead.py (FND-04 mutation gate)
- `9 passed` — tests/test_publishers_pipeline.py + test_subcommand_surface_locked
- `ruff check src/screener/sizing.py` — All checks passed
- `mypy --strict src/screener/sizing.py` — Success: no issues found
- `grep -cE "^def _stop_...|^def classify_...|^def _trail...|^def _recent..."` — 6 functions confirmed
- `grep -cE "^STOP_HELPERS: Final"` — 1 match confirmed
- `wc -l src/screener/sizing.py` — 360 lines (>= 200 minimum)
- Module sanity: `3 helpers registered` — STOP_HELPERS has exactly 3 entries

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_shares_formula VCP1 assertion inconsistent with fixture**
- **Found during:** Task 2 (first test run)
- **Issue:** The plan's test body asserted `VCP1.shares == 106` but the `sized_input_cross` fixture has `adr_pct=4.2` for VCP1. With `stop=92.0` (from VCP diagnostics), `risk_per_share=8.0 > adr_dollars=4.2` — VCP1 is ADR-rejected (adr_exceeded), shares=0. The plan test was written against a hypothetical fixture, not the actual one committed in Plan 07-01.
- **Fix:** Replaced VCP1 shares assertion with a custom single-row cross section having `adr_pct=10.0` (wide enough to avoid ADR rejection), keeping `pattern_diagnostics` from the fixture (pivot_price=100, final_contraction_depth=0.08). The shares formula path is still exercised: risk=8, raw=floor(850/8)=106, cap=floor(25000/100)=250 -> shares=106.
- **Files modified:** tests/test_sizing.py
- **Commit:** fa77474

**2. [Rule 1 - Bug] ruff UP037 + RUF002/003 lint failures from Unicode math in docstrings**
- **Found during:** Task 2 (post-write ruff check)
- **Issue:** The plan's provided code snippets used Unicode math characters (×, −) in docstrings and a comment. ruff flagged 25 errors (10 UP037 auto-fixable quoted annotations; 15 RUF002/003 ambiguous Unicode).
- **Fix:** Auto-fixed UP037 with `ruff --fix`; manually replaced × with `x` and − with `-` in all docstrings and comments.
- **Files modified:** src/screener/sizing.py
- **Commit:** fa77474 (bundled with test bodies commit)

**3. [Rule 2 - Missing critical functionality] mypy strict error on panel.xs() return type**
- **Found during:** Post-task-2 mypy check
- **Issue:** `panel.xs(t, level="ticker", drop_level=True)` is declared by pandas stubs as returning `DataFrame | Series[Any]`. sizing.py was already in `pyproject.toml`'s `[tool.mypy]` strict files list. Without the fix, CI mypy would fail.
- **Fix:** Added `isinstance(result, pd.DataFrame)` guard in `_ticker_history` inner function; returns empty DataFrame fallback when result is not a DataFrame (defensive — can't happen at runtime with a 2-level MultiIndex panel, but required for type correctness).
- **Files modified:** src/screener/sizing.py
- **Commit:** a99137a

## Known Stubs

None. All 11 test bodies are fully implemented. sizing.py has no placeholder values, TODO comments, or hardcoded empty data.

## Threat Surface Scan

No new network endpoints, auth paths, or external trust boundaries introduced. The `sizing.py` module is a pure function with no I/O. The `pattern_diagnostics` JSON guard in `_stop_minervini_vcp` (Pitfall 5 mitigation) handles the T-07-06 threat as designed — corrupt blob raises `ValueError("missing_diagnostics")` which the outer try/except converts to `rejection_reason='missing_diagnostics'`. Tested via `test_vcp_stop_from_diagnostics`.

## Self-Check: PASSED
