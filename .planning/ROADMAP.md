# Roadmap: Momentum Swing Screener

**Created:** 2026-04-27
**Granularity:** Standard (5–8 phases, 3–5 plans each)
**Total v1 Requirements:** 64
**Coverage:** 64/64 mapped (100%)
**UI Hint:** None (CLI / data project; no frontend in v1)

## Core Value

Every evening, the user opens one report and gets a small, ranked list of high-quality long candidates with playbook-specific trade plans they can execute the next morning — reliable enough to size real positions on once paper-trade validation confirms it works.

## Phase Structure Rationale

This roadmap follows the 8-phase ordering proposed by `research/SUMMARY.md`, validated against the 64 v1 requirements. Each phase delivers a thin, end-to-end-runnable slice rather than a horizontal layer. Three ordering decisions are non-negotiable and worth surfacing here:

1. **Phase 1 (Data Foundation) carries the most pitfall-prevention weight.** Survivorship snapshot, yfinance retries + post-fetch invariants, corporate-action storage, universe-coverage health check, and the pyproject dependency lock all live here. There is no retroactive fix for a missing weekly snapshot or a silent partial fetch.

2. **Phase 4 (Backtest Harness) ships BEFORE Phase 5 (Full Pattern Detection).** The no-look-ahead test (FND-04) must be a CI-blocking gate before any signal-touching PR is merged. Counter-intuitive but firm: the harness is built against the Trend-Template-only signal set from Phase 3, then pattern detection in Phase 5 inherits a hardened backtest path.

3. **Phase 5 ships patterns + Qullamaggie scan + CANSLIM overlay + composite-with-playbook + catalysts together.** They are mutually dependent: composite weights need pattern scoring, playbook tag depends on pattern classification, CANSLIM overlay and catalyst flags both feed composite components. Splitting any of these would force a partial-system milestone with no end-to-end value.

A fourth: **Phase 6 (Sizing + Journal) ships together** — sizing dispatches by playbook tag, the journal schema includes the playbook tag column, and the journal is the v2 ML training contract that must be frozen before the first paper trade.

## Phases

- [ ] **Phase 1: Repo Skeleton & CI Hygiene** — uv-managed pyproject, typer CLI skeleton, Makefile targets, ruff/mypy/pytest CI, pre-registration doc placeholder
- [ ] **Phase 2: Data Foundation** — Russell 1000 universe with weekly snapshots, yfinance OHLCV cache with Stooq fallback, retry/health-check infrastructure, pandera schemas at I/O boundaries
- [ ] **Phase 3: Indicator Panel & Regime** — SMA/ATR/ADR%/RS-percentile panel, macro data layer, three-state regime gate with continuous regime_score
- [ ] **Phase 4: Trend Template, Composite Skeleton & First Report** — Minervini 8-condition gate, composite skeleton (weights pre-registered), ATR-based sizing, first daily markdown report
- [ ] **Phase 5: Backtest Harness & No-Look-Ahead Gate** — vectorbt walk-forward harness, CI-blocking no-look-ahead test, slippage tiers, forensic audit CLI, per-playbook + per-regime breakdowns
- [ ] **Phase 6: Pattern Detection, Full Signal Stack & Playbook Tagging** — VCP + continuation-flag + post-gap-continuation detectors, Qullamaggie Setup A scan, CANSLIM C+L+M overlay, composite playbook tagger, catalyst flags
- [ ] **Phase 7: Sizing Finalization & Paper-Trade Journal** — per-playbook stop/trail rules, auto-rejection at 1×ADR risk, append-only SQLite journal with `features_json` blob — the v2 ML contract
- [ ] **Phase 8: GitHub Actions Cron & Operations** — nightly refresh workflow, heartbeat job, structured run log, manual workflow_dispatch trigger

## Phase Details

### Phase 1: Repo Skeleton & CI Hygiene

**Goal:** Engineering hygiene first — `uv` env, locked v1 stack, CI gates active, Makefile orchestrating the DAG, pre-registration doc placeholder ready for Phase 4 weights.

**Depends on:** Nothing (first phase)

**Requirements:** FND-01, FND-02, FND-03

**Success Criteria** (what must be TRUE):
  1. `uv sync` from a clean clone installs the full v1 stack (pandas, pandas-ta-classic, yfinance, vectorbt, edgartools, finnhub-python, fredapi, pydantic-settings, pandera, structlog, typer) with versions matching `STACK.md` pins.
  2. Running `make data && make rank && make report && make backtest` from a clean checkout exits zero (with placeholder behavior — real artifacts ship in later phases) and requires no manual setup beyond `uv sync` and a populated `.env`.
  3. Opening any pull request triggers GitHub Actions CI that runs `ruff check`, `mypy --strict src/screener/{indicators,signals}`, and `pytest` — all three must pass for the PR to be mergeable.
  4. `docs/strategy_v1_preregistration.md` exists with the pre-registration template and the placeholder `<weights frozen at Phase 4 completion>`.

**Estimated Complexity:** S

**Plans:** TBD

### Phase 2: Data Foundation

**Goal:** All downstream stages can rely on a fresh, schema-validated, survivorship-aware OHLCV panel — yfinance failures fail loud, weekly universe snapshots accumulate from day one, and corporate-action splits are stored alongside prices for honest pattern detection in Phase 6.

**Depends on:** Phase 1

**Requirements:** DAT-01, DAT-02, DAT-03, DAT-06, DAT-07, DAT-08, DAT-09

**Success Criteria** (what must be TRUE):
  1. `make universe` produces a Parquet snapshot at `data/universe/YYYY-MM-DD.parquet` with 950–1010 Russell 1000 tickers; running it on a fresh Monday writes a new dated file without overwriting prior weeks.
  2. `make ohlcv` refreshes the universe's OHLCV via yfinance (Stooq fallback), caches per-ticker Parquet, and on subsequent runs only appends bars after the last cached date — verifiable by running it twice and observing only the latest bar appended.
  3. The universe-coverage health check fails the run (non-zero exit, no commit) when `successful_fetches < 0.95 × universe_size`; simulating this by injecting fetch failures for 6%+ of tickers triggers a loud failure rather than a silently partial result.
  4. `splits.parquet` exists alongside each ticker's OHLCV file; for known split events (NVDA 2024-06-10 10:1, AAPL 2020-08-31 4:1) the stored split ratio matches the documented event.
  5. Pandera schemas reject any DataFrame with wrong dtypes, missing required columns, or null values in `close` at the `data/ → indicators/` boundary — a unit test feeding a corrupted DataFrame must raise `pandera.errors.SchemaError`.

**Estimated Complexity:** L

**Plans:** TBD

### Phase 3: Indicator Panel & Regime

**Goal:** A pure-function indicator panel (SMAs, ATR, ADR%, OBV, dryup, RS percentile) operates cross-sectionally over the universe, and a regime module emits the three-state market gate plus a continuous `regime_score` — the foundation for both the Trend Template (Phase 4) and the playbook-aware composite (Phase 6).

**Depends on:** Phase 2

**Requirements:** DAT-04, IND-01, IND-02, IND-03, IND-04, IND-05, REG-01, REG-02, REG-03, REG-04

**Success Criteria** (what must be TRUE):
  1. `make macro` refreshes SPY, ^IXIC, ^VIX, the NYSE A/D line (Stooq), and FRED yields, writing them to `data/macro/*.parquet`; subsequent runs append only the latest bar.
  2. `indicators.build_panel()` returns a multi-ticker DataFrame containing SMA(10/20/50/150/200), ATR(14), ADR%(20), OBV, dryup-ratio, and RS rating (integer 1–99) for every Russell 1000 ticker — RS percentile is universe-relative on the same date, recomputed daily.
  3. The CI grep `rg "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py` returns zero matches; introducing an EMA reference fails CI.
  4. Regime golden-file tests classify 2008-Q4, 2020-Q1, and 2022-H1 as `Correction` for the documented date ranges; running `pytest tests/test_regime.py -k 'corrections'` passes on all three.
  5. The regime module emits both a discrete state ∈ {Confirmed Uptrend, Uptrend Under Pressure, Correction} and a continuous `regime_score ∈ [0, 1]` — verifiable by inspecting the output DataFrame columns.

**Estimated Complexity:** M

**Plans:** TBD

### Phase 4: Trend Template, Composite Skeleton & First Report

**Goal:** Ship the simplest end-to-end signal — Minervini Trend Template + RS + regime — through composite scoring, ATR-based sizing, and a markdown report. Pre-register the v1 composite weights with a git hash before any backtest result is reported.

**Depends on:** Phase 3

**Requirements:** FND-05, SIG-01, SIG-04, OUT-01, OUT-02, OUT-03

**Success Criteria** (what must be TRUE):
  1. `make report` produces `reports/YYYY-MM-DD.md` containing a regime banner, a top-N picks table (default N=15), per-pick blocks (ticker, score breakdown, ATR distance from pivot, catalyst-flag placeholders), and a data-quality footer with universe size, scan time, fetch success rate, and last yfinance refresh.
  2. The Trend Template gate emits both `passes_trend_template: bool` and `trend_template_score: int (0–8)` per ticker; on a normal market day, the pass rate across the Russell 1000 falls in the 5–15% sanity band (alerting at >25% per pitfall #4).
  3. `data/snapshots/YYYY-MM-DD.parquet` is written for every `make report` run with the full ranked universe (not just top picks), making the day's ranking auditable and backtestable later.
  4. `docs/strategy_v1_preregistration.md` is committed with the v1 composite weights (RS 25 / Trend 20 / Pattern 20 / Volume 10 / Earnings 15 / Catalyst 10), the freeze date, and a referenced git hash; modifying the weights without updating the doc fails CI.
  5. `signals/composite.py` accepts a weights dict (not hardcoded column references) so v2 ML can add `"ml_probability"` as one weight key without refactoring downstream consumers.

**Estimated Complexity:** M

**Plans:** TBD

### Phase 5: Backtest Harness & No-Look-Ahead Gate

**Goal:** A vectorbt 1.0 walk-forward harness reads disk artifacts only, enforces next-bar-open execution, and ships the CI-blocking no-look-ahead mutation test BEFORE pattern detection lands. Backtests against the Trend-Template-only signal stack establish a baseline before Phase 6 expands the signal surface.

**Depends on:** Phase 4

**Requirements:** FND-04, BCK-01, BCK-02, BCK-03, BCK-04, BCK-05, BCK-06, BCK-07

**Success Criteria** (what must be TRUE):
  1. `tests/test_backtest_no_lookahead.py` is a CI-blocking gate on every PR touching `signals/` or `backtest/`; the test constructs a "perfect-foresight" signal equal to next-day return and asserts the strategy's total return is below a noise threshold when `.shift(1)` is applied correctly. Removing the `.shift(1)` from the harness causes the test to fail (mutation-tested).
  2. `make backtest` runs a 3-yr IS / 1-yr OOS rolling-window walk-forward and reports the OOS Sharpe distribution (min, median, max) across windows — the single-period Sharpe is not a supported reporting mode.
  3. Slippage tiers (5 bps for ADV > $50M, 15 bps for $5M–$50M, 30 bps for < $5M) are wired into `vbt.Portfolio.from_signals` by default; the zero-slippage path is not exposed as a public API.
  4. Every backtest report includes a disclosure header naming the universe-source date, survivorship-bias caveat, slippage assumptions, and period selection — and per-regime + per-playbook breakdowns (with playbook attribution stubbed pending Phase 6).
  5. `make backtest-audit` runs a forensic checklist (no-look-ahead test passing, weight-pre-registration hash match, universe snapshot date ≤ backtest start date) and exits non-zero if any check fails — backtest results are not considered reportable until this passes.

**Estimated Complexity:** L

**Plans:** TBD

### Phase 6: Pattern Detection, Full Signal Stack & Playbook Tagging

**Goal:** Ship the differentiator — VCP, continuation-flag, and post-gap-continuation detectors; the Qullamaggie Setup A scan; the CANSLIM C+L+M overlay; the catalyst-flag annotations; and the composite scorer's playbook tagger that emits `qullamaggie_continuation` / `minervini_vcp` / `leader_hold` per pick. The hardest phase, gated by the no-look-ahead harness from Phase 5.

**Depends on:** Phase 5

**Requirements:** DAT-05, PAT-01, PAT-02, PAT-03, PAT-04, PAT-05, PAT-06, SIG-02, SIG-03, CMP-01, CMP-02, CMP-03, CMP-04, CMP-05, CAT-01, CAT-02, CAT-03, CAT-04

**Success Criteria** (what must be TRUE):
  1. Golden-file tests on three known historical setups (e.g., NVDA 2023 base, AAPL 2020 base, NVDA 2024 split-adjusted) classify the VCP / continuation-flag / post-gap pattern correctly; introducing a regression in the contraction-depth or volume-contraction logic causes a specific named test to fail.
  2. Pivot prices are re-derived from adjusted closes on every run (never cached as fixed dollar levels) — verified by a unit test that runs pivot detection across a known split event (NVDA 2024-06-10) and confirms the pivot is continuous, not bisected by the split.
  3. Each pick in the report declares a playbook tag from {`qullamaggie_continuation`, `minervini_vcp`, `leader_hold`} chosen by the documented tie-breaking rules (Qullamaggie wins if pattern < 25 bars and ADR% ≥ 5; Minervini VCP wins if pattern ≥ 25 bars or final contraction ≤ 8%; leader-hold is the fallback) and exposes its component breakdown (`RS=92, Trend=8/8, Pattern_VCP_tightness=6.2%, Volume=1.2, Earnings=1, Catalyst=0.5`).
  4. The Qullamaggie Setup A scan filters to the top 1–2% performers over 1m/3m/6m AND avg dollar volume > $1.5M AND ADR%(20) ≥ 4; the post-gap-continuation detector flags D+1 candidates that gapped ≥ 8% with strong volume on D-0 and held the gap (D-0 close in upper third of D-0 range).
  5. Each pick's report block flags `days_to_next_earnings` (with BMO/AMC notation), `crossed_52w_high_within_60d`, and `insider_cluster_buy: true` when ≥ 2 insiders bought within a rolling 5-day window in the last 30 days; `edgartools.set_identity()` is called at startup or the run fails loud.
  6. The CANSLIM C+L+M overlay is applied as additive scoring (not a hard gate) and respects the 45-day post-quarter-end fundamentals lag — fundamentals are tagged with a `knowable_from` date and not consumed before that date passes (verified by a unit test feeding a fresh-from-quarter fundamental and asserting it is masked).

**Estimated Complexity:** L

**Plans:** TBD

### Phase 7: Sizing Finalization & Paper-Trade Journal

**Goal:** Per-playbook entry/stop/trail rules dispatch from the playbook tag; the append-only SQLite journal captures every actionable pick with the full `features_json` blob, freezing the schema as the v2 ML training contract. No paper trade is logged until this schema lands.

**Depends on:** Phase 6

**Requirements:** SIZ-01, SIZ-02, SIZ-03, SIZ-04, SIZ-05, OUT-04, OUT-05, OUT-06

**Success Criteria** (what must be TRUE):
  1. The position sizer computes `shares = (account_equity × risk_pct × regime_score) / (entry - stop)` per pick, capped at 25% of equity per single position; auto-rejects any pick where `risk_per_share > 1 × ADR_dollars` and surfaces the rejection reason ("skipped: R/R broken, risk = 1.4× ADR") in the report.
  2. Stop placement and trailing rules dispatch by playbook: Qullamaggie continuation uses low-of-entry-day stop and 10/20/50d SMA trail (by speed); Minervini VCP uses below-final-contraction-low stop and 21d EMA / 50d SMA trail; leader-hold uses below-recent-swing-low (1.5–2×ADR distance) stop and 50d SMA close trail. A unit test asserts each playbook calls the correct stop+trail helper.
  3. Each pick reports its distance-from-pivot in ATRs with an `in-zone` (≤ 0.66×ATR above pivot) or `chase, skip` (> 1×ATR above pivot) annotation in the markdown report.
  4. Every actionable pick (composite ≥ threshold, regime allows new entries) is appended to `data/journal.sqlite` at publish time — including picks the user does not execute. The journal schema is append-only with decision columns immutable; attempting an UPDATE on a decision column raises a database constraint error.
  5. Each journal row stores a `features_json` blob with the full score-component snapshot at signal time — verifiable by inserting a pick, then loading and parsing the JSON to recover the exact component breakdown the rules saw.
  6. The journal records both the decision-time state and the eventual outcome (entry filled? exit price? holding period? max favorable/adverse excursion?) once the trade closes — outcome columns are nullable and updated by a separate `journal-update` flow, never by the live pipeline.

**Estimated Complexity:** M

**Plans:** TBD

### Phase 8: GitHub Actions Cron & Operations

**Goal:** Productionalize the locally-robust pipeline via GitHub Actions cron, with a heartbeat job to defeat the 60-day idle throttle, structured run logging for observability, and a manual `workflow_dispatch` trigger for re-runs.

**Depends on:** Phase 7

**Requirements:** OPS-01, OPS-02, OPS-03, OPS-04, OPS-05

**Success Criteria** (what must be TRUE):
  1. `.github/workflows/refresh.yml` runs on schedule `30 22 * * 1-5` (UTC, weekdays) and executes the full pipeline (universe → ohlcv → macro → fundamentals → score → report → journal) with a single workflow run; the run produces the day's `reports/YYYY-MM-DD.md`, `snapshots/YYYY-MM-DD.parquet`, and journal updates committed via `stefanzweifel/git-auto-commit-action@v5`.
  2. A separate weekly heartbeat workflow commits a heartbeat artifact, preventing GitHub from disabling the nightly cron after 60 days of idle.
  3. `workflow_dispatch` is configured on the refresh workflow so the user can manually re-run the daily pipeline from the Actions tab when the scheduled run drifts or fails.
  4. Each run appends a structured JSON record to `runs.jsonl` (start_time, duration_seconds, fetch_success_rate, regime_state, picks_count, n_429_responses) — the file grows append-only and is committed alongside the day's artifacts.
  5. A run that fails the universe-coverage health check (< 95%) exits non-zero, does not commit partial artifacts, and surfaces the failure in the GitHub Actions summary.

**Estimated Complexity:** S

**Plans:** TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Repo Skeleton & CI Hygiene | 0/? | Not started | - |
| 2. Data Foundation | 0/? | Not started | - |
| 3. Indicator Panel & Regime | 0/? | Not started | - |
| 4. Trend Template, Composite Skeleton & First Report | 0/? | Not started | - |
| 5. Backtest Harness & No-Look-Ahead Gate | 0/? | Not started | - |
| 6. Pattern Detection, Full Signal Stack & Playbook Tagging | 0/? | Not started | - |
| 7. Sizing Finalization & Paper-Trade Journal | 0/? | Not started | - |
| 8. GitHub Actions Cron & Operations | 0/? | Not started | - |

## Coverage Report

**Total v1 requirements:** 64
**Mapped:** 64 (100%)
**Unmapped:** 0
**Duplicates:** 0

### Per-Phase Mapping

| Phase | Requirement Count | Requirements |
|-------|-------------------|--------------|
| Phase 1 | 3 | FND-01, FND-02, FND-03 |
| Phase 2 | 7 | DAT-01, DAT-02, DAT-03, DAT-06, DAT-07, DAT-08, DAT-09 |
| Phase 3 | 10 | DAT-04, IND-01, IND-02, IND-03, IND-04, IND-05, REG-01, REG-02, REG-03, REG-04 |
| Phase 4 | 6 | FND-05, SIG-01, SIG-04, OUT-01, OUT-02, OUT-03 |
| Phase 5 | 8 | FND-04, BCK-01, BCK-02, BCK-03, BCK-04, BCK-05, BCK-06, BCK-07 |
| Phase 6 | 18 | DAT-05, PAT-01, PAT-02, PAT-03, PAT-04, PAT-05, PAT-06, SIG-02, SIG-03, CMP-01, CMP-02, CMP-03, CMP-04, CMP-05, CAT-01, CAT-02, CAT-03, CAT-04 |
| Phase 7 | 8 | SIZ-01, SIZ-02, SIZ-03, SIZ-04, SIZ-05, OUT-04, OUT-05, OUT-06 |
| Phase 8 | 5 | OPS-01, OPS-02, OPS-03, OPS-04, OPS-05 |
| **Total** | **64** | — |

### Per-Category Coverage

| Category | Count | Phases |
|----------|-------|--------|
| FND (Foundation) | 5 | Phase 1 (3), Phase 4 (1), Phase 5 (1) |
| DAT (Data) | 9 | Phase 2 (7), Phase 3 (1), Phase 6 (1) |
| IND (Indicators) | 5 | Phase 3 (5) |
| PAT (Patterns) | 6 | Phase 6 (6) |
| SIG (Signals) | 4 | Phase 4 (2), Phase 6 (2) |
| REG (Regime) | 4 | Phase 3 (4) |
| CMP (Composite & Playbook) | 5 | Phase 6 (5) |
| SIZ (Sizing & Trade Plans) | 5 | Phase 7 (5) |
| CAT (Catalysts) | 4 | Phase 6 (4) |
| OUT (Output) | 6 | Phase 4 (3), Phase 7 (3) |
| BCK (Backtest) | 7 | Phase 5 (7) |
| OPS (Operations) | 5 | Phase 8 (5) |
| **Total** | **64** | — |

### Cross-Cutting Mappings (Why Some Categories Span Phases)

- **FND-04** (no-look-ahead test) ships in Phase 5 (Backtest Harness) — the test belongs with the harness it validates, and is a CI gate on every signal-touching PR thereafter.
- **FND-05** (composite-weights pre-registration) ships in Phase 4 — co-located with the composite scorer skeleton, before any backtest result lands.
- **DAT-04** (`make macro`) ships in Phase 3 — paired with the regime module that consumes macro data.
- **DAT-05** (`make fundamentals` + 45-day lag) ships in Phase 6 — paired with the CANSLIM overlay (SIG-03) and catalyst flags (CAT-*) that consume fundamentals.
- **OUT-01..03** (report + snapshot + report content) ship in Phase 4 (first report); **OUT-04..06** (journal) ship in Phase 7 (journal schema). Splitting OUT across two phases reflects the report-first-then-journal sequencing.
- **SIG-01, SIG-04** (Trend Template + signals-purity) ship in Phase 4; **SIG-02, SIG-03** (Qullamaggie scan + CANSLIM overlay) ship in Phase 6 alongside pattern detection they depend on.

## Pitfall-Prevention Mapping

Each phase ships specific testable invariants that prevent the canonical pitfalls (per `research/PITFALLS.md`). Listed here for downstream `/gsd-plan-phase` to derive must-haves from.

| Pitfall | Phase | Invariant Shipped |
|---------|-------|-------------------|
| #1 Survivorship bias | Phase 2 | Weekly universe snapshots from day one (DAT-02) |
| #2 Look-ahead bias | Phase 5 | `test_backtest_no_lookahead.py` mutation-tested, CI-blocking (FND-04) |
| #3 Corporate-action integrity | Phase 2 + Phase 6 | `splits.parquet` stored (DAT-08); pivots re-derived from adjusted closes (PAT-05) |
| #4 EMA-vs-SMA confusion | Phase 3 | CI grep blocks `ema` references in `signals/minervini.py` and `indicators/trend.py` (IND-02) |
| #5 In-sample weight overfit | Phase 4 + Phase 5 | Pre-registration doc with git hash (FND-05); walk-forward as default reporting (BCK-01) |
| #6 Forgotten regime gate | Phase 3 | Regime golden-file tests for 2008/2020/2022 (REG-04); regime_score multiplied into sizing (REG-03) |
| #7 yfinance silent partial | Phase 2 | Tenacity retries + post-fetch invariants (DAT-06); 95% universe-coverage health check (DAT-07) |
| #8 Backtest realism | Phase 5 | Slippage tiers wired by default (BCK-03); per-playbook + per-regime breakdowns (BCK-04, BCK-05) |
| #9 Free-tier quota | Phase 2 + Phase 6 | requests-cache + tenacity (DAT-06); cache-first fundamentals (DAT-05) |
| #10 Universe leakage | Phase 5 | Backtest-audit asserts `universe.snapshot_date ≤ backtest.start_date` (BCK-07) |
| #11 Journal pollution | Phase 7 | Append-only schema, decision columns immutable, `features_json` blob (OUT-04, OUT-05, OUT-06) |
| #13 Multiple-testing blindness | Phase 4 + Phase 5 | Pre-registration hash (FND-05); walk-forward OOS Sharpe distribution (BCK-01) |
| #14 Streamlit deploy debt | Phase 1 | pandas-ta-classic locked, no TA-Lib in pyproject (FND-01) |
| #15 Sharpe > 2 self-skepticism | Phase 5 | `make backtest-audit` forensic checklist (BCK-07); disclosure header (BCK-06) |

## Architectural Contract for v2 (Preserved by v1 Phases)

`signals/composite.py` is the single M2 extension point. Phase 4 establishes the contract:
- Composite scorer takes a weights dict (not hardcoded columns).
- Playbook tagger is co-located with the scorer (added in Phase 6).
- Journal `features_json` blob (Phase 7) freezes the M2 ML training contract.

v2 adds `"ml_probability": 0.20` to the weights dict and imports from a new `screener/ml/predict.py`. Zero changes required in `data/`, `indicators/`, `signals/{minervini, qullamaggie, canslim}`, `regime`, `sizing`, or `publishers`.

---
*Roadmap created: 2026-04-27*
*Last updated: 2026-04-27*
