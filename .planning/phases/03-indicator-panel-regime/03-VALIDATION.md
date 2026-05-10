---
phase: 3
slug: indicator-panel-regime
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-10
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml (existing — Phase 1 D-12) |
| **Quick run command** | `pytest -m "not slow and not integration" -x -q` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~30 seconds (quick); ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -m "not slow and not integration" -x -q`
- **After every plan wave:** Run `pytest` (full)
- **Before `/gsd-verify-work`:** Full suite must be green; ruff + mypy clean on indicators/ + signals/
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> One row per plan-task. Status column is ⬜ pending until execute-phase runs.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| T01.1 | 03-01 | 1 | DAT-04, IND-03 (D-12 settings) | T-3-01 (input-shape gate) | Settings instantiation typed defaults verified | unit (smoke) | `uv run python -c "from screener.config import get_settings; s=get_settings(); assert s.MACRO_CACHE_DIR.as_posix()=='data/macro'; assert s.RS_SNAPSHOT_DIR.as_posix()=='data/rs_snapshots'; assert s.MACRO_BACKFILL_START=='2005-01-01'; assert s.REGIME_BREADTH_THRESHOLD==0.60; assert s.REGIME_DIST_DAYS_PRESSURE==5; assert s.REGIME_DIST_DAYS_CORRECTION==9; assert s.REGIME_VIX_CORRECTION==30.0; assert s.REGIME_VIX_CONFIRMED==20.0; print('OK')"` | ✅ existing (config.py) | ⬜ pending |
| T01.2 | 03-01 | 1 | DAT-04, IND-03 (schemas + helpers) | T-3-01, T-3-04 | Pandera schemas + atomic-write contract preserved | unit (smoke) | `uv run python -c "from screener.persistence import MacroOhlcvSchema, VixSchema, YieldsSchema, NyadMacroSchema, RsSnapshotSchema, write_rs_snapshot_atomic, read_rs_snapshot, write_macro_atomic, read_macro_spy, read_macro_qqq, read_macro_vix, read_macro_yields, read_macro_nyad, _macro_dir, _rs_snapshot_dir; print('OK')"` | ✅ existing (persistence.py) | ⬜ pending |
| T01.3 | 03-01 | 1 | DAT-04, IND-03 (Wave 0 tests) | T-3-04 (atomic-write crash safety) | Mid-write crash leaves no partial file; lazy-read validation collects errors | unit | `uv run pytest tests/test_rs_snapshot.py tests/test_persistence.py -m "not slow and not integration" -x -q` | ❌ W0 (tests/test_rs_snapshot.py created in this task) | ⬜ pending |
| T02.1 | 03-02 | 2 | DAT-04 (macro fetchers + breadth fallback) | T-3-01, T-3-02, T-3-03 | yfinance 4-invariant gate; FRED key never logged; Stooq fail routes to r1000_proxy | unit (smoke) | `uv run python -c "from screener.data.macro import refresh_spy, refresh_qqq, refresh_vix, refresh_nyad, refresh_yields, _compute_breadth_fallback, _fetch_yf_macro, _fetch_fred_yields, _stooq_to_breadth; from screener.data import macro; print('OK')"` | ❌ W0 (data/macro.py created in this task) | ⬜ pending |
| T02.2 | 03-02 | 2 | DAT-04 (CLI body + tests + Make target) | T-3-02 (no-secret-in-logs), T-3-03 | refresh-macro CLI emits sanitized error events; CliRunner-driven secret-leak test; D-14 surface preserved | unit + CLI smoke | `uv run pytest tests/test_macro_refresh.py tests/test_cli_smoke.py -m "not slow and not integration" -x -q` | ❌ W0 (tests/test_macro_refresh.py created in this task) | ⬜ pending |
| T03.1 | 03-03 | 2 | IND-01, IND-03, IND-04, IND-05 (pure-fn indicators) | T-3-01 (input-shape gate) | Pure functions; no I/O imports — architecture test enforced | unit (smoke + architecture) | `uv run pytest tests/test_architecture.py -x -q && uv run python -c "from screener.indicators.trend import sma_panel, _safe_sma; from screener.indicators.volatility import atr_panel, adr_pct_panel, _safe_atr; from screener.indicators.volume import obv_panel, dryup_ratio_panel, _safe_obv; from screener.indicators.relative_strength import rs_panel; print('OK')"` | ❌ W0 (indicators/ modules created in this task) | ⬜ pending |
| T03.2 | 03-03 | 2 | IND-01, IND-03, IND-04, IND-05 (build_panel + Wave 0 indicator tests) | T-3-01 | NaN-warmup invariants; per-ticker shift isolation; no look-ahead in RS computation | unit | `uv run pytest tests/test_indicators_panel.py tests/test_indicators_trend.py tests/test_indicators_volatility.py tests/test_indicators_volume.py tests/test_indicators_rs.py tests/test_indicators_purity.py tests/test_architecture.py -m "not slow and not integration" -x -q` | ❌ W0 (6 indicator test files created in this task) | ⬜ pending |
| T04.1 | 03-04 | 3 | REG-01, REG-02, REG-03 (regime body) | T-3-01 (regime input validation) | Discrete state + continuous score in [0,1]; Correction overrides via if/elif priority | unit (smoke + architecture) | `uv run pytest tests/test_architecture.py -x -q && uv run python -c "from screener.regime import compute_for_date, build_history, _classify_state, _compute_distribution_days, _regime_score, RegimeState; print('OK')"` | ❌ W0 (regime.py replaced in this task) | ⬜ pending |
| T04.2 | 03-04 | 3 | REG-01, REG-02 (regime tests) | T-3-01 | regime_score boundary cases (all-good=1.0, all-bad≈0.0); distribution-day strict-IBD definition | unit | `uv run pytest tests/test_regime.py tests/test_regime_score.py -m "not slow and not integration" -x -q` | ❌ W0 (tests created in this task) | ⬜ pending |
| T05.1 | 03-05 | 3 | IND-02 (SMA-not-EMA grep gate + mutation test) | T-3-01 (CI invariant; substituted EMA fails CI) | grep filtered to non-comment lines; mutation test verifies the gate trips on ema reference | unit (shell-invoking) + CI step | `uv run pytest tests/test_ci_ema_grep_gate.py -x -q && bash -c 'if grep -ilE "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py 2>/dev/null; then echo "FAIL: ema match found"; exit 1; else echo "PASS: gate clean"; fi'` | ❌ W0 (test + ci.yml step created in this task) | ⬜ pending |
| T05.2 | 03-05 | 3 | REG-04 (golden-file regime tests) | T-3-01 | 2008-Q4 / 2020-Q1 / 2022-H1 each classify Correction at ≥1 date in their window | unit (golden-file) | `uv run pytest tests/test_regime_golden.py -x -q` | ❌ W0 (tests/test_regime_golden.py created in this task) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_indicators_panel.py` — deterministic-input → known-output tests for SMA / ATR / ADR% / OBV / dryup / RS-rating (IND-01, IND-03, IND-04) — created in T03.2
- [x] `tests/test_indicators_purity.py` — architecture test asserting `indicators/` modules import nothing from `data/` or network deps (IND-05) — created in T03.2
- [x] `tests/test_macro_refresh.py` — macro refresh idempotence + Stooq fallback path + secret-safe logging (DAT-04, D-05, D-06) — created in T02.2
- [x] `tests/test_regime.py` — golden-file fixtures for 2008-Q4, 2020-Q1, 2022-H1 (REG-04) plus distribution-day counter unit tests (REG-01) — created in T04.2 + T05.2
- [x] `tests/test_regime_score.py` — D-03 regime_score boundary cases (REG-02): all-good = 1.0, all-bad ≈ 0.0, edge clipping — created in T04.2
- [x] `tests/test_rs_snapshot.py` — RsSnapshotSchema round-trip + `read_rs_snapshot()` point-in-time read (D-10, D-11) — created in T01.3
- [x] `tests/conftest.py` — synthetic OHLCV fixture (≥260 rows for SMA200 warmup), synthetic SPY+VIX fixtures for regime golden tests — extended in T01.3 + T03.2 + T04.2
- [x] `.github/workflows/ci.yml` — EMA grep step (IND-02): `grep -i "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py` must exit non-zero (no matches) — created in T05.1

All Wave 0 obligations are inlined into plan tasks per the TDD `tdd="true"` + `<behavior>` block pattern; no separate Wave 0 plan file is required.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FRED API key live-fetch | DAT-04 (yields) | Requires `FRED_API_KEY` secret; CI runs offline | Local: `FRED_API_KEY=… make macro` then `ls data/macro/yields.parquet` |
| yfinance live-fetch for SPY/QQQ/^VIX | DAT-04 (indices) | External API, throttled, flaky in CI | Local: `make macro --force` then inspect Parquet row count + last_date |
| Stooq `$NYAD` reachability | DAT-04 (D-05) | Stooq currently broken end-to-end (RESEARCH.md Pitfall) — fallback is the operational primary | Local: run `data.macro.fetch_nyad()` and assert `nyad_source` event is logged (`stooq` or `r1000_proxy`) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (8 stub files above)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter (planner-attested after revision 2026-05-10)

**Approval:** ready (planner-attested; awaiting checker re-verification)
