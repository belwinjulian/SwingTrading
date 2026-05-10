---
phase: 3
slug: indicator-panel-regime
status: draft
nyquist_compliant: false
wave_0_complete: false
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

> Populated by gsd-planner — table is filled with one row per task using the matrix below.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD     | TBD  | TBD  | TBD         | TBD        | TBD             | unit      | TBD               | ❌ W0       | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_indicators_panel.py` — deterministic-input → known-output tests for SMA / ATR / ADR% / OBV / dryup / RS-rating (IND-01, IND-03, IND-04)
- [ ] `tests/test_indicators_purity.py` — architecture test asserting `indicators/` modules import nothing from `data/` or network deps (IND-05)
- [ ] `tests/test_macro_refresh.py` — macro refresh idempotence + Stooq fallback path (DAT-04, D-05, D-06)
- [ ] `tests/test_regime.py` — golden-file fixtures for 2008-Q4, 2020-Q1, 2022-H1 (REG-04) plus distribution-day counter unit tests (REG-01)
- [ ] `tests/test_regime_score.py` — D-03 regime_score boundary cases (REG-02): all-good = 1.0, all-bad ≈ 0.0, edge clipping
- [ ] `tests/test_rs_snapshot.py` — RsSnapshotSchema round-trip + `read_rs_snapshot()` point-in-time read (D-10, D-11)
- [ ] `tests/conftest.py` — synthetic OHLCV fixture (≥260 rows for SMA200 warmup), synthetic SPY+VIX fixtures for regime golden tests
- [ ] `.github/workflows/ci.yml` — EMA grep step (IND-02): `grep -i "ema" src/screener/signals/minervini.py src/screener/indicators/trend.py` must exit non-zero (no matches)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FRED API key live-fetch | DAT-04 (yields) | Requires `FRED_API_KEY` secret; CI runs offline | Local: `FRED_API_KEY=… make macro` then `ls data/macro/yields.parquet` |
| yfinance live-fetch for SPY/QQQ/^VIX | DAT-04 (indices) | External API, throttled, flaky in CI | Local: `make macro --force` then inspect Parquet row count + last_date |
| Stooq `$NYAD` reachability | DAT-04 (D-05) | Stooq currently broken end-to-end (RESEARCH.md Pitfall) — fallback is the operational primary | Local: run `data.macro.fetch_nyad()` and assert `nyad_source` event is logged (`stooq` or `r1000_proxy`) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (8 stub files above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter (set by gsd-nyquist-auditor or planner)

**Approval:** pending
