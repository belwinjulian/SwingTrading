# Phase 5: Backtest Harness & No-Look-Ahead Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-16
**Phase:** 05-Backtest Harness & No-Look-Ahead Gate
**Areas discussed:** Walk-forward data strategy, No-look-ahead test scope, Per-playbook stub in Phase 5, Backtest report output

---

## Walk-forward data strategy

**Q1: How should the walk-forward get its historical signal data?**

| Option | Description | Selected |
|--------|-------------|----------|
| Backfill script | scripts/backfill_snapshots.py loops over historical dates, calls run_pipeline(), writes snapshots back to 2016. | ✓ |
| Cold start — accumulate forward | Ship harness now; reports 'insufficient history' until snapshots accumulate naturally (~4 years). | |
| Relax backtest/ architecture constraint | Allow backtest/ to import signals/ and indicators/ for in-line recomputation. | |

**User's choice:** Backfill script

---

**Q2: How far back should the backfill go?**

| Option | Description | Selected |
|--------|-------------|----------|
| 5 years (2021–2025) | Two market cycles; 2 complete windows. | |
| 3 years (2023–2025) | Minimal — misses 2022 bear market. | |
| 10 years (2016–2025) | Covers 3 cycles (2020 COVID, 2022 bear, 2023–2024 bull). ~6 OOS windows. | ✓ |

**User's choice:** 10 years (2016–2025)

---

**Q3: How does the backfill script integrate with make?**

| Option | Description | Selected |
|--------|-------------|----------|
| New make target: make backfill-snapshots | Separate, explicit, idempotent. Never auto-runs. | ✓ |
| Folds into make backtest as a pre-check | Auto-runs before backtest if history insufficient. Surprises user. | |

**User's choice:** New make target: make backfill-snapshots

---

**Q4: Should the backfill script reuse run_pipeline() or call score logic directly?**

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse run_pipeline() with write_report=False | Single code path, already tested. | ✓ |
| Call score logic directly | Brittle — two code paths for the same scoring logic. | |

**User's choice:** Reuse run_pipeline() with write_report=False

---

## No-look-ahead test scope

**Q1: Should the no-look-ahead mutation test call the actual harness or use a self-contained vectorbt portfolio?**

| Option | Description | Selected |
|--------|-------------|----------|
| Integration test — calls actual harness | Tests the real vbt_runner.py; removing .shift(1) causes failure. True mutation gate. | ✓ |
| Self-contained proof — synthetic vectorbt portfolio | Fast and isolated but doesn't gate vbt_runner.py itself. | |

**User's choice:** Integration test — calls actual harness

---

**Q2: What should the assertion threshold be when .shift(1) is applied correctly?**

| Option | Description | Selected |
|--------|-------------|----------|
| Total return ≤ 2× buy-and-hold | Cap allows noise; without shift, perfect-foresight produces 10–100×. | ✓ |
| Sharpe ≤ 0.5 on OOS windows | Statistically principled but sensitive to synthetic price series. | |

**User's choice:** Total return ≤ 2× buy-and-hold

---

**Q3: How is the mutation proven?**

| Option | Description | Selected |
|--------|-------------|----------|
| Two-call parameterized test | vbt_runner exposes _lookahead=True backdoor. Both calls assert correct behavior. | ✓ |
| Docstring assertion only | Comment explains scenario but no code verifies. Weaker. | |

**User's choice:** Two-call parameterized test with _lookahead backdoor

---

## Per-playbook stub in Phase 5

**Q1: What should the per-playbook breakdown look like in Phase 5 before tagging exists?**

| Option | Description | Selected |
|--------|-------------|----------|
| All picks as 'leader_hold' | Fallback tag; one row with full metrics. Honest. | ✓ |
| Three placeholder rows with null metrics | Shows schema; may be confusing. | |
| Section deferred entirely | BCK-04 doesn't ship until Phase 6. | |

**User's choice:** All picks as 'leader_hold' (Phase 4 fallback)

---

**Q2: Per-regime breakdown data source?**

| Option | Description | Selected |
|--------|-------------|----------|
| Read regime_state from snapshot Parquet | Already stored by Phase 4; no extra computation. | ✓ |
| Recompute regime from macro data | Violates backtest/ import constraint (can't import regime.py). | |

**User's choice:** Read regime_state from snapshot Parquet

---

## Backtest report output

**Q1: Where should the backtest report live?**

| Option | Description | Selected |
|--------|-------------|----------|
| reports/backtest-YYYY-MM-DD.md | File only; consistent with existing reports/ pattern. | |
| Terminal stdout only | Lightweight; no audit trail. | |
| Both terminal + file | Immediate feedback + persistent record. | ✓ |

**User's choice:** Both terminal + file (reports/backtest-YYYY-MM-DD.md)

---

**Q2: Should make backtest auto-commit the report?**

| Option | Description | Selected |
|--------|-------------|----------|
| Leave uncommitted — user commits manually | Consistent with make report behavior. User reviews first. | ✓ |
| Auto-commit with structured message | Commits to main without review. | |

**User's choice:** Leave uncommitted — user commits manually

---

**Q3: Should forensic audit block if fewer than 2 OOS windows exist?**

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — require at least 2 complete OOS windows | Prevents reporting a single-point "distribution." | ✓ |
| No minimum window gate | Allows misleading single-window Sharpe reporting. | |

**User's choice:** Yes — require at least 2 complete OOS windows

---

## Claude's Discretion

- **vectorbt `Portfolio.from_signals()` API wiring** — exact kwargs for slippage, direction, and sizing
- **OOS window alignment** — calendar year vs. trading days
- **`backtest/metrics.py` vs inline** — whether metrics go in a separate module or inline in vbt_runner.py
- **Backfill script progress reporting** — `tqdm` vs `print()` (either acceptable for one-off script)

## Deferred Ideas

- **Real per-playbook attribution** — Phase 6 adds `playbook_tag` column; harness groups by it
- **Monte Carlo simulation** — Phase 7+ if OOS Sharpe distribution needs confidence intervals
- **Walk-forward window parameter sweep** — Locked at 3yr/1yr; sweep deferred (risks IS overfit on window parameter)
- **`workflow_dispatch` for backtest-audit** — Phase 8 OPS
