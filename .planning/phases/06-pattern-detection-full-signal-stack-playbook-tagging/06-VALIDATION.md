---
phase: 6
slug: pattern-detection-full-signal-stack-playbook-tagging
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-16
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + hypothesis 6.x (existing; per `pyproject.toml`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| **Quick run command** | `uv run pytest tests/test_patterns_golden.py tests/test_canslim_lag.py tests/test_playbook_tagger.py tests/test_breakout_strength.py -x` |
| **Full suite command** | `uv run pytest --no-cov -q` |
| **Estimated runtime** | ~10s (quick) / ~30s (full at end of Phase 5; expect ~45s after Phase 6 adds ~14 test files) |

---

## Sampling Rate

- **After every task commit:** Run quick command (4 most load-bearing Phase 6 gates: golden patterns, lag enforcement, tagger, breakout_strength)
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green AND `uv run pytest tests/test_backtest_no_lookahead.py` (FND-04 gate must remain green)
- **Max feedback latency:** 10 seconds per-commit; 45 seconds per-wave

---

## Per-Task Verification Map

> Populated by the planner during plan creation. Each task in every PLAN.md gets one row mapping it to its automated verify command. Format: `{plan-id}-{wave}-{task-N}` (e.g., `06-01-01`).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _Pending plan creation — every plan's tasks must add a row here before that plan can be marked complete._ | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 establishes the test scaffolding + pandera schemas + Settings extensions that every subsequent wave depends on. **No other wave can be started until Wave 0 is green.**

### New test files (12)

- [ ] `tests/test_patterns_golden.py` — 4 golden-file tests (D-02): NVDA 2023 VCP, AAPL 2020 VCP, NVDA 2024 split-adjusted, NVDA 2023-05-25 continuation flag (PAT-06)
- [ ] `tests/test_patterns_split.py` — NVDA 2024-06-10 10:1 split pivot continuity (PAT-05; D-25 regression gate)
- [ ] `tests/test_qullamaggie.py` — Setup A scan synthetic-panel coverage (SIG-02)
- [ ] `tests/test_canslim.py` — C-only additive scoring + L/M de-dup verification (SIG-03; D-18)
- [ ] `tests/test_canslim_lag.py` — 45-day lag enforcement (DAT-05; D-13b verbatim: write row with `quarter_end = as_of_date - 30d`, assert masked; advance `as_of_date + 16d`, assert unmasked)
- [ ] `tests/test_fundamentals_io.py` — Finnhub `/calendar/earnings` + yfinance EPS fetch (responses-mocked) (CAT-01)
- [ ] `tests/test_insider_io.py` — Form 4 fetch + SQLite write (edgar-mocked) (CAT-04)
- [ ] `tests/test_insider_cluster_buy.py` — cluster query against synthetic Form 4 fixture (CAT-03)
- [ ] `tests/test_composite_full.py` — all components active; `PHASE_4_ZEROED` shrinks to empty (CMP-01; D-16)
- [ ] `tests/test_playbook_tagger.py` — D-14 tie-breaker matrix (qull/minervini overlap, leader_hold isolation, none-tag pickup) (CMP-02, CMP-03)
- [ ] `tests/test_breakout_strength.py` — D-06 graded formula `clip((vol/sma50 - 1.0) / 1.5, 0, 1)` + NaN/0 edge cases (Pitfall 10)
- [ ] `tests/conftest.py` — shared fixtures for pattern fixtures + Form 4 fixture loaders (extend existing)

### Pandera schemas (3)

- [ ] `FundamentalsSchema` — quarter_end, eps_actual, eps_prior_yoy, knowable_from, source, ingested_at; `coerce=False, strict=True` (Phase 2 D-15 policy)
- [ ] `InsiderSchema` — filing_id (PK), ticker, insider, transaction_date, type ∈ {BUY,SELL}, shares, value_usd, ingested_at
- [ ] `PatternAuditSchema` — ticker, snapshot_date, pattern_type, leg_idx, start_date, end_date, high, low, depth, avg_volume

### Settings extensions (5 env vars)

- [ ] `Settings.FINNHUB_API_KEY` — REQUIRED for Phase 6+; `.env.example` documents
- [ ] `Settings.EDGAR_IDENTITY` — REQUIRED for Phase 6+; `.env.example` documents; `cli.py` startup hook fails loud if unset (CAT-04)
- [ ] `Settings.FUNDAMENTALS_CACHE_DIR` — default `data/fundamentals/`
- [ ] `Settings.INSIDER_CACHE_PATH` — default `data/insider/form4.sqlite`
- [ ] `Settings.PATTERN_AUDIT_DIR` — default `data/pattern_audit/`

### Test fixtures (7)

- [ ] `tests/fixtures/patterns/nvda_2023_vcp.parquet` — extract slice from `data/ohlcv/NVDA.parquet`
- [ ] `tests/fixtures/patterns/aapl_2020_vcp.parquet` — extract slice from `data/ohlcv/AAPL.parquet`
- [ ] `tests/fixtures/patterns/nvda_2024_split.parquet` — slice spanning 2024-05-15..2024-07-15
- [ ] `tests/fixtures/patterns/nvda_2023_flag.parquet` — slice 2023-05-15..2023-06-20
- [ ] `tests/fixtures/fundamentals/sample_quarterly.parquet` — synthetic EPS for lag-enforcement test
- [ ] `tests/fixtures/form4_cluster.sqlite` — synthetic Form 4 fixture for cluster query test
- [ ] `tests/fixtures/form4_no_cluster.sqlite` — negative case (only 1 insider in window)

### Architecture test extension (D-23)

- [ ] `tests/test_architecture.py` — extend ALLOWED dict with: `data/fundamentals`, `data/insider`, `indicators/patterns`, `signals/qullamaggie`, `signals/canslim`; assert `signals/` and `indicators/` cannot import `data/` (structural defense of D-13b)

### CLI smoke extension

- [ ] `tests/test_cli_smoke.py::test_edgar_identity_required` — new assertion: `cli.py` startup fails loud if `EDGAR_IDENTITY` unset (CAT-04). MUST NOT modify `D14_SUBCOMMANDS` list (D-24).

---

## Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| DAT-05 | `make fundamentals` runs end-to-end with 45-day lag enforced | integration | `uv run pytest tests/test_canslim_lag.py -x` | ❌ Wave 0 |
| PAT-01 | VCP detector identifies pivots via `scipy.signal.argrelextrema` | unit + golden | `uv run pytest tests/test_patterns_golden.py::test_nvda_2023_vcp -x` | ❌ Wave 0 |
| PAT-02 | VCP threshold criteria (depth contractions, n_contractions, breakout vol) enforced | unit | `uv run pytest tests/test_patterns_golden.py::test_vcp_thresholds -x` | ❌ Wave 0 |
| PAT-03 | Flag detector recognizes 5–25 bar consolidation along rising SMA, higher lows | unit + golden | `uv run pytest tests/test_patterns_golden.py::test_nvda_2023_flag -x` | ❌ Wave 0 |
| PAT-04 | Post-gap-continuation boolean: `gap≥8% AND vol>1.5×SMA50 AND close in upper third` (D-04) | unit | `uv run pytest tests/test_patterns_golden.py::test_post_gap_continuation -x` | ❌ Wave 0 |
| PAT-05 | Pivot re-derived from adjusted closes; survives NVDA 2024-06-10 10:1 split | unit | `uv run pytest tests/test_patterns_split.py::test_nvda_2024_split_pivot_continuity -x` | ❌ Wave 0 |
| PAT-06 | Golden-file tests for ≥3 historical setups + flag (D-02 = 4 tests) | regression | `uv run pytest tests/test_patterns_golden.py -x` | ❌ Wave 0 |
| SIG-02 | Qullamaggie Setup A scan: top 1–2% perf 1m/3m/6m AND ADV>$1.5M AND ADR%≥4 | unit | `uv run pytest tests/test_qullamaggie.py -x` | ❌ Wave 0 |
| SIG-03 | CANSLIM additive; L (RS≥80) and M (regime) NOT double-counted (D-18) | unit | `uv run pytest tests/test_canslim.py::test_no_double_count -x` | ❌ Wave 0 |
| CMP-01 | Composite weights unchanged from Phase 4; sum to 1.0; preregistration CI gate green | unit (existing) | `uv run pytest tests/test_signals_composite.py::test_weights_sum_to_one -x` AND `uv run python scripts/check_preregistration.py` | ✅ |
| CMP-02 | Each pick emits `playbook_tag ∈ {qullamaggie_continuation, minervini_vcp, leader_hold, none}` | unit | `uv run pytest tests/test_playbook_tagger.py::test_tag_values_valid -x` | ❌ Wave 0 |
| CMP-03 | Tie-breaker matrix (D-14: Qullamaggie wins on overlap; D-15: leader_hold = trend pass + RS≥90 + no pattern) | unit | `uv run pytest tests/test_playbook_tagger.py::test_d14_tiebreaker -x tests/test_playbook_tagger.py::test_d15_leader_hold -x` | ❌ Wave 0 |
| CMP-04 | `tag_playbook` co-located in `signals/composite.py`; `signals/` cannot import `data/` | architectural | `uv run pytest tests/test_architecture.py -x` (extended for D-23) | ✅ extended |
| CMP-05 | Per-pick component breakdown matches D-19 format `RS=92 \| Trend=8/8 \| Pattern=... \| Volume=... \| Earnings=... \| Catalyst=...` | unit | `uv run pytest tests/test_publishers_report.py::test_d19_breakdown_format -x` | ❌ Wave 0 (extend existing) |
| CAT-01 | `days_to_next_earnings` (+ BMO/AMC) + `earnings_in_3d_warn` populated | unit | `uv run pytest tests/test_fundamentals_io.py::test_earnings_calendar_normalize -x` | ❌ Wave 0 |
| CAT-02 | `crossed_52w_high_within_60d` populated correctly | unit | `uv run pytest tests/test_publishers_snapshot.py::test_52w_high_60d_flag -x` | ❌ Wave 0 (extend existing) |
| CAT-03 | Insider cluster-buy: ≥2 distinct insiders BUY within 5-day rolling window over last 30 days | unit | `uv run pytest tests/test_insider_cluster_buy.py -x` | ❌ Wave 0 |
| CAT-04 | `edgartools.set_identity()` called at CLI startup; fails loud if `EDGAR_IDENTITY` unset | integration | `uv run pytest tests/test_cli_smoke.py::test_edgar_identity_required -x` | ❌ Wave 0 |

### Cross-cutting verification (decisions, not REQ-IDs)

| Decision | Behavior | Automated Command | File Exists? |
|----------|----------|-------------------|--------------|
| D-13b (lag) | 45-day lag enforced at persistence read; signal cannot bypass | `uv run pytest tests/test_canslim_lag.py::test_lag_enforcement_30d_then_16d -x` | ❌ Wave 0 |
| D-06 (breakout_strength) | `clip((vol/sma50 - 1.0) / 1.5, 0, 1)` graded formula + NaN/0 edges | `uv run pytest tests/test_breakout_strength.py -x` | ❌ Wave 0 |
| D-16 (PHASE_4_ZEROED shrink) | After Phase 6, `PHASE_4_ZEROED == frozenset()` | `uv run pytest tests/test_signals_composite.py::test_phase_4_zeroed_empty -x` | ✅ extend existing |
| D-23 (architecture) | `signals/` and `indicators/` cannot import `data/` | `uv run pytest tests/test_architecture.py::test_layer_import_contract -x` | ✅ extend existing |
| D-24 (CLI surface lock) | `D14_SUBCOMMANDS` list unchanged (no 10th subcommand) | `uv run pytest tests/test_cli_smoke.py::test_subcommand_surface_locked -x` | ✅ |
| FND-04 (no-look-ahead) | Phase 5 CI gate remains green after Phase 6 changes to `signals/` | `uv run pytest tests/test_backtest_no_lookahead.py -x` | ✅ |
| BCK-04 (per-playbook attribution) | Phase 5 harness picks up new playbook tags from snapshots | manual: `make backfill-snapshots && make backtest` | partial (existing harness) |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Finnhub `/calendar/earnings` returns expected schema for current universe | CAT-01 | Requires real API call + valid `FINNHUB_API_KEY`; cached responses-mock tests cover schema invariants but not field drift | After Wave 0, run `make fundamentals` once with real key; eyeball `data/fundamentals/*.parquet` for ~Russell 1000 coverage and BMO/AMC populated on ≥70% of upcoming dates |
| Live EDGAR Form 4 ingest captures real cluster-buy events | CAT-03 / CAT-04 | edgartools network-bound; first nightly run will surface auth/identity/format issues that mocks miss | After Wave 0, run `make fundamentals --insider-only` once with real `EDGAR_IDENTITY`; query `data/insider/form4.sqlite` for ≥1 known historical cluster (e.g., search for any insider ticker with COUNT>=2 in last 90 days) |
| Pattern_diagnostics JSON renders correctly in markdown report | CMP-05 (D-19 format) | Visual inspection of `reports/YYYY-MM-DD.md` after first full run | After Wave 0, run `make rank && make report`; verify per-pick block matches D-19 format exactly (no trailing commas, no quote escapes in JSON) |
| Per-playbook attribution in Phase 5 backtest after backfill | BCK-04 | Phase 5 harness must consume new `playbook_tag` column; requires re-running backfill | After Phase 6 complete: `make backfill-snapshots && make backtest`; verify `qullamaggie_continuation`, `minervini_vcp`, `leader_hold` rows appear in attribution table (was leader_hold-only stub in Phase 5) |
| 4 golden-file pattern tests classify correctly | PAT-06 (Success Criterion 1) | Tuning `argrelextrema(order=N)` may need empirical iteration on real OHLCV slices before tests stabilize | Wave 1: iterate `order` value (start 5 for VCP, 3 for flag) until all 4 golden tests pass; document chosen values in `patterns.py` module docstring |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (planner enforces during plan creation)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all 12 new test files, 3 pandera schemas, 5 Settings extensions, 7 fixtures, architecture + CLI smoke extensions
- [ ] No watch-mode flags (CI runs once)
- [ ] Feedback latency < 10s per commit
- [ ] `nyquist_compliant: true` set in frontmatter after all per-task verifies pass
- [ ] FND-04 no-look-ahead CI gate remains green throughout Phase 6 execution

**Approval:** pending
