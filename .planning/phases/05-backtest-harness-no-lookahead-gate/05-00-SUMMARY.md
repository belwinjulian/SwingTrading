---
phase: 5
plan: 0
slug: backtest-harness-no-lookahead-gate
subsystem: test-infrastructure
tags: [phase-5, wave-0, validation-skeleton, fixtures, skip-stubs, no-lookahead-gate]
status: complete
completed: 2026-05-16
duration_minutes: 20
tasks_completed: 2
files_created: 4
files_modified: 1
dependency_graph:
  requires:
    - "tests/conftest.py existing analog: synthetic_multi_ticker_panel (Phase 2)"
    - "pytest 8.x + numpy + pandas (already in pyproject.toml dev extras)"
  provides:
    - "tests/conftest.py::synthetic_ohlcv_panel (session-scoped GBM panel; consumed by Wave 1/2 plans 05-01, 05-02)"
    - "tests/test_backtest_no_lookahead.py (skip-stub; filled by plan 05-02)"
    - "tests/test_walkforward_windows.py (skip-stub; filled by plan 05-01)"
    - "tests/test_slippage_tiers.py (skip-stub; filled by plan 05-01)"
    - "tests/test_backtest_audit.py (skip-stub; filled by plan 05-05)"
  affects:
    - "Every Wave 1/2/3 plan in Phase 5 — their per-task verify commands now resolve to existing files (Nyquist-compliance precondition)"
tech_stack:
  added: []
  patterns: ["pytest skip-stub for Wave 0 anti-Nyquist seeding", "deterministic GBM fixture (numpy default_rng + log-return cumulative)"]
key_files:
  created:
    - "tests/test_backtest_no_lookahead.py"
    - "tests/test_walkforward_windows.py"
    - "tests/test_slippage_tiers.py"
    - "tests/test_backtest_audit.py"
  modified:
    - "tests/conftest.py (added synthetic_ohlcv_panel fixture)"
decisions:
  - "Preserved n_bars=1300 from plan action block despite span miscalculation (planner claimed ~5.15yr; actual=4.98yr). Plan's hard guard 'DO NOT reduce below 1300' was honored; documented as deviation."
  - "Added # noqa: E501 to skip messages to satisfy project ruff line-length=100 limit; preserves the plan's literal skip message text."
  - "Replaced unicode '×' with ASCII 'x' in fixture docstring to satisfy ruff RUF002."
metrics:
  duration: "20 minutes"
  completed_date: "2026-05-16"
  baseline_tests_before: "134 passed, 2 skipped"
  baseline_tests_after: "134 passed, 13 skipped (11 new skips from Wave 0 stubs)"
  ruff_status_plan_files: "all clean (tests/conftest.py + 4 new stubs)"
threat_model_refs:
  - "T-5-04 (Tampering on fixture) — mitigated: pinned seed_base=42, pure-stdlib numpy default_rng, no env-coupled randomness; fixture lives in tests/ (cannot leak to production paths); two-call determinism confirmed."
requirements:
  partial:
    - "FND-04 (stub seeded; Wave 1 mutation test fills body)"
    - "BCK-01 (window-construction stub seeded; Wave 1 unit test fills body)"
    - "BCK-03 (slippage-tier stub seeded; Wave 1 unit test fills body)"
    - "BCK-07 (audit CLI stub seeded; Wave 3 CliRunner test fills body)"
---

# Phase 5 Plan 0: Backtest Harness — Wave 0 Validation Skeleton

**One-liner:** Seeded the Phase-5 validation skeleton with a deterministic `synthetic_ohlcv_panel` GBM fixture (1300 bdays x 3 tickers, seed=42, loc=0.0) and 4 skip-stub test files so every Wave 1/2/3 per-task verify command resolves to an existing file (anti-Nyquist-drift precondition).

## Tasks Completed

| # | Name | Commit | Files | Tests |
|---|------|--------|-------|-------|
| 1 | Add `synthetic_ohlcv_panel` fixture to `tests/conftest.py` | `7b55ef6` | `tests/conftest.py` (+54 lines) | Direct fn invocation: 3900 rows, 3 tickers, 4.98yr span, deterministic |
| 2 | Create 4 skip-stub test files (no-lookahead, walkforward, slippage, audit) | `f395c4c` | 4 new test files (+120 lines) | 11 skips reported, 0 failures |

## Verification Results

**Success criteria (from plan):**

1. ✅ `pytest tests/test_backtest_no_lookahead.py tests/test_walkforward_windows.py tests/test_slippage_tiers.py tests/test_backtest_audit.py -q --no-cov` → **11 skipped** (0 failed, 0 errored). 2+3+3+3 = 11 as expected.
2. ✅ `synthetic_ohlcv_panel` is importable from `tests.conftest`. Note: `pytest --collect-only` does not list fixtures (only tests); fixture registration verified by import + direct invocation.
3. ✅ Shape: 3900 rows (3 tickers × 1300 bdays), tickers = `{'AAA', 'BBB', 'CCC'}`, MultiIndex `(ticker, date)`.
4. ⚠️ Span: **4.980 calendar years** (2019-01-01..2023-12-25), not 5.15yr as plan docstring claims — see Deviations below. Walk-forward window count check (`assert len(windows) >= 2`) is downstream-verifiable in plan 05-01 once `walk_forward_windows` exists.
5. ✅ Full suite: `pytest -q --no-cov` → **134 passed, 13 skipped** (baseline 134/2; the 11 new skips are exactly this plan's stubs).
6. ✅ `tests/test_architecture.py` → 3 passed (no `src/` touched, allowed-imports invariant intact).
7. ✅ `ruff check` on plan-modified files (`tests/conftest.py` + 4 new stubs) → All checks passed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's fixture span miscalculation (1300 bdays != 5.15yr)**

- **Found during:** Task 1 verification.
- **Issue:** Plan docstring claims "1300 bdays starting 2019-01-01 covers ~5.15 calendar years (ends ~2024-01-XX)". Actual: 1300 bdays from 2019-01-01 ends **2023-12-25** = **4.98 calendar years**. The plan's verification check (`assert years >= 5.0`) and Win 2 OOS dates (2023-01-01..2023-12-31) both presuppose a span this fixture does not produce.
- **Resolution:** Preserved `n_bars=1300` as written in the plan's `action` block (the plan has an explicit hard guard "DO NOT reduce n_bars below 1300" AND the verification asserts `panel.shape[0] == 3900` which fixes n_bars at exactly 1300; raising n_bars to 1310+ to satisfy `years >= 5.0` would have failed the row-count check). This is a planner spec inconsistency — three constraints (n_bars=1300, shape=3900, span>=5.0yr) cannot all be satisfied simultaneously.
- **Downstream impact:** When plan 05-01 implements `walk_forward_windows(start, end, is_years=3, oos_years=1)`, Win 2 (IS 2020..2022 / OOS 2023) needs OOS-end <= fixture-end. With fixture-end = 2023-12-25 and OOS-end = 2023-12-31, the window will be **excluded** under strict `oos_end <= end` semantics → only Win 1 (IS 2019..2021 / OOS 2022) survives, NOT the ≥2 windows the plan promises. Plan 05-02's iter-3 explicit `assert len(result.windows) >= 1` precondition will still pass (1 ≥ 1), but the stated invariant ">=2 complete windows" is violated.
- **Recommendation for downstream:** Plan 05-01 should either (a) loosen window-end semantics to `oos_end <= end + 1bday`, OR (b) future-amend this fixture to `n_bars >= 1310` AND drop the `panel.shape[0] == 3900` assertion. C-1 fix iter 3 narrative remains valid in spirit; only the magic number 1300 is off by ~10 bars.
- **Files modified:** `tests/conftest.py`
- **Commit:** `7b55ef6`

**2. [Rule 3 - Blocking] Plan's docstring used unicode "×" (RUF002 failure)**

- **Found during:** Task 1 ruff check.
- **Issue:** Plan's `action` block uses unicode multiplication sign `×` in two docstring lines ("1300 business days × 3 tickers" and "3 tickers × 1300 = 3900 rows"). Project ruff config flags RUF002 (ambiguous unicode in docstring).
- **Resolution:** Replaced both `×` with ASCII `x`. Preserves the plan's literal meaning; no behavioral change.
- **Files modified:** `tests/conftest.py`
- **Commit:** `7b55ef6`

**3. [Rule 3 - Blocking] Plan's stub skip-message lines exceed project ruff line-length=100**

- **Found during:** Task 2 ruff check.
- **Issue:** Each of the 11 `pytest.skip(...)` lines in the 4 new stub files is 111 chars (the path `.planning/phases/05-backtest-harness-no-lookahead-gate/05-XX-PLAN.md` is itself ~80 chars). Project's `tool.ruff.line-length = 100` flags E501.
- **Resolution:** Appended `# noqa: E501` to each skip line. Preserves the plan's literal skip message text; well-precedented pattern in project (`tests/test_signals_minervini.py` uses `# noqa: E712`; `tests/test_regime_imports.py` uses `# noqa: F401`).
- **Files modified:** All 4 stub files
- **Commit:** `f395c4c`

### Out-of-Scope Discoveries (NOT fixed)

- `ruff check tests/` reports **19 pre-existing errors** in `tests/test_data_ohlcv.py`, `tests/test_data_stooq.py`, `tests/test_data_universe.py`, `tests/test_indicators_trend.py` (F401 unused imports, SIM117 nested-with, RUF059 unused unpacks, E501 line-length, I001 import ordering, N806 naming). None of these are in files this plan created or modified. Per execution scope boundary rule, they are deferred. The plan's verification check (`ruff check tests/`) would have caught these too — appears to be pre-existing tech debt the plan author didn't anticipate.

## Files Created / Modified

### Created (4)

| Path | Lines | Tests | Wave Owner |
|------|-------|-------|------------|
| `tests/test_backtest_no_lookahead.py` | 28 | 2 skips | Wave 1 (plan 05-02) — FND-04, BCK-02 |
| `tests/test_walkforward_windows.py` | 29 | 3 skips | Wave 1 (plan 05-01) — BCK-01 |
| `tests/test_slippage_tiers.py` | 30 | 3 skips | Wave 1 (plan 05-01) — BCK-03 |
| `tests/test_backtest_audit.py` | 33 | 3 skips | Wave 3 (plan 05-05) — BCK-07 |

### Modified (1)

| Path | Change | Lines Added |
|------|--------|-------------|
| `tests/conftest.py` | Added `synthetic_ohlcv_panel` session-scope fixture between `synthetic_multi_ticker_panel` (Phase 2 analog) and Phase 3 regime fixtures block | +54 |

## Authentication Gates

None. This plan creates test-only files with no network/IO/auth surface.

## Key Decisions Made

- **Fixture insertion location:** Placed `synthetic_ohlcv_panel` immediately after the Phase 2 `synthetic_multi_ticker_panel` analog (line 313→316), under a new section header `# --- Phase 5 backtest harness fixtures (Plan 05-00) ---`. Matches the project's existing per-phase section convention in conftest.py.
- **Skip-stub message format:** Used `pytest.skip("Wave N fills body — see {plan path}")` exactly as the plan prescribes, with `# noqa: E501` for length. The pointer to the specific Wave/plan keeps continuation context discoverable from CI logs.
- **Determinism guarantee:** Verified that two direct invocations of the fixture function produce `panel.equals(panel2)` True. Per-ticker RNG `default_rng(seed_base + i)` ensures independence across AAA/BBB/CCC AND reproducibility across pytest sessions.

## Known Stubs

All 11 stub tests intentionally call `pytest.skip(...)` with explicit pointers to the downstream plan that fills the body. These are NOT bugs — they are the explicit Wave 0 anti-Nyquist seeding pattern documented in 05-VALIDATION.md §"Wave 0 Requirements". Downstream plans 05-01, 05-02, 05-05 will replace each `pytest.skip` with the real assertion body.

## Threat Flags

None. Wave 0 introduces no new network/auth/file-write/schema surface beyond the deterministic in-memory fixture.

## TDD Gate Compliance

N/A — plan frontmatter is `type: execute`, not `type: tdd`. Tasks are explicitly Wave 0 skip-stub seeding; the test bodies they stub out will be filled by downstream plans using RED/GREEN if those plans declare TDD.

## Commits

1. `7b55ef6` — `test(05-00): add synthetic_ohlcv_panel fixture for backtest harness` (1 file, +54 lines)
2. `f395c4c` — `test(05-00): add 4 skip-stub test files for Phase 5 backtest harness` (4 files, +120 lines)

## Self-Check: PASSED

**Created files (verified on disk):**
- ✅ `tests/test_backtest_no_lookahead.py` — FOUND
- ✅ `tests/test_walkforward_windows.py` — FOUND
- ✅ `tests/test_slippage_tiers.py` — FOUND
- ✅ `tests/test_backtest_audit.py` — FOUND

**Modified files (verified on disk):**
- ✅ `tests/conftest.py` contains `synthetic_ohlcv_panel` — FOUND (grep confirms; line ~319)

**Commits exist in git log:**
- ✅ `7b55ef6` — FOUND
- ✅ `f395c4c` — FOUND

**Behavioral assertions:**
- ✅ `pytest tests/test_backtest_*.py tests/test_walkforward_*.py tests/test_slippage_*.py -q --no-cov` → 11 skipped
- ✅ Full suite: 134 passed, 13 skipped (baseline+11 new skips, no new failures)
- ✅ `tests/test_architecture.py` → 3 passed
- ✅ `ruff check` on plan-touched files → All checks passed
