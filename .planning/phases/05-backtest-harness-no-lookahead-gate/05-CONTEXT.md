# Phase 5: Backtest Harness & No-Look-Ahead Gate - Context

**Gathered:** 2026-05-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 delivers four interconnected pieces that must ship BEFORE Phase 6 (Pattern Detection) to enforce the no-look-ahead invariant as a CI gate:

1. **Historical snapshot backfill** — `scripts/backfill_snapshots.py` + `make backfill-snapshots`. Recomputes and writes `data/snapshots/YYYY-MM-DD.parquet` going back to 2016-01-01 (10 years), seeding the walk-forward harness with usable IS/OOS window depth.

2. **vectorbt 1.0 walk-forward harness** — `backtest/vbt_runner.py` implementing `run(start, end, _lookahead=False)`. Reads `data/snapshots/*.parquet` for signals and `data/` OHLCV for execution. Enforces next-bar-open execution via `.shift(1)`. Outputs OOS Sharpe distribution (min/median/max) across all complete 3yr IS / 1yr OOS windows.

3. **CI-blocking no-look-ahead mutation test** — `tests/test_backtest_no_lookahead.py`. Integration test calling the actual harness with a perfect-foresight signal. Two-call parameterized: shifted (passes ≤ 2× BH) and unshifted (_lookahead=True, proves the gate works). Runs on every PR touching `signals/` or `backtest/`.

4. **Forensic audit CLI** — `make backtest-audit` wires up the `backtest-audit` stub in `cli.py`. Runs 4 checks: (a) no-look-ahead test passing, (b) preregistration hash match, (c) universe snapshot date ≤ backtest start date, (d) ≥ 2 complete OOS windows exist. Exits non-zero if any check fails.

Requirements covered: **FND-04** (no-look-ahead mutation test + CI gate), **BCK-01** (walk-forward OOS Sharpe distribution), **BCK-02** (next-bar open execution), **BCK-03** (slippage tiers), **BCK-04** (per-playbook attribution — stubbed as leader_hold), **BCK-05** (per-regime breakdown), **BCK-06** (disclosure header), **BCK-07** (forensic audit CLI).

</domain>

<decisions>
## Implementation Decisions

### Walk-forward data strategy (BCK-01)

- **D-01: Backfill script at `scripts/backfill_snapshots.py`.** Loops over trading dates from 2016-01-01 to present, calling `run_pipeline(date, write_report=False)` from `publishers/pipeline.py` for each date. Writes `data/snapshots/YYYY-MM-DD.parquet`. Idempotent — skips dates where snapshot already exists. The script lives outside `backtest/` so it can import `signals/` and `indicators/` freely through the pipeline.

- **D-02: `make backfill-snapshots` is a separate Makefile target.** Never runs automatically as part of `make backtest`. User calls it once to seed historical data, then periodically if the cache drifts. Not a CLI subcommand — preserves the 9-subcommand lock.

- **D-03: Walk-forward window configuration.** 3-year IS / 1-year OOS rolling windows, sliding by 1 year per step. With 10 years of backfill (2016–2025): ~6 complete OOS windows (2019, 2020, 2021, 2022, 2023, 2024). OOS Sharpe distribution reported as `(min, median, max)` across all windows — never a single-period Sharpe.

- **D-04: Harness reads `data/snapshots/*.parquet` for signals.** The `passes_trend_template`, `composite_score`, `regime_state`, `regime_score` columns are already written there by Phase 4's publisher. OHLCV for execution prices is read via `persistence.read_panel()`. No fresh signal recomputation in the harness — avoids look-ahead and preserves point-in-time integrity.

### No-look-ahead mutation test (FND-04, BCK-02)

- **D-05: Integration test — calls the actual `backtest.vbt_runner.run()`.** `tests/test_backtest_no_lookahead.py` writes synthetic OHLCV (250 bars, deterministic seed) to a temp directory, overrides `persistence.read_panel()` to return it, and calls `vbt_runner.run()` with a perfect-foresight signal.

- **D-06: Perfect-foresight signal = enter when next-day return > 0.** At bar t, signal = `(close[t+1] - close[t]) / close[t] > 0`. When `.shift(1)` is applied in the harness, the signal becomes 2-bar delayed → negates the foresight advantage → total return ≈ random/market.

- **D-07 (REVISED 2026-05-16 from research): Absolute return thresholds replace "≤ 2× BH".** When `_lookahead=False`, assert `abs(total_return) < 0.50`. When `_lookahead=True`, assert `total_return > 1.00`. 4× separation between the two regimes, robust across 10 GBM seeds. The original "≤ 2× BH" wording was flaky — 10-seed Monte Carlo on the planned synthetic OHLCV (GBM, 250 bars) showed the shifted-foresight strategy still earns ~+25% on near-zero-drift markets due to GBM autocorrelation, so the BH-relative bound did not separate cleanly from the foresight regime. See 05-RESEARCH.md §B Q5 for the experiment.

- **D-08: Two-call parameterized test proves the mutation.** `vbt_runner.run()` accepts a `_lookahead: bool = False` test-only parameter. When `True`, `.shift(1)` is bypassed. Test call 1: `_lookahead=False` → assert `total_return ≤ 2× BH` (PASS). Test call 2: `_lookahead=True` → assert `total_return > 2× BH` (PASS — proves that removing the shift causes dramatic outperformance). Removing `.shift(1)` from the production harness is equivalent to hardcoding `_lookahead=True`, which the second assertion would then fail.

- **D-09: CI gate — path filter on `signals/` or `backtest/`.** `.github/workflows/ci.yml` runs `test_backtest_no_lookahead.py` on every PR touching `src/screener/signals/**` or `src/screener/backtest/**`. Already the standard pytest invocation; path filter ensures it runs even when full test suite isn't triggered.

### Slippage tiers (BCK-03)

- **D-10: ADV computed in harness from raw OHLCV via `persistence.read_panel()`.** ADV = 20-day rolling mean of `(close × volume)`. Computed per-ticker per-date within `backtest/`. Consistent with `backtest/` importing only `persistence` — no `indicators/` import needed.

- **D-11: Slippage tier mapping (verbatim from BCK-03):**
  - ADV > $50M → 5 bps
  - $5M ≤ ADV ≤ $50M → 15 bps
  - ADV < $5M → 30 bps
  - Zero-slippage path is NOT exposed as a public API. Slippage is always applied.

### Per-playbook and per-regime breakdowns (BCK-04, BCK-05)

- **D-12: Phase 5 treats all picks as `leader_hold` (the documented fallback tag).** Report shows one per-playbook row: `leader_hold` with full CAGR / Sharpe / max DD / win rate / profit factor / expectancy. Phase 6 adds real tagging; the per-playbook section gains `qullamaggie_continuation` and `minervini_vcp` rows without structural refactor.

- **D-13: Per-regime breakdown reads `regime_state` from `data/snapshots/*.parquet`.** `regime_state` ∈ {`Confirmed Uptrend`, `Uptrend Under Pressure`, `Correction`} is already written by Phase 4's snapshot publisher (confirmed in `src/screener/publishers/snapshot.py` docstring). Harness groups trade outcomes by `regime_state` across OOS windows. No extra imports.

### Backtest report output (BCK-06)

- **D-14: Terminal summary + `reports/backtest-YYYY-MM-DD.md` file.** `make backtest` prints a compact summary to stdout AND writes the full report with disclosure header, OOS Sharpe distribution table, per-regime breakdown, and per-playbook breakdown to `reports/backtest-YYYY-MM-DD.md`.

- **D-15: User commits the report manually.** `make backtest` does not auto-commit. Consistent with how Phase 4's `make report` works. User reviews, then `git add reports/backtest-*.md && git commit`.

### Forensic audit (BCK-07)

- **D-16: `make backtest-audit` runs 4 checks (exits non-zero if any fails):**
  1. No-look-ahead test passes (`pytest tests/test_backtest_no_lookahead.py -q`)
  2. Weight preregistration hash match — `scripts/check_preregistration.py` confirms `DEFAULT_WEIGHTS` in `signals/composite.py` matches `docs/strategy_v1_preregistration.md` (Phase 4 D-09 script, already CI-gated)
  3. Universe snapshot date check (REVISED 2026-05-16 from research): **earliest available** `data/universe/*.parquet` stem ≤ earliest IS window start. Original wording ("latest snapshot ≤ start") would never pass until a backdated 2016 snapshot exists; relaxing to "earliest available" lets the audit run today and the survivorship caveat is honestly recorded in the BCK-06 disclosure header. The audit emits a WARN line naming the earliest snapshot date and the gap to the IS start. See 05-RESEARCH.md §D for the gap analysis.
  4. ≥ 2 complete OOS windows exist (requires ≥ 4 years of `data/snapshots/` coverage). Failure message: `"Insufficient OOS history: N complete windows found, 2 required."`

### Carried-forward constraints (not re-discussed)

- **D-17 (from Phase 1 D-16): `backtest/` imports only `persistence` from internal modules.** Architecture test `ALLOWED["backtest"] = {"persistence"}`. No `signals/`, `indicators/`, `config/`, `obs/` — use stdlib `logging` inside `backtest/` if needed. The `_lookahead` parameter stays in `vbt_runner.py`'s own internal code path.
- **D-18 (from Phase 1 D-14): 9-subcommand CLI surface locked.** `backtest` and `backtest-audit` stubs already exist — Phase 5 fills in their bodies. No 10th subcommand added.
- **D-19 (from Phase 4 D-14 via CLAUDE.md): Signals execute at next-bar open.** Enforced by `.shift(1)` in `vbt_runner.py`. The no-look-ahead test (D-05..D-09) is the CI enforcement mechanism.

### Claude's Discretion

- **vectorbt 1.0 `Portfolio.from_signals()` API wiring:** Planner decides exact kwargs for slippage, direction, and sizing. The `slippage` parameter accepts a per-trade float — planner resolves how to pass a per-ticker ADV-tiered value (likely a pre-computed slippage Series aligned with signals).
- **OOS window alignment:** Planner decides whether windows roll by calendar year or by trading days. Calendar year is simpler and aligns with ROADMAP language.
- **`backtest/metrics.py` vs inline:** Planner decides whether OOS Sharpe / max DD / etc. metrics go in a separate `backtest/metrics.py` or inline in `vbt_runner.py`. Given the import constraint, either is fine.
- **Backfill script progress reporting:** Planner decides whether `scripts/backfill_snapshots.py` uses `tqdm` or plain `print()` for progress. `print()` is acceptable for a one-off script.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 5: Backtest Harness & No-Look-Ahead Gate" — goal, success criteria 1–5, phase rationale ("Phase 4 ships BEFORE Phase 6")
- `.planning/REQUIREMENTS.md` §FND-04 — no-look-ahead mutation test + CI gate requirement
- `.planning/REQUIREMENTS.md` §BCK-01..BCK-07 — all backtest requirements verbatim

### Testing rules (MUST follow)
- `CLAUDE.md` §"Testing Rules" — "YOU MUST run `pytest tests/test_backtest_no_lookahead.py` after any change to `signals/` or `backtest/`" — this is the Phase 5 CI gate requirement
- `CLAUDE.md` §"Critical Pitfalls" pitfall #7 — survivorship-biased Sharpe must be disclosed; BCK-06 disclosure header is the mechanism

### Backtest methodology
- `docs/backtesting.md` — vectorbt patterns, mandatory hygiene checklist, walk-forward + Monte Carlo patterns, metrics table, decile evaluation approach

### Architecture constraints
- `tests/test_architecture.py` — `ALLOWED["backtest"] = {"persistence"}` verbatim. Read lines 30–45 for the exact enforcement logic. `backtest/` MUST NOT import from `signals/`, `indicators/`, `config/`, `obs/`, `data/`, or any other internal layer.
- `src/screener/cli.py` — 9-subcommand surface locked (D-18). `backtest` and `backtest-audit` stubs on lines ~160–175 are the Phase 5 entry points. No new subcommands.

### Prior phase decisions (carry-forward constraints)
- `.planning/phases/04-trend-template-composite-skeleton-first-report/04-CONTEXT.md` — D-09 (`scripts/check_preregistration.py` already exists for hash match), D-10 (preregistration doc + git hash), D-03 (regime gate is soft multiplication), D-14 (next-bar open execution seam)
- `.planning/phases/03-indicator-panel-regime/03-CONTEXT.md` — D-10/D-11 (RS snapshots in `data/rs_snapshots/YYYY-MM-DD.parquet`, read via `persistence.read_rs_snapshot()`)
- `.planning/phases/01-repo-skeleton-ci-hygiene/01-CONTEXT.md` — D-16 (architecture test enforcement), D-14 (9-subcommand CLI surface locked)

### Existing pipeline code for backfill script
- `src/screener/publishers/pipeline.py` — `run_pipeline(date, write_report=False)` is the entry point the backfill script reuses. Read to understand how it orchestrates scoring + snapshot write.
- `src/screener/publishers/snapshot.py` — snapshot schema: shows `regime_state`, `regime_score` are already written to `data/snapshots/*.parquet`

### Preregistration (forensic audit check #2)
- `docs/strategy_v1_preregistration.md` — the hash-bearing preregistration doc. Forensic audit verifies `DEFAULT_WEIGHTS` in `signals/composite.py` matches this doc.
- `scripts/check_preregistration.py` — existing Phase 4 script for hash matching; forensic audit calls it.

### Stack reference
- `docs/tech-stack.md` — vectorbt 1.0.x; Apache 2 + Commons Clause license note; confirm API stability
- `CLAUDE.md` §"Library Quick-Reference" — vectorbt 1.0.x is the walk-forward engine

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/screener/publishers/pipeline.py:run_pipeline()` — the backfill script's primary reuse point. Accepts a date string and `write_report: bool`; handles scoring + snapshot write. Already tested.
- `src/screener/publishers/snapshot.py` — confirms `regime_state` and `regime_score` are in the snapshot schema. Harness reads these columns for per-regime breakdown (D-13).
- `src/screener/persistence.py` — `read_panel(date)` for OHLCV, `read_rs_snapshot(date)` for RS. Harness uses these exclusively for data reads (D-04, architecture constraint D-17).
- `scripts/check_preregistration.py` — Phase 4 preregistration hash script; forensic audit (D-16) calls it directly without reimplementing.
- `src/screener/backtest/__init__.py` — docstring already documents the import constraint: "persistence + stdlib only — no data, no config, no obs, no network." Phase 5 creates `backtest/vbt_runner.py`, `backtest/walkforward.py`, `backtest/metrics.py` under this constraint.

### Established Patterns
- **Stub bodies in `cli.py`:** `backtest` and `backtest-audit` subcommands exist as `_stub()` no-ops. Phase 5 replaces these with real implementations — same pattern as Phase 4 replaced `score` and `report` stubs.
- **Atomic write via `persistence._write_parquet_atomic()`:** Used for all Parquet writes. Backfill script follows the same pattern when writing historical snapshots.
- **Idempotent incremental append:** Backfill checks existing snapshots (`data/snapshots/`) and skips dates already present — same pattern as Phase 2 OHLCV incremental append (Phase 2 D-07).

### Integration Points
- **`data/snapshots/*.parquet` → `backtest/vbt_runner.py`:** Primary signal source. Phase 4 writes daily; Phase 5 backfill extends to 2016. Harness reads all files in the date range, assembles a panel, extracts `passes_trend_template` as the entry signal.
- **`backtest/vbt_runner.run()` → `tests/test_backtest_no_lookahead.py`:** Test calls the real harness with synthetic data. The `_lookahead=True/False` backdoor parameter must be present in `vbt_runner.run()`.
- **`make backtest-audit` → `scripts/check_preregistration.py` + `pytest`:** Forensic audit orchestrates multiple existing tools, not a reimplementation.
- **`src/screener/cli.py` `backtest-audit` stub → Phase 5 body:** The audit body calls `subprocess` to run pytest + the preregistration check + its own disk checks, then reports pass/fail per check. Exits non-zero on any failure.

### Architecture constraint (critical)
- `tests/test_architecture.py` ALLOWED dict: `"backtest": {"persistence"}`. vectorbt is a third-party import (not a screener internal), so importing `vectorbt` inside `backtest/` passes the test. The constraint only applies to `screener.*` imports. stdlib imports (e.g., `logging`, `os`, `datetime`) are also allowed.

</code_context>

<specifics>
## Specific Ideas

- **Backfill date range:** `2016-01-01` to `today` (10 years). Covers 2022 bear market, 2020 COVID crash, and 2023–2024 bull run. Enough for ~6 complete 3yr IS / 1yr OOS windows.
- **Walk-forward window example:** IS 2016-2018 → OOS 2019; IS 2017-2019 → OOS 2020; IS 2018-2020 → OOS 2021; IS 2019-2021 → OOS 2022; IS 2020-2022 → OOS 2023; IS 2021-2023 → OOS 2024.
- **OOS Sharpe distribution format in report:** Table with columns `Window | IS Period | OOS Period | OOS Sharpe | OOS MaxDD | OOS WinRate`. Summary line: `Sharpe distribution: min=X.XX | median=X.XX | max=X.XX`.
- **Perfect-foresight signal construction:** `foresight_signal = (close.shift(-1) > close).astype(float)`. With `.shift(1)` applied in harness: execution delayed one bar, foresight negated.
- **`_lookahead` parameter signature:** `def run(start: str, end: str, *, _lookahead: bool = False) -> BacktestResult`. Keyword-only, prefixed with underscore to signal "test-only."
- **Disclosure header fields (BCK-06):** Universe source date (latest `data/universe/*.parquet` stem), survivorship caveat (standard phrase), slippage tiers (verbatim BCK-03 tiers), IS/OOS period selection (per window), regime gate note ("soft gate — composite × regime_score").
- **Forensic audit output format:** Checklist with ✓/✗ per check + reason for failure. Final line: `AUDIT PASSED` or `AUDIT FAILED (N checks failed)` — non-zero exit on failure.
- **ADV computation:** `adv_20d = (panel['close'] * panel['volume']).groupby(level='ticker').rolling(20).mean()`. Computed within harness from `persistence.read_panel()` result. No extra storage needed.

</specifics>

<deferred>
## Deferred Ideas

- **Real per-playbook attribution (Qullamaggie / Minervini VCP / leader-hold split)** — Phase 6. Phase 5 treats all picks as `leader_hold`. Phase 6 adds real tagging and the backtest harness will group by `playbook_tag` column (Phase 6 adds this to the snapshot schema).
- **Monte Carlo simulation of OOS returns** — Phase 5 ships the deterministic walk-forward. Monte Carlo (bootstrap resample) is a Phase 7+ refinement if paper-trade validation shows the OOS Sharpe distribution is narrow.
- **Walk-forward parameter sweep (IS/OOS window sizing)** — Locked at 3yr/1yr per ROADMAP. Sweep over window sizes is deferred; it risks IS overfit on the window parameter itself.
- **`workflow_dispatch` manual trigger for backtest-audit** — Phase 8 (OPS). Phase 8 adds GitHub Actions `workflow_dispatch` for the full nightly pipeline, which includes the audit check.

</deferred>

---

*Phase: 5-Backtest Harness & No-Look-Ahead Gate*
*Context gathered: 2026-05-16*
