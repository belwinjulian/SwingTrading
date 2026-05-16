---
phase: 5
slug: backtest-harness-no-lookahead-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-16
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Populated from 05-RESEARCH.md §"Validation Architecture" and CONTEXT.md decisions D-01..D-19 (D-07 and D-16 check #3 revised 2026-05-16).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (existing pytest section) |
| **Quick run command** | `pytest tests/test_backtest_no_lookahead.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~5s (no-lookahead test) · ~45s (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_backtest_no_lookahead.py -q` (quick gate, < 5s)
- **After every plan wave:** Run `pytest -q && ruff check src/ && mypy src/screener/indicators/ src/screener/signals/`
- **Before `/gsd-verify-work`:** Full suite must be green AND `make backtest-audit` exits 0
- **Max feedback latency:** 5 seconds (quick) · 60 seconds (full)

---

## Per-Task Verification Map

> Populated by the planner. Each row maps a planned task to its validation surface. The planner will fill task IDs once PLAN.md files are authored; this table seeds the schema.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-XX-YY | XX | W | REQ-XX | T-5-XX or — | {behavior or N/A} | unit/integration/cli | `{command}` | ❌ W0 / ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Files the planner MUST create as stubs before Wave 1 begins (so per-task verify commands resolve from the first commit):

- [ ] `tests/test_backtest_no_lookahead.py` — stubs the parameterized `_lookahead=True/False` test (FND-04, BCK-02). Stub returns `pytest.skip("Wave 1 fills body")` until vbt_runner.run() lands.
- [ ] `tests/test_walkforward_windows.py` — stubs the window-construction unit test (BCK-01). Skip stub.
- [ ] `tests/test_slippage_tiers.py` — stubs the per-ticker ADV-tiered slippage panel test (BCK-03). Skip stub.
- [ ] `tests/test_backtest_audit.py` — stubs the 4-check audit CLI test (BCK-07). Skip stub.
- [ ] `tests/conftest.py` — confirm existing fixtures still satisfy; add `synthetic_ohlcv_panel(seed=42, n_bars=250)` fixture (GBM, deterministic) usable by Wave 1 tests.
- [ ] No framework install needed — pytest 8.x + vectorbt 1.0.0 already in `pyproject.toml`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Backfill completes for 2016–today range | BCK-01 (data depth) | One-off bulk operation (~hours of yfinance throttle); user runs once per machine, not on every commit. | `make backfill-snapshots` and confirm `ls data/snapshots/ \| wc -l` ≥ 2,500 trading days. |
| OOS Sharpe distribution sanity-check vs published industry baselines | BCK-01 | Domain judgment — the planner can verify the number is computed, but only the user can decide whether 0.6 / 0.8 / 1.2 Sharpe is "reasonable" for the strategy. | After `make backtest`, read the OOS table in `reports/backtest-YYYY-MM-DD.md`. Sanity-check median Sharpe against ~0.5–1.5 published swing-trading benchmarks. |
| Disclosure header completeness (BCK-06) | BCK-06 | Disclosure quality is a judgment call about communication style, not a mechanical assertion. | Eyeball `reports/backtest-YYYY-MM-DD.md` header for: universe source date, survivorship caveat phrasing, slippage tiers, IS/OOS period table. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (4 test stubs + conftest fixture)
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s for quick gate, < 60s for full suite
- [ ] `nyquist_compliant: true` set in frontmatter after planner fills per-task map

**Approval:** pending
