---
phase: 05-backtest-harness-no-lookahead-gate
verified: 2026-05-16T22:25:00Z
status: human_needed
score: 5/5 roadmap success criteria verified; 8/8 requirements satisfied (1 partial-by-design via D-12); 3 items require human decision/action
re_verification:
  previous_status: none
  notes: initial verification
human_verification:
  - test: "Ratify D-07 recalibration (CONTEXT.md doc drift)"
    expected: "User reviews 05-02-SUMMARY's 10-seed Monte Carlo evidence and either (a) updates CONTEXT.md D-07 to D-07-REVISED-3 (8e-7 ceiling / 8e-7 floor / 3.0x ratio) with the production-harness rationale, or (b) instructs that the deviation be reverted. The test docstring + 05-02-SUMMARY already carry the new thresholds; only CONTEXT.md/RESEARCH.md still read 0.50/1.00."
    why_human: "DEVIATION-1 in 05-02-SUMMARY is explicitly flagged by the executor as `User decision REQUIRED before merge`. The planner anticipated this branch (the plan literally says `ping the user to update D-07 (REVISED-3) before committing`). The mutation gate IS load-bearing (manually verified by sed-removal of .shift(1) producing a FAIL with the expected message), so functional achievement is not in question — only the documentation source-of-truth needs ratification."
  - test: "Apply branch protection update to make no-lookahead-gate binding"
    expected: "Repo owner runs the `gh api -X PATCH ... required_status_checks[contexts][]=no-lookahead-gate` command from 05-05-SUMMARY's USER ACTION REQUIRED section, then verifies via `gh api .../branches/main/protection --jq '.required_status_checks.contexts'` that the output includes `no-lookahead-gate`. Until then, the workflow runs on every qualifying PR but failing runs do not block merges."
    why_human: "Requires repo-owner GitHub admin authority — same pattern as Phase 1 D-08's branch protection setup (which is also tracked as a USER ACTION in docs/branch_protection.md). The Phase 5 SC1 contract `CI-blocking gate` is structurally complete in code (workflow file + path filter + name matches required-check identifier); enforcement binding is a GitHub config change outside the code."
  - test: "Decide disposition of audit check #1 coverage-gate interaction"
    expected: "User chooses one of: (a) accept the deferred item as-is (audit's pytest subprocess truthfully reports the project-wide coverage gate firing — production behavior preserves the no-lookahead invariant via the no-lookahead-gate.yml CI workflow which is the real enforcement point), (b) authorize a follow-up plan to add `--no-cov` to the audit's pytest argv, or (c) authorize a pyproject.toml coverage-scope narrowing. Documented in deferred-items.md."
    why_human: "The deferred item is benign for the FND-04 invariant (the no-lookahead-gate CI workflow is the actual merge-blocker; the local `make backtest-audit` reporting FAIL on check 1 is a UX rough edge, not a correctness gap). Choosing the right fix depends on the user's preference between audit-CLI usability and project coverage hygiene; not an autonomous decision."
overrides: []
gaps: []
deferred:
  - truth: "Universe snapshot date <= backtest start date (audit check #3 passes without WARN)"
    addressed_in: "User-initiated backfill operation (not a future phase plan)"
    evidence: "Phase 5 deliberately ships REVISED D-16 (WARN-not-FAIL semantics) so the audit can run TODAY with the 2026-04-27 universe. The 3,769-day gap is documented in BCK-06 disclosure header and acknowledged in code via `WARN` result. A backdated universe snapshot is a one-off data operation the user controls; not a phase-5 deliverable."
  - truth: ">= 2 complete OOS windows exist in data/snapshots/ (audit check #4 PASS)"
    addressed_in: "User-initiated `make backfill-snapshots` operation"
    evidence: "Plan 05-04 shipped the `make backfill-snapshots` Makefile target + idempotent `scripts/backfill_snapshots.py`; the data-depth precondition is enabled. The actual backfill is a one-off user operation (~hours of yfinance throttle); 05-04-SUMMARY explicitly documents this as user-initiated and provides first-run guidance. The audit correctly reports FAIL pre-backfill — this is the gate working as designed."
  - truth: "Real per-playbook attribution rows (qullamaggie_continuation, minervini_vcp)"
    addressed_in: "Phase 6"
    evidence: "Phase 6 ROADMAP goal: 'Pattern Detection, Full Signal Stack & Playbook Tagging — VCP + continuation-flag + post-gap-continuation detectors, Qullamaggie Setup A scan, CANSLIM C+L+M overlay, composite playbook tagger'. Phase 6 SC3: 'Each pick declares a playbook tag from {qullamaggie_continuation, minervini_vcp, leader_hold}'. Phase 5 BCK-04 is intentionally partial per D-12 (leader_hold stub); report.py wires the metrics.per_playbook_breakdown reference so Phase 6 swaps in real rows without restructuring."
---

# Phase 5: Backtest Harness & No-Look-Ahead Gate Verification Report

**Phase Goal:** Ship vectorbt walk-forward harness, CI-blocking no-look-ahead test, slippage tiers, forensic audit CLI, per-playbook + per-regime breakdowns BEFORE Phase 6 (Pattern Detection) so the no-look-ahead invariant is enforced as a CI gate on every signals/ or backtest/ change.

**Verified:** 2026-05-16T22:25:00Z
**Status:** human_needed (5/5 SCs codebase-verified; 3 items pending user decision/action)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria + frontmatter must_haves merged)

| #   | Truth (ROADMAP Success Criterion)                                                                                                                  | Status     | Evidence                                                                                                                                                                                                                                                          |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SC1 | `tests/test_backtest_no_lookahead.py` is CI-blocking gate; perfect-foresight signal; `total_return` below noise threshold when `.shift(1)` applied; mutation-tested | ✓ VERIFIED | 2 tests pass live (`test_no_lookahead_correct_path` + `test_no_lookahead_mutation_detected`). Mutation surface at `vbt_runner.py:328-329` (`.shift(1, fill_value=False)` on entries+exits in else branch). Manual sed-removal verified by 05-02-SUMMARY produces FAIL with `Look-ahead detected: total_return=+1.640e-06 exceeds noise ceiling +8e-07`. `.github/workflows/no-lookahead-gate.yml` exists with paths filter on `signals/**` + `backtest/**` + the test file itself; `name: no-lookahead-gate` is required-check capable. (Thresholds recalibrated — see Deviations / Human Verification #1.) |
| SC2 | `make backtest` runs 3yr IS / 1yr OOS rolling walk-forward; reports OOS Sharpe distribution (min/median/max)                                       | ✓ VERIFIED | `src/screener/backtest/walkforward.py:walk_forward_windows(start, end, is_years=3, oos_years=1, slide_years=1)` (60 LOC, pure). `vbt_runner.run()` returns `BacktestResult.sharpe_min/sharpe_median/sharpe_max/n_zero_trade_windows`. Report renders per-window table + `Summary: Sharpe distribution: min=X.XX | median=X.XX | max=X.XX (n_zero_trade_windows=N)`. CLI wired: `screener backtest --start 2016-01-01 --end <today>` (W-5 options). Live smoke confirms `n_windows=7` for default range. |
| SC3 | Slippage tiers 5/15/30 bps wired into `vbt.Portfolio.from_signals` by default; zero-slippage path NOT exposed                                       | ✓ VERIFIED | `vbt_runner.py:38 SLIPPAGE_TIERS` constant defines the 3 tiers verbatim per D-11. `_build_slippage_panel` applies them via ADV np.where chain; 19-bar NaN warmup defaults to 30 bps (worst tier). 3 unit tests passing (`test_adv_above_50m_gets_5bps`, `test_adv_below_5m_gets_30bps`, `test_warmup_nan_filled_with_worst_tier`). Slippage is unconditionally applied in `Portfolio.from_signals(slippage=slip_panel, ...)`; no `_zero_slippage=True` or equivalent backdoor exposed. |
| SC4 | Backtest report disclosure header (universe source date, survivorship caveat, slippage assumptions, period selection) + per-regime + per-playbook breakdowns | ✓ VERIFIED | `src/screener/backtest/report.py:render_report` writes YAML frontmatter with all 9 keys (backtest_date, universe_source_date, survivorship_caveat, slippage_tiers, period_selection, regime_gate, playbook_attribution, preregistration, library_license) — exceeds BCK-06's 4 required fields. `_render_per_regime_section` consumes `BacktestResult.all_regime_returns` via `metrics.per_regime_breakdown` and always emits 3 canonical regime rows (Confirmed Uptrend / Uptrend Under Pressure / Correction). C-2 iter-3 WARN line (`> ⚠ No regime-attributed returns produced. See 05-RESEARCH.md §A Q11.`) emitted when input empty. Per-playbook section emits single `leader_hold` row per D-12; Phase 6 will swap in real rows via `per_playbook_breakdown` seam. Commons Clause caveat present per RESEARCH §E L3. |
| SC5 | `make backtest-audit` runs 4-check forensic checklist (no-look-ahead, preregistration hash, universe snapshot date, OOS depth) + exits non-zero on failure | ✓ VERIFIED | `cli.py:289 @app.command("backtest-audit")` filled with all 4 checks per REVISED D-16. Live smoke captured: 1 PASS (preregistration) + 1 WARN (universe gap, REVISED D-16) + 2 FAIL (no-lookahead coverage gate + empty snapshots) → `AUDIT FAILED (2 checks failed)` → exit 1. 4 CliRunner tests passing (happy path + 3 failure modes). All `subprocess.run` calls use list-form argv + `shell=False` (T-5-02). `_stub("backtest-audit")` call REMOVED. (See Human Verification #3 re: check #1 coverage-gate interaction.) |
| MH1 | C-1 fix: `_assert_nontrivial_window_count` precondition wired into BOTH no-lookahead tests BEFORE the threshold check                              | ✓ VERIFIED | `tests/test_backtest_no_lookahead.py:146` defines the helper; 2 invocations at the top of each test function. Failure message names the gap and the remedy (`Extend synthetic_ohlcv_panel start date`). Closes the iter-2 silent-zero-window backdoor. |
| MH2 | B-1 fix: All log calls in `src/screener/backtest/` use stdlib f-string form (NEVER structlog **kwargs)                                            | ✓ VERIFIED | `grep -nE '^\s*log\.(info\|warning\|error\|debug)\("[a-z_]+",' src/screener/backtest/*.py` returns empty. The stdlib `logging.Logger` requirement is enforced by D-17 (no structlog import in backtest layer). |
| MH3 | B-3 fix: per-regime breakdown is REAL 3-row table from `BacktestResult.all_regime_returns` (NOT a placeholder)                                     | ✓ VERIFIED | `_render_per_regime_section` calls `per_regime_breakdown(result.all_regime_returns)` and iterates `CANONICAL_REGIMES`; empty regimes still render with `0 | — | — | —`. Non-empty + empty smoke tests both documented in 05-03-SUMMARY. |
| MH4 | D-17 architectural invariant: `backtest/` imports only persistence + stdlib + intra-layer (no structlog, signals, indicators, config, obs, publishers, data, regime, sizing) | ✓ VERIFIED | `grep -rnE "^(from|import) (structlog\|screener\.(config\|obs\|signals\|indicators\|regime\|sizing\|publishers\|data))" src/screener/backtest/` returns empty. `tests/test_architecture.py::test_backtest_does_not_import_data_layer` passes. |
| MH5 | D-18 9-subcommand CLI surface lock preserved                                                                                                       | ✓ VERIFIED | `tests/test_cli_smoke.py::test_help_lists_all_d14_subcommands` passes. `screener --help` lists exactly 9 commands: refresh-universe, refresh-ohlcv, refresh-macro, refresh-fundamentals, score, report, journal, backtest, backtest-audit. W-5 added `--start`/`--end` as options on existing `backtest` command (not a 10th). |
| MH6 | Atomic write for `reports/backtest-YYYY-MM-DD.md` (POSIX-rename via tempfile + os.replace)                                                          | ✓ VERIFIED | `report.py:_write_text_atomic` inline-copied from `publishers/report.py` (D-17 forbids cross-layer import); same-directory tempfile + `os.replace()` pattern. |

**Score:** 5 / 5 ROADMAP Success Criteria verified · 8 / 8 requirements satisfied (BCK-04 partial-by-design per D-12) · 6 / 6 frontmatter must-haves verified.

### Deferred Items (Step 9b — addressed elsewhere)

| #   | Item                                                                                          | Addressed In                                            | Evidence                                                                                                                                                                                                  |
| --- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Universe snapshot date <= backtest start date (audit check #3 PASS without WARN)              | User-initiated backfill / acceptance of D-16 REVISED    | REVISED D-16 ships WARN-not-FAIL semantics so audit can run today; survivorship caveat in BCK-06 disclosure header; a backdated 2016 universe is a one-off data op the user controls.                       |
| D2  | >= 2 complete OOS windows exist in data/snapshots/ (audit check #4 PASS)                      | User-initiated `make backfill-snapshots` operation      | Plan 05-04 ships the script + Makefile target + first-run guidance. Actual backfill is a ~hours-long yfinance operation the user runs once; audit correctly reports FAIL pre-backfill (gate working).      |
| D3  | Real per-playbook attribution rows (qullamaggie_continuation, minervini_vcp)                  | Phase 6 (Pattern Detection)                             | Phase 6 SC3 explicitly: "Each pick declares a playbook tag from {qullamaggie_continuation, minervini_vcp, leader_hold}". Phase 5 D-12 leaves leader_hold stub; `per_playbook_breakdown` reference preserves the swap-in seam. |

### Required Artifacts (3-level verification)

| Artifact                                              | Expected                                                       | Status      | Details                                                                                                                                                                                                                         |
| ----------------------------------------------------- | -------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/screener/backtest/walkforward.py`                | `walk_forward_windows(start, end, is_years, oos_years, slide_years)` pure utility | ✓ VERIFIED  | Exists (58 LOC); imported by `vbt_runner`, `report` is decoupled; 4 walkforward tests pass; D-17 invariant intact (stdlib + pandas only).                                                                                       |
| `src/screener/backtest/metrics.py`                    | `oos_sharpe_distribution`, `per_regime_breakdown` (3-row long-format), `per_playbook_breakdown`, `CANONICAL_REGIMES` | ✓ VERIFIED  | Exists (195 LOC); imported by `vbt_runner` + `report`; smoke tests confirm 3 canonical regime rows render.                                                                                                                       |
| `src/screener/backtest/vbt_runner.py`                 | `run(start, end, *, _lookahead=False) -> BacktestResult`; `BacktestResult.all_regime_returns`; `SLIPPAGE_TIERS`; `_build_slippage_panel`; mutation surface | ✓ VERIFIED  | Exists (420 LOC); `_lookahead` keyword-only with prominent DO-NOT-REFACTOR comment block; `.shift(1, fill_value=False)` on entries+exits in else branch (line 328-329); cash_sharing+group_by+direction='longonly'+size_type='value' all verified by grep. |
| `src/screener/backtest/report.py`                     | `render_report` + atomic write + 9 YAML keys + B-3 3-row regime + C-2 WARN line + leader_hold playbook row | ✓ VERIFIED  | Exists (378 LOC); imports only stdlib + intra-layer (vbt_runner, metrics); EMPTY_REGIME_RETURNS_WARN_LINE constant emitted verbatim; smoke tests in 05-03-SUMMARY confirm empty + non-empty cases.                              |
| `tests/test_backtest_no_lookahead.py`                 | 2 real tests (correct-path + mutation-detected) with recalibrated thresholds + C-1 precondition | ✓ VERIFIED  | 297 LOC; 2 tests pass in ~3s; 0 `pytest.skip` calls; monkeypatch.setattr on `vbt_runner.read_panel` + `_load_snapshots_in_range`; thresholds 8e-7/8e-7/3.0x (recalibrated per DEVIATION-1); `_assert_nontrivial_window_count` helper invoked in both tests. |
| `tests/test_walkforward_windows.py`                   | 3+ real tests (7-window count + boundaries + empty + fixture-span override) | ✓ VERIFIED  | 87 LOC; 4 tests pass (incl. worktree's >=2 windows for conftest fixture override).                                                                                                                                              |
| `tests/test_slippage_tiers.py`                        | 3 real tests (5 bps high-ADV + 30 bps low-ADV + warmup default) | ✓ VERIFIED  | 51 LOC; 3 tests pass.                                                                                                                                                                                                            |
| `tests/test_backtest_audit.py`                        | 4 CliRunner scenarios (happy path + 3 failure modes)            | ✓ VERIFIED  | 148 LOC; 4 tests pass in 0.75s; subprocess.run + CWD both monkeypatched.                                                                                                                                                          |
| `tests/conftest.py::synthetic_ohlcv_panel`            | Session-scoped GBM fixture, seed=42, loc=0.0, 1300 bdays × 3 tickers from 2019-01-01 | ✓ VERIFIED  | Fixture present; produces 3900 rows; ~4.98 calendar years (deviation from planned 5.15yr documented in 05-00-SUMMARY but unblocking — yields ≥1 walk-forward window which satisfies the C-1 precondition).                       |
| `scripts/backfill_snapshots.py`                       | argparse main, lazy run_pipeline import, idempotent skip, best-effort failure | ✓ VERIFIED  | 104 LOC; module-top imports are stdlib + pandas only; lazy `from screener.publishers.pipeline import run_pipeline` inside `main()`; T-5-01 _DATE_RE regex; idempotent skip verified by 05-04-SUMMARY.                            |
| `Makefile::backfill-snapshots` target                 | TAB-indented `uv run python scripts/backfill_snapshots.py` recipe; in .PHONY; NOT in `all:` | ✓ VERIFIED  | `make help` shows `backfill-snapshots`. `.PHONY` includes it. `all:` target unmodified (D-02).                                                                                                                                  |
| `src/screener/cli.py @app.command("backtest")`        | Filled body with configure_logging + lazy imports + --start/--end W-5 options + terminal summary | ✓ VERIFIED  | Body at line 238; no `_stub("backtest")` remaining; `test_backtest_subcommand_no_longer_stub` passes; live smoke confirms `--start 2020-01-01 --end 2024-12-31` accepted with `n_windows=2`.                                    |
| `src/screener/cli.py @app.command("backtest-audit")`  | Filled body with 4 checks + REVISED D-16 WARN-not-FAIL on check 3 | ✓ VERIFIED  | Body at line 289; no `_stub("backtest-audit")` remaining; live `make backtest-audit` smoke produces all 4 audit_check events + audit_complete + AUDIT FAILED/PASSED line.                                                       |
| `.github/workflows/no-lookahead-gate.yml`             | Single-job workflow with paths filter + SHA-pinned actions + concurrency + permissions:read | ✓ VERIFIED  | Valid YAML; `name: no-lookahead-gate` (matches required-check identifier); paths filter on `src/screener/signals/**` + `src/screener/backtest/**` + `tests/test_backtest_no_lookahead.py`; SHA pins match ci.yml; cancel-in-progress concurrency; permissions: contents: read. |
| `.github/workflows/ci.yml`                            | UNTOUCHED                                                       | ✓ VERIFIED  | `git diff main -- .github/workflows/ci.yml` returns empty.                                                                                                                                                                       |

### Key Link Verification (must_haves wiring)

| From                                          | To                                              | Via                                                       | Status     | Details                                                                                          |
| --------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------ |
| `cli.py::backtest`                            | `vbt_runner.run`                                | lazy import inside body                                   | ✓ WIRED    | `from screener.backtest.vbt_runner import run` at line ~256 in body                              |
| `cli.py::backtest`                            | `report.render_report`                          | lazy import inside body                                   | ✓ WIRED    | `from screener.backtest.report import render_report` at line ~255 in body                        |
| `cli.py::backtest_audit`                      | `walk_forward_windows`                          | direct import (cli is composition root per ALLOWED)       | ✓ WIRED    | `from screener.backtest.walkforward import walk_forward_windows` in lazy block                   |
| `cli.py::backtest_audit`                      | `subprocess.run([pytest tests/test_backtest_no_lookahead.py])` | list-form argv (T-5-02)                             | ✓ WIRED    | Check 1 subprocess in audit body                                                                  |
| `cli.py::backtest_audit`                      | `subprocess.run([scripts/check_preregistration.py])` | list-form argv (T-5-02)                                 | ✓ WIRED    | Check 2 subprocess in audit body                                                                  |
| `report.py`                                   | `vbt_runner.SLIPPAGE_TIERS`                     | single-source-of-truth import for disclosure header       | ✓ WIRED    | `from screener.backtest.vbt_runner import BacktestResult, SLIPPAGE_TIERS`                        |
| `report.py`                                   | `metrics.per_regime_breakdown, per_playbook_breakdown` | B-3 per-regime + Phase-6 swap-in seam                | ✓ WIRED    | `from screener.backtest.metrics import CANONICAL_REGIMES, per_playbook_breakdown, per_regime_breakdown` |
| `test_backtest_no_lookahead.py`               | `vbt_runner.run` + `_load_snapshots_in_range` + `read_panel` | monkeypatch on vbt_runner-rebound symbols (Q7)        | ✓ WIRED    | 2 `monkeypatch.setattr` targets on `screener.backtest.vbt_runner.{read_panel,_load_snapshots_in_range}`; tests pass live |
| `test_backtest_no_lookahead.py`               | `conftest.py::synthetic_ohlcv_panel`            | pytest fixture injection by name                          | ✓ WIRED    | Fixture parameter declared; test pulls endpoints via `_fixture_date_range`                       |
| `.github/workflows/no-lookahead-gate.yml`     | `tests/test_backtest_no_lookahead.py`           | `uv run pytest` invocation                                | ✓ WIRED    | Final step: `uv run pytest tests/test_backtest_no_lookahead.py -v --tb=short`                    |
| `scripts/backfill_snapshots.py`               | `publishers.pipeline.run_pipeline`              | lazy import inside main()                                 | ✓ WIRED    | `from screener.publishers.pipeline import run_pipeline` inside main(); module top is stdlib+pandas only |
| `Makefile::backfill-snapshots`                | `scripts/backfill_snapshots.py`                 | `uv run python` shell-out                                  | ✓ WIRED    | Recipe verified by `make -n backfill-snapshots`                                                  |

### Data-Flow Trace (Level 4)

| Artifact                            | Data Variable                       | Source                                              | Produces Real Data | Status        |
| ----------------------------------- | ----------------------------------- | --------------------------------------------------- | ------------------ | ------------- |
| `report.py::_render_sharpe_distribution_section` | `result.windows` + summary stats    | `vbt_runner.run() → list[WindowResult]`             | Yes (real vbt.Portfolio.from_signals output) | ✓ FLOWING |
| `report.py::_render_per_regime_section` | `result.all_regime_returns`         | `vbt_runner._build_regime_returns_for_window` per OOS window (hard isinstance assert per C-2 iter 3) | Yes when snapshots have `regime_state`; empty produces verbatim WARN line | ✓ FLOWING |
| `report.py::_render_per_playbook_section` | aggregated from `result.windows`    | Phase 5 stub-routes all to `leader_hold` (D-12); Phase 6 will populate per-trade DataFrame with `playbook_tag` | Stub by-design — single leader_hold row aggregating all windows | ⚠️ STATIC (D-12 by design; Phase 6 swap-in) |
| `cli.py::backtest_audit check #4`   | `walk_forward_windows(earliest_snap, latest_snap)` | `Path("data/snapshots").glob("*.parquet").stem` filtered via `_DATE_RE` (T-5-01) | Yes when snapshots exist; empty produces FAIL | ✓ FLOWING |
| `cli.py::backtest_audit check #3`   | `Path("data/universe").glob("*.parquet")` earliest stem | Filtered via `_DATE_RE`; compared to `walk_forward_windows(2016-01-01, today)[0][0]` | Yes; PASS / WARN-with-gap-detail / FAIL-on-missing branches all live | ✓ FLOWING |

### Behavioral Spot-Checks (Step 7b)

| Behavior                                                                                   | Command                                                                                          | Result                                                                                                                                                              | Status |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| Full Phase 5 test suite passes                                                             | `uv run pytest tests/test_backtest_no_lookahead.py tests/test_walkforward_windows.py tests/test_slippage_tiers.py tests/test_backtest_audit.py tests/test_cli_smoke.py tests/test_architecture.py -v --no-cov` | 27 passed in 10.64s; no failures, no skips                                                                                                                          | ✓ PASS  |
| 9-subcommand CLI surface intact                                                            | `uv run screener --help`                                                                          | Lists exactly 9 commands: refresh-universe, refresh-ohlcv, refresh-macro, refresh-fundamentals, score, report, journal, backtest, backtest-audit                     | ✓ PASS  |
| `make backtest-audit` runs all 4 checks                                                    | `make backtest-audit`                                                                            | All 4 audit_check events emitted (1 FAIL [coverage gate, deferred], 1 PASS, 1 WARN, 1 FAIL [empty snapshots — expected]); audit_complete event; `AUDIT FAILED (2 checks failed)`; exit 1 | ✓ PASS  |
| `make help` lists `backfill-snapshots`                                                     | `make help`                                                                                       | Shows `backfill-snapshots` with description "Backfill historical snapshots 2016-01-01..today (one-off; see D-01)"                                                    | ✓ PASS  |
| Stub-call cleanup complete                                                                 | `grep -nE '_stub\(\"(backtest\|backtest-audit)\"\)' src/screener/cli.py`                          | Empty                                                                                                                                                                | ✓ PASS  |
| D-17 architecture invariant (backtest layer imports)                                       | `grep -rnE "^(from\|import) (structlog\|screener\.(config\|obs\|signals\|indicators\|regime\|sizing\|publishers\|data))" src/screener/backtest/` | Empty                                                                                                                                                                | ✓ PASS  |
| B-1 stdlib-Logger kwarg violation check                                                    | `grep -nE '^\s*log\.(info\|warning\|error\|debug)\("[a-z_]+",' src/screener/backtest/*.py`        | Empty                                                                                                                                                                | ✓ PASS  |

### Requirements Coverage

| Requirement | Source Plan(s)         | Description                                                                                                                          | Status            | Evidence                                                                                                                                                                                  |
| ----------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FND-04      | 05-00, 05-02, 05-05    | No-look-ahead mutation test + CI gate on every signals/ or backtest/ PR                                                              | ✓ SATISFIED       | `tests/test_backtest_no_lookahead.py` 2/2 pass; manual sed-removal of `.shift(1)` triggers the gate (05-02-SUMMARY); `.github/workflows/no-lookahead-gate.yml` ships with paths filter   |
| BCK-01      | 05-00, 05-01, 05-04    | Walk-forward 3yr IS / 1yr OOS rolling windows; OOS Sharpe distribution (min/median/max)                                              | ✓ SATISFIED       | `walk_forward_windows` + `vbt_runner.run` + `BacktestResult.sharpe_{min,median,max}` + per-window table in report; `make backfill-snapshots` ships the data-depth seeding mechanism      |
| BCK-02      | 05-01, 05-02           | Next-bar-open execution via `.shift(1, fill_value=False)` on entries + exits                                                          | ✓ SATISFIED       | `vbt_runner.py:328-329`; verified by FND-04 mutation test                                                                                                                                  |
| BCK-03      | 05-00, 05-01           | ADV-tiered slippage: 5 bps > $50M / 15 bps $5-50M / 30 bps < $5M; warmup defaults to 30 bps                                          | ✓ SATISFIED       | `SLIPPAGE_TIERS` constant; `_build_slippage_panel` ADV np.where chain; 3/3 slippage tests pass                                                                                            |
| BCK-04      | 05-01, 05-03           | Per-playbook attribution (CAGR / Sharpe / max DD / win rate / profit factor / expectancy split by playbook)                          | ✓ SATISFIED (partial-by-design per D-12) | Single `leader_hold` row in report; `per_playbook_breakdown` reference preserves Phase 6 swap-in seam; Phase 6 ROADMAP SC3 owns the real tagger                              |
| BCK-05      | 05-01, 05-03           | Per-regime breakdown (Confirmed Uptrend / Uptrend Under Pressure / Correction)                                                       | ✓ SATISFIED       | `_render_per_regime_section` always renders 3 canonical rows; `BacktestResult.all_regime_returns` long-format frame (B-3); C-2 WARN line on empty input                                  |
| BCK-06      | 05-03                  | Disclosure header: universe source date + survivorship caveat + slippage assumptions + period selection                              | ✓ SATISFIED       | All 9 YAML keys present (frontmatter); `SLIPPAGE_TIERS` single source of truth; Commons Clause caveat per RESEARCH §E L3                                                                |
| BCK-07      | 05-00, 05-05           | `make backtest-audit` 4-check forensic checklist; non-zero exit on any failure                                                       | ✓ SATISFIED       | All 4 checks live; REVISED D-16 check #3 WARN-not-FAIL semantics; live smoke confirms `AUDIT FAILED` exit 1 on the worktree's expected failure mix                                       |

**Coverage:** 8 / 8 requirements satisfied. No ORPHANED requirements (every ROADMAP-mapped requirement is claimed by at least one plan's frontmatter).

### Anti-Patterns Found

| File                                                | Line  | Pattern                                                                                                              | Severity | Impact                                                                                                                                                                       |
| --------------------------------------------------- | ----- | -------------------------------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/screener/backtest/report.py`                   | ~478  | `_ = per_playbook_breakdown  # noqa: F841 — referenced for Phase 6 wiring`                                            | ℹ️ Info  | Intentional dead reference to keep the import live for Phase 6 swap-in; documented in section header text and known-stubs section of 05-03-SUMMARY                          |
| `pyproject.toml + audit check #1`                   | n/a   | Coverage gate fires on subprocess `pytest tests/test_backtest_no_lookahead.py -q` invocation                          | ⚠️ Warning | Audit reports FAIL on check #1 in worktree even though the 2 underlying tests pass; production no-lookahead invariant is preserved via the no-lookahead-gate.yml workflow (the actual merge-blocker); local audit-CLI UX rough edge — deferred to follow-up plan |
| CONTEXT.md D-07                                     | n/a   | Documentation drift: D-07 still reads `abs(total_return) < 0.50` / `> 1.00`; test ships with 8e-7 ceiling + 3.0x ratio per DEVIATION-1 | ⚠️ Warning | Functional achievement is intact (mutation gate fires per manual sed verification); CONTEXT/RESEARCH docs need ratification + revision to D-07-REVISED-3 with the production-harness rationale |

No BLOCKER anti-patterns. No silent stubs in user-facing data paths. The per-playbook `leader_hold` single-row aggregation is BCK-04's intentional D-12 stub (Phase 6 supplies the real per-trade tagger).

### Human Verification Required

#### 1. Ratify D-07 recalibration (CONTEXT.md documentation drift)

**Test:** User reviews 05-02-SUMMARY's 10-seed Monte Carlo evidence table (per-seed False total_returns from -3.71e-7 to +1.18e-7; per-seed True from +1.55e-6 to +1.86e-6; ratios from 4.25× to 56.66×) and decides whether to (a) update `.planning/phases/05-backtest-harness-no-lookahead-gate/05-CONTEXT.md` D-07 to D-07-REVISED-3 with the production-harness rationale, or (b) instruct that the deviation be reverted.

**Expected:** Either D-07 is updated to read `LOOKAHEAD_FALSE_MAX_RETURN = 8e-7` / `LOOKAHEAD_TRUE_MIN_RETURN = 8e-7` / `LOOKAHEAD_RATIO_MIN = 3.0` with a note explaining why Q5's calibration (single-ticker ungrouped from_signals) diverges from the production harness (multi-ticker cash_sharing+group_by+size=0.05+size_type='value'), OR the user instructs reversion to 0.50/1.00 and triggers a fixture/harness redesign.

**Why human:** DEVIATION-1 in 05-02-SUMMARY is explicitly flagged by the executor with "User decision REQUIRED before merge." The planner literally instructed this branch ("Ping the user to update D-07 (REVISED-3) before committing"). The mutation gate IS load-bearing (manually verified by sed-removal of `.shift(1)` producing a FAIL with the expected message). Functional achievement is not in question — only the documentation source-of-truth needs ratification. This is a deliberate human-in-the-loop checkpoint, not a verification gap.

#### 2. Apply branch protection update to bind no-lookahead-gate

**Test:** Repo owner runs:
```bash
gh api -X PATCH /repos/:owner/:repo/branches/main/protection \
  -f required_status_checks[strict]=true \
  -F required_status_checks[contexts][]=lint \
  -F required_status_checks[contexts][]=typecheck \
  -F required_status_checks[contexts][]=test \
  -F required_status_checks[contexts][]=no-lookahead-gate
```
Then verifies:
```bash
gh api /repos/:owner/:repo/branches/main/protection --jq '.required_status_checks.contexts'
```

**Expected:** Verification command outputs `["lint","typecheck","test","no-lookahead-gate"]`. After this, failing `no-lookahead-gate` runs will block merges on every PR touching `signals/` or `backtest/`.

**Why human:** Requires repo-owner GitHub admin authority. Same pattern as Phase 1 D-08's branch protection setup (which is also a USER ACTION tracked in `docs/branch_protection.md`). The Phase 5 SC1 contract is structurally complete in code (workflow file exists, paths filter matches the required scope, `name:` matches the required-check identifier the gh command expects); the binding enforcement is a GitHub configuration change outside the codebase. Pending this action, the workflow will RUN on every qualifying PR but failing runs do NOT block merges.

#### 3. Decide disposition of audit check #1 coverage-gate interaction

**Test:** User reviews `.planning/phases/05-backtest-harness-no-lookahead-gate/deferred-items.md` item #2 and chooses one of:
- (a) accept as-is (the no-lookahead-gate.yml CI workflow is the real enforcement; `make backtest-audit` reporting FAIL on check 1 in worktree is a UX rough edge, not a correctness gap),
- (b) authorize a follow-up plan to add `--no-cov` to the audit's pytest argv,
- (c) authorize a `pyproject.toml` coverage-scope narrowing.

**Expected:** A documented decision (note in deferred-items.md, or a new follow-up plan stub).

**Why human:** The deferred item is benign for the FND-04 invariant. Choosing the right fix depends on user preference between audit-CLI usability and project coverage hygiene; not an autonomous decision.

### Gaps Summary

No functional gaps were found that block Phase 5 goal achievement. All 5 ROADMAP Success Criteria, all 8 requirement IDs, and all 6 frontmatter must-haves are satisfied in the codebase:

- The FND-04 mutation gate is provably live (manual sed verification + 2 passing tests + 8e-7 ceiling sitting strictly between observed pre/post mutation envelopes).
- The walk-forward harness produces real OOS Sharpe distributions (live smoke: `--start 2020-01-01 --end 2024-12-31` → `n_windows=2`).
- Slippage tiers are unconditionally applied via the `SLIPPAGE_TIERS` constant (no zero-slippage backdoor exposed).
- The disclosure header carries all required BCK-06 fields plus 4 extras.
- The audit CLI runs all 4 checks and exits non-zero on failure (live smoke confirmed).
- 9-subcommand CLI surface locked (D-18 invariant intact).
- D-17 architecture invariant intact (no forbidden imports in backtest layer).

Three items require human decision/action but do not represent verification gaps:
1. **CONTEXT.md D-07 documentation needs ratification** to reflect the empirically-recalibrated thresholds (functional behavior is correct; only the source-of-truth doc lags).
2. **Branch protection update** to bind `no-lookahead-gate` as a required check (workflow ships; binding is an admin operation outside code, same posture as Phase 1's pending D-08 USER ACTION).
3. **Audit check #1 coverage-gate UX disposition** (the audit truthfully reports the subprocess exit code; production no-lookahead enforcement is via the workflow, not via local audit invocations).

Three additional items are deferred — addressed elsewhere outside the Phase 5 scope: real per-playbook attribution (Phase 6), backdated universe snapshot (one-off data op the user controls — REVISED D-16 ships WARN-not-FAIL so audit can run today), and historical snapshot backfill execution (`make backfill-snapshots` is shipped; the actual ~hours-long backfill is user-initiated per 05-04 first-run guidance).

Phase 5 establishes the no-look-ahead invariant as a CI gate BEFORE Phase 6 lands, satisfying the phase's stated rationale.

---

_Verified: 2026-05-16T22:25:00Z_
_Verifier: Claude (gsd-verifier, Opus 4.7 1M)_
