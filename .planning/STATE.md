---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
last_updated: "2026-05-02T00:00:00.000Z"
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 5
  completed_plans: 0
---

# Project State

**Last updated:** 2026-05-02 (Phase 1 plans created; ready for `/gsd-execute-phase 1`)

## Project Reference

- **Project:** Momentum Swing Screener
- **Core value:** Every evening, the user opens one report and gets a small, ranked list of high-quality long candidates with playbook-specific trade plans they can execute the next morning — reliable enough to size real positions on once paper-trade validation confirms it works.
- **Current focus:** Phase 1 (Repo Skeleton & CI Hygiene) — context gathered, awaiting `/gsd-plan-phase 1`.
- **Out of scope (v1):** ML/LightGBM, Streamlit dashboard, FinBERT/Reddit sentiment, intraday/pre-market scanning, broker API, paid data feeds, PySpark, dbt+duckdb, hosted demo, options data, alt-data.
- **Audience:** Belwin (data engineer; personal-trading first; portfolio-credible second).

## Current Position

- **Milestone:** v1 (Personal-trading-ready EOD screener)
- **Phase:** Phase 1 — Repo Skeleton & CI Hygiene (5 plans committed; planning complete)
- **Plan:** 5 plans across 4 waves; ready to execute
- **Status:** Ready to run `/gsd-execute-phase 1`
- **Progress:** [░░░░░░░░] 0/8 phases complete; 0/5 Phase 1 plans complete

## Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Phases planned | 1 / 8 | Phase 1 plans created (5); Phases 2–8 still TBD |
| Plans complete | 0 / 5 | Phase 1 plans staged; execution pending |
| Requirements mapped | 64 / 64 | 100% coverage |
| Requirements completed | 0 / 64 | None shipped yet |
| Last test coverage | n/a | No code yet |
| Last lint pass | n/a | No code yet |

## Roadmap Snapshot

| # | Phase | Status | REQ-IDs |
|---|-------|--------|---------|
| 1 | Repo Skeleton & CI Hygiene | Ready to execute (5 plans) | FND-01, FND-02, FND-03 |
| 2 | Data Foundation | Not started | DAT-01..03, DAT-06..09 |
| 3 | Indicator Panel & Regime | Not started | DAT-04, IND-01..05, REG-01..04 |
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
- [ ] Execute Phase 1 (`/gsd-execute-phase 1`)
- [ ] Decide on `data/` directory commit policy (gitignore vs commit Parquet snapshots) — defer to Phase 2 planning
- [ ] Decide whether to commit `journal.sqlite` to repo (recommended yes for paper-trade history) — defer to Phase 7 planning

### Blockers

None.

## Session Continuity

### Last Session

- **Activity:** `/gsd-plan-phase 1` — research skipped (CONTEXT.md already locked D-01..D-16; greenfield repo had nothing for pattern-mapper to extract). Spawned `gsd-planner` (5 plans across 4 waves), `gsd-plan-checker` (verification passed). One non-blocking warning (D-16 widened the `backtest` ALLOWED set) was tightened in-place: `backtest` is now `{"persistence"}` only, per D-16 verbatim.
- **Outcome:** 5 plans committed. Phase 1 ready to execute.
- **Resume file:** `.planning/phases/01-repo-skeleton-ci-hygiene/01-01-pyproject-and-lockfile-PLAN.md` (Wave 1 entry point).

### Next Session

- **Recommended:** `/gsd-execute-phase 1` to run all 5 Phase 1 plans across 4 waves. The Wave 4 branch-protection task is `autonomous: false` — execution will checkpoint there for the user to run the `gh api` admin command (or click through the GitHub UI).
- **Alternative:** `cat .planning/phases/01-repo-skeleton-ci-hygiene/*-PLAN.md` to review plans, or `/gsd-review --phase 1 --all` for cross-AI peer review of the plans before execution.

---
*State initialized: 2026-04-27*
