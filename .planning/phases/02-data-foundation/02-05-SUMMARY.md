---
phase: "02-data-foundation"
plan: "05"
subsystem: "cli-wiring"
tags: ["cli", "health-gate", "ohlcv", "universe", "typer", "tests", "readme"]
dependency_graph:
  requires: ["02-03", "02-04"]
  provides: ["end-to-end-make-data-runnable", "DAT-07-gate"]
  affects: ["all-phases-that-read-ohlcv", "phase-08-cron"]
tech_stack:
  added: []
  patterns:
    - "CLI thin-wrapper: command body delegates entirely to data/ layer + persistence"
    - "monkeypatch against screener.cli.<name> attribute for module-level imports"
    - "95% health gate: (yf_ok + stooq_ok) / n_universe >= threshold; typer.Exit(code=1) below"
key_files:
  created: []
  modified:
    - src/screener/cli.py
    - tests/test_cli_smoke.py
    - README.md
decisions:
  - "refresh-universe body is a thin try/except wrapper around refresh_universe_impl; idempotent skip emits refresh_universe_skipped event; any exception exits 1 with refresh_universe_failed event"
  - "_latest_universe_snapshot is a CLI-internal helper (not in persistence) since it does glob+sort pattern over UNIVERSE_CACHE_DIR, not schema-validating read"
  - "PHASE_1_STUBS list in test_cli_smoke.py holds 7 items; D14_SUBCOMMANDS locked at 9; the two lists diverge intentionally and are co-located in the same file to keep the change visible"
  - "test_refresh_universe_success_path_smoke does NOT assert a 'snapshot_written' event because that event is emitted inside data/universe.py, not the CLI body — CLI body emits only on skip or failure"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-03"
  tasks_completed: 3
  files_modified: 3
---

# Phase 02 Plan 05: CLI Wiring + 95% Health Gate Summary

**One-liner:** CLI refresh-universe and refresh-ohlcv wired to Phase 2 data layer with a 95% combined-coverage health gate enforced by two integration tests.

## What Was Built

### Task 1: cli.py refresh-universe and refresh-ohlcv real bodies (commit 395674a)

**Stubs replaced (2 of 9 subcommands):**

`refresh_universe`:
- Calls `refresh_universe_impl(force=force, today=date.today())` — thin wrapper
- Accepts `--force` typer Option flag to override the idempotent weekly skip
- On `None` return (snapshot already exists): emits `refresh_universe_skipped` event, exits 0
- On exception: emits `refresh_universe_failed` event, `typer.Exit(code=1)`
- `configure_logging()` is the first statement of the body (Phase 1 contract preserved)

`refresh_ohlcv`:
- Accepts `--ticker <T>` typer Option flag for single-ticker debug (bypasses gate)
- Single-ticker path: `fetch_ohlcv` + `write_ohlcv_atomic` + `fetch_splits` + `write_splits_atomic`; exits 0 on success, exits 1 on exception
- Universe path: `_latest_universe_snapshot()` (CLI-internal glob helper) -> `read_universe(stem)` -> `run_with_breaker(tickers, today)`
- Gate: `(yf_ok + stooq_ok) / n_universe >= UNIVERSE_HEALTH_THRESHOLD (0.95)` - exits 0 with `health_check_passed` above; exits 1 with `health_check_failed` below
- No-universe guard: if `_latest_universe_snapshot()` returns None, emits `refresh_ohlcv_no_universe` event and exits 1

**Stubs preserved unchanged (7 of 9 subcommands):**
refresh-macro, refresh-fundamentals, score, report, journal, backtest, backtest-audit — all still call `_stub(command)` which emits `[stub]` log line and exits 0.

**New imports in cli.py:**
```python
from screener.data.ohlcv import fetch_ohlcv, fetch_splits, run_with_breaker
from screener.data.universe import iso_week_monday, refresh_universe as refresh_universe_impl
from screener.persistence import read_universe, write_ohlcv_atomic, write_splits_atomic
```

### Task 2: tests/test_cli_smoke.py extended (commit ce527a2)

**6 tests total (up from 2):**

| Test | What it locks |
|------|--------------|
| `test_help_lists_all_d14_subcommands` | UNCHANGED — D-14 surface lock; all 9 subcommands in `--help` |
| `test_each_phase1_stub_exits_zero_with_stub_log` | AMENDED — iterates only 7 PHASE_1_STUBS; asserts `[stub]` event + exit 0 |
| `test_health_gate_below_95_fails_run` | NEW — 8/10 = 0.80 < 0.95 -> exit != 0 + `health_check_failed` with success_count/universe_size/threshold |
| `test_health_gate_above_95_passes_run` | NEW — 10/10 = 1.0 >= 0.95 -> exit 0 + `health_check_passed` event |
| `test_refresh_universe_idempotent_skip_smoke` | NEW — impl returns None -> `refresh_universe_skipped` event + exit 0 |
| `test_refresh_universe_success_path_smoke` | NEW — impl returns Path -> exit 0, no skip/fail events |

**Test approach:** monkeypatch against `screener.cli._latest_universe_snapshot`, `screener.cli.read_universe`, `screener.cli.run_with_breaker`, `screener.cli.refresh_universe_impl` — module-level imports in cli.py make this the correct idiom. CliRunner in-process (no subprocess).

**D14_SUBCOMMANDS list:** unchanged (9 items). PHASE_1_STUBS list: new (7 items, excludes refresh-universe and refresh-ohlcv).

### Task 3: README.md Data layer section (commit e6cf0aa)

New `## Data layer` section inserted between `## Project layout` and `## References` with 5 sub-sections:

1. **Layout** — per-ticker path `data/ohlcv/<TICKER>/{prices,splits}.parquet`; universe snapshot `data/universe/<iso-monday>.parquet`; annotated directory tree
2. **Backfill** — ~30-60 min, ~5 GB first run; ~17 min nightly incremental; start `2005-01-01`
3. **Stooq fallback** — circuit-breaker at 50-ticker probe if < 80% yf success; 95% combined gate still applies; reference to D-12
4. **Survivorship-bias disclosure** — current-R1000 only; +1-2% CAGR estimated bias; weekly snapshot mitigation; link to `CLAUDE.md §5.3`
5. **Atomic writes** — `tempfile + os.replace()` POSIX-atomic contract; reference to `persistence.py::_write_parquet_atomic`

## 95% Health Gate Logic

The gate computation lives entirely in `refresh_ohlcv()` in `cli.py`:

```python
yf_ok, stooq_ok, failed = run_with_breaker(tickers, today)
combined_ok = yf_ok + stooq_ok
ratio = combined_ok / n_universe if n_universe > 0 else 0.0
threshold = settings.UNIVERSE_HEALTH_THRESHOLD  # default: 0.95

if ratio < threshold:
    log.error("health_check_failed", success_count=combined_ok, ...)
    raise typer.Exit(code=1)

log.info("health_check_passed", success_count=combined_ok, ...)
```

Where `UNIVERSE_HEALTH_THRESHOLD` is read from `screener.config.Settings` (default 0.95, D-20). The gate uses `run_with_breaker`'s returned counters — CLI never inspects individual ticker results, it only sees the aggregate.

## Phase 2 End-to-End Status

Phase 2 is now end-to-end runnable from `make data`:

```
make data  ==  screener refresh-universe
              + screener refresh-ohlcv
              + screener refresh-macro    (stub)
              + screener refresh-fundamentals  (stub)
```

The first two are real; the last two are Phase-1 stubs that exit 0. A fresh clone can run `screener refresh-universe && screener refresh-ohlcv` against a live network and either succeed (writing universe + per-ticker artifacts) or fail loud.

Manual-only verifications in `02-VALIDATION.md` remain to be exercised before `/gsd-verify-work`:
- Live `screener refresh-universe` against iShares endpoint
- Live `screener refresh-ohlcv` on a representative subset (5 tickers)
- Health gate actual threshold test against a degraded Yahoo session

## Deviations from Plan

None — plan executed exactly as written. The `data/ohlcv/<TICKER>` grep requirement was resolved by adding an explicit prose sentence in the Layout sub-section alongside the directory tree (the tree itself uses `AAPL/` as the example).

## Known Stubs

The following Phase-1 stubs remain in `cli.py` and are intentional — each will be filled in by its owning phase:

| Stub | Phase |
|------|-------|
| `refresh-macro` | Phase 3 (macro/regime inputs) |
| `refresh-fundamentals` | Phase 6 (CANSLIM + EDGAR) |
| `score` | Phase 4 (composite scorer) |
| `report` | Phase 4 (Markdown report) |
| `journal` | Phase 7 (paper-trade journal) |
| `backtest` | Phase 5 (vectorbt walk-forward) |
| `backtest-audit` | Phase 5 (no-look-ahead forensics) |

These stubs are tracked and visible via `test_each_phase1_stub_exits_zero_with_stub_log` — any phase that fills in a stub must also update the PHASE_1_STUBS list in test_cli_smoke.py.

## Self-Check: PASSED

Checked commits exist: 395674a feat(02-05): wire refresh-universe + refresh-ohlcv real bodies + 95% health gate
Checked commits exist: ce527a2 test(02-05): extend CLI smoke tests with health-gate + refresh-universe coverage
Checked commits exist: e6cf0aa docs(02-05): add README Data layer section with layout + backfill + fallback + disclosure

Checked files exist:
- src/screener/cli.py: FOUND
- tests/test_cli_smoke.py: FOUND
- README.md: FOUND

All 6 tests in test_cli_smoke.py pass (verified).
Full test suite: 39 passed, 2 skipped.
