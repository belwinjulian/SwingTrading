---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
stopped_at: null
last_updated: "2026-05-10T22:00:00.000Z"
progress:
  total_phases: 8
  completed_phases: 3
  total_plans: 20
  completed_plans: 16
  percent: 55
---

# Project State

**Last updated:** 2026-05-10 (Phase 4 PLANNED — 5 plans across 4 waves; verifier passed after revision-2; ready to execute)

## Project Reference

- **Project:** Momentum Swing Screener
- **Core value:** Every evening, the user opens one report and gets a small, ranked list of high-quality long candidates with playbook-specific trade plans they can execute the next morning — reliable enough to size real positions on once paper-trade validation confirms it works.
- **Current focus:** Phase 04 — trend-template-composite-skeleton-first-report
- **Out of scope (v1):** ML/LightGBM, Streamlit dashboard, FinBERT/Reddit sentiment, intraday/pre-market scanning, broker API, paid data feeds, PySpark, dbt+duckdb, hosted demo, options data, alt-data.
- **Audience:** Belwin (data engineer; personal-trading first; portfolio-credible second).

## Current Position

Phase: 02 (data-foundation) — COMPLETE
Phase: 03 (indicator-panel-&-regime) — COMPLETE (all 5 plans, 2026-05-10)
Phase: 04 (trend-template-composite-skeleton-first-report) — PLANNED, ready to execute (5 plans / 4 waves)

- **Milestone:** v1 (Personal-trading-ready EOD screener)
- **Phase:** 4 (ready to execute)
- **Plan:** 15 / 20 executed (Phase 4 plans landed; execution pending)
- **Status:** Ready to execute Phase 4
- **Progress:** [██████████░░░░░] 50%

### Phase 3 Plan Summary

| Wave | Plan | Objective |
|------|------|-----------|
| 1 | 03-01 | Settings + 5 pandera schemas + persistence helpers (read/write_macro + read/write_rs_snapshot) |
| 2 | 03-02 | Macro data layer (SPY/QQQ/^VIX/$NYAD/FRED) + refresh-macro CLI + make macro |
| 2 | 03-03 | Indicator panel — pure-fn trend/volatility/volume/RS + build_panel orchestrator |
| 3 | 03-04 | Regime module (compute_for_date, build_history, _classify_state, _regime_score) |
| 3 | 03-05 | SMA-not-EMA CI grep gate + 3 golden-file regime tests (2008-Q4 / 2020-Q1 / 2022-H1) |

### Phase 4 Plan Summary (2026-05-10)

| Wave | Plan | Objective |
|------|------|-----------|
| 1 | 04-01 | Foundation — extend `indicators/trend.py` with `high_52w`/`low_52w`, extend `Settings` (REPORT_TOP_N, TREND_TEMPLATE_PASS_RATE_WARN/HARD_FAIL), `RankingSnapshotSchema` + `write_snapshot_atomic` in persistence, conftest fixtures, `data/snapshots/` .gitignore + .gitkeep |
| 2 | 04-02 | `signals/minervini.py` — pure `passes_trend_template(panel)` returning `passes_trend_template: bool` + `trend_template_score: int (0–8)` per ticker; 5 tests (8 conditions, score dtype, NaN-safe short history, pass-rate smoke, EMA-gate non-regression) |
| 2 | 04-03 | `signals/composite.py` — `DEFAULT_WEIGHTS: Final[dict]` (RS 25 / Trend 20 / Pattern 20 / Volume 10 / Earnings 15 / Catalyst 10), `PHASE_4_ZEROED` set, weights-iterating `score(panel, weights)` (D-13 M2 seam); 7 tests incl. unknown-key, sum=1.0, [0,100] property, zeroed components, extension seam (`ml_probability`) |
| 3 | 04-04 | Publishers — `pipeline.run_pipeline` orchestrator + `apply_regime_gate` (D-03 soft) + `validate_run` (D-08 hard fail); `snapshot.write_snapshot` (atomic); `report.render_report` (regime banner / top-N / per-pick blocks / data-quality footer; pivot zone with 3rd "unknown" state for NaN); 15 tests across pipeline/snapshot/report |
| 4 | 04-05 | Wiring + freeze — `cli.score`/`cli.report` bodies (no 10th subcommand — D-14 lock preserved), `scripts/check_preregistration.py` (grep-diff CI gate), `docs/strategy_v1_preregistration.md` (weights table + freeze date + `Frozen at commit: <sha>` two-commit ceremony), CI step in `.github/workflows/ci.yml`, 3 preregistration tests + 1 D-08 CliRunner integration test. **Final task uses `checkpoint:human-verify` for the freeze-commit hash dance.** |

## Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Phases complete | 3 / 8 | Phase 1 ✓ 2026-05-02; Phase 2 ✓ 2026-05-03; Phase 3 ✓ 2026-05-10 |
| Plans complete | 15 / 15 (Phases 1+2+3) | 01-01..01-05, 02-01..02-05, 03-01..03-05 all shipped |
| Requirements mapped | 64 / 64 | 100% coverage |
| Requirements completed | 21 / 64 | FND-01..03, DAT-01..04, DAT-06..09, IND-01..05, REG-01..04 |
| Last test run | 72 passed, 2 skipped | `pytest -m "not slow and not integration"` 2026-05-10 |
| Last lint pass | clean | ruff + mypy passing |
| Phase 01 P04 | 2min | 2 tasks | 2 files |
| Phase 01 P05 | 3min | 2 tasks | 6 files |
| Phase 02 P02 | 10min | 3 tasks | 5 files |

## Roadmap Snapshot

| # | Phase | Status | REQ-IDs |
|---|-------|--------|---------|
| 1 | Repo Skeleton & CI Hygiene | ✓ Complete (verified 2026-05-02; 4/4 must-haves) | FND-01, FND-02, FND-03 |
| 2 | Data Foundation | ✓ Complete (verified 2026-05-03; 7/7 must-haves) | DAT-01..03, DAT-06..09 |
| 3 | Indicator Panel & Regime | ✓ Complete (2026-05-10; 5/5 plans; 72 tests green) | DAT-04, IND-01..05, REG-01..04 |
| 4 | Trend Template, Composite Skeleton & First Report | Not started | FND-05, SIG-01, SIG-04, OUT-01..03 |
| 5 | Backtest Harness & No-Look-Ahead Gate | Not started | FND-04, BCK-01..07 |
| 6 | Pattern Detection, Full Signal Stack & Playbook Tagging | Not started | DAT-05, PAT-01..06, SIG-02, SIG-03, CMP-01..05, CAT-01..04 |
| 7 | Sizing Finalization & Paper-Trade Journal | Not started | SIZ-01..05, OUT-04..06 |
| 8 | GitHub Actions Cron & Operations | Not started | OPS-01..05 |

## Accumulated Context

### Decisions Locked at Initialization

1. **Per-pick playbook tagging is the v1 differentiator.** Composite score + playbook tag + per-playbook trade plan is the core feature; protected from compression in every phase.
2. **Rules-based composite is authoritative in v1.** ML probability is M2; the composite scorer in Phase 4 takes a weights dict to keep the M2 extension seam clean.
3. **Free-data, $0 budget; survivorship bias accepted and disclosed.** Mitigated going forward by weekly universe snapshots starting Phase 2.
4. **EOD-only workflow.** No intraday or pre-market in v1. Setup B is approximated as a D+1 post-gap-continuation detector.
5. **SMAs (not EMAs) for the Trend Template.** Enforced by a CI grep starting Phase 3.
6. **Signals execute at next-bar open.** Enforced by the no-look-ahead test in Phase 5; mutation-tested.
7. **Fundamentals lag 45 days post-quarter-end** before being treated as known. Enforced at the data layer in Phase 6.
8. **`signals/composite.py` is the single M2 extension point.** v1 architecture protects this seam.
9. **Journal schema is the v2 ML training contract** and is frozen at Phase 7.

### Composite Score Weights (Pre-Registration Targets)

To be committed to `docs/strategy_v1_preregistration.md` at Phase 4 completion, then frozen for v1:

| Component | Weight |
|-----------|--------|
| RS percentile | 25% |
| Trend Template (0–8 normalized) | 20% |
| Pattern (VCP/flag tightness) | 20% |
| Volume confirmation | 10% |
| Earnings momentum (CANSLIM C+A) | 15% |
| Catalyst presence | 10% |

These are starting points, not validated. Walk-forward results inform M2 weight tuning, not v1 changes.

### Open Questions / Calibration Targets

- **Playbook tie-breaking thresholds** (Qullamaggie vs Minervini VCP vs leader-hold) are heuristic defaults pending paper-trade validation.
- **VCP detection thresholds** (CLAUDE.md §13.4 starting values) tuned via golden-file tests, not against backtest results.
- **Post-gap-continuation D+1 detection** is novel — concrete entry rule (gap > 8% on day 0, day-1 close in upper third of range, day-2 entry) finalized in Phase 6 planning.
- **Leader-hold playbook** is the loosest defined — may collapse to "informational only" after paper trading.
- **Stooq full-Russell-1000 per-ticker coverage** unverified; treat as best-effort fallback.

### Todos

- [x] Phase 1 context gathered (`/gsd-discuss-phase 1`) — 2026-04-28 → `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md`
- [x] Plan Phase 1 (`/gsd-plan-phase 1`) — 2026-05-02 → 5 plans (`01-01..01-05-*-PLAN.md`), 4 waves; verifier passed with one warning (D-16 widening) which was tightened in revision (backtest restricted to `persistence`-only per D-16 verbatim)
- [x] Execute Phase 1 (`/gsd-execute-phase 1`) — 2026-05-02; all 5 plans committed; CI workflow + pre-commit + branch-protection doc shipped (01-05)
- [ ] **USER ACTION:** Apply branch protection on `main` via the `gh api` command in `docs/branch_protection.md` (or web-UI fallback). Verify with `gh api /repos/:owner/:repo/branches/main/protection --jq '.required_status_checks.contexts'` returning `["lint","typecheck","test"]`. This closes FND-03's binding-gate semantics and Phase 1.
- [ ] Decide on `data/` directory commit policy (gitignore vs commit Parquet snapshots) — defer to Phase 2 planning
- [ ] Decide whether to commit `journal.sqlite` to repo (recommended yes for paper-trade history) — defer to Phase 7 planning

### Blockers

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260503-q01 | Fix DAT-08: add fetch_splits + write_splits_atomic to Stooq else-branch in run_with_breaker | 2026-05-03 | afe55fb | [260503-q01-fix-dat-08-stooq-splits](.planning/quick/260503-q01-fix-dat-08-stooq-splits/) |

## Session Continuity

### Last Session

- **Activity:** `/gsd-execute-phase 2` Plan 02-02 — extended Settings to 15 fields (8 D-20 data-layer fields), added pandas-datareader>=0.10 dep, updated mypy strict files list and ignore_missing_imports, amended .gitignore with D-19 carve-out (prices.parquet ignored, splits.parquet + universe/*.parquet committed), added .gitkeep anchors.
- **Outcome:** 3 commits (f7f5de7 Settings D-20, c9cc323 pandas-datareader + mypy, 88087dc .gitignore carve-out). Tests 5 passed.
- **Resume file:** None
- **Stopped at:** context exhaustion at 75% (2026-05-03)

### Next Session

- **First, user action:** Run the `gh api` command in `docs/branch_protection.md` (or click through `/settings/branches`). Verify with the documented `gh api ... --jq '.required_status_checks.contexts'` call.
- **Then:** `/gsd-discuss-phase 2` to gather context for the Data Foundation phase (universe builder, OHLCV cache, macro/regime-input ingest, EDGAR identity setup, requests-cache + tenacity wiring, weekly universe snapshots to mitigate survivorship bias going forward).
- **Phase 2 reminder:** When API keys (`FINNHUB_API_KEY`, `FRED_API_KEY`, `EDGAR_IDENTITY`) land in CI, add them as GitHub Actions `secrets:` and reference via `${{ secrets.X }}`. Never `echo` them. The Phase 1 workflow has `permissions: contents: read` and uses no secrets, which is correct for now.

---
*State initialized: 2026-04-27*
